"""Download Dukascopy raw day files (bid and ask 1-minute candles) into data/raw/bi5.

Resumable: existing files are skipped, 404 days are stored as empty markers.
One request at a time with pacing; Dukascopy throttles aggressively.

    uv run python scripts/dukascopy_download.py --symbols EURUSD,GBPUSD --start 2026-07-27 --end today
    uv run python scripts/dukascopy_download.py --symbols indices --start 2015-01-01
    uv run python scripts/dukascopy_download.py --symbols fx --start 2024-01-01 --sides ASK
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer  # noqa: E402

from edge.data import store, universe  # noqa: E402
from edge.data.bi5 import Bi5Client  # noqa: E402

app = typer.Typer(add_completion=False)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("dukascopy_download")


def _symbols(arg: str) -> list[str]:
    key = arg.lower()
    if key == "all":
        return list(universe.ALL_SYMBOLS)
    if key == "fx":
        return list(universe.FX_ALL)
    if key == "majors":
        return list(universe.FX_MAJORS)
    if key == "metals":
        return list(universe.METALS)
    if key == "indices":
        return list(universe.INDICES)
    return [universe.validate_symbol(s) for s in arg.replace(";", ",").split(",") if s.strip()]


def _date(s: str) -> date:
    if s.lower() in ("today", "now"):
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(s)


@app.command()
def main(
    symbols: str = typer.Option(..., help="comma list or: all, fx, majors, metals, indices"),
    start: str = typer.Option(..., help="first UTC day, YYYY-MM-DD"),
    end: str = typer.Option("today", help="last UTC day, YYYY-MM-DD or 'today'"),
    sides: str = typer.Option("BID,ASK", help="BID, ASK or BID,ASK"),
    pace: float = typer.Option(0.6, help="minimum seconds between requests"),
    max_attempts: int = typer.Option(12),
) -> None:
    side_tuple = tuple(s.strip().upper() for s in sides.split(",") if s.strip())
    d0, d1 = _date(start), _date(end)
    syms = _symbols(symbols)
    log.info("downloading %d symbols, %s..%s, sides=%s, pace=%.2fs", len(syms), d0, d1, side_tuple, pace)
    t_start = time.time()
    with Bi5Client(pace_s=pace, max_attempts=max_attempts) as client:
        for sym in syms:
            t0 = time.time()
            counts = client.download_range(sym, d0, d1, store.raw_dir(sym), sides=side_tuple)
            log.info("%s finished in %.0fs: %s", sym, time.time() - t0, counts)
        log.info("all done in %.0fs: %s", time.time() - t_start, client.stats)


if __name__ == "__main__":
    app()
