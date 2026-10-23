"""Size the approved USDJPY basket for the Alpha Swing rules with this project's prop simulator.

Fixed before running (pre-registered):
  legs      runs/basket/legs/{vol_box,vol_gotobi,fade,m3}.parquet (scripts/basket_legs.py; gj-strat engine, all costs)
  rules     config/prop_firms.yaml alpha_swing_10k: P1 +10%, P2 +5%, 10% static max loss, 5% daily loss on the
            closed balance (balance-based), day resets 17:00 New York, >= 3 trading days per phase
  windows   challenge starts from the first trade (2010) and from 2018-01-01, both up to 2025-10-07, like gj-strat
  step 0    replicate the gj-strat incumbent (vol-box 0.25%, vol-gotobi 3%, fade 0.5%, M-3 3%):
            expect about 59% pass eventually / 7.3 months per funded account (all starts) and 74% / 5.8 (2018 on)
  grid      vol_box {0, 0.25, 0.5} x vol_gotobi {0, 1, 2, 3, 4} x fade {0, 0.5, 1} x m3 {0, 1, 2, 3, 4}
  accept    goal.yaml on the 2018 window with the closed-balance daily rule (pass eventually >= 60, pass <= 3m >= 25,
            fail <= 6m <= 35, months per funded <= 6) AND pass eventually >= 55 and fail <= 6m <= 35 on all starts;
            rank by months per funded account on the 2018 window, ties by lower fail <= 6m
  stress    top 5 + incumbent: daily loss marked to market (worst excursion), +0.3 pip slippage per trade,
            half of every leg's average edge removed, starts 2021 on
  bootstrap resample calendar years of challenge starts with replacement (1000 draws): 10/50/90th percentiles
Outputs runs/basket/sizing_table.csv, sizing_stress.csv, sizing_bootstrap.csv, sizing_report.md.

    .venv/Scripts/python.exe scripts/basket_sizing.py
"""
from __future__ import annotations

import itertools
import sys
import time
from multiprocessing import Pool
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
GRID = {"vol_box": (0.0, 0.25, 0.5), "vol_gotobi": (0.0, 1.0, 2.0, 3.0, 4.0), "fade": (0.0, 0.5, 1.0), "m3": (0.0, 1.0, 2.0, 3.0, 4.0)}
INCUMBENT = (0.25, 3.0, 0.5, 3.0)
WINDOWS = {"all": None, "2018": "2018-01-01", "2021": "2021-01-01"}
LAST_START = "2025-10-07"
REF = {"all": (59.1, 7.3), "2018": (74.0, 5.8)}
STRESS = ("closed", "floating", "slip+0.3pip", "half_edge")
KEEP = ("challenges", "pass_le_2m_pct", "pass_le_3m_pct", "pass_le_6m_pct", "fail_le_6m_pct", "pass_eventually_pct",
        "median_months_to_pass", "months_per_funded_account", "fail_daily_pct", "fail_max_pct")

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


def outcomes(mix: tuple, window: str, stress: str = "closed") -> pl.DataFrame:
    rules = PropRules.load("alpha_swing_10k")
    legs = make_legs(mix, WINDOWS[window], stress)
    return simulate(legs, rules, LAST_START, include_floating=(stress == "floating"))


def run_one(job: tuple) -> dict:
    mix, window, stress = job
    s = summarize(outcomes(mix, window, stress))
    return {"vol_box": mix[0], "vol_gotobi": mix[1], "fade": mix[2], "m3": mix[3], "mix": fmt_mix(mix),
            "window": window, "stress": stress, **{k: s[k] for k in KEEP}}


def init_worker() -> None:
    global _LEGS
    _LEGS = load_legs()


def bootstrap(out: pl.DataFrame, draws: int = 1000, seed: int = 7) -> dict:
    """Resample calendar years of challenge starts with replacement; percentiles of the summary stats."""
    rng = np.random.default_rng(seed)
    starts = np.array(out.get_column("start_ts").to_list(), dtype="datetime64[us]")
    res = out.get_column("result").to_numpy().astype(str)
    days = out.get_column("days").to_numpy().astype(float)
    year = starts.astype("datetime64[Y]").astype(int) + 1970
    years = np.unique(year)
    idx = {int(y): np.flatnonzero(year == y) for y in years}
    keys = ("pass_eventually_pct", "pass_le_3m_pct", "fail_le_6m_pct", "months_per_funded_account")
    acc = {k: [] for k in keys}
    for _ in range(draws):
        pick = np.concatenate([idx[int(y)] for y in rng.choice(years, size=len(years), replace=True)])
        s = summarize(pl.DataFrame({"result": res[pick], "days": days[pick]}))
        for k in keys:
            acc[k].append(s[k])
    out_: dict = {}
    for k in keys:
        a = np.array(acc[k], dtype=float)
        a = a[np.isfinite(a)]
        for q in (10, 50, 90):
            out_[f"{k}_p{q}"] = float(np.percentile(a, q)) if a.size else float("nan")
    return out_


def cell(r: dict) -> str:
    return f"{r['pass_eventually_pct']:.0f} / {r['months_per_funded_account']:.1f} / {r['fail_le_6m_pct']:.0f}"


def main() -> None:
    t0 = time.time()
    goal = load_goal()
    OUT.mkdir(parents=True, exist_ok=True)
    init_worker()
    rules = PropRules.load("alpha_swing_10k")
    lines = ["# USDJPY basket sizing for Alpha Swing $10k", "",
             f"Rules: {rules.firm} {rules.plan}; daily loss on the closed balance (floating = stress case); day resets at "
             f"17:00 New York; challenge starts up to {LAST_START}. Goal: {goal}", "",
             "## Step 0: replication of the gj-strat incumbent (vol-box 0.25 / vol-gotobi 3 / fade 0.5 / M-3 3)", "",
             "| window | pass eventually % (gj-strat) | months per funded (gj-strat) | pass <=3m % | fail <=6m % | fail daily % |",
             "|---|---|---|---|---|---|"]
    for w in ("all", "2018"):
        r = run_one((INCUMBENT, w, "closed"))
        ref = REF[w]
        lines.append(f"| {w} | {r['pass_eventually_pct']:.1f} ({ref[0]}) | {r['months_per_funded_account']:.1f} ({ref[1]}) | "
                     f"{r['pass_le_3m_pct']:.1f} | {r['fail_le_6m_pct']:.1f} | {r['fail_daily_pct']:.1f} |")
        print(lines[-1], flush=True)

    mixes = [m for m in itertools.product(*(GRID[n] for n in LEGS)) if any(x > 0 for x in m)]
    jobs = [(m, w, s) for m in mixes for w in ("all", "2018") for s in ("closed", "floating")]
    print(f"grid: {len(mixes)} mixes, {len(jobs)} simulations", flush=True)
    with Pool(10, initializer=init_worker) as pool:
        rows = pool.map(run_one, jobs, chunksize=4)
    table = pl.DataFrame(rows)
    table.write_csv(OUT / "sizing_table.csv")
    print(f"grid done ({time.time() - t0:.0f}s)", flush=True)

    closed = table.filter(pl.col("stress") == "closed")
    w18 = closed.filter(pl.col("window") == "2018")
    wall = closed.filter(pl.col("window") == "all").select(
        "mix", pl.col("pass_eventually_pct").alias("pe_all"), pl.col("fail_le_6m_pct").alias("f6_all"),
        pl.col("months_per_funded_account").alias("mpf_all"), pl.col("pass_le_3m_pct").alias("p3_all"))
    j = w18.join(wall, on="mix")
    ok = j.filter((pl.col("pass_eventually_pct") >= goal["pass_eventually_min_pct"])
                  & (pl.col("pass_le_3m_pct") >= goal["pass_le_3m_min_pct"])
                  & (pl.col("fail_le_6m_pct") <= goal["fail_le_6m_max_pct"])
                  & (pl.col("months_per_funded_account") <= goal["months_per_funded_account_max"])
                  & (pl.col("pe_all") >= 55.0) & (pl.col("f6_all") <= goal["fail_le_6m_max_pct"]))
    ranked = ok.sort(["months_per_funded_account", "fail_le_6m_pct"])
    lines += ["", f"## Step 1: grid of {len(mixes)} mixes; {ok.height} meet the goal on the 2018 window and the safety floor on all starts", "",
              "| mix | pass eventually % (2018 / all) | months per funded (2018 / all) | pass <=3m % | fail <=6m % (2018 / all) | fail daily % |",
              "|---|---|---|---|---|---|"]

    def row(r: dict, label: str = "") -> str:
        return (f"| {label}{r['mix']} | {r['pass_eventually_pct']:.1f} / {r['pe_all']:.1f} | {r['months_per_funded_account']:.1f} / {r['mpf_all']:.1f} | "
                f"{r['pass_le_3m_pct']:.1f} | {r['fail_le_6m_pct']:.1f} / {r['f6_all']:.1f} | {r['fail_daily_pct']:.1f} |")

    for r in ranked.head(15).to_dicts():
        lines.append(row(r))
    inc = j.filter(pl.col("mix") == fmt_mix(INCUMBENT)).to_dicts()[0]
    lines.append(row(inc, "incumbent: "))
    lines += ["", "Fastest mixes that fail the goal (for reference):", ""]
    for r in j.sort("months_per_funded_account").head(5).to_dicts():
        lines.append(row(r))

    top = ranked.head(5).to_dicts()
    cands = [tuple(float(r[n]) for n in LEGS) for r in top]
    if INCUMBENT not in cands:
        cands.append(INCUMBENT)
    sjobs = [(m, w, s) for m in cands for w in ("all", "2018", "2021") for s in STRESS]
    with Pool(10, initializer=init_worker) as pool:
        srows = pool.map(run_one, sjobs, chunksize=2)
    stress = pl.DataFrame(srows)
    stress.write_csv(OUT / "sizing_stress.csv")
    lines += ["", "## Step 2: stress on the top 5 and the incumbent (pass eventually % / months per funded / fail <=6m %)", "",
              "| mix | window | closed | floating | +0.3 pip slippage | half edge |", "|---|---|---|---|---|---|"]
    for m in cands:
        for w in ("all", "2018", "2021"):
            cells = []
            for s in STRESS:
                r = stress.filter((pl.col("mix") == fmt_mix(m)) & (pl.col("window") == w) & (pl.col("stress") == s)).to_dicts()[0]
                cells.append(cell(r))
            lines.append(f"| {fmt_mix(m)}{' (incumbent)' if m == INCUMBENT else ''} | {w} | " + " | ".join(cells) + " |")
    print(f"stress done ({time.time() - t0:.0f}s)", flush=True)

    brows = []
    lines += ["", "## Step 3: year-block bootstrap (1000 draws), closed-balance rule", "",
              "| mix | window | pass eventually % p10 / p50 / p90 | months per funded p10 / p50 / p90 | pass <=3m % p10 / p50 / p90 | fail <=6m % p10 / p50 / p90 |",
              "|---|---|---|---|---|---|"]
    for m in cands:
        for w in ("all", "2018"):
            b = bootstrap(outcomes(m, w))
            brows.append({"mix": fmt_mix(m), "window": w, **b})
            lines.append(f"| {fmt_mix(m)}{' (incumbent)' if m == INCUMBENT else ''} | {w} | "
                         f"{b['pass_eventually_pct_p10']:.0f} / {b['pass_eventually_pct_p50']:.0f} / {b['pass_eventually_pct_p90']:.0f} | "
                         f"{b['months_per_funded_account_p10']:.1f} / {b['months_per_funded_account_p50']:.1f} / {b['months_per_funded_account_p90']:.1f} | "
                         f"{b['pass_le_3m_pct_p10']:.0f} / {b['pass_le_3m_pct_p50']:.0f} / {b['pass_le_3m_pct_p90']:.0f} | "
                         f"{b['fail_le_6m_pct_p10']:.0f} / {b['fail_le_6m_pct_p50']:.0f} / {b['fail_le_6m_pct_p90']:.0f} |")
    pl.DataFrame(brows).write_csv(OUT / "sizing_bootstrap.csv")
    print(f"bootstrap done ({time.time() - t0:.0f}s)", flush=True)

    best = cands[0]
    lines += ["", f"## Drop-one from the best candidate ({fmt_mix(best)}), 2018 window, closed rule", "",
              "| without | pass eventually % | months per funded | pass <=3m % | fail <=6m % |", "|---|---|---|---|---|"]
    for i, n in enumerate(LEGS):
        if best[i] <= 0:
            continue
        m = tuple(0.0 if k == i else v for k, v in enumerate(best))
        if not any(x > 0 for x in m):
            continue
        r = run_one((m, "2018", "closed"))
        lines.append(f"| {n} | {r['pass_eventually_pct']:.1f} | {r['months_per_funded_account']:.1f} | {r['pass_le_3m_pct']:.1f} | {r['fail_le_6m_pct']:.1f} |")

    fl = table.filter((pl.col("stress") == "floating") & (pl.col("window") == "2018"))
    lines += ["", "## Floating (mark-to-market) daily rule, 2018 window, candidates", "",
              "| mix | pass eventually % | months per funded | fail daily % |", "|---|---|---|---|"]
    for m in cands:
        r = fl.filter(pl.col("mix") == fmt_mix(m)).to_dicts()[0]
        lines.append(f"| {fmt_mix(m)} | {r['pass_eventually_pct']:.1f} | {r['months_per_funded_account']:.1f} | {r['fail_daily_pct']:.1f} |")
    (OUT / "sizing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done in {time.time() - t0:.0f}s -> {OUT / 'sizing_report.md'}")


if __name__ == "__main__":
    main()
