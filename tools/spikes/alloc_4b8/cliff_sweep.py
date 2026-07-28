#!/usr/bin/env python3
"""Session 4B.8 CU5(b)(c)(d) — WHERE IS THE CLIFF, AND IS IT GENERAL?

DIAGNOSIS ONLY. No fix, no fallback, no window rule.

CU5(a) already settled the prior question: the 200-order / 14-day instance IS
SATISFIABLE — with the objective dropped, a solution is found in 4.51 s wall and
0.082 deterministic units, and the model BUILDS in 0.17 s. So this is not an
R-SC2 admission defect and not a build-time problem. The difficulty is entirely
in OPTIMIZING, and the question is where that difficulty turns on.

Per (orders, window depth) this reports:
  * n_free ops admitted, and ops per machine (max and median) — the per-machine
    cliff is a live hypothesis independent of n_free;
  * BUILD time separately from SOLVE time, always;
  * deterministic units to the FIRST solution (a satisfaction probe, objective
    replaced by a constant) — the floor under the optimizer;
  * the status and consumption of the real COST solve at the shipped budget;
  * (d) what the COARSE ZONE says about the same plant at that depth: how many
    demands fall beyond the horizon and how many coarse cells BIND. Narrowing
    the window moves work from fine to coarse rather than discarding it, so this
    is what decides whether narrowing is graceful degradation or a loss.
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
DET_TOTAL = 6.0
WALL = 600.0


def _status_name(cp, st):
    return {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE", cp.UNKNOWN: "UNKNOWN",
            cp.MODEL_INVALID: "MODEL_INVALID"}.get(st, "UNKNOWN")


def build(plant, win):
    from mre.modules.rolling_horizon import _build_window
    t = time.perf_counter()
    model, var_map = _build_window(plant, win["free_ops"], [], win["ref"],
                                   win["win_horizon_end"])
    n = 0
    for op in win["free_ops"]:
        v = var_map.op_start.get(op["id"])
        if v is not None:
            model.add(v >= win["t0_min"])
            n += 1
    return model, var_map, n, time.perf_counter() - t


def run_depth(orders, window, seed, coarse):
    from ortools.sat.python import cp_model as cp

    plant = AH.build_plant(orders)
    win = AH.window_inputs(plant, window_days=window)

    # --- SATISFACTION: how hard is it to find ANY solution? -----------------
    model, var_map, n_free, build_s = build(plant, win)
    per_machine = {}
    for op in win["free_ops"]:
        for rid in (var_map.op_eligible or {}).get(op["id"], []):
            per_machine[rid] = per_machine.get(rid, 0) + 1
    counts = sorted(per_machine.values(), reverse=True)
    model.minimize(0)                      # objective -> constant (see CU5a probe)
    s = cp.CpSolver()
    s.parameters.max_time_in_seconds = WALL
    s.parameters.num_search_workers = 1
    s.parameters.random_seed = seed
    s.parameters.stop_after_first_solution = True
    t = time.perf_counter()
    st = s.Solve(model)
    sat_s = time.perf_counter() - t
    sat_status, sat_det = _status_name(cp, st), AH._det_time(s)

    # --- COST: the real solve, at the shipped budget -------------------------
    model2, var_map2, _n, build2_s = build(plant, win)
    s2 = cp.CpSolver()
    s2.parameters.max_time_in_seconds = WALL
    s2.parameters.num_search_workers = 1
    s2.parameters.random_seed = seed
    s2.parameters.max_deterministic_time = DET_TOTAL
    t = time.perf_counter()
    st2 = s2.Solve(model2)
    cost_s = time.perf_counter() - t
    cost_status = _status_name(cp, st2)
    obj = bound = gap = None
    if cost_status in ("OPTIMAL", "FEASIBLE"):
        obj, bound = s2.ObjectiveValue(), s2.BestObjectiveBound()
        gap = (abs(obj - bound) / abs(obj)) if obj else 0.0

    row = dict(orders=orders, window_days=window, seed=seed,
               n_free_ops=n_free, n_machines=len(per_machine),
               ops_per_machine_max=(counts[0] if counts else 0),
               ops_per_machine_median=(counts[len(counts) // 2] if counts else 0),
               build_s=round(build_s, 2),
               sat_status=sat_status, sat_solve_s=round(sat_s, 2),
               sat_det=sat_det,
               cost_status=cost_status, cost_solve_s=round(cost_s, 2),
               cost_det=AH._det_time(s2), cost_objective=obj,
               cost_bound=bound, cost_gap=gap,
               cost_wall_truncated=(s2.WallTime() >= WALL - 0.05))

    # --- (d) THE COARSE ZONE at this depth -----------------------------------
    if coarse:
        try:
            from mre.modules.coarse_horizon import build_coarse_zone
            from mre.modules.rolling_horizon import build_rolling_view
            view = build_rolling_view(plant, window_days=window, frozen_days=3,
                                      seed=seed, deterministic=True,
                                      persist=False)
            zone = build_coarse_zone(plant, view)
            cells = getattr(zone, "cells", None) or []
            binding = sum(1 for c in cells if getattr(c, "binding", False))
            row.update(beyond_horizon=len(view.beyond_demand_ids),
                       coarse_cells=len(cells), coarse_binding_cells=binding,
                       coarse_status=getattr(zone, "status", None))
        except Exception as exc:   # noqa: BLE001 — diagnostic, never fatal
            row["coarse_error"] = f"{type(exc).__name__}: {exc}"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, nargs="+", default=[200])
    ap.add_argument("--windows", type=int, nargs="+",
                    default=[7, 8, 9, 10, 11, 12, 14])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--coarse", action="store_true")
    ap.add_argument("--out", default=str(OUT / "cliff.jsonl"))
    args = ap.parse_args()

    out_path = Path(args.out)
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["orders"], r["window_days"], r["seed"]))

    for orders in args.orders:
        for w in args.windows:
            if (orders, w, args.seed) in done:
                print(f"[skip] {orders}/{w}", flush=True)
                continue
            row = run_depth(orders, w, args.seed, args.coarse)
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
            print(f"[cliff] o={orders} w={w} free={row['n_free_ops']} "
                  f"opm={row['ops_per_machine_max']}/{row['ops_per_machine_median']} "
                  f"build={row['build_s']}s SAT={row['sat_status']}@{row['sat_det']} "
                  f"COST={row['cost_status']}@{row['cost_det']} "
                  f"gap={row['cost_gap']}", flush=True)


if __name__ == "__main__":
    main()
