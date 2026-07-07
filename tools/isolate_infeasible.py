"""Isolate which WP(s) in range [start, end) cause INFEASIBLE.

Run from repo root:  python tools/isolate_infeasible.py [start] [end]
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

START = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
END   = int(sys.argv[2]) if len(sys.argv) > 2 else 2000

from datetime import datetime, timedelta, timezone
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import SolverBuilder
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
snap = "snap-run"
reader = store.load_snapshot(snap)

all_wps  = list(reader.iter_entities("workpackage"))
all_ops  = list(reader.iter_entities("operation"))
all_fuls = list(reader.iter_entities("fulfillment"))
all_demands = {d["id"]: d for d in reader.iter_entities("demand")}
resources   = list(reader.iter_entities("resource"))
pools       = list(reader.iter_entities("resourcepool"))
all_cals    = list(reader.iter_entities("calendar"))
costmodels  = list(reader.iter_entities("costmodel"))
cost_model  = costmodels[0] if costmodels else {}

# Use ONLY WPs in [START, END)
subset_wps_list = all_wps[START:END]
subset_wp_ids = {wp["id"] for wp in subset_wps_list}
subset_ops  = [op for op in all_ops  if op.get("workpackage_ref") in subset_wp_ids]
subset_fuls = [f  for f  in all_fuls if f.get("workpackage_ref") in subset_wp_ids]
demand_ids  = {f["demand_ref"] for f in subset_fuls if "demand_ref" in f}
subset_demands = [d for d_id, d in all_demands.items() if d_id in demand_ids]

print(f"Testing WPs [{START}, {END}): {len(subset_wps_list)} WPs, {len(subset_ops)} ops")

all_earliest = [datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
                for d in subset_demands if d.get("earliest_start")]
all_due = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
           for d in subset_demands if d.get("due")]
wp_starts = [datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC)
             for wp in subset_wps_list if wp.get("earliest_start")]
all_starts = all_earliest + wp_starts

hs = (min(all_starts) if all_starts else datetime(2025, 3, 3, tzinfo=UTC)).replace(
    hour=0, minute=0, second=0, microsecond=0)
he = (max(all_due) if all_due else hs + timedelta(days=60)).replace(
    hour=23, minute=59, second=59) + timedelta(days=14)
horizon_minutes = int((he - hs).total_seconds() / 60)
print(f"  horizon: {hs.date()} to {he.date()} ({horizon_minutes} min)")

flattened = []
for cal in all_cals:
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    flat = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
    c2 = dict(cal)
    c2["horizon_resolved"] = flat
    flattened.append(c2)

builder = SolverBuilder()
model, var_map = builder.build(
    subset_wps_list + subset_ops,
    resources + pools,
    flattened,
    subset_fuls + subset_demands,
    [],
    cost_model,
)

from ortools.sat.python import cp_model as cp
solver = cp.CpSolver()
solver.parameters.max_time_in_seconds = 5
status = solver.Solve(model)
status_str = {
    cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
    cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
}.get(status, str(status))
print(f"  Status: {status_str}  wall_time={solver.WallTime():.2f}s")

# If INFEASIBLE, find the op with domain contradiction
if status == cp.INFEASIBLE:
    from mre.modules.solver_builder import _td_to_minutes, _parse_td
    res_dict = {r["id"]: r for r in resources}
    # Recompute solver_builder horizon (uses +7, not +14)
    sb_he = (max(all_due) if all_due else hs + timedelta(days=60)) + timedelta(days=7)
    sb_horizon = int((sb_he - hs).total_seconds() / 60)
    print(f"  Solver-builder horizon_minutes: {sb_horizon}")
    for op in subset_ops:
        setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
        run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
        total = setup + run
        wp_id = op.get("workpackage_ref", "")
        wp = next((w for w in subset_wps_list if w["id"] == wp_id), {})
        wp_earliest_min = 0
        if wp.get("earliest_start"):
            es_dt = datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC)
            wp_earliest_min = max(0, int((es_dt - hs).total_seconds() / 60))
        ub = sb_horizon - total
        if ub < wp_earliest_min:
            reqs = op.get("resource_requirements", [])
            refs = reqs[0].get("resource_refs", []) if reqs else []
            res_name = refs[0][:20] if refs else "?"
            print(f"  DOMAIN EMPTY: op setup={setup} run={run} total={total} "
                  f"lb={wp_earliest_min} ub={ub} res={res_name}")
