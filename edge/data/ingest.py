"""Build the canonical M1 store from raw Dukascopy day files plus the legacy parquet store.

Sources, in priority order:
  1. raw bi5 day files in data/raw/bi5/{SYM}/ (gj-strat datastore tars and our own downloads):
     bid and ask sides, 2010 onwards for the 28 FX pairs.
  2. legacy parquet store (D:\\AI\\trade\\data\\parquet, bid only, 2018-01 to 2026-07):
     used only for whole days the raw files do not cover.
"""
from __future__ import annotations

import logging
import os
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl

from . import store
from .bi5 import decode_file, parse_raw_file_name

log = logging.getLogger(__name__)

_SIDE_RENAME = {
    "BID": {"o": "bid_o", "h": "bid_h", "l": "bid_l", "c": "bid_c", "v": "vol"},
    "ASK": {"o": "ask_o", "h": "ask_h", "l": "ask_l", "c": "ask_c", "v": "ask_vol"},
}


def extract_gj_tars(
    datastore_dir: Path = store.GJ_DATASTORE_DIR,
    raw_root: Path = store.RAW_BI5_DIR,
    symbols: list[str] | None = None,
) -> dict[str, int]:
    """Unpack datastore/*.tar into data/raw/bi5/{SYM}/ (skipping files already present)."""
    counts: dict[str, int] = {}
    tars = sorted(datastore_dir.glob("*.tar"))
    if not tars:
        raise FileNotFoundError(f"no tars in {datastore_dir}")
    for tar_path in tars:
        sym = tar_path.stem.split("_")[0].upper()
        if symbols and sym not in symbols:
            continue
        dest = raw_root / sym
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path) as tar:
            members = [
                m for m in tar.getmembers()
                if m.isfile() and "/" not in m.name and m.name.endswith(".bi5") and not (dest / m.name).exists()
            ]
            if members:
                tar.extractall(dest, members=members, filter="data")
        counts[sym] = counts.get(sym, 0) + len(members)
        log.info("extracted %-6s %-28s %6d new files", sym, tar_path.name, len(members))
    return counts


def _decode_side(files: list[Path], side: str, workers: int) -> pl.DataFrame | None:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        frames = [f for f in ex.map(decode_file, files, chunksize=16) if f is not None]
    if not frames:
        return None
    df = pl.concat(frames, how="vertical").rename(_SIDE_RENAME[side])
    return df.unique(subset="ts", keep="last").sort("ts")


def build_m1_from_raw(sym: str, raw_root: Path = store.RAW_BI5_DIR, workers: int | None = None) -> pl.DataFrame | None:
    """Decode every raw day file for a symbol into one bid/ask M1 frame (src = 0)."""
    sym = sym.upper()
    folder = raw_root / sym
    if not folder.exists():
        return None
    by_side: dict[str, list[Path]] = {"BID": [], "ASK": []}
    skipped = 0
    for p in sorted(folder.glob(f"{sym}_*_*.bi5")):
        if p.stat().st_size == 0:
            continue
        try:
            _, _, side = parse_raw_file_name(p.name)
        except ValueError:
            skipped += 1  # not a {SYM}_{YYYYMMDD}_{SIDE}.bi5 day file (e.g. hourly archives)
            continue
        if side in by_side:
            by_side[side].append(p)
    if skipped:
        log.warning("%s: skipped %d raw files with unexpected names", sym, skipped)
    if not by_side["BID"]:
        return None
    workers = workers or max(4, (os.cpu_count() or 8) - 2)
    bid = _decode_side(by_side["BID"], "BID", workers)
    if bid is None:
        return None
    ask = _decode_side(by_side["ASK"], "ASK", workers) if by_side["ASK"] else None
    if ask is not None:
        df = bid.join(ask.drop("ask_vol"), on="ts", how="left")
    else:
        df = bid
    df = df.with_columns(pl.lit(store.SRC_BI5, dtype=pl.Int8).alias("src"))
    log.info("%s raw: %d bid files, %d ask files -> %d bars (%s .. %s)",
             sym, len(by_side["BID"]), len(by_side["ASK"]), df.height, df["ts"].min(), df["ts"].max())
    return store.conform_m1(df)


def load_legacy_m1(sym: str, legacy_dir: Path = store.LEGACY_PARQUET_DIR) -> pl.DataFrame | None:
    """Legacy bid-only store -> canonical schema with null ask columns (src = 1)."""
    path = legacy_dir / f"{sym.upper()}_M1.parquet"
    if not path.exists():
        return None
    df = pl.read_parquet(path).rename(
        {"timestamp": "ts", "open": "bid_o", "high": "bid_h", "low": "bid_l", "close": "bid_c", "volume": "vol"}
    )
    df = df.with_columns(
        pl.col("ts").dt.cast_time_unit("us"),
        pl.lit(store.SRC_LEGACY, dtype=pl.Int8).alias("src"),
    )
    df = df.unique(subset="ts", keep="last").sort("ts")
    return store.conform_m1(df)


def merge_m1(primary: pl.DataFrame | None, secondary: pl.DataFrame | None) -> pl.DataFrame:
    """Combine two M1 frames. Secondary rows are used only for whole UTC days absent from primary."""
    if primary is None and secondary is None:
        raise ValueError("nothing to merge")
    if primary is None:
        return secondary.sort("ts")
    if secondary is None:
        return primary.sort("ts")
    primary_days = primary.get_column("ts").dt.date().unique()
    fill = secondary.filter(~pl.col("ts").dt.date().is_in(primary_days))
    out = pl.concat([primary, fill], how="vertical").sort("ts")
    dups = out.height - out.get_column("ts").n_unique()
    if dups:
        log.warning("merge produced %d duplicate timestamps; keeping the first", dups)
        out = out.unique(subset="ts", keep="first").sort("ts")
    return out


def build_symbol(sym: str, use_legacy: bool = True, workers: int | None = None) -> tuple[pl.DataFrame, dict]:
    """Build and write data/m1/{SYM}.parquet. Returns the frame and a small stats dict."""
    sym = sym.upper()
    raw = build_m1_from_raw(sym, workers=workers)
    legacy = load_legacy_m1(sym) if use_legacy else None
    df = merge_m1(raw, legacy)
    df = store.conform_m1(df)
    path = store.write_parquet(df, store.m1_path(sym))
    stats = {
        "symbol": sym,
        "rows": df.height,
        "start": str(df["ts"].min()),
        "end": str(df["ts"].max()),
        "rows_raw": int((df["src"] == store.SRC_BI5).sum()),
        "rows_legacy": int((df["src"] == store.SRC_LEGACY).sum()),
        "ask_coverage": float(df["ask_c"].is_not_null().mean()),
        "size_mb": round(path.stat().st_size / 1e6, 1),
    }
    log.info("%s -> %s", sym, stats)
    return df, stats
