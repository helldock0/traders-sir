"""Liquidity-withdrawal reversal (fx_liquidity_withdrawal_reversal): M15, long/short fade of a one-hour move made
while the quoted spread was wide against its own time-of-day norm.

Mechanism: short-term reversals are the pay of liquidity providers, and the pay is large only when liquidity supply
is scarce. In FX the scarcity shows as a widened top-of-book spread. A large one-hour move made while the spread of
the bar is at least spread_ratio_min times its norm for that 15-minute slot is treated as a price concession to the
few providers still quoting and is faded for about two hours. The same move with a normal spread is not faded.
spread_ratio_min = 0 is the no-spread-condition control (every bar whose slot norm is defined qualifies);
exclude_news = False is the scheduled-release control. Both controls run at stage A only.

Rules (all times UTC; M15 bars are labelled by open time, so a bar closes at ts + 15 min; bars are sparse, so
everything is located by timestamp and no bar per slot is assumed; every value for bar i uses bars 0..i only):

DEFINITIONS
* mid = (bid_c + ask_c) / 2. move[i] = mid[i] - mid[i-4], valid only if i >= 4 and ts[i] - ts[i-4] <= max_gap_min
  (75) minutes.
* ATR20 = F.atr_prev(F.daily_bars(m), 20) mapped to bars (known at the start of the trading day); finite and > 0.
* Spread proxy spr[i] = max(ask_o - bid_o, ask_c - bid_c, ask_h - bid_h, ask_l - bid_l), in price units.
* Slot norm: slot = minute of day of the bar open. norm[i] = median of spr over the previous norm_window (20) bars
  that share slot[i], strictly before bar i (the first norm_window bars of a slot have no norm). ratio = spr / norm,
  used only where norm is finite and > 0. Every arm, the control included, needs norm, so all arms cover one period.
* Move window of bar i = [open + 15 min - 60 min, open + 15 min). With mod = open minute of day: ws = (mod - 45)
  mod 1440 and we = (mod + 15) mod 1440. A block [b0, b1) in minutes of day overlaps the window if ws < we and
  ws < b1 and b0 < we, or if ws >= we (the window crosses 00:00 UTC, this includes we == 0) and (ws < b1 or b0 < we).
* ROLLOVER block, always applied in every arm: [20:45, 22:15) = minutes [1245, 1335). A data-quality exclusion
  (the asymmetric rollover widening distorts the mid price), not news.
* NEWS blocks, applied only when exclude_news is true: US [12:00, 15:30) and [18:00, 20:00) on every market, plus
  the blocks of each leg of m.sym (letters 0-2 and 3-5): JPY [03:00, 05:00); EUR [06:00, 10:15) and [11:30, 12:00);
  GBP [06:00, 10:15) and [10:45, 12:00); AUD [00:15, 02:15) and [03:00, 05:00); USD and XAU have none of their own.
  USDJPY therefore keeps exactly [03:00, 05:00), [12:00, 15:30), [18:00, 20:00) and the rollover block.

CANDIDATE BAR i: valid move, ATR20 finite and > 0, norm defined, |move[i]| >= move_atr_min * ATR20[i],
ratio[i] >= spread_ratio_min, the move window clear of the rollover block, and (exclude_news false or the move
window clear of every NEWS block).
Both thresholds are ">=" comparisons and an exact tie passes. Prices sit on a point grid, so a spread of exactly
twice the slot norm is common; both comparisons carry a relative tolerance of 1e-9 (TIE_TOL) so that floating-point
noise cannot decide a tie (see the comment in signals()).

EPISODES (one trade per episode): candidate indices in ascending order. Accept i if i >= last + cooldown_bars (12)
and set last = i at acceptance, BEFORE any delay check, so both entry_delay_bars arms trade the same episodes.

ORDERS: j = i + entry_delay_bars (0 or 1). Skip the episode if j >= m.n, or if entry_delay_bars > 0 and
ts[j] - ts[i] > delay_max_gap_min (30) minutes. Every field is written at index j and uses information of bars
<= j only (neither ts[j+1] nor any field of the fill bar is read):
  move[i] > 0 -> entry_short[j] (fade the up move);  move[i] < 0 -> entry_long[j] (fade the down move);
  market order at the next open (entry_type 0, valid_bars 1); sl_dist[j] = stop_mult * |move[i]| (1 R is the size
  of the move being faded, > 0 because |move[i]| >= move_atr_min * ATR20 > 0); tp_dist NaN (no target, the time
  exit measures the mean retracement); max_bars[j] = hold_bars (8, about two hours).
No exit signals, no other filters, no pyramiding (the executor blocks entries while a position is open).

Parameters (all read from p): spread_ratio_min, move_atr_min, exclude_news, entry_delay_bars, stop_mult (1.0),
hold_bars (8), cooldown_bars (12), norm_window (20), max_gap_min (75), delay_max_gap_min (30). Structural
constants fixed by the definitions: M15 bars, a 4-bar (60 minute) move, ATR over 20 trading days.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from edge.engine import features as F
from edge.engine.market import Market
from edge.engine.strategy import Signals

NAME = "fx_liquidity_withdrawal_reversal"
PARAMS = {"spread_ratio_min": 2, "move_atr_min": 0.25, "exclude_news": True, "entry_delay_bars": 0,
          "stop_mult": 1.0, "hold_bars": 8, "cooldown_bars": 12, "norm_window": 20, "max_gap_min": 75,
          "delay_max_gap_min": 30}
GRID = {"spread_ratio_min": [0, 2], "move_atr_min": [0.25, 0.4], "exclude_news": [True, False],
        "entry_delay_bars": [0, 1]}

# ---- structural constants fixed by the definitions (not tunables)
BAR_MIN = 15          # M15 bars
MOVE_BARS = 4         # the move is mid_c[i] - mid_c[i-4], one hour
WINDOW_MIN = 60       # nominal move window [close - 60 min, close)
ATR_DAYS = 20         # ATR20, previous 20 trading days
DAY_MIN = 1440
TIE_TOL = 1e-9        # relative tolerance that makes the ">= threshold" comparisons tie-safe (see signals())

# ---- blocks, minutes of the UTC day, half-open [b0, b1)
ROLL_BLOCKS = [(1245, 1335)]                      # 20:45-22:15, always applied
US_NEWS_BLOCKS = [(720, 930), (1080, 1200)]       # 12:00-15:30 and 18:00-20:00, every market
LEG_NEWS_BLOCKS = {
    "JPY": [(180, 300)],                          # 03:00-05:00
    "EUR": [(360, 615), (690, 720)],              # 06:00-10:15 and 11:30-12:00
    "GBP": [(360, 615), (645, 720)],              # 06:00-10:15 and 10:45-12:00
    "AUD": [(15, 135), (180, 300)],               # 00:15-02:15 and 03:00-05:00
    "USD": [],
    "XAU": [],
}


def _as_bool(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y")
    return bool(v)


def _news_blocks(sym: str) -> list[tuple[int, int]]:
    """US blocks on every market plus the blocks of each leg of the symbol (letters 0-2 and 3-5)."""
    s = sym.upper()
    blocks = list(US_NEWS_BLOCKS)
    for leg in (s[:3], s[3:6]):
        blocks += LEG_NEWS_BLOCKS.get(leg, [])
    return blocks


def _window_hits(open_min: np.ndarray, blocks: list[tuple[int, int]]) -> np.ndarray:
    """True where the nominal one-hour move window ending at the close of the bar overlaps any block.

    The window is [open + 15 - 60, open + 15) in minutes of day: ws = (mod - 45) mod 1440, we = (mod + 15) mod 1440.
    If ws < we the window sits inside one day; if ws >= we it crosses 00:00 UTC (we == 0 included)."""
    ws = (open_min - (WINDOW_MIN - BAR_MIN)) % DAY_MIN
    we = (open_min + BAR_MIN) % DAY_MIN
    crosses = ws >= we
    hit = np.zeros(open_min.shape[0], dtype=bool)
    for b0, b1 in blocks:
        plain = (ws < b1) & (b0 < we)
        wrapped = (ws < b1) | (b0 < we)
        hit |= np.where(crosses, wrapped, plain)
    return hit


def _slot_norm(spr: np.ndarray, slot: np.ndarray, window: int) -> np.ndarray:
    """Median of spr over the previous `window` bars that share the slot, strictly before each bar; NaN before that.

    Loops over the slots only. For a slot with ascending bar indices idx, window r covers idx[r:r+window] and is
    assigned to idx[r+window], the next occurrence of the slot, so a bar never sees itself or anything later."""
    norm = np.full(spr.shape[0], np.nan)
    for sl in np.unique(slot):
        idx = np.flatnonzero(slot == sl)
        if idx.size <= window:
            continue
        wins = sliding_window_view(spr[idx], window)[:-1]    # drop the last window: its successor does not exist
        norm[idx[window:]] = np.median(wins, axis=1)
    return norm


def signals(m: Market, p: dict) -> Signals:
    s = Signals(m.n)
    if m.tf.upper() != "M15":
        raise ValueError(f"{NAME} is defined on M15 bars only, got {m.tf}")
    n = m.n
    if n <= MOVE_BARS:
        return s

    # ---- one-hour move ending at each bar: valid only when the four bars back span <= max_gap_min minutes
    mid = 0.5 * (m.bid_c + m.ask_c)
    span_min = (m.ts[MOVE_BARS:] - m.ts[:-MOVE_BARS]) / np.timedelta64(1, "m")
    move = np.full(n, np.nan)
    move[MOVE_BARS:] = np.where(span_min <= float(p["max_gap_min"]), mid[MOVE_BARS:] - mid[:-MOVE_BARS], np.nan)

    # ---- ATR20, known at the start of the trading day
    daily = F.daily_bars(m)
    atr = daily.to_bars(F.atr_prev(daily, ATR_DAYS))

    # ---- quoted-spread proxy and its norm for the same 15-minute slot (previous occurrences only)
    spr = np.maximum(np.maximum(m.ask_o - m.bid_o, m.ask_c - m.bid_c),
                     np.maximum(m.ask_h - m.bid_h, m.ask_l - m.bid_l))
    slot = F.minute_of_day_utc(m)
    norm = _slot_norm(spr, slot, int(p["norm_window"]))

    # ---- candidate bars
    # Ties at a threshold must pass (">=") and floating-point noise must not decide them. Quoted prices are
    # quantised at one point (0.1 pip on FX), so a spread is a whole number of points a and the slot norm (median of
    # an even number of values) a multiple of half a point, b/2: a true ratio is 2a/b for integers a and b, and a bar
    # spread of exactly twice the norm (1.0 pip against 0.5 pip) is common. In floats spr / norm then lands on
    # 2 +/- 1e-12 and a plain `ratio >= 2` keeps some exact ties and drops others. Anything within 1e-9 (relative)
    # of a threshold is an exact tie: the float noise is at most about 1e-10 relative, and a genuine non-tie ratio
    # would need a slot norm above 5e8 points to fall inside the tolerance. A relative tolerance is used, not spreads
    # rounded to points, because it keeps the ratio invariant under Market.widen_spread (cost stress), where rounding
    # widened half-points is not scale-invariant. The move threshold gets the same tolerance for consistency.
    with np.errstate(invalid="ignore", divide="ignore"):
        norm_ok = np.isfinite(norm) & (norm > 0)
        ratio = np.where(norm_ok, spr / norm, np.nan)
        abs_move = np.abs(move)
        cand = (np.isfinite(move) & (abs_move > 0) & np.isfinite(atr) & (atr > 0) & norm_ok
                & (abs_move >= float(p["move_atr_min"]) * atr * (1.0 - TIE_TOL))
                & (ratio >= float(p["spread_ratio_min"]) * (1.0 - TIE_TOL)))
    cand &= ~_window_hits(slot, ROLL_BLOCKS)
    if _as_bool(p["exclude_news"]):
        cand &= ~_window_hits(slot, _news_blocks(m.sym))

    # ---- episodes: accepted before any delay check, so every delay arm trades the same episodes
    cooldown = int(p["cooldown_bars"])
    last = -(1 << 60)
    episodes = []
    for i in np.flatnonzero(cand).tolist():
        if i >= last + cooldown:
            episodes.append(i)
            last = i
    if not episodes:
        return s

    # ---- orders, written at j = i + entry_delay_bars from information of bars <= j
    delay = int(p["entry_delay_bars"])
    ei = np.asarray(episodes, dtype=np.int64)
    ej = ei + delay
    keep = ej < n
    if delay > 0:
        ej_c = np.minimum(ej, n - 1)
        gap_min = (m.ts[ej_c] - m.ts[ei]) / np.timedelta64(1, "m")
        keep &= gap_min <= float(p["delay_max_gap_min"])
    ei, ej = ei[keep], ej[keep]
    if ei.size == 0:
        return s

    mv = move[ei]
    fade_short = mv > 0                       # fade an up move
    s.entry_short[ej[fade_short]] = True
    s.entry_long[ej[~fade_short]] = True
    s.sl_dist[ej] = float(p["stop_mult"]) * np.abs(mv)
    s.max_bars[ej] = int(p["hold_bars"])
    return s
