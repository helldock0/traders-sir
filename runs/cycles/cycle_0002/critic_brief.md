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
  "slug": "usdjpy_tokyo_fix_holiday_shift",
  "title": "Holiday-shifted Tokyo-fix demand: USDJPY rises into the 09:55 JST fix on the weekday before and after a Japanese market holiday",
  "family": "settlement_flow_tokyo_fix",
  "rationale": "The Tokyo fix at 09:55 JST is where Japanese importers and other yen-side payers buy dollars for settlement; on gotobi days that demand is concentrated and USDJPY rises into the fix and gives it back afterwards (the known gotobi edge, +0.10 R per trade as a trade, design t 3.2). The counterparties are the dealers who warehouse the flow and sell it back after the fix. A Japanese market holiday removes a settlement day entirely: payments falling on the holiday move to the preceding business day (maeoshi) or to the following one (yokueigyobi), so the fix on the weekday before and the weekday after a holiday carries the holiday's settlement demand on top of its own. The same reasoning produced the only post-2010 calendar survivor outside gotobi and month-end: the atlas's 'day after a US holiday' USDJPY buy at the Tokyo fix (+0.12 / +0.05 / +0.07 R design / check / holdout). Japanese holidays are more numerous (16-20 weekdays a year) and the flow is the direct yen-settlement flow, so the effect should be at least as large. Costs are the lowest in the universe (USDJPY median spread 0.6 pips, about 1.7 pips all-in for a 1-3 hour trade against a 15-35 pip stop). Gotobi days are excluded so the test measures only the holiday-shifted demand and cannot borrow the known edge. The grid pre-registers which side carries the flow: 'after' if the convention is next-business-day, 'before' if it is preceding-business-day, 'either' pools them for power.",
  "markets": [
   "USDJPY"
  ],
  "timeframe": "M5",
  "rules": "All times UTC (Tokyo has no daylight saving, so these never shift). Bars: M5 on USDJPY.\nJAPANESE MARKET HOLIDAYS. Hardcode this exact list in the module as a tuple of ISO date strings (no datetime module; parse with numpy datetime64): 2010-01-01, 2010-01-02, 2010-01-03, 2010-01-11, 2010-02-11, 2010-03-21, 2010-03-22, 2010-04-29, 2010-05-03, 2010-05-04, 2010-05-05, 2010-07-19, 2010-09-20, 2010-09-23, 2010-10-11, 2010-11-03, 2010-11-23, 2010-12-23, 2010-12-31, 2011-01-01, 2011-01-02, 2011-01-03, 2011-01-10, 2011-02-11, 2011-03-21, 2011-04-29, 2011-05-03, 2011-05-04, 2011-05-05, 2011-07-18, 2011-09-19, 2011-09-23, 2011-10-10, 2011-11-03, 2011-11-23, 2011-12-23, 2011-12-31, 2012-01-01, 2012-01-02, 2012-01-03, 2012-01-09, 2012-02-11, 2012-03-20, 2012-04-29, 2012-04-30, 2012-05-03, 2012-05-04, 2012-05-05, 2012-07-16, 2012-09-17, 2012-09-22, 2012-10-08, 2012-11-03, 2012-11-23, 2012-12-23, 2012-12-24, 2012-12-31, 2013-01-01, 2013-01-02, 2013-01-03, 2013-01-14, 2013-02-11, 2013-03-20, 2013-04-29, 2013-05-03, 2013-05-04, 2013-05-05, 2013-05-06, 2013-07-15, 2013-09-16, 2013-09-23, 2013-10-14, 2013-11-03, 2013-11-04, 2013-11-23, 2013-12-23, 2013-12-31, 2014-01-01, 2014-01-02, 2014-01-03, 2014-01-13, 2014-02-11, 2014-03-21, 2014-04-29, 2014-05-03, 2014-05-04, 2014-05-05, 2014-05-06, 2014-07-21, 2014-09-15, 2014-09-23, 2014-10-13, 2014-11-03, 2014-11-23, 2014-11-24, 2014-12-23, 2014-12-31, 2015-01-01, 2015-01-02, 2015-01-03, 2015-01-12, 2015-02-11, 2015-03-21, 2015-04-29, 2015-05-03, 2015-05-04, 2015-05-05, 2015-05-06, 2015-07-20, 2015-09-21, 2015-09-22, 2015-09-23, 2015-10-12, 2015-11-03, 2015-11-23, 2015-12-23, 2015-12-31, 2016-01-01, 2016-01-02, 2016-01-03, 2016-01-11, 2016-02-11, 2016-03-20, 2016-03-21, 2016-04-29, 2016-05-03, 2016-05-04, 2016-05-05, 2016-07-18, 2016-08-11, 2016-09-19, 2016-09-22, 2016-10-10, 2016-11-03, 2016-11-23, 2016-12-23, 2016-12-31, 2017-01-01, 2017-01-02, 2017-01-03, 2017-01-09, 2017-02-11, 2017-03-20, 2017-04-29, 2017-05-03, 2017-05-04, 2017-05-05, 2017-07-17, 2017-08-11, 2017-09-18, 2017-09-23, 2017-10-09, 2017-11-03, 2017-11-23, 2017-12-23, 2017-12-31, 2018-01-01, 2018-01-02, 2018-01-03, 2018-01-08, 2018-02-11, 2018-02-12, 2018-03-21, 2018-04-29, 2018-04-30, 2018-05-03, 2018-05-04, 2018-05-05, 2018-07-16, 2018-08-11, 2018-09-17, 2018-09-23, 2018-09-24, 2018-10-08, 2018-11-03, 2018-11-23, 2018-12-23, 2018-12-24, 2018-12-31, 2019-01-01, 2019-01-02, 2019-01-03, 2019-01-14, 2019-02-11, 2019-03-21, 2019-04-29, 2019-04-30, 2019-05-01, 2019-05-02, 2019-05-03, 2019-05-04, 2019-05-05, 2019-05-06, 2019-07-15, 2019-08-11, 2019-08-12, 2019-09-16, 2019-09-23, 2019-10-14, 2019-10-22, 2019-11-03, 2019-11-04, 2019-11-23, 2019-12-31, 2020-01-01, 2020-01-02, 2020-01-03, 2020-01-13, 2020-02-11, 2020-02-23, 2020-02-24, 2020-03-20, 2020-04-29, 2020-05-03, 2020-05-04, 2020-05-05, 2020-05-06, 2020-07-23, 2020-07-24, 2020-08-10, 2020-09-21, 2020-09-22, 2020-11-03, 2020-11-23, 2020-12-31, 2021-01-01, 2021-01-02, 2021-01-03, 2021-01-11, 2021-02-11, 2021-02-23, 2021-03-20, 2021-04-29, 2021-05-03, 2021-05-04, 2021-05-05, 2021-07-22, 2021-07-23, 2021-08-08, 2021-08-09, 2021-09-20, 2021-09-23, 2021-11-03, 2021-11-23, 2021-12-31, 2022-01-01, 2022-01-02, 2022-01-03, 2022-01-10, 2022-02-11, 2022-02-23, 2022-03-21, 2022-04-29, 2022-05-03, 2022-05-04, 2022-05-05, 2022-07-18, 2022-08-11, 2022-09-19, 2022-09-23, 2022-10-10, 2022-11-03, 2022-11-23, 2022-12-31, 2023-01-01, 2023-01-02, 2023-01-03, 2023-01-09, 2023-02-11, 2023-02-23, 2023-03-21, 2023-04-29, 2023-05-03, 2023-05-04, 2023-05-05, 2023-07-17, 2023-08-11, 2023-09-18, 2023-09-23, 2023-10-09, 2023-11-03, 2023-11-23, 2023-12-31, 2024-01-01, 2024-01-02, 2024-01-03, 2024-01-08, 2024-02-11, 2024-02-12, 2024-02-23, 2024-03-20, 2024-04-29, 2024-05-03, 2024-05-04, 2024-05-05, 2024-05-06, 2024-07-15, 2024-08-11, 2024-08-12, 2024-09-16, 2024-09-22, 2024-09-23, 2024-10-14, 2024-11-03, 2024-11-04, 2024-11-23, 2024-12-31, 2025-01-01, 2025-01-02, 2025-01-03, 2025-01-13, 2025-02-11, 2025-02-23, 2025-02-24, 2025-03-20, 2025-04-29, 2025-05-03, 2025-05-04, 2025-05-05, 2025-05-06, 2025-07-21, 2025-08-11, 2025-09-15, 2025-09-23, 2025-10-13, 2025-11-03, 2025-11-23, 2025-11-24, 2025-12-31, 2026-01-01, 2026-01-02, 2026-01-03, 2026-01-12, 2026-02-11, 2026-02-23, 2026-03-20, 2026-04-29, 2026-05-03, 2026-05-04, 2026-05-05, 2026-05-06, 2026-07-20, 2026-08-11, 2026-09-21, 2026-09-22, 2026-09-23, 2026-10-12, 2026-11-03, 2026-11-23, 2026-12-31. It is the statutory national holidays 2010-2026 including substitute holidays (a Sunday holiday moves to the next free weekday), citizens' holidays (a weekday between two holidays), the 2019 enthronement days (04-30, 05-01, 05-02, 10-22), the 2020/2021 Olympic shifts of Marine, Mountain and Sports Day, plus the bank closures 12-31, 01-02 and 01-03 every year. MISSED-FIX DAYS = the listed dates that fall on Monday to Friday (F.weekday(dates) < 5): no Tokyo fix is set and no yen settlement happens on them.\nCANDIDATE DATES. Let dates = np.unique(F.utc_dates(m)) restricted to Monday-Friday, not in the holiday list, and with F.is_gotobi(dates) False (gotobi days carry the known settlement flow and are excluded so this test measures only the holiday-shifted demand). prev_wd(d) = the previous weekday (Friday when d is Monday); next_wd(d) = the next weekday (Monday when d is Friday). d is an AFTER day if prev_wd(d) is a missed-fix day; d is a BEFORE day if next_wd(d) is a missed-fix day. Param side: 'after' trades AFTER days, 'before' trades BEFORE days, 'either' trades days that are AFTER or BEFORE (a day that is both counts once).\nENTRY (long USDJPY, i.e. buy USD). Entry target time = entry_utc on the same UTC date d when entry_utc < '12:00', otherwise entry_utc on the previous calendar date d-1 (so '22:30' means 22:30 UTC the evening before = 07:30 JST on d; for a Monday that is Sunday 22:30 UTC, when Dukascopy already quotes). Let ei = F.first_bar_at_or_after(m, target_date, hh, mm). Skip the day if ei >= m.n or m.ts[ei] is more than max_delay_min minutes after the target. Signal the market entry on bar ei-1 (s.entry_long[ei-1] = True) so the order fills at the open (ask) of bar ei.\nEXIT. xi = F.first_bar_at_or_after(m, d, 0, 55) for exit_utc '00:55' (the 09:55 JST fix). Skip the day if xi >= m.n, xi <= ei, or m.ts[xi] is more than max_delay_min minutes after 00:55 UTC. Set s.exit_long[xi-1] = True so the position closes at the open (bid) of bar xi. No take-profit, no re-entry, one trade per date.\nSTOP. sl_dist = sl_atr * ATR20 where ATR20 = F.atr_prev(F.daily_bars(m), 20) broadcast to bars with daily.to_bars (previous-20-trading-day average true range on New York 17:00 daily bars, known at the start of the trading day containing bar ei). Take the value at bar ei; skip the day if it is not finite or <= 0. Write sl_dist on the signal bar ei-1.\nPARAMETERS. side in {before, after, either}; entry_utc in {22:30, 23:30, 00:00}; exit_utc fixed '00:55'; sl_atr in {0.25, 0.5}; max_delay_min = 10. Read every tunable from p.",
  "params": {
   "side": "either",
   "entry_utc": "23:30",
   "exit_utc": "00:55",
   "sl_atr": 0.25,
   "max_delay_min": 10
  },
  "grid": {
   "side": [
    "before",
    "after",
    "either"
   ],
   "entry_utc": [
    "22:30",
    "23:30",
    "00:00"
   ],
   "sl_atr": [
    0.25,
    0.5
   ]
  },
  "stage_a_market": "USDJPY",
  "pre_registered": {
   "expected_design_t_min": 1.5,
   "expected_avg_r": 0.12,
   "min_trades_design_per_market": 50,
   "kill_if": "Stage A on USDJPY: no combination with at least 50 design trades has design avg R > 0 and t >= 1. Also treat as dead if the best combination's design avg R is below +0.05 R (half the gotobi trade's +0.10 R): a holiday-shifted flow weaker than that cannot carry a basket leg on 15-20 days a year. If 'either' is positive only because one side is strongly positive and the other clearly negative, record which side carries the flow and do not pool in any follow-up."
  },
  "similar_prior": [
   "prior_flow_atlas",
   "prior_fix_fades"
  ],
  "why_different": "The flow atlas scanned unconditional half-hour means by day type and included 'day before a Japan holiday' but not 'day after a Japan holiday'; its survival bar (design |t| >= 4.5 for pairs, built for 600,912 tests) could not have seen a trade-sized effect of +0.1 R, which is the size of the gotobi edge itself (t 3.2 as a trade). This is one pre-registered prediction derived from the settlement convention, with the known gotobi days removed, not a re-slice of the scan. The fix-fade tests traded fixed calendar slots (month-start Tokyo fix, gotobi) in both directions; none conditioned on holiday-shifted settlement dates.",
  "parent_slug": null
 },
 {
  "slug": "jpy_tokyo_open_contrarian_flow",
  "title": "Tokyo-open contrarian flow: fade the New York session move in USDJPY and AUDJPY at 09:00 JST",
  "family": "liquidity_provision_tokyo_open",
  "rationale": "Two large yen-side participant groups trade against the overnight move when Tokyo opens. Japanese retail margin traders (several trillion yen of monthly turnover, documented by the BoJ and the Tokyo Financial Exchange as systematically contrarian: they add to long USDJPY and AUDJPY positions after falls and take profit after rises) and Japanese importers and institutions who buy dollars more readily when the New York session has made them cheaper. Both groups are absent during New York hours, when macro accounts and CTAs move the price, and both arrive at 09:00 JST. The prediction is a partial reversal of the New York session move in the first one to two hours of Tokyo, strongest for falls (importer plus retail buying) and larger after larger moves. The other side is the New York accounts that pushed the price and the dealers who carried the inventory overnight. Costs: USDJPY 0.6 pips and AUDJPY 0.9 pips spread, about 1.7 to 2.0 pips all-in, against a 2-hour sigma of roughly 12-18 pips and stops of 0.25-0.5 ATR20 (15-40 pips). Sample: a 1.25-sigma threshold selects about a fifth of weekdays, roughly 400 design trades per market. The 'both' arm tests whether the flow is symmetric contrarian liquidity provision; the primary arm is long-only.",
  "markets": [
   "USDJPY",
   "AUDJPY"
  ],
  "timeframe": "M5",
  "rules": "All times UTC. Bars: M5. Markets USDJPY (primary) and AUDJPY, same rules.\nREFERENCE MOVE. For every UTC calendar date d that is a Tuesday, Wednesday, Thursday or Friday, the reference session is the New York session of the previous calendar date d-1 (always a weekday Monday-Thursday): P13 = bid close of the last bar strictly before ny_start ('13:00') on d-1 and P21 = bid close of the last bar strictly before ny_end ('21:00') on d-1 (use F.first_bar_at_or_after(m, d-1, hh, mm) and take the bar before it). Skip the day if either bar is more than 15 minutes before its target time or does not exist. M(d) = ln(P21 / P13). Mondays are never traded (the weekend gap sits between Friday's New York session and Monday's Tokyo open).\nVOLATILITY SCALE. sigma(d) = sample standard deviation (ddof 1) of the previous vol_window (20) available values of M, i.e. the M values of the 20 most recent earlier reference days, not including M(d). Skip days that have fewer than 20 earlier values. Compute this with a Python loop over days or a rolling window on the per-day array; never with information from d or later.\nSIGNAL. Trade only if |M(d)| >= theta * sigma(d). Direction is contrarian to the New York move: M(d) < 0 (the pair fell in New York) -> LONG at the Tokyo open; M(d) > 0 -> SHORT, but shorts are taken only when side == 'both' (side == 'long_only' takes the long trades only). M(d) == 0 -> no trade.\nENTRY. ei = F.first_bar_at_or_after(m, d, 0, 0) for entry_utc '00:00' (09:00 JST, Tokyo open). Skip if ei >= m.n or m.ts[ei] is more than max_delay_min (10) minutes after the target. Signal the market order on bar ei-1 (entry_long or entry_short) so it fills at the open of bar ei (ask for longs, bid for shorts).\nEXIT. xi = F.first_bar_at_or_after(m, d, hh, mm) for exit_utc in {'00:55', '02:00'}. Skip if xi >= m.n, xi <= ei or m.ts[xi] is more than max_delay_min minutes after the target. Set exit_long / exit_short on bar xi-1 so the position closes at the open of bar xi. No take-profit, one trade per date, no re-entry.\nSTOP. sl_dist = sl_atr * ATR20 where ATR20 = F.atr_prev(F.daily_bars(m), 20) broadcast to bars (New York 17:00 daily bars, known before the trading day that contains bar ei). Value at bar ei; skip if not finite or <= 0; write it on the signal bar ei-1.\nPARAMETERS. theta in {0.75, 1.25}; exit_utc in {00:55, 02:00}; sl_atr in {0.25, 0.5}; side in {long_only, both}; ny_start = 13:00, ny_end = 21:00, entry_utc = 00:00, vol_window = 20, max_delay_min = 10. Read every tunable from p.",
  "params": {
   "theta": 0.75,
   "exit_utc": "00:55",
   "sl_atr": 0.25,
   "side": "long_only",
   "ny_start": "13:00",
   "ny_end": "21:00",
   "entry_utc": "00:00",
   "vol_window": 20,
   "max_delay_min": 10
  },
  "grid": {
   "theta": [
    0.75,
    1.25
   ],
   "exit_utc": [
    "00:55",
    "02:00"
   ],
   "sl_atr": [
    0.25,
    0.5
   ],
   "side": [
    "long_only",
    "both"
   ]
  },
  "stage_a_market": "USDJPY",
  "pre_registered": {
   "expected_design_t_min": 1.5,
   "expected_avg_r": 0.06,
   "min_trades_design_per_market": 200,
   "kill_if": "Stage A on USDJPY: no combination with at least 200 design trades has design avg R > 0 and t >= 1. Also scrap if the long-only arm is <= 0 while the 'both' arm is positive (that would be a generic intraday reversal, a family that has already died, not the importer-plus-retail flow claimed here). A result that exists only at exit 02:00 and not at 00:55 is allowed but must be noted as a slower flow than claimed."
  },
  "similar_prior": [
   "prior_fx_session_rev",
   "prior_box_breakouts",
   "prior_nasdaq_lead_lag"
  ],
  "why_different": "The session-reversal tests faded the Asian-session extreme currency into London and New York, where no specific contrarian participant exists, and found nothing; the box tests traded breakouts of the pre-Tokyo range; the lead-lag tests used Nasdaq and Nikkei moves to predict USDJPY. This hypothesis fades the New York session move of the pair itself at the Tokyo open, a time and place with a named, documented contrarian participant (Japanese retail margin traders and importers), restricted to the two yen pairs those participants dominate, over a one-to-two-hour horizon.",
  "parent_slug": null
 }
]

# Scrap index
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

# Output
Write a JSON object matching this schema to runs/cycles/cycle_0002/critic_review.json (one review per hypothesis, same slugs).

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
