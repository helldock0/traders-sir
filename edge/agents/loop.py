"""The research cycle: Director judges and proposes -> Critic reviews -> Builder codes -> checker ->
Critic code review -> pipeline -> state. Runs until the goal is met, a pause file appears, or a budget cap hits.

Files: runs/PAUSE stops the loop after the current step; runs/cycles/cycle_<n>.json logs each cycle.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..data import store
from ..data.universe import ALL_SYMBOLS
from ..engine.backtest import get_market
from ..research import datafacts
from ..research.pipeline import HypothesisSpec, run_locked_test, run_pipeline
from ..research.state import ResearchState
from . import prompts
from .codecheck import full_check
from .llm import LLM
from .roles import Builder, Critic, Director

log = logging.getLogger(__name__)

RUNS = store.ROOT / "runs"
PAUSE_FILE = RUNS / "PAUSE"
CYCLES_DIR = RUNS / "cycles"
AUTO_SPECS = store.ROOT / "specs" / "auto"


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_")
    return s[:40] or "hyp"


from .steps import apply_judgments as _apply_judgments, notify  # noqa: E402  (shared with the Claude Code skill path)


class ResearchLoop:
    def __init__(self, state: ResearchState | None = None, llm: LLM | None = None, workers: int = 8,
                 director_effort: str = "high", daily_cap_usd: float | None = None):
        self.state = state or ResearchState()
        self.llm = llm or LLM(self.state)
        self.director = Director(self.llm, effort=director_effort)
        self.critic = Critic(self.llm)
        self.builder = Builder(self.llm)
        self.workers = workers
        self.daily_cap_usd = daily_cap_usd
        self.cycles_dir = CYCLES_DIR
        self.cycles_dir.mkdir(parents=True, exist_ok=True)
        AUTO_SPECS.mkdir(parents=True, exist_ok=True)
        self.datafacts_md = self._datafacts()

    # ------------------------------------------------------------------ context
    def _datafacts(self) -> str:
        path = RUNS / "datafacts.md"
        if not path.exists():
            datafacts.build()
        ext = RUNS.parent / "data" / "external" / "README.md"
        extra = ("\n\n" + ext.read_text(encoding="utf-8")) if ext.exists() else ""
        return path.read_text() + extra

    def _pending_reports(self) -> list[dict]:
        """Reports of hypotheses finished since the Director last judged them."""
        out = []
        for h in self.state.hypotheses():
            if h["status"] in ("candidate", "scrap") and h.get("report_path") and not h.get("critic_verdict", "").startswith("director:"):
                rp = Path(h["report_path"]).with_suffix(".json")
                if rp.exists():
                    try:
                        out.append(json.loads(rp.read_text()))
                    except json.JSONDecodeError:
                        continue
        return out

    def _director_user(self, cycle: int) -> str:
        scrap = self.state.scrap_index()
        candidates = [h for h in self.state.hypotheses("candidate")]
        good = self.state.bucket("good")
        pending = self._pending_reports()
        lessons = [h["lesson"] for h in self.state.hypotheses() if h.get("lesson") and h.get("cycle") and h["cycle"] >= max(1, cycle - 3)]
        return prompts.render_director_user(self.state.overview(), scrap, candidates, good, pending, self.datafacts_md, cycle, lessons[-12:])

    # ------------------------------------------------------------------ steps
    def apply_judgments(self, judgments: list[dict], cycle: int) -> list[str]:
        return _apply_judgments(self.state, judgments, cycle)

    def build_and_test(self, hyp: dict, review: dict, cycle: int) -> dict:
        slug = _slugify(hyp["slug"])
        hyp = dict(hyp)
        hyp["slug"] = slug
        hid = self.state.add_hypothesis(slug, hyp["title"], hyp["family"], hyp["rationale"], hyp, cycle=cycle)
        self.state.update_hypothesis(hid, status="building", critic_verdict=review["verdict"], critic_notes="; ".join(review.get("reasons", [])))
        markets = [s for s in hyp["markets"] if s in ALL_SYMBOLS and store.m1_path(s).exists()]
        if not markets:
            self.state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson="no data for the requested markets")
            return {"slug": slug, "outcome": "scrap:no_markets"}
        hyp["markets"] = markets
        primary = hyp.get("stage_a_market") if hyp.get("stage_a_market") in markets else markets[0]
        from ..research.pipeline import holdout_start
        aux = tuple(hyp.get("aux_markets") or ())
        m = get_market(primary, hyp["timeframe"], end=holdout_start(), aux=aux)   # the checker never sees holdout bars
        critic_notes = review.get("notes_for_builder", "") + ("\nRevisions: " + review["revisions"] if review.get("revisions") else "")
        code, feedback, checker, mod = None, None, None, None
        for attempt in range(1, 4):
            res = self.builder.build(hyp, critic_notes, cycle, feedback, code)
            code = res.data["code"]
            checker, mod, path = full_check(code, slug, hyp["params"], hyp["grid"], m)
            if checker["ok"]:
                break
            feedback = "Checker results:\n" + json.dumps(checker, indent=1, default=str)[:6000]
            log.info("%s: builder attempt %d failed checks", slug, attempt)
        if not checker or not checker["ok"]:
            self.state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson="build failed automated checks: " + "; ".join(
                (checker or {}).get("static", {}).get("issues", []) + ((checker or {}).get("dynamic") or {}).get("issues", []))[:800])
            return {"slug": slug, "outcome": "scrap:build_failed", "checker": checker}
        for rnd in range(2):
            cr = self.critic.review_code(hyp, code, checker, cycle).data
            self.state.add_verdict(hid, "critic", f"code:{cr['verdict']}", json.dumps(cr)[:2000])
            if cr["verdict"] == "approve":
                break
            blockers = [i for i in cr["issues"] if i["severity"] in ("blocker", "major")]
            if not blockers:
                break
            feedback = "Critic findings:\n" + json.dumps(blockers, indent=1)
            res = self.builder.build(hyp, critic_notes, cycle, feedback, code)
            code = res.data["code"]
            checker, mod, path = full_check(code, slug, hyp["params"], hyp["grid"], m)
            if not checker["ok"]:
                self.state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson="revision failed automated checks")
                return {"slug": slug, "outcome": "scrap:revision_failed", "checker": checker}
        spec = HypothesisSpec(slug=slug, title=hyp["title"], family=hyp["family"], rationale=hyp["rationale"], markets=markets,
                              timeframe=hyp["timeframe"], strategy_path=str(Path("strategies") / "auto" / f"{slug}.py"),
                              params=hyp["params"], grid=hyp["grid"], stage_a={"market": primary},
                              pre_registered=hyp["pre_registered"], notes=hyp.get("rules", ""), aux_markets=list(aux))
        spec.to_json(AUTO_SPECS / f"{slug}.json")
        self.state.update_hypothesis(hid, status="testing", strategy_path=spec.strategy_path)
        rep = run_pipeline(spec, self.state, hid, workers=self.workers)
        status = rep["verdict"] if rep["verdict"] == "candidate" else "scrap"
        lesson = "" if status == "candidate" else f"{rep['verdict']}: failed {rep['failing']}"
        self.state.update_hypothesis(hid, status=status, bucket=status, report_path=str(RUNS / slug / "report.md"), lesson=lesson)
        if status == "candidate":
            notify(f"CANDIDATE {slug}: {rep.get('pooled')} soft failures {rep.get('soft_failures')}")
        return {"slug": slug, "outcome": status, "verdict": rep["verdict"], "failing": rep["failing"], "pooled": rep.get("pooled")}

    def run_cycle(self, cycle: int) -> dict:
        t0 = time.time()
        logrec: dict = {"cycle": cycle, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": []}
        user = self._director_user(cycle)
        d = self.director.propose(user, cycle)
        logrec["director"] = {"usd": d.usd, "seconds": d.seconds, "direction_note": d.data.get("direction_note", "")}
        log.info("Director (%.2f USD, %.0fs): %s", d.usd, d.seconds, d.data.get("direction_note", "")[:300])
        logrec["events"] += self.apply_judgments(d.data.get("judgments", []), cycle)
        # mark pending reports as judged so they are not shown again
        judged = {j["slug"] for j in d.data.get("judgments", [])}
        for h in self.state.hypotheses():
            if h["slug"] in judged and not (h.get("critic_verdict") or "").startswith("director:"):
                self.state.update_hypothesis(h["id"], critic_verdict="director:seen")
        hyps = d.data.get("hypotheses", [])[:3]
        if not hyps:
            logrec["events"].append("director proposed nothing")
        else:
            rev = self.critic.review_hypotheses(hyps, self.state.scrap_index(), self.datafacts_md, cycle).data["reviews"]
            by_slug = {r["slug"]: r for r in rev}
            for hyp in hyps:
                r = by_slug.get(hyp["slug"], {"verdict": "approve", "reasons": [], "revisions": "", "notes_for_builder": ""})
                if r["verdict"] == "reject":
                    hid = self.state.add_hypothesis(_slugify(hyp["slug"]), hyp["title"], hyp["family"], hyp["rationale"], hyp, cycle=cycle)
                    self.state.update_hypothesis(hid, status="rejected", bucket="scrap", critic_verdict="reject",
                                                 critic_notes="; ".join(r.get("reasons", [])), lesson="rejected by critic: " + "; ".join(r.get("reasons", []))[:600])
                    logrec["events"].append(f"{hyp['slug']}: rejected by critic")
                    continue
                try:
                    out = self.build_and_test(hyp, r, cycle)
                except Exception:
                    out = {"slug": hyp["slug"], "outcome": "error", "trace": traceback.format_exc(limit=8)}
                    log.error("%s failed: %s", hyp["slug"], out["trace"])
                logrec["events"].append(out)
        if self.state.bucket("good"):
            try:
                from ..research import portfolio
                basket = portfolio.evaluate(self.state)
                logrec["basket"] = {"best": basket.get("best"), "meets_goal": basket.get("meets_goal")}
                if basket.get("meets_goal"):
                    notify(f"GOAL CANDIDATE: basket {basket['best']}")
            except Exception:
                log.error("basket evaluation failed:\n%s", traceback.format_exc())
        logrec["spend_cycle_usd"] = round(self.llm.total_usd, 4)
        logrec["overview"] = self.state.overview()
        logrec["seconds"] = round(time.time() - t0, 1)
        self.cycles_dir.mkdir(parents=True, exist_ok=True)
        (self.cycles_dir / f"cycle_{cycle:04d}.json").write_text(json.dumps(logrec, indent=1, default=str))
        log.info("cycle %d done in %.0fs; spend so far %.2f USD; %s", cycle, logrec["seconds"], self.llm.total_usd, logrec["overview"])
        return logrec

    def goal_met(self) -> bool:
        return (RUNS / "GOAL_REACHED").exists()

    def run(self, max_cycles: int | None = None, sleep_between_s: float = 5.0) -> None:
        cycle = self._next_cycle_number()
        done = 0
        while True:
            if PAUSE_FILE.exists():
                log.info("pause file present; stopping")
                return
            if self.daily_cap_usd is not None:
                since = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
                if self.state.spend_total(since) >= self.daily_cap_usd:
                    log.info("daily cap reached; sleeping an hour")
                    time.sleep(3600)
                    continue
            try:
                self.run_cycle(cycle)
            except Exception:
                log.error("cycle %d crashed:\n%s", cycle, traceback.format_exc())
                time.sleep(60)
            cycle += 1
            done += 1
            if max_cycles is not None and done >= max_cycles:
                return
            if self.goal_met():
                notify("GOAL REACHED: basket meets the pass-probability target; switching to forward-test mode.")
                return
            time.sleep(sleep_between_s)

    def _next_cycle_number(self) -> int:
        nums = [int(p.stem.split("_")[1]) for p in self.cycles_dir.glob("cycle_*.json")]
        return (max(nums) + 1) if nums else 1
