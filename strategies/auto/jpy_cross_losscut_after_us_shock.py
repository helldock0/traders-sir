"""Forced losscut flow: short a JPY cross into the Tokyo pre-open after a US100 cash-session shock.

Mechanism: Japanese retail margin accounts are long the high-yield yen crosses (AUDJPY, NZDJPY, CADJPY).
After a hard US equity sell-off the crosses open the Tokyo morning with unreacted losses, and losscuts /
manual de-risking continue the move in the first Tokyo hours.

Window used: the DST-AWARE New York cash-session window (NOT the fixed 14:30-20:00 UTC fallback).
Per UTC date D the New York offset follows the US rule (daylight saving from the second Sunday of March
to the first Sunday of November: NY = UTC-4, otherwise UTC-5). t_start = 09:30 NY and t_end = 16:00 NY on D
converted to UTC (13:30/20:00 UTC in summer, 14:30/21:00 UTC in winter).

Rules (all times UTC unless stated; M15 bars on the primary yen cross):
  SHOCK    a = US100 CFD (USATECHIDXUSD, read through F.aux_market with explicit close times).
           start = first aux bar with ts >= t_start; end = last aux bar whose close time <= t_end.
           Require end > start and both bars on UTC date D. shock_pct = 100 * (bid_c[end] / bid_o[start] - 1)
           (the window-start level is the denominator).
  SIGNAL   on each UTC date D that is Monday to Thursday, S = first primary bar whose close time is in
           [23:00, 23:59) on D (08:00 JST) and is >= t_end. shock_pct is attached to S only.
           Condition: shock_pct <= -k (k in percent).
  ENTRY    entry_short[S] = True, market order at the next bar's open, valid_bars 1, one trade per date.
  STOP     sl_dist[S] = sl_atr * ATR20_prev (daily ATR of the previous 20 trading days, known at the start of the
           trading day that contains S). No trade if NaN or <= 0. No target.
  EXIT     time exit: exit_short on the last bar of D+1 whose close time is <= exit_utc and after S's close time
           (the executor closes at the following bar's open). Safety net max_bars[S] = number of primary bars from
           S up to 06:00 UTC on D+1, plus 4.
Shorts only, no other filters. Fridays are excluded (no Tokyo session after a Friday US session).
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "jpy_cross_losscut_after_us_shock"
PARAMS = {"k": 1.0, "sl_atr": 0.5, "exit_utc": "02:00",
          "aux": "USATECHIDXUSD", "signal_from_utc": "23:00", "signal_to_utc": "23:59",
          "safety_exit_utc": "06:00", "safety_extra_bars": 4,
          "ny_open": "09:30", "ny_close": "16:00", "atr_n": 20}
GRID = {"k": [0.5, 0.75, 1.0], "sl_atr": [0.5, 1.0], "exit_utc": ["02:00", "06:00"]}


def _us_dst(dates: np.ndarray) -> np.ndarray:
    """True where the US daylight saving rule applies (second Sunday of March to first Sunday of November).

    Evaluated at date level; the changeover happens on Sundays at 02:00 local, and the cash window
    (09:30-16:00 NY) is always after the changeover on that day."""
    dates = dates.astype("datetime64[D]")
    years = dates.astype("datetime64[Y]")
    out = np.zeros(len(dates), dtype=bool)
    for y in np.unique(years):
        mar1 = (y + np.timedelta64(2, "M")).astype("datetime64[D]")
        nov1 = (y + np.timedelta64(10, "M")).astype("datetime64[D]")
        # weekday: Monday = 0 ... Sunday = 6
        w_mar = int(F.weekday(np.array([mar1]))[0])
        w_nov = int(F.weekday(np.array([nov1]))[0])
        start = mar1 + np.timedelta64((6 - w_mar) % 7 + 7, "D")   # second Sunday of March
        end = nov1 + np.timedelta64((6 - w_nov) % 7, "D")         # first Sunday of November
        sel = years == y
        out[sel] = (dates[sel] >= start) & (dates[sel] < end)
    return out


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    if m.n == 0:
        return s
    a = F.aux_market(m, p["aux"])
    if a.n == 0:
        return s

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))

    dates = np.unique(F.utc_dates(m))
    dates = dates[F.weekday(dates) < 4]            # Monday to Thursday
    if len(dates) == 0:
        return s
    day_us = dates.astype("datetime64[us]")

    # --- US cash-session window per date (DST aware), in UTC ---
    oh, om = F.parse_hhmm(p["ny_open"])
    ch, cm = F.parse_hhmm(p["ny_close"])
    off_h = np.where(_us_dst(dates), 4, 5).astype(np.int64)   # NY = UTC - off_h
    t_start = day_us + (off_h * 60 + oh * 60 + om).astype("timedelta64[m]")
    t_end = day_us + (off_h * 60 + ch * 60 + cm).astype("timedelta64[m]")

    a_close = a.close_times()
    i_start = np.searchsorted(a.ts, t_start, side="left")
    i_end = np.searchsorted(a_close, t_end, side="right") - 1
    ok = (i_start < a.n) & (i_end >= 0) & (i_end > i_start)
    i_start_c = np.clip(i_start, 0, a.n - 1)
    i_end_c = np.clip(i_end, 0, a.n - 1)
    ok &= (a.ts[i_start_c].astype("datetime64[D]") == dates)
    ok &= (a.ts[i_end_c].astype("datetime64[D]") == dates)
    denom = a.bid_o[i_start_c]
    ok &= np.isfinite(denom) & (denom > 0) & np.isfinite(a.bid_c[i_end_c])
    shock = np.full(len(dates), np.nan)
    shock[ok] = 100.0 * (a.bid_c[i_end_c[ok]] / denom[ok] - 1.0)

    # --- signal bar S: first primary bar closing in [23:00, 23:59) UTC on D ---
    m_close = m.close_times()
    fh, fm = F.parse_hhmm(p["signal_from_utc"])
    th, tm = F.parse_hhmm(p["signal_to_utc"])
    sig_lo = day_us + np.timedelta64(fh * 60 + fm, "m")
    sig_hi = day_us + np.timedelta64(th * 60 + tm, "m")
    S_idx = np.searchsorted(m_close, sig_lo, side="left")
    S_c = np.clip(S_idx, 0, m.n - 1)
    valid_s = (S_idx < m.n) & (m_close[S_c] < sig_hi) & (m_close[S_c] >= t_end)

    # --- exit and safety-net bars on D+1 ---
    xh, xm = F.parse_hhmm(p["exit_utc"])
    sh, sm = F.parse_hhmm(p["safety_exit_utc"])
    next_us = day_us + np.timedelta64(1, "D")
    exit_idx = np.searchsorted(m_close, next_us + np.timedelta64(xh * 60 + xm, "m"), side="right") - 1
    safety_end = np.searchsorted(m.ts, next_us + np.timedelta64(sh * 60 + sm, "m"), side="left")

    k = float(p["k"])
    for j in range(len(dates)):
        if not ok[j] or not valid_s[j] or not np.isfinite(shock[j]):
            continue
        if not (shock[j] <= -k):
            continue
        si = int(S_idx[j])
        sl = float(p["sl_atr"]) * atr[si]
        if not np.isfinite(sl) or sl <= 0:
            continue
        s.entry_short[si] = True
        s.entry_type[si] = 0
        s.valid_bars[si] = 1
        s.sl_dist[si] = sl
        xi = int(exit_idx[j])
        if 0 <= xi < m.n and xi > si and m_close[xi] > m_close[si]:
            s.exit_short[xi] = True
        s.max_bars[si] = max(int(safety_end[j]) - si, 1) + int(p["safety_extra_bars"])
    return s
