"""Look-ahead-safe feature helpers for strategies, in numpy on a Market.

Trading days follow the New York 17:00 close (the session that opens Sunday 17:00 NY belongs to
Monday). Daily features are shifted so that the value attached to a bar is known before that bar's
trading day starts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import polars as pl

from .external import ExtSeries
from .market import Market

NY_TZ = "America/New_York"


def utc_dates(m: Market) -> np.ndarray:
    return m.ts.astype("datetime64[D]")


def minute_of_day_utc(m: Market) -> np.ndarray:
    return ((m.ts - m.ts.astype("datetime64[D]")) / np.timedelta64(1, "m")).astype(np.int64)


def weekday(dates: np.ndarray) -> np.ndarray:
    """Monday = 0 ... Sunday = 6 for datetime64[D] arrays."""
    return (dates.astype("datetime64[D]").astype(np.int64) + 3) % 7


def trading_days(m: Market) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar trading-day index and the array of trading-day dates (datetime64[D])."""
    s = pl.Series("ts", m.ts).dt.replace_time_zone("UTC").dt.convert_time_zone(NY_TZ)
    d = (s + timedelta(hours=7)).dt.date().to_numpy().astype("datetime64[D]")
    days, idx = np.unique(d, return_inverse=True)
    return idx.astype(np.int64), days


@dataclass
class Daily:
    date: np.ndarray      # datetime64[D], one per trading day
    start_i: np.ndarray   # first bar index of the day
    end_i: np.ndarray     # last bar index of the day
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    day_idx: np.ndarray   # per bar -> row in the arrays above

    @property
    def n(self) -> int:
        return len(self.date)

    def to_bars(self, per_day: np.ndarray) -> np.ndarray:
        """Broadcast a per-day array onto bars."""
        return per_day[self.day_idx]


def daily_bars(m: Market) -> Daily:
    day_idx, days = trading_days(m)
    starts = np.concatenate([[0], np.flatnonzero(np.diff(day_idx)) + 1])
    ends = np.concatenate([starts[1:] - 1, [m.n - 1]])
    return Daily(
        date=days, start_i=starts, end_i=ends,
        o=m.bid_o[starts], h=np.maximum.reduceat(m.bid_h, starts), l=np.minimum.reduceat(m.bid_l, starts),
        c=m.bid_c[ends], day_idx=day_idx,
    )


def rolling_mean(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing mean over n values including the current one; NaN for the first n-1."""
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def shift(x: np.ndarray, k: int = 1) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:-k] if k > 0 else x
    return out


def atr_prev(daily: Daily, n: int = 20) -> np.ndarray:
    """Average daily range (high - low) of the previous n trading days, known at the day's start."""
    return shift(rolling_mean(daily.h - daily.l, n), 1)


def sma_prev(daily: Daily, n: int) -> np.ndarray:
    """Simple average of the previous n daily closes, known at the day's start."""
    return shift(rolling_mean(daily.c, n), 1)


def first_bar_at_or_after(m: Market, dates: np.ndarray, hh: int, mm: int = 0) -> np.ndarray:
    """For each calendar date, the index of the first bar at or after hh:mm UTC (m.n if none)."""
    targets = dates.astype("datetime64[D]").astype("datetime64[us]") + np.timedelta64(hh * 60 + mm, "m")
    return np.searchsorted(m.ts, targets, side="left")


def is_gotobi(dates: np.ndarray) -> np.ndarray:
    """5th, 10th, 15th, 20th, 25th and last day of the month; a weekend target moves back to Friday."""
    dates = dates.astype("datetime64[D]")
    out = np.zeros(len(dates), dtype=bool)
    cache: dict[int, set[int]] = {}
    days_int = dates.astype(np.int64)
    months = dates.astype("datetime64[M]")
    for k in range(len(dates)):
        mo = months[k]
        key = int(mo.astype(np.int64))
        if key not in cache:
            start = mo.astype("datetime64[D]")
            end = (mo + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
            adj = set()
            for t in [start + np.timedelta64(d - 1, "D") for d in (5, 10, 15, 20, 25)] + [end]:
                ti = int(t.astype(np.int64))
                while (ti + 3) % 7 >= 5:
                    ti -= 1
                adj.add(ti)
            cache[key] = adj
        out[k] = int(days_int[k]) in cache[key]
    return out


def kth_last_weekday(dates: np.ndarray) -> np.ndarray:
    """0 for the last weekday of the month, 1 for the one before, ...; -1 for weekend dates."""
    dates = dates.astype("datetime64[D]")
    months = dates.astype("datetime64[M]")
    month_end = (months + np.timedelta64(1, "M")).astype("datetime64[D]")  # first day of next month
    k = np.busday_count(dates + np.timedelta64(1, "D"), month_end)
    k = np.where(weekday(dates) >= 5, -1, k)
    return k.astype(np.int64)


def parse_hhmm(s: str) -> tuple[int, int]:
    hh, mm = s.split(":")
    return int(hh), int(mm)


def aux_market(m: Market, name: str) -> Market:
    """The auxiliary market attached to m under `name` (listed in the hypothesis as aux_markets)."""
    try:
        return m.aux[name.upper()]
    except KeyError:
        raise KeyError(f"auxiliary market {name!r} is not attached to {m.sym}; available: {sorted(m.aux)}") from None


def aux_asof(m: Market, name: str, col: str = "bid_c") -> np.ndarray:
    """Value of an auxiliary market's column known at each primary bar's close.

    Uses the last auxiliary bar whose close time is at or before the primary bar's close time, so no
    auxiliary bar that is still forming leaks in. NaN before the first auxiliary bar."""
    a = aux_market(m, name)
    idx = np.searchsorted(a.close_times(), m.close_times(), side="right") - 1
    vals = getattr(a, col)
    out = np.full(m.n, np.nan)
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


def aux_window_change(m: Market, name: str, start_hh: int, start_mm: int, end_hh: int, end_mm: int,
                      col: str = "bid_c") -> np.ndarray:
    """Per primary bar: the auxiliary market's change from its first bar at or after start (UTC) to its last
    bar closed by end (UTC) on the same calendar date, known only from the primary bars at or after `end`.
    NaN elsewhere. Useful for 'what did the index do in its cash session' conditions."""
    a = aux_market(m, name)
    out = np.full(m.n, np.nan)
    dates = np.unique(utc_dates(m))
    day_us = dates.astype("datetime64[us]")
    t_start = day_us + np.timedelta64(start_hh * 60 + start_mm, "m")
    t_end = day_us + np.timedelta64(end_hh * 60 + end_mm, "m")
    a_close = a.close_times()
    vals = getattr(a, col)
    i_start = np.searchsorted(a.ts, t_start, side="left")
    i_end = np.searchsorted(a_close, t_end, side="right") - 1      # last aux bar closed by t_end
    m_close = m.close_times()
    j_from = np.searchsorted(m_close, t_end, side="left")           # first primary bar closed at/after t_end
    j_to = np.searchsorted(m.ts, day_us + np.timedelta64(1, "D"), side="left")
    for s, e, jf, jt in zip(i_start, i_end, j_from, j_to):
        if s >= a.n or e < s or jf >= m.n or jt <= jf:
            continue
        out[jf:jt] = vals[e] - vals[s]
    return out


# ----------------------------------------------------------------------------------------------- external series
def ext_series(m: Market, name: str) -> ExtSeries:
    """The external series attached to m under `name` (listed in the hypothesis as ext_series: calendar, cot, vol)."""
    try:
        return m.ext[name.lower()]
    except KeyError:
        raise KeyError(f"external series {name!r} is not attached to {m.sym}; available: {sorted(m.ext)}") from None


def _ext(m: Market, src) -> ExtSeries:
    return src if isinstance(src, ExtSeries) else ext_series(m, src)


def ext_subset(m: Market, name, mask: np.ndarray) -> ExtSeries:
    """Rows of an external series selected by a boolean mask over its rows, built from e.column(...) (for example
    high-impact USD calendar rows). The result keeps ts_avail and can be passed to ext_asof / ext_recent."""
    e = _ext(m, name)
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != (e.n,):
        raise ValueError(f"mask has shape {mask.shape}, expected ({e.n},)")
    return e.take(mask)


def ext_asof(m: Market, name, col: str) -> np.ndarray:
    """Per primary bar: `col` of the last row usable at the bar's close (ts_avail <= close); NaN (or None for
    text columns) before the first usable row."""
    e = _ext(m, name)
    idx = np.searchsorted(e.ts_avail, m.close_times(), side="right") - 1
    vals = e.column(col)
    out = np.full(m.n, np.nan) if vals.dtype.kind == "f" else np.full(m.n, None, dtype=object)
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


def ext_recent(m: Market, name, minutes: int, col: str | None = None) -> np.ndarray:
    """Per primary bar: whether a row became usable in the `minutes` before the bar's close (bool), or with `col`
    the latest such row's value (NaN where none). Use it for 'within an hour after a release' conditions."""
    e = _ext(m, name)
    close = m.close_times()
    hi = np.searchsorted(e.ts_avail, close, side="right")
    lo = np.searchsorted(e.ts_avail, close - np.timedelta64(int(minutes), "m"), side="right")
    has = hi > lo
    if col is None:
        return has
    vals = e.column(col).astype(np.float64)
    out = np.full(m.n, np.nan)
    out[has] = vals[hi[has] - 1]
    return out


def ext_minutes_since(m: Market, name) -> np.ndarray:
    """Per primary bar: minutes from the last usable row's ts_avail to the bar's close (inf before the first)."""
    e = _ext(m, name)
    close = m.close_times()
    idx = np.searchsorted(e.ts_avail, close, side="right") - 1
    out = np.full(m.n, np.inf)
    ok = idx >= 0
    out[ok] = (close[ok] - e.ts_avail[idx[ok]]) / np.timedelta64(1, "m")
    return out
