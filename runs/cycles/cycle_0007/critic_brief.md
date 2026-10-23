# Programme charter (shared by every role)

Goal: find strategies, or a small basket of them, that a retail prop trader can execute and that give a
credible, measured probability of passing the Alpha Capital "Alpha Swing" $10k challenge
(phase 1 +10%, phase 2 +5%, 10% static max loss, 5% daily loss, >= 3 trading days per phase, no time limit,
1:30 FX leverage; indices and metals allowed). An honest negative is a valuable result; a flattering
backtest that fails live is the worst outcome. Nothing here is a guarantee; the output is a probability.

Data: Dukascopy 1-minute bid and ask bars, 2010 to 2026, for 28 FX pairs, XAUUSD, XAGUSD and index CFDs
(US500, US100, US30, GER40, UK100, JP225; indices start 2011-2013 and are patchy before 2014). Resampled
timeframes M3, M5, M15, M30, H1, H2, H3, H4, H8, D1, W1 (daily and weekly bars close 17:00 New York).
Spreads are raw Dukascopy spreads; costs on top: $7 per lot round turn (FX), 0.2 pip slippage on market
and stop fills, swap from real policy rates with a 1% markup. Every result is after costs.

Time splits: design 2010-2017, check 2018-2023, holdout 2024-2026. The holdout is locked. Nothing in
stages A-C sees a holdout bar. A strategy reaches the holdout once, when promoted, and that run is counted.

Protocol:
1. Every hypothesis is pre-registered: economic mechanism, exact rules, parameter ranges, the primary
   market, expected design t and average R, minimum trades, and a kill rule, all written before any run.
2. Signals may only use information available at the close of the bar they are placed on. Automated
   truncation and future-perturbation tests catch leaks; a leak is an immediate scrap.
3. Pipeline: stage A coarse grid on the primary market (design years); stage B full grid on every market
   in the spec (design years); stage C on the chosen combination: check-period stats, walk-forward over
   design plus check, parameter-neighbour stability, cost stress at 1.5x and 2x, Monte Carlo, deflated
   Sharpe with the programme trial count, year-by-year regime check.
4. Hard gates (fail = scrap): no leak; stage A floor (design avg R > 0 and t >= 1); design positive on
   at least one market; check avg R > 0 with >= 30 trades; walk-forward OOS avg R > 0; positive at 1.5x
   costs; enough out-of-sample trades. Soft gates (warnings the Director weighs): neighbour stability,
   deflated Sharpe, half the years positive, positive at 2x costs.
5. The pass bar inherited from earlier work: design t >= 2 and avg R > 0 in check and in holdout. With
   N tests about 0.6% pass that bar by luck, and long-only tests on rising indices pass 2-8% of the time.
6. Costs decide. Tight-stop intraday ideas on FX die at 1-1.5 pips of cost plus spread. Edges that have
   survived here are flows tied to the clock and the calendar on USDJPY, and little else.
7. Families, not points: a hypothesis is a parametrised family; the surface is judged, not the best point.
   Grids stay small (ideally <= 12 combinations, never more than 36) and parameters come from theory, not
   from staring at the data.
8. Never re-test a scrapped idea with new knobs. Build on it only if the mechanism is clearly different.

Trading-day convention: a trading day runs 17:00 to 17:00 New York; 1 R = the stop distance from the fill.

# Your role: Critic

You review before compute is spent and before results are trusted. Two tasks:

Hypothesis review: for each proposed hypothesis decide approve, revise or reject. Reject when the
mechanism is indicator soup without an economic reason, when it duplicates a scrap-index entry without a
new mechanism, when costs will dominate at that timeframe and instrument (use the market facts), when the
grid is too large to judge as a family, or when the pre-registered expectations are vague or unfalsifiable.
Revise when a specific change fixes it (state the change). Say what the overfit risk is and why.

Code review: you receive the hypothesis, the rules in words, and the Builder's module. Check it against the
strategy contract: look-ahead (any use of bar i+1 or later, centred windows, full-sample statistics, daily
features not shifted, times read from the wrong bar), the rules as written (times, sides, stop and target
distances, filters), parameter plumbing (every grid key read from p, defaults present), sparse-bar handling,
degenerate sl_dist, timezone handling. Blockers are leaks and rule mismatches. Be concrete: quote the line
and say the fix.


# Hypotheses to review
[
 {
  "slug": "jpy_fiscal_year_end_repatriation",
  "title": "Japanese fiscal-calendar flows in Tokyo hours: short USDJPY in the last business days of March (and September) when exporters and institutions repatriate and square books for the fiscal year-end, long USDJPY in the first business days of April (and October) when new-year outward allocations start; each leg with a same-window ordinary-month control arm",
  "family": "fiscal_calendar_flow_jpy",
  "rationale": "Mechanism: about 70 percent of listed Japanese companies close their fiscal year on 31 March (half-year on 30 September). Exporters and their overseas subsidiaries repatriate foreign-currency earnings to book them and fund year-end dividends and tax; corporate treasuries and banks square foreign-currency exposures for the balance-sheet date; life insurers, pension funds and the GPIF rebalance to fiscal-year targets. These participants must trade by a date, they execute in Tokyo hours (the Tokyo cash session and the 09:55 JST fix), and the flow is one-way (sell USD, buy JPY) and concentrated in the last two weeks of March. After 1 April the sign reverses: life insurers and pension funds deploy new-fiscal-year foreign-asset allocations, and Toshin launches cluster in April (the dealer convention of April yen selling). The other side is dealers and speculators who know the convention; the gotobi edge (post-fix short +0.14 R design, +0.11 R check, gj-strat) shows that known, dated, obligated Tokyo-hour flows still move price in this data set, and the gotobi month-end-only variant (94 trades, design +0.176 R, check +0.393 R, gotobi_tweaks) shows month-end Tokyo flows are larger than ordinary gotobi flows. This hypothesis asks whether fiscal month-ends carry a flow beyond the ordinary month-end and month-start, which the control arm measures directly. Why this is new: the flow atlas conditioned on clock x weekday, gotobi, k-th-last weekday and holiday-adjacent day types but never on the month of the year, so the fiscal calendar is the one calendar dimension the 600,912-test scan did not cover; the month-end hedge (Melvin-Prins) is an equity-hedge flow at the London 4pm fix on every month-end and is dead after 2018; the Tokyo-fix tests traded a fix minute, not the session; the gold autumn seasonal tested a diffuse festival demand with no settlement date and died, and its lesson is scoped to gold. This is a dealer convention, not a published anomaly, so it is an out-of-sample test of the convention. Design: M15 bars on USDJPY (0.6 pip median spread; about 0.7-0.9 pips at the Tokyo open), market entry at 00:00 UTC (09:00 JST, Tokyo cash open), time exit at 06:00 UTC (15:00 JST, cash close), stop 0.25 or 0.5 x ATR20, no target; one trade per selected weekday. Two legs: ye_short (last n_days weekdays of the fiscal-end months, SHORT USDJPY) and ny_long (first n_days weekdays of the new-year months, LONG USDJPY). Three month sets: mar (March / April only), mar_sep (March+September / April+October) and ctrl (the same windows in the ordinary months 1, 2, 5, 7, 8, 11; June and December are excluded as quarter and calendar year-ends). Counts (design 2010-2017, from the calendar, no outcomes): ye_short mar n10 = 80 trades, mar_sep n10 = 160, ctrl n10 = 480; n5 halves these; check 2018-2023 has 60 / 120 / 360. Costs: round trip about 1.7 pips (0.6-0.9 spread, 0.7 commission, 0.4 slippage) = about 0.10 R at the 0.25 x ATR stop (about 17 pips in the design years), 0.05 R at 0.5 x ATR. Expected: if the fiscal flow moves USDJPY an extra 3-4 pips per Tokyo session beyond ordinary days, the March cell nets about +0.10 R at sl 0.25 with sd about 0.7 R, design t about 1.2-1.5 on 80 trades (lower on the mar_sep cell if September is weaker); the control should sit near zero or slightly positive (the gotobi month-end effect leaks into it on 2 of every 10 days). With these counts the stage A floor passes with only about 55-60 percent probability if the effect is real, so a kill is weak evidence and a pass is strong evidence. Human execution: two orders a day on at most 20 days a year, placed at 09:00 JST with a time exit at 15:00 JST; trivially executable on a prop account and uncorrelated in time with the vol-box, gotobi and M-3 legs except on the 2-3 gotobi dates inside each window.",
  "markets": [
   "USDJPY",
   "EURJPY",
   "AUDJPY",
   "GBPJPY"
  ],
  "aux_markets": [],
  "timeframe": "M15",
  "rules": "All times UTC. Bars: M15, sparse; locate every time by timestamp with F.first_bar_at_or_after and never assume one bar per slot.\n\nDATE SELECTION (calendar dates, UTC): dates = unique F.utc_dates(m) with F.weekday(d) < 5 and d >= start. month(d) = calendar month number of d (1..12).\n- Month sets by p['months']: if 'mar': H_short = {3}, H_long = {4}; if 'mar_sep': H_short = {3, 9}, H_long = {4, 10}; if 'ctrl': H_short = H_long = {1, 2, 5, 7, 8, 11}.\n- Leg p['leg'] = 'ye_short': select d with month(d) in H_short and F.kth_last_weekday(dates)[d] in {0, 1, ..., n_days - 1} (the last n_days weekdays of the month; 0 = last weekday). Side = SHORT.\n- Leg p['leg'] = 'ny_long': select d with month(d) in H_long and rank(d) in {0, 1, ..., n_days - 1}, where rank(d) = np.busday_count(first calendar day of d's month, d) = the number of weekdays in the month strictly before d (0 for the first weekday of the month; default Mon-Fri weekmask, no holidays). Side = LONG.\n- Japanese and other holidays are not excluded (no calendar in the engine); the flow is simply absent on those days.\n\nENTRY: ei = F.first_bar_at_or_after(m, d, 0, 0) (entry_utc '00:00'). Skip the date if ei < 1, or ei >= m.n, or m.ts[ei] is more than max_delay_min (10) minutes after d 00:00 UTC. sig = ei - 1, so the fill is at the open of bar ei (ask for longs, bid for shorts, plus slippage). entry_short[sig] = True (ye_short) or entry_long[sig] = True (ny_long); entry_type[sig] = 0; valid_bars[sig] = 1.\n\nSTOP: ATR20 = F.atr_prev(F.daily_bars(m), atr_n = 20) mapped to bars with daily.to_bars (known at the start of the trading day). Skip the date if ATR20[ei] is not finite or <= 0. sl_dist[sig] = sl_atr x ATR20[ei] (price units, > 0). tp_dist = NaN (no target). max_bars = 0.\n\nEXIT: xi = F.first_bar_at_or_after(m, d, 6, 0) (exit_utc '06:00'). Skip the date if xi >= m.n or xi <= ei. exit_short[xi - 1] = True (ye_short) or exit_long[xi - 1] = True (ny_long), so the position closes at the open of the first bar at or after 06:00 UTC. No other exits, no filters, one trade per selected date; the executor blocks overlapping entries.\n\nPARAMETERS (every one read from p): leg (grid 'ye_short', 'ny_long'), months (grid 'mar', 'mar_sep', 'ctrl'), n_days (grid 5, 10), sl_atr (grid 0.25, 0.5); fixed entry_utc '00:00', exit_utc '06:00', max_delay_min 10, atr_n 20, start '2010-01-01'. Grid = 24 cells. The 'ctrl' cells are control arms: they run at stage A only; stages B, C, the walk-forward and any holdout use months in {'mar', 'mar_sep'} (16 cells), set in the spec after the review step.\n\nREPORTING (stage A table and stage C, computed from the trades): per cell the number of trades, avg R, trade-level t, month-window-clustered t (R averaged per calendar month of the entry date, then a t over those month means), mean fill spread in pips, by-year avg R; for the chosen cell the avg R and count after removing gotobi dates (F.is_gotobi) and the avg R without the best two month-windows.",
  "params": {
   "leg": "ye_short",
   "months": "mar",
   "n_days": 10,
   "sl_atr": 0.25,
   "entry_utc": "00:00",
   "exit_utc": "06:00",
   "max_delay_min": 10,
   "atr_n": 20,
   "start": "2010-01-01"
  },
  "grid": {
   "leg": [
    "ye_short",
    "ny_long"
   ],
   "months": [
    "mar",
    "mar_sep",
    "ctrl"
   ],
   "n_days": [
    5,
    10
   ],
   "sl_atr": [
    0.25,
    0.5
   ]
  },
  "stage_a_market": "USDJPY",
  "pre_registered": {
   "expected_design_t_min": 1.2,
   "expected_avg_r": 0.1,
   "min_trades_design_per_market": 80,
   "kill_if": "(1) Hypothesis-cell floor on USDJPY, applied by the Director even if the pipeline reports a candidate (the automatic stage A gate ranks all 24 cells by design t and a 480-trade control cell can outrank an 80-trade hypothesis cell): the best cell with months in {mar, mar_sep} must have design avg R > 0, trade-level t >= 1 and month-window-clustered t >= 1 with at least 80 trades; otherwise scrap. The chosen cell is that best hypothesis cell; its leg, n_days and sl_atr fix the comparisons below. (2) Control: avg R(chosen cell) minus avg R(the ctrl cell with the same leg, n_days and sl_atr) must be >= +0.06 R in design; if the ordinary months earn as much in the same window, the effect is the generic month-end or month-start Tokyo pattern that the atlas's last-weekday and k-th-weekday day types and the gotobi month-end variant already measured, and the hypothesis dies with that lesson. (3) Gotobi separation: design avg R at the chosen cell must stay > 0 after removing gotobi dates (F.is_gotobi: 5th, 10th, 15th, 20th, 25th and month-end, weekend dates moved back to Friday); if it does not, the result is the gotobi short again (measured, including its month-end-only variant) and the hypothesis is dead. (4) Regime and clustering: at least 4 of the 8 design years positive at the chosen cell, and design avg R must stay > 0 after removing the best two month-windows; a result carried by one or two Marches is scrapped as an episode, not a flow. (5) Costs: the hard gate (positive at 1.5x costs) stands; the mean fill spread is reported; if the chosen cell is positive gross but negative net, the lesson is that the fiscal flow exists but moves USDJPY by less than about 2 pips per Tokyo session and cannot be traded from the open. (6) Replication: the repatriation is against every foreign currency, so at the chosen cell the design avg R pooled over EURJPY, AUDJPY and GBPJPY must be > 0, and the pooled-check hard gate (avg R > 0 with >= 30 trades) and the walk-forward gate stand; a USDJPY-only result with the crosses negative is scrapped as noise. (7) Legs are separate claims with their own pre-registered sign: if only one leg passes rules 1-6 the other is scrapped with its lesson and the survivor goes forward alone; neither leg's sign is ever flipped. Honest expectation: about +0.10 R net at sl 0.25 on 80 March trades, design t 1.2-1.5, mar_sep weaker if September is a smaller flow; the stage A floor passes with only about 55-60 percent probability if the effect is real at that size, so a kill is weak evidence and a pass is strong evidence; the most likely failure is that the flow is spread over London hours and hedged forward rather than executed spot in Tokyo, which would show as a control-sized or zero result."
  },
  "similar_prior": [
   "prior_flow_atlas",
   "prior_fix_fades",
   "prior_tokyo_fix_long",
   "prior_gotobi_holiday_calendar",
   "prior_monthend_hedge",
   "prior_ust_auction",
   "usdjpy_tokyo_fix_holiday_shift",
   "gold_autumn_physical_demand"
  ],
  "why_different": "Every calendar test in the index conditioned on weekday, k-th-last weekday, gotobi or holiday-adjacent day types (the atlas: clock x those day types x currency strength; M-3; month-end hedge at the London fix; gotobi and its 40 tweaks including the month-end-only and run-up variants), or on a fix minute (Tokyo fix long, holiday-shifted fix). None conditioned on the month of the year, so the fiscal calendar is the one calendar dimension the 600,912-test scan left unmeasured, and this hypothesis is not a re-slice of a scanned slot: the slot (one month, one session, one direction) is fixed by the mechanism before any data is seen, so the family-wise error is the 24-cell grid, not the atlas's 600k tests, which is the same logic the programme applies to every pre-registered hypothesis. The gold autumn test was a diffuse festival demand with no settlement deadline and its lesson is scoped to gold; here the participant is obligated by a balance-sheet date, as the gotobi importers are by their settlement date, and the control arm measures the generic month-end component that the gotobi month-end variant already showed to exist, so the test isolates the fiscal excess. The ny_long leg is not a snooped flip of ye_short: it is a different month, a different participant (new-year outward investors) and its sign comes from the mechanism, registered here before any run.",
  "parent_slug": null
 }
]

# Scrap index
- fx_liquidity_withdrawal_reversal [liquidity_provision_spread_state] Liquidity-withdrawal reversal: fade a large one-hour move only when the quoted spread blew out during it (dealers withdrew), with no-spread-condition and scheduled-news control arms, on USDJPY first: The quoted-spread state does not identify tradeable liquidity concessions on USDJPY at the intraday horizon, and the liquidity-provision family (conditioning on clock, level, size, tick volume and now spread) is closed. The hypothesis cell (one-hour move >= 0.25 x ATR20 with the M15 spread proxy >= 2 x its same-slot median, scheduled releases and the rollover excluded, two-hour time exit) had 160 design episodes on 123 trading days and made -0.020 R net (t -0.31; clustered t +0.22) with a gross of exactly 0.000 R on bid/ask fills, so the concession is competed away before a market order fills; the one-bar delay arm made -0.058 R (t -0.94); check was -0.065 and -0.081 R; the 0.40 x ATR cells -0.078 and -0.107 R. The no-spread-condition control measured the plain one-hour intraday shock fade on USDJPY for the first time at scale: -0.068 R (t -4.5, 2075 trades, every design year negative, gross -0.039 R before commission) and -0.073 R in check (t -4.2, 1629 trades); news-inclusive -0.070 R on 3576 trades. So one-hour moves of a quarter ATR keep going for the next two hours, by about 2 percent of the move on mid prices, which is below the 0.05 R round-trip cost: the spread condition recovered +0.048 R of that loss (below the +0.08 R pre-registered threshold) but nothing more, the news-inclusive arm was no different (-0.004 vs -0.020 R, inside the 0.05 R bound: no overreaction to scheduled news either), the fill spread was 0.89 pips so cost was not the cause, and the only positive pocket (28 episodes inside the 23:50 UTC Japan-data and 06:30 BoJ windows, +0.47 R) is a post-hoc cluster of information events and is not to be chased. Do not register the follow-the-move mirror (its gross edge of about 0.02-0.04 R is less than the cost and its sign was read off this run), do not retry with M5 or H1 bars, tighter or looser spread ratios, other move sizes, limit entries (the executor pays the spread on limits too), or EURUSD and gold as the primary, and do not use the spread ratio as a filter on any other idea.
- carry_cross_weekend_premium [weekend_risk_premium_carry] Weekend risk premium in carry crosses: long AUDJPY (NZDJPY, AUDUSD, NZDUSD) from the Friday New York afternoon to the Monday Tokyo or London open, with a weekday-overnight control: There is no weekend risk premium in carry crosses net of costs, and no weekday-overnight premium either. On AUDJPY every one of the 16 pre-registered arms lost in design (2010-2017, 412 trades per arm): the eight Friday-to-Monday arms made -0.008 to -0.030 R (t -1.2 to -2.5) and the eight Monday-to-Tuesday overnight controls -0.004 to -0.026 R (t -0.3 to -4.3); the check period was flat (-0.021 to +0.006 R). Holding AUDJPY across the Friday-to-Monday gap costs the weekend-edge spread (3-4 pips round trip including commission) and earns nothing in price; the premium that equities show overnight does not exist in FX carry pairs at this horizon. Stage B never ran, so NZDJPY, AUDUSD, NZDUSD and EURJPY are unmeasured, but the primary market was the best-motivated one and the control arms lost too. Do not retry with other entry or exit hours, the Thursday-to-Monday hold, the short side (a snooped flip), EURJPY or GBPJPY stage A, a VIX or realised-vol gate, or an equity-state aux condition.
- gold_autumn_physical_demand [seasonal_physical_demand_metal] Gold autumn effect out of sample: long XAUUSD on every trading day of September-October (Indian festival and wedding-season physical demand), daily entries: Gold calendar-month seasonals are dead for this programme. Baur's autumn effect (long gold in September and November) tested out of sample with an all-other-months control: the published months LOST in design (-0.040 R per 23-hour trade, t -1.9, 275 trades; September-November -0.036 R, t -2.2, 416 trades) while the rest-of-year control was flat (0.000 R, 1228 trades), so the effect reversed sign after 2010 rather than fading. Do not retry with other month windows, Chinese New Year windows, Diwali-date windows, or a short-the-weak-season mirror.
- fx_volume_climax_reversal [liquidity_provision_capitulation] Volume-climax capitulation reversal: fade a one-day shock move only when it carries a tick-volume climax (forced liquidation), on FX majors, yen crosses and gold, 1-3 day hold: Tick volume is not a capitulation signal on FX. Dukascopy volume is summed quoted size: its 20-day ratio rarely exceeds 1.7 even on crisis days, so climax arms hold 10-50 design trades and cannot be read. The no-filter control (v = 0) measured the plain one-day shock reversal on EURUSD for the first time in this programme: fading a one-day move >= 1 x ATR20 LOSES -0.10 R (t -2.5, 245 design trades) and -0.18 R at 1.25 x ATR20, so shock days on majors continue rather than reverse at the one-day horizon, extending cross_zfade's lesson from crosses to majors; the volume filter only softened that loss (v = 1.3: -0.08 to -0.21 R on 43-46 trades). Do not reuse tick volume as a signal input, and do not register the 'follow the shock' mirror: its sign was read off this run's control arm, and the check period of that arm was near zero (-0.04 R fade), so the mirror would be a snooped flip with no out-of-sample support.
- jpy_cross_losscut_after_us_shock [cross_asset_forced_liquidation] Forced losscut flow: short AUDJPY (NZDJPY, CADJPY) into the Tokyo pre-open after a US-session equity shock: Conditional NY-to-Tokyo continuation in yen crosses is dead, like unconditional continuation and unconditional fades before it. Shorting AUDJPY at 08:00 JST after a US100 cash-session drop lost in every one of 12 arms in design (best -0.02 R, worst -0.16 R, t -0.6 to -2.8), and the loss grew with shock size and with the shorter 02:00 UTC exit: the crosses bounce in the Tokyo morning after a US selloff. If retail losscuts happen they are done before 08:00 JST. The mirror long is not a new hypothesis: its sign was read off this run on design and check data, so it is a data-snooped flip and must never be registered or given a holdout touch. Do not retry with NZDJPY/CADJPY stage A, other shock thresholds, USDJPY, or the US500 aux.
- boj_etf_lunch_bid_jp225 [central_bank_flow_index] BoJ ETF purchase flow: buy JP225 at the Tokyo lunch break when the morning session is down versus the previous close, exit before the cash close: rejected by critic: The named buyer no longer exists, so the strategy cannot be traded. In April 2021 the BoJ moved to purchases only on large declines (about 2% or more), purchases were rare in 2022-2023, and in March 2024 the BoJ stopped ETF buying altogether. The holdout (2024-2026) and any live challenge in 2026 have no BoJ flow at all. The pre-registration itself predicts a fade from 2021. If the mechanism is real, the counted holdout run should be about zero and fail the pass bar (avg R > 0 in the holdout), and nothing tradeable comes out. If the holdout comes out positive anyway, the me
- prior_monthend_hedge [calendar_flow] Melvin-Prins equity-hedge rebalancing flow at month-end on USDJPY (monthend_hedge): Design t 2.5 to 4.0 but negative in check - month-end fix flows faded after 2018 in every form tested; only the 11:00 UTC 3rd-last-weekday USD bid (M-3) survived.
- prior_nasdaq_intraday_momentum [intraday_momentum_index] Nasdaq intraday momentum (first half hour predicts last half hour, Gao et al.) and pre-holiday drift (index_anomalies E3/E4): E4a/E4b intraday momentum -0.12 R in design after 1 point slippage per fill; E3 pre-holiday weakly positive, below the bar. Index CFD intraday trades cost 7-14 bp round trip in 2012-2014; intraday index ideas are cost-dead in the design years.
- prior_gotobi_holiday_calendar [fix_flow] Gotobi dates shifted off Japanese public holidays (gotobi_calendar): Holiday-adjusted calendar measured at design +0.143 R vs +0.144 R for the simple weekend rule - no gain, not adopted. Day-before-Japan-holiday and England bank holiday day types are in the flow atlas.
- prior_tokyo_fix_long [fix_flow] Long into the 09:55 JST Tokyo fix (patterns_usdjpy P1), all day types: Cost-dominated on every day type - gotobi about 0 R, other weekdays -0.07 to -0.09 R in design and negative in check. Only the post-fix SHORT on gotobi days (sell 00:55 UTC, exit 06:00 UTC) pays; pre-fix longs, non-gotobi post-fix shorts and Tokyo-open variants are measured and dead.
- jpy_tokyo_open_contrarian_flow [liquidity_provision_tokyo_open] Tokyo-open contrarian flow: fade the New York session move in USDJPY and AUDJPY at 09:00 JST: rejected by critic: This is the same family as dead entries, with only a participant label added. Fading the previous session's move when the next session's participants arrive is prior_fx_session_rev: fading the Asia-session extreme at the London open found no reversal even on mid prices (base reversal variant mid-to-mid about -0.001 R) and lost after costs. Tokyo-hours fades on USDJPY have also lost: the gj-strat quiet-hours Bollinger fade (22:00-06:00 UTC) made -0.062 R (t -3.4) in design and -0.068 R in check. This cycle's own lesson puts session reversal in the dead pile. Charter rule 8 r
- usdjpy_tokyo_fix_holiday_shift [settlement_flow_tokyo_fix] Holiday-shifted Tokyo-fix demand: USDJPY rises into the 09:55 JST fix on the weekday before and after a Japanese market holiday: rejected by critic: The leg traded here has already been measured, and it does not pay even on the days where the claimed flow is strongest. The rationale cites the gotobi edge (+0.10 to +0.14 R, design t 3.2), but that edge is the post-fix SHORT (sell at 00:55 UTC, exit 06:00 UTC: design +0.144 R, check +0.112 R; gj-strat results/patterns_usdjpy). The same pre-declared grid also tested this hypothesis's leg: long into the 09:55 JST fix, stop 0.25 x ATR20, full costs (P1 fix-long). On gotobi days it made +0.013 / +0.007 / -0.016 R in design for 23:00 / 23:30 / 00:00 UTC entries (t 0.42 / 0.24
- gold_asia_session_physical_bid [intraday_seasonality_metal] Gold rises during Asian hours: physical demand executes in Asia, paper selling in London and New York: rejected by critic: Duplicate of prior_flow_atlas: the atlas scanned XAUUSD on the Tokyo clock (no DST) with 30-minute to 8-hour windows starting every half hour on all weekdays, including exactly 08:00-16:00 and 09:00-17:00 JST = 23:00-07:00 and 00:00-08:00 UTC; neither reached even the watch list (design |t| >= 3.5) on mid prices before costs, and the strongest Asian-hours gold slot (01:30-02:30 UTC, mid t 5.9) lost after the atlas's costs as a trade (design -0.044 R, check -0.060 R). Do not re-slice Asian-hours gold.; Where the atlas did find Asian-hours gold strength in design it did not p
- london_trend_day_ny_continuation [intraday_continuation_trend_day] Trend-day continuation: London open-drive carries into the New York session: Same-day continuation of London trend days into New York is not a durable FX flow. The trend-day signature (London range >= k x ATR20 and a close at the extreme by 12:00 UTC) gave EURUSD design +0.10 R (t 1.8) but check -0.09 R; pooled check over four markets was -0.002 R on 666 trades and walk-forward OOS was 0.001 R. GBPJPY was the only market with positive walk-forward and it died at 2x costs. Conditional intraday continuation now joins session reversal, box breakouts and fix follows in the dead pile: do not retry with other range or close-location thresholds, other exit hours, or other majors.
- prior_trade_research_2026_07 [htf_pullback_and_session] trade-research repo - 11 strategies (session CS momentum, ORB, D1 momentum, H4/M15 EMA pullbacks with/without ADX, London fail fade, MSNR zones, VWAP fade, H1 Donchian+ATR, XAUUSD HTF pullback): All NO-GO after FTMO-style costs, expectancy -0.03 to -0.13 R. Do not stack filters on rejected HTF pullback lines.
- prior_recent_winners [meta_rotation] Walk-forward "recent winners" rotation over ~500 signal streams; logistic filter on the box: Fails out of sample; selection noise dominates.
- prior_nasdaq_lead_lag [cross_asset_leadlag] Nikkei / Nasdaq lead-lag vs USDJPY, gap fills, NFP, Monday gap: Nothing after costs. Nasdaq turn-of-month weakly positive everywhere but below the bar.
- prior_round_numbers [price_level] Round-number fade and breakout: Nothing after costs.
- prior_flow_atlas [clock_calendar_scan] 600,912 clock x calendar x currency-strength mean tests: Three tradeable slots only - EURGBP month-end fix, USDJPY after US holiday, USD bid 11:00-12:00 UTC on the 3rd-last weekday (M-3). Any new clock/calendar idea must beat this scan's Bonferroni bar (design t >= 3.7).
- prior_fix_fades [fix_flow] London 4pm fix fade/follow, ECB fix, NY cut, gold fix, CNY fix, Tokyo fix month-start: Only the Tokyo fix on gotobi days (USDJPY) and the EURGBP month-end fix survived; the rest did not.
- prior_box_breakouts [session_breakout] Time-box breakouts at many clock times on 31 markets (London, Asian range, prev-day, inside bar, NR7, NY ORB, Frankfurt): Only the 05:00 IST USDJPY box works, best with a vol filter; everything else dies on 1-1.5 pip costs plus spread. Fade of the failed break (Version C) works only on USDJPY (+0.14R).
- prior_cot_positioning [positioning] CFTC positioning fades and follows, 8 markets: Fading crowds is flat in design; other variants lose after weekly costs.
- prior_eq_overnight_drift [overnight_drift] Index overnight drift at the European open (14 variants): Real before costs (about 0.9 bp per trade) but costs are about 3.3 bp.
- prior_ust_auction [event_treasury] USDJPY around month-end Treasury auctions (8 variants): The gain is the month-end USD effect (M-3), not an auction effect.
- prior_fx_value_mom [value_momentum] G8 FX value + momentum + carry combinations (8 variants): Value lost on the yen 2024-26; momentum lost at every horizon.
- prior_index_vol_timing [vol_timing] VRP / realised-vol scaled index exposure (18 variants): Cuts the worst day and drawdown but never beats buy-and-hold; safety, not edge.
- prior_cb_drift [event_central_bank] Follow or fade the decision-day move at 7 central banks (10 variants): No drift after the decision day; follow and fade are mirror images of zero.
- prior_fx_session_rev [intraday_reversal] Asia-session extreme reversal into London/NY (8 variants): No reversal and no momentum before costs; costs make every variant lose.
- prior_cross_zfade [mean_reversion_fx] Z-score fades on range-bound FX crosses (9 variants): 2-sigma moves kept running; stop hit on 43-58% of trades.
- prior_index_flows [calendar_flow_index] Option expiry, pension rebalancing, turn-of-month on indices (8 variants): Turn-of-month long when stocks beat bonds is the best near miss (design t 1.49); S&P barely confirms.
- prior_fx_rates [macro_rates] 2-year yield gap fair-value and momentum (10 variants): Yield momentum copies price momentum; fair-value fade only worked after 2018.
- prior_fx_carry [carry] G8 FX carry with trend and low-vol filters (9 variants): Carry earned its swap then gave it back in crash months (2015-08, 2020-03, 2024-08).
- prior_trend_follow [trend_following] Donchian / trend-gated breakouts on 13 markets, D1 and H4: FX trend is flat to negative even before costs; index and gold breakouts made money only from the bull market.
- prior_fomc_cycle [event_fed] Pre- and post-FOMC drift on Nasdaq and USD pairs (9 variants): Pre-meeting drift exists before costs but only since 2016; 2010-15 lost. Not tradeable after costs.
- prior_index_meanrev [mean_reversion_index] Index dip-buying (44 variants, Nasdaq/S&P/Nikkei): Only RSI(2)<5 above SMA200 on Nasdaq (MR6) survived two of three adversarial checks; weak, 4-5 trades/yr, flat 2018-23, knife-edge threshold. MR4 (buy after big down day, hold 5d) refuted - it was index drift. Random longs on a rising index pass the bar 2-8% of the time.

# Market facts
# Market facts (development years only: spreads 2022-23, profiles 2018-23)

| Symbol | Rows | Start | End | Median spread (pips) | ATR20 median / p10 / p90 (pips) | Cheapest hours (spread/range) | Busiest hours (range) | Monday gap (pips) | AC1 M5 / H1 / D1 |
|---|---|---|---|---|---|---|---|---|---|
| AUDCAD | 6,259,473 | 2009-12-31 | 2026-10-07 | 2.1 | 65.5 / 51.8 / 84.1 | 14,13,15,12 | 14,13,15,12 | 1.7 | -0.0659 / -0.0547 / -0.0088 |
| AUDCHF | 6,256,875 | 2009-12-31 | 2026-10-07 | 1.65 | 56.5 / 46.5 / 77.7 | 14,13,15,08 | 14,13,15,07 | 2.8 | -0.0639 / -0.0427 / -0.0352 |
| AUDJPY | 6,263,773 | 2009-12-31 | 2026-10-07 | 0.9 | 80.9 / 58.4 / 126.6 | 14,15,13,01 | 14,01,00,15 | 1.2 | -0.0463 / -0.0358 / -0.0192 |
| AUDNZD | 6,254,659 | 2009-12-31 | 2026-10-07 | 2.25 | 56.6 / 46.0 / 72.9 | 14,01,13,15 | 21,01,14,00 | 4.1 | -0.0944 / -0.0672 / 0.013 |
| AUDUSD | 6,243,035 | 2009-12-31 | 2026-10-07 | 1.1 | 65.5 / 44.9 / 92.0 | 14,13,15,12 | 14,13,15,01 | 0.6 | -0.0343 / -0.0317 / 0.0202 |
| CADCHF | 6,241,702 | 2009-12-31 | 2026-10-07 | 1.8 | 53.8 / 43.3 / 69.3 | 14,15,13,12 | 14,13,15,12 | 1.6 | -0.0584 / -0.0278 / -0.0395 |
| CADJPY | 6,263,323 | 2009-12-31 | 2026-10-07 | 1.3 | 75.9 / 53.0 / 126.7 | 14,15,13,12 | 14,13,15,12 | 1.2 | -0.0161 / -0.0096 / -0.0487 |
| CHFJPY | 6,249,993 | 2009-12-31 | 2026-10-07 | 2.0 | 77.2 / 55.6 / 155.5 | 14,13,08,07 | 14,13,08,07 | 4.6 | -0.0467 / -0.0347 / -0.0553 |
| EURAUD | 6,261,296 | 2009-12-31 | 2026-10-07 | 2.5 | 116.1 / 87.4 / 163.6 | 14,15,13,12 | 14,13,15,01 | 1.9 | -0.0496 / -0.043 / -0.0323 |
| EURCAD | 6,258,714 | 2009-12-31 | 2026-10-07 | 2.15 | 96.9 / 73.8 / 123.9 | 14,13,15,12 | 14,13,15,12 | 1.4 | -0.0441 / -0.0273 / -0.0646 |
| EURCHF | 6,237,881 | 2009-12-31 | 2026-10-07 | 1.15 | 48.3 / 37.7 / 74.8 | 14,08,13,15 | 14,07,08,13 | 1.4 | -0.0596 / -0.0494 / 0.0123 |
| EURGBP | 6,255,449 | 2009-12-31 | 2026-10-07 | 1.0 | 53.9 / 40.9 / 76.5 | 14,13,15,11 | 14,08,13,15 | 1.0 | -0.0637 / -0.0328 / -0.0042 |
| EURJPY | 6,262,757 | 2009-12-31 | 2026-10-07 | 1.1 | 94.0 / 63.5 / 164.4 | 14,13,15,07 | 14,13,07,08 | 2.0 | -0.0342 / -0.0109 / -0.0339 |
| EURNZD | 6,242,134 | 2009-12-31 | 2026-10-07 | 3.4 | 129.8 / 102.8 / 171.0 | 14,13,15,12 | 14,13,15,12 | 4.9 | -0.0482 / -0.0366 / -0.0711 |
| EURUSD | 6,259,225 | 2009-12-31 | 2026-10-09 | 0.35 | 75.5 / 50.6 / 105.6 | 14,13,12,15 | 14,13,12,15 | 0.3 | -0.0288 / -0.0184 / 0.0195 |
| GBPAUD | 6,251,598 | 2009-12-31 | 2026-10-07 | 3.3 | 146.1 / 113.9 / 188.1 | 14,15,13,08 | 14,13,15,08 | 4.0 | -0.0609 / -0.0475 / -0.0189 |
| GBPCAD | 6,250,199 | 2009-12-31 | 2026-10-07 | 3.35 | 128.2 / 100.3 / 167.3 | 14,13,15,12 | 14,13,15,12 | 3.8 | -0.0509 / -0.0418 / -0.0227 |
| GBPCHF | 6,251,082 | 2009-12-31 | 2026-10-07 | 2.05 | 91.1 / 71.0 / 121.0 | 14,08,13,15 | 14,08,13,07 | 3.8 | -0.0603 / -0.0402 / 0.0022 |
| GBPJPY | 6,261,360 | 2009-12-31 | 2026-10-07 | 2.15 | 133.5 / 97.8 / 198.9 | 14,15,13,07 | 14,08,13,07 | 3.9 | -0.033 / -0.0224 / 0.0296 |
| GBPNZD | 6,227,565 | 2009-12-31 | 2026-10-07 | 5.25 | 158.9 / 128.9 / 203.6 | 14,13,15,08 | 14,13,15,08 | 10.4 | -0.0619 / -0.0419 / -0.0474 |
| GBPUSD | 6,261,804 | 2009-12-31 | 2026-10-09 | 1.0 | 103.1 / 81.4 / 142.1 | 14,13,15,12 | 14,13,15,12 | 0.9 | -0.0337 / -0.0324 / 0.0535 |
| JPNIDXJPY | 4,116,635 | 2011-09-18 | 2026-10-07 | 7.16 | 421.3 / 261.0 / 581.7 | 00,01,14,23 | 00,01,14,23 | 30.2 | -0.0102 / -0.001 / -0.1344 |
| NZDCAD | 6,245,316 | 2009-12-31 | 2026-10-07 | 2.55 | 66.1 / 55.1 / 82.2 | 14,13,15,12 | 14,13,15,12 | 2.2 | -0.0626 / -0.0431 / -0.0086 |
| NZDCHF | 6,250,893 | 2009-12-31 | 2026-10-07 | 1.85 | 54.5 / 45.7 / 69.7 | 14,15,13,08 | 14,13,15,21 | 2.3 | -0.0608 / -0.0427 / -0.0548 |
| NZDJPY | 6,257,905 | 2009-12-31 | 2026-10-07 | 1.2 | 75.3 / 56.0 / 109.4 | 14,15,13,07 | 14,01,13,00 | 2.0 | -0.0396 / -0.0338 / -0.0111 |
| NZDUSD | 6,244,813 | 2009-12-31 | 2026-10-07 | 1.25 | 62.4 / 48.7 / 83.6 | 14,13,15,12 | 14,13,15,12 | 1.0 | -0.03 / -0.0283 / 0.0136 |
| USATECHIDXUSD | 4,253,659 | 2011-09-18 | 2026-10-07 | 3.45 | 212.6 / 93.2 / 373.0 | 14,15,19,16 | 14,15,13,19 | 10.6 | -0.0058 / -0.0101 / -0.1156 |
| USDCAD | 6,251,673 | 2009-12-31 | 2026-10-07 | 1.3 | 83.2 / 63.8 / 108.0 | 14,13,15,12 | 14,13,15,12 | 0.6 | -0.03 / -0.0227 / -0.0184 |
| USDCHF | 6,234,988 | 2009-12-31 | 2026-10-07 | 1.0 | 61.1 / 48.8 / 89.8 | 14,13,15,12 | 14,13,15,12 | 0.9 | -0.0372 / -0.0315 / 0.0465 |
| USDJPY | 6,258,314 | 2009-12-31 | 2026-10-08 | 0.6 | 67.3 / 49.5 / 159.7 | 14,13,12,15 | 14,13,12,00 | 0.7 | -0.0142 / -0.0016 / -0.0144 |
| XAUUSD | 5,966,723 | 2009-12-31 | 2026-10-07 | 33.85 | 2247.6 / 1146.2 / 3072.4 | 13,14,12,15 | 13,14,12,15 | 53.0 | -0.0306 / -0.0183 / 0.0322 |

Hours are UTC. Cost ratio = median spread / mean hourly range; below 0.05 is cheap, above 0.15 is expensive.
AC1 = lag-1 autocorrelation of log returns (negative = short-term mean reversion).


Review each hypothesis. Approve only what deserves compute.

# Prior research reports (already measured; do not re-test without a different mechanism)

112 reports. Read any of them with the Read tool, or grep `reference/gj-strat/results` for a keyword, before proposing. Each line: path | title | opening summary.

- `reference/gj-strat/results/adaptive/REPORT.md` | Adaptive rules on the USDJPY basket, 2010–2026 | Rules in run_adaptive.py (fixed before running).
- `reference/gj-strat/results/after_sl/EXCURSION.md` | After the box SL: run-on, come-back and a half-size-stop trade (USDJPY 2010–2026) | 3292 SL exits (1599 were the day's first trade, before 11:00). Median box (= 1R) 16.4 pips.
- `reference/gj-strat/results/after_sl/REPORT.md` | What USDJPY does after a box trade hits its SL (2010–2026) | 3292 stopped-out trades. Moves in R (1R = that trade's SL distance); + = keeps going the SL way, − = turns back.
- `reference/gj-strat/results/all_matrix/REPORT.md` | All strategies × all markets — last 3 years (from 2023-10-07) vs 2010–2023 | 411 tests. With t ≥ 2 in the last 3 years: 3 (about 10 expected by luck). Also t ≥ 2 and positive in 2010–2023: **1**.
- `reference/gj-strat/results/alpha_hunt/cb_drift/REPORT.md` | Central-bank decision-day drift in FX (cb_drift) | Script: `run_alpha_cb_drift.py` (every rule in its docstring, fixed before running). Costs in every R: $7/lot commission, 0.2 pip slippage per market/stop fill, swap (FRED rates +1%), real bid/ask fills.
- `reference/gj-strat/results/alpha_hunt/CHARTER.md` | Alpha hunt charter (every agent reads this first) | Repo: /home/user/gj-strat (Python, pandas + numpy, own backtester). Goal: find **any** real, tradeable edge (any style: carry, momentum, reversal, mean reversion, seasonality, event/flow, regime, relative value, volatility, cross-asset) that a retail prop trader can execute, ideally one that helps pass the Alpha Capital "Alpha Swing" $10k challenge faster (P1 +10%, P2 +5%, 10% static max loss, 5% daily loss, >= 3 tra
- `reference/gj-strat/results/alpha_hunt/cot_positioning/REPORT.md` | Alpha hunt: CFTC positioning (cot_positioning) | Script: `run_alpha_cot_positioning.py` (rules fixed in its docstring before the first run). Markets: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD (CME currency futures positioning mapped to spot) and XAUUSD (COMEX gold). CFTC Legacy Futures-Only reports 2005-2026, trades from 2010. Costs included everywhere (commission 7/lot, 0.2 pip slippage per stop fill, swap at FRED rates +1% markup; gold: run_all_matri
- `reference/gj-strat/results/alpha_hunt/cross_zfade/REPORT.md` | Alpha hunt: range-bound crosses, daily z-score fade (`cross_zfade`) | Rules, variants and the survival bar are in the docstring of `run_alpha_cross_zfade.py` (fixed before running). 5 crosses (AUDNZD, EURGBP, AUDCAD, NZDCAD, EURCHF excluding entries 2011-09-06..2015-01-15), signal = bid close of the 16:44 NY minute, market entry and non-stop exits at the 16:45 NY open, SL 1.5 x ATR20 (Z9 2.5), exit on the z-score crossing 0 or a 10 / 20 trading-day time stop. All costs included ($7/lot
- `reference/gj-strat/results/alpha_hunt/eq_overnight_drift/REPORT.md` | Alpha hunt: US equity-index overnight drift at the European open (`eq_overnight_drift`) | Rules, variants and the survival bar are in the docstring of `run_alpha_eq_overnight_drift.py` (fixed before running). Long at the 08:00 Berlin open (first live minute in 07:55-08:00), exit 09:00 Berlin (X1) or 09:25 NY (X2), stop 0.5 / 1.0 x ATR20, all costs. Periods: design from data start (European-open minutes live from about 2013) to 2017, check 2018-23, holdout 2024-26; last 3 years = 2023-10-08..2026-10-07.
- `reference/gj-strat/results/alpha_hunt/fomc_cycle/REPORT.md` | FOMC announcement premia (fomc_cycle) | Script: `run_alpha_fomc_cycle.py` (all rules in its docstring, fixed before running). Costs included everywhere (Nasdaq/Nikkei: run_all_matrix.net_r; S&P: 1 pt round trip + 0.25 pt stop slippage + 3%/yr financing; FX: $7/lot, 0.2 pip stop slippage, swap +1%).
- `reference/gj-strat/results/alpha_hunt/fx_carry/REPORT.md` | Alpha hunt: fx_carry (G8 cross-sectional FX carry with crash-risk switches, dollar carry) | Script: `run_alpha_fx_carry.py` (spec in its docstring, written before the run). Tables below are regenerated by `python run_alpha_fx_carry.py --report` into `REPORT_tables.md`; CSVs: `monthly_summary.csv`, `leg_summary.csv`, `swap_split.csv`, `monthly_R.csv`, `leg_results.csv` (every simulated leg), `legs_plan.csv`, `months.csv` (rates, ranking, VIX/FXVOL gates per month), `episodes.csv`, `worst_day.csv`, `daily_pct
- `reference/gj-strat/results/alpha_hunt/fx_carry/REPORT_tables.md` | Alpha hunt: fx_carry (G8 cross-sectional FX carry with crash-risk switches, dollar carry) | Spec fixed before running: see the docstring of `run_alpha_fx_carry.py` (rates = BIS policy rates, EUR = ECB deposit rate, dated <= signal day - 1; signal = last weekday of the month; entry/exit 07:00 UTC first weekday; SL 3 x ATR20, no TP; costs $7/lot, 0.2 pip slippage per stop fill, swap from FRED rates with 1.0%/yr markup (C10: 2.5%), so the carry income is inside R).
- `reference/gj-strat/results/alpha_hunt/fx_rates/REPORT.md` | Alpha hunt: FX under-reaction to relative 2-year yields (`fx_rates`) | Rules, variants and the survival bar are in the docstring of `run_alpha_fx_rates.py` (fixed before the first run). Markets: EURUSD GBPUSD AUDUSD USDJPY USDCAD (Y1-Y4, FV1-FV5) plus the 10 crosses among EUR JPY GBP CAD AUD for the cross-sectional Y5. All costs included ($7/lot, 0.2 pip slippage on stop fills, bid/ask fills, swap with 1% markup). Periods by entry day: design 2010-17, check 2018-23, holdout 2024-26; las
- `reference/gj-strat/results/alpha_hunt/fx_session_rev/REPORT.md` | Alpha hunt: fx_session_rev (conditional cross-session currency-strength reversal) | Spec, rules and the survival bar are in the docstring of `run_alpha_fx_session_rev.py` (fixed before running). Every weekday t: currency strength s_c from the 16:54 NY close of the previous weekday (A) to the 06:59 London close of t (B), all 28 pairs; trade the weakest/strongest pair at the 07:00 London open, SL 1 x ATR20, no TP, exit 16:05 London (X1) or 16:55 NY (X2). Reversal = buy the weakest, sell the strongest;
- `reference/gj-strat/results/alpha_hunt/fx_value_mom/REPORT_tables.md` | Alpha hunt: fx_value_mom (G8 FX value, cross-sectional momentum, carry-momentum-value combos) | Spec fixed before running: see the docstring of `run_alpha_fx_value_mom.py`.
- `reference/gj-strat/results/alpha_hunt/index_flows/REPORT.md` | Alpha hunt: index calendar flows - option expiry and month-end pension rebalancing (`index_flows`) | Rules, variants and the survival bar are in the docstring of `run_alpha_index_flows.py` (fixed before running). Swing trades of 3-7 trading days on the close, long and short, stops 1-2 x ATR20 (Nasdaq checked minute by minute on bid/ask; S&P on hourly bars), all costs included. Periods: design 2011-17 (data start), check 2018-23, holdout 2024-26; last 3 years = 2023-10-08..2026-10-07.
- `reference/gj-strat/results/alpha_hunt/index_meanrev/REPORT.md` | Alpha hunt: equity-index short-term reversal / dip-buying (`index_meanrev`) | Rules, variants and the survival bar are in the docstring of `run_alpha_index_meanrev.py` (fixed before running). Long-only on the close (MR11 = SELL control), 1-10 day holds, stops 1-2 x ATR20 checked minute by minute (S&P on hourly bars), all costs included. Periods: design 2010-17 (indices from data start), check 2018-23, holdout 2024-26; last 3 years = 2023-10-08..2026-10-07.
- `reference/gj-strat/results/alpha_hunt/index_vol_timing/REPORT.md` | Alpha hunt: volatility-managed index premium with VRP and VIX term-structure timing (`index_vol_timing`) | All rules, variants, the survival bar and the fixes are in the docstring of `run_alpha_index_vol_timing.py`. They were fixed before the first run. - **Strategy:** long-only index weights held close to close and rebalanced at the last close of each month (P5 and P6 also act daily). - **Costs:** half the signal-minute spread plus slippage on every weight change, plus 3%/yr financing on the notional. - **Periods:** desi
- `reference/gj-strat/results/alpha_hunt/index_vol_timing/tables.md` | tables (generated) | 
- `reference/gj-strat/results/alpha_hunt/prop/REPORT.md` | Alpha hunt -> prop: verified edges added to the Alpha Swing and Blueberry baskets | Rules, risk levels and acceptance are in the docstring of `run_alpha_prop.py` (fixed before running). All results after costs.
- `reference/gj-strat/results/alpha_hunt/REPORT.md` | Alpha hunt: final report | Date: 2026-10-11. Data: 2010-01 to 2026-10-07. All results are after costs (spread, commission, slippage, swap or financing).
- `reference/gj-strat/results/alpha_hunt/trend_follow/REPORT.md` | Alpha hunt: trend following (`trend_follow`) - monthly TSMOM + daily Turtle / chandelier breakouts | Rules, variants and the survival bar are in the docstring of `run_alpha_trend_follow.py` (fixed before running). 13 markets (7 FX majors, AUDJPY, EURJPY, gold, Nasdaq 100, Nikkei 225, S&P 500 hourly), all costs included (FX: $7/lot + 0.2 pip + swap with 1% markup; gold / indices: 3%/yr financing per night). Periods: design 2010-17 (indices from data start), check 2018-23, holdout 2024-26 (by signal day); last 3 years
- `reference/gj-strat/results/alpha_hunt/ust_auction/REPORT.md` | US Treasury auction concession cycle via USDJPY and gold (ust_auction) | Script: `run_alpha_ust_auction.py` (all rules in its docstring, fixed before running). Costs included everywhere (USDJPY: $7/lot, 0.2 pip stop slippage, swap +1%; XAUUSD: run_all_matrix.net_r with commission, slippage and 3%/yr financing).
- `reference/gj-strat/results/basket_last3y/REPORT.md` | Last 3 years (Oct 2023 – Oct 2026): USDJPY basket + month-end USD bid (M-3) | All costs ($7/lot, swap +1%, 0.2 pip slippage); one compounding account per plan. Rules in run_basket_last3y.py.
- `reference/gj-strat/results/blueberry_elite/REPORT.md` | Blueberry Instant Elite $2,500 — confirmed rules, money withdrawn | Rules and assumptions in run_blueberry_elite.py.
- `reference/gj-strat/results/box_dd_filters/LAST3Y.md` | Last 3 years (Oct 2023 – Oct 2026): vol-filtered USDJPY box + gotobi | All costs ($7/lot, swap +1%, 0.2 pip slippage); one compounding account from $10,000.
- `reference/gj-strat/results/box_dd_filters/MONTHLY_2026.md` | 2026 month by month — USDJPY vol-box, gotobi, fade | R per month (trades in brackets), by exit month; mix columns = % of account (simple sum). All costs. Jan–early Oct 2026.
- `reference/gj-strat/results/box_dd_filters/PROFITS.md` | Profits — vol-filtered USDJPY box + gotobi (2010–2026, all costs, from $10,000) | | plan | $10k became | per year % | max drawdown % | worst year % | best year % | losing years | last 3 years % |
- `reference/gj-strat/results/box_dd_filters/REPORT.md` | Drawdown filters for the USDJPY green box (2010–2026) | Filters and acceptance rule in run_box_dd_filters.py (fixed before running).
- `reference/gj-strat/results/box_gotobi_days/REPORT.md` | USDJPY green box on gotobi days only, 2010–2026 | Variants and pass rule in run_box_gotobi_days.py.
- `reference/gj-strat/results/box_indices/REPORT.md` | Box breakout on JPN225 and Nasdaq 100, 2011–2026 | Setups, costs and pass rule in run_box_indices.py (all fixed before running).
- `reference/gj-strat/results/box_meta/REPORT.md` | Box meta-labelling: walk-forward logistic filter on the USDJPY 1:9 box | Rules in run_box_meta.py (fixed before running). Out-of-sample 2014–2026 only.
- `reference/gj-strat/results/box_multi/REPORT.md` | Green box strategy on other pairs, 2010–2026 | Version B, SL 1 × box + spread, RR 9, BE 3R, 05:00 IST box, unchanged. All costs, 0.5% risk. Rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. USDJPY is included for reference (its rules came from 2024–2026).
- `reference/gj-strat/results/boxes_all/REPORT.md` | Your boxes on all 31 markets, 2010–2026 | Rules in run_boxes_all.py (fixed before running). 372 tests; about 2 survivors expected by luck.
- `reference/gj-strat/results/costs_gotobi/REPORT.md` | Costs and gotobi refinements (USDJPY 2010–2026) | Rules in run_costs_gotobi_vol.py.
- `reference/gj-strat/results/edge_hunt/REPORT.md` | Edge hunt — USDJPY clock scan, Nikkei/Nasdaq lead-lag, NFP | Tests and rules in run_edge_hunt.py (all fixed before running).
- `reference/gj-strat/results/fade_usdjpy/REPORT.md` | Version C (fade) on USDJPY, box-sized stop, 2010–2026 | Grid, costs and selection rule in run_fade_usdjpy.py (fixed before running).
- `reference/gj-strat/results/fix_times/REPORT.md` | Exact institutional times — 17 pre-declared tests, 2010–2026 | Rules in run_fix_times.py.
- `reference/gj-strat/results/flow_atlas/NOTES.md` | What the flow atlas found | 
- `reference/gj-strat/results/flow_atlas/REPORT.md` | Flow atlas: clock x calendar scan, 2010–2026 | Rules in run_flow_atlas.py (fixed before running).
- `reference/gj-strat/results/frankfurt_box/REPORT.md` | Frankfurt-hour range breakout, 2010–2026 | Rules in run_frankfurt_box.py.
- `reference/gj-strat/results/gap_cnyfix/REPORT.md` | Monday gap fill (28 FX + gold) and China CNY-fix minute (AUD, NZD), 2010–2026 | Rules in run_gap_cnyfix.py.
- `reference/gj-strat/results/gold_boxes/REPORT.md` | Your boxes on gold (and USDJPY), 2010–2026 | Rules in run_gold_boxes.py (fixed before running).
- `reference/gj-strat/results/gotobi_box_rr/REPORT.md` | Gotobi + box on gotobi days only, every RR (USDJPY 2010–2026) | Grid, costs and rules in run_gotobi_box_rr.py.
- `reference/gj-strat/results/gotobi_calendar/REPORT.md` | Gotobi short: Japanese calendar and entry time (USDJPY 2010–2026) | Rules and pass test in run_gotobi_calendar.py.
- `reference/gj-strat/results/gotobi_jpn_flip/REPORT.md` | Gotobi on JPN225, flipped (buy) vs original (sell), 2011–2026 | | Side | Trades | Win % | Avg R before slippage | Avg R net | t | Years + | Verdict |
- `reference/gj-strat/results/gotobi_rr/REPORT.md` | Gotobi short: RR exit vs time exit (USDJPY 2010–2026) | Rules and pass test in run_gotobi_rr.py.
- `reference/gj-strat/results/gotobi_tweaks/REPORT.md` | Gotobi short tweaks — USDJPY 2010–2026 | 40 pre-declared variants (see run_gotobi_tweaks.py). Holdout shown only for the design-best variant and the current rule.
- `reference/gj-strat/results/gotobi_usd_check/REPORT.md` | Gotobi placebo check on USD pairs without the yen, 2010–2026 | Rule and pass test in run_gotobi_usd_check.py.
- `reference/gj-strat/results/hot_rotation/REPORT.md` | Short-term alpha: recent winners next month (walk-forward) | Rules in run_hot_rotation.py (fixed before running). 488 trade streams.
- `reference/gj-strat/results/index_anomalies/REPORT.md` | Equity-index calendar anomalies (Nasdaq 100, S&P 500 replication) | Rules in run_index_anomalies.py (fixed before running).
- `reference/gj-strat/results/index_prop/REPORT.md` | Alpha Swing with the Nasdaq calendar trades | Rules in run_index_prop.py (fixed before running). Added: E1b turn of month (from last day).
- `reference/gj-strat/results/inside_oos/REPORT.md` | Inside-day breakout — out-of-sample on 26 new markets, 2010–2026 | Rules frozen from run_patterns_intraday.py (I3 inside). Costs and pass rule in run_inside_oos.py.
- `reference/gj-strat/results/instant_elite/REPORT.md` | Blueberry Funded Instant Elite (no daily limit, 10% trailing-lock max drawdown), $2,500 — vol-box + gotobi (USDJPY) | Rules as reported online (verify with Blueberry). Details and assumptions in run_instant_lite.py.
- `reference/gj-strat/results/instant_elite_static/REPORT.md` | Blueberry Funded Instant Elite (no daily limit, 10% static max drawdown), $2,500 — vol-box + gotobi (USDJPY) | Rules as reported online (verify with Blueberry). Details and assumptions in run_instant_lite.py.
- `reference/gj-strat/results/instant_lite/REPORT.md` | Blueberry Funded Instant Lite (2% daily, 4% trailing-lock max drawdown, 1% max risk after +4%), $2,500 — vol-box + gotobi (USDJPY) | Rules as reported online (verify with Blueberry). Details and assumptions in run_instant_lite.py.
- `reference/gj-strat/results/instant_payouts/REPORT.md` | Blueberry Instant Elite $2,500 — money actually withdrawn | 14-day payouts, $100 minimum, 80% split; rules and models in run_instant_payouts.py.
- `reference/gj-strat/results/jpy_edges_oos/REPORT.md` | USDJPY edges on unseen JPY markets — gotobi short and green box, 2010–2026 | Frozen rules, costs and pass rule in run_jpy_edges_oos.py. EURJPY / GBPJPY / USDJPY rows are reference only (not clean).
- `reference/gj-strat/results/m3_addon/REPORT.md` | Month-end USD bid (M-3) as a 4th prop leg | Rules and acceptance in run_m3_addon.py (fixed before running).
- `reference/gj-strat/results/m3_monthly/REPORT.md` | Month by month: M-3 and the full plans, 2011–2026 | Rules in run_m3_monthly.py. Fixed risk (no compounding).
- `reference/gj-strat/results/majors/REPORT.md` | Versions A and B on every major pair | Base settings: IST 05:00–05:59 box, SL 30 pips + spread, RR 4, BE 3R → +5 pips, 1% risk compounding from $10,000, each pair its own account. Dukascopy bid/ask, 2024-01-01 → 2026-10-07. 60/40 in-sample / out-of-sample split by tradable days. GBPJPY is the original pair, shown for reference only and not included in the pooled row.
- `reference/gj-strat/results/majors_box_sl/REPORT.md` | Versions A and B on every major pair — SL = 1 × box | Base settings: IST 05:00–05:59 box, SL = 1 × that day's 05:00–05:59 box + spread (BE offset scaled the same: 5/30 of the SL distance), RR 4, BE 3R → +5 pips, 1% risk compounding from $10,000, each pair its own account. Dukascopy bid/ask, 2024-01-01 → 2026-10-07. 60/40 in-sample / out-of-sample split by tradable days. GBPJPY is the original pair, shown for reference only and not included in the pooled row.
- `reference/gj-strat/results/majors_wide_sl_smoke/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 2 pairs: RR 1.5–10 × BE | 138 setups per pair, 276 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/AUDCAD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/AUDCHF/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/AUDNZD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/CADCHF/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/EURAUD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/EURCAD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/EURCHF/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/EURGBP/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/EURNZD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/GBPAUD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/GBPCAD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/GBPCHF/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/GBPNZD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/NZDCAD/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/pairs/NZDCHF/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 1 pairs: RR 1.5–10 × BE | 184 setups per pair, 184 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/minors_grid/REPORT.md` | Version B (SL 1 × box, 05:00 IST) on 15 pairs: RR 1.5–10 × BE | 184 setups per pair, 2760 in total. $7/lot, swap (+1% markup), 0.2 pip slippage. 2024–2026 split 60/40 into design / check. With this many tries, judge by the check columns and by how many pairs agree.
- `reference/gj-strat/results/monthend_hedge/REPORT.md` | Month-end hedge rebalancing on USDJPY (Nasdaq vs JPN225 signal), 2011–2026 | Rules, variants and selection in run_monthend_hedge.py (fixed before running).
- `reference/gj-strat/results/monthend_t2/REPORT.md` | Month-end T+2 USD bid (11:00–12:00 UTC = 16:30–17:30 IST) | Rules and predictions in run_monthend_t2.py (fixed before running).
- `reference/gj-strat/results/patterns_eurjpy/REPORT.md` | Pattern search — EURJPY 2010–2026 (beyond the box breakout) | 36 pre-declared setups in 4 families (see run_patterns.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) is shown only for survivors.
- `reference/gj-strat/results/patterns_eurusd/REPORT.md` | Pattern search — EURUSD 2010–2026 (beyond the box breakout) | 36 pre-declared setups in 4 families (see run_patterns.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) is shown only for survivors.
- `reference/gj-strat/results/patterns_flow/REPORT.md` | Flow / session pattern search — 5 pairs, 2010–2026 | 12 pre-declared setups per pair, 60 tests (see run_patterns_flow.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) only for survivors.
- `reference/gj-strat/results/patterns_gbpjpy/REPORT.md` | Pattern search — GBPJPY 2010–2026 (beyond the box breakout) | 36 pre-declared setups in 4 families (see run_patterns.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) is shown only for survivors.
- `reference/gj-strat/results/patterns_gbpusd/REPORT.md` | Pattern search — GBPUSD 2010–2026 (beyond the box breakout) | 36 pre-declared setups in 4 families (see run_patterns.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) is shown only for survivors.
- `reference/gj-strat/results/patterns_intraday/REPORT.md` | Intraday pattern search — USDJPY, EURJPY, GBPJPY, EURUSD, GBPUSD, 2010–2026 | 20 pre-declared setups per market, 100 tests (see run_patterns_intraday.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) only for survivors.
- `reference/gj-strat/results/patterns_usdjpy/REPORT.md` | Pattern search — USDJPY 2010–2026 (beyond the box breakout) | 36 pre-declared setups in 4 families (see run_patterns.py). Costs: $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill. Survival rule fixed before running: design (2010–2017) avg R > 0 with t ≥ 2 AND check (2018–2023) avg R > 0. Holdout (2024–2026) is shown only for survivors.
- `reference/gj-strat/results/prop_alpha_swing/REPORT.md` | Alpha Capital — Alpha Swing challenge with vol-box + gotobi (USDJPY) | Rules (as reported; verify): P1 +10%, P2 +5%, 10% static max loss, 5% daily, ≥3 days per phase. Details in run_prop_alpha_swing.py.
- `reference/gj-strat/results/prop_dynamic/FAIR_COMPARISON.md` | FAIR_COMPARISON | 
- `reference/gj-strat/results/prop_dynamic/REPORT.md` | Prop challenge: dynamic risk — USDJPY Version B | Same rules as `results/prop_sim` (P1 +8%, P2 +6%, static 10%, daily 4%, ≥3 days, costs + 0.2 pip slippage). Schemes fixed before any result (see run_prop_dynamic.py).
- `reference/gj-strat/results/prop_ej/REPORT.md` | Prop challenge — adding EURJPY gotobi to USDJPY box + gotobi | Correlation of USDJPY and EURJPY gotobi results on the same days: 0.79. Mixes fixed before running; rules and costs in run_prop_ej.py.
- `reference/gj-strat/results/prop_fade/REPORT.md` | Prop challenge — USDJPY box vs fade vs both, with gotobi | Trades: box 4556, fade 1672, gotobi 1192. Correlation of daily box and fade results: 0.12. Mixes fixed before running; rules and costs in run_prop_fade.py.
- `reference/gj-strat/results/prop_portfolio/REPORT.md` | Prop challenge — USDJPY box breakout + gotobi Tokyo-fix short | Challenges started on every trading day 2010-01 to 2025-10 (P1 +8%, P2 +6%, static 10%, daily 4%, ≥3 days). All costs. Risk mixes fixed before running.
- `reference/gj-strat/results/prop_risk_rules/REPORT.md` | Alpha Swing: risk rules on the current basket | Rules in run_prop_risk_rules.py (fixed before running).
- `reference/gj-strat/results/prop_sim/REPORT.md` | Prop challenge pass rate — USDJPY Version B (SL 1 × box, RR 9, BE 3R) | Rules: Phase 1 +8%, Phase 2 +6%, static 10% max drawdown, 4% daily drawdown (day ends 17:00 New York), at least 3 trading days per phase, no time limit, weekend holding allowed. Trades net of $7/lot, swap (+1% markup) and 0.2 pip slippage per stop fill. One challenge started on every trading day since 2010; closed-trade balance only.
- `reference/gj-strat/results/prop_speed/REPORT.md` | Fastest / cheapest route to a funded account (USDJPY box + gotobi) | Fee $100 per attempt; failed attempts restart at once. Rules in run_prop_speed.py.
- `reference/gj-strat/results/REPORT.md` | GBPJPY 05:00–06:00 IST range breakout — backtest report | *Data:* Dukascopy GBPJPY 1-minute BID + ASK candles; USDJPY 1-minute BID for pip value. *Period:* 2024-01-02 → 2026-10-07 (IST trading days), 707 tradable days. *In-sample:* 2024-01-02 → 2025-08-28 (424 days). *Out-of-sample:* 2025-08-29 → 2026-10-07 (283 days). *Costs:* real bid/ask from the data (median entry spread 2.1 pips, 90th pct 2.7), commission $0/lot, no swap, lots rounded down to 0.01. Start $10,000, 1% ri
- `reference/gj-strat/results/round_numbers/REPORT.md` | Round numbers (Osler): fade at the big figure / breakout beyond it | Rules in run_round_numbers.py (fixed before running).
- `reference/gj-strat/results/swing_basket/REPORT.md` | Alpha Swing: adding the fade to vol-box + gotobi | Rules in run_swing_basket.py.
- `reference/gj-strat/results/usdjpy_boxfilter/REPORT.md` | USDJPY Version B, RR 9, BE 3R, SL = 1 × box: relative small-box filter | Protocol fixed before any result: skip the day if its box < k × median box of the previous 20 tradable days; k = none, 0.3, 0.5, 0.7. All numbers after $7/lot, swap (+1% markup) and 0.2 pip slippage per stop fill. Pick on 2010–2017 by avg R; check on 2018–2026.
- `reference/gj-strat/results/usdjpy_grid/REPORT.md` | USDJPY, SL = 1 × box: Versions A and B, RR 2–10, BE off / 3R | Protocol fixed before any result: 32 combos, $7/lot + swap (+1% markup). Pick ONE on 2010–2017 by avg R after 0.2 pip slippage per stop fill; check it on 2018–2026.
- `reference/gj-strat/results/usdjpy_history/REPORT.md` | USDJPY 2010–2026: Versions A and B, SL = 1 × box, with swap | Rules: IST 05:00–05:59 box, SL = that day's box + spread, TP 4R, BE at 3R → entry + 5/30 of the SL distance, 1% risk compounding from $10,000, Dukascopy bid/ask. 4082 tradable days; 292 skipped (no data or a tick-less minute in the box).
- `reference/gj-strat/results/usdjpy_history_comm7/REPORT.md` | USDJPY 2010–2026: Versions A and B, SL = 1 × box, with swap, $7/lot commission | Rules: IST 05:00–05:59 box, SL = that day's box + spread, TP 4R, BE at 3R → entry + 5/30 of the SL distance, 1% risk compounding from $10,000, Dukascopy bid/ask. 4082 tradable days; 292 skipped (no data or a tick-less minute in the box).
- `reference/gj-strat/results/usdjpy_last3y/REPORT.md` | USDJPY approved strategy — last 3 years (2023-10-09 → 2026-10-07) | Version B, SL = 1 × box, RR 9, BE 3R, 05:00 IST box. $7/lot, swap (+1% markup), 0.2 pip slippage per stop fill.
- `reference/gj-strat/results/usdjpy_sl/REPORT.md` | USDJPY Version A: wider stop-loss test ($7/lot, swap +1% markup) | Protocol fixed before any result: candidates SL = 1, 1.5, 2 × the day's box (+ spread), TP 4R and BE 3R unchanged. Pick ONE on 2010–2017 by avg R after 0.2 pip slippage per stop fill. Check it on 2018–2026.
- `reference/gj-strat/results/verdict.md` | verdict | 
- `reference/gj-strat/results/version_comparison/REPORT.md` | Version comparison — breakout (A, B), fade (C), weekly bias (W) | Base settings RR 4, SL 30 pips + spread, BE 3R → +5 pips. 707 days 2024-01-02 → 2026-10-07; in-sample to 2025-08-28, out-of-sample from 2025-08-29.
- `reference/gj-strat/results/window_scan/REPORT.md` | USDJPY: which time of day does the box breakout work? | 1-hour box at every hour 00:00–23:00 IST × order window 1–7 h = 168 windows, Version B (SL 1 × box, RR 9, BE 3R), $7/lot + swap + 0.2 pip slippage. Pick on 2010–2017 by avg R, check on 2018–2026. With 168 tries, a best design t-stat near 3 is expected from luck alone.
- `reference/gj-strat/green/BASKET.md` | USDJPY basket: 4 trades (all times IST) | 
- `reference/gj-strat/green/STRATEGY.md` | ✅ USDJPY Tokyo-open box breakout — Version B (approved) | 
- `reference/trade-research/docs/STATUS.md` | Research status | Source data: Dukascopy BID OHLC in `data/parquet` (local only). Detailed run artifacts stay in `reports/` (local only).


# Output
Write a JSON object matching this schema to runs/cycles/cycle_0007/critic_review.json (one review per hypothesis, same slugs).

```json
{
 "type": "object",
 "properties": {
  "reviews": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "slug": {
      "type": "string"
     },
     "verdict": {
      "type": "string",
      "enum": [
       "approve",
       "revise",
       "reject"
      ]
     },
     "reasons": {
      "type": "array",
      "items": {
       "type": "string"
      }
     },
     "revisions": {
      "type": "string"
     },
     "overfit_risk": {
      "type": "string",
      "enum": [
       "low",
       "medium",
       "high"
      ]
     },
     "cost_risk": {
      "type": "string",
      "enum": [
       "low",
       "medium",
       "high"
      ]
     },
     "duplicate_of": {
      "type": [
       "string",
       "null"
      ]
     },
     "notes_for_builder": {
      "type": "string"
     }
    },
    "required": [
     "slug",
     "verdict",
     "reasons",
     "revisions",
     "overfit_risk",
     "cost_risk",
     "duplicate_of",
     "notes_for_builder"
    ],
    "additionalProperties": false
   }
  }
 },
 "required": [
  "reviews"
 ],
 "additionalProperties": false
}
```
