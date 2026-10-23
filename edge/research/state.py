"""Research state: hypotheses, trials, verdicts and buckets in SQLite (runs/research.sqlite).

Every backtest that is used to judge an idea is a trial; the programme-wide trial count feeds the
deflated Sharpe gate. Scrap is kept forever so the Director never re-tests a dead idea.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..data import store

DB_PATH = store.ROOT / "runs" / "research.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    cycle INTEGER,
    slug TEXT UNIQUE,
    title TEXT NOT NULL,
    family TEXT,
    rationale TEXT,
    spec_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',   -- proposed | rejected | building | testing | scrap | candidate | good
    bucket TEXT,
    critic_verdict TEXT,
    critic_notes TEXT,
    strategy_path TEXT,
    report_path TEXT,
    lesson TEXT
);
CREATE TABLE IF NOT EXISTS trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    hypothesis_id INTEGER,
    stage TEXT,
    strategy TEXT,
    sym TEXT,
    tf TEXT,
    params_json TEXT,
    n INTEGER,
    avg_r REAL,
    t REAL,
    design_t REAL,
    check_avg_r REAL,
    holdout_avg_r REAL,
    passes_bar INTEGER,
    stats_json TEXT,
    FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(id)
);
CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    hypothesis_id INTEGER,
    actor TEXT,          -- director | critic | engine
    verdict TEXT,
    notes TEXT,
    FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(id)
);
CREATE TABLE IF NOT EXISTS holdout_touches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    hypothesis_id INTEGER,
    note TEXT
);
CREATE TABLE IF NOT EXISTS spend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    cycle INTEGER,
    role TEXT,
    model TEXT,
    input_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_write_tokens INTEGER,
    output_tokens INTEGER,
    usd REAL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ResearchState:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ---- hypotheses
    def add_hypothesis(self, slug: str, title: str, family: str, rationale: str, spec: dict, cycle: int | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO hypotheses(created, cycle, slug, title, family, rationale, spec_json) VALUES (?,?,?,?,?,?,?)",
            (_now(), cycle, slug, title, family, rationale, json.dumps(spec)))
        self.conn.commit()
        return int(cur.lastrowid)

    def update_hypothesis(self, hid: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE hypotheses SET {cols} WHERE id = ?", (*fields.values(), hid))
        self.conn.commit()

    def hypothesis(self, hid: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM hypotheses WHERE id = ?", (hid,)).fetchone()
        return dict(row) if row else None

    def hypotheses(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self.conn.execute("SELECT * FROM hypotheses WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM hypotheses ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ---- trials
    def record_trial(self, hypothesis_id: int | None, stage: str, summary: dict, stats: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO trials(created, hypothesis_id, stage, strategy, sym, tf, params_json, n, avg_r, t, design_t, "
            "check_avg_r, holdout_avg_r, passes_bar, stats_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), hypothesis_id, stage, summary.get("strategy"), summary.get("sym"), summary.get("tf"),
             json.dumps(summary.get("params", {})), summary.get("n"), summary.get("avg_r"), summary.get("t"),
             summary.get("design_t"), summary.get("check_avg_r"), summary.get("holdout_avg_r"),
             int(bool(summary.get("passes_bar"))), json.dumps(stats, default=str)))
        self.conn.commit()
        return int(cur.lastrowid)

    def n_trials(self, hypothesis_id: int | None = None) -> int:
        if hypothesis_id is None:
            return int(self.conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0])
        return int(self.conn.execute("SELECT COUNT(*) FROM trials WHERE hypothesis_id = ?", (hypothesis_id,)).fetchone()[0])

    def trial_sharpe_variance(self) -> float:
        """Variance of per-trial Sharpe-like ratios (avg_r x sqrt(n) / t recovers sd; use t/sqrt(n))."""
        rows = self.conn.execute("SELECT t, n FROM trials WHERE t IS NOT NULL AND n > 2").fetchall()
        srs = [r["t"] / (r["n"] ** 0.5) for r in rows if r["t"] == r["t"]]
        if len(srs) < 2:
            return 0.0
        import statistics
        return float(statistics.pvariance(srs))

    # ---- verdicts and buckets
    def add_verdict(self, hypothesis_id: int, actor: str, verdict: str, notes: str = "") -> None:
        self.conn.execute("INSERT INTO verdicts(created, hypothesis_id, actor, verdict, notes) VALUES (?,?,?,?,?)",
                          (_now(), hypothesis_id, actor, verdict, notes))
        self.conn.commit()

    def touch_holdout(self, hypothesis_id: int, note: str = "") -> None:
        self.conn.execute("INSERT INTO holdout_touches(created, hypothesis_id, note) VALUES (?,?,?)", (_now(), hypothesis_id, note))
        self.conn.commit()

    def n_holdout_touches(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM holdout_touches").fetchone()[0])

    def record_spend(self, cycle: int | None, role: str, model: str, usage: dict, usd: float) -> None:
        self.conn.execute(
            "INSERT INTO spend(created, cycle, role, model, input_tokens, cache_read_tokens, cache_write_tokens, output_tokens, usd) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (_now(), cycle, role, model, usage.get("input_tokens", 0), usage.get("cache_read_input_tokens", 0),
             usage.get("cache_creation_input_tokens", 0), usage.get("output_tokens", 0), usd))
        self.conn.commit()

    def spend_total(self, since: str | None = None) -> float:
        if since:
            row = self.conn.execute("SELECT COALESCE(SUM(usd), 0) FROM spend WHERE created >= ?", (since,)).fetchone()
        else:
            row = self.conn.execute("SELECT COALESCE(SUM(usd), 0) FROM spend").fetchone()
        return float(row[0])

    # ---- summaries for the Director
    def scrap_index(self, limit: int = 400) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, slug, title, family, status, bucket, lesson, critic_verdict FROM hypotheses "
            "WHERE status IN ('scrap', 'rejected') ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def bucket(self, name: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM hypotheses WHERE bucket = ? ORDER BY id", (name,)).fetchall()
        return [dict(r) for r in rows]

    def overview(self) -> dict:
        counts = {r["status"]: r["c"] for r in self.conn.execute("SELECT status, COUNT(*) c FROM hypotheses GROUP BY status")}
        return {"hypotheses": counts, "trials": self.n_trials(), "holdout_touches": self.n_holdout_touches(),
                "spend_usd": round(self.spend_total(), 2)}

    def close(self) -> None:
        self.conn.close()
