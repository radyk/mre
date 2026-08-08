"""R4.0 recon P3 — what a rolling board's accept hands its own child.

Drives the REAL accept path in-process on a SCRATCH copy — the same two calls
``api._execute_accept`` makes (``planner_edit.apply_planner_edit`` then
``schedule_assembler.build_document_from_run``) — and reports what the child
document carries versus what its rolling parent carried.

REFUSES to run against the live data root. Every child it mints is named on
stdout so the close-out can list it.

Usage:
  python tools/spikes/rolling_stack/p3_accept_child.py --run <SCRATCH run dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="a SCRATCH copy of a run dir")
    ap.add_argument("--child-out", required=True, help="scratch dir for the child")
    args = ap.parse_args()
    run_dir, child_out = Path(args.run), Path(args.child_out)

    for p in (run_dir, child_out):
        if "_data" in p.resolve().parts:
            print("REFUSING: that path is inside the live data root.")
            return 2

    from mre.modules import longpath, standing_pins as sp
    from mre.modules.planner_edit import apply_planner_edit
    from mre.modules.sandbox import SANDBOX_DET_TIME_S, SANDBOX_SEED
    from mre.modules.scenario import derive_base_context
    from mre.modules.schedule_assembler import build_document_from_run

    parent_doc = json.loads(
        (run_dir / "schedule_document.json").read_text(encoding="utf-8"))
    base_snap = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())

    print("--- THE PARENT ---")
    print(f"  schedule_id        : {parent_doc.get('schedule_id')}")
    print(f"  contract_version   : {parent_doc.get('contract_version')}")
    print(f"  rolling block      : {bool(parent_doc.get('rolling'))}")
    print(f"  solver.calibration : "
          f"{(parent_doc.get('solver') or {}).get('calibration') is not None}")
    print(f"  reference_date     : {parent_doc.get('reference_date')}")
    print(f"  assignments        : {len(parent_doc.get('assignments') or [])}")

    # a ZERO-MOVE accept: pin the first active single-chunk bar at its OWN place
    bar = None
    for a in parent_doc.get("assignments") or []:
        ch = a.get("chunks") or []
        if a.get("commitment_state") != "committed" and len(ch) == 1 and ch[0].get("start"):
            bar = (a["operation_ref"], a["resource_id"], ch[0]["start"])
            break
    if bar is None:
        print("no editable bar")
        return 1
    op, res, start = bar
    print(f"\n--- THE GESTURE (zero-move) ---\n  op {op} on {res} @ {start}")

    child_out.mkdir(parents=True, exist_ok=True)
    longpath.copytree(run_dir / "snapshots" / base_snap,
                      child_out / "snapshots" / base_snap)
    # NOTE: the API walks to the ROOT run here (app.py:1588) precisely so the
    # reference date is not lost. On a BASE rolling board root == base, so this
    # single read is the same thing the API would do for this gesture.
    base_ctx = derive_base_context(run_dir / "runs")
    base_ctx["base_runs_dir"] = str(run_dir / "runs")
    print(f"  base_context.reference_date : {base_ctx.get('reference_date')}")

    result = apply_planner_edit(
        out_dir=child_out, base_snapshot_id=base_snap,
        pin_op_id=op, pin_resource_id=res, pin_start_iso=start,
        authority="r4-recon-p3", base_context=base_ctx, budget_s=120.0,
        standing_pins=[], hold_all_placements=True,
        det_time_s=SANDBOX_DET_TIME_S, seed=SANDBOX_SEED,
    )
    doc = build_document_from_run(
        child_out, result.child_snapshot_id, "r4-recon-p3-run",
        runs_subdir="runs", parent_schedule_id=parent_doc.get("schedule_id"),
        standing_pin_ops=sp.standing_pin_ops(
            sp.compose_lineage_pins([], result.pin)),
    )
    d = json.loads(doc.model_dump_json())
    print("\n--- THE CHILD (minted to scratch, NOT registered) ---")
    print(f"  schedule_id        : {d.get('schedule_id')}")
    print(f"  contract_version   : {d.get('contract_version')}")
    print(f"  rolling block      : {bool(d.get('rolling'))}")
    print(f"  solver.calibration : "
          f"{(d.get('solver') or {}).get('calibration') is not None}")
    print(f"  reference_date     : {d.get('reference_date')}")
    print(f"  assignments        : {len(d.get('assignments') or [])}")
    print(f"  moved_count        : {result.moved_count}")

    print("\n--- WHAT THE CHILD'S OWN RUN DIR CAN RECOVER ---")
    ctx2 = derive_base_context(child_out / "runs")
    print(f"  derive_base_context(child/runs) : {ctx2}")
    print(f"  reference_date recoverable      : "
          f"{ctx2.get('reference_date') is not None}")

    print("\n--- VERDICT ---")
    lost = []
    if parent_doc.get("rolling") and not d.get("rolling"):
        lost.append("the rolling block")
    if ((parent_doc.get("solver") or {}).get("calibration") is not None
            and (d.get("solver") or {}).get("calibration") is None):
        lost.append("solver.calibration (R-CAL1)")
    if base_ctx.get("reference_date") and not ctx2.get("reference_date"):
        lost.append("reference_date (recoverable from the child's run dir)")
    if lost:
        print("  THE ACCEPT DROPPED: " + "; ".join(lost))
        print("  A child with no rolling block gets restrict_op_ids=None from")
        print("  api._rolling_gesture_context — so every later gesture on it")
        print("  rebuilds the WHOLE PLANT, not the window.")
    else:
        print("  nothing dropped on this specimen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
