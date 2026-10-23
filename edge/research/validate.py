"""Validation gates beyond the simple pass bar.

  grid_search      every parameter combination on one market, with per-split stats
  walk_forward     rolling re-optimisation on a train window, evaluation on the following test window
  stability        performance of the chosen parameters' grid neighbours
  cost_stress      the same strategy at 1.5x and 2x commission, slippage and spread
  monte_carlo      bootstrap of the trade sequence: drawdown and loss-probability distribution
  deflated_sharpe  Bailey & Lopez de Prado (2014) probability that the best-of-N Sharpe is real
  regime_check     year-by-year consistency
"""
from __future__ import annotations

import itertools
import math
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType

import numpy as np
import polars as pl
from scipy.stats import norm

from ..engine.backtest import BacktestResult, backtest
from ..engine.costs import CostModel
from ..engine.market import Market
from ..engine.stats import load_splits, tstat

EULER_GAMMA = 0.5772156649015329


def param_grid(grid: dict[str, list]) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]


def _result_row(res: BacktestResult) -> dict:
    row = {"params": res.params, "n": res.stats["all"]["n"], "avg_r": res.stats["all"]["avg_r"], "t": res.stats["all"]["t"],
           "total_r": res.stats["all"]["total_r"], "max_dd_r": res.stats["all"]["max_dd_r"], "passes_bar": res.passes_bar}
    for name in ("design", "check", "holdout"):
        s = res.stats.get(name)
        if s is not None:
            row[f"{name}_n"] = s["n"]
            row[f"{name}_avg_r"] = s["avg_r"]
            row[f"{name}_t"] = s["t"]
    return row


def grid_search(mod: ModuleType, m: Market, grid: dict[str, list], costs: CostModel | None = None,
                workers: int = 8, splits: dict | None = None) -> tuple[pl.DataFrame, list[BacktestResult]]:
    combos = param_grid(grid)
    costs = costs or CostModel()

    def run(p: dict) -> BacktestResult:
        return backtest(mod, m.sym, m.tf, p, costs, market=m, splits=splits)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        results = list(ex.map(run, combos))
    rows = [_result_row(r) for r in results]
    df = pl.DataFrame([{**{k: str(v) for k, v in r["params"].items()}, **{k: v for k, v in r.items() if k != "params"}} for r in rows])
    return df, results


def _window_stats(trades: pl.DataFrame, lo: np.datetime64, hi: np.datetime64) -> tuple[int, float, float]:
    if trades.height == 0:
        return 0, float("nan"), float("nan")
    ts = trades.get_column("entry_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
    r = trades.get_column("r_net").to_numpy()
    sel = (ts >= lo) & (ts < hi)
    rr = r[sel]
    return int(len(rr)), (float(rr.mean()) if len(rr) else float("nan")), tstat(rr)


def walk_forward(mod: ModuleType, m: Market, grid: dict[str, list], costs: CostModel | None = None,
                 train_years: int = 4, test_years: int = 1, step_years: int = 1, objective: str = "t",
                 min_train_trades: int = 30, first_year: int | None = None, last_year: int | None = None,
                 workers: int = 8, results: list[BacktestResult] | None = None) -> dict:
    """Pick the best combo on each train window, evaluate on the next test window, pool the OOS trades.

    `results` may carry the grid's backtests on this market (one per combo) to avoid recomputing them."""
    costs = costs or CostModel()
    combos = param_grid(grid)
    y0 = first_year or int(str(m.ts[0].astype("datetime64[Y]")))
    y1 = last_year or int(str(m.ts[-1].astype("datetime64[Y]")))

    if results is None:
        # one backtest per combo on the whole market; windows are then evaluated by slicing trades (same signals)
        def run(p: dict) -> BacktestResult:
            return backtest(mod, m.sym, m.tf, p, costs, market=m)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            results = list(ex.map(run, combos))

    windows = []
    oos_frames = []
    is_avgs, oos_avgs = [], []
    for ty in range(y0 + train_years, y1 - test_years + 2, step_years):
        tr_lo, tr_hi = np.datetime64(f"{ty - train_years}-01-01", "us"), np.datetime64(f"{ty}-01-01", "us")
        te_lo, te_hi = tr_hi, np.datetime64(f"{ty + test_years}-01-01", "us")
        if te_lo > m.ts[-1]:
            break
        best, best_score, best_is = None, -np.inf, None
        for res in results:
            n, avg, t = _window_stats(res.trades, tr_lo, tr_hi)
            if n < min_train_trades:
                continue
            score = t if objective == "t" else avg
            if score == score and score > best_score:
                best, best_score, best_is = res, score, (n, avg, t)
        if best is None:
            windows.append({"test_year": ty, "chosen": None, "reason": "no combo with enough train trades"})
            continue
        n_te, avg_te, t_te = _window_stats(best.trades, te_lo, te_hi)
        ts = best.trades.get_column("entry_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
        oos_frames.append(best.trades.filter(pl.Series((ts >= te_lo) & (ts < te_hi))))
        windows.append({"test_year": ty, "chosen": best.params, "train_n": best_is[0], "train_avg_r": best_is[1],
                        "train_t": best_is[2], "test_n": n_te, "test_avg_r": avg_te, "test_t": t_te})
        is_avgs.append(best_is[1])
        oos_avgs.append(avg_te)
    oos = pl.concat(oos_frames) if oos_frames else pl.DataFrame()
    r = oos.get_column("r_net").to_numpy() if oos.height else np.array([])
    valid = [(a, b) for a, b in zip(is_avgs, oos_avgs) if b == b]
    eff = (float(np.mean([b for _, b in valid]) / np.mean([a for a, _ in valid])) if valid and np.mean([a for a, _ in valid]) > 0 else float("nan"))
    return {
        "windows": windows,
        "oos_n": int(len(r)),
        "oos_avg_r": float(r.mean()) if len(r) else float("nan"),
        "oos_t": tstat(r) if len(r) else float("nan"),
        "oos_total_r": float(r.sum()) if len(r) else 0.0,
        "windows_positive": int(sum(1 for b in oos_avgs if b == b and b > 0)),
        "windows_total": int(sum(1 for b in oos_avgs if b == b)),
        "wf_efficiency": eff,
        "oos_trades": oos,
    }


def stability(grid_df: pl.DataFrame, grid: dict[str, list], best: dict, metric: str = "avg_r") -> dict:
    """Neighbours = combos differing from `best` by one grid step in exactly one dimension."""
    keys = [k for k in grid if k in best]
    rows = grid_df.to_dicts()
    def lookup(p: dict):
        for r in rows:
            if all(str(r[k]) == str(p[k]) for k in keys):
                return r
        return None
    base = lookup(best)
    neigh = []
    for k in keys:
        vals = list(grid[k])
        if best[k] not in vals:
            continue
        i = vals.index(best[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                p = dict(best)
                p[k] = vals[j]
                r = lookup(p)
                if r is not None:
                    neigh.append(r[metric])
    neigh = [x for x in neigh if x == x]
    base_v = base[metric] if base else float("nan")
    return {
        "best": base_v, "neighbours": len(neigh),
        "neighbours_positive": int(sum(1 for x in neigh if x > 0)),
        "neighbour_mean": float(np.mean(neigh)) if neigh else float("nan"),
        "neighbour_ratio": float(np.mean(neigh) / base_v) if neigh and base_v and base_v > 0 else float("nan"),
        "share_grid_positive": float((grid_df.get_column(metric) > 0).mean()) if grid_df.height else float("nan"),
    }


def cost_stress(mod: ModuleType, m: Market, params: dict, costs: CostModel | None = None,
                multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)) -> list[dict]:
    costs = costs or CostModel()
    out = []
    for mult in multipliers:
        cm = CostModel(commission_per_lot_usd=costs.commission_per_lot_usd * mult,
                       commission_per_lot_usd_cfd=costs.commission_per_lot_usd_cfd * mult,
                       slippage_pips=costs.slippage_pips * mult, slippage_points_cfd=costs.slippage_points_cfd * mult,
                       swap_markup_pct=costs.swap_markup_pct, cfd_financing_markup_pct=costs.cfd_financing_markup_pct,
                       include_swap=costs.include_swap, rates_dir=costs.rates_dir)
        mm = m if mult == 1.0 else m.widen_spread(mult)
        res = backtest(mod, m.sym, m.tf, params, cm, market=mm)
        a = res.stats["all"]
        out.append({"mult": mult, "n": a["n"], "avg_r": a["avg_r"], "t": a["t"], "total_r": a["total_r"],
                    "check_avg_r": res.stats.get("check", {}).get("avg_r"), "holdout_avg_r": res.stats.get("holdout", {}).get("avg_r")})
    return out


def monte_carlo(r: np.ndarray, n_sims: int = 2000, seed: int = 0, block: int = 1) -> dict:
    """Bootstrap the trade sequence (optionally in blocks) and report drawdown and loss probabilities."""
    rng = np.random.default_rng(seed)
    n = len(r)
    if n < 5:
        return {"n": n}
    dds, totals = np.empty(n_sims), np.empty(n_sims)
    for s in range(n_sims):
        if block <= 1:
            x = r[rng.integers(0, n, n)]
        else:
            starts = rng.integers(0, max(1, n - block), int(np.ceil(n / block)))
            x = np.concatenate([r[i:i + block] for i in starts])[:n]
        eq = np.cumsum(x)
        peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
        dds[s] = (peak - eq).max()
        totals[s] = eq[-1]
    return {
        "n": int(n), "sims": int(n_sims),
        "dd_r_p50": float(np.percentile(dds, 50)), "dd_r_p95": float(np.percentile(dds, 95)), "dd_r_p99": float(np.percentile(dds, 99)),
        "total_r_p05": float(np.percentile(totals, 5)), "total_r_p50": float(np.percentile(totals, 50)),
        "prob_total_negative": float((totals < 0).mean()),
    }


def deflated_sharpe(sr: float, n_obs: int, skew: float, kurt: float, n_trials: int, var_sr_trials: float) -> dict:
    """Probability that an observed per-trade Sharpe `sr` beats the Sharpe expected from the best of
    `n_trials` unskilled tries. kurt is the plain (not excess) kurtosis. Returns the probability and SR0."""
    if n_obs < 3 or not (sr == sr):
        return {"dsr": float("nan"), "sr0": float("nan")}
    n_trials = max(int(n_trials), 1)
    sd = math.sqrt(max(var_sr_trials, 1e-12))
    if n_trials > 1:
        sr0 = sd * ((1 - EULER_GAMMA) * norm.ppf(1 - 1.0 / n_trials) + EULER_GAMMA * norm.ppf(1 - 1.0 / (n_trials * math.e)))
    else:
        sr0 = 0.0
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4.0 * sr * sr, 1e-12))
    z = (sr - sr0) * math.sqrt(n_obs - 1) / denom
    return {"dsr": float(norm.cdf(z)), "sr0": float(sr0), "z": float(z)}


def sharpe_inputs(r: np.ndarray) -> dict:
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return {"sr": float("nan"), "skew": 0.0, "kurt": 3.0, "n": n}
    mu, sd = r.mean(), r.std(ddof=1)
    z = (r - mu) / sd
    return {"sr": float(mu / sd), "skew": float((z ** 3).mean()), "kurt": float((z ** 4).mean()), "n": int(n)}


def regime_check(by_year: dict[int, float]) -> dict:
    vals = list(by_year.values())
    if not vals:
        return {"years": 0}
    return {"years": len(vals), "positive_years": int(sum(1 for v in vals if v > 0)),
            "share_positive": float(np.mean([v > 0 for v in vals])), "worst_year_r": float(min(vals)),
            "best_year_r": float(max(vals)), "worst_year": int(min(by_year, key=by_year.get))}
