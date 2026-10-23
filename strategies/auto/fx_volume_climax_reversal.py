"""Volume-climax capitulation reversal (fx_volume_climax_reversal), H1, long/short fade.

Mechanism: a one-day shock move that carries a tick-volume climax is forced liquidation (stop cascades,
margin calls); liquidity providers are paid by a reversal over the next 1-3 days. The same shock day
without a volume climax is informed repricing and is not faded. v = 0.0 is the true control arm: the only
volume test is V >= v * Vbar, so at v = 0 every shock day with a valid Vbar qualifies.

Rules (all times UTC, bars located by timestamp, H1 bars are labelled by open time so close = ts + 1h):
* Daily reference bar E(D): for each UTC date D, the last H1 bar whose close time is <= 20:00 on D and
  > 16:00 on D. No such bar -> D is not a signal day. Only Monday-Friday dates are used.
  C(D) = bid_c[E(D)].
* D_prev = most recent earlier signal-eligible date with D - D_prev <= 4 calendar days (else the day has
  no valid move/volume window). ret(D) = C(D) - C(D_prev).
* ATR20_prev = F.atr_prev(F.daily_bars(m), 20) mapped to bar E(D) (known at the start of its trading day).
* Shock day: |ret(D)| >= k * ATR20_prev.
* Volume: V(D) = sum of m.vol over H1 bars with close time in (20:00 on D_prev, 20:00 on D].
  Vbar(D) = mean of V over the 20 most recent earlier dates with a valid V (strictly before D).
  Require Vbar > 0, V finite and V(D) >= v * Vbar (the only volume test; v = 0.0 is the no-volume control).
* Entry: on bar E(D), if shock and volume condition hold: ret < 0 -> entry_long, ret > 0 -> entry_short
  (fade the move). Market entry at the next open (entry_type 0, valid_bars 1).
* Stop: sl_dist = sl_atr * ATR20_prev (no trade if NaN or <= 0). No target.
* Exit: X = E(D + hold_days) where D + hold_days is the hold_days-th later eligible date. The exit flag is
  placed on bar X - 1 (only if X - 1 > E(D)), so the position closes at the open of bar X, flat before a new
  shock signal at X registers. Safety net max_bars = 24 * (hold_days + 3).
* One position at a time, causally: signals are taken in date order. For each accepted signal the module
  tracks when the trade goes flat (first stop touch on bid_l / ask_h after the fill at the next open, its own
  exit bar X, or the max_bars cap, whichever is first = flat_at). A later signal on a bar before flat_at is
  skipped and nothing is written for it (not even an exit flag), so a leftover exit flag can never close a
  different trade. A signal on the bar where the previous trade closes (ei >= flat_at) is accepted.
* No other filters, no pyramiding. XAUUSD artefact minutes are not filtered.
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "fx_volume_climax_reversal"
PARAMS = {"k": 1.0, "v": 1.3, "sl_atr": 1.0, "hold_days": 1,
          "ref_start_utc": "16:00", "ref_end_utc": "20:00", "max_gap_days": 4, "vol_window": 20}
GRID = {"k": [1.0, 1.25], "v": [0.0, 1.3, 1.5], "hold_days": [1, 3]}


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    if m.n < 2:
        return s
    sh, sm = F.parse_hhmm(p["ref_start_utc"])
    eh, em = F.parse_hhmm(p["ref_end_utc"])
    hour = np.timedelta64(1, "h")
    close_t = m.ts + hour                       # close time of each H1 bar
    cum_vol = np.concatenate([[0.0], np.cumsum(np.nan_to_num(m.vol.astype(np.float64)))])

    dates = np.unique(F.utc_dates(m))
    dates = dates[F.weekday(dates) < 5]
    d_us = dates.astype("datetime64[D]").astype("datetime64[us]")
    t_end = d_us + np.timedelta64(eh * 60 + em, "m")
    t_start = d_us + np.timedelta64(sh * 60 + sm, "m")
    hi = np.searchsorted(close_t, t_end, side="right")      # bars with close <= 20:00 on D: [0, hi)
    e_idx = hi - 1
    ok = e_idx >= 0
    ok[ok] = close_t[e_idx[ok]] > t_start[ok]
    dates, t_end, e_idx, hi = dates[ok], t_end[ok], e_idx[ok], hi[ok]
    nd = len(dates)
    if nd < 3:
        return s

    # previous-eligible-date move and volume window
    gap_ok = np.zeros(nd, dtype=bool)
    gap_ok[1:] = (dates[1:] - dates[:-1]) <= np.timedelta64(int(p["max_gap_days"]), "D")
    close_e = m.bid_c[e_idx]
    ret = np.full(nd, np.nan)
    ret[1:] = np.where(gap_ok[1:], close_e[1:] - close_e[:-1], np.nan)
    vol = np.full(nd, np.nan)
    vol[1:] = np.where(gap_ok[1:], cum_vol[hi[1:]] - cum_vol[hi[:-1]], np.nan)

    # Vbar: mean of the previous vol_window valid V values, strictly before each date
    w = int(p["vol_window"])
    valid_pos = np.flatnonzero(np.isfinite(vol))
    vbar = np.full(nd, np.nan)
    if len(valid_pos) >= w:
        cs = np.concatenate([[0.0], np.cumsum(vol[valid_pos])])
        cnt = np.searchsorted(valid_pos, np.arange(nd), side="left")   # valid values strictly before i
        good = cnt >= w
        c = cnt[good]
        vbar[good] = (cs[c] - cs[c - w]) / w

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, 20))[e_idx]

    hold = int(p["hold_days"])
    with np.errstate(invalid="ignore"):
        shock = np.isfinite(ret) & np.isfinite(atr) & (atr > 0) & (np.abs(ret) >= p["k"] * atr)
        climax = np.isfinite(vol) & np.isfinite(vbar) & (vbar > 0) & (vol >= p["v"] * vbar)
    sel = np.flatnonzero(shock & climax & (ret != 0))
    max_bars = 24 * (hold + 3)

    flat_at = -1
    for j in sel:
        ei = int(e_idx[j])
        if ei < flat_at:          # executor would ignore this signal: write nothing
            continue
        is_long = ret[j] < 0
        dist = p["sl_atr"] * atr[j]
        if is_long:
            s.entry_long[ei] = True
        else:
            s.entry_short[ei] = True
        s.sl_dist[ei] = dist
        s.max_bars[ei] = max_bars
        end = m.n
        xi = -1
        if j + hold < nd:
            xi = int(e_idx[j + hold])
            if xi - 1 > ei:
                end = xi
        end = min(end, ei + 1 + max_bars, m.n)
        # when does this trade go flat? first stop touch after the next-open fill, else its exit/cap bar
        flat_at = end
        if ei + 1 < m.n and end > ei + 1:
            if is_long:
                stop = m.ask_o[ei + 1] - dist
                hit = np.flatnonzero(m.bid_l[ei + 1:end] <= stop)
            else:
                stop = m.bid_o[ei + 1] + dist
                hit = np.flatnonzero(m.ask_h[ei + 1:end] >= stop)
            if len(hit):
                flat_at = ei + 1 + int(hit[0])
        # exit flag only if the trade is still open at X - 1 (a stopped-out trade leaves no flag behind)
        if xi > 0 and end == xi and flat_at == xi:
            if is_long:
                s.exit_long[xi - 1] = True
            else:
                s.exit_short[xi - 1] = True
    return s
