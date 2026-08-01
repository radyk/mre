#!/usr/bin/env python3
"""Session 4B.24 ITEM 1 — MEASURE FIRST. SCRATCH ONLY (nothing in src/ imports it).

The budgets in the R-T2 amendment have to be measured numbers, not liked ones.
Four measurements, on the dense demo board, seeds 42-46:

  (a) beat one's DETERMINISTIC-unit cost to reach a verdict. The shipped 2s wall
      is both marginal (4B.23) and the wrong currency.
  (b) a full window re-solve's units to FIRST SOLUTION and to PLATEAU (the
      incumbent unchanged for N units — N is stated, not implied).
  (c) LOCAL pricing cost: hold every placement, apply the pin, recompute the
      ledger, validate. Expect milliseconds; measure it.
  (d) the observed WALL-PER-UNIT exchange rate, so feel.js's ceiling can be set
      as a CEILING above the deterministic budget rather than as the budget.

Wall times are machine-specific; the DETERMINISTIC time consumed is the
reproducible measure and is recorded beside them (the 4B.6c convention).

    set PYTHONHASHSEED=0
    python tools/spikes/sandbox_4b24/measure.py --part a b c d
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctx import Board, DEMO, PINNED  # noqa: E402

OUT = HERE / "measurements.jsonl"
SEEDS = [42, 43, 44, 45, 46]

# The founder's own gesture, as coordinates on the demo board.
FOUNDER = {"order": "ORD-000057", "op_seq": 30, "shift_min": 240}


def emit(rec: dict) -> None:
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")
    print(json.dumps(rec, default=str))


def bar_of(board, order, op_seq):
    for a in board.assignments():
        if order in (a.get("work_orders") or []) and a.get("op_seq") == op_seq:
            return a
    raise SystemExit(f"no {order} op{op_seq} on {board.schedule_id}")


def gesture(board, spec=FOUNDER):
    bar = bar_of(board, spec["order"], spec["op_seq"])
    s = datetime.fromisoformat(bar["chunks"][0]["start"].replace("Z", "+00:00"))
    return {"pin_op_id": bar["operation_ref"],
            "pin_resource_id": bar["resource_id"],
            "pin_start_iso": (s + timedelta(minutes=spec["shift_min"])).isoformat()}


# ---------------------------------------------------------------------------
# (a) beat one — deterministic units to a verdict
# ---------------------------------------------------------------------------

def part_a(board, det_ceiling=20.0, wall_ceiling=300.0):
    from mre.modules.sandbox import feasibility_ghost
    g = gesture(board)
    for seed in SEEDS:
        t0 = time.monotonic()
        ghost = feasibility_ghost(
            board.out_dir, board.snapshot_id, **g,
            budget_s=wall_ceiling, det_time_s=det_ceiling,
            restrict_op_ids=board.window_op_ids, seed=seed)
        emit({"part": "a", "board": board.schedule_id, "seed": seed,
              "verdict": ghost.verdict, "status": ghost.status,
              "det_consumed": ghost.det_consumed,
              "wall_s": ghost.wall_time_s,
              "wall_truncated": ghost.wall_truncated,
              "total_wall_s": round(time.monotonic() - t0, 3)})


# ---------------------------------------------------------------------------
# (b) the window re-solve — units to first solution, and to plateau
# ---------------------------------------------------------------------------

def part_b(board, det_ceiling=10.0, wall_ceiling=900.0):
    """Build the SAME window model the baseline re-solve builds (via the shipped
    loader), warm-start it from the incumbent, hold the standing commitments, and
    record the deterministic time at EVERY improving solution."""
    from mre.modules.local_price import _load_held_world
    from mre.modules.solver_builder import apply_solution_hints
    from mre.modules import standing_pins as sp
    from mre.modules.snapshot_store import SnapshotStore
    from ortools.sat.python import cp_model as cp

    for seed in SEEDS:
        t_build = time.monotonic()
        world = _load_held_world(board.out_dir, board.snapshot_id, "runs",
                                 board.window_op_ids)
        build_s = round(time.monotonic() - t_build, 3)
        reader = SnapshotStore(board.out_dir / "snapshots").load_snapshot(
            board.snapshot_id)
        incumbent = list(reader.iter_entities("assignment"))
        apply_solution_hints(world.model, world.var_map, incumbent)
        sp.apply_standing_pins(world.model, world.var_map, board.standing_pins,
                               world.horizon_start)

        trace: list[dict] = []

        class _CB(cp.CpSolverSolutionCallback):
            def on_solution_callback(self):
                trace.append({"det": round(self.DeterministicTime(), 4),
                              "wall": round(self.WallTime(), 3),
                              "obj": self.ObjectiveValue()})

        solver = cp.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = seed
        solver.parameters.max_deterministic_time = det_ceiling
        solver.parameters.max_time_in_seconds = wall_ceiling
        t0 = time.monotonic()
        st = solver.Solve(world.model, _CB())
        wall = round(time.monotonic() - t0, 3)
        status = {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
                  cp.INFEASIBLE: "INFEASIBLE"}.get(st, "UNKNOWN")
        det = round(solver.ResponseProto().deterministic_time, 4)
        first = trace[0] if trace else None
        last = trace[-1] if trace else None
        emit({"part": "b", "board": board.schedule_id, "seed": seed,
              "status": status, "det_consumed": det, "wall_s": wall,
              "build_s": build_s, "solutions": len(trace),
              "first_solution_det": (first or {}).get("det"),
              "first_solution_obj": (first or {}).get("obj"),
              "last_improvement_det": (last or {}).get("det"),
              "final_obj": (last or {}).get("obj"),
              "quiet_units_after_last": (None if last is None
                                         else round(det - last["det"], 4)),
              "wall_per_unit": (round(wall / det, 3) if det else None),
              "trace": trace})


# ---------------------------------------------------------------------------
# (c) the local price
# ---------------------------------------------------------------------------

def part_c(board, reps=5):
    from mre.modules.local_price import price_local_move
    g = gesture(board)
    for i in range(reps):
        t0 = time.monotonic()
        res = price_local_move(
            board.out_dir, board.snapshot_id,
            pin_op_id=g["pin_op_id"], pin_resource_id=g["pin_resource_id"],
            pin_start_iso=g["pin_start_iso"],
            restrict_op_ids=board.window_op_ids,
            standing_pins=board.standing_pins, validate=True)
        emit({"part": "c", "board": board.schedule_id, "rep": i,
              "priced": res.priced, "cost_delta_abs": res.cost_delta_abs,
              "affected": len(res.affected_orders),
              "total_before": res.total_before, "total_after": res.total_after,
              "agrees_with_persisted": res.agrees_with_persisted,
              "validation": res.validation.get("status"),
              "validate_wall_s": res.validation.get("wall_time_s"),
              "build_wall_s": res.build_wall_time_s,
              "price_wall_s": res.price_wall_time_s,
              "total_wall_s": round(time.monotonic() - t0, 3)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", nargs="+", default=["a", "b", "c"])
    ap.add_argument("--board", default=DEMO)
    ap.add_argument("--det-ceiling", type=float, default=10.0)
    a = ap.parse_args()
    board = Board(a.board)
    if "a" in a.part:
        part_a(board)
    if "b" in a.part:
        part_b(board, det_ceiling=a.det_ceiling)
    if "c" in a.part:
        part_c(board)


if __name__ == "__main__":
    main()
