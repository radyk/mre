#!/usr/bin/env python3
"""Session 4B.8 CU5(a) — IS THE 14-DAY 200-ORDER INSTANCE EVEN FEASIBLE?

DIAGNOSIS ONLY. This changes nothing and proposes nothing.

docs/07 §5a.15 records that the shipped 14/3 convention at 200 orders admits 313
free operations and returns UNKNOWN at a deterministic budget of 6.0 AND of 20.0
(wall 509 s), while the same plant at a 7-day window admits 99 and proves OPTIMAL
in 3.08 units. UNKNOWN means CP-SAT neither found a solution nor proved
infeasibility — so "it is slow" and "it is impossible" are STILL BOTH LIVE, and
they are different findings with different owners:

  * FEASIBLE  -> a scale/search finding. The cliff sweep (CU5 b-d) is the subject.
  * INFEASIBLE -> NOT a scale finding at all. It means gravity admitted more work
    than the window can hold: an R-SC2 ADMISSION defect wearing a scale costume,
    and the rest of CU5 is moot.

The budget here is deliberately enormous and is STATED on the row rather than
tuned until something happens.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "spikes" / "tiebreak_4b6c"))

import arm_harness as AH   # noqa: E402

OUT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=200)
    ap.add_argument("--window", type=int, default=14)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--det", type=float, default=400.0,
                    help="deterministic budget — VERY large, once, and stated")
    ap.add_argument("--wall", type=float, default=7200.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default=str(OUT / "feasibility.jsonl"))
    args = ap.parse_args()

    from mre.modules.rolling_horizon import _build_window
    from ortools.sat.python import cp_model as cp

    plant = AH.build_plant(args.orders)
    win = AH.window_inputs(plant, window_days=args.window)
    free_ops = win["free_ops"]
    print(f"[world] orders={args.orders} w={args.window} "
          f"free_ops={len(free_ops)}", flush=True)

    t_b = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    build_s = time.perf_counter() - t_b
    print(f"[build] {build_s:.1f}s", flush=True)

    free_start_vars = []
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            free_start_vars.append(v)
    model.minimize(sum(var_map.objective_terms))

    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = args.wall
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.seed
    solver.parameters.max_deterministic_time = args.det
    solver.parameters.log_search_progress = False
    t = time.perf_counter()
    st = solver.Solve(model)
    wall_s = time.perf_counter() - t
    name = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
            cp.MODEL_INVALID: "MODEL_INVALID"}.get(st, "UNKNOWN")

    row = dict(orders=args.orders, window_days=args.window, seed=args.seed,
               det_budget=args.det, wall_ceiling=args.wall,
               workers=args.workers, n_free_ops=len(free_start_vars),
               build_s=round(build_s, 2), status=name,
               solve_wall_s=round(wall_s, 2),
               det_consumed=AH._det_time(solver),
               objective=(solver.ObjectiveValue() if name in ("OPTIMAL", "FEASIBLE") else None),
               best_bound=(solver.BestObjectiveBound() if name in ("OPTIMAL", "FEASIBLE") else None),
               wall_truncated=(solver.WallTime() >= args.wall - 0.05))
    Path(args.out).open("a", encoding="utf-8").write(json.dumps(row, default=str) + "\n")
    print("[VERDICT] " + json.dumps(row, default=str), flush=True)


if __name__ == "__main__":
    main()
