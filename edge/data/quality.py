"""Data quality checks on the canonical M1 store: coverage, gaps, duplicates, spikes."""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from . import store
from .universe import asset_class

log = logging.getLogger(__name__)

# Days the FX market is closed or nearly so; a missing day here is not a data problem.
_KNOWN_CLOSED = {(1, 1), (12, 25)}


def _expected_weekdays(start: date, end: date) -> set[date]:
    days = set()
    d = start
    while d <= end:
        if d.weekday() < 5 and (d.month, d.day) not in _KNOWN_CLOSED:
            days.add(d)
        d += timedelta(days=1)
    return days


def check_symbol(sym: str, spike_threshold: float | None = None) -> dict:
    df = pl.read_parquet(store.m1_path(sym))
    ts = df.get_column("ts")
    n = df.height
    start, end = ts.min(), ts.max()
    present_days = set(ts.dt.date().unique().to_list())
    missing = sorted(_expected_weekdays(start.date(), end.date()) - present_days)

    cls = asset_class(sym)
    thr = spike_threshold if spike_threshold is not None else (0.01 if cls == "fx" else 0.03)
    ret = (pl.col("bid_c") / pl.col("bid_c").shift(1) - 1).abs()
    spikes = df.select(((ret > thr) & (pl.col("ts").diff().dt.total_minutes() <= 5)).sum()).item()

    neg_spread = 0
    if df["ask_c"].is_not_null().any():
        neg_spread = df.select(((pl.col("ask_c") - pl.col("bid_c")) < 0).sum()).item()

    bad_ohlc = df.select(
        ((pl.col("bid_h") < pl.max_horizontal("bid_o", "bid_c")) | (pl.col("bid_l") > pl.min_horizontal("bid_o", "bid_c"))).sum()
    ).item()

    return {
        "symbol": sym,
        "rows": n,
        "start": str(start),
        "end": str(end),
        "days": len(present_days),
        "missing_weekdays": len(missing),
        "missing_weekdays_sample": [str(d) for d in missing[:12]],
        "dup_ts": n - ts.n_unique(),
        "unsorted": int(not ts.is_sorted()),
        "ask_coverage": round(float(df["ask_c"].is_not_null().mean()), 4),
        "zero_vol_share": round(float((df["vol"] == 0).mean()), 6),
        "spikes_over_threshold": int(spikes),
        "spike_threshold": thr,
        "negative_spreads": int(neg_spread),
        "bad_ohlc": int(bad_ohlc),
        "rows_legacy": int((df["src"] == store.SRC_LEGACY).sum()),
    }


def report(symbols: list[str] | None = None, out_dir: Path = store.REPORT_DIR) -> list[dict]:
    symbols = symbols or store.list_m1_symbols()
    rows = []
    for sym in symbols:
        try:
            rows.append(check_symbol(sym))
        except Exception as exc:  # keep going; one bad file should not hide the others
            log.error("%s: %s", sym, exc)
            rows.append({"symbol": sym, "error": str(exc)})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m1_quality.json").write_text(json.dumps(rows, indent=2))
    lines = [
        "# M1 store quality",
        "",
        "| Symbol | Rows | Start | End | Days | Missing weekdays | Dup ts | Ask cov | Spikes | Neg spread | Bad OHLC | Legacy rows |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['symbol']} | ERROR: {r['error']} |")
            continue
        lines.append(
            f"| {r['symbol']} | {r['rows']:,} | {r['start'][:10]} | {r['end'][:10]} | {r['days']} | "
            f"{r['missing_weekdays']} | {r['dup_ts']} | {r['ask_coverage']:.0%} | {r['spikes_over_threshold']} | "
            f"{r['negative_spreads']} | {r['bad_ohlc']} | {r['rows_legacy']:,} |"
        )
    (out_dir / "m1_quality.md").write_text("\n".join(lines) + "\n")
    return rows
