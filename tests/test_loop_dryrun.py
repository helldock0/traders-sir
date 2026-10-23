"""One research cycle with a fake model: exercises Director -> Critic -> Builder -> checker -> pipeline -> state."""
from __future__ import annotations

import json
import shutil

import pytest

from edge.agents.llm import LLMResult
from edge.agents.loop import AUTO_SPECS, RUNS, ResearchLoop
from edge.data import store
from edge.research.state import ResearchState

SLUG = "m3_dryrun"
HYP = {
    "slug": SLUG, "title": "M-3 dry run", "family": "calendar_flow", "rationale": "month-end USD demand",
    "markets": ["USDJPY"], "timeframe": "M1",
    "rules": "Buy USDJPY at 11:00 UTC on the 3rd-last weekday, exit 12:00 UTC, stop 0.25 x ATR20",
    "params": {"k": 2, "entry_utc": "11:00", "exit_utc": "12:00", "sl_atr": 0.25, "side": "auto", "start": "2011-01-01", "max_delay_min": 5},
    "grid": {"k": [1, 2, 3], "sl_atr": [0.25, 0.5]}, "stage_a_market": "USDJPY",
    "pre_registered": {"expected_design_t_min": 2.0, "expected_avg_r": 0.08, "min_trades_design_per_market": 30, "kill_if": "design avg R <= 0"},
    "similar_prior": ["prior_flow_atlas"], "why_different": "replication", "parent_slug": None,
}
ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


class FakeLLM:
    total_usd = 0.0

    def __init__(self):
        self.calls: list[str] = []
        self.code = (store.ROOT / "strategies" / "oracle" / "m3_usd_bid.py").read_text().replace('NAME = "oracle_m3_usd_bid"', f'NAME = "{SLUG}"')

    def call(self, role, model, system, user, schema, effort="high", max_tokens=16000, cycle=None, history=None):
        self.calls.append(role)
        if role == "director":
            data = {"judgments": [], "hypotheses": [HYP], "direction_note": "dry run"}
        elif role == "critic" and "# Builder module" in user:
            data = {"verdict": "approve", "issues": [], "lookahead_risk": "low", "matches_rules": True, "notes": ""}
        elif role == "critic":
            data = {"reviews": [{"slug": SLUG, "verdict": "approve", "reasons": ["known flow"], "revisions": "", "overfit_risk": "low",
                                 "cost_risk": "low", "duplicate_of": None, "notes_for_builder": ""}]}
        else:
            data = {"code": self.code, "notes": "", "assumptions": []}
        return LLMResult(data=data, text=json.dumps(data), model=model, stop_reason="end_turn", usage=dict(ZERO_USAGE), usd=0.0, seconds=0.0)


@pytest.mark.skipif(not store.m1_path("USDJPY").exists(), reason="needs the built M1 store")
def test_one_cycle_dry_run(tmp_path):
    state = ResearchState(tmp_path / "state.sqlite")
    fake = FakeLLM()
    loop = ResearchLoop(state=state, llm=fake, workers=4)
    loop.cycles_dir = tmp_path / "cycles"
    try:
        rec = loop.run_cycle(1)
        assert fake.calls[:2] == ["director", "critic"]
        assert "builder" in fake.calls
        hyps = {h["slug"]: h for h in state.hypotheses()}
        assert SLUG in hyps and hyps[SLUG]["status"] in ("candidate", "scrap")
        assert (RUNS / SLUG / "report.md").exists()
        assert state.n_trials() > 0
        assert (tmp_path / "cycles" / "cycle_0001.json").exists()
        assert any(isinstance(e, dict) and e.get("slug") == SLUG for e in rec["events"])
    finally:
        shutil.rmtree(RUNS / SLUG, ignore_errors=True)
        (store.ROOT / "strategies" / "auto" / f"{SLUG}.py").unlink(missing_ok=True)
        (AUTO_SPECS / f"{SLUG}.json").unlink(missing_ok=True)
