"""Run/schedule/submission registry — SQLite index over filesystem truth.

The filesystem stores (snapshots, evidence JSONL, certificates, schedule
documents) remain the artifact truth; SQLite is only the INDEX for listing
and status lookup. Nothing here parses evidence or entities.

Run-scoped outputs are enforced structurally: every API-triggered run gets
its own ``<data_root>/runs/<run_id>/`` directory minted by ``create_run``,
so artifacts from one run can never shadow another's. ``prepare_out_dir``
is the single owner of output-directory preparation — the CLI
(``python -m mre``) routes through the same function.

No FastAPI imports here; the CLI may import this module.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from mre.modules import longpath

UTC = timezone.utc

_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    dir           TEXT NOT NULL,
    source        TEXT
);
CREATE TABLE IF NOT EXISTS certificates (
    submission_id TEXT PRIMARY KEY REFERENCES submissions(id),
    grade         TEXT NOT NULL,
    costing_grade TEXT NOT NULL,
    json_path     TEXT NOT NULL,
    md_path       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,            -- solve | whatif
    submission_id TEXT REFERENCES submissions(id),
    base_run_id   TEXT,                     -- whatif: run of the base schedule
    snapshot_id   TEXT NOT NULL,
    status        TEXT NOT NULL,            -- running | succeeded | failed
    out_dir       TEXT NOT NULL,
    params_json   TEXT,
    result_json   TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    finished_at   TEXT
);
CREATE TABLE IF NOT EXISTS schedules (
    id                 TEXT PRIMARY KEY,
    run_id             TEXT NOT NULL REFERENCES runs(id),
    submission_id      TEXT,
    snapshot_id        TEXT NOT NULL,
    status             TEXT NOT NULL,       -- proposed | published | superseded
    contract_version   TEXT NOT NULL,
    is_scenario        INTEGER NOT NULL DEFAULT 0,
    parent_schedule_id TEXT,
    document_path      TEXT NOT NULL,
    created_at         TEXT NOT NULL
);
-- Solution pools live in their OWN tables, never in schedules: pool members
-- can therefore never appear in any schedule listing (the scenario
-- isolation rule, made structural).
CREATE TABLE IF NOT EXISTS pools (
    id            TEXT PRIMARY KEY,
    schedule_id   TEXT NOT NULL REFERENCES schedules(id),
    status        TEXT NOT NULL,            -- warming | ready | empty | failed | invalidated
    kind          TEXT NOT NULL DEFAULT 'pool',  -- 'pool' | 'alternatives' (R-T1a)
    params_json   TEXT,
    summary_json  TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    finished_at   TEXT
);
-- ``source`` distinguishes the two Tier-1 ghost sources (R-T1a): 'pool'
-- (near-optimal, cheap) and 'forced_alternative' (the priced road not taken).
-- ``verdict`` + ``label_json`` carry the forced-alternative first-class info
-- (incl. an infeasible verdict, which has no document — hence the nullable
-- document_path).
CREATE TABLE IF NOT EXISTS pool_members (
    pool_id                TEXT NOT NULL REFERENCES pools(id),
    member_index           INTEGER NOT NULL,
    objective              REAL,
    objective_delta_pct    REAL,
    hamming_from_incumbent INTEGER,
    document_path          TEXT,
    source                 TEXT NOT NULL DEFAULT 'pool',
    verdict                TEXT,
    label_json             TEXT,
    PRIMARY KEY (pool_id, member_index)
);
"""


def prepare_out_dir(
    out_dir: Path | str,
    snapshot_id: str,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[Path, Path]:
    """Prepare a pipeline output directory; returns (out_dir, runs_dir).

    Clears any stale snapshot of the same id and any stale runs/ evidence so
    previous-run records never appear in the new index (the shadowed-artifact
    incident class). Single code path for both the CLI and API-minted run
    directories.
    """
    out_dir = Path(out_dir)
    longpath.makedirs(out_dir)
    runs_dir = out_dir / "runs"
    snap_dir = out_dir / "snapshots" / snapshot_id
    # Snapshot/run dirs nest deep under a chained-edit run; route their existence
    # + clear through the long-path seam so MAX_PATH never bites here (4.0d).
    if longpath.exists(snap_dir):
        longpath.rmtree(snap_dir)
        if log:
            log(f"cleared stale snapshot: {snap_dir}")
    if longpath.exists(runs_dir):
        longpath.rmtree(runs_dir)
        if log:
            log(f"cleared stale runs: {runs_dir}")
    return out_dir, runs_dir


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Registry:
    """SQLite-backed index of submissions, runs, and schedule documents."""

    def __init__(self, data_root: Path | str) -> None:
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        (self.data_root / "submissions").mkdir(exist_ok=True)
        (self.data_root / "runs").mkdir(exist_ok=True)
        self._db_path = self.data_root / "registry.sqlite"
        with self._conn() as con:
            con.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        # One connection per operation: safe across FastAPI background tasks.
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    # ------------------------------------------------------------------
    # Submissions + certificates
    # ------------------------------------------------------------------

    def create_submission(self, source: str = "") -> dict[str, Any]:
        sid = str(uuid.uuid4())
        sub_dir = self.data_root / "submissions" / sid
        (sub_dir / "files").mkdir(parents=True)
        with self._conn() as con:
            con.execute(
                "INSERT INTO submissions (id, created_at, dir, source) VALUES (?,?,?,?)",
                (sid, _now(), str(sub_dir), source),
            )
        return {"id": sid, "dir": sub_dir, "files_dir": sub_dir / "files"}

    def get_submission(self, submission_id: str) -> Optional[dict]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM submissions WHERE id=?", (submission_id,)
            ).fetchone()
        return dict(row) if row else None

    def record_certificate(
        self, submission_id: str, grade: str, costing_grade: str,
        json_path: Path | str, md_path: Path | str,
    ) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO certificates "
                "(submission_id, grade, costing_grade, json_path, md_path, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (submission_id, grade, costing_grade, str(json_path), str(md_path), _now()),
            )

    def get_certificate(self, submission_id: str) -> Optional[dict]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM certificates WHERE submission_id=?", (submission_id,)
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Runs — structural run-dir minting
    # ------------------------------------------------------------------

    def create_run(
        self,
        kind: str,
        submission_id: Optional[str] = None,
        base_run_id: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Mint a run: fresh run_id, its own out_dir, its own snapshot id."""
        run_id = str(uuid.uuid4())
        snapshot_id = f"snap-{run_id[:8]}"
        out_dir, _ = prepare_out_dir(self.data_root / "runs" / run_id, snapshot_id)
        with self._conn() as con:
            con.execute(
                "INSERT INTO runs (id, kind, submission_id, base_run_id, snapshot_id, "
                "status, out_dir, params_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, kind, submission_id, base_run_id, snapshot_id,
                 "running", str(out_dir), json.dumps(params or {}), _now()),
            )
        return {"id": run_id, "snapshot_id": snapshot_id, "out_dir": out_dir}

    def finish_run(
        self,
        run_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE runs SET status=?, result_json=?, error=?, finished_at=? WHERE id=?",
                (status, json.dumps(result or {}), error, _now(), run_id),
            )

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._conn() as con:
            row = con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        run = dict(row)
        run["params"] = json.loads(run.pop("params_json") or "{}")
        run["result"] = json.loads(run.pop("result_json") or "{}")
        return run

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def register_schedule(
        self,
        schedule_id: str,
        run_id: str,
        snapshot_id: str,
        status: str,
        contract_version: str,
        document_path: Path | str,
        submission_id: Optional[str] = None,
        is_scenario: bool = False,
        parent_schedule_id: Optional[str] = None,
    ) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO schedules (id, run_id, submission_id, snapshot_id, status, "
                "contract_version, is_scenario, parent_schedule_id, document_path, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (schedule_id, run_id, submission_id, snapshot_id, status,
                 contract_version, int(is_scenario), parent_schedule_id,
                 str(document_path), _now()),
            )

    def get_schedule(self, schedule_id: str) -> Optional[dict]:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM schedules WHERE id=?", (schedule_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_schedule_meta(self, schedule_id: str) -> Optional[dict]:
        """Registry-level metadata for a schedule, joined to its submission's
        certificate GRADE. The grade is a submission property (it lives in the
        certificate store, not the derived-not-invented schedule document), so
        the cockpit's top strip reads it here rather than from the document."""
        with self._conn() as con:
            row = con.execute(
                "SELECT s.id, s.run_id, s.submission_id, s.snapshot_id, "
                "       s.status, s.contract_version, s.is_scenario, "
                "       s.parent_schedule_id, c.grade, c.costing_grade "
                "FROM schedules s "
                "LEFT JOIN certificates c ON c.submission_id = s.submission_id "
                "WHERE s.id=?",
                (schedule_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_schedules(self, include_scenarios: bool = False) -> list[dict]:
        """Default listing NEVER includes what-if scenarios — the evidence-
        isolation rule (docs/01 §8) extended to the API surface. Pool
        members are excluded structurally: they are never rows here."""
        q = "SELECT * FROM schedules"
        if not include_scenarios:
            q += " WHERE is_scenario=0"
        q += " ORDER BY created_at"
        with self._conn() as con:
            rows = con.execute(q).fetchall()
        return [dict(r) for r in rows]

    def publish_schedule(self, schedule_id: str) -> list[str]:
        """Publish a proposed schedule (docs/07 Phase 3 CU1): proposed →
        published, and supersede its immediate PRIOR version (its
        parent_schedule_id) — invalidating that version's pools/alternatives via
        the existing supersede machinery. The base is only superseded HERE, on an
        explicit publish, never on accept. Returns the ids superseded."""
        superseded: list[str] = []
        with self._conn() as con:
            row = con.execute(
                "SELECT parent_schedule_id FROM schedules WHERE id=?", (schedule_id,)
            ).fetchone()
            con.execute("UPDATE schedules SET status='published' WHERE id=?",
                        (schedule_id,))
            parent = row["parent_schedule_id"] if row else None
            if parent:
                con.execute(
                    "UPDATE schedules SET status='superseded' WHERE id=? "
                    "AND status!='superseded'", (parent,))
                con.execute(
                    "UPDATE pools SET status='invalidated' WHERE schedule_id=?",
                    (parent,))
                superseded.append(parent)
        return superseded

    def live_successor(self, schedule_id: str) -> Optional[str]:
        """The live (non-superseded) descendant that replaced ``schedule_id``,
        or None if there is none (session 3.8 CU3). Publish supersedes a version
        by publishing its child, so the successor is the child whose
        ``parent_schedule_id`` is this id; follow the chain forward past any
        further-superseded links until a live version is reached. A deep link to
        a superseded id uses this to offer "view current" instead of a raw
        error."""
        with self._conn() as con:
            cur = schedule_id
            for _ in range(100):  # cycle guard — the chain is short in practice
                row = con.execute(
                    "SELECT id, status FROM schedules WHERE parent_schedule_id=? "
                    "ORDER BY created_at DESC LIMIT 1", (cur,)).fetchone()
                if row is None:
                    return None
                if row["status"] != "superseded":
                    return row["id"]
                cur = row["id"]
        return None

    def mark_schedule_superseded(self, schedule_id: str) -> None:
        """Supersede a schedule and invalidate its solution pools — a pool
        is keyed to one schedule version; a superseded base makes every
        member's objective delta and placements stale (docs/07 Phase 2)."""
        with self._conn() as con:
            con.execute("UPDATE schedules SET status='superseded' WHERE id=?",
                        (schedule_id,))
            con.execute(
                "UPDATE pools SET status='invalidated' WHERE schedule_id=?",
                (schedule_id,))

    # ------------------------------------------------------------------
    # Solution pools (docs/07 Phase 2)
    # ------------------------------------------------------------------

    def create_pool(self, pool_id: str, schedule_id: str,
                    params: Optional[dict] = None, kind: str = "pool") -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO pools (id, schedule_id, status, kind, params_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (pool_id, schedule_id, "warming", kind, json.dumps(params or {}), _now()),
            )

    def finish_pool(self, pool_id: str, status: str,
                    summary: Optional[dict] = None,
                    members: Optional[list[dict]] = None,
                    error: Optional[str] = None) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE pools SET status=?, summary_json=?, error=?, finished_at=? "
                "WHERE id=?",
                (status, json.dumps(summary or {}, default=str), error, _now(), pool_id),
            )
            for m in members or []:
                con.execute(
                    "INSERT OR REPLACE INTO pool_members (pool_id, member_index, "
                    "objective, objective_delta_pct, hamming_from_incumbent, "
                    "document_path, source, verdict, label_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (pool_id, m["member_index"], m.get("objective"),
                     m.get("objective_delta_pct"), m.get("hamming_from_incumbent"),
                     m.get("document_path"), m.get("source", "pool"),
                     m.get("verdict"),
                     json.dumps(m["label"], default=str) if m.get("label") else None),
                )

    def append_pool_members(self, pool_id: str, members: list[dict]) -> list[int]:
        """Append members to an existing pool WITHOUT clobbering, assigning
        globally-unique member indices after the current max (session 3.3 CU1,
        the on-demand pricing path). Returns the assigned indices. Leaves the
        pool's status/summary untouched — the pool stays 'ready' as fresh ghosts
        for newly-grabbed ops trickle in."""
        assigned: list[int] = []
        with self._conn() as con:
            row = con.execute(
                "SELECT COALESCE(MAX(member_index), -1) AS mx FROM pool_members "
                "WHERE pool_id=?", (pool_id,)).fetchone()
            nxt = int(row["mx"]) + 1
            for m in members:
                idx = nxt + len(assigned)
                con.execute(
                    "INSERT OR REPLACE INTO pool_members (pool_id, member_index, "
                    "objective, objective_delta_pct, hamming_from_incumbent, "
                    "document_path, source, verdict, label_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (pool_id, idx, m.get("objective"),
                     m.get("objective_delta_pct"), m.get("hamming_from_incumbent"),
                     m.get("document_path"), m.get("source", "forced_alternative"),
                     m.get("verdict"),
                     json.dumps(m["label"], default=str) if m.get("label") else None),
                )
                assigned.append(idx)
        return assigned

    def get_pool_for_schedule(self, schedule_id: str,
                              kind: str = "pool") -> Optional[dict]:
        """The schedule's most recent pool of the given kind ('pool' or
        'alternatives'), with its member rows."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM pools WHERE schedule_id=? AND kind=? "
                "ORDER BY created_at DESC LIMIT 1", (schedule_id, kind),
            ).fetchone()
            if row is None:
                return None
            pool = dict(row)
            members = con.execute(
                "SELECT * FROM pool_members WHERE pool_id=? ORDER BY member_index",
                (pool["id"],),
            ).fetchall()
        pool["params"] = json.loads(pool.pop("params_json") or "{}")
        pool["summary"] = json.loads(pool.pop("summary_json") or "{}")
        member_rows = []
        for m in members:
            md = dict(m)
            md["label"] = json.loads(md.pop("label_json")) if md.get("label_json") else None
            member_rows.append(md)
        pool["members"] = member_rows
        return pool
