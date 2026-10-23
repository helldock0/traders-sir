# Edge research system

Autonomous strategy research for the Alpha Capital "Alpha Swing" $10k challenge. Three models decide,
a Python engine computes:

| Role | Model | Job |
|---|---|---|
| Research Director | Claude Fable 5.1 | judges finished reports, proposes pre-registered hypotheses |
| Critic | Claude Opus 5.5 | rejects weak hypotheses before compute; reviews strategy code for look-ahead and rule mismatches |
| Builder | Claude Sonnet 5.5 | writes the strategy module, fixes checker and Critic findings |
| Engine | Python (polars, numpy, numba) | data store, backtests, leak tests, walk-forward, stress, Monte Carlo, prop simulation |

Plan and design: [PLAN.md](PLAN.md). Current state and next steps: [STATUS.md](STATUS.md).

## Layout

```
config/        universe.yaml (symbols, splits), prop_firms.yaml (rule profiles), goal.yaml, prior_scrap.yaml
data/          m1/<SYM>.parquet (bid+ask 1-minute), tf/<SYM>_<TF>.parquet, raw/bi5 (Dukascopy day files), rates/, reports/
data/external  calendar / cot / vol / tfx parquet tables with ts_avail (release time) + README.md; raw downloads per source
edge/data      Dukascopy downloader + decoder, store, ingest, resample, quality
edge/engine    market loader, strategy contract (Signals), numba executor, costs, stats, features, external series, prop simulator, backtest
edge/research  leak tests, validation gates, staged pipeline, datafacts, portfolio/baskets, research state (SQLite)
edge/agents    LLM wrapper, prompts and schemas, code checker, roles, research loop
strategies/    oracle/ (replications of known trades), auto/ (written by the Builder)
specs/         hypothesis specs (JSON); specs/auto/ written by the loop
runs/          research.sqlite, <slug>/report.md + report.json + trades, cycles/, basket/ (legs, sizing_report.md), datafacts.md
scripts/       build_store, dukascopy_download, build_external, basket_legs, basket_sizing, run_backtest, run_pipeline, run_loop, seed_scrap
reference/     read-only clones: gj-strat (datastore + prior alpha hunt), trade-research
tests/         pytest suite (executor rules, prop rules, leak tests, checker, one dry-run cycle)
```

## Setup

```powershell
uv sync --extra dev                       # Python 3.12 environment in .venv
copy .env.example .env                    # then put ANTHROPIC_API_KEY in .env
```

## Data

```powershell
.\.venv\Scripts\python.exe scripts\build_store.py all          # extract gj-strat tars, build M1, resample, quality report
.\.venv\Scripts\python.exe scripts\dukascopy_download.py --symbols indices --start 2011-09-18   # paced raw downloads
.\.venv\Scripts\python.exe scripts\build_store.py build-m1 --symbols USA500IDXUSD && ... resample --symbols USA500IDXUSD
```

Dukascopy throttles hard; the downloader paces requests and resumes. Quality report: `data/reports/m1_quality.md`.

External inputs (economic calendar with consensus, actual and standardised surprises; CFTC positioning by trader group;
CBOE implied-volatility indices; TFX retail positioning) are built by `scripts\build_external.py` and
`scripts\build_external_tfx.py` into `data\external\*.parquet`, each row stamped with `ts_avail`, the time from which
it may be used. Sources, validation and columns: `data\external\README.md`.

## Backtests and the pipeline

```powershell
.\.venv\Scripts\python.exe scripts\run_backtest.py strategies\oracle\m3_usd_bid.py --symbols USDJPY --tf M1
.\.venv\Scripts\python.exe scripts\run_pipeline.py specs\oracle_m3_usd_bid.json --no-state     # stages 0, A, B, C
.\.venv\Scripts\python.exe scripts\run_pipeline.py specs\oracle_m3_usd_bid.json --locked       # the one-shot holdout
.\.venv\Scripts\python.exe -m pytest -q
```

A strategy is a module with `NAME`, `PARAMS`, optional `GRID` and `signals(m, p) -> Signals`
(see `edge/engine/strategy.py` and the examples in `strategies/oracle/`). Signals are decided at bar
close and executed from the next bar; the executor's fill rules are documented in `edge/engine/executor.py`.
Cross-market conditions use auxiliary markets: list them in the hypothesis as `aux_markets`, and read them
in the module through `F.aux_asof(m, NAME)` or `F.aux_window_change(...)`; the leak tests cover them. External
series work the same way: list `ext_series` (`calendar`, `cot`, `vol`, `tfx`), attached as `m.ext[name]`, read through
`F.ext_asof`, `F.ext_recent`, `F.ext_subset` and `F.ext_minutes_since`; the leak tests cut them at `ts_avail`, perturb
them beyond, and add cuts just before releases. Example: `strategies/oracle/ext_surprise_follow_example.py`.

## Basket sizing

`scripts\basket_legs.py` rebuilds the approved gj-strat USDJPY legs (vol-box, vol-gotobi, fade, M-3) from the local store
with the gj-strat engine and adds each trade's worst excursion; `scripts\basket_sizing.py` runs the pre-registered risk grid,
stresses and a year-block bootstrap under the Alpha Swing rules and writes `runs\basket\sizing_report.md`.

`runs/reference_index.md` (from `scripts/build_reference_index.py`) lists every prior report in `reference/`
and is shown to the Director and Critic each cycle so measured ideas are not proposed again.

## Running the research loop

Each cycle: Director judges candidates and finished reports, proposes 1-3 hypotheses -> Critic approves,
revises or rejects -> Builder writes the module -> checker (imports, parameter wiring, truncation and
perturbation leak tests) -> Critic code review -> staged pipeline with the holdout locked -> candidate or
scrap, with a lesson. Promotion runs the holdout once; passes go to the good bucket; the basket step
sizes combinations under the prop rules and writes `runs/basket/`.

### Option A: inside Claude Code on your subscription (current)

The Claude Code session is the Director (Fable). `.claude/agents/critic.md` (Opus) and
`.claude/agents/builder.md` (Sonnet) are the subagents; `.claude/skills/research-cycle/SKILL.md` is the
procedure, driven by `scripts/cycle_step.py` (start, director, review, check, code-verdict, test, finish).

```
/research-cycle                 # one cycle, in a Claude Code session opened in D:\Traders sir
/loop 2h /research-cycle        # repeat while the session stays open; plan limits pause it when hit
```

Agent files are loaded when a session starts, so open a fresh session after changing them. Regenerate them
from the prompts with `scripts\export_agents.py`. Throughput is bounded by the plan's five-hour and weekly
limits, and the session must stay open.

### Option B: standalone 24/7 script on an API key

```powershell
copy .env.example .env                                     # set ANTHROPIC_API_KEY (prepaid API credits)
.\.venv\Scripts\python.exe scripts\run_loop.py --max-cycles 1
.\scripts\start_loop.ps1                                   # restart-safe, runs until runs\PAUSE or runs\GOAL_REACHED
```

Both options share the same state database, pipeline and buckets. Spend of the API path is recorded per
call in `runs/research.sqlite` (table `spend`). Create `runs/PAUSE` to stop the script loop after the
current step. Seed the scrap index once with `scripts\seed_scrap.py` (already done).
