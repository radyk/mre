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
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = out_dir / "runs"
    snap_dir = out_dir / "snapshots" / snapshot_id
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
        if log:
            log(f"cleared stale snapshot: {snap_dir}")
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
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

    def list_schedules(self, include_scenarios: bool = False) -> list[dict]:
        """Default listing NEVER includes what-if scenarios — the evidence-
        isolation rule (docs/01 §8) extended to the API surface."""
        q = "SELECT * FROM schedules"
        if not include_scenarios:
            q += " WHERE is_scenario=0"
        q += " ORDER BY created_at"
        with self._conn() as con:
            rows = con.execute(q).fetchall()
        return [dict(r) for r in rows]
