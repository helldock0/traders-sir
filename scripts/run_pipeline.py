"""Run the staged pipeline for a hypothesis spec (JSON) and print the verdict.

    uv run python scripts/run_pipeline.py specs/m3_usd_bid.json
    uv run python scripts/run_pipeline.py specs/m3_usd_bid.json --locked     # holdout, counted
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer  # noqa: E402

from edge.research.pipeline import HypothesisSpec, run_locked_test, run_pipeline  # noqa: E402
from edge.research.state import ResearchState  # noqa: E402

app = typer.Typer(add_completion=False)
logging.basicConfig(level=logging.WARNING)


@app.command()
def main(spec_path: str = typer.Argument(...), workers: int = typer.Option(8), no_state: bool = typer.Option(False),
         locked: bool = typer.Option(False, help="run the one-shot holdout test with the params in runs/<slug>/report.json")) -> None:
    spec = HypothesisSpec.from_json(spec_path)
    state = None if no_state else ResearchState()
    if locked:
        rep = json.loads((ROOT / "runs" / spec.slug / "report.json").read_text())
        chosen = {sym: d["params"] for sym, d in rep["stages"].get("C", {}).items()}
        if not chosen:
            raise typer.BadParameter("no Stage C params in the report; run the pipeline first")
        out = run_locked_test(spec, chosen, state)
        print(json.dumps({k: v for k, v in out.items() if k != "markets"}, indent=2, default=str))
        for sym, d in out["markets"].items():
            print(sym, "holdout:", {k: round(v, 3) if isinstance(v, float) else v for k, v in d["holdout"].items()})
        return
    hid = None
    if state is not None:
        hid = state.add_hypothesis(spec.slug, spec.title, spec.family, spec.rationale, json.loads(Path(spec_path).read_text()))
    rep = run_pipeline(spec, state, hid, workers=workers)
    if state is not None:
        state.update_hypothesis(hid, status=rep["verdict"] if rep["verdict"] in ("candidate", "scrap") else "scrap",
                                report_path=str(ROOT / "runs" / spec.slug / "report.md"))
    print(f"verdict: {rep['verdict']}  failing: {rep['failing']}  ({rep['seconds']}s)")
    print("gates:", rep["gates"])
    print("pooled:", rep.get("pooled"))
    print("report:", ROOT / "runs" / spec.slug / "report.md")


if __name__ == "__main__":
    app()
