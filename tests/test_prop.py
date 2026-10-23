"""Prop-challenge simulator tests on synthetic trade lists."""
from __future__ import annotations

import numpy as np
import polars as pl

from edge.engine.prop import Leg, Phase, PropRules, run_challenge, build_events, simulate, summarize

RULES = PropRules(name="test", firm="t", plan="t", account_size=10_000,
                  phases=[Phase("p1", 10.0, 5.0, 10.0, 3), Phase("p2", 5.0, 5.0, 10.0, 3)],
                  max_loss_model="static", daily_loss_includes_floating=False, daily_reset_timezone="UTC")


def trades(rs: list[float], start="2024-01-01T10:00", hours_between=24, mae=None) -> pl.DataFrame:
    t0 = np.datetime64(start, "us")
    entry = np.array([t0 + np.timedelta64(i * hours_between, "h") for i in range(len(rs))])
    exit_ = entry + np.timedelta64(1, "h")
    df = pl.DataFrame({"entry_ts": entry, "exit_ts": exit_, "r_net": np.array(rs, dtype=float),
                       "mae_r": np.array(mae if mae is not None else [0.0] * len(rs), dtype=float)})
    return df.with_columns(pl.col("entry_ts").dt.replace_time_zone("UTC"), pl.col("exit_ts").dt.replace_time_zone("UTC"))


def test_pass_two_phases():
    # +1R a day at 3%: phase 1 needs 10% -> 4 trades (3.0, 6.1, 9.3, 12.5), phase 2 needs 5% -> 2 trades
    legs = [Leg("a", trades([1.0] * 10), 3.0)]
    ev = build_events(legs, "UTC")
    result, phase, pos, bal = run_challenge(ev, RULES, 0)
    assert result == "PASS" and phase == 2
    out = simulate(legs, RULES, last_start="2024-01-02")
    assert out.filter(pl.col("result") == "PASS").height >= 1


def test_min_trading_days_blocks_early_pass():
    # +4R on day one at 3% risk clears 10% but only 1 trading day -> keeps going
    legs = [Leg("a", trades([4.0, 0.0, 0.0, 0.0], hours_between=1), 3.0)]
    ev = build_events(legs, "UTC")
    result, phase, pos, bal = run_challenge(ev, RULES, 0)
    assert result == "unfinished" and phase == 1


def test_daily_loss_fail_same_day():
    # two -1R trades on the same day at 3% each = -6% -> fails the 5% daily limit
    legs = [Leg("a", trades([-1.0, -1.0, 1.0], hours_between=2), 3.0)]
    ev = build_events(legs, "UTC")
    result, phase, pos, bal = run_challenge(ev, RULES, 0)
    assert result == "fail:daily"


def test_max_loss_fail_across_days():
    # -1R a day at 3%: 0.97, 0.941, 0.913, 0.885 -> below 0.90 on the 4th day, each day within the daily limit
    legs = [Leg("a", trades([-1.0] * 6), 3.0)]
    ev = build_events(legs, "UTC")
    result, phase, pos, bal = run_challenge(ev, RULES, 0)
    assert result == "fail:max" and pos == ev.first_pos[3] + 1


def test_floating_excursion_counts_when_enabled():
    # a trade that ends +1R but was -2R under water at 3% risk = -6% intraday -> daily fail if floating counts
    legs = [Leg("a", trades([1.0, 1.0], mae=[2.0, 0.0]), 3.0)]
    ev = build_events(legs, "UTC")
    assert run_challenge(ev, RULES, 0, include_floating=True)[0] == "fail:daily"
    assert run_challenge(ev, RULES, 0, include_floating=False)[0] == "unfinished"


def test_trailing_floor_locks_at_breakeven():
    rules = PropRules(name="t", firm="t", plan="t", account_size=10_000,
                      phases=[Phase("p1", 10.0, 4.0, 6.0, 1)], max_loss_model="trailing",
                      daily_loss_includes_floating=False, daily_reset_timezone="UTC")
    # +2R at 2% -> 1.04 peak; then -1R at 2% -> 1.0192 (floor = 1.04-0.06 = 0.98, fine); then -1R -> 0.999 fine;
    # a further -1R -> 0.979 < floor 0.98 -> fail:max even though static 6% would allow it
    legs = [Leg("a", trades([2.0, -1.0, -1.0, -1.0]), 2.0)]
    ev = build_events(legs, "UTC")
    result, phase, pos, bal = run_challenge(ev, rules, 0)
    assert result == "fail:max"


def test_summary_fields():
    legs = [Leg("a", trades([1.0] * 30), 3.0)]
    out = simulate(legs, RULES, last_start="2024-01-20")
    s = summarize(out)
    assert s["challenges"] >= 10
    assert s["pass_eventually_pct"] == 100.0
    assert s["months_per_funded_account"] > 0


def test_day_reset_offset_moves_the_boundary_to_17_new_york():
    # 20:30 UTC on 2024-07-01 is 16:30 New York (same server day); 21:30 UTC is 17:30 (next server day)
    from edge.engine.prop import _day_ids
    ts = np.array(["2024-07-01T20:30", "2024-07-01T21:30"], dtype="datetime64[us]")
    plain = _day_ids(ts, "America/New_York")
    assert plain[0] == plain[1]
    shifted = _day_ids(ts, "America/New_York", 7.0)
    assert shifted[1] == shifted[0] + 1
    assert _day_ids(ts, "UTC")[0] == _day_ids(ts, "UTC")[1]
