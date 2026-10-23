# Builder brief: jpy_cross_losscut_after_us_shock

Write the strategy module to `strategies/auto/jpy_cross_losscut_after_us_shock.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "jpy_cross_losscut_after_us_shock",
 "title": "Forced losscut flow: short AUDJPY (NZDJPY, CADJPY) into the Tokyo pre-open after a US-session equity shock",
 "family": "cross_asset_forced_liquidation",
 "rationale": "Japanese retail margin accounts are the largest retail FX market in the world (GMO Click, DMM, SBI; about USD 1 trillion a month of volume) and are structurally long the high-yield yen crosses (AUDJPY, NZDJPY, and since 2022 USDJPY) for carry at 5-25x leverage. The brokers enforce an automatic losscut when margin falls below a maintenance ratio, and a large part of the retail book is managed during Tokyo hours. When US equities sell off hard during the New York session, the yen crosses fall with them overnight for Tokyo; the retail book opens the Tokyo morning sitting on losses it has not reacted to, and the losscut orders, margin calls and manual de-risking are executed in the 08:00-10:00 JST window. Who is on the other side: Tokyo-session dealers who buy the forced selling and hold the inventory, which is the pressure that shows up as continuation of the overnight move in the first Tokyo hours on exactly those days. This is the 'Mrs Watanabe forced unwind' documented on the 2007-08, 2015-08-24 and 2016-06-24 and 2024-08-05 episodes; the question here is whether it exists at a tradeable size on ordinary shock days (US100 down 0.75-1.5% in the cash session), which happen 10-20 times a year. On ordinary days Japanese retail are contrarian dip buyers, which is why unconditional Tokyo-open fades and follows are both zero (fx_session_rev, edge_hunt); the mechanism here only operates when the overnight loss is large enough to trigger forced selling, so it is conditioned on an external equity shock measured in the aux market, not on the cross's own move. Costs: AUDJPY median spread 0.9 pips plus 0.4 pips slippage against a 0.5 x ATR20 stop of about 40 pips, about 0.035 R, and the trade is a market order at 08:00 JST with a time exit, which a human can execute on a prop account. Critic revisions accepted before any run: DST-aware New York cash-session window; start level used directly as the denominator; k grid lowered to 0.5/0.75/1.0 for power; regime kill with 2022 removed; expected design t restated as 1.0-1.5 and cost as 0.05-0.08 R.",
 "markets": [
  "AUDJPY",
  "NZDJPY",
  "CADJPY"
 ],
 "aux_markets": [
  "USATECHIDXUSD"
 ],
 "timeframe": "M15",
 "rules": "All times UTC unless stated. Bars: M15 on the primary yen cross; the auxiliary market USATECHIDXUSD (US100 CFD) is attached on M15 and read through F.aux_market with explicit close-time logic (or F.aux_window_change if the fixed fallback window is used).\n\nUS SHOCK (New York cash session, DST-aware): for each UTC date D compute the New York offset with the US rule (daylight saving from the second Sunday of March to the first Sunday of November: NY = UTC-4, otherwise UTC-5). t_start = 09:30 New York on D, t_end = 16:00 New York on D, both converted to UTC (13:30 and 20:00 UTC in summer, 14:30 and 21:00 UTC in winter). On the aux market a = F.aux_market(m, \"USATECHIDXUSD\"): start = searchsorted(a.ts, t_start, 'left') (first aux bar at or after t_start), end = searchsorted(a.close_times(), t_end, 'right') - 1 (last aux bar closed by t_end). Require end > start and both bars on UTC date D; otherwise no signal on D. shock_pct = 100 * (a.bid_c[end] / a.bid_o[start] - 1), using the window-start level directly. Acceptable fallback if the DST conversion cannot be done cleanly: a fixed 14:30-20:00 UTC window via F.aux_window_change(m, \"USATECHIDXUSD\", 14, 30, 20, 0) with the start level read from the aux bar at 14:30 UTC; the module docstring must say which was used.\n\nSIGNAL BAR: on each UTC date D whose weekday is Monday to Thursday, let S be the first primary bar whose close time is at or after 23:00 UTC on D and before 23:59 UTC on D (= 08:00 JST, one hour before the Tokyo open; this is already the next 17:00-New-York trading day). Require m.close_times()[S] >= t_end (the US close has happened). If no such bar exists, no trade on D. Attach shock_pct only to S. Condition: shock_pct <= -k (k in percent).\n\nENTRY: entry_short[S] = True, entry_type 0 (market at the next bar's open), valid_bars 1. One trade per UTC date; the executor ignores new entries while a position is open.\n\nSTOP: sl_dist[S] = sl_atr * ATR20_prev with ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to bar S (the daily ATR known at the start of the trading day that contains S). No trade if NaN or <= 0. tp_dist = NaN.\n\nEXIT: time exit at exit_utc (\"HH:MM\", F.parse_hhmm) on the next UTC date D+1: exit_short = True on the last bar whose close time is at or before exit_utc on D+1 and after the entry signal bar's close; the executor closes at the following bar's open. Safety net: max_bars[S] = number of M15 bars from S to 06:00 UTC on D+1 plus 4.\n\nFridays are excluded because there is no Tokyo session after a Friday US session; no longs, no other filters.",
 "params": {
  "k": 1.0,
  "sl_atr": 0.5,
  "exit_utc": "02:00"
 },
 "grid": {
  "k": [
   0.5,
   0.75,
   1.0
  ],
  "sl_atr": [
   0.5,
   1.0
  ],
  "exit_utc": [
   "02:00",
   "06:00"
  ]
 },
 "stage_a_market": "AUDJPY"
}

## Critic notes
Read US100 only through F.aux_market(m, 'USATECHIDXUSD') with explicit close-time logic, or through F.aux_window_change / F.aux_asof. For the DST-aware window, compute each UTC date's NY offset with the US rule (DST from the second Sunday of March to the first Sunday of November) or with polars convert_time_zone on the per-date timestamps. Find the start aux bar with searchsorted(a.ts, t_start, 'left') and the end aux bar with searchsorted(a.close_times(), t_end, 'right') - 1. Require end > start and both on the same date. Attach the shock value only to the primary signal bar S, and check that S's close time (m.close_times()[S]) is >= t_end, so the US close has happened. S = first primary bar with close time in [23:00, 23:59) UTC on UTC date D, with D Monday-Thursday. sl_dist = sl_atr * F.atr_prev(F.daily_bars(m), 20) mapped to S; skip if NaN or <= 0. Exit: exit_short on the last bar of D+1 whose close time is <= exit_utc and > S's close time. max_bars[S] = bars from S to 06:00 UTC on D+1 plus 4. One trade per date, shorts only. Every grid key (k, sl_atr, exit_utc) must be read from p. Do not use aux_asof at S as a denominator.
Revisions required: 1) Measure the shock on the US cash session in New York time: from the first US100 bar at or after 09:30 NY to the last US100 bar closed by 16:00 NY on the same NY date. Convert to UTC per date with the US DST rule (13:30/20:00 UTC in summer, 14:30/21:00 UTC in winter). shock_pct = 100 * (bid_c[end] / bid_o[start] - 1), using the start level directly, not lvl - chg. Acceptable fallback if the Builder cannot do this cleanly: a fixed 14:30-20:00 UTC window, which is inside the cash session in both seasons; say in the spec which was used. 2) Change the k grid to [0.5, 0.75, 1.0], so every arm has at least about 79 design trades. Restate the monotone kill as avg R(k=1.0) >= avg R(k=0.75) >= avg R(k=0.5) at the same stop and exit; a violation of more than 0.02 R at any step is a kill. Keep sl_atr [0.5, 1.0] and exit_utc ['02:00', '06:00']: 12 combinations. 3) Add a pre-registered regime kill: check-period avg R with 2022 removed must be > 0 at the chosen combination. 4) Update the expectations honestly: expected design t is 1.0-1.5 at the chosen point. State that a pass needs the pooled check (about 150+ trades at k = 1.0) and walk-forward to carry the evidence, and that a design t below 1 is a kill as written. 5) Keep the markets AUDJPY (stage A), NZDJPY and CADJPY, and the cross-market kill. Do not add markets after seeing stage A.

## Requirements
- `NAME = "jpy_cross_losscut_after_us_shock"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"k": 1.0, "sl_atr": 0.5, "exit_utc": "02:00"}
- `GRID = {"k": [0.5, 0.75, 1.0], "sl_atr": [0.5, 1.0], "exit_utc": ["02:00", "06:00"]}`
- Markets: ['AUDJPY', 'NZDJPY', 'CADJPY'] on M15 bars. Primary market for checks: AUDJPY.
- Auxiliary markets attached as m.aux: ['USATECHIDXUSD']. Read them only through F.aux_asof / F.aux_window_change / F.aux_market (see the strategy contract); they are cut to the same horizon and covered by the leak tests.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check jpy_cross_losscut_after_us_shock` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.