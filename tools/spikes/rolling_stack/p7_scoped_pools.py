"""R4.1 W3 — the two pool builders, scoped, on a scratch copy of gen-3.

R4.0 measured both pool builders against the pinned gen-3 demo board and found
them publishing nothing:

    the alternatives pool   0 of 8 publishable  (all `infeasible_this_horizon`)
    the near-optimal pool   0 of 3, status `empty`

and proved the verdicts wrong by rebuilding the same targets against
``plan_of_record_scope``, where 8 of 8 came back FEASIBLE. This runs the REAL
builders — not a probe reimplementation — now that R-SG1 clause (1) is in
force, and reports what each publishes.

Always runs on a SCRATCH COPY. `_data` is never written.

    python tools/spikes/rolling_stack/p7_scoped_pools.py --work <dir> [--alt-only]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

GEN3_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")
GEN3_SCHED = "rolling-9fdee7aa-ec5"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--run", default=str(GEN3_RUN))
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--alt-only", action="store_true")
    ap.add_argument("--pool-only", action="store_true")
    args = ap.parse_args()

    work = Path(args.work)
    copy = work / "gen3_copy"
    if copy.exists():
        shutil.rmtree(copy)
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(args.run), copy)
    print(f"scratch copy : {copy}")

    snap_id = next(p.name for p in (copy / "snapshots").iterdir() if p.is_dir())
    print(f"snapshot     : {snap_id}")

    # How much narrower is the plan of record than the snapshot? This is the
    # whole of clause (1) in two numbers.
    from mre.modules.sandbox import plan_of_record_scope
    from mre.modules.snapshot_store import SnapshotStore
    reader = SnapshotStore(copy / "snapshots").load_snapshot(snap_id)
    all_ops = sum(1 for _ in reader.iter_entities("operation"))
    scope = plan_of_record_scope(list(reader.iter_entities("assignment")))
    print(f"snapshot ops : {all_ops}")
    print(f"plan of record scope : {len(scope)} ops "
          f"({all_ops - len(scope)} carried by the OLD unscoped rebuild)")
    print()

    if not args.pool_only:
        from mre.modules.forced_alternatives import build_forced_alternatives
        print("=" * 70)
        print(f"THE ALTERNATIVES POOL (budget {args.budget})")
        print("=" * 70)
        res = build_forced_alternatives(
            out_dir=copy, snapshot_id=snap_id, base_schedule_id=GEN3_SCHED,
            run_id="scratch", budget=args.budget,
        )
        pub = 0
        for m in res.members:
            ok = m.verdict == "priced"
            pub += ok
            print(f"  member {m.member_index}  {m.target_operation_ref[:12]}  "
                  f"{m.status:10} {m.verdict:24} "
                  f"{'-> ' + (m.alternative_resource_ref or '')[:12] if ok else ''}"
                  f"{('  delta ' + format(m.objective_delta_pct, '+.3f') + '%') if ok and m.objective_delta_pct is not None else ''}")
        print(f"\n  publishable : {pub} of {len(res.members)}")

    if not args.alt_only:
        from mre.modules.solution_pool import warm_solution_pool
        print()
        print("=" * 70)
        print(f"THE NEAR-OPTIMAL POOL (k={args.k})")
        print("=" * 70)
        pr = warm_solution_pool(
            out_dir=copy, snapshot_id=snap_id, base_schedule_id=GEN3_SCHED,
            run_id="scratch", k=args.k)
        print(f"  status  : {pr.status}")
        print(f"  members : {len(pr.members)}")
        for m in pr.members:
            print(f"    member {m.member_index}  {m.status:10} "
                  f"objective={m.objective}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
