# Month-end USD bid on the 3rd-last weekday (oracle replication)  (`oracle_m3_usd_bid`)

Family: calendar_flow | verdict: **candidate** | failing gates: none | 20.9s

## Rationale
Corporate and fund month-end USD demand concentrates around the 11:00 UTC window on the third-last business day; documented in gj-strat flow atlas as the only month-end slot that survived costs.

## Pre-registered
```json
{
  "expected_design_t_min": 2.0,
  "expected_avg_r": 0.08,
  "min_trades_per_market_design": 30,
  "kill_if": "best design avg R on USDJPY <= 0 or design t < 1",
  "prior_result": "gj-strat: USDJPY k=2 sl 0.25: 189 trades, +0.124 R, design t 2.11, check +0.21, holdout +0.02"
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | True |
| GB_design_positive_markets | 3 |
| G2_check_positive | True |
| G2b_walk_forward_positive | True |
| G4_cost_1_5x_positive | True |
| G5_sample_size | True |

## Soft gates (warnings for the Director)
| check | result |
|---|---|
| W3_stability | True |
| W6_dsr_hypothesis_0_9 | False |
| W6b_dsr_program_0_5 | True |
| W7_regime_half_years_positive | True |
| W8_cost_2x_positive | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 156

## Stage A: coarse grid on USDJPY (6 combos, design years)
| k | entry_utc | exit_utc | sl_atr | side | start | max_delay_min | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 11:00 | 12:00 | 0.5 | auto | 2011-01-01 | 5 | 156 | 0.070 | 3.965 | 10.985 | 1.265 | 84 | 0.044 | 2.175 | 72 | 0.101 | 3.360 |
| 2 | 11:00 | 12:00 | 0.25 | auto | 2011-01-01 | 5 | 156 | 0.136 | 3.717 | 21.154 | 2.682 | 84 | 0.081 | 1.881 | 72 | 0.200 | 3.292 |
| 3 | 11:00 | 12:00 | 0.25 | auto | 2011-01-01 | 5 | 156 | 0.004 | 0.107 | 0.588 | 6.265 | 84 | -0.033 | -0.768 | 72 | 0.047 | 0.808 |
| 1 | 11:00 | 12:00 | 0.5 | auto | 2011-01-01 | 5 | 156 | -0.011 | -0.608 | -1.727 | 4.380 | 84 | -0.019 | -0.771 | 72 | -0.002 | -0.063 |
| 3 | 11:00 | 12:00 | 0.5 | auto | 2011-01-01 | 5 | 156 | 0.003 | 0.199 | 0.546 | 3.212 | 84 | -0.017 | -0.801 | 72 | 0.028 | 0.986 |
| 1 | 11:00 | 12:00 | 0.25 | auto | 2011-01-01 | 5 | 156 | -0.032 | -0.907 | -5.060 | 8.982 | 84 | -0.041 | -0.881 | 72 | -0.023 | -0.405 |

## Stage B: full grid per market (design years)
- USDJPY: best design t 2.17, avg R 0.044, n 84; params {k=2, sl_atr=0.5}
- EURUSD: best design t 2.35, avg R 0.125, n 84; params {k=2, sl_atr=0.25}
- GBPUSD: best design t 0.90, avg R 0.059, n 84; params {k=2, sl_atr=0.25}

## Stage C: validation of the chosen combos (holdout locked)
Pooled check: n 216, avg R 0.075, t 2.14. Pooled walk-forward OOS: n 360, avg R 0.059, t 2.47.

### USDJPY  params {'entry_utc': '11:00', 'exit_utc': '12:00', 'side': 'auto', 'start': '2011-01-01', 'k': 2, 'sl_atr': 0.5}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 84 | +0.044 | 2.17 | 58 | +0.16 | -0.12 | 1.91 | +3.7 | 0.6 | 0.88 |
| check | 72 | +0.101 | 3.36 | 57 | +0.27 | -0.13 | 2.84 | +7.3 | 1.3 | 1.00 |
| all | 156 | +0.070 | 3.97 | 58 | +0.21 | -0.12 | 2.37 | +11.0 | 1.3 | 1.01 |
R by year: {2011: 0.5, 2012: 0.8, 2013: 0.8, 2014: 0.3, 2015: 0.9, 2016: 0.6, 2017: -0.2, 2018: 2.6, 2019: 0.2, 2020: 1.5, 2021: 0.4, 2022: 1.2, 2023: 1.4}
Walk-forward: OOS n 120, avg R 0.050, t 1.96, windows positive 8/10, efficiency 0.61
Stability: neighbours positive 1/3, neighbour/best ratio 0.33, share of grid positive 0.33
Cost stress: x1.0: avg R 0.070 (t 3.97); x1.5: avg R 0.049 (t 2.77); x2.0: avg R 0.028 (t 1.57)
Monte Carlo: DD p50 1.0 R, p95 1.8 R, P(total<0) 0.00
Deflated Sharpe: hypothesis-level 0.61, programme-level 0.61 (per-trade SR 0.317, n 156)
Regime: 12/13 years positive, worst year 2017 (-0.2 R)

### EURUSD  params {'entry_utc': '11:00', 'exit_utc': '12:00', 'side': 'auto', 'start': '2011-01-01', 'k': 2, 'sl_atr': 0.25}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 84 | +0.125 | 2.35 | 63 | +0.40 | -0.34 | 2.01 | +10.5 | 1.6 | 0.88 |
| check | 72 | +0.069 | 0.97 | 56 | +0.47 | -0.44 | 1.35 | +4.9 | 3.8 | 1.00 |
| all | 156 | +0.099 | 2.28 | 60 | +0.43 | -0.39 | 1.63 | +15.5 | 3.8 | 1.01 |
R by year: {2011: 2.4, 2012: 3.9, 2013: -0.5, 2014: 2.5, 2015: -0.3, 2016: 2.7, 2017: -0.1, 2018: 2.5, 2019: 1.3, 2020: 0.3, 2021: -2.3, 2022: 0.2, 2023: 2.9}
Walk-forward: OOS n 120, avg R 0.146, t 3.09, windows positive 9/10, efficiency 1.04
Stability: neighbours positive 2/3, neighbour/best ratio 0.23, share of grid positive 0.67
Cost stress: x1.0: avg R 0.099 (t 2.28); x1.5: avg R 0.066 (t 1.51); x2.0: avg R 0.032 (t 0.74)
Monte Carlo: DD p50 3.7 R, p95 6.7 R, P(total<0) 0.01
Deflated Sharpe: hypothesis-level 0.47, programme-level 0.47 (per-trade SR 0.182, n 156)
Regime: 9/13 years positive, worst year 2021 (-2.3 R)

### GBPUSD  params {'entry_utc': '11:00', 'exit_utc': '12:00', 'side': 'auto', 'start': '2011-01-01', 'k': 2, 'sl_atr': 0.25}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 84 | +0.059 | 0.90 | 54 | +0.49 | -0.44 | 1.29 | +4.9 | 3.6 | 0.88 |
| check | 72 | +0.055 | 0.77 | 50 | +0.53 | -0.42 | 1.27 | +4.0 | 4.6 | 1.00 |
| all | 156 | +0.057 | 1.19 | 52 | +0.50 | -0.43 | 1.28 | +8.9 | 4.6 | 1.01 |
R by year: {2011: 2.5, 2012: 4.2, 2013: -0.2, 2014: -0.6, 2015: 1.3, 2016: 0.6, 2017: -2.8, 2018: 1.5, 2019: -0.1, 2020: 0.6, 2021: -2.8, 2022: 1.5, 2023: 3.3}
Walk-forward: OOS n 120, avg R -0.018, t -0.38, windows positive 4/10, efficiency -0.32
Stability: neighbours positive 1/3, neighbour/best ratio -0.64, share of grid positive 0.33
Cost stress: x1.0: avg R 0.057 (t 1.19); x1.5: avg R 0.021 (t 0.45); x2.0: avg R -0.014 (t -0.30)
Monte Carlo: DD p50 5.3 R, p95 10.5 R, P(total<0) 0.13
Deflated Sharpe: hypothesis-level 0.12, programme-level 0.12 (per-trade SR 0.095, n 156)
Regime: 8/13 years positive, worst year 2021 (-2.8 R)
