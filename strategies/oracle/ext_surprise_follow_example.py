"""Example strategy for the external series (a template, not a measured claim): follow the first move after a
large macro surprise.

When a high-impact release for the quote or base currency comes out with |surprise_z| >= z_min (calendar series,
standardised against that event's earlier surprises), wait `delay_min` minutes, then enter in the direction of the
move since the release (bid close now vs the last bar closed before the release), stop = sl_atr x ATR20, time exit
after `hold_min` minutes. Shows every external helper: F.ext_series / F.ext_subset to pick rows, F.ext_recent for
"a release happened in the last N minutes", F.ext_asof for the latest value, and F.ext_minutes_since.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "ext_surprise_follow_example"
PARAMS = {"z_min": 1.0, "delay_min": 15, "hold_min": 120, "sl_atr": 0.25, "currencies": "USD,JPY"}
GRID = {"z_min": [1.0, 2.0], "delay_min": [15, 30]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    cal = F.ext_series(m, "calendar")
    ccy = cal.column("currency")
    want = np.isin(ccy, [c.strip().upper() for c in str(p["currencies"]).split(",")])
    z = cal.column("surprise_z")
    big = want & (cal.column("impact") == "high") & np.isfinite(z) & (np.abs(z) >= p["z_min"])
    rel = F.ext_subset(m, "calendar", big)                 # the releases we react to
    if rel.n == 0:                                         # nothing usable yet (for example a truncated sample)
        return s
    since = F.ext_minutes_since(m, rel)                    # minutes from the last such release to each bar's close
    bar_min = F.minute_of_day_utc(m)
    step = int(np.median(np.diff(bar_min[:1000])[np.diff(bar_min[:1000]) > 0])) if m.n > 1000 else 1
    # the first bar that closes at least delay_min after the release
    trigger = (since >= p["delay_min"]) & (since < p["delay_min"] + step)
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))
    close = m.bid_c
    idx_rel = np.searchsorted(rel.ts_avail, m.close_times(), side="right") - 1   # index of the last release per bar
    # reference price: last bar closed before that release (its close is public information at the release time)
    ref_bar = np.searchsorted(m.close_times(), rel.ts_avail[np.clip(idx_rel, 0, max(rel.n - 1, 0))], side="left") - 1
    valid = trigger & (idx_rel >= 0) & (ref_bar >= 0) & np.isfinite(atr) & (atr > 0)
    move = np.zeros(m.n)
    move[valid] = close[valid] - close[ref_bar[valid]]
    hold_bars = max(int(round(p["hold_min"] / max(step, 1))), 1)
    long = valid & (move > 0)
    short = valid & (move < 0)
    s.entry_long[long] = True
    s.entry_short[short] = True
    s.sl_dist[valid] = p["sl_atr"] * atr[valid]
    s.max_bars[valid] = hold_bars
    return s
