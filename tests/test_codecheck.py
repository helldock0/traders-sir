"""Checker tests: static rules and the dynamic parameter/leak checks on a synthetic market."""
from __future__ import annotations

import numpy as np

from edge.agents.codecheck import dynamic_check, load_module_from_code, static_check
from edge.engine.market import Market

GOOD = '''
"""Test strategy."""
import numpy as np
from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "chk_good"
PARAMS = {"lookback": 50, "sl_pips": 10.0}
GRID = {"lookback": [20, 50], "sl_pips": [10.0, 20.0]}

def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    lb = int(p["lookback"])
    sma = F.rolling_mean(m.bid_c, lb)
    prev_c = F.shift(m.bid_c, 1)
    prev_sma = F.shift(sma, 1)
    cross = (m.bid_c > sma) & (prev_c <= prev_sma)
    s.entry_long[:] = np.nan_to_num(cross, nan=False).astype(bool)
    s.sl_dist[:] = p["sl_pips"] * m.pip
    s.tp_dist[:] = p["sl_pips"] * m.pip
    return s
'''

BAD_IMPORT = GOOD.replace("import numpy as np", "import numpy as np\nimport os")
LEAKY = GOOD.replace("cross = (m.bid_c > sma) & (prev_c <= prev_sma)", "cross = np.concatenate([m.bid_c[1:] > m.bid_c[:-1] + 0.0005, [False]])")


def synthetic_market(n: int = 30_000, seed: int = 3) -> Market:
    rng = np.random.default_rng(seed)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0002, n))
    open_ = np.concatenate([[1.10], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0001, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0001, n))
    ts = np.datetime64("2020-01-01T00:00", "us") + np.arange(n).astype("timedelta64[m]")
    sp = 0.0001
    return Market("EURUSD", "M1", ts, open_, high, low, close, open_ + sp, high + sp, low + sp, close + sp,
                  np.ones(n), np.ones(n), 0.0001, 0.00001, "fx", 0.0)


def test_static_rejects_forbidden_import():
    st = static_check(BAD_IMPORT, "x", {}, {})
    assert not st["ok"] and any("forbidden import: os" in i for i in st["issues"])


def test_dynamic_passes_good_module(tmp_path):
    mod, path, err = load_module_from_code(GOOD, "chk_good", tmp_path)
    assert err is None, err
    out = dynamic_check(mod, synthetic_market(), {"lookback": 50, "sl_pips": 10.0}, {"lookback": [20, 50], "sl_pips": [10.0, 20.0]}, sample_bars=20_000)
    assert out["ok"], out
    assert out["entries"] > 0


def test_dynamic_catches_leak(tmp_path):
    mod, path, err = load_module_from_code(LEAKY, "chk_leaky", tmp_path)
    assert err is None, err
    out = dynamic_check(mod, synthetic_market(), {"lookback": 50, "sl_pips": 10.0}, {"lookback": [20, 50], "sl_pips": [10.0, 20.0]}, sample_bars=20_000)
    assert not out["ok"]
    assert any("leak" in i for i in out["issues"])


def test_dynamic_flags_unwired_parameter(tmp_path):
    code = GOOD.replace('GRID = {"lookback": [20, 50], "sl_pips": [10.0, 20.0]}', 'GRID = {"lookback": [20, 50], "sl_pips": [10.0, 20.0], "unused": [1, 2]}')
    code = code.replace('PARAMS = {"lookback": 50, "sl_pips": 10.0}', 'PARAMS = {"lookback": 50, "sl_pips": 10.0, "unused": 1}')
    mod, path, err = load_module_from_code(code, "chk_unwired", tmp_path)
    assert err is None, err
    out = dynamic_check(mod, synthetic_market(), {"lookback": 50, "sl_pips": 10.0, "unused": 1},
                        {"lookback": [20, 50], "sl_pips": [10.0, 20.0], "unused": [1, 2]}, sample_bars=20_000)
    assert any("no effect" in i for i in out["issues"])
