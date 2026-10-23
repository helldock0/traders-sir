"""System prompts, JSON schemas and context rendering for the three roles."""
from __future__ import annotations

import json
from pathlib import Path

from ..data import store
from ..engine import features, strategy

ROOT = store.ROOT

CHARTER = """# Programme charter (shared by every role)

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
"""


def strategy_contract() -> str:
    doc = (strategy.__doc__ or "").strip()
    feat = (features.__doc__ or "").strip()
    helpers = """
Helpers in edge.engine.features (import as `from edge.engine import features as F`):
  F.utc_dates(m) -> datetime64[D] per bar          F.minute_of_day_utc(m) -> int per bar
  F.weekday(dates) -> 0=Mon..6=Sun                 F.trading_days(m) -> (day_idx per bar, day dates)
  F.daily_bars(m) -> Daily(date, start_i, end_i, o, h, l, c, day_idx) with .to_bars(per_day_array)
  F.rolling_mean(x, n), F.shift(x, k)              F.atr_prev(daily, n=20), F.sma_prev(daily, n)   (known at day start)
  F.first_bar_at_or_after(m, dates, hh, mm) -> bar index per date (m.n if none)
  F.is_gotobi(dates), F.kth_last_weekday(dates), F.parse_hhmm("11:00")
  F.ext_series(m, name), F.ext_subset(m, name, mask), F.ext_asof(m, name, col), F.ext_recent(m, name, minutes, col=None),
  F.ext_minutes_since(m, name)   (external series: calendar, cot, vol; see below)

Market object `m` (numpy float64 arrays, all the same length m.n): m.ts (datetime64[us] UTC), m.bid_o, m.bid_h,
m.bid_l, m.bid_c, m.ask_o, m.ask_h, m.ask_l, m.ask_c, m.vol, m.quote_per_usd, m.pip, m.point, m.asset ('fx'|'metal'|'index'),
m.sym, m.tf. Bars are sparse: minutes without ticks do not exist, so never assume one bar per minute; use timestamps.

Execution rules (fixed, not configurable): orders placed at bar i close work from bar i+1; market fills at the next
open (ask for longs, bid for shorts) plus slippage; stop entries fill at max(level, open) (+slippage); limit entries at
min(level, open); on the entry bar only the stop can be hit; on later bars: gap through stop -> signal exit at open ->
time exit at open -> stop inside bar -> target inside bar (stop wins ties); longs exit on bid, shorts on ask; long and
short entries from the same bar are an OCO pair; an open position blocks new entries (one position at a time).
Break-even and trailing stops exist as run-level options (be_trigger_r, be_lock_r, trail_r) and are not part of Signals.

Auxiliary markets: when the hypothesis lists aux_markets (for example ["USATECHIDXUSD"] for a risk-off condition),
they are attached as m.aux[NAME] on the same timeframe and cut to the same horizon. Read them only through
F.aux_asof(m, NAME, col) (value of the last auxiliary bar closed by each primary bar's close) or
F.aux_window_change(m, NAME, start_hh, start_mm, end_hh, end_mm) (the auxiliary move inside a UTC window, known only
from the primary bars at or after the window end), or F.aux_market(m, NAME) with your own close-time logic. The leak
tests truncate and perturb auxiliary markets together with the primary one, so using a bar that has not closed yet is
caught like any other look-ahead.

External series: when the hypothesis lists ext_series (calendar, cot, vol, tfx, tfx_daily), they are attached as m.ext[name]
(an ExtSeries: .ts_avail per row, .column(col), .columns; see data/external/README.md for the columns). Read them
only through F.ext_asof(m, name, col) (value of the last row usable at each bar's close), F.ext_recent(m, name,
minutes, col=None) (a row became usable within the last `minutes`; or that row's value), F.ext_minutes_since(m, name),
and F.ext_subset(m, name, mask) (rows selected by a mask over e.column(...), for example high-impact USD releases;
the result can be passed to the same helpers). Rows are usable only from ts_avail; the leak tests cut the series
there and perturb its numbers beyond, so reading a release early is caught.

Coding rules for strategy modules: pure functions of (m, p); numpy and polars only (plus edge.engine.features);
no file, network or clock access; no randomness; deterministic; vectorised over bars (a Python loop over days or
events is fine, a loop over every bar is not); every tunable read from p[...]; PARAMS holds defaults and must contain
every key used in the grid; sl_dist must be > 0 wherever an entry is signalled; use closed-bar information only.
Define NAME (str), PARAMS (dict), optional GRID (dict of lists) and signals(m, p) -> Signals.
"""
    examples = ""
    for name in ("m3_usd_bid.py", "gotobi_short.py", "ext_surprise_follow_example.py"):
        path = ROOT / "strategies" / "oracle" / name
        if path.exists():
            examples += f"\n--- example strategy: strategies/oracle/{name} ---\n{path.read_text()}\n"
    return f"# Strategy contract\n\n{doc}\n\n{feat}\n{helpers}\n{examples}"


DIRECTOR_SYSTEM = CHARTER + """
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

Speed bar: the goal is a pass within 60 days, so judge every idea by avg R x sqrt(trades per month) after costs,
not by t alone. State the expected trades per month. A mechanism that fires twice a month needs +0.5 R per trade;
one that fires every day needs +0.15 R. The external series (calendar surprises, positioning, implied vol, TFX
retail flow) are the unexplored inputs; price, clock and calendar-date slices alone have been measured out, so a
hypothesis should condition on at least one external state unless its mechanism is genuinely new.

The quality of this programme is the quality of your hypotheses and your honesty about results.
"""

CRITIC_SYSTEM = CHARTER + """
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
"""

BUILDER_SYSTEM = CHARTER + """
# Your role: Builder

You turn an approved hypothesis into one strategy module that follows the strategy contract exactly and
is faithful to the rules as written. Write the complete file content. Prefer clarity to cleverness; put
helpers inside the module; vectorise over bars; loop over days or events only. Use the parameter names
given in the spec and read every tunable from p. Add a module docstring with the rules restated.
When you receive checker errors or Critic findings, fix exactly those and return the complete file again.
"""

DIRECTOR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "judgments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "decision": {"type": "string", "enum": ["promote", "scrap", "refine", "hold"]},
                    "lesson": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["slug", "decision", "lesson", "notes"],
                "additionalProperties": False,
            },
        },
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "snake_case, unique, <= 40 chars"},
                    "title": {"type": "string"},
                    "family": {"type": "string"},
                    "rationale": {"type": "string"},
                    "markets": {"type": "array", "items": {"type": "string"}},
                    "aux_markets": {"type": "array", "items": {"type": "string"},
                                    "description": "other instruments the signals condition on (read through F.aux_asof); empty if none"},
                    "ext_series": {"type": "array", "items": {"type": "string", "enum": ["calendar", "cot", "vol", "tfx", "tfx_daily"]},
                                   "description": "external series the signals condition on (calendar surprises, CFTC positioning, implied vol, TFX retail positioning weekly long/short or daily open interest; read through F.ext_asof / F.ext_recent); empty if none"},
                    "timeframe": {"type": "string", "enum": ["M1", "M3", "M5", "M15", "M30", "H1", "H2", "H3", "H4", "H8", "D1"]},
                    "rules": {"type": "string", "description": "entry, exit, stop, target, filters, times in UTC, exact formulas"},
                    "params": {"type": "object", "additionalProperties": {"type": ["number", "string", "boolean", "integer"]}},
                    "grid": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": ["number", "string", "boolean", "integer"]}}},
                    "stage_a_market": {"type": "string"},
                    "pre_registered": {
                        "type": "object",
                        "properties": {
                            "expected_design_t_min": {"type": "number"},
                            "expected_avg_r": {"type": "number"},
                            "min_trades_design_per_market": {"type": "integer"},
                            "expected_trades_per_month": {"type": "number", "description": "per market, after filters; with expected_avg_r it gives the speed score avg R x sqrt(trades per month)"},
                            "kill_if": {"type": "string"},
                        },
                        "required": ["expected_design_t_min", "expected_avg_r", "min_trades_design_per_market", "expected_trades_per_month", "kill_if"],
                        "additionalProperties": False,
                    },
                    "similar_prior": {"type": "array", "items": {"type": "string"}},
                    "why_different": {"type": "string"},
                    "parent_slug": {"type": ["string", "null"]},
                },
                "required": ["slug", "title", "family", "rationale", "markets", "aux_markets", "ext_series", "timeframe", "rules", "params", "grid",
                             "stage_a_market", "pre_registered", "similar_prior", "why_different", "parent_slug"],
                "additionalProperties": False,
            },
        },
        "direction_note": {"type": "string"},
    },
    "required": ["judgments", "hypotheses", "direction_note"],
    "additionalProperties": False,
}

CRITIC_REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["approve", "revise", "reject"]},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "revisions": {"type": "string"},
                    "overfit_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "cost_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "duplicate_of": {"type": ["string", "null"]},
                    "notes_for_builder": {"type": "string"},
                },
                "required": ["slug", "verdict", "reasons", "revisions", "overfit_risk", "cost_risk", "duplicate_of", "notes_for_builder"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reviews"],
    "additionalProperties": False,
}

CRITIC_CODE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "fix"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                    "where": {"type": "string"},
                    "issue": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["severity", "where", "issue", "fix"],
                "additionalProperties": False,
            },
        },
        "lookahead_risk": {"type": "string"},
        "matches_rules": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["verdict", "issues", "lookahead_risk", "matches_rules", "notes"],
    "additionalProperties": False,
}

BUILDER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "complete Python module"},
        "notes": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["code", "notes", "assumptions"],
    "additionalProperties": False,
}


def render_scrap(entries: list[dict]) -> str:
    if not entries:
        return "(empty)"
    lines = []
    for e in entries:
        lesson = (e.get("lesson") or "").strip().replace("\n", " ")
        lines.append(f"- {e['slug']} [{e.get('family') or ''}] {e['title']}: {lesson}")
    return "\n".join(lines)


def render_bucket(entries: list[dict]) -> str:
    if not entries:
        return "(empty)"
    return "\n".join(f"- {e['slug']}: {e['title']} (status {e['status']}; report {e.get('report_path') or 'n/a'})" for e in entries)


def report_digest(report: dict, max_chars: int = 6000) -> str:
    """Compact digest of a pipeline report for the Director (holdout numbers are never present)."""
    out = [f"## {report['slug']}: verdict {report['verdict']}; failing {report.get('failing')}; soft failures {report.get('soft_failures', [])}",
           f"gates: {report.get('gates')}", f"warnings: {report.get('warnings')}", f"pooled: {report.get('pooled')}"]
    c = report.get("stages", {}).get("C", {})
    for sym, d in c.items():
        st = d["stats"]
        out.append(f"{sym} params {d['params']}: design n {st['design']['n']} avg {st['design']['avg_r']:.3f} t {st['design']['t']:.2f}; "
                   f"check n {st['check']['n']} avg {st['check']['avg_r']:.3f} t {st['check']['t']:.2f}; "
                   f"WF oos avg {d['walk_forward']['oos_avg_r']:.3f} (windows + {d['walk_forward']['windows_positive']}/{d['walk_forward']['windows_total']}); "
                   f"stability {d['stability']['neighbours_positive']}/{d['stability']['neighbours']}; "
                   f"cost x1.5 {next(x['avg_r'] for x in d['cost_stress'] if x['mult'] == 1.5):.3f}, x2 {next(x['avg_r'] for x in d['cost_stress'] if x['mult'] == 2.0):.3f}; "
                   f"DSR hyp {d['dsr_hypothesis']['dsr']:.2f} prog {d['dsr_program']['dsr']:.2f}; years + {d['regime']['positive_years']}/{d['regime']['years']}; "
                   f"R by year {d['by_year']}")
    a = report.get("stages", {}).get("A")
    if a and not c:
        out.append(f"stage A best: {a.get('best')}")
    b = report.get("stages", {}).get("B")
    if b and not c:
        out.append("stage B best per market: " + "; ".join(f"{s}: {d['best'] and {k: d['best'][k] for k in ('design_n', 'design_avg_r', 'design_t')}}" for s, d in b.items()))
    text = "\n".join(out)
    return text[:max_chars]


def render_director_user(overview: dict, scrap: list[dict], candidates: list[dict], good: list[dict],
                         pending_reports: list[dict], datafacts_md: str, cycle: int, recent_lessons: list[str]) -> str:
    parts = [f"# Cycle {cycle}", f"State: {json.dumps(overview)}", "",
             "# Candidates awaiting your judgment (reports below)", render_bucket(candidates), "",
             "# Good bucket (passed the holdout)", render_bucket(good), "",
             "# Reports finished since your last turn"]
    parts += [report_digest(r) for r in pending_reports] or ["(none)"]
    parts += ["", "# Scrap index (do not re-test; build on only with a different mechanism)", render_scrap(scrap), "",
              "# Market facts", datafacts_md, "",
              "# Recent lessons", "\n".join(f"- {x}" for x in recent_lessons) or "(none)", "",
              "Return your judgments for every candidate and every finished report listed above, then one to three "
              "new pre-registered hypotheses, then a short direction note."]
    return "\n".join(parts)


def render_critic_review_user(hypotheses: list[dict], scrap: list[dict], datafacts_md: str) -> str:
    return "\n".join(["# Hypotheses to review", json.dumps(hypotheses, indent=1), "",
                      "# Scrap index", render_scrap(scrap), "", "# Market facts", datafacts_md, "",
                      "Review each hypothesis. Approve only what deserves compute."])


def render_builder_user(hyp: dict, critic_notes: str, feedback: str | None = None, previous_code: str | None = None) -> str:
    keys = [k for k in ("slug", "title", "rationale", "markets", "aux_markets", "ext_series", "timeframe", "rules", "params", "grid") if k in hyp]
    parts = ["# Hypothesis", json.dumps({k: hyp[k] for k in keys}, indent=1),
             "", "# Critic notes for the builder", critic_notes or "(none)", "",
             f"Module requirements: NAME = \"{hyp['slug']}\"; PARAMS must contain these keys with these defaults: {json.dumps(hyp['params'])}; "
             f"GRID = {json.dumps(hyp['grid'])}; signals(m, p) -> Signals. Markets: {hyp['markets']} on {hyp['timeframe']} bars. "
             f"Auxiliary markets attached as m.aux: {hyp.get('aux_markets') or 'none'}. External series attached as m.ext: {hyp.get('ext_series') or 'none'}."]
    if previous_code:
        parts += ["", "# Your previous module", previous_code]
    if feedback:
        parts += ["", "# Feedback to address", feedback]
    parts += ["", "Return the complete module."]
    return "\n".join(parts)


def render_critic_code_user(hyp: dict, code: str, checker: dict) -> str:
    keys = [k for k in ("slug", "title", "rules", "params", "grid", "markets", "aux_markets", "ext_series", "timeframe") if k in hyp]
    return "\n".join(["# Hypothesis", json.dumps({k: hyp[k] for k in keys}, indent=1),
                      "", "# Builder module", code, "", "# Automated checker results", json.dumps(checker, indent=1, default=str), "",
                      "Review the module against the rules and the strategy contract."])
