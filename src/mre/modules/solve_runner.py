"""M6 — Solve Runner.

Accepts a CP-SAT model and VariableMap, runs the solver with a configured
time limit, streams improving solutions as Evidence Events, and returns a
SolveResult.

RunContext close carries solver telemetry (status, best bound, gap, wall time).
SOLVER_NONOPTIMAL finding emitted when accepted with gap > threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    # True when a DETERMINISTIC-budget solve was actually stopped by the
    # wall clock (Errand session, CU2b). ``max_deterministic_time`` is what makes
    # a truncated solve reproducible; ``max_time_in_seconds`` is always set as
    # well, so if the wall limit trips FIRST the result is whatever CP-SAT
    # happened to reach in N seconds of real time on this machine — a lottery
    # wearing a determinism label. Defaults False (no deterministic budget in
    # force ⇒ nothing was claimed).
    wall_truncated: bool = False

    # SESSION 4B.8 CU3 — THE TWO PROOFS, NEVER FUSED.
    #
    # An R-SC3 solve proves two different things. Stage 1 proves a claim about
    # COST ("no cheaper schedule exists"). Stage 2 proves a claim about the
    # TIEBREAK ("no equally-cheap schedule starts earlier"). They are separate
    # claims with separate budgets and they routinely disagree: above ~8 orders
    # stage 1 proves OPTIMAL in a fraction of its budget while stage 2 exhausts
    # its own without closing.
    #
    # ``status`` is STAGE 1's — the cost proof, which is what a planner asking
    # "is this optimal?" means. Before this it was stage 2's, so every rolling
    # board read FEASIBLE over a ledger we could prove OPTIMAL (docs/07 §5a.21).
    # A tiebreak left unproven does not downgrade the cost claim.
    #
    # ``tiebreak_status`` is stage 2's, None when stage 2 did not run at all —
    # in which case ``tiebreak_skipped_reason`` says WHY. A tiebreak that
    # silently did not run is indistinguishable from one that ran and won
    # nothing, so the skip is always recorded rather than inferred from a blank.
    tiebreak_status: Optional[str] = None
    tiebreak_skipped_reason: Optional[str] = None

    # THE INCUMBENT TRAIL (Session W2.1, R-SP1). One entry per improving
    # solution, in the order CP-SAT found them: {"index", "objective",
    # "elapsed_s"}. EMPTY on a solve that found nothing — an empty list, never a
    # manufactured first plan.
    #
    # `objective` is the SCALED SOLVER OBJECTIVE and is not currency (clause 3,
    # and R-DP12 clause (3) behind it). `elapsed_s` is the solver's own reading:
    # a RECORDED fact that varies run to run and is never asserted. Under
    # deterministic law the SEQUENCE of objectives is reproducible, and that is
    # what the guards assert (clause 6).
    incumbent_trail: list = field(default_factory=list)

    # THE FIRST INCUMBENT'S PLACEMENTS (Session W2.2, R-SP1 AMENDMENT 1).
    #
    # ONE snapshot, at the first improving solution only — the amendment's
    # one-snapshot bound is the wall, and a per-incumbent capture loop is
    # exactly what it forbids. None on a solve that found nothing.
    #
    # It is a real ``SolveValues``, taken by ``VariableMap.extract`` — the SAME
    # function that reads the final solution, because that function reads
    # through ``solver.Value(v)`` and a solution callback provides exactly that
    # accessor. So the snapshot invents no field and no second reader can
    # disagree with the first, which is what lets the ledger price it for real
    # rather than approximately.
    first_incumbent_values: Optional[SolveValues] = None

    # The DETERMINISTIC time this solve actually consumed (CP-SAT's own
    # response_proto.deterministic_time), or None if it could not be read.
    # Session 4B.8 CU2 needs it because stage 2's budget is now the REMAINDER of
    # a declared total after stage 1 ran — which is unknowable until stage 1 has
    # run. It is also the only figure that can hold the budget guard honest:
    # "stage 1 + stage 2 <= total" is a claim about consumption, not about limits.
    det_consumed: Optional[float] = None


def _deterministic_time_of(solver) -> Optional[float]:
    """CP-SAT's own deterministic-time reading for a completed solve, or None.

    The accessor has moved across ortools versions, so both spellings are tried
    and a failure returns None rather than raising — a budget split that cannot
    read the meter must fall back to a stated default, never crash a solve. The
    4B.6c spike harness needed the same readback and reached into the response
    proto directly; this is that probe, promoted to the shipped path so the
    figure is available to the guards and to evidence."""
    for getter in (lambda: solver.response_proto.deterministic_time,
                   lambda: solver.ResponseProto().deterministic_time):
        try:
            return float(getter())
        except Exception:  # noqa: BLE001 — version-dependent accessor
            continue
    return None


class _SolutionCallback:
    """Callback that streams improving solutions as Evidence Events AND collects
    them into the R-SP1 incumbent trail.

    THE PER-RECORD PING WAS ALREADY HERE AND WAS NOT A RECORD OF THE SEARCH. One
    ``improving_solution`` Event per incumbent has been emitted since this file
    was written — with no elapsed time, no terminal bound beside it, no
    collection and no reader. Nobody could assemble a story from it, and the
    consequence was that the optimizer's contribution was invisible on every
    surface. The Event stays exactly as it was (evidence is append-only and
    something may yet read it); ``trail`` is the collection it always needed.

    ``elapsed_s`` is the CALLBACK's own ``WallTime()`` — the solver's reading of
    how long it had been searching when it found this plan. Recorded, never
    asserted (clause 6).
    """

    def __init__(self, var_map: VariableMap, reporter) -> None:
        self._var_map = var_map
        self._reporter = reporter
        self._count = 0
        self._best_obj: Optional[float] = None
        self.trail: list[dict] = []
        #: R-SP1 AMENDMENT 1 — the FIRST incumbent's placements, captured once.
        self.first_values: Optional[SolveValues] = None

    def on_solution_callback(self, solver) -> None:
        self._count += 1
        if self._count == 1:
            # ONE snapshot, and it is taken by the production reader. A capture
            # that failed must not kill a solve that is otherwise fine: the
            # money story is decoration on a correct schedule, and its absence
            # is a state the surfaces already render.
            try:
                self.first_values = self._var_map.extract(solver)
            except Exception:  # noqa: BLE001 — a price is never worth a solve
                self.first_values = None
        try:
            obj = solver.ObjectiveValue()
        except Exception:
            obj = 0.0
        # A callback that cannot read its own clock records the plan without the
        # time rather than dropping the plan: the SEQUENCE is the reproducible
        # thing and it must never be lost to a missing accessor.
        try:
            elapsed = float(solver.WallTime())
        except Exception:  # noqa: BLE001 — version-dependent accessor
            elapsed = 0.0
        self.trail.append({"index": self._count, "objective": float(obj),
                           "elapsed_s": elapsed})

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
        defer_progress: bool = False,
    ) -> SolveResult:
        """``defer_progress`` — WHOEVER KNOWS THE SHIPPED PLAN EMITS THE TRAIL.

        Session W2.2, R-SP1 AMENDMENT 1. This runner emits the solve-progress
        records beside its own ``solve_complete``, which was right while the
        trail was objective-space only. It cannot survive pricing: on a
        TWO-STAGE solve the shipped plan is STAGE 2's placements, and stage 1's
        runner has not seen them. Pricing a "final" that is not the plan the
        board publishes would put a number on the screen that no ledger
        anywhere agrees with.

        So ``solve_two_stage`` sets this: the runner captures, and the
        two-stage caller emits once stage 2 has returned. A single-stage caller
        knows the shipped plan immediately and still emits inline.
        """
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
        trail = list(cb._inner.trail)
        first_values = cb._inner.first_values

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
            # R-SP1 — THE TRAIL, BESIDE THE TERMINAL TELEMETRY IT BELONGS TO.
            # This is the MONOLITHIC path's seam. The rolling path emits its own
            # `solve_complete` (this runner is called there with reporter=None)
            # and calls the SAME function beside it — one definition of the
            # records, one per path, which is the shape S-02 used at the gate's
            # two exits. A record written on only one path would be a gap shaped
            # exactly like the one it was built to close.
            #
            # No `window_key`: a monolithic solve has no window to name, and
            # clause (1)'s no-summing rule is about windows that exist.
            if not defer_progress:
                from mre.modules.solve_progress import emit_solve_progress
                emit_solve_progress(
                    reporter, trail=trail, status=status_str,
                    best_bound=bound, gap=gap,
                    det_consumed=_deterministic_time_of(solver),
                    det_budget=self._deterministic_time,
                    window_key=None,
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
            wall_truncated=(self._deterministic_time is not None
                            and wall_time >= self._time_limit - 0.05),
            det_consumed=_deterministic_time_of(solver),
            incumbent_trail=trail,
            first_incumbent_values=first_values,
        )
