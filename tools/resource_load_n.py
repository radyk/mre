"""Check resource load for the first N WPs in snapshot order.

Run from repo root:  python tools/resource_load_n.py [N]
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1806

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solver_builder import _td_to_minutes, _parse_td
from mre.modules.calendar_utils import flatten_calendar

UTC = timezone.utc
store = SnapshotStore("mre_output/snapshots")
reader = store.load_snapshot("snap-run")

all_wps  = list(reader.iter_entities("workpackage"))
all_ops  = list(reader.iter_entities("operation"))
all_fuls = list(reader.iter_entities("fulfillment"))
all_demands = list(reader.iter_entities("demand"))
resources   = {r["id"]: r for r in reader.iter_entities("resource")}
all_cals    = {c["id"]: c for c in reader.iter_entities("calendar")}

# Horizon: solver_builder uses all snapshot demands + all WPs (first N)
admitted_wp_ids = {wp["id"] for wp in all_wps[:N]}
wps_subset = all_wps[:N]
ops_subset  = [op for op in all_ops  if op.get("workpackage_ref") in admitted_wp_ids]
fuls_subset = [f  for f  in all_fuls if f.get("workpackage_ref") in admitted_wp_ids]

# Solver builder horizon uses ALL demands (same as __main__.py behavior)
all_starts = []
for wp in wps_subset:
    if wp.get("earliest_start"):
        all_starts.append(datetime.fromisoformat(wp["earliest_start"][:19]).replace(tzinfo=UTC))
for d in all_demands:
    if d.get("earliest_start"):
        all_starts.append(datetime.fromisoformat(d["earliest_start"][:19]).replace(tzinfo=UTC))
all_due = [datetime.fromisoformat(d["due"][:19]).replace(tzinfo=UTC)
           for d in all_demands if d.get("due")]

hs = min(all_starts).replace(hour=0, minute=0, second=0, microsecond=0)
he = max(all_due) + timedelta(days=7)
horizon_minutes = int((he - hs).total_seconds() / 60)

print(f"N={N} WPs, {len(ops_subset)} ops")
print(f"Solver builder horizon: {hs.date()} to {he.date()} ({horizon_minutes} min)")

# Available minutes per resource
def avail_minutes(rid: str) -> float:
    cal_id = resources[rid].get("calendar_ref")
    if not cal_id or cal_id not in all_cals:
        return float("inf")
    cal = all_cals[cal_id]
    windows = flatten_calendar(cal.get("base_pattern", {}), [], hs, he)
    return sum((w.end - w.start).total_seconds() / 60 for w in windows)

# Tally ops per resource
res_demand: dict[str, float] = defaultdict(float)
res_count:  dict[str, int]   = defaultdict(int)

for op in ops_subset:
    setup = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
    run   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
    total = setup + run
    reqs = op.get("resource_requirements", [])
    if not reqs:
        continue
    req = reqs[0]
    if req.get("mode") == "explicit_set":
        refs = req.get("resource_refs") or []
        matched = [r for r in refs if r in resources]
        for rid in (matched or list(resources.keys())):
            res_demand[rid] += total
            res_count[rid]  += 1
    pass

# Top resources by load
sorted_res = sorted(
    [(rid, res_demand[rid], avail_minutes(rid), res_count[rid]) for rid in resources],
    key=lambda x: -x[1]/x[2] if x[2] > 0 else 0,
)

print(f"\nTop 15 resources by load% (N={N} WPs):")
print(f"{'Resource':<40} {'Demand':>10} {'Avail':>10} {'Load%':>8} {'Ops':>6}")
print("-" * 78)
for rid, demand, avail, count in sorted_res[:15]:
    pct = (demand / avail * 100) if avail > 0 else float("inf")
    flag = " << OVERLOADED" if demand > avail else ""
    ext = resources[rid].get("external_refs") or [{}]
    res_name = ext[0].get("value", rid[:20]) if ext else rid[:20]
    print(f"{res_name:<40} {demand:>10.0f} {avail:>10.0f} {pct:>7.0f}% {count:>6}{flag}")
