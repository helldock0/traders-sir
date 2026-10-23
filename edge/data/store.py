"""On-disk layout and canonical M1 schema.

data/raw/bi5/{SYM}/{SYM}_{YYYYMMDD}_{SIDE}.bi5   raw Dukascopy day files (gj-strat tars + our downloads)
data/m1/{SYM}.parquet                            canonical 1-minute bars, bid and ask sides
data/tf/{SYM}_{TF}.parquet                       resampled bars
data/reports/                                    quality reports

M1 schema (all prices float64, ts is timezone-aware UTC microseconds):
    ts, bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c, vol, src
ask_* is null where only bid data exists (legacy store). vol is bid-side tick volume.
src: 0 = Dukascopy raw file, 1 = legacy parquet store (bid only).
"""
from __future__ import annotations

import os
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_BI5_DIR = DATA_DIR / "raw" / "bi5"
M1_DIR = DATA_DIR / "m1"
TF_DIR = DATA_DIR / "tf"
REPORT_DIR = DATA_DIR / "reports"

LEGACY_PARQUET_DIR = Path(os.environ.get("EDGE_LEGACY_DIR", r"D:\AI\trade\data\parquet"))
GJ_DATASTORE_DIR = Path(os.environ.get("EDGE_GJ_DATASTORE", ROOT / "reference" / "gj-strat" / "datastore"))

SRC_BI5 = 0
SRC_LEGACY = 1

M1_COLUMNS = ["ts", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "vol", "src"]
M1_SCHEMA = {
    "ts": pl.Datetime("us", "UTC"),
    "bid_o": pl.Float64,
    "bid_h": pl.Float64,
    "bid_l": pl.Float64,
    "bid_c": pl.Float64,
    "ask_o": pl.Float64,
    "ask_h": pl.Float64,
    "ask_l": pl.Float64,
    "ask_c": pl.Float64,
    "vol": pl.Float64,
    "src": pl.Int8,
}


def m1_path(sym: str) -> Path:
    return M1_DIR / f"{sym.upper()}.parquet"


def tf_path(sym: str, tf: str) -> Path:
    return TF_DIR / f"{sym.upper()}_{tf.upper()}.parquet"


def raw_dir(sym: str) -> Path:
    return RAW_BI5_DIR / sym.upper()


def write_parquet(df: pl.DataFrame, path: Path) -> Path:
    """Atomic write: to a temp file first, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.write_parquet(tmp, compression="zstd", statistics=True)
    tmp.replace(path)
    return path


def conform_m1(df: pl.DataFrame) -> pl.DataFrame:
    """Cast to the canonical schema and column order."""
    out = df
    for col, dtype in M1_SCHEMA.items():
        if col not in out.columns:
            out = out.with_columns(pl.lit(None).cast(dtype).alias(col))
    return out.select([pl.col(c).cast(M1_SCHEMA[c]) for c in M1_COLUMNS])


def scan_m1(sym: str) -> pl.LazyFrame:
    return pl.scan_parquet(m1_path(sym))


def read_m1(sym: str, start: str | None = None, end: str | None = None) -> pl.DataFrame:
    """Read canonical M1 bars, optionally restricted to [start, end) given as ISO strings."""
    lf = scan_m1(sym)
    if start is not None:
        lf = lf.filter(pl.col("ts") >= pl.lit(start).str.to_datetime(time_zone="UTC"))
    if end is not None:
        lf = lf.filter(pl.col("ts") < pl.lit(end).str.to_datetime(time_zone="UTC"))
    return lf.collect()


def read_tf(sym: str, tf: str) -> pl.DataFrame:
    return pl.read_parquet(tf_path(sym, tf))


def list_m1_symbols() -> list[str]:
    if not M1_DIR.exists():
        return []
    return sorted(p.stem for p in M1_DIR.glob("*.parquet"))
