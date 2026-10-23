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
  "slug": "london_trend_day_ny_continuation",
  "title": "Trend-day continuation: London open-drive carries into the New York session",
  "family": "intraday_continuation_trend_day",
  "rationale": "On most days the London session is two-sided and its extremes revert, which is why session-reversal and box-breakout ideas died. A minority of days are trend days: a macro or CTA flow arrives at the London open and price runs one way with shallow pullbacks, closing the London morning near its extreme. Those flows are executed over the whole day by participants who must finish (funds rebalancing, systematic trend followers adding on strength, corporates with deadlines), and the New York session adds the same-direction US accounts plus the stops of early faders. The other side is counter-trend liquidity providers who are forced to cover into the New York open. The signature (large London range and a close at the extreme) is observable at 12:00 UTC, before the US participants arrive; the continuation should show up as positive drift from 12:00 to 16:00 UTC on those days only. Costs are lowest at 12 to 15 UTC on the majors (market facts), and the stop is sized to the day's own range, so R is meaningful rather than a fixed pip number.",
  "markets": [
   "EURUSD",
   "GBPUSD",
   "USDJPY",
   "AUDUSD",
   "USDCAD",
   "GBPJPY"
  ],
  "timeframe": "M5",
  "rules": "All times UTC. For each calendar date d (Monday to Friday): the London window is all bars with 07:00 <= ts < 12:00 on d. Let O = bid open of the first bar at or after 07:00 (skip the day if that bar is more than 15 minutes after 07:00), H = highest bid high in the window, L = lowest bid low in the window, C = bid close of the last bar before 12:00 (skip the day if that bar is more than 15 minutes before 12:00), R = H - L. ATR = previous-20-trading-day average daily range (F.atr_prev on NY-close daily bars) known at the start of the trading day that contains 12:00 UTC on d; skip the day if ATR is not available. Trend-day signature: R >= k * ATR. Direction: long if (C - L) / R >= 1 - q; short if (C - L) / R <= q; otherwise no trade. Entry: market order signalled on that last bar before 12:00, so it fills at the open of the first bar at or after 12:00 (ask for longs, bid for shorts). Stop: m * R from the fill. No take-profit. Exit: close the position at the open of the first bar at or after exit_utc (default 16:00) by setting the exit flag on the last bar before exit_utc; the stop stays live until then. One trade per day at most, no re-entry. Parameters: k (range threshold in ATR units), q (close-location fraction), m (stop in units of R), window_start = 07:00, window_end = 12:00, exit_utc = 16:00, max_delay_min = 15.",
  "params": {
   "k": 0.65,
   "q": 0.25,
   "m": 0.5,
   "window_start": "07:00",
   "window_end": "12:00",
   "exit_utc": "16:00",
   "max_delay_min": 15
  },
  "grid": {
   "k": [
    0.5,
    0.65,
    0.8
   ],
   "q": [
    0.15,
    0.25
   ],
   "m": [
    0.5,
    0.75
   ]
  },
  "stage_a_market": "EURUSD",
  "pre_registered": {
   "expected_design_t_min": 2.0,
   "expected_avg_r": 0.05,
   "min_trades_design_per_market": 150,
   "kill_if": "Stage A on EURUSD: best design avg R <= 0 or design t < 1. Also treat as dead if the effect exists only when m = 0.75 and k = 0.5 (the loosest corner), because that is the configuration closest to a plain afternoon-momentum bet."
  },
  "similar_prior": [
   "prior_fx_session_rev",
   "prior_box_breakouts",
   "prior_trend_follow"
  ],
  "why_different": "Session-reversal tests traded the Asian extreme into London and New York and found neither reversal nor momentum on average days; box breakouts entered on the first break of a quiet range. This hypothesis trades only days that already show a one-sided London session (large range plus close at the extreme) and bets on the New York continuation of that established flow, with the stop scaled to the day's range. It is a conditional, intraday, same-day mechanism rather than a daily or multi-day trend rule.",
  "parent_slug": null
 },
 {
  "slug": "gold_asia_session_physical_bid",
  "title": "Gold rises during Asian hours: physical demand executes in Asia, paper selling in London and New York",
  "family": "intraday_seasonality_metal",
  "rationale": "Physical gold demand from China and India (jewellers, bullion banks pricing off the Shanghai Gold Exchange, retail) is executed during Asian trading hours, while the bulk of paper selling (ETF outflows, COMEX futures, London OTC) happens in London and New York hours. The two groups trade at different times of day, so the price can carry a persistent intraday pattern: a positive drift from the Asian open to the London open, and weaker or negative drift later, which is the documented bias around the London fixes. The other side is the Western paper seller who is simply not active at 01:00 UTC. The gold-fix fade and gold box breakouts in the scrap index are point-in-time trades at the fix or on a range break; this is a session-long directional bias. Gold is expensive to trade per hour of range in Asia (cost ratio about 0.1), so the stop is scaled to the daily ATR to keep cost per R near 5 percent.",
  "markets": [
   "XAUUSD"
  ],
  "timeframe": "M5",
  "rules": "All times UTC. For each calendar date d: entry target time = d at entry_utc (23:00 or 00:00). The exit target time is exit_utc (07:00 or 08:00) on the next calendar day when entry_utc >= 12:00, otherwise on d. Signal a long market entry on the last bar before the entry target time, provided the first bar at or after the entry target is no more than max_delay_min (15) minutes after it (this skips weekends and holidays, when the next available bar is far away). The order fills at the open of the first bar at or after the entry target (ask). ATR = previous-20-trading-day average daily range (F.atr_prev on NY-close daily bars) known at the start of the trading day containing the entry bar; skip if not available. Stop: s * ATR below the fill. No take-profit. Exit: set the exit flag on the last bar before the exit target so the position closes at the open of the first bar at or after it; skip the day if that first exit bar is more than 15 minutes after the exit target. Long only, one position at a time. Parameters: entry_utc, exit_utc, s (stop in ATR units), max_delay_min = 15.",
  "params": {
   "entry_utc": "23:00",
   "exit_utc": "07:00",
   "s": 0.3,
   "max_delay_min": 15
  },
  "grid": {
   "entry_utc": [
    "23:00",
    "00:00"
   ],
   "exit_utc": [
    "07:00",
    "08:00"
   ],
   "s": [
    0.3,
    0.5
   ]
  },
  "stage_a_market": "XAUUSD",
  "pre_registered": {
   "expected_design_t_min": 2.0,
   "expected_avg_r": 0.04,
   "min_trades_design_per_market": 300,
   "kill_if": "Stage A: best design avg R <= 0 or design t < 1. Treat as dead if the check-period average is negative even when the design period passes, since the physical-demand structure must be persistent to be worth trading."
  },
  "similar_prior": [
   "prior_fix_fades",
   "prior_box_breakouts"
  ],
  "why_different": "Prior gold tests faded or followed the fix at a point in time or traded breakouts of a time box. This is a session-long long-only bias explained by who is active when (physical buyers in Asian hours, paper sellers later), not by a fix-time flow or a range break.",
  "parent_slug": null
 }
]

# Scrap index
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

# Output
Write a JSON object matching this schema to runs/cycles/cycle_0001/critic_review.json (one review per hypothesis, same slugs).

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
