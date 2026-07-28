#!/usr/bin/env python3
"""4B.10 — IS THE COST OBJECTIVE CONSTANT AT alternates=1?

The tardiness counterfactual showed that removing the tardiness price turns an
unprovable instance into a provable one. The tempting explanation was that with
one eligible machine per operation the whole objective is a CONSTANT. That
explanation predicts a near-instant proof, and the FREE arm took 4.72
deterministic units — so it is at best incomplete.

This settles it WITHOUT a theory: take two DIFFERENT feasible solutions of the
same model and evaluate `sum(objective_terms)` at each.

  * if the two values are equal, the objective really is constant and the
    difficulty is elsewhere;
  * if they differ, something other than tardiness varies with placement, and
    the "constant + tardiness" decomposition is wrong.

It also reports the size of every eligible set, so "the assignment is forced" is
checked rather than assumed.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import density_sweep as DS      # noqa: E402


def build(plant, win, free_tardiness: bool):
    from mre.modules.rolling_horizon import _build_window
    if free_tardiness:
        cm = dict(plant.cost_model)
        tw = dict(cm.get("tardiness_weights") or {})
        tw["base_weight"] = 0.0
        for k, v in list(tw.items()):
            if isinstance(v, dict):
                tw[k] = {kk: 0.0 for kk in v}
        cm["tardiness_weights"] = tw
        plant.cost_model = cm
    model, vm = _build_window(plant, win["free_ops"], [], win["ref"],
                              win["win_horizon_end"])
    for op in win["free_ops"]:
        v = vm.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
    return model, vm


def first_solution_objective(plant, win, seed, free_tardiness):
    from ortools.sat.python import cp_model as cp
    model, vm = build(plant, win, free_tardiness)
    terms = vm.objective_terms
    model.minimize(0)                       # objective -> constant: any solution
    s = cp.CpSolver()
    s.parameters.max_time_in_seconds = 600
    s.parameters.num_search_workers = 1
    s.parameters.random_seed = seed
    s.parameters.stop_after_first_solution = True
    st = s.Solve(model)
    if st not in (cp.OPTIMAL, cp.FEASIBLE):
        return None, None, vm
    cost = int(s.value(sum(terms))) if terms else 0
    tard = int(s.value(sum(vm.tardiness.values()))) if vm.tardiness else 0
    return cost, tard, vm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=165)
    ap.add_argument("--alternates", type=int, default=1)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    args = ap.parse_args()

    plant = DS.build_plant(args.orders, args.alternates)
    win = DS.window_inputs(plant)
    print(f"orders={args.orders} alternates={args.alternates} "
          f"free_ops={len(win['free_ops'])} machines={len(plant.resources)}")

    # is the assignment actually forced?
    _c, _t, vm = first_solution_objective(plant, win, args.seeds[0], False)
    sizes = Counter(len(v or []) for v in (vm.op_eligible or {}).values())
    print(f"eligible-set sizes: {dict(sizes)}   "
          f"objective_terms={len(vm.objective_terms)}   "
          f"tardiness_vars={len(vm.tardiness)}")

    for free in (False, True):
        label = "TARDINESS FREE " if free else "TARDINESS PRICED"
        vals = []
        for seed in args.seeds:
            p = DS.build_plant(args.orders, args.alternates)
            w = DS.window_inputs(p)
            cost, tard, _ = first_solution_objective(p, w, seed, free)
            vals.append(cost)
            print(f"  {label}  seed={seed}  sum(objective_terms)={cost:,}  "
                  f"sum(tardiness_minutes)={tard:,}")
        uniq = sorted(set(v for v in vals if v is not None))
        print(f"  -> {len(uniq)} distinct objective value(s) across "
              f"{len(vals)} different feasible solutions")
        if len(uniq) == 1:
            print("     CONSTANT: every feasible solution has the same cost.")
        else:
            print(f"     NOT CONSTANT: spread {min(uniq):,} .. {max(uniq):,} "
                  f"({100*(max(uniq)-min(uniq))/min(uniq):.3f}%)")
        print()


if __name__ == "__main__":
    main()
