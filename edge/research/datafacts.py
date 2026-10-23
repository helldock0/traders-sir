"""Descriptive market facts for the Research Director, computed on development years only.

Per market: spread by UTC hour (recent development years), hourly range profile, daily ATR, cost
ratio (spread / typical hourly range), weekend gaps, day-of-week ranges, 1-lag return
autocorrelation by timeframe. Written to runs/datafacts.json and runs/datafacts.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from ..data import store
from ..data.universe import pip_size
from ..engine.stats import load_splits

OUT_DIR = store.ROOT / "runs"


def _dev_range() -> tuple[str, str]:
    s = load_splits()
    return s["design"][0], s["check"][1]


def market_facts(sym: str, spread_years: tuple[str, str] = ("2022-01-01", "2023-12-31"),
                 profile_years: tuple[str, str] = ("2018-01-01", "2023-12-31")) -> dict:
    pip = pip_size(sym)
    facts: dict = {"symbol": sym, "pip": pip}
    m1 = pl.scan_parquet(store.m1_path(sym))
    span = m1.select(pl.col("ts").min().alias("start"), pl.col("ts").max().alias("end"), pl.len().alias("rows")).collect().row(0)
    facts.update({"start": str(span[0])[:10], "end": str(span[1])[:10], "rows": int(span[2])})

    lo, hi = (pl.lit(x).str.to_datetime(time_zone="UTC") for x in spread_years)
    spr = (m1.filter((pl.col("ts") >= lo) & (pl.col("ts") <= hi))
             .select(pl.col("ts").dt.hour().alias("hour"), ((pl.col("ask_c") - pl.col("bid_c")) / pip).alias("spr"))
             .group_by("hour").agg(pl.col("spr").median().alias("med"), pl.col("spr").quantile(0.9).alias("p90"))
             .sort("hour").collect())
    facts["spread_pips_by_hour_utc"] = {int(h): round(float(v), 2) for h, v in zip(spr["hour"], spr["med"])}
    facts["spread_pips_p90_by_hour_utc"] = {int(h): round(float(v), 2) for h, v in zip(spr["hour"], spr["p90"])}
    facts["spread_pips_median"] = round(float(np.median(spr["med"].to_numpy())), 2) if spr.height else None

    h1 = pl.read_parquet(store.tf_path(sym, "H1"))
    lo2, hi2 = (pl.lit(x).str.to_datetime(time_zone="UTC") for x in profile_years)
    h1 = h1.filter((pl.col("ts") >= lo2) & (pl.col("ts") <= hi2))
    prof = (h1.select(pl.col("ts").dt.hour().alias("hour"), ((pl.col("bid_h") - pl.col("bid_l")) / pip).alias("rng"))
              .group_by("hour").agg(pl.col("rng").mean()).sort("hour"))
    facts["hourly_range_pips_by_hour_utc"] = {int(h): round(float(v), 1) for h, v in zip(prof["hour"], prof["rng"])}
    facts["cost_ratio_by_hour_utc"] = {
        h: round(facts["spread_pips_by_hour_utc"].get(h, float("nan")) / r, 4) if r else None
        for h, r in facts["hourly_range_pips_by_hour_utc"].items()
    }
    dow = (h1.select(pl.col("ts").dt.weekday().alias("dow"), ((pl.col("bid_h") - pl.col("bid_l")) / pip).alias("rng"))
             .group_by("dow").agg(pl.col("rng").mean()).sort("dow"))
    facts["hourly_range_pips_by_weekday"] = {int(d): round(float(v), 1) for d, v in zip(dow["dow"], dow["rng"])}

    d1 = pl.read_parquet(store.tf_path(sym, "D1")).filter((pl.col("ts") >= lo2) & (pl.col("ts") <= hi2)).sort("ts")
    rng = ((d1["bid_h"] - d1["bid_l"]) / pip).to_numpy()
    if len(rng) > 20:
        atr20 = np.convolve(rng, np.ones(20) / 20, mode="valid")
        facts["atr20_pips"] = {"median": round(float(np.median(atr20)), 1), "p10": round(float(np.percentile(atr20, 10)), 1),
                               "p90": round(float(np.percentile(atr20, 90)), 1), "last_dev": round(float(atr20[-1]), 1)}
    close = d1["bid_c"].to_numpy()
    open_ = d1["bid_o"].to_numpy()
    ts = d1["ts"].to_numpy()
    if len(close) > 5:
        gap = np.abs(open_[1:] - close[:-1]) / pip
        dow_open = pl.Series(ts[1:]).dt.weekday().to_numpy()
        facts["gap_pips"] = {"mean_all": round(float(gap.mean()), 1),
                             "mean_monday": round(float(gap[dow_open == 1].mean()), 1) if (dow_open == 1).any() else None}

    ac: dict[str, float] = {}
    for tf in ("M5", "M15", "H1", "H4", "D1"):
        path = store.tf_path(sym, tf)
        if not path.exists():
            continue
        c = pl.read_parquet(path, columns=["ts", "bid_c"]).filter((pl.col("ts") >= lo2) & (pl.col("ts") <= hi2))["bid_c"].to_numpy()
        r = np.diff(np.log(c))
        r = r[np.isfinite(r)]
        if len(r) > 100:
            ac[tf] = round(float(np.corrcoef(r[:-1], r[1:])[0, 1]), 4)
    facts["return_autocorr_lag1"] = ac
    return facts


def build(symbols: list[str] | None = None, out_dir: Path = OUT_DIR) -> dict:
    symbols = symbols or store.list_m1_symbols()
    all_facts = {}
    for sym in symbols:
        try:
            all_facts[sym] = market_facts(sym)
        except Exception as exc:  # one broken market should not stop the rest
            all_facts[sym] = {"symbol": sym, "error": str(exc)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "datafacts.json").write_text(json.dumps(all_facts, indent=1))
    (out_dir / "datafacts.md").write_text(render(all_facts))
    return all_facts


def render(all_facts: dict) -> str:
    L = ["# Market facts (development years only: spreads 2022-23, profiles 2018-23)", "",
         "| Symbol | Rows | Start | End | Median spread (pips) | ATR20 median / p10 / p90 (pips) | Cheapest hours (spread/range) | Busiest hours (range) | Monday gap (pips) | AC1 M5 / H1 / D1 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for sym, f in all_facts.items():
        if "error" in f:
            L.append(f"| {sym} | ERROR {f['error']} |")
            continue
        cr = {h: v for h, v in f["cost_ratio_by_hour_utc"].items() if v is not None and v == v}
        cheap = ",".join(f"{h:02d}" for h, _ in sorted(cr.items(), key=lambda kv: kv[1])[:4])
        busy = ",".join(f"{h:02d}" for h, _ in sorted(f["hourly_range_pips_by_hour_utc"].items(), key=lambda kv: -kv[1])[:4])
        atr = f.get("atr20_pips", {})
        ac = f.get("return_autocorr_lag1", {})
        L.append(f"| {sym} | {f['rows']:,} | {f['start']} | {f['end']} | {f['spread_pips_median']} | "
                 f"{atr.get('median')} / {atr.get('p10')} / {atr.get('p90')} | {cheap} | {busy} | {f.get('gap_pips', {}).get('mean_monday')} | "
                 f"{ac.get('M5')} / {ac.get('H1')} / {ac.get('D1')} |")
    L += ["", "Hours are UTC. Cost ratio = median spread / mean hourly range; below 0.05 is cheap, above 0.15 is expensive.",
          "AC1 = lag-1 autocorrelation of log returns (negative = short-term mean reversion)."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    build()
