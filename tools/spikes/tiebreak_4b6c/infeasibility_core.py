#!/usr/bin/env python3
"""Session 4B.6c — the diagnostic that found what a naive left-shift misses.

KEPT because the technique is reusable and the lesson is load-bearing. The
compressor's first version honoured precedence, calendar containment and
machine sequence, and STILL produced INFEASIBLE schedules on `pilot_scale`.

This script pins every operation to its solved start under an ASSUMPTION
LITERAL (one bool per op, the pin enforced only under it), nudges ONE target
op 15 minutes earlier, and asks CP-SAT for
``sufficient_assumptions_for_infeasibility()``. The core came back as exactly
two machine-adjacent operations — which is how the missing constraint was
identified as the SEQUENCE-DEPENDENT SETUP TRANSITION MATRIX
(``SolverBuilder._add_transition_constraints``, a 15-minute family changeover
on pilot_scale), which is PAIRWISE over every pair that may share a resource,
not only adjacent ones. Any future compressor must carry it.

Measurement only. Not reachable from src/.

    python tools/spikes/tiebreak_4b6c/infeasibility_core.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import arm_harness as H                                    # noqa: E402
from mre.modules.rolling_horizon import _build_window      # noqa: E402
from ortools.sat.python import cp_model as cp              # noqa: E402

ORDERS = 40
TARGET_PREFIX = "a647785d"     # the op whose 15-minute pull went infeasible
NUDGE_MINUTES = 15


def main():
    plant = H.build_plant(ORDERS)
    H._ORDERS_ATTR[id(plant)] = ORDERS
    win = H.window_inputs(plant)
    free_ops = win["free_ops"]
    _, payload = H.run_arm(plant, win, "A0", 42, keep_placements=True)
    sv = payload["sv"]

    target = next((o for o in sv.op_start_minutes if o.startswith(TARGET_PREFIX)), None)
    if target is None:
        print(f"target {TARGET_PREFIX} not placed in this solve — nothing to show")
        return
    print("target", target, sv.op_start_minutes[target], sv.op_end_minutes[target])

    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    assum = {}
    for oid, s in sv.op_start_minutes.items():
        if oid not in var_map.op_start:
            continue
        b = model.new_bool_var(f"pin_{oid}")
        want = s - NUDGE_MINUTES if oid == target else s
        model.add(var_map.op_start[oid] == want).only_enforce_if(b)
        lit = var_map.op_assign.get(oid, {}).get(sv.op_resource[oid])
        if lit is not None:
            model.add(lit == 1).only_enforce_if(b)
        assum[b.index] = oid
    model.clear_objective()
    model.add_assumptions([model.get_bool_var_from_proto_index(i) for i in assum])

    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 300
    status = solver.Solve(model)
    print("status", solver.status_name(status))
    if status == cp.INFEASIBLE:
        core = solver.sufficient_assumptions_for_infeasibility()
        print("core size", len(core))
        for i in core:
            oid = assum.get(i)
            if not oid:
                continue
            print(f"   {oid[:8]}  res {sv.op_resource[oid][:8]}  "
                  f"start {sv.op_start_minutes[oid]}  end {sv.op_end_minutes[oid]}"
                  f"{'   <- TARGET' if oid == target else ''}")


if __name__ == "__main__":
    main()
