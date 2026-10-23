"""Retail dip-buying fragility on the yen crosses: short a cross at the Tokyo open after a five-day decline of at
least k x ATR20 during which the TFX Click 365 retail open interest grew heavily, hold 2 or 4 weekdays.

Mechanism: Japanese retail margin traders (Click 365 is the exchange-traded slice) are structurally long the yen
crosses and contrarian: they add longs as the cross falls. The positions are 10 to 25 times levered with broker
losscuts, so a book that grew heavily into a decline is latent forced supply; if the decline extends, losscuts fire
in a cascade. Hypothesis (one-sided, fixed before any run): after heavy accumulation into weakness a short has a
positive expectation over the next days; the "light" band (the same decline without accumulation) is the control.

Rules (all times UTC; H1 bars are stamped at the bar open and are sparse, so every time is located by timestamp:
m.ts for opens, m.close_times() for closes):

  ROWS     tfx_daily rows with symbol == m.sym, in ts_avail order (ts_avail = Click 365 date + 1 day at 00:00 UTC).
           oi_g[r] = oi[r] / oi[r - L] - 1 over the previous L = oi_lookback rows (rows, not calendar days);
           undefined when r < L or when any of the L + 1 values oi[r-L..r] is not > 0. No whole-sample statistic.
           ValueError if the symbol has no rows.
  PRICE    daily = F.daily_bars(m) (trading days closing 17:00 New York); ATR20 = F.atr_prev(daily, atr_n), known
           at the day start. At the signal bar sig, D = the trading day before the one containing sig. Require
           daily.date[D] == the date of the row (otherwise skip: a holiday that one venue observes),
           D - ret_lookback >= 0 and ATR20[sig] finite and > 0.
           drop_atr = (daily.c[D] - daily.c[D - ret_lookback]) / ATR20[sig]; condition drop_atr <= -k
           (k 1.0 or 1.5).
  BAND     heavy10: oi_g >= 0.10; heavy15: oi_g >= 0.15; light: oi_g <= 0.02 (control: the same decline without
           accumulation, including days the book shrank). Any other value raises ValueError. A row qualifies only
           if its band condition and the price condition both hold.
  SIGNAL   T* = the first 00:00 UTC at or after ts_avail that falls on Monday to Friday (ts_avail itself for
           Monday-Thursday rows, the following Monday 00:00 UTC for Friday rows). sig = the bar whose close time
           equals T* (the 23:00-00:00 UTC bar; on Sunday night it belongs to the Monday trading day); if no bar
           closes exactly at T*, the first bar with close time >= T*, provided close - T* <= max_delay_min (120)
           minutes and the close is on the UTC date of T*; otherwise the row is skipped.
  ENTRY    short only: entry_short[sig], market order (entry_type 0, valid_bars 1), filled at the open of bar
           sig + 1 (normally 00:00 UTC = 09:00 Tokyo) on the bid minus slippage.
  STOP     sl_dist[sig] = sl_atr x ATR20[sig] (price units, sl_atr 1.0). No target (tp_dist NaN), max_bars 0.
  EXIT     E = the hold_days-th Monday-to-Friday date after the UTC date of bar sig + 1 (hold_days 2 or 4; holidays
           are not skipped); target = E at exit_utc (20:00); xi = the first bar with open >= target. Primary
           marker: exit_short[xi - 1] (close at the open of the first bar at or after the target), set only when
           xi < m.n and xi > sig + 1. Causal fallback: exit_short is also True on every bar j with
           m.ts[j] >= target and j <= the signal bar of the next KEPT row (m.n - 1 for the last kept row), so a
           missing target bar closes the position at the first bar after the gap and never carries it into the
           next trade. The bar whose close is the first at or after the target (xi - 1 whenever that bar
           straddles the target) is marked as well: the same bar as the primary marker, but decided from its own
           close time, so it does not need bar xi to exist. No other exits, no other filters.
  DE-OVERLAP (planned hold, replaces any leftover guard): the qualifying rows of the active band are walked in
           time order; a row is kept only if m.ts[sig] >= the target of the last KEPT row (the first kept row has
           no condition). A dropped row sets no entry and no markers; a trade stopped early does not reopen the
           window, because the window is the planned one.

Parameters (every one read from p): band, k, hold_days (the grid), and the fixed sl_atr 1.0, oi_lookback 5,
ret_lookback 5, exit_utc "20:00", max_delay_min 120, atr_n 20. GRID is the full 12 cells; the pipeline spec runs
all 12 on AUDJPY in stage A (the "light" cells are the control) and band in (heavy10, heavy15) elsewhere.

Closed-bar information only: a row is used from sig, whose close time is >= T* >= ts_avail; the price condition
uses completed trading days and the ATR known at the day start. Whether a later bar exists never decides whether a
row trades (so a truncated sample gives the same signals on its prefix); a row whose exit target lies beyond the
last bar simply has no primary exit marker and runs to the end of the data.

Note on the time exit: exit_utc 20:00 is the open of the 20:00 UTC bar. In the months with New York on daylight time
that is the last Friday H1 bar (the 17:00 New York close is 21:00 UTC), so a target on a Friday exits on the Friday and
no position is carried over the weekend; on every other day it is before the 21:00 UTC rollover hour. (The earlier
20:30 default fell through to the Sunday evening open for Friday targets in those months.)
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "jpy_retail_dipbuy_fragility"
PARAMS = {"band": "heavy10", "k": 1.0, "hold_days": 2, "sl_atr": 1.0, "oi_lookback": 5, "ret_lookback": 5,
          "exit_utc": "20:00", "max_delay_min": 120, "atr_n": 20}
GRID = {"band": ["heavy10", "heavy15", "light"], "k": [1.0, 1.5], "hold_days": [2, 4]}

# The band definitions are part of the pre-registration (the band name is the parameter): thresholds on the
# five-row open-interest growth, as (direction, threshold).
BANDS = {"heavy10": (">=", 0.10), "heavy15": (">=", 0.15), "light": ("<=", 0.02)}
_EPS = 1e-9   # float guard so a ratio of exactly 1.15 (integer contracts) counts as >= 0.15


def _symbol_rows(m: Market):
    """The tfx_daily rows of the symbol of this market, in ts_avail order (the symbol column holds None for pairs
    that are not in the price store, so the comparison is done value by value)."""
    sym_col = F.ext_series(m, "tfx_daily").column("symbol")
    mask = np.fromiter((v == m.sym for v in sym_col), dtype=bool, count=len(sym_col))
    if not mask.any():
        raise ValueError(f"tfx_daily has no rows for symbol {m.sym!r}")
    return F.ext_subset(m, "tfx_daily", mask)


def _oi_growth(oi: np.ndarray, lag: int) -> np.ndarray:
    """oi[r] / oi[r - lag] - 1 over rows; NaN when r < lag or any of oi[r-lag..r] is not finite and > 0."""
    n = len(oi)
    out = np.full(n, np.nan)
    if lag < 1 or n <= lag:
        return out
    bad = ~(np.isfinite(oi) & (oi > 0))
    bad_cum = np.concatenate([[0], np.cumsum(bad)])            # bad_cum[i] = number of bad values in oi[:i]
    r = np.arange(lag, n)
    clean = (bad_cum[r + 1] - bad_cum[r - lag]) == 0           # window oi[r-lag .. r] has no bad value
    r = r[clean]
    out[r] = oi[r] / oi[r - lag] - 1.0
    return out


def _band_mask(oi_g: np.ndarray, band: str) -> np.ndarray:
    direction, thr = BANDS[band]
    with np.errstate(invalid="ignore"):
        hit = (oi_g >= thr - _EPS) if direction == ">=" else (oi_g <= thr + _EPS)
    return np.isfinite(oi_g) & hit


def _next_weekday_midnight(ts_avail: np.ndarray) -> np.ndarray:
    """First 00:00 UTC at or after ts_avail that falls on Monday to Friday (datetime64[us])."""
    day = ts_avail.astype("datetime64[D]")
    day = day + (ts_avail > day.astype("datetime64[us]")).astype("timedelta64[D]")   # ceil to midnight (no-op here)
    wd = F.weekday(day)                                                              # Monday = 0 ... Sunday = 6
    day = day + np.where(wd == 5, 2, np.where(wd == 6, 1, 0)).astype("timedelta64[D]")
    return day.astype("datetime64[us]")


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    band = str(p["band"])
    if band not in BANDS:
        raise ValueError(f"unknown band {band!r}; expected one of {sorted(BANDS)}")
    rows = _symbol_rows(m)
    if m.n < 2:
        return s

    k = float(p["k"])
    hold = int(p["hold_days"])
    back = int(p["ret_lookback"])
    xh, xm = F.parse_hhmm(p["exit_utc"])

    # ---- per-row quantities (rows are in ts_avail order); nothing here looks past the signal bar
    r_date = rows.column("date").astype("datetime64[D]")                 # Click 365 trading date
    oi_g = _oi_growth(rows.column("oi"), int(p["oi_lookback"]))
    t_star = _next_weekday_midnight(rows.ts_avail)                       # T*: Friday rows move to Monday 00:00 UTC
    close = m.close_times()
    sig = np.searchsorted(close, t_star, side="left")                    # first bar closing at or after T*
    sc = np.minimum(sig, m.n - 1)
    ok = sig < m.n
    ok = ok & ((close[sc] - t_star) <= np.timedelta64(int(p["max_delay_min"]), "m"))
    ok = ok & (close[sc].astype("datetime64[D]") == t_star.astype("datetime64[D]"))

    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, int(p["atr_n"])))             # ATR of the previous days, known at day start
    d_prev = daily.day_idx[sc] - 1                                       # D: last completed trading day at the signal
    d_back = d_prev - back
    ok = ok & (d_back >= 0)
    dp = np.clip(d_prev, 0, daily.n - 1)
    db = np.clip(d_back, 0, daily.n - 1)
    ok = ok & (daily.date[dp] == r_date)                                 # both venues describe the same day
    a = atr[sc]
    ok = ok & np.isfinite(a) & (a > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        drop_atr = (daily.c[dp] - daily.c[db]) / a
    ok = ok & np.isfinite(drop_atr) & (drop_atr <= -k)
    ok = ok & _band_mask(oi_g, band)

    q = np.flatnonzero(ok)
    if q.size == 0:
        return s
    sig_q = sig[q]

    # ---- planned exit per qualifying row: the hold_days-th weekday after the date of the fill bar, at exit_utc
    fill_i = np.minimum(sig_q + 1, m.n - 1)
    # the fill bar opens at T* (00:00 UTC) in practice; when it does not exist yet (end of data) the date of T* is used
    base = np.where(sig_q + 1 < m.n, m.ts[fill_i].astype("datetime64[D]"), t_star[q].astype("datetime64[D]"))
    exit_day = np.busday_offset(base, hold, roll="backward")             # hold-th Monday-Friday date after base
    target = exit_day.astype("datetime64[us]") + np.timedelta64(xh * 60 + xm, "m")
    xi_q = np.searchsorted(m.ts, target, side="left")                    # first bar with open >= target
    j0_q = np.searchsorted(close, target, side="left")                   # first bar with close >= target (xi - 1 or xi)

    # ---- planned-hold de-overlap: keep a row only if its signal bar is at or after the target of the last kept row
    ts_sig = m.ts[sig_q]
    kept = []
    target_prev = None
    for j in range(q.size):
        if target_prev is not None and ts_sig[j] < target_prev:
            continue                                                     # dropped: no entry, no markers
        kept.append(j)
        target_prev = target[j]
    kept_a = np.asarray(kept, dtype=np.int64)
    k_sig = sig_q[kept_a]
    k_xi = xi_q[kept_a]
    k_j0 = j0_q[kept_a]

    # ---- entries
    s.entry_short[k_sig] = True
    s.entry_type[k_sig] = 0
    s.valid_bars[k_sig] = 1
    s.sl_dist[k_sig] = float(p["sl_atr"]) * atr[k_sig]

    # ---- exits: primary marker at xi - 1, plus the causal fallback up to the signal bar of the next kept row
    fallback_end = np.append(k_sig[1:], m.n - 1)
    for sg, xi, j0, hi in zip(k_sig.tolist(), k_xi.tolist(), k_j0.tolist(), fallback_end.tolist()):
        if xi < m.n and xi > sg + 1:
            s.exit_short[xi - 1] = True
        if xi <= hi:
            s.exit_short[xi:hi + 1] = True
        # causal form of the primary marker: the bar whose close is the first at or after the target is xi - 1 when
        # that bar straddles the target (always, except around holiday gaps), and its close time alone shows that the
        # target has passed, so this marker does not need the next bar to exist (same bar as the primary marker)
        if sg < j0 <= hi:
            s.exit_short[j0] = True
    return s
