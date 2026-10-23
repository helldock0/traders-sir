"""Deterministic steps of one research cycle, driven by the Claude Code skill /research-cycle.

    cycle_step.py start                     -> cycle number + Director context (charter, state, reports, scrap, facts, schema)
    cycle_step.py director --cycle N        -> validate runs/cycles/cycle_N/director.json, apply judgments, register hypotheses
    cycle_step.py review --cycle N          -> validate runs/cycles/cycle_N/critic_review.json, write builder briefs
    cycle_step.py check <slug>              -> checker on strategies/auto/<slug>.py (exit 0 if ok), writes the code-review brief
    cycle_step.py code-verdict <slug>       -> record runs/<slug>/critic_code.json; prints blockers
    cycle_step.py fail <slug> --reason ...  -> scrap a hypothesis that could not be built
    cycle_step.py test <slug>               -> staged pipeline; prints the digest
    cycle_step.py finish --cycle N --note   -> basket step, cycle log, overview
    cycle_step.py status                    -> overview of the state database
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import typer  # noqa: E402

from edge.agents import steps  # noqa: E402
from edge.research.state import ResearchState  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)
logging.basicConfig(level=logging.WARNING)
logging.getLogger("edge.agents.steps").setLevel(logging.INFO)


def _read_json(path: Path) -> dict:
    if not path.exists():
        typer.echo(f"ERROR: {path} not found")
        raise typer.Exit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"ERROR: {path} is not valid JSON: {exc}")
        raise typer.Exit(2)


@app.command()
def start(cycle: int = typer.Option(None, help="resume or force a cycle number")) -> None:
    state = ResearchState()
    n = cycle or steps.next_cycle_number()
    text = steps.director_context(state, n)
    typer.echo(f"CYCLE {n}\n")
    typer.echo(text)


@app.command()
def director(cycle: int = typer.Option(...)) -> None:
    state = ResearchState()
    data = _read_json(steps.cycle_dir(cycle) / "director.json")
    errs = steps.validate_director(data)
    if errs:
        typer.echo("VALIDATION ERRORS:\n- " + "\n- ".join(errs))
        raise typer.Exit(1)
    out = steps.apply_director(state, cycle, data)
    typer.echo(json.dumps(out, indent=1, default=str))


@app.command()
def review(cycle: int = typer.Option(...)) -> None:
    state = ResearchState()
    d = steps.cycle_dir(cycle)
    data = _read_json(d / "critic_review.json")
    expected = [h["slug"] for h in json.loads((d / "hypotheses.json").read_text(encoding="utf-8"))]
    errs = steps.validate_review(data, expected)
    if errs:
        typer.echo("VALIDATION ERRORS:\n- " + "\n- ".join(errs))
        raise typer.Exit(1)
    typer.echo(json.dumps(steps.apply_review(state, cycle, data), indent=1, default=str))


@app.command()
def check(slug: str = typer.Argument(...)) -> None:
    state = ResearchState()
    out = steps.check(state, slug)
    typer.echo(json.dumps(out, indent=1, default=str))
    raise typer.Exit(0 if out.get("ok") else 1)


@app.command("code-verdict")
def code_verdict(slug: str = typer.Argument(...)) -> None:
    state = ResearchState()
    data = _read_json(steps.RUNS / slug / "critic_code.json")
    typer.echo(json.dumps(steps.record_code_verdict(state, slug, data), indent=1, default=str))


@app.command()
def fail(slug: str = typer.Argument(...), reason: str = typer.Option(...)) -> None:
    typer.echo(json.dumps(steps.fail(ResearchState(), slug, reason), indent=1))


@app.command()
def test(slug: str = typer.Argument(...), workers: int = typer.Option(8)) -> None:
    out = steps.test(ResearchState(), slug, workers)
    digest = out.pop("digest")
    typer.echo(json.dumps(out, indent=1, default=str))
    typer.echo("\n" + digest)


@app.command()
def finish(cycle: int = typer.Option(...), note: str = typer.Option("")) -> None:
    typer.echo(json.dumps(steps.finish(ResearchState(), cycle, note), indent=1, default=str))


@app.command()
def status() -> None:
    state = ResearchState()
    typer.echo(json.dumps(state.overview(), indent=1))
    for name in ("candidate", "good"):
        rows = state.bucket(name) if name == "good" else state.hypotheses(name)
        typer.echo(f"{name}: {[r['slug'] for r in rows]}")


if __name__ == "__main__":
    app()
