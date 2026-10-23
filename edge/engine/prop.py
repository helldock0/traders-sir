"""Prop-firm challenge simulation on merged trade lists.

A "mix" is a list of legs (strategy trade lists with a risk % per trade). Challenges start at the first
trade of every trading day and are replayed in time order against a relative balance (1.0 = account
size), risking risk_pct of the *current* balance per trade:

  * daily loss: balance change since the day started (day boundary = midnight in the firm's reset timezone,
    shifted by daily_reset_offset_hours; America/New_York with offset 7 = 17:00 New York = MT5 server midnight)
    below -daily_loss_pct of the day's starting balance -> fail. With include_floating, a trade's
    worst excursion (mae_r) is also checked as if marked to market (conservative approximation).
  * max loss: static (floor = 1 - max_loss_pct) or trailing (floor = min(peak - max_loss_pct, 1.0)).
  * a phase passes when balance >= 1 + target and distinct trading days >= min_trading_days;
    the next phase starts fresh at 1.0 and open trades are dropped (their P/L is ignored).
  * optional time limit per phase and consistency rule (max share of phase profit from one day).

Outputs per challenge: result (PASS / fail:daily / fail:max / fail:time / unfinished), days taken and
phase reached. `summarize` turns these into pass-within-N-months rates, pass-eventually and
months per funded account (total challenge months spent / number of passes), the figure that
measures how fast a mix actually gets funded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import polars as pl
import yaml

from ..data import store

PROP_CONFIG = store.ROOT / "config" / "prop_firms.yaml"


@dataclass
class Phase:
    name: str
    target_pct: float
    daily_loss_pct: float
    max_loss_pct: float
    min_trading_days: int = 0


@dataclass
class PropRules:
    name: str
    firm: str
    plan: str
    account_size: float
    phases: list[Phase]
    max_loss_model: str = "static"
    daily_loss_includes_floating: bool = True
    daily_reset_timezone: str = "UTC"
    time_limit_days: int | None = None
    consistency_max_day_share: float | None = None
    daily_reset_offset_hours: float = 0.0     # day boundary = local midnight in daily_reset_timezone minus this offset

    @classmethod
    def load(cls, profile: str | None = None, path: Path = PROP_CONFIG) -> "PropRules":
        cfg = yaml.safe_load(path.read_text())
        key = profile or cfg["default"]
        p = cfg[key]
        phases = [Phase(ph.get("name", f"phase{i + 1}"), float(ph["profit_target_pct"]), float(ph["max_daily_loss_pct"]),
                        float(ph["max_loss_pct"]), int(ph.get("min_trading_days", 0))) for i, ph in enumerate(p["phases"])]
        return cls(name=key, firm=p.get("firm", ""), plan=p.get("plan", ""), account_size=float(p.get("account_size", 10_000)),
                   phases=phases, max_loss_model=p.get("max_loss_model", "static"),
                   daily_loss_includes_floating=bool(p.get("daily_loss_includes_floating", True)),
                   daily_reset_timezone=p.get("daily_reset_timezone", "UTC") or "UTC",
                   time_limit_days=p.get("time_limit_days"), consistency_max_day_share=p.get("consistency_max_day_share"),
                   daily_reset_offset_hours=float(p.get("daily_reset_offset_hours", 0.0) or 0.0))


@dataclass
class Leg:
    name: str
    trades: pl.DataFrame      # needs entry_ts, exit_ts, r_net (mae_r optional)
    risk_pct: float


@dataclass
class Events:
    entry_ts: np.ndarray      # per trade, datetime64[us]
    exit_ts: np.ndarray
    r: np.ndarray
    mae_r: np.ndarray
    leg: np.ndarray           # leg index per trade
    entry_day: np.ndarray     # int day id in reset tz, per trade
    ev_trade: np.ndarray      # per event: trade index
    ev_kind: np.ndarray       # per event: 0 exit, 1 entry
    ev_day: np.ndarray        # per event: int day id in reset tz
    ev_ts: np.ndarray
    first_pos: np.ndarray     # per trade: position of its entry event
    risk_pct: np.ndarray      # per leg

    @property
    def n_trades(self) -> int:
        return len(self.r)


def _day_ids(ts: np.ndarray, tz: str, offset_hours: float = 0.0) -> np.ndarray:
    """Calendar day id of each timestamp in `tz`, after shifting by `offset_hours` (e.g. tz America/New_York
    with offset 7 gives the MT5 convention: the day rolls at 17:00 New York = 00:00 server time)."""
    if offset_hours:
        ts = ts + np.timedelta64(int(round(offset_hours * 60)), "m")
    s = pl.Series("ts", ts).dt.replace_time_zone("UTC").dt.convert_time_zone(tz)
    return s.dt.date().to_numpy().astype("datetime64[D]").astype(np.int64)


def build_events(legs: list[Leg], tz: str, offset_hours: float = 0.0) -> Events:
    frames = []
    for k, leg in enumerate(legs):
        t = leg.trades
        if "mae_r" not in t.columns:
            t = t.with_columns(pl.lit(0.0).alias("mae_r"))
        frames.append(t.select("entry_ts", "exit_ts", "r_net", "mae_r").with_columns(pl.lit(k, dtype=pl.Int32).alias("leg")))
    allt = pl.concat(frames).sort("entry_ts", "exit_ts")
    entry_ts = allt.get_column("entry_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
    exit_ts = allt.get_column("exit_ts").dt.replace_time_zone(None).to_numpy().astype("datetime64[us]")
    n = len(entry_ts)
    # events: exits before entries at the same timestamp; a trade closed on its entry bar exits after its entry
    ev_ts = np.concatenate([entry_ts, exit_ts])
    ev_kind = np.concatenate([np.ones(n, dtype=np.int8), np.zeros(n, dtype=np.int8)])
    ev_trade = np.concatenate([np.arange(n), np.arange(n)])
    same = exit_ts <= entry_ts
    order_key = np.concatenate([np.ones(n, dtype=np.int8), np.where(same, 2, 0).astype(np.int8)])
    order = np.lexsort((ev_trade, order_key, ev_ts))
    ev_ts, ev_kind, ev_trade = ev_ts[order], ev_kind[order], ev_trade[order]
    first_pos = np.empty(n, dtype=np.int64)
    first_pos[ev_trade[ev_kind == 1]] = np.flatnonzero(ev_kind == 1)
    return Events(
        entry_ts=entry_ts, exit_ts=exit_ts, r=allt.get_column("r_net").to_numpy().astype(np.float64),
        mae_r=np.nan_to_num(allt.get_column("mae_r").to_numpy().astype(np.float64)),
        leg=allt.get_column("leg").to_numpy().astype(np.int64),
        entry_day=_day_ids(entry_ts, tz, offset_hours), ev_trade=ev_trade, ev_kind=ev_kind,
        ev_day=_day_ids(ev_ts, tz, offset_hours), ev_ts=ev_ts,
        first_pos=first_pos, risk_pct=np.array([leg.risk_pct for leg in legs], dtype=np.float64),
    )


def run_challenge(ev: Events, rules: PropRules, start_trade: int, include_floating: bool | None = None,
                  scale: Callable[[float, float, int, float], float] | None = None,
                  budget_pct: float | None = None) -> tuple[str, int, int, float]:
    """Replay one challenge from trade `start_trade`. Returns (result, phase_reached, end_event_pos, end_balance)."""
    floating = rules.daily_loss_includes_floating if include_floating is None else include_floating
    phases = rules.phases
    phase = 0
    ph = phases[0]
    bal = peak = 1.0
    open_: dict[int, float] = {}
    days: set[int] = set()
    cur_day = -1
    day_start = 1.0
    day_pnl: dict[int, float] = {}
    phase_start_ts = ev.ev_ts[ev.first_pos[start_trade]]
    for pos in range(ev.first_pos[start_trade], len(ev.ev_kind)):
        k = ev.ev_trade[pos]
        if k < start_trade:
            continue
        d = ev.ev_day[pos]
        if d != cur_day:
            cur_day, day_start = d, bal
        if rules.time_limit_days is not None:
            elapsed = (ev.ev_ts[pos] - phase_start_ts) / np.timedelta64(1, "D")
            if elapsed > rules.time_limit_days:
                return "fail:time", phase + 1, pos, bal
        if ev.ev_kind[pos] == 1:
            pct = ev.risk_pct[ev.leg[k]]
            if scale is not None:
                pct = scale(pct, bal, phase, ph.target_pct / 100.0)
            if budget_pct is not None:
                # the assistant's entry budget: closed loss so far today + risk of every open stop + the new risk
                worst = max(day_start - bal, 0.0) + sum(open_.values()) + pct / 100.0 * bal
                if worst > budget_pct / 100.0 * day_start:
                    continue
            open_[k] = pct / 100.0 * bal
            days.add(int(ev.entry_day[k]))
            continue
        if k not in open_:
            continue
        risk_usd = open_.pop(k)
        floor = (1.0 - ph.max_loss_pct / 100.0) if rules.max_loss_model == "static" else min(peak - ph.max_loss_pct / 100.0, 1.0)
        if floating and ev.mae_r[k] > 0:
            worst = bal - risk_usd * ev.mae_r[k]
            if worst - day_start < -ph.daily_loss_pct / 100.0 * day_start:
                return "fail:daily", phase + 1, pos, worst
            if worst <= floor:
                return "fail:max", phase + 1, pos, worst
        pnl = risk_usd * ev.r[k]
        bal += pnl
        peak = max(peak, bal)
        day_pnl[d] = day_pnl.get(d, 0.0) + pnl
        if bal - day_start < -ph.daily_loss_pct / 100.0 * day_start:
            return "fail:daily", phase + 1, pos, bal
        if bal <= floor:
            return "fail:max", phase + 1, pos, bal
        consistent = True
        if rules.consistency_max_day_share is not None and bal > 1.0:
            consistent = max(day_pnl.values()) <= rules.consistency_max_day_share * (bal - 1.0)
        if bal >= 1.0 + ph.target_pct / 100.0 and len(days) >= ph.min_trading_days and consistent:
            if phase == len(phases) - 1:
                return "PASS", phase + 1, pos, bal
            phase += 1
            ph = phases[phase]
            bal = peak = 1.0
            open_ = {}
            days = set()
            cur_day = -1
            day_pnl = {}
            phase_start_ts = ev.ev_ts[pos]
    return "unfinished", phase + 1, len(ev.ev_kind) - 1, bal


def challenge_starts(ev: Events, last_start: np.datetime64 | None) -> np.ndarray:
    """Index of the first trade on each distinct trading day (entry order), up to last_start."""
    change = np.concatenate([[True], ev.entry_day[1:] != ev.entry_day[:-1]])
    starts = np.flatnonzero(change)
    if last_start is not None:
        starts = starts[ev.entry_ts[starts] <= np.datetime64(last_start, "us")]
    return starts


def simulate(legs: list[Leg], rules: PropRules, last_start: str | np.datetime64 | None = None,
             include_floating: bool | None = None, scale=None, budget_pct: float | None = None) -> pl.DataFrame:
    """One row per challenge start: start_ts, result, days, phase_reached, end_balance."""
    ev = build_events(legs, rules.daily_reset_timezone, rules.daily_reset_offset_hours)
    if last_start is None:
        last = ev.entry_ts.max() - np.timedelta64(365, "D")
    else:
        last = np.datetime64(last_start, "us")
    rows = []
    for s in challenge_starts(ev, last):
        result, phase_reached, pos, bal = run_challenge(ev, rules, int(s), include_floating, scale, budget_pct)
        t0 = ev.entry_ts[s]
        days = float((ev.ev_ts[pos] - t0) / np.timedelta64(1, "D"))
        rows.append((t0, result, days, phase_reached, bal))
    return pl.DataFrame(rows, schema=["start_ts", "result", "days", "phase_reached", "end_balance"], orient="row")


def summarize(outcomes: pl.DataFrame, months: tuple[int, ...] = (1, 2, 3, 6)) -> dict:
    n = outcomes.height
    if n == 0:
        return {"challenges": 0}
    res = outcomes.get_column("result").to_numpy()
    days = outcomes.get_column("days").to_numpy()
    passed = res == "PASS"
    finished = res != "unfinished"
    out: dict = {"challenges": int(n), "finished": int(finished.sum())}
    failed = np.char.startswith(res.astype(str), "fail")
    for mth in months:
        out[f"pass_le_{mth}m_pct"] = float(100 * (passed & (days <= mth * 30.4375)).mean())
        out[f"fail_le_{mth}m_pct"] = float(100 * (failed & (days <= mth * 30.4375)).mean())
    if 6 not in months:
        out["fail_le_6m_pct"] = float(100 * (failed & (days <= 6 * 30.4375)).mean())
    out["pass_eventually_pct"] = float(100 * passed[finished].mean()) if finished.any() else float("nan")
    out["median_months_to_pass"] = float(np.median(days[passed]) / 30.4375) if passed.any() else float("nan")
    out["months_per_funded_account"] = float(days[finished].sum() / 30.4375 / passed.sum()) if passed.any() else float("inf")
    for kind in ("fail:daily", "fail:max", "fail:time"):
        out[f"{kind.replace(':', '_')}_pct"] = float(100 * (res == kind).mean())
    out["avg_days_per_attempt"] = float(days[finished].mean()) if finished.any() else float("nan")
    return out


def mix_equity(legs: list[Leg], tz: str = "UTC") -> dict:
    """Compounding stats of the mix over the whole sample: final multiple, CAGR, max drawdown (closed trades)."""
    ev = build_events(legs, tz)
    bal = peak = 1.0
    dd = 0.0
    open_: dict[int, float] = {}
    for pos in range(len(ev.ev_kind)):
        k = ev.ev_trade[pos]
        if ev.ev_kind[pos] == 1:
            open_[k] = ev.risk_pct[ev.leg[k]] / 100.0 * bal
        else:
            bal += open_.pop(k) * ev.r[k]
            peak = max(peak, bal)
            dd = max(dd, 1 - bal / peak)
    years = max((ev.exit_ts.max() - ev.entry_ts.min()) / np.timedelta64(365, "D"), 1e-9)
    return {"final_multiple": bal, "cagr_pct": 100 * (bal ** (1 / years) - 1), "max_dd_pct": 100 * dd, "years": float(years)}


def format_summary(name: str, s: dict) -> str:
    if s.get("challenges", 0) == 0:
        return f"| {name} | 0 | | | | | | | |"
    return (f"| {name} | {s['challenges']} | {s['pass_le_2m_pct']:.1f} | {s['pass_le_3m_pct']:.1f} | {s['pass_le_6m_pct']:.1f} | "
            f"{s['fail_le_6m_pct']:.1f} | {s['pass_eventually_pct']:.1f} | {s['median_months_to_pass']:.1f} | "
            f"{s['months_per_funded_account']:.1f} | {s['fail_daily_pct']:.1f} | {s['fail_max_pct']:.1f} |")


SUMMARY_HEADER = ("| mix | challenges | pass <=2m % | pass <=3m % | pass <=6m % | fail <=6m % | pass eventually % | "
                  "median months to pass | months per funded account | fail daily % | fail max % |\n"
                  "|---|---|---|---|---|---|---|---|---|---|---|")
