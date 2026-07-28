#!/usr/bin/env python3
"""Session 4B.8 CU5(a) — SATISFIABILITY, asked properly.

DIAGNOSIS ONLY.

The first probe (feasibility_probe.py) asked CP-SAT to MINIMIZE COST on the
200-order / 14-day window under a huge budget. That conflates two questions, and
only one of them is CU5(a)'s:

    "does a feasible schedule EXIST?"        <- the question
    "what is the cheapest feasible schedule?" <- vastly harder, and not asked

UNKNOWN on the optimization tells us nothing about satisfiability, because an
optimizer can burn its whole budget improving bounds on an instance whose first
feasible solution was easy. So this probe DROPS THE OBJECTIVE ENTIRELY and asks
the pure constraint-satisfaction question. A model with no objective either has
a solution (FEASIBLE) or provably does not (INFEASIBLE).

If INFEASIBLE: this is NOT a scale finding. Gravity admitted more work than the
window can hold — an R-SC2 admission defect wearing a scale costume.

BUILD TIME IS REPORTED SEPARATELY from solve time throughout, because the gap
probe found 289 s of model build alone on the monolith and "slow" has so far
never been decomposed into build vs search.
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


def probe(orders, window, seed, wall, workers, first_only):
    from mre.modules.rolling_horizon import _build_window
    from ortools.sat.python import cp_model as cp

    plant = AH.build_plant(orders)
    win = AH.window_inputs(plant, window_days=window)
    free_ops = win["free_ops"]

    t_b = time.perf_counter()
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    n_free = 0
    for op in free_ops:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            n_free += 1
    build_s = time.perf_counter() - t_b

    # ops per machine — the other live hypothesis (a per-machine cliff near 850
    # ops was seen with only 12 resumables), measured from ELIGIBILITY, since a
    # pre-solve model has no assignment yet.
    per_machine = {}
    for op in free_ops:
        for rid in (var_map.op_eligible or {}).get(op["id"], []):
            per_machine[rid] = per_machine.get(rid, 0) + 1
    counts = sorted(per_machine.values(), reverse=True)
    ops_max = counts[0] if counts else 0
    ops_med = counts[len(counts) // 2] if counts else 0

    # THE OBJECTIVE IS DROPPED. This is the satisfiability question, nothing
    # else. `_build_window` leaves minimize(sum(objective_terms)) set.
    assert model.proto.has_objective, (
        "no objective was set — then this probe is not dropping anything and "
        "its result would not mean what the docstring says it means")
    # Replacing it with a CONSTANT is equivalent to dropping it and is the
    # spelling this ortools build actually honours: every feasible solution has
    # the same objective value, so the first one found is optimal and the search
    # has nothing to improve. (`proto.clear_objective()` leaves `has_objective`
    # set in this build — checked, not assumed.)
    model.minimize(0)

    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = wall
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = False
    if first_only:
        solver.parameters.stop_after_first_solution = True
    t = time.perf_counter()
    st = solver.Solve(model)
    solve_s = time.perf_counter() - t
    name = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
            cp.MODEL_INVALID: "MODEL_INVALID"}.get(st, "UNKNOWN")

    return dict(orders=orders, window_days=window, seed=seed, workers=workers,
                wall_ceiling=wall, first_solution_only=first_only,
                n_free_ops=n_free, n_machines=len(per_machine),
                ops_per_machine_max=ops_max, ops_per_machine_median=ops_med,
                build_s=round(build_s, 2), solve_s=round(solve_s, 2),
                satisfiable=name, det_consumed=AH._det_time(solver),
                wall_truncated=(solver.WallTime() >= wall - 0.05))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=[200])
    ap.add_argument("--windows", type=int, nargs="+", default=[14])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--wall", type=float, default=900.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--first-only", action="store_true",
                    help="stop at the first feasible solution")
    ap.add_argument("--out", default=str(OUT / "satisfiability.jsonl"))
    args = ap.parse_args()

    for orders in args.orders:
        for w in args.windows:
            row = probe(orders, w, args.seed, args.wall, args.workers,
                        args.first_only)
            Path(args.out).open("a", encoding="utf-8").write(
                json.dumps(row, default=str) + "\n")
            print("[SAT] " + json.dumps(row, default=str), flush=True)


if __name__ == "__main__":
    main()
