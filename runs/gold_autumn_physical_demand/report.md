# Gold autumn effect out of sample: long XAUUSD on every trading day of September-October (Indian festival and wedding-season physical demand), daily entries  (`gold_autumn_physical_demand`)

Family: seasonal_physical_demand_metal | verdict: **kill:stage_a** | failing gates: GA_stage_a_floor | 18.0s

## Rationale
Baur (2013, 'The autumn effect of gold price returns') documents on 1980-2010 data that gold's positive returns concentrate in September and November, and attributes it to physical demand: Indian jewellery buying for the Diwali and wedding season (India was 25-30% of world gold jewellery demand through the 2010s, and dealers restock from August to October), Chinese demand ahead of the October Golden Week, and central-bank and investor hedging into the fourth quarter. The buyers are price-insensitive on the calendar (weddings and festivals do not move), the sellers are bullion banks and ETFs that lean on the flow, and the pressure shows up as a positive drift over the season rather than at a clock time, which is why the flow atlas's intraday windows (which scanned gold by clock and day type, not by month) could not see it. This programme's data starts in 2010, so 2010-2017 is a clean out-of-sample test of a published pre-2010 anomaly, and 2018-2023 a second one. The structure is daily entries at 20:00 UTC with a 24-hour hold and a wide stop, so each trading day in the window is one trade and the sample is about 40 trades a year; the effective independent sample is still eight seasons in design, which is why the pre-registered t is modest. A control window is pre-registered inside the grid: March-April, the season Baur finds weakest, must not show the same drift. Costs are about 0.01 R per trade (33 pips of spread plus slippage against a 2 x ATR20 stop of about 4500 pips). Critic revisions accepted before any run: the primary window is the published September-and-November months, the control is all other months of the same years (April-May has its own Indian demand peak, so March-April was not a clean control), the window-minus-rest difference is a pre-registered requirement in design, check and any holdout, and the exit flag sits on the bar before the next signal bar so every Monday-Thursday day trades.

## Pre-registered
```json
{
  "expected_design_t_min": 1.0,
  "expected_avg_r": 0.03,
  "min_trades_design_per_market": 250,
  "kill_if": "(1) Design avg R for sep_nov_baur at sl_atr = 2.0 <= 0 or design t < 1. (2) Control: in design, avg R(sep_nov_baur) - avg R(rest) >= 0.02 at the same stop, otherwise kill regardless of sign (the drift would be gold's general trend, not seasonal demand). (3) Seasons, not days: at least 5 of the 8 design seasons (Sep + Nov R summed per year) must be positive. (4) Check: avg R at the chosen combination > 0 with at least 4 of 6 seasons positive, and avg R(window) - avg R(rest) > 0 in check. (5) If ever promoted, the holdout verdict must report the window-minus-rest difference and a holdout where the window does not beat the rest is a fail even if raw avg R > 0 (2024-2026 is a gold bull market, so a long-only raw pass proves little). Minimum design trades: 250 for sep_nov_baur. Honest expectations: design t 1.0-1.7 is accepted as below the pass bar; a pass needs design t >= 2, which this test reaches only if the effect is stronger than published. Even if real it is worth about 1 R a year; its value is a clean out-of-sample reading of a published anomaly either way."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 481

## Stage A: coarse grid on XAUUSD (6 combos, design years)
| window | sl_atr | sig_start_utc | sig_end_utc | bar_minutes | max_hold_bars | atr_n | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rest | 2.0 | 16:00 | 20:00 | 60 | 30 | 20 | 2160 | 0.002 | 0.214 | 3.284 | 17.927 | 1228 | 0.000 | 0.045 | 932 | 0.003 | 0.275 |
| rest | 1.0 | 16:00 | 20:00 | 60 | 30 | 20 | 2160 | 0.004 | 0.301 | 8.789 | 35.858 | 1228 | -0.001 | -0.055 | 932 | 0.011 | 0.526 |
| sep_nov_baur | 2.0 | 16:00 | 20:00 | 60 | 30 | 20 | 481 | -0.033 | -2.099 | -15.740 | 21.206 | 275 | -0.040 | -1.941 | 206 | -0.023 | -0.959 |
| sep_nov_baur | 1.0 | 16:00 | 20:00 | 60 | 30 | 20 | 481 | -0.054 | -1.869 | -26.146 | 35.184 | 275 | -0.076 | -1.959 | 206 | -0.026 | -0.581 |
| sep_nov | 1.0 | 16:00 | 20:00 | 60 | 30 | 20 | 728 | -0.030 | -1.295 | -22.174 | 38.011 | 416 | -0.061 | -1.991 | 312 | 0.010 | 0.280 |
| sep_nov | 2.0 | 16:00 | 20:00 | 60 | 30 | 20 | 728 | -0.020 | -1.613 | -14.665 | 23.659 | 416 | -0.036 | -2.162 | 312 | 0.000 | 0.025 |
