"""Baskets: combine good strategies, size them, and measure the prop-challenge odds.

Legs come from runs/<slug>/trades_full_<SYM>.parquet (written by the locked test, so they span the
whole sample), alone and combined with the parked USDJPY legs (runs/basket/legs, approved sizing). For every
subset of up to `max_legs` legs and every risk scale, the challenge is replayed from each trading-day start
(two windows: all years and 2018 on). Baskets are ranked by the goal's `rank_by` (pass within 60 days) among
those meeting its constraints. The goal is met when the best basket clears config/goal.yaml.
"""
from __future__ import annotations

import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from ..data import store
from ..engine.prop import SUMMARY_HEADER, Leg, PropRules, format_summary, mix_equity, simulate, summarize
from .state import ResearchState

RUNS = store.ROOT / "runs"
GOAL_CONFIG = store.ROOT / "config" / "goal.yaml"
DEFAULT_GOAL = {"pass_le_2m_min_pct": 50.0, "fail_le_2m_max_pct": 15.0, "pass_eventually_min_pct": 60.0,
                "rank_by": "pass_le_2m_pct", "window": "2018"}


def load_goal() -> dict:
    if GOAL_CONFIG.exists():
        g = dict(DEFAULT_GOAL)
        g.update(yaml.safe_load(GOAL_CONFIG.read_text()) or {})
        return g
    return dict(DEFAULT_GOAL)


BASKET_LEGS = RUNS / "basket" / "legs"
APPROVED_RISK = {"vol_box": 0.25, "vol_gotobi": 3.0, "fade": 0.5, "m3": 3.0}   # gj-strat sizing of the parked USDJPY legs
MAX_LEG_RISK = 4.9                                                              # one full loss must stay inside the 5% daily limit


def legs_from_good(state: ResearchState, risk_pct: float = 1.0) -> list[Leg]:
    legs = []
    for h in state.bucket("good"):
        folder = RUNS / h["slug"]
        for path in sorted(folder.glob("trades_full_*.parquet")):
            sym = path.stem.replace("trades_full_", "")
            t = pl.read_parquet(path)
            if t.height:
                legs.append(Leg(f"{h['slug']}:{sym}", t, risk_pct))
    return legs


def legs_from_basket() -> list[Leg]:
    """The parked USDJPY legs (scripts/basket_legs.py) at their approved risk, so new edges are judged in combination."""
    legs = []
    if not BASKET_LEGS.exists():
        return legs
    for name, risk in APPROVED_RISK.items():
        path = BASKET_LEGS / f"{name}.parquet"
        if path.exists():
            t = pl.read_parquet(path).select("entry_ts", "exit_ts", "r_net", "mae_r")
            if t.height:
                legs.append(Leg(f"basket:{name}", t, risk))
    return legs


def daily_r_correlation(legs: list[Leg]) -> pl.DataFrame:
    frames = []
    for leg in legs:
        d = leg.trades.group_by(pl.col("exit_ts").dt.date().alias("day")).agg(pl.col("r_net").sum().alias(leg.name))
        frames.append(d)
    if not frames:
        return pl.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.join(f, on="day", how="full", coalesce=True)
    out = out.fill_null(0.0).sort("day")
    cols = [c for c in out.columns if c != "day"]
    if len(cols) < 2:
        return pl.DataFrame({"leg": cols})
    mat = np.corrcoef(out.select(cols).to_numpy().T)
    return pl.DataFrame({"leg": cols, **{c: mat[:, i] for i, c in enumerate(cols)}})


def basket_search(legs: list[Leg], rules: PropRules, scales: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0),
                  max_legs: int = 4, since: str | None = "2018-01-01", always: list[Leg] | None = None) -> pl.DataFrame:
    """Every subset of up to `max_legs` of `legs`, each leg's risk = its base risk x scale (capped at MAX_LEG_RISK),
    optionally combined with the `always` legs (the parked basket) at their base risk x the same scale."""
    rows = []
    n = len(legs)
    always = always or []
    combos = [c for k in range(0 if always else 1, min(max_legs, n) + 1) for c in itertools.combinations(range(n), k)]
    for combo in combos:
        for scale in scales:
            mix = [Leg(legs[i].name, legs[i].trades, min(legs[i].risk_pct * scale, MAX_LEG_RISK)) for i in combo]
            mix += [Leg(a.name, a.trades, min(a.risk_pct * scale, MAX_LEG_RISK)) for a in always]
            if not mix:
                continue
            for window, lo in (("all", None), ("2018", since)):
                sub = mix if lo is None else [Leg(l.name, l.trades.filter(pl.col("entry_ts") >= pl.lit(lo).str.to_datetime(time_zone="UTC")), l.risk_pct) for l in mix]
                if any(l.trades.height < 20 for l in sub):
                    continue
                out = simulate(sub, rules)
                s = summarize(out)
                eq = mix_equity(sub)
                rows.append({"legs": " + ".join(f"{l.name}@{l.risk_pct:g}%" for l in mix), "n_legs": len(mix), "scale": scale, "window": window, **s,
                             "cagr_pct": eq["cagr_pct"], "max_dd_pct": eq["max_dd_pct"]})
    return pl.DataFrame(rows) if rows else pl.DataFrame()


CONSTRAINTS = (("pass_le_2m_min_pct", "pass_le_2m_pct", ">="), ("fail_le_2m_max_pct", "fail_le_2m_pct", "<="),
               ("pass_eventually_min_pct", "pass_eventually_pct", ">="), ("pass_le_3m_min_pct", "pass_le_3m_pct", ">="),
               ("fail_le_6m_max_pct", "fail_le_6m_pct", "<="), ("months_per_funded_account_max", "months_per_funded_account", "<="))


def pick_best(table: pl.DataFrame, goal: dict) -> dict | None:
    """Best basket on the goal window: among those meeting every constraint present in the goal, the best by `rank_by`
    (higher is better unless it is months_per_funded_account); if none meets them, the best by rank among all."""
    if table.height == 0:
        return None
    w = table.filter(pl.col("window") == goal.get("window", "2018"))
    mask = pl.lit(True)
    for key, col, op in CONSTRAINTS:
        if key in goal and goal[key] is not None and col in w.columns:
            mask = mask & ((pl.col(col) >= goal[key]) if op == ">=" else (pl.col(col) <= goal[key]))
    ok = w.filter(mask)
    rank = goal.get("rank_by", "pass_le_2m_pct")
    descending = rank != "months_per_funded_account"
    pool = ok if ok.height else w
    if pool.height == 0:
        return None
    best = pool.sort(rank, descending=descending).row(0, named=True)
    best["meets_goal"] = bool(ok.height)
    return best


def evaluate(state: ResearchState, rules: PropRules | None = None, out_dir: Path = RUNS / "basket") -> dict:
    rules = rules or PropRules.load()
    goal = load_goal()
    legs = legs_from_good(state)
    parked = legs_from_basket()
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {"ran": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rules": rules.name, "goal": goal,
                    "legs": [l.name for l in legs], "parked_legs": [l.name for l in parked], "best": None, "meets_goal": False}
    if not legs:
        (out_dir / "basket.json").write_text(json.dumps(result, indent=1, default=str))
        return result
    table = pl.concat([basket_search(legs, rules), basket_search(legs, rules, always=parked)]) if parked else basket_search(legs, rules)
    corr = daily_r_correlation(legs + parked)
    best = pick_best(table, goal)
    result["best"] = best
    result["meets_goal"] = bool(best and best.get("meets_goal"))
    table.write_csv(out_dir / "basket_table.csv")
    if corr.height:
        corr.write_csv(out_dir / "correlation.csv")
    (out_dir / "basket.json").write_text(json.dumps(result, indent=1, default=str))
    lines = [f"# Baskets ({rules.firm} {rules.plan}), evaluated {result['ran']}", "", f"Goal: {goal}", "",
             "## Best basket", json.dumps(best, indent=1, default=str) if best else "(none)", "", "## All baskets (window 2018+)", SUMMARY_HEADER]
    rank = goal.get("rank_by", "pass_le_2m_pct")
    for r in table.filter(pl.col("window") == "2018").sort(rank, descending=rank != "months_per_funded_account").head(40).to_dicts():
        lines.append(format_summary(r["legs"], r))
    (out_dir / "basket.md").write_text("\n".join(lines) + "\n")
    if result["meets_goal"]:
        (RUNS / "GOAL_REACHED").write_text(json.dumps(best, indent=1, default=str))
    return result
