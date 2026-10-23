# Japanese fiscal-calendar flows in Tokyo hours: short USDJPY in the last business days of March (and September) when exporters and institutions repatriate and square books for the fiscal year-end, long USDJPY in the first business days of April (and October) when new-year outward allocations start; each leg with a same-window ordinary-month control arm  (`jpy_fiscal_year_end_repatriation`)

Family: fiscal_calendar_flow_jpy | verdict: **scrap** | failing gates: G2_check_positive, G2b_walk_forward_positive, G4_cost_1_5x_positive | 8.6s

## Rationale
Mechanism: about 70 percent of listed Japanese companies close their fiscal year on 31 March (half-year on 30 September). Exporters and their overseas subsidiaries repatriate foreign-currency earnings to book them and fund year-end dividends and tax; corporate treasuries and banks square foreign-currency exposures for the balance-sheet date; life insurers, pension funds and the GPIF rebalance to fiscal-year targets. These participants must trade by a date, they execute in Tokyo hours (the Tokyo cash session and the 09:55 JST fix), and the flow is one-way (sell USD, buy JPY) and concentrated in the last two weeks of March. After 1 April the sign reverses: life insurers and pension funds deploy new-fiscal-year foreign-asset allocations, and Toshin launches cluster in April (the dealer convention of April yen selling). The other side is dealers and speculators who know the convention; the gotobi edge (post-fix short +0.14 R design, +0.11 R check, gj-strat) shows that known, dated, obligated Tokyo-hour flows still move price in this data set. The plain Tokyo-session short on all days is a cost-level effect that faded after 2017 (patterns_usdjpy fix-short to 06:00 UTC: +0.056 R design, -0.004 R check on all days; +0.022 / -0.048 R on non-gotobi days), so only the fiscal excess over a same-window control can carry this test, and the control arm measures that excess directly while cancelling USDJPY's Tokyo-session drift (about 0.05-0.08 R per trade in trending years such as 2013 and 2022, the same size as the hypothesised effect). Why this is new: the flow atlas (run_flow_atlas.py) conditioned on weekdays, gotobi, month-start and month-end ordinals and US, Japan and England holidays, never on the calendar month, so the fiscal calendar is the one calendar dimension the 600,912-test scan did not cover and its Bonferroni bar does not bind (the cycle 4 ruling on the gold seasonal); the programme bar (design t >= 2) does. The month-end hedge (Melvin-Prins) is an equity-hedge flow at the London 4pm fix on every month-end and is dead after 2018; the Tokyo-fix tests traded a fix minute, not the session; the gold autumn seasonal tested a diffuse festival demand with no settlement date and died, and its lesson is scoped to gold. This is a dealer convention, not a published anomaly, so it is an out-of-sample test of the convention. Design: M15 bars on USDJPY, market entry at 00:00 UTC (09:00 JST, Tokyo cash open), time exit at 06:00 UTC (15:00 JST, cash close), stop 0.25 or 0.5 x ATR20, no target; one trade per selected weekday. Two legs: ye_short (last n_days weekdays of the fiscal-end months, SHORT USDJPY; the primary claim, because its participants face a balance-sheet deadline) and ny_long (first n_days weekdays of the new-year months, LONG USDJPY; the secondary claim). Three month sets: mar (March / April only), mar_sep (March+September / April+October) and ctrl (the same windows in ordinary months: for ye_short the last n_days weekdays of months 1, 2, 5, 7, 8, 11, excluding the June and December quarter and calendar year-ends; for ny_long the first n_days weekdays of months 2, 6, 8, 11, 12, excluding the January and July new-period starts and the Golden Week month, so that the control is neither the mechanism under test nor diluted by Tokyo closures). Counts (USDJPY design 2010-2017, from the calendar, no outcomes): ye_short mar n10 = 80 trades, mar_sep n10 = 160, ctrl n10 = 471; ny_long mar n10 = 80, mar_sep n10 = 160, ctrl n10 about 400; n5 halves these; check 2018-2023 has about 60 / 120 / 350 and 60 / 120 / 300. The gotobi share is balanced between hypothesis and control (ye_short n10: 30.0 vs 31.0 percent; ny_long n10: 22.5 vs 23.2 percent), so gotobi cancels in the control difference and is tested separately by the gotobi-separation rule. Costs: the median design ATR20 at entry is 87 pips, so the 0.25 x ATR stop is about 22 pips; the fill spread is about 0.68 pips at 00:00 UTC and 0.63 at 06:00; the round trip is about 1.8 pips (1.06 of spread and slippage plus 0.75 of commission), about 0.08 R at sl 0.25 and 0.04 R at sl 0.5; on the crosses at sl 0.25 about 0.07 R for EURJPY, 0.10 R for AUDJPY and 0.08 R for GBPJPY. A net +0.10 R therefore needs about +0.18 R gross, about 4 pips per Tokyo session, and the 1.5x cost gate removes another 0.04 R. Expected: if the fiscal flow moves USDJPY an extra 4 pips per Tokyo session beyond ordinary days, the March cell nets about +0.10 R at sl 0.25 with sd about 0.7 R, design t about 1.2-1.5 on 80 trades (lower on the mar_sep cell if September is weaker); the control should sit near zero. Power is low: there are 8 independent Marches in design (16 with September), P(design t >= 2 | effect real at +0.10 R) is about 25 percent, and the kill rules together will kill a real effect of that size more often than not, so a kill is weak evidence and a pass is strong evidence; a positive below the bar is recorded as below the bar and not promoted. Value if it passes: 10-20 trades a year at about +0.1 R, +1-2 R a year, and about 30 percent of ye_short dates are gotobi days on which the basket's gotobi leg is already short USDJPY, so that part stacks risk rather than diversifying it. Approval rests on cheap compute and on closing the last unscanned calendar dimension, not on an expected tradeable edge. Human execution: two orders a day on at most 20 days a year, placed at 09:00 JST with a time exit at 15:00 JST; trivially executable on a prop account.

## Pre-registered
```json
{
  "expected_design_t_min": 1.2,
  "expected_avg_r": 0.1,
  "min_trades_design_per_market": 40,
  "kill_if": "Kill rules apply per leg; ye_short (balance-sheet deadline) is the primary claim and ny_long the secondary. (1) Hypothesis-cell floor on USDJPY per leg, applied by the Director from all 24 stage A rows in the trials table (stage 'A') even if the pipeline reports a candidate (the automatic stage A gate ranks all 24 cells by design t, so a control cell or the other leg can clear it): among that leg's 8 hypothesis cells (months in {mar, mar_sep}) with at least 40 design trades, the chosen cell is the one with the highest trade-level design t (the pipeline's own ranking); it must have design avg R > 0, trade-level t >= 1 and month-window-clustered t >= 1 (R averaged per calendar month of the entry date, then t over those month means); otherwise that leg is scrapped. If ye_short fails this rule but the automatic floor lets the pipeline continue on an ny_long or ctrl cell, its B/C output is ignored and ye_short is scrapped under this rule. (2) Control difference: at the chosen cell, design avg R(chosen) minus design avg R(the ctrl cell with the same leg, n_days and sl_atr) must be >= +0.06 R, and check avg R(chosen) minus check avg R(matching ctrl) must be > 0 (the stage A backtests span design and check). The control difference cancels USDJPY's Tokyo-session drift (about 0.05-0.08 R per trade in trending years, the same size as the effect), so a raw positive check that the control matches is a drift result, not a flow, and the leg dies with the lesson that the generic month-end or month-start Tokyo pattern (already measured by the atlas's month-ordinal day types and the patterns_usdjpy fix-short, +0.056 R design and -0.004 R check on all days) explains it. If a leg is promoted, the locked holdout run also runs the matching ctrl cell (same touch, counted), and a holdout where chosen minus ctrl <= 0 is a fail even if the raw holdout avg R > 0. (3) Gotobi separation: design avg R at the chosen cell must stay > 0 after removing gotobi dates (F.is_gotobi: 5th, 10th, 15th, 20th, 25th and month-end, weekend dates moved back to Friday; about 30 percent of ye_short dates and 23 percent of ny_long dates, balanced with the control); if it does not, the result is the gotobi short again (measured, including its month-end-only variant) and the leg is dead. (4) Regime and clustering: at least 4 of the 8 design years positive at the chosen cell, and design avg R must stay > 0 after dropping the best ceil(W/8) design month-windows, where W is the cell's number of design month-windows (1 dropped for mar cells with 8 windows, 2 for mar_sep cells with 16); a result carried by one March is an episode, not a flow. (5) Costs: the hard gate (positive at 1.5x costs) stands; the mean fill spread is reported; if the chosen cell is positive gross but negative net, the lesson is that the fiscal flow exists but moves USDJPY by less than about 2 pips per Tokyo session and cannot be traded from the open. (6) Replication: the repatriation is against every foreign currency, so at the leg's rule-1 cell read from the stage B trials table on each cross, the design avg R pooled date-clustered over EURJPY, AUDJPY and GBPJPY (average the same-date R across the crosses, then t over dates) must be > 0, and the pooled-check hard gate (avg R > 0 with >= 30 trades) and the walk-forward gate stand; a USDJPY-only result with the crosses negative is scrapped as noise. (7) Legs are separate claims with their own pre-registered sign: each is judged by rules 1-6 on its own; a failing leg is scrapped with its lesson and the survivor goes forward alone; neither leg's sign is ever flipped. (8) Pass bar: a positive result below the programme bar (design t >= 2 at the chosen cell with the design and check control differences positive) is recorded as below the bar and is not promoted. Diagnostics reported but not gating: avg R and count on Japanese public holidays inside the window (about 8.8 percent of ye_short mar n10 dates, 11.9 percent of mar_sep n10) and on Good Friday and Easter Monday dates (3 of 80 ye_short mar n10 dates, 8 of 80 ny_long), and the per-year table of chosen minus control. Honest expectation: USDJPY stop about 22 pips at sl 0.25 (median design ATR20 87 pips); round trip about 1.8 pips, about 0.08 R at sl 0.25 and 0.04 R at sl 0.5; crosses 0.07-0.10 R at sl 0.25; +0.10 R net needs about +0.18 R gross, about 4 pips per Tokyo session; design t 1.2-1.5 on 80 March trades; P(design t >= 2 | effect real at +0.10 R) is about 25 percent and rules 1-6 together will kill a real effect of that size more often than not, so a kill is weak evidence and a pass is strong evidence; the most likely failure is that the flow is spread over London hours and hedged forward rather than executed spot in Tokyo, which shows as a control-sized or zero result."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | True |
| GB_design_positive_markets | 3 |
| G2_check_positive | False |
| G2b_walk_forward_positive | False |
| G4_cost_1_5x_positive | False |
| G5_sample_size | True |

## Soft gates (warnings for the Director)
| check | result |
|---|---|
| W3_stability | False |
| W6_dsr_hypothesis_0_9 | False |
| W6b_dsr_program_0_5 | False |
| W7_regime_half_years_positive | False |
| W8_cost_2x_positive | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 140

## Stage A: coarse grid on USDJPY (24 combos, design years)
| leg | months | n_days | sl_atr | entry_utc | exit_utc | max_delay_min | atr_n | start | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ye_short | ctrl | 10 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 832 | 0.034 | 1.667 | 28.137 | 10.795 | 472 | 0.032 | 1.186 | 360 | 0.036 | 1.174 |
| ye_short | ctrl | 5 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 417 | 0.074 | 2.604 | 31.039 | 6.876 | 237 | 0.043 | 1.164 | 180 | 0.116 | 2.566 |
| ye_short | ctrl | 5 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 417 | 0.101 | 1.916 | 42.212 | 11.462 | 237 | 0.060 | 0.904 | 180 | 0.155 | 1.819 |
| ye_short | ctrl | 10 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 832 | 0.029 | 0.810 | 24.507 | 34.021 | 472 | 0.025 | 0.525 | 360 | 0.035 | 0.628 |
| ye_short | mar_sep | 5 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 140 | -0.005 | -0.060 | -0.741 | 15.293 | 80 | 0.026 | 0.248 | 60 | -0.047 | -0.302 |
| ye_short | mar | 5 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 70 | 0.032 | 0.226 | 2.233 | 6.029 | 40 | -0.039 | -0.266 | 30 | 0.126 | 0.471 |
| ye_short | mar | 5 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 70 | -0.001 | -0.017 | -0.092 | 3.298 | 40 | -0.022 | -0.275 | 30 | 0.027 | 0.182 |
| ye_short | mar_sep | 5 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 140 | -0.008 | -0.165 | -1.142 | 6.132 | 80 | -0.018 | -0.302 | 60 | 0.005 | 0.065 |
| ny_long | mar | 5 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 70 | -0.066 | -0.479 | -4.654 | 12.266 | 40 | -0.107 | -0.494 | 30 | -0.012 | -0.081 |
| ye_short | mar_sep | 10 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 280 | -0.041 | -0.709 | -11.589 | 24.860 | 160 | -0.036 | -0.526 | 120 | -0.048 | -0.479 |
| ny_long | mar | 10 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 140 | -0.030 | -0.350 | -4.244 | 14.021 | 80 | -0.083 | -0.658 | 60 | 0.040 | 0.353 |
| ny_long | mar_sep | 5 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 140 | -0.022 | -0.249 | -3.032 | 12.925 | 80 | -0.106 | -0.814 | 60 | 0.090 | 0.855 |
| ny_long | mar | 5 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 70 | -0.029 | -0.398 | -2.061 | 7.082 | 40 | -0.111 | -0.924 | 30 | 0.080 | 1.310 |
| ye_short | mar | 10 | 0.25 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 140 | 0.014 | 0.156 | 1.895 | 10.501 | 80 | -0.093 | -1.007 | 60 | 0.156 | 0.979 |
| ye_short | mar_sep | 10 | 0.5 | 00:00 | 06:00 | 10 | 20 | 2010-01-01 | 280 | -0.037 | -1.101 | -10.314 | 13.903 | 160 | -0.042 | -1.034 | 120 | -0.030 | -0.532 |

## Stage B: full grid per market (design years)
- USDJPY: best design t 0.25, avg R 0.026, n 80; params {leg=ye_short, months=mar_sep, n_days=5, sl_atr=0.25}
- EURJPY: best design t 0.44, avg R 0.048, n 80; params {leg=ye_short, months=mar_sep, n_days=5, sl_atr=0.25}
- AUDJPY: best design t 0.69, avg R 0.086, n 80; params {leg=ye_short, months=mar_sep, n_days=5, sl_atr=0.25}
- GBPJPY: best design t -0.06, avg R -0.003, n 80; params {leg=ye_short, months=mar, n_days=10, sl_atr=0.5}

## Stage C: validation of the chosen combos (holdout locked)
Pooled check: n 180, avg R -0.034, t -0.42. Pooled walk-forward OOS: n 340, avg R -0.025, t -0.54.

### USDJPY  params {'leg': 'ye_short', 'months': 'mar_sep', 'n_days': 5, 'sl_atr': 0.25, 'entry_utc': '00:00', 'exit_utc': '06:00', 'max_delay_min': 10, 'atr_n': 20, 'start': '2010-01-01'}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 80 | +0.026 | 0.25 | 50 | +0.78 | -0.73 | 1.07 | +2.1 | 8.0 | 0.83 |
| check | 60 | -0.047 | -0.30 | 40 | +1.12 | -0.82 | 0.91 | -2.8 | 7.4 | 0.83 |
| all | 140 | -0.005 | -0.06 | 46 | +0.91 | -0.77 | 0.99 | -0.7 | 15.3 | 0.86 |
R by year: {2010: -0.3, 2011: 4.3, 2012: 6.0, 2013: -2.3, 2014: -3.9, 2015: 4.5, 2016: -5.4, 2017: -0.8, 2018: -3.3, 2019: 0.9, 2020: -0.8, 2021: -3.5, 2022: 2.7, 2023: 1.3}
Walk-forward: OOS n 110, avg R -0.027, t -0.29, windows positive 6/11, efficiency -0.37
Stability: neighbours positive 0/3, neighbour/best ratio -1.21, share of grid positive 0.12
Cost stress: x1.0: avg R -0.005 (t -0.06); x1.5: avg R -0.042 (t -0.48); x2.0: avg R -0.081 (t -0.92)
Monte Carlo: DD p50 13.3 R, p95 25.7 R, P(total<0) 0.52
Deflated Sharpe: hypothesis-level 0.22, programme-level 0.02 (per-trade SR -0.005, n 140)
Regime: 6/14 years positive, worst year 2016 (-5.4 R)

### EURJPY  params {'leg': 'ye_short', 'months': 'mar_sep', 'n_days': 5, 'sl_atr': 0.25, 'entry_utc': '00:00', 'exit_utc': '06:00', 'max_delay_min': 10, 'atr_n': 20, 'start': '2010-01-01'}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 80 | +0.048 | 0.44 | 52 | +0.79 | -0.77 | 1.13 | +3.9 | 5.5 | 0.83 |
| check | 60 | +0.044 | 0.34 | 52 | +0.84 | -0.81 | 1.11 | +2.6 | 3.2 | 0.83 |
| all | 140 | +0.047 | 0.56 | 52 | +0.81 | -0.79 | 1.12 | +6.5 | 6.2 | 0.86 |
R by year: {2010: -0.5, 2011: 2.0, 2012: 4.9, 2013: -2.1, 2014: -2.6, 2015: 4.1, 2016: -3.0, 2017: 1.0, 2018: -2.2, 2019: 1.6, 2020: 1.2, 2021: -1.3, 2022: 2.8, 2023: 0.5}
Walk-forward: OOS n 110, avg R -0.029, t -0.47, windows positive 5/11, efficiency -0.39
Stability: neighbours positive 1/3, neighbour/best ratio -0.68, share of grid positive 0.38
Cost stress: x1.0: avg R 0.047 (t 0.56); x1.5: avg R 0.013 (t 0.15); x2.0: avg R -0.027 (t -0.33)
Monte Carlo: DD p50 9.7 R, p95 19.8 R, P(total<0) 0.27
Deflated Sharpe: hypothesis-level 0.24, programme-level 0.07 (per-trade SR 0.048, n 140)
Regime: 8/14 years positive, worst year 2016 (-3.0 R)

### AUDJPY  params {'leg': 'ye_short', 'months': 'mar_sep', 'n_days': 5, 'sl_atr': 0.25, 'entry_utc': '00:00', 'exit_utc': '06:00', 'max_delay_min': 10, 'atr_n': 20, 'start': '2010-01-01'}
| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |
|---|---|---|---|---|---|---|---|---|---|---|
| design | 80 | +0.086 | 0.69 | 51 | +0.97 | -0.84 | 1.21 | +6.9 | 7.3 | 0.83 |
| check | 60 | -0.100 | -0.69 | 38 | +1.12 | -0.86 | 0.81 | -6.0 | 10.1 | 0.83 |
| all | 140 | +0.006 | 0.06 | 46 | +1.02 | -0.85 | 1.01 | +0.8 | 12.7 | 0.86 |
R by year: {2010: 0.5, 2011: 1.8, 2012: 3.8, 2013: -1.0, 2014: -1.6, 2015: 6.0, 2016: -6.0, 2017: 3.3, 2018: -1.4, 2019: -0.2, 2020: -0.4, 2021: -6.8, 2022: 4.3, 2023: -1.5}
Walk-forward: OOS n 120, avg R -0.019, t -0.23, windows positive 5/11, efficiency -0.27
Stability: neighbours positive 2/3, neighbour/best ratio 0.21, share of grid positive 0.62
Cost stress: x1.0: avg R 0.006 (t 0.06); x1.5: avg R -0.033 (t -0.35); x2.0: avg R -0.089 (t -0.95)
Monte Carlo: DD p50 13.3 R, p95 27.3 R, P(total<0) 0.47
Deflated Sharpe: hypothesis-level 0.30, programme-level 0.03 (per-trade SR 0.005, n 140)
Regime: 6/14 years positive, worst year 2021 (-6.8 R)
