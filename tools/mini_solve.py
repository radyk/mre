"""Test solve on first N admitted WorkPackages from the snapshot.

Run from repo root:  python tools/mini_solve.py [N]
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

from datetime import datetime, timedelta, timezone
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import SolverBuilder
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
snap = "snap-run"
reader = store.load_snapshot(snap)

all_wps  = {wp["id"]: wp for wp in reader.iter_entities("workpackage")}
all_ops  = list(reader.iter_entities("operation"))
all_fuls = list(reader.iter_entities("fulfillment"))
all_demands = {d["id"]: d for d in reader.iter_entities("demand")}
resources   = list(reader.iter_entities("resource"))
pools       = list(reader.iter_entities("resourcepool"))
all_cals    = list(reader.iter_entities("calendar"))
costmodels  = list(reader.iter_entities("costmodel"))
cost_model  = costmodels[0] if costmodels else {}

# Take first N workpackages
subset_wp_ids = set(list(all_wps.keys())[:N])
subset_wps  = [wp for wp_id, wp in all_wps.items() if wp_id in subset_wp_ids]
subset_ops  = [op for op in all_ops if op.get("workpackage_ref") in subset_wp_ids]
subset_fuls = [f  for f  in all_fuls if f.get("workpackage_ref") in subset_wp_ids]

demand_ids_in_subset = {f["demand_ref"] for f in subset_fuls if "demand_ref" in f}
subset_demands = [d for d_id, d in all_demands.items() if d_id in demand_ids_in_subset]

print(f"Testing with first {N} workpackages...")
print(f"  ops: {len(subset_ops)}, fuls: {len(subset_fuls)}, demands: {len(subset_demands)}")

# Build horizon from subset demands
all_earliest = [
    datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
    for d in subset_demands if d.get("earliest_start")
]
all_due = [
    datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
    for d in subset_demands if d.get("due")
]
if not all_earliest:
    # fallback: try WP earliest_start
    all_earliest = [
        datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC)
        for wp in subset_wps if wp.get("earliest_start")
    ]

hs = (min(all_earliest) if all_earliest else datetime(2025, 2, 26, tzinfo=UTC)).replace(
    hour=0, minute=0, second=0, microsecond=0)
he = (max(all_due) if all_due else hs + timedelta(days=60)).replace(
    hour=23, minute=59, second=59) + timedelta(days=14)

horizon_minutes = int((he - hs).total_seconds() / 60)
print(f"  horizon: {hs.date()} to {he.date()} ({horizon_minutes} min)")

# Print op durations for the first 10 ops
print(f"  First 5 operations:")
for op in subset_ops[:5]:
    from mre.modules.solver_builder import _td_to_minutes, _parse_td
    setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
    run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
    total = setup + run
    reqs = op.get("resource_requirements", [])
    mode = reqs[0].get("mode") if reqs else "none"
    refs = reqs[0].get("resource_refs", []) if reqs else []
    print(f"    {op['id'][:20]}: setup={setup} run={run} total={total} mode={mode} refs={len(refs)}")

# Flatten calendars for our horizon
flattened = []
for cal in all_cals:
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    flat = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
    c2 = dict(cal)
    c2["horizon_resolved"] = flat
    flattened.append(c2)

# Build model on subset
builder = SolverBuilder()
model, var_map = builder.build(
    subset_wps + subset_ops,
    resources + pools,
    flattened,
    subset_fuls + subset_demands,
    [],
    cost_model,
)

from ortools.sat.python import cp_model as cp
solver = cp.CpSolver()
solver.parameters.max_time_in_seconds = 15
status = solver.Solve(model)
status_str = {
    cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
    cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
}.get(status, str(status))
print(f"  Status: {status_str}  wall_time={solver.WallTime():.2f}s")

if status == cp.INFEASIBLE:
    print("  INFEASIBLE - checking which ops cause issues:")
    res_dict = {r["id"]: r for r in resources}
    for op in subset_ops:
        from mre.modules.solver_builder import _td_to_minutes, _parse_td
        setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
        run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
        total = setup + run
        # Check domain validity
        wp = all_wps.get(op.get("workpackage_ref"), {})
        wp_earliest_min = 0
        if wp.get("earliest_start"):
            es_dt = datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC)
            wp_earliest_min = max(0, int((es_dt - hs).total_seconds() / 60))
        ub = horizon_minutes - total
        if ub < wp_earliest_min:
            reqs = op.get("resource_requirements", [])
            print(f"    DOMAIN EMPTY: op {op['id'][:20]} lb={wp_earliest_min} ub={ub} total={total}")
