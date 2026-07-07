"""Replicate exactly what __main__.py passes to SolverBuilder and test.

Run from repo root:  python tools/replicate_main.py [N_WPs]
N_WPs: limit admitted WPs, 0 = all. Default 0.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

from datetime import datetime, timedelta, timezone
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import SolverBuilder
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
snap = "snap-run"
reader = store.load_snapshot(snap)

# Read everything exactly as __main__.py does
all_demands  = list(reader.iter_entities("demand"))    # ALL snapshot demands (incl. excluded)
fuls         = list(reader.iter_entities("fulfillment"))
wps          = list(reader.iter_entities("workpackage"))
ops          = list(reader.iter_entities("operation"))
resources    = list(reader.iter_entities("resource"))
pools        = list(reader.iter_entities("resourcepool"))
calendars    = list(reader.iter_entities("calendar"))
costmodels   = list(reader.iter_entities("costmodel"))
cost_model   = costmodels[0] if costmodels else {}

# Limit WPs if requested
if N > 0:
    admitted_wp_ids = {wp["id"] for wp in wps[:N]}
    wps  = [wp for wp in wps if wp["id"] in admitted_wp_ids]
    ops  = [op for op in ops if op.get("workpackage_ref") in admitted_wp_ids]
    fuls = [f  for f  in fuls if f.get("workpackage_ref") in admitted_wp_ids]

print(f"WPs: {len(wps)}, ops: {len(ops)}, fuls: {len(fuls)}")
print(f"ALL snapshot demands: {len(all_demands)}")  # includes excluded

# Horizon exactly as __main__.py (from ADMITTED fuls only for schedulable)
admitted_demand_ids = {f["demand_ref"] for f in fuls if "demand_ref" in f}
schedulable = [d for d in all_demands if d["id"] in admitted_demand_ids]
all_earliest = [datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
                for d in schedulable if d.get("earliest_start")]
all_due = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
           for d in schedulable if d.get("due")]
hs = (min(all_earliest) if all_earliest else datetime(2025, 2, 26, tzinfo=UTC)).replace(
    hour=0, minute=0, second=0, microsecond=0)
he = (max(all_due) if all_due else hs).replace(
    hour=23, minute=59, second=59) + timedelta(days=14)

print(f"__main__ horizon: {hs.date()} to {he.date()}")
print(f"  min admitted earliest_start: {min(all_earliest).date() if all_earliest else 'N/A'}")

# Flatten calendars exactly as __main__.py (for admitted horizon)
flattened = []
for cal in calendars:
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    flat = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
    c2 = dict(cal)
    c2["horizon_resolved"] = flat
    flattened.append(c2)

# Pass demand_items = fuls + ALL demands (exactly as __main__.py)
# This is the key difference: ALL demands go in, not just admitted
print(f"\nSolver builder demand_items: {len(fuls)} fuls + {len(all_demands)} all_demands")

builder = SolverBuilder()
model, var_map = builder.build(
    wps + ops,            # work_items (admitted WPs + ops only)
    resources + pools,    # capacity_items
    flattened,            # calendars (pre-flattened for admitted horizon)
    fuls + all_demands,   # demand_items — ALL demands as in __main__.py
    [],                   # constraints
    cost_model,
)

# Check what horizon the solver builder computed
# SolverBuilder._compute_horizon uses both workpackages AND demands
sb_demands_for_horizon = {d["id"]: d for d in fuls + all_demands if "due" in d}
sb_starts = []
sb_wps = {wp["id"]: wp for wp in wps}
for wp in sb_wps.values():
    if wp.get("earliest_start"):
        sb_starts.append(datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC))
for d in sb_demands_for_horizon.values():
    if d.get("earliest_start"):
        sb_starts.append(datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC))
sb_ends = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
           for d in sb_demands_for_horizon.values() if d.get("due")]
sb_hs = min(sb_starts).replace(hour=0, minute=0, second=0, microsecond=0) if sb_starts else hs
sb_he = max(sb_ends) + timedelta(days=7) if sb_ends else hs + timedelta(days=60)
sb_horizon_minutes = int((sb_he - sb_hs).total_seconds() / 60)
print(f"Solver builder computed horizon: {sb_hs.date()} to {sb_he.date()} ({sb_horizon_minutes} min)")

from ortools.sat.python import cp_model as cp
solver = cp.CpSolver()
solver.parameters.max_time_in_seconds = 15
status = solver.Solve(model)
status_str = {
    cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
    cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
}.get(status, str(status))
print(f"\nStatus: {status_str}  wall_time={solver.WallTime():.2f}s")

# If INFEASIBLE, check for domain contradictions using solver_builder's horizon
if status == cp.INFEASIBLE:
    from mre.modules.solver_builder import _td_to_minutes, _parse_td
    print(f"\nLooking for domain contradictions (lb > ub) with sb_horizon={sb_horizon_minutes}:")
    found = 0
    for op in ops:
        setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
        run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
        total = setup + run
        wp_id = op.get("workpackage_ref", "")
        wp = sb_wps.get(wp_id, {})
        wp_earliest_min = 0
        if wp.get("earliest_start"):
            es_dt = datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC)
            wp_earliest_min = max(0, int((es_dt - sb_hs).total_seconds() / 60))
        ub = sb_horizon_minutes - total
        if ub < wp_earliest_min:
            reqs = op.get("resource_requirements", [])
            refs = reqs[0].get("resource_refs", []) if reqs else []
            res_id = refs[0] if refs else "?"
            print(f"  DOMAIN EMPTY: total={total} lb={wp_earliest_min} ub={ub} res={res_id[:20]}")
            found += 1
    if not found:
        print("  No simple domain contradictions found — infeasibility is from constraint propagation")
        print("  (resource calendar + mandatory no-overlap = capacity exceeded)")
