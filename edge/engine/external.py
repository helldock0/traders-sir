"""External (non-price) series: economic calendar with surprises, CFTC positioning, implied-volatility indices,
and TFX Click 365 retail positioning: tfx (weekly long/short, 2022 on) and tfx_daily (daily open interest, 2005 on),
built by scripts/build_external_tfx.py and scripts/build_external_tfx_daily.py, see data/external/tfx/README*.md.

Each table lives in data/external/<name>.parquet (built by scripts/build_external.py, described in
data/external/README.md) and carries `ts_avail`, the UTC time from which a row may be used. An ExtSeries is
attached to a Market as m.ext[name] (listed in the hypothesis as ext_series), cut to the market's horizon like an
auxiliary market, and the leak tests truncate it and perturb its numeric columns from the primary bar's close.
Strategies read it only through edge.engine.features (ext_asof, ext_recent, ext_subset), which use nothing
before ts_avail.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from ..data import store

EXT_DIR = store.ROOT / "data" / "external"
KNOWN = ("calendar", "cot", "vol", "tfx", "tfx_daily")


@dataclass
class ExtSeries:
    name: str
    ts_avail: np.ndarray      # datetime64[us], ascending
    frame: pl.DataFrame       # one row per ts_avail entry, same order, ts_avail included

    @property
    def n(self) -> int:
        return len(self.ts_avail)

    @property
    def columns(self) -> list[str]:
        return [c for c in self.frame.columns if c != "ts_avail"]

    def numeric_columns(self) -> list[str]:
        return [c for c in self.columns if self.frame.schema[c].is_numeric()]

    def column(self, col: str) -> np.ndarray:
        s = self.frame.get_column(col)
        if s.dtype.is_numeric():
            return s.cast(pl.Float64).fill_null(np.nan).to_numpy()
        return s.to_numpy()

    def until(self, horizon: np.datetime64) -> "ExtSeries":
        """Rows usable at or before `horizon`."""
        k = int(np.searchsorted(self.ts_avail, np.datetime64(horizon, "us"), side="right"))
        return self.take(slice(0, k))

    def take(self, sel) -> "ExtSeries":
        if isinstance(sel, slice):
            return ExtSeries(self.name, self.ts_avail[sel], self.frame[sel])
        idx = np.flatnonzero(np.asarray(sel, dtype=bool)) if np.asarray(sel).dtype == bool else np.asarray(sel, dtype=np.int64)
        return ExtSeries(self.name, self.ts_avail[idx], self.frame[idx])

    def perturbed_from(self, j: int, direction: float, seed: int) -> "ExtSeries":
        """Copy whose numeric values from row j on are replaced by values far from the history before j."""
        n_fut = self.n - j
        if n_fut <= 0:
            return self
        rng = np.random.default_rng(seed)
        cols = []
        for c in self.numeric_columns():
            v = self.column(c)
            past = v[:j]
            past = past[np.isfinite(past)]
            base = float(np.median(past)) if past.size else 0.0
            scale = float(np.std(past)) if past.size > 1 and np.std(past) > 0 else max(abs(base), 1.0)
            fut = base + direction * 10.0 * scale + rng.normal(0.0, scale, n_fut)
            cols.append(pl.Series(c, np.concatenate([v[:j], fut])).cast(self.frame.schema[c], strict=False))
        return ExtSeries(self.name, self.ts_avail, self.frame.with_columns(cols))


def load_ext(name: str, end: str | None = None) -> ExtSeries:
    """Load one external table; rows usable at or after `end` are dropped (the holdout cut)."""
    name = name.lower()
    path = EXT_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"no external series {name!r}: {path}")
    df = pl.read_parquet(path)
    if "ts_avail" not in df.columns:
        raise ValueError(f"external series {name} has no ts_avail column")
    ts = df.get_column("ts_avail")
    if ts.dtype.time_zone is not None if isinstance(ts.dtype, pl.Datetime) else False:
        df = df.with_columns(pl.col("ts_avail").dt.convert_time_zone("UTC").dt.replace_time_zone(None))
    df = df.with_columns(pl.col("ts_avail").cast(pl.Datetime("us"))).sort("ts_avail", maintain_order=True)
    if end is not None:
        df = df.filter(pl.col("ts_avail") < pl.lit(end).str.to_datetime())
    ts_avail = df.get_column("ts_avail").to_numpy().astype("datetime64[us]")
    return ExtSeries(name, ts_avail, df)
