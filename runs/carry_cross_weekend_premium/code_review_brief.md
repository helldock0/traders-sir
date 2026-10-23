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
 "slug": "carry_cross_weekend_premium",
 "title": "Weekend risk premium in carry crosses: long AUDJPY (NZDJPY, AUDUSD, NZDUSD) from the Friday New York afternoon to the Monday Tokyo or London open, with a weekday-overnight control",
 "rules": "All times UTC. Bars: H1, labelled by open time; a bar's close time is ts + 1h. Bars are sparse; locate by timestamp.\n\nENTRY DAY: entry_day is a string parameter: \"fri\" (the hypothesis, F.weekday == 4) or \"mon\" (the weekday-overnight control, F.weekday == 0). For each UTC date D whose weekday equals entry_day, let ei = F.first_bar_at_or_after(m, [D], entry_hh, entry_mm); require ei >= 1 and m.ts[ei] no more than 60 minutes after the target time D + entry_utc, otherwise no trade on D. The signal bar is S = ei - 1 (the bar that closes at the entry time), so the market fill lands at the open of bar ei, i.e. at entry_utc (oracle pattern, strategies/oracle/m3_usd_bid.py).\n\nENTRY: entry_long[S] = True, entry_type 0 (market at the next bar's open), valid_bars 1. One trade per entry date. Longs only (long the high-yield currency: AUDJPY, NZDJPY, AUDUSD, NZDUSD, EURJPY are all quoted so that a long is long the first currency, which is the higher-yielding side in 2010-2023 for AUD and NZD; EURJPY is the low-carry comparison).\n\nSTOP: sl_dist[S] = sl_atr * ATR20_prev, ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to S; no trade if NaN or <= 0. tp_dist = NaN. A gap through the stop at the Sunday/Monday open exits at that open (executor rule).\n\nEXIT: let D_exit = D + 3 calendar days when entry_day = \"fri\" (the Monday) and D + 1 calendar day when entry_day = \"mon\" (the Tuesday). Let X = F.first_bar_at_or_after(m, [D_exit], exit_hh, exit_mm), the first H1 bar whose OPEN time is at or after exit_utc on D_exit (a Monday 00:00 target may be preceded by Sunday-evening UTC bars; first_bar_at_or_after on the Monday date handles that). Set the exit flag only if X < m.n, X - 1 > S and m.ts[X] is no more than 60 minutes after the target time; if the exit bar is missing or late the trade is NOT skipped (skipping an entry because of a future exit bar is a look-ahead and fails the truncation test) and the max_bars safety net closes it instead. Set exit_long[X - 1] = True, so the position closes at the open of the bar starting at exit_utc. Safety net: max_bars[S] = 24 for both arms (a longer net could let a missed exit run to the Wednesday triple rollover and mix in the carry the control is meant to exclude).\n\nNo other filters.\n\nREPORTING (stage C): for every arm report gross R (before spread and commission) alongside net R, the mean entry and exit spread in pips, the paired fri-minus-mon difference and its t per market, and the individual weekend trades of 2015-08 and 2020-03 (and 2024-08 only at promotion).",
 "params": {
  "entry_day": "fri",
  "entry_utc": "20:00",
  "exit_utc": "07:00",
  "sl_atr": 1.5
 },
 "grid": {
  "entry_day": [
   "fri",
   "mon"
  ],
  "entry_utc": [
   "16:00",
   "20:00"
  ],
  "exit_utc": [
   "00:00",
   "07:00"
  ],
  "sl_atr": [
   1.5,
   3.0
  ]
 },
 "markets": [
  "AUDJPY",
  "NZDJPY",
  "AUDUSD",
  "NZDUSD",
  "EURJPY"
 ],
 "aux_markets": [],
 "timeframe": "H1"
}

# Builder module
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


# Automated checker results
{
 "static": {
  "ok": true,
  "issues": []
 },
 "import": {
  "ok": true,
  "error": null,
  "path": "D:\\Traders sir\\strategies\\auto\\carry_cross_weekend_premium.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 723,
  "leak": {
   "ok": true,
   "truncation": {
    "ok": true,
    "probes": [
     {
      "k": 43669,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 78605,
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
      "k": 43669,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 43669,
      "direction": -1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 78605,
      "direction": 1.0,
      "mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 78605,
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
   "n_entries": 723,
   "aux_markets": []
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/carry_cross_weekend_premium/critic_code.json.

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
