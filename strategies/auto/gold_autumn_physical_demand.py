"""Gold autumn effect out of sample: long XAUUSD once per Monday-Thursday trading day inside a seasonal window.

Mechanism: Indian festival / wedding-season physical demand, Chinese Golden Week buying and Q4 hedging
(Baur 2013, "The autumn effect of gold price returns"). Positive drift over the season, not at a clock time.

Rules (all times UTC, H1 bars labelled by open time, a bar closes at ts + 1h):
  DAILY SIGNAL BAR: for each UTC date D, E(D) = last H1 bar of date D whose close time is after 16:00 and at or
    before 20:00 UTC (normally the bar opening 19:00). No such bar -> no trade on D.
  WINDOW (by UTC month of D, p["window"]; any other value raises ValueError):
    "sep_nov_baur" = September or November (published months; primary)
    "sep_nov"      = September, October or November (broader season)
    "rest"         = January-August and December (control)
  Weekday of D must be Monday-Thursday (no Friday entry, so every trade is a ~23-24 hour hold).
  ENTRY: long, market at the next bar's open (entry_type 0, valid_bars 1) on bar E(D).
  STOP: sl_dist = p["sl_atr"] * ATR20_prev (previous 20 trading-day mean high-low range, known at day start),
    taken at E(D); no trade if NaN or <= 0. No take-profit.
  EXIT: X = E(D_next), the signal bar of the next UTC date (any weekday, any month, including Friday) that has a
    valid E. exit_long[X - 1] = True, only if X - 1 > E(D); the executor closes at the open of bar X (20:00 UTC on
    D_next), so the position is flat when the next signal registers. Safety net: max_bars = 30.
  Longs only, no other filters.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "gold_autumn_physical_demand"
PARAMS = {"window": "sep_nov_baur", "sl_atr": 2.0, "sig_start_utc": "16:00", "sig_end_utc": "20:00",
          "bar_minutes": 60, "max_hold_bars": 30, "atr_n": 20}
GRID = {"window": ["sep_nov_baur", "sep_nov", "rest"], "sl_atr": [1.0, 2.0]}

_WINDOW_MONTHS = {
    "sep_nov_baur": (9, 11),
    "sep_nov": (9, 10, 11),
    "rest": (1, 2, 3, 4, 5, 6, 7, 8, 12),
}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    window = p["window"]
    if window not in _WINDOW_MONTHS:
        raise ValueError(f"unknown window {window!r}; allowed: {sorted(_WINDOW_MONTHS)}")
    months_ok = np.array(_WINDOW_MONTHS[window])

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))

    # E(D): last bar of each UTC date whose close time is in (start, end] UTC.
    sh, sm = F.parse_hhmm(p["sig_start_utc"])
    eh, em = F.parse_hhmm(p["sig_end_utc"])
    bar_len = np.timedelta64(int(p["bar_minutes"]), "m")
    dates_bar = F.utc_dates(m)
    day_start = dates_bar.astype("datetime64[us]")
    close_ts = m.ts + bar_len
    in_win = (close_ts > day_start + np.timedelta64(sh * 60 + sm, "m")) & \
             (close_ts <= day_start + np.timedelta64(eh * 60 + em, "m"))
    idx = np.flatnonzero(in_win)
    if len(idx) == 0:
        return s
    d_sel = dates_bar[idx]
    # last bar per date (idx ascending, dates non-decreasing)
    last = np.flatnonzero(np.r_[d_sel[1:] != d_sel[:-1], True])
    e_idx = idx[last]          # E(D) per date with a valid signal bar
    e_dates = d_sel[last]

    months = e_dates.astype("datetime64[M]").astype(np.int64) % 12 + 1
    wd = F.weekday(e_dates)
    take = np.isin(months, months_ok) & (wd <= 3)

    for k in range(len(e_idx)):
        if not take[k]:
            continue
        ei = int(e_idx[k])
        a = atr[ei]
        if not np.isfinite(a) or a <= 0:
            continue
        s.entry_long[ei] = True
        s.sl_dist[ei] = p["sl_atr"] * a
        s.max_bars[ei] = int(p["max_hold_bars"])
        if k + 1 < len(e_idx):
            x = int(e_idx[k + 1])
            if x - 1 > ei:
                s.exit_long[x - 1] = True
    return s
