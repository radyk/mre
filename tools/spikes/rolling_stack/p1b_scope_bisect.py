"""R4.0 recon P1b — WHICH of the rebuild's two frame errors kills it.

READ-ONLY. The rolling window model (``rolling_horizon._build_window``) is built
over a SUBSET — the admitted free ops plus the still-overlapping pinned ops —
inside a window. The alternatives rebuild
(``forced_alternatives._load_alt_context``) builds over the WHOLE snapshot at
the window's recorded horizon. Two candidate frame errors travel together:

  (i)  SCOPE  — 695 operations built where the incumbent only ever placed 386.
  (ii) HORIZON— those extra ops' demands are due beyond the recorded horizon_end.

This bisects them, and in doing so measures the fix shape:

  A. FULL scope,   recorded horizon      (what the product does today)
  B. FULL scope,   horizon stretched to the last due date
  C. PLACED scope, recorded horizon      (the incumbent's own scope)
  D. PLACED scope, recorded horizon, + the forced-alternative cut

If C is feasible and A is not, the defect is SCOPE, and D answers the question
the pool was asked in the first place.

Usage: python tools/spikes/rolling_stack/p1b_scope_bisect.py [--run <dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

DEFAULT_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")


def _dt(s):
    from mre.modules.solution_pool import _parse_dt
    return _parse_dt(s)


def _cell(actx, *, ops, wps, fuls, demands, horizon_end, label,
          target=None, tl=60.0, seed=1234):
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import (
        SolverBuilder, add_forced_alternative_cut, apply_solution_hints,
    )
    t0 = time.monotonic()
    cals = flatten_all_calendars(actx.calendars, actx.horizon_start, horizon_end)
    model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
        wps + ops + actx.edges, actx.resources + actx.pools, cals,
        fuls + demands, actx.constraints, actx.cost_model,
    )
    apply_solution_hints(model, var_map, actx.incumbent_assignments)
    applied = None
    if target:
        applied = add_forced_alternative_cut(
            model, var_map, target, actx.incumbent_placement[target][0])
    res = SolveRunner(time_limit_seconds=tl, num_search_workers=1,
                      random_seed=seed).solve(model, var_map, None)
    print(f"  {label:52} ops={len(ops):4} dem={len(demands):4} "
          f"end={str(horizon_end)[:10]}  status={res.status:11} "
          f"cut={applied!s:5} {time.monotonic()-t0:6.2f}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--time-limit", type=float, default=60.0)
    args = ap.parse_args()
    run_dir = Path(args.run)

    from mre.modules.forced_alternatives import _load_alt_context

    snap_id = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())
    actx = _load_alt_context(run_dir, snap_id, "runs")
    target = json.loads(
        (run_dir / "alternatives" / "alternatives.json").read_text()
    )["members"][0]["target_operation_ref"]

    placed = set(actx.incumbent_placement)
    p_ops = [o for o in actx.ops if o["id"] in placed]
    p_wp_ids = {o["workpackage_ref"] for o in p_ops}
    p_wps = [w for w in actx.wps if w["id"] in p_wp_ids]
    p_fuls = [f for f in actx.fuls if f.get("workpackage_ref") in p_wp_ids]
    p_dem_ids = {f["demand_ref"] for f in p_fuls}
    p_dems = [d for d in actx.demands if d["id"] in p_dem_ids]

    dues = [_dt(d["due"]) for d in actx.demands if d.get("due")]
    last_due = max(d for d in dues if d)

    print(f"run        : {run_dir}")
    print(f"horizon    : {actx.horizon_start} -> {actx.horizon_end}")
    print(f"last due   : {last_due}   ({(last_due - actx.horizon_end).days} days "
          f"past horizon_end)")
    dues_past = [d for d in dues if d and d > actx.horizon_end]
    print(f"demands due PAST the rebuilt horizon_end: {len(dues_past)} / "
          f"{len(dues)}")
    print(f"FULL   scope: {len(actx.ops)} ops / {len(actx.demands)} demands")
    print(f"PLACED scope: {len(p_ops)} ops / {len(p_dems)} demands")
    print(f"target      : {target}\n")

    stretched = (last_due + timedelta(days=14)).replace(
        hour=23, minute=59, second=59)

    print("--- the bisect ---")
    a = _cell(actx, ops=actx.ops, wps=actx.wps, fuls=actx.fuls,
              demands=actx.demands, horizon_end=actx.horizon_end,
              label="A. FULL scope,   recorded horizon  (TODAY)",
              tl=args.time_limit)
    b = _cell(actx, ops=actx.ops, wps=actx.wps, fuls=actx.fuls,
              demands=actx.demands, horizon_end=stretched,
              label="B. FULL scope,   horizon -> last due + 14d",
              tl=args.time_limit)
    c = _cell(actx, ops=p_ops, wps=p_wps, fuls=p_fuls, demands=p_dems,
              horizon_end=actx.horizon_end,
              label="C. PLACED scope, recorded horizon",
              tl=args.time_limit)
    d = _cell(actx, ops=p_ops, wps=p_wps, fuls=p_fuls, demands=p_dems,
              horizon_end=actx.horizon_end, target=target,
              label="D. PLACED scope, recorded horizon, + THE CUT",
              tl=args.time_limit)

    ok = ("OPTIMAL", "FEASIBLE")
    print("\n--- VERDICT ---")
    print(f"  A {a.status:11} B {b.status:11} C {c.status:11} D {d.status:11}")
    if a.status not in ok and c.status in ok:
        print("  SCOPE is the defect: the incumbent's own scope solves; the")
        print("  whole-snapshot scope does not.")
        if b.status in ok:
            print("  (horizon alone ALSO rescues it — both frames are wrong,")
            print("   scope is the one that matches the incumbent.)")
        else:
            print("  (stretching the horizon alone does NOT rescue it — scope")
            print("   is the load-bearing error.)")
    if d.status in ok:
        print(f"  AND THE ALTERNATIVE IS REAL: D priced at obj={d.objective}")
        print("  — the same target the product called 'infeasible_this_horizon'.")
    elif d.status not in ok and c.status in ok:
        print("  D infeasible on a scope where C is feasible: THIS target's")
        print("  move genuinely has no home. A true infeasible, honestly found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
