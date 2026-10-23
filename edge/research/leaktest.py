"""Automated look-ahead detection.

A strategy that only uses information up to bar i must produce exactly the same signal for bar i
whatever happens after it. Three checks, each comparing the signal prefix [0, k) element by element:

  truncation    signals on bars[:k] vs the full run. Catches full-sample statistics (global means,
                z-scores, quantiles, centred windows).
  perturbation  bars >= k are replaced by a distant random walk, once shifted far up and once far
                down. Catches next-bar leaks: any comparison against a future value flips in at
                least one direction.
  determinism   two identical runs must agree.

Auxiliary markets are truncated and perturbed together with the primary market, cut at the primary
bar's close time, so a strategy that reads an auxiliary bar before it has closed is caught too. External
series (m.ext) are cut by their ts_avail and their numeric columns are perturbed from the first row not yet
usable at the cut, so reading a release before it is out is caught the same way; extra cuts are placed just
before releases spread over the sample, because a leak that reaches only minutes ahead of a sparse event can
slip between the fixed-fraction cuts.
"""
from __future__ import annotations

from types import ModuleType

import numpy as np

from ..engine.market import Market, tf_minutes
from ..engine.strategy import Signals, run_signals

_COMPARE = ("entry_long", "entry_short", "entry_type", "entry_price_long", "entry_price_short", "valid_bars",
            "sl_dist", "tp_dist", "max_bars", "exit_long", "exit_short")


def _diff_prefix(full: Signals, part: Signals, k: int) -> tuple[int, int, str]:
    """(mismatch count, first mismatch index, fields) over indices [0, k)."""
    total, first, fields = 0, -1, []
    for name in _COMPARE:
        a = getattr(full, name)[:k]
        b = getattr(part, name)[:k]
        if a.dtype.kind == "f":
            neq = ~((a == b) | (np.isnan(a) & np.isnan(b)))
        else:
            neq = a != b
        cnt = int(neq.sum())
        if cnt:
            total += cnt
            fields.append(name)
            f0 = int(np.flatnonzero(neq)[0])
            first = f0 if first == -1 else min(first, f0)
    return total, first, ",".join(fields)


def _perturb_from(mk: Market, j: int, direction: float, seed: int) -> Market:
    """Copy of mk whose bars from index j on are a fresh random walk starting far from the real price."""
    rng = np.random.default_rng(seed)
    n_fut = mk.n - j
    if n_fut <= 0 or j <= 0:
        return mk
    scale = float(np.nanmedian(np.abs(np.diff(mk.bid_c[max(0, j - 5000):j])))) if j > 1 else mk.point
    scale = max(scale if scale == scale else mk.point, mk.point)
    level = mk.bid_c[j - 1] * (1.0 + direction * 0.08)      # 8 percent away: beyond any sane threshold
    steps = rng.normal(0.0, scale, n_fut)
    close = level + np.cumsum(steps)
    open_ = np.concatenate([[level], close[:-1]])
    wick = np.abs(rng.normal(0.0, scale, (2, n_fut)))
    high = np.maximum(open_, close) + wick[0]
    low = np.minimum(open_, close) - wick[1]
    spread = max(float(np.median(mk.ask_c[:j] - mk.bid_c[:j])), 0.0)

    def join(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.concatenate([a[:j], b])

    return Market(mk.sym, mk.tf, mk.ts, join(mk.bid_o, open_), join(mk.bid_h, high), join(mk.bid_l, low), join(mk.bid_c, close),
                  join(mk.ask_o, open_ + spread), join(mk.ask_h, high + spread), join(mk.ask_l, low + spread),
                  join(mk.ask_c, close + spread), join(mk.vol, np.ones(n_fut)), mk.quote_per_usd, mk.pip, mk.point, mk.asset,
                  mk.ask_modelled_share, {})


def _perturbed(m: Market, k: int, direction: float, seed: int = 0) -> Market:
    """Perturb the primary market from bar k on, and every auxiliary market from the first bar not yet
    closed at the primary bar k-1's close."""
    out = _perturb_from(m, k, direction, seed)
    if m.aux or m.ext:
        horizon = m.ts[k - 1] + np.timedelta64(tf_minutes(m.tf), "m")
        for i, (name, a) in enumerate(m.aux.items()):
            j = int(np.searchsorted(a.close_times(), horizon, side="right"))
            out.aux[name] = _perturb_from(a, j, direction, seed + 101 + i)
        for i, (name, e) in enumerate(m.ext.items()):
            j = int(np.searchsorted(e.ts_avail, horizon, side="right"))
            out.ext[name] = e.perturbed_from(j, direction, seed + 301 + i)
    return out


def truncation_test(mod: ModuleType, m: Market, params: dict | None = None,
                    fractions: tuple[float, ...] = (0.5, 0.9), full: Signals | None = None) -> dict:
    full = full or run_signals(mod, m, params)
    probes, ok = [], True
    for f in fractions:
        k = int(m.n * f)
        if k < 10:
            continue
        part = run_signals(mod, m.head(k), params)
        cnt, first, fields = _diff_prefix(full, part, k)
        probes.append({"k": k, "mismatches": cnt, "first_mismatch": first, "fields": fields})
        ok = ok and cnt == 0
    return {"ok": ok, "probes": probes}


def perturbation_test(mod: ModuleType, m: Market, params: dict | None = None,
                      fractions: tuple[float, ...] = (0.5, 0.9), full: Signals | None = None) -> dict:
    full = full or run_signals(mod, m, params)
    probes, ok = [], True
    for f in fractions:
        k = int(m.n * f)
        if k < 10:
            continue
        for direction in (1.0, -1.0):
            part = run_signals(mod, _perturbed(m, k, direction), params)
            cnt, first, fields = _diff_prefix(full, part, k)
            probes.append({"k": k, "direction": direction, "mismatches": cnt, "first_mismatch": first, "fields": fields})
            ok = ok and cnt == 0
    return {"ok": ok, "probes": probes}


def determinism_test(mod: ModuleType, m: Market, params: dict | None = None, full: Signals | None = None) -> dict:
    a = full or run_signals(mod, m, params)
    b = run_signals(mod, m, params)
    cnt, first, fields = _diff_prefix(a, b, m.n)
    return {"ok": cnt == 0, "mismatches": cnt, "first_mismatch": first, "fields": fields}


def ext_release_probes(mod: ModuleType, m: Market, params: dict | None = None, full: Signals | None = None,
                       max_probes: int = 8) -> dict:
    """Cut the sample just before external releases spread over it, then truncate and perturb there. A strategy
    that uses a release before its ts_avail changes its signals on the bars before the cut; the fixed-fraction
    cuts above can miss a leak that only reaches a few minutes ahead of sparse events."""
    if not m.ext:
        return {"ok": True, "probes": []}
    full = full or run_signals(mod, m, params)
    close = m.close_times()
    times = np.unique(np.concatenate([e.ts_avail for e in m.ext.values()]))
    times = times[(times > close[min(10, m.n - 1)]) & (times <= close[-1])]
    if times.size == 0:
        return {"ok": True, "probes": []}
    pick = times[np.unique(np.linspace(0, times.size - 1, max_probes).round().astype(int))]
    probes, ok = [], True
    for t in pick:
        k = int(np.searchsorted(close, t, side="left"))        # bars 0..k-1 close before the release
        if k < 10 or k >= m.n:
            continue
        part = run_signals(mod, m.head(k), params)
        cnt, first, fields = _diff_prefix(full, part, k)
        pert = run_signals(mod, _perturbed(m, k, 1.0, seed=7), params)
        cnt2, first2, fields2 = _diff_prefix(full, pert, k)
        firsts = [x for x in (first, first2) if x >= 0]
        probes.append({"k": k, "release": str(t), "truncation_mismatches": cnt, "perturbation_mismatches": cnt2,
                       "first_mismatch": min(firsts) if firsts else -1,
                       "fields": ",".join(sorted({f for f in (fields + "," + fields2).split(",") if f}))})
        ok = ok and cnt == 0 and cnt2 == 0
    return {"ok": ok, "probes": probes}


def leak_report(mod: ModuleType, m: Market, params: dict | None = None) -> dict:
    full = run_signals(mod, m, params)
    t = truncation_test(mod, m, params, full=full)
    p = perturbation_test(mod, m, params, full=full)
    d = determinism_test(mod, m, params, full=full)
    x = ext_release_probes(mod, m, params, full=full)
    return {"ok": t["ok"] and p["ok"] and d["ok"] and x["ok"], "truncation": t, "perturbation": p, "determinism": d,
            "ext_release": x, "n_entries": full.n_entries, "aux_markets": sorted(m.aux), "ext_series": sorted(m.ext)}
