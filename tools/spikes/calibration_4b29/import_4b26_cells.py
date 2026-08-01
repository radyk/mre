"""Import 4B.26's measured rows as calibration cells (Session 4B.29 Item 3).

R-CAL1 rule (1) says a profile's grid is SOLVER OUTPUT, never authored. It does
not say the solver has to run today. 4B.26's rows were produced by the same
instrument (``solve_rolling_portfolio``), at the same coefficients, against the
same two submissions, in deterministic mode — re-running them would reproduce
them to the cent and cost four hours. So they are IMPORTED, and every imported
cell carries ``source`` naming where it came from. Rule (1) forbids anonymity,
not re-use.

    python tools/spikes/calibration_4b29/import_4b26_cells.py

Writes cells into the two ceremony out-dirs, append-only, exactly as the
ceremony itself would.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "src"))

SWEEP = REPO / "tools" / "spikes" / "portfolio_4b25" / "sweep.jsonl"
MEAS = REPO / "tools" / "spikes" / "portfolio_4b25" / "measurements.jsonl"

OUT_DEMO = REPO / "_4b29_scratch" / "demo"
OUT_MID = REPO / "_4b29_scratch" / "mid170"

# arm label -> (out dir, window_days, frozen_days, det_total)
ARMS = {
    "demo-6.0": (OUT_DEMO, 10, 1, 6.0),
    "demo-10.0": (OUT_DEMO, 10, 1, 10.0),
    "demo-15.0": (OUT_DEMO, 10, 1, 15.0),
    "mid170-w14-6.0": (OUT_MID, 14, 1, 6.0),
    "mid170-w10-6.0": (OUT_MID, 10, 1, 6.0),
}


def _cells_from_block(block, out, w, fz, det, source):
    from mre.contracts.calibration import CalibrationCell

    for m in block["members"]:
        yield out, CalibrationCell(
            window_days=w, frozen_days=fz, det_total=det, seed=m["seed"],
            status=m.get("status") or "",
            ledger_total=m.get("ledger_total"),
            det_consumed=m.get("det_consumed"),
            wall_time_s=m.get("wall_time_s"),
            publishable=bool(m.get("selectable")
                             and m.get("ledger_total") is not None),
            reason=m.get("reason") or "",
            measured_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            source=source)


def main() -> int:
    from mre.modules.calibration import append_cell

    n = 0
    for line in SWEEP.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") != "arm" or r["arm"] not in ARMS:
            continue
        out, w, fz, det = ARMS[r["arm"]]
        for o, c in _cells_from_block(r["block"], out, w, fz, det,
                                      f"imported:4B.26 sweep.jsonl {r['arm']}"):
            append_cell(o, c)
            n += 1

    # 4B.25's 3.0-unit demo row, SEQUENTIAL execution (the parallel run of the
    # same seeds carries identical ledgers and identical deterministic times to
    # ten decimal places — 4B.25 §5a.103 — but its walls are contended, and the
    # wall column is half of what a calibration is for).
    for line in MEAS.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") != "portfolio" or r.get("execution") != "sequential":
            continue
        for o, c in _cells_from_block(r["block"], OUT_DEMO, 10, 1, 3.0,
                                      "imported:4B.25 measurements.jsonl "
                                      "demo-3.0 sequential"):
            append_cell(o, c)
            n += 1
    print(f"imported {n} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
