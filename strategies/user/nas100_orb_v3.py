"""User strategy: NAS100 5-minute range breakout with a one-candle confirmation, v3 rules (given 2026-10-23).

All times are New York, so the IST times in the user's rules (4:30-7:30 PM in US summer, one hour later in
US winter) follow automatically.

  1. Range = highest high / lowest low of the 5-minute candles opening 07:00-09:55 (07:00-10:00 New York).
  2. From 10:00 a candle must CLOSE above the high (break up) or below the low (break down).
  3. The next candle must also close outside on the same side. If it closes back inside, that break is dropped
     and the scan goes on. If it closes outside on the other side, it counts as a new break on that side.
  4. Enter at the close of the confirming candle (the engine fills at the next candle's open, the same moment):
     buy after an upside break, sell after a downside break.
     Skip filter (the whole day is skipped), `skip_mode`:
       "as_written": buy skipped if the confirming close < break-candle low - 2; sell if > break-candle high + 2
       "chase":      buy skipped if the confirming close > break-candle high + 2; sell if < break-candle low - 2
       "off":        no filter
  5. Stop = 2 x ATR(14), simple-average true range on 5-minute bars, read at the confirming candle's close,
     measured from the fill.
  6. Target = 4 x the stop distance.
  7. No management, no time exit: held through nights and weekends until the stop or target.
  8. First confirmed break of the day only; the executor ignores it while an earlier trade is still open;
     the confirming candle must close by 16:55 New York (2:25 AM IST summer / 3:25 AM winter).

Prices are bid (the MT5 / TradingView chart). DIAG holds day counts from the last signals() call.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "nas100_orb_v3"
PARAMS = {"range_start": "07:00", "range_end": "10:00", "last_entry": "16:55", "atr_n": 14, "sl_atr": 2.0,
          "tp_r": 4.0, "skip_pts": 2.0, "skip_mode": "as_written", "min_range_bars": 36}

DIAG: dict = {}


def atr_sma(m: Market, n: int) -> np.ndarray:
    prev_c = np.concatenate([[np.nan], m.bid_c[:-1]])
    tr = np.fmax(m.bid_h - m.bid_l, np.fmax(np.abs(m.bid_h - prev_c), np.abs(m.bid_l - prev_c)))
    tr[0] = m.bid_h[0] - m.bid_l[0]
    return F.rolling_mean(tr, n)


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    ny = pl.Series("ts", m.ts).dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    day = ny.dt.date().to_numpy().astype("datetime64[D]")
    mod = (ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32)).to_numpy()
    atr = atr_sma(m, p["atr_n"])
    rh, rm = F.parse_hhmm(p["range_start"])
    eh, em = F.parse_hhmm(p["range_end"])
    lh, lm = F.parse_hhmm(p["last_entry"])
    r0, r1 = rh * 60 + rm, eh * 60 + em
    last_open = lh * 60 + lm - 5          # the confirming candle must close by last_entry
    skip_pts, mode = p["skip_pts"], p["skip_mode"]
    c, h, lo = m.bid_c, m.bid_h, m.bid_l

    diag = {"weekdays": 0, "range_incomplete": 0, "no_break": 0, "skipped": 0, "signals": 0, "failed_confirms": 0,
            "flipped_breaks": 0}
    starts = np.flatnonzero(np.concatenate([[True], day[1:] != day[:-1]]))
    ends = np.concatenate([starts[1:], [m.n]])
    for a, b in zip(starts, ends):
        if F.weekday(day[a:a + 1])[0] >= 5:
            continue
        diag["weekdays"] += 1
        md = mod[a:b]
        rng = np.flatnonzero((md >= r0) & (md < r1)) + a
        if len(rng) < p["min_range_bars"]:
            diag["range_incomplete"] += 1
            continue
        hi, low = h[rng].max(), lo[rng].min()
        scan = np.flatnonzero((md >= r1) & (md <= last_open)) + a
        pend_side, pend_i, done = 0, -1, False
        for j in scan:
            out = 1 if c[j] > hi else (-1 if c[j] < low else 0)
            if pend_side != 0 and out == pend_side:
                side, bi = pend_side, pend_i
                skip = False
                if mode == "as_written":
                    skip = c[j] < lo[bi] - skip_pts if side > 0 else c[j] > h[bi] + skip_pts
                elif mode == "chase":
                    skip = c[j] > h[bi] + skip_pts if side > 0 else c[j] < lo[bi] - skip_pts
                if skip:
                    diag["skipped"] += 1
                elif np.isfinite(atr[j]) and atr[j] > 0 and j + 1 < m.n:
                    if side > 0:
                        s.entry_long[j] = True
                    else:
                        s.entry_short[j] = True
                    s.sl_dist[j] = p["sl_atr"] * atr[j]
                    s.tp_dist[j] = p["tp_r"] * p["sl_atr"] * atr[j]
                    diag["signals"] += 1
                done = True
                break
            if pend_side != 0:
                if out == 0:
                    diag["failed_confirms"] += 1
                else:
                    diag["flipped_breaks"] += 1
            pend_side, pend_i = (out, j) if out != 0 else (0, -1)
        if not done:
            diag["no_break"] += 1
    DIAG.clear()
    DIAG.update(diag)
    return s
