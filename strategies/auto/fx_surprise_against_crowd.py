"""Positioning-amplified surprise continuation: trade a high-impact data surprise 15 minutes after the release,
by arm of the CFTC leveraged-fund crowd state ("against" the crowd = the hypothesis, "with" and "neutral" = controls).

Mechanism: a scheduled release that surprises against a crowded leveraged-fund book forces risk-limit and
end-of-day position cuts that are executed over hours, so the move after the first 15 minutes should continue
only in the 'against' state. 'with' and 'neutral' trade the same surprises, with the same first reaction, costs
and event set, and differ only in the positioning state. The hypothesis is the asymmetry between the arms.

Markets: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCAD on M15 bars (bars are stamped at the open and sparse:
every time is located by timestamp, m.ts for opens and m.close_times() for closes). External series: calendar, cot.
All times UTC. Loops run over releases (a few hundred per market), everything else is vectorised.

SYMBOL CONSTANTS
  base = sym[:3], quote = sym[3:]. The COT currency is the non-USD one (EUR, GBP, AUD, NZD, JPY, CAD);
  cot_sign = +1 when it is the base (EURUSD, GBPUSD, AUDUSD, NZDUSD) and -1 when it is the quote (USDJPY, USDCAD).
  Any other symbol raises ValueError.

CALENDAR EVENT SET
  Rows with impact == 'high', time_source == 'scraped', finite surprise_z, currency in (base, quote), and an event
  name that does not contain (case-insensitive) 'Crude Oil', 'Natural Gas', 'Inventories', 'Unemployment Claims',
  'TIC Long', 'Votes' or 'Asset Purchase Facility'. Row contribution for the pair:
  surprise_z x inv x side, with inv = -1 when the name contains 'Unemployment Rate', 'Unemployment Change',
  'Claimant Count', 'Net Borrowing' or 'Jobless' (a higher number is bad for that currency) and +1 otherwise,
  and side = +1 when the currency is the base, -1 when it is the quote. (surprise_z x inv x side equals
  sign x |surprise_z| of the brief.) Rows with the same ts_avail are one release: dz = sum of their contributions.
  A release qualifies when |dz| >= z_min; dir = sign(dz) (+1 long the pair, -1 short). dz is never rescaled and no
  rank, quantile or z-score is taken over the sample. Releases are processed in ts_avail order, T = ts_avail.

POSITIONING STATE
  c = the COT rows of the COT currency in ts_avail order. For row r with at least rank_weeks rows up to and
  including r: rank_r = (number of the last rank_weeks rows of spec_net_oi that are <= spec_net_oi_r) / rank_weeks,
  in (0, 1]; earlier rows have no rank. For a release at T the row is the last one with ts_avail <= T; a release
  with no such row or no rank is skipped in every arm. state = +1 if rank >= crowd_q, -1 if rank <= 1 - crowd_q,
  else 0; crowd_pair_dir = cot_sign x state (+1 crowded long the pair, -1 crowded short, 0 not crowded).

ARMS (p['arm'], anything else raises ValueError); every arm trades in the surprise direction dir
  against: crowd_pair_dir != 0 and dir == -crowd_pair_dir   (the surprise hits the crowded book)
  with:    crowd_pair_dir != 0 and dir ==  crowd_pair_dir   (the surprise agrees with the book)
  neutral: crowd_pair_dir == 0

ENTRY
  sig = first bar whose close time >= T + delay_min minutes (searchsorted on close times, 'left'). Skip the
  release if sig >= m.n - 1, if close_time[sig] - T > max_delay_min minutes (data gap), if the UTC date of bar
  sig differs from the UTC date of T, or if ATR20[sig] is not finite or <= 0. Market order at the next open:
  entry_long[sig] for dir +1, entry_short[sig] for dir -1, entry_type 0, valid_bars 1.

STOP
  sl_dist[sig] = sl_atr x ATR20[sig], ATR20 = mean daily range of the previous atr_n trading days, known at the
  day start (F.atr_prev on F.daily_bars, broadcast to bars). No target (tp_dist NaN), max_bars 0.

EXIT
  Exit date E = the UTC date of T for hold 'd0'; for hold 'd1' the next weekday (Monday to Friday) after the UTC
  date of T (a Friday release exits on Monday). target = E at exit_utc. xi = first bar with m.ts >= target
  (searchsorted, 'left'). Primary marker: exit_long[xi - 1] = exit_short[xi - 1] = True when bar xi exists, so the
  position closes at the open of the first bar at or after the target. Causal fallback: on every bar j with
  m.ts[j] >= target and j <= the signal bar of the next kept release (m.n - 1 for the last one) both exit
  flags are True, so a missing target bar closes the position at the first bar after the gap and never carries it
  into the trade of the next release. Markers with no open position are ignored by the executor; a marker on the
  signal bar of the next release acts at its fill bar, where only the stop is checked, so the new trade is
  untouched. No other exits, no other filters.

R1  Late releases: a release is skipped entirely (no entry, no markers) unless xi > sig + 1, i.e. unless the fill
    bar sig + 1 opens before the exit target. For d0 this removes releases whose fill is at or after 20:30 UTC
    (the NZD releases at 21:45 and 22:45 UTC). For d1 it never binds.
R2  Planned-hold de-overlap (replaces the leftover guard). The qualifying releases of the active arm that pass
    every skip rule are walked in ts_avail order; a release is kept only if m.ts[sig] >= target_prev, the exit
    target of the last KEPT release (no condition for the first kept release). A dropped release sets no entry and
    no markers. A trade stopped early does not reopen the window. With this rule the previous trade has been
    closed at or before the open of the next signal bar, so the executor is flat when the next entry registers
    and no qualifying release is ignored silently by the executor.

PARAMETERS (every one read from p): arm, crowd_q, z_min, hold, sl_atr, delay_min, max_delay_min, exit_utc, atr_n,
rank_weeks. GRID = the full 24 cells (3 arms x 2 crowd_q x 2 z_min x 2 holds); stage A runs all 24 on EURUSD,
later stages run arm 'against' only (the Director spec).

CAUSALITY. Every decision at bar sig uses bars 0..sig, calendar rows and COT rows with ts_avail <= the close of
the signal bar, and timestamps (the open time of the fill bar is used only to apply R1, as for every next-open
order). The entry never depends on whether the exit target bar exists in the data: R1 is evaluated as
searchsorted(m.ts, target) > sig + 1, which is also true when the target lies beyond the end of the data. Such a
trade (only possible in the last day or two of a sample) has no scheduled exit and is closed by the executor at
the end of the data. A rule that dropped it would make the signals depend on how much data follows the signal
bar, which the truncation test treats as look-ahead. The primary marker is placed only when bar xi exists.

EXPECTED COUNTS (EURUSD, design releases from 2011-07-15, the first usable 52-week rank): against / with / neutral
releases 101 / 113 / 172 at crowd_q 0.8, z_min 1.0; 69 / 77 / 240 at 0.9, 1.0; 49 / 51 / 94 at 0.8, 1.5;
32 / 33 / 129 at 0.9, 1.5. After R1-R2 the q 0.8, z 1.0 arms hold about 98 / 106 / 162 trades (d0) and
86 / 92 / 127 (d1).

release_plan(m, p) returns the per-release table behind signals() (for reporting; signals() uses the same table).
"""
from __future__ import annotations

import numpy as np

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "fx_surprise_against_crowd"
PARAMS = {"arm": "against", "crowd_q": 0.8, "z_min": 1.0, "hold": "d1", "sl_atr": 1.0, "delay_min": 15,
          "max_delay_min": 60, "exit_utc": "20:30", "atr_n": 20, "rank_weeks": 52}
GRID = {"arm": ["against", "with", "neutral"], "crowd_q": [0.8, 0.9], "z_min": [1.0, 1.5], "hold": ["d0", "d1"]}

_ARMS = ("against", "with", "neutral")
_HOLDS = ("d0", "d1")
_COT_CURRENCIES = ("EUR", "GBP", "AUD", "NZD", "JPY", "CAD")
# event names (lower case) that are dropped from the event set
_EXCLUDED_EVENTS = ("crude oil", "natural gas", "inventories", "unemployment claims", "tic long", "votes",
                    "asset purchase facility")
# event names (lower case) where a higher-than-forecast number is bad for the currency
_INVERTED_EVENTS = ("unemployment rate", "unemployment change", "claimant count", "net borrowing", "jobless")


def _pair_roles(sym: str) -> tuple[str, str, str, int]:
    """(base, quote, COT currency, cot_sign) for a USD pair with one of the six COT currencies; else ValueError."""
    s = str(sym).upper()
    if len(s) == 6:
        base, quote = s[:3], s[3:]
        if quote == "USD" and base in _COT_CURRENCIES:
            return base, quote, base, 1
        if base == "USD" and quote in _COT_CURRENCIES:
            return base, quote, quote, -1
    raise ValueError(f"unsupported symbol {sym!r}: need USD against one of {_COT_CURRENCIES}")


def _read_params(p: dict) -> dict:
    """Read and validate every tunable from p."""
    arm, hold = p["arm"], p["hold"]
    if arm not in _ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {_ARMS}")
    if hold not in _HOLDS:
        raise ValueError(f"unknown hold {hold!r}; expected one of {_HOLDS}")
    cfg = {
        "arm": arm, "hold": hold,
        "crowd_q": float(p["crowd_q"]), "z_min": float(p["z_min"]), "sl_atr": float(p["sl_atr"]),
        "delay_min": int(p["delay_min"]), "max_delay_min": int(p["max_delay_min"]),
        "atr_n": int(p["atr_n"]), "rank_weeks": int(p["rank_weeks"]),
        "exit_hm": F.parse_hhmm(str(p["exit_utc"])),
    }
    if not cfg["sl_atr"] > 0.0:
        raise ValueError("sl_atr must be positive")
    if cfg["rank_weeks"] < 2 or cfg["atr_n"] < 1:
        raise ValueError("rank_weeks must be >= 2 and atr_n >= 1")
    return cfg


def _merged_releases(m: Market, base: str, quote: str, z_min: float) -> tuple[np.ndarray, np.ndarray]:
    """Merged releases (one per ts_avail) of the event set with |dz| >= z_min: (ts_avail, dz), ts ascending."""
    empty = (np.empty(0, dtype="datetime64[us]"), np.empty(0, dtype=np.float64))
    cal = F.ext_series(m, "calendar")
    ccy = cal.column("currency")
    z = cal.column("surprise_z")
    mask = ((cal.column("impact") == "high") & (cal.column("time_source") == "scraped") & np.isfinite(z)
            & ((ccy == base) | (ccy == quote)))
    rows = F.ext_subset(m, "calendar", mask)
    if rows.n == 0:
        return empty
    low = [("" if v is None else str(v)).lower() for v in rows.column("event")]
    excluded = np.array([any(w in nm for w in _EXCLUDED_EVENTS) for nm in low], dtype=bool)
    inverted = np.array([any(w in nm for w in _INVERTED_EVENTS) for nm in low], dtype=bool)
    side = np.where(rows.column("currency") == base, 1.0, -1.0)
    contrib = rows.column("surprise_z") * np.where(inverted, -1.0, 1.0) * side   # sign x |surprise_z| per row
    use = ~excluded
    if not use.any():
        return empty
    ts, group = np.unique(rows.ts_avail[use], return_inverse=True)
    dz = np.bincount(group, weights=contrib[use], minlength=len(ts))
    keep = (np.abs(dz) >= z_min) & (dz != 0.0)
    return ts[keep], dz[keep]


def _crowd_rank(m: Market, cot_ccy: str, rank_weeks: int) -> tuple[np.ndarray, np.ndarray]:
    """(ts_avail, rank) per COT row of the currency; rank = share of the last rank_weeks readings <= this one."""
    cot = F.ext_series(m, "cot")
    rows = F.ext_subset(m, "cot", cot.column("market") == cot_ccy)
    v = rows.column("spec_net_oi")
    rank = np.full(rows.n, np.nan)
    if rows.n >= rank_weeks:
        win = np.lib.stride_tricks.sliding_window_view(v, rank_weeks)      # row r: readings r-rw+1 .. r
        count = (win <= win[:, -1:]).sum(axis=1)
        rank[rank_weeks - 1:] = np.where(np.isfinite(win).all(axis=1), count / rank_weeks, np.nan)
    return rows.ts_avail, rank


def _exit_targets(t: np.ndarray, hold: str, exit_hm: tuple[int, int]) -> np.ndarray:
    """Exit target time per release: exit_utc on the UTC date of T (d0) or on the next Monday-to-Friday date (d1)."""
    day = t.astype("datetime64[D]")
    if hold == "d1":
        day = day + np.timedelta64(1, "D")
        wd = F.weekday(day)                                  # Monday = 0 ... Sunday = 6
        day = day + np.where(wd == 5, 2, np.where(wd == 6, 1, 0)).astype("timedelta64[D]")
    return day.astype("datetime64[us]") + np.timedelta64(exit_hm[0] * 60 + exit_hm[1], "m")


def release_plan(m: Market, p: dict) -> dict:
    """Per merged qualifying release (|dz| >= z_min), in ts_avail order, the table behind signals().

    Keys: t (ts_avail), dz, dir (+1 or -1), rank (NaN = none), state (-1, 0 or +1), pair_dir (cot_sign x state),
    in_arm (ranked and in the active arm), sig, xi, target, atr (ATR20 at sig), ok (in_arm and every skip rule,
    including R1), kept (ok and R2)."""
    cfg = _read_params(p)
    base, quote, cot_ccy, cot_sign = _pair_roles(m.sym)
    if m.n >= 2:
        t, dz = _merged_releases(m, base, quote, cfg["z_min"])
    else:
        t, dz = np.empty(0, dtype="datetime64[us]"), np.empty(0, dtype=np.float64)
    k = len(t)
    plan = {"t": t, "dz": dz, "dir": np.where(dz > 0, 1, -1).astype(np.int8),
            "rank": np.full(k, np.nan), "state": np.zeros(k, dtype=np.int8), "pair_dir": np.zeros(k, dtype=np.int8),
            "in_arm": np.zeros(k, dtype=bool), "sig": np.zeros(k, dtype=np.int64), "xi": np.zeros(k, dtype=np.int64),
            "target": np.empty(k, dtype="datetime64[us]"), "atr": np.full(k, np.nan),
            "ok": np.zeros(k, dtype=bool), "kept": np.zeros(k, dtype=bool)}
    if k == 0:
        return plan

    # ---- positioning state at each release
    cot_ts, cot_rank = _crowd_rank(m, cot_ccy, cfg["rank_weeks"])
    row = np.searchsorted(cot_ts, t, side="right") - 1                   # last COT row usable at T
    rank = np.full(k, np.nan)
    has_row = row >= 0
    rank[has_row] = cot_rank[row[has_row]]
    q = cfg["crowd_q"]
    state = np.where(rank >= q, 1, np.where(rank <= 1.0 - q, -1, 0)).astype(np.int8)
    pair_dir = (cot_sign * state).astype(np.int8)
    ranked = np.isfinite(rank)
    d = plan["dir"]
    if cfg["arm"] == "against":
        in_arm = ranked & (pair_dir != 0) & (d == -pair_dir)
    elif cfg["arm"] == "with":
        in_arm = ranked & (pair_dir != 0) & (d == pair_dir)
    else:
        in_arm = ranked & (pair_dir == 0)

    # ---- entry bar, stop, exit target and the skip rules
    close = m.close_times()
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, cfg["atr_n"]))
    sig = np.searchsorted(close, t + np.timedelta64(cfg["delay_min"], "m"), side="left")
    sig_c = np.minimum(sig, m.n - 1)
    target = _exit_targets(t, cfg["hold"], cfg["exit_hm"])
    xi = np.searchsorted(m.ts, target, side="left")
    ok = in_arm & (sig <= m.n - 2)                                        # the fill bar must exist
    ok &= (close[sig_c] - t) <= np.timedelta64(cfg["max_delay_min"], "m")  # no data gap
    ok &= m.ts[sig_c].astype("datetime64[D]") == t.astype("datetime64[D]")  # same UTC date
    ok &= np.isfinite(atr[sig_c]) & (atr[sig_c] > 0.0)
    ok &= xi > sig + 1                                                    # R1: the fill opens before the target

    # ---- R2: planned-hold de-overlap, walking the releases of the active arm in time order
    kept = np.zeros(k, dtype=bool)
    target_prev = None
    for i in np.flatnonzero(ok):
        if target_prev is not None and m.ts[sig[i]] < target_prev:
            continue
        kept[i] = True
        target_prev = target[i]

    plan.update({"rank": rank, "state": state, "pair_dir": pair_dir, "in_arm": in_arm, "sig": sig, "xi": xi,
                 "target": target, "atr": atr[sig_c], "ok": ok, "kept": kept})
    return plan


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    cfg = _read_params(p)
    plan = release_plan(m, p)
    idx = np.flatnonzero(plan["kept"])
    for pos, i in enumerate(idx):
        sg = int(plan["sig"][i])
        xi = int(plan["xi"][i])
        if plan["dir"][i] > 0:
            s.entry_long[sg] = True
        else:
            s.entry_short[sg] = True
        s.entry_type[sg] = 0
        s.valid_bars[sg] = 1
        s.sl_dist[sg] = cfg["sl_atr"] * plan["atr"][i]
        if xi < m.n:                                    # primary exit: close at the open of the first bar >= target
            s.exit_long[xi - 1] = True
            s.exit_short[xi - 1] = True
        nxt = int(plan["sig"][idx[pos + 1]]) if pos + 1 < len(idx) else m.n - 1
        s.exit_long[xi:nxt + 1] = True                  # causal fallback: every bar at or after the target
        s.exit_short[xi:nxt + 1] = True
    return s
