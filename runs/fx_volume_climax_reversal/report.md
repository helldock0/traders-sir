# Volume-climax capitulation reversal: fade a one-day shock move only when it carries a tick-volume climax (forced liquidation), on FX majors, yen crosses and gold, 1-3 day hold  (`fx_volume_climax_reversal`)

Family: liquidity_provision_capitulation | verdict: **kill:stage_a** | failing gates: GA_stage_a_floor | 4.2s

## Rationale
Large one-day moves come in two kinds. Informed repricing (a data surprise, a central bank shift) is absorbed over days and tends to continue, which is why fading 2-sigma moves on crosses lost (cross_zfade: moves kept running) and why unfiltered big-down-day buying on gold was zero (index_meanrev gold rows MR1-MR4 and MR9-MR10, all about 0 R in design). Forced liquidation is different: stop cascades, margin calls and risk-limit cuts (CTAs, retail margin books, option dealers delta-hedging through strikes) sell or buy regardless of value, and the inventory is absorbed by dealers and liquidity providers who are compensated by a reversal over the following one to three days (Nagel 2012 'Evaporating liquidity'; the classic Grossman-Miller liquidity-provision return). The two kinds cannot be told apart from price alone, but forced liquidation leaves a fingerprint that no prior test in this programme has used: tick volume far above its recent level. Dukascopy tick volume per bar is in the data for every market (m.vol); its raw scale shifts between years and has rare near-zero days, so it is only usable as a ratio to its own trailing 20-day mean, which this spec uses. The hypothesis is therefore conditional: a shock day (|close-to-close move| >= k x ATR20) with volume >= v x its 20-day mean reverses; the same shock day without the volume climax does not. The v = 0.0 arm is the control (every shock day, no volume condition) and must stay near zero; a real effect shows as a monotone rise of avg R with v. Costs are negligible at this horizon: the fill is at 20:00 UTC, before the 17:00 New York rollover widens spreads, against a stop of one ATR20 (EURUSD 0.35 pips spread and 0.4 pips slippage against a 75-pip stop, about 0.01 R; gold about 0.02 R). Expected sample: shock days at k = 1.5 are about 8% of days, so 150-170 design days per market before the volume filter and 40-70 after it; pooling six markets in stage B and the check period gives the power that one market lacks. Critic revisions accepted before any run: thresholds lowered for sample size from an outcome-free frequency count (Dukascopy volume is quoted size, its shock-day ratio rarely exceeds 1.7), the monotone-in-volume kill moved to pooled stage-B cells, date-clustered pooled t-statistics, and the exit flag placed on the bar before the hold-day signal bar so follow-on shocks can trade. Second amendment after the code review, before any run: the control arm is v = 0.0 (v = 1.0 excluded below-average-volume shock days and was not a control), and signals are accepted one position at a time so no exit flag can close another trade.

## Pre-registered
```json
{
  "expected_design_t_min": 1.0,
  "expected_avg_r": 0.08,
  "min_trades_design_per_market": 40,
  "kill_if": "(1) Stage A best design avg R on EURUSD <= 0 or design t < 1. (2) Volume is the mechanism, judged on pooled stage-B design data (6 markets): for each v, take avg R averaged over the four (k, hold) cells with trades from all markets pooled; require avg R(v=1.5) >= avg R(v=1.3) - 0.02 and max(avg R(1.3), avg R(1.5)) - avg R(0.0) >= 0.04; then the same 0.04 gap must hold in the check period at the chosen (k, hold). Failing either is a kill regardless of sign: if the v=0.0 control (no volume filter) is as good as the filtered arms the result is plain reversal, already measured as about zero. (3) Cross-market: at the chosen combination at least four of the six markets must be positive in design. (4) Regime: the check period must be positive with 2020 removed. Pooled t-statistics in stage B, check and walk-forward should be read on date-clustered R (average the R of all markets that traded the same signal date into one observation, t over dates) because Brexit, the SNB day and the yen flash crash hit 3-5 markets at once; the unclustered figure is reported alongside. Minimum trades: 40 per market in design at k=1.0, v=1.3, and 200 pooled. Record: the thresholds were moved from k 1.5/2.0 and v 1.0/1.75/2.5 to k 1.0/1.25 and v 0.0/1.3/1.5 (v=0.0 replacing v=1.0 as the control after the code review showed v=1.0 drops 25-30% of shock days) for sample-size feasibility, from a frequency count with no outcomes examined; the original arms held 0-8 design trades per market because Dukascopy volume is summed quoted size whose 90th-percentile 20-day ratio on shock days is only 1.56-1.71. Honest expectations: per-market design t about 0.6-1.2 at 0.08 R, so a stage A kill on EURUSD alone has a real chance of being a false negative; the pooled stage B and the check carry the evidence."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 97

## Stage A: coarse grid on EURUSD (12 combos, design years)
| k | v | sl_atr | hold_days | ref_start_utc | ref_end_utc | max_gap_days | vol_window | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.25 | 1.5 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 25 | 0.201 | 1.105 | 5.024 | 2.236 | 10 | 0.157 | 0.517 | 15 | 0.230 | 0.983 |
| 1.25 | 1.5 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 24 | 0.160 | 0.575 | 3.830 | 4.101 | 10 | 0.141 | 0.313 | 14 | 0.173 | 0.474 |
| 1.0 | 1.5 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 41 | 0.064 | 0.526 | 2.630 | 3.289 | 16 | 0.043 | 0.211 | 25 | 0.078 | 0.499 |
| 1.25 | 1.3 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 61 | 0.041 | 0.248 | 2.496 | 8.937 | 28 | -0.073 | -0.310 | 33 | 0.137 | 0.592 |
| 1.0 | 1.5 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 38 | 0.065 | 0.327 | 2.464 | 6.395 | 15 | -0.099 | -0.313 | 23 | 0.171 | 0.664 |
| 1.25 | 1.3 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 63 | -0.054 | -0.486 | -3.380 | 7.637 | 28 | -0.107 | -0.677 | 35 | -0.011 | -0.072 |
| 1.0 | 1.3 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 97 | -0.111 | -1.348 | -10.767 | 13.418 | 46 | -0.083 | -0.709 | 51 | -0.137 | -1.166 |
| 1.0 | 1.3 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 91 | -0.101 | -0.829 | -9.165 | 13.344 | 43 | -0.211 | -1.318 | 48 | -0.002 | -0.010 |
| 1.25 | 0.0 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 192 | -0.057 | -0.709 | -10.942 | 22.513 | 108 | -0.168 | -1.646 | 84 | 0.086 | 0.672 |
| 1.0 | 0.0 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 438 | -0.074 | -2.372 | -32.310 | 34.085 | 245 | -0.102 | -2.482 | 193 | -0.038 | -0.799 |
| 1.0 | 0.0 | 1.0 | 3 | 16:00 | 20:00 | 4 | 20 | 398 | -0.109 | -2.152 | -43.576 | 51.216 | 222 | -0.166 | -2.502 | 176 | -0.038 | -0.485 |
| 1.25 | 0.0 | 1.0 | 1 | 16:00 | 20:00 | 4 | 20 | 204 | -0.109 | -2.230 | -22.178 | 24.717 | 114 | -0.181 | -2.871 | 90 | -0.018 | -0.234 |
