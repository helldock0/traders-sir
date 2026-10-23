"""Build the canonical data store.

    uv run python scripts/build_store.py extract-gj
    uv run python scripts/build_store.py build-m1 --symbols EURUSD,GBPJPY
    uv run python scripts/build_store.py resample --symbols EURUSD --tfs M5,M15,H1,H4,D1,W1
    uv run python scripts/build_store.py quality
    uv run python scripts/build_store.py all
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer  # noqa: E402

from edge.data import ingest, quality, resample, store, universe  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_store")


def _symbols(arg: str | None) -> list[str]:
    if not arg or arg.lower() == "all":
        return list(universe.ALL_SYMBOLS)
    if arg.lower() == "fx":
        return list(universe.FX_ALL)
    return [universe.validate_symbol(s) for s in arg.replace(";", ",").split(",") if s.strip()]


@app.command("extract-gj")
def extract_gj(symbols: str = typer.Option(None, help="comma list, 'fx' or 'all'")) -> None:
    """Unpack the gj-strat datastore tars into data/raw/bi5."""
    counts = ingest.extract_gj_tars(symbols=_symbols(symbols) if symbols else None)
    log.info("extracted %d new files across %d symbols", sum(counts.values()), len(counts))


@app.command("build-m1")
def build_m1(
    symbols: str = typer.Option("all", help="comma list, 'fx' or 'all'"),
    no_legacy: bool = typer.Option(False, help="ignore the legacy parquet store"),
    workers: int = typer.Option(None, help="decode threads"),
) -> None:
    """Decode raw files (+ legacy fill) into data/m1/{SYM}.parquet."""
    for sym in _symbols(symbols):
        t0 = time.time()
        try:
            _, stats = ingest.build_symbol(sym, use_legacy=not no_legacy, workers=workers)
            log.info("%s done in %.1fs: %s rows, %s..%s, ask %.0f%%", sym, time.time() - t0,
                     f"{stats['rows']:,}", stats["start"][:10], stats["end"][:10], 100 * stats["ask_coverage"])
        except ValueError as exc:
            log.warning("%s skipped: %s", sym, exc)


@app.command("resample")
def resample_cmd(
    symbols: str = typer.Option("all", help="comma list, 'fx' or 'all'"),
    tfs: str = typer.Option(",".join(resample.DEFAULT_TFS), help="comma list of timeframes"),
    anchor: str = typer.Option("ny_close", help="'ny_close' or 'utc' for D1/W1"),
) -> None:
    """Write data/tf/{SYM}_{TF}.parquet for each symbol and timeframe."""
    tf_list = tuple(t.strip().upper() for t in tfs.split(",") if t.strip())
    for sym in _symbols(symbols):
        if not store.m1_path(sym).exists():
            log.warning("%s: no M1 file, skipping", sym)
            continue
        t0 = time.time()
        counts = resample.resample_symbol(sym, tf_list, anchor)
        log.info("%s resampled in %.1fs: %s", sym, time.time() - t0, counts)


@app.command("quality")
def quality_cmd(symbols: str = typer.Option(None)) -> None:
    """Write data/reports/m1_quality.{md,json}."""
    rows = quality.report(_symbols(symbols) if symbols else None)
    for r in rows:
        if "error" in r:
            log.error("%s: %s", r["symbol"], r["error"])
        else:
            log.info("%-14s rows=%-10s %s..%s missing_wd=%d dup=%d ask=%.0f%% spikes=%d negspr=%d badohlc=%d",
                     r["symbol"], f"{r['rows']:,}", r["start"][:10], r["end"][:10], r["missing_weekdays"],
                     r["dup_ts"], 100 * r["ask_coverage"], r["spikes_over_threshold"], r["negative_spreads"], r["bad_ohlc"])
    log.info("report: %s", store.REPORT_DIR / "m1_quality.md")


@app.command("all")
def run_all(symbols: str = typer.Option("all")) -> None:
    """extract-gj -> build-m1 -> resample -> quality."""
    extract_gj(symbols=None)
    build_m1(symbols=symbols, no_legacy=False, workers=None)
    resample_cmd(symbols=symbols, tfs=",".join(resample.DEFAULT_TFS), anchor="ny_close")
    quality_cmd(symbols=symbols)


if __name__ == "__main__":
    app()
