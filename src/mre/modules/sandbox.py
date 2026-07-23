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

import hashlib
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# The budget is a DESIGN TOKEN, not a magic constant — feel-iteration owned,
# surfaced in the UI, and the single knob the latency regression is measured
# against (R-T1c). Override per-call for tests / tuning.
SANDBOX_BUDGET_S = 15.0

# --- R-T2 two-beat interaction contract (Session 4B.3b) --------------------
# BEAT ONE is a first-feasible feasibility check under a SMALL deterministic
# budget — a cheap "can the op go here at all" verdict that NEVER displays a
# monetary quantity (R-T2(1)). It is a RELAXATION of the full budgeted solve
# (beat two): it pins only the dragged op and does NOT hold the lineage's
# committed/standing work, so beat two (which does) may legitimately CONTRADICT
# it (infeasible, or a materially different placement) — R-T2(4). The budget is
# a design token, small so grab→ghost stays snappy; measured shape at demo
# density is first-feasible ~0.3s.
FEASIBILITY_BUDGET_S = 2.0
# The deterministic-time budget for beat one, so a first-feasible verdict is
# reproducible run-to-run (workers=1 + fixed seed + max_deterministic_time).
FEASIBILITY_DET_TIME_S = 1.0

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
    delta_pct: Optional[float] = None      # vs the incumbent objective (SCALED)
    delta_abs: Optional[float] = None      # objective_after - objective_before (SCALED)
    # The DOLLAR cost delta from the ledger (Phase-3 exit audit fix): the solver
    # objective is a SCALED, tardiness-weighted sum (~100× the dollar ledger), so
    # ``delta_abs`` must NEVER be shown as a dollar amount. These carry the true
    # cost delta — extracted from the re-solve's own ledger vs the base schedule's
    # total — so every number the delta card shows in dollars traces to ledger
    # records (docs/02 §4.4). None when the ledger could not be computed (the card
    # then degrades to a relative-% headline, never a false dollar figure).
    cost_delta_abs: Optional[float] = None   # dollars: total_after - total_before
    cost_delta_pct: Optional[float] = None   # cost_delta_abs / total_before * 100
    message: str = ""
    # The moved-set (R-DP7): every op the pinned re-solve displaced relative to
    # the incumbent, old → new (resource + start). The pinned op itself is
    # flagged (``pinned``) and always present when feasible. Warm-starting keeps
    # this set minimal by construction — the property that makes tracing it
    # tractable (R-DP7 implementation note). The cockpit maps operation_ref →
    # bar to draw the ghost-of-old + motion trace and the delta-card line items.
    moves: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)  # {operation_ref, resource_id, start}
    # --- R-T2 beat-two layered card (Session 4B.3b, CU2) --------------------
    # The deterministic correlation id linking this priced beat two to its beat
    # one (feasibility ghost). Derived from the pin, so the two beats of the same
    # gesture always agree without server state.
    correlation_id: str = ""
    # The ALWAYS-VISIBLE layer (decision-sufficient on its own):
    #   * cost_delta_abs / feasible (above) — the signed total + the verdict
    #   * dominant_driver — the one driver behind the change, in driver_phrase
    #     language, HEDGED where the attribution is by price rank alone (docs/02
    #     §4.2: EARLINESS_PREFERENCE). {code, phrase, hedge|None}.
    dominant_driver: dict = field(default_factory=dict)
    #   * affected_orders — the top-N orders this move touches, each with its own
    #     tardiness ($) and lateness (min) delta (per-Demand truth from the
    #     service outcomes, never per-WorkPackage). [{work_order, demand_ref,
    #     tardiness_delta, lateness_delta_min}], |delta|-ranked, N capped.
    affected_orders: list[dict] = field(default_factory=list)
    #   * lateness_delta_min — net tardiness-minutes introduced (+) or recovered
    #     (−) across every demand, so "made something late / rescued a date" is
    #     one number.
    lateness_delta_min: int = 0
    #   * no_committed_work_changes — the standing invariant, ASSERTED against the
    #     moved-set (a committed/standing-pinned op can never be a consequence).
    #     The card renders it as a line; a test pins it True.
    no_committed_work_changes: bool = True
    # The DETAIL layer (same card): the cost decomposition by ledger line. Each
    # entry {line, delta}; the lines sum EXACTLY to cost_delta_abs (rollup_of
    # discipline — the card may never claim arithmetic the ledger cannot back).
    # An explicit "other" remainder line carries any delta the named lines do not
    # factor (0 when the ledger fully decomposes). None when no ledger (degrade).
    cost_lines: Optional[list[dict]] = None

    def summary(self) -> dict:
        return asdict(self)


# The field names beat one is FORBIDDEN to carry — any monetary quantity of any
# kind (R-T2(1), enforced BY CONSTRUCTION with a contract test that inspects the
# dataclass fields). Beat one is feasibility + placement + a correlation id only.
_MONEY_FIELD_TOKENS = ("cost", "delta", "price", "dollar", "objective", "ledger",
                       "tardiness", "spend", "money", "$")


@dataclass(frozen=True)
class FeasibilityGhost:
    """BEAT ONE of the R-T2 two-beat interaction: a first-feasible feasibility
    verdict + placement, NEVER a monetary quantity (R-T2(1)).

    This type CANNOT represent money by construction — it has no cost/delta/price/
    objective field, and ``test_feasibility_no_money`` asserts the field ABSENCE
    (not emptiness). The board renders ``placement`` in the R-M1 ghost class under
    a non-monetary "pricing…" state (R-T2(2)); beat two (the priced
    :class:`SandboxResult`, correlated by ``correlation_id``) supersedes it.

    Beat one mints NO edits and touches NO persistent state (R-T2(5))."""
    correlation_id: str
    feasible: bool
    within_budget: bool
    wall_time_s: float
    budget_s: float
    status: str                  # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    message: str
    # placement of the pinned op AND any op the first-feasible solve moved —
    # resource + start/end ISO only, NO cost. [{operation_ref, resource_id,
    # start, end, pinned}]. The ghost the board draws.
    placement: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return asdict(self)


def correlation_id_for(snapshot_id: str, pin_op_id: str,
                       pin_resource_id: Optional[str],
                       pin_start_iso: Optional[str]) -> str:
    """The deterministic id linking beat one to beat two for one gesture. Derived
    purely from the pin (+ snapshot), so both beats compute the SAME id with no
    server state — the client passes beat one's id into beat two and the two are
    provably the same gesture."""
    raw = f"{snapshot_id}|{pin_op_id}|{pin_resource_id}|{pin_start_iso}"
    return "corr-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


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


def _restrict_window(ops, wps, fuls, demands, restrict_op_ids):
    """Restrict the loaded entity sets to a rolling ACTIVE WINDOW (Session 4B.3c
    CU3). ``restrict_op_ids`` is the set of operation ids the window solve placed
    (committed ∪ active — every op with a persisted assignment). Restricting the
    build to exactly that set makes the sandbox re-solve the WINDOW, not the whole
    plant: the SolverBuilder derives the same horizon_start the window-0 solve did
    (it was built over the same ops), so the pin arithmetic aligns with the
    persisted placements, and the beyond-horizon (future) work never re-enters as
    free ops. None ⇒ no restriction (a monolithic schedule)."""
    if restrict_op_ids is None:
        return ops, wps, fuls, demands
    keep = set(restrict_op_ids)
    ops = [o for o in ops if o["id"] in keep]
    wp_ids = {o.get("workpackage_ref", "") for o in ops}
    wps = [w for w in wps if w["id"] in wp_ids]
    fuls = [f for f in fuls if f.get("workpackage_ref", "") in wp_ids]
    dem_ids = {f.get("demand_ref", "") for f in fuls}
    demands = [d for d in demands if d["id"] in dem_ids]
    return ops, wps, fuls, demands


def feasibility_ghost(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    budget_s: float = FEASIBILITY_BUDGET_S,
    det_time_s: float = FEASIBILITY_DET_TIME_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    restrict_op_ids: Optional[set] = None,
) -> FeasibilityGhost:
    """BEAT ONE (R-T2): a first-feasible feasibility verdict + placement for a
    dropped bar, under a SMALL deterministic budget, carrying NO monetary
    quantity (R-T2(1)).

    It is a RELAXATION of the full budgeted solve (:func:`sandbox_pin_resolve`,
    beat two): it pins ONLY the dragged op and does NOT hold the lineage's
    committed/standing work, so the fast "can it go here at all" answer is cheap.
    Beat two, which DOES hold every commitment and runs to a proof, may therefore
    legitimately contradict beat one (R-T2(4)).

    Mints NOTHING and touches NO persistent state (R-T2(5)) — no reporter
    Decisions, no snapshot writes; the evidence Reporter records are read-only
    telemetry under the sandbox run dir, exactly as the priced re-solve's are."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules import standing_pins as sp
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

    # CU3: on a rolling schedule, restrict the build to the ACTIVE WINDOW's ops so
    # beat one re-solves the window (not the whole plant), aligned with the
    # persisted window-0 incumbent.
    ops, wps, fuls, demands = _restrict_window(ops, wps, fuls, demands, restrict_op_ids)

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

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
    corr = correlation_id_for(snapshot_id, pin_op_id, pin_resource_id,
                              pin_start_dt.isoformat())

    workers = 1 if deterministic else ctx.get("solver_workers")
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="feasibility ghost model build",
        config={"pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min, "beat": "one"},
        trigger="sandbox_feasibility", snapshot_id=snapshot_id,
        sink_dir=sandbox_dir / "runs",
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    apply_solution_hints(model, var_map, incumbent_assignments)
    # RELAXATION: pin ONLY the dragged op — NOT the lineage's standing/committed
    # work. This is exactly what lets beat two (which holds them) contradict beat
    # one (R-T2(4)); it also keeps beat one cheap.
    try:
        sp.apply_pin(model, var_map, pin_op_id, pin_resource_id, pin_start_min)
    except sp.PinUnsatisfiable as exc:
        return FeasibilityGhost(
            correlation_id=corr, feasible=False, within_budget=True,
            wall_time_s=0.0, budget_s=budget_s, status="INFEASIBLE",
            message=f"this placement isn't possible: {exc.reason}",
            placement=[],
            pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
                 "start": pin_start_dt.isoformat()},
        )

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="feasibility ghost solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "stop_after_first_solution": True, "beat": "one"},
        trigger="sandbox_feasibility", snapshot_id=snapshot_id,
        sink_dir=sandbox_dir / "runs",
    )
    t0 = time.monotonic()
    solve_result = SolveRunner(
        time_limit_seconds=budget_s, num_search_workers=workers,
        random_seed=0 if deterministic else None,
        deterministic_time=det_time_s if deterministic else None,
        stop_after_first_solution=True,
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)

    placement: list[dict] = []
    if feasible:
        placement = _placement_list(solve_result.solve_values,
                                    incumbent_placement, horizon_start, pin_op_id)
    return FeasibilityGhost(
        correlation_id=corr, feasible=feasible,
        within_budget=wall <= budget_s + _BUDGET_STOP_MARGIN_S,
        wall_time_s=wall, budget_s=budget_s, status=solve_result.status,
        message=("this placement is possible — pricing it now"
                 if feasible else "this placement isn't possible here"),
        placement=placement,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
    )


def _placement_list(solve_values, incumbent_placement, horizon_start,
                    pin_op_id) -> list[dict]:
    """The pinned op's placement + any op the (relaxed, first-feasible) solve
    moved, positions ONLY (resource + start/end). Beat one's ghost — NO cost."""
    out: list[dict] = []

    def _pl(op_id):
        rid = solve_values.op_resource.get(op_id)
        smin = solve_values.op_start_minutes.get(op_id)
        emin = solve_values.op_end_minutes.get(op_id)
        if rid is None or smin is None:
            return None
        s = horizon_start + timedelta(minutes=smin)
        e = horizon_start + timedelta(minutes=emin if emin is not None else smin)
        return rid, s, e

    pin_pl = _pl(pin_op_id)
    if pin_pl:
        out.append({"operation_ref": pin_op_id, "resource_id": pin_pl[0],
                    "start": pin_pl[1].isoformat(), "end": pin_pl[2].isoformat(),
                    "pinned": True})
    for op_id, (old_rid, old_start) in incumbent_placement.items():
        if op_id == pin_op_id:
            continue
        pl = _pl(op_id)
        if pl is None:
            continue
        new_rid, new_start, new_end = pl
        moved = new_rid != old_rid or abs(
            round((new_start - old_start).total_seconds() / 60.0)) >= 1
        if not moved:
            continue
        out.append({"operation_ref": op_id, "resource_id": new_rid,
                    "start": new_start.isoformat(), "end": new_end.isoformat(),
                    "pinned": False})
    return out


def sandbox_pin_resolve(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    budget_s: float = SANDBOX_BUDGET_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    standing_pins: Optional[list[dict]] = None,
    restrict_op_ids: Optional[set] = None,
) -> SandboxResult:
    """Re-solve with one op pinned to (machine + time), the rest free, under a
    hard `budget_s`. Returns a classified :class:`SandboxResult`.

    Defaults (no pin args) pin the FIRST incumbent op at its own placement —
    the latency FLOOR (a trivially feasible re-solve the solver must confirm
    within budget); the CI regression uses this. A caller may pin any op at any
    (resource, start) to price a real drag (R-DP1 literalness).

    ``standing_pins`` are the lineage's ACCEPTED commitments (R-DP8): every one is
    compiled as a hard constraint alongside the new drop, so the re-solve can
    never silently relocate a placement the planner already committed. A drop that
    is infeasible against a standing pin returns an honest INFEASIBLE verdict that
    NAMES the blocking commitment — never a quiet sacrifice of the older pin.
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
    from mre.modules import standing_pins as sp
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

    # CU3: on a rolling schedule, restrict the build to the ACTIVE WINDOW's ops.
    # Beat two ALSO holds the committed frozen front (passed as ``standing_pins``),
    # so it can legitimately contradict beat one (which relaxed them) — the R-T2
    # contradiction, now on a real rolling substrate.
    ops, wps, fuls, demands = _restrict_window(ops, wps, fuls, demands, restrict_op_ids)

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
    # R-T2: the correlation id linking this priced beat two to its beat one.
    corr = correlation_id_for(snapshot_id, pin_op_id, pin_resource_id,
                              pin_start_dt.isoformat())

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
    # R-DP1 (4.0 hotfix): the machine pin binds ONLY when the op is eligible on
    # the target (a literal exists in ``op_assign``). The prior
    # ``if lit is not None: model.add(lit == 1)`` SILENTLY SKIPPED the machine
    # constraint otherwise, so the re-solve kept the op on its cheaper incumbent
    # machine and STILL reported a feasible verdict — a false "OK" for a placement
    # never actually tested (right time, wrong machine). An un-pinnable target is
    # a PROVEN-ILLEGAL placement (R-DP2 return-home), not a happy verdict, so
    # short-circuit to an infeasible verdict before spending the solve budget.
    try:
        sp.apply_pin(model, var_map, pin_op_id, pin_resource_id, pin_start_min)
    except sp.PinUnsatisfiable as exc:
        return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                  pin_start_dt, exc.reason, corr)
    # R-DP8: compile the lineage's ACCEPTED pins as hard constraints too, so the
    # re-solve holds every prior commitment fixed (skip the op being dragged — the
    # new drop re-commits it). A standing pin that cannot bind is a genuine lineage
    # inconsistency → honest infeasible, never a silent skip.
    new_pin = {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
               "start": pin_start_dt.isoformat()}
    try:
        sp.apply_standing_pins(model, var_map, standing_pins, horizon_start,
                               skip_op=pin_op_id)
    except sp.PinUnsatisfiable as exc:
        return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                  pin_start_dt,
                                  f"a standing commitment could not be held: {exc.reason}",
                                  corr)
    standing_ops = sp.standing_pin_ops(standing_pins)

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
    # R-DP8: an INFEASIBLE drop may be blocked by a standing commitment. If a
    # standing pin directly overlaps the drop on its resource, say WHICH decision
    # blocks it (an authored reason), rather than a bare "pin infeasible" — the
    # planner must never be left guessing why their move was refused, nor have an
    # older commitment quietly sacrificed to make room.
    if not feasible and standing_pins:
        conflict = sp.detect_conflict(new_pin, standing_pins, var_map, horizon_start)
        if conflict is not None:
            return _pin_conflict(budget_s, pin_op_id, pin_resource_id,
                                 pin_start_dt, conflict, corr)
    # R-DP1 post-condition (4.0 hotfix): with the machine + time pins now
    # mandatory, a feasible solve MUST place the pinned op exactly where pinned.
    # Belt-and-suspenders against any residual model looseness — if it did not,
    # the verdict would be honest-looking but for the wrong placement, so treat it
    # as unsatisfiable rather than report a delta the drop never earned.
    if feasible:
        solved_res = solve_result.solve_values.op_resource.get(pin_op_id)
        solved_start = solve_result.solve_values.op_start_minutes.get(pin_op_id)
        if solved_res != pin_resource_id or solved_start != pin_start_min:
            return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                      pin_start_dt, "pin did not bind to the target",
                                      corr)
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
            pin_op_id, exclude_ops=standing_ops,
        )
        _annotate_move_reasons(moves, solve_result.solve_values, horizon_start,
                               pin_op_id)

    # The R-T2 beat-two LAYERED card (CU2). One in-memory extract of the re-solve
    # gives the new ledger + per-order service outcomes + drivers; diffed against
    # the base (its persisted summary + service outcomes) yields the always-visible
    # + detail layers, all ledger-backed. Fully guarded → empty/None on any
    # failure so the card degrades to the relative-% headline, never a false figure.
    cost_delta_abs = cost_delta_pct = None
    cost_lines = None
    affected_orders: list[dict] = []
    lateness_delta_min = 0
    dominant_driver: dict = {}
    if feasible:
        card = _priced_card_data(
            reader, solve_result.solve_values, ops, wps, resources, fuls,
            demands, cost_model, var_map, pin_op_id)
        cost_delta_abs = card["cost_delta_abs"]
        cost_delta_pct = card["cost_delta_pct"]
        cost_lines = card["cost_lines"]
        affected_orders = card["affected_orders"]
        lateness_delta_min = card["lateness_delta_min"]
        dominant_driver = card["dominant_driver"]
    # R-T2/R-DP8 standing invariant: a committed/standing-pinned op is structurally
    # excluded from the moved-set (``exclude_ops``), so this is True by
    # construction — but ASSERT it against the actual moves (test pins it).
    no_committed_changes = not any(
        m.get("operation_ref") in standing_ops and not m.get("pinned")
        for m in moves)
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
        delta_pct=delta_pct, delta_abs=delta_abs,
        cost_delta_abs=cost_delta_abs, cost_delta_pct=cost_delta_pct,
        message=message, moves=moves,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
        correlation_id=corr, dominant_driver=dominant_driver,
        affected_orders=affected_orders, lateness_delta_min=lateness_delta_min,
        no_committed_work_changes=no_committed_changes, cost_lines=cost_lines,
    )


def _pin_unsatisfiable(budget_s: float, pin_op_id: str, pin_resource_id: str,
                       pin_start_dt: datetime, why: str,
                       corr: str = "") -> SandboxResult:
    """The pin cannot be honoured by construction (the op has no assignment
    literal for the target resource, or no start variable): the placement is
    PROVEN illegal, so the honest verdict is an infeasible return-home — never a
    silently-skipped machine pin that reports a happy delta (4.0 hotfix, R-DP1)."""
    return SandboxResult(
        outcome=SANDBOX_VERDICT, status="INFEASIBLE", within_budget=True,
        wall_time_s=0.0, budget_s=budget_s, applied_time_limit_s=budget_s,
        feasible=False, objective=None, delta_pct=None, delta_abs=None,
        cost_delta_abs=None, cost_delta_pct=None,
        message=f"this placement isn't possible: {why}",
        moves=[],
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
        correlation_id=corr,
    )


def _pin_conflict(budget_s: float, pin_op_id: str, pin_resource_id: str,
                  pin_start_dt: datetime, conflict, corr: str = "") -> SandboxResult:
    """The drop is infeasible because it OVERLAPS a standing commitment on the
    same resource (R-DP8). An honest infeasible verdict that NAMES the blocking
    decision — the planner sees which commitment is in the way, and the older pin
    is never quietly sacrificed to make room. ``conflict.op_id`` is a canonical
    operation id; the cockpit resolves it to planner vocabulary."""
    return SandboxResult(
        outcome=SANDBOX_VERDICT, status="INFEASIBLE", within_budget=True,
        wall_time_s=0.0, budget_s=budget_s, applied_time_limit_s=budget_s,
        feasible=False, objective=None, delta_pct=None, delta_abs=None,
        cost_delta_abs=None, cost_delta_pct=None,
        message="this placement conflicts with a commitment you already made — "
                "it overlaps a placement you accepted earlier",
        moves=[],
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat(),
             "conflict_op_ref": conflict.op_id,
             "conflict_resource_id": conflict.resource_id},
        correlation_id=corr,
    )


# The named ledger lines the beat-two decomposition reports, in card order. Each
# maps to an extractor cost_ledger / summary_metrics key. total = the sum of
# these four (the extractor's exact decomposition, docs/02 §4.4), so an explicit
# "other" remainder is 0 whenever the ledger fully decomposes — but the card
# always shows it, so a claim the lines cannot back is impossible.
_LEDGER_LINES = (
    ("tardiness", "tardiness_cost"),
    ("setup", "setup_cost"),
    ("production (regular)", "production_regular_cost"),
    ("production (overtime)", "production_overtime_cost"),
)
# How many affected orders the always-visible layer shows (a design token — small,
# so the card leads with the orders a planner actually feels).
_AFFECTED_ORDERS_TOP_N = 4


def _priced_card_data(reader, solve_values, ops, wps, resources, fuls,
                      demands, cost_model, var_map, pin_op_id) -> dict:
    """The R-T2 beat-two LAYERED card data (CU2). ONE in-memory extract of the
    re-solve gives the new ledger + per-order service outcomes + drivers; diffed
    against the base (its persisted summary + service outcomes) yields:

      * cost_delta_abs / cost_delta_pct — the signed total (always-visible);
      * cost_lines — the ledger-line decomposition (detail layer), summing
        EXACTLY to cost_delta_abs (an explicit ``other`` remainder carries any
        residual — rollup_of discipline);
      * affected_orders — top-N by |tardiness delta|, each with its per-Demand
        tardiness ($) + lateness (min) delta (never per-WorkPackage);
      * lateness_delta_min — net tardiness-minutes introduced (+) / recovered (−);
      * dominant_driver — the pinned op's driver, in driver_phrase language,
        HEDGED where the attribution is by price rank (docs/02 §4.2).

    Fully guarded: any failure returns empty/None so the card degrades to the
    relative-% headline, never a false figure."""
    from mre.modules.planner_language import driver_phrase, driver_hedge
    empty = {"cost_delta_abs": None, "cost_delta_pct": None, "cost_lines": None,
             "affected_orders": [], "lateness_delta_min": 0, "dominant_driver": {}}
    try:
        from mre.modules.extractor import Extractor
        schedules = list(reader.iter_entities("schedule"))
        base_sm = schedules[-1].get("summary_metrics", {}) if schedules else {}
        base_total = float(base_sm.get("total_cost", 0.0))
        base_svc = list(reader.iter_entities("serviceoutcome"))
        er = Extractor().extract(
            solve_values=solve_values, snapshot_id="sandbox-cost",
            operations=ops, workpackages=wps, resources=resources,
            fulfillments=fuls, demands=demands, cost_model=cost_model,
            reporter=None, cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible, snapshot_writer=None,
            is_scenario=True, overtime_windows=var_map.overtime_windows,
        )
        new_ledger = er.cost_ledger or {}
        new_total = float(new_ledger.get("total_cost", 0.0))
        if not base_total:
            return empty
        cost_delta_abs = round(new_total - base_total, 2)
        cost_delta_pct = round(cost_delta_abs / base_total * 100.0, 4)

        # cost_lines: named ledger-line deltas + an explicit "other" remainder so
        # the lines sum EXACTLY to cost_delta_abs (rollup_of discipline).
        named_sum = 0.0
        cost_lines: list[dict] = []
        for label, key in _LEDGER_LINES:
            d = round(float(new_ledger.get(key, 0.0)) - float(base_sm.get(key, 0.0)), 2)
            named_sum += d
            cost_lines.append({"line": label, "delta": d})
        other = round(cost_delta_abs - named_sum, 2)
        cost_lines.append({"line": "other placement changes", "delta": other})

        # per-order tardiness/lateness deltas (per-Demand truth from the service
        # outcomes). Resolve work-order names via the identity map.
        idmap = reader.read_identity_map()
        wo_of = _order_name_resolver(idmap)
        base_by_dem = {s.get("demand_ref"): s for s in base_svc}
        affected: list[dict] = []
        lateness_delta = 0
        for s in er.service_outcomes:
            dem = s.get("demand_ref")
            b = base_by_dem.get(dem, {})
            t_new = float(s.get("tardiness_cost", 0.0))
            t_old = float(b.get("tardiness_cost", 0.0))
            l_new = _svc_lateness_min(s)
            l_old = _svc_lateness_min(b)
            lateness_delta += max(0, l_new) - max(0, l_old)
            t_d = round(t_new - t_old, 2)
            l_d = l_new - l_old
            if abs(t_d) < 0.005 and l_d == 0:
                continue
            affected.append({
                "demand_ref": dem, "work_order": wo_of(dem),
                "tardiness_delta": t_d, "lateness_delta_min": l_d,
            })
        affected.sort(key=lambda a: (-abs(a["tardiness_delta"]),
                                     -abs(a["lateness_delta_min"])))
        affected = affected[:_AFFECTED_ORDERS_TOP_N]

        # dominant driver = the pinned op's attribution in the re-solve.
        code = None
        for a in er.assignments:
            if a.get("operation_ref") == pin_op_id:
                code = a.get("driver")
                break
        dominant = {}
        if code:
            dominant = {"code": str(code), "phrase": driver_phrase(code),
                        "hedge": driver_hedge(code)}
        return {"cost_delta_abs": cost_delta_abs, "cost_delta_pct": cost_delta_pct,
                "cost_lines": cost_lines, "affected_orders": affected,
                "lateness_delta_min": lateness_delta, "dominant_driver": dominant}
    except Exception:
        return empty


def beat_two_contradicts(ghost: "FeasibilityGhost | dict",
                         result: "SandboxResult | dict",
                         tolerance_min: int = 1) -> dict:
    """Does beat two (the priced re-solve) CONTRADICT beat one (the feasibility
    ghost)? R-T2(4): a contradiction must be SHOWN, never silently reconciled.

    Two contradiction kinds (the frontend mirrors this pure logic to decide
    ghost-relocate vs snap-back):
      * ``infeasible`` — beat one said feasible but beat two proves it isn't
        (e.g. a committed/standing commitment blocks it, which beat one relaxed);
      * ``moved`` — both feasible, but beat two places the SAME op at a
        materially different (resource, start) than the ghost showed.

    Returns ``{"infeasible": bool, "moved": bool, "contradicts": bool}``."""
    g = ghost.summary() if hasattr(ghost, "summary") else dict(ghost)
    r = result.summary() if hasattr(result, "summary") else dict(result)
    g_feasible = bool(g.get("feasible"))
    r_feasible = bool(r.get("feasible"))
    infeasible = g_feasible and not r_feasible
    moved = False
    if g_feasible and r_feasible:
        pin_op = (g.get("pin") or {}).get("operation_ref")
        ghost_pin = next((p for p in (g.get("placement") or [])
                          if p.get("pinned")), None)
        r_pin = (r.get("pin") or {})
        if ghost_pin and pin_op:
            same_res = ghost_pin.get("resource_id") == r_pin.get("resource_id")
            gs, rs = ghost_pin.get("start"), r_pin.get("start")
            shifted = True
            if gs and rs:
                shifted = abs((_parse_dt(rs) - _parse_dt(gs)).total_seconds()
                              / 60.0) >= tolerance_min
            moved = (not same_res) or shifted
    return {"infeasible": infeasible, "moved": moved,
            "contradicts": infeasible or moved}


def _svc_lateness_min(svc: dict) -> int:
    """Lateness in signed minutes from a service outcome, handling BOTH shapes:
    the extractor's fresh dict (``lateness_minutes``: int) and the persisted
    canonical entity (``lateness``: ISO 8601 duration string, e.g. ``-P2DT12H58M``).
    Negative = early."""
    if svc.get("lateness_minutes") is not None:
        return int(svc["lateness_minutes"])
    raw = svc.get("lateness")
    if raw is None:
        return 0
    from mre.modules.scenario import _parse_duration_minutes
    return int(_parse_duration_minutes(raw) or 0)


def _order_name_resolver(idmap):
    """A demand_ref → work-order (external) name resolver, via the identity map —
    the same source the schedule assembler uses (never an entity attribute)."""
    from mre.modules.schedule_assembler import _ORDER_REF_TYPES, _external_name

    def _wo(demand_ref):
        try:
            return _external_name(idmap, demand_ref, _ORDER_REF_TYPES)
        except Exception:
            return None
    return _wo


def _moved_set(
    solve_values,
    incumbent_placement: dict[str, tuple],
    horizon_start: datetime,
    pin_op_id: str,
    tolerance_min: int = 1,
    exclude_ops: Optional[set[str]] = None,
) -> list[dict]:
    """Compare the re-solve's placements to the incumbent, op by op, and emit
    the displaced set old → new. The pinned op is always included (flagged) so
    the tentative bar is part of the traced change even when only its neighbours
    truly moved. Sorted: pinned first, then largest start shift, so the delta
    card's line items lead with the biggest displacements (R-DP7c).

    ``exclude_ops`` are ops carrying a STANDING commitment (R-DP8): they are held
    fixed by the standing pins, so a committed op can NEVER be a moved consequence
    — it is structurally excluded here (not filtered downstream), the CU2
    guarantee. The freshly-dropped ``pin_op_id`` is exempt from the exclusion: it
    IS the change being shown."""
    exclude = (exclude_ops or set()) - {pin_op_id}

    def _new_placement(op_id: str):
        rid = solve_values.op_resource.get(op_id)
        smin = solve_values.op_start_minutes.get(op_id)
        if rid is None or smin is None:
            return None
        return rid, horizon_start + timedelta(minutes=smin)

    moves: list[dict] = []
    for op_id, (old_rid, old_start) in incumbent_placement.items():
        if op_id in exclude:
            continue
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
