"""External series: as-of alignment, truncation at the primary horizon, and leak detection through releases."""
from __future__ import annotations

import types

import numpy as np
import polars as pl

from edge.engine import features as F
from edge.engine.external import ExtSeries
from edge.engine.market import Market
from edge.engine.strategy import Signals
from edge.research.leaktest import leak_report
from tests.test_aux import market


def releases(n_days: int = 60, seed: int = 3) -> ExtSeries:
    """One 'release' per weekday at 13:30 UTC with a surprise value and a text tag."""
    rng = np.random.default_rng(seed)
    days = np.datetime64("2020-01-06", "D") + np.arange(n_days)
    days = days[(days.astype("datetime64[D]").astype(np.int64) + 3) % 7 < 5]
    ts = days.astype("datetime64[us]") + np.timedelta64(13 * 60 + 30, "m")
    z = rng.normal(0, 1, len(ts))
    frame = pl.DataFrame({"ts_avail": ts, "surprise_z": z, "currency": ["USD" if i % 2 == 0 else "EUR" for i in range(len(ts))]})
    return ExtSeries("calendar", ts, frame)


def primary_with_ext(n: int = 12_000) -> Market:
    m = market("EURUSD", n, 1, 1.10, 0.0002, 0.0001)
    m.ext["calendar"] = releases()
    return m


def test_ext_asof_uses_only_released_rows():
    m = primary_with_ext(2000)
    e = m.ext["calendar"]
    v = F.ext_asof(m, "calendar", "surprise_z")
    close = m.close_times()
    for i in (0, 500, 1999):
        k = int(np.searchsorted(e.ts_avail, close[i], side="right")) - 1
        if k < 0:
            assert np.isnan(v[i])
        else:
            assert v[i] == e.column("surprise_z")[k]
    # a bar that closes exactly at a release sees it; the bar before does not
    j = int(np.searchsorted(close, e.ts_avail[0]))
    assert close[j] >= e.ts_avail[0]
    assert np.isnan(v[j - 1]) and not np.isnan(v[j])


def test_ext_recent_window_and_subset():
    m = primary_with_ext(3000)
    e = m.ext["calendar"]
    usd = F.ext_subset(m, "calendar", e.column("currency") == "USD")
    assert usd.n == int((e.column("currency") == "USD").sum())
    flag = F.ext_recent(m, usd, 60)
    val = F.ext_recent(m, usd, 60, "surprise_z")
    assert flag.dtype == bool and flag.sum() > 0
    assert np.isnan(val[~flag]).all() and np.isfinite(val[flag]).all()
    # each USD release is 'recent' for exactly the bars closing within 60 minutes after it (5-minute bars -> 12 bars)
    close = m.close_times()
    first = int(np.searchsorted(close, usd.ts_avail[0]))
    assert flag[first:first + 12].all() and not flag[first + 12] and not flag[first - 1]
    since = F.ext_minutes_since(m, usd)
    assert since[first] == float((close[first] - usd.ts_avail[0]) / np.timedelta64(1, "m"))


def test_rows_cut_ext_at_horizon():
    m = primary_with_ext(3000)
    h = m.head(1000)
    horizon = m.ts[999] + np.timedelta64(5, "m")
    assert h.ext["calendar"].n == int((m.ext["calendar"].ts_avail <= horizon).sum())
    assert h.ext["calendar"].n < m.ext["calendar"].n


def ext_strategy(leaky: bool) -> types.ModuleType:
    mod = types.ModuleType("ext_strat")
    mod.NAME, mod.PARAMS = "ext_strat", {"thr": 0.5}

    def signals(m: Market, p: dict) -> Signals:
        s = Signals(m.n)
        if leaky:
            e = m.ext["calendar"]
            # use each release from one hour BEFORE it is out: look-ahead through the external series
            idx = np.searchsorted(e.ts_avail - np.timedelta64(60, "m"), m.close_times(), side="right") - 1
            z = np.full(m.n, np.nan)
            z[idx >= 0] = e.column("surprise_z")[idx[idx >= 0]]
            cond = z > p["thr"]
        else:
            cond = F.ext_recent(m, "calendar", 60, "surprise_z") > p["thr"]
        s.entry_long[:] = np.nan_to_num(cond, nan=False).astype(bool)
        s.sl_dist[:] = 0.002
        s.tp_dist[:] = 0.002
        return s
    mod.signals = signals
    return mod


def test_clean_ext_strategy_passes_leak_tests():
    rep = leak_report(ext_strategy(False), primary_with_ext())
    assert rep["ok"], rep
    assert rep["n_entries"] > 0 and rep["ext_series"] == ["calendar"]


def test_leaky_ext_strategy_is_caught():
    m = primary_with_ext()
    rep = leak_report(ext_strategy(True), m)
    assert not rep["ok"], rep
    # a leak that reaches only one hour ahead of sparse releases slips between the fixed-fraction cuts
    # (truncation and perturbation can both pass) but the release-aligned probes catch it
    assert not rep["ext_release"]["ok"]
    assert any(p["truncation_mismatches"] > 0 or p["perturbation_mismatches"] > 0 for p in rep["ext_release"]["probes"])
