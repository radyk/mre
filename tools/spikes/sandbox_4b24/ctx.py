#!/usr/bin/env python3
"""Session 4B.24 — shared board context for the sandbox measurements. SCRATCH.

Loads a registered schedule exactly as the API's sandbox endpoints do — the
registry row, the run dir, the rolling gesture context (window op ids +
committed pins) — so every measurement here is taken against the same inputs
`POST /sandbox` would hand `sandbox_pin_resolve`.

Nothing in src/ imports this.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

DATA_ROOT = REPO / "_data"
DEMO = "rolling-c9973708-865"      # dense demo board, 386 bars
PINNED = "rolling-c362baa4-1b0"    # pinned exam world, 56 bars


class Board:
    def __init__(self, schedule_id: str, data_root: Path = DATA_ROOT):
        con = sqlite3.connect(data_root / "registry.sqlite")
        con.row_factory = sqlite3.Row
        row = con.execute("select * from schedules where id = ?",
                          (schedule_id,)).fetchone()
        if row is None:
            raise SystemExit(f"unknown schedule {schedule_id}")
        self.row = dict(row)
        run = con.execute("select * from runs where id = ?",
                          (self.row["run_id"],)).fetchone()
        self.run = dict(run)
        con.close()
        self.schedule_id = schedule_id
        self.out_dir = Path(self.run["out_dir"])
        self.snapshot_id = self.row["snapshot_id"]
        self.doc = json.loads(
            Path(self.row["document_path"]).read_text(encoding="utf-8"))
        self.pins = json.loads(self.row.get("pins_json") or "[]")
        self.window_op_ids, self.committed_pins = self._gesture_context()

    def _gesture_context(self):
        """The API's own ``_rolling_gesture_context``, transcribed."""
        doc = self.doc
        if not doc.get("rolling"):
            return None, []
        window: set = set()
        committed: list[dict] = []
        for a in doc.get("assignments", []):
            oid = a.get("operation_ref")
            if not oid:
                continue
            window.add(oid)
            chunks = a.get("chunks") or []
            if a.get("commitment_state") == "committed" and chunks:
                committed.append({"operation_ref": oid,
                                  "resource_id": a.get("resource_id"),
                                  "start": chunks[0].get("start")})
        return window, committed

    @property
    def standing_pins(self) -> list[dict]:
        return list(self.pins) + list(self.committed_pins)

    def assignments(self) -> list[dict]:
        return self.doc.get("assignments", [])

    def bars_for_order(self, work_order: str) -> list[dict]:
        return [a for a in self.assignments()
                if a.get("work_order") == work_order
                or a.get("order_ref") == work_order]


def summarize(board: Board) -> dict:
    a = board.assignments()
    return {
        "schedule_id": board.schedule_id,
        "bars": len(a),
        "committed": sum(1 for x in a if x.get("commitment_state") == "committed"),
        "window_ops": len(board.window_op_ids or ()),
        "committed_pins": len(board.committed_pins),
        "out_dir": str(board.out_dir),
    }


if __name__ == "__main__":
    for sid in (DEMO, PINNED):
        print(json.dumps(summarize(Board(sid)), indent=2))
