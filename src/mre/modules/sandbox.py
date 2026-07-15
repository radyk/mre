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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
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

# A moved op counts as MAJOR — and so earns a "why" clause on the delta card
# (session 3.3 CU3) — only when it shifted at least this far. A design token:
# it keeps the card from annotating twenty one-minute shuffles with reasons,
# leading instead with the displacements a planner actually feels.
MAJOR_MOVE_THRESHOLD_MIN = 60

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
    # The time limit actually handed to the solver for this re-solve (= budget_s
    # in normal operation). Echoed explicitly (session 3.3 CU5) so budget-vs-
    # actual is always inspectable straight from the payload — the "was 60s the
    # limit or the wall time?" question answers itself.
    applied_time_limit_s: float = 0.0
    objective: Optional[float] = None
    delta_pct: Optional[float] = None      # vs the incumbent objective
    delta_abs: Optional[float] = None      # objective_after - objective_before
    message: str = ""
    # The moved-set (R-DP7): every op the pinned re-solve displaced relative to
    # the incumbent, old → new (resource + start). The pinned op itself is
    # flagged (``pinned``) and always present when feasible. Warm-starting keeps
    # this set minimal by construction — the property that makes tracing it
    # tractable (R-DP7 implementation note). The cockpit maps operation_ref →
    # bar to draw the ghost-of-old + motion trace and the delta-card line items.
    moves: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)  # {operation_ref, resource_id, start}

    def summary(self) -> dict:
        return asdict(self)


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
    delta_pct = delta_abs = None
    if feasible and incumbent_objective and solve_result.objective is not None:
        delta_abs = round(solve_result.objective - incumbent_objective, 4)
        if incumbent_objective > 0:
            delta_pct = round(delta_abs / incumbent_objective * 100.0, 4)

    # The moved-set (R-DP7): old → new placement for every displaced op. Read
    # the new placement from the solve values, the old from the incumbent; a
    # move is a resource change or a start shift ≥ 1 min (the differ tolerance).
    moves: list[dict] = []
    if feasible:
        moves = _moved_set(
            solve_result.solve_values, incumbent_placement, horizon_start,
            pin_op_id,
        )
        _annotate_move_reasons(moves, solve_result.solve_values, horizon_start,
                               pin_op_id)
    message = {
        SANDBOX_VERDICT: ("optimal delta proven" if feasible
                          else "pin infeasible this horizon"),
        SANDBOX_FEASIBLE_UNPROVEN: "≈ delta, bound not proven",
        SANDBOX_NO_VERDICT: "couldn't verify this placement in time",
    }[outcome]
    return SandboxResult(
        outcome=outcome, status=solve_result.status,
        within_budget=wall <= budget_s + _BUDGET_STOP_MARGIN_S,
        wall_time_s=wall, budget_s=budget_s, applied_time_limit_s=budget_s,
        feasible=feasible, objective=solve_result.objective,
        delta_pct=delta_pct, delta_abs=delta_abs, message=message, moves=moves,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
    )


def _moved_set(
    solve_values,
    incumbent_placement: dict[str, tuple],
    horizon_start: datetime,
    pin_op_id: str,
    tolerance_min: int = 1,
) -> list[dict]:
    """Compare the re-solve's placements to the incumbent, op by op, and emit
    the displaced set old → new. The pinned op is always included (flagged) so
    the tentative bar is part of the traced change even when only its neighbours
    truly moved. Sorted: pinned first, then largest start shift, so the delta
    card's line items lead with the biggest displacements (R-DP7c)."""
    def _new_placement(op_id: str):
        rid = solve_values.op_resource.get(op_id)
        smin = solve_values.op_start_minutes.get(op_id)
        if rid is None or smin is None:
            return None
        return rid, horizon_start + timedelta(minutes=smin)

    moves: list[dict] = []
    for op_id, (old_rid, old_start) in incumbent_placement.items():
        new = _new_placement(op_id)
        if new is None:
            continue
        new_rid, new_start = new
        start_delta = round((new_start - old_start).total_seconds() / 60.0)
        changed = (new_rid != old_rid) or (abs(start_delta) >= tolerance_min)
        is_pin = op_id == pin_op_id
        if not changed and not is_pin:
            continue
        moves.append({
            "operation_ref": op_id,
            "from_resource": old_rid, "to_resource": new_rid,
            "from_start": old_start.isoformat(), "to_start": new_start.isoformat(),
            "start_delta_min": start_delta,
            "resource_changed": new_rid != old_rid,
            "pinned": is_pin,
        })
    moves.sort(key=lambda m: (not m["pinned"], -abs(m["start_delta_min"])))
    return moves


def _annotate_move_reasons(
    moves: list[dict],
    solve_values,
    horizon_start: datetime,
    pin_op_id: str,
    threshold_min: int = MAJOR_MOVE_THRESHOLD_MIN,
) -> None:
    """Attach a one-clause ``reason`` to each MAJOR forward-shifted move
    (session 3.3 CU3). A delta card that says "+9818 min" without a WHY is a
    number with no story; this reads the story straight off the re-solve's own
    placements — the same occupancy arithmetic the reconstruction already knows.

    For an op that moved later, the reason is whatever holds its NEW machine
    right up until its new start: if that is the DROPPED op, "displaced by the
    dropped op"; otherwise the machine was simply busy — "blocked on <machine>
    until <time>". The reason is STRUCTURED (resource ids, not names) so the
    cockpit renders it in planner vocabulary via its own identity map. Only
    major shifts are annotated (the threshold token), and only when the machine
    is busy contiguously up to the start — a distant blocker is not the reason,
    so no clause is invented.

    Mutates ``moves`` in place; leaves minor shuffles and the pinned drop
    unannotated (the card's own move text already reads them).
    """
    # New placement of EVERY op in the re-solve (for the per-machine timeline).
    new_all: dict[str, tuple[str, datetime, datetime]] = {}
    for op_id, rid in solve_values.op_resource.items():
        smin = solve_values.op_start_minutes.get(op_id)
        emin = solve_values.op_end_minutes.get(op_id)
        if smin is None or emin is None:
            continue
        new_all[op_id] = (rid, horizon_start + timedelta(minutes=smin),
                          horizon_start + timedelta(minutes=emin))
    by_res: dict[str, list[tuple[datetime, datetime, str]]] = {}
    for op_id, (rid, s, e) in new_all.items():
        by_res.setdefault(rid, []).append((s, e, op_id))
    for v in by_res.values():
        v.sort()

    gap = timedelta(minutes=threshold_min)
    for m in moves:
        if m["pinned"] or m["start_delta_min"] < threshold_min:
            continue
        placed = new_all.get(m["operation_ref"])
        if placed is None:
            continue
        rid, start, _end = placed
        # the op that occupies this machine latest, ending at or before `start`
        blocker_op, blocker_end = None, None
        for bs, be, boid in by_res.get(rid, []):
            if boid == m["operation_ref"]:
                continue
            if be <= start and (blocker_end is None or be > blocker_end):
                blocker_op, blocker_end = boid, be
        if blocker_op is None or (start - blocker_end) > gap:
            continue      # not held contiguously — don't fabricate a why
        if blocker_op == pin_op_id:
            m["reason"] = {"kind": "displaced_by_drop"}
        else:
            m["reason"] = {"kind": "occupancy", "on_resource": rid,
                           "blocker_op": blocker_op,
                           "until": blocker_end.isoformat()}


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
