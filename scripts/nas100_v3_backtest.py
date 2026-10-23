"""Backtest the user's NAS100 v3 range-breakout rules (strategies/user/nas100_orb_v3.py) on Dukascopy US100 M5.

Costs: Dukascopy bid/ask spread inside the fills, 1 index point slippage on market and stop fills, no commission,
financing per 17:00 New York rollover (long pays Fed funds + 2.5 %/yr, short receives Fed funds - 2.5 %/yr,
Wednesday x3). Stress: one extra point of spread per trade (a wider prop-firm feed).
Prop odds: Alpha Swing $10k (config/prop_firms.yaml, daily loss on equity including open trades).

    .venv\\Scripts\\python.exe scripts\\nas100_v3_backtest.py
Writes runs/nas100_v3/report.md, trades.csv, equity.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from edge.engine import prop  # noqa: E402
from edge.engine.backtest import backtest, get_market, load_strategy  # noqa: E402
from edge.engine.costs import CostModel  # noqa: E402

SYM, TF = "USATECHIDXUSD", "M5"
OUT = ROOT / "runs" / "nas100_v3"
PERIODS = [("2013-05 to 2017", 2013, 2017), ("2018-2023", 2018, 2023), ("2024-2026", 2024, 2026), ("all", 2013, 2026)]
RISKS = [0.5, 1.0, 1.5, 2.0]


def stats(t: pl.DataFrame, col: str = "r_net") -> dict:
    if t.height == 0:
        return {"n": 0}
    r = t.get_column(col).to_numpy()
    cum = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:] - cum))
    streak = best = 0
    for x in r:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    win = r > 0
    pf = r[win].sum() / -r[~win].sum() if (~win).any() and r[~win].sum() < 0 else float("inf")
    return {"n": len(r), "win": 100 * win.mean(), "avg": r.mean(), "t": r.mean() / (r.std(ddof=1) / np.sqrt(len(r))),
            "total": r.sum(), "pf": pf, "dd": dd, "streak": best}


def row(name: str, s: dict) -> str:
    if s["n"] == 0:
        return f"| {name} | 0 | | | | | | | |"
    return (f"| {name} | {s['n']} | {s['win']:.1f} | {s['avg']:+.3f} | {s['t']:+.2f} | {s['total']:+.1f} | {s['pf']:.2f} | "
            f"{s['dd']:.1f} | {s['streak']} |")


HDR = ("| period | trades | win % | avg R | t | total R | profit factor | max drawdown R | longest losing run |\n"
       "|---|---|---|---|---|---|---|---|---|")


def year_col(t: pl.DataFrame) -> pl.DataFrame:
    return t.with_columns(pl.col("entry_ts").dt.convert_time_zone("America/New_York").dt.year().alias("year"))


def period(t: pl.DataFrame, y0: int, y1: int) -> pl.DataFrame:
    return t.filter((pl.col("year") >= y0) & (pl.col("year") <= y1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mod = load_strategy(ROOT / "strategies" / "user" / "nas100_orb_v3.py")
    m = get_market(SYM, TF)
    lines = ["# NAS100 v3 range breakout - backtest", "",
             f"Data: Dukascopy US100 CFD, 5-minute bid/ask, {str(m.ts[0])[:10]} to {str(m.ts[-1])[:10]} "
             "(the 07:00-10:00 New York range only exists from 2013-05). Rules: strategies/user/nas100_orb_v3.py.",
             "Costs: spread in the fills, 1 pt slippage per market/stop fill, no commission, overnight financing "
             "(Fed funds +/- 2.5 %/yr). R = net result divided by the stop distance.", ""]

    runs = {}
    for mode in ("as_written", "chase", "off"):
        res = backtest(mod, SYM, TF, {"skip_mode": mode}, CostModel(), market=m)
        runs[mode] = (year_col(res.trades), dict(mod.DIAG))
    t, diag = runs["as_written"]
    t.write_csv(OUT / "trades.csv")

    lines += ["## Day counts", "",
              f"Weekdays {diag['weekdays']}; range incomplete (no data / holidays) {diag['range_incomplete']}; "
              f"no confirmed break by 16:55 {diag['no_break']}; skip rule fired {diag['skipped']}; "
              f"confirmed breaks {diag['signals']}; traded {t.height} (the rest came while a trade was open); "
              f"failed confirmations {diag['failed_confirms']}.", ""]

    lines += ["## Results as written (net of costs)", "", HDR]
    for name, y0, y1 in PERIODS:
        lines.append(row(name, stats(period(t, y0, y1))))

    # zero-cost rerun: frictionless R (no spread, slippage or financing), to show what costs take
    free = CostModel(slippage_points_cfd=0.0, include_swap=False)
    mid = m._copy(slice(None))
    mid.ask_o, mid.ask_h, mid.ask_l, mid.ask_c = m.bid_o.copy(), m.bid_h.copy(), m.bid_l.copy(), m.bid_c.copy()
    tf_ = year_col(backtest(mod, SYM, TF, {}, free, market=mid).trades)
    lines += ["", "## Frictionless (no spread, slippage or financing)", "", HDR]
    for name, y0, y1 in PERIODS:
        lines.append(row(name, stats(period(tf_, y0, y1))))

    lines += ["", "## By year", "", "| year | trades | win % | avg R net | total R net | avg R frictionless | "
              "avg stop (points) | avg spread at entry (points) | financing R per trade |", "|---|---|---|---|---|---|---|---|---|"]
    for y in sorted(t.get_column("year").unique().to_list()):
        ty = t.filter(pl.col("year") == y)
        fy = tf_.filter(pl.col("year") == y)
        s = stats(ty)
        lines.append(f"| {y} | {s['n']} | {s['win']:.1f} | {s['avg']:+.3f} | {s['total']:+.1f} | {fy['r_net'].mean():+.3f} | "
                     f"{ty['risk'].mean():.1f} | {ty['spread_entry'].mean():.2f} | {ty['swap_r'].mean():+.3f} |")

    # wider-spread stress: one more point paid per trade
    ts_ = t.with_columns((pl.col("r_net") - 1.0 / pl.col("risk")).alias("r_net"))
    lines += ["", "## Stress: +1 point spread per trade", "", HDR]
    for name, y0, y1 in PERIODS:
        lines.append(row(name, stats(period(ts_, y0, y1))))

    lines += ["", "## Skip-rule readings (net)", "",
              "as_written: buy skipped if the confirming close < break low - 2 (sell: > break high + 2). "
              "chase: buy skipped if the confirming close > break high + 2 (sell: < break low - 2). off: no filter.", "",
              HDR.replace("period", "reading / period")]
    for mode, (tm, dg) in runs.items():
        for name, y0, y1 in PERIODS[1:]:
            lines.append(row(f"{mode} ({dg['skipped']} skips) {name}", stats(period(tm, y0, y1))))

    lines += ["", "## Long vs short (net, 2018-2026)", "", HDR.replace("period", "side")]
    recent = period(t, 2018, 2026)
    for side, nm in ((1, "long"), (-1, "short")):
        lines.append(row(nm, stats(recent.filter(pl.col("side") == side))))

    hold_h = (t["exit_ts"] - t["entry_ts"]).dt.total_minutes().to_numpy() / 60
    lines += ["", "## Holding", "",
              f"Median hold {np.median(hold_h):.1f} h, mean {hold_h.mean():.1f} h, 90th percentile {np.percentile(hold_h, 90):.1f} h, "
              f"longest {hold_h.max() / 24:.1f} days; {100 * (t['nights'] > 0).mean():.0f}% of trades held overnight; "
              f"exits: {dict(zip(*t.group_by('reason').len().sort('reason').to_dict(as_series=False).values()))}; "
              f"average financing {t['swap_r'].mean():+.3f} R per trade.", ""]

    rules = prop.PropRules.load()
    lines += ["## Alpha Swing $10k (phase 1 +10 %, phase 2 +5 %, 5 % daily on equity, 10 % max)", "",
              "| risk per trade | starts from | challenges | pass <= 1m % | pass <= 2m % | fail <= 2m % | pass eventually % | "
              "median months to pass |", "|---|---|---|---|---|---|---|---|"]
    trades_p = t.select("entry_ts", "exit_ts", "r_net", "mae_r")
    for risk in RISKS:
        out = prop.simulate([prop.Leg("v3", trades_p, risk)], rules)
        out = out.with_columns(pl.Series("start_ts", np.array(out["start_ts"].to_list(), dtype="datetime64[us]")))
        for since in ("2018-01-01", "2021-01-01"):
            o = out.filter(pl.col("start_ts") >= datetime.fromisoformat(since))
            s = prop.summarize(o)
            lines.append(f"| {risk}% | {since[:4]} | {s['challenges']} | {s['pass_le_1m_pct']:.1f} | {s['pass_le_2m_pct']:.1f} | "
                         f"{s['fail_le_2m_pct']:.1f} | {s['pass_eventually_pct']:.1f} | {s['median_months_to_pass']:.1f} |")

    _plot(t, tf_, OUT / "equity.png")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def _plot(t: pl.DataFrame, free: pl.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = t["entry_ts"].to_numpy()
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=120)
    ax.plot(x, np.cumsum(t["r_net"].to_numpy()), color="#2a6fdb", lw=1.6, label="net of costs")
    ax.plot(free["entry_ts"].to_numpy(), np.cumsum(free["r_net"].to_numpy()), color="#e8833a", lw=1.2, alpha=0.9,
            label="zero costs (no spread, slippage or financing)")
    ax.axhline(0, color="#888", lw=0.8)
    ax.set_title("NAS100 v3 breakout - cumulative R per trade (1 R = the stop)", loc="left", fontsize=11)
    ax.set_ylabel("cumulative R")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
