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

# Your role: Research Director

You run the research programme. Each cycle you receive the state of research (buckets, scrap index with
lessons, trial and holdout counters, spend), the measured market facts, and the reports of the ideas that
finished since your last turn. You judge finished work and propose what to test next.

Judging: a report marked 'candidate' passed every hard gate; decide whether to promote it to the one-shot
holdout test (be stingy: each holdout run burns a little of the only unseen data), scrap it with a lesson,
or ask for one refinement (a refinement is a new pre-registered hypothesis that counts as new trials).
A report marked 'scrap' needs a lesson that will stop the programme from circling back to it.

Proposing: one to three hypotheses per cycle, each with a real economic mechanism (who trades, why they
must, who is on the other side, why the pressure shows up in price at that time or state), exact rules
that a careful programmer can implement from your text alone, a small parameter family, the primary
market for the coarse stage, and pre-registered expectations with a kill rule. Prefer mechanisms that are
different in kind from the scrap index, cheap relative to costs (the market facts tell you which hours
and instruments are cheap), and executable by a human on a prop account (no scalping at 1 pip). You may
range over any style and any instrument in the data. Specify times in UTC. Keep rules in words plus
formulas; the Builder translates them into code against the strategy contract.

The quality of this programme is the quality of your hypotheses and your honesty about results.


# Cycle 2
State: {"hypotheses": {"rejected": 1, "scrap": 22}, "trials": 84, "holdout_touches": 0, "spend_usd": 0.0}

# Candidates awaiting your judgment (reports below)
(empty)

# Good bucket (passed the holdout)
(empty)

# Reports finished since your last turn
## london_trend_day_ny_continuation: verdict scrap; failing ['G2_check_positive']; soft failures ['W6_dsr_hypothesis_0_9', 'W6b_dsr_program_0_5', 'W7_regime_half_years_positive', 'W8_cost_2x_positive']
gates: {'G0_no_leak': True, 'GA_stage_a_floor': True, 'GB_design_positive_markets': 4, 'G2_check_positive': False, 'G2b_walk_forward_positive': True, 'G4_cost_1_5x_positive': True, 'G5_sample_size': True}
warnings: {'W3_stability': True, 'W6_dsr_hypothesis_0_9': False, 'W6b_dsr_program_0_5': False, 'W7_regime_half_years_positive': False, 'W8_cost_2x_positive': False}
pooled: {'check_n': 666, 'check_avg_r': -0.002304954447799111, 'check_t': -0.07450772252798121, 'wf_oos_n': 1387, 'wf_oos_avg_r': 0.0008267629826666087, 'wf_oos_t': 0.04336062646788524}
EURUSD params {'k': 0.8, 'q': 0.15, 'm': 0.75, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}: design n 107 avg 0.102 t 1.82; check n 91 avg -0.089 t -1.60; WF oos avg -0.027 (windows + 5/11); stability 3/3; cost x1.5 0.003, x2 -0.009; DSR hyp 0.26 prog 0.11; years + 7/14; R by year {'2010': 1.5762237485348896, '2011': 0.7341882266472661, '2012': 7.6273152502844095, '2013': -0.3216828308196613, '2014': 0.939543539725718, '2015': 3.3572631379379425, '2016': -3.224031755986607, '2017': 0.19178878548643352, '2018': -1.3084921904681066, '2019': -5.5588783130188, '2020': 1.3466801982440917, '2021': -0.9097947630522987, '2022': -1.0535939120961082, '2023': -0.6049841342750224}
GBPUSD params {'k': 0.8, 'q': 0.25, 'm': 0.75, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}: design n 241 avg 0.033 t 1.03; check n 168 avg 0.006 t 0.14; WF oos avg -0.007 (windows + 4/11); stability 3/3; cost x1.5 0.010, x2 -0.003; DSR hyp 0.39 prog 0.08; years + 6/14; R by year {'2010': -1.7370882122346105, '2011': -1.3521120074914663, '2012': 2.6406579389912306, '2013': -0.48008725781681116, '2014': -0.08757255077550058, '2015': 4.883055002390114, '2016': 4.183689403806665, '2017': -0.020257587820116774, '2018': -1.5107013202574011, '2019': 0.1355314831258132, '2020': -0.3520837218969848, '2021': 2.9870180917540536, '2022': 0.14875222093364632, '2023': -0.44882334751843295}
AUDUSD params {'k': 0.8, 'q': 0.25, 'm': 0.5, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}: design n 75 avg 0.039 t 0.39; check n 68 avg 0.024 t 0.26; WF oos avg -0.024 (windows + 5/11); stability 1/3; cost x1.5 0.007, x2 -0.019; DSR hyp 0.14 prog 0.14; years + 5/14; R by year {'2010': -0.2502664422676818, '2011': 4.8988299264582125, '2012': -0.12082404509927819, '2013': -3.836356616217723, '2014': -2.3080540129662337, '2015': 3.063672335136878, '2016': 1.2154861830139545, '2017': 0.2758640421148246, '2018': -1.2598513033710304, '2019': -1.0219927080528624, '2020': 7.387544069536438, '2021': -0.6766291401582327, '2022': -0.41508456751908884, '2023': -2.3571879355958916}
GBPJPY params {'k': 0.5, 'q': 0.15, 'm': 0.5, 'window_start': '07:00', 'window_end': '12:00', 'exit_utc': '16:00', 'max_delay_min': 15}: design n 372 avg 0.050 t 1.04; check n 339 avg 0.012 t 0.22; WF oos avg 0.041 (windows + 8/11); stability 1/3; cost x1.5 0.001, x2 -0.027; DSR hyp 0.32 prog 0.02; years + 10/14; R by year {'2010': 0.928215833961872, '2011': -0.9411211615020156, '2012': 3.4754416315701953, '2013': 3.1652387415940204, '2014': 2.788091846880114, '2015': 7.062345258568344, '2016': 3.6060678618897644, '2017': -1.3195786656764352, '2018': 1.049204397675424, '2019': 7.089748016039525, '2020': -7.803142167598162, '2021': 2.4463456943872446, '2022': 3.3812572570752764, '2023': -2.225941566127301}

# Scrap index (do not re-test; build on only with a different mechanism)
- gold_asia_session_physical_bid [intraday_seasonality_metal] Gold rises during Asian hours: physical demand executes in Asia, paper selling in London and New York: rejected by critic: Duplicate of prior_flow_atlas: the atlas scanned XAUUSD on the Tokyo clock (no DST) with 30-minute to 8-hour windows starting every half hour on all weekdays, including exactly 08:00-16:00 and 09:00-17:00 JST = 23:00-07:00 and 00:00-08:00 UTC; neither reached even the watch list (design |t| >= 3.5) on mid prices before costs, and the strongest Asian-hours gold slot (01:30-02:30 UTC, mid t 5.9) lost after the atlas's costs as a trade (design -0.044 R, check -0.060 R). Do not re-slice Asian-hours gold.; Where the atlas did find Asian-hours gold strength in design it did not p
- london_trend_day_ny_continuation [intraday_continuation_trend_day] Trend-day continuation: London open-drive carries into the New York session: scrap: failed ['G2_check_positive']
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


# Recent lessons
- scrap: failed ['G2_check_positive']
- rejected by critic: Duplicate of prior_flow_atlas: the atlas scanned XAUUSD on the Tokyo clock (no DST) with 30-minute to 8-hour windows starting every half hour on all weekdays, including exactly 08:00-16:00 and 09:00-17:00 JST = 23:00-07:00 and 00:00-08:00 UTC; neither reached even the watch list (design |t| >= 3.5) on mid prices before costs, and the strongest Asian-hours gold slot (01:30-02:30 UTC, mid t 5.9) lost after the atlas's costs as a trade (design -0.044 R, check -0.060 R). Do not re-slice Asian-hours gold.; Where the atlas did find Asian-hours gold strength in design it did not p

Return your judgments for every candidate and every finished report listed above, then one to three new pre-registered hypotheses, then a short direction note.

# Output
Write a JSON object matching this schema to runs/cycles/cycle_0002/director.json, then run `cycle_step.py director --cycle 2`.
Every candidate and every finished report above needs a judgment. 1 to 3 hypotheses; grids of at most 36 combinations; params must contain every grid key; times in UTC.

```json
{
 "type": "object",
 "properties": {
  "judgments": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "slug": {
      "type": "string"
     },
     "decision": {
      "type": "string",
      "enum": [
       "promote",
       "scrap",
       "refine",
       "hold"
      ]
     },
     "lesson": {
      "type": "string"
     },
     "notes": {
      "type": "string"
     }
    },
    "required": [
     "slug",
     "decision",
     "lesson",
     "notes"
    ],
    "additionalProperties": false
   }
  },
  "hypotheses": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "slug": {
      "type": "string",
      "description": "snake_case, unique, <= 40 chars"
     },
     "title": {
      "type": "string"
     },
     "family": {
      "type": "string"
     },
     "rationale": {
      "type": "string"
     },
     "markets": {
      "type": "array",
      "items": {
       "type": "string"
      }
     },
     "timeframe": {
      "type": "string",
      "enum": [
       "M1",
       "M3",
       "M5",
       "M15",
       "M30",
       "H1",
       "H2",
       "H3",
       "H4",
       "H8",
       "D1"
      ]
     },
     "rules": {
      "type": "string",
      "description": "entry, exit, stop, target, filters, times in UTC, exact formulas"
     },
     "params": {
      "type": "object",
      "additionalProperties": {
       "type": [
        "number",
        "string",
        "boolean",
        "integer"
       ]
      }
     },
     "grid": {
      "type": "object",
      "additionalProperties": {
       "type": "array",
       "items": {
        "type": [
         "number",
         "string",
         "boolean",
         "integer"
        ]
       }
      }
     },
     "stage_a_market": {
      "type": "string"
     },
     "pre_registered": {
      "type": "object",
      "properties": {
       "expected_design_t_min": {
        "type": "number"
       },
       "expected_avg_r": {
        "type": "number"
       },
       "min_trades_design_per_market": {
        "type": "integer"
       },
       "kill_if": {
        "type": "string"
       }
      },
      "required": [
       "expected_design_t_min",
       "expected_avg_r",
       "min_trades_design_per_market",
       "kill_if"
      ],
      "additionalProperties": false
     },
     "similar_prior": {
      "type": "array",
      "items": {
       "type": "string"
      }
     },
     "why_different": {
      "type": "string"
     },
     "parent_slug": {
      "type": [
       "string",
       "null"
      ]
     }
    },
    "required": [
     "slug",
     "title",
     "family",
     "rationale",
     "markets",
     "timeframe",
     "rules",
     "params",
     "grid",
     "stage_a_market",
     "pre_registered",
     "similar_prior",
     "why_different",
     "parent_slug"
    ],
    "additionalProperties": false
   }
  },
  "direction_note": {
   "type": "string"
  }
 },
 "required": [
  "judgments",
  "hypotheses",
  "direction_note"
 ],
 "additionalProperties": false
}
```
