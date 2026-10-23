"""Load bars for the engine: one (symbol, timeframe) frame with bid/ask OHLC and the USD conversion rate.

The engine works in numpy arrays. `Market` holds them contiguously, plus `quote_per_usd` (units of
the quote currency per 1 USD, as-of each bar's open) so pip values and notionals can be expressed in
USD without look-ahead. Ask columns that are null (legacy bid-only rows) are filled with
bid + modelled spread, where the model is the median spread of the same UTC hour over the rows that
do have an ask side.

Auxiliary markets: a strategy may condition on other instruments (an index for risk-off, a cross for
USD strength). They are attached as `m.aux[name]`, loaded on the primary timeframe and cut to the same
horizon, and the leak tests truncate and perturb them together with the primary market. Read them
through features.aux_asof so only bars already closed at the primary bar's close are used.

External series (economic calendar, CFTC positioning, implied vol; see edge/engine/external.py) are attached
as `m.ext[name]`, cut to the same horizon by their `ts_avail` column, and covered by the same leak tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from ..data import store
from ..data.universe import asset_class, conversion_pair, pip_size, point_size
from .external import ExtSeries, load_ext  # noqa: F401

ASK_COLS = ["ask_o", "ask_h", "ask_l", "ask_c"]
BID_COLS = ["bid_o", "bid_h", "bid_l", "bid_c"]
TF_MINUTES = {"M1": 1, "M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H2": 120, "H3": 180, "H4": 240, "H8": 480,
              "H12": 720, "D1": 1440, "W1": 10080}


def tf_minutes(tf: str) -> int:
    return TF_MINUTES[tf.upper()]


@dataclass
class Market:
    sym: str
    tf: str
    ts: np.ndarray            # datetime64[us], UTC, bar open time
    bid_o: np.ndarray
    bid_h: np.ndarray
    bid_l: np.ndarray
    bid_c: np.ndarray
    ask_o: np.ndarray
    ask_h: np.ndarray
    ask_l: np.ndarray
    ask_c: np.ndarray
    vol: np.ndarray
    quote_per_usd: np.ndarray  # as of bar open
    pip: float
    point: float
    asset: str
    ask_modelled_share: float  # share of bars whose ask side came from the spread model
    aux: dict = field(default_factory=dict)   # name -> Market of an auxiliary instrument on the same timeframe
    ext: dict = field(default_factory=dict)   # name -> ExtSeries (calendar, cot, vol), cut to the same horizon

    @property
    def n(self) -> int:
        return len(self.ts)

    def close_times(self) -> np.ndarray:
        """When each bar's information becomes known: its open time plus one bar."""
        return self.ts + np.timedelta64(tf_minutes(self.tf), "m")

    def frame(self) -> pl.DataFrame:
        return pl.DataFrame({
            "ts": self.ts, "bid_o": self.bid_o, "bid_h": self.bid_h, "bid_l": self.bid_l, "bid_c": self.bid_c,
            "ask_o": self.ask_o, "ask_h": self.ask_h, "ask_l": self.ask_l, "ask_c": self.ask_c,
            "vol": self.vol, "quote_per_usd": self.quote_per_usd,
        }).with_columns(pl.col("ts").dt.replace_time_zone("UTC"))

    def _copy(self, sl: slice, aux: dict | None = None, ext: dict | None = None) -> "Market":
        return Market(self.sym, self.tf, self.ts[sl], self.bid_o[sl], self.bid_h[sl], self.bid_l[sl], self.bid_c[sl],
                      self.ask_o[sl], self.ask_h[sl], self.ask_l[sl], self.ask_c[sl], self.vol[sl],
                      self.quote_per_usd[sl], self.pip, self.point, self.asset, self.ask_modelled_share, aux or {}, ext or {})

    def slice(self, start: str | None = None, end: str | None = None) -> "Market":
        """Rows with start <= ts < end (ISO strings, UTC)."""
        lo = 0 if start is None else int(np.searchsorted(self.ts, np.datetime64(start, "us")))
        hi = self.n if end is None else int(np.searchsorted(self.ts, np.datetime64(end, "us")))
        return self.rows(lo, hi)

    def rows(self, lo: int, hi: int) -> "Market":
        """Bars lo..hi-1 by position. Auxiliary markets keep only bars closed by the last kept bar's close, and
        external series only rows usable by then."""
        aux, ext = {}, {}
        if (self.aux or self.ext) and hi > lo:
            horizon = self.ts[hi - 1] + np.timedelta64(tf_minutes(self.tf), "m")
            aux = {k: a.until(horizon) for k, a in self.aux.items()}
            ext = {k: e.until(horizon) for k, e in self.ext.items()}
        return self._copy(slice(lo, hi), aux, ext)

    def until(self, horizon: np.datetime64) -> "Market":
        """Bars whose close time is at or before `horizon` (used to cut auxiliary markets)."""
        n_keep = int(np.searchsorted(self.close_times(), np.datetime64(horizon, "us"), side="right"))
        return self._copy(slice(0, n_keep))

    def head(self, k: int) -> "Market":
        return self.rows(0, k)

    def widen_spread(self, mult: float) -> "Market":
        """Copy with the bid-ask spread multiplied (bid unchanged, ask moved up). Auxiliary markets unchanged."""
        extra = mult - 1.0
        return Market(self.sym, self.tf, self.ts, self.bid_o, self.bid_h, self.bid_l, self.bid_c,
                      self.ask_o + extra * (self.ask_o - self.bid_o), self.ask_h + extra * (self.ask_h - self.bid_h),
                      self.ask_l + extra * (self.ask_l - self.bid_l), self.ask_c + extra * (self.ask_c - self.bid_c),
                      self.vol, self.quote_per_usd, self.pip, self.point, self.asset, self.ask_modelled_share, dict(self.aux),
                      dict(self.ext))


def _bars_path(sym: str, tf: str) -> Path:
    return store.m1_path(sym) if tf.upper() == "M1" else store.tf_path(sym, tf)


def load_bars(sym: str, tf: str) -> pl.DataFrame:
    path = _bars_path(sym, tf)
    if not path.exists():
        raise FileNotFoundError(f"no bars for {sym} {tf}: {path}")
    return pl.read_parquet(path).sort("ts")


def fill_ask(df: pl.DataFrame) -> tuple[pl.DataFrame, float]:
    """Fill null ask columns with bid + median spread of the same UTC hour (from rows that have an ask)."""
    missing = df.get_column("ask_c").is_null()
    share = float(missing.mean()) if df.height else 0.0
    if share == 0.0:
        return df, 0.0
    hour = pl.col("ts").dt.hour().alias("hour")
    known = df.filter(~missing).select(hour, (pl.col("ask_c") - pl.col("bid_c")).alias("spr"))
    if known.height == 0:
        default = 2.0 * point_size_from_frame(df)
        model = pl.DataFrame({"hour": list(range(24)), "spr": [default] * 24})
    else:
        model = known.group_by("hour").agg(pl.col("spr").median()).sort("hour")
        overall = float(known.get_column("spr").median())
        model = pl.DataFrame({"hour": list(range(24))}).join(model, on="hour", how="left").fill_null(overall)
    model = model.with_columns(pl.col("hour").cast(pl.Int8))
    out = df.with_columns(hour.cast(pl.Int8)).join(model, on="hour", how="left")
    exprs = [pl.coalesce([pl.col(a), pl.col(b) + pl.col("spr")]).alias(a) for a, b in zip(ASK_COLS, BID_COLS)]
    out = out.with_columns(exprs).drop(["hour", "spr"])
    return out, share


def point_size_from_frame(df: pl.DataFrame) -> float:
    """Rough tick size from the data itself (used only when no ask side exists anywhere)."""
    c = df.get_column("bid_c").head(100_000).to_numpy()
    d = np.abs(np.diff(c))
    d = d[d > 0]
    return float(np.min(d)) if d.size else 1e-4


def attach_quote_per_usd(df: pl.DataFrame, sym: str, tf: str) -> pl.DataFrame:
    pair, invert = conversion_pair(sym)
    if pair is None:
        return df.with_columns(pl.lit(1.0).alias("quote_per_usd"))
    conv = load_bars(pair, tf).select("ts", pl.col("bid_o").alias("_conv"))
    out = df.join_asof(conv, on="ts", strategy="backward")
    out = out.with_columns(pl.col("_conv").fill_null(strategy="backward"))
    expr = (1.0 / pl.col("_conv")) if invert else pl.col("_conv")
    return out.with_columns(expr.alias("quote_per_usd")).drop("_conv")


def load_market(sym: str, tf: str, start: str | None = None, end: str | None = None,
                aux: tuple[str, ...] | list[str] = (), ext: tuple[str, ...] | list[str] = ()) -> Market:
    """Load one market; `aux` names auxiliary instruments to attach on the same timeframe and horizon, `ext` names
    external series (calendar, cot, vol) to attach, cut at the same end."""
    sym, tf = sym.upper(), tf.upper()
    df = load_bars(sym, tf)
    if start is not None:
        df = df.filter(pl.col("ts") >= pl.lit(start).str.to_datetime(time_zone="UTC"))
    if end is not None:
        df = df.filter(pl.col("ts") < pl.lit(end).str.to_datetime(time_zone="UTC"))
    df, modelled = fill_ask(df)
    # Dukascopy builds bid and ask candles from separate tick streams; the ask side can print below the
    # bid when the last ask tick is stale. A negative spread would be free money, so clamp ask >= bid.
    df = df.with_columns([pl.max_horizontal(a, b).alias(a) for a, b in zip(ASK_COLS, BID_COLS)])
    df = attach_quote_per_usd(df, sym, tf)
    f = lambda c: np.ascontiguousarray(df.get_column(c).to_numpy(), dtype=np.float64)  # noqa: E731
    ts = df.get_column("ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
    m = Market(
        sym=sym, tf=tf, ts=ts,
        bid_o=f("bid_o"), bid_h=f("bid_h"), bid_l=f("bid_l"), bid_c=f("bid_c"),
        ask_o=f("ask_o"), ask_h=f("ask_h"), ask_l=f("ask_l"), ask_c=f("ask_c"),
        vol=f("vol"), quote_per_usd=f("quote_per_usd"),
        pip=pip_size(sym), point=point_size(sym), asset=asset_class(sym), ask_modelled_share=modelled,
    )
    for name in aux:
        name = name.upper()
        if name == sym:
            continue
        m.aux[name] = load_market(name, tf, start=None, end=end)
    for name in ext:
        m.ext[name.lower()] = load_ext(name, end=end)
    return m
