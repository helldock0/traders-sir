# Forced losscut flow: short AUDJPY (NZDJPY, CADJPY) into the Tokyo pre-open after a US-session equity shock  (`jpy_cross_losscut_after_us_shock`)

Family: cross_asset_forced_liquidation | verdict: **kill:stage_a** | failing gates: GA_stage_a_floor | 3.5s

## Rationale
Japanese retail margin accounts are the largest retail FX market in the world (GMO Click, DMM, SBI; about USD 1 trillion a month of volume) and are structurally long the high-yield yen crosses (AUDJPY, NZDJPY, and since 2022 USDJPY) for carry at 5-25x leverage. The brokers enforce an automatic losscut when margin falls below a maintenance ratio, and a large part of the retail book is managed during Tokyo hours. When US equities sell off hard during the New York session, the yen crosses fall with them overnight for Tokyo; the retail book opens the Tokyo morning sitting on losses it has not reacted to, and the losscut orders, margin calls and manual de-risking are executed in the 08:00-10:00 JST window. Who is on the other side: Tokyo-session dealers who buy the forced selling and hold the inventory, which is the pressure that shows up as continuation of the overnight move in the first Tokyo hours on exactly those days. This is the 'Mrs Watanabe forced unwind' documented on the 2007-08, 2015-08-24 and 2016-06-24 and 2024-08-05 episodes; the question here is whether it exists at a tradeable size on ordinary shock days (US100 down 0.75-1.5% in the cash session), which happen 10-20 times a year. On ordinary days Japanese retail are contrarian dip buyers, which is why unconditional Tokyo-open fades and follows are both zero (fx_session_rev, edge_hunt); the mechanism here only operates when the overnight loss is large enough to trigger forced selling, so it is conditioned on an external equity shock measured in the aux market, not on the cross's own move. Costs: AUDJPY median spread 0.9 pips plus 0.4 pips slippage against a 0.5 x ATR20 stop of about 40 pips, about 0.035 R, and the trade is a market order at 08:00 JST with a time exit, which a human can execute on a prop account. Critic revisions accepted before any run: DST-aware New York cash-session window; start level used directly as the denominator; k grid lowered to 0.5/0.75/1.0 for power; regime kill with 2022 removed; expected design t restated as 1.0-1.5 and cost as 0.05-0.08 R.

## Pre-registered
```json
{
  "expected_design_t_min": 1.0,
  "expected_avg_r": 0.08,
  "min_trades_design_per_market": 40,
  "kill_if": "(1) Stage A best design avg R on AUDJPY <= 0 or design t < 1. (2) Monotone response: at the same stop and exit, avg R(k=1.0) >= avg R(k=0.75) >= avg R(k=0.5) must hold; a violation of more than 0.02 R at any step is a kill (then the sign is noise, not a size-triggered liquidation). (3) Cross-market: NZDJPY and CADJPY both negative in stage B while AUDJPY is positive is a kill (one market's luck, not a retail-book effect). (4) Regime: check-period avg R with 2022 removed must be > 0 at the chosen combination (2022 supplies about a third of check shock days; a bear-market trend must not pass as losscut flow). Honest expectations: the design sample is small (about 121 / 79 Monday-Thursday shock days at k = 0.5 / 1.0 in 2012-2017, the US100 feed being clean from 2013), so the expected design t at the chosen point is 1.0-1.5 and this test is underpowered against the t >= 2 pass bar; a pass needs the pooled check (about 150+ trades at k = 1.0) and the walk-forward to carry the evidence. Cost is about 0.05-0.08 R per trade because the 23:00 UTC fill sits an hour after the New York rollover when spreads are wider; and automatic losscuts at Japanese brokers trigger in real time, so part of the forced selling may already be done before entry, which is a reason the effect could be small."
}
```

## Hard gates
| gate | result |
|---|---|
| G0_no_leak | True |
| GA_stage_a_floor | False |

## Stage 0: leak tests
ok = True; truncation: True; perturbation: True; determinism: True; entries: 288

## Stage A: coarse grid on AUDJPY (12 combos, design years)
| k | sl_atr | exit_utc | aux | signal_from_utc | signal_to_utc | safety_exit_utc | safety_extra_bars | ny_open | ny_close | atr_n | n | avg_r | t | total_r | max_dd_r | design_n | design_avg_r | design_t | check_n | check_avg_r | check_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 1.0 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 535 | -0.029 | -1.529 | -15.543 | 22.275 | 216 | -0.020 | -0.632 | 319 | -0.035 | -1.476 |
| 0.5 | 0.5 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 535 | -0.063 | -1.735 | -33.934 | 43.075 | 216 | -0.045 | -0.762 | 319 | -0.076 | -1.628 |
| 0.75 | 1.0 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 388 | -0.036 | -1.527 | -13.899 | 20.273 | 151 | -0.029 | -0.773 | 237 | -0.040 | -1.334 |
| 0.75 | 0.5 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 388 | -0.074 | -1.653 | -28.674 | 37.342 | 151 | -0.057 | -0.811 | 237 | -0.085 | -1.459 |
| 1.0 | 1.0 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 288 | -0.047 | -1.644 | -13.493 | 19.172 | 103 | -0.062 | -1.312 | 185 | -0.038 | -1.072 |
| 1.0 | 0.5 | 06:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 288 | -0.099 | -1.826 | -28.489 | 35.778 | 103 | -0.131 | -1.495 | 185 | -0.081 | -1.176 |
| 0.5 | 1.0 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 535 | -0.036 | -3.101 | -19.342 | 21.599 | 216 | -0.041 | -2.042 | 319 | -0.033 | -2.333 |
| 0.5 | 0.5 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 535 | -0.075 | -3.272 | -40.029 | 43.128 | 216 | -0.084 | -2.185 | 319 | -0.068 | -2.432 |
| 0.75 | 1.0 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 388 | -0.051 | -3.612 | -19.742 | 20.943 | 151 | -0.060 | -2.429 | 237 | -0.045 | -2.669 |
| 0.75 | 0.5 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 388 | -0.101 | -3.719 | -39.236 | 40.984 | 151 | -0.118 | -2.512 | 237 | -0.090 | -2.736 |
| 1.0 | 1.0 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 288 | -0.052 | -3.132 | -14.968 | 15.945 | 103 | -0.078 | -2.601 | 185 | -0.038 | -1.904 |
| 1.0 | 0.5 | 02:00 | USATECHIDXUSD | 23:00 | 23:59 | 06:00 | 4 | 09:30 | 16:00 | 20 | 288 | -0.107 | -3.321 | -30.748 | 32.620 | 103 | -0.159 | -2.811 | 185 | -0.077 | -1.998 |
