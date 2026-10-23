"""London trend-day continuation: the London open-drive carries into the New York session.

Mechanism (pre-registered): on a minority of days a macro or trend-following flow arrives at the London open
and price runs one way, closing the London morning near its extreme. The flow is worked through the whole day
and the New York session adds same-direction US accounts and the stops of early faders, so from 12:00 to 16:00
UTC the drift should continue in the London direction on those days only. The signature (large London range,
close at the extreme) is observable at 12:00 UTC. Markets: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, GBPJPY on
M5 bars; primary market EURUSD.

Rules (all times UTC; every calendar date d from Monday to Friday; at most one trade per day, no re-entry):
  London window  all bars with window_start (07:00) <= ts < window_end (12:00) on d. The bar that opens at
                 window_end is the entry bar and is never part of the window.
  O              bid open of the first bar at or after 07:00. Day skipped if that bar is more than
                 max_delay_min after 07:00. (O is used only through this skip rule; no other rule uses its value.)
  H, L           highest bid high and lowest bid low of the window bars; R = H - L.
  C              bid close of the last bar before 12:00. Day skipped if that bar is more than max_delay_min
                 before 12:00.
  ATR            previous-20-trading-day average daily range (F.atr_prev on NY-close daily bars), known at the
                 start of the trading day that contains 12:00 UTC on d. Day skipped if not available.
  Trend day      R >= k * ATR.
  Direction      long if (C - L) / R >= 1 - q; short if (C - L) / R <= q; otherwise no trade.
  Entry          market order signalled on the last bar before 12:00, so it fills at the open of the first bar
                 at or after 12:00 (ask for longs, bid for shorts). Day skipped if that bar does not exist or is
                 more than max_delay_min after 12:00 (sparse-bar guard, as in the oracle modules).
  Stop           m * R from the fill. No take-profit.
  Exit           close at the open of the first bar at or after exit_utc (16:00): the exit flag is set on the last
                 bar before exit_utc; the stop stays live until then. Day skipped if that bar does not exist.
Parameters: k (range threshold in ATR units), q (close-location fraction), m (stop in units of R),
window_start, window_end, exit_utc, max_delay_min.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "london_trend_day_ny_continuation"
PARAMS = {"k": 0.65, "q": 0.25, "m": 0.5, "window_start": "07:00", "window_end": "12:00",
          "exit_utc": "16:00", "max_delay_min": 15}
GRID = {"k": [0.5, 0.65, 0.8], "q": [0.15, 0.25], "m": [0.5, 0.75]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))        # previous-20-day average range, known at the day's start
    dates = np.unique(F.utc_dates(m))
    dates = dates[F.weekday(dates) < 5]               # Monday to Friday
    sh, sm = F.parse_hhmm(p["window_start"])
    eh, em = F.parse_hhmm(p["window_end"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    i_first = F.first_bar_at_or_after(m, dates, sh, sm)   # first London-window bar
    i_fill = F.first_bar_at_or_after(m, dates, eh, em)    # entry bar; the window is bars i_first .. i_fill - 1
    i_exit = F.first_bar_at_or_after(m, dates, xh, xm)    # bar at whose open the trade is closed
    day_us = dates.astype("datetime64[us]")
    t_start = day_us + np.timedelta64(sh * 60 + sm, "m")
    t_end = day_us + np.timedelta64(eh * 60 + em, "m")
    max_delay = np.timedelta64(int(p["max_delay_min"]), "m")
    k_atr, q_close, stop_mult = p["k"], p["q"], p["m"]    # stop_mult = stop in units of R (m is the Market)
    for t0, t1, i0, i1, ix in zip(t_start, t_end, i_first, i_fill, i_exit):
        # sparse-bar guards: window not empty, fill bar and exit bar exist, bars sit near their clock times
        if i1 <= i0 or i1 >= m.n or ix >= m.n or ix <= i1:
            continue
        if m.ts[i0] - t0 > max_delay or t1 - m.ts[i1 - 1] > max_delay or m.ts[i1] - t1 > max_delay:
            continue
        sig = i1 - 1                                  # last window bar: its close is the decision point
        a = atr[sig]                                  # same NY trading day as 12:00 UTC on d
        if not (np.isfinite(a) and a > 0):
            continue
        hi = m.bid_h[i0:i1].max()
        lo = m.bid_l[i0:i1].min()
        rng = hi - lo                                 # R
        if not (np.isfinite(rng) and rng > 0 and rng >= k_atr * a):
            continue                                  # not a trend day
        loc = (m.bid_c[sig] - lo) / rng               # close location inside the London range, 0 = low, 1 = high
        go_long = loc >= 1.0 - q_close
        go_short = loc <= q_close
        if go_long == go_short:                       # neither: no trade (both is possible only for q >= 0.5)
            continue
        if go_long:
            s.entry_long[sig] = True
            s.exit_long[ix - 1] = True
        else:
            s.entry_short[sig] = True
            s.exit_short[ix - 1] = True
        s.entry_type[sig] = 0                         # market order at the next open
        s.valid_bars[sig] = 1
        s.sl_dist[sig] = stop_mult * rng
    return s
