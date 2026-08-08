"""R4.0 recon P1c — how many of the pool's 8 "infeasible" targets are real.

READ-ONLY. Re-prices every target in a committed alternatives pool against the
INCUMBENT'S OWN SCOPE (``plan_of_record_scope``) instead of the whole snapshot,
and reports how many of the ``infeasible_this_horizon`` verdicts survive.

R-T2 discipline: this establishes FEASIBILITY only. Members are solved with
``stop_after_first_solution``, so no objective here is a price and none is
reported as one.

Usage: python tools/spikes/rolling_stack/p1c_all_targets.py [--run <dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

DEFAULT_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--time-limit", type=float, default=120.0)
    args = ap.parse_args()
    run_dir = Path(args.run)

    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.forced_alternatives import _eligible_refs, _load_alt_context
    from mre.modules.sandbox import plan_of_record_scope, _restrict_window
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import (
        SolverBuilder, add_forced_alternative_cut, apply_solution_hints,
    )

    snap_id = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())
    actx = _load_alt_context(run_dir, snap_id, "runs")
    pool = json.loads(
        (run_dir / "alternatives" / "alternatives.json").read_text())

    scope = plan_of_record_scope(actx.incumbent_assignments)
    ops, wps, fuls, demands = _restrict_window(
        actx.ops, actx.wps, actx.fuls, actx.demands, scope)
    cals = flatten_all_calendars(actx.calendars, actx.horizon_start,
                                 actx.horizon_end)
    op_by_id = {o["id"]: o for o in actx.ops}

    print(f"run   : {run_dir}")
    print(f"pool  : {pool['pool_id']}  status={pool['status']}  "
          f"members={len(pool['members'])}")
    print(f"scope : {len(ops)} ops (plan of record) vs {len(actx.ops)} in snapshot\n")

    flips = 0
    for m in pool["members"]:
        target = m["target_operation_ref"]
        elig = _eligible_refs(op_by_id.get(target) or {})
        t0 = time.monotonic()
        model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
            wps + ops + actx.edges, actx.resources + actx.pools, cals,
            fuls + demands, actx.constraints, actx.cost_model,
        )
        apply_solution_hints(model, var_map, actx.incumbent_assignments)
        applied = add_forced_alternative_cut(
            model, var_map, target, m["forbidden_resource_ref"])
        res = SolveRunner(time_limit_seconds=args.time_limit,
                          num_search_workers=1, random_seed=1234,
                          stop_after_first_solution=True).solve(model, var_map, None)
        alt_res = res.solve_values.op_resource.get(target) if res.solve_values else None
        feasible = res.status in ("OPTIMAL", "FEASIBLE")
        flips += bool(feasible)
        print(f"  member {m['member_index']}  target {target[:12]}  "
              f"eligible={len(elig)}  cut={applied}\n"
              f"      PRODUCT SAID : {m['status']:11} / {m['verdict']}\n"
              f"      SCOPED SAYS  : {res.status:11} / "
              f"{'FEASIBLE — a real road' if feasible else 'still infeasible'}"
              f"   moved_to={str(alt_res)[:12]}  {time.monotonic()-t0:.1f}s")

    print(f"\n--- VERDICT ---")
    print(f"  the product published : 0 of {len(pool['members'])} publishable")
    print(f"  correctly scoped      : {flips} of {len(pool['members'])} FEASIBLE")
    print("  (feasibility only — stop_after_first_solution, so no price is")
    print("   claimed here; R-T2 forbids pricing a truncated search.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
