"""R4.0 recon P1 — the negative control the alternatives builder never ran.

READ-ONLY against the board's run dir (loads the snapshot, solves in memory,
writes nothing back).

The question: when ``build_forced_alternatives`` rebuilds the base model on a
ROLLING board and gets INFEASIBLE, is that the CUT's doing — or is the rebuilt
model infeasible before any cut is applied?

Three cells, same context, same builder, same solver settings:

  A. NO CUT            — the rebuild alone. If this is INFEASIBLE, the pool's
                         "infeasible_this_horizon" says nothing about the
                         alternative; it is reporting a broken rebuild.
  B. WITH THE CUT      — reproduces what the pool member actually ran.
  C. NO CUT, HINTS OFF — controls for the warm start being the thing that
                         poisons it.

Usage: python tools/spikes/rolling_stack/p1_no_cut_control.py [--run <dir>]
                                                              [--target <op_id>]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

DEFAULT_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")


def _solve(actx, *, target, cut, hints, label, seed=1234, tl=30.0):
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import (
        SolverBuilder, add_forced_alternative_cut, apply_solution_hints,
    )
    t0 = time.monotonic()
    model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
        actx.wps + actx.ops + actx.edges, actx.resources + actx.pools,
        actx.flattened_cals, actx.fuls + actx.demands, actx.constraints,
        actx.cost_model,
    )
    applied = None
    if hints:
        apply_solution_hints(model, var_map, actx.incumbent_assignments)
    if cut:
        forbidden = actx.incumbent_placement[target][0]
        applied = add_forced_alternative_cut(model, var_map, target, forbidden)
    res = SolveRunner(time_limit_seconds=tl, num_search_workers=1,
                      random_seed=seed).solve(model, var_map, None)
    print(f"  {label:34} status={res.status:12} "
          f"obj={res.objective!s:>14}  cut_applied={applied}  "
          f"{time.monotonic()-t0:.2f}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--target", default=None)
    ap.add_argument("--time-limit", type=float, default=30.0)
    args = ap.parse_args()
    run_dir = Path(args.run)

    from mre.modules.forced_alternatives import _load_alt_context

    snap_id = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())
    actx = _load_alt_context(run_dir, snap_id, "runs")

    print(f"run          : {run_dir}")
    print(f"snapshot     : {snap_id}")
    print(f"horizon      : {actx.horizon_start} -> {actx.horizon_end}")
    print(f"operations   : {len(actx.ops)}   placed by incumbent: "
          f"{len(actx.incumbent_placement)}")
    print(f"demands      : {len(actx.demands)}   fulfillments: {len(actx.fuls)}")
    print(f"incumbent obj: {actx.incumbent_objective}")

    target = args.target
    if target is None:
        import json
        alt = json.loads((run_dir / "alternatives" / "alternatives.json").read_text())
        target = alt["members"][0]["target_operation_ref"]
    print(f"target op    : {target}\n")

    print("--- the three cells ---")
    a = _solve(actx, target=target, cut=False, hints=True,
               label="A. NO CUT (hints on)", tl=args.time_limit)
    b = _solve(actx, target=target, cut=True, hints=True,
               label="B. WITH THE CUT (the member)", tl=args.time_limit)
    c = _solve(actx, target=target, cut=False, hints=False,
               label="C. NO CUT, NO HINTS", tl=args.time_limit)

    print("\n--- VERDICT ---")
    if a.status not in ("OPTIMAL", "FEASIBLE"):
        print("  A is INFEASIBLE: the rebuild cannot even reproduce a plan the")
        print("  board already HAS. The cut is not what made B infeasible, and")
        print("  'infeasible_this_horizon' is not a statement about the")
        print("  alternative — it is a broken rebuild reported as a plant fact.")
    else:
        print("  A is solvable — the rebuild is sound and the cut is load-bearing.")
        print(f"  A obj={a.objective}  B={b.status}  C={c.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
