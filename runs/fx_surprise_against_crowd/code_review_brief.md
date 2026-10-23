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
 "slug": "fx_surprise_against_crowd",
 "title": "Positioning-amplified surprise continuation: trade in the direction of a high-impact scheduled data surprise 15 minutes after the release, only when CFTC leveraged funds are crowded on the other side of that surprise, holding to the New York afternoon of the release day or of the next weekday; with surprise-agrees-with-the-crowd and uncrowded control arms that trade the same surprises",
 "rules": "All times UTC. M15 bars, stamped at the bar open and sparse; locate every time by timestamp (m.ts for opens, m.close_times() for closes), never by bar count. Loop over releases (a few hundred per market), vectorise everything else.\n\nSYMBOL CONSTANTS: base = first three letters of m.sym, quote = last three. The COT currency is the non-USD one (EUR, GBP, AUD, NZD, JPY, CAD); cot_sign = +1 when it is the base (EURUSD, GBPUSD, AUDUSD, NZDUSD) and -1 when it is the quote (USDJPY, USDCAD). Raise for any other symbol.\n\nCALENDAR EVENT SET: e = F.ext_series(m, 'calendar'); keep rows with impact == 'high', time_source == 'scraped' (rows with a typical or unknown release minute are useless for a 15-minute entry), finite surprise_z, currency in (base, quote), and an event name that does NOT contain (case-insensitive) any of: 'Crude Oil', 'Natural Gas', 'Inventories', 'Unemployment Claims', 'TIC Long', 'Votes', 'Asset Purchase Facility'. Use F.ext_subset(m, 'calendar', mask). Row direction for the pair: s_row = sign(surprise_z) x inv x side, where inv = -1 if the event name contains 'Unemployment Rate', 'Unemployment Change', 'Claimant Count', 'Net Borrowing' or 'Jobless' (a higher-than-forecast number is bad for that currency) and +1 otherwise; side = +1 if currency == base, -1 if currency == quote. Row weight w_row = |surprise_z|. Rows sharing one ts_avail (the same release minute) are merged into one release: dz = sum over those rows of s_row x w_row. A release qualifies when |dz| >= z_min; its trade direction dir = sign(dz) (+1 long the pair, -1 short). Process releases in ts_avail order.\n\nPOSITIONING STATE: c = F.ext_subset(m, 'cot', market == COT currency), rows in ts_avail order (ts_avail = 19:30 or 20:30 UTC on the Friday release). For row r with at least rank_weeks (52) rows up to and including r: rank_r = (number of those 52 rows whose spec_net_oi <= spec_net_oi_r) / 52, in (0, 1]; earlier rows have no rank. For a release at time T use the last COT row with ts_avail <= T; skip the release in every arm if that row has no rank. state = +1 if rank >= crowd_q, -1 if rank <= 1 - crowd_q, 0 otherwise. crowd_pair_dir = cot_sign x state: +1 means the leveraged funds are crowded long the pair, -1 crowded short, 0 not crowded.\n\nARMS (p['arm']): 'against': crowd_pair_dir != 0 and dir == -crowd_pair_dir (the surprise hits the crowded book); 'with': crowd_pair_dir != 0 and dir == crowd_pair_dir (the surprise agrees with the book); 'neutral': crowd_pair_dir == 0. Every arm trades in the surprise direction dir, so the first reaction, the costs and the event set are identical across arms and only the positioning state differs. Raise ValueError on any other arm value.\n\nENTRY: T = ts_avail of the release. sig = the first bar whose close time >= T + delay_min minutes (delay_min 15, so for a release on the quarter hour the bar that contains the release is the signal bar and the fill is 15 minutes after the release). Skip the release if sig >= m.n - 1, if close_times[sig] - T > max_delay_min (60) minutes (data gap), if the UTC date of bar sig differs from the UTC date of T, or if ATR20[sig] is not finite or <= 0. Market order at the next open: entry_long[sig] = True for dir +1, entry_short[sig] = True for dir -1; entry_type[sig] = 0; valid_bars[sig] = 1; the fill is at the open of bar sig + 1 (ask for longs, bid for shorts, plus slippage). One position at a time: the executor ignores an entry while a position is open, so a second qualifying release inside an open hold is not traded.\n\nSTOP: daily = F.daily_bars(m); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), the mean daily range of the previous 20 trading days, known at the day start; read at sig. sl_dist[sig] = sl_atr x ATR20[sig] (sl_atr 1.0, price units, > 0). tp_dist NaN (no target), max_bars 0.\n\nEXIT: exit date E = the UTC date of T for hold 'd0'; for hold 'd1' the next weekday (Monday to Friday) after the UTC date of T (a Friday release exits on Monday). target = E at exit_utc (20:30, i.e. 16:30 New York in daylight time, 15:30 in winter, well before the Friday close). xi = F.first_bar_at_or_after(m, E, 20, 30); if xi < m.n and xi > sig + 1: exit_long[xi - 1] = exit_short[xi - 1] = True (the position closes at the open of the first bar at or after the target). Causal fallback: for each signalled release k, set exit_long and exit_short True on every bar j with m.ts[j] >= target_k and j <= sig_(k+1) (the signal bar of the next signalled release, or m.n - 1 for the last one), so a missing target bar closes the position at the first bar after the gap and never carries it into the next release's trade; a marker on sig_(k+1) acts at the open of the next fill bar, where the executor checks only the stop, so the new trade is untouched. Leftover guard: exit_long[sig_k] = exit_short[sig_k] = True. Markers with no open position are ignored by the executor. No other exits, no other filters.\n\nPARAMETERS (every one read from p): arm (grid 'against', 'with', 'neutral'), crowd_q (grid 0.8, 0.9), z_min (grid 1.0, 1.5), hold (grid 'd0', 'd1'); fixed sl_atr 1.0, delay_min 15, max_delay_min 60, exit_utc '20:30', atr_n 20, rank_weeks 52. Module GRID = the full 24 cells so the checker exercises every value. Spec grids: stage A on EURUSD runs all 24 cells (the 'with' and 'neutral' cells are control arms and run only there); stages B, C, the walk-forward and any holdout run arm 'against' only (crowd_q x z_min x hold, 8 cells). The Director sets specs/auto/fx_surprise_against_crowd.json after the review step so that stage_a.grid holds the 24 cells and grid holds arm = against only.\n\nEXPECTED COUNTS (EURUSD design 2010-2017, from the calendar and COT tables, a check for the Builder and the checker): against / with / neutral about 101 / 113 / 235 releases at crowd_q 0.8 and z_min 1.0 before data-gap and overlap skips (fewer trades than releases where a second release falls inside an open hold); 69 / 77 / 303 at crowd_q 0.9; 49 / 51 / 127 at z_min 1.5 and crowd_q 0.8. A count far from these means the event set, the sign mapping or the rank is wrong. The calendar covers 2010-01 to 2025-04, so the check period is complete and the holdout is partial (noted for any promotion).\n\nREPORTING (from the trades; all 24 stage A rows read from the trials table, stage 'A'): per cell the number of trades, avg R, trade-level t, release-date-clustered t (R averaged per UTC release date, then t over dates), mean fill spread in pips and as a share of the stop, by-year avg R, for design and for check; for the chosen against cell: the matching with and neutral cells (same crowd_q, z_min, hold), avg R split by news side (base-currency releases against quote-currency releases) and by event group (employment: Non-Farm, Employment Change, Claimant Count, Unemployment Rate, ADP; inflation: CPI, PPI, earnings; activity: PMI, ISM, retail sales, GDP, production, confidence, housing, trade; rates: rate decisions), the avg R after dropping the best ceil(N/10) release dates, and the per-year against-minus-with and against-minus-neutral differences in design and check.",
 "params": {
  "arm": "against",
  "crowd_q": 0.8,
  "z_min": 1.0,
  "hold": "d1",
  "sl_atr": 1.0,
  "delay_min": 15,
  "max_delay_min": 60,
  "exit_utc": "20:30",
  "atr_n": 20,
  "rank_weeks": 52
 },
 "grid": {
  "arm": [
   "against",
   "with",
   "neutral"
  ],
  "crowd_q": [
   0.8,
   0.9
  ],
  "z_min": [
   1.0,
   1.5
  ],
  "hold": [
   "d0",
   "d1"
  ]
 },
 "markets": [
  "EURUSD",
  "GBPUSD",
  "AUDUSD",
  "NZDUSD",
  "USDJPY",
  "USDCAD"
 ],
 "aux_markets": [],
 "ext_series": [
  "calendar",
  "cot"
 ],
 "timeframe": "M15"
}

# Builder module
"""Positioning-amplified surprise continuation: trade a high-impact data surprise 15 minutes after the release,
by arm of the CFTC leveraged-fund crowd state ("against" the crowd = the hypothesis, "with" and "neutral" = controls).

Mechanism: a scheduled release that surprises against a crowded leveraged-fund book forces risk-limit and
end-of-day position cuts that are executed over hours, so the move after the first 15 minutes should continue
only in the 'against' state. 'with' and 'neutral' trade the same surprises, with the same first reaction, costs
and event set, and differ only in the positioning state. The hypothesis is the asymmetry between the arms.

Markets: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCAD on M15 bars (bars are stamped at the open and sparse:
every time is located by timestamp, m.ts for opens and m.close_times() for closes). External series: calendar, cot.
All times UTC. Loops run over releases (a few hundred per market), everything else is vectorised.

SYMBOL CONSTANTS
  base = sym[:3], quote = sym[3:]. The COT currency is the non-USD one (EUR, GBP, AUD, NZD, JPY, CAD);
  cot_sign = +1 when it is the base (EURUSD, GBPUSD, AUDUSD, NZDUSD) and -1 when it is the quote (USDJPY, USDCAD).
  Any other symbol raises ValueError.

CALENDAR EVENT SET
  Rows with impact == 'high', time_source == 'scraped', finite surprise_z, currency in (base, quote), and an event
  name that does not contain (case-insensitive) 'Crude Oil', 'Natural Gas', 'Inventories', 'Unemployment Claims',
  'TIC Long', 'Votes' or 'Asset Purchase Facility'. Row contribution for the pair:
  surprise_z x inv x side, with inv = -1 when the name contains 'Unemployment Rate', 'Unemployment Change',
  'Claimant Count', 'Net Borrowing' or 'Jobless' (a higher number is bad for that currency) and +1 otherwise,
  and side = +1 when the currency is the base, -1 when it is the quote. (surprise_z x inv x side equals
  sign x |surprise_z| of the brief.) Rows with the same ts_avail are one release: dz = sum of their contributions.
  A release qualifies when |dz| >= z_min; dir = sign(dz) (+1 long the pair, -1 short). dz is never rescaled and no
  rank, quantile or z-score is taken over the sample. Releases are processed in ts_avail order, T = ts_avail.

POSITIONING STATE
  c = the COT rows of the COT currency in ts_avail order. For row r with at least rank_weeks rows up to and
  including r: rank_r = (number of the last rank_weeks rows of spec_net_oi that are <= spec_net_oi_r) / rank_weeks,
  in (0, 1]; earlier rows have no rank. For a release at T the row is the last one with ts_avail <= T; a release
  with no such row or no rank is skipped in every arm. state = +1 if rank >= crowd_q, -1 if rank <= 1 - crowd_q,
  else 0; crowd_pair_dir = cot_sign x state (+1 crowded long the pair, -1 crowded short, 0 not crowded).

ARMS (p['arm'], anything else raises ValueError); every arm trades in the surprise direction dir
  against: crowd_pair_dir != 0 and dir == -crowd_pair_dir   (the surprise hits the crowded book)
  with:    crowd_pair_dir != 0 and dir ==  crowd_pair_dir   (the surprise agrees with the book)
  neutral: crowd_pair_dir == 0

ENTRY
  sig = first bar whose close time >= T + delay_min minutes (searchsorted on close times, 'left'). Skip the
  release if sig >= m.n - 1, if close_time[sig] - T > max_delay_min minutes (data gap), if the UTC date of bar
  sig differs from the UTC date of T, or if ATR20[sig] is not finite or <= 0. Market order at the next open:
  entry_long[sig] for dir +1, entry_short[sig] for dir -1, entry_type 0, valid_bars 1.

STOP
  sl_dist[sig] = sl_atr x ATR20[sig], ATR20 = mean daily range of the previous atr_n trading days, known at the
  day start (F.atr_prev on F.daily_bars, broadcast to bars). No target (tp_dist NaN), max_bars 0.

EXIT
  Exit date E = the UTC date of T for hold 'd0'; for hold 'd1' the next weekday (Monday to Friday) after the UTC
  date of T (a Friday release exits on Monday). target = E at exit_utc. xi = first bar with m.ts >= target
  (searchsorted, 'left'). Primary marker: exit_long[xi - 1] = exit_short[xi - 1] = True when bar xi exists, so the
  position closes at the open of the first bar at or after the target. Causal fallback: on every bar j with
  m.ts[j] >= target and j <= the signal bar of the next kept release (m.n - 1 for the last one) both exit
  flags are True, so a missing target bar closes the position at the first bar after the gap and never carries it
  into the trade of the next release. Markers with no open position are ignored by the executor; a marker on the
  signal bar of the next release acts at its fill bar, where only the stop is checked, so the new trade is
  untouched. No other exits, no other filters.

R1  Late releases: a release is skipped entirely (no entry, no markers) unless xi > sig + 1, i.e. unless the fill
    bar sig + 1 opens before the exit target. For d0 this removes releases whose fill is at or after 20:30 UTC
    (the NZD releases at 21:45 and 22:45 UTC). For d1 it never binds.
R2  Planned-hold de-overlap (replaces the leftover guard). The qualifying releases of the active arm that pass
    every skip rule are walked in ts_avail order; a release is kept only if m.ts[sig] >= target_prev, the exit
    target of the last KEPT release (no condition for the first kept release). A dropped release sets no entry and
    no markers. A trade stopped early does not reopen the window. With this rule the previous trade has been
    closed at or before the open of the next signal bar, so the executor is flat when the next entry registers
    and no qualifying release is ignored silently by the executor.

PARAMETERS (every one read from p): arm, crowd_q, z_min, hold, sl_atr, delay_min, max_delay_min, exit_utc, atr_n,
rank_weeks. GRID = the full 24 cells (3 arms x 2 crowd_q x 2 z_min x 2 holds); stage A runs all 24 on EURUSD,
later stages run arm 'against' only (the Director spec).

CAUSALITY. Every decision at bar sig uses bars 0..sig, calendar rows and COT rows with ts_avail <= the close of
the signal bar, and timestamps (the open time of the fill bar is used only to apply R1, as for every next-open
order). The entry never depends on whether the exit target bar exists in the data: R1 is evaluated as
searchsorted(m.ts, target) > sig + 1, which is also true when the target lies beyond the end of the data. Such a
trade (only possible in the last day or two of a sample) has no scheduled exit and is closed by the executor at
the end of the data. A rule that dropped it would make the signals depend on how much data follows the signal
bar, which the truncation test treats as look-ahead. The primary marker is placed only when bar xi exists.

EXPECTED COUNTS (EURUSD, design releases from 2011-07-15, the first usable 52-week rank): against / with / neutral
releases 101 / 113 / 172 at crowd_q 0.8, z_min 1.0; 69 / 77 / 240 at 0.9, 1.0; 49 / 51 / 94 at 0.8, 1.5;
32 / 33 / 129 at 0.9, 1.5. After R1-R2 the q 0.8, z 1.0 arms hold about 98 / 106 / 162 trades (d0) and
86 / 92 / 127 (d1).

release_plan(m, p) returns the per-release table behind signals() (for reporting; signals() uses the same table).
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "fx_surprise_against_crowd"
PARAMS = {"arm": "against", "crowd_q": 0.8, "z_min": 1.0, "hold": "d1", "sl_atr": 1.0, "delay_min": 15,
          "max_delay_min": 60, "exit_utc": "20:30", "atr_n": 20, "rank_weeks": 52}
GRID = {"arm": ["against", "with", "neutral"], "crowd_q": [0.8, 0.9], "z_min": [1.0, 1.5], "hold": ["d0", "d1"]}

_ARMS = ("against", "with", "neutral")
_HOLDS = ("d0", "d1")
_COT_CURRENCIES = ("EUR", "GBP", "AUD", "NZD", "JPY", "CAD")
# event names (lower case) that are dropped from the event set
_EXCLUDED_EVENTS = ("crude oil", "natural gas", "inventories", "unemployment claims", "tic long", "votes",
                    "asset purchase facility")
# event names (lower case) where a higher-than-forecast number is bad for the currency
_INVERTED_EVENTS = ("unemployment rate", "unemployment change", "claimant count", "net borrowing", "jobless")


def _pair_roles(sym: str) -> tuple[str, str, str, int]:
    """(base, quote, COT currency, cot_sign) for a USD pair with one of the six COT currencies; else ValueError."""
    s = str(sym).upper()
    if len(s) == 6:
        base, quote = s[:3], s[3:]
        if quote == "USD" and base in _COT_CURRENCIES:
            return base, quote, base, 1
        if base == "USD" and quote in _COT_CURRENCIES:
            return base, quote, quote, -1
    raise ValueError(f"unsupported symbol {sym!r}: need USD against one of {_COT_CURRENCIES}")


def _read_params(p: dict) -> dict:
    """Read and validate every tunable from p."""
    arm, hold = p["arm"], p["hold"]
    if arm not in _ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {_ARMS}")
    if hold not in _HOLDS:
        raise ValueError(f"unknown hold {hold!r}; expected one of {_HOLDS}")
    cfg = {
        "arm": arm, "hold": hold,
        "crowd_q": float(p["crowd_q"]), "z_min": float(p["z_min"]), "sl_atr": float(p["sl_atr"]),
        "delay_min": int(p["delay_min"]), "max_delay_min": int(p["max_delay_min"]),
        "atr_n": int(p["atr_n"]), "rank_weeks": int(p["rank_weeks"]),
        "exit_hm": F.parse_hhmm(str(p["exit_utc"])),
    }
    if not cfg["sl_atr"] > 0.0:
        raise ValueError("sl_atr must be positive")
    if cfg["rank_weeks"] < 2 or cfg["atr_n"] < 1:
        raise ValueError("rank_weeks must be >= 2 and atr_n >= 1")
    return cfg


def _merged_releases(m: Market, base: str, quote: str, z_min: float) -> tuple[np.ndarray, np.ndarray]:
    """Merged releases (one per ts_avail) of the event set with |dz| >= z_min: (ts_avail, dz), ts ascending."""
    empty = (np.empty(0, dtype="datetime64[us]"), np.empty(0, dtype=np.float64))
    cal = F.ext_series(m, "calendar")
    ccy = cal.column("currency")
    z = cal.column("surprise_z")
    mask = ((cal.column("impact") == "high") & (cal.column("time_source") == "scraped") & np.isfinite(z)
            & ((ccy == base) | (ccy == quote)))
    rows = F.ext_subset(m, "calendar", mask)
    if rows.n == 0:
        return empty
    low = [("" if v is None else str(v)).lower() for v in rows.column("event")]
    excluded = np.array([any(w in nm for w in _EXCLUDED_EVENTS) for nm in low], dtype=bool)
    inverted = np.array([any(w in nm for w in _INVERTED_EVENTS) for nm in low], dtype=bool)
    side = np.where(rows.column("currency") == base, 1.0, -1.0)
    contrib = rows.column("surprise_z") * np.where(inverted, -1.0, 1.0) * side   # sign x |surprise_z| per row
    use = ~excluded
    if not use.any():
        return empty
    ts, group = np.unique(rows.ts_avail[use], return_inverse=True)
    dz = np.bincount(group, weights=contrib[use], minlength=len(ts))
    keep = (np.abs(dz) >= z_min) & (dz != 0.0)
    return ts[keep], dz[keep]


def _crowd_rank(m: Market, cot_ccy: str, rank_weeks: int) -> tuple[np.ndarray, np.ndarray]:
    """(ts_avail, rank) per COT row of the currency; rank = share of the last rank_weeks readings <= this one."""
    cot = F.ext_series(m, "cot")
    rows = F.ext_subset(m, "cot", cot.column("market") == cot_ccy)
    v = rows.column("spec_net_oi")
    rank = np.full(rows.n, np.nan)
    if rows.n >= rank_weeks:
        win = np.lib.stride_tricks.sliding_window_view(v, rank_weeks)      # row r: readings r-rw+1 .. r
        count = (win <= win[:, -1:]).sum(axis=1)
        rank[rank_weeks - 1:] = np.where(np.isfinite(win).all(axis=1), count / rank_weeks, np.nan)
    return rows.ts_avail, rank


def _exit_targets(t: np.ndarray, hold: str, exit_hm: tuple[int, int]) -> np.ndarray:
    """Exit target time per release: exit_utc on the UTC date of T (d0) or on the next Monday-to-Friday date (d1)."""
    day = t.astype("datetime64[D]")
    if hold == "d1":
        day = day + np.timedelta64(1, "D")
        wd = F.weekday(day)                                  # Monday = 0 ... Sunday = 6
        day = day + np.where(wd == 5, 2, np.where(wd == 6, 1, 0)).astype("timedelta64[D]")
    return day.astype("datetime64[us]") + np.timedelta64(exit_hm[0] * 60 + exit_hm[1], "m")


def release_plan(m: Market, p: dict) -> dict:
    """Per merged qualifying release (|dz| >= z_min), in ts_avail order, the table behind signals().

    Keys: t (ts_avail), dz, dir (+1 or -1), rank (NaN = none), state (-1, 0 or +1), pair_dir (cot_sign x state),
    in_arm (ranked and in the active arm), sig, xi, target, atr (ATR20 at sig), ok (in_arm and every skip rule,
    including R1), kept (ok and R2)."""
    cfg = _read_params(p)
    base, quote, cot_ccy, cot_sign = _pair_roles(m.sym)
    if m.n >= 2:
        t, dz = _merged_releases(m, base, quote, cfg["z_min"])
    else:
        t, dz = np.empty(0, dtype="datetime64[us]"), np.empty(0, dtype=np.float64)
    k = len(t)
    plan = {"t": t, "dz": dz, "dir": np.where(dz > 0, 1, -1).astype(np.int8),
            "rank": np.full(k, np.nan), "state": np.zeros(k, dtype=np.int8), "pair_dir": np.zeros(k, dtype=np.int8),
            "in_arm": np.zeros(k, dtype=bool), "sig": np.zeros(k, dtype=np.int64), "xi": np.zeros(k, dtype=np.int64),
            "target": np.empty(k, dtype="datetime64[us]"), "atr": np.full(k, np.nan),
            "ok": np.zeros(k, dtype=bool), "kept": np.zeros(k, dtype=bool)}
    if k == 0:
        return plan

    # ---- positioning state at each release
    cot_ts, cot_rank = _crowd_rank(m, cot_ccy, cfg["rank_weeks"])
    row = np.searchsorted(cot_ts, t, side="right") - 1                   # last COT row usable at T
    rank = np.full(k, np.nan)
    has_row = row >= 0
    rank[has_row] = cot_rank[row[has_row]]
    q = cfg["crowd_q"]
    state = np.where(rank >= q, 1, np.where(rank <= 1.0 - q, -1, 0)).astype(np.int8)
    pair_dir = (cot_sign * state).astype(np.int8)
    ranked = np.isfinite(rank)
    d = plan["dir"]
    if cfg["arm"] == "against":
        in_arm = ranked & (pair_dir != 0) & (d == -pair_dir)
    elif cfg["arm"] == "with":
        in_arm = ranked & (pair_dir != 0) & (d == pair_dir)
    else:
        in_arm = ranked & (pair_dir == 0)

    # ---- entry bar, stop, exit target and the skip rules
    close = m.close_times()
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, cfg["atr_n"]))
    sig = np.searchsorted(close, t + np.timedelta64(cfg["delay_min"], "m"), side="left")
    sig_c = np.minimum(sig, m.n - 1)
    target = _exit_targets(t, cfg["hold"], cfg["exit_hm"])
    xi = np.searchsorted(m.ts, target, side="left")
    ok = in_arm & (sig <= m.n - 2)                                        # the fill bar must exist
    ok &= (close[sig_c] - t) <= np.timedelta64(cfg["max_delay_min"], "m")  # no data gap
    ok &= m.ts[sig_c].astype("datetime64[D]") == t.astype("datetime64[D]")  # same UTC date
    ok &= np.isfinite(atr[sig_c]) & (atr[sig_c] > 0.0)
    ok &= xi > sig + 1                                                    # R1: the fill opens before the target

    # ---- R2: planned-hold de-overlap, walking the releases of the active arm in time order
    kept = np.zeros(k, dtype=bool)
    target_prev = None
    for i in np.flatnonzero(ok):
        if target_prev is not None and m.ts[sig[i]] < target_prev:
            continue
        kept[i] = True
        target_prev = target[i]

    plan.update({"rank": rank, "state": state, "pair_dir": pair_dir, "in_arm": in_arm, "sig": sig, "xi": xi,
                 "target": target, "atr": atr[sig_c], "ok": ok, "kept": kept})
    return plan


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    cfg = _read_params(p)
    plan = release_plan(m, p)
    idx = np.flatnonzero(plan["kept"])
    for pos, i in enumerate(idx):
        sg = int(plan["sig"][i])
        xi = int(plan["xi"][i])
        if plan["dir"][i] > 0:
            s.entry_long[sg] = True
        else:
            s.entry_short[sg] = True
        s.entry_type[sg] = 0
        s.valid_bars[sg] = 1
        s.sl_dist[sg] = cfg["sl_atr"] * plan["atr"][i]
        if xi < m.n:                                    # primary exit: close at the open of the first bar >= target
            s.exit_long[xi - 1] = True
            s.exit_short[xi - 1] = True
        nxt = int(plan["sig"][idx[pos + 1]]) if pos + 1 < len(idx) else m.n - 1
        s.exit_long[xi:nxt + 1] = True                  # causal fallback: every bar at or after the target
        s.exit_short[xi:nxt + 1] = True
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
  "path": "D:\\Traders sir\\strategies\\auto\\fx_surprise_against_crowd.py"
 },
 "dynamic": {
  "ok": true,
  "issues": [],
  "entries": 80,
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
   "ext_release": {
    "ok": true,
    "probes": [
     {
      "k": 16,
      "release": "2017-12-26T04:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 21758,
      "release": "2018-11-08T15:30:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 43591,
      "release": "2019-09-25T14:30:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 64456,
      "release": "2020-07-28T13:30:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 85397,
      "release": "2021-06-01T07:15:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 106896,
      "release": "2022-04-11T06:00:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 128461,
      "release": "2023-02-18T16:30:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     },
     {
      "k": 149993,
      "release": "2023-12-29T20:30:00.000000",
      "truncation_mismatches": 0,
      "perturbation_mismatches": 0,
      "first_mismatch": -1,
      "fields": ""
     }
    ]
   },
   "n_entries": 80,
   "aux_markets": [],
   "ext_series": [
    "calendar",
    "cot"
   ]
  }
 },
 "ok": true
}

Review the module against the rules and the strategy contract.

# Output
Write a JSON object matching this schema to runs/fx_surprise_against_crowd/critic_code.json.

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
