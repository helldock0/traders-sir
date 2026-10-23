"""Leak test and validation helpers on synthetic data and a deliberately leaking strategy."""
from __future__ import annotations

import types

import numpy as np
import pytest

from edge.engine.market import Market
from edge.engine.strategy import Signals
from edge.research.leaktest import leak_report, perturbation_test, truncation_test
from edge.research.validate import deflated_sharpe, monte_carlo, param_grid, sharpe_inputs, stability

import polars as pl


def synthetic_market(n: int = 20_000, seed: int = 1) -> Market:
    rng = np.random.default_rng(seed)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0002, n))
    open_ = np.concatenate([[1.10], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0001, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0001, n))
    ts = np.datetime64("2020-01-01T00:00", "us") + np.arange(n).astype("timedelta64[m]")
    spread = 0.0001
    return Market("EURUSD", "M1", ts, open_, high, low, close, open_ + spread, high + spread, low + spread, close + spread,
                  np.ones(n), np.ones(n), 0.0001, 0.00001, "fx", 0.0)


def clean_strategy() -> types.ModuleType:
    mod = types.ModuleType("clean")
    mod.NAME, mod.PARAMS = "clean", {"lookback": 50}

    def signals(m: Market, p: dict) -> Signals:
        s = Signals(m.n)
        c = m.bid_c
        lb = p["lookback"]
        sma = np.full(m.n, np.nan)
        cs = np.cumsum(np.insert(c, 0, 0.0))
        sma[lb - 1:] = (cs[lb:] - cs[:-lb]) / lb
        prev = np.roll(sma, 1)
        s.entry_long[:] = (c > sma) & (np.roll(c, 1) <= prev)
        s.entry_long[:lb] = False
        s.sl_dist[:] = 0.0010
        s.tp_dist[:] = 0.0010
        return s
    mod.signals = signals
    return mod


def leaky_strategy() -> types.ModuleType:
    mod = types.ModuleType("leaky")
    mod.NAME, mod.PARAMS = "leaky", {}

    def signals(m: Market, p: dict) -> Signals:
        s = Signals(m.n)
        nxt = np.roll(m.bid_c, -1)          # tomorrow's close: look-ahead
        s.entry_long[:-1] = nxt[:-1] > m.bid_c[:-1] + 0.0003
        s.sl_dist[:] = 0.0010
        s.tp_dist[:] = 0.0010
        return s
    mod.signals = signals
    return mod


def global_leak_strategy() -> types.ModuleType:
    mod = types.ModuleType("zscore_leak")
    mod.NAME, mod.PARAMS = "zscore_leak", {}

    def signals(m: Market, p: dict) -> Signals:
        s = Signals(m.n)
        z = (m.bid_c - m.bid_c.mean()) / m.bid_c.std()      # full-sample statistics: look-ahead
        s.entry_long[:] = z < -1.5
        s.sl_dist[:] = 0.0010
        s.tp_dist[:] = 0.0010
        return s
    mod.signals = signals
    return mod


def test_leak_report_passes_clean_strategy():
    m = synthetic_market()
    rep = leak_report(clean_strategy(), m)
    assert rep["ok"], rep


def test_perturbation_catches_next_bar_leak():
    m = synthetic_market()
    rep = perturbation_test(leaky_strategy(), m)
    assert not rep["ok"]
    # the mismatch sits at the boundary bar, whose "tomorrow" was replaced
    assert any(p["mismatches"] >= 1 and p["first_mismatch"] == p["k"] - 1 for p in rep["probes"])


def test_truncation_catches_global_statistic_leak():
    m = synthetic_market()
    rep = truncation_test(global_leak_strategy(), m)
    assert not rep["ok"]


def test_param_grid_and_stability():
    grid = {"a": [1, 2, 3], "b": [10, 20]}
    combos = param_grid(grid)
    assert len(combos) == 6
    df = pl.DataFrame({"a": [str(c["a"]) for c in combos], "b": [str(c["b"]) for c in combos],
                       "avg_r": [0.1, 0.2, 0.15, -0.1, 0.05, 0.0]})
    st = stability(df, grid, {"a": 2, "b": 10})
    assert st["neighbours"] == 3            # a=1,b=10 ; a=3,b=10 ; a=2,b=20
    assert st["neighbours_positive"] == 2


def test_monte_carlo_and_dsr():
    rng = np.random.default_rng(0)
    r = rng.normal(0.1, 1.0, 300)
    mc = monte_carlo(r, n_sims=300)
    assert mc["dd_r_p95"] >= mc["dd_r_p50"] > 0
    si = sharpe_inputs(r)
    strong = deflated_sharpe(si["sr"], si["n"], si["skew"], si["kurt"], n_trials=1, var_sr_trials=0.0)
    many = deflated_sharpe(si["sr"], si["n"], si["skew"], si["kurt"], n_trials=500, var_sr_trials=0.01)
    assert strong["dsr"] > many["dsr"]
    assert 0.0 <= many["dsr"] <= 1.0
