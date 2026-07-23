"""M6 — Solve Runner.

Accepts a CP-SAT model and VariableMap, runs the solver with a configured
time limit, streams improving solutions as Evidence Events, and returns a
SolveResult.

RunContext close carries solver telemetry (status, best bound, gap, wall time).
SOLVER_NONOPTIMAL finding emitted when accepted with gap > threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mre.modules.solver_builder import SolveValues, VariableMap


@dataclass
class SolveResult:
    """Plain-value solve result. No ortools types."""
    status: str                   # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    objective: Optional[float]
    best_bound: Optional[float]
    gap: Optional[float]          # (objective - best_bound) / objective
    wall_time: float
    solutions_found: int
    solve_values: SolveValues


class _SolutionCallback:
    """Callback that streams improving solutions as Evidence Events."""

    def __init__(self, var_map: VariableMap, reporter) -> None:
        self._var_map = var_map
        self._reporter = reporter
        self._count = 0
        self._best_obj: Optional[float] = None

    def on_solution_callback(self, solver) -> None:
        self._count += 1
        try:
            obj = solver.ObjectiveValue()
        except Exception:
            obj = 0.0

        if self._reporter is not None:
            from mre.contracts.vocabularies import RecordTier
            self._reporter.record_event(
                status_text=f"improving_solution",
                payload={"solution_number": self._count, "objective": obj},
                tier=RecordTier.SUPPORTING,
                message=f"Improving solution #{self._count}: objective={obj:.2f}",
            )
        self._best_obj = obj


class SolveRunner:
    """Run the CP-SAT solver and collect telemetry."""

    def __init__(
        self,
        time_limit_seconds: float = 60.0,
        nonoptimal_gap_threshold: float = 0.01,
        num_search_workers: Optional[int] = None,
        random_seed: Optional[int] = None,
        deterministic_time: Optional[float] = None,
        stop_after_first_solution: bool = False,
    ) -> None:
        """num_search_workers/random_seed are optional determinism knobs.

        CP-SAT's default parallel search is not reproducible run-to-run when
        the model has tied-cost alternatives (confirmed empirically: two
        stock runs of the sample_data pipeline produce different resource
        assignments for the same proven-optimal total cost). Production
        callers leave these unset (default parallel search, fastest wall
        time). Regression tests that need bit-identical output across runs
        (e.g. tests/test_defaults_reproduce_baseline.py) pin both.
        """
        self._time_limit = time_limit_seconds
        self._gap_threshold = nonoptimal_gap_threshold
        self._num_search_workers = num_search_workers
        self._random_seed = random_seed
        # A DETERMINISTIC-time budget (CP-SAT max_deterministic_time): unlike the
        # wall-clock max_time_in_seconds, a truncated solve under this budget is
        # REPRODUCIBLE run-to-run (with num_search_workers=1 + a fixed seed). The
        # rolling-horizon measurement (Session 4B.2) uses it so a budgeted window
        # solve is a deterministic measurement, not a wall-clock lottery.
        self._deterministic_time = deterministic_time
        # Stop at the FIRST feasible solution (Session 4B.3b, R-T2 beat one): a
        # cheap "is this placement possible at all" verdict — a RELAXATION of the
        # full budgeted solve, never a priced/optimal one. With workers=1 + a fixed
        # seed the first-feasible solution is reproducible. Off by default so every
        # existing caller (the priced/optimal path) is byte-unchanged.
        self._stop_after_first_solution = stop_after_first_solution

    def solve(
        self,
        model,
        var_map: VariableMap,
        reporter=None,
    ) -> SolveResult:
        from ortools.sat.python import cp_model as cp

        solver = cp.CpSolver()
        solver.parameters.max_time_in_seconds = self._time_limit
        solver.parameters.log_search_progress = False
        if self._num_search_workers is not None:
            solver.parameters.num_search_workers = self._num_search_workers
        if self._random_seed is not None:
            solver.parameters.random_seed = self._random_seed
        if self._deterministic_time is not None:
            solver.parameters.max_deterministic_time = self._deterministic_time
        if self._stop_after_first_solution:
            solver.parameters.stop_after_first_solution = True

        # Solution callback for streaming
        class _Cb(cp.CpSolverSolutionCallback):
            def __init__(self_, vm, rep):
                super().__init__()
                self_._inner = _SolutionCallback(vm, rep)

            def on_solution_callback(self_):
                self_._inner.on_solution_callback(self_)
                self_._inner._count_from_cb = getattr(self_._inner, "_count_from_cb", 0) + 1

        cb = _Cb(var_map, reporter)
        status_enum = solver.Solve(model, cb)

        status_map = {
            cp.OPTIMAL:    "OPTIMAL",
            cp.FEASIBLE:   "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE",
            cp.UNKNOWN:    "UNKNOWN",
            cp.MODEL_INVALID: "INFEASIBLE",
        }
        status_str = status_map.get(status_enum, "UNKNOWN")

        wall_time = solver.WallTime()
        obj: Optional[float] = None
        bound: Optional[float] = None
        gap: Optional[float] = None
        solutions_found = solver.NumBranches()  # approximate

        if status_str in ("OPTIMAL", "FEASIBLE"):
            try:
                obj   = solver.ObjectiveValue()
                bound = solver.BestObjectiveBound()
                if obj and abs(obj) > 1e-9:
                    gap = abs(obj - bound) / abs(obj)
                else:
                    gap = 0.0
            except Exception:
                pass

        # Emit SOLVER_NONOPTIMAL finding if gap is large
        if reporter is not None and status_str == "FEASIBLE":
            from mre.contracts.vocabularies import (
                FindingCode, FindingDisposition, FindingSeverity, RecordTier,
            )
            reporter.record_finding(
                code=FindingCode.SOLVER_NONOPTIMAL,
                severity=FindingSeverity.WARNING,
                subjects=[],
                evidence={
                    "status": status_str,
                    "wall_time": wall_time,
                    "gap": gap,
                    "time_limit": self._time_limit,
                },
                disposition=FindingDisposition.PROCEEDED_FLAGGED,
                tier=RecordTier.SUPPORTING,
            )

        # Terminal telemetry event — the schedule-document assembler reads
        # this (status/objective/gap/wall time) from the evidence stream.
        # solution_info is CP-SAT's own description of what produced the
        # returned solution — for warm-started solves it is the
        # hint-acceptance telemetry (e.g. "hint" when the seeded solution
        # was accepted as the incumbent).
        try:
            solution_info = solver.SolutionInfo()
        except Exception:
            solution_info = None
        if reporter is not None:
            from mre.contracts.vocabularies import RecordTier
            reporter.record_event(
                status_text="solve_complete",
                payload={
                    "status": status_str,
                    "objective": obj,
                    "best_bound": bound,
                    "gap": gap,
                    "wall_time_s": wall_time,
                    "solution_info": solution_info,
                },
                tier=RecordTier.SUPPORTING,
                message=(
                    f"Solve complete: status={status_str}, objective={obj}, "
                    f"wall_time={wall_time:.2f}s"
                ),
            )

        # Extract values if feasible
        if status_str in ("OPTIMAL", "FEASIBLE"):
            sv = var_map.extract(solver)
        else:
            sv = SolveValues(
                op_start_minutes={},
                op_end_minutes={},
                op_resource={},
                wp_end_minutes={},
                tardiness_minutes={},
                horizon_start=var_map.horizon_start,
            )

        return SolveResult(
            status=status_str,
            objective=obj,
            best_bound=bound,
            gap=gap,
            wall_time=wall_time,
            solutions_found=int(solutions_found),
            solve_values=sv,
        )
