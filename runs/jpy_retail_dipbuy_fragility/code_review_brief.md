# Programme charter (shared by every role)

Goal (set by the user on 2026-10-14): strategies, or a basket of them with the parked USDJPY legs, that pass the
Alpha Capital "Alpha Swing" $10k challenge (phase 1 +10%, phase 2 +5%, 10% static max loss, 5% daily loss,
>= 3 trading days per phase, no time limit, 1:30 FX leverage; indices and metals allowed) WITHIN 60 DAYS in at
least half of the challenge starts since 2018, losing the account within 60 days in at most 15%. Slower edges are
recorded, not traded. What that needs: about +15.5% net inside two months under the loss limits, so roughly 8%
a month at about 4% monthly volatility (monthly Sharpe near 2). The parked basket (vol-box, vol-gotobi, fade,
month-end USD bid; runs/basket) earns 3% a month at 8% volatility, monthly Sharpe 0.4, and passes within 60 days
about 1 time in 4. So a new strategy must bring, after costs, avg R x sqrt(trades per month) of about 0.7 or more
(monthly Sharpe 1; design t of about 10 over eight years) and be weakly correlated with the parked legs; four such
strategies would reach the target. Nothing measured here or in the 171 earlier tests is close (the best, the gotobi
short, scores 0.3). Many trades a month at a modest R or a few at a large R both qualify; costs cap the first and
rarity caps the second. An honest negative is a valuable result; a flattering backtest that fails live is the worst
outcome. Nothing here is a guarantee; the output is a probability.

Data: Dukascopy 1-minute bid and ask bars, 2010 to 2026, for 28 FX pairs, XAUUSD, XAGUSD and index CFDs
(US500, US100, US30, GER40, UK100, JP225; indices start 2011-2013 and are patchy before 2014). Resampled
timeframes M3, M5, M15, M30, H1, H2, H3, H4, H8, D1, W1 (daily and weekly bars close 17:00 New York).
Spreads are raw Dukascopy spreads; costs on top: $7 per lot round turn (FX), 0.2 pip slippage on market
and stop fills, swap from real policy rates with a 1% markup. Every result is after costs.

External inputs (data/external, described in its README): an economic calendar with consensus and actual
values and standardised surprises (2010 to 2025-04), CFTC positioning by trader group for 7 currencies, the
USD index, S&P 500, Nasdaq-100 and gold (2010 to 2026), CBOE implied-volatility indices (VIX, VXN, EVZ,
GVZ, OVX), and Japanese retail positioning from TFX Click 365: tfx_daily (daily open interest, volume and settlement
per pair since 2005, a direction-free retail-flow proxy: open interest rising on a down day is dip-buying; usable in
the design years) and tfx (weekly long and short positions for 33 pairs, 2022-11 on; holdout-era conditioning only).
Every row is usable only from its release time (ts_avail). These are new dimensions: the price, clock and
calendar-date dimensions of the store have been measured exhaustively.

Time splits: design 2010-2017, check 2018-2023, holdout 2024-2026. The holdout is locked. Nothing in
stages A-C sees a holdout bar. A strategy reaches the holdout once, when promoted, and that run is counted.

Protocol:
1. Every hypothesis is pre-registered: economic mechanism, exact rules, parameter ranges, the primary
   market, expected design t and average R, expected trades per month (the speed bar: avg R x sqrt(trades per
   month) >= 0.7 after costs, or a stated path to it in a basket), minimum trades, and a kill rule, all written
   before any run.
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

External series: when the hypothesis lists ext_series (calendar, cot, vol, tfx, tfx_daily), they are attached as m.ext[name]
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
 "slug": "jpy_retail_dipbuy_fragility",
 "title": "Retail dip-buying fragility: short a yen cross at the Tokyo open after a five-day decline of at least 1 x ATR20 during which the TFX Click 365 retail open interest grew by 10 or 15 percent or more, against a light-accumulation control (open interest up at most 2 percent on the same decline), holding 2 or 4 weekdays",
 "rules": "All times UTC. H1 bars, stamped at the bar open and sparse; locate every time by timestamp (m.ts for opens, m.close_times() for closes). Loop over TFX rows (about 250 a year), vectorise everything else.\n\nTFX ROWS: t = F.ext_series(m, 'tfx_daily'); keep rows with symbol == m.sym (the price-store symbol column; raise if none) in ts_avail order (ts_avail = Click 365 trading date + 1 day at 00:00 UTC). For row r (TFX date d_r): oi_g_r = oi_r / oi_(r-5) - 1 over the previous five TFX rows (oi_lookback 5); undefined when fewer than five earlier rows exist or any of the six oi values is <= 0.\n\nPRICE CONDITION, from the store's own daily bars: daily = F.daily_bars(m) (trading days closing 17:00 New York); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), known at the day start. At the signal bar (below) the last completed trading day is D (the trading day before the one containing the signal bar). Require daily.date[D] == d_r (the Click 365 day d_r ends at the New York close of d_r, so the two venues describe the same day; skip the row when they do not match, which happens around holidays that one venue observes). drop_atr = (daily.c[D] - daily.c[D - ret_lookback]) / ATR20[sig] with ret_lookback 5 (five trading days). Condition: drop_atr <= -k (k 1.0 or 1.5). Skip if D - 5 < 0 or ATR20[sig] is not finite or <= 0.\n\nBANDS (p['band']): 'heavy10': oi_g_r >= 0.10; 'heavy15': oi_g_r >= 0.15; 'light': oi_g_r <= 0.02 (the control: the same decline without retail accumulation, including days the book shrank). Raise ValueError on any other value. A row trades only if its band condition and the price condition both hold.\n\nSIGNAL BAR AND ENTRY: T = ts_avail of the row (00:00 UTC). sig = the bar whose close time == T (the 23:00-00:00 UTC bar); if no bar closes exactly at T, use the first bar with close time >= T provided close - T <= max_delay_min (120) minutes and the bar's UTC date equals T's date, else skip (a Friday TFX row has T on Saturday and is always skipped). Short only: entry_short[sig] = True, entry_type[sig] = 0, valid_bars[sig] = 1; the fill is at the open of bar sig + 1 (normally the 00:00 UTC bar, 09:00 Tokyo) on the bid plus slippage. One position at a time: an entry while a position is open is ignored by the executor, so overlapping decline days produce one trade per hold.\n\nSTOP: sl_dist[sig] = sl_atr x ATR20[sig] (sl_atr 1.0, price units, > 0). tp_dist NaN (no target), max_bars 0.\n\nEXIT: exit date E = the hold_days-th weekday (Monday to Friday) after the UTC date of bar sig + 1 (hold_days 2 or 4; weekends skipped, holidays not); target = E at exit_utc (20:30). xi = F.first_bar_at_or_after(m, E, 20, 30); if xi < m.n and xi > sig + 1: exit_short[xi - 1] = True (close at the open of the first bar at or after the target). Causal fallback: for each signalled row k set exit_short True on every bar j with m.ts[j] >= target_k and j <= sig_(k+1) (the signal bar of the next signalled row, or m.n - 1 for the last), so a missing target bar closes the position at the first bar after the gap and never carries it into the next trade; a marker on sig_(k+1) acts at the open of the next fill bar, where the executor checks only the stop. Leftover guard: exit_short[sig_k] = True. Markers with no open position are ignored. No other exits, no other filters.\n\nPARAMETERS (every one read from p): band (grid 'heavy10', 'heavy15', 'light'), k (grid 1.0, 1.5), hold_days (grid 2, 4); fixed sl_atr 1.0, oi_lookback 5, ret_lookback 5, exit_utc '20:30', max_delay_min 120, atr_n 20. Module GRID = the full 12 cells so the checker exercises every value. Spec grids: stage A on AUDJPY runs all 12 cells (the 'light' cells are the control arm and run only there); stages B, C, the walk-forward and any holdout run band in ('heavy10', 'heavy15') only (8 cells). The Director sets specs/auto/jpy_retail_dipbuy_fragility.json after the review step so that stage_a.grid holds the 12 cells and grid holds the two heavy bands.\n\nEXPECTED COUNTS (AUDJPY design 2010-2017, from the TFX and daily tables, a check for the Builder and the checker): about 460 qualifying decline days at k 1.0 (about 270 at 1.5) before the band split and the overlap skips; heavy10 about 45 percent of them, heavy15 about 30 percent, light about 15 percent; about 80 to 120 heavy trades and 30 to 45 light trades after the one-position-at-a-time rule. A count far from these means the symbol subset, the day alignment or the open-interest ratio is wrong.\n\nREPORTING (from the trades; all 12 stage A rows read from the trials table, stage 'A'): per cell the number of trades, avg R, trade-level t, by-year avg R, mean fill spread in pips and as a share of the stop, for design and for check; for the chosen heavy cell: the matching light cell (same k and hold_days) and the other heavy band at the same k and hold_days, the avg R after dropping the best ceil(N/10) entry dates, the avg R of entries inside the three largest drawdown months of the design years against the rest, and the per-year heavy-minus-light difference in design and check.",
 "params": {
  "band": "heavy10",
  "k": 1.0,
  "hold_days": 2,
  "sl_atr": 1.0,
  "oi_lookback": 5,
  "ret_lookback": 5,
  "exit_utc": "20:00",
  "max_delay_min": 120,
  "atr_n": 20
 },
 "grid": {
  "band": [
   "heavy10",
   "heavy15",
   "light"
  ],
  "k": [
   1.0,
   1.5
  ],
  "hold_days": [
   2,
   4
  ]
 },
 "markets": [
  "AUDJPY",
  "NZDJPY",
  "USDJPY",
  "GBPJPY",
  "EURJPY"
 ],
 "aux_markets": [],
 "ext_series": [
  "tfx_daily"
 ],
 "timeframe": "H1"
}

# Builder module
"""Retail dip-buying fragility on the yen crosses: short a cross at the Tokyo open after a five-day decline of at
least k x ATR20 during which the TFX Click 365 retail open interest grew heavily, hold 2 or 4 weekdays.

Mechanism: Japanese retail margin traders (Click 365 is the exchange-traded slice) are structurally long the yen
crosses and contrarian: they add longs as the cross falls. The positions are 10 to 25 times levered with broker
losscuts, so a book that grew heavily into a decline is latent forced supply; if the decline extends, losscuts fire
in a cascade. Hypothesis (one-sided, fixed before any run): after heavy accumulation into weakness a short has a
positive expectation over the next days; the "light" band (the same decline without accumulation) is the control.

Rules (all times UTC; H1 bars are stamped at the bar open and are sparse, so every time is located by timestamp:
m.ts for opens, m.close_times() for closes):

  ROWS     tfx_daily rows with symbol == m.sym, in ts_avail order (ts_avail = Click 365 date + 1 day at 00:00 UTC).
           oi_g[r] = oi[r] / oi[r - L] - 1 over the previous L = oi_lookback rows (rows, not calendar days);
           undefined when r < L or when any of the L + 1 values oi[r-L..r] is not > 0. No whole-sample statistic.
           ValueError if the symbol has no rows.
  PRICE    daily = F.daily_bars(m) (trading days closing 17:00 New York); ATR20 = F.atr_prev(daily, atr_n), known
           at the day start. At the signal bar sig, D = the trading day before the one containing sig. Require
           daily.date[D] == the date of the row (otherwise skip: a holiday that one venue observes),
           D - ret_lookback >= 0 and ATR20[sig] finite and > 0.
           drop_atr = (daily.c[D] - daily.c[D - ret_lookback]) / ATR20[sig]; condition drop_atr <= -k
           (k 1.0 or 1.5).
  BAND     heavy10: oi_g >= 0.10; heavy15: oi_g >= 0.15; light: oi_g <= 0.02 (control: the same decline without
           accumulation, including days the book shrank). Any other value raises ValueError. A row qualifies only
           if its band condition and the price condition both hold.
  SIGNAL   T* = the first 00:00 UTC at or after ts_avail that falls on Monday to Friday (ts_avail itself for
           Monday-Thursday rows, the following Monday 00:00 UTC for Friday rows). sig = the bar whose close time
           equals T* (the 23:00-00:00 UTC bar; on Sunday night it belongs to the Monday trading day); if no bar
           closes exactly at T*, the first bar with close time >= T*, provided close - T* <= max_delay_min (120)
           minutes and the close is on the UTC date of T*; otherwise the row is skipped.
  ENTRY    short only: entry_short[sig], market order (entry_type 0, valid_bars 1), filled at the open of bar
           sig + 1 (normally 00:00 UTC = 09:00 Tokyo) on the bid minus slippage.
  STOP     sl_dist[sig] = sl_atr x ATR20[sig] (price units, sl_atr 1.0). No target (tp_dist NaN), max_bars 0.
  EXIT     E = the hold_days-th Monday-to-Friday date after the UTC date of bar sig + 1 (hold_days 2 or 4; holidays
           are not skipped); target = E at exit_utc (20:00); xi = the first bar with open >= target. Primary
           marker: exit_short[xi - 1] (close at the open of the first bar at or after the target), set only when
           xi < m.n and xi > sig + 1. Causal fallback: exit_short is also True on every bar j with
           m.ts[j] >= target and j <= the signal bar of the next KEPT row (m.n - 1 for the last kept row), so a
           missing target bar closes the position at the first bar after the gap and never carries it into the
           next trade. The bar whose close is the first at or after the target (xi - 1 whenever that bar
           straddles the target) is marked as well: the same bar as the primary marker, but decided from its own
           close time, so it does not need bar xi to exist. No other exits, no other filters.
  DE-OVERLAP (planned hold, replaces any leftover guard): the qualifying rows of the active band are walked in
           time order; a row is kept only if m.ts[sig] >= the target of the last KEPT row (the first kept row has
           no condition). A dropped row sets no entry and no markers; a trade stopped early does not reopen the
           window, because the window is the planned one.

Parameters (every one read from p): band, k, hold_days (the grid), and the fixed sl_atr 1.0, oi_lookback 5,
ret_lookback 5, exit_utc "20:00", max_delay_min 120, atr_n 20. GRID is the full 12 cells; the pipeline spec runs
all 12 on AUDJPY in stage A (the "light" cells are the control) and band in (heavy10, heavy15) elsewhere.

Closed-bar information only: a row is used from sig, whose close time is >= T* >= ts_avail; the price condition
uses completed trading days and the ATR known at the day start. Whether a later bar exists never decides whether a
row trades (so a truncated sample gives the same signals on its prefix); a row whose exit target lies beyond the
last bar simply has no primary exit marker and runs to the end of the data.

Note on the time exit: exit_utc 20:00 is the open of the 20:00 UTC bar. In the months with New York on daylight time
that is the last Friday H1 bar (the 17:00 New York close is 21:00 UTC), so a target on a Friday exits on the Friday and
no position is carried over the weekend; on every other day it is before the 21:00 UTC rollover hour. (The earlier
20:30 default fell through to the Sunday evening open for Friday targets in those months.)
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "jpy_retail_dipbuy_fragility"
PARAMS = {"band": "heavy10", "k": 1.0, "hold_days": 2, "sl_atr": 1.0, "oi_lookback": 5, "ret_lookback": 5,
          "exit_utc": "20:00", "max_delay_min": 120, "atr_n": 20}
GRID = {"band": ["heavy10", "heavy15", "light"], "k": [1.0, 1.5], "hold_days": [2, 4]}

# The band definitions are part of the pre-registration (the band name is the parameter): thresholds on the
# five-row open-interest growth, as (direction, threshold).
BANDS = {"heavy10": (">=", 0.10), "heavy15": (">=", 0.15), "light": ("<=", 0.02)}
_EPS = 1e-9   # float guard so a ratio of exactly 1.15 (integer contracts) counts as >= 0.15


def _symbol_rows(m: Market):
    """The tfx_daily rows of the symbol of this market, in ts_avail order (the symbol column holds None for pairs
    that are not in the price store, so the comparison is done value by value)."""
    sym_col = F.ext_series(m, "tfx_daily").column("symbol")
    mask = np.fromiter((v == m.sym for v in sym_col), dtype=bool, count=len(sym_col))
    if not mask.any():
        raise ValueError(f"tfx_daily has no rows for symbol {m.sym!r}")
    return F.ext_subset(m, "tfx_daily", mask)


def _oi_growth(oi: np.ndarray, lag: int) -> np.ndarray:
    """oi[r] / oi[r - lag] - 1 over rows; NaN when r < lag or any of oi[r-lag..r] is not finite and > 0."""
    n = len(oi)
    out = np.full(n, np.nan)
    if lag < 1 or n <= lag:
        return out
    bad = ~(np.isfinite(oi) & (oi > 0))
    bad_cum = np.concatenate([[0], np.cumsum(bad)])            # bad_cum[i] = number of bad values in oi[:i]
    r = np.arange(lag, n)
    clean = (bad_cum[r + 1] - bad_cum[r - lag]) == 0           # window oi[r-lag .. r] has no bad value
    r = r[clean]
    out[r] = oi[r] / oi[r - lag] - 1.0
    return out


def _band_mask(oi_g: np.ndarray, band: str) -> np.ndarray:
    direction, thr = BANDS[band]
    with np.errstate(invalid="ignore"):
        hit = (oi_g >= thr - _EPS) if direction == ">=" else (oi_g <= thr + _EPS)
    return np.isfinite(oi_g) & hit


def _next_weekday_midnight(ts_avail: np.ndarray) -> np.ndarray:
    """First 00:00 UTC at or after ts_avail that falls on Monday to Friday (datetime64[us])."""
    day = ts_avail.astype("datetime64[D]")
    day = day + (ts_avail > day.astype("datetime64[us]")).astype("timedelta64[D]")   # ceil to midnight (no-op here)
    wd = F.weekday(day)                                                              # Monday = 0 ... Sunday = 6
    day = day + np.where(wd == 5, 2, np.where(wd == 6, 1, 0)).astype("timedelta64[D]")
    return day.astype("datetime64[us]")


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    band = str(p["band"])
    if band not in BANDS:
        raise ValueError(f"unknown band {band!r}; expected one of {sorted(BANDS)}")
    rows = _symbol_rows(m)
    if m.n < 2:
        return s

    k = float(p["k"])
    hold = int(p["hold_days"])
    back = int(p["ret_lookback"])
    xh, xm = F.parse_hhmm(p["exit_utc"])

    # ---- per-row quantities (rows are in ts_avail order); nothing here looks past the signal bar
    r_date = rows.column("date").astype("datetime64[D]")                 # Click 365 trading date
    oi_g = _oi_growth(rows.column("oi"), int(p["oi_lookback"]))
    t_star = _next_weekday_midnight(rows.ts_avail)                       # T*: Friday rows move to Monday 00:00 UTC
    close = m.close_times()
    sig = np.searchsorted(close, t_star, side="left")                    # first bar closing at or after T*
    sc = np.minimum(sig, m.n - 1)
    ok = sig < m.n
    ok = ok & ((close[sc] - t_star) <= np.timedelta64(int(p["max_delay_min"]), "m"))
    ok = ok & (close[sc].astype("datetime64[D]") == t_star.astype("datetime64[D]"))

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))             # ATR of the previous days, known at day start
    d_prev = daily.day_idx[sc] - 1                                       # D: last completed trading day at the signal
    d_back = d_prev - back
    ok = ok & (d_back >= 0)
    dp = np.clip(d_prev, 0, daily.n - 1)
    db = np.clip(d_back, 0, daily.n - 1)
    ok = ok & (daily.date[dp] == r_date)                                 # both venues describe the same day
    a = atr[sc]
    ok = ok & np.isfinite(a) & (a > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        drop_atr = (daily.c[dp] - daily.c[db]) / a
    ok = ok & np.isfinite(drop_atr) & (drop_atr <= -k)
    ok = ok & _band_mask(oi_g, band)

    q = np.flatnonzero(ok)
    if q.size == 0:
        return s
    sig_q = sig[q]

    # ---- planned exit per qualifying row: the hold_days-th weekday after the date of the fill bar, at exit_utc
    fill_i = np.minimum(sig_q + 1, m.n - 1)
    # the fill bar opens at T* (00:00 UTC) in practice; when it does not exist yet (end of data) the date of T* is used
    base = np.where(sig_q + 1 < m.n, m.ts[fill_i].astype("datetime64[D]"), t_star[q].astype("datetime64[D]"))
    exit_day = np.busday_offset(base, hold, roll="backward")             # hold-th Monday-Friday date after base
    target = exit_day.astype("datetime64[us]") + np.timedelta64(xh * 60 + xm, "m")
    xi_q = np.searchsorted(m.ts, target, side="left")                    # first bar with open >= target
    j0_q = np.searchsorted(close, target, side="left")                   # first bar with close >= target (xi - 1 or xi)

    # ---- planned-hold de-overlap: keep a row only if its signal bar is at or after the target of the last kept row
    ts_sig = m.ts[sig_q]
    kept = []
    target_prev = None
    for j in range(q.size):
        if target_prev is not None and ts_sig[j] < target_prev:
            continue                                                     # dropped: no entry, no markers
        kept.append(j)
        target_prev = target[j]
    kept_a = np.asarray(kept, dtype=np.int64)
    k_sig = sig_q[kept_a]
    k_xi = xi_q[kept_a]
    k_j0 = j0_q[kept_a]

    # ---- entries
    s.entry_short[k_sig] = True
    s.entry_type[k_sig] = 0
    s.valid_bars[k_sig] = 1
    s.sl_dist[k_sig] = float(p["sl_atr"]) * atr[k_sig]

    # ---- exits: primary marker at xi - 1, plus the causal fallback up to the signal bar of the next kept row
    fallback_end = np.append(k_sig[1:], m.n - 1)
    for sg, xi, j0, hi in zip(k_sig.tolist(), k_xi.tolist(), k_j0.tolist(), fallback_end.tolist()):
        if xi < m.n and xi > sg + 1:
            s.exit_short[xi - 1] = True
        if xi <= hi:
            s.exit_short[xi:hi + 1] = True
        # causal form of the primary marker: the bar whose close is the first at or after the target is xi - 1 when
        # that bar straddles the target (always, except around holiday gaps), and its close time alone shows that the
        # target has passed, so this marker does not need the next bar to exist (same bar as the primary marker)
        if sg < j0 <= hi:
            s.exit_short[j0] = True
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
  "path": "D:\\Traders sir\\strategies\\auto\\jpy_retail_dipbuy_fragility.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 137,
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
   "ext_release": {
    "ok": true,
    "probes": [
     {
      "k": 23,
      "release": "2010-01-01T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 12526,
      "release": "2011-12-31T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 24994,
      "release": "2013-12-31T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 37446,
      "release": "2015-12-31T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 49911,
      "release": "2017-12-29T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 62363,
      "release": "2019-12-31T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 74829,
      "release": "2021-12-30T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 87316,
      "release": "2023-12-29T00:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     }
    ]
   },
   "n_entries": 137,
   "aux_markets": [],
   "ext_series": [
    "tfx_daily"
   ]
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/jpy_retail_dipbuy_fragility/critic_code.json.

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
