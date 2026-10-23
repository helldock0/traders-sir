"""Start the 24/7 research loop.

    uv run python scripts/run_loop.py --max-cycles 1          # one cycle, then stop
    uv run python scripts/run_loop.py                          # run until runs/PAUSE exists or the goal is reached
    uv run python scripts/run_loop.py --director-effort xhigh --workers 12
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer  # noqa: E402

from edge.agents.llm import credentials_present  # noqa: E402

app = typer.Typer(add_completion=False)


@app.command()
def main(max_cycles: int = typer.Option(None), workers: int = typer.Option(8), director_effort: str = typer.Option("high"),
         daily_cap_usd: float = typer.Option(None, help="optional spend cap per UTC day")) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "logs" / "research_loop.log", encoding="utf-8")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    if not credentials_present():
        typer.echo("No Anthropic credentials. Copy .env.example to .env and set ANTHROPIC_API_KEY, then rerun.")
        raise typer.Exit(2)
    from edge.agents.loop import ResearchLoop  # noqa: E402

    loop = ResearchLoop(workers=workers, director_effort=director_effort, daily_cap_usd=daily_cap_usd)
    loop.run(max_cycles=max_cycles)


if __name__ == "__main__":
    app()
