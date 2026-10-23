"""Resample canonical M1 bars to higher timeframes.

Intraday bars are aligned to UTC clock boundaries (00:00, 00:15, ...), left-closed and
labelled by their open time. Daily and weekly bars are anchored to the New York 17:00 close
by default, which is how MT5 charts and most prop firms define a trading day: the session that
opens Sunday 17:00 New York belongs to Monday. Pass anchor="utc" for calendar UTC days.

Every bar carries bid and ask OHLC, summed bid tick volume and n_m1, the number of real
1-minute bars inside it, so sparse bars can be filtered.
"""
from __future__ import annotations

import logging

import polars as pl

from . import store

log = logging.getLogger(__name__)

INTRADAY: dict[str, str] = {
    "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H3": "3h", "H4": "4h", "H8": "8h", "H12": "12h",
}
DEFAULT_TFS: tuple[str, ...] = ("M5", "M15", "M30", "H1", "H4", "D1", "W1")
ALL_TFS: tuple[str, ...] = tuple(INTRADAY) + ("D1", "W1")

_AGG = [
    pl.col("bid_o").first(),
    pl.col("bid_h").max(),
    pl.col("bid_l").min(),
    pl.col("bid_c").last(),
    pl.col("ask_o").first(),
    pl.col("ask_h").max(),
    pl.col("ask_l").min(),
    pl.col("ask_c").last(),
    pl.col("vol").sum(),
    pl.len().alias("n_m1"),
]

OUT_COLUMNS = ["ts", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "vol", "n_m1"]


def trading_day_expr(ts: pl.Expr = pl.col("ts")) -> pl.Expr:
    """Date of the trading day under the New York 17:00 close convention."""
    return (ts.dt.convert_time_zone("America/New_York") + pl.duration(hours=7)).dt.date()


def resample_intraday(m1: pl.DataFrame, tf: str, offset: str = "0m") -> pl.DataFrame:
    every = INTRADAY[tf.upper()]
    out = (
        m1.sort("ts").set_sorted("ts")
        .group_by_dynamic("ts", every=every, offset=offset, closed="left", label="left")
        .agg(_AGG)
    )
    return out.select(OUT_COLUMNS)


def resample_daily(m1: pl.DataFrame, anchor: str = "ny_close") -> pl.DataFrame:
    if anchor == "utc":
        out = (
            m1.sort("ts").set_sorted("ts")
            .group_by_dynamic("ts", every="1d", offset="0m", closed="left", label="left")
            .agg(_AGG)
            .with_columns(pl.col("ts").dt.date().alias("day"))
        )
        return out.select(OUT_COLUMNS + ["day"])
    out = (
        m1.sort("ts")
        .with_columns(trading_day_expr().alias("day"))
        .group_by("day", maintain_order=True)
        .agg([pl.col("ts").first()] + _AGG)
    )
    return out.select(OUT_COLUMNS + ["day"])


def resample_weekly(m1: pl.DataFrame, anchor: str = "ny_close") -> pl.DataFrame:
    day = trading_day_expr() if anchor != "utc" else pl.col("ts").dt.date()
    week = day.cast(pl.Datetime("us")).dt.truncate("1w").cast(pl.Date).alias("week")
    out = (
        m1.sort("ts")
        .with_columns(week)
        .group_by("week", maintain_order=True)
        .agg([pl.col("ts").first()] + _AGG)
    )
    return out.select(OUT_COLUMNS + ["week"])


def resample(m1: pl.DataFrame, tf: str, anchor: str = "ny_close") -> pl.DataFrame:
    tf = tf.upper()
    if tf in INTRADAY:
        return resample_intraday(m1, tf)
    if tf == "D1":
        return resample_daily(m1, anchor)
    if tf == "W1":
        return resample_weekly(m1, anchor)
    raise ValueError(f"unknown timeframe {tf}")


def resample_symbol(sym: str, tfs: tuple[str, ...] = DEFAULT_TFS, anchor: str = "ny_close") -> dict[str, int]:
    """Read data/m1/{SYM}.parquet, write data/tf/{SYM}_{TF}.parquet for each tf. Returns bar counts."""
    m1 = pl.read_parquet(store.m1_path(sym))
    counts: dict[str, int] = {}
    for tf in tfs:
        bars = resample(m1, tf, anchor)
        store.write_parquet(bars, store.tf_path(sym, tf))
        counts[tf] = bars.height
    log.info("%s resampled: %s", sym, counts)
    return counts
