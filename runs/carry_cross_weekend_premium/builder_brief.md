# Builder brief: carry_cross_weekend_premium

Write the strategy module to `strategies/auto/carry_cross_weekend_premium.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "carry_cross_weekend_premium",
 "title": "Weekend risk premium in carry crosses: long AUDJPY (NZDJPY, AUDUSD, NZDUSD) from the Friday New York afternoon to the Monday Tokyo or London open, with a weekday-overnight control",
 "family": "weekend_risk_premium_carry",
 "rationale": "Leveraged carry positions (Japanese retail margin books, CTAs, macro funds) cannot be adjusted for about 48 hours over the weekend, and weekend gap risk in the yen crosses is the largest in FX (the Monday-gap column of the market facts shows AUDJPY 1.2, NZDJPY 2.0, GBPJPY 3.9 pips median, with the tails far larger). Risk managers therefore cut high-yield exposure into the Friday New York afternoon and re-establish it on Monday in Tokyo and London; dealers widen and run flat inventory over the weekend and buy back Monday. The holder who carries the risk over the weekend is paid, if at all, by price alone: spot settles T+2, so the triple rollover falls on Wednesday (in Dukascopy prices and in this engine's cost model), and both the Friday arm and the Monday control cross exactly one single rollover, so net carry is about zero minus the 1% markup. The premium, if it exists, is the price effect of Friday selling and Monday buying. This is the FX analogue of the weekend and overnight risk premia documented in equities (Lou, Polk and Skouras 2019) and of the 'weekend effect' literature in currencies (Yamori and Kurihara 2004), which the flow atlas could not see: its windows were intraday (30 minutes to 8 hours) on single weekdays, so a Friday-to-Monday hold was never measured, and no prior report in the index holds a position over a weekend by design (the gap tests measured Monday gap fills, not the weekend return). Costs are not negligible at the weekend edges: spreads at the Friday 20:00 UTC entry and around the Monday 00:00 UTC exit are far wider than the all-hours median, roughly 3-4 pips round trip including commission on AUDJPY, which is 0.015-0.03 R against a 1.5-3 x ATR20 stop of 120-240 pips, the same order as the premium being sought; every arm therefore reports gross and net R and its mean entry and exit spread. Sample: every weekend, so about 410 design trades per market, which is why this family was chosen after cycles 3 and 4 died at the underpowered single-market gate. A weekday-overnight control is built into the grid: the same hold from Monday 20:00 UTC to Tuesday morning measures the overnight carry drift without the weekend, so the weekend premium must beat it. EURJPY is included as a low-carry comparison: if EURJPY shows the same premium the effect is a JPY-risk premium rather than carry, which is still tradeable but changes the interpretation. Critic revisions accepted before any run: carry claim removed (triple rollover is Wednesday), cost estimate from the actual weekend-edge spreads, exit at the open of the first bar opening at or after exit_utc, 2020 rule additive to the hard gate, paired fri-minus-mon t and 3-of-4 market rule, safety-net hold cut to 24 bars.",
 "markets": [
  "AUDJPY",
  "NZDJPY",
  "AUDUSD",
  "NZDUSD",
  "EURJPY"
 ],
 "aux_markets": [],
 "timeframe": "H1",
 "rules": "All times UTC. Bars: H1, labelled by open time; a bar's close time is ts + 1h. Bars are sparse; locate by timestamp.\n\nENTRY DAY: entry_day is a string parameter: \"fri\" (the hypothesis, F.weekday == 4) or \"mon\" (the weekday-overnight control, F.weekday == 0). For each UTC date D whose weekday equals entry_day, let ei = F.first_bar_at_or_after(m, [D], entry_hh, entry_mm); require ei >= 1 and m.ts[ei] no more than 60 minutes after the target time D + entry_utc, otherwise no trade on D. The signal bar is S = ei - 1 (the bar that closes at the entry time), so the market fill lands at the open of bar ei, i.e. at entry_utc (oracle pattern, strategies/oracle/m3_usd_bid.py).\n\nENTRY: entry_long[S] = True, entry_type 0 (market at the next bar's open), valid_bars 1. One trade per entry date. Longs only (long the high-yield currency: AUDJPY, NZDJPY, AUDUSD, NZDUSD, EURJPY are all quoted so that a long is long the first currency, which is the higher-yielding side in 2010-2023 for AUD and NZD; EURJPY is the low-carry comparison).\n\nSTOP: sl_dist[S] = sl_atr * ATR20_prev, ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to S; no trade if NaN or <= 0. tp_dist = NaN. A gap through the stop at the Sunday/Monday open exits at that open (executor rule).\n\nEXIT: let D_exit = D + 3 calendar days when entry_day = \"fri\" (the Monday) and D + 1 calendar day when entry_day = \"mon\" (the Tuesday). Let X = F.first_bar_at_or_after(m, [D_exit], exit_hh, exit_mm), the first H1 bar whose OPEN time is at or after exit_utc on D_exit (a Monday 00:00 target may be preceded by Sunday-evening UTC bars; first_bar_at_or_after on the Monday date handles that). Require X < m.n, X - 1 > S and m.ts[X] no more than 60 minutes after the target time; otherwise skip the trade entirely (do not rely on max_bars for a missing exit). Set exit_long[X - 1] = True, so the position closes at the open of the bar starting at exit_utc. Safety net: max_bars[S] = 24 for both arms (a longer net could let a missed exit run to the Wednesday triple rollover and mix in the carry the control is meant to exclude).\n\nNo other filters.\n\nREPORTING (stage C): for every arm report gross R (before spread and commission) alongside net R, the mean entry and exit spread in pips, the paired fri-minus-mon difference and its t per market, and the individual weekend trades of 2015-08 and 2020-03 (and 2024-08 only at promotion).",
 "params": {
  "entry_day": "fri",
  "entry_utc": "20:00",
  "exit_utc": "07:00",
  "sl_atr": 1.5
 },
 "grid": {
  "entry_day": [
   "fri",
   "mon"
  ],
  "entry_utc": [
   "16:00",
   "20:00"
  ],
  "exit_utc": [
   "00:00",
   "07:00"
  ],
  "sl_atr": [
   1.5,
   3.0
  ]
 },
 "stage_a_market": "AUDJPY"
}

## Critic notes
Follow the oracle pattern (strategies/oracle/m3_usd_bid.py) for clock times. Entry: for each UTC date D with weekday == entry_day (Fri = 4, Mon = 0 via F.weekday), ei = F.first_bar_at_or_after(m, [D], eh, em). Require m.ts[ei] - (D + entry_utc) <= max_delay (60 min on H1) and ei >= 1. sig = ei - 1; entry_long[sig] = True, entry_type 0, valid_bars 1. sl_dist[sig] = p['sl_atr'] * atr[ei], where atr = daily.to_bars(F.atr_prev(daily, 20)); skip if not finite or <= 0. tp_dist NaN. Exit: D_exit = D + 3 days for 'fri', D + 1 day for 'mon'. xi = F.first_bar_at_or_after(m, [D_exit], xh, xm). Require xi < m.n, xi - 1 > sig and m.ts[xi] - (D_exit + exit_utc) <= 60 min. Then exit_long[xi - 1] = True, max_bars[sig] = 24 as a safety net. Do NOT use 'first bar whose close >= exit_utc' (that exits one hour early). Note that a Monday 00:00 exit target can be preceded by Sunday-evening UTC bars (the market opens Sun 21:00/22:00 UTC); first_bar_at_or_after on the Monday date handles that correctly. Read every grid key from p (entry_day, entry_utc, exit_utc, sl_atr) and put all of them in PARAMS. Longs only on every market; no side logic needed. Do not filter on anything else (no vol filter, no rate filter): the hypothesis is unconditional. Loop over dates, not bars.
Revisions required: 1) Rationale and expectations: delete the 'three days of positive carry' / 'paid twice' claim. State that both arms cross exactly one 1x rollover (triple is Wednesday, in the engine and in Dukascopy prices), so net carry is about zero minus the 1% markup and the premium must come from price. Re-state the expected design avg R as a price-only premium after realistic weekend-edge costs: at least +0.02 R at sl_atr 1.5. 2) Cost statement: replace 'about 0.01 R' with an estimate from the actual Friday 20:00 UTC and Monday 00:00 UTC spreads, roughly 3-4 pips round trip including commission, 0.015-0.03 R. Report gross (before spread/commission) and net R for every arm, and report the mean entry and exit spread for each arm, so the fri/mon comparison can be read net of the spread difference. 3) Exit rule: X = the first H1 bar whose OPEN time (m.ts) is at or after exit_utc on D_exit, i.e. F.first_bar_at_or_after(m, [D_exit], hh, mm). Skip the trade if m.ts[X] is more than 60 minutes after the target (the max_bars net then does not apply). Set exit_long[X-1] = True when X-1 > S, so the close happens at the open of the bar starting at exit_utc. 4) Kill rule (4): the hard gate (check avg R > 0 over all check years) stays. 'Positive with 2020 removed' is an extra requirement, not a substitute. Also report 2015-08, 2020-03 and 2024-08 (holdout, at promotion only) weekend trades individually. 5) Control kill rule (2): keep the >= 0.03 R threshold and also report the t of the paired fri-minus-mon difference per market. Pre-register that the difference must be positive on at least 3 of the 4 AUD/NZD markets at the chosen combination, so one market cannot carry it. 6) Reduce max_bars to 24 for both arms. 80 H1 bars would let a missed Monday exit run to Wednesday and cross the triple rollover, mixing in exactly the carry the control is meant to exclude.

## Requirements
- `NAME = "carry_cross_weekend_premium"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"entry_day": "fri", "entry_utc": "20:00", "exit_utc": "07:00", "sl_atr": 1.5}
- `GRID = {"entry_day": ["fri", "mon"], "entry_utc": ["16:00", "20:00"], "exit_utc": ["00:00", "07:00"], "sl_atr": [1.5, 3.0]}`
- Markets: ['AUDJPY', 'NZDJPY', 'AUDUSD', 'NZDUSD', 'EURJPY'] on H1 bars. Primary market for checks: AUDJPY.
- No auxiliary markets: use only m's own bars.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check carry_cross_weekend_premium` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.