# Builder brief: gold_autumn_physical_demand

Write the strategy module to `strategies/auto/gold_autumn_physical_demand.py` (create or overwrite that file only).

## Hypothesis
{
 "slug": "gold_autumn_physical_demand",
 "title": "Gold autumn effect out of sample: long XAUUSD on every trading day of September-October (Indian festival and wedding-season physical demand), daily entries",
 "family": "seasonal_physical_demand_metal",
 "rationale": "Baur (2013, 'The autumn effect of gold price returns') documents on 1980-2010 data that gold's positive returns concentrate in September and November, and attributes it to physical demand: Indian jewellery buying for the Diwali and wedding season (India was 25-30% of world gold jewellery demand through the 2010s, and dealers restock from August to October), Chinese demand ahead of the October Golden Week, and central-bank and investor hedging into the fourth quarter. The buyers are price-insensitive on the calendar (weddings and festivals do not move), the sellers are bullion banks and ETFs that lean on the flow, and the pressure shows up as a positive drift over the season rather than at a clock time, which is why the flow atlas's intraday windows (which scanned gold by clock and day type, not by month) could not see it. This programme's data starts in 2010, so 2010-2017 is a clean out-of-sample test of a published pre-2010 anomaly, and 2018-2023 a second one. The structure is daily entries at 20:00 UTC with a 24-hour hold and a wide stop, so each trading day in the window is one trade and the sample is about 40 trades a year; the effective independent sample is still eight seasons in design, which is why the pre-registered t is modest. A control window is pre-registered inside the grid: March-April, the season Baur finds weakest, must not show the same drift. Costs are about 0.01 R per trade (33 pips of spread plus slippage against a 2 x ATR20 stop of about 4500 pips). Critic revisions accepted before any run: the primary window is the published September-and-November months, the control is all other months of the same years (April-May has its own Indian demand peak, so March-April was not a clean control), the window-minus-rest difference is a pre-registered requirement in design, check and any holdout, and the exit flag sits on the bar before the next signal bar so every Monday-Thursday day trades.",
 "markets": [
  "XAUUSD"
 ],
 "aux_markets": [],
 "timeframe": "H1",
 "rules": "All times UTC. Bars: H1 on XAUUSD. Bars are sparse; locate by timestamp.\n\nDAILY SIGNAL BAR: for each UTC date D, let E(D) be the last H1 bar whose close time is at or before 20:00 UTC on D and after 16:00 UTC on D. If none exists, no trade on D.\n\nWINDOW: window is a string parameter with three allowed values, by the UTC month of D: \"sep_nov_baur\" = D in September or November (the months Baur publishes; primary); \"sep_nov\" = D in September, October or November (the broader physical-demand season); \"rest\" = every other month (January to August and December; the pre-registered control). Raise on any other value. Weekday of D must be Monday to Thursday (a Friday entry would hold over the weekend; it is excluded so every trade is a 24-hour hold).\n\nENTRY: on bar E(D) inside the window: entry_long[E(D)] = True, entry_type 0 (market at the next bar's open), valid_bars 1. With the exit placed on the bar before the next signal bar, the position is flat when the next signal registers.\n\nSTOP: sl_dist[E(D)] = sl_atr * ATR20_prev with ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to E(D); no trade if NaN or <= 0. tp_dist = NaN.\n\nEXIT: let X = E(D_next), the signal bar of the next UTC date (any weekday, including Friday) that has a valid E. Set exit_long[X - 1] = True (the last bar before X), only if X - 1 > E(D); the executor then closes at the open of bar X, which ends at 20:00 UTC on D_next (about a 23-hour hold), so the position is flat when the next day's signal at X registers and every Monday-Thursday day in the window trades. Safety net: max_bars[E(D)] = 30. H1 bars are labelled by open time; a bar's close time is ts + 1h.\n\nLongs only, no other filters.",
 "params": {
  "window": "sep_nov_baur",
  "sl_atr": 2.0
 },
 "grid": {
  "window": [
   "sep_nov_baur",
   "sep_nov",
   "rest"
  ],
  "sl_atr": [
   1.0,
   2.0
  ]
 },
 "stage_a_market": "XAUUSD"
}

## Critic notes
H1 bars are labelled by open time. E(D) is the last bar on UTC date D whose close (ts + 1h) is in (16:00, 20:00] UTC, normally the bar opening 19:00. Window membership uses the UTC month of D. window is a string param read from p['window'], with values sep_nov_baur (months 9 and 11), sep_nov (months 9-11) and rest (months 1-8 and 12); raise on any other value. Weekday of D must be Mon-Thu. ATR: daily.to_bars(F.atr_prev(daily, 20))[E(D)]; skip if NaN or <= 0. Entry: entry_long[E(D)] = True, type 0, valid_bars 1, sl_dist = sl_atr * ATR, tp NaN, max_bars = 30. Exit: let X = E(D_next), where D_next is the next UTC date with a valid E (any weekday, including Friday). Set exit_long[X - 1] = True only if X - 1 > E(D) (oracle pattern exit_long[xi - 1]). Do not add an entry on Fridays or weekends. Loop over dates, not bars. No other filters.
Revisions required: 1) Windows: "sep_nov_baur" = D in September or November (the published months; primary), "sep_nov" = September 1 to November 30 (the broader physical-demand season), "rest" = every other month (January-August and December; the control). Drop sep_oct and mar_apr. Grid: window x sl_atr [1.0, 2.0] = 6 combinations. Default window = sep_nov_baur, sl_atr = 2.0. 2) Kill rule (1) moves to sep_nov_baur at sl_atr = 2.0. Kill rule (2) becomes: in design, avg R(sep_nov_baur) - avg R(rest) >= 0.02 at the same stop, otherwise kill regardless of sign. Kill rule (4) adds: in check, avg R(window) - avg R(rest) > 0 at the chosen combination. If promoted, the holdout verdict must also report the window-minus-rest difference, and a holdout where the window does not beat the rest is a fail even if raw avg R > 0. Pre-register this now. 3) Kill rule (3), seasons not days: at least 5 of 8 design seasons (Sep + Nov R sum per year) positive. Keep it. 4) Exit: set exit_long on the last bar before E(D_next), not on E(D_next). The trade then closes at the open of the bar ending at 20:00 UTC on D_next (about a 23-hour hold), the position is flat when the next day's signal registers at E(D_next), and every Mon-Thu day in the window trades. Minimum design trades: 250 for sep_nov_baur. 5) Update expectations: design t 1.0-1.7 is accepted as below the pass bar. Register that a pass needs design t >= 2, which this test reaches only if the effect is stronger than published.

## Requirements
- `NAME = "gold_autumn_physical_demand"`; `PARAMS` must contain exactly these defaults (more keys are fine): {"window": "sep_nov_baur", "sl_atr": 2.0}
- `GRID = {"window": ["sep_nov_baur", "sep_nov", "rest"], "sl_atr": [1.0, 2.0]}`
- Markets: ['XAUUSD'] on H1 bars. Primary market for checks: XAUUSD.
- No auxiliary markets: use only m's own bars.
- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).
- Restate the rules in the module docstring.

## Checker
Run `.\.venv\Scripts\python.exe scripts\cycle_step.py check gold_autumn_physical_demand` from D:\Traders sir after writing the file. It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.