"""Rule-by-rule executor tests on hand-built candles."""
from __future__ import annotations

import numpy as np
import pytest

from edge.engine.executor import execute
from edge.engine.market import Market
from edge.engine.strategy import LIMIT, MARKET, STOP, Signals

SPREAD = 0.0002


def make_market(bid_ohlc: list[tuple[float, float, float, float]], spread: float = SPREAD) -> Market:
    a = np.array(bid_ohlc, dtype=np.float64)
    n = len(a)
    ts = np.datetime64("2024-01-01T00:00", "us") + np.arange(n).astype("timedelta64[m]")
    return Market(
        sym="EURUSD", tf="M1", ts=ts,
        bid_o=a[:, 0].copy(), bid_h=a[:, 1].copy(), bid_l=a[:, 2].copy(), bid_c=a[:, 3].copy(),
        ask_o=a[:, 0] + spread, ask_h=a[:, 1] + spread, ask_l=a[:, 2] + spread, ask_c=a[:, 3] + spread,
        vol=np.ones(n), quote_per_usd=np.ones(n), pip=0.0001, point=0.00001, asset="fx", ask_modelled_share=0.0,
    )


def sig(n: int, **kw) -> Signals:
    s = Signals(n)
    for k, v in kw.items():
        getattr(s, k)[...] = v if not isinstance(v, dict) else getattr(s, k)
        if isinstance(v, dict):
            for i, val in v.items():
                getattr(s, k)[i] = val
    return s


def test_long_market_entry_take_profit():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),   # bar 0: signal at close
                     (1.1000, 1.1010, 1.0998, 1.1005),   # bar 1: fill at ask open 1.1002
                     (1.1005, 1.1030, 1.1004, 1.1025),   # bar 2: TP (bid high 1.1030 >= 1.1022)
                     (1.1025, 1.1030, 1.1020, 1.1022)])
    s = Signals(4)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s)
    assert t.height == 1
    row = t.row(0, named=True)
    assert row["entry_i"] == 1 and row["exit_i"] == 2
    assert row["entry_px"] == pytest.approx(1.1002)
    assert row["exit_px"] == pytest.approx(1.1022)
    assert row["reason"] == "TP"
    assert row["r_gross"] == pytest.approx(2.0)


def test_entry_bar_only_stop_can_hit():
    # bar 1 would hit both SL (bid low) and TP (bid high) relative to fill 1.1002: SL wins on the entry bar
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1040, 1.0985, 1.1030),
                     (1.1030, 1.1035, 1.1025, 1.1030)])
    s = Signals(3)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s)
    assert t.height == 1
    assert t["reason"][0] == "SL" and t["exit_i"][0] == 1
    assert t["r_gross"][0] == pytest.approx(-1.0)


def test_same_bar_stop_and_target_goes_to_stop():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),   # entry 1.1002, nothing hit
                     (1.1001, 1.1040, 1.0985, 1.1030),   # both SL (1.0992) and TP (1.1022) inside -> SL
                     (1.1030, 1.1035, 1.1025, 1.1030)])
    s = Signals(4)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s)
    assert t["reason"][0] == "SL" and t["exit_i"][0] == 2
    assert t["exit_px"][0] == pytest.approx(1.0992)


def test_gap_through_stop_fills_at_open():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),   # entry 1.1002, SL 1.0992
                     (1.0970, 1.0975, 1.0960, 1.0965)])  # opens far below the stop
    s = Signals(3)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    t = execute(m, s)
    assert t["reason"][0] == "SL"
    assert t["exit_px"][0] == pytest.approx(1.0970)
    assert t["r_gross"][0] < -1.0


def test_stop_entry_fills_at_level_or_gap_open():
    # buy stop at 1.1020 (ask). Bar 1 ask high 1.1022 >= level -> fill at level; bid low stays above the stop.
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1012, 1.1020, 1.1011, 1.1018),
                     (1.1018, 1.1050, 1.1017, 1.1045)])
    s = Signals(3)
    s.entry_long[0] = True
    s.entry_type[0] = STOP
    s.entry_price_long[0] = 1.1020
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s)
    assert t["entry_px"][0] == pytest.approx(1.1020)
    assert t["reason"][0] == "TP"
    # gap: bar 1 opens above the level -> fill at the ask open
    m2 = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                      (1.1030, 1.1040, 1.1025, 1.1035),
                      (1.1035, 1.1070, 1.1034, 1.1060)])
    t2 = execute(m2, s)
    assert t2["entry_px"][0] == pytest.approx(1.1032)


def test_limit_entry_fills_at_level_no_slippage():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1002, 1.0975, 1.0990),   # ask low 1.0977 <= 1.0980 -> fill 1.0980
                     (1.0990, 1.1030, 1.0989, 1.1025)])
    s = Signals(3)
    s.entry_long[0] = True
    s.entry_type[0] = LIMIT
    s.entry_price_long[0] = 1.0980
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s, slippage=0.0001)
    assert t["entry_px"][0] == pytest.approx(1.0980)


def test_oco_first_fill_cancels_other():
    # box breakout: buy stop 1.1020, sell stop 1.0980 from the same bar; price breaks up on bar 1
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1005, 1.1025, 1.1000, 1.1020),   # long fills at 1.1020 (ask high 1.1027), SL 1.0990
                     (1.1020, 1.1022, 1.0950, 1.0960),   # stops the long; the short stop at 1.0980 was cancelled
                     (1.0960, 1.0965, 1.0940, 1.0950)])
    s = Signals(4)
    s.entry_long[0] = True
    s.entry_short[0] = True
    s.entry_type[0] = STOP
    s.entry_price_long[0] = 1.1020
    s.entry_price_short[0] = 1.0980
    s.sl_dist[0] = 0.0030
    s.valid_bars[0] = 3
    t = execute(m, s)
    assert t.height == 1 and t["side"][0] == 1
    assert t["reason"][0] == "SL" and t["exit_i"][0] == 2
    assert t["exit_px"][0] == pytest.approx(1.0990)


def test_oco_both_triggered_nearer_level_wins():
    # both stops inside bar 1; the open is nearer the short level -> short fills, long cancelled
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.0990, 1.1030, 1.0970, 1.1025),
                     (1.1025, 1.1060, 1.1020, 1.1055)])
    s = Signals(3)
    s.entry_long[0] = True
    s.entry_short[0] = True
    s.entry_type[0] = STOP
    s.entry_price_long[0] = 1.1020
    s.entry_price_short[0] = 1.0980
    s.sl_dist[0] = 0.0100
    t = execute(m, s)
    assert t.height == 1 and t["side"][0] == -1
    assert t["entry_px"][0] == pytest.approx(1.0980)


def test_time_exit_at_open():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),   # entry bar (fill 1.1002)
                     (1.1001, 1.1004, 1.1000, 1.1003),   # held 1 bar
                     (1.1003, 1.1006, 1.1002, 1.1005),   # held 2 bars -> exit at this open (bid 1.1003)
                     (1.1005, 1.1008, 1.1004, 1.1007)])
    s = Signals(5)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    s.max_bars[0] = 2
    t = execute(m, s)
    assert t["reason"][0] == "TIME" and t["exit_i"][0] == 3
    assert t["exit_px"][0] == pytest.approx(1.1003)


def test_signal_exit_next_open():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),   # entry
                     (1.1001, 1.1004, 1.1000, 1.1003),   # exit signal at this close
                     (1.1003, 1.1006, 1.1002, 1.1005),   # exit at open 1.1003
                     (1.1005, 1.1008, 1.1004, 1.1007)])
    s = Signals(5)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    s.exit_long[2] = True
    t = execute(m, s)
    assert t["reason"][0] == "SIGNAL" and t["exit_i"][0] == 3


def test_break_even_moves_stop():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),   # entry 1.1002, SL 1.0992 (risk 10 pips)
                     (1.1001, 1.1035, 1.1000, 1.1030),   # MFE 33 pips >= 3R -> BE: SL to 1.1002 + 1 pip
                     (1.1030, 1.1031, 1.0998, 1.1000),   # falls through the BE stop (1.1003)
                     (1.1000, 1.1001, 1.0990, 1.0995)])
    s = Signals(5)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    t = execute(m, s, be_trigger_r=3.0, be_lock_r=0.1)
    assert t["reason"][0] == "SL" and t["exit_i"][0] == 3
    assert t["exit_px"][0] == pytest.approx(1.1003)
    assert t["r_gross"][0] == pytest.approx(0.1)


def test_short_mirror():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0990, 1.0995),   # short fill at bid open 1.1000
                     (1.0995, 1.0996, 1.0960, 1.0970)])  # TP: ask low 1.0962 <= 1.0980
    s = Signals(3)
    s.entry_short[0] = True
    s.sl_dist[0] = 0.0010
    s.tp_dist[0] = 0.0020
    t = execute(m, s)
    assert t["side"][0] == -1
    assert t["entry_px"][0] == pytest.approx(1.1000)
    assert t["exit_px"][0] == pytest.approx(1.0980)
    assert t["r_gross"][0] == pytest.approx(2.0)


def test_open_position_closed_at_end():
    m = make_market([(1.1000, 1.1005, 1.0995, 1.1000),
                     (1.1000, 1.1003, 1.0999, 1.1001),
                     (1.1001, 1.1004, 1.1000, 1.1003)])
    s = Signals(3)
    s.entry_long[0] = True
    s.sl_dist[0] = 0.0010
    t = execute(m, s)
    assert t["reason"][0] == "END" and t["exit_px"][0] == pytest.approx(1.1003)


def test_random_walk_has_no_edge_and_pays_spread():
    rng = np.random.default_rng(0)
    n = 200_000
    steps = rng.normal(0, 0.0002, n)
    close = 1.10 + np.cumsum(steps)
    open_ = np.concatenate([[1.10], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0001, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0001, n))
    m = make_market(list(zip(open_, high, low, close)), spread=0.0001)
    s = Signals(n)
    s.entry_long[:] = rng.random(n) < 0.01
    s.entry_short[:] = (~s.entry_long) & (rng.random(n) < 0.01)
    s.sl_dist[:] = 0.0020
    s.tp_dist[:] = 0.0020
    t = execute(m, s)
    assert t.height > 500
    avg = t["r_gross"].mean()
    # spread is 1 pip on a 20-pip stop = -0.05 R expected; allow noise
    assert -0.12 < avg < 0.0
