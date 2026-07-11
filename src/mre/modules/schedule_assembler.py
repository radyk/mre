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
    CalendarWindow,
    Chunk,
    CostSummary,
    HorizonBlock,
    InteractionBlock,
    OperationInteraction,
    Phases,
    PhaseWindow,
    PoolBlock,
    PrecedenceEdgeBlock,
    ResourceLane,
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
) -> ScheduleDocument:
    """Assemble the versioned schedule document. Entity args are persisted
    entity dicts (SnapshotReader shape); evidence_records are the run's raw
    JSONL records.

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
    asgn_blocks: list[AssignmentBlock] = []
    for asgn in assignments:
        op = ops_by_id.get(asgn.get("operation_ref", ""), {})
        chunks = _chunks(asgn)
        resource_id = _assigned_resource(asgn)
        asgn_blocks.append(AssignmentBlock(
            assignment_id=asgn["id"],
            operation_ref=asgn.get("operation_ref", ""),
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
        svc_blocks.append(ServiceOutcomeBlock(
            demand_ref=svc.get("demand_ref", ""),
            work_order=_external_name(identity_map, svc.get("demand_ref", ""), _ORDER_REF_TYPES),
            customer_ref=demand.get("customer_ref"),
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
        fulfillments, demands_by_id,
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
) -> ScheduleDocument:
    """Rebuild the document from a persisted pipeline run directory.

    Reads the snapshot's entities + identity map and the evidence JSONL
    under ``out_dir/<runs_subdir>/``, then calls the pure assembler.
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
    )


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
        if kind == "closure":
            closures.append(CalendarException(
                window=TimeWindow(start=w_start, end=w_end),
                type=CalendarExceptionType.CLOSURE,
                reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
            ))
            if w_end > horizon.start and w_start < horizon.end:
                out.append(CalendarWindow(start=w_start, end=w_end, kind="closure"))
        else:  # added capacity
            if w_end > horizon.start and w_start < horizon.end:
                out.append(CalendarWindow(
                    start=w_start, end=w_end,
                    kind="overtime" if e.get("reason") == "overtime" else "regular",
                ))

    for w in flatten_calendar(cal.get("base_pattern", {}), closures,
                              horizon.start, horizon.end):
        out.append(CalendarWindow(start=w.start, end=w.end, kind="regular"))

    out.sort(key=lambda w: (w.start.isoformat(), w.kind))
    return out

def _interaction_block(
    edges: list[dict],
    asgn_blocks: list[AssignmentBlock],
    ops_by_id: dict[str, dict],
    resources: list[dict],
    fulfillments: list[dict],
    demands_by_id: dict[str, dict],
) -> InteractionBlock:
    """Build the Tier-0 payload: per-scheduled-operation eligible sets +
    durations + release floor, and the precedence graph. Pure derivation —
    eligibility comes from the OperationSpec's resource_requirements (the WHOLE
    eligible set, not the chosen resource), durations from the assignment's
    chunks + the op's setup, the release floor from the op's demand."""
    resources_by_id = {r["id"]: r for r in resources}
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
        ops_out.append(OperationInteraction(
            operation_ref=a.operation_ref,
            eligible_resource_ids=_eligible_resource_ids(op, resources_by_id),
            working_min=working_min,
            setup_min=setup_min,
            earliest_start=max(releases) if releases else None,
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


# uuid5 namespace + capability id, mirrors solver_builder._eligible_resources
# so the Tier-0 client sees the SAME eligible set the solver enforced.
_CAP_NS = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def _eligible_resource_ids(op: dict, resources_by_id: dict[str, dict]) -> list[str]:
    """The full set of resource UUIDs the operation may run on — the same
    resolution the Solver Builder uses (explicit_set → resource_refs;
    capability → resources bearing the capability). An empty/absent
    requirement means every resource is eligible (solver scope-cut)."""
    import uuid as _uuid
    ns = _uuid.UUID(_CAP_NS)
    reqs = op.get("resource_requirements") or []
    if not reqs:
        return sorted(resources_by_id)
    req = reqs[0]
    mode = req.get("mode", "")
    if mode == "explicit_set":
        refs = [r for r in (req.get("resource_refs") or []) if r in resources_by_id]
        return sorted(refs) if refs else sorted(resources_by_id)
    if mode == "capability":
        cap_ref = req.get("capability_ref", "")
        matched = [
            rid for rid, res in resources_by_id.items()
            if any(str(_uuid.uuid5(ns, f"capability:{c}")) == cap_ref
                   for c in res.get("capabilities", []))
        ]
        return sorted(matched) if matched else sorted(resources_by_id)
    return sorted(resources_by_id)


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
