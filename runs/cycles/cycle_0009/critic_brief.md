# Programme charter (shared by every role)

Goal (set by the user on 2026-10-14): strategies, or a basket of them with the parked USDJPY legs, that pass the
Alpha Capital "Alpha Swing" $10k challenge (phase 1 +10%, phase 2 +5%, 10% static max loss, 5% daily loss,
>= 3 trading days per phase, no time limit, 1:30 FX leverage; indices and metals allowed) WITHIN 60 DAYS in at
least half of the challenge starts since 2018, losing the account within 60 days in at most 15%. Slower edges are
recorded, not traded. What that needs: about +15.5% net inside two months under the loss limits, so roughly 8%
a month at about 4% monthly volatility (monthly Sharpe near 2). The parked basket (vol-box, vol-gotobi, fade,
month-end USD bid; runs/basket) earns 3% a month at 8% volatility, monthly Sharpe 0.4, and passes within 60 days
about 1 time in 4. So a new strategy must bring, after costs, avg R x sqrt(trades per month) of about 0.7 or more
(monthly Sharpe 1; design t of about 10 over eight years) and be weakly correlated with the parked legs; four such
strategies would reach the target. Nothing measured here or in the 171 earlier tests is close (the best, the gotobi
short, scores 0.3). Many trades a month at a modest R or a few at a large R both qualify; costs cap the first and
rarity caps the second. An honest negative is a valuable result; a flattering backtest that fails live is the worst
outcome. Nothing here is a guarantee; the output is a probability.

Data: Dukascopy 1-minute bid and ask bars, 2010 to 2026, for 28 FX pairs, XAUUSD, XAGUSD and index CFDs
(US500, US100, US30, GER40, UK100, JP225; indices start 2011-2013 and are patchy before 2014). Resampled
timeframes M3, M5, M15, M30, H1, H2, H3, H4, H8, D1, W1 (daily and weekly bars close 17:00 New York).
Spreads are raw Dukascopy spreads; costs on top: $7 per lot round turn (FX), 0.2 pip slippage on market
and stop fills, swap from real policy rates with a 1% markup. Every result is after costs.

External inputs (data/external, described in its README): an economic calendar with consensus and actual
values and standardised surprises (2010 to 2025-04), CFTC positioning by trader group for 7 currencies, the
USD index, S&P 500, Nasdaq-100 and gold (2010 to 2026), CBOE implied-volatility indices (VIX, VXN, EVZ,
GVZ, OVX), and Japanese retail positioning from TFX Click 365: tfx_daily (daily open interest, volume and settlement
per pair since 2005, a direction-free retail-flow proxy: open interest rising on a down day is dip-buying; usable in
the design years) and tfx (weekly long and short positions for 33 pairs, 2022-11 on; holdout-era conditioning only).
Every row is usable only from its release time (ts_avail). These are new dimensions: the price, clock and
calendar-date dimensions of the store have been measured exhaustively.

Time splits: design 2010-2017, check 2018-2023, holdout 2024-2026. The holdout is locked. Nothing in
stages A-C sees a holdout bar. A strategy reaches the holdout once, when promoted, and that run is counted.

Protocol:
1. Every hypothesis is pre-registered: economic mechanism, exact rules, parameter ranges, the primary
   market, expected design t and average R, expected trades per month (the speed bar: avg R x sqrt(trades per
   month) >= 0.7 after costs, or a stated path to it in a basket), minimum trades, and a kill rule, all written
   before any run.
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
  "slug": "fx_surprise_against_crowd",
  "title": "Positioning-amplified surprise continuation: trade in the direction of a high-impact scheduled data surprise 15 minutes after the release, only when CFTC leveraged funds are crowded on the other side of that surprise, holding to the New York afternoon of the release day or of the next weekday; with surprise-agrees-with-the-crowd and uncrowded control arms that trade the same surprises",
  "family": "event_positioning_unwind_fx",
  "rationale": "Mechanism: a forced unwind, not an information drift. Who trades: leveraged funds (the CFTC Traders in Financial Futures 'leveraged funds' group: hedge funds and CTAs) holding a crowded directional book in a currency future, measured as the net position as a share of open interest ranked against its own last 52 weekly readings, known from the Friday 15:30 New York release. Why they must: a scheduled high-impact release that surprises against that book moves the price against them within the first minutes (Andersen, Bollerslev, Diebold and Vega 2003: the conditional mean reaction is complete in about five minutes, which is why this test does not trade the jump itself); risk limits, stop-losses, VaR and end-of-day marks then force position cuts, and large funds execute those cuts over hours (order splitting, waiting for liquidity), so forced flow keeps arriving after the first reaction. Evans and Lyons (2005, 2008) show that most of the exchange-rate response to macro news is transmitted through induced order flow spread over hours and days rather than through the instantaneous repricing, and Brunnermeier, Nagel and Pedersen (2008) show that crowded speculator positions in the CFTC data unwind abruptly and produce the negative skew of currency returns. Who is on the other side: dealers who warehouse the flow intraday and slower real money. Why it shows up in price only in that state: when positioning is neutral, or when the surprise agrees with the crowd, there is no forced seller or buyer after the first minutes, so the post-15-minute drift should be near zero; the hypothesis is the asymmetry between the arms, not the sign of post-release drift as such. What has been measured before: edge_hunt tested NFP follow and fade on USDJPY, EURUSD and gold (92 events, 1 to 3 hour holds, direction read from the first move, no surprise size and no positioning) and found nothing; cot_positioning tested eight standalone positioning rules (crowding fades, hedging pressure, one-week flow follow and reversal) and found nothing after weekly costs; cb_drift and fomc_cycle measured decision-day drift unconditionally; the news-inclusive arm of fx_liquidity_withdrawal_reversal measured fades of one-hour price moves on USDJPY with a two-hour exit, not surprise-signed trades. None conditioned a post-release trade on positioning, and the external README names positioning as a conditioning state. Costs: EURUSD median spread 0.35 pips, perhaps 0.6 to 1.0 pips in the quarter hour after a release; with 0.2 pips of slippage on each side and the 7 dollar commission (about 0.7 pips) the round trip is about 1.5 to 2.5 pips against a 1.0 x ATR20 stop of 50 to 105 pips (median 75), so about 0.02 to 0.03 R; the other five markets cost 0.03 to 0.05 R. Counts from the calendar and COT tables only (design 2010-2017, EURUSD, no price outcomes): qualifying releases with |dz| >= 1.0 split against / with / neutral as 101 / 113 / 235 at crowd_q 0.8 and 69 / 77 / 303 at 0.9; with |dz| >= 1.5: 49 / 51 / 127 and 32 / 33 / 162; GBPUSD 133 / 149 / 321, AUDUSD 137 / 132 / 260, USDJPY 76 / 81 / 240, USDCAD 136 / 126 / 318 at z 1.0 and q 0.8; about 414 release days a year-set on EURUSD, 1.25 qualifying releases per release day. Expected: the against arm +0.12 R (about 9 pips of drift on a 75-pip stop) with trade-level design t about 1.3 on about 100 trades at crowd_q 0.8 and z_min 1.0, the with arm and the neutral arm within +-0.05 R of zero after costs; P(design t >= 2 | effect real at +0.12 R) about 0.3, so a kill is weak evidence and a pass is strong evidence. Speed: about 1 trade a month per market in the against arm, about 5 a month pooled over the six markets but clustered on US release days, so the speed score at expectation is 0.12 x sqrt(5) = 0.27: this is an edge-recording test, it reaches the challenge speed bar only if the against arm earns +0.3 R or more, and even a below-bar positive result is useful as a timing filter on the parked USDJPY legs around releases. Human execution: wait for the release, read actual against consensus on the calendar, check the crowd state from the Friday COT report, place one market order 15 minutes after the release with a 1 x ATR20 stop, exit 20:30 UTC the same day or the next weekday; two to six orders a month across the pairs. Most likely failure: the unwind is finished inside the first 15 minutes (ABDV) or the dealers lean against it so the drift is below 0.05 R, or crowdedness measured weekly is too stale to identify the book that is hurt on the day.",
  "markets": [
   "EURUSD",
   "GBPUSD",
   "AUDUSD",
   "NZDUSD",
   "USDJPY",
   "USDCAD"
  ],
  "aux_markets": [],
  "ext_series": [
   "calendar",
   "cot"
  ],
  "timeframe": "M15",
  "rules": "All times UTC. M15 bars, stamped at the bar open and sparse; locate every time by timestamp (m.ts for opens, m.close_times() for closes), never by bar count. Loop over releases (a few hundred per market), vectorise everything else.\n\nSYMBOL CONSTANTS: base = first three letters of m.sym, quote = last three. The COT currency is the non-USD one (EUR, GBP, AUD, NZD, JPY, CAD); cot_sign = +1 when it is the base (EURUSD, GBPUSD, AUDUSD, NZDUSD) and -1 when it is the quote (USDJPY, USDCAD). Raise for any other symbol.\n\nCALENDAR EVENT SET: e = F.ext_series(m, 'calendar'); keep rows with impact == 'high', time_source == 'scraped' (rows with a typical or unknown release minute are useless for a 15-minute entry), finite surprise_z, currency in (base, quote), and an event name that does NOT contain (case-insensitive) any of: 'Crude Oil', 'Natural Gas', 'Inventories', 'Unemployment Claims', 'TIC Long', 'Votes', 'Asset Purchase Facility'. Use F.ext_subset(m, 'calendar', mask). Row direction for the pair: s_row = sign(surprise_z) x inv x side, where inv = -1 if the event name contains 'Unemployment Rate', 'Unemployment Change', 'Claimant Count', 'Net Borrowing' or 'Jobless' (a higher-than-forecast number is bad for that currency) and +1 otherwise; side = +1 if currency == base, -1 if currency == quote. Row weight w_row = |surprise_z|. Rows sharing one ts_avail (the same release minute) are merged into one release: dz = sum over those rows of s_row x w_row. A release qualifies when |dz| >= z_min; its trade direction dir = sign(dz) (+1 long the pair, -1 short). Process releases in ts_avail order.\n\nPOSITIONING STATE: c = F.ext_subset(m, 'cot', market == COT currency), rows in ts_avail order (ts_avail = 19:30 or 20:30 UTC on the Friday release). For row r with at least rank_weeks (52) rows up to and including r: rank_r = (number of those 52 rows whose spec_net_oi <= spec_net_oi_r) / 52, in (0, 1]; earlier rows have no rank. For a release at time T use the last COT row with ts_avail <= T; skip the release in every arm if that row has no rank. state = +1 if rank >= crowd_q, -1 if rank <= 1 - crowd_q, 0 otherwise. crowd_pair_dir = cot_sign x state: +1 means the leveraged funds are crowded long the pair, -1 crowded short, 0 not crowded.\n\nARMS (p['arm']): 'against': crowd_pair_dir != 0 and dir == -crowd_pair_dir (the surprise hits the crowded book); 'with': crowd_pair_dir != 0 and dir == crowd_pair_dir (the surprise agrees with the book); 'neutral': crowd_pair_dir == 0. Every arm trades in the surprise direction dir, so the first reaction, the costs and the event set are identical across arms and only the positioning state differs. Raise ValueError on any other arm value.\n\nENTRY: T = ts_avail of the release. sig = the first bar whose close time >= T + delay_min minutes (delay_min 15, so for a release on the quarter hour the bar that contains the release is the signal bar and the fill is 15 minutes after the release). Skip the release if sig >= m.n - 1, if close_times[sig] - T > max_delay_min (60) minutes (data gap), if the UTC date of bar sig differs from the UTC date of T, or if ATR20[sig] is not finite or <= 0. Market order at the next open: entry_long[sig] = True for dir +1, entry_short[sig] = True for dir -1; entry_type[sig] = 0; valid_bars[sig] = 1; the fill is at the open of bar sig + 1 (ask for longs, bid for shorts, plus slippage). One position at a time: the executor ignores an entry while a position is open, so a second qualifying release inside an open hold is not traded.\n\nSTOP: daily = F.daily_bars(m); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), the mean daily range of the previous 20 trading days, known at the day start; read at sig. sl_dist[sig] = sl_atr x ATR20[sig] (sl_atr 1.0, price units, > 0). tp_dist NaN (no target), max_bars 0.\n\nEXIT: exit date E = the UTC date of T for hold 'd0'; for hold 'd1' the next weekday (Monday to Friday) after the UTC date of T (a Friday release exits on Monday). target = E at exit_utc (20:30, i.e. 16:30 New York in daylight time, 15:30 in winter, well before the Friday close). xi = F.first_bar_at_or_after(m, E, 20, 30); if xi < m.n and xi > sig + 1: exit_long[xi - 1] = exit_short[xi - 1] = True (the position closes at the open of the first bar at or after the target). Causal fallback: for each signalled release k, set exit_long and exit_short True on every bar j with m.ts[j] >= target_k and j <= sig_(k+1) (the signal bar of the next signalled release, or m.n - 1 for the last one), so a missing target bar closes the position at the first bar after the gap and never carries it into the next release's trade; a marker on sig_(k+1) acts at the open of the next fill bar, where the executor checks only the stop, so the new trade is untouched. Leftover guard: exit_long[sig_k] = exit_short[sig_k] = True. Markers with no open position are ignored by the executor. No other exits, no other filters.\n\nPARAMETERS (every one read from p): arm (grid 'against', 'with', 'neutral'), crowd_q (grid 0.8, 0.9), z_min (grid 1.0, 1.5), hold (grid 'd0', 'd1'); fixed sl_atr 1.0, delay_min 15, max_delay_min 60, exit_utc '20:30', atr_n 20, rank_weeks 52. Module GRID = the full 24 cells so the checker exercises every value. Spec grids: stage A on EURUSD runs all 24 cells (the 'with' and 'neutral' cells are control arms and run only there); stages B, C, the walk-forward and any holdout run arm 'against' only (crowd_q x z_min x hold, 8 cells). The Director sets specs/auto/fx_surprise_against_crowd.json after the review step so that stage_a.grid holds the 24 cells and grid holds arm = against only.\n\nEXPECTED COUNTS (EURUSD design 2010-2017, from the calendar and COT tables, a check for the Builder and the checker): against / with / neutral about 101 / 113 / 235 releases at crowd_q 0.8 and z_min 1.0 before data-gap and overlap skips (fewer trades than releases where a second release falls inside an open hold); 69 / 77 / 303 at crowd_q 0.9; 49 / 51 / 127 at z_min 1.5 and crowd_q 0.8. A count far from these means the event set, the sign mapping or the rank is wrong. The calendar covers 2010-01 to 2025-04, so the check period is complete and the holdout is partial (noted for any promotion).\n\nREPORTING (from the trades; all 24 stage A rows read from the trials table, stage 'A'): per cell the number of trades, avg R, trade-level t, release-date-clustered t (R averaged per UTC release date, then t over dates), mean fill spread in pips and as a share of the stop, by-year avg R, for design and for check; for the chosen against cell: the matching with and neutral cells (same crowd_q, z_min, hold), avg R split by news side (base-currency releases against quote-currency releases) and by event group (employment: Non-Farm, Employment Change, Claimant Count, Unemployment Rate, ADP; inflation: CPI, PPI, earnings; activity: PMI, ISM, retail sales, GDP, production, confidence, housing, trade; rates: rate decisions), the avg R after dropping the best ceil(N/10) release dates, and the per-year against-minus-with and against-minus-neutral differences in design and check.",
  "params": {
   "arm": "against",
   "crowd_q": 0.8,
   "z_min": 1.0,
   "hold": "d1",
   "sl_atr": 1.0,
   "delay_min": 15,
   "max_delay_min": 60,
   "exit_utc": "20:30",
   "atr_n": 20,
   "rank_weeks": 52
  },
  "grid": {
   "arm": [
    "against",
    "with",
    "neutral"
   ],
   "crowd_q": [
    0.8,
    0.9
   ],
   "z_min": [
    1.0,
    1.5
   ],
   "hold": [
    "d0",
    "d1"
   ]
  },
  "stage_a_market": "EURUSD",
  "pre_registered": {
   "expected_design_t_min": 1.3,
   "expected_avg_r": 0.12,
   "min_trades_design_per_market": 40,
   "expected_trades_per_month": 1.0,
   "kill_if": "(1) Hypothesis-cell floor on EURUSD, applied by the Director from all 24 stage A rows in the trials table (stage 'A') even if the pipeline reports a candidate, because the automatic floor ranks every cell and a control cell can clear it: among the 12 'against' cells with at least 40 design trades, the chosen cell is the one with the highest trade-level design t (the pipeline's own ranking); it must have design avg R > 0 and trade-level t >= 1; if the automatic floor is cleared only by a 'with' or 'neutral' cell, the B/C output is ignored and the hypothesis is scrapped under this rule. (2) Asymmetry, the test of the mechanism: at the chosen cell, design avg R(against) minus design avg R(the 'with' cell with the same crowd_q, z_min and hold) must be >= +0.08 R, and design avg R(against) minus design avg R(the matching 'neutral' cell) must be >= +0.05 R; both differences must be > 0 in check (the stage A backtests span design and check). If the with or neutral arms earn as much as the against arm, the positioning mechanism is dead and whatever drift exists is unconditional post-release continuation; that is recorded as the lesson. Because the neutral arm's direction (the surprise sign) was fixed here before any run, a neutral arm that itself reaches design t >= 2 with check avg R > 0 may be carried forward once as a new pre-registered under-reaction hypothesis (counted trials), but never promoted from this run. (3) Breadth: at the chosen cell, design avg R > 0 on both base-currency-news and quote-currency-news trades, and design avg R > 0 after dropping the best ceil(N/10) release dates; an edge carried by one event type or one year is an episode. (4) Regime: at least 4 of the 8 design years positive at the chosen cell (2010 is thin because surprise_z needs eight earlier surprises per event). (5) Replication: at the chosen cell read from the stage B trials table, the pooled design avg R over the other five markets (equal-weighted over trades) must be > 0, and the pooled-check hard gate (avg R > 0 with >= 30 trades) and the walk-forward gate stand; a EURUSD-only result with the pooled others negative is scrapped as noise. (6) Costs: the hard gate (positive at 1.5x costs) stands; the fill spread as a share of the stop is reported; if the chosen cell is positive gross but negative net the lesson is that the post-release unwind is smaller than a 2-pip round trip. (7) Pass bar: design t >= 2 at the chosen cell with (2) satisfied in design and check; a positive result below that is recorded as below the bar and is not promoted. Speed: at about 1 trade a month per market and +0.12 R the score is 0.27 (about 5 trades a month pooled, correlated on US release days), so this is recorded as an edge unless the against arm earns +0.3 R or more; honest expectation +0.12 R, design t about 1.3, P(t >= 2 | real) about 0.3; most likely failure: the unwind is complete inside the first 15 minutes or dealers absorb it, leaving a drift below 0.05 R."
  },
  "similar_prior": [
   "prior_cot_positioning",
   "prior_nasdaq_lead_lag",
   "prior_cb_drift",
   "prior_fomc_cycle",
   "fx_liquidity_withdrawal_reversal"
  ],
  "why_different": "Every prior news or positioning test used one input alone. edge_hunt's NFP tests (inside prior_nasdaq_lead_lag) traded the direction of the first 15-minute move on 92 NFP days with 1 to 3 hour holds and no surprise size or positioning; cot_positioning's eight variants used positioning as a standalone signal at weekly horizons (crowding fades, hedging pressure, one-week flow follow and reversal) and found no edge after weekly costs; cb_drift and fomc_cycle measured decision-day drift without a surprise measure; the news-inclusive arm of fx_liquidity_withdrawal_reversal faded one-hour price moves on USDJPY and read nothing from the calendar. This hypothesis conditions a scheduled information shock on the state of the leveraged-fund book: the direction comes from the standardised surprise, not from the price move, so it is not a follow-the-move relabel; the entry waits out the five-minute repricing that ABDV measured; and the family carries two control arms that trade the same surprises in the same direction with the same costs, so a generic post-release drift or a generic cost effect appears in all three arms and only the forced-unwind component separates them. The pre-registered prediction is the asymmetry (against minus with >= 0.08 R, against minus neutral >= 0.05 R in design, both positive in check), which neither the price-only tests nor the positioning-only tests could have measured, and the external README explicitly reserves positioning for this conditioning use.",
  "parent_slug": null
 },
 {
  "slug": "jpy_retail_dipbuy_fragility",
  "title": "Retail dip-buying fragility: short a yen cross at the Tokyo open after a five-day decline of at least 1 x ATR20 during which the TFX Click 365 retail open interest grew by 10 or 15 percent or more, against a light-accumulation control (open interest up at most 2 percent on the same decline), holding 2 or 4 weekdays",
  "family": "retail_positioning_fragility_jpy",
  "rationale": "Mechanism: latent forced supply from an underwater leveraged retail book. Who trades: Japanese retail margin traders, of whom TFX Click 365 is the exchange-traded slice (350,000 to 600,000 open USDJPY contracts in the design years; the OTC margin book is about ten times larger and behaves the same way). They are structurally long the yen crosses for carry and contrarian: they add longs as the crosses fall. Descriptive, design years only: AUDJPY daily open-interest changes correlate -0.26 with daily returns, open interest rises about 3.5 percent on down days and falls 2.2 percent on up days; on five-day declines of at least 1 x ATR20 the five-day open-interest growth has quartiles +4, +9 and +18 percent, so the retail book grows into almost every decline and the question is how much. Why it matters: the positions are 10 to 25 times levered with broker-enforced losscuts, so a book that grew heavily into a decline is latent forced supply: if the decline extends, losscuts fire in a cascade and the move accelerates (the BIS Quarterly Review of December 2019 attributes the 3 January 2019 yen flash crash in large part to Japanese retail losscuts; the August 2015 and January-February 2016 yen-cross drops showed the same pattern), so after heavy accumulation into weakness the return distribution of the cross over the next days is negatively skewed and a short has a positive expectation; after a decline that retail did not buy (the light arm, including days the book shrank, where the losscuts have already happened), there is no latent supply and no continuation is expected, or a bounce. Who is on the other side: real money and CTAs selling the carry, whose selling retail absorbs. The 2011 Bank of Japan Review found that retail margin traders dampen volatility in calm times, which says the expected edge is small outside stress and is why this test pre-registers a one-sided direction (fade the retail accumulation), a monotonicity check (15 percent >= 10 percent >= light) and a modest expectation. What has been measured before: cross_zfade found two-sigma moves on crosses keep running at the daily horizon; fx_volume_climax_reversal found one-day shocks on majors continue and tick volume is not a capitulation signal; trend_follow found price-only trend flat before costs; jpy_cross_losscut_after_us_shock found no Tokyo-session continuation after a US equity shock and a Tokyo-morning bounce instead, and its mirror long was banned as a snooped flip. None of those had a positioning measure; this test conditions on the retail book itself, has no equity shock, holds for days rather than one session, and carries a control arm (the same decline without accumulation) that isolates the retail-book effect from the plain decline. Costs: AUDJPY spread 0.9 pips, 0.2 pips of slippage each side, 7 dollars commission (about 0.9 pips), about 2.2 pips against a 1.0 x ATR20 stop of 58 to 127 pips (median 81), so about 0.03 R; swap on a short AUDJPY is about -0.4 pips a day in the design years, negligible. Counts (design 2010-2017, from the TFX and price tables, no outcomes): AUDJPY about 460 days with a five-day decline of at least 1 x ATR20 (about 270 at 1.5 x); heavy10 covers about 45 percent of them, heavy15 about 30 percent, light (growth <= 2 percent) about 15 percent; with one position at a time and 2 to 4 weekday holds about 80 to 120 heavy trades and 30 to 45 light trades on AUDJPY; USDJPY, NZDJPY and GBPJPY similar; EURJPY's retail book was not structurally long in 2010-2017 (median five-day open-interest change on declines -2 percent), so it is the natural placebo market and is expected to show the weakest heavy-arm result. Expected: heavy arms +0.08 R, trade-level design t about 1.0 on about 100 trades, light arm at or below zero; P(design t >= 2 | effect real at +0.08 R) about 0.15, so an inconclusive negative is the most likely outcome, but this is the first measurement of the retail-flow dimension and its control fixes the baseline for every later TFX idea. Speed: about 1.1 trades a month per market, about 4 a month pooled over the four structurally long crosses (correlated), score 0.08 x 2 = 0.16: an edge-recording test that reaches the challenge speed bar only at +0.35 R. Human execution: one check of the TFX daily statistics after midnight UTC, one market order at the Tokyo open on the qualifying days, a 1 x ATR20 stop and a time exit two or four weekdays later at 20:30 UTC; a few orders a month. Most likely failure: the accumulation is the normal state of the book, so the heavy arms are the decline itself and the light arm is too small to tell; or the fragility shows only in the two or three crash episodes of the design years and dies in the breadth test.",
  "markets": [
   "AUDJPY",
   "NZDJPY",
   "USDJPY",
   "GBPJPY",
   "EURJPY"
  ],
  "aux_markets": [],
  "ext_series": [
   "tfx_daily"
  ],
  "timeframe": "H1",
  "rules": "All times UTC. H1 bars, stamped at the bar open and sparse; locate every time by timestamp (m.ts for opens, m.close_times() for closes). Loop over TFX rows (about 250 a year), vectorise everything else.\n\nTFX ROWS: t = F.ext_series(m, 'tfx_daily'); keep rows with symbol == m.sym (the price-store symbol column; raise if none) in ts_avail order (ts_avail = Click 365 trading date + 1 day at 00:00 UTC). For row r (TFX date d_r): oi_g_r = oi_r / oi_(r-5) - 1 over the previous five TFX rows (oi_lookback 5); undefined when fewer than five earlier rows exist or any of the six oi values is <= 0.\n\nPRICE CONDITION, from the store's own daily bars: daily = F.daily_bars(m) (trading days closing 17:00 New York); ATR20 = daily.to_bars(F.atr_prev(daily, atr_n = 20)), known at the day start. At the signal bar (below) the last completed trading day is D (the trading day before the one containing the signal bar). Require daily.date[D] == d_r (the Click 365 day d_r ends at the New York close of d_r, so the two venues describe the same day; skip the row when they do not match, which happens around holidays that one venue observes). drop_atr = (daily.c[D] - daily.c[D - ret_lookback]) / ATR20[sig] with ret_lookback 5 (five trading days). Condition: drop_atr <= -k (k 1.0 or 1.5). Skip if D - 5 < 0 or ATR20[sig] is not finite or <= 0.\n\nBANDS (p['band']): 'heavy10': oi_g_r >= 0.10; 'heavy15': oi_g_r >= 0.15; 'light': oi_g_r <= 0.02 (the control: the same decline without retail accumulation, including days the book shrank). Raise ValueError on any other value. A row trades only if its band condition and the price condition both hold.\n\nSIGNAL BAR AND ENTRY: T = ts_avail of the row (00:00 UTC). sig = the bar whose close time == T (the 23:00-00:00 UTC bar); if no bar closes exactly at T, use the first bar with close time >= T provided close - T <= max_delay_min (120) minutes and the bar's UTC date equals T's date, else skip (a Friday TFX row has T on Saturday and is always skipped). Short only: entry_short[sig] = True, entry_type[sig] = 0, valid_bars[sig] = 1; the fill is at the open of bar sig + 1 (normally the 00:00 UTC bar, 09:00 Tokyo) on the bid plus slippage. One position at a time: an entry while a position is open is ignored by the executor, so overlapping decline days produce one trade per hold.\n\nSTOP: sl_dist[sig] = sl_atr x ATR20[sig] (sl_atr 1.0, price units, > 0). tp_dist NaN (no target), max_bars 0.\n\nEXIT: exit date E = the hold_days-th weekday (Monday to Friday) after the UTC date of bar sig + 1 (hold_days 2 or 4; weekends skipped, holidays not); target = E at exit_utc (20:30). xi = F.first_bar_at_or_after(m, E, 20, 30); if xi < m.n and xi > sig + 1: exit_short[xi - 1] = True (close at the open of the first bar at or after the target). Causal fallback: for each signalled row k set exit_short True on every bar j with m.ts[j] >= target_k and j <= sig_(k+1) (the signal bar of the next signalled row, or m.n - 1 for the last), so a missing target bar closes the position at the first bar after the gap and never carries it into the next trade; a marker on sig_(k+1) acts at the open of the next fill bar, where the executor checks only the stop. Leftover guard: exit_short[sig_k] = True. Markers with no open position are ignored. No other exits, no other filters.\n\nPARAMETERS (every one read from p): band (grid 'heavy10', 'heavy15', 'light'), k (grid 1.0, 1.5), hold_days (grid 2, 4); fixed sl_atr 1.0, oi_lookback 5, ret_lookback 5, exit_utc '20:30', max_delay_min 120, atr_n 20. Module GRID = the full 12 cells so the checker exercises every value. Spec grids: stage A on AUDJPY runs all 12 cells (the 'light' cells are the control arm and run only there); stages B, C, the walk-forward and any holdout run band in ('heavy10', 'heavy15') only (8 cells). The Director sets specs/auto/jpy_retail_dipbuy_fragility.json after the review step so that stage_a.grid holds the 12 cells and grid holds the two heavy bands.\n\nEXPECTED COUNTS (AUDJPY design 2010-2017, from the TFX and daily tables, a check for the Builder and the checker): about 460 qualifying decline days at k 1.0 (about 270 at 1.5) before the band split and the overlap skips; heavy10 about 45 percent of them, heavy15 about 30 percent, light about 15 percent; about 80 to 120 heavy trades and 30 to 45 light trades after the one-position-at-a-time rule. A count far from these means the symbol subset, the day alignment or the open-interest ratio is wrong.\n\nREPORTING (from the trades; all 12 stage A rows read from the trials table, stage 'A'): per cell the number of trades, avg R, trade-level t, by-year avg R, mean fill spread in pips and as a share of the stop, for design and for check; for the chosen heavy cell: the matching light cell (same k and hold_days) and the other heavy band at the same k and hold_days, the avg R after dropping the best ceil(N/10) entry dates, the avg R of entries inside the three largest drawdown months of the design years against the rest, and the per-year heavy-minus-light difference in design and check.",
  "params": {
   "band": "heavy10",
   "k": 1.0,
   "hold_days": 2,
   "sl_atr": 1.0,
   "oi_lookback": 5,
   "ret_lookback": 5,
   "exit_utc": "20:30",
   "max_delay_min": 120,
   "atr_n": 20
  },
  "grid": {
   "band": [
    "heavy10",
    "heavy15",
    "light"
   ],
   "k": [
    1.0,
    1.5
   ],
   "hold_days": [
    2,
    4
   ]
  },
  "stage_a_market": "AUDJPY",
  "pre_registered": {
   "expected_design_t_min": 1.0,
   "expected_avg_r": 0.08,
   "min_trades_design_per_market": 40,
   "expected_trades_per_month": 1.1,
   "kill_if": "(1) Hypothesis-cell floor on AUDJPY, applied by the Director from all 12 stage A rows in the trials table (stage 'A') even if the pipeline reports a candidate: among the 8 heavy cells with at least 40 design trades, the chosen cell is the one with the highest trade-level design t (the pipeline's own ranking); it must have design avg R > 0 and t >= 1; if the automatic floor is cleared only by a 'light' cell, the B/C output is ignored and the hypothesis is scrapped under this rule. (2) Control difference and monotonicity, the test of the mechanism: at the chosen cell, design avg R(heavy) minus design avg R(the light cell with the same k and hold_days) must be >= +0.06 R and the same difference must be > 0 in check; and in design the heavy15 cell at the same k and hold_days must be >= the heavy10 cell minus 0.02 R (more accumulation, more fragility). If the light arm earns as much as the heavy arm, the decline and not the retail book carries the continuation, the lesson is that retail accumulation adds nothing to a plain multi-day decline, and no unconditional follow-the-decline hypothesis may be registered from this run (its sign would be read off the control arm). (3) Breadth: at the chosen cell at least 4 of the 8 design years positive, and design avg R > 0 after dropping the best ceil(N/10) entry dates; a result carried by the 2011, 2015 or 2016 crash months alone is an episode and is recorded as such. (4) Replication: at the chosen cell read from the stage B trials table, the pooled design avg R over NZDJPY, USDJPY and GBPJPY (equal-weighted over trades) must be > 0, and the pooled-check hard gate (avg R > 0 with >= 30 trades) and the walk-forward gate stand; EURJPY is the pre-registered placebo (its book was not structurally long in the design years) and is reported, not gated: a EURJPY heavy arm as strong as AUDJPY's is evidence that the signal is the decline, not the book. (5) Costs: the hard gate (positive at 1.5x costs) stands. (6) Pass bar: design t >= 2 at the chosen cell with (2) satisfied in design and check; a positive result below that is recorded as below the bar and is not promoted. Speed: at about 1.1 trades a month per market and +0.08 R the score is 0.16 (about 4 trades a month pooled over the four structurally long crosses), so this is recorded as an edge unless the heavy arm earns +0.35 R or more; honest expectation +0.08 R, design t about 1.0, P(t >= 2 | real) about 0.15; most likely failure: accumulation is the normal state of the book so the heavy arms measure the decline itself, or the fragility lives only in two or three crash episodes."
  },
  "similar_prior": [
   "jpy_cross_losscut_after_us_shock",
   "prior_cross_zfade",
   "fx_volume_climax_reversal",
   "prior_trend_follow",
   "prior_cot_positioning"
  ],
  "why_different": "No prior test in the programme used a measure of the retail book; the TFX daily open interest was built on 2026-10-14 for this purpose and the external README names open interest rising on a down day as the retail-flow proxy. jpy_cross_losscut_after_us_shock was an intraday test (short at 08:00 JST after a US equity-session drop, exit the same Tokyo session) whose condition was an equity shock, whose horizon was hours, and whose lesson was that the crosses bounce in the Tokyo morning; this test has no equity condition, conditions on how much the retail book grew over a five-day decline, holds two or four weekdays, and predicts an asymmetry between heavy and light accumulation on the same decline, which the intraday test could not measure. cross_zfade, fx_volume_climax_reversal and trend_follow were price-only (z-score, one-day shock, Donchian) with no positioning state; their finding that daily moves tend to continue is the reason the control arm exists: the light arm carries the plain decline and whatever continuation it has, so only the retail-book component separates the arms. cot_positioning measured speculator futures positioning at weekly horizons; the retail book is a different population with the opposite behaviour (contrarian, carry-long) and a forced-liquidation mechanism of its own. The sign is fixed from the mechanism (fade the accumulation) and from the published flash-crash evidence, not from any prior run of this programme.",
  "parent_slug": null
 }
]

# Scrap index
- index_earnings_season_premium [announcement_risk_premium_index] Aggregate earnings-announcement premium: hold the Nasdaq 100 CFD long Monday-to-Friday only in the weeks when most S&P 500 and Nasdaq 100 companies report (weeks 2 to 6 after each quarter-end), with every other week of the year as the control arm; replication on the S&P 500 and Nikkei 225 CFDs: The reporting-season weekly excess on the Nasdaq 100 CFD is at most about +0.05 to +0.10 R per week over the same-year control and never reaches trade-level t 1 in design, so the index-side calendar risk premium is measured and closed. All 16 stage A cells on USATECHIDXUSD (design 2013-2017, check 2018-2023, Monday 14:30 to Friday 19:30 UTC hold): the best season cell by design t (start 17 days after the quarter start, 5 weeks, stop 2.0 x ATR20) made +0.062 R (t 0.83, 96 trades) against -0.039 R for its matching control, and the other three start_off 17 season cells +0.017 to +0.090 R (t 0.19 to 0.69), while all four start_off 10 season cells lost in design (-0.014 to -0.077 R), so whatever excess exists sits in the later reporting weeks and is a fraction of its own standard error. In check every season cell was positive (+0.055 to +0.192 R, t up to 1.44) against controls of +0.014 to +0.038 R, which is consistent with a small premium of the size the pre-registration expected (0 to +0.08 R) and which a weekly CFD hold costing 0.05 to 0.13 R cannot turn into a trade; the pre-registered rule 1 (trade-level design t >= 1 at the chosen season cell) failed as the honest prior said it would in two cases out of three if the effect is real at that size. With FOMC cycle, turn-of-month, option expiry, pre-holiday drift, overnight drift and now the earnings season measured, no index calendar premium passes on a retail CFD. Do not retry with other window offsets or week counts, a day-of-announcement-only hold (the Savor-Wilson macro-announcement-day premium is about 10 bp a day against a 3-5 bp CFD round trip, so even the clean version nets about +0.03 R and would need thousands of trades), the S&P 500 or Nikkei 225 as primary, or an options-implied version this data cannot trade.
- jpy_fiscal_year_end_repatriation [fiscal_calendar_flow_jpy] Japanese fiscal-calendar flows in Tokyo hours: short USDJPY in the last business days of March (and September) when exporters and institutions repatriate and square books for the fiscal year-end, long USDJPY in the first business days of April (and October) when new-year outward allocations start; each leg with a same-window ordinary-month control arm: Japanese fiscal-calendar flows do not show up as a tradeable spot flow in Tokyo hours net of costs, and the month-of-year dimension is now measured. Pre-registered per-leg rule 1 failed for both legs on all 24 stage A cells (USDJPY, design 2010-2017, check 2018-2023, Tokyo session 00:00-06:00 UTC, stop 0.25 or 0.5 x ATR20, median stop 21.4 pips, fill spread 0.63 pips). ye_short (last 5 or 10 weekdays of March, or March and September): every March-only cell lost in design (-0.022 to -0.093 R, t -0.27 to -1.23, 40-80 trades); the best hypothesis cell by design t (March+September, 5 days, sl 0.25) made +0.026 R (t 0.25, month-window-clustered t 0.21, -0.034 R without its best month-window, +0.022 R without gotobi dates) and -0.047 R in check; the ordinary-month controls (same windows in months 1, 2, 5, 7, 8, 11) did better in design (+0.025 to +0.060 R) and in check (+0.035 to +0.155 R, t up to 2.6), so the fiscal excess is negative and the Tokyo-session short in the last weekdays of any month is a generic, cost-level month-end pattern already covered by the atlas's month-ordinal day types and the patterns_usdjpy fix-short. ny_long (first 5 or 10 weekdays of April, or April and October): every cell lost in design (-0.083 to -0.111 R, t -0.49 to -1.88) while check was positive (+0.04 to +0.13 R) against negative controls (-0.02 to -0.08 R), which is the 2021-2023 USDJPY rally drift the Critic predicted, not a new-fiscal-year flow. Stage B/C on the ye_short arm: pooled check -0.034 R (180 trades), walk-forward -0.025 R (340), negative at 1.5x costs, 3 of 3 markets positive in design only by cells with t below 0.7. Do not retry with other day counts, the London session or a full-day hold, the fix minute, September or October alone, the Japanese half-year dividend repatriation (June/December), an AUD or EUR fiscal year-end, or a JPY cross as primary; if repatriation exists it is hedged forward or executed off the Tokyo clock and leaves no spot footprint this programme can trade.
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


# External inputs (built 2026-10-14 by scripts/build_external.py)

Every table has `ts_avail` (UTC, naive): the first moment a row may be used. Strategies read these through `F.ext_asof` / `F.ext_rows` (see edge/engine/features.py); the leak tests cut and perturb them at the primary bar's close like auxiliary markets.

## calendar.parquet

71,033 rows, 2009-12-31 .. 2025-04-07. Columns: ts_release, ts_avail, time_known, time_source (scraped / typical / unknown), currency, event, impact (high / medium / low / none), actual, forecast, previous (strings as published), actual_num, forecast_num, previous_num (K/M/B/T scaled, % kept as the number), surprise = actual - forecast, surprise_z = surprise / std of that event's earlier surprises (at least 8), source.

Sources: 2010-2023 github.com/spoluan/forex-factory-scraper (datasets/forex_factory_calendar_YYYY.csv, ForexFactory scrape, times UTC+8 without daylight saving); 2024-01-01 .. 2025-04-07 huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar (forex_factory_cache.csv, MIT licence on the file, ForexFactory scrape). ForexFactory's own terms apply to the underlying data: private research use only. No source after 2025-04-07 yet.

- US Non-Farm Employment Change release times (UTC): {'12:30': 117, '13:30': 73} over 190 rows
- 2024+ NFP timestamps: ['2024-01-05 13:30', '2024-02-02 13:30', '2024-03-08 13:30', '2024-04-05 12:30', '2024-05-03 12:30', '2024-06-07 12:30']
- high-impact rows per year: {2010: 1163, 2011: 1191, 2012: 1159, 2013: 1159, 2014: 1207, 2015: 1189, 2016: 1096, 2017: 1010, 2018: 837, 2019: 839, 2020: 748, 2021: 545, 2022: 677, 2023: 908, 2024: 921, 2025: 250}
- time_source counts: {'scraped': 65586, 'unknown': 3578, 'typical': 1869}
- high-impact rows with numeric actual and forecast: 10304 of 14899; with surprise_z: 9311

## cot.parquet

9,345 rows, Tuesday positions 2010-01-05 .. 2026-10-06. Columns: market (EUR, JPY, GBP, CHF, CAD, AUD, NZD, USDX, SPX, NDX from the Traders in Financial Futures report; GOLD from the Disaggregated report), ts_asof, ts_release_date, ts_avail (15:30 New York on the release date), oi, and per group long / short / net / net_oi: spec (leveraged funds; managed money for gold), inst (asset managers; swap dealers for gold), comm (dealers; producers for gold), other, nonrept.

Source: cftc.gov/files/dea/history/fut_fin_txt_YYYY.zip and fut_disagg_txt_YYYY.zip, 2010-2026, public domain. Release dates: three US business days after the Tuesday (CFTC closures and holiday shifts from the gj-strat cot_positioning research); the 2013, 2018-19 and 2025 shutdown weeks and the 2023 ION-incident weeks are usable only from the end of their catch-up. gj-strat already tested positioning as a standalone signal (8 variants, negative); use it as a conditioning state.

- contracts: {'090741': 'CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '092741': 'SWISS FRANC - CHICAGO MERCANTILE EXCHANGE ', '096742': 'BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE ', '097741': 'JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE ', '098662': 'U.S. DOLLAR INDEX - ICE FUTURES U.S. ', '099741': 'EURO FX - CHICAGO MERCANTILE EXCHANGE ', '112741': 'NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '13874A': 'E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE ', '209742': 'NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE ', '232741': 'AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE ', '088691': 'GOLD - COMMODITY EXCHANGE INC. '}
- rows without an as-of date dropped: 0
- rows per market: {'GOLD': 875, 'AUD': 847, 'CAD': 847, 'CHF': 847, 'EUR': 847, 'GBP': 847, 'JPY': 847, 'NDX': 847, 'NZD': 847, 'SPX': 847, 'USDX': 847}
- as-of range: 2010-01-05 .. 2026-10-06; release lag days: {3: 8223, 4: 66, 6: 605, 7: 55, 10: 22, 14: 22, 17: 22, 21: 22, 24: 22, 28: 22, 31: 22, 35: 22, 38: 22, 42: 22, 45: 22, 49: 22, 52: 11, 56: 11, 59: 11, 63: 11, 71: 11, 77: 11, 80: 11, 84: 11, 91: 11, 98: 11, 105: 11, 112: 11}

## vol.parquet

Daily CBOE implied-volatility closes from FRED: vix (S&P 500), vxn (Nasdaq-100), evz (EuroCurrency ETF, i.e. EURUSD implied vol), gvz (gold), ovx (oil). Columns: ts_avail (21:30 UTC on the observation date), date, vix, vxn, evz, gvz, ovx.

Source: fred.stlouisfed.org/graph/fredgraph.csv?id=<series>, downloaded 2026-10-14. FRED terms: non-commercial use.

- range 2009-01-01 .. 2026-10-12, 4638 days; missing per series: {'vix': 134, 'vxn': 165, 'evz': 564, 'gvz': 165, 'ovx': 165}

## tfx.parquet

TFX (Tokyo Financial Exchange) Click 365 weekly retail long and short positions for 33 pairs, Tuesdays from
2022-11-22, usable from the Tuesday plus 8 days (ts_avail). Columns: pair, symbol, ts_asof, sell, buy, oi, net,
long_share, ts_avail. Built by scripts/build_external_tfx.py from the exchange's .xls files (data/external/tfx/raw);
details and caveats in data/external/tfx/README.md. Short history: usable for check-period and live conditioning,
not for design-period tests.

## tfx_daily.parquet

TFX Click 365 daily statistics per pair (36 pairs, trading days 2005-07-01 on): prev_settle, open, high, low, close, settle,
change, swap_point, volume, oi, d_oi, d_oi_pct, ret, with pair, symbol, date and ts_avail (= date + 1 day 00:00 UTC). Total
open interest only (no long/short split), so it is a direction-free retail-flow proxy with design-period history; tfx.parquet
holds the weekly long/short split from 2022-11. Built by scripts/build_external_tfx_daily.py; details in
data/external/tfx/README_daily.md.


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
Write a JSON object matching this schema to runs/cycles/cycle_0009/critic_review.json (one review per hypothesis, same slugs).

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
