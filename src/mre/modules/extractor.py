"""M7 — Extractor.

Turns SolveValues + canonical entities into:
  - Schedule entity
  - Assignment records (one per solved Operation)
  - ServiceOutcome records (one per Fulfillment, D-07)
  - Reconstructed-alternative Decisions (one per Assignment)
  - Cost ledger as plain dict with rollup_of chain

After extraction the solver model is discarded. The result carries no ortools types.

Hard rules (docs/02 §4.2):
  - All assignment Decisions carry basis=reconstructed.
  - Phrased as "X was chosen; alternatives would have cost..."
  - cost total = production + setup + tardiness (verified by caller / consolidator).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TYPE_CHECKING

from mre.contracts.entities import (
    Assignment as AssignmentEntity,
    EntityRef,
    PhaseWindows,
    ResourceAssignment,
    ResourceRequirement,
    Schedule as ScheduleEntity,
    ServiceOutcome as ServiceOutcomeEntity,
    TimeWindow,
)
from mre.contracts.provenance import DerivedProvenance, InputRef, ProvenanceSidecar
from mre.contracts.records import DecisionAlternative
from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode, RecordTier,
    ResourceRequirementMode, ScheduleStatus,
)
from mre.modules.solver_builder import SolveValues

if TYPE_CHECKING:
    from mre.modules.snapshot_store import SnapshotWriter

UTC = timezone.utc


@dataclass
class ExtractResult:
    """Plain-value extraction result. No ortools types."""
    schedule: dict[str, Any]
    assignments: list[dict[str, Any]]
    service_outcomes: list[dict[str, Any]]
    cost_ledger: dict[str, float]


class Extractor:
    """Convert SolveValues into canonical schedule entities."""

    def extract(
        self,
        solve_values: SolveValues,
        snapshot_id: str,
        operations: list[dict],
        workpackages: list[dict],
        resources: list[dict],
        fulfillments: list[dict],
        demands: list[dict],
        cost_model: dict,
        reporter=None,
        cal_windows: Optional[dict] = None,
        op_eligible: Optional[dict] = None,
        snapshot_writer: Optional["SnapshotWriter"] = None,
        is_scenario: bool = False,
        overtime_windows: Optional[dict] = None,
    ) -> ExtractResult:
        """Extract Schedule, Assignments, ServiceOutcomes, and cost ledger.

        All assignment Decisions carry basis=RECONSTRUCTED (docs/02 §4.2).
        """
        import uuid
        horizon = solve_values.horizon_start

        ops_by_id   = {o["id"]: o for o in operations}
        ress_by_id  = {r["id"]: r for r in resources}
        wps_by_id   = {w["id"]: w for w in workpackages}
        demands_by_id = {d["id"]: d for d in demands}
        fuls_by_id  = {f["id"]: f for f in fulfillments}

        rates: dict[str, float] = cost_model.get("resource_rates", {})
        # Overtime premium multiplier (docs/06 §5.9); ≤ 1.0 means no premium
        # is priced and every minute bills at the regular rate.
        ot_mult: float = float(cost_model.get("overtime_premium", 0.0) or 0.0)
        ot_windows: dict = overtime_windows or {}
        setup_fixed: float = cost_model.get(
            "setup_cost_basis", {}
        ).get("fixed_per_setup", 0.0)
        base_w: float = cost_model.get("tardiness_weights", {}).get("base_weight", 1.0)
        cc_mult: dict = cost_model.get("tardiness_weights", {}).get(
            "commitment_class_multipliers", {}
        )

        # ------------------------------------------------------------------
        # Build Schedule container
        # ------------------------------------------------------------------
        sched_id = str(uuid.uuid4())
        schedule: dict = {
            "id": sched_id,
            "snapshot_ref": snapshot_id,
            "costmodel_ref": cost_model.get("id", ""),
            "solver_run_ref": None,
            "status": "proposed",
            "summary_metrics": {},
        }

        # ------------------------------------------------------------------
        # Build Assignments
        # ------------------------------------------------------------------
        assignments: list[dict] = []
        production_regular_cost = 0.0
        production_overtime_cost = 0.0

        for op_id, chosen_rid in solve_values.op_resource.items():
            op = ops_by_id.get(op_id, {})
            wp_id = op.get("workpackage_ref", "")
            start_min = solve_values.op_start_minutes.get(op_id, 0)
            end_min   = solve_values.op_end_minutes.get(op_id, 0)

            run_start = horizon + timedelta(minutes=start_min)
            run_end   = horizon + timedelta(minutes=end_min)

            # Resumable (chunked) operations: op_chunk_windows carries the
            # per-window minute ranges actually used (docs/05 R-C3). Billing
            # and phase_windows.run must use WORKING minutes (sum of each
            # chunk's own span), never the overall elapsed span — the gaps
            # between chunks are unpaid pauses, not production time.
            chunk_windows_min = solve_values.op_chunk_windows.get(op_id)
            if chunk_windows_min:
                run_windows = [
                    (horizon + timedelta(minutes=s), horizon + timedelta(minutes=e))
                    for s, e in chunk_windows_min
                ]
                dur_min = sum(e - s for s, e in chunk_windows_min)
            else:
                run_windows = [(run_start, run_end)]
                dur_min = end_min - start_min

            # Production cost for this assignment. Minutes inside a premium
            # window (overtime capacity, docs/06 §5.6) bill at rate × ot_mult;
            # everything else at the regular rate. With no premium active
            # (ot_mult ≤ 1 or no overtime windows) this reduces exactly to
            # the historical dur_min × rate.
            rate = rates.get(chosen_rid, 0.0)
            premium = ot_windows.get(chosen_rid, []) if ot_mult > 1.0 else []
            if premium:
                minute_spans = chunk_windows_min or [(start_min, end_min)]
                ot_min = sum(
                    max(0, min(a_e, we) - max(a_s, ws))
                    for a_s, a_e in minute_spans
                    for ws, we in premium
                )
                ot_min = min(ot_min, dur_min)
            else:
                ot_min = 0
            regular_min = dur_min - ot_min
            op_regular_cost = regular_min * rate
            op_overtime_cost = ot_min * rate * ot_mult
            op_cost = op_regular_cost + op_overtime_cost
            production_regular_cost += op_regular_cost
            production_overtime_cost += op_overtime_cost

            # Eligible resources: use solver-derived list when available (accurate
            # capability matching); fall back to all resources for PoC scope cut.
            eligible_rids = (op_eligible or {}).get(op_id, list(ress_by_id.keys()))

            driver = self._assignment_driver(
                chosen_rid, eligible_rids, rates,
                op_start_min=start_min, op_end_min=end_min,
                cal_windows=cal_windows,
            )

            # Reconstructed alternatives — calendar-blocked resources get a
            # different consequence message so the AI layer can explain them.
            alternatives: list[DecisionAlternative] = []
            for rid in eligible_rids:
                if rid == chosen_rid:
                    continue
                if cal_windows is not None:
                    windows = cal_windows.get(rid, [])
                    fits = any(s <= start_min and e >= end_min for s, e in windows)
                    if not fits:
                        alternatives.append(DecisionAlternative(
                            option=f"resource:{rid}",
                            consequence="Unavailable: no calendar window covers this operation slot.",
                        ))
                        continue
                alt_rate = rates.get(rid, 0.0)
                cost_diff = (alt_rate - rate) * dur_min
                if cost_diff > 0:
                    consequence = f"Would cost ${cost_diff:.2f} more."
                elif cost_diff < 0:
                    consequence = f"Would save ${-cost_diff:.2f}."
                else:
                    consequence = "Same cost."
                alternatives.append(
                    DecisionAlternative(
                        option=f"resource:{rid}",
                        consequence=consequence,
                    )
                )

            # Emit reconstructed Decision
            decision_id = str(uuid.uuid4())
            is_chunked = len(run_windows) > 1
            if reporter is not None:
                chosen: dict[str, Any] = {
                    "resource_id": chosen_rid,
                    "start_minutes": start_min,
                    "end_minutes": end_min,
                    "production_cost": op_cost,
                }
                if is_chunked:
                    chosen["chunked"] = True
                    chosen["chunk_count"] = len(run_windows)
                if ot_min > 0:
                    chosen["overtime_minutes"] = ot_min
                    chosen["overtime_premium_multiplier"] = ot_mult
                    chosen["overtime_cost"] = op_overtime_cost
                msg = (
                    f"Operation {op_id} assigned to {chosen_rid} "
                    f"({run_start.isoformat()} → {run_end.isoformat()}). "
                    f"Cost: {op_cost:.2f}."
                )
                if is_chunked:
                    msg += f" Resumable: split into {len(run_windows)} chunks pausing at calendar boundaries."
                if ot_min > 0:
                    msg += (
                        f" Includes {ot_min} min in an overtime calendar window "
                        f"(premium ×{ot_mult:g}: {op_overtime_cost - ot_min * rate:.2f} "
                        f"above the regular rate)."
                    )
                dec = reporter.record_decision(
                    decision_type=DecisionType.ASSIGNMENT,
                    subjects=[EntityRef(entity_id=op_id, entity_type="operation")],
                    chosen=chosen,
                    alternatives=alternatives,
                    driver=driver,
                    basis=DecisionBasis.RECONSTRUCTED,
                    tier=RecordTier.SUPPORTING,
                    message=msg,
                )
                decision_id = dec.record_id

            asgn: dict = {
                "id": str(uuid.uuid4()),
                "snapshot_id": snapshot_id,
                "operation_ref": op_id,
                "workpackage_ref": wp_id,
                "resource_id": chosen_rid,
                "run_start": run_start.isoformat(),
                "run_end": run_end.isoformat(),
                "run_windows": [
                    {"start": s.isoformat(), "end": e.isoformat()} for s, e in run_windows
                ],
                "production_cost": op_cost,
                "overtime_minutes": ot_min,
                "decision_ref": decision_id,
            }
            assignments.append(asgn)

        # ------------------------------------------------------------------
        # ServiceOutcomes (one per Fulfillment)
        # ------------------------------------------------------------------
        service_outcomes: list[dict] = []
        tardiness_cost = 0.0

        for ful in fulfillments:
            fid = ful["id"]
            d_id  = ful["demand_ref"]
            wp_id = ful["workpackage_ref"]
            demand = demands_by_id.get(d_id, {})

            due_dt = _parse_dt(demand.get("due", ""))
            wp_end_min = solve_values.wp_end_minutes.get(wp_id, 0)
            completion = horizon + timedelta(minutes=wp_end_min)

            lateness_min = int((completion - due_dt).total_seconds() / 60)
            tard_min = max(0, lateness_min)

            cclass = demand.get("commitment_class", "standard")
            mult   = cc_mult.get(cclass, 1.0)
            cust_w = float(demand.get("customer_weight", 1.0))
            t_cost = tard_min * base_w * mult * cust_w
            tardiness_cost += t_cost

            svc: dict = {
                "id": str(uuid.uuid4()),
                "snapshot_id": snapshot_id,
                "demand_ref": d_id,
                "fulfillment_ref": fid,
                "projected_completion": completion.isoformat(),
                "lateness_minutes": lateness_min,
                "tardiness_cost": t_cost,
            }
            service_outcomes.append(svc)

            # Emit lateness and completion metrics so M9 can answer
            # "why is WO-X late?" by entity-key lookup.
            if reporter is not None:
                subj = [EntityRef(entity_id=d_id, entity_type="demand")]
                reporter.record_metric(
                    name="lateness_minutes",
                    value=float(lateness_min),
                    unit="minutes",
                    subjects=subj,
                    message=f"Demand {d_id[:8]} lateness: {lateness_min} min",
                )
                reporter.record_metric(
                    name="projected_completion_epoch",
                    value=float(completion.timestamp()),
                    unit="epoch_seconds",
                    subjects=subj,
                    message=f"Demand {d_id[:8]} projected completion: {completion.isoformat()}",
                )

        # ------------------------------------------------------------------
        # Cost ledger (must decompose twice: production = regular + overtime;
        # total = production + setup + tardiness)
        # ------------------------------------------------------------------
        # Setup billing honours observed WIP (docs/06 §5.13, CU0.5 ruling):
        # a completed or in-flight op's setup already happened before this
        # submission's reference_date — it is SUNK and must not be re-charged
        # in the movable objective. The Solver Builder already excludes both
        # from the objective's setup term (no assign literals); the ledger now
        # matches it, so total = production + setup + tardiness still verifies
        # exactly. The sunk portion is reported separately (informational, NOT
        # part of the decomposition) so a WIP cost report can still see it.
        new_setup_ops = sum(
            1 for o in operations
            if o.get("wip_status") not in ("complete", "in_progress")
        )
        sunk_setup_ops = len(operations) - new_setup_ops
        setup_cost = new_setup_ops * setup_fixed        # one setup per RUNNING op
        sunk_setup_cost = sunk_setup_ops * setup_fixed  # already incurred, pre-reference
        production_cost = production_regular_cost + production_overtime_cost
        total_cost = production_cost + setup_cost + tardiness_cost

        cost_ledger: dict[str, float] = {
            "total_cost": total_cost,
            "production_cost": production_cost,
            "production_regular_cost": production_regular_cost,
            "production_overtime_cost": production_overtime_cost,
            "setup_cost": setup_cost,
            "tardiness_cost": tardiness_cost,
        }
        # Additive, non-decomposing line: only present (non-zero) when WIP is
        # observed, so WIP-less runs keep a byte-identical ledger.
        if sunk_setup_cost:
            cost_ledger["sunk_setup_cost"] = sunk_setup_cost

        # Attach summary to schedule — full cost breakdown stored for diff queries
        schedule["summary_metrics"] = {
            "total_cost": total_cost,
            "production_cost": production_cost,
            "production_regular_cost": production_regular_cost,
            "production_overtime_cost": production_overtime_cost,
            "setup_cost": setup_cost,
            "tardiness_cost": tardiness_cost,
            "assignments": len(assignments),
            "service_outcomes": len(service_outcomes),
        }
        if sunk_setup_cost:
            schedule["summary_metrics"]["sunk_setup_cost"] = sunk_setup_cost
        if is_scenario:
            schedule["summary_metrics"]["is_scenario"] = True

        if snapshot_writer is not None:
            self._persist_entities(
                snapshot_writer, snapshot_id,
                schedule, assignments, service_outcomes,
                ops_by_id,
            )

        return ExtractResult(
            schedule=schedule,
            assignments=assignments,
            service_outcomes=service_outcomes,
            cost_ledger=cost_ledger,
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_entities(
        self,
        writer: "SnapshotWriter",
        snapshot_id: str,
        schedule_dict: dict,
        assignment_dicts: list[dict],
        outcome_dicts: list[dict],
        ops_by_id: dict,
    ) -> None:
        """Write Schedule, Assignment, ServiceOutcome entities to the snapshot."""

        def _sidecar(entity_id: str, attr: str, formula: str,
                     input_refs: list[InputRef]) -> ProvenanceSidecar:
            return ProvenanceSidecar(
                entity_id=entity_id,
                attribute_name=attr,
                snapshot_id=snapshot_id,
                provenance_class="derived",
                payload=DerivedProvenance(
                    formula_id=formula,
                    input_refs=input_refs,
                ),
            )

        formula_s = "M7.schedule_extraction"
        formula_a = "M7.assignment_extraction"
        formula_o = "M7.service_outcome_extraction"

        # --- Schedule ---
        sched_id = schedule_dict["id"]
        sched_entity = ScheduleEntity(
            id=sched_id,
            snapshot_ref=schedule_dict["snapshot_ref"],
            costmodel_ref=schedule_dict["costmodel_ref"],
            solver_run_ref=schedule_dict.get("solver_run_ref"),
            status=ScheduleStatus(schedule_dict.get("status", "proposed")),
            summary_metrics=schedule_dict.get("summary_metrics", {}),
        )
        sched_prov = [
            _sidecar(sched_id, "snapshot_ref", formula_s, []),
            _sidecar(sched_id, "costmodel_ref", formula_s,
                     [InputRef(entity_id=schedule_dict["costmodel_ref"],
                               attribute_name="id", snapshot_id=snapshot_id)]),
            _sidecar(sched_id, "solver_run_ref", formula_s, []),
            _sidecar(sched_id, "status", formula_s, []),
            _sidecar(sched_id, "summary_metrics", formula_s, []),
        ]
        writer.write_entity(sched_entity, sched_prov)

        # --- Assignments ---
        for asgn_dict in assignment_dicts:
            asgn_id = asgn_dict["id"]
            op_id = asgn_dict["operation_ref"]
            op = ops_by_id.get(op_id, {})
            chosen_rid = asgn_dict["resource_id"]
            run_start = datetime.fromisoformat(asgn_dict["run_start"])
            run_end = datetime.fromisoformat(asgn_dict["run_end"])
            if run_start.tzinfo is None:
                run_start = run_start.replace(tzinfo=UTC)
            if run_end.tzinfo is None:
                run_end = run_end.replace(tzinfo=UTC)

            # Reconstruct ResourceRequirement from the operation's first requirement
            req_dicts = op.get("resource_requirements", [])
            req = (
                ResourceRequirement(
                    mode=ResourceRequirementMode(req_dicts[0]["mode"]),
                    capability_ref=req_dicts[0].get("capability_ref"),
                    resource_refs=req_dicts[0].get("resource_refs", []),
                    count=req_dicts[0].get("count", 1),
                )
                if req_dicts
                else ResourceRequirement(
                    mode=ResourceRequirementMode.EXPLICIT_SET,
                    resource_refs=[chosen_rid],
                )
            )

            # Resumable (chunked) operations carry multiple run windows —
            # the gaps between them are the pauses (docs/05 R-C3). Falls
            # back to the single overall window when run_windows is absent
            # (older evidence) or has exactly one entry (non-resumable).
            run_windows_raw = asgn_dict.get("run_windows")
            if run_windows_raw:
                run_tw = []
                for w in run_windows_raw:
                    ws = datetime.fromisoformat(w["start"])
                    we = datetime.fromisoformat(w["end"])
                    if ws.tzinfo is None:
                        ws = ws.replace(tzinfo=UTC)
                    if we.tzinfo is None:
                        we = we.replace(tzinfo=UTC)
                    run_tw.append(TimeWindow(start=ws, end=we))
            else:
                run_tw = [TimeWindow(start=run_start, end=run_end)]

            asgn_entity = AssignmentEntity(
                id=asgn_id,
                snapshot_id=snapshot_id,
                operation_ref=op_id,
                workpackage_ref=asgn_dict["workpackage_ref"],
                resource_assignments=[
                    ResourceAssignment(requirement=req, resource_ref=chosen_rid)
                ],
                phase_windows=PhaseWindows(run=run_tw),
                overtime_minutes=int(asgn_dict.get("overtime_minutes", 0)),
                decision_ref=asgn_dict["decision_ref"],
            )
            asgn_prov = [
                _sidecar(asgn_id, "operation_ref", formula_a,
                         [InputRef(entity_id=op_id, attribute_name="id",
                                   snapshot_id=snapshot_id)]),
                _sidecar(asgn_id, "workpackage_ref", formula_a,
                         [InputRef(entity_id=asgn_dict["workpackage_ref"],
                                   attribute_name="id", snapshot_id=snapshot_id)]),
                _sidecar(asgn_id, "resource_assignments", formula_a,
                         [InputRef(entity_id=chosen_rid, attribute_name="id",
                                   snapshot_id=snapshot_id)]),
                _sidecar(asgn_id, "phase_windows", formula_a,
                         [InputRef(entity_id=op_id, attribute_name="run_duration",
                                   snapshot_id=snapshot_id)]),
                # Overlap of this assignment's run windows with the resource
                # calendar's premium (overtime-added) windows — arithmetic on
                # the solved placement, so derived, not observed.
                _sidecar(asgn_id, "overtime_minutes", "M7.overtime_attribution",
                         [InputRef(entity_id=chosen_rid, attribute_name="calendar_ref",
                                   snapshot_id=snapshot_id)]),
                _sidecar(asgn_id, "decision_ref", formula_a, []),
            ]
            writer.write_entity(asgn_entity, asgn_prov)

        # --- ServiceOutcomes ---
        for svc_dict in outcome_dicts:
            svc_id = svc_dict["id"]
            completion_dt = datetime.fromisoformat(svc_dict["projected_completion"])
            if completion_dt.tzinfo is None:
                completion_dt = completion_dt.replace(tzinfo=UTC)
            lateness_min = svc_dict["lateness_minutes"]

            svc_entity = ServiceOutcomeEntity(
                id=svc_id,
                snapshot_id=snapshot_id,
                demand_ref=svc_dict["demand_ref"],
                fulfillment_ref=svc_dict["fulfillment_ref"],
                projected_completion=completion_dt,
                lateness=timedelta(minutes=lateness_min),
                tardiness_cost=svc_dict["tardiness_cost"],
            )
            svc_prov = [
                _sidecar(svc_id, "demand_ref", formula_o,
                         [InputRef(entity_id=svc_dict["demand_ref"],
                                   attribute_name="id", snapshot_id=snapshot_id)]),
                _sidecar(svc_id, "fulfillment_ref", formula_o,
                         [InputRef(entity_id=svc_dict["fulfillment_ref"],
                                   attribute_name="id", snapshot_id=snapshot_id)]),
                _sidecar(svc_id, "projected_completion", formula_o, []),
                _sidecar(svc_id, "lateness", formula_o, []),
                _sidecar(svc_id, "tardiness_cost", formula_o, []),
            ]
            writer.write_entity(svc_entity, svc_prov)

    def _assignment_driver(
        self,
        chosen_rid: str,
        eligible: list[str],
        rates: dict[str, float],
        op_start_min: int = 0,
        op_end_min: int = 0,
        cal_windows: Optional[dict] = None,
    ) -> DriverCode:
        """Classify the primary driver for this assignment choice.

        Priority: CALENDAR_WINDOW > COST_TRADEOFF > CAPACITY_BLOCKED.
        """
        if not eligible or len(eligible) == 1:
            return DriverCode.CAPACITY_BLOCKED
        # CALENDAR_WINDOW: any eligible alternative had no window for this slot
        if cal_windows is not None:
            for rid in eligible:
                if rid == chosen_rid:
                    continue
                windows = cal_windows.get(rid, [])
                fits = any(s <= op_start_min and e >= op_end_min for s, e in windows)
                if not fits:
                    return DriverCode.CALENDAR_WINDOW
        # COST_TRADEOFF: chosen resource is the cheapest eligible option
        chosen_rate = rates.get(chosen_rid, 0.0)
        other_rates = [rates.get(r, 0.0) for r in eligible if r != chosen_rid]
        if other_rates and chosen_rate < min(other_rates):
            return DriverCode.COST_TRADEOFF
        return DriverCode.CAPACITY_BLOCKED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime(2099, 1, 1, tzinfo=UTC)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
