"""R4.0 recon P2/P4 — the beat-one frame, and the calendar ground truth.

READ-ONLY. Rebuilds beat one's model EXACTLY as ``sandbox.feasibility_ghost``
does (same loads, same ``_restrict_window``, same builder) but writes nothing —
no Reporter, no sandbox dir — so it is safe against a pinned world.

It then answers three things the refusal sentence depends on:

  (1) FRAME. ``feasibility_ghost`` computes ``pin_start_min`` from the
      M5-EVIDENCE ``horizon_start``; ``var_map.cal_windows`` is minutes from the
      builder's OWN computed ``var_map.horizon_start``. If those two instants
      differ, every calendar comparison in ``relaxed_refusal`` is offset and the
      sentence "the machine is not open at that time" can be false.
  (2) GROUND TRUTH. For each probed instant, the calendar's REAL open windows
      for that resource, computed independently from the canonical calendar
      entities — never from ``var_map``.
  (3) THE VERDICT. What ``relaxed_refusal`` actually returns for a nudge ladder
      of +30/+60/+120/+240 minutes off each op's incumbent start, on its OWN
      incumbent machine.

Usage: python tools/spikes/rolling_stack/p2_frame.py [--run <dir>] [--n 5]
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

DEFAULT_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")
NUDGES = (30, 60, 120, 240)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--n", type=int, default=5, help="how many ops to walk")
    ap.add_argument("--no-restrict", action="store_true",
                    help="what the API does for a document with no rolling "
                         "block: restrict_op_ids=None, i.e. the WHOLE PLANT")
    ap.add_argument("--force-ref", default=None,
                    help="ISO date to force as reference_date — isolates the "
                         "LOST-reference_date defect from the LOST-scope one")
    args = ap.parse_args()
    run_dir = Path(args.run)

    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.sandbox import (
        _incumbent_duration_min, _is_chunked, _parse_ref_date, _restrict_window,
    )
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.local_price import relaxed_refusal

    snap_id = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())
    reader = SnapshotStore(run_dir / "snapshots").load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    # exactly what api._rolling_gesture_context hands beat one: the ops the
    # window-0 solve placed (committed ∪ active).
    restrict = (None if args.no_restrict
                else {a["operation_ref"] for a in incumbent_assignments
                      if a.get("operation_ref")})
    ops, wps, fuls, demands = _restrict_window(ops, wps, fuls, demands, restrict)

    evidence = _read_evidence(run_dir / "runs")
    ctx = derive_base_context(run_dir / "runs")
    reference_date = _parse_ref_date(args.force_ref or ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )

    print("=" * 74)
    print("(1) THE FRAME")
    print("=" * 74)
    print(f"  reference_date (run context)      : {reference_date}")
    print(f"  horizon_start (M5 evidence)       : {horizon_start}")
    print(f"  var_map.horizon_start (builder)   : {var_map.horizon_start}")
    delta = (var_map.horizon_start - horizon_start).total_seconds() / 60.0
    print(f"  OFFSET (builder - evidence)       : {delta:+.0f} minutes")
    print(f"  restricted scope                  : {len(ops)} ops "
          f"(restrict={'None (WHOLE PLANT)' if restrict is None else '%d placed' % len(restrict)})")
    cw_all = [w for ws in (var_map.cal_windows or {}).values() for w in ws]
    if cw_all:
        print(f"  var_map window minutes range      : "
              f"{min(w[0] for w in cw_all)} .. {max(w[1] for w in cw_all)}")
        print(f"  a pin inside the board's own window lands at pin_min ~"
              f"{int((horizon_start - horizon_start).total_seconds()//60)}.."
              f"{int((horizon_end - horizon_start).total_seconds()//60)}")
    if abs(delta) > 0:
        print("  >> FRAMES DISAGREE: pin_start_min and cal_windows are measured")
        print("     from DIFFERENT origins. Every calendar check is offset.")
    else:
        print("  >> frames agree; the origin is not the defect on this board.")

    # --- ground truth: the real calendar windows, from the canonical entities
    print()
    print("=" * 74)
    print("(2)+(3) THE WALK — ground truth vs relaxed_refusal")
    print("=" * 74)

    from datetime import datetime as _dtc

    res_by_id = {r["id"]: r for r in resources}
    cal_by_id = {c.get("id"): c for c in flattened_cals}

    def truth_windows(rid):
        """The resource's REAL open windows as datetimes, independent of
        var_map: read from the flattened canonical calendars' OWN key,
        ``horizon_resolved`` (calendar_utils.flatten_all_calendars).

        Raises rather than returning [] when the calendar cannot be resolved —
        an empty ground truth would silently make every refusal look correct,
        which is the (d.2) 'zero from a blind instrument' failure this probe
        exists to avoid."""
        r = res_by_id.get(rid) or {}
        cal_ref = r.get("calendar_ref")
        cal = cal_by_id.get(cal_ref)
        if cal is None:
            raise RuntimeError(
                f"no calendar for resource {rid} (calendar_ref={cal_ref!r}); "
                f"known calendars: {sorted(cal_by_id)}")
        hr = cal.get("horizon_resolved")
        if not hr:
            raise RuntimeError(
                f"calendar {cal_ref} has no horizon_resolved windows")
        return [(_dtc.fromisoformat(w["start"]), _dtc.fromisoformat(w["end"]))
                for w in hr]

    walked = 0
    rows = []
    for op_id, (rid, inc_start) in incumbent_placement.items():
        if walked >= args.n:
            break
        asg = next((a for a in incumbent_assignments
                    if a.get("operation_ref") == op_id), None)
        dur = _incumbent_duration_min(asg)
        if not dur:
            continue
        walked += 1
        chunked = _is_chunked(incumbent_assignments, op_id)
        print(f"\n  op {op_id[:12]}  machine {rid[:12]}  "
              f"incumbent start {inc_start}  dur {dur}min  chunked={chunked}")
        tw = truth_windows(rid)
        vw = (var_map.cal_windows or {}).get(rid) or []
        print(f"    canonical open windows for this machine : {len(tw)}")
        print(f"    var_map.cal_windows entries             : {len(vw)}")
        if not vw:
            print("    >> var_map has NO windows for this machine: every instant")
            print("       will read 'not open'. A default that ASSERTS.")
        for nudge in (0,) + NUDGES:
            at = inc_start + timedelta(minutes=nudge)
            pin_min = int((at - horizon_start).total_seconds() // 60)
            r = relaxed_refusal(var_map, op_id, rid, pin_min, pin_min + dur,
                                chunked=chunked)
            # independent ground truth on the SAME instant
            open_now = any(ws <= at < we for ws, we in tw)
            fits = any(ws <= at and at + timedelta(minutes=dur) <= we
                       for ws, we in tw)
            verdict = "(no refusal)" if r is None else f"{r.family}: {r.sentence}"
            flag = ""
            if r is not None and "not open at that time" in (r.sentence or "") \
                    and open_now:
                flag = "   <<< FALSE: the calendar IS open at that instant"
            rows.append((op_id, nudge, verdict, open_now, fits, flag != ""))
            print(f"    +{nudge:4}min  {str(at)[:19]}  pin_min={pin_min:6}  "
                  f"truth[open={open_now!s:5} fits={fits!s:5}]  "
                  f"{verdict}{flag}")

    print("\n" + "=" * 74)
    print("SUMMARY")
    print("=" * 74)
    total = len(rows)
    refused = sum(1 for r in rows if r[2] != "(no refusal)")
    false_ones = sum(1 for r in rows if r[5])
    print(f"  probes                                  : {total}")
    print(f"  refused by relaxed_refusal              : {refused}")
    print(f"  refusals that are FALSE of the calendar : {false_ones}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
