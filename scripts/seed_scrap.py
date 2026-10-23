"""Seed the research state with prior negative results (config/prior_scrap.yaml). Idempotent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from edge.research.state import ResearchState  # noqa: E402


def main() -> None:
    items = yaml.safe_load((ROOT / "config" / "prior_scrap.yaml").read_text())
    state = ResearchState()
    existing = {h["slug"] for h in state.hypotheses()}
    added = 0
    for it in items:
        if it["slug"] in existing:
            continue
        hid = state.add_hypothesis(it["slug"], it["title"], it["family"], it.get("rationale", "prior research"),
                                   {"source": "prior", "title": it["title"]}, cycle=0)
        state.update_hypothesis(hid, status="scrap", bucket="scrap", lesson=it["lesson"], critic_verdict="prior")
        added += 1
    print(f"seeded {added} prior scrap entries; total hypotheses {len(state.hypotheses())}")
    print(state.overview())


if __name__ == "__main__":
    main()
