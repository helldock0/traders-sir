"""Trade statistics per time split, in R.

Splits default to the gj-strat convention: design 2010-2017, check 2018-2023, holdout 2024-2026.
The pass bar used across the research programme: design t >= 2 and average R > 0 in both check and
holdout. It is a floor, not proof; the validation gates add walk-forward, stability and trial counting.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from ..data import store

DEFAULT_SPLITS: dict[str, tuple[str, str]] = {
    "design": ("2010-01-01", "2017-12-31"),
    "check": ("2018-01-01", "2023-12-31"),
    "holdout": ("2024-01-01", "2026-12-31"),
}


def load_splits(path: Path = store.ROOT / "config" / "universe.yaml") -> dict[str, tuple[str, str]]:
    if not path.exists():
        return dict(DEFAULT_SPLITS)
    cfg = yaml.safe_load(path.read_text()) or {}
    out = {}
    for name, rng in (cfg.get("splits") or {}).items():
        s, e = rng["start"], rng["end"]
        out[name] = (s.isoformat() if isinstance(s, date) else str(s), e.isoformat() if isinstance(e, date) else str(e))
    return out or dict(DEFAULT_SPLITS)


def tstat(r: np.ndarray) -> float:
    n = len(r)
    if n < 2:
        return float("nan")
    sd = r.std(ddof=1)
    return float(r.mean() / (sd / np.sqrt(n))) if sd > 0 else float("nan")


def max_drawdown_r(r: np.ndarray) -> float:
    if len(r) == 0:
        return 0.0
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((peak - eq).max())


def longest_losing_streak(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def basic_stats(r: np.ndarray, months: float | None = None) -> dict:
    n = len(r)
    if n == 0:
        return {"n": 0, "avg_r": float("nan"), "t": float("nan"), "win_rate": float("nan"), "avg_win": float("nan"),
                "avg_loss": float("nan"), "profit_factor": float("nan"), "total_r": 0.0, "max_dd_r": 0.0,
                "losing_streak": 0, "trades_per_month": 0.0}
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / -losses.sum()) if losses.size and losses.sum() < 0 else float("inf")
    return {
        "n": int(n),
        "avg_r": float(r.mean()),
        "t": tstat(r),
        "win_rate": float((r > 0).mean()),
        "avg_win": float(wins.mean()) if wins.size else float("nan"),
        "avg_loss": float(losses.mean()) if losses.size else float("nan"),
        "profit_factor": pf,
        "total_r": float(r.sum()),
        "max_dd_r": max_drawdown_r(r),
        "losing_streak": longest_losing_streak(r),
        "trades_per_month": float(n / months) if months else float("nan"),
    }


def _months(start: str, end: str) -> float:
    s, e = np.datetime64(start, "D"), np.datetime64(end, "D")
    return float((e - s).astype(int) + 1) / 30.4375


def split_stats(trades: pl.DataFrame, splits: dict[str, tuple[str, str]] | None = None,
                r_col: str = "r_net", ts_col: str = "entry_ts") -> dict[str, dict]:
    splits = splits or load_splits()
    out: dict[str, dict] = {}
    if trades.height == 0:
        for name, (s, e) in splits.items():
            out[name] = basic_stats(np.array([]), _months(s, e))
        out["all"] = basic_stats(np.array([]))
        return out
    ts = trades.get_column(ts_col).dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
    r = trades.get_column(r_col).to_numpy()
    for name, (s, e) in splits.items():
        lo = np.datetime64(s, "us")
        hi = np.datetime64(e, "us") + np.timedelta64(1, "D")
        sel = (ts >= lo) & (ts < hi)
        out[name] = basic_stats(r[sel], _months(s, e))
    first, last = ts.min(), ts.max()
    months = max(float((last - first).astype("timedelta64[D]").astype(int)) / 30.4375, 1 / 30.4375)
    out["all"] = basic_stats(r, months)
    return out


def r_by_year(trades: pl.DataFrame, r_col: str = "r_net", ts_col: str = "entry_ts") -> dict[int, float]:
    if trades.height == 0:
        return {}
    g = trades.group_by(pl.col(ts_col).dt.year().alias("year")).agg(pl.col(r_col).sum()).sort("year")
    return {int(y): float(v) for y, v in zip(g["year"], g[r_col])}


def passes_bar(stats: dict[str, dict], design_t: float = 2.0) -> bool:
    d, c, h = stats.get("design", {}), stats.get("check", {}), stats.get("holdout", {})
    t = d.get("t", float("nan"))
    return bool(t == t and t >= design_t and c.get("avg_r", -1) > 0 and h.get("avg_r", -1) > 0)


def format_split_table(stats: dict[str, dict]) -> str:
    rows = ["| Period | Trades | Avg R | t | Win % | Avg win | Avg loss | PF | Total R | Max DD (R) | Trades/mo |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, s in stats.items():
        if s["n"] == 0:
            rows.append(f"| {name} | 0 | | | | | | | | | |")
            continue
        rows.append(f"| {name} | {s['n']} | {s['avg_r']:+.3f} | {s['t']:.2f} | {100 * s['win_rate']:.0f} | "
                    f"{s['avg_win']:+.2f} | {s['avg_loss']:+.2f} | {s['profit_factor']:.2f} | {s['total_r']:+.1f} | "
                    f"{s['max_dd_r']:.1f} | {s['trades_per_month']:.2f} |")
    return "\n".join(rows)
