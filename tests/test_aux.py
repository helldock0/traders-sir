"""Auxiliary markets: as-of alignment, truncation at the primary horizon, and leak detection through aux data."""
from __future__ import annotations

import types

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals
from edge.research.leaktest import leak_report, perturbation_test


def walk(n: int, seed: int, start: float, step: float) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, step, n))
    open_ = np.concatenate([[start], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, step / 2, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, step / 2, n))
    return open_, high, low, close


def market(sym: str, n: int, seed: int, start: float, step: float, spread: float, tf: str = "M5") -> Market:
    o, h, l, c = walk(n, seed, start, step)
    ts = np.datetime64("2020-01-06T00:00", "us") + (np.arange(n) * 5).astype("timedelta64[m]")
    return Market(sym, tf, ts, o, h, l, c, o + spread, h + spread, l + spread, c + spread, np.ones(n), np.ones(n),
                  0.0001 if sym != "USATECHIDXUSD" else 1.0, 0.00001, "fx" if sym != "USATECHIDXUSD" else "index", 0.0)


def primary_with_aux(n: int = 12_000) -> Market:
    m = market("AUDJPY", n, 1, 90.0, 0.01, 0.01)
    m.aux["USATECHIDXUSD"] = market("USATECHIDXUSD", n, 2, 15000.0, 3.0, 1.0)
    return m


def test_aux_asof_uses_only_closed_bars():
    m = primary_with_aux(500)
    a = m.aux["USATECHIDXUSD"]
    v = F.aux_asof(m, "USATECHIDXUSD")
    # same grid, same timeframe: bar i of the aux closes with bar i of the primary
    assert np.allclose(v, a.bid_c)
    # shift the aux grid 1 minute later: its bar i closes after the primary bar i -> as-of must use bar i-1
    a.ts = a.ts + np.timedelta64(1, "m")
    v2 = F.aux_asof(m, "USATECHIDXUSD")
    assert np.isnan(v2[0]) and np.allclose(v2[1:], a.bid_c[:-1])


def test_rows_cut_aux_at_horizon():
    m = primary_with_aux(1000)
    h = m.head(400)
    assert h.aux["USATECHIDXUSD"].n == 400
    m.aux["USATECHIDXUSD"].ts = m.aux["USATECHIDXUSD"].ts + np.timedelta64(1, "m")
    h2 = m.head(400)
    assert h2.aux["USATECHIDXUSD"].n == 399


def aux_strategy(leaky: bool) -> types.ModuleType:
    mod = types.ModuleType("aux_strat")
    mod.NAME, mod.PARAMS = "aux_strat", {"thr": 20.0}

    def signals(m: Market, p: dict) -> Signals:
        s = Signals(m.n)
        if leaky:
            a = m.aux["USATECHIDXUSD"]
            nxt = np.concatenate([a.bid_c[1:], [np.nan]])          # tomorrow's index close: look-ahead through aux
            cond = (nxt - a.bid_c) < -p["thr"]
        else:
            idx = F.aux_asof(m, "USATECHIDXUSD")
            prev = F.shift(idx, 12)
            cond = (idx - prev) < -p["thr"]
        s.entry_short[:] = np.nan_to_num(cond, nan=False).astype(bool)
        s.sl_dist[:] = 0.20
        s.tp_dist[:] = 0.20
        return s
    mod.signals = signals
    return mod


def test_clean_aux_strategy_passes_leak_tests():
    rep = leak_report(aux_strategy(False), primary_with_aux())
    assert rep["ok"], rep
    assert rep["aux_markets"] == ["USATECHIDXUSD"]


def test_aux_leak_is_caught():
    rep = perturbation_test(aux_strategy(True), primary_with_aux())
    assert not rep["ok"]
