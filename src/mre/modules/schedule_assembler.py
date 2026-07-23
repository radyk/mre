"""Schedule-document assembler: canonical snapshot + evidence → ScheduleDocument.

Pure derivation — no solver imports, no writes. Every document field maps to
an existing source:

  schedule_id / status / cost figures   Schedule entity (summary_metrics)
  assignments / chunks                  Assignment entities (phase_windows.run)
  in_overtime_min                       the assignment Decision's chosen payload
  service_outcomes                      ServiceOutcome + Demand entities
  work_orders / external names          the identity map (never entity attrs)
  solver telemetry                      M6 run evidence (solve_complete event
                                        + RunContext config)
  reference_date / horizon              M3 / M5 RunContext config
  locks                                 Constraint entities (frozen/pinned)

The assembler is deterministic: all lists are sorted, so a document rebuilt
from the same persisted run equals the one built at extraction time
(round-trip tested).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.schedule_document import (
    Annotations,
    AssignmentBlock,
    BeyondHorizonItem,
    CalendarWindow,
    Chunk,
    CONTRACT_VERSION,
    CostSummary,
    HorizonBlock,
    InteractionBlock,
    OperationInteraction,
    Phases,
    PhaseWindow,
    PoolBlock,
    PrecedenceEdgeBlock,
    ResourceLane,
    RollingBlock,
    ScenarioBlock,
    ScheduleDocument,
    ServiceOutcomeBlock,
    SolverBlock,
)
from mre.contracts.vocabularies import ScheduleStatus
from mre.modules.calendar_utils import flatten_calendar
from mre.modules.scenario import _parse_duration_minutes as _iso_minutes

UTC = timezone.utc

# External-ref types that carry each vocabulary, across adapters
# (sample/ERP uses work_order + machine_id; IDS uses order_id + resource_id).
_ORDER_REF_TYPES = ("work_order", "order_id")
_RESOURCE_REF_TYPES = ("machine_id", "resource_id")
_POOL_REF_TYPES = ("pool_id", "workcenter_id", "workcenter")
_FACILITY_REF_TYPES = ("facility", "facility_id")
_CUSTOMER_REF_TYPES = ("customer_id", "customer")

_LOCK_CONSTRAINT_TYPES = ("frozen_assignment", "pinned_window")


def assemble_schedule_document(
    *,
    snapshot_id: str,
    run_id: str,
    schedule: dict,
    assignments: list[dict],
    service_outcomes: list[dict],
    operations: list[dict],
    workpackages: list[dict],
    fulfillments: list[dict],
    demands: list[dict],
    resources: list[dict],
    pools: list[dict],
    calendars: list[dict],
    constraints: list[dict],
    costmodels: list[dict],
    identity_map: Any = None,
    evidence_records: Optional[list[dict]] = None,
    parent_schedule_id: Optional[str] = None,
    pool_block: Optional[PoolBlock] = None,
    edges: Optional[list[dict]] = None,
    standing_pin_ops: Optional[set[str]] = None,
) -> ScheduleDocument:
    """Assemble the versioned schedule document. Entity args are persisted
    entity dicts (SnapshotReader shape); evidence_records are the run's raw
    JSONL records.

    ``standing_pin_ops`` are the operation ids carrying a STANDING commitment on
    this version's lineage (R-DP8 CU2): their assignment blocks are marked
    ``standing_pin=True`` so the cockpit renders a subtle standing-pin marker and
    knows never to list them as a moved consequence.

    ``edges`` are PrecedenceEdge entity dicts. When provided, the contract-1.2
    ``interaction`` block is built (the Tier-0 client-side legality payload);
    when None (pool members, pre-1.2 callers) ``interaction`` stays None and
    1.1 consumers are unaffected."""
    evidence = evidence_records or []
    ops_by_id = {o["id"]: o for o in operations}
    demands_by_id = {d["id"]: d for d in demands}
    decisions_by_id = {
        r["record_id"]: r for r in evidence if r.get("record_type") == "decision"
    }

    # ------------------------------------------------------------------
    # Evidence-derived blocks: solver telemetry, reference date, horizon
    # ------------------------------------------------------------------
    solver = _solver_block(evidence)
    reference_date = _reference_date(evidence)
    horizon = _horizon_block(evidence)

    # ------------------------------------------------------------------
    # Cost summary from the Schedule entity's summary_metrics
    # ------------------------------------------------------------------
    sm = schedule.get("summary_metrics", {})
    production = float(sm.get("production_cost", 0.0))
    cost_summary = CostSummary(
        total=float(sm.get("total_cost", 0.0)),
        production_regular=float(sm.get("production_regular_cost", production)),
        production_overtime=float(sm.get("production_overtime_cost", 0.0)),
        setup=float(sm.get("setup_cost", 0.0)),
        tardiness=float(sm.get("tardiness_cost", 0.0)),
        costmodel_version=_costmodel_version(schedule, costmodels),
    )

    # ------------------------------------------------------------------
    # Work-order names per workpackage (merged WPs list every order)
    # ------------------------------------------------------------------
    wp_orders: dict[str, list[str]] = {}
    for ful in fulfillments:
        wp_id = ful.get("workpackage_ref", "")
        name = _external_name(identity_map, ful.get("demand_ref", ""), _ORDER_REF_TYPES)
        if name:
            wp_orders.setdefault(wp_id, []).append(name)
    for names in wp_orders.values():
        names.sort()

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------
    pinned_ops = standing_pin_ops or set()
    asgn_blocks: list[AssignmentBlock] = []
    for asgn in assignments:
        op = ops_by_id.get(asgn.get("operation_ref", ""), {})
        chunks = _chunks(asgn)
        resource_id = _assigned_resource(asgn)
        op_ref = asgn.get("operation_ref", "")
        asgn_blocks.append(AssignmentBlock(
            assignment_id=asgn["id"],
            operation_ref=op_ref,
            workpackage_ref=asgn.get("workpackage_ref", ""),
            work_orders=wp_orders.get(asgn.get("workpackage_ref", ""), []),
            op_seq=int(op.get("sequence", 0)),
            setup_family=op.get("setup_family", "") or "",
            resource_id=resource_id,
            external_name=_external_name(identity_map, resource_id, _RESOURCE_REF_TYPES),
            chunks=chunks,
            phases=_phases(op, chunks),
            in_overtime_min=_overtime_minutes(asgn, decisions_by_id),
            decision_ref=asgn.get("decision_ref", "") or "",
            standing_pin=op_ref in pinned_ops,
        ))
    asgn_blocks.sort(key=lambda a: (
        a.chunks[0].start.isoformat() if a.chunks else "",
        a.operation_ref,
    ))

    # ------------------------------------------------------------------
    # Service outcomes (per Demand, via Fulfillments)
    # ------------------------------------------------------------------
    svc_blocks: list[ServiceOutcomeBlock] = []
    for svc in service_outcomes:
        demand = demands_by_id.get(svc.get("demand_ref", ""), {})
        lateness = svc.get("lateness_minutes")
        if lateness is None:
            lateness = _iso_minutes(svc.get("lateness")) or 0.0
        customer_ref = demand.get("customer_ref")
        # Demand.quantity is a Quantity {value, uom} (dict in the snapshot).
        qraw = demand.get("quantity")
        qty = qraw.get("value") if isinstance(qraw, dict) else qraw
        quom = qraw.get("uom") if isinstance(qraw, dict) else None
        svc_blocks.append(ServiceOutcomeBlock(
            demand_ref=svc.get("demand_ref", ""),
            work_order=_external_name(identity_map, svc.get("demand_ref", ""), _ORDER_REF_TYPES),
            customer_ref=customer_ref,
            # Resolve the customer to its external vocabulary (1.6) so the job-card
            # hover never renders a UUID; None when there's no customer or it does
            # not resolve through the identity map.
            customer_name=(_external_name(identity_map, customer_ref, _CUSTOMER_REF_TYPES)
                           if customer_ref else None),
            quantity=float(qty) if qty is not None else None,
            quantity_uom=quom,
            due=_parse_dt(demand.get("due")),
            projected_completion=_parse_dt(svc.get("projected_completion")),
            lateness_min=int(lateness),
            tardiness_cost=float(svc.get("tardiness_cost", 0.0)),
        ))
    svc_blocks.sort(key=lambda s: (s.work_order or "", s.demand_ref))

    # ------------------------------------------------------------------
    # Resource lanes with flattened calendar windows
    # ------------------------------------------------------------------
    cals_by_id = {c["id"]: c for c in calendars}
    # Row intelligence (1.6 CU4): per-row booked-through + next-open-gap, computed
    # over the SAME flattened minute windows the solver's eligibility uses, never
    # from anything rendered. See row_intelligence.py.
    row_booked, row_gap = _row_intelligence(
        asgn_blocks, resources, cals_by_id, horizon, reference_date)
    lanes: list[ResourceLane] = []
    for res in resources:
        rid = res["id"]
        pool_name = None
        pool_refs = res.get("pool_refs") or []
        if pool_refs:
            pool_name = _external_name(identity_map, pool_refs[0], _POOL_REF_TYPES) or pool_refs[0]
        lanes.append(ResourceLane(
            resource_id=rid,
            external_name=_external_name(identity_map, rid, _RESOURCE_REF_TYPES),
            facility=_external_name(identity_map, rid, _FACILITY_REF_TYPES),
            pool=pool_name,
            calendar_windows=_calendar_windows(
                cals_by_id.get(res.get("calendar_ref") or ""), horizon
            ),
            booked_through=row_booked.get(rid),
            next_open_gap=row_gap.get(rid),
        ))
    lanes.sort(key=lambda r: (r.external_name or "", r.resource_id))

    # ------------------------------------------------------------------
    # Annotations: locks + scenario lineage
    # ------------------------------------------------------------------
    locks = sorted(
        _render_lock(con, identity_map)
        for con in constraints
        if con.get("constraint_type") in _LOCK_CONSTRAINT_TYPES
    )
    is_scenario = bool(sm.get("is_scenario", False))

    # ------------------------------------------------------------------
    # Interaction payload (contract 1.2): Tier-0 legality arithmetic,
    # client-side. Built only when precedence edges are supplied.
    # ------------------------------------------------------------------
    interaction = _interaction_block(
        edges, asgn_blocks, ops_by_id, resources,
        fulfillments, demands_by_id, workpackages, calendars, horizon,
    ) if edges is not None else None

    return ScheduleDocument(
        schedule_id=schedule["id"],
        snapshot_id=snapshot_id,
        run_id=run_id,
        status=ScheduleStatus(schedule.get("status", "proposed")),
        reference_date=reference_date,
        horizon=horizon,
        solver=solver,
        cost_summary=cost_summary,
        resources=lanes,
        assignments=asgn_blocks,
        service_outcomes=svc_blocks,
        annotations=Annotations(
            locks=locks,
            scenario=ScenarioBlock(
                is_scenario=is_scenario,
                parent_schedule_id=parent_schedule_id,
            ),
            pool=pool_block,
        ),
        interaction=interaction,
    )


def build_document_from_run(
    out_dir: Path | str,
    snapshot_id: str,
    run_id: str,
    runs_subdir: str = "runs",
    parent_schedule_id: Optional[str] = None,
    standing_pin_ops: Optional[set[str]] = None,
) -> ScheduleDocument:
    """Rebuild the document from a persisted pipeline run directory.

    Reads the snapshot's entities + identity map and the evidence JSONL
    under ``out_dir/<runs_subdir>/``, then calls the pure assembler.
    ``standing_pin_ops`` (R-DP8) marks the lineage's committed ops.
    """
    from mre.modules.snapshot_store import SnapshotStore

    out_dir = Path(out_dir)
    reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)

    schedules = list(reader.iter_entities("schedule"))
    if not schedules:
        raise ValueError(f"Snapshot '{snapshot_id}' contains no schedule entity")

    evidence: list[dict] = []
    runs_dir = out_dir / runs_subdir
    if runs_dir.exists():
        for f in sorted(runs_dir.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    evidence.append(json.loads(line))

    return assemble_schedule_document(
        snapshot_id=snapshot_id,
        run_id=run_id,
        schedule=schedules[-1],
        assignments=list(reader.iter_entities("assignment")),
        service_outcomes=list(reader.iter_entities("serviceoutcome")),
        operations=list(reader.iter_entities("operation")),
        workpackages=list(reader.iter_entities("workpackage")),
        fulfillments=list(reader.iter_entities("fulfillment")),
        demands=list(reader.iter_entities("demand")),
        resources=list(reader.iter_entities("resource")),
        pools=list(reader.iter_entities("resourcepool")),
        calendars=list(reader.iter_entities("calendar")),
        constraints=list(reader.iter_entities("constraint")),
        costmodels=list(reader.iter_entities("costmodel")),
        identity_map=reader.read_identity_map(),
        evidence_records=evidence,
        parent_schedule_id=parent_schedule_id,
        edges=list(reader.iter_entities("precedenceedge")),
        standing_pin_ops=standing_pin_ops,
    )


# ---------------------------------------------------------------------------
# CU1 (Session 4B.3a) — the ROLLING (sliced) document.
#
# A monolithic solve → assemble_schedule_document (above). A rolling-horizon solve
# (pilot_scale, R-SC2) → assemble_rolling_document: it renders the plant AS OF the
# reference origin from a RollingView (the current window). Same contract, same
# ResourceLane / AssignmentBlock / ServiceOutcomeBlock shapes; the additions are
# each bar's commitment_state and the document-level RollingBlock (window metadata
# + the beyond-horizon tray). The COMPLETENESS INVARIANT is enforced here: every
# schedulable demand appears exactly once (committed / active / beyond / — for a
# gate exclusion — certificate-visible), or assembly RAISES rather than ship a
# document where known work is silently invisible (the Glass Box cardinal danger).
# ---------------------------------------------------------------------------

_ROLLING_SHIFT_MIN = 720   # nominal working minutes/day (mirrors rolling_horizon)


def _earliest_window_estimate(demand: dict, working_min: int,
                              ref: datetime) -> Optional[datetime]:
    """A CHEAP, honest estimate of when this beyond-horizon work must first enter
    a scheduling window: its latest-feasible-start (due − ceil(working-days)),
    clamped to the reference origin. None when no due date exists — an estimate is
    only offered when it can be derived, never invented."""
    due = _parse_dt(demand.get("due"))
    if due is None:
        return None
    days = max(1, -(-max(0, working_min) // _ROLLING_SHIFT_MIN))   # ceil working days
    est = due - timedelta(days=days)
    return est if est > ref else ref


def assemble_rolling_document(
    *,
    plant: Any,
    view: Any,
    schedule_id: str,
    run_id: str,
    identity_map: Any = None,
) -> ScheduleDocument:
    """Assemble a contract-1.7 rolling document from a PreparedPlant + a
    RollingView (rolling_horizon.build_rolling_view). ``plant`` and ``view`` are
    duck-typed (attribute access only) to avoid a solver-module import cycle."""
    ref = view.reference_origin
    horizon = HorizonBlock(start=ref, end=view.window_end + timedelta(days=21))

    ops_by_id = {o["id"]: o for o in plant.operations}
    demands_by_id = {d["id"]: d for d in plant.demands}

    # work-order names per workpackage (merged WPs list every order)
    wp_orders: dict[str, list[str]] = {}
    for ful in plant.fulfillments:
        wp_id = ful.get("workpackage_ref", "")
        name = _external_name(identity_map, ful.get("demand_ref", ""), _ORDER_REF_TYPES)
        if name:
            wp_orders.setdefault(wp_id, []).append(name)
    for names in wp_orders.values():
        names.sort()

    # ---- assignments: one bar per placed op, with commitment_state ----------
    placed = view.placed                       # committed ∪ active
    committed_ops = set(view.committed)
    asgn_blocks: list[AssignmentBlock] = []
    for oid, pl in placed.items():
        op = ops_by_id.get(oid, {})
        start = _parse_dt(pl["start"])
        end = _parse_dt(pl["end"])
        chunks = [Chunk(chunk_seq=1, start=start, end=end,
                        working_min=int((end - start).total_seconds() // 60))]
        wp_ref = op.get("workpackage_ref", "")
        asgn_blocks.append(AssignmentBlock(
            assignment_id=f"rasgn-{oid}",
            operation_ref=oid,
            workpackage_ref=wp_ref,
            work_orders=wp_orders.get(wp_ref, []),
            op_seq=int(op.get("sequence", 0)),
            setup_family=op.get("setup_family", "") or "",
            resource_id=pl["resource"],
            external_name=_external_name(identity_map, pl["resource"], _RESOURCE_REF_TYPES),
            chunks=chunks,
            phases=_phases(op, chunks),
            commitment_state="committed" if oid in committed_ops else "active_window",
        ))
    asgn_blocks.sort(key=lambda a: (
        a.chunks[0].start.isoformat() if a.chunks else "", a.operation_ref))

    # ---- service outcomes for the placed (in-window) demands ----------------
    svc_blocks: list[ServiceOutcomeBlock] = []
    for svc in view.service_outcomes:
        demand = demands_by_id.get(svc.get("demand_ref", ""), {})
        lateness = svc.get("lateness_minutes")
        if lateness is None:
            lateness = _iso_minutes(svc.get("lateness")) or 0.0
        customer_ref = demand.get("customer_ref")
        qraw = demand.get("quantity")
        qty = qraw.get("value") if isinstance(qraw, dict) else qraw
        quom = qraw.get("uom") if isinstance(qraw, dict) else None
        svc_blocks.append(ServiceOutcomeBlock(
            demand_ref=svc.get("demand_ref", ""),
            work_order=_external_name(identity_map, svc.get("demand_ref", ""), _ORDER_REF_TYPES),
            customer_ref=customer_ref,
            customer_name=(_external_name(identity_map, customer_ref, _CUSTOMER_REF_TYPES)
                           if customer_ref else None),
            quantity=float(qty) if qty is not None else None,
            quantity_uom=quom,
            due=_parse_dt(demand.get("due")),
            projected_completion=_parse_dt(svc.get("projected_completion")),
            lateness_min=int(lateness),
            tardiness_cost=float(svc.get("tardiness_cost", 0.0)),
        ))
    svc_blocks.sort(key=lambda s: (s.work_order or "", s.demand_ref))

    # ---- resource lanes -----------------------------------------------------
    cals_by_id = {c["id"]: c for c in plant.calendars}
    resources_by_id = {r["id"]: r for r in plant.resources}
    lanes: list[ResourceLane] = []
    for res in plant.resources:
        rid = res["id"]
        pool_name = None
        pool_refs = res.get("pool_refs") or []
        if pool_refs:
            pool_name = _external_name(identity_map, pool_refs[0], _POOL_REF_TYPES) or pool_refs[0]
        lanes.append(ResourceLane(
            resource_id=rid,
            external_name=_external_name(identity_map, rid, _RESOURCE_REF_TYPES),
            facility=_external_name(identity_map, rid, _FACILITY_REF_TYPES),
            pool=pool_name,
            calendar_windows=_calendar_windows(
                cals_by_id.get(res.get("calendar_ref") or ""), horizon),
        ))
    lanes.sort(key=lambda r: (r.external_name or "", r.resource_id))

    # ---- the beyond-horizon tray + window metadata --------------------------
    working_min_of = getattr(plant, "demand_working_minutes", {}) or {}
    beyond: list[BeyondHorizonItem] = []
    for did in view.beyond_demand_ids:
        d = demands_by_id.get(did, {})
        customer_ref = d.get("customer_ref")
        beyond.append(BeyondHorizonItem(
            demand_ref=did,
            work_order=_external_name(identity_map, did, _ORDER_REF_TYPES),
            customer_name=(_external_name(identity_map, customer_ref, _CUSTOMER_REF_TYPES)
                           if customer_ref else None),
            due=_parse_dt(d.get("due")),
            earliest_window_estimate=_earliest_window_estimate(
                d, int(working_min_of.get(did, 0)), ref),
        ))
    beyond.sort(key=lambda b: (b.due or datetime.max.replace(tzinfo=UTC), b.work_order or "", b.demand_ref))

    rolling = RollingBlock(
        reference_origin=ref,
        window_start=view.window_start, window_end=view.window_end,
        frozen_until=view.frozen_end,
        window_days=view.window_days, frozen_days=view.frozen_days,
        committed_count=len(view.committed), active_count=len(view.active),
        beyond_horizon=beyond,
    )

    # ---- COMPLETENESS INVARIANT (the anti-silent-exclusion clause) ----------
    # Every schedulable demand appears exactly once — as a placed bar's demand, a
    # beyond-horizon tray entry, or (a gate exclusion) a certificate-visible one.
    _assert_rolling_completeness(plant, view, beyond)

    # ---- interaction payload for the ACTIVE WINDOW (contract 1.8, CU2) -------
    # The SAME Tier-0 legality arithmetic the monolithic board carries, computed
    # for the ACTIVE-WINDOW ops only — so committed (frozen-front) bars carry NO
    # interaction op and are therefore non-targets BY CONSTRUCTION (the gesture
    # surface only builds targets for ops in the payload), exactly as the
    # beyond-horizon tray is. Occupancy still comes from assignments[] (all placed
    # bars, committed included), so committed work blocks a drop; and beat one is a
    # real feasibility solve that holds precedence, so any Tier-0 permissiveness is
    # caught downstream (R-DP6 backstop).
    active_asgn = [a for a in asgn_blocks if a.commitment_state == "active_window"]
    interaction = _interaction_block(
        plant.edges, active_asgn, ops_by_id, plant.resources,
        plant.fulfillments, demands_by_id, plant.workpackages,
        plant.calendars, horizon,
    )

    # ---- cost summary (decomposes exactly) ----------------------------------
    led = view.cost_ledger or {}
    cost_summary = CostSummary(
        total=float(led.get("total_cost", 0.0)),
        production_regular=float(led.get("production_regular_cost",
                                         led.get("production_cost", 0.0))),
        production_overtime=float(led.get("production_overtime_cost", 0.0)),
        setup=float(led.get("setup_cost", 0.0)),
        tardiness=float(led.get("tardiness_cost", 0.0)),
    )

    solver = SolverBlock(status=view.status, deterministic=True)

    return ScheduleDocument(
        contract_version=CONTRACT_VERSION,
        schedule_id=schedule_id, snapshot_id=plant.snapshot_id, run_id=run_id,
        status=ScheduleStatus.PROPOSED,
        reference_date=ref, horizon=horizon, solver=solver,
        cost_summary=cost_summary,
        resources=lanes, assignments=asgn_blocks, service_outcomes=svc_blocks,
        annotations=Annotations(),
        interaction=interaction,
        rolling=rolling,
    )


def _assert_rolling_completeness(plant, view, beyond) -> None:
    """Enforce the 1.7 completeness invariant: the union of placed demands,
    beyond-horizon demands, and gate-excluded demands must cover EVERY demand in
    the snapshot, and the placed/beyond sets must not overlap. A demand in none of
    these buckets, or in two at once, is a defect — raise rather than ship a
    silently-incomplete document."""
    all_demand_ids = {d["id"] for d in plant.demands}
    excluded = set(getattr(plant, "excluded_demand_ids", set()) or set())
    # placed demands = those carrying a bar this window, derived from the placed
    # ops' workpackages (the source of truth), not the service outcomes.
    wp_of_op = {o["id"]: o.get("workpackage_ref", "") for o in plant.operations}
    dem_of_wp: dict[str, list[str]] = {}
    for f in plant.fulfillments:
        dem_of_wp.setdefault(f.get("workpackage_ref", ""), []).append(f.get("demand_ref", ""))
    placed_demand_ids: set[str] = set()
    for oid in view.placed:
        for did in dem_of_wp.get(wp_of_op.get(oid, ""), []):
            placed_demand_ids.add(did)
    beyond_ids = {b.demand_ref for b in beyond}

    overlap = placed_demand_ids & beyond_ids
    if overlap:
        raise ValueError(
            f"rolling completeness: {len(overlap)} demand(s) both placed AND "
            f"beyond-horizon (e.g. {sorted(overlap)[:3]})")
    covered = placed_demand_ids | beyond_ids | excluded
    schedulable = all_demand_ids - excluded
    missing = schedulable - placed_demand_ids - beyond_ids
    if missing:
        raise ValueError(
            f"rolling completeness: {len(missing)} schedulable demand(s) appear in "
            f"NO bucket (committed/active/beyond/excluded) — silent exclusion "
            f"(e.g. {sorted(missing)[:3]})")
    _ = covered  # (documents the full cover; the two checks above are the teeth)


# ---------------------------------------------------------------------------
# Evidence readers
# ---------------------------------------------------------------------------

def _latest_run_open(evidence: list[dict], module: str, purpose_excludes: str = "") -> dict:
    opens = [
        r for r in evidence
        if r.get("record_type") == "run_context_open" and r.get("module") == module
        and (not purpose_excludes or purpose_excludes not in (r.get("purpose") or ""))
    ]
    opens.sort(key=lambda r: r.get("started_at", ""))
    return opens[-1] if opens else {}

def _solver_block(evidence: list[dict]) -> SolverBlock:
    m6 = _latest_run_open(evidence, "M6")
    cfg = m6.get("config_snapshot") or {}
    deterministic = (
        cfg.get("num_search_workers") == 1 and cfg.get("random_seed") is not None
    )
    complete = [
        r for r in evidence
        if r.get("record_type") == "event"
        and r.get("status_text") == "solve_complete"
        and r.get("run_id") == m6.get("run_id")
    ]
    if not complete:
        raise ValueError(
            "No solve_complete event in evidence for the M6 run — cannot "
            "derive solver telemetry (pre-contract run?)"
        )
    p = complete[-1].get("payload", {})
    return SolverBlock(
        status=p.get("status", "UNKNOWN"),
        objective=p.get("objective"),
        gap=p.get("gap"),
        wall_time_s=float(p.get("wall_time_s", 0.0)),
        deterministic=deterministic,
    )

def _reference_date(evidence: list[dict]) -> Optional[datetime]:
    m3 = _latest_run_open(evidence, "M3")
    raw = (m3.get("config_snapshot") or {}).get("reference_date")
    if not raw or raw == "now":
        return None
    return _parse_dt(raw)

def _horizon_block(evidence: list[dict]) -> Optional[HorizonBlock]:
    m5 = _latest_run_open(evidence, "M5")
    cfg = m5.get("config_snapshot") or {}
    start, end = cfg.get("horizon_start"), cfg.get("horizon_end")
    if not start or not end:
        return None
    return HorizonBlock(start=_parse_dt(start), end=_parse_dt(end))


# ---------------------------------------------------------------------------
# Entity-derivation helpers
# ---------------------------------------------------------------------------

def _external_name(identity_map: Any, canonical_id: str, ref_types: tuple) -> Optional[str]:
    if identity_map is None or not canonical_id:
        return None
    for ref in identity_map.external_refs(canonical_id):
        if ref.type in ref_types:
            return ref.value
    return None

def _assigned_resource(asgn: dict) -> str:
    # Persisted entity shape (resource_assignments) or extractor dict shape
    if asgn.get("resource_id"):
        return asgn["resource_id"]
    ras = asgn.get("resource_assignments") or []
    return ras[0].get("resource_ref", "") if ras else ""

def _chunks(asgn: dict) -> list[Chunk]:
    pw = asgn.get("phase_windows") or {}
    windows = pw.get("run") or asgn.get("run_windows") or []
    out: list[Chunk] = []
    for w in sorted(windows, key=lambda w: w.get("start", "")):
        start, end = _parse_dt(w.get("start")), _parse_dt(w.get("end"))
        out.append(Chunk(
            chunk_seq=len(out) + 1,
            start=start,
            end=end,
            working_min=int((end - start).total_seconds() // 60),
        ))
    return out

def _phases(op: dict, chunks: list[Chunk]) -> Phases:
    """Setup occupies the first setup_duration minutes of the first chunk
    (the solver models the operation as setup + run contiguous from its
    start). Teardown is not modeled — always null."""
    setup_min = _iso_minutes(op.get("setup_duration")) or 0.0
    if setup_min <= 0 or not chunks:
        return Phases()
    first = chunks[0]
    setup_end = min(first.start + timedelta(minutes=setup_min), first.end)
    return Phases(setup=PhaseWindow(start=first.start, end=setup_end))

def _overtime_minutes(asgn: dict, decisions_by_id: dict[str, dict]) -> int:
    # Source-of-truth order (2026-07-13 ruling, docs/01 §6.9): the Assignment
    # entity's overtime_minutes attribute is authoritative — the extractor
    # persists it with derived provenance. The assignment Decision's chosen
    # payload is narrative context only; it remains here solely as a
    # fallback for snapshots persisted before the attribute existed.
    if asgn.get("overtime_minutes") is not None:
        return int(asgn["overtime_minutes"])
    dec = decisions_by_id.get(asgn.get("decision_ref", ""))
    if dec and isinstance(dec.get("chosen"), dict):
        return int(dec["chosen"].get("overtime_minutes", 0))
    return 0

def _costmodel_version(schedule: dict, costmodels: list[dict]) -> int:
    cm_ref = schedule.get("costmodel_ref", "")
    for cm in costmodels:
        if cm.get("id") == cm_ref:
            return int(cm.get("version", 1))
    return 1

def _calendar_windows(cal: Optional[dict], horizon: Optional[HorizonBlock]) -> list[CalendarWindow]:
    """Flatten one calendar into typed windows over the document horizon:
    base-pattern shifts (minus closed days) → regular; 'added' exceptions →
    overtime when reason=overtime, else regular; 'closure' exceptions →
    closure (rendered so the Gantt can shade downtime)."""
    if cal is None or horizon is None:
        return []
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import (
        CalendarExceptionReason, CalendarExceptionType,
    )

    closures: list[CalendarException] = []
    out: list[CalendarWindow] = []
    for e in cal.get("exceptions", []):
        if not (isinstance(e, dict) and "window" in e):
            continue
        w_start, w_end = _parse_dt(e["window"]["start"]), _parse_dt(e["window"]["end"])
        kind = e.get("type", "closure")
        reason = e.get("reason", "planned_maintenance") if kind == "closure" else e.get("reason")
        if kind == "closure":
            closures.append(CalendarException(
                window=TimeWindow(start=w_start, end=w_end),
                type=CalendarExceptionType.CLOSURE,
                reason=CalendarExceptionReason(reason),
            ))
            if w_end > horizon.start and w_start < horizon.end:
                # Carry the exception reason (1.6) so the cockpit can shade a
                # planned-maintenance closure distinctly and name it in the hover.
                out.append(CalendarWindow(
                    start=w_start, end=w_end, kind="closure", reason=reason))
        else:  # added capacity
            if w_end > horizon.start and w_start < horizon.end:
                is_ot = e.get("reason") == "overtime"
                out.append(CalendarWindow(
                    start=w_start, end=w_end,
                    kind="overtime" if is_ot else "regular",
                    reason=(e.get("reason") if is_ot else None),
                ))

    for w in flatten_calendar(cal.get("base_pattern", {}), closures,
                              horizon.start, horizon.end):
        out.append(CalendarWindow(start=w.start, end=w.end, kind="regular"))

    out.sort(key=lambda w: (w.start.isoformat(), w.kind))
    return out

def _row_intelligence(
    asgn_blocks: list[AssignmentBlock],
    resources: list[dict],
    cals_by_id: dict[str, dict],
    horizon: Optional[HorizonBlock],
    reference_date: Optional[datetime],
) -> tuple[dict[str, Optional[datetime]], dict[str, Optional[datetime]]]:
    """Per-resource booked-through + next-open-gap absolute timestamps (1.6 CU4).

    Occupancy is the union of every assignment's chunk spans on the row, in
    minutes from the horizon origin; open windows come from the SAME
    ``flatten_resource_windows`` the solver's eligibility uses, so the numbers
    are the model's, not a re-derivation. Returns two rid → datetime|None maps.
    With no horizon (nothing to flatten) both are empty."""
    booked: dict[str, Optional[datetime]] = {}
    gap: dict[str, Optional[datetime]] = {}
    if horizon is None:
        return booked, gap
    from mre.modules.eligibility import flatten_resource_windows
    from mre.modules.row_intelligence import (
        booked_through_min, next_available_gap_min,
    )

    origin = horizon.start

    def _to_min(dt: datetime) -> int:
        return int((dt - origin).total_seconds() // 60)

    def _to_dt(m: int) -> datetime:
        return origin + timedelta(minutes=m)

    resources_by_id = {r["id"]: r for r in resources}
    windows_by_res = flatten_resource_windows(
        resources_by_id, cals_by_id, horizon.start, horizon.end)

    occ_by_res: dict[str, list[tuple[int, int]]] = {}
    for a in asgn_blocks:
        if not a.chunks:
            continue
        s = _to_min(a.chunks[0].start)
        e = _to_min(a.chunks[-1].end)
        occ_by_res.setdefault(a.resource_id, []).append((s, e))

    from_min = _to_min(reference_date) if reference_date else 0
    from_min = max(0, from_min)
    for rid in resources_by_id:
        occ = occ_by_res.get(rid, [])
        bt = booked_through_min(occ)
        booked[rid] = _to_dt(bt) if bt is not None else None
        ng = next_available_gap_min(windows_by_res.get(rid, []), occ, from_min)
        gap[rid] = _to_dt(ng) if ng is not None else None
    return booked, gap


def _interaction_block(
    edges: list[dict],
    asgn_blocks: list[AssignmentBlock],
    ops_by_id: dict[str, dict],
    resources: list[dict],
    fulfillments: list[dict],
    demands_by_id: dict[str, dict],
    workpackages: list[dict],
    calendars: list[dict],
    horizon: Optional[HorizonBlock],
) -> InteractionBlock:
    """Build the Tier-0 payload: per-scheduled-operation eligible sets +
    durations + release floor, and the precedence graph. Pure derivation.

    ``eligible_resource_ids`` is the set the SOLVER would give an op_assign
    literal — capability resolution AND (for a resumable op) the same calendar
    feasible-window prune the builder applies — computed through the shared
    ``eligibility`` module, so Tier-0 can never green a row the R-DP1 pin would
    silently skip (docs/04 R-DP6, Session 4.0b). A capability-eligible resource
    the builder still refuses carries a truthful ``dim_reasons`` entry so Tier-0
    dims it with an honest hover ("no open calendar window") rather than the
    generic "capability"."""
    from mre.modules.eligibility import flatten_resource_windows, pinnable_resources

    resources_by_id = {r["id"]: r for r in resources}
    wp_by_id = {w["id"]: w for w in workpackages}
    cal_map = {c["id"]: c for c in calendars}

    # Flatten calendars to per-resource minute windows exactly as the solver did
    # (same shared function, same horizon), so the resumable prune matches. With
    # no recorded horizon we cannot flatten; the prune is then skipped (the
    # pre-4.0b behaviour) — non-resumable ops are unaffected either way.
    windows_by_res: dict[str, list[tuple[int, int]]] = {}
    if horizon is not None:
        windows_by_res = flatten_resource_windows(
            resources_by_id, cal_map, horizon.start, horizon.end
        )

    # A workpackage may fulfil several demands (merged WPs); its release floor
    # is the MAX release across them — every demand must be released to start.
    wp_releases: dict[str, list[datetime]] = {}
    for f in fulfillments:
        # Demand.earliest_start is the canonical release floor (docs/05 R-A4:
        # "one field, provenance-bearing").
        rel = _parse_dt(demands_by_id.get(f.get("demand_ref", ""), {}).get("earliest_start"))
        if rel is not None:
            wp_releases.setdefault(f.get("workpackage_ref", ""), []).append(rel)

    ops_out: list[OperationInteraction] = []
    for a in asgn_blocks:
        op = ops_by_id.get(a.operation_ref, {})
        working_min = sum(c.working_min for c in a.chunks)
        setup_min = int(_iso_minutes(op.get("setup_duration")) or 0.0)
        releases = wp_releases.get(a.workpackage_ref, [])

        # The WorkPackage release floor the solver used for the feasible-window
        # prune (workpackage.earliest_start → minutes from horizon start), NOT
        # the demand-side release above (which floors client-side precedence).
        wp_earliest_min = 0
        wp = wp_by_id.get(a.workpackage_ref, {})
        if horizon is not None and wp.get("earliest_start"):
            es = _parse_dt(wp["earliest_start"])
            wp_earliest_min = max(0, int((es - horizon.start).total_seconds() / 60))
        # total (setup + run) minutes — the duration the solver's resumable
        # feasible-window check uses, from the op spec (not the scheduled chunks).
        total_min = int((_iso_minutes(op.get("setup_duration")) or 0.0)
                        + (_iso_minutes(op.get("run_duration")) or 0.0))

        pinnable, dim_reasons = pinnable_resources(
            op, resources_by_id, windows_by_res, wp_earliest_min, total_min
        )
        ops_out.append(OperationInteraction(
            operation_ref=a.operation_ref,
            eligible_resource_ids=sorted(pinnable),
            dim_reasons=dict(sorted(dim_reasons.items())),
            working_min=working_min,
            setup_min=setup_min,
            earliest_start=max(releases) if releases else None,
            resumable=bool(op.get("splittable", False)),
        ))
    ops_out.sort(key=lambda o: o.operation_ref)
    scheduled_ops = {o.operation_ref for o in ops_out}

    # PrecedenceEdge records are TEMPLATE-level (keyed by OperationSpec, one
    # chain per Process). Expand to concrete Operation-INSTANCE edges the same
    # way the Solver Builder does — (workpackage_ref, spec_ref) → op id — so
    # the payload's refs live in the same id-space as interaction.operations
    # (and the board's bars). Only edges between two scheduled instances are
    # emitted (a completed/absent endpoint has no bar to anchor to).
    op_by_wp_spec: dict[tuple[str, str], str] = {
        (op.get("workpackage_ref", ""), op.get("spec_ref", "")): op["id"]
        for op in ops_by_id.values()
        if op.get("workpackage_ref") and op.get("spec_ref")
    }
    workpackage_refs = {op.get("workpackage_ref", "") for op in ops_by_id.values()}
    edge_blocks: list[PrecedenceEdgeBlock] = []
    for e in edges:
        pred_spec, succ_spec = e.get("predecessor"), e.get("successor")
        if not (pred_spec and succ_spec):
            continue
        min_lag = int(_iso_minutes(e.get("min_lag")) or 0.0)
        max_lag = int(_iso_minutes(e.get("max_lag"))) if e.get("max_lag") else None
        for wp_id in workpackage_refs:
            pred_id = op_by_wp_spec.get((wp_id, pred_spec))
            succ_id = op_by_wp_spec.get((wp_id, succ_spec))
            if pred_id in scheduled_ops and succ_id in scheduled_ops:
                edge_blocks.append(PrecedenceEdgeBlock(
                    predecessor_ref=pred_id, successor_ref=succ_id,
                    min_lag_min=min_lag, max_lag_min=max_lag,
                ))
    edge_blocks.sort(key=lambda e: (e.predecessor_ref, e.successor_ref))
    return InteractionBlock(operations=ops_out, precedence_edges=edge_blocks)


# The Tier-0 eligible set is now derived through the shared ``eligibility``
# module (capability resolution + the solver's calendar prune), consumed in
# _interaction_block — no hand-copy of the capability logic lives here (the
# 4.0b unification; the copy that drifted from the solver is gone).


def _render_lock(con: dict, identity_map: Any) -> str:
    names = []
    for sid in con.get("subjects", []):
        names.append(
            _external_name(identity_map, sid, _ORDER_REF_TYPES + _RESOURCE_REF_TYPES)
            or sid
        )
    params = json.dumps(con.get("parameters", {}), sort_keys=True, default=str)
    return f"{con.get('constraint_type')}[{', '.join(names)}] {params}"

def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
