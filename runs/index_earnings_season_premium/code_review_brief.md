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

External inputs (data/external, described in its README): an economic calendar with consensus and actual
values and standardised surprises (2010 to 2025-04), CFTC positioning by trader group for 7 currencies, the
USD index, S&P 500, Nasdaq-100 and gold (2010 to 2026), CBOE implied-volatility indices (VIX, VXN, EVZ,
GVZ, OVX), and Japanese retail positioning from TFX Click 365 (weekly long and short positions for 33 pairs,
2022-11 on; short history, so design-period tests are impossible and it serves holdout-era conditioning only).
Every row is usable only from its release time (ts_avail). These are new dimensions: the price, clock and
calendar-date dimensions of the store have been measured exhaustively.

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
  F.ext_series(m, name), F.ext_subset(m, name, mask), F.ext_asof(m, name, col), F.ext_recent(m, name, minutes, col=None),
  F.ext_minutes_since(m, name)   (external series: calendar, cot, vol; see below)

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

External series: when the hypothesis lists ext_series (calendar, cot, vol, tfx), they are attached as m.ext[name]
(an ExtSeries: .ts_avail per row, .column(col), .columns; see data/external/README.md for the columns). Read them
only through F.ext_asof(m, name, col) (value of the last row usable at each bar's close), F.ext_recent(m, name,
minutes, col=None) (a row became usable within the last `minutes`; or that row's value), F.ext_minutes_since(m, name),
and F.ext_subset(m, name, mask) (rows selected by a mask over e.column(...), for example high-impact USD releases;
the result can be passed to the same helpers). Rows are usable only from ts_avail; the leak tests cut the series
there and perturb its numbers beyond, so reading a release early is caught.

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


--- example strategy: strategies/oracle/ext_surprise_follow_example.py ---
"""Example strategy for the external series (a template, not a measured claim): follow the first move after a
large macro surprise.

When a high-impact release for the quote or base currency comes out with |surprise_z| >= z_min (calendar series,
standardised against that event's earlier surprises), wait `delay_min` minutes, then enter in the direction of the
move since the release (bid close now vs the last bar closed before the release), stop = sl_atr x ATR20, time exit
after `hold_min` minutes. Shows every external helper: F.ext_series / F.ext_subset to pick rows, F.ext_recent for
"a release happened in the last N minutes", F.ext_asof for the latest value, and F.ext_minutes_since.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "ext_surprise_follow_example"
PARAMS = {"z_min": 1.0, "delay_min": 15, "hold_min": 120, "sl_atr": 0.25, "currencies": "USD,JPY"}
GRID = {"z_min": [1.0, 2.0], "delay_min": [15, 30]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    cal = F.ext_series(m, "calendar")
    ccy = cal.column("currency")
    want = np.isin(ccy, [c.strip().upper() for c in str(p["currencies"]).split(",")])
    z = cal.column("surprise_z")
    big = want & (cal.column("impact") == "high") & np.isfinite(z) & (np.abs(z) >= p["z_min"])
    rel = F.ext_subset(m, "calendar", big)                 # the releases we react to
    if rel.n == 0:                                         # nothing usable yet (for example a truncated sample)
        return s
    since = F.ext_minutes_since(m, rel)                    # minutes from the last such release to each bar's close
    bar_min = F.minute_of_day_utc(m)
    step = int(np.median(np.diff(bar_min[:1000])[np.diff(bar_min[:1000]) > 0])) if m.n > 1000 else 1
    # the first bar that closes at least delay_min after the release
    trigger = (since >= p["delay_min"]) & (since < p["delay_min"] + step)
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))
    close = m.bid_c
    idx_rel = np.searchsorted(rel.ts_avail, m.close_times(), side="right") - 1   # index of the last release per bar
    # reference price: last bar closed before that release (its close is public information at the release time)
    ref_bar = np.searchsorted(m.close_times(), rel.ts_avail[np.clip(idx_rel, 0, max(rel.n - 1, 0))], side="left") - 1
    valid = trigger & (idx_rel >= 0) & (ref_bar >= 0) & np.isfinite(atr) & (atr > 0)
    move = np.zeros(m.n)
    move[valid] = close[valid] - close[ref_bar[valid]]
    hold_bars = max(int(round(p["hold_min"] / max(step, 1))), 1)
    long = valid & (move > 0)
    short = valid & (move < 0)
    s.entry_long[long] = True
    s.entry_short[short] = True
    s.sl_dist[valid] = p["sl_atr"] * atr[valid]
    s.max_bars[valid] = hold_bars
    return s



# Hypothesis
{
 "slug": "index_earnings_season_premium",
 "title": "Aggregate earnings-announcement premium: hold the Nasdaq 100 CFD long Monday-to-Friday only in the weeks when most S&P 500 and Nasdaq 100 companies report (weeks 2 to 6 after each quarter-end), with every other week of the year as the control arm; replication on the S&P 500 and Nikkei 225 CFDs",
 "rules": "All times UTC. Bars: H1, stamped at the bar OPEN; sparse (whole hours are missing in 2013 and 2015-2017); locate every time by timestamp with F.first_bar_at_or_after and never assume one bar per hour.\n\nWEEK SELECTION (calendar, UTC): mondays = unique F.utc_dates(m) with F.weekday == 0 and date >= np.datetime64(p['start']). For each Monday d: months = d.astype('datetime64[M]'); q0 = (months - (months.astype(np.int64) % 12 % 3).astype('timedelta64[M]')).astype('datetime64[D]') = the first day of the calendar quarter containing d; off = (d - q0).astype(int) in days (0..91). Unit check: 2015-02-16 gives q0 2015-01-01 and off 46; 2015-04-13 gives off 12. s0 = start_off + (jp_shift_days if m.sym starts with 'JPN' else 0). season(d) = s0 <= off < s0 + 7 * n_weeks. arm 'season' keeps Mondays with season(d) true; arm 'ctrl' keeps the others (every other week of the year); raise ValueError on any other arm value. US and Japanese holidays are not excluded; holiday Mondays that have a 15:00 UTC CFD bar are traded (expected).\n\nENTRY (decided from Monday information only): (eh, em) = F.parse_hhmm(p['entry_utc']) = 14:30; ei = F.first_bar_at_or_after(m, d, eh, em), which is the 15:00 UTC bar on a normal Monday. Skip the week only if ei < 1, or ei >= m.n, or m.ts[ei] is more than max_delay_min (90) minutes after d 14:30 UTC, or ATR20[ei] is not finite or <= 0. No skip may depend on any bar after ei. sig = ei - 1 (the 14:00 bar); the fill is at the open of bar ei, i.e. 15:00 UTC = 11:00 New York in daylight time, 10:00 in winter (ask side plus slippage). entry_long[sig] = True; entry_type[sig] = 0; valid_bars[sig] = 1. Long only in both arms; the control arm measures the drift and cost that the season arm must beat.\n\nSTOP: daily = F.daily_bars(m); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), known at the start of the trading day; read it at ei, not sig. sl_dist[sig] = sl_atr x ATR20[ei] (price units, > 0). tp_dist = NaN (no target). max_bars = 0.\n\nEXIT: f = d + 4 days (the Friday of the same week); (xh, xm) = F.parse_hhmm(p['exit_utc']) = 19:30; xi = F.first_bar_at_or_after(m, f, xh, xm), which is the 20:00 UTC bar on a normal Friday (the CFD session ends at 21:00 UTC in US daylight time, so the 20:00 bar is the last Friday bar then; the fill at its open is 16:00 New York in daylight time and 15:00 in winter). (a) Normal exit: if xi < m.n and xi > ei and m.ts[xi] is no more than max_exit_delay_min (180) minutes after f 19:30 UTC, set exit_long[xi - 1] = True (the 19:00 bar), closing at the open of bar xi. (b) Causal fallback: set exit_long[j] = True on every bar j with ts in [f 20:00 UTC, d + 7 days 12:00 UTC), i.e. Friday 20:00 to the following Monday 12:00, so a week whose Friday session is missing or cut short exits at the first bar after the gap instead of running into the next trade week; markers on bars with no open position are ignored by the executor. Never skip a week because of the Friday bars. No other exits, no filters, one trade per selected week; the executor blocks overlapping entries. Follow the causal pattern of strategies/auto/carry_cross_weekend_premium.py.\n\nPARAMETERS (every one read from p): arm (grid 'season', 'ctrl'), start_off (grid 10, 17), n_weeks (grid 4, 5), sl_atr (grid 1.0, 2.0); fixed entry_utc '14:30', exit_utc '19:30', max_delay_min 90, max_exit_delay_min 180, atr_n 20, start '2013-01-01', jp_shift_days 14 (added to start_off only when m.sym starts with 'JPN', because Tokyo companies with a March year-end report about two weeks after US large caps; no effect on the primary market). Module GRID = the full 16 cells so the checker exercises arm. Spec grids: stage A on USATECHIDXUSD runs all 16 cells (the 'ctrl' cells are control arms and run only there); stages B, C, the walk-forward and any holdout run the season arm only (8 cells).\n\nEXPECTED COUNTS (USATECHIDXUSD design 2013-2017, a check for the Builder and the checker): about 80 (n_weeks 4) or 100 (n_weeks 5) calendar season weeks before the few skips, about 70-90 after; control about 140-170. A count far below that means the week selection or the Friday exit is wrong. The Friday 20:00 UTC bar exists on 565 of 609 Fridays 2012-2023 on USATECHIDXUSD.\n\nREPORTING (by the Director, from the trade lists of the chosen season cell and its matching ctrl cell, re-run with scripts/run_backtest.py --end 2024-01-01 --save-trades): per cell trades, avg R, t, season-window-clustered t (R averaged per calendar quarter of the entry date), mean fill spread in points and as a share of the stop, financing per trade in R (the engine charges 6 nights for a Monday-to-Friday hold because Wednesday is tripled), number of fallback (non-Friday-20:00) exits per arm, by-year avg R; the quarter-paired difference D_q (season mean minus non-season mean within each calendar quarter that has at least one week in each arm), its mean and t over quarters in design and in check; the same D with every week containing a scheduled FOMC decision dropped from both arms (dates from the 'Federal Funds Rate' rows of data/external/calendar_spoluan/forex_factory_calendar_YYYY.csv, which are stamped about 8 hours ahead of UTC, so '2014-01-30 03:00' is the 29 January 2014 decision); avg R and D by reporting season (January, April, July, October); the pooled date-clustered season-minus-ctrl difference over USA500IDXUSD and JPNIDXJPY.",
 "params": {
  "arm": "season",
  "start_off": 10,
  "n_weeks": 5,
  "sl_atr": 1.0,
  "entry_utc": "14:30",
  "exit_utc": "19:30",
  "max_delay_min": 90,
  "max_exit_delay_min": 180,
  "atr_n": 20,
  "start": "2013-01-01",
  "jp_shift_days": 14
 },
 "grid": {
  "arm": [
   "season",
   "ctrl"
  ],
  "start_off": [
   10,
   17
  ],
  "n_weeks": [
   4,
   5
  ],
  "sl_atr": [
   1.0,
   2.0
  ]
 },
 "markets": [
  "USATECHIDXUSD",
  "USA500IDXUSD",
  "JPNIDXJPY"
 ],
 "aux_markets": [],
 "timeframe": "H1"
}

# Builder module
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


# Automated checker results
{
 "static": {
  "ok": true,
  "issues": []
 },
 "import": {
  "ok": true,
  "error": null,
  "path": "D:\\Traders sir\\strategies\\auto\\index_earnings_season_premium.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 217,
  "leak": {
   "ok": true,
   "truncation": {
    "ok": true,
    "probes": [
     {
      "k": 29347,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 52824,
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
      "k": 29347,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 29347,
      "direction": -1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 52824,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 52824,
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
   "ext_release": {
    "ok": true,
    "probes": []
   },
   "n_entries": 217,
   "aux_markets": [],
   "ext_series": []
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/index_earnings_season_premium/critic_code.json.

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
