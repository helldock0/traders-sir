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
 "slug": "fx_liquidity_withdrawal_reversal",
 "title": "Liquidity-withdrawal reversal: fade a large one-hour move only when the quoted spread widened during it (quotes withdrawn), with a no-spread-condition control and a scheduled-news control at stage A, on USDJPY first",
 "rules": "All times UTC. Bars: M15, labelled by open time; a bar's close time is ts + 15 minutes. Bars are sparse; locate by timestamp and never assume one bar per slot.\n\nDEFINITIONS (all computed from closed bars 0..i):\n- mid_c[i] = (bid_c[i] + ask_c[i]) / 2. The one-hour move ending at bar i is move[i] = mid_c[i] - mid_c[i-4]; valid only if i >= 4 and ts[i] - ts[i-4] <= max_gap_min (75) minutes, otherwise no signal at i.\n- ATR20[i] = F.atr_prev(F.daily_bars(m), 20) mapped to bars with daily.to_bars (known at the start of the trading day); must be finite and > 0.\n- Quoted-spread proxy of bar i: spr[i] = max(ask_o[i] - bid_o[i], ask_c[i] - bid_c[i], ask_h[i] - bid_h[i], ask_l[i] - bid_l[i]) in price units (the loader clamps ask >= bid).\n- Slot norm: slot[i] = F.minute_of_day_utc(m)[i]. norm[i] = median of spr over the previous norm_window (20) bars that share slot[i], strictly before bar i. Loop over the 96 slots, never over bars: for a slot with ascending bar indices idx, norm[idx[k]] = median(spr[idx[k-W:k]]) for k >= W (numpy sliding_window_view over the slot's spr values, median over axis 1, window r assigned to idx[r + W]) and NaN otherwise. ratio[i] = spr[i] / norm[i], used only where norm is finite and > 0. Every arm, including the control, requires norm to be defined, so all arms cover the same period.\n- Move window of bar i: [ts[i] + 15 min - 60 min, ts[i] + 15 min). With mod = the open minute-of-day of bar i: ws = (mod - 45) mod 1440 and we = (mod + 15) mod 1440. For a block [b0, b1) in minutes of day: if ws < we, the window overlaps the block when ws < b1 and b0 < we; if ws >= we, the window crosses 00:00 UTC (this includes we == 0) and overlaps when ws < b1 or b0 < we.\n- ROLLOVER block, always applied in every arm (a data-quality exclusion, not news: the asymmetric rollover widening distorts the mid price): [20:45, 22:15) = minutes [1245, 1335).\n- NEWS blocks, applied only when exclude_news is true: US blocks [12:00, 15:30) and [18:00, 20:00) = minutes [720, 930) and [1080, 1200) on every market, plus the blocks of each leg of m.sym (letters 0-2 and 3-5): JPY [03:00, 05:00) = [180, 300); EUR [06:00, 10:15) and [11:30, 12:00) = [360, 615) and [690, 720); GBP [06:00, 10:15) and [10:45, 12:00) = [360, 615) and [645, 720); AUD [00:15, 02:15) and [03:00, 05:00) = [15, 135) and [180, 300); USD and XAU have no blocks of their own. USDJPY therefore keeps exactly its four registered blocks: [03:00, 05:00), [12:00, 15:30), [18:00, 20:00) and the rollover.\n\nCANDIDATE BAR i: valid move, valid ATR20 and norm; |move[i]| >= move_atr_min * ATR20[i]; ratio[i] >= spread_ratio_min evaluated tie-safe as ratio[i] >= spread_ratio_min * (1 - 1e-9), because spreads are quantised at 0.1 pip so a true ratio is 2a/b for integers a and b and an exact tie must count as >= (spread_ratio_min = 0 is the no-spread-condition control arm and is satisfied wherever norm is defined); the move window does not overlap the rollover block; and (exclude_news is false OR the move window overlaps no NEWS block).\n\nEPISODES (one trade per episode): loop over the candidate indices only, in ascending order. Accept i if i >= last + cooldown_bars (12, three hours) and set last = i at acceptance, BEFORE any delay check, so both entry_delay_bars arms use the same episode set.\n\nORDER PLACEMENT: j = i + entry_delay_bars (0 or 1). Skip the episode if j >= m.n, or if entry_delay_bars > 0 and ts[j] - ts[i] > delay_max_gap_min (30) minutes. All signal fields are written at index j and use only information from bars <= j; never read ts[j+1] or any field of the fill bar.\n- If move[i] > 0: entry_short[j] = True (fade an up move). If move[i] < 0: entry_long[j] = True (fade a down move).\n- entry_type[j] = 0 (market at the open of bar j + 1: ask for longs, bid for shorts), valid_bars[j] = 1.\n- sl_dist[j] = stop_mult (1.0) * |move[i]|, so 1 R = the size of the move being faded; always > 0 because |move[i]| >= move_atr_min * ATR20 > 0.\n- tp_dist[j] = NaN (no target; the time exit measures the mean retracement).\n- max_bars[j] = hold_bars (8, about two hours). No exit_long / exit_short signals, no other filters, no pyramiding (the executor blocks entries while a position is open).\n\nPARAMETERS, every one read from p: spread_ratio_min (grid 0, 2), move_atr_min (grid 0.25, 0.40), exclude_news (grid true, false), entry_delay_bars (grid 0, 1); fixed: stop_mult 1.0, hold_bars 8, cooldown_bars 12, norm_window 20, max_gap_min 75, delay_max_gap_min 30.\n\nGRIDS: stage A on USDJPY runs the 16-cell grid above; it is the only place the control arms run. Stages B and C, the walk-forward and any holdout run only the hypothesis arm: spread_ratio_min 2, exclude_news true, move_atr_min 0.25, entry_delay_bars 0 and 1 (2 cells). The Director sets stage_a.grid (16 cells) and grid (2 cells) in specs/auto/fx_liquidity_withdrawal_reversal.json after the review step and before the test; the module GRID stays at the 16 cells so the checker exercises every value.\n\nSANITY COUNTS (signal bars on USDJPY M15, 2010-2017 only, counted by the Critic before any run with these exact definitions): defaults 160 at both delays; spread_ratio_min 0 2,075; exclude_news false (rollover still excluded) 567; move_atr_min 0.4 83 (271 with news included); EURUSD defaults 64 with the EUR blocks, GBPUSD 35, AUDUSD 24, EURJPY 41, GBPJPY 37, AUDJPY 17, XAUUSD 82. These are the counts after the tie-safe threshold comparison (ratio >= threshold * (1 - 1e-9)); the earlier figures (135 / 522 / 76 / 57) came from a float comparison that dropped 37 of the 106 exact-tie bars on USDJPY and were corrected at code review, before any run. A count that differs by more than about 10 percent means the window-overlap or slot-median logic is wrong and must be fixed before anything else.\n\nREPORTING (computed from the trades; stage A table and stage C): per arm the number of episodes, avg R, trade-level t and date-clustered t (R averaged per 17:00 New York trading day), the mean quoted spread at the fill bar's open in pips, gross R before spread and commission, and design years individually. Stage C additions: (a) the share of trades that exit at the stop and the mean of (mae_r - 1) on those exits, to show gap exposure; (b) avg R without the 5 trading days with the largest total R (a diagnostic, not a gate: removing the best 5 of about 123 days costs about 0.05-0.07 R by construction even if the effect is real); (c) episodes whose move window contains the 23:50 UTC Japan releases or the 06:30 UTC BoJ press conference, reported separately; (d) episodes whose move window contains 16:00 UTC in UK winter (the WM/R fix) or 00:55 UTC on a gotobi day, reported separately and removed for the fix-flow kill rule; (e) design, check and walk-forward statistics pooled over the seven non-primary markets, date-clustered across markets.",
 "params": {
  "spread_ratio_min": 2,
  "move_atr_min": 0.25,
  "exclude_news": true,
  "entry_delay_bars": 0,
  "stop_mult": 1.0,
  "hold_bars": 8,
  "cooldown_bars": 12,
  "norm_window": 20,
  "max_gap_min": 75,
  "delay_max_gap_min": 30
 },
 "grid": {
  "spread_ratio_min": [
   0,
   2
  ],
  "move_atr_min": [
   0.25,
   0.4
  ],
  "exclude_news": [
   true,
   false
  ],
  "entry_delay_bars": [
   0,
   1
  ]
 },
 "markets": [
  "USDJPY",
  "EURUSD",
  "GBPUSD",
  "AUDUSD",
  "EURJPY",
  "GBPJPY",
  "AUDJPY",
  "XAUUSD"
 ],
 "aux_markets": [],
 "timeframe": "M15"
}

# Builder module
"""Liquidity-withdrawal reversal (fx_liquidity_withdrawal_reversal): M15, long/short fade of a one-hour move made
while the quoted spread was wide against its own time-of-day norm.

Mechanism: short-term reversals are the pay of liquidity providers, and the pay is large only when liquidity supply
is scarce. In FX the scarcity shows as a widened top-of-book spread. A large one-hour move made while the spread of
the bar is at least spread_ratio_min times its norm for that 15-minute slot is treated as a price concession to the
few providers still quoting and is faded for about two hours. The same move with a normal spread is not faded.
spread_ratio_min = 0 is the no-spread-condition control (every bar whose slot norm is defined qualifies);
exclude_news = False is the scheduled-release control. Both controls run at stage A only.

Rules (all times UTC; M15 bars are labelled by open time, so a bar closes at ts + 15 min; bars are sparse, so
everything is located by timestamp and no bar per slot is assumed; every value for bar i uses bars 0..i only):

DEFINITIONS
* mid = (bid_c + ask_c) / 2. move[i] = mid[i] - mid[i-4], valid only if i >= 4 and ts[i] - ts[i-4] <= max_gap_min
  (75) minutes.
* ATR20 = F.atr_prev(F.daily_bars(m), 20) mapped to bars (known at the start of the trading day); finite and > 0.
* Spread proxy spr[i] = max(ask_o - bid_o, ask_c - bid_c, ask_h - bid_h, ask_l - bid_l), in price units.
* Slot norm: slot = minute of day of the bar open. norm[i] = median of spr over the previous norm_window (20) bars
  that share slot[i], strictly before bar i (the first norm_window bars of a slot have no norm). ratio = spr / norm,
  used only where norm is finite and > 0. Every arm, the control included, needs norm, so all arms cover one period.
* Move window of bar i = [open + 15 min - 60 min, open + 15 min). With mod = open minute of day: ws = (mod - 45)
  mod 1440 and we = (mod + 15) mod 1440. A block [b0, b1) in minutes of day overlaps the window if ws < we and
  ws < b1 and b0 < we, or if ws >= we (the window crosses 00:00 UTC, this includes we == 0) and (ws < b1 or b0 < we).
* ROLLOVER block, always applied in every arm: [20:45, 22:15) = minutes [1245, 1335). A data-quality exclusion
  (the asymmetric rollover widening distorts the mid price), not news.
* NEWS blocks, applied only when exclude_news is true: US [12:00, 15:30) and [18:00, 20:00) on every market, plus
  the blocks of each leg of m.sym (letters 0-2 and 3-5): JPY [03:00, 05:00); EUR [06:00, 10:15) and [11:30, 12:00);
  GBP [06:00, 10:15) and [10:45, 12:00); AUD [00:15, 02:15) and [03:00, 05:00); USD and XAU have none of their own.
  USDJPY therefore keeps exactly [03:00, 05:00), [12:00, 15:30), [18:00, 20:00) and the rollover block.

CANDIDATE BAR i: valid move, ATR20 finite and > 0, norm defined, |move[i]| >= move_atr_min * ATR20[i],
ratio[i] >= spread_ratio_min, the move window clear of the rollover block, and (exclude_news false or the move
window clear of every NEWS block).
Both thresholds are ">=" comparisons and an exact tie passes. Prices sit on a point grid, so a spread of exactly
twice the slot norm is common; both comparisons carry a relative tolerance of 1e-9 (TIE_TOL) so that floating-point
noise cannot decide a tie (see the comment in signals()).

EPISODES (one trade per episode): candidate indices in ascending order. Accept i if i >= last + cooldown_bars (12)
and set last = i at acceptance, BEFORE any delay check, so both entry_delay_bars arms trade the same episodes.

ORDERS: j = i + entry_delay_bars (0 or 1). Skip the episode if j >= m.n, or if entry_delay_bars > 0 and
ts[j] - ts[i] > delay_max_gap_min (30) minutes. Every field is written at index j and uses information of bars
<= j only (neither ts[j+1] nor any field of the fill bar is read):
  move[i] > 0 -> entry_short[j] (fade the up move);  move[i] < 0 -> entry_long[j] (fade the down move);
  market order at the next open (entry_type 0, valid_bars 1); sl_dist[j] = stop_mult * |move[i]| (1 R is the size
  of the move being faded, > 0 because |move[i]| >= move_atr_min * ATR20 > 0); tp_dist NaN (no target, the time
  exit measures the mean retracement); max_bars[j] = hold_bars (8, about two hours).
No exit signals, no other filters, no pyramiding (the executor blocks entries while a position is open).

Parameters (all read from p): spread_ratio_min, move_atr_min, exclude_news, entry_delay_bars, stop_mult (1.0),
hold_bars (8), cooldown_bars (12), norm_window (20), max_gap_min (75), delay_max_gap_min (30). Structural
constants fixed by the definitions: M15 bars, a 4-bar (60 minute) move, ATR over 20 trading days.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "fx_liquidity_withdrawal_reversal"
PARAMS = {"spread_ratio_min": 2, "move_atr_min": 0.25, "exclude_news": True, "entry_delay_bars": 0,
          "stop_mult": 1.0, "hold_bars": 8, "cooldown_bars": 12, "norm_window": 20, "max_gap_min": 75,
          "delay_max_gap_min": 30}
GRID = {"spread_ratio_min": [0, 2], "move_atr_min": [0.25, 0.4], "exclude_news": [True, False],
        "entry_delay_bars": [0, 1]}

# ---- structural constants fixed by the definitions (not tunables)
BAR_MIN = 15          # M15 bars
MOVE_BARS = 4         # the move is mid_c[i] - mid_c[i-4], one hour
WINDOW_MIN = 60       # nominal move window [close - 60 min, close)
ATR_DAYS = 20         # ATR20, previous 20 trading days
DAY_MIN = 1440
TIE_TOL = 1e-9        # relative tolerance that makes the ">= threshold" comparisons tie-safe (see signals())

# ---- blocks, minutes of the UTC day, half-open [b0, b1)
ROLL_BLOCKS = [(1245, 1335)]                      # 20:45-22:15, always applied
US_NEWS_BLOCKS = [(720, 930), (1080, 1200)]       # 12:00-15:30 and 18:00-20:00, every market
LEG_NEWS_BLOCKS = {
    "JPY": [(180, 300)],                          # 03:00-05:00
    "EUR": [(360, 615), (690, 720)],              # 06:00-10:15 and 11:30-12:00
    "GBP": [(360, 615), (645, 720)],              # 06:00-10:15 and 10:45-12:00
    "AUD": [(15, 135), (180, 300)],               # 00:15-02:15 and 03:00-05:00
    "USD": [],
    "XAU": [],
}


def _as_bool(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y")
    return bool(v)


def _news_blocks(sym: str) -> list[tuple[int, int]]:
    """US blocks on every market plus the blocks of each leg of the symbol (letters 0-2 and 3-5)."""
    s = sym.upper()
    blocks = list(US_NEWS_BLOCKS)
    for leg in (s[:3], s[3:6]):
        blocks += LEG_NEWS_BLOCKS.get(leg, [])
    return blocks


def _window_hits(open_min: np.ndarray, blocks: list[tuple[int, int]]) -> np.ndarray:
    """True where the nominal one-hour move window ending at the close of the bar overlaps any block.

    The window is [open + 15 - 60, open + 15) in minutes of day: ws = (mod - 45) mod 1440, we = (mod + 15) mod 1440.
    If ws < we the window sits inside one day; if ws >= we it crosses 00:00 UTC (we == 0 included)."""
    ws = (open_min - (WINDOW_MIN - BAR_MIN)) % DAY_MIN
    we = (open_min + BAR_MIN) % DAY_MIN
    crosses = ws >= we
    hit = np.zeros(open_min.shape[0], dtype=bool)
    for b0, b1 in blocks:
        plain = (ws < b1) & (b0 < we)
        wrapped = (ws < b1) | (b0 < we)
        hit |= np.where(crosses, wrapped, plain)
    return hit


def _slot_norm(spr: np.ndarray, slot: np.ndarray, window: int) -> np.ndarray:
    """Median of spr over the previous `window` bars that share the slot, strictly before each bar; NaN before that.

    Loops over the slots only. For a slot with ascending bar indices idx, window r covers idx[r:r+window] and is
    assigned to idx[r+window], the next occurrence of the slot, so a bar never sees itself or anything later."""
    norm = np.full(spr.shape[0], np.nan)
    for sl in np.unique(slot):
        idx = np.flatnonzero(slot == sl)
        if idx.size <= window:
            continue
        wins = sliding_window_view(spr[idx], window)[:-1]    # drop the last window: its successor does not exist
        norm[idx[window:]] = np.median(wins, axis=1)
    return norm


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    if m.tf.upper() != "M15":
        raise ValueError(f"{NAME} is defined on M15 bars only, got {m.tf}")
    n = m.n
    if n <= MOVE_BARS:
        return s

    # ---- one-hour move ending at each bar: valid only when the four bars back span <= max_gap_min minutes
    mid = 0.5 * (m.bid_c + m.ask_c)
    span_min = (m.ts[MOVE_BARS:] - m.ts[:-MOVE_BARS]) / np.timedelta64(1, "m")
    move = np.full(n, np.nan)
    move[MOVE_BARS:] = np.where(span_min <= float(p["max_gap_min"]), mid[MOVE_BARS:] - mid[:-MOVE_BARS], np.nan)

    # ---- ATR20, known at the start of the trading day
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, ATR_DAYS))

    # ---- quoted-spread proxy and its norm for the same 15-minute slot (previous occurrences only)
    spr = np.maximum(np.maximum(m.ask_o - m.bid_o, m.ask_c - m.bid_c),
                     np.maximum(m.ask_h - m.bid_h, m.ask_l - m.bid_l))
    slot = F.minute_of_day_utc(m)
    norm = _slot_norm(spr, slot, int(p["norm_window"]))

    # ---- candidate bars
    # Ties at a threshold must pass (">=") and floating-point noise must not decide them. Quoted prices are
    # quantised at one point (0.1 pip on FX), so a spread is a whole number of points a and the slot norm (median of
    # an even number of values) a multiple of half a point, b/2: a true ratio is 2a/b for integers a and b, and a bar
    # spread of exactly twice the norm (1.0 pip against 0.5 pip) is common. In floats spr / norm then lands on
    # 2 +/- 1e-12 and a plain `ratio >= 2` keeps some exact ties and drops others. Anything within 1e-9 (relative)
    # of a threshold is an exact tie: the float noise is at most about 1e-10 relative, and a genuine non-tie ratio
    # would need a slot norm above 5e8 points to fall inside the tolerance. A relative tolerance is used, not spreads
    # rounded to points, because it keeps the ratio invariant under Market.widen_spread (cost stress), where rounding
    # widened half-points is not scale-invariant. The move threshold gets the same tolerance for consistency.
    with np.errstate(invalid="ignore", divide="ignore"):
        norm_ok = np.isfinite(norm) & (norm > 0)
        ratio = np.where(norm_ok, spr / norm, np.nan)
        abs_move = np.abs(move)
        cand = (np.isfinite(move) & (abs_move > 0) & np.isfinite(atr) & (atr > 0) & norm_ok
                & (abs_move >= float(p["move_atr_min"]) * atr * (1.0 - TIE_TOL))
                & (ratio >= float(p["spread_ratio_min"]) * (1.0 - TIE_TOL)))
    cand &= ~_window_hits(slot, ROLL_BLOCKS)
    if _as_bool(p["exclude_news"]):
        cand &= ~_window_hits(slot, _news_blocks(m.sym))

    # ---- episodes: accepted before any delay check, so every delay arm trades the same episodes
    cooldown = int(p["cooldown_bars"])
    last = -(1 << 60)
    episodes = []
    for i in np.flatnonzero(cand).tolist():
        if i >= last + cooldown:
            episodes.append(i)
            last = i
    if not episodes:
        return s

    # ---- orders, written at j = i + entry_delay_bars from information of bars <= j
    delay = int(p["entry_delay_bars"])
    ei = np.asarray(episodes, dtype=np.int64)
    ej = ei + delay
    keep = ej < n
    if delay > 0:
        ej_c = np.minimum(ej, n - 1)
        gap_min = (m.ts[ej_c] - m.ts[ei]) / np.timedelta64(1, "m")
        keep &= gap_min <= float(p["delay_max_gap_min"])
    ei, ej = ei[keep], ej[keep]
    if ei.size == 0:
        return s

    mv = move[ei]
    fade_short = mv > 0                       # fade an up move
    s.entry_short[ej[fade_short]] = True
    s.entry_long[ej[~fade_short]] = True
    s.sl_dist[ej] = float(p["stop_mult"]) * np.abs(mv)
    s.max_bars[ej] = int(p["hold_bars"])
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
  "path": "D:\\Traders sir\\strategies\\auto\\fx_liquidity_withdrawal_reversal.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 97,
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
   "n_entries": 97,
   "aux_markets": []
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/fx_liquidity_withdrawal_reversal/critic_code.json.

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
