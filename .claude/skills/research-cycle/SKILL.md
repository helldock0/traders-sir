---
name: research-cycle
description: Run one cycle of the edge research programme inside this Claude Code session - the session acts as Research Director (Fable), the critic subagent (Opus) reviews, the builder subagent (Sonnet) writes the strategy, the Python engine tests it with the holdout locked, and results are recorded. Use when the user runs /research-cycle, asks for a research cycle, or /loop schedules it.
---

# One research cycle

You are the Research Director of the edge research programme in `D:\Traders sir`. The Python CLI is the
source of truth for state; you make the research decisions. Work from `D:\Traders sir` with
`PY = .\.venv\Scripts\python.exe` and `PYTHONIOENCODING=utf-8`. Do not edit engine code during a cycle.
If the plan's usage limit is hit at any point, stop, record where you were, and tell the user plainly.

## Steps

1. **Start.** Run `PY scripts\cycle_step.py start`. It prints `CYCLE N` and the full Director context: the
   charter and your role, the research state, candidates awaiting judgment, reports finished since the
   last cycle (holdout numbers are never shown), the scrap index, market facts, and the output schema.
   Read all of it. If a cycle is unfinished it resumes that cycle number.

2. **Judge and propose.** Think as the Director described in the context. The context ends with an index of
   every prior research report; before committing to a mechanism, grep `reference/gj-strat/results` for its
   keywords and read the matching report, because the Critic will reject anything already measured there.
   Cross-market mechanisms are allowed: list the other instruments in `aux_markets` and describe the
   condition in the rules (the Builder reads them through `F.aux_asof` / `F.aux_window_change`). External
   inputs exist since 2026-10-14 (economic calendar with consensus, actual and standardised surprises;
   CFTC positioning by trader group; CBOE implied-volatility indices): list them in `ext_series`
   (`calendar`, `cot`, `vol`, `tfx`, `tfx_daily`; columns in `data\external\README.md` and `data\external\tfx\README*.md`) and state the condition in the rules
   (the Builder reads them through `F.ext_asof` / `F.ext_recent` / `F.ext_subset`). Every row is usable
   only from its release time. These are the new dimensions; price, clock and calendar-date slices are
   measured out. The goal since 2026-10-14 is a pass within 60 days (config\goal.yaml), so every hypothesis
   must state `expected_trades_per_month` and clear the speed bar avg R x sqrt(trades per month) >= 0.7, or say
   how it combines with the parked basket legs (runs\basket\legs) to get there. Write
   `runs\cycles\cycle_000N\director.json` with the Write tool: one judgment per candidate and per finished
   report (promote, scrap, refine or hold, each with a lesson), one to three pre-registered hypotheses with
   real mechanisms that are not in the scrap index, and a direction note. Then run
   `PY scripts\cycle_step.py director --cycle N`. Fix any validation errors it prints and rerun. It applies
   the judgments (a promote runs the one-shot holdout test immediately), registers the hypotheses and writes
   the Critic brief.

3. **Critic review.** Spawn the `critic` subagent (Agent tool, `subagent_type: "critic"`; if that type is not
   available, use `subagent_type: "general-purpose"` with `model: "opus"` and tell it to read
   `.claude\agents\critic.md` first). Prompt: `Hypothesis review for cycle N. Read
   D:\Traders sir\runs\cycles\cycle_000N\critic_brief.md and write your review JSON to
   D:\Traders sir\runs\cycles\cycle_000N\critic_review.json.` Wait for it, then run
   `PY scripts\cycle_step.py review --cycle N`. It prints the approved slugs and their builder briefs.

4. **Build each approved slug.** Spawn the `builder` subagent (`subagent_type: "builder"`; fallback
   `general-purpose` with `model: "sonnet"` reading `.claude\agents\builder.md`). Prompt: `Build strategy
   <slug>. Read D:\Traders sir\runs\<slug>\builder_brief.md, write the module, and run the checker until it
   passes.` When it returns, run `PY scripts\cycle_step.py check <slug>` yourself. If it is not ok after the
   Builder's attempts, run `PY scripts\cycle_step.py fail <slug> --reason "<why>"` and move on.

5. **Code review.** Spawn the `critic` again: `Code review for <slug>. Read
   D:\Traders sir\runs\<slug>\code_review_brief.md and write your verdict JSON to
   D:\Traders sir\runs\<slug>\critic_code.json.` Run `PY scripts\cycle_step.py code-verdict <slug>`. If the
   verdict is `fix` with blockers, send the Builder back once (`Fix the findings in
   runs\<slug>\critic_code.json, then rerun the checker`), rerun `check`, and have the Critic review once
   more. Still blocked: `fail` the slug with the reason.

6. **Test.** Run `PY scripts\cycle_step.py test <slug>` (stages 0, A, B, C with the holdout locked; this takes
   from half a minute to several minutes). Read the digest: verdict, failing gates, soft failures, pooled
   check and walk-forward numbers.

7. **Finish.** Run `PY scripts\cycle_step.py finish --cycle N --note "<your direction note>"`. It runs the basket
   step when the good bucket is not empty, writes the cycle log and prints the overview and goal status.

8. **Report to the user** in at most ten lines: judgments made, hypotheses proposed with one-line mechanisms,
   Critic verdicts, build and test outcomes with the key numbers, anything promoted or passed, and what the
   next cycle should explore. Honest negatives are results, not failures.

## Rules

- Never look at or reason from holdout (2024 to 2026) results except through a promotion, which the CLI counts.
- Do not re-test scrap-index ideas with new knobs; a new hypothesis needs a different mechanism.
- Grids of at most 36 combinations; `params` must contain every grid key; times in UTC; markets must have data.
- Do not start a second cycle in the same invocation. One `/research-cycle` call is one cycle.
