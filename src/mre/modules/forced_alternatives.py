"""Forced-alternative service (docs/07 Phase 3, R-T1a/b): the TRUE price of a
road not taken.

The solution pool (``solution_pool.py``) surfaces the CHEAP alternatives —
near-optimal placements the optimum could just as well have chosen. But under
economically realistic DISTINCT rates the near-optimal pool converges on
machine placement, so pool-only ghosts degrade precisely where machine choice
matters most (the 3.1 multi_route finding). The forced-alternative service
fills that gap: for a selected operation, a targeted re-solve carrying a
"not on the incumbent machine" cut (``add_forced_alternative_cut``),
warm-started from the incumbent under a short time limit, yields the true best
cost of moving THAT op off its machine — or proves the move infeasible this
horizon (R-T1a: "not feasible this horizon" is a renderable answer, stored as
first-class information).

Two build modes share the same per-member machinery (``_solve_alternative``):

  * The PRECOMPUTED build (``build_forced_alternatives``): the selection
    heuristic picks likely-grabbed ops and prices ONE alternative each (the
    solver's single cheapest escape off the incumbent machine). Cheap enough to
    run async post-publish for a batch of ops.
  * The ON-DEMAND build (``build_op_alternatives``, session 3.3 CU1): fired the
    instant a planner grabs an op the precomputed batch missed. It honors
    R-T1a's original language — price EVERY eligible machine for that one op,
    not just one cut — so every road wears a price or a "not feasible this
    horizon" verdict. Guarded by a per-solve time limit and a caller-side
    concurrency cap (``MAX_CONCURRENT_ONDEMAND``, enforced in the API worker).

Each priced result is a pool-member-class document (``annotations.pool`` with
``source="forced_alternative"``) — same registry tables, same
never-in-schedule-listings exclusion, same supersede invalidation as the pool.
Infeasible forced solves carry a verdict and no document.

Selection heuristic (``select_target_ops``, records itself in the docs/04
amendment; it WILL evolve): the at-risk demands — late first, then the tightest
by slack — and their multi-eligible operations (only a multi-eligible op can be
moved off its machine at all), PLUS the top-N most-EXPENSIVE ops overall
(session 3.3 CU1 widening: the biggest-ticket ops are where a cross-machine move
is most likely to buy something, independent of lateness). A budget caps the
count (each target is a full warm-started re-solve; R-T1b names the solve-count
multiplier honestly).

Isolation + laziness posture is identical to the pool: writes only under
``out_dir/alternatives/``; leaves the base snapshot untouched (in-memory
extraction, no snapshot writer, no reporter Decisions); registry indexing is
the caller's job (this module stays registry-free).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mre.modules.solution_pool import (
    _incumbent_objective,
    _m5_horizon,
    _parse_dt,
    _placements,
    _read_evidence,
)

DEFAULT_MEMBER_TIME_LIMIT_S = 10.0
DEFAULT_SEED = 1234
DEFAULT_BUDGET = 4          # max targeted re-solves per precomputed build
# Widening (session 3.3 CU1): how many of the most-expensive ops overall to add
# to the heuristic's candidate list, on top of the at-risk demands' ops. A
# config token — the biggest-ticket ops are the likeliest to reward a move.
DEFAULT_TOP_N_EXPENSIVE = 6
# On-demand pricing (session 3.3 CU1): how many eligible machines to price for a
# freshly-grabbed op, and the per-solve time limit. Both guard the solve bill —
# a grab must not fan out into an unbounded fleet of re-solves.
DEFAULT_ONDEMAND_MAX_MACHINES = 4
DEFAULT_ONDEMAND_TIME_LIMIT_S = 6.0


@dataclass
class ForcedAlternative:
    member_index: int
    target_operation_ref: str
    forbidden_resource_ref: str
    status: str                            # FEASIBLE | OPTIMAL | INFEASIBLE | UNKNOWN
    verdict: str                           # "priced" | "infeasible_this_horizon" | "no_solution"
    objective: Optional[float] = None
    objective_delta_pct: Optional[float] = None
    alternative_resource_ref: Optional[str] = None
    wall_time_s: float = 0.0
    # The applied per-solve time limit (echoed so budget-vs-actual is always
    # inspectable — the same discipline session 3.3 CU5 added to the sandbox).
    time_limit_s: Optional[float] = None
    document_path: Optional[str] = None
    # Compact placement of the MOVED op on its alternative machine — the Tier-1
    # ghost the cockpit renders (a bar at resource+start, wearing the price).
    # Extracted from this member's own solved document so the cockpit needs no
    # full-document fetch to draw the ghost (R-T1a, CU2). Carries work_orders
    # (planner vocabulary, session 3.3 CU2). None for infeasible.
    alternative_placement: Optional[dict] = None


@dataclass
class ForcedAlternativeResult:
    pool_id: str
    base_schedule_id: str
    snapshot_id: str
    status: str                            # ready | empty
    members: list[ForcedAlternative] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    wall_time_s: float = 0.0
    summary_path: Optional[str] = None

    def summary(self) -> dict:
        return asdict(self)

    def priced_cross_machine(self) -> list[ForcedAlternative]:
        """Feasible forced alternatives that actually crossed machines and
        carry a price — the Tier-1 priced-ghost payload."""
        return [m for m in self.members
                if m.verdict == "priced" and m.alternative_resource_ref
                and m.alternative_resource_ref != m.forbidden_resource_ref
                and m.objective_delta_pct is not None]


def _eligible_refs(op: dict) -> list[str]:
    """The explicit eligible set of an operation instance (multi_route uses
    explicit_set). Empty for a single-requirement capability op (resolution
    needs the resource table — v1 selection only needs the count for
    explicit_set data)."""
    reqs = op.get("resource_requirements") or []
    if not reqs:
        return []
    return list(reqs[0].get("resource_refs") or [])


def _incumbent_costs(
    incumbent_assignments: list[dict], cost_model: dict,
) -> dict[str, float]:
    """op_id → reconstructed incumbent production cost (working minutes × the
    incumbent machine's rate). Derived, not read from a canonical attribute —
    the Assignment entity carries no cost field — so it is only a RANKING key
    for the top-N-expensive widening, never surfaced as a priced number."""
    rates: dict[str, float] = cost_model.get("resource_rates", {})
    costs: dict[str, float] = {}
    for a in incumbent_assignments:
        ras = a.get("resource_assignments") or []
        rid = a.get("resource_id") or (ras[0].get("resource_ref") if ras else None)
        windows = (a.get("phase_windows") or {}).get("run") or a.get("run_windows") or []
        if not (rid and windows):
            continue
        working_min = 0.0
        for w in windows:
            s, e = _parse_dt(w["start"]), _parse_dt(w["end"])
            if s and e:
                working_min += (e - s).total_seconds() / 60.0
        costs[a["operation_ref"]] = working_min * rates.get(rid, 0.0)
    return costs


def select_target_ops(
    *,
    operations: list[dict],
    fulfillments: list[dict],
    demands: list[dict],
    service_outcomes: list[dict],
    incumbent_placement: dict[str, tuple],
    budget: int = DEFAULT_BUDGET,
    incumbent_cost: Optional[dict[str, float]] = None,
    top_n_expensive: int = DEFAULT_TOP_N_EXPENSIVE,
) -> list[str]:
    """Heuristic v2 (R-T1b; widened session 3.3 CU1). Three phases, budget-capped:

      A. LATE demands' multi-eligible ops (lateness > 0), late-first — the
         original priority: a move most likely to rescue a missed date.
      B. the top-N most-EXPENSIVE multi-eligible ops overall (the widening) —
         where a cross-machine move is most likely to buy something, whether or
         not the op's demand is late.
      C. the remaining at-risk demands' ops by slack (tightest first) — the
         catch-all so a board with no late demands still gets coverage.

    Only multi-eligible SCHEDULED ops qualify at all (a forced-off-machine cut
    can only move an op with an alternative). Phase B needs ``incumbent_cost``;
    without it (a caller that only has placements) the heuristic degrades to A+C
    — the pre-widening behavior.
    """
    demand_by_id = {d["id"]: d for d in demands}
    svc_by_demand = {s.get("demand_ref"): s for s in service_outcomes}
    op_by_id = {o["id"]: o for o in operations}

    def _movable(oid: str) -> bool:
        op = op_by_id.get(oid)
        return bool(op) and oid in incumbent_placement and len(_eligible_refs(op)) > 1

    def _lateness(demand_id: str) -> float:
        svc = svc_by_demand.get(demand_id, {})
        lateness = svc.get("lateness_minutes")
        if lateness is None:
            from mre.modules.scenario import _parse_duration_minutes as _m
            lateness = _m(svc.get("lateness")) or 0.0
        return float(lateness)

    def _slack(demand_id: str) -> float:
        svc = svc_by_demand.get(demand_id, {})
        due = _parse_dt(demand_by_id.get(demand_id, {}).get("due")) if demand_by_id.get(demand_id, {}).get("due") else None
        proj = svc.get("projected_completion")
        proj_dt = _parse_dt(proj) if proj else None
        return ((due - proj_dt).total_seconds() / 60.0
                if due and proj_dt else float("inf"))

    all_demands = [s.get("demand_ref") for s in service_outcomes if s.get("demand_ref")]
    late = sorted((d for d in all_demands if _lateness(d) > 0),
                  key=lambda d: -_lateness(d))
    not_late = sorted((d for d in all_demands if _lateness(d) <= 0), key=_slack)

    ops_by_wp: dict[str, list[dict]] = {}
    for op in operations:
        ops_by_wp.setdefault(op.get("workpackage_ref", ""), []).append(op)
    wp_by_demand: dict[str, list[str]] = {}
    for f in fulfillments:
        wp_by_demand.setdefault(f.get("demand_ref", ""), []).append(f.get("workpackage_ref", ""))

    picked: list[str] = []
    seen: set[str] = set()

    def _take(oid: str) -> bool:
        if oid in seen or not _movable(oid):
            return False
        seen.add(oid)
        picked.append(oid)
        return len(picked) >= budget

    def _walk_demands(demand_ids) -> bool:
        for demand_id in demand_ids:
            for wp_id in wp_by_demand.get(demand_id, []):
                for op in ops_by_wp.get(wp_id, []):
                    if _take(op["id"]):
                        return True
        return False

    # A. late demands' multi-eligible ops
    if _walk_demands(late):
        return picked
    # B. top-N most-expensive multi-eligible ops overall (the widening)
    if incumbent_cost and top_n_expensive > 0:
        by_cost = sorted((oid for oid in incumbent_cost if _movable(oid)),
                         key=lambda oid: incumbent_cost.get(oid, 0.0), reverse=True)
        for oid in by_cost[:top_n_expensive]:
            if _take(oid):
                return picked
    # C. remaining at-risk demands by slack (the catch-all)
    _walk_demands(not_late)
    return picked


# ---------------------------------------------------------------------------
# Shared solve context + per-member solve (used by both build modes)
# ---------------------------------------------------------------------------

@dataclass
class _AltContext:
    """Everything the per-member solve needs, loaded once from the snapshot."""
    demands: list
    fuls: list
    wps: list
    ops: list
    edges: list
    resources: list
    pools: list
    calendars: list
    constraints: list
    costmodels: list
    service_outcomes: list
    incumbent_assignments: list
    identity_map: Any
    cost_model: dict
    reference_date: Optional[datetime]
    horizon_start: datetime
    horizon_end: datetime
    incumbent_objective: Optional[float]
    flattened_cals: dict
    incumbent_placement: dict
    incumbent_cost: dict
    wp_orders: dict
    solver_workers: Optional[int]


def _load_alt_context(out_dir: Path, snapshot_id: str, runs_subdir: str) -> _AltContext:
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.schedule_assembler import _ORDER_REF_TYPES, _external_name
    from mre.modules.snapshot_store import SnapshotStore

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
    service_outcomes = list(reader.iter_entities("serviceoutcome"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    identity_map = reader.read_identity_map()
    cost_model = costmodels[0] if costmodels else {}

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)
    incumbent_placement = _placements(incumbent_assignments)
    incumbent_cost = _incumbent_costs(incumbent_assignments, cost_model)

    # Work-order names per workpackage (planner vocabulary for ghost labels,
    # CU2). Same source as the schedule assembler: the identity map + the
    # fulfillments, never an entity attribute.
    wp_orders: dict[str, list[str]] = {}
    for ful in fuls:
        name = _external_name(identity_map, ful.get("demand_ref", ""), _ORDER_REF_TYPES)
        if name:
            wp_orders.setdefault(ful.get("workpackage_ref", ""), []).append(name)
    for names in wp_orders.values():
        names.sort()

    return _AltContext(
        demands=demands, fuls=fuls, wps=wps, ops=ops, edges=edges,
        resources=resources, pools=pools, calendars=calendars,
        constraints=constraints, costmodels=costmodels,
        service_outcomes=service_outcomes,
        incumbent_assignments=incumbent_assignments, identity_map=identity_map,
        cost_model=cost_model, reference_date=reference_date,
        horizon_start=horizon_start, horizon_end=horizon_end,
        incumbent_objective=incumbent_objective, flattened_cals=flattened_cals,
        incumbent_placement=incumbent_placement, incumbent_cost=incumbent_cost,
        wp_orders=wp_orders, solver_workers=ctx.get("solver_workers"),
    )


def _solve_alternative(
    actx: _AltContext, *,
    work_dir: Path,
    member_index: int,
    target: str,
    required_resource: Optional[str],
    snapshot_id: str,
    run_id: str,
    base_schedule_id: str,
    pool_id: str,
    member_time_limit_s: float,
    seed: int,
) -> ForcedAlternative:
    """Price one alternative for ``target`` and return its member.

    ``required_resource is None`` → FORBID mode (the precomputed build): forbid
    the incumbent machine, let the solver find its single cheapest escape.
    ``required_resource`` set → REQUIRE mode (the on-demand K' path): pin the op
    to THAT machine exactly, so every eligible machine gets its own true price.
    Either way ``forbidden_resource_ref`` records the incumbent, so the ghost's
    delta reads "the price of moving off the incumbent".
    """
    from mre.contracts.schedule_document import PoolBlock
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.extractor import Extractor
    from mre.modules.schedule_assembler import assemble_schedule_document
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import (
        SolverBuilder,
        add_forced_alternative_cut,
        add_required_resource_cut,
        apply_solution_hints,
    )
    from mre.reporter import Reporter

    m_t0 = time.monotonic()
    forbidden = actx.incumbent_placement[target][0]
    runs_dir = work_dir / f"member_{member_index}_runs"

    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose=f"forced-alt {member_index} model build",
        config={"horizon_start": actx.horizon_start.isoformat(),
                "horizon_end": actx.horizon_end.isoformat(),
                "pool_id": pool_id, "member_index": member_index,
                "target_operation": target, "forbidden_resource": forbidden,
                "required_resource": required_resource},
        trigger="forced_alternative", snapshot_id=snapshot_id, sink_dir=runs_dir,
    )
    model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
        actx.wps + actx.ops + actx.edges, actx.resources + actx.pools,
        actx.flattened_cals, actx.fuls + actx.demands, actx.constraints,
        actx.cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    apply_solution_hints(model, var_map, actx.incumbent_assignments)
    if required_resource is not None:
        applied = add_required_resource_cut(model, var_map, target, required_resource)
    else:
        applied = add_forced_alternative_cut(model, var_map, target, forbidden)

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose=f"forced-alt {member_index} solve",
        config={"time_limit": member_time_limit_s,
                "num_search_workers": actx.solver_workers,
                "random_seed": seed + member_index, "pool_id": pool_id,
                "member_index": member_index, "target_operation": target},
        trigger="forced_alternative", snapshot_id=snapshot_id, sink_dir=runs_dir,
    )
    solve_result = SolveRunner(
        time_limit_seconds=member_time_limit_s,
        num_search_workers=actx.solver_workers,
        random_seed=seed + member_index,
    ).solve(model, var_map, r_rep)
    r_rep.end(RunStatus.SUCCESS
              if solve_result.status in ("OPTIMAL", "FEASIBLE")
              else RunStatus.PARTIAL)

    member = ForcedAlternative(
        member_index=member_index, target_operation_ref=target,
        forbidden_resource_ref=forbidden, status=solve_result.status,
        verdict="no_solution", wall_time_s=round(time.monotonic() - m_t0, 3),
        time_limit_s=member_time_limit_s,
    )
    if not applied:
        # nothing to cut (op had no literal for the incumbent/required machine —
        # e.g. single-eligibility, or not eligible on the required machine):
        # there is no alternative to price.
        member.verdict = "infeasible_this_horizon"
        return member
    if solve_result.status not in ("OPTIMAL", "FEASIBLE"):
        # R-T1a: infeasibility is information — "not feasible this horizon".
        member.verdict = "infeasible_this_horizon"
        return member

    member.objective = solve_result.objective
    if actx.incumbent_objective and actx.incumbent_objective > 0 and solve_result.objective:
        member.objective_delta_pct = round(
            (solve_result.objective - actx.incumbent_objective)
            / actx.incumbent_objective * 100.0, 4)
    member.alternative_resource_ref = solve_result.solve_values.op_resource.get(target)
    member.verdict = "priced"

    extract = Extractor().extract(
        solve_values=solve_result.solve_values,
        snapshot_id=snapshot_id,
        operations=actx.ops, workpackages=actx.wps, resources=actx.resources,
        fulfillments=actx.fuls, demands=actx.demands, cost_model=actx.cost_model,
        reporter=None, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=None,
        overtime_windows=var_map.overtime_windows,
    )
    member.alternative_placement = _placement_of(extract.assignments, target, actx.wp_orders)
    document = assemble_schedule_document(
        snapshot_id=snapshot_id, run_id=run_id,
        schedule=extract.schedule, assignments=extract.assignments,
        service_outcomes=extract.service_outcomes,
        operations=actx.ops, workpackages=actx.wps, fulfillments=actx.fuls,
        demands=actx.demands, resources=actx.resources, pools=actx.pools,
        calendars=actx.calendars, constraints=actx.constraints,
        costmodels=actx.costmodels, identity_map=actx.identity_map,
        evidence_records=_read_evidence(runs_dir),
        pool_block=PoolBlock(
            pool_id=pool_id, base_schedule_id=base_schedule_id,
            member_index=member_index, objective=solve_result.objective,
            objective_delta_pct=member.objective_delta_pct,
            source="forced_alternative",
            target_operation_ref=target,
            forbidden_resource_ref=forbidden,
            alternative_resource_ref=member.alternative_resource_ref,
        ),
    )
    doc_path = work_dir / f"member_{member_index}.json"
    doc_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    member.document_path = str(doc_path)
    return member


def build_forced_alternatives(
    out_dir: Path | str,
    snapshot_id: str,
    base_schedule_id: str,
    run_id: str,
    target_op_ids: Optional[list[str]] = None,
    budget: int = DEFAULT_BUDGET,
    member_time_limit_s: float = DEFAULT_MEMBER_TIME_LIMIT_S,
    seed: int = DEFAULT_SEED,
    runs_subdir: str = "runs",
    pool_id: Optional[str] = None,
    top_n_expensive: int = DEFAULT_TOP_N_EXPENSIVE,
) -> ForcedAlternativeResult:
    """Build the precomputed forced-alternative ghosts for a solved run.

    When ``target_op_ids`` is None the heuristic selects them (at-risk demands'
    multi-eligible ops + the top-N most-expensive, session 3.3 CU1). Each target
    gets ONE warm-started re-solve with its incumbent machine forbidden; the
    result is a pool-member-class document (feasible) or a verdict-only member
    (infeasible). Registry-free — the caller indexes the result.
    """
    t0 = time.monotonic()
    out_dir = Path(out_dir)
    alt_dir = out_dir / "alternatives"
    alt_dir.mkdir(parents=True, exist_ok=True)
    pool_id = pool_id or f"alt-{uuid.uuid4().hex[:12]}"

    actx = _load_alt_context(out_dir, snapshot_id, runs_subdir)

    explicit = target_op_ids is not None
    if not explicit:
        target_op_ids = select_target_ops(
            operations=actx.ops, fulfillments=actx.fuls, demands=actx.demands,
            service_outcomes=actx.service_outcomes,
            incumbent_placement=actx.incumbent_placement, budget=budget,
            incumbent_cost=actx.incumbent_cost, top_n_expensive=top_n_expensive,
        )
    else:
        target_op_ids = [o for o in target_op_ids if o in actx.incumbent_placement][:budget]

    params = {
        "budget": budget, "member_time_limit_s": member_time_limit_s,
        "seed": seed, "incumbent_objective": actx.incumbent_objective,
        "selection": ("explicit" if explicit else "heuristic_v2"),
        "top_n_expensive": top_n_expensive,
        "n_targets": len(target_op_ids),
        "mechanism": (
            "per target op: warm-start hints from incumbent + a "
            "'not on the incumbent machine' cut (add_forced_alternative_cut), "
            "short time limit; no objective bound (the true best price of the "
            "road not taken, even when worse than the incumbent)"
        ),
    }

    members: list[ForcedAlternative] = []
    for i, target in enumerate(target_op_ids):
        members.append(_solve_alternative(
            actx, work_dir=alt_dir, member_index=i, target=target,
            required_resource=None, snapshot_id=snapshot_id, run_id=run_id,
            base_schedule_id=base_schedule_id, pool_id=pool_id,
            member_time_limit_s=member_time_limit_s, seed=seed,
        ))

    result = ForcedAlternativeResult(
        pool_id=pool_id, base_schedule_id=base_schedule_id,
        snapshot_id=snapshot_id,
        status="ready" if any(m.verdict == "priced" for m in members) else "empty",
        members=members, params=params,
        wall_time_s=round(time.monotonic() - t0, 3),
    )
    summary_path = alt_dir / "alternatives.json"
    summary_path.write_text(json.dumps(result.summary(), indent=2, default=str),
                            encoding="utf-8")
    result.summary_path = str(summary_path)
    return result


def build_op_alternatives(
    out_dir: Path | str,
    snapshot_id: str,
    base_schedule_id: str,
    run_id: str,
    op_id: str,
    max_machines: int = DEFAULT_ONDEMAND_MAX_MACHINES,
    member_time_limit_s: float = DEFAULT_ONDEMAND_TIME_LIMIT_S,
    seed: int = DEFAULT_SEED,
    runs_subdir: str = "runs",
    pool_id: Optional[str] = None,
) -> ForcedAlternativeResult:
    """ON-DEMAND (session 3.3 CU1, R-T1a K'): price EVERY eligible machine for a
    single freshly-grabbed op, capped at ``max_machines``.

    Where ``build_forced_alternatives`` forbids the incumbent and takes the
    solver's one cheapest escape, this pins the op to each OTHER eligible
    machine in turn — so every road wears its own true price or a "not feasible
    this horizon" verdict. Fired the instant a planner grabs an op the
    precomputed batch missed; the per-solve time limit and ``max_machines`` cap
    the solve bill, and the API worker adds the concurrency cap across grabs.
    Member documents live under ``alternatives/op_<op8>/`` so they never
    collide with the precomputed batch. Registry-free — the caller appends.
    """
    t0 = time.monotonic()
    out_dir = Path(out_dir)
    op8 = op_id.split("-")[0][:8] if op_id else "op"
    work_dir = out_dir / "alternatives" / f"op_{op8}"
    work_dir.mkdir(parents=True, exist_ok=True)
    pool_id = pool_id or f"alt-{uuid.uuid4().hex[:12]}"

    actx = _load_alt_context(out_dir, snapshot_id, runs_subdir)

    op = next((o for o in actx.ops if o["id"] == op_id), None)
    incumbent = actx.incumbent_placement.get(op_id, (None, None))[0]
    eligible = _eligible_refs(op) if op else []
    machines = [r for r in eligible if r != incumbent][:max_machines]

    params = {
        "op_id": op_id, "incumbent_resource": incumbent,
        "eligible_machines": eligible, "priced_machines": machines,
        "max_machines": max_machines, "member_time_limit_s": member_time_limit_s,
        "seed": seed, "incumbent_objective": actx.incumbent_objective,
        "selection": "on_demand",
        "mechanism": (
            "per eligible machine: warm-start hints from incumbent + a pin to "
            "THAT machine (add_required_resource_cut), short time limit; every "
            "road not taken wears its own true price or an infeasible verdict"
        ),
    }

    members: list[ForcedAlternative] = []
    for i, machine in enumerate(machines):
        members.append(_solve_alternative(
            actx, work_dir=work_dir, member_index=i, target=op_id,
            required_resource=machine, snapshot_id=snapshot_id, run_id=run_id,
            base_schedule_id=base_schedule_id, pool_id=pool_id,
            member_time_limit_s=member_time_limit_s, seed=seed,
        ))

    result = ForcedAlternativeResult(
        pool_id=pool_id, base_schedule_id=base_schedule_id,
        snapshot_id=snapshot_id,
        status="ready" if any(m.verdict == "priced" for m in members) else "empty",
        members=members, params=params,
        wall_time_s=round(time.monotonic() - t0, 3),
    )
    summary_path = work_dir / "alternatives.json"
    summary_path.write_text(json.dumps(result.summary(), indent=2, default=str),
                            encoding="utf-8")
    result.summary_path = str(summary_path)
    return result


def _placement_of(
    assignments: list[dict], op_id: str,
    wp_orders: Optional[dict[str, list[str]]] = None,
) -> Optional[dict]:
    """The compact ghost placement of one op in an extracted schedule:
    {resource_id, start, end, work_orders}. Reads the extractor dict shape
    (resource_assignments + phase_windows.run). ``work_orders`` is resolved from
    the workpackage → order-name map (planner vocabulary, CU2) — the extractor's
    assignment dict carries none. None if the op is absent."""
    wp_orders = wp_orders or {}
    for a in assignments:
        if a.get("operation_ref") != op_id:
            continue
        ras = a.get("resource_assignments") or []
        rid = a.get("resource_id") or (ras[0].get("resource_ref") if ras else None)
        windows = (a.get("phase_windows") or {}).get("run") or a.get("run_windows") or []
        if not (rid and windows):
            return None
        return {
            "resource_id": rid,
            "start": windows[0]["start"],
            "end": windows[-1]["end"],
            "work_orders": a.get("work_orders")
            or wp_orders.get(a.get("workpackage_ref", ""), []),
        }
    return None


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
