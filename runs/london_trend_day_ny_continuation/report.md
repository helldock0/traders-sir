# Trend-day continuation: London open-drive carries into the New York session  (`london_trend_day_ny_continuation`)

Family: intraday_continuation_trend_day | verdict: **scrap** | failing gates: G2_check_positive | 21.7s

## Rationale
On most days the London session is two-sided and its extremes revert, which is why session-reversal and box-breakout ideas died. A minority of days are trend days: a macro or CTA flow arrives at the London open and price runs one way with shallow pullbacks, closing the London morning near its extreme. Those flows are executed over the whole day by participants who must finish (funds rebalancing, systematic trend followers adding on strength, corporates with deadlines), and the New York session adds the same-direction US accounts plus the stops of early faders. The other side is counter-trend liquidity providers who are forced to cover into the New York open. The signature (large London range and a close at the extreme) is observable at 12:00 UTC, before the US participants arrive; the continuation should show up as positive drift from 12:00 to 16:00 UTC on those days only. Costs are lowest at 12 to 15 UTC on the majors (market facts), and the stop is sized to the day's own range, so R is meaningful rather than a fixed pip number.

## Pre-registered
```json
{
  "expected_design_t_min": 2.0,
  "expected_avg_r": 0.05,
  "min_trades_design_per_market": 150,
  "kill_if": "Stage A on EURUSD: best design avg R <= 0 or design t < 1. Also treat as dead if the effect exists only when m = 0.75 and k = 0.5 (the loosest corner), because that is the configuration closest to a plain afternoon-momentum bet."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | True |
| GB_design_positive_markets | 4 |
| G2_check_positive | False |
| G2b_walk_forward_positive | True |
| G4_cost_1_5x_positive | True |
| G5_sample_size | True |

## Soft gates (warnings for the Director)
| check | result |
|---|---|
| W3_stability | True |
| W6_dsr_hypothesis_0_9 | False |
| W6b_dsr_program_0_5 | False |
| W7_regime_half_years_positive | False |
| W8_cost_2x_positive | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 584

## Stage A: coarse grid on EURUSD (12 combos, design years)
| k | q | m | window_start | window_end | exit_utc | max_delay_min | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.8 | 0.15 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 198 | 0.014 | 0.352 | 2.792 | 13.261 | 107 | 0.102 | 1.823 | 91 | -0.089 | -1.595 |
| 0.8 | 0.25 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 300 | 0.024 | 0.718 | 7.175 | 12.369 | 168 | 0.053 | 1.168 | 132 | -0.013 | -0.270 |
| 0.65 | 0.15 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 372 | -0.004 | -0.129 | -1.469 | 16.453 | 203 | 0.046 | 1.118 | 169 | -0.064 | -1.386 |
| 0.8 | 0.15 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 198 | -0.026 | -0.452 | -5.060 | 20.505 | 107 | 0.075 | 0.912 | 91 | -0.144 | -1.928 |
| 0.65 | 0.15 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 372 | -0.013 | -0.313 | -4.988 | 22.019 | 203 | 0.032 | 0.543 | 169 | -0.068 | -1.102 |
| 0.8 | 0.25 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 300 | -0.009 | -0.192 | -2.694 | 21.518 | 168 | 0.033 | 0.499 | 132 | -0.062 | -0.957 |
| 0.5 | 0.15 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 655 | -0.035 | -1.244 | -22.916 | 40.018 | 348 | 0.016 | 0.441 | 307 | -0.093 | -2.116 |
| 0.65 | 0.25 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 584 | -0.002 | -0.084 | -1.218 | 22.919 | 334 | -0.003 | -0.100 | 250 | -0.001 | -0.013 |
| 0.65 | 0.25 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 584 | -0.011 | -0.327 | -6.585 | 31.335 | 334 | -0.013 | -0.290 | 250 | -0.009 | -0.163 |
| 0.5 | 0.25 | 0.75 | 07:00 | 12:00 | 16:00 | 15 | 1057 | -0.031 | -1.434 | -32.942 | 56.028 | 582 | -0.008 | -0.307 | 475 | -0.059 | -1.705 |
| 0.5 | 0.15 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 655 | -0.051 | -1.322 | -33.304 | 50.314 | 348 | -0.019 | -0.382 | 307 | -0.087 | -1.460 |
| 0.5 | 0.25 | 0.5 | 07:00 | 12:00 | 16:00 | 15 | 1057 | -0.057 | -1.921 | -60.681 | 90.248 | 582 | -0.051 | -1.342 | 475 | -0.065 | -1.373 |

## Stage B: full grid per market (design years)
- EURUSD: best design t 1.82, avg R 0.102, n 107; params {k=0.8, q=0.15, m=0.75}
- GBPUSD: best design t 1.03, avg R 0.033, n 241; params {k=0.8, q=0.25, m=0.75}
- USDJPY: best design t -0.00, avg R -0.000, n 49; params {k=0.8, q=0.15, m=0.5}
- AUDUSD: best design t 0.39, avg R 0.039, n 75; params {k=0.8, q=0.25, m=0.5}
- USDCAD: best design t -0.33, avg R -0.043, n 49; params {k=0.8, q=0.15, m=0.5}
- GBPJPY: best design t 1.04, avg R 0.050, n 372; params {k=0.5, q=0.15, m=0.5}

## Stage C: validation of the chosen combos (holdout locked)
Pooled check: n 666, avg R -0.002, t -0.07. Pooled walk-forward OOS: n 1387, avg R 0.001, t 0.04.

### EURUSD  params {'k': 0.8, 'q': 0.15, 'm': 0.75, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 107 | +0.102 | 1.82 | 55 | +0.51 | -0.39 | 1.57 | +10.9 | 5.4 | 1.11 |
| check | 91 | -0.089 | -1.60 | 48 | +0.33 | -0.48 | 0.64 | -8.1 | 10.4 | 1.26 |
| all | 198 | +0.014 | 0.35 | 52 | +0.43 | -0.44 | 1.07 | +2.8 | 13.3 | 1.20 |
R by year: {2010: 1.6, 2011: 0.7, 2012: 7.6, 2013: -0.3, 2014: 0.9, 2015: 3.4, 2016: -3.2, 2017: 0.2, 2018: -1.3, 2019: -5.6, 2020: 1.3, 2021: -0.9, 2022: -1.1, 2023: -0.6}
Walk-forward: OOS n 254, avg R -0.027, t -0.68, windows positive 5/11, efficiency -0.53
Stability: neighbours positive 3/3, neighbour/best ratio 0.57, share of grid positive 0.58
Cost stress: x1.0: avg R 0.014 (t 0.35); x1.5: avg R 0.003 (t 0.07); x2.0: avg R -0.009 (t -0.21)
Monte Carlo: DD p50 7.4 R, p95 14.5 R, P(total<0) 0.38
Deflated Sharpe: hypothesis-level 0.26, programme-level 0.11 (per-trade SR 0.025, n 198)
Regime: 7/14 years positive, worst year 2019 (-5.6 R)

### GBPUSD  params {'k': 0.8, 'q': 0.25, 'm': 0.75, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 241 | +0.033 | 1.03 | 49 | +0.41 | -0.33 | 1.20 | +8.0 | 4.0 | 2.51 |
| check | 168 | +0.006 | 0.14 | 48 | +0.45 | -0.40 | 1.03 | +1.0 | 6.5 | 2.33 |
| all | 409 | +0.022 | 0.86 | 48 | +0.43 | -0.36 | 1.12 | +9.0 | 6.5 | 2.47 |
R by year: {2010: -1.7, 2011: -1.4, 2012: 2.6, 2013: -0.5, 2014: -0.1, 2015: 4.9, 2016: 4.2, 2017: -0.0, 2018: -1.5, 2019: 0.1, 2020: -0.4, 2021: 3.0, 2022: 0.1, 2023: -0.4}
Walk-forward: OOS n 573, avg R -0.007, t -0.27, windows positive 4/11, efficiency 0.43
Stability: neighbours positive 3/3, neighbour/best ratio 0.46, share of grid positive 0.67
Cost stress: x1.0: avg R 0.022 (t 0.86); x1.5: avg R 0.010 (t 0.38); x2.0: avg R -0.003 (t -0.10)
Monte Carlo: DD p50 8.5 R, p95 16.8 R, P(total<0) 0.19
Deflated Sharpe: hypothesis-level 0.39, programme-level 0.08 (per-trade SR 0.043, n 409)
Regime: 6/14 years positive, worst year 2010 (-1.7 R)

### AUDUSD  params {'k': 0.8, 'q': 0.25, 'm': 0.5, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 75 | +0.039 | 0.39 | 47 | +0.71 | -0.54 | 1.13 | +2.9 | 7.3 | 0.78 |
| check | 68 | +0.024 | 0.26 | 51 | +0.61 | -0.60 | 1.08 | +1.7 | 4.8 | 0.94 |
| all | 143 | +0.032 | 0.47 | 49 | +0.66 | -0.57 | 1.11 | +4.6 | 7.3 | 0.86 |
R by year: {2010: -0.3, 2011: 4.9, 2012: -0.1, 2013: -3.8, 2014: -2.3, 2015: 3.1, 2016: 1.2, 2017: 0.3, 2018: -1.3, 2019: -1.0, 2020: 7.4, 2021: -0.7, 2022: -0.4, 2023: -2.4}
Walk-forward: OOS n 165, avg R -0.024, t -0.40, windows positive 5/11, efficiency -1.36
Stability: neighbours positive 1/3, neighbour/best ratio -0.25, share of grid positive 0.17
Cost stress: x1.0: avg R 0.032 (t 0.47); x1.5: avg R 0.007 (t 0.10); x2.0: avg R -0.019 (t -0.28)
Monte Carlo: DD p50 8.2 R, p95 16.9 R, P(total<0) 0.31
Deflated Sharpe: hypothesis-level 0.14, programme-level 0.14 (per-trade SR 0.039, n 143)
Regime: 5/14 years positive, worst year 2013 (-3.8 R)

### GBPJPY  params {'k': 0.5, 'q': 0.15, 'm': 0.5, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 372 | +0.050 | 1.04 | 49 | +0.81 | -0.69 | 1.14 | +18.8 | 8.4 | 3.88 |
| check | 339 | +0.012 | 0.22 | 46 | +0.87 | -0.71 | 1.03 | +3.9 | 10.1 | 4.71 |
| all | 711 | +0.032 | 0.90 | 48 | +0.84 | -0.70 | 1.09 | +22.7 | 10.1 | 4.29 |
R by year: {2010: 0.9, 2011: -0.9, 2012: 3.5, 2013: 3.2, 2014: 2.8, 2015: 7.1, 2016: 3.6, 2017: -1.3, 2018: 1.0, 2019: 7.1, 2020: -7.8, 2021: 2.4, 2022: 3.4, 2023: -2.2}
Walk-forward: OOS n 395, avg R 0.041, t 1.00, windows positive 8/11, efficiency 0.44
Stability: neighbours positive 1/3, neighbour/best ratio 0.07, share of grid positive 0.50
Cost stress: x1.0: avg R 0.032 (t 0.90); x1.5: avg R 0.001 (t 0.02); x2.0: avg R -0.027 (t -0.77)
Monte Carlo: DD p50 20.2 R, p95 39.4 R, P(total<0) 0.20
Deflated Sharpe: hypothesis-level 0.32, programme-level 0.02 (per-trade SR 0.034, n 711)
Regime: 10/14 years positive, worst year 2020 (-7.8 R)
