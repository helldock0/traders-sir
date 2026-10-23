# Builder brief: fx_volume_climax_reversal

Write the strategy module to `strategies/auto/fx_volume_climax_reversal.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "fx_volume_climax_reversal",
 "title": "Volume-climax capitulation reversal: fade a one-day shock move only when it carries a tick-volume climax (forced liquidation), on FX majors, yen crosses and gold, 1-3 day hold",
 "family": "liquidity_provision_capitulation",
 "rationale": "Large one-day moves come in two kinds. Informed repricing (a data surprise, a central bank shift) is absorbed over days and tends to continue, which is why fading 2-sigma moves on crosses lost (cross_zfade: moves kept running) and why unfiltered big-down-day buying on gold was zero (index_meanrev gold rows MR1-MR4 and MR9-MR10, all about 0 R in design). Forced liquidation is different: stop cascades, margin calls and risk-limit cuts (CTAs, retail margin books, option dealers delta-hedging through strikes) sell or buy regardless of value, and the inventory is absorbed by dealers and liquidity providers who are compensated by a reversal over the following one to three days (Nagel 2012 'Evaporating liquidity'; the classic Grossman-Miller liquidity-provision return). The two kinds cannot be told apart from price alone, but forced liquidation leaves a fingerprint that no prior test in this programme has used: tick volume far above its recent level. Dukascopy tick volume per bar is in the data for every market (m.vol); its raw scale shifts between years and has rare near-zero days, so it is only usable as a ratio to its own trailing 20-day mean, which this spec uses. The hypothesis is therefore conditional: a shock day (|close-to-close move| >= k x ATR20) with volume >= v x its 20-day mean reverses; the same shock day without the volume climax does not. The v = 0.0 arm is the control (every shock day, no volume condition) and must stay near zero; a real effect shows as a monotone rise of avg R with v. Costs are negligible at this horizon: the fill is at 20:00 UTC, before the 17:00 New York rollover widens spreads, against a stop of one ATR20 (EURUSD 0.35 pips spread and 0.4 pips slippage against a 75-pip stop, about 0.01 R; gold about 0.02 R). Expected sample: shock days at k = 1.5 are about 8% of days, so 150-170 design days per market before the volume filter and 40-70 after it; pooling six markets in stage B and the check period gives the power that one market lacks. Critic revisions accepted before any run: thresholds lowered for sample size from an outcome-free frequency count (Dukascopy volume is quoted size, its shock-day ratio rarely exceeds 1.7), the monotone-in-volume kill moved to pooled stage-B cells, date-clustered pooled t-statistics, and the exit flag placed on the bar before the hold-day signal bar so follow-on shocks can trade. Second amendment after the code review, before any run: the control arm is v = 0.0 (v = 1.0 excluded below-average-volume shock days and was not a control), and signals are accepted one position at a time so no exit flag can close another trade.",
 "markets": [
  "EURUSD",
  "GBPUSD",
  "AUDUSD",
  "USDJPY",
  "AUDJPY",
  "XAUUSD"
 ],
 "aux_markets": [],
 "timeframe": "H1",
 "rules": "All times UTC. Bars: H1 on each market. Bars are sparse; locate by timestamp.\n\nDAILY REFERENCE CLOSE: for each UTC date D, let E(D) be the last H1 bar whose close time is at or before 20:00 UTC on D and after 16:00 UTC on D (so a stale bar cannot stand in for the US afternoon close). If no such bar exists, D is not a signal day. C(D) = bid_c[E(D)].\n\nSHOCK MOVE: ret(D) = C(D) - C(D_prev), where D_prev is the most recent earlier UTC date with a valid E(D_prev) and D - D_prev <= 4 calendar days. ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to bar E(D) (the daily ATR known at the start of the trading day that contains E(D)). A shock day is |ret(D)| >= k * ATR20_prev.\n\nVOLUME CLIMAX: V(D) = sum of m.vol over all H1 bars with close time in (20:00 UTC on D_prev, 20:00 UTC on D]. Vbar(D) = mean of V over the 20 most recent earlier signal-eligible dates (dates with a valid E and a valid V), all strictly before D. Require Vbar(D) > 0 and V(D) finite. Volume condition: V(D) >= v * Vbar(D). v = 0.0 is the control arm: the volume condition is V >= 0, so every shock day qualifies with no volume filter at all (the formula V >= v * Vbar is the only test; do not add a separate V >= Vbar floor).\n\nENTRY: on bar E(D), if the day is a shock day and the volume condition holds and the weekday of D is Monday to Friday: if ret(D) < 0 set entry_long[E(D)] = True, else set entry_short[E(D)] = True (fade the day's move). entry_type 0 (market at the next bar's open), valid_bars 1. One signal per date; the executor ignores new entries while a position is open.\n\nSTOP: sl_dist[E(D)] = sl_atr * ATR20_prev; no trade if NaN or <= 0. tp_dist = NaN.\n\nEXIT: time exit after hold_days: let X = E(D + hold_days), where D + hold_days means the hold_days-th later UTC date that has a valid E (skipping weekends and dateless days). Set exit_long/exit_short = True on bar X - 1 (the last bar before X), only if X - 1 > E(D); the executor then closes at the open of bar X, which ends at 20:00 UTC on that date, so the position is flat when a new shock signal at X registers (shock days cluster; this keeps the follow-on shocks). Safety net: max_bars[E(D)] = 24 * (hold_days + 3) H1 bars.\n\nNo other filters, no pyramiding, no re-entry while a position is open.\n\nVOLUME DETAIL: H1 bars are labelled by open time, so a bar's close time is ts + 1h; V(D) sums m.vol over bars whose close time lies in (20:00 UTC on D_prev, 20:00 UTC on D]. Vbar(D) is the mean of the previous 20 valid V values strictly before D. Monday windows include the Friday-evening and Sunday-open hours; accept as specified, do not renormalise. XAUUSD has artefact minutes holding up to 91% of a day's volume: do not filter them (no new knobs); the stage C report should list the dates of the XAUUSD climax trades.\n\nONE POSITION AT A TIME, CAUSALLY: accept signals in date order and write entry, stop, max_bars and the exit flag only for signals the executor will actually take. Track when the accepted trade goes flat (its first stop touch on bid_l/ask_h after the fill at the next open, its own exit bar X, or the max_bars cap, whichever is first) and skip any later signal whose signal bar is before that flat bar, writing nothing for it (not even an exit flag), so a leftover exit flag can never close a different trade. A signal on the bar where the previous trade closes is accepted. This decision for a later signal uses only bars at or before that later signal bar, so it is causal.",
 "params": {
  "k": 1.0,
  "v": 1.3,
  "sl_atr": 1.0,
  "hold_days": 1
 },
 "grid": {
  "k": [
   1.0,
   1.25
  ],
  "v": [
   0.0,
   1.3,
   1.5
  ],
  "hold_days": [
   1,
   3
  ]
 },
 "stage_a_market": "EURUSD"
}

## Critic notes
Volume: sum m.vol over H1 bars whose CLOSE time (ts + 1h, since bars are labelled by open time) lies in (20:00 UTC on D_prev, 20:00 UTC on D]. E(D) is the last bar whose close time is in (16:00, 20:00] UTC on D, so normally the bar opening 19:00. Vbar(D) is the mean of the previous 20 valid V values, strictly before D (no D in its own mean). Use a loop over dates, not bars. Skip if Vbar <= 0 or V is not finite. ret(D) uses bid_c at E(D) and E(D_prev), with D - D_prev <= 4 calendar days. ATR: daily.to_bars(F.atr_prev(daily, 20)) read at index E(D); E(D) at 19:00-20:00 UTC lies inside the NY trading day that started the previous evening, so atr_prev is already shifted. Signal on bar E(D): entry_long if ret < 0, entry_short if ret > 0, entry_type 0, valid_bars 1, sl_dist = sl_atr * ATR, tp NaN, max_bars = 24 * (hold_days + 3). Exit flag goes on index X - 1, where X = E of the hold_days-th later valid date (the oracle pattern exit_long[xi - 1]), and only if X - 1 > E(D). Monday windows include Friday-evening and Sunday-open hours. Accept this as specified; do not renormalise. XAUUSD has artefact minutes holding up to 91% of a day's volume. Do not filter them (no new knobs), but list the dates of the XAUUSD climax trades in the stage C report so artefact-driven signals can be seen. Weekday of D must be Mon-Fri. No other filters.
Revisions required: 1) Grid: k in [1.0, 1.25], v in [1.0, 1.3, 1.5], hold_days in [1, 3] (12 combinations). Defaults: k = 1.0, v = 1.3, sl_atr = 1.0, hold_days = 1. Record in the pre-registration that the thresholds were moved for sample-size feasibility from a frequency count with no outcomes examined, and that the original k = 1.5 / v = 1.75 / v = 2.5 arms were dropped because they hold 0-8 design trades per market. 2) Minimum trades: 40 per market in design at k = 1.0, v = 1.3, and 200 pooled. 3) Rewrite kill rule (2) on pooled stage-B design data (6 markets). For each v, compute avg R averaged over the four (k, hold) cells, with trades from all markets pooled. Require avg R(v = 1.5) >= avg R(v = 1.3) - 0.02, and max(avg R(1.3), avg R(1.5)) - avg R(1.0) >= 0.04. Then repeat the 0.04 gap test in the check period at the chosen (k, hold); failing it is a kill. 4) Pooled t-statistics in stage B, check and walk-forward are computed on date-clustered R: average the R of all markets that traded the same signal date into one observation, then compute t over dates. Report the unclustered figure alongside. 5) Exit timing: put the exit flag on the last bar before E(D + hold_days), not on E(D + hold_days). The trade then closes at the open of the bar that ends at 20:00 UTC on that date, and a new shock signal at E(D + hold_days) can register. With the rule as written, the executor sees the position still open when the next day's signal arrives and silently drops it. Shock days cluster, so that loses exactly the follow-on shocks. 6) Keep kill rules (1), (3) and (4) as written. Update expected numbers: per-market design t about 0.6-1.2 at 0.08 R, so stage A on EURUSD alone has a real chance of a false negative. The Director should know this before reading a stage A kill.

## Requirements
- `NAME = "fx_volume_climax_reversal"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"k": 1.0, "v": 1.3, "sl_atr": 1.0, "hold_days": 1}
- `GRID = {"k": [1.0, 1.25], "v": [0.0, 1.3, 1.5], "hold_days": [1, 3]}`
- Markets: ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'AUDJPY', 'XAUUSD'] on H1 bars. Primary market for checks: EURUSD.
- No auxiliary markets: use only m's own bars.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check fx_volume_climax_reversal` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.