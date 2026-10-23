"""Rebuild the approved USDJPY basket legs with the gj-strat engine from this project's minute store.

Legs (reference/gj-strat/run_m3_addon.build_legs, costs $7/lot, swap +1%, 0.2 pip slippage):
  vol_box     Tokyo-open box breakout Version B (RR 9, BE at 3R, re-entry at the box level), ATR20 >= 250-day median
  vol_gotobi  gotobi Tokyo-fix short (00:55-06:00 UTC, SL 0.25 x ATR20), same vol filter
  fade        box fade Version C (RR 5, no BE), every day
  m3          month-end USD bid, 3rd-last weekday 11:00-12:00 UTC, SL 0.25 x ATR20
Adds the intraday worst excursion per trade (mae_r, bid lows for longs / ask highs for shorts, entry bar
included) so the prop simulator can mark the daily loss to market. Writes runs/basket/legs/<leg>.parquet.

    .venv\Scripts\python.exe scripts\basket_legs.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
GJ = ROOT / "reference" / "gj-strat"
sys.path.insert(0, str(GJ))

from gjstrat.accounting import account            # noqa: E402
from gjstrat.data import Market, to_grid           # noqa: E402
from gjstrat.engine import Params, run, trading_days  # noqa: E402
from gjstrat.patterns import daily_table, gotobi_short, month_end_usd_bid, simulate  # noqa: E402
from gjstrat.swap import SwapModel                 # noqa: E402

OUT = ROOT / "runs" / "basket" / "legs"
SYM = "USDJPY"


def market_from_store(sym: str = SYM) -> Market:
    t = pl.read_parquet(ROOT / "data" / "m1" / f"{sym}.parquet")
    df = t.to_pandas()
    idx = pd.DatetimeIndex(df["ts"]).tz_convert("UTC").tz_localize(None)
    bid = pd.DataFrame({"o": df["bid_o"].to_numpy(), "h": df["bid_h"].to_numpy(), "l": df["bid_l"].to_numpy(),
                        "c": df["bid_c"].to_numpy(), "v": df["vol"].to_numpy()}, index=idx)
    ask = pd.DataFrame({"o": df["ask_o"].to_numpy(), "h": df["ask_h"].to_numpy(), "l": df["ask_l"].to_numpy(),
                        "c": df["ask_c"].to_numpy(), "v": df["vol"].to_numpy()}, index=idx)
    last_live = bid.index[bid["v"] > 0][-1]
    bid, ask = bid.loc[:last_live], ask.loc[:last_live]
    conv = bid["c"] if sym.startswith("USD") else 1.0       # quote currency per USD
    return to_grid(bid, ask, conv, pip=0.01 if sym.endswith("JPY") else 0.0001)


def mae_r(m: Market, t) -> float:
    lo, hi = t.entry_i, t.exit_i
    if t.side == "BUY":
        adverse = t.entry - float(np.min(m.bl[lo:hi + 1]))
    else:
        adverse = float(np.max(m.ah[lo:hi + 1])) - t.entry
    return max(adverse, 0.0) / t.risk


def export(name: str, m: Market, trades: list, sw: SwapModel) -> pl.DataFrame:
    tr = sorted(trades, key=lambda t: (t.exit_i, t.entry_i))
    acc = account(tr, m, 10_000, commission=7, swap=sw, sym=SYM, slippage_pips=0.2)
    r_net = acc["R"].to_numpy()
    rows = {
        "leg": [name] * len(tr),
        "day": [t.day for t in tr],
        "side": [t.side for t in tr],
        "entry_ts": [m.ts(t.entry_i) for t in tr],
        "exit_ts": [m.ts(t.exit_i) for t in tr],
        "entry_px": [t.entry for t in tr], "exit_px": [t.exit for t in tr],
        "risk_pips": [t.risk / m.pip for t in tr],
        "r_gross": [t.r for t in tr], "r_net": r_net,
        "mae_r": [mae_r(m, t) for t in tr],
        "reason": [t.reason for t in tr], "be_moved": [t.be_moved for t in tr],
        "swap_usd": acc["swap_usd"].to_numpy(), "lots_at_10k_1pct": acc["lots"].to_numpy(),
    }
    out = pl.DataFrame(rows).with_columns(pl.col("entry_ts").dt.replace_time_zone("UTC"),
                                          pl.col("exit_ts").dt.replace_time_zone("UTC"),
                                          pl.col("day").cast(pl.Date))
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_parquet(OUT / f"{name}.parquet")
    return out


def period_stats(df: pl.DataFrame) -> str:
    bits = []
    for label, lo, hi in (("design", "2010-01-01", "2018-01-01"), ("check", "2018-01-01", "2024-01-01"), ("holdout", "2024-01-01", "2027-01-01")):
        sub = df.filter((pl.col("day") >= pl.lit(lo).str.to_date()) & (pl.col("day") < pl.lit(hi).str.to_date()))
        r = sub.get_column("r_net").to_numpy()
        t = r.mean() / r.std(ddof=1) * np.sqrt(len(r)) if len(r) > 2 and r.std(ddof=1) > 0 else float("nan")
        bits.append(f"{label} n={len(r)} avgR={r.mean():+.3f} t={t:.2f}" if len(r) else f"{label} n=0")
    return "; ".join(bits)


def main() -> None:
    t0 = time.time()
    m = market_from_store()
    print(f"market {SYM}: {m.n:,} minutes from {m.t0} ({time.time() - t0:.0f}s)", flush=True)
    sw = SwapModel.from_fred(str(ROOT / "data" / "rates"), 1.0)
    d = daily_table(m)
    d11 = d[d.index >= pd.Timestamp("2011-01-01")]
    days = trading_days(m, start="2010-01-01")
    _, pr = run(m, Params(sl_box_mult=1.0), days)
    sk = {x for x, _ in pr.skipped_dates}
    days = [x for x in days if x.date() not in sk]
    print(f"trading days {len(days)} (skipped {len(sk)}) ({time.time() - t0:.0f}s)", flush=True)
    base = dict(sl_pips=30, be_plus=5, sl_box_mult=1.0)
    box, _ = run(m, Params(rr=9, be_trigger=3, version="B", **base), days)
    print(f"box trades {len(box)} ({time.time() - t0:.0f}s)", flush=True)
    fade, _ = run(m, Params(rr=5, be_trigger=None, version="C", fade_expiry_11=True, **base), days)
    print(f"fade trades {len(fade)} ({time.time() - t0:.0f}s)", flush=True)
    med = d["atr20"].rolling(250, min_periods=250).median()
    hot = lambda t: d["atr20"].get(t.day, np.nan) >= med.get(t.day, np.nan)   # noqa: E731
    got = [t for t in (simulate(m, s) for s in gotobi_short(m, d11)) if t is not None]
    m3 = [t for t in (simulate(m, s) for s in month_end_usd_bid(m, d11, "BUY")) if t is not None]
    legs = {"vol_box": [t for t in box if hot(t)], "vol_gotobi": [t for t in got if hot(t)], "fade": fade, "m3": m3}
    for name, tr in legs.items():
        df = export(name, m, tr, sw)
        print(f"{name}: {df.height} trades, avg R {df['r_net'].mean():+.3f}, mean mae_r {df['mae_r'].mean():.2f}; {period_stats(df)}", flush=True)
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
