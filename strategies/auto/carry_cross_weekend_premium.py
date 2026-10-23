"""Weekend risk premium in carry crosses (Friday afternoon to Monday open) with a weekday-overnight control.

Mechanism: carry positions cannot be adjusted over the weekend; risk managers cut high-yield exposure into
the Friday New York afternoon and re-establish it Monday. Both the Friday arm and the Monday control cross
exactly one single rollover (the triple rollover is Wednesday), so net carry is about zero minus the 1%
markup; any premium must come from price.

Rules (all times UTC, H1 bars labelled by open time, bars are sparse so everything is located by timestamp):
- entry_day: "fri" (weekday 4, the hypothesis) or "mon" (weekday 0, the weekday-overnight control).
- For each UTC date D with that weekday: ei = first bar at or after D + entry_utc. Require ei >= 1 and
  ts[ei] no more than 60 minutes after the target, otherwise no trade. Signal bar S = ei - 1, so the market
  fill lands at the open of bar ei (entry_utc).
- Entry: long only, market at next open (entry_type 0, valid_bars 1). One trade per entry date.
- Stop: sl_dist[S] = sl_atr * ATR20_prev (known at day start); no trade if NaN or <= 0. No target.
- Exit: D_exit = D + 3 days (fri -> Monday) or D + 1 day (mon -> Tuesday). X = first bar whose OPEN time
  is at or after D_exit + exit_utc. If X < n, X - 1 > S and ts[X] is no more than 60 minutes after the
  target, exit_long[X - 1] = True (close at the open of bar X).
- Safety net: max_bars[S] = 24 for both arms.
- Deviation from the amended pre-registration, forced by the truncation leak test: the brief says to skip
  the trade when the exit bar is missing or more than 60 minutes late. That decision needs bars after the
  signal bar, so a prefix of the data would signal differently from the full series (a real look-ahead
  in the entry). The entry is therefore decided from the entry-side information only, and a trade whose
  exit bar is missing or late is closed by the 24-bar safety net instead of being skipped.
- No other filters.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "carry_cross_weekend_premium"
PARAMS = {"entry_day": "fri", "entry_utc": "20:00", "exit_utc": "07:00", "sl_atr": 1.5,
          "max_delay_min": 60, "max_hold_bars": 24}
GRID = {"entry_day": ["fri", "mon"], "entry_utc": ["16:00", "20:00"],
        "exit_utc": ["00:00", "07:00"], "sl_atr": [1.5, 3.0]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    if m.n < 3:
        return s
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))
    dates = np.unique(F.utc_dates(m))
    day = str(p["entry_day"]).lower()
    if day == "fri":
        wd, shift_days = 4, 3
    elif day == "mon":
        wd, shift_days = 0, 1
    else:
        raise ValueError("entry_day must be 'fri' or 'mon'")
    dates = dates[F.weekday(dates) == wd]
    if len(dates) == 0:
        return s
    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    exit_dates = dates + np.timedelta64(shift_days, "D")
    entry_idx = F.first_bar_at_or_after(m, dates, eh, em)
    exit_idx = F.first_bar_at_or_after(m, exit_dates, xh, xm)
    max_delay = np.timedelta64(int(p["max_delay_min"]), "m")
    for d, dx, ei, xi in zip(dates, exit_dates, entry_idx, exit_idx):
        if ei < 1 or ei >= m.n:
            continue
        sig = ei - 1
        e_target = d.astype("datetime64[us]") + np.timedelta64(eh * 60 + em, "m")
        x_target = dx.astype("datetime64[us]") + np.timedelta64(xh * 60 + xm, "m")
        if m.ts[ei] - e_target > max_delay:
            continue
        a = atr[ei]
        if not np.isfinite(a) or a <= 0:
            continue
        s.entry_long[sig] = True
        s.entry_type[sig] = 0
        s.valid_bars[sig] = 1
        s.sl_dist[sig] = p["sl_atr"] * a
        s.max_bars[sig] = int(p["max_hold_bars"])
        if xi < m.n and xi - 1 > sig and m.ts[xi] - x_target <= max_delay:
            s.exit_long[xi - 1] = True
    return s
