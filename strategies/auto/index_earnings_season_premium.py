"""Aggregate earnings-announcement premium on index CFDs: Monday-to-Friday long in reporting-season weeks.

Mechanism (a risk premium, not a flow): investors who hold the index through the weeks in which most large
companies report bear concentrated cash-flow and discount-rate news and may be paid for it. Large US companies
report from about the second week after a quarter-end for four to five weeks; Tokyo companies with a March
year-end about two weeks later. The control arm is long in every other week of the same years, so drift,
costs and financing are identical in both arms and only the reporting-week excess is scored.

Rules (all times UTC; H1 bars are stamped at the bar OPEN and are sparse, so every time is located by
timestamp with F.first_bar_at_or_after, never by bar count):

Week selection (calendar only, fixed before any data is seen):
- Mondays = unique UTC dates with weekday 0 and date >= start.
- q0 = first day of the calendar quarter containing the Monday; off = (Monday - q0) in days (0..91).
  Unit check: 2015-02-16 -> q0 2015-01-01, off 46; 2015-04-13 -> off 12.
- s0 = start_off + (jp_shift_days if the symbol starts with 'JPN' else 0).
- season(Monday) = s0 <= off < s0 + 7 * n_weeks.
- arm 'season' keeps the season Mondays; arm 'ctrl' keeps all the other Mondays; any other arm raises
  ValueError. US and Japanese holidays are not excluded (a holiday Monday with a bar in the window trades).

Entry (decided from Monday information only):
- ei = first bar at or after Monday 14:30 (entry_utc), i.e. the 15:00 UTC bar on a normal Monday
  (11:00 New York in daylight time, 10:00 in winter). Skip the week only if ei < 1, ei >= n, ts[ei] is more
  than max_delay_min (90) minutes after Monday 14:30, or ATR20[ei] is not finite or <= 0. No skip depends on
  any bar after ei.
- Signal bar sig = ei - 1; long only, market order at the next open (entry_type 0, valid_bars 1), so the fill
  is at the open of bar ei (ask side plus slippage). Long only in both arms.

Stop: sl_dist[sig] = sl_atr * ATR20[ei], ATR20 = mean daily high-low range of the previous atr_n trading days,
known at the start of the trading day. No target (tp_dist NaN), max_bars 0.

Exit: f = Monday + 4 days (the Friday of the same week).
- (a) Normal exit: xi = first bar at or after Friday 19:30 (exit_utc), i.e. the 20:00 UTC bar on a normal Friday
  (16:00 New York in daylight time, 15:00 in winter; the CFD session ends 21:00 UTC in US daylight time so it
  is the last Friday bar then). If xi < n, xi > ei and ts[xi] is no more than max_exit_delay_min (180) minutes
  after Friday 19:30, exit_long[xi - 1] = True, closing at the open of bar xi.
- (b) Causal fallback: for each entered week, exit_long[j] = True on every bar j with ts in [Friday 20:00 of
  that week, entry_utc (Monday 14:30) of the NEXT ENTERED week); for the last entered week the window runs to
  the end of the data. A week whose Friday session is missing or cut short then exits at the open of the bar
  after the first post-gap bar (the first post-gap bar carries the marker, and a marker closes at the next
  bar's open) instead of running into the next trade week. Every marked bar lies before the next entry
  fill, so no later trade can be hit. Markers on bars with no open position are ignored by the executor.
  The week is never skipped because of the Friday bars.
- (c) Leftover-position guard: exit_long[sig] = True on the signal bar of every entered week. A position still
  open from an earlier week (for example when the whole [Friday 20:00, Monday entry) window has no bar, as in
  some 2013 data gaps) is closed at the open of ei; that week's entry is then not taken, which the executor
  would have forced anyway because it blocks entries while a position is open. A marker on the signal bar
  never touches the new trade, which is filled at the open of ei.
- No other exits, no filters, one trade per selected week.

Deviation from the first version of rule (b) (window ending at the following Monday 12:00), made to meet the
rule's stated purpose that a week never runs into the next trade week: with a window that ends at the
following Monday 12:00 and no bar in it, a position stayed open through weeks of the other arm.

The fallback window start (Friday 20:00) is a structural part of the rule, not a tunable.
Follows the causal pattern of strategies/auto/carry_cross_weekend_premium.py.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "index_earnings_season_premium"
PARAMS = {"arm": "season", "start_off": 10, "n_weeks": 5, "sl_atr": 1.0, "entry_utc": "14:30",
          "exit_utc": "19:30", "max_delay_min": 90, "max_exit_delay_min": 180, "atr_n": 20,
          "start": "2013-01-01", "jp_shift_days": 14}
GRID = {"arm": ["season", "ctrl"], "start_off": [10, 17], "n_weeks": [4, 5], "sl_atr": [1.0, 2.0]}

# Structural fallback window start, relative to the Monday of the trade week: Friday 20:00 UTC (Monday + 4 days).
# The window ends at the entry time of the next entered week (or the end of the data).
_FALLBACK_START_MIN = 4 * 24 * 60 + 20 * 60


def signals(m: Market, p: dict) -> Signals:
    arm = str(p["arm"]).lower()
    if arm not in ("season", "ctrl"):
        raise ValueError("arm must be 'season' or 'ctrl'")
    s = Signals(m.n)
    if m.n < 3:
        return s

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))

    # ---- week selection: Mondays on or after start, split by days since the calendar quarter start
    dates = np.unique(F.utc_dates(m))
    mondays = dates[(F.weekday(dates) == 0) & (dates >= np.datetime64(p["start"]))]
    if len(mondays) == 0:
        return s
    months = mondays.astype("datetime64[M]")
    q0 = (months - (months.astype(np.int64) % 12 % 3).astype("timedelta64[M]")).astype("datetime64[D]")
    off = (mondays - q0).astype(np.int64)
    s0 = int(p["start_off"]) + (int(p["jp_shift_days"]) if str(m.sym).upper().startswith("JPN") else 0)
    season = (off >= s0) & (off < s0 + 7 * int(p["n_weeks"]))
    keep = season if arm == "season" else ~season
    mondays = mondays[keep]
    if len(mondays) == 0:
        return s

    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    entry_idx = F.first_bar_at_or_after(m, mondays, eh, em)
    fridays = mondays + np.timedelta64(4, "D")
    exit_idx = F.first_bar_at_or_after(m, fridays, xh, xm)
    max_delay = np.timedelta64(int(p["max_delay_min"]), "m")
    max_exit_delay = np.timedelta64(int(p["max_exit_delay_min"]), "m")

    entered = []   # Mondays of the weeks that signalled an entry, in time order

    for d, f, ei, xi in zip(mondays, fridays, entry_idx, exit_idx):
        if ei < 1 or ei >= m.n:
            continue
        e_target = d.astype("datetime64[us]") + np.timedelta64(eh * 60 + em, "m")
        if m.ts[ei] - e_target > max_delay:
            continue
        a = atr[ei]
        if not np.isfinite(a) or a <= 0:
            continue
        sig = ei - 1
        s.entry_long[sig] = True
        s.entry_type[sig] = 0
        s.valid_bars[sig] = 1
        s.sl_dist[sig] = float(p["sl_atr"]) * a
        s.max_bars[sig] = 0
        # (a) normal exit: close at the open of the first bar at or after Friday exit_utc
        x_target = f.astype("datetime64[us]") + np.timedelta64(xh * 60 + xm, "m")
        if xi < m.n and xi > ei and m.ts[xi] - x_target <= max_exit_delay:
            s.exit_long[xi - 1] = True
        # (c) a leftover long from an earlier week is closed at the open of ei (never touches this trade)
        s.exit_long[sig] = True
        entered.append(d)

    # (b) causal fallback: every bar from Friday 20:00 of an entered week up to the next entered week's entry
    # time (end of data for the last entered week) closes an open long
    if entered:
        ent = np.array(entered, dtype="datetime64[D]").astype("datetime64[us]")
        lo = np.searchsorted(m.ts, ent + np.timedelta64(_FALLBACK_START_MIN, "m"), side="left")
        hi = np.append(np.searchsorted(m.ts, ent[1:] + np.timedelta64(eh * 60 + em, "m"), side="left"), m.n)
        for a, b in zip(lo, hi):
            if b > a:
                s.exit_long[a:b] = True
    return s
