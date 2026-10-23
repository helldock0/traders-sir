"""Run one strategy on one market: signals -> executor -> costs -> stats."""
from __future__ import annotations

import importlib
import importlib.util
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import polars as pl

from .costs import CostModel, Rates, apply_costs
from .executor import execute
from .market import Market, load_market
from .stats import load_splits, passes_bar, r_by_year, split_stats
from .strategy import run_signals

_MARKET_CACHE: dict[tuple, Market] = {}
_RATES: Rates | None = None


def get_market(sym: str, tf: str, start: str | None = None, end: str | None = None, cache: bool = True,
               aux: tuple[str, ...] | list[str] = (), ext: tuple[str, ...] | list[str] = ()) -> Market:
    aux_key = tuple(sorted(a.upper() for a in aux if a.upper() != sym.upper()))
    ext_key = tuple(sorted(e.lower() for e in ext))
    key = (sym.upper(), tf.upper(), start, end, aux_key, ext_key)
    if cache and key in _MARKET_CACHE:
        return _MARKET_CACHE[key]
    m = load_market(sym, tf, start, end, aux=aux_key, ext=ext_key)
    if cache:
        if len(_MARKET_CACHE) >= 12:
            _MARKET_CACHE.pop(next(iter(_MARKET_CACHE)))
        _MARKET_CACHE[key] = m
    return m


def clear_market_cache() -> None:
    _MARKET_CACHE.clear()


def load_strategy(path_or_module: str | Path) -> ModuleType:
    """Import a strategy from a dotted module name or a .py file path."""
    p = Path(str(path_or_module))
    if p.suffix == ".py" and p.exists():
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod
    return importlib.import_module(str(path_or_module))


@dataclass
class BacktestResult:
    strategy: str
    sym: str
    tf: str
    params: dict
    trades: pl.DataFrame
    stats: dict[str, dict]
    by_year: dict[int, float]
    passes_bar: bool
    seconds: float
    notes: dict = field(default_factory=dict)

    def summary(self) -> dict:
        a = self.stats.get("all", {})
        return {
            "strategy": self.strategy, "sym": self.sym, "tf": self.tf, "params": self.params,
            "n": a.get("n", 0), "avg_r": a.get("avg_r"), "t": a.get("t"),
            "design_t": self.stats.get("design", {}).get("t"),
            "check_avg_r": self.stats.get("check", {}).get("avg_r"),
            "holdout_avg_r": self.stats.get("holdout", {}).get("avg_r"),
            "passes_bar": self.passes_bar, "seconds": round(self.seconds, 2),
        }


def backtest(mod: ModuleType, sym: str, tf: str, params: dict | None = None, costs: CostModel | None = None,
             start: str | None = None, end: str | None = None, market: Market | None = None,
             be_trigger_r: float = 0.0, be_lock_r: float = 0.0, trail_r: float = 0.0,
             splits: dict | None = None, aux: tuple[str, ...] | list[str] = (),
             ext: tuple[str, ...] | list[str] = ()) -> BacktestResult:
    global _RATES
    t0 = time.time()
    costs = costs or CostModel()
    m = market or get_market(sym, tf, start, end, aux=aux, ext=ext)
    sig = run_signals(mod, m, params)
    trades = execute(m, sig, slippage=costs.slippage_price(m), be_trigger_r=be_trigger_r,
                     be_lock_r=be_lock_r, trail_r=trail_r)
    if costs.include_swap and _RATES is None:
        _RATES = Rates(costs.rates_dir)
    trades = apply_costs(trades, m, costs, _RATES)
    splits = splits or load_splits()
    st = split_stats(trades, splits)
    full_params = dict(getattr(mod, "PARAMS", {}))
    full_params.update(params or {})
    return BacktestResult(
        strategy=getattr(mod, "NAME", mod.__name__), sym=m.sym, tf=m.tf, params=full_params, trades=trades,
        stats=st, by_year=r_by_year(trades), passes_bar=passes_bar(st), seconds=time.time() - t0,
        notes={"ask_modelled_share": m.ask_modelled_share, "bars": m.n, "aux_markets": sorted(m.aux), "ext_series": sorted(m.ext)},
    )
