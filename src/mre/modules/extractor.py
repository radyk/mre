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
from typing import Any, Optional

from mre.contracts.entities import EntityRef
from mre.contracts.records import DecisionAlternative
from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode, RecordTier,
)
from mre.modules.solver_builder import SolveValues

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
        production_cost = 0.0

        for op_id, chosen_rid in solve_values.op_resource.items():
            op = ops_by_id.get(op_id, {})
            wp_id = op.get("workpackage_ref", "")
            start_min = solve_values.op_start_minutes.get(op_id, 0)
            end_min   = solve_values.op_end_minutes.get(op_id, 0)

            run_start = horizon + timedelta(minutes=start_min)
            run_end   = horizon + timedelta(minutes=end_min)

            # Production cost for this assignment
            dur_min = end_min - start_min
            rate = rates.get(chosen_rid, 0.0)
            op_cost = dur_min * rate
            production_cost += op_cost

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
                alternatives.append(
                    DecisionAlternative(
                        option=f"resource:{rid}",
                        consequence=(
                            f"Would cost {cost_diff:+.2f} more."
                            if cost_diff != 0
                            else "Same cost."
                        ),
                    )
                )

            # Emit reconstructed Decision
            decision_id = str(uuid.uuid4())
            if reporter is not None:
                dec = reporter.record_decision(
                    decision_type=DecisionType.ASSIGNMENT,
                    subjects=[EntityRef(entity_id=op_id, entity_type="operation")],
                    chosen={
                        "resource_id": chosen_rid,
                        "start_minutes": start_min,
                        "end_minutes": end_min,
                        "production_cost": op_cost,
                    },
                    alternatives=alternatives,
                    driver=driver,
                    basis=DecisionBasis.RECONSTRUCTED,
                    tier=RecordTier.SUPPORTING,
                    message=(
                        f"Operation {op_id} assigned to {chosen_rid} "
                        f"({run_start.isoformat()} → {run_end.isoformat()}). "
                        f"Cost: {op_cost:.2f}."
                    ),
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
                "production_cost": op_cost,
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

        # ------------------------------------------------------------------
        # Cost ledger (must decompose: total = production + setup + tardiness)
        # ------------------------------------------------------------------
        setup_cost = len(operations) * setup_fixed  # one setup per operation
        total_cost = production_cost + setup_cost + tardiness_cost

        cost_ledger: dict[str, float] = {
            "total_cost": total_cost,
            "production_cost": production_cost,
            "setup_cost": setup_cost,
            "tardiness_cost": tardiness_cost,
        }

        # Attach summary to schedule
        schedule["summary_metrics"] = {
            "total_cost": total_cost,
            "assignments": len(assignments),
            "service_outcomes": len(service_outcomes),
        }

        return ExtractResult(
            schedule=schedule,
            assignments=assignments,
            service_outcomes=service_outcomes,
            cost_ledger=cost_ledger,
        )

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
