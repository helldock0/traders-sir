# Builder brief: london_trend_day_ny_continuation

Write the strategy module to `strategies/auto/london_trend_day_ny_continuation.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "london_trend_day_ny_continuation",
 "title": "Trend-day continuation: London open-drive carries into the New York session",
 "family": "intraday_continuation_trend_day",
 "rationale": "On most days the London session is two-sided and its extremes revert, which is why session-reversal and box-breakout ideas died. A minority of days are trend days: a macro or CTA flow arrives at the London open and price runs one way with shallow pullbacks, closing the London morning near its extreme. Those flows are executed over the whole day by participants who must finish (funds rebalancing, systematic trend followers adding on strength, corporates with deadlines), and the New York session adds the same-direction US accounts plus the stops of early faders. The other side is counter-trend liquidity providers who are forced to cover into the New York open. The signature (large London range and a close at the extreme) is observable at 12:00 UTC, before the US participants arrive; the continuation should show up as positive drift from 12:00 to 16:00 UTC on those days only. Costs are lowest at 12 to 15 UTC on the majors (market facts), and the stop is sized to the day's own range, so R is meaningful rather than a fixed pip number.",
 "markets": [
  "EURUSD",
  "GBPUSD",
  "USDJPY",
  "AUDUSD",
  "USDCAD",
  "GBPJPY"
 ],
 "timeframe": "M5",
 "rules": "All times UTC. For each calendar date d (Monday to Friday): the London window is all bars with 07:00 <= ts < 12:00 on d. Let O = bid open of the first bar at or after 07:00 (skip the day if that bar is more than 15 minutes after 07:00), H = highest bid high in the window, L = lowest bid low in the window, C = bid close of the last bar before 12:00 (skip the day if that bar is more than 15 minutes before 12:00), R = H - L. ATR = previous-20-trading-day average daily range (F.atr_prev on NY-close daily bars) known at the start of the trading day that contains 12:00 UTC on d; skip the day if ATR is not available. Trend-day signature: R >= k * ATR. Direction: long if (C - L) / R >= 1 - q; short if (C - L) / R <= q; otherwise no trade. Entry: market order signalled on that last bar before 12:00, so it fills at the open of the first bar at or after 12:00 (ask for longs, bid for shorts). Stop: m * R from the fill. No take-profit. Exit: close the position at the open of the first bar at or after exit_utc (default 16:00) by setting the exit flag on the last bar before exit_utc; the stop stays live until then. One trade per day at most, no re-entry. Parameters: k (range threshold in ATR units), q (close-location fraction), m (stop in units of R), window_start = 07:00, window_end = 12:00, exit_utc = 16:00, max_delay_min = 15.",
 "params": {
  "k": 0.65,
  "q": 0.25,
  "m": 0.5,
  "window_start": "07:00",
  "window_end": "12:00",
  "exit_utc": "16:00",
  "max_delay_min": 15
 },
 "grid": {
  "k": [
   0.5,
   0.65,
   0.8
  ],
  "q": [
   0.15,
   0.25
  ],
  "m": [
   0.5,
   0.75
  ]
 },
 "stage_a_market": "EURUSD"
}

## Critic notes
Implement the rules exactly as written. For each UTC date d with F.weekday(d) < 5: i07, i12, i16 = F.first_bar_at_or_after(m, dates, hh, mm) for p['window_start'], p['window_end'], p['exit_utc'] (F.parse_hhmm). The London window is bars i07..i12-1; never include bar i12 (it is the entry bar, so using it is look-ahead). Skip the day if i12 <= i07, if ts[i07] > 07:00 + max_delay_min, if ts[i12-1] < 12:00 - max_delay_min (compare bar timestamps), or if i12 >= m.n or ts[i12] > 12:00 + max_delay_min (sparse-bar guard, as in the oracle modules). O = bid_o[i07]; H = max(bid_h[i07:i12]); L = min(bid_l[i07:i12]); C = bid_c[i12-1]; R = H - L. ATR = daily.to_bars(F.atr_prev(daily, 20)) read at i12-1, which is in the same NY trading day as 12:00 UTC; skip if not finite or <= 0. Trade only if R >= k*ATR (then R > 0); long if (C - L)/R >= 1 - q, short if (C - L)/R <= q. Signal on bar i12-1: entry_long or entry_short, entry_type 0, sl_dist = p['m'] * R, tp_dist NaN. Set exit_long or exit_short on bar i16-1 only when i16 < m.n and i16-1 > i12-1, otherwise skip the day. The stop multiple is p['m']: do not bind it to a local called m, which is the Market. Read k, q, m and max_delay_min from p, keep every PARAMS default identical to the spec, and loop over days, not bars.
Revisions required: Pre-registration only: the Builder implements the rules exactly as written (no change to rules, PARAMS or GRID). The Director applies these at judgment. (1) Expectations: expected_design_t_min 2.0 applies to the six-market pool at the chosen cells; per market, +0.05 R implies a design t of about 1, so a lone market far above t 2 on a small cell is suspect rather than confirming. (2) Eligibility: a cell with fewer than 150 design trades on a market is reported but cannot be that market's chosen cell; if no eligible EURUSD cell clears the stage-A floor, kill. (3) Surface kill at stage A (EURUSD, eligible cells): dead if fewer than half have design avg R > 0, or if the eligible k = 0.8 cells (mean over q and m) are <= 0 while the k = 0.5 cells are > 0, since the mechanism says the strongest signatures continue most; this is in addition to the loosest-corner clause. (4) Symmetry: in the chosen cells, USD-buy and USD-sell trades (GBPJPY: long and short) must each have design avg R > 0 pooled across markets; a result carried by one side is a clock drift, not trend-day continuation. (5) Read the pooled check statistics as roughly three independent markets, not six, because London trend days are mostly USD days.

## Requirements
- `NAME = "london_trend_day_ny_continuation"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"k": 0.65, "q": 0.25, "m": 0.5, "window_start": "07:00", "window_end": "12:00", "exit_utc": "16:00", "max_delay_min": 15}
- `GRID = {"k": [0.5, 0.65, 0.8], "q": [0.15, 0.25], "m": [0.5, 0.75]}`
- Markets: ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'GBPJPY'] on M5 bars. Primary market for checks: EURUSD.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check london_trend_day_ny_continuation` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.