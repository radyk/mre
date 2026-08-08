"""Accepted cockpit edits become real schedule versions (docs/07 Phase 3, CU1;
R-DP1/R-DP2/R-DP7).

When a planner drops a bar and ACCEPTS the Tier-2 verdict, the edit stops being
a sandbox scenario and becomes a NEW proposed schedule version — the base is
never mutated (R-DP2's "nothing mutates before accept" becomes "accept CREATES,
never overwrites"). This module does exactly that and nothing more:

  1. derive a child snapshot from the base (copy every planned entity — the M4
     workpackages/operations/fulfillments included — so the accepted version
     reproduces the base's planning EXACTLY, differing only by the pin);
  2. warm-start from the base schedule, PIN the dropped op at (machine + time as
     displayed, R-DP1), and re-solve its surroundings under the sandbox budget;
  3. extract canonical entities (Schedule/Assignment/ServiceOutcome) into the
     child snapshot — a real schedule, ``is_scenario=False``;
  4. record ONE ``planner_edit`` Decision (basis=observed — a human command;
     authority MANDATORY; payload = the pin, the priced delta, the moved-set).

The API accept worker registers the result as a ``proposed`` schedule whose
parent is the base; publish (proposed → published) is a separate act in the
registry that supersedes the base and invalidates its pools/alternatives.

Determinism: the re-solve is warm-started + pinned + deterministic, so an accept
reproduces the sandbox verdict the planner already saw rather than drifting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Copied from the base snapshot when deriving the accepted-edit child snapshot:
# every planned entity EXCEPT the M7 outputs (Schedule/Assignment/ServiceOutcome),
# which the extractor writes fresh from the pinned re-solve. Copying the M4
# workpackages/operations/fulfillments (not just the M1 inputs the ScenarioRunner
# copies) means the accepted edit does NOT re-plan — it reproduces the base's
# exact planning and differs only by the pin.
_EDIT_COPY_TYPES = [
    "demand", "product", "resource", "resourcepool", "calendar", "constraint",
    "costmodel", "process", "operationspec", "precedenceedge",
    "workpackage", "operation", "fulfillment",
]


@dataclass
class PlannerEditResult:
    child_snapshot_id: str
    feasible: bool
    status: str
    objective: Optional[float]
    delta_abs: Optional[float]
    delta_pct: Optional[float]
    moved_count: int
    decision_record_id: Optional[str]
    wall_time_s: float
    message: str = ""
    moves: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)
    # The DECOMPOSED dollar cost delta (production/setup/tardiness), so the
    # accepted card shows LEDGER dollars, never the scaled objective (exit-audit).
    cost_delta: dict = field(default_factory=dict)


def apply_planner_edit(
    out_dir: Path | str,
    base_snapshot_id: str,
    pin_op_id: str,
    pin_resource_id: str,
    pin_start_iso: str,
    authority: str,
    base_context: dict,
    budget_s: float = 15.0,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    standing_pins: Optional[list[dict]] = None,
    hold_all_placements: bool = False,
    det_time_s: Optional[float] = None,
    seed: Optional[int] = None,
) -> PlannerEditResult:
    """Materialize an accepted edit as a child snapshot + a ``planner_edit``
    Decision, under ``out_dir`` (a freshly minted run directory whose
    ``snapshots/`` already contains a copy of the base snapshot).

    ``standing_pins`` are the lineage's prior ACCEPTED commitments (R-DP8): each
    is compiled as a hard constraint alongside the new drop, so the re-solve holds
    every earlier decision fixed and can never silently revert one. A new drop
    that is infeasible against a standing commitment raises (nothing accepted, the
    base stands) with the blocking commitment named.

    ``hold_all_placements`` (Session 4B.24) pins EVERY incumbent placement, not
    just the lineage's commitments, so the accepted version is EXACTLY the one the
    card previewed. Under the R-T2 amendment the card's money is a LOCAL price —
    "nothing else moved" — and an accept that then re-solved the window freely
    would hand the planner a different schedule from the one they said yes to.
    The promise on the card and the schedule that lands must be the same object.

    ``det_time_s`` gives the re-solve a DETERMINISTIC budget (clause 1). Without
    one the accept is a wall-clock lottery like every other sandbox solve was.

    Returns a :class:`PlannerEditResult`; the caller assembles the document from
    ``child_snapshot_id`` and registers it as a proposed schedule. Raises on an
    infeasible pin — an accept must never register an unsolvable version.
    """
    from mre.contracts.entities import EntityRef
    from mre.contracts.records import DecisionAlternative
    from mre.contracts.vocabularies import (
        DecisionBasis, DecisionType, ModuleCode, RecordTier, RunStatus,
    )
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.sandbox import (
        _annotate_move_reasons, _moved_set, _restrict_window, plan_of_record_scope,
    )
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import (
        _incumbent_objective, _m5_horizon, _placements, _read_evidence,
    )
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter

    if not authority:
        raise ValueError("a planner_edit requires an authority (who accepted it)")

    out_dir = Path(out_dir)
    store = SnapshotStore(out_dir / "snapshots")
    runs_dir = out_dir / runs_subdir
    runs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Derive the child snapshot (copy every planned entity but the M7 outputs).
    edit_hash = _short_pin_hash(pin_op_id, pin_resource_id, pin_start_iso)
    child_snap_id = _edit_snapshot_id(base_snapshot_id, edit_hash)
    store.derive_scenario_snapshot(base_snapshot_id, child_snap_id, _EDIT_COPY_TYPES)

    # 2. Load base entities (base snapshot still intact — accept never mutates it).
    base_reader = store.load_snapshot(base_snapshot_id)
    demands = list(base_reader.iter_entities("demand"))
    fuls = list(base_reader.iter_entities("fulfillment"))
    wps = list(base_reader.iter_entities("workpackage"))
    ops = list(base_reader.iter_entities("operation"))
    edges = list(base_reader.iter_entities("precedenceedge"))
    resources = list(base_reader.iter_entities("resource"))
    pools = list(base_reader.iter_entities("resourcepool"))
    calendars = list(base_reader.iter_entities("calendar"))
    constraints = list(base_reader.iter_entities("constraint"))
    costmodels = list(base_reader.iter_entities("costmodel"))
    incumbent_assignments = list(base_reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    # R-DP11 (Session 4B.31) — THE ACCEPT MODEL IS THE PLAN OF RECORD'S OWN SCOPE.
    # Build over exactly the operations the published plan PLACES, so the published
    # plan is a feasible assignment of this model BY CONSTRUCTION and an accept can
    # only ever fail because of the EDIT, never because of the plan it edits.
    #
    # Before this the accept compiled the WHOLE BOOK against the WINDOW's horizon.
    # On a rolling board that meant every beyond-horizon tray order the rolling
    # engine had deliberately declined to admit re-entered as FREE work that had to
    # fit the window's 31 days around 386 held placements — and it does not fit.
    # Measured on the Khalil board (4B.31 CU1): a ZERO-MOVE accept, pinning a bar at
    # its own placement, refused INFEASIBLE in 2.5s, and a deletion filter reduced
    # the cause to ONE unadmitted tray order (ORD-000062, 3 operations). Nothing had
    # ever committed on any rolling board. The scope is DERIVED here, not passed in,
    # because the identical restriction has existed since 4B.3c and the caller
    # forgot it at exactly one of the four Tier-2 surfaces.
    restrict_op_ids = plan_of_record_scope(incumbent_assignments)
    ops, wps, fuls, demands = _restrict_window(
        ops, wps, fuls, demands, restrict_op_ids)

    reference_date = _parse_ref_date(base_context.get("reference_date"))
    # The horizon must match the base run's M5 horizon exactly, so the pinned
    # re-solve places against the same clock the incumbent did.
    evidence = _read_evidence(_base_runs_dir(base_context))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    pin_start_dt = _parse_dt(pin_start_iso)
    if pin_start_dt is None:
        raise ValueError(f"cannot parse pin start {pin_start_iso!r}")
    pin_start_min = int((pin_start_dt - horizon_start).total_seconds() // 60)

    workers = 1 if deterministic else base_context.get("solver_workers")

    # 3. Build + warm-start + pin + solve (mirrors the sandbox re-solve, R-DP1).
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="planner-edit model build",
        config={"horizon_start": horizon_start.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                # R-CH1 clause (2), Session R4.2 — THE CHILD'S RUN CONTEXT
                # RECORDS WHAT DOWNSTREAM DERIVATION NEEDS. An accept run has no
                # M3, so `derive_base_context` recovered no reference_date from
                # a child's own run dir and nine of its eleven callers then
                # built a model whose origin dragged back to the earliest
                # release in the WHOLE PLANT — 35 days off the frame the
                # planner's pin is expressed in, measured on `b5daba66` (R4.0
                # §3.4). Recorded here, at the one site that actually used the
                # value, rather than patched at the read sites.
                "reference_date": (reference_date.isoformat()
                                   if reference_date else None),
                "pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)
    # R-SG1 (2): ``pin_start_min`` and every standing pin below are minutes
    # from the EVIDENCE origin. An accept that lands the planner's bar one
    # frame off is a wrong plan of record, not a wrong answer — assert first.
    sp.assert_frame(var_map, horizon_start, site="planner edit accept")

    apply_solution_hints(model, var_map, incumbent_assignments)
    # R-DP1 (4.0 hotfix): the pin MUST bind on BOTH axes — machine AND time.
    # The machine literal exists ONLY for resources the op is eligible on; a
    # target outside that set has no literal. The prior code did
    # ``if lit is not None: model.add(lit == 1)`` and SILENTLY SKIPPED the
    # machine constraint when the literal was absent, so the re-solve honoured
    # only the time pin and legally relocated the op to a cheaper eligible
    # machine — right time, wrong machine, reported as a happy verdict. An accept
    # must NEVER place the op anywhere but where the planner dropped it, so an
    # un-pinnable target is a hard error (nothing accepted, the base stands) —
    # never a silent skip.
    try:
        sp.apply_pin(model, var_map, pin_op_id, pin_resource_id, pin_start_min)
    except sp.PinUnsatisfiable as exc:
        raise RuntimeError(
            f"planner edit: {exc.reason} (op {pin_op_id} → {pin_resource_id}) — "
            "R-DP1 requires the pinned resource be honoured; nothing accepted, "
            "the base stands") from exc
    # R-DP8: hold every prior ACCEPTED commitment of this lineage fixed too — the
    # new drop re-commits pin_op_id (skip it), the rest are compiled as hard
    # constraints so the re-solve can NEVER revert a decision the planner already
    # made. A standing pin that cannot bind is a lineage inconsistency and aborts
    # the accept (loudly, base stands).
    new_pin = {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
               "start": pin_start_dt.isoformat()}
    try:
        sp.apply_standing_pins(model, var_map, standing_pins, horizon_start,
                               skip_op=pin_op_id)
    except sp.PinUnsatisfiable as exc:
        raise RuntimeError(
            f"planner edit: a standing commitment could not be held ({exc.reason}) "
            "— nothing accepted; the base version stands") from exc
    standing_ops = sp.standing_pin_ops(standing_pins)

    # Session 4B.24: hold every other placement exactly where the card showed it.
    # These are HARD constraints but NOT lineage commitments — the pin register
    # is unchanged, so `standing_pin` on a bar still means "the planner committed
    # this", not "the accept happened to hold it".
    held_all = 0
    if hold_all_placements:
        for oid, (rid, s_dt) in incumbent_placement.items():
            if oid == pin_op_id:
                continue
            try:
                sp.apply_pin(model, var_map, oid, rid,
                             int((s_dt - horizon_start).total_seconds() // 60))
                held_all += 1
            except sp.PinUnsatisfiable as exc:
                raise RuntimeError(
                    f"planner edit: the previewed schedule could not be held — "
                    f"op {oid} ({exc.reason}); nothing accepted, the base "
                    "version stands") from exc

    # R-DP12 CU1 (Session 4B.32) — VERDICT IDENTITY: the card's model and the
    # accept's model are asked the SAME QUESTION.
    #
    # With ``hold_all_placements`` every operation in scope is pinned to a
    # (resource, start) — the plan of record's own, plus the planner's drop — so
    # the model has exactly one assignment left and THERE IS NOTHING TO OPTIMISE.
    # The objective is then pure decoration: it cannot change the plan, and the
    # only thing it can change is the WORD the solve returns. Left in place it
    # turns a proof question into a search question under a budget, so the accept
    # could answer UNKNOWN ("we ran out of time") where the card — which validates
    # through ``local_price.validate_held_world`` with the objective cleared,
    # method ``cp-sat-pin-all`` — had proved OPTIMAL. A budget verdict wearing a
    # plant verdict's clothes, and the residue 4B.31 §8(c) named.
    #
    # Clearing it here makes the two surfaces ONE AUTHORITY rather than two that
    # happen to agree, which is what discharges R-DP10's two-beat obligation
    # (docs/04 2026-08-03). Guarded on the `pilot_scale` 200/w7 dense fixture by
    # `test_a_held_accept_proves_rather_than_searches`, which asserts OPTIMAL and
    # never UNKNOWN. 4B.31's own UNKNOWN-after-60.9s specimen was `demo_board`
    # 120/w7 and this session did NOT re-run that world.
    #
    # WITHOUT the hold this is a genuine window search and the objective is what
    # makes it meaningful, so it stays. One rule, both board classes: the
    # condition is "is anything free to move", never "is this board rolling".
    objective_cleared = False
    if hold_all_placements:
        model.clear_objective()
        objective_cleared = True

    solve_seed = (seed if seed is not None
                  else (0 if deterministic else base_context.get("solver_seed")))
    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="planner-edit re-solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "random_seed": solve_seed, "deterministic_time": det_time_s,
                "held_placements": held_all, "pin_op": pin_op_id,
                # which QUESTION this solve was asked (R-DP12 CU1)
                "objective_cleared": objective_cleared},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    t0 = time.monotonic()
    solve_result = SolveRunner(
        time_limit_seconds=budget_s, num_search_workers=workers,
        random_seed=solve_seed,
        deterministic_time=det_time_s if deterministic else None,
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)

    if not feasible:
        # R-DP8: if a standing commitment directly blocks the drop, name it in the
        # refusal rather than a bare "infeasible" — the older pin is never quietly
        # sacrificed to make room.
        conflict = sp.detect_conflict(new_pin, standing_pins, var_map, horizon_start)
        if conflict is not None:
            raise RuntimeError(
                f"planner edit: this placement conflicts with a commitment you "
                f"already made — it overlaps op {conflict.op_id[:8]} on resource "
                f"{conflict.resource_id[:8]}; nothing accepted, the base stands")
        # Session 4B.31 CU4: name the blocker in the words the CARD would have
        # used, from the ONE refusal vocabulary (4B.24). A planner may not be
        # handed a solver status as an explanation — and the accept and the card
        # must not describe the same refusal in two registers, which is how
        # 4B.31's own specimen read as a contradiction rather than as agreement.
        named = _named_refusal(base_context, base_snapshot_id, restrict_op_ids,
                               standing_pins, pin_op_id, pin_resource_id,
                               pin_start_iso)
        if named:
            raise RuntimeError(
                f"planner edit: {named}; nothing accepted, the base version stands")
        raise RuntimeError(
            f"planner edit infeasible with the pin held (status={solve_result.status}) "
            "— nothing accepted; the base version stands")

    # R-DP1 post-condition (4.0 hotfix): the pinned op MUST have solved to the
    # pinned resource at the pinned start. The mandatory constraints above
    # guarantee it, but an accept is irreversible once registered — so verify the
    # solved placement (what extraction is about to write) BEFORE minting the
    # version. A mismatch means the pin did not bind and the accept aborts; it
    # must never register a version that renders the op somewhere the planner did
    # not drop it.
    # Compare in the SAME canonical minute grid the pin compiled to (int minutes
    # since horizon_start), never re-serialized datetimes — solve_values carry
    # integer minutes straight from solver.Value(), and pin_start_min is an int,
    # so there is no rounding/tz seam between the pin and the check (4.0c).
    solved_res = solve_result.solve_values.op_resource.get(pin_op_id)
    solved_start = solve_result.solve_values.op_start_minutes.get(pin_op_id)
    solved_start = int(solved_start) if solved_start is not None else None
    if solved_res != pin_resource_id or solved_start != pin_start_min:
        raise RuntimeError(
            f"planner edit: R-DP1 post-condition FAILED — pinned op {pin_op_id} "
            f"solved to resource {solved_res} @ {solved_start}min, not the pinned "
            f"{pin_resource_id} @ {pin_start_min}min; nothing accepted, the base "
            "version stands")

    # SOLVER TELEMETRY, and nothing else (R-DP12 clause 3, Session 4B.32). This
    # is the SCALED objective minus the incumbent's — and on a rolling board the
    # incumbent's objective is the WINDOW SOLVE's, a different expression over a
    # different op set from the restricted accept model's. The two are not
    # comparable, which is why the Khalil board's ZERO-MOVE accept reported
    # `delta_abs −7,014,821 / −5.88%` beside a ledger delta of exactly $0.00
    # (4B.31 §8(a)). It is computed only where an objective actually exists, it
    # never selects a driver, it never reaches a planner surface, and where the
    # objective was cleared it is None — never 0.0, which would read as "no
    # change" rather than "not asked" (4B.18's `unreadable` discipline).
    delta_abs = delta_pct = None
    if (not objective_cleared and incumbent_objective
            and solve_result.objective is not None):
        delta_abs = round(solve_result.objective - incumbent_objective, 4)
        if incumbent_objective > 0:
            delta_pct = round(delta_abs / incumbent_objective * 100.0, 4)

    moves = _moved_set(solve_result.solve_values, incumbent_placement,
                       horizon_start, pin_op_id, exclude_ops=standing_ops)
    _annotate_move_reasons(moves, solve_result.solve_values, horizon_start, pin_op_id)

    # 4. Extract canonical entities into the child snapshot — a REAL schedule.
    e_rep = Reporter.begin(
        module=ModuleCode.M7, purpose="planner-edit schedule extraction",
        config={}, trigger="planner_edit",
        snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    m7_writer = store.extend_snapshot(child_snap_id)
    extract_result = Extractor().extract(
        solve_values=solve_result.solve_values, snapshot_id=child_snap_id,
        operations=ops, workpackages=wps, resources=resources,
        fulfillments=fuls, demands=demands, cost_model=cost_model,
        reporter=e_rep, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=m7_writer,
        is_scenario=False, overtime_windows=var_map.overtime_windows,
    )
    m7_writer.finalize()
    e_rep.end(RunStatus.SUCCESS)

    # The cost delta, DECOMPOSED (production Δ + setup Δ + tardiness Δ) from the
    # ledgers — the answer to "why does this move cost N" (CU2). Recorded on the
    # Decision so it is self-contained evidence, single-run-scoped, decomposing
    # exactly (docs/02 §4.4). Base ledger from the base schedule's summary; new
    # from the fresh extraction.
    cost_delta = _cost_delta(base_reader, extract_result)

    # 5. Record the planner_edit Decision (basis=observed; authority mandatory).
    d_rep = Reporter.begin(
        module=ModuleCode.M4, purpose="planner-edit accept",
        config={"pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "authority": authority},
        trigger="planner_edit", snapshot_id=child_snap_id, sink_dir=runs_dir,
    )
    chosen = {
        "pin": {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
                "start": pin_start_dt.isoformat()},
        # SOLVER TELEMETRY (R-DP12 clause 3) — kept because a diagnostic reader
        # wants it, LABELLED because nothing planner-facing may read it and
        # nothing may select a driver from it. None where the model was asked a
        # feasibility question (CU1).
        "delta_abs": delta_abs, "delta_pct": delta_pct,
        "objective_cleared": objective_cleared,
        "moved_count": len(moves),
        "verdict": "OPTIMAL" if solve_result.status == "OPTIMAL" else solve_result.status,
        # the decomposed cost delta (dollars) + the moved-set with its "why"
        # clauses — the self-contained evidence CU2's edit-question domain reads.
        "cost_delta": cost_delta,
        "moves": moves,
    }
    old_res, old_start = incumbent_placement.get(pin_op_id, (None, None))
    alternatives = [DecisionAlternative(
        option="keep the incumbent placement",
        consequence=("the base schedule stands unchanged (0 cost delta)"
                     if old_res else "no prior placement recorded"),
    )]
    subjects = [EntityRef(entity_type="operation", entity_id=pin_op_id),
                EntityRef(entity_type="resource", entity_id=pin_resource_id)]
    # R-DP12 (Session 4B.32) — THE LEDGER IS THE ONLY COMPARABLE NUMBER. Every
    # dollar this Decision states derives from ``cost_delta``, the same figure
    # the card showed, computed identically on every board class.
    # R-DP13 (Session 4B.33) — the DRIVER derives from nothing: an accept's
    # cause is that a human directed the placement, at every ledger delta.
    driver = _edit_driver()
    ledger_delta = _ledger_total_delta(cost_delta)
    decision = d_rep.record_decision(
        decision_type=DecisionType.PLANNER_EDIT,
        subjects=subjects, chosen=chosen, alternatives=alternatives,
        driver=driver, basis=DecisionBasis.OBSERVED,
        tier=RecordTier.HEADLINE, authority=authority,
        message=(f"Planner edit: pinned op {pin_op_id[:8]} to "
                 f"{pin_resource_id[:8]} @ {pin_start_dt.isoformat()}"
                 # DOLLARS, from the ledger. Until 4B.32 this printed a "$" in
                 # front of ``delta_abs`` — the SCALED objective — so the Khalil
                 # board's zero-move accept would have recorded "(−$7,014,821)"
                 # for a move that changed the ledger by nothing at all.
                 + (f" ({'+' if ledger_delta >= 0 else '−'}${abs(ledger_delta):,.0f})"
                    if ledger_delta is not None else "")),
    )
    d_rep.end(RunStatus.SUCCESS)

    return PlannerEditResult(
        child_snapshot_id=child_snap_id, feasible=True,
        status=solve_result.status,
        # A cleared objective has no value to report. CP-SAT answers 0.0 for a
        # model with no objective, and 0.0 here would read as a real total.
        objective=None if objective_cleared else solve_result.objective,
        delta_abs=delta_abs, delta_pct=delta_pct, moved_count=len(moves),
        decision_record_id=decision.record_id, wall_time_s=wall,
        message="accepted", moves=moves, cost_delta=cost_delta,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
    )


def _ledger_total_delta(cost_delta: dict) -> Optional[float]:
    """The accept's dollar delta: ``cost_delta.total_delta`` and nothing else.

    R-DP12 (Session 4B.32). Returns None when the ledgers could not be read —
    "we do not know what this cost" and "this cost nothing" are different
    statements and a surface may not confuse them."""
    if not cost_delta:
        return None
    total = cost_delta.get("total_delta")
    return None if total is None else float(total)


def _edit_driver():
    """The driver of a ``planner_edit`` accept Decision: ``PLANNER_DIRECTIVE``.

    THE PARAMETER IS GONE, AND ITS ABSENCE IS THE RULING. Until 4B.33 this took
    ``cost_delta`` — a residue of the era when the driver was *selected by a
    number*. Under R-DP13 the driver is a property of the DECISION TYPE, not of
    any quantity, so a signature that accepts a quantity would advertise a
    derivation that no longer happens. R-DP12's rule is not weakened by this: its
    point was that the driver must never come from the incomparable scaled
    objective, and a constant trivially does not.

    R-DP12 (Session 4B.32). Until that session the driver was selected by
    ``delta_abs > 0`` — the SCALED objective of the restricted accept model minus
    the incumbent objective read from the base run's evidence. On a rolling board
    those are different expressions over different operation sets, so every
    rolling accept minted a Decision whose driver was chosen by arithmetic
    between two incomparable numbers. Measured (4B.31 §8(a)): the Khalil board's
    ZERO-MOVE accept — a bar pinned at its own placement, ledger unchanged to the
    cent — scored ``delta_abs −7,014,821`` and therefore recorded
    ``NO_ALTERNATIVE``, which the ask layer voices as *"there was no other
    feasible option"*: a claim about the PLANT manufactured from a fact about our
    ARITHMETIC. Drivers are exactly what the ask layer testifies about.

    R-DP13 (Session 4B.33) — ``PLANNER_DIRECTIVE``, THE CODE THE TAXONOMY
    LACKED. 4B.32 recorded the gap rather than stretching a member to fit
    (close-out §4; docs/07 §5a.130), and this is the member. A ``planner_edit``
    accept's real driver is *a human directed this placement*, which is what the
    code now says. The two it displaces, and why neither was honest:

      * ``NO_ALTERNATIVE`` (what HEAD recorded until 4B.32) is RETIRED from this
        site permanently. It asserts something about the PLANT that an accept
        never establishes, and under ``hold_all_placements`` it would be
        asserting it from a property of OUR METHOD (every placement pinned ⇒ of
        course nothing else was reachable).
      * ``COST_TRADEOFF`` (4B.32's least-wrong interim) claims a cost decided the
        matter. Its phrase — *"it was the cheaper option once every cost was
        weighed"* — is FALSE at a $0.00 delta, where the comparison came back
        level, and FALSE of a DEARER accept, where the planner knowingly paid
        (4B.32 §7(e)). A driver is exactly what the ask layer testifies from, so
        a phrase the ledger can contradict is a defect, not a rounding.

    The driver remains a CONSTANT here, deliberately, and R-DP13 does not change
    that: the variation ``delta_abs`` used to supply was not information, it was
    noise with a sign, and the honest variation — how much the move actually cost
    — rides ``chosen.cost_delta`` where anyone can check it. ONE RULE ON BOTH
    BOARD CLASSES (R-DP11's discipline): a directed placement is a directed
    placement whether the board rolls or not."""
    from mre.contracts.vocabularies import DriverCode
    return DriverCode.PLANNER_DIRECTIVE


def _named_refusal(base_context: dict, base_snapshot_id: str,
                   restrict_op_ids, standing_pins, pin_op_id: str,
                   pin_resource_id: str, pin_start_iso: str) -> str:
    """The refusal sentence the CARD would have shown for this same pin, taken
    from the one refusal vocabulary (``local_price.structural_refusal``, 4B.24).

    Best-effort by design: it runs only on a path that has ALREADY refused, so a
    failure here must never replace a loud refusal with a louder crash. When it
    cannot name anything the caller falls back to the solver-status sentence —
    which is worse copy, but never a wrong claim about the plant.

    R-DP10's residue lives here too: a core is A sufficient set and never THE
    unique cause, so the sentence says what cannot hold, never "the reason is"."""
    try:
        from mre.modules.local_price import price_local_move
        base_out = Path(base_context["base_runs_dir"]).parent
        priced = price_local_move(
            base_out, base_snapshot_id, pin_op_id, pin_resource_id, pin_start_iso,
            restrict_op_ids=restrict_op_ids, standing_pins=standing_pins,
            validate=False)
    except Exception:  # noqa: BLE001
        return ""
    refusal = getattr(priced, "refusal", None)
    if not refusal:
        return ""
    sentence = refusal.get("sentence") or ""
    if not sentence:
        return ""
    occupants = refusal.get("other_work_orders") or []
    if occupants:
        sentence += f" ({', '.join(str(o) for o in occupants[:3])})"
    family = refusal.get("family")
    return f"{sentence}" + (f" [{family}]" if family else "")


def _cost_delta(base_reader, extract_result) -> dict:
    """Decompose the cost delta (new − base) into production / setup / tardiness
    dollars, which sum to the total delta (docs/02 §4.4 decomposability). Base
    ledger from the base schedule's summary_metrics; new ledger from the fresh
    extraction's cost_ledger."""
    schedules = list(base_reader.iter_entities("schedule"))
    base_sm = schedules[-1].get("summary_metrics", {}) if schedules else {}
    new = getattr(extract_result, "cost_ledger", {}) or {}
    base_prod = float(base_sm.get("production_cost", 0.0))
    base_setup = float(base_sm.get("setup_cost", 0.0))
    base_tard = float(base_sm.get("tardiness_cost", 0.0))
    base_total = float(base_sm.get("total_cost", base_prod + base_setup + base_tard))
    new_prod = float(new.get("production_cost", 0.0))
    new_setup = float(new.get("setup_cost", 0.0))
    new_tard = float(new.get("tardiness_cost", 0.0))
    new_total = float(new.get("total_cost", new_prod + new_setup + new_tard))
    return {
        "total_before": round(base_total, 2), "total_after": round(new_total, 2),
        "total_delta": round(new_total - base_total, 2),
        "production_delta": round(new_prod - base_prod, 2),
        "setup_delta": round(new_setup - base_setup, 2),
        "tardiness_delta": round(new_tard - base_tard, 2),
    }


def _short_pin_hash(*parts: str) -> str:
    import hashlib
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8]


# A child snapshot id is a directory NAME on disk (snapshots/<id>/entities_*.jsonl).
# History: the naive scheme appended "--edit-<hash>" to the parent id on every
# accept, so a chain of edits grew the id — and thus the on-disk path — without
# bound, crossing Windows MAX_PATH (260) and failing the derive/copy with
# FileNotFoundError [WinError 3] (4.0c). 4.0c capped that at 90 chars, but the cap
# was validated in a SHORT temp prefix; at Daryn's real ~130-char data-root prefix
# a near-cap id still crossed 260 on a shallow chain (4.0d).
#
# 4.0d makes the directory name a SHORT, FIXED-WIDTH opaque id that embeds NO
# lineage at all — the parent chain lives solely in the registry's
# parent_schedule_id. The on-disk snapshot path is therefore bounded and tiny no
# matter how deep the edit chain goes (defense in depth alongside the long-path
# seam, which independently lifts MAX_PATH — see mre.modules.longpath). The id is:
#   * fixed-width  — always _EDIT_SNAP_PREFIX + 12 hex = 22 chars;
#   * deterministic per (base, edit_hash) — a re-accept of the same pin reproduces
#     the same id (idempotent), and different parents yield different ids (the
#     digest is over the exact parent id), so lineages never collide.
_EDIT_SNAP_PREFIX = "snap-edit-"
# The guaranteed upper bound on an edit-snapshot directory name. The opaque scheme
# is fixed-width (22) and far under this; the ceiling is asserted by the tests as a
# standing guard against the name ever growing again.
_MAX_EDIT_SNAP_ID_LEN = 32


def _edit_snapshot_id(base_snapshot_id: str, edit_hash: str) -> str:
    """A SHORT, OPAQUE directory name for an accepted-edit child snapshot (4.0d).

    Embeds no lineage — the parent chain is the registry's parent_schedule_id — so
    the name stays fixed-width however deep the chain grows. Deterministic per
    (base_snapshot_id, edit_hash) and distinct per parent."""
    import hashlib
    digest = hashlib.sha256(f"{base_snapshot_id}|{edit_hash}".encode()).hexdigest()[:12]
    return f"{_EDIT_SNAP_PREFIX}{digest}"


def _base_runs_dir(base_context: dict) -> Path:
    """The base run's ``runs/`` directory, carried in base_context so the M5
    horizon + incumbent objective read from the SAME evidence the base solved
    against (not the empty new-run evidence)."""
    return Path(base_context["base_runs_dir"])


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
