"""Research-cycle steps as plain functions over the state database.

Used by scripts/cycle_step.py, which the Claude Code skill `/research-cycle` drives: the Claude Code
session acts as Research Director, Critic and Builder run as subagents, and this module keeps the
bookkeeping deterministic. The API loop (loop.py) shares the judgment logic.

Cycle files: runs/cycles/cycle_<n>/ (context.md, director.json, hypotheses.json, critic_brief.md,
critic_review.json) and runs/cycles/cycle_<n>.json once finished. Per hypothesis: runs/<slug>/
(hypothesis.json, builder_brief.md, checker.json, code_review_brief.md, critic_code.json, report.*).
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path

from ..data import store
from ..data.universe import ALL_SYMBOLS
from ..engine.backtest import get_market
from ..engine.external import EXT_DIR, KNOWN as EXT_KNOWN
from ..research import datafacts, portfolio
from ..research.pipeline import HypothesisSpec, holdout_start, run_locked_test, run_pipeline
from ..research.state import ResearchState
from . import prompts
from .codecheck import full_check

log = logging.getLogger(__name__)

RUNS = store.ROOT / "runs"
CYCLES = RUNS / "cycles"
AUTO_SPECS = store.ROOT / "specs" / "auto"
AUTO_STRATS = store.ROOT / "strategies" / "auto"
TIMEFRAMES = {"M1", "M3", "M5", "M15", "M30", "H1", "H2", "H3", "H4", "H8", "D1"}
MAX_GRID = 36


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_")
    return s[:40] or "hyp"


def notify(text: str) -> None:
    """Telegram message if configured; always logged."""
    log.info("NOTIFY: %s", text)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            import httpx
            httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": text[:3900]}, timeout=20)
        except Exception as exc:  # notifications must never stop research
            log.warning("telegram failed: %s", exc)


# ---------------------------------------------------------------- cycle bookkeeping
def cycle_dir(n: int) -> Path:
    d = CYCLES / f"cycle_{n:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def next_cycle_number() -> int:
    CYCLES.mkdir(parents=True, exist_ok=True)
    finished = {int(p.stem.split("_")[1]) for p in CYCLES.glob("cycle_*.json")}
    started = {int(p.name.split("_")[1]) for p in CYCLES.glob("cycle_*") if p.is_dir()}
    unfinished = sorted(started - finished)
    if unfinished:
        return unfinished[-1]
    return (max(finished | started) + 1) if (finished | started) else 1


def external_md() -> str:
    path = EXT_DIR / "README.md"
    return path.read_text(encoding="utf-8") if path.exists() else "(no external series built; run scripts/build_external.py)"


def datafacts_md() -> str:
    path = RUNS / "datafacts.md"
    if not path.exists():
        datafacts.build()
    return path.read_text(encoding="utf-8")


def reference_index_md() -> str:
    """Index of every prior research report (gj-strat, trade-research); built by scripts/build_reference_index.py."""
    path = RUNS / "reference_index.md"
    if not path.exists():
        return ("# Prior research reports\n(index missing: run scripts/build_reference_index.py; meanwhile grep "
                "reference/gj-strat/results/*/REPORT.md for the mechanism's keywords before proposing)\n")
    return path.read_text(encoding="utf-8")


def pending_reports(state: ResearchState) -> list[dict]:
    out = []
    for h in state.hypotheses():
        if h["status"] in ("candidate", "scrap") and h.get("report_path") and not (h.get("critic_verdict") or "").startswith("director:"):
            rp = Path(h["report_path"]).with_suffix(".json")
            if rp.exists():
                try:
                    out.append(json.loads(rp.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
    return out


def director_context(state: ResearchState, cycle: int) -> str:
    scrap = state.scrap_index()
    candidates = state.hypotheses("candidate")
    good = state.bucket("good")
    pending = pending_reports(state)
    lessons = [h["lesson"] for h in state.hypotheses() if h.get("lesson") and h.get("cycle") and h["cycle"] >= max(1, cycle - 3)]
    user = prompts.render_director_user(state.overview(), scrap, candidates, good, pending, datafacts_md() + "\n\n" + external_md(), cycle, lessons[-12:])
    user += "\n\n" + reference_index_md()
    text = (prompts.DIRECTOR_SYSTEM + "\n\n" + user + "\n\n# Output\nWrite a JSON object matching this schema to "
            f"runs/cycles/cycle_{cycle:04d}/director.json, then run `cycle_step.py director --cycle {cycle}`.\n"
            "Every candidate and every finished report above needs a judgment. 1 to 3 hypotheses; grids of at most 36 combinations; "
            "params must contain every grid key; times in UTC.\n\n```json\n" + json.dumps(prompts.DIRECTOR_SCHEMA, indent=1) + "\n```\n")
    d = cycle_dir(cycle)
    (d / "context.md").write_text(text, encoding="utf-8")
    (d / "scrap.md").write_text(prompts.render_scrap(scrap), encoding="utf-8")
    return text


# ---------------------------------------------------------------- director
def validate_director(data: dict) -> list[str]:
    errs = []
    if not isinstance(data, dict):
        return ["director.json must be a JSON object"]
    for key in ("judgments", "hypotheses", "direction_note"):
        if key not in data:
            errs.append(f"missing key {key}")
    hyps = data.get("hypotheses") or []
    if len(hyps) > 3:
        errs.append("more than 3 hypotheses")
    for i, h in enumerate(hyps):
        tag = f"hypotheses[{i}]"
        for key in ("slug", "title", "family", "rationale", "markets", "timeframe", "rules", "params", "grid", "stage_a_market", "pre_registered"):
            if key not in h:
                errs.append(f"{tag}: missing {key}")
        if h.get("timeframe") not in TIMEFRAMES:
            errs.append(f"{tag}: timeframe must be one of {sorted(TIMEFRAMES)}")
        grid = h.get("grid") or {}
        params = h.get("params") or {}
        combos = 1
        for k, vals in grid.items():
            if not isinstance(vals, list) or not vals:
                errs.append(f"{tag}: grid[{k}] must be a non-empty list")
                continue
            combos *= len(vals)
            if k not in params:
                errs.append(f"{tag}: params lacks grid key {k}")
        if combos > MAX_GRID:
            errs.append(f"{tag}: grid has {combos} combinations (max {MAX_GRID})")
        for key in ("markets", "aux_markets"):
            syms = h.get(key) or []
            unknown = [m for m in syms if m.upper() not in ALL_SYMBOLS]
            if unknown:
                errs.append(f"{tag}: unknown {key} {unknown}")
            missing_data = [m for m in syms if m.upper() in ALL_SYMBOLS and not store.m1_path(m).exists()]
            if missing_data:
                errs.append(f"{tag}: no data yet for {key} {missing_data}")
        ext = h.get("ext_series") or []
        bad = [e for e in ext if str(e).lower() not in EXT_KNOWN]
        if bad:
            errs.append(f"{tag}: unknown ext_series {bad} (known: {list(EXT_KNOWN)})")
        missing_ext = [e for e in ext if str(e).lower() in EXT_KNOWN and not (EXT_DIR / f"{str(e).lower()}.parquet").exists()]
        if missing_ext:
            errs.append(f"{tag}: external series not built yet {missing_ext} (scripts/build_external.py)")
        pr = h.get("pre_registered") or {}
        for key in ("expected_design_t_min", "expected_avg_r", "min_trades_design_per_market", "kill_if"):
            if key not in pr:
                errs.append(f"{tag}: pre_registered lacks {key}")
    return errs


def apply_judgments(state: ResearchState, judgments: list[dict], cycle: int) -> list[str]:
    events = []
    by_slug = {h["slug"]: h for h in state.hypotheses()}
    for j in judgments:
        h = by_slug.get(j.get("slug", ""))
        if h is None:
            events.append(f"{j.get('slug')}: unknown slug, ignored")
            continue
        hid = h["id"]
        decision = j.get("decision", "hold")
        state.add_verdict(hid, "director", decision, j.get("notes", ""))
        if decision == "promote" and h["status"] == "candidate":
            spec_path = AUTO_SPECS / f"{h['slug']}.json"
            rep_path = Path(h["report_path"]).with_suffix(".json") if h.get("report_path") else None
            if not spec_path.exists() or rep_path is None or not rep_path.exists():
                events.append(f"{h['slug']}: promote requested but spec or report missing")
                continue
            spec = HypothesisSpec.from_json(spec_path)
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
            chosen = {sym: d["params"] for sym, d in rep.get("stages", {}).get("C", {}).items()}
            out = run_locked_test(spec, chosen, state, hid)
            status = "good" if out["passed"] else "scrap"
            state.update_hypothesis(hid, status=status, bucket=status, lesson=j.get("lesson", ""), critic_verdict=f"director:promote->{status}")
            msg = f"LOCKED TEST {h['slug']}: {'PASSED' if out['passed'] else 'failed'}; pooled holdout {out['pooled_holdout']}"
            notify(msg)
            events.append(msg)
        elif decision == "scrap":
            state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson=j.get("lesson", ""), critic_verdict="director:scrap")
            events.append(f"{h['slug']}: scrapped by director")
        elif decision == "hold":
            state.update_hypothesis(hid, critic_verdict="director:hold", lesson=j.get("lesson") or h.get("lesson") or "")
            events.append(f"{h['slug']}: held")
        else:
            state.update_hypothesis(hid, critic_verdict="director:refine", lesson=j.get("lesson") or h.get("lesson") or "")
            events.append(f"{h['slug']}: refinement requested")
    return events


def apply_director(state: ResearchState, cycle: int, data: dict) -> dict:
    d = cycle_dir(cycle)
    events = apply_judgments(state, data.get("judgments", []), cycle)
    judged = {j.get("slug") for j in data.get("judgments", [])}
    for h in state.hypotheses():
        if h["slug"] in judged and not (h.get("critic_verdict") or "").startswith("director:"):
            state.update_hypothesis(h["id"], critic_verdict="director:seen")
    existing = {h["slug"] for h in state.hypotheses()}
    registered = []
    for hyp in data.get("hypotheses", [])[:3]:
        hyp = dict(hyp)
        slug = slugify(hyp["slug"])
        if slug in existing:
            for k in itertools.count(2):
                if f"{slug}_{k}" not in existing:
                    slug = f"{slug}_{k}"
                    break
        hyp["slug"] = slug
        hyp["markets"] = [m.upper() for m in hyp["markets"]]
        hyp["aux_markets"] = [m.upper() for m in (hyp.get("aux_markets") or [])]
        hyp["ext_series"] = [str(e).lower() for e in (hyp.get("ext_series") or [])]
        hyp["stage_a_market"] = hyp.get("stage_a_market", hyp["markets"][0]).upper()
        hid = state.add_hypothesis(slug, hyp["title"], hyp["family"], hyp["rationale"], hyp, cycle=cycle)
        state.update_hypothesis(hid, status="proposed")
        folder = RUNS / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "hypothesis.json").write_text(json.dumps(hyp, indent=1), encoding="utf-8")
        registered.append(hyp)
        existing.add(slug)
    (d / "hypotheses.json").write_text(json.dumps(registered, indent=1), encoding="utf-8")
    brief = (prompts.CRITIC_SYSTEM + "\n\n" + prompts.render_critic_review_user(registered, state.scrap_index(), datafacts_md() + "\n\n" + external_md())
             + "\n\n" + reference_index_md()
             + f"\n\n# Output\nWrite a JSON object matching this schema to runs/cycles/cycle_{cycle:04d}/critic_review.json "
             "(one review per hypothesis, same slugs).\n\n```json\n" + json.dumps(prompts.CRITIC_REVIEW_SCHEMA, indent=1) + "\n```\n")
    (d / "critic_brief.md").write_text(brief, encoding="utf-8")
    (d / "director_events.json").write_text(json.dumps(events, indent=1), encoding="utf-8")
    return {"events": events, "hypotheses": [h["slug"] for h in registered], "critic_brief": str(d / "critic_brief.md"),
            "critic_review_path": str(d / "critic_review.json")}


# ---------------------------------------------------------------- critic review
def validate_review(data: dict, expected_slugs: list[str]) -> list[str]:
    errs = []
    reviews = data.get("reviews") if isinstance(data, dict) else None
    if not isinstance(reviews, list):
        return ["critic_review.json must contain a 'reviews' list"]
    seen = set()
    for r in reviews:
        if r.get("verdict") not in ("approve", "revise", "reject"):
            errs.append(f"{r.get('slug')}: verdict must be approve, revise or reject")
        seen.add(r.get("slug"))
    for s in expected_slugs:
        if s not in seen:
            errs.append(f"no review for {s}")
    return errs


def builder_brief(hyp: dict, review: dict) -> str:
    slug = hyp["slug"]
    notes = (review.get("notes_for_builder") or "") + (("\nRevisions required: " + review["revisions"]) if review.get("revisions") else "")
    keys = [k for k in ("slug", "title", "family", "rationale", "markets", "aux_markets", "ext_series", "timeframe", "rules", "params", "grid", "stage_a_market") if k in hyp]
    aux = hyp.get("aux_markets") or []
    ext = hyp.get("ext_series") or []
    return "\n".join([
        f"# Builder brief: {slug}", "",
        "Write the strategy module to `strategies/auto/" + slug + ".py` (create or overwrite that file only).", "",
        "## Hypothesis", json.dumps({k: hyp[k] for k in keys}, indent=1), "",
        "## Critic notes", notes or "(none)", "",
        "## Requirements",
        f"- `NAME = \"{slug}\"`; `PARAMS` must contain exactly these defaults (more keys are fine): {json.dumps(hyp['params'])}",
        f"- `GRID = {json.dumps(hyp['grid'])}`",
        f"- Markets: {hyp['markets']} on {hyp['timeframe']} bars. Primary market for checks: {hyp['stage_a_market']}.",
        (f"- Auxiliary markets attached as m.aux: {aux}. Read them only through F.aux_asof / F.aux_window_change / F.aux_market "
         f"(see the strategy contract); they are cut to the same horizon and covered by the leak tests." if aux else
         "- No auxiliary markets: use only m's own bars."),
        (f"- External series attached as m.ext: {ext}. Read them only through F.ext_asof / F.ext_recent / F.ext_subset / "
         f"F.ext_minutes_since (see the strategy contract); columns are listed in data/external/README.md; rows are usable "
         f"only from their ts_avail and the leak tests cover them." if ext else "- No external series."),
        "- Follow the strategy contract in your instructions (closed-bar information only, sl_dist > 0 on every entry, sparse bars, p[...] for every tunable).",
        "- Restate the rules in the module docstring.", "",
        "## Checker",
        f"Run `.\\.venv\\Scripts\\python.exe scripts\\cycle_step.py check {slug}` from D:\\Traders sir after writing the file. "
        "It imports the module, runs it on the primary market, checks that every grid parameter changes the signals, and runs the "
        "look-ahead tests. Fix and rerun until it prints ok=true (at most 3 attempts). Do not edit any file other than your module.",
    ])


def apply_review(state: ResearchState, cycle: int, data: dict) -> dict:
    d = cycle_dir(cycle)
    hyps = {h["slug"]: h for h in json.loads((d / "hypotheses.json").read_text(encoding="utf-8"))}
    by_slug = {h["slug"]: h for h in state.hypotheses()}
    approved, rejected = [], []
    for r in data.get("reviews", []):
        slug = r.get("slug")
        if slug not in hyps or slug not in by_slug:
            continue
        hid = by_slug[slug]["id"]
        reasons = "; ".join(r.get("reasons", []))
        state.add_verdict(hid, "critic", r["verdict"], json.dumps(r)[:3000])
        if r["verdict"] == "reject":
            state.update_hypothesis(hid, status="rejected", bucket="scrap", critic_verdict="reject", critic_notes=reasons,
                                    lesson=("rejected by critic: " + reasons)[:600])
            rejected.append(slug)
            continue
        hyp = hyps[slug]
        state.update_hypothesis(hid, status="building", critic_verdict=r["verdict"], critic_notes=reasons)
        spec = HypothesisSpec(slug=slug, title=hyp["title"], family=hyp["family"], rationale=hyp["rationale"], markets=hyp["markets"],
                              timeframe=hyp["timeframe"], strategy_path=str(Path("strategies") / "auto" / f"{slug}.py"),
                              params=hyp["params"], grid=hyp["grid"], stage_a={"market": hyp["stage_a_market"]},
                              pre_registered=hyp["pre_registered"], notes=hyp.get("rules", ""),
                              aux_markets=list(hyp.get("aux_markets") or []), ext_series=list(hyp.get("ext_series") or []))
        AUTO_SPECS.mkdir(parents=True, exist_ok=True)
        spec.to_json(AUTO_SPECS / f"{slug}.json")
        (RUNS / slug / "builder_brief.md").write_text(builder_brief(hyp, r), encoding="utf-8")
        (RUNS / slug / "critic_review.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
        approved.append(slug)
    return {"approved": approved, "rejected": rejected,
            "briefs": {s: str(RUNS / s / "builder_brief.md") for s in approved}}


# ---------------------------------------------------------------- builder checks and critic code review
def check(state: ResearchState, slug: str) -> dict:
    hyp = json.loads((RUNS / slug / "hypothesis.json").read_text(encoding="utf-8"))
    path = AUTO_STRATS / f"{slug}.py"
    if not path.exists():
        return {"ok": False, "error": f"{path} does not exist"}
    code = path.read_text(encoding="utf-8")
    m = get_market(hyp["stage_a_market"], hyp["timeframe"], end=holdout_start(),
                   aux=tuple(hyp.get("aux_markets") or ()), ext=tuple(hyp.get("ext_series") or ()))   # never holdout bars
    result, mod, _ = full_check(code, slug, hyp["params"], hyp["grid"], m)
    (RUNS / slug / "checker.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    brief = (prompts.CRITIC_SYSTEM + "\n\n" + prompts.strategy_contract() + "\n\n"
             + prompts.render_critic_code_user(hyp, code, result)
             + f"\n\n# Output\nWrite a JSON object matching this schema to runs/{slug}/critic_code.json.\n\n```json\n"
             + json.dumps(prompts.CRITIC_CODE_SCHEMA, indent=1) + "\n```\n")
    (RUNS / slug / "code_review_brief.md").write_text(brief, encoding="utf-8")
    summary = {"ok": result["ok"], "static": result["static"], "import_ok": (result.get("import") or {}).get("ok"),
               "import_error": (result.get("import") or {}).get("error"),
               "dynamic_issues": ((result.get("dynamic") or {}).get("issues")), "entries": ((result.get("dynamic") or {}).get("entries")),
               "leak_ok": (((result.get("dynamic") or {}).get("leak")) or {}).get("ok"),
               "code_review_brief": str(RUNS / slug / "code_review_brief.md"), "critic_code_path": str(RUNS / slug / "critic_code.json")}
    return summary


def record_code_verdict(state: ResearchState, slug: str, data: dict) -> dict:
    by_slug = {h["slug"]: h for h in state.hypotheses()}
    hid = by_slug[slug]["id"]
    state.add_verdict(hid, "critic", f"code:{data.get('verdict')}", json.dumps(data)[:3000])
    blockers = [i for i in data.get("issues", []) if i.get("severity") in ("blocker", "major")]
    return {"verdict": data.get("verdict"), "blockers": blockers, "matches_rules": data.get("matches_rules"), "notes": data.get("notes", "")}


def fail(state: ResearchState, slug: str, reason: str) -> dict:
    by_slug = {h["slug"]: h for h in state.hypotheses()}
    hid = by_slug[slug]["id"]
    state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson=("build failed: " + reason)[:800])
    return {"slug": slug, "status": "scrap", "reason": reason}


# ---------------------------------------------------------------- pipeline
def test(state: ResearchState, slug: str, workers: int = 8) -> dict:
    by_slug = {h["slug"]: h for h in state.hypotheses()}
    hid = by_slug[slug]["id"]
    spec = HypothesisSpec.from_json(AUTO_SPECS / f"{slug}.json")
    state.update_hypothesis(hid, status="testing", strategy_path=spec.strategy_path)
    rep = run_pipeline(spec, state, hid, workers=workers)
    status = "candidate" if rep["verdict"] == "candidate" else "scrap"
    lesson = "" if status == "candidate" else f"{rep['verdict']}: failed {rep['failing']}"
    state.update_hypothesis(hid, status=status, bucket=status, report_path=str(RUNS / slug / "report.md"), lesson=lesson)
    if status == "candidate":
        notify(f"CANDIDATE {slug}: {rep.get('pooled')} soft failures {rep.get('soft_failures')}")
    return {"slug": slug, "status": status, "verdict": rep["verdict"], "failing": rep["failing"], "soft_failures": rep.get("soft_failures", []),
            "pooled": rep.get("pooled"), "seconds": rep.get("seconds"), "report": str(RUNS / slug / "report.md"),
            "digest": prompts.report_digest(rep)}


# ---------------------------------------------------------------- finish
def finish(state: ResearchState, cycle: int, note: str) -> dict:
    d = cycle_dir(cycle)
    rec: dict = {"cycle": cycle, "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"), "direction_note": note}
    for name in ("director_events.json", "director.json", "critic_review.json"):
        p = d / name
        if p.exists():
            try:
                rec[name.replace(".json", "")] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    if state.bucket("good"):
        try:
            basket = portfolio.evaluate(state)
            rec["basket"] = {"best": basket.get("best"), "meets_goal": basket.get("meets_goal")}
            if basket.get("meets_goal"):
                notify(f"GOAL CANDIDATE: basket {basket['best']}")
        except Exception:
            rec["basket_error"] = traceback.format_exc(limit=6)
    rec["overview"] = state.overview()
    rec["goal_reached"] = (RUNS / "GOAL_REACHED").exists()
    (CYCLES / f"cycle_{cycle:04d}.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    return {"cycle": cycle, "overview": rec["overview"], "goal_reached": rec["goal_reached"], "basket": rec.get("basket")}
