"""VIX state for the gotobi Tokyo-fix short on USDJPY (pre-registered measurement, cycle 10).

Base trade, copied from strategies/oracle/gotobi_short.py: on a gotobi weekday (5th, 10th, 15th, 20th, 25th and
month-end; a weekend date moves back to Friday) from p['start'], SELL USDJPY at market at the first bar at or after
p['entry_utc'] (00:55 UTC, the 09:55 Tokyo fix), provided that bar opens within p['max_delay_min'] minutes of it; exit
at the open of the first bar at or after p['exit_utc'] (06:00 UTC) the same day; stop = p['sl_atr'] x ATR20
(F.atr_prev(daily, p['atr_n'])), no target; one position at a time. The oracle's guards are kept (a bar before the
entry bar exists, an exit bar exists and comes after the entry bar, ATR finite and positive).

What is added is a day filter built from two states that are known before the trade:
  ATR state, as the oracle's vol filter: med[i] = nanmedian(atr_d[i - w + 1 : i + 1]) over the previous w = p['atr_window']
    (250) daily ATR20 values including the current day's; ATR-high = ATR20 >= med, ATR-low otherwise.
  VIX state: the CBOE VIX closes of data/external/vol.parquet (usable from ts_avail = 21:30 UTC on the observation
    date, so the 00:55 UTC entry sees the previous US session's close). Rows with a null vix (US holidays) are
    dropped before the as-of mapping. pct[j] = 100 x mean(x[lo : j + 1] <= x[j]) with lo = max(0, j - p['vix_window'] + 1),
    NaN if fewer than p['vix_min_obs'] closes; the value used on a day is the last row usable at the close of the
    signal bar (the F.ext_asof rule). V+ = pct >= p['vix_pct'] - 1e-9 (VIX at or above its trailing 250-close median),
    V- = pct < p['vix_pct'] - 1e-9, a strict complement.
  Common sample: in every arm, 'all' included, a day is traded only if both states are defined, so the four ATR x VIX
    strata partition 'all' exactly.

Arms, p['state'] (an unknown value raises ValueError). Design trades 2011-2017, pre-registered -> as built:
  gotobi days: 'all' about 504 -> 504; 'atr' (ATR-high) 219 -> 219; 'atr_vix' (ATR-high and V+) 83 -> 83;
    'atr_vixlo' (ATR-high and V-) 136 -> 136; 'natr_vix' (ATR-low and V+) 101 -> 101; 'natr_vixlo' (ATR-low and V-)
    182 -> 184; 'atr_or_vix' (ATR-high or V+, the hypothesis cell, about 3.8 trades a month) 320 -> 320
  placebo, the identical short, stop and exit on non-gotobi weekdays: 'ng_vix' (V+) about 495 -> 495;
    'ng_vixlo' (V-) about 817 -> 822
  The surplus of 2 and 5 days is 2011-01-03 to 2011-01-11 (all ATR-low and V-): the oracle's median is defined from
  2010-12-15 on 230 finite ATR20 values, so the oracle's own rule already counts those days.
The reference and placebo arms are never promoted. The spec grid (stages B and C, walk-forward, any holdout) is
{state: ['atr_or_vix'], vix_pct: [50]}; stage A records all nine arms at vix_pct 50 as trials, and the module GRID lists
the nine arms so that the checker exercises every value.

Warm-up convention (assumption, p['atr_min_obs']): the oracle leaves the ATR state undefined until a full
p['atr_window'] days of history exist. Here the median is also taken over the shorter trailing window once at least
p['atr_min_obs'] finite ATR20 values exist, clamped to atr_window - atr_n so that every day on which the oracle's state is
defined has exactly the oracle's value. The pipeline always loads USDJPY from 2009-12-31, where the oracle's state is
defined from 2010-12-15, before p['start'], so no registered trade changes; the convention only lets the checker's
106-trading-day sample produce entries. Setting atr_min_obs to 230 or more restores the oracle's rule everywhere.

Known property of the copied base trade: the oracle's guard `xi >= m.n` makes an entry depend on the exit bar existing,
so a truncation cut placed between 00:55 and 06:00 UTC on a traded day shows a spurious one-day mismatch (the oracle
itself does the same). The checker's cuts (default arm) and the pipeline's Stage 0 cuts (50% and 90% of the pre-holdout
sample, every arm, plus the 21:30 UTC release probes) do not fall in such a window.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "vix_state_gotobi_fix_reversal"
PARAMS = {"state": "atr_or_vix", "vix_pct": 50, "entry_utc": "00:55", "exit_utc": "06:00", "sl_atr": 0.25,
          "max_delay_min": 5, "vix_window": 250, "vix_min_obs": 120, "atr_n": 20, "atr_window": 250,
          "start": "2011-01-01", "atr_min_obs": 30}
GRID = {"state": ["all", "atr", "atr_vix", "atr_vixlo", "natr_vix", "natr_vixlo", "atr_or_vix", "ng_vix", "ng_vixlo"],
        "vix_pct": [50]}

# arm -> (placebo day set (non-gotobi weekdays)?, rule(atr_high, vix_high) -> trade the day?)
_ARMS = {
    "all": (False, lambda a, v: True),
    "atr": (False, lambda a, v: a),
    "atr_vix": (False, lambda a, v: a and v),
    "atr_vixlo": (False, lambda a, v: a and not v),
    "natr_vix": (False, lambda a, v: (not a) and v),
    "natr_vixlo": (False, lambda a, v: (not a) and (not v)),
    "atr_or_vix": (False, lambda a, v: a or v),
    "ng_vix": (True, lambda a, v: v),
    "ng_vixlo": (True, lambda a, v: not v),
}


def _causal_percentile(x: np.ndarray, window: int, min_obs: int) -> np.ndarray:
    """pct[j] = 100 x mean(x[lo : j + 1] <= x[j]), lo = max(0, j - window + 1); NaN with fewer than min_obs closes."""
    out = np.full(len(x), np.nan)
    for j in range(len(x)):
        lo = max(0, j - window + 1)
        if j + 1 - lo < min_obs:
            continue
        out[j] = 100.0 * np.mean(x[lo:j + 1] <= x[j])
    return out


def signals(m: Market, p: dict) -> Signals:
    state = p["state"]
    if state not in _ARMS:
        raise ValueError(f"unknown state {state!r}; expected one of {sorted(_ARMS)}")
    placebo, rule = _ARMS[state]
    s = Signals(m.n)

    # VIX state: only closes that have a value (US-holiday rows carry a ts_avail but a null vix), usable from ts_avail.
    e = F.ext_series(m, "vol")
    sub = F.ext_subset(m, "vol", np.isfinite(e.column("vix")))
    if sub.n == 0:                      # nothing usable yet (for example a truncated sample)
        return s
    pct = _causal_percentile(sub.column("vix"), int(p["vix_window"]), int(p["vix_min_obs"]))
    k = np.searchsorted(sub.ts_avail, m.close_times(), side="right") - 1        # the F.ext_asof rule
    vix_pct = np.full(m.n, np.nan)
    ok = k >= 0
    vix_pct[ok] = pct[k[ok]]

    # ATR state: ATR20 known at the day's start against the median of its trailing window (current day included).
    daily = F.daily_bars(m)
    atr_d = F.atr_prev(daily, int(p["atr_n"]))
    atr = daily.to_bars(atr_d)
    w = int(p["atr_window"])
    need = max(1, min(int(p["atr_min_obs"]), w - int(p["atr_n"])))
    med = np.full(daily.n, np.nan)
    for i in range(daily.n):
        win = atr_d[max(0, i - w + 1):i + 1]
        if np.count_nonzero(np.isfinite(win)) >= need:
            med[i] = np.nanmedian(win)
    with np.errstate(invalid="ignore"):
        high_d = np.isfinite(med) & (atr_d >= med)
    atr_def = daily.to_bars(np.isfinite(med) & np.isfinite(atr_d))
    hot = daily.to_bars(high_d)

    dates = np.unique(F.utc_dates(m))
    pool = ~F.is_gotobi(dates) if placebo else F.is_gotobi(dates)
    dates = dates[pool & (F.weekday(dates) < 5) & (dates >= np.datetime64(p["start"]))]
    eh, em = F.parse_hhmm(p["entry_utc"])
    xh, xm = F.parse_hhmm(p["exit_utc"])
    entry_idx = F.first_bar_at_or_after(m, dates, eh, em)
    exit_idx = F.first_bar_at_or_after(m, dates, xh, xm)
    max_delay = np.timedelta64(p["max_delay_min"], "m")
    cut = float(p["vix_pct"]) - 1e-9
    for d, ei, xi in zip(dates, entry_idx, exit_idx):
        if ei < 1 or xi >= m.n or xi <= ei:
            continue
        target = d.astype("datetime64[us]") + np.timedelta64(eh * 60 + em, "m")
        if m.ts[ei] - target > max_delay:
            continue
        if not np.isfinite(atr[ei]) or atr[ei] <= 0:
            continue
        sig = ei - 1
        v = vix_pct[sig]
        if not atr_def[ei] or not np.isfinite(v):       # common sample: both states must be defined
            continue
        if not rule(bool(hot[ei]), bool(v >= cut)):
            continue
        s.entry_short[sig] = True
        s.exit_short[xi - 1] = True
        s.sl_dist[sig] = p["sl_atr"] * atr[ei]
    return s
