# Edge Research System: Plan

Date: 2026-10-11. Project folder: D:\Traders sir (empty at time of writing).

## 1. Verdict

Yes. A three-model research loop that downloads Dukascopy forex data, proposes strategies, builds and tests them, sorts them into buckets and runs around the clock is buildable with today's tools. Your role split is close to right. Two changes make it actually work:

1. **The models decide, code computes.** Fable, Opus and Sonnet are called at a few decision points per cycle. A Python engine does the backtesting in between. That is the difference between a loop that costs tens of dollars a day and one that costs thousands.
2. **The output is a probability, not a promise.** The deliverable is a basket of strategies with a measured chance of passing a specific firm's rules, found under controls strict enough that the number means something. Nothing can guarantee a pass. The default failure of this kind of project is a "good bucket" full of curve-fit noise that looks great in a backtest and loses money live. Most of the design below exists to prevent exactly that.

Timeline honesty: building the system takes about two to three weeks of work with me. How long the research phase takes to find something that survives every gate is unknown. It could be two weeks; for a given idea space it could be never. Add two to four weeks of forward testing on a demo account before risking a challenge fee. "Passing within one or two months" from today is optimistic. Three months to a well-founded challenge attempt is a realistic target if the research finds an edge.

## 2. Terminology check

"Docker copy candles" is read as **Dukascopy**: the Swiss bank whose free historical tick and minute data is the standard free source for forex research. Say so if you meant something else.

## 3. Roles

| Role | Model | Price in / out per 1M tokens | What it does | How often |
|---|---|---|---|---|
| Research Director | Claude Fable 5.1 (`claude-fable-5-1`) | $10 / $50 | Reads the state of research (what failed, what passed, what is unexplored, data facts). Judges last cycle's results against its own pre-registered expectations. Proposes the next 1 to 3 hypotheses as structured specs with economic rationale, parameter ranges, pairs, timeframes, expected metrics and kill criteria. | Once per cycle |
| Critic | Claude Opus 5.5 (`claude-opus-5-5`) | $4 / $20 | Adversarial review before compute is spent: is this indicator soup, is it already in scrap, will costs kill it at this timeframe, is the grid too large. Then reviews the Builder's code for look-ahead bias, off-by-one on bar close, cost and sizing bugs. | Twice per cycle |
| Builder / Runner | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 / $10 | Turns an approved spec into a strategy module against the engine's interface, runs the automated leak tests, launches the backtest pipeline, writes the report. | 1 to 3 calls per cycle |
| Housekeeping (optional) | Claude Haiku 5.5 (`claude-haiku-5-5`) | $0.10 / $0.50 | Log summaries, scrap-index compression, notifications. | As needed |

Why a different model as Critic: two models share fewer blind spots than one model grading itself. Why the Critic runs before the backtest: killing a bad idea costs cents; backtesting it costs an hour of compute and a trial against the multiple-testing budget.

Cost lever: Fable is 2.5x the price of Opus. If spend matters more than the last few percent of judgment quality, Opus can take the Director seat and Fable can be reserved for promotion decisions only. The design does not change.

## 4. One research cycle

Target wall-clock per cycle: 20 to 60 minutes, almost all of it compute.

1. **Director** receives the research state: scrap index (what failed and why), candidates, good bucket, trial count so far, coverage map (pairs x timeframes x strategy families explored), and engine-computed data facts (volatility by session, spread by hour, autocorrelation by timeframe). Returns: judgment on the last batch, plus new hypothesis specs. Each spec pre-registers expected out-of-sample Sharpe, trade count, average trade relative to cost, and a kill rule.
2. **Critic** reviews each spec. Verdicts: approve, revise, reject. Rejections go straight to scrap with the reason. No compute spent.
3. **Builder** implements approved specs as modules (a signal function plus a config schema). Runs the harness tests: shifted-data test, future-leak probe, randomized-data test (a strategy that beats shuffled data is leaking).
4. **Critic** reviews the code. At most two rounds back to the Builder.
5. **Engine** (pure code, no model calls) runs a staged pipeline:
   - Stage A: one pair, one timeframe, coarse grid, in-sample years. Seconds. Kill if nothing clears the pre-registered floor.
   - Stage B: full grid across approved pairs and timeframes, in-sample. Minutes.
   - Stage C: walk-forward, parameter-neighborhood stability, cost stress at 1.5x and 2x, Monte Carlo of trade sequences, deflated Sharpe using the program-wide trial count, prop-rule simulation. Minutes to an hour.
6. **Director** reads the Stage C report against the pre-registered expectations. Outcome: scrap with lesson, candidate for one refinement round (counts as new trials), or promotion to the locked test.
7. **Locked test** runs once per promoted strategy on years no agent has seen. Pass: good bucket. Fail: scrap, and the test-set exposure counter increments.
8. **Portfolio step** whenever the good bucket has two or more entries: correlation of daily returns, combined equity curve, prop-rule Monte Carlo on the combination, position sizing chosen to maximize pass probability subject to a breach-probability ceiling.
9. **Goal check**: basket pass probability above target and breach probability below ceiling on the locked test. Reached: notify you and switch to forward-test mode. Not reached: next cycle.

Everything is persisted: SQLite for hypotheses, trials, verdicts and metrics; files for strategy code, reports and plots. The Director never repeats an idea because it reads the scrap index.

What makes the search efficient rather than a brute-force indicator grid:

- Hypothesis first. Every spec needs an economic reason (session liquidity, order flow after sweeps, carry and trend interaction, volatility regimes, central-bank days). Indicator combinations without a reason are rejected by the Critic.
- Families, not points. A hypothesis is a parametrized family; the whole surface is judged, not the best point on it.
- Cheap first. Stage A kills most ideas in seconds before Stage B and C spend minutes or hours.
- Negative results are memory. Scrap is indexed and read every cycle.
- Trial accounting. Every backtest increments a program-wide counter that feeds the deflated Sharpe gate, so the system pays for its own curiosity.

## 5. Data

| Item | Decision |
|---|---|
| Source | Dukascopy via the `dukascopy-node` downloader (Node 24 is already on this machine) |
| What to download | Tick data (bid and ask) for the pairs you will actually trade, plus 1-minute candles for the full universe |
| Why not download each timeframe separately | All higher timeframes are resampled from 1-minute data so every timeframe is consistent and arbitrary ones such as 3-hour are free |
| Timeframes produced | 1m, 3m, 5m, 15m, 30m, 1h, 2h, 3h, 4h, 8h, D1, W1 |
| Default universe | 28 majors and minors; gold (XAUUSD) optional |
| History | 2010 to present for research; the last two to three years are the locked test |
| Storage | Parquet files, UTC timestamps, one file per pair and timeframe |
| Expected size | About 3 to 5 GB for 1-minute across 28 pairs; 20 to 40 GB more if ticks are kept for eight pairs |
| Quality checks | Gap detection, duplicate bars, weekend handling, DST-aware session labels, outlier spikes |
| Spread model | Hourly median and 90th-percentile spread per pair from tick data; fixed conservative spread where ticks are not kept |

Caveat: the prop firm's broker feed will differ slightly from Dukascopy. Research on Dukascopy, then calibrate costs and run the forward test on the firm's own MT5 demo feed.

## 6. Engine requirements

- Signals computed only from closed candles; fills at the next bar's open plus half-spread plus slippage.
- Costs: spread, commission per lot, slippage model, swap and triple-swap Wednesday, weekend gap handling.
- Vectorized signal generation (pandas and numpy) and a compiled trade loop (numba), so a full grid across 28 pairs and several timeframes finishes in minutes rather than hours.
- Prop-firm rule layer, configurable per firm: profit target, daily loss limit and how the day resets, maximum loss, minimum trading days, time limit if any, news and weekend restrictions, consistency rule, maximum lots.
- Position sizing modes: fixed fractional risk, volatility-scaled, and a pass-probability optimizer.
- Engine self-tests: buy-and-hold matches the price change; a random-entry strategy loses exactly its costs on average; a deliberately leaked strategy is caught by the harness.

## 7. Validation gates and buckets

A strategy must clear every gate in order. Any failure sends it to scrap with the failing gate recorded.

| Gate | Requirement |
|---|---|
| G1 In-sample floor | Clears the Director's pre-registered minimum on the development years |
| G2 Walk-forward | Rolling re-optimization; out-of-sample performance at least half of in-sample; profitable in most windows |
| G3 Parameter stability | Neighbors of the chosen parameters are also profitable; no isolated spikes |
| G4 Cost stress | Still positive at 1.5x assumed costs; degrades gracefully at 2x |
| G5 Sample size | Minimum trade count out-of-sample (hundreds, not dozens) |
| G6 Multiple testing | Deflated Sharpe ratio using the program-wide trial count above threshold |
| G7 Regime check | Survives 2020 and 2022 style regimes; logic transfers to related pairs |
| G8 Locked test | One run on unseen years. Final. |
| G9 Prop simulation | Monte Carlo of trade sequences under the firm's rules gives pass and breach probabilities |

Buckets: `scrap/` (kept, with reasons, so ideas are never re-tested), `candidates/` (past G1 to G4, pending the rest), `good/` (past G8), `basket/` (portfolio compositions with G9 numbers). Scrap is as valuable as good: it is the system's memory of what does not work.

## 8. Goal mode

- Loop: `while not goal_reached and budget_ok: run_cycle()`.
- Goal: a basket whose locked-test pass probability is at or above the target you set (suggested 60 percent) with breach probability at or below the ceiling (suggested 20 percent), and which then survives the forward test.
- Hard stops: daily and monthly API spend caps, error-rate circuit breaker, disk-space check, and a manual pause file.
- Notifications: Telegram or email on promotion, goal reached, or stop.
- Runs on this PC left on 24/7. The machine (12 cores, 24 threads, 32 GB RAM) is strong enough that a VPS is only worth it if the PC cannot stay on. Compute is the bottleneck, not the models: more cores means more cycles per day at the same model cost per cycle.
- Where the orchestrator lives: a Python script using the Anthropic SDK with structured outputs, so each role's output is machine-checkable JSON; prompt caching on the stable system prompts; server-side fallback so a declined request retries on another model instead of stalling the loop. Claude Code subagents are useful for dry runs while building, but a 24/7 unattended loop belongs in a standalone script billed on the API, not on a chat subscription.

## 9. Cost

Model spend per cycle, assuming prompt caching on the stable parts of each prompt:

| Call | Model | Approx. per cycle |
|---|---|---|
| Director (judge last batch and propose next) | Fable 5.1 | $0.30 to $0.50 |
| Critic, hypothesis and code review | Opus 5.5 | $0.30 to $0.40 |
| Builder, 1 to 3 rounds | Sonnet 5.5 | $0.20 to $0.50 |
| **Total** | | **about $1 to $1.50** |

| Cycles per day | Model spend per day | Per month |
|---|---|---|
| 12 | $12 to $18 | $360 to $540 |
| 24 | $24 to $36 | $720 to $1,080 |
| 48 | $48 to $72 | $1,440 to $2,160 |

Compute is free on your PC. A VPS with 8 to 16 cores would add roughly $40 to $100 per month. Data is free.

## 10. Build phases

| Phase | Days | Deliverable |
|---|---|---|
| 0 Setup | 1 | Python installed, project skeleton, API key configured, data download started (the download itself runs for hours) |
| 1 Data | 2 to 4 | Download, resample, Parquet store, quality report, spread and cost model, session calendar |
| 2 Engine | 4 to 6 | Backtester, prop-rule simulator, validation suite, leak-test harness, engine self-tests passing |
| 3 Agents | 3 to 4 | Orchestrator with the three roles, state database, buckets, budget caps, notifications; dry run on a few hand-written hypotheses |
| 4 Research | open | 24/7 loop; weekly review together of scrap lessons and candidates |
| 5 Forward test | 14 to 28 | Good basket runs on the firm's demo feed; go or no-go for the challenge |

## 11. Decisions needed from you

1. **Which prop firm, account size and phase?** Default until you say otherwise: FTMO-style, 10 percent target, 5 percent daily loss, 10 percent maximum loss, no time limit.
2. **Pairs.** Default: 28 majors and minors. Say if you want gold or indices.
3. **Timeframes.** Default: everything from 1-minute to daily. Expect the 1-minute and 3-minute ideas to die on costs; that is useful information, not a bug.
4. **Daily API budget cap.** Pick a number from the table above.
5. **Uptime.** Can this PC stay on 24/7? If not, a VPS.
6. **Forward-test account.** Do you have an MT5 demo with the firm's broker? It is needed for cost calibration and the forward test.
7. **Director model.** Fable as you asked, or Opus to cut spend by about a third.
8. **Permission to install Python 3.12** on this machine.

## 12. Machine prerequisites

| Check | Status on 2026-10-11 | Action |
|---|---|---|
| Python | Not installed (the `python` command is the Microsoft Store stub) | Install Python 3.12 from python.org or `winget install Python.Python.3.12` |
| Node | v24.18.1 present | Nothing; used for the Dukascopy downloader |
| Docker | Not installed | Not needed |
| Disk | D: 574 GB free, C: 234 GB free | Plenty, even keeping tick data for all 28 pairs |
| CPU and RAM | AMD Ryzen 9 5900X, 12 cores / 24 threads, 32 GB | Strong enough to run the whole research loop locally |
| Anthropic API key | Not yet configured | Needed for the 24/7 loop; billing must be enabled |
| Uptime | Unknown | PC stays on, or use a VPS |
