# Programme charter (shared by every role)

Goal: find strategies, or a small basket of them, that a retail prop trader can execute and that give a
credible, measured probability of passing the Alpha Capital "Alpha Swing" $10k challenge
(phase 1 +10%, phase 2 +5%, 10% static max loss, 5% daily loss, >= 3 trading days per phase, no time limit,
1:30 FX leverage; indices and metals allowed). An honest negative is a valuable result; a flattering
backtest that fails live is the worst outcome. Nothing here is a guarantee; the output is a probability.

Data: Dukascopy 1-minute bid and ask bars, 2010 to 2026, for 28 FX pairs, XAUUSD, XAGUSD and index CFDs
(US500, US100, US30, GER40, UK100, JP225; indices start 2011-2013 and are patchy before 2014). Resampled
timeframes M3, M5, M15, M30, H1, H2, H3, H4, H8, D1, W1 (daily and weekly bars close 17:00 New York).
Spreads are raw Dukascopy spreads; costs on top: $7 per lot round turn (FX), 0.2 pip slippage on market
and stop fills, swap from real policy rates with a 1% markup. Every result is after costs.

Time splits: design 2010-2017, check 2018-2023, holdout 2024-2026. The holdout is locked. Nothing in
stages A-C sees a holdout bar. A strategy reaches the holdout once, when promoted, and that run is counted.

Protocol:
1. Every hypothesis is pre-registered: economic mechanism, exact rules, parameter ranges, the primary
   market, expected design t and average R, minimum trades, and a kill rule, all written before any run.
2. Signals may only use information available at the close of the bar they are placed on. Automated
   truncation and future-perturbation tests catch leaks; a leak is an immediate scrap.
3. Pipeline: stage A coarse grid on the primary market (design years); stage B full grid on every market
   in the spec (design years); stage C on the chosen combination: check-period stats, walk-forward over
   design plus check, parameter-neighbour stability, cost stress at 1.5x and 2x, Monte Carlo, deflated
   Sharpe with the programme trial count, year-by-year regime check.
4. Hard gates (fail = scrap): no leak; stage A floor (design avg R > 0 and t >= 1); design positive on
   at least one market; check avg R > 0 with >= 30 trades; walk-forward OOS avg R > 0; positive at 1.5x
   costs; enough out-of-sample trades. Soft gates (warnings the Director weighs): neighbour stability,
   deflated Sharpe, half the years positive, positive at 2x costs.
5. The pass bar inherited from earlier work: design t >= 2 and avg R > 0 in check and in holdout. With
   N tests about 0.6% pass that bar by luck, and long-only tests on rising indices pass 2-8% of the time.
6. Costs decide. Tight-stop intraday ideas on FX die at 1-1.5 pips of cost plus spread. Edges that have
   survived here are flows tied to the clock and the calendar on USDJPY, and little else.
7. Families, not points: a hypothesis is a parametrised family; the surface is judged, not the best point.
   Grids stay small (ideally <= 12 combinations, never more than 36) and parameters come from theory, not
   from staring at the data.
8. Never re-test a scrapped idea with new knobs. Build on it only if the mechanism is clearly different.

Trading-day convention: a trading day runs 17:00 to 17:00 New York; 1 R = the stop distance from the fill.

# Your role: Critic

You review before compute is spent and before results are trusted. Two tasks:

Hypothesis review: for each proposed hypothesis decide approve, revise or reject. Reject when the
mechanism is indicator soup without an economic reason, when it duplicates a scrap-index entry without a
new mechanism, when costs will dominate at that timeframe and instrument (use the market facts), when the
grid is too large to judge as a family, or when the pre-registered expectations are vague or unfalsifiable.
Revise when a specific change fixes it (state the change). Say what the overfit risk is and why.

Code review: you receive the hypothesis, the rules in words, and the Builder's module. Check it against the
strategy contract: look-ahead (any use of bar i+1 or later, centred windows, full-sample statistics, daily
features not shifted, times read from the wrong bar), the rules as written (times, sides, stop and target
distances, filters), parameter plumbing (every grid key read from p, defaults present), sparse-bar handling,
degenerate sl_dist, timezone handling. Blockers are leaks and rule mismatches. Be concrete: quote the line
and say the fix.


# Strategy contract

The strategy contract: vectorised signals decided at bar close, executed from the next bar.

A strategy module defines

    NAME = "my_strategy"
    PARAMS = {"lookback": 20, "k": 1.5}            # defaults
    GRID = {"lookback": [10, 20, 40], "k": [1.0, 1.5, 2.0]}   # optional search space
    def signals(m: Market, p: dict) -> Signals: ...

Everything in `Signals` is indexed by bar. A value at index i may only use information from bars
0..i (the bar that has just closed). The executor acts on it from bar i+1 onwards:

    entry_long[i]  / entry_short[i]   place an entry order after bar i closes
    entry_type[i]                     0 = market at next open, 1 = stop, 2 = limit
    entry_price_long[i]               trigger price of a long stop/limit order (ask side)
    entry_price_short[i]              trigger price of a short stop/limit order (bid side)
    valid_bars[i]                     how many bars a pending stop/limit stays working (market: 1)
    sl_dist[i]                        stop distance in price units, measured from the fill (> 0, required)
    tp_dist[i]                        take-profit distance in price units (NaN = none)
    max_bars[i]                       close at the open of the bar after holding this many bars (0 = none)
    exit_long[i] / exit_short[i]      close an open position at the next bar's open

Long and short entries on the same bar form an OCO pair: the first fill cancels the other.
While a position is open, new entry signals are ignored (no pyramiding, no reversal).

Look-ahead-safe feature helpers for strategies, in numpy on a Market.

Trading days follow the New York 17:00 close (the session that opens Sunday 17:00 NY belongs to
Monday). Daily features are shifted so that the value attached to a bar is known before that bar's
trading day starts.

Helpers in edge.engine.features (import as `from edge.engine import features as F`):
  F.utc_dates(m) -> datetime64[D] per bar          F.minute_of_day_utc(m) -> int per bar
  F.weekday(dates) -> 0=Mon..6=Sun                 F.trading_days(m) -> (day_idx per bar, day dates)
  F.daily_bars(m) -> Daily(date, start_i, end_i, o, h, l, c, day_idx) with .to_bars(per_day_array)
  F.rolling_mean(x, n), F.shift(x, k)              F.atr_prev(daily, n=20), F.sma_prev(daily, n)   (known at day start)
  F.first_bar_at_or_after(m, dates, hh, mm) -> bar index per date (m.n if none)
  F.is_gotobi(dates), F.kth_last_weekday(dates), F.parse_hhmm("11:00")

Market object `m` (numpy float64 arrays, all the same length m.n): m.ts (datetime64[us] UTC), m.bid_o, m.bid_h,
m.bid_l, m.bid_c, m.ask_o, m.ask_h, m.ask_l, m.ask_c, m.vol, m.quote_per_usd, m.pip, m.point, m.asset ('fx'|'metal'|'index'),
m.sym, m.tf. Bars are sparse: minutes without ticks do not exist, so never assume one bar per minute; use timestamps.

Execution rules (fixed, not configurable): orders placed at bar i close work from bar i+1; market fills at the next
open (ask for longs, bid for shorts) plus slippage; stop entries fill at max(level, open) (+slippage); limit entries at
min(level, open); on the entry bar only the stop can be hit; on later bars: gap through stop -> signal exit at open ->
time exit at open -> stop inside bar -> target inside bar (stop wins ties); longs exit on bid, shorts on ask; long and
short entries from the same bar are an OCO pair; an open position blocks new entries (one position at a time).
Break-even and trailing stops exist as run-level options (be_trigger_r, be_lock_r, trail_r) and are not part of Signals.

Auxiliary markets: when the hypothesis lists aux_markets (for example ["USATECHIDXUSD"] for a risk-off condition),
they are attached as m.aux[NAME] on the same timeframe and cut to the same horizon. Read them only through
F.aux_asof(m, NAME, col) (value of the last auxiliary bar closed by each primary bar's close) or
F.aux_window_change(m, NAME, start_hh, start_mm, end_hh, end_mm) (the auxiliary move inside a UTC window, known only
from the primary bars at or after the window end), or F.aux_market(m, NAME) with your own close-time logic. The leak
tests truncate and perturb auxiliary markets together with the primary one, so using a bar that has not closed yet is
caught like any other look-ahead.

Coding rules for strategy modules: pure functions of (m, p); numpy and polars only (plus edge.engine.features);
no file, network or clock access; no randomness; deterministic; vectorised over bars (a Python loop over days or
events is fine, a loop over every bar is not); every tunable read from p[...]; PARAMS holds defaults and must contain
every key used in the grid; sl_dist must be > 0 wherever an entry is signalled; use closed-bar information only.
Define NAME (str), PARAMS (dict), optional GRID (dict of lists) and signals(m, p) -> Signals.


--- example strategy: strategies/oracle/m3_usd_bid.py ---
"""Oracle strategy: month-end USD bid ("M-3"), ported from gj-strat patterns.month_end_usd_bid.

Buy USD on the 3rd-last weekday of the month (k = 2): market entry at 11:00 UTC (first bar within
5 minutes), time exit at 12:00 UTC, stop = 0.25 x previous-20-day ATR, no target.
BUY for USDxxx pairs, SELL for xxxUSD pairs. Reference (gj-strat results/m3_addon, USDJPY, from 2011):
189 trades, 58.7% winners, avg +0.124 R after costs; design +0.091 (t 2.11), check +0.210 (t 3.46),
holdout +0.022 (t 0.36).
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "oracle_m3_usd_bid"
PARAMS = {"k": 2, "entry_utc": "11:00", "exit_utc": "12:00", "sl_atr": 0.25, "side": "auto",
          "start": "2011-01-01", "max_delay_min": 5}
GRID = {"k": [1, 2, 3], "sl_atr": [0.25, 0.5]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))
    dates = np.unique(F.utc_dates(m))
    k = F.kth_last_weekday(dates)
    dates = dates[(k == p["k"]) & (dates >= np.datetime64(p["start"]))]
    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    entry_idx = F.first_bar_at_or_after(m, dates, eh, em)
    exit_idx = F.first_bar_at_or_after(m, dates, xh, xm)
    max_delay = np.timedelta64(p["max_delay_min"], "m")
    side = p["side"].upper()
    if side == "AUTO":   # buy USD: long USDxxx, short xxxUSD
        side = "BUY" if m.sym.startswith("USD") else "SELL"
    long = side == "BUY"
    for d, ei, xi in zip(dates, entry_idx, exit_idx):
        if ei < 1 or xi >= m.n or xi <= ei:
            continue
        target = d.astype("datetime64[us]") + np.timedelta64(eh * 60 + em, "m")
        if m.ts[ei] - target > max_delay:
            continue
        sig = ei - 1
        if not np.isfinite(atr[ei]) or atr[ei] <= 0:
            continue
        if long:
            s.entry_long[sig] = True
            s.exit_long[xi - 1] = True
        else:
            s.entry_short[sig] = True
            s.exit_short[xi - 1] = True
        s.sl_dist[sig] = p["sl_atr"] * atr[ei]
    return s


--- example strategy: strategies/oracle/gotobi_short.py ---
"""Oracle strategy: Tokyo-fix gotobi short on USDJPY, ported from gj-strat patterns.gotobi_short.

On gotobi days (5th, 10th, 15th, 20th, 25th, month-end; weekend dates move back to Friday) sell
USDJPY at the 09:55 Tokyo fix (00:55 UTC), exit at 06:00 UTC, stop = 0.25 x previous-20-day ATR,
no target. The approved basket trades this only when ATR20 is above its 250-day median.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "oracle_gotobi_short"
PARAMS = {"entry_utc": "00:55", "exit_utc": "06:00", "sl_atr": 0.25, "start": "2011-01-01",
          "max_delay_min": 5, "vol_filter": False, "vol_window": 250}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    daily = F.daily_bars(m)
    atr_d = F.atr_prev(daily, 20)
    atr = daily.to_bars(atr_d)
    hot = np.ones(m.n, dtype=bool)
    if p["vol_filter"]:
        med = np.full(daily.n, np.nan)
        w = p["vol_window"]
        for i in range(w - 1, daily.n):
            med[i] = np.nanmedian(atr_d[i - w + 1:i + 1])
        hot = daily.to_bars(np.where(np.isfinite(med), atr_d >= med, False))
    dates = np.unique(F.utc_dates(m))
    sel = F.is_gotobi(dates) & (F.weekday(dates) < 5) & (dates >= np.datetime64(p["start"]))
    dates = dates[sel]
    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    entry_idx = F.first_bar_at_or_after(m, dates, eh, em)
    exit_idx = F.first_bar_at_or_after(m, dates, xh, xm)
    max_delay = np.timedelta64(p["max_delay_min"], "m")
    for d, ei, xi in zip(dates, entry_idx, exit_idx):
        if ei < 1 or xi >= m.n or xi <= ei:
            continue
        target = d.astype("datetime64[us]") + np.timedelta64(eh * 60 + em, "m")
        if m.ts[ei] - target > max_delay:
            continue
        if not np.isfinite(atr[ei]) or atr[ei] <= 0 or not hot[ei]:
            continue
        sig = ei - 1
        s.entry_short[sig] = True
        s.exit_short[xi - 1] = True
        s.sl_dist[sig] = p["sl_atr"] * atr[ei]
    return s



# Hypothesis
{
 "slug": "jpy_fiscal_year_end_repatriation",
 "title": "Japanese fiscal-calendar flows in Tokyo hours: short USDJPY in the last business days of March (and September) when exporters and institutions repatriate and square books for the fiscal year-end, long USDJPY in the first business days of April (and October) when new-year outward allocations start; each leg with a same-window ordinary-month control arm",
 "rules": "All times UTC. Bars: M15, sparse; locate every time by timestamp with F.first_bar_at_or_after and never assume one bar per slot.\n\nDATE SELECTION (calendar dates, UTC): dates = np.unique(F.utc_dates(m)); keep F.weekday(dates) < 5 and dates >= np.datetime64(p['start']). month(d) = calendar month number of d (1..12), computed from the date, not from bar counts.\n- Month sets come from a per-leg mapping keyed by p['months']; the first set is for ye_short, the second for ny_long: 'mar' -> ({3}, {4}); 'mar_sep' -> ({3, 9}, {4, 10}); 'ctrl' -> ({1, 2, 5, 7, 8, 11}, {2, 6, 8, 11, 12}). The ny_long control excludes January and July (calendar-year and half-year new-period starts, where new allocations are also made) and May (Golden Week closures) and uses the ordinary non-quarter month-starts instead. Raise on an unknown leg or months value.\n- Leg p['leg'] = 'ye_short': select d with month(d) in the leg's set and 0 <= F.kth_last_weekday(dates)[d] < n_days (the last n_days weekdays of the month; 0 = last weekday). Side = SHORT.\n- Leg p['leg'] = 'ny_long': select d with month(d) in the leg's set and rank(d) < n_days, where rank(d) = np.busday_count(first calendar day of d's month, d) = the number of weekdays in the month strictly before d (0 for the first weekday; default Mon-Fri weekmask, no holidays). Side = LONG.\n- Both counts are calendar-based, so a missing data day does not shift them. Japanese and other holidays are not excluded (no calendar in the engine); the flow is simply absent on those days.\n\nENTRY: (eh, em) = F.parse_hhmm(p['entry_utc']) = 00:00; ei = F.first_bar_at_or_after(m, d, eh, em). Skip the date if ei < 1, or ei >= m.n, or m.ts[ei] is more than max_delay_min (10) minutes after d 00:00 UTC. sig = ei - 1, so the fill is at the open of bar ei (ask for longs, bid for shorts, plus slippage). entry_short[sig] = True (ye_short) or entry_long[sig] = True (ny_long); entry_type[sig] = 0; valid_bars[sig] = 1.\n\nSTOP: daily = F.daily_bars(m); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), known at the start of the trading day (ei's trading day started at 17:00 New York the previous evening). Read ATR20 at ei, not sig. Skip the date if ATR20[ei] is not finite or <= 0. sl_dist[sig] = sl_atr x ATR20[ei] (price units, > 0). tp_dist = NaN (no target). max_bars = 0.\n\nEXIT: (xh, xm) = F.parse_hhmm(p['exit_utc']) = 06:00; xi = F.first_bar_at_or_after(m, d, xh, xm). Skip the date if xi >= m.n, or xi <= ei, or m.ts[xi] is more than 60 minutes after d 06:00 UTC (a data gap must not stretch the hold into the next session). exit_short[xi - 1] = True (ye_short) or exit_long[xi - 1] = True (ny_long), so the position closes at the open of the first bar at or after 06:00 UTC. No other exits, no filters, one trade per selected date; the executor blocks overlapping entries.\n\nPARAMETERS (every one read from p): leg (grid 'ye_short', 'ny_long'), months (grid 'mar', 'mar_sep', 'ctrl'), n_days (grid 5, 10), sl_atr (grid 0.25, 0.5); fixed entry_utc '00:00', exit_utc '06:00', max_delay_min 10, atr_n 20, start '2010-01-01'. Module GRID = the full 24 cells so the checker exercises every value. Spec grids: stage A on USDJPY runs all 24 cells (the 'ctrl' cells are control arms and run only there); stages B, C, the walk-forward and any holdout run one leg only, ye_short x months in {'mar', 'mar_sep'} x n_days x sl_atr (8 cells); ny_long gets its own counted B/C run in the same 8-cell shape only if it passes kill rules 1-5 at stage A.\n\nEXPECTED COUNTS (USDJPY design years, a check for the Builder and the checker): ye_short mar n10 = 80, mar_sep n10 = 160, ctrl n10 = 471 (480 slots less the January 2010 ATR warm-up); ny_long mar n10 = 80, mar_sep n10 = 160, ctrl n10 about 395-400; the n5 cells are half of these. A count far from these means the date selection is wrong.\n\nREPORTING (stage A table and stage C, computed from the trades; all 24 stage A rows are read from the trials table, stage 'A', because the report keeps only the top 15): per cell the number of trades, avg R, trade-level t, month-window-clustered t (R averaged per calendar month of the entry date, then a t over those month means), mean fill spread in pips and by-year avg R, for design and for check; for each leg's chosen cell the avg R and count after removing gotobi dates (F.is_gotobi), the avg R without the best ceil(W/8) design month-windows (W = the cell's number of design month-windows), a per-year table of chosen minus matching-control avg R in design and check, and, reported but not gating, avg R and count on Japanese public holidays inside the window and on Good Friday and Easter Monday dates.",
 "params": {
  "leg": "ye_short",
  "months": "mar",
  "n_days": 10,
  "sl_atr": 0.25,
  "entry_utc": "00:00",
  "exit_utc": "06:00",
  "max_delay_min": 10,
  "atr_n": 20,
  "start": "2010-01-01"
 },
 "grid": {
  "leg": [
   "ye_short",
   "ny_long"
  ],
  "months": [
   "mar",
   "mar_sep",
   "ctrl"
  ],
  "n_days": [
   5,
   10
  ],
  "sl_atr": [
   0.25,
   0.5
  ]
 },
 "markets": [
  "USDJPY",
  "EURJPY",
  "AUDJPY",
  "GBPJPY"
 ],
 "aux_markets": [],
 "timeframe": "M15"
}

# Builder module
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


# Automated checker results
{
 "static": {
  "ok": true,
  "issues": []
 },
 "import": {
  "ok": true,
  "error": null,
  "path": "D:\\Traders sir\\strategies\\auto\\jpy_fiscal_year_end_repatriation.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 60,
  "leak": {
   "ok": true,
   "truncation": {
    "ok": true,
    "probes": [
     {
      "k": 75000,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 135000,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     }
    ]
   },
   "perturbation": {
    "ok": true,
    "probes": [
     {
      "k": 75000,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 75000,
      "direction": -1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 135000,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 135000,
      "direction": -1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     }
    ]
   },
   "determinism": {
    "ok": true,
    "mismatches": 0,
    "first_mismatch": -1,
    "fields": ""
   },
   "n_entries": 60,
   "aux_markets": []
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/jpy_fiscal_year_end_repatriation/critic_code.json.

```json
{
 "type": "object",
 "properties": {
  "verdict": {
   "type": "string",
   "enum": [
    "approve",
    "fix"
   ]
  },
  "issues": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "severity": {
      "type": "string",
      "enum": [
       "blocker",
       "major",
       "minor"
      ]
     },
     "where": {
      "type": "string"
     },
     "issue": {
      "type": "string"
     },
     "fix": {
      "type": "string"
     }
    },
    "required": [
     "severity",
     "where",
     "issue",
     "fix"
    ],
    "additionalProperties": false
   }
  },
  "lookahead_risk": {
   "type": "string"
  },
  "matches_rules": {
   "type": "boolean"
  },
  "notes": {
   "type": "string"
  }
 },
 "required": [
  "verdict",
  "issues",
  "lookahead_risk",
  "matches_rules",
  "notes"
 ],
 "additionalProperties": false
}
```
