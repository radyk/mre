"""Test if infeasibility disappears when calendar blocking is removed (24/7 resources).

Run from repo root:  python tools/test_no_calendar.py [N]
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1810

from datetime import datetime, timedelta, timezone
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import SolverBuilder

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
reader = store.load_snapshot("snap-run")

all_wps  = list(reader.iter_entities("workpackage"))
all_ops  = list(reader.iter_entities("operation"))
all_fuls = list(reader.iter_entities("fulfillment"))
all_demands = list(reader.iter_entities("demand"))
resources   = list(reader.iter_entities("resource"))
pools       = list(reader.iter_entities("resourcepool"))
all_cals    = list(reader.iter_entities("calendar"))
costmodels  = list(reader.iter_entities("costmodel"))
cost_model  = costmodels[0] if costmodels else {}

admitted_wp_ids = {wp["id"] for wp in all_wps[:N]}
wps  = all_wps[:N]
ops  = [op for op in all_ops  if op.get("workpackage_ref") in admitted_wp_ids]
fuls = [f  for f  in all_fuls if f.get("workpackage_ref") in admitted_wp_ids]

admitted_demand_ids = {f["demand_ref"] for f in fuls if "demand_ref" in f}
schedulable = [d for d in all_demands if d["id"] in admitted_demand_ids]
all_earliest = [datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
                for d in schedulable if d.get("earliest_start")]
all_due = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
           for d in schedulable if d.get("due")]
hs = (min(all_earliest) if all_earliest else datetime(2025, 2, 26, tzinfo=UTC)).replace(
    hour=0, minute=0, second=0, microsecond=0)
he = (max(all_due) if all_due else hs).replace(hour=23, minute=59, second=59) + timedelta(days=14)

# Create 24/7 calendars (no blocking)
no_block_cals = []
for cal in all_cals:
    # One big window covering the whole horizon
    c2 = dict(cal)
    c2["horizon_resolved"] = [
        {"start": hs.isoformat(), "end": he.isoformat()}
    ]
    no_block_cals.append(c2)

print(f"Testing {N} WPs with 24/7 calendars (no blocking)...")
builder = SolverBuilder()
model, var_map = builder.build(
    wps + ops,
    resources + pools,
    no_block_cals,
    fuls + all_demands,
    [],
    cost_model,
)

from ortools.sat.python import cp_model as cp
solver = cp.CpSolver()
solver.parameters.max_time_in_seconds = 10
status = solver.Solve(model)
status_str = {
    cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
    cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
}.get(status, str(status))
print(f"  Status with 24/7: {status_str}  wall_time={solver.WallTime():.2f}s")

# Now test with precedence constraints removed (set all sequences to the same value)
print(f"\nTesting {N} WPs with REAL calendars (should be INFEASIBLE)...")
from mre.modules.calendar_utils import flatten_calendar
real_cals = []
for cal in all_cals:
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    flat = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
    c2 = dict(cal)
    c2["horizon_resolved"] = flat
    real_cals.append(c2)

builder2 = SolverBuilder()
model2, var_map2 = builder2.build(
    wps + ops,
    resources + pools,
    real_cals,
    fuls + all_demands,
    [],
    cost_model,
)
solver2 = cp.CpSolver()
solver2.parameters.max_time_in_seconds = 5
status2 = solver2.Solve(model2)
status_str2 = {
    cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
    cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
}.get(status2, str(status2))
print(f"  Status with real calendars: {status_str2}  wall_time={solver2.WallTime():.2f}s")
