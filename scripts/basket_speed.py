"""Size the parked USDJPY basket for the 60-day objective (config/goal.yaml, 2026-10-14) with the prop simulator.

Fixed before running (pre-registered):
  legs      runs/basket/legs/{vol_box,vol_gotobi,fade,m3}.parquet (scripts/basket_legs.py; gj-strat engine, all costs)
  rules     config/prop_firms.yaml alpha_swing_10k (P1 +10%, P2 +5%, 10% static, 5% daily on the closed balance,
            day resets 17:00 New York, >= 3 trading days per phase); floating daily rule as a stress
  windows   challenge starts from 2010 ('all'), 2018-01-01 ('2018', the goal window) and 2021-01-01 ('2021'),
            all up to 2025-10-07
  family A  static risk per leg, in percent of balance: vol_box {0.25, 0.5} x vol_gotobi {2, 3, 4, 4.9} x fade {0, 0.5}
            x m3 {3, 4}; 4.9 is the largest single-trade risk that cannot breach the 5% daily limit on one stop
  family B  dynamic schemes on the base no-fade mix (0.25 / 3 / 0 / 3) and on the best static mix under the ruin
            ceiling, through the simulator's scale callback (the callback sees the phase balance, reset to 1.0 at
            each phase start, and the phase target):
              boost     risk x 1.5 while the phase balance is below 1 + target / 2 (the first half of the target)
              p2half    risk x 0.5 in phase 2 (its target is half of phase 1's)
              protect   risk x 0.5 while the phase balance is below 0.97
              finish    risk x 1.5 once the phase balance is at or above 1 + 0.7 x target
              boost+protect, boost+p2half
  metrics   pass <= 1/2/3/6 months, fail <= 2/6 months, pass eventually, median months to pass, months per funded
            account, attempts per funded account (finished / passed) and fees per funded account at $100 an attempt
            (the fee is a placeholder: set FEE to the real Alpha Swing $10k fee)
  accept    goal.yaml on the 2018 window with the closed-balance rule: pass <= 2m >= 50%, fail <= 2m <= 15%,
            pass eventually >= 60%; rank by pass <= 2m. If nothing qualifies, report the frontier: the best
            pass <= 2m at ruin ceilings of 5, 10, 15 and 25%, and recommend the best mix under 15% that also
            keeps fail <= 2m under 20% with the floating rule and on the 2021 window
  stress    top mixes: floating daily rule, +0.3 pip slippage per trade, half of every leg's average edge removed
  bootstrap resample calendar years of challenge starts with replacement (1000 draws) for the recommended mix and
            the base mix: 10/50/90th percentiles of pass <= 2m and fail <= 2m
Outputs runs/basket/speed_table.csv, speed_dynamic.csv, speed_bootstrap.csv, speed_report.md.

    .venv/Scripts/python.exe scripts/basket_speed.py
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edge.engine.prop import Leg, PropRules, simulate, summarize  # noqa: E402
from edge.research.portfolio import load_goal                     # noqa: E402

LEG_DIR = ROOT / "runs" / "basket" / "legs"
OUT = ROOT / "runs" / "basket"
LEGS = ("vol_box", "vol_gotobi", "fade", "m3")
GRID = {"vol_box": (0.25, 0.5), "vol_gotobi": (2.0, 3.0, 4.0, 4.9), "fade": (0.0, 0.5), "m3": (3.0, 4.0)}
BASE = (0.25, 3.0, 0.0, 3.0)          # the mix recommended for the live account on 2026-10-14
INCUMBENT = (0.25, 3.0, 0.5, 3.0)
WINDOWS = {"all": None, "2018": "2018-01-01", "2021": "2021-01-01"}
LAST_START = "2025-10-07"
FEE = 100.0
STRESS = ("closed", "floating", "slip+0.3pip", "half_edge")
KEEP = ("challenges", "pass_le_1m_pct", "pass_le_2m_pct", "pass_le_3m_pct", "pass_le_6m_pct", "fail_le_2m_pct",
        "fail_le_6m_pct", "pass_eventually_pct", "median_months_to_pass", "months_per_funded_account",
        "fail_daily_pct", "fail_max_pct")
RUIN_CEILINGS = (5.0, 10.0, 15.0, 25.0)

_LEGS: dict[str, pl.DataFrame] = {}


def load_legs() -> dict[str, pl.DataFrame]:
    out = {}
    for name in LEGS:
        t = pl.read_parquet(LEG_DIR / f"{name}.parquet")
        out[name] = t.select("entry_ts", "exit_ts", "r_net", "mae_r", "risk_pips").sort("entry_ts")
    return out


def transform(t: pl.DataFrame, stress: str) -> pl.DataFrame:
    if stress == "slip+0.3pip":
        return t.with_columns((pl.col("r_net") - 0.3 / pl.col("risk_pips")).alias("r_net"))
    if stress == "half_edge":
        return t.with_columns((pl.col("r_net") - 0.5 * pl.col("r_net").mean()).alias("r_net"))
    return t


def fmt_mix(mix: tuple) -> str:
    return " / ".join(f"{n} {r:g}%" for n, r in zip(LEGS, mix) if r > 0)


def make_legs(mix: tuple, since: str | None, stress: str = "closed") -> list[Leg]:
    legs = []
    for name, risk in zip(LEGS, mix):
        if risk <= 0:
            continue
        t = transform(_LEGS[name], stress)
        if since:
            t = t.filter(pl.col("entry_ts") >= pl.lit(since).str.to_datetime(time_zone="UTC"))
        legs.append(Leg(name, t, float(risk)))
    return legs


# ------------------------------------------------------------------------------------------------- dynamic schemes
def scheme(name: str):
    """scale(pct, bal, phase, target) -> pct. bal is the phase balance (1.0 at the phase start); target the phase
    target as a fraction (0.10, 0.05)."""
    parts = name.split("+")

    def f(pct: float, bal: float, phase: int, target: float) -> float:
        out = pct
        if "boost" in parts and bal < 1.0 + target / 2.0:
            out *= 1.5
        if "finish" in parts and bal >= 1.0 + 0.7 * target:
            out *= 1.5
        if "p2half" in parts and phase >= 1:
            out *= 0.5
        if "protect" in parts and bal < 0.97:
            out *= 0.5
        return out

    return None if name == "static" else f


SCHEMES = ("static", "boost", "p2half", "protect", "finish", "boost+protect", "boost+p2half")


def outcomes(mix: tuple, window: str, stress: str = "closed", sch: str = "static") -> pl.DataFrame:
    rules = PropRules.load("alpha_swing_10k")
    legs = make_legs(mix, WINDOWS[window], stress)
    return simulate(legs, rules, LAST_START, include_floating=(stress == "floating"), scale=scheme(sch))


def economics(s: dict) -> dict:
    passed = s["pass_eventually_pct"] / 100.0
    attempts = (1.0 / passed) if passed > 0 else float("inf")
    return {"attempts_per_funded": attempts, "fees_per_funded_usd": FEE * attempts}


def run_one(job: tuple) -> dict:
    mix, window, stress, sch = job
    s = summarize(outcomes(mix, window, stress, sch), months=(1, 2, 3, 6))
    return {"vol_box": mix[0], "vol_gotobi": mix[1], "fade": mix[2], "m3": mix[3], "mix": fmt_mix(mix),
            "window": window, "stress": stress, "scheme": sch, **{k: s[k] for k in KEEP}, **economics(s)}


def bootstrap(out: pl.DataFrame, draws: int = 1000, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    starts = np.array(out.get_column("start_ts").to_list(), dtype="datetime64[us]")
    res = out.get_column("result").to_numpy().astype(str)
    days = out.get_column("days").to_numpy().astype(float)
    year = starts.astype("datetime64[Y]").astype(int) + 1970
    years = np.unique(year)
    idx = {int(y): np.flatnonzero(year == y) for y in years}
    keys = ("pass_le_2m_pct", "fail_le_2m_pct", "pass_eventually_pct", "months_per_funded_account")
    acc = {k: [] for k in keys}
    for _ in range(draws):
        pick = np.concatenate([idx[int(y)] for y in rng.choice(years, size=len(years), replace=True)])
        s = summarize(pl.DataFrame({"result": res[pick], "days": days[pick]}), months=(1, 2, 3, 6))
        for k in keys:
            acc[k].append(s[k])
    out_: dict = {}
    for k in keys:
        a = np.array(acc[k], dtype=float)
        a = a[np.isfinite(a)]
        for q in (10, 50, 90):
            out_[f"{k}_p{q}"] = float(np.percentile(a, q)) if a.size else float("nan")
    return out_


def row(r: dict, label: str = "") -> str:
    return (f"| {label}{r['mix']} | {r['pass_le_1m_pct']:.0f} | {r['pass_le_2m_pct']:.0f} | {r['fail_le_2m_pct']:.0f} | "
            f"{r['pass_le_3m_pct']:.0f} | {r['fail_le_6m_pct']:.0f} | {r['pass_eventually_pct']:.0f} | "
            f"{r['median_months_to_pass']:.1f} | {r['months_per_funded_account']:.1f} | {r['fees_per_funded_usd']:.0f} | "
            f"{r['fail_daily_pct']:.0f} |")


HEADER = ("| mix | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | "
          "median months to pass | months per funded | fees per funded $ | fail daily % |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|")


def main() -> None:
    t0 = time.time()
    global _LEGS
    _LEGS = load_legs()
    goal = load_goal()
    OUT.mkdir(parents=True, exist_ok=True)
    rules = PropRules.load("alpha_swing_10k")

    mixes = [m for m in itertools.product(*(GRID[n] for n in LEGS))]
    for extra in (BASE, INCUMBENT):
        if extra not in mixes:
            mixes.append(extra)
    jobs = [(m, w, s, "static") for m in mixes for w in WINDOWS for s in ("closed", "floating")]
    rows = [run_one(j) for j in jobs]
    table = pl.DataFrame(rows)
    table.write_csv(OUT / "speed_table.csv")
    print(f"family A: {len(mixes)} mixes, {len(jobs)} simulations ({time.time() - t0:.0f}s)", flush=True)

    w18 = table.filter((pl.col("window") == "2018") & (pl.col("stress") == "closed"))
    ok = w18.filter((pl.col("pass_le_2m_pct") >= goal["pass_le_2m_min_pct"]) & (pl.col("fail_le_2m_pct") <= goal["fail_le_2m_max_pct"])
                    & (pl.col("pass_eventually_pct") >= goal["pass_eventually_min_pct"]))
    lines = ["# USDJPY basket: sizing for a pass within 60 days (Alpha Swing $10k)", "",
             f"Rules: {rules.firm} {rules.plan}; daily loss on the closed balance (floating = stress); day resets 17:00 New York; "
             f"challenge starts up to {LAST_START}; fee placeholder ${FEE:.0f} per attempt. Goal: {goal}", "",
             f"## Family A: {len(mixes)} static mixes on the 2018 window, closed rule. Mixes meeting the goal: {ok.height}", "",
             "Sorted by pass <= 2m. Risk per leg in percent of balance.", "", HEADER]
    for r in w18.sort("pass_le_2m_pct", descending=True).to_dicts():
        lines.append(row(r))

    lines += ["", "### Frontier: best pass <= 2m under a ruin ceiling (fail <= 2m), 2018 window, closed rule", "",
              "| fail <=2m ceiling | best mix | pass <=2m % | fail <=2m % | pass eventually % | months per funded |", "|---|---|---|---|---|---|"]
    for c in RUIN_CEILINGS:
        f = w18.filter(pl.col("fail_le_2m_pct") <= c).sort("pass_le_2m_pct", descending=True)
        if f.height:
            r = f.row(0, named=True)
            lines.append(f"| {c:.0f}% | {r['mix']} | {r['pass_le_2m_pct']:.1f} | {r['fail_le_2m_pct']:.1f} | {r['pass_eventually_pct']:.1f} | {r['months_per_funded_account']:.1f} |")

    # recommendation rule: best pass<=2m with fail<=2m <= 15 on 2018 closed, and fail<=2m <= 20 on 2018 floating and on 2021 closed
    def lookup(mix_s: str, window: str, stress: str) -> dict:
        return table.filter((pl.col("mix") == mix_s) & (pl.col("window") == window) & (pl.col("stress") == stress)).row(0, named=True)

    cands = []
    for r in w18.filter(pl.col("fail_le_2m_pct") <= goal["fail_le_2m_max_pct"]).sort("pass_le_2m_pct", descending=True).to_dicts():
        fl = lookup(r["mix"], "2018", "floating")
        w21 = lookup(r["mix"], "2021", "closed")
        if fl["fail_le_2m_pct"] <= 20.0 and w21["fail_le_2m_pct"] <= 20.0:
            cands.append(r)
    rec = cands[0] if cands else w18.sort("pass_le_2m_pct", descending=True).row(0, named=True)
    rec_mix = tuple(float(rec[n]) for n in LEGS)
    lines += ["", f"## Recommended static mix under the ruin ceiling: {rec['mix']}", "",
              "| window | rule | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for w in WINDOWS:
        for s in ("closed", "floating"):
            r = lookup(rec["mix"], w, s)
            lines.append(f"| {w} | {s} | {r['pass_le_1m_pct']:.0f} | {r['pass_le_2m_pct']:.0f} | {r['fail_le_2m_pct']:.0f} | {r['pass_le_3m_pct']:.0f} | "
                         f"{r['fail_le_6m_pct']:.0f} | {r['pass_eventually_pct']:.0f} | {r['months_per_funded_account']:.1f} | {r['fail_daily_pct']:.0f} |")
    lines += ["", f"Base mix for comparison: {fmt_mix(BASE)}", "",
              "| window | rule | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for w in WINDOWS:
        for s in ("closed", "floating"):
            r = lookup(fmt_mix(BASE), w, s)
            lines.append(f"| {w} | {s} | {r['pass_le_1m_pct']:.0f} | {r['pass_le_2m_pct']:.0f} | {r['fail_le_2m_pct']:.0f} | {r['pass_le_3m_pct']:.0f} | "
                         f"{r['fail_le_6m_pct']:.0f} | {r['pass_eventually_pct']:.0f} | {r['months_per_funded_account']:.1f} | {r['fail_daily_pct']:.0f} |")

    # family B: dynamic schemes on BASE and the recommended mix
    djobs = [(m, w, "closed", sch) for m in {BASE, rec_mix} for w in ("2018", "all") for sch in SCHEMES]
    drows = [run_one(j) for j in djobs]
    dyn = pl.DataFrame(drows)
    dyn.write_csv(OUT / "speed_dynamic.csv")
    lines += ["", "## Family B: dynamic risk schemes (closed rule). boost = x1.5 in the first half of a phase target; p2half = half risk in phase 2; "
              "protect = half risk below 0.97 of the phase start; finish = x1.5 at or above 70% of the target", "",
              "| mix | scheme | window | pass <=1m % | pass <=2m % | fail <=2m % | pass <=3m % | fail <=6m % | pass eventually % | months per funded | fail daily % |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in dyn.sort(["mix", "window", "scheme"]).to_dicts():
        lines.append(f"| {r['mix']} | {r['scheme']} | {r['window']} | {r['pass_le_1m_pct']:.0f} | {r['pass_le_2m_pct']:.0f} | {r['fail_le_2m_pct']:.0f} | "
                     f"{r['pass_le_3m_pct']:.0f} | {r['fail_le_6m_pct']:.0f} | {r['pass_eventually_pct']:.0f} | {r['months_per_funded_account']:.1f} | {r['fail_daily_pct']:.0f} |")
    print(f"family B done ({time.time() - t0:.0f}s)", flush=True)

    # stress on the recommended mix, the base and the incumbent
    srows = [run_one((m, w, s, "static")) for m in {rec_mix, BASE, INCUMBENT} for w in ("2018", "all") for s in STRESS]
    st = pl.DataFrame(srows)
    lines += ["", "## Stress (pass <=2m % / fail <=2m % / pass eventually %)", "",
              "| mix | window | closed | floating | +0.3 pip slippage | half edge |", "|---|---|---|---|---|---|"]
    for m in (rec_mix, BASE, INCUMBENT):
        for w in ("2018", "all"):
            cells = []
            for s in STRESS:
                r = st.filter((pl.col("mix") == fmt_mix(m)) & (pl.col("window") == w) & (pl.col("stress") == s)).row(0, named=True)
                cells.append(f"{r['pass_le_2m_pct']:.0f} / {r['fail_le_2m_pct']:.0f} / {r['pass_eventually_pct']:.0f}")
            lines.append(f"| {fmt_mix(m)}{' (incumbent)' if m == INCUMBENT else ''} | {w} | " + " | ".join(cells) + " |")

    # bootstrap
    brows = []
    lines += ["", "## Year-block bootstrap (1000 draws), 2018 window, closed rule: p10 / p50 / p90", "",
              "| mix | pass <=2m % | fail <=2m % | pass eventually % | months per funded |", "|---|---|---|---|---|"]
    for m in (rec_mix, BASE):
        b = bootstrap(outcomes(m, "2018"))
        brows.append({"mix": fmt_mix(m), **b})
        lines.append(f"| {fmt_mix(m)} | {b['pass_le_2m_pct_p10']:.0f} / {b['pass_le_2m_pct_p50']:.0f} / {b['pass_le_2m_pct_p90']:.0f} | "
                     f"{b['fail_le_2m_pct_p10']:.0f} / {b['fail_le_2m_pct_p50']:.0f} / {b['fail_le_2m_pct_p90']:.0f} | "
                     f"{b['pass_eventually_pct_p10']:.0f} / {b['pass_eventually_pct_p50']:.0f} / {b['pass_eventually_pct_p90']:.0f} | "
                     f"{b['months_per_funded_account_p10']:.1f} / {b['months_per_funded_account_p50']:.1f} / {b['months_per_funded_account_p90']:.1f} |")
    pl.DataFrame(brows).write_csv(OUT / "speed_bootstrap.csv")

    (OUT / "speed_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done in {time.time() - t0:.0f}s -> {OUT / 'speed_report.md'}")


if __name__ == "__main__":
    main()
