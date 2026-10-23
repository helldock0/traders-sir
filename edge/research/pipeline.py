"""Staged evaluation of one hypothesis, holdout locked.

  Stage 0  leak tests on the primary market (truncation, determinism)
  Stage A  coarse grid on the primary market, design years only; kill if nothing clears the floor
  Stage B  full grid on every market in the spec, design years; best combo per market by design t
  Stage C  for the chosen combos: check-period stats, walk-forward over design+check, parameter
           stability, cost stress, Monte Carlo, deflated Sharpe, regime check
  Locked   holdout evaluation, run only when the Director promotes; every run is counted

Every market used in stages 0-C is cut at the first holdout day, so holdout bars are never seen.
Everything is written to runs/<slug>/ (report.md, report.json, trades_<SYM>.parquet).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

from ..data import store
from ..engine.backtest import BacktestResult, backtest, get_market, load_strategy
from ..engine.costs import CostModel
from ..engine.stats import format_split_table, load_splits
from .leaktest import leak_report
from .state import ResearchState
from .validate import (cost_stress, deflated_sharpe, grid_search, monte_carlo, param_grid, regime_check,
                       sharpe_inputs, stability, walk_forward)

RUNS_DIR = store.ROOT / "runs"


@dataclass
class HypothesisSpec:
    slug: str
    title: str
    family: str
    rationale: str
    markets: list[str]
    timeframe: str
    strategy_path: str
    params: dict = field(default_factory=dict)
    grid: dict = field(default_factory=dict)
    stage_a: dict = field(default_factory=dict)          # {"market": "EURUSD", "grid": {...}}
    pre_registered: dict = field(default_factory=dict)   # expectations and kill rules, written before any run
    costs: dict = field(default_factory=dict)            # CostModel overrides
    notes: str = ""
    aux_markets: list[str] = field(default_factory=list)  # auxiliary instruments the signals may condition on
    ext_series: list[str] = field(default_factory=list)   # external series (calendar, cot, vol) the signals may condition on

    @classmethod
    def from_json(cls, path: str | Path) -> "HypothesisSpec":
        d = json.loads(Path(path).read_text())
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))


def coarse_grid(grid: dict[str, list], max_per_dim: int = 3) -> dict[str, list]:
    out = {}
    for k, vals in grid.items():
        vals = list(vals)
        if len(vals) <= max_per_dim:
            out[k] = vals
        else:
            idx = np.unique(np.linspace(0, len(vals) - 1, max_per_dim).round().astype(int))
            out[k] = [vals[i] for i in idx]
    return out


def dev_splits() -> dict[str, tuple[str, str]]:
    s = load_splits()
    return {k: v for k, v in s.items() if k != "holdout"}


def holdout_start() -> str:
    return load_splits()["holdout"][0]


def _best_row(df: pl.DataFrame, min_design_n: int) -> dict | None:
    if df.height == 0 or "design_t" not in df.columns:
        return None
    ok = df.filter((pl.col("design_n") >= min_design_n) & pl.col("design_t").is_not_nan())
    if ok.height == 0:
        return None
    return ok.sort("design_t", descending=True).row(0, named=True)


def _params_from_row(row: dict, grid: dict, base: dict) -> dict:
    p = dict(base)
    for k, vals in grid.items():
        if k in row:
            target = str(row[k])
            for v in vals:
                if str(v) == target:
                    p[k] = v
                    break
    return p


def _record(state: ResearchState | None, hid: int | None, stage: str, results: list[BacktestResult]) -> None:
    if state is None:
        return
    for r in results:
        state.record_trial(hid, stage, r.summary(), r.stats)


def run_pipeline(spec: HypothesisSpec, state: ResearchState | None = None, hid: int | None = None,
                 out_dir: Path | None = None, workers: int = 8, stage_a_min_t: float = 1.0,
                 min_design_n: int = 30, min_check_n: int = 30, wf_train_years: int = 4) -> dict:
    t_start = time.time()
    out_dir = out_dir or (RUNS_DIR / spec.slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"slug": spec.slug, "title": spec.title, "family": spec.family, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "spec": asdict(spec), "stages": {}, "gates": {}, "verdict": None, "failing": []}
    mod = load_strategy(spec.strategy_path)
    costs = CostModel(**spec.costs) if spec.costs else CostModel()
    splits = dev_splits()
    cut = holdout_start()
    grid = spec.grid or {k: [v] for k, v in (spec.params or getattr(mod, "PARAMS", {})).items()}
    primary = spec.stage_a.get("market") or spec.markets[0]
    aux = tuple(spec.aux_markets or ())
    ext = tuple(spec.ext_series or ())
    markets = {sym: get_market(sym, spec.timeframe, end=cut, aux=aux, ext=ext) for sym in spec.markets}
    if primary not in markets:
        markets[primary] = get_market(primary, spec.timeframe, end=cut, aux=aux, ext=ext)

    # ---- Stage 0: leak tests
    leak = leak_report(mod, markets[primary], spec.params)
    report["stages"]["leak"] = leak
    report["gates"]["G0_no_leak"] = leak["ok"]
    if not leak["ok"]:
        return _finish(report, out_dir, "fail:leak", ["G0_no_leak"], t_start)

    # ---- Stage A: coarse grid, primary market
    grid_a = spec.stage_a.get("grid") or coarse_grid(grid)
    df_a, res_a = grid_search(mod, markets[primary], grid_a, costs, workers, splits=splits)
    _record(state, hid, "A", res_a)
    best_a = _best_row(df_a, min_design_n)
    report["stages"]["A"] = {"market": primary, "grid": grid_a, "combos": df_a.height,
                             "table": df_a.sort("design_t", descending=True, nulls_last=True).head(15).to_dicts(),
                             "best": best_a}
    floor_ok = best_a is not None and best_a["design_avg_r"] > 0 and best_a["design_t"] >= stage_a_min_t
    report["gates"]["GA_stage_a_floor"] = bool(floor_ok)
    if not floor_ok:
        return _finish(report, out_dir, "kill:stage_a", ["GA_stage_a_floor"], t_start)

    # ---- Stage B: full grid, every market
    stage_b: dict = {}
    chosen: dict[str, dict] = {}
    results_b: dict[str, list[BacktestResult]] = {}
    grids_b: dict[str, pl.DataFrame] = {}
    for sym, m in markets.items():
        df_b, res_b = grid_search(mod, m, grid, costs, workers, splits=splits)
        _record(state, hid, "B", res_b)
        results_b[sym], grids_b[sym] = res_b, df_b
        best = _best_row(df_b, min_design_n)
        stage_b[sym] = {"combos": df_b.height, "best": best,
                        "top": df_b.sort("design_t", descending=True, nulls_last=True).head(5).to_dicts()}
        if best is not None:
            chosen[sym] = _params_from_row(best, grid, spec.params or getattr(mod, "PARAMS", {}))
    report["stages"]["B"] = stage_b
    positive = [s for s, b in stage_b.items() if b["best"] and b["best"]["design_avg_r"] > 0]
    report["gates"]["GB_design_positive_markets"] = len(positive)
    if not positive:
        return _finish(report, out_dir, "kill:stage_b", ["GB_design_positive_markets"], t_start)

    # ---- Stage C: validation on the chosen combos
    stage_c: dict = {}
    pooled_check, pooled_wf = [], []
    for sym in positive:
        m = markets[sym]
        p = chosen[sym]
        res = next((r for r in results_b[sym] if all(str(r.params.get(k)) == str(v) for k, v in p.items())), None)
        if res is None:
            res = backtest(mod, sym, spec.timeframe, p, costs, market=m, splits=splits)
        wf = walk_forward(mod, m, grid, costs, train_years=wf_train_years, test_years=1, step_years=1,
                          min_train_trades=min_design_n, results=results_b[sym], workers=workers)
        stab = stability(grids_b[sym], grid, p, metric="design_avg_r")
        stress = cost_stress(mod, m, p, costs)
        _record(state, hid, "C", [])
        r_all = res.trades.get_column("r_net").to_numpy()
        mc = monte_carlo(r_all, n_sims=1000)
        si = sharpe_inputs(r_all)
        n_hyp = len(param_grid(grid)) * len(markets)
        n_prog = state.n_trials() if state is not None else n_hyp
        var_sr = state.trial_sharpe_variance() if state is not None else 0.0
        var_sr_hyp = float(np.var([(row["t"] or 0.0) / max(row["n"], 1) ** 0.5 for row in grids_b[sym].to_dicts() if row["n"] and row["n"] > 2])) if grids_b[sym].height > 1 else 0.0
        dsr_h = deflated_sharpe(si["sr"], si["n"], si["skew"], si["kurt"], n_hyp, var_sr_hyp)
        dsr_p = deflated_sharpe(si["sr"], si["n"], si["skew"], si["kurt"], max(n_prog, n_hyp), max(var_sr, var_sr_hyp))
        res.trades.write_parquet(out_dir / f"trades_{sym}.parquet")
        stage_c[sym] = {
            "params": p, "stats": res.stats, "by_year": res.by_year, "regime": regime_check(res.by_year),
            "walk_forward": {k: v for k, v in wf.items() if k != "oos_trades"},
            "stability": stab, "cost_stress": stress, "monte_carlo": mc,
            "sharpe": si, "dsr_hypothesis": dsr_h, "dsr_program": dsr_p,
        }
        if wf["oos_trades"].height:
            pooled_wf.append(wf["oos_trades"].get_column("r_net").to_numpy())
        pooled_check.append(res.trades.filter(
            (pl.col("entry_ts") >= pl.lit(splits["check"][0]).str.to_datetime(time_zone="UTC"))).get_column("r_net").to_numpy())
    report["stages"]["C"] = stage_c

    # ---- gates
    chk = np.concatenate(pooled_check) if pooled_check else np.array([])
    wfr = np.concatenate(pooled_wf) if pooled_wf else np.array([])
    from ..engine.stats import tstat
    report["pooled"] = {"check_n": int(len(chk)), "check_avg_r": float(chk.mean()) if len(chk) else float("nan"),
                        "check_t": tstat(chk) if len(chk) else float("nan"),
                        "wf_oos_n": int(len(wfr)), "wf_oos_avg_r": float(wfr.mean()) if len(wfr) else float("nan"),
                        "wf_oos_t": tstat(wfr) if len(wfr) else float("nan")}
    # Hard gates decide candidate vs scrap. Soft gates are warnings the Director weighs.
    g = report["gates"]
    g["G2_check_positive"] = bool(len(chk) >= min_check_n and chk.mean() > 0)
    g["G2b_walk_forward_positive"] = bool(len(wfr) >= min_check_n and wfr.mean() > 0)
    g["G4_cost_1_5x_positive"] = bool(all(next(x for x in c["cost_stress"] if x["mult"] == 1.5)["avg_r"] > 0 for c in stage_c.values()))
    g["G5_sample_size"] = bool(len(chk) + len(wfr) >= 2 * min_check_n)
    w = report.setdefault("warnings", {})
    w["W3_stability"] = bool(all(c["stability"]["neighbours"] == 0 or c["stability"]["neighbours_positive"] >= max(1, c["stability"]["neighbours"] // 2)
                                 for c in stage_c.values()))
    w["W6_dsr_hypothesis_0_9"] = bool(any(c["dsr_hypothesis"]["dsr"] >= 0.9 for c in stage_c.values()))
    w["W6b_dsr_program_0_5"] = bool(any(c["dsr_program"]["dsr"] >= 0.5 for c in stage_c.values()))
    w["W7_regime_half_years_positive"] = bool(all(c["regime"]["share_positive"] >= 0.5 for c in stage_c.values()))
    w["W8_cost_2x_positive"] = bool(all(next(x for x in c["cost_stress"] if x["mult"] == 2.0)["avg_r"] > 0 for c in stage_c.values()))
    failing = [k for k, v in g.items() if v is False]
    verdict = "candidate" if not failing else "scrap"
    report["soft_failures"] = [k for k, v in w.items() if v is False]
    return _finish(report, out_dir, verdict, failing, t_start)


def run_locked_test(spec: HypothesisSpec, chosen: dict[str, dict], state: ResearchState | None = None,
                    hid: int | None = None, out_dir: Path | None = None) -> dict:
    """The one-shot holdout evaluation. Counted in holdout_touches."""
    out_dir = out_dir or (RUNS_DIR / spec.slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    mod = load_strategy(spec.strategy_path)
    costs = CostModel(**spec.costs) if spec.costs else CostModel()
    splits = load_splits()
    out: dict = {"slug": spec.slug, "ran": datetime.now(timezone.utc).isoformat(timespec="seconds"), "markets": {}}
    pooled = []
    for sym, p in chosen.items():
        res = backtest(mod, sym, spec.timeframe, p, costs, splits=splits, aux=tuple(spec.aux_markets or ()),
                       ext=tuple(spec.ext_series or ()))
        _record(state, hid, "locked", [res])
        h = res.stats["holdout"]
        out["markets"][sym] = {"params": p, "holdout": h, "all": res.stats["all"], "by_year": res.by_year, "passes_bar": res.passes_bar}
        ts = res.trades.get_column("entry_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
        pooled.append(res.trades.get_column("r_net").to_numpy()[ts >= np.datetime64(splits["holdout"][0], "us")])
        res.trades.write_parquet(out_dir / f"trades_full_{sym}.parquet")
    r = np.concatenate(pooled) if pooled else np.array([])
    from ..engine.stats import tstat
    out["pooled_holdout"] = {"n": int(len(r)), "avg_r": float(r.mean()) if len(r) else float("nan"), "t": tstat(r) if len(r) else float("nan")}
    out["passed"] = bool(len(r) > 0 and r.mean() > 0)
    if state is not None:
        state.touch_holdout(hid or -1, f"{spec.slug}: pooled n={len(r)} avg_r={out['pooled_holdout']['avg_r']:.4f}")
    (out_dir / "locked_test.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def _finish(report: dict, out_dir: Path, verdict: str, failing: list[str], t_start: float) -> dict:
    report["verdict"] = verdict
    report["failing"] = failing
    report["seconds"] = round(time.time() - t_start, 1)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / "report.md").write_text(render_markdown(report))
    return report


def _fmt(x, nd=3) -> str:
    if x is None:
        return ""
    if isinstance(x, float):
        return "nan" if x != x else f"{x:.{nd}f}"
    return str(x)


def render_markdown(rep: dict) -> str:
    L = [f"# {rep['title']}  (`{rep['slug']}`)", "",
         f"Family: {rep['family']} | verdict: **{rep['verdict']}** | failing gates: {', '.join(rep['failing']) or 'none'} | {rep.get('seconds', '?')}s", "",
         "## Rationale", rep["spec"].get("rationale", ""), "",
         "## Pre-registered", "```json", json.dumps(rep["spec"].get("pre_registered", {}), indent=2), "```", ""]
    L += ["## Hard gates", "| gate | result |", "|---|---|"]
    for k, v in rep["gates"].items():
        L.append(f"| {k} | {v} |")
    if rep.get("warnings"):
        L += ["", "## Soft gates (warnings for the Director)", "| check | result |", "|---|---|"]
        for k, v in rep["warnings"].items():
            L.append(f"| {k} | {v} |")
    leak = rep["stages"].get("leak")
    if leak:
        L += ["", "## Stage 0: leak tests",
              f"ok = {leak['ok']}; truncation: {leak['truncation']['ok']}; perturbation: {leak.get('perturbation', {}).get('ok')}; "
              f"determinism: {leak['determinism']['ok']}; entries: {leak.get('n_entries')}"]
    a = rep["stages"].get("A")
    if a:
        L += ["", f"## Stage A: coarse grid on {a['market']} ({a['combos']} combos, design years)", _table(a["table"])]
    b = rep["stages"].get("B")
    if b:
        L += ["", "## Stage B: full grid per market (design years)"]
        for sym, d in b.items():
            best = d["best"]
            if best is None:
                L.append(f"- {sym}: no combo with enough design trades")
            else:
                L.append(f"- {sym}: best design t {_fmt(best['design_t'], 2)}, avg R {_fmt(best['design_avg_r'])}, n {best['design_n']}; "
                         f"params {{{', '.join(f'{k}={best[k]}' for k in rep['spec']['grid'])}}}")
    c = rep["stages"].get("C")
    if c:
        L += ["", "## Stage C: validation of the chosen combos (holdout locked)"]
        p = rep.get("pooled", {})
        L.append(f"Pooled check: n {p.get('check_n')}, avg R {_fmt(p.get('check_avg_r'))}, t {_fmt(p.get('check_t'), 2)}. "
                 f"Pooled walk-forward OOS: n {p.get('wf_oos_n')}, avg R {_fmt(p.get('wf_oos_avg_r'))}, t {_fmt(p.get('wf_oos_t'), 2)}.")
        for sym, d in c.items():
            L += ["", f"### {sym}  params {d['params']}", format_split_table({k: v for k, v in d['stats'].items() if k != 'holdout'}),
                  f"R by year: { {y: round(v, 1) for y, v in d['by_year'].items()} }",
                  f"Walk-forward: OOS n {d['walk_forward']['oos_n']}, avg R {_fmt(d['walk_forward']['oos_avg_r'])}, t {_fmt(d['walk_forward']['oos_t'], 2)}, "
                  f"windows positive {d['walk_forward']['windows_positive']}/{d['walk_forward']['windows_total']}, efficiency {_fmt(d['walk_forward']['wf_efficiency'], 2)}",
                  f"Stability: neighbours positive {d['stability']['neighbours_positive']}/{d['stability']['neighbours']}, neighbour/best ratio {_fmt(d['stability']['neighbour_ratio'], 2)}, share of grid positive {_fmt(d['stability']['share_grid_positive'], 2)}",
                  "Cost stress: " + "; ".join(f"x{s['mult']}: avg R {_fmt(s['avg_r'])} (t {_fmt(s['t'], 2)})" for s in d["cost_stress"]),
                  f"Monte Carlo: DD p50 {_fmt(d['monte_carlo'].get('dd_r_p50'), 1)} R, p95 {_fmt(d['monte_carlo'].get('dd_r_p95'), 1)} R, P(total<0) {_fmt(d['monte_carlo'].get('prob_total_negative'), 2)}",
                  f"Deflated Sharpe: hypothesis-level {_fmt(d['dsr_hypothesis']['dsr'], 2)}, programme-level {_fmt(d['dsr_program']['dsr'], 2)} (per-trade SR {_fmt(d['sharpe']['sr'])}, n {d['sharpe']['n']})",
                  f"Regime: {d['regime']['positive_years']}/{d['regime']['years']} years positive, worst year {d['regime'].get('worst_year')} ({_fmt(d['regime'].get('worst_year_r'), 1)} R)"]
    return "\n".join(L) + "\n"


def _table(rows: list[dict]) -> str:
    if not rows:
        return "(no rows)"
    cols = [c for c in rows[0].keys() if c not in ("passes_bar",)]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_fmt(r.get(c), 3) for c in cols) + " |")
    return "\n".join(out)
