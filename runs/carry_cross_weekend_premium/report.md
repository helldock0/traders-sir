# Weekend risk premium in carry crosses: long AUDJPY (NZDJPY, AUDUSD, NZDUSD) from the Friday New York afternoon to the Monday Tokyo or London open, with a weekday-overnight control  (`carry_cross_weekend_premium`)

Family: weekend_risk_premium_carry | verdict: **kill:stage_a** | failing gates: GA_stage_a_floor | 2.7s

## Rationale
Leveraged carry positions (Japanese retail margin books, CTAs, macro funds) cannot be adjusted for about 48 hours over the weekend, and weekend gap risk in the yen crosses is the largest in FX (the Monday-gap column of the market facts shows AUDJPY 1.2, NZDJPY 2.0, GBPJPY 3.9 pips median, with the tails far larger). Risk managers therefore cut high-yield exposure into the Friday New York afternoon and re-establish it on Monday in Tokyo and London; dealers widen and run flat inventory over the weekend and buy back Monday. The holder who carries the risk over the weekend is paid, if at all, by price alone: spot settles T+2, so the triple rollover falls on Wednesday (in Dukascopy prices and in this engine's cost model), and both the Friday arm and the Monday control cross exactly one single rollover, so net carry is about zero minus the 1% markup. The premium, if it exists, is the price effect of Friday selling and Monday buying. This is the FX analogue of the weekend and overnight risk premia documented in equities (Lou, Polk and Skouras 2019) and of the 'weekend effect' literature in currencies (Yamori and Kurihara 2004), which the flow atlas could not see: its windows were intraday (30 minutes to 8 hours) on single weekdays, so a Friday-to-Monday hold was never measured, and no prior report in the index holds a position over a weekend by design (the gap tests measured Monday gap fills, not the weekend return). Costs are not negligible at the weekend edges: spreads at the Friday 20:00 UTC entry and around the Monday 00:00 UTC exit are far wider than the all-hours median, roughly 3-4 pips round trip including commission on AUDJPY, which is 0.015-0.03 R against a 1.5-3 x ATR20 stop of 120-240 pips, the same order as the premium being sought; every arm therefore reports gross and net R and its mean entry and exit spread. Sample: every weekend, so about 410 design trades per market, which is why this family was chosen after cycles 3 and 4 died at the underpowered single-market gate. A weekday-overnight control is built into the grid: the same hold from Monday 20:00 UTC to Tuesday morning measures the overnight carry drift without the weekend, so the weekend premium must beat it. EURJPY is included as a low-carry comparison: if EURJPY shows the same premium the effect is a JPY-risk premium rather than carry, which is still tradeable but changes the interpretation. Critic revisions accepted before any run: carry claim removed (triple rollover is Wednesday), cost estimate from the actual weekend-edge spreads, exit at the open of the first bar opening at or after exit_utc, 2020 rule additive to the hard gate, paired fri-minus-mon t and 3-of-4 market rule, safety-net hold cut to 24 bars.

## Pre-registered
```json
{
  "expected_design_t_min": 1.5,
  "expected_avg_r": 0.02,
  "min_trades_design_per_market": 300,
  "kill_if": "(1) Stage A best design avg R on AUDJPY at entry_day = fri <= 0 or design t < 1. (2) Control: at the same entry_utc, exit_utc and sl_atr, avg R(fri) - avg R(mon) >= 0.03 R in design, the paired fri-minus-mon t is reported per market, and the difference must be positive on at least 3 of the 4 AUD/NZD markets at the chosen combination (one market cannot carry it); if the weekday-overnight control earns as much as the weekend hold, the result is overnight drift and the hypothesis dies regardless of sign. (3) Cross-market: at the chosen combination at least three of AUDJPY, NZDJPY, AUDUSD, NZDUSD positive in design. (4) Regime: the hard gate (check avg R > 0 over all check years) stays; in addition the check period must be positive with 2020 removed, and at least half of the design years positive. (5) Costs: both gross and net R are reported for every arm with the mean entry and exit spreads, because the weekend-edge spread (about 3-4 pips round trip including commission, 0.015-0.03 R) is the same order as the premium; the 1.5x cost gate is a real threat and is accepted as such. (6) Interpretation, not a kill: if EURJPY is as good as the AUD/NZD crosses the premium is a JPY-risk premium, not carry. Honest expectations: both arms cross exactly one single rollover (triple is Wednesday), so this is a price-only premium; the expected design avg R is at least +0.02 R net at sl_atr 1.5, 3-7 pips of price premium per weekend; with about 410 design trades and sd about 0.5 R, design t is 0.8-2.0, adequately powered for the first time in three cycles, but the effect may be absent."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 723

## Stage A: coarse grid on AUDJPY (16 combos, design years)
| entry_day | entry_utc | exit_utc | sl_atr | max_delay_min | max_hold_bars | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mon | 16:00 | 07:00 | 3.0 | 60 | 24 | 723 | -0.002 | -0.318 | -1.370 | 4.327 | 412 | -0.004 | -0.461 | 311 | 0.000 | 0.030 |
| mon | 20:00 | 07:00 | 3.0 | 60 | 24 | 723 | -0.004 | -0.718 | -2.908 | 4.710 | 412 | -0.005 | -0.696 | 311 | -0.003 | -0.304 |
| mon | 16:00 | 07:00 | 1.5 | 60 | 24 | 723 | -0.004 | -0.333 | -2.806 | 9.471 | 412 | -0.011 | -0.707 | 311 | 0.006 | 0.331 |
| mon | 20:00 | 07:00 | 1.5 | 60 | 24 | 723 | -0.009 | -0.835 | -6.748 | 10.573 | 412 | -0.015 | -0.986 | 311 | -0.002 | -0.123 |
| fri | 16:00 | 07:00 | 3.0 | 60 | 24 | 723 | -0.005 | -0.814 | -3.443 | 6.525 | 412 | -0.009 | -1.162 | 311 | 0.000 | 0.047 |
| fri | 16:00 | 07:00 | 1.5 | 60 | 24 | 723 | -0.008 | -0.732 | -6.056 | 12.509 | 412 | -0.018 | -1.183 | 311 | 0.004 | 0.214 |
| fri | 16:00 | 00:00 | 1.5 | 60 | 24 | 723 | -0.010 | -1.209 | -7.376 | 15.853 | 412 | -0.015 | -1.290 | 311 | -0.004 | -0.321 |
| fri | 16:00 | 00:00 | 3.0 | 60 | 24 | 723 | -0.005 | -1.199 | -3.645 | 7.884 | 412 | -0.008 | -1.296 | 311 | -0.002 | -0.292 |
| fri | 20:00 | 07:00 | 3.0 | 60 | 24 | 723 | -0.008 | -1.424 | -5.696 | 8.402 | 412 | -0.013 | -1.812 | 311 | -0.001 | -0.126 |
| fri | 20:00 | 07:00 | 1.5 | 60 | 24 | 723 | -0.017 | -1.558 | -12.399 | 17.826 | 412 | -0.030 | -2.058 | 311 | 0.000 | 0.017 |
| fri | 20:00 | 00:00 | 3.0 | 60 | 24 | 723 | -0.008 | -2.192 | -5.899 | 8.159 | 412 | -0.012 | -2.317 | 311 | -0.003 | -0.610 |
| mon | 16:00 | 00:00 | 3.0 | 60 | 24 | 723 | -0.009 | -2.683 | -6.326 | 6.848 | 412 | -0.010 | -2.323 | 311 | -0.007 | -1.419 |
| mon | 16:00 | 00:00 | 1.5 | 60 | 24 | 723 | -0.018 | -2.758 | -13.189 | 14.234 | 412 | -0.021 | -2.391 | 311 | -0.014 | -1.437 |
| fri | 20:00 | 00:00 | 1.5 | 60 | 24 | 723 | -0.018 | -2.352 | -13.130 | 17.455 | 412 | -0.026 | -2.452 | 311 | -0.008 | -0.686 |
| mon | 20:00 | 00:00 | 1.5 | 60 | 24 | 723 | -0.024 | -5.422 | -17.082 | 17.148 | 412 | -0.026 | -4.337 | 311 | -0.021 | -3.259 |
