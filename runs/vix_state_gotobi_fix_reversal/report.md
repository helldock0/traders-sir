# Implied-volatility state for the gotobi Tokyo-fix short: does the global risk gauge add to the approved realised-vol filter?  (`vix_state_gotobi_fix_reversal`)

Family: vol_state_parked_leg_gotobi | verdict: **candidate** | failing gates: none | 29.6s

## Rationale
The gotobi short (sell USDJPY at the 09:55 JST fix on settlement days, exit 06:00 UTC, stop 0.25 x ATR20) earns the post-fix reversal of the importer USD demand that banks front-run into the fix; the approved version trades it only when ATR20 is above its 250-day median. Testable claim (narrowed at the Critic's review): global risk appetite, proxied by the CBOE VIX close published before the Tokyo open, changes the size of the front-run inventory that dealers unwind after the fix, so the post-fix reversal is larger on VIX-high days. VIX is not a forward-looking gauge of USDJPY risk in design (ATR-high and VIX-high shares diverge by year; the two trailing-year percentiles correlate 0.09 on gotobi days), which is what makes the increment identifiable and not a relabelled ATR filter. Under the 60-day goal the only gate that can raise this leg's speed is the union ATR-high or VIX-high (320 design trades, 3.8 a month, against 219 and 2.6 for the approved filter), and it helps only if the VIX-high days it adds beat the ATR-low days it leaves out; a 2 x 2 ATR x VIX table measures that, and a non-gotobi placebo separates a fix-specific effect from a VIX-conditioned Tokyo-morning drift (yen crosses bounce in the Tokyo morning after US selloffs, cycle 3). This is a measurement with a modest prior, not a likely edge: even a positive result adds a few hundredths to the basket's monthly Sharpe of 0.4.

## Pre-registered
```json
{
  "expected_design_t_min": 2.0,
  "expected_avg_r": 0.15,
  "min_trades_design_per_market": 300,
  "expected_trades_per_month": 3.8,
  "kill_if": "Read from every stage A cell in research.sqlite (the report keeps the top 15 rows); the GA floor and this rule apply to 'atr_or_vix' and the strata, never to 'all' or 'atr'. K1: the stratified VIX effect E = w_A x (R[atr_vix] - R[atr_vixlo]) + w_N x (R[natr_vix] - R[natr_vixlo]), weights = each ATR stratum's share of the common sample, must be at least +0.10 R in design (about one SE) with both within-stratum differences above 0. K2: the union's design t must exceed the 'atr' arm's design t (same period), and R[natr_vix] must exceed R[natr_vixlo] (otherwise the union looks faster only because ATR-low gotobi days happened to be positive in design). K3: the gotobi VIX effect (trade-weighted over the strata) must exceed the placebo effect (R[ng_vix] - R[ng_vixlo]) by at least +0.05 R; if the placebo effect is as large, the result is a VIX-conditioned Tokyo-morning drift: nothing is registered as a gotobi refinement and its sign is never used to register a standalone VIX short (a snooped flip; the US-shock-to-Tokyo family is dead). K4: before anything is adopted, from the same cells' check rows: E above 0 in check 2018-2023 and the union's check t at least the 'atr' arm's check t (the stage C gates cannot fail a gotobi subset). K5: report E gross and net of costs with month-clustered SEs; a VIX-low result is never registered as a low-vol hypothesis. Expectations: union about 3.8 trades a month (320 design trades, minimum 300); E between 0 and +0.10 R; union score 0.27-0.33 if E > 0 against 0.27 for the approved vol-gotobi; a null is recorded as 'no VIX effect larger than about 0.2 R on the gotobi', not as 'implied vol closed'; the design SE of E is about 0.10 R and VIX-high days come in about 90 episodes, so trades within an episode are not independent."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | True |
| GB_design_positive_markets | 1 |
| G2_check_positive | True |
| G2b_walk_forward_positive | True |
| G4_cost_1_5x_positive | True |
| G5_sample_size | True |

## Soft gates (warnings for the Director)
| check | result |
|---|---|
| W3_stability | True |
| W6_dsr_hypothesis_0_9 | True |
| W6b_dsr_program_0_5 | False |
| W7_regime_half_years_positive | True |
| W8_cost_2x_positive | True |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 613

## Stage A: coarse grid on USDJPY (9 combos, design years)
| state | vix_pct | entry_utc | exit_utc | sl_atr | max_delay_min | vix_window | vix_min_obs | atr_n | atr_window | start | atr_min_obs | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 936 | 0.119 | 3.381 | 111.554 | 16.112 | 504 | 0.132 | 2.694 | 432 | 0.104 | 2.054 |
| atr_vixlo | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 209 | 0.246 | 3.165 | 51.330 | 5.423 | 136 | 0.225 | 2.683 | 73 | 0.284 | 1.789 |
| atr_or_vix | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 613 | 0.159 | 3.367 | 97.315 | 17.598 | 320 | 0.173 | 2.559 | 293 | 0.144 | 2.185 |
| natr_vix | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 198 | 0.162 | 2.172 | 32.002 | 13.942 | 101 | 0.205 | 2.091 | 97 | 0.117 | 1.034 |
| atr | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 415 | 0.157 | 2.624 | 65.312 | 10.238 | 219 | 0.158 | 1.799 | 196 | 0.157 | 1.937 |
| ng_vix | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 1056 | 0.002 | 0.064 | 2.031 | 42.621 | 495 | 0.062 | 1.398 | 561 | -0.051 | -1.253 |
| natr_vixlo | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 323 | 0.044 | 0.898 | 14.239 | 17.223 | 184 | 0.063 | 0.947 | 139 | 0.020 | 0.267 |
| atr_vix | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 206 | 0.068 | 0.742 | 13.983 | 12.667 | 83 | 0.048 | 0.256 | 123 | 0.081 | 0.925 |
| ng_vixlo | 50 | 00:55 | 06:00 | 0.25 | 5 | 250 | 120 | 20 | 250 | 2011-01-01 | 30 | 1390 | -0.031 | -1.267 | -42.970 | 53.005 | 822 | -0.011 | -0.332 | 568 | -0.060 | -1.695 |

## Stage B: full grid per market (design years)
- USDJPY: best design t 2.56, avg R 0.173, n 320; params {state=atr_or_vix, vix_pct=50}

## Stage C: validation of the chosen combos (holdout locked)
Pooled check: n 293, avg R 0.144, t 2.18. Pooled walk-forward OOS: n 527, avg R 0.171, t 3.27.

### USDJPY  params {'state': 'atr_or_vix', 'vix_pct': 50, 'entry_utc': '00:55', 'exit_utc': '06:00', 'sl_atr': 0.25, 'max_delay_min': 5, 'vix_window': 250, 'vix_min_obs': 120, 'atr_n': 20, 'atr_window': 250, 'start': '2011-01-01'}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 320 | +0.173 | 2.56 | 55 | +0.92 | -0.73 | 1.52 | +55.2 | 11.2 | 3.33 |
| check | 293 | +0.144 | 2.18 | 53 | +0.88 | -0.67 | 1.45 | +42.1 | 17.6 | 4.07 |
| all | 613 | +0.159 | 3.37 | 54 | +0.90 | -0.70 | 1.49 | +97.3 | 17.6 | 3.98 |
R by year: {2011: 9.8, 2012: -2.4, 2013: 17.5, 2014: 3.9, 2015: 4.8, 2016: 15.0, 2017: 6.5, 2018: -9.8, 2019: 4.3, 2020: 20.1, 2021: 4.5, 2022: 19.8, 2023: 3.1}
Walk-forward: OOS n 527, avg R 0.171, t 3.27, windows positive 10/11, efficiency 1.21
Stability: neighbours positive 0/0, neighbour/best ratio nan, share of grid positive 1.00
Cost stress: x1.0: avg R 0.159 (t 3.37); x1.5: avg R 0.119 (t 2.54); x2.0: avg R 0.073 (t 1.56)
Monte Carlo: DD p50 11.6 R, p95 19.8 R, P(total<0) 0.00
Deflated Sharpe: hypothesis-level 1.00, programme-level 0.01 (per-trade SR 0.136, n 613)
Regime: 11/13 years positive, worst year 2018 (-9.8 R)
