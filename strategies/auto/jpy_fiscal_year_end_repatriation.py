"""Japanese fiscal-calendar flows in Tokyo hours: fiscal year-end short, new-year long, with control arms.

Mechanism: most listed Japanese companies close their fiscal year on 31 March (half-year 30 September).
Exporters repatriate foreign earnings and institutions square foreign-currency exposure before the
balance-sheet date (sell USD, buy JPY, Tokyo hours); after 1 April (1 October) life insurers, pension funds
and Toshin launches deploy new-year foreign allocations (buy USD). The same windows in ordinary months are
the control arm that cancels USDJPY's Tokyo-session drift.

Rules (all times UTC, bars M15, sparse: every time is located by timestamp):
- Dates: unique UTC dates of the bars, weekdays only, date >= start. month(d) is the calendar month of d.
- Month sets by leg, keyed by `months` (first set for ye_short, second for ny_long):
    'mar'     -> ({3}, {4})
    'mar_sep' -> ({3, 9}, {4, 10})
    'ctrl'    -> ({1, 2, 5, 7, 8, 11}, {2, 6, 8, 11, 12})
  An unknown `leg` or `months` raises ValueError.
- leg 'ye_short': month(d) in the leg's set and 0 <= F.kth_last_weekday(d) < n_days (the last n_days
  weekdays of the month, 0 = last weekday). Side SHORT.
- leg 'ny_long': month(d) in the leg's set and rank(d) < n_days, rank(d) = np.busday_count(first day of the
  month, d) = weekdays in the month strictly before d. Side LONG.
  Both counts are calendar-based, so a missing data day does not shift them. No holiday calendar.
- Entry: market at the open of the first bar at or after entry_utc (00:00 UTC = 09:00 JST). Skipped if that
  bar is missing, is the first bar of the data, or opens more than max_delay_min minutes after the target.
  The signal sits on the bar before it (sig = ei - 1).
- Stop: sl_atr x ATR(atr_n) of the previous atr_n trading days (known at the start of the entry bar's
  trading day, read at ei). Skipped if not finite or <= 0. No target, no max_bars.
- Exit: close at the open of the first bar at or after exit_utc (06:00 UTC = 15:00 JST); the exit flag is on
  xi - 1. Skipped if xi >= m.n, xi <= ei, or that bar opens more than 60 minutes after the exit target.
- One trade per selected date, no filters.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "jpy_fiscal_year_end_repatriation"
PARAMS = {"leg": "ye_short", "months": "mar", "n_days": 10, "sl_atr": 0.25, "entry_utc": "00:00",
          "exit_utc": "06:00", "max_delay_min": 10, "atr_n": 20, "start": "2010-01-01"}
GRID = {"leg": ["ye_short", "ny_long"], "months": ["mar", "mar_sep", "ctrl"],
        "n_days": [5, 10], "sl_atr": [0.25, 0.5]}

# month sets per `months` value: (ye_short months, ny_long months)
_MONTH_SETS = {
    "mar": ({3}, {4}),
    "mar_sep": ({3, 9}, {4, 10}),
    "ctrl": ({1, 2, 5, 7, 8, 11}, {2, 6, 8, 11, 12}),
}
_EXIT_GUARD_MIN = 60


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    leg = p["leg"]
    if leg not in ("ye_short", "ny_long"):
        raise ValueError(f"unknown leg: {leg!r}")
    if p["months"] not in _MONTH_SETS:
        raise ValueError(f"unknown months value: {p['months']!r}")
    short_set, long_set = _MONTH_SETS[p["months"]]
    is_short = leg == "ye_short"
    month_set = short_set if is_short else long_set
    n_days = int(p["n_days"])

    dates = np.unique(F.utc_dates(m))
    dates = dates[(F.weekday(dates) < 5) & (dates >= np.datetime64(p["start"]))]
    if len(dates) == 0:
        return s

    month_of = (dates.astype("datetime64[M]").astype(np.int64) % 12) + 1
    in_months = np.isin(month_of, np.array(sorted(month_set), dtype=np.int64))
    if is_short:
        k = F.kth_last_weekday(dates)
        in_window = (k >= 0) & (k < n_days)
    else:
        first_of_month = dates.astype("datetime64[M]").astype("datetime64[D]")
        rank = np.busday_count(first_of_month, dates)
        in_window = rank < n_days
    dates = dates[in_months & in_window]
    if len(dates) == 0:
        return s

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))

    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    entry_idx = F.first_bar_at_or_after(m, dates, eh, em)
    exit_idx = F.first_bar_at_or_after(m, dates, xh, xm)
    max_delay = np.timedelta64(int(p["max_delay_min"]), "m")
    exit_guard = np.timedelta64(_EXIT_GUARD_MIN, "m")

    for d, ei, xi in zip(dates, entry_idx, exit_idx):
        if ei < 1 or ei >= m.n or xi >= m.n or xi <= ei:
            continue
        d_us = d.astype("datetime64[us]")
        if m.ts[ei] - (d_us + np.timedelta64(eh * 60 + em, "m")) > max_delay:
            continue
        if m.ts[xi] - (d_us + np.timedelta64(xh * 60 + xm, "m")) > exit_guard:
            continue
        a = atr[ei]
        if not np.isfinite(a) or a <= 0:
            continue
        sig = ei - 1
        if is_short:
            s.entry_short[sig] = True
            s.exit_short[xi - 1] = True
        else:
            s.entry_long[sig] = True
            s.exit_long[xi - 1] = True
        s.sl_dist[sig] = p["sl_atr"] * a
    return s
