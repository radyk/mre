"""Find which specific WP(s) in [lo, hi] flip the problem to INFEASIBLE.

Run from repo root:  python tools/find_infeasible_wp.py [lo] [hi]
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

LO = int(sys.argv[1]) if len(sys.argv) > 1 else 1805
HI = int(sys.argv[2]) if len(sys.argv) > 2 else 1810

from datetime import datetime, timedelta, timezone
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import SolverBuilder, _td_to_minutes, _parse_td
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
snap = "snap-run"
reader = store.load_snapshot(snap)

all_wps  = list(reader.iter_entities("workpackage"))
all_ops  = {op["id"]: op for op in reader.iter_entities("operation")}
all_fuls = list(reader.iter_entities("fulfillment"))
all_demands = list(reader.iter_entities("demand"))
resources   = list(reader.iter_entities("resource"))
pools       = list(reader.iter_entities("resourcepool"))
all_cals    = list(reader.iter_entities("calendar"))
costmodels  = list(reader.iter_entities("costmodel"))
cost_model  = costmodels[0] if costmodels else {}
all_demands_dict = {d["id"]: d for d in all_demands}
all_wps_dict = {wp["id"]: wp for wp in all_wps}
all_fuls_by_wp = {}
for f in all_fuls:
    all_fuls_by_wp.setdefault(f.get("workpackage_ref"), []).append(f)

# Base set: first LO WPs + all snapshot demands (constant)
def make_admitted_demand_ids(n_wps):
    return {wp["id"] for wp in all_wps[:n_wps]}

def build_and_solve(n_wps, time_limit=3):
    admitted_wp_ids = make_admitted_demand_ids(n_wps)
    wps = all_wps[:n_wps]
    ops = [op for op in all_ops.values() if op.get("workpackage_ref") in admitted_wp_ids]
    fuls = [f for f in all_fuls if f.get("workpackage_ref") in admitted_wp_ids]

    admitted_demand_ids = {f["demand_ref"] for f in fuls if "demand_ref" in f}
    schedulable = [d for d in all_demands if d["id"] in admitted_demand_ids]
    all_earliest = [datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
                    for d in schedulable if d.get("earliest_start")]
    all_due = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
               for d in schedulable if d.get("due")]
    hs = (min(all_earliest) if all_earliest else datetime(2025, 2, 26, tzinfo=UTC)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    he = (max(all_due) if all_due else hs).replace(hour=23, minute=59, second=59) + timedelta(days=14)

    flattened = []
    for cal in all_cals:
        windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
        flat = [{"start": w.start.isoformat(), "end": w.end.isoformat()} for w in windows]
        c2 = dict(cal)
        c2["horizon_resolved"] = flat
        flattened.append(c2)

    builder = SolverBuilder()
    model, var_map = builder.build(
        wps + ops,
        resources + pools,
        flattened,
        fuls + all_demands,  # ALL demands as __main__.py
        [],
        cost_model,
    )

    from ortools.sat.python import cp_model as cp
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    return {
        cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
        cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
    }.get(status, str(status))

# Check if LO is OK (not INFEASIBLE)
status_lo = build_and_solve(LO)
print(f"N={LO}: {status_lo}")

# Add WPs one by one from LO to HI
for n in range(LO + 1, HI + 1):
    status = build_and_solve(n)
    print(f"N={n}: {status}", end="")
    if status == "INFEASIBLE":
        # Found the culprit WP
        wp = all_wps[n - 1]
        wp_id = wp["id"]
        wp_fuls = all_fuls_by_wp.get(wp_id, [])
        demand_id = wp_fuls[0]["demand_ref"] if wp_fuls else None
        d = all_demands_dict.get(demand_id, {}) if demand_id else {}
        wono = next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), "?")
        qty = d.get("quantity", {})
        print(f"  <-- WP #{n}: WO={wono} due={d.get('due', '?')[:10]} qty={qty}")

        # Find ops for this WP and their resources
        ops_for_wp = [op for op in all_ops.values() if op.get("workpackage_ref") == wp_id]
        for op in ops_for_wp:
            setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
            run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
            total = setup + run
            reqs = op.get("resource_requirements", [])
            refs = reqs[0].get("resource_refs", []) if reqs else []
            res_id = refs[0][:40] if refs else "?"
            res_obj = next((r for r in resources if r["id"] == (refs[0] if refs else "")), {})
            res_name = (res_obj.get("external_refs") or [{}])[0].get("value", res_id[:20])
            print(f"    op: total={total}min res={res_name}")
        break
    else:
        print()
