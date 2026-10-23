"""Bar-by-bar execution of vectorised signals, compiled with numba.

Fill and exit rules (conservative, matching the gj-strat reference engine):
  * Orders placed at the close of bar i work from bar i+1. Market orders fill at that bar's open
    (ask for longs, bid for shorts) plus slippage.
  * Stop entries fill at max(level, open) for longs / min(level, open) for shorts, plus slippage.
    Limit entries fill at min(level, open) / max(level, open), no slippage.
  * On the entry bar only the stop loss can be hit (the path inside the bar is unknown).
  * On later bars, in order: gap through the stop at the open -> signal exit at the open ->
    time exit at the open -> stop inside the bar -> take profit inside the bar. Stop and target in
    the same bar count as a stop. Longs exit on bid prices, shorts on ask prices.
  * Stops and market exits pay slippage; take-profit fills (limits) do not.
  * Break-even and trailing stops are evaluated after a bar closes and become live on the next bar.
  * Long and short entries from the same signal bar are an OCO pair. If both would fill in one bar,
    the side that gapped at the open fills; otherwise the level nearer the open.
  * An open position blocks new entries. Any position still open at the last bar is closed at its close.
"""
from __future__ import annotations

import math

import numpy as np
import polars as pl
from numba import njit

from .market import Market
from .strategy import Signals

REASON_SL, REASON_TP, REASON_TIME, REASON_SIGNAL, REASON_END = 0, 1, 2, 3, 4
REASON_NAMES = ["SL", "TP", "TIME", "SIGNAL", "END"]


@njit(cache=True, nogil=True)
def _record(k, t_sig, t_entry_i, t_exit_i, t_side, t_entry_px, t_exit_px, t_sl0, t_tp, t_risk, t_reason,
            t_mae, t_mfe, t_spread,
            sig_i, e_i, x_i, side, e_px, x_px, sl0, tp, risk, reason, mae, mfe, spread):
    t_sig[k] = sig_i
    t_entry_i[k] = e_i
    t_exit_i[k] = x_i
    t_side[k] = side
    t_entry_px[k] = e_px
    t_exit_px[k] = x_px
    t_sl0[k] = sl0
    t_tp[k] = tp
    t_risk[k] = risk
    t_reason[k] = reason
    t_mae[k] = mae
    t_mfe[k] = mfe
    t_spread[k] = spread


@njit(cache=True, nogil=True)
def _execute(bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c,
             entry_long, entry_short, entry_type, entry_price_long, entry_price_short, valid_bars,
             sl_dist, tp_dist, max_bars, exit_long, exit_short,
             slippage, be_trigger_r, be_lock_r, trail_r):
    n = bid_o.shape[0]
    cap = 1
    for i in range(n):
        if entry_long[i] or entry_short[i]:
            cap += 1
    t_sig = np.empty(cap, np.int64)
    t_entry_i = np.empty(cap, np.int64)
    t_exit_i = np.empty(cap, np.int64)
    t_side = np.empty(cap, np.int8)
    t_entry_px = np.empty(cap, np.float64)
    t_exit_px = np.empty(cap, np.float64)
    t_sl0 = np.empty(cap, np.float64)
    t_tp = np.empty(cap, np.float64)
    t_risk = np.empty(cap, np.float64)
    t_reason = np.empty(cap, np.int8)
    t_mae = np.empty(cap, np.float64)
    t_mfe = np.empty(cap, np.float64)
    t_spread = np.empty(cap, np.float64)
    count = 0

    side = 0
    e_i = -1
    e_px = 0.0
    sl = 0.0
    sl0 = 0.0
    tp = math.nan
    risk = 0.0
    sig_i = -1
    mfe = 0.0
    mae = 0.0
    be_done = False
    max_hold = 0
    spread_e = 0.0

    pl_on = False
    pl_type = 0
    pl_px = 0.0
    pl_exp = -1
    pl_sig = -1
    ps_on = False
    ps_type = 0
    ps_px = 0.0
    ps_exp = -1
    ps_sig = -1

    for i in range(n):
        # ---------------- manage a position opened on an earlier bar
        if side != 0 and e_i < i:
            exit_px = math.nan
            reason = -1
            if side > 0:
                if bid_o[i] <= sl:
                    exit_px = bid_o[i] - slippage
                    reason = REASON_SL
                elif exit_long[i - 1]:
                    exit_px = bid_o[i] - slippage
                    reason = REASON_SIGNAL
                elif max_hold > 0 and (i - e_i) >= max_hold:
                    exit_px = bid_o[i] - slippage
                    reason = REASON_TIME
                elif bid_l[i] <= sl:
                    exit_px = sl - slippage
                    reason = REASON_SL
                elif (not math.isnan(tp)) and bid_h[i] >= tp:
                    exit_px = tp
                    reason = REASON_TP
                fav = bid_h[i] - e_px
                adv = e_px - bid_l[i]
            else:
                if ask_o[i] >= sl:
                    exit_px = ask_o[i] + slippage
                    reason = REASON_SL
                elif exit_short[i - 1]:
                    exit_px = ask_o[i] + slippage
                    reason = REASON_SIGNAL
                elif max_hold > 0 and (i - e_i) >= max_hold:
                    exit_px = ask_o[i] + slippage
                    reason = REASON_TIME
                elif ask_h[i] >= sl:
                    exit_px = sl + slippage
                    reason = REASON_SL
                elif (not math.isnan(tp)) and ask_l[i] <= tp:
                    exit_px = tp
                    reason = REASON_TP
                fav = e_px - ask_l[i]
                adv = ask_h[i] - e_px
            if fav > mfe:
                mfe = fav
            if adv > mae:
                mae = adv
            if reason >= 0:
                _record(count, t_sig, t_entry_i, t_exit_i, t_side, t_entry_px, t_exit_px, t_sl0, t_tp, t_risk,
                        t_reason, t_mae, t_mfe, t_spread,
                        sig_i, e_i, i, side, e_px, exit_px, sl0, tp, risk, reason, mae, mfe, spread_e)
                count += 1
                side = 0
            else:
                if be_trigger_r > 0.0 and (not be_done) and mfe >= be_trigger_r * risk:
                    if side > 0:
                        sl = e_px + be_lock_r * risk
                    else:
                        sl = e_px - be_lock_r * risk
                    be_done = True
                if trail_r > 0.0:
                    if side > 0:
                        cand = bid_h[i] - trail_r * risk
                        if cand > sl:
                            sl = cand
                    else:
                        cand = ask_l[i] + trail_r * risk
                        if cand < sl:
                            sl = cand

        # ---------------- pending entries
        if side == 0:
            if pl_on and i > pl_exp:
                pl_on = False
            if ps_on and i > ps_exp:
                ps_on = False
            fill_long = False
            fill_short = False
            px_l = 0.0
            px_s = 0.0
            gap_l = False
            gap_s = False
            if pl_on and i > pl_sig:
                if pl_type == 0:
                    fill_long = True
                    px_l = ask_o[i] + slippage
                elif pl_type == 1:
                    if ask_o[i] >= pl_px:
                        fill_long = True
                        px_l = ask_o[i] + slippage
                        gap_l = True
                    elif ask_h[i] >= pl_px:
                        fill_long = True
                        px_l = pl_px + slippage
                else:
                    if ask_o[i] <= pl_px:
                        fill_long = True
                        px_l = ask_o[i]
                        gap_l = True
                    elif ask_l[i] <= pl_px:
                        fill_long = True
                        px_l = pl_px
            if ps_on and i > ps_sig:
                if ps_type == 0:
                    fill_short = True
                    px_s = bid_o[i] - slippage
                elif ps_type == 1:
                    if bid_o[i] <= ps_px:
                        fill_short = True
                        px_s = bid_o[i] - slippage
                        gap_s = True
                    elif bid_l[i] <= ps_px:
                        fill_short = True
                        px_s = ps_px - slippage
                else:
                    if bid_o[i] >= ps_px:
                        fill_short = True
                        px_s = bid_o[i]
                        gap_s = True
                    elif bid_h[i] >= ps_px:
                        fill_short = True
                        px_s = ps_px
            if fill_long and fill_short:
                if gap_l and not gap_s:
                    fill_short = False
                elif gap_s and not gap_l:
                    fill_long = False
                else:
                    dl = abs(pl_px - ask_o[i]) if pl_type != 0 else 0.0
                    ds = abs(ps_px - bid_o[i]) if ps_type != 0 else 0.0
                    if dl <= ds:
                        fill_short = False
                    else:
                        fill_long = False
            if fill_long or fill_short:
                if fill_long:
                    side = 1
                    e_px = px_l
                    sig_i = pl_sig
                else:
                    side = -1
                    e_px = px_s
                    sig_i = ps_sig
                e_i = i
                risk = sl_dist[sig_i]
                if side > 0:
                    sl = e_px - risk
                else:
                    sl = e_px + risk
                sl0 = sl
                tpd = tp_dist[sig_i]
                if math.isnan(tpd):
                    tp = math.nan
                elif side > 0:
                    tp = e_px + tpd
                else:
                    tp = e_px - tpd
                max_hold = max_bars[sig_i]
                be_done = False
                spread_e = ask_o[i] - bid_o[i]
                pl_on = False
                ps_on = False
                if side > 0:
                    mfe = bid_h[i] - e_px
                    mae = e_px - bid_l[i]
                    stopped = bid_l[i] <= sl
                    stop_px = sl - slippage
                else:
                    mfe = e_px - ask_l[i]
                    mae = ask_h[i] - e_px
                    stopped = ask_h[i] >= sl
                    stop_px = sl + slippage
                if mfe < 0.0:
                    mfe = 0.0
                if mae < 0.0:
                    mae = 0.0
                if stopped:
                    _record(count, t_sig, t_entry_i, t_exit_i, t_side, t_entry_px, t_exit_px, t_sl0, t_tp, t_risk,
                            t_reason, t_mae, t_mfe, t_spread,
                            sig_i, e_i, i, side, e_px, stop_px, sl0, tp, risk, REASON_SL, mae, mfe, spread_e)
                    count += 1
                    side = 0

        # ---------------- register this bar's signals (ignored while a position is open)
        if side == 0:
            if entry_long[i]:
                pl_on = True
                pl_type = entry_type[i]
                pl_px = entry_price_long[i]
                pl_exp = i + valid_bars[i]
                pl_sig = i
            if entry_short[i]:
                ps_on = True
                ps_type = entry_type[i]
                ps_px = entry_price_short[i]
                ps_exp = i + valid_bars[i]
                ps_sig = i

    if side != 0:
        last = n - 1
        if side > 0:
            x_px = bid_c[last]
            fav = bid_h[last] - e_px
            adv = e_px - bid_l[last]
        else:
            x_px = ask_c[last]
            fav = e_px - ask_l[last]
            adv = ask_h[last] - e_px
        if fav > mfe:
            mfe = fav
        if adv > mae:
            mae = adv
        _record(count, t_sig, t_entry_i, t_exit_i, t_side, t_entry_px, t_exit_px, t_sl0, t_tp, t_risk,
                t_reason, t_mae, t_mfe, t_spread,
                sig_i, e_i, last, side, e_px, x_px, sl0, tp, risk, REASON_END, mae, mfe, spread_e)
        count += 1

    return (t_sig[:count], t_entry_i[:count], t_exit_i[:count], t_side[:count], t_entry_px[:count],
            t_exit_px[:count], t_sl0[:count], t_tp[:count], t_risk[:count], t_reason[:count],
            t_mae[:count], t_mfe[:count], t_spread[:count])


def execute(m: Market, sig: Signals, slippage: float = 0.0, be_trigger_r: float = 0.0,
            be_lock_r: float = 0.0, trail_r: float = 0.0) -> pl.DataFrame:
    """Run the executor and return one row per trade with gross R (before commission and swap)."""
    out = _execute(m.bid_o, m.bid_h, m.bid_l, m.bid_c, m.ask_o, m.ask_h, m.ask_l, m.ask_c,
                   sig.entry_long, sig.entry_short, sig.entry_type, sig.entry_price_long, sig.entry_price_short,
                   sig.valid_bars,
                   sig.sl_dist, sig.tp_dist, sig.max_bars, sig.exit_long, sig.exit_short,
                   float(slippage), float(be_trigger_r), float(be_lock_r), float(trail_r))
    (t_sig, e_i, x_i, side, e_px, x_px, sl0, tp, risk, reason, mae, mfe, spread) = out
    with np.errstate(divide="ignore", invalid="ignore"):
        r_gross = np.where(side > 0, x_px - e_px, e_px - x_px) / risk
        mae_r = mae / risk
        mfe_r = mfe / risk
    df = pl.DataFrame({
        "sig_i": t_sig, "entry_i": e_i, "exit_i": x_i, "side": side,
        "entry_ts": m.ts[e_i], "exit_ts": m.ts[x_i],
        "entry_px": e_px, "exit_px": x_px, "sl0": sl0, "tp": tp, "risk": risk,
        "r_gross": r_gross, "reason_code": reason, "mae_r": mae_r, "mfe_r": mfe_r,
        "spread_entry": spread, "bars_held": x_i - e_i,
        "quote_per_usd": m.quote_per_usd[e_i],
    })
    reason_map = pl.Series(REASON_NAMES)
    return df.with_columns(
        pl.col("entry_ts").dt.replace_time_zone("UTC"),
        pl.col("exit_ts").dt.replace_time_zone("UTC"),
        pl.col("reason_code").cast(pl.UInt32).map_elements(lambda c: REASON_NAMES[c], return_dtype=pl.String).alias("reason"),
    ).drop("reason_code")
