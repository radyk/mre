"""Count operations per resource to find overloaded resources.

Run from repo root:  python tools/check_resource_load.py
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import _td_to_minutes, _parse_td
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc

store = SnapshotStore("mre_output/snapshots")
reader = store.load_snapshot("snap-run")

all_ops  = list(reader.iter_entities("operation"))
all_wps  = {wp["id"]: wp for wp in reader.iter_entities("workpackage")}
resources = {r["id"]: r for r in reader.iter_entities("resource")}
calendars = {c["id"]: c for c in reader.iter_entities("calendar")}

# Compute horizon matching solver builder with ALL demands
all_demands = list(reader.iter_entities("demand"))
starts = [datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC)
          for d in all_demands if d.get("earliest_start")]
ends   = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
          for d in all_demands if d.get("due")]
for wp in all_wps.values():
    if wp.get("earliest_start"):
        starts.append(datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC))

hs = min(starts).replace(hour=0, minute=0, second=0, microsecond=0)
he = max(ends) + timedelta(days=7)
horizon_minutes = int((he - hs).total_seconds() / 60)
print(f"Solver builder horizon: {hs.date()} to {he.date()} ({horizon_minutes} min)")

# Available minutes per resource via calendar
def avail_minutes(rid: str) -> float:
    cal_id = resources[rid].get("calendar_ref")
    if not cal_id or cal_id not in calendars:
        return 0.0
    cal = calendars[cal_id]
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    return sum((w.end - w.start).total_seconds() / 60 for w in windows)

res_avail = {rid: avail_minutes(rid) for rid in resources}
print(f"Total resources: {len(resources)}")
total_avail = sum(res_avail.values())
print(f"Total available minutes across all resources: {total_avail:,.0f}")
print(f"Avg per resource: {total_avail/len(resources):,.0f}")

# Tally operations per resource
res_op_minutes: dict[str, float] = defaultdict(float)
res_op_count:   dict[str, int]   = defaultdict(int)
unassigned_ops = 0
no_reqs_ops = 0

for op in all_ops:
    setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
    run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
    total = setup + run

    reqs = op.get("resource_requirements", [])
    if not reqs:
        no_reqs_ops += 1
        # fallback: goes to ALL resources — count for each but that's misleading
        continue
    for req in reqs:
        mode = req.get("mode", "")
        if mode == "explicit_set":
            refs = req.get("resource_refs") or []
            matched = [r for r in refs if r in resources]
            if matched:
                for rid in matched:
                    res_op_minutes[rid] += total
                    res_op_count[rid]   += 1
            else:
                unassigned_ops += 1
        elif mode == "capability":
            cap = req.get("capability")
            matched = [rid for rid, r in resources.items() if cap in r.get("capabilities", [])]
            if matched:
                for rid in matched:
                    res_op_minutes[rid] += total / len(matched)
                    res_op_count[rid]   += 1
        break  # only first req

print(f"\nOps with no resource_requirements: {no_reqs_ops}")
print(f"Ops with unmatched explicit_set: {unassigned_ops}")

# Top overloaded resources
print("\nTop 20 resources by ops load:")
print(f"{'Resource':<40} {'Demand':>10} {'Avail':>10} {'Load%':>8} {'Ops':>6}")
print("-" * 78)

sorted_by_load = sorted(
    [(rid, res_op_minutes[rid], res_avail[rid], res_op_count[rid])
     for rid in resources],
    key=lambda x: -x[1],
)
for rid, demand, avail, count in sorted_by_load[:20]:
    pct = (demand / avail * 100) if avail > 0 else float("inf")
    flag = " <-- OVERLOADED" if demand > avail else ""
    res_name = resources[rid].get("external_refs", [{}])[0].get("value", rid[:20]) if resources[rid].get("external_refs") else rid[:20]
    print(f"{res_name:<40} {demand:>10.0f} {avail:>10.0f} {pct:>7.0f}% {count:>6}{flag}")

total_demand = sum(res_op_minutes.values())
print(f"\nTotal op-minutes demanded: {total_demand:,.0f}")
print(f"Total op-minutes available: {total_avail:,.0f}")
print(f"Overall load: {total_demand/total_avail*100:.0f}%")
