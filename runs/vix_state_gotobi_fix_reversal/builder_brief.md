# Builder brief: vix_state_gotobi_fix_reversal

Write the strategy module to `strategies/auto/vix_state_gotobi_fix_reversal.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "vix_state_gotobi_fix_reversal",
 "title": "Implied-volatility state for the gotobi Tokyo-fix short: does the global risk gauge add to the approved realised-vol filter?",
 "family": "vol_state_parked_leg_gotobi",
 "rationale": "The gotobi short (sell USDJPY at the 09:55 JST fix on settlement days, exit 06:00 UTC, stop 0.25 x ATR20) earns the post-fix reversal of the importer USD demand that banks front-run into the fix; the approved version trades it only when ATR20 is above its 250-day median. Testable claim (narrowed at the Critic's review): global risk appetite, proxied by the CBOE VIX close published before the Tokyo open, changes the size of the front-run inventory that dealers unwind after the fix, so the post-fix reversal is larger on VIX-high days. VIX is not a forward-looking gauge of USDJPY risk in design (ATR-high and VIX-high shares diverge by year; the two trailing-year percentiles correlate 0.09 on gotobi days), which is what makes the increment identifiable and not a relabelled ATR filter. Under the 60-day goal the only gate that can raise this leg's speed is the union ATR-high or VIX-high (320 design trades, 3.8 a month, against 219 and 2.6 for the approved filter), and it helps only if the VIX-high days it adds beat the ATR-low days it leaves out; a 2 x 2 ATR x VIX table measures that, and a non-gotobi placebo separates a fix-specific effect from a VIX-conditioned Tokyo-morning drift (yen crosses bounce in the Tokyo morning after US selloffs, cycle 3). This is a measurement with a modest prior, not a likely edge: even a positive result adds a few hundredths to the basket's monthly Sharpe of 0.4.",
 "markets": [
  "USDJPY"
 ],
 "aux_markets": [],
 "ext_series": [
  "vol"
 ],
 "timeframe": "M1",
 "rules": "Base trade exactly as strategies/oracle/gotobi_short.py: weekdays from p['start'] (2011-01-01); SELL USDJPY at market at the first bar at or after p['entry_utc'] (00:55 UTC) within p['max_delay_min'] minutes; exit at the open of the first bar at or after p['exit_utc'] (06:00 UTC) the same day; stop = p['sl_atr'] x ATR20 (F.atr_prev(F.daily_bars(m), p['atr_n'])), no target; one position at a time; keep the oracle's guards (ei < 1, xi >= m.n, xi <= ei, ATR not finite or not positive).\nDay sets: gotobi days = F.is_gotobi(dates) for every state except the placebo states, which use the non-gotobi weekdays.\nStates at the signal bar (ei - 1): ATR state exactly as the oracle's vol filter: med[i] = nanmedian of atr_d[i - w + 1 : i + 1] with w = p['atr_window'] (the previous 250 daily ATR20 values including the current), ATR-high = ATR20 >= med, ATR-low otherwise, undefined where med is NaN. VIX state: e = F.ext_series(m, 'vol'); sub = F.ext_subset(m, 'vol', np.isfinite(e.column('vix'))) (US-holiday rows carry a ts_avail with a null vix and must be dropped before the as-of mapping); row-wise causal percentile pct[j] = 100 x mean(x[lo:j+1] <= x[j]) with lo = max(0, j - p['vix_window'] + 1), NaN if fewer than p['vix_min_obs'] closes; mapped to bars with the ext_asof rule (last row with ts_avail <= the bar's close; the VIX close is usable from 21:30 UTC, so the 00:55 UTC entry sees the previous US session's close). V+ = pct >= p['vix_pct'] - 1e-9 (VIX at or above its trailing 250-close median, the same construction as the approved ATR median rule); V- = pct < p['vix_pct'] - 1e-9, a strict complement. Return empty Signals if the VIX subset is empty (truncated leak-test samples).\nCommon sample (R1): in every arm, 'all' included, a day is traded only if both states are defined; because a gotobi trade never runs into the next day, the strata partition 'all' exactly.\nArms, p['state']: 'all'; 'atr' (ATR-high, the approved vol-gotobi); 'atr_vix' (ATR-high and V+); 'atr_vixlo' (ATR-high and V-); 'natr_vix' (ATR-low and V+); 'natr_vixlo' (ATR-low and V-); 'atr_or_vix' (ATR-high or V+, the hypothesis cell); placebo on non-gotobi weekdays with the identical short, stop and exit: 'ng_vix' (V+) and 'ng_vixlo' (V-). Unknown state: raise ValueError.\nGrids: spec grid (stages B and C, walk-forward, any holdout) = {state: ['atr_or_vix'], vix_pct: [50]}; stage A grid = {state: all nine arms, vix_pct: [50]} recorded as trials; the module GRID lists the nine arms so the checker exercises every value. The reference and placebo arms are never promoted. Expected design counts 2011-2017 (within a few days): all about 504, atr 219, atr_vix 83, atr_vixlo 136, natr_vix 101, natr_vixlo 182, atr_or_vix 320, ng_vix about 495, ng_vixlo about 817. Compare quantised quantities with a 1e-9 relative tolerance.",
 "params": {
  "state": "atr_or_vix",
  "vix_pct": 50,
  "entry_utc": "00:55",
  "exit_utc": "06:00",
  "sl_atr": 0.25,
  "max_delay_min": 5,
  "vix_window": 250,
  "vix_min_obs": 120,
  "atr_n": 20,
  "atr_window": 250,
  "start": "2011-01-01"
 },
 "grid": {
  "state": [
   "all",
   "atr",
   "atr_vix",
   "atr_vixlo",
   "natr_vix",
   "natr_vixlo",
   "atr_or_vix",
   "ng_vix",
   "ng_vixlo"
  ],
  "vix_pct": [
   50
  ]
 },
 "stage_a_market": "USDJPY"
}

## Critic notes
Base trade: copy strategies/oracle/gotobi_short.py. Dates come from F.utc_dates, weekdays only, from p['start']. The entry bar ei = F.first_bar_at_or_after(m, dates, 0, 55) must fall within p['max_delay_min'] minutes. Set entry_short on ei - 1 and exit_short on xi - 1, where xi is the first bar at or after 06:00 UTC. sl_dist = p['sl_atr'] x ATR20 at ei. Keep the oracle's guards (ei < 1, xi >= m.n, xi <= ei, ATR not finite or not positive). Day sets: gotobi = F.is_gotobi(dates) for every state except 'ng_vix' and 'ng_vixlo', which use the non-gotobi weekdays (~F.is_gotobi(dates)). ATR state: use the oracle's loop verbatim (for i >= w - 1, med[i] = np.nanmedian(atr_d[i - w + 1:i + 1]) with w = p['atr_window'], and hot = atr_d >= med); the state is undefined where med is NaN. VIX state: build e = F.ext_series(m, 'vol') and sub = F.ext_subset(m, 'vol', np.isfinite(e.column('vix'))). Do not use F.ext_asof on the full table: its US-holiday rows have a ts_avail but a null vix, which would make the next Tokyo morning undefined. Return the empty Signals if sub.n == 0 (truncated leak-test samples). Compute pct[j] = 100 x mean(x[lo:j + 1] <= x[j]) with lo = max(0, j - p['vix_window'] + 1), and NaN if j + 1 - lo < p['vix_min_obs']. A Python loop over about 4,000 rows is fine; never use a full-sample or centred statistic, because the perturbation test catches it. Map pct to bars with k = np.searchsorted(sub.ts_avail, m.close_times(), side='right') - 1 (the F.ext_asof rule), NaN where k < 0, and read it at the signal bar ei - 1. V+ = pct >= p['vix_pct'] - 1e-9 and V- = pct < p['vix_pct'] - 1e-9; ATR-high = hot, ATR-low = not hot. Common sample: in every arm, 'all' included, skip the day unless both states are defined. Arms for p['state']: 'all', 'atr' (ATR-high), 'atr_vix' (ATR-high and V+), 'atr_vixlo' (ATR-high and V-), 'natr_vix' (ATR-low and V+), 'natr_vixlo' (ATR-low and V-), 'atr_or_vix' (ATR-high or V+), 'ng_vix' (non-gotobi, V+), 'ng_vixlo' (non-gotobi, V-). Raise on an unknown state. PARAMS must hold every grid key with defaults state 'atr_or_vix' and vix_pct 50, plus entry_utc, exit_utc, sl_atr, max_delay_min, vix_window 250, vix_min_obs 120, atr_n 20, atr_window 250 and start '2011-01-01'. Expected design counts (2011-2017, within a few days): all about 504, atr 219, atr_vix 83, atr_vixlo 136, natr_vix 101, natr_vixlo 182, atr_or_vix 320, ng_vix about 495, ng_vixlo about 817. A count far from these means the day set or a state is wrong.
Revisions required: R1 Common sample: every arm, 'all' included, trades only gotobi weekdays from 2011-01-01 on which both the oracle's ATR median and the VIX percentile are defined. All cells then sit inside one day set, and because a gotobi trade never runs into the next day, the strata partition 'all' exactly. R2 One threshold, chosen from theory: vix_pct = 50 only (VIX at or above its trailing 250-close median, the same construction as the approved ATR median rule). V+ = pct >= 50 and V- = pct < 50, a strict complement. Drop the 70 cells and the 'pct <= 100 - vix_pct' arm. R3 Hypothesis cell: the spec grid, and the only cell stages B and C validate, is {state: ['atr_or_vix'], vix_pct: [50]}, i.e. ATR-high or VIX-high (320 design trades, 3.8 a month). It is the only gate that can raise the leg's speed. Minimum: 300 design trades. R4 Stage A grid of 9 cells, all at vix_pct 50, recorded as trials. Gotobi days: 'atr_vix' (ATR-high and VIX-high, 83 design), 'atr_vixlo' (ATR-high, VIX-low, 136), 'natr_vix' (ATR-low, VIX-high, 101), 'natr_vixlo' (ATR-low, VIX-low, 182), 'all' (about 504), 'atr' (219) and 'atr_or_vix' (320). Placebo on non-gotobi weekdays, running the identical short, stop and exit: 'ng_vix' (VIX-high, 495) and 'ng_vixlo' (VIX-low, 817). The reference and placebo arms are never promoted. R5 Kill rule. Every clause must hold, read from the stage A cells, and the GA floor and the kill rule are applied to 'atr_or_vix' and the strata, never to 'all' or 'atr'. K1: the stratified VIX effect E = w_A x (R[atr_vix] - R[atr_vixlo]) + w_N x (R[natr_vix] - R[natr_vixlo]), with each weight equal to that stratum's share of the common sample, is at least +0.10 R in design (about 1 SE, the increment analogue of the stage A floor), and both within-stratum differences are above 0. K2: the union's design t exceeds the 'atr' arm's design t (same period, so the union is faster), and R[natr_vix] exceeds R[natr_vixlo]; without the second part the union could look faster only because ATR-low gotobi days happened to be positive in design. K3: the gotobi VIX effect over all gotobi days (trade-weighted from the strata) exceeds the placebo's (R[ng_vix] - R[ng_vixlo]) by at least +0.05 R. If the placebo effect is as large, the result is a VIX-conditioned Tokyo-morning drift: nothing is registered as a gotobi refinement, and its sign may not be used to register a standalone VIX short (that would be a snooped flip, and the US-shock-to-Tokyo family is dead). K4: before anything is adopted, using the same cells' check rows, E is above 0 in check 2018-2023 and the union's check t is at least the 'atr' arm's check t. This clause is needed because the stage C gates cannot fail a gotobi subset. K5: report E gross of costs as well as net, and with month-clustered SEs. R6 Restate the expectations: union about 3.8 trades a month; expected E between 0 and +0.10 R; union score 0.27-0.33 if E > 0. Record a null as 'no VIX effect larger than about 0.2 R on the gotobi', not as 'implied vol closed'. R7 Restate the mechanism as risk appetite and front-run inventory, not as a forward-looking gauge of USDJPY risk, and keep the clause that a VIX-low result is never registered as a low-vol hypothesis.

## Requirements
- Module `GRID` must list every arm so the checker exercises each value: `GRID = {"state": ["all", "atr", "atr_vix", "atr_vixlo", "natr_vix", "natr_vixlo", "atr_or_vix", "ng_vix", "ng_vixlo"], "vix_pct": [50]}` (the spec's own grid is the hypothesis cell only).
- `NAME = "vix_state_gotobi_fix_reversal"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"state": "atr_or_vix", "vix_pct": 50, "entry_utc": "00:55", "exit_utc": "06:00", "sl_atr": 0.25, "max_delay_min": 5, "vix_window": 250, "vix_min_obs": 120, "atr_n": 20, "atr_window": 250, "start": "2011-01-01"}
- `GRID = {"state": ["all", "atr", "atr_vix", "atr_vixlo", "natr_vix", "natr_vixlo", "atr_or_vix", "ng_vix", "ng_vixlo"], "vix_pct": [50]}`
- Markets: ['USDJPY'] on M1 bars. Primary market for checks: USDJPY.
- No auxiliary markets: use only m's own bars.
- External series attached as m.ext: ['vol']. Read them only through F.ext_asof / F.ext_recent / F.ext_subset / F.ext_minutes_since (see the strategy contract); columns are listed in data/external/README.md; rows are usable only from their ts_avail and the leak tests cover them.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check vix_state_gotobi_fix_reversal` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.