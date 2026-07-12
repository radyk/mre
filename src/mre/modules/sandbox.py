"""Tier-2 sandbox re-solve under a hard latency budget (docs/07 Phase 3, R-T1c;
elaborates R-DP2).

When the planner drops a bar (R-DP1: the pin is machine + time exactly as
displayed), the what-if sandbox re-solves the model with that ONE op pinned and
its surroundings free — and it must never spin unboundedly. The re-solve runs
under a hard, VISIBLE budget (a design token, initial 15s) with exactly three
honest outcomes:

  (1) VERDICT within budget            → the delta card as designed. A proven
      (verdict)                          OPTIMAL delta, or a proven-INFEASIBLE
                                         return-home with the binding reason.
  (2) FEASIBLE, bound unproven         → the card ships FLAGGED ("≈ delta,
      (feasible_unproven)                bound not proven" — SOLVER_NONOPTIMAL
                                         surfaced in the UI).
  (3) NOTHING within budget            → R-DP2 return-home ("couldn't verify
      (no_verdict)                       this placement in time").

The board is never blocked during the wait. CI acceptance (a standing latency
regression): a pinned re-solve on the demo fixture must return a VERDICT within
budget — so a heavy fixture fails a test before it fails a demo.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# The budget is a DESIGN TOKEN, not a magic constant — feel-iteration owned,
# surfaced in the UI, and the single knob the latency regression is measured
# against (R-T1c). Override per-call for tests / tuning.
SANDBOX_BUDGET_S = 15.0

# A solve given ``time_limit = budget`` stops AT the budget and reports a hair
# over it (thread teardown). "Within budget" means it honored the budget, so a
# small stop-overhead margin is allowed — it is not a second budget.
_BUDGET_STOP_MARGIN_S = 1.0

# The three honest outcomes (R-T1c). String constants so evidence/JSON carry a
# stable vocabulary.
SANDBOX_VERDICT = "verdict"                    # (1) proven within budget
SANDBOX_FEASIBLE_UNPROVEN = "feasible_unproven"  # (2) feasible, bound unproven
SANDBOX_NO_VERDICT = "no_verdict"              # (3) nothing within budget


@dataclass
class SandboxResult:
    outcome: str                 # one of the three SANDBOX_* constants
    status: str                  # raw solver status (OPTIMAL|FEASIBLE|INFEASIBLE|UNKNOWN)
    within_budget: bool          # wall_time_s <= budget_s
    wall_time_s: float
    budget_s: float
    feasible: bool               # a placement exists with the pin held
    objective: Optional[float] = None
    delta_pct: Optional[float] = None      # vs the incumbent objective
    message: str = ""


def classify_sandbox_outcome(status: str, wall_time_s: float,
                             budget_s: float = SANDBOX_BUDGET_S) -> str:
    """Pure classifier — the heart of R-T1c, unit-testable without a solve.

    Maps a solve (status + wall time) to one of the three honest outcomes:

      * OPTIMAL / INFEASIBLE  → VERDICT — the solver PROVED something (an
        optimal delta, or that the pin cannot be honored this horizon). A proof
        that arrives is a verdict even if it landed at the budget edge.
      * FEASIBLE              → FEASIBLE_UNPROVEN when it ran out the budget
        (the common case: a placement exists but optimality is unproven); a
        FEASIBLE that somehow returned INSIDE the budget is still unproven, so
        it is flagged too — only a terminal proof clears the flag.
      * anything else (UNKNOWN / no solution) → NO_VERDICT (return home).

    ``wall_time_s`` / ``budget_s`` decide only ``within_budget`` in the result;
    the OUTCOME is a function of what the solver proved, because a budget-capped
    solve reports UNKNOWN/FEASIBLE precisely when it could not prove more.
    """
    if status in ("OPTIMAL", "INFEASIBLE"):
        return SANDBOX_VERDICT
    if status == "FEASIBLE":
        return SANDBOX_FEASIBLE_UNPROVEN
    return SANDBOX_NO_VERDICT


def sandbox_pin_resolve(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    budget_s: float = SANDBOX_BUDGET_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
) -> SandboxResult:
    """Re-solve with one op pinned to (machine + time), the rest free, under a
    hard `budget_s`. Returns a classified :class:`SandboxResult`.

    Defaults (no pin args) pin the FIRST incumbent op at its own placement —
    the latency FLOOR (a trivially feasible re-solve the solver must confirm
    within budget); the CI regression uses this. A caller may pin any op at any
    (resource, start) to price a real drag (R-DP1 literalness).
    """
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import (
        _incumbent_objective, _m5_horizon, _placements, _read_evidence,
    )
    from mre.reporter import Reporter

    out_dir = Path(out_dir)
    sandbox_dir = out_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    # Resolve the pin: default to the first incumbent op at its own placement.
    if pin_op_id is None:
        pin_op_id = next(iter(incumbent_placement), None)
        if pin_op_id is None:
            raise ValueError("no incumbent placements to pin")
    inc_res, inc_start = incumbent_placement.get(pin_op_id, (None, None))
    if pin_resource_id is None:
        pin_resource_id = inc_res
    pin_start_dt = (_parse_dt(pin_start_iso) if pin_start_iso else inc_start)
    if pin_start_dt is None or pin_resource_id is None:
        raise ValueError(f"cannot resolve a pin for op {pin_op_id}")
    pin_start_min = int((pin_start_dt - horizon_start).total_seconds() // 60)

    workers = 1 if deterministic else ctx.get("solver_workers")
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="sandbox pin re-solve model build",
        config={"horizon_start": horizon_start.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min},
        trigger="sandbox", snapshot_id=snapshot_id, sink_dir=sandbox_dir / "runs",
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    # warm-start from the incumbent, then pin the target (machine + time), R-DP1.
    apply_solution_hints(model, var_map, incumbent_assignments)
    if pin_op_id in var_map.op_start:
        model.add(var_map.op_start[pin_op_id] == pin_start_min)
    lit = var_map.op_assign.get(pin_op_id, {}).get(pin_resource_id)
    if lit is not None:
        model.add(lit == 1)

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="sandbox pin re-solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "random_seed": 0 if deterministic else None,
                "pin_op": pin_op_id},
        trigger="sandbox", snapshot_id=snapshot_id, sink_dir=sandbox_dir / "runs",
    )
    t0 = time.monotonic()
    solve_result = SolveRunner(
        time_limit_seconds=budget_s, num_search_workers=workers,
        random_seed=0 if deterministic else None,
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    r_rep.end(RunStatus.SUCCESS
              if solve_result.status in ("OPTIMAL", "FEASIBLE")
              else RunStatus.PARTIAL)

    outcome = classify_sandbox_outcome(solve_result.status, wall, budget_s)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    delta_pct = None
    if feasible and incumbent_objective and incumbent_objective > 0 and solve_result.objective:
        delta_pct = round((solve_result.objective - incumbent_objective)
                          / incumbent_objective * 100.0, 4)
    message = {
        SANDBOX_VERDICT: ("optimal delta proven" if feasible
                          else "pin infeasible this horizon"),
        SANDBOX_FEASIBLE_UNPROVEN: "≈ delta, bound not proven",
        SANDBOX_NO_VERDICT: "couldn't verify this placement in time",
    }[outcome]
    return SandboxResult(
        outcome=outcome, status=solve_result.status,
        within_budget=wall <= budget_s + _BUDGET_STOP_MARGIN_S,
        wall_time_s=wall, budget_s=budget_s,
        feasible=feasible, objective=solve_result.objective,
        delta_pct=delta_pct, message=message,
    )


def _parse_dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
