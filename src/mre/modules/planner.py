"""M4 — Planner.

Reads Demands + Processes from a snapshot and produces WorkPackages,
Operations, and Fulfillments.

Three policies:
  identity_v1           one Demand → one WorkPackage (1:1)
  merge_by_family_v1    merge Demands sharing product + setup_family whose
                        due dates fall within a configurable window
  merge_by_family_v2    same candidate grouping as v1, gated: a feasibility
                        check (class-aware window-fit, docs/05 R-C3) and a
                        risk check (tardiness exposure vs. setup benefit,
                        margin-adjustable) each must pass or the merge is
                        rejected and its constituents fall back to solo
                        WorkPackages. Not the default (see docs/04 2026-07-12
                        amendment) — opt in via --policy merge_by_family_v2.

Hard rules:
- WorkPackage has NO due date, NO priority (docs/01 §5.2).
- run_duration = quantity × spec.run_rate (DERIVED provenance with chain).
- Every Fulfillment and WorkPackage carries a created_by Decision ref.
- Merge Decision: type=demand_merge, driver=SETUP_AMORTIZATION, basis=policy_applied.
- Rejected merge Decision: type=demand_merge, chosen.decision="merge_rejected",
  driver=CAPACITY_BLOCKED (feasibility gate) or COST_TRADEOFF (risk gate).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from mre.contracts.entities import (
    Demand, EntityRef, Fulfillment, Operation, OperationSpec, Process,
    Product, Quantity, WorkPackage,
)
from mre.contracts.provenance import (
    DefaultedProvenance, DerivedProvenance, InputRef, ObservedProvenance,
    ProvenanceClass, ProvenanceSidecar,
)
from mre.contracts.records import DecisionAlternative
from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode,
    ProcessStatus, RecordTier, WorkPackageState,
)
from mre.modules.calendar_utils import longest_shift_minutes, weekly_open_minutes
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join(parts)))


@dataclass
class PlannerResult:
    workpackage_count: int
    operation_count: int
    fulfillment_count: int
    merge_count: int


class Planner:
    """Stateless planner — reads from snapshot, writes derived entities back."""

    def __init__(
        self,
        policy: str = "identity_v1",
        merge_window_days: int = 3,
        setup_cost_per_setup: float = 50.0,
        risk_margin: float = 1.0,
    ) -> None:
        if policy not in ("identity_v1", "merge_by_family_v1", "merge_by_family_v2"):
            raise ValueError(f"Unknown policy: {policy!r}")
        self._policy = policy
        self._window_days = merge_window_days
        self._setup_cost = setup_cost_per_setup
        # Rep 4 (docs/07 Phase 1): merge_by_family_v2's risk gate rejects a
        # merge when estimated tardiness exposure exceeds estimated setup
        # benefit x this margin. Policy knob, not calibrated — 1.0 means
        # "risk must not exceed benefit at all."
        self._risk_margin = risk_margin

    def run(
        self,
        snapshot_id: str,
        store: SnapshotStore,
        reporter: Reporter,
        excluded_demand_ids: Optional[set[str]] = None,
        suppressed_merge_ids: Optional[set[str]] = None,
    ) -> PlannerResult:
        reader = store.load_snapshot(snapshot_id)
        writer = store.extend_snapshot(snapshot_id)

        # Load reference data from snapshot; skip TEMPORAL_IMPOSSIBILITY-excluded demands
        _excluded = excluded_demand_ids or set()
        demands = {
            d["id"]: d for d in reader.iter_entities("demand")
            if d["id"] not in _excluded
        }
        products = {p["id"]: p for p in reader.iter_entities("product")}
        processes = {pr["id"]: pr for pr in reader.iter_entities("process")}
        specs = {s["id"]: s for s in reader.iter_entities("operationspec")}

        # Build product_ref → process mapping
        prod_to_process: dict[str, dict] = {}
        for proc in processes.values():
            prod_to_process[proc["product_ref"]] = proc

        # Group demands into batches according to policy
        if self._policy == "identity_v1":
            batches = [[d] for d in demands.values()]
        elif self._policy == "merge_by_family_v1":
            batches = self._merge_batches(
                list(demands.values()), products, suppressed_merge_ids
            )
        else:  # merge_by_family_v2
            resources_by_id = {r["id"]: r for r in reader.iter_entities("resource")}
            calendars_by_id = {c["id"]: c for c in reader.iter_entities("calendar")}
            candidate_batches = self._merge_batches(
                list(demands.values()), products, suppressed_merge_ids
            )
            batches, v2_risk_evidence = self._gate_merges_v2(
                candidate_batches, prod_to_process, specs,
                resources_by_id, calendars_by_id, snapshot_id, reporter,
            )

        wp_count = op_count = ful_count = merge_count = 0

        for batch in batches:
            is_merge = len(batch) > 1
            if is_merge:
                merge_count += 1

            # Emit a Decision that authorises this WorkPackage. v2 merges that
            # passed both gates carry the corrected benefit formula + a
            # numeric estimated_risk (docs/02 §4.2); v1 and identity_v1 (and
            # v2's un-merged singletons) use the original emission.
            if is_merge and self._policy == "merge_by_family_v2":
                risk_ev = v2_risk_evidence[tuple(sorted(d["id"] for d in batch))]
                decision = self._emit_batch_decision_v2(
                    batch, risk_ev, snapshot_id, reporter
                )
            else:
                decision = self._emit_batch_decision(
                    batch, snapshot_id, reporter, is_merge
                )

            prod_ref = batch[0]["product_ref"]
            proc = prod_to_process.get(prod_ref)
            spec_ids: list[str] = proc["operation_specs"] if proc else []

            # WorkPackage quantity = sum of constituent quantities
            total_qty = sum(float(d["quantity"]["value"]) for d in batch)
            uom = batch[0]["quantity"].get("uom", "EA")
            earliest = min(
                (d["earliest_start"] for d in batch if d.get("earliest_start")),
                default=None,
            )

            # WIP landing (docs/06 §5.13): project the constituent order's
            # observed execution state onto the operations we instantiate and
            # onto the WorkPackage state seam. Only SINGLETON batches carry
            # WIP: a merged operation is a new aggregate that corresponds to
            # no single order's in-flight op, so its observed actuals would be
            # ambiguous (and the remainder arithmetic would divide one order's
            # progress by the merged total). The raw observation stays on
            # Demand.wip_operations regardless — it is never destroyed. The
            # WIP doorway runs identity_v1 (1:1), where every batch is a
            # singleton, so this is a no-op restriction on the supported flow.
            wip_by_spec: dict[str, dict] = {}
            wip_demand_id: Optional[str] = None
            wip_demand_qty: Optional[float] = None
            if len(batch) == 1:
                wip_demand_id = batch[0]["id"]
                wip_demand_qty = float(batch[0]["quantity"]["value"])
                for obs in batch[0].get("wip_operations", []):
                    wip_by_spec[obs["spec_ref"]] = obs

            wp_id = _uid("wp", *[d["id"] for d in batch])
            wp = WorkPackage(
                id=wp_id,
                snapshot_id=snapshot_id,
                product_ref=prod_ref,
                quantity=Quantity(value=total_qty, uom=uom),
                earliest_start=earliest,
                operations=[],          # filled below
                process_version=proc["version"] if proc else 1,
                state=WorkPackageState.PLANNED,
                created_by=decision.record_id,
            )

            # Instantiate Operations from OperationSpecs
            op_ids: list[str] = []
            wp_op_statuses: list[str] = []
            wip_source_rows: set[int] = set()
            for spec_id in spec_ids:
                spec = specs.get(spec_id)
                if spec is None:
                    continue
                op_id = _uid("op", wp_id, spec_id)
                run_duration = _compute_run_duration(total_qty, spec)

                obs = wip_by_spec.get(spec_id)
                wip_fields, wip_sidecars = _resolve_op_wip(
                    op_id, snapshot_id, obs, spec, wip_demand_qty, wip_demand_id,
                )
                wp_op_statuses.append(obs["status"] if obs else "not_started")
                if obs:
                    wip_source_rows.update(obs.get("source_rows", []))

                spec_min_chunk = spec.get("min_chunk")
                op = Operation(
                    id=op_id,
                    snapshot_id=snapshot_id,
                    spec_ref=spec_id,
                    workpackage_ref=wp_id,
                    sequence=int(spec["sequence"]),
                    resource_requirements=spec.get("resource_requirements", []),
                    setup_family=spec.get("setup_family", ""),
                    setup_duration=_parse_td(spec.get("base_setup", "PT0S")),
                    run_duration=run_duration,
                    splittable=bool(spec.get("splittable", False)),
                    min_chunk=_parse_td(spec_min_chunk) if spec_min_chunk else None,
                    **wip_fields,
                )
                op_provenance = _op_provenance(
                    op_id, snapshot_id,
                    demand_ids=[d["id"] for d in batch],
                    spec_id=spec_id,
                    run_duration_inputs=[
                        InputRef(entity_id=d["id"], attribute_name="quantity",
                                 snapshot_id=snapshot_id) for d in batch
                    ] + [
                        InputRef(entity_id=spec_id, attribute_name="run_rate",
                                 snapshot_id=snapshot_id)
                    ],
                ) + wip_sidecars
                writer.write_entity(op, op_provenance)
                op_ids.append(op_id)
                op_count += 1

            # Roll observed operation statuses up to the WorkPackage state
            # seam (docs/06 §5.13): observed provenance citing the wip source
            # rows when any real observation exists; planner default otherwise.
            wp_state, wp_state_sidecar = _resolve_wp_state(
                wp_id, snapshot_id, wp_op_statuses, sorted(wip_source_rows),
            )

            # Now write WorkPackage (with populated operations list + state)
            wp = wp.model_copy(update={"operations": op_ids, "state": wp_state})
            wp_provenance = _wp_provenance(
                wp_id, snapshot_id,
                demand_ids=[d["id"] for d in batch],
                spec_ids=spec_ids,
                state_sidecar=wp_state_sidecar,
            )
            writer.write_entity(wp, wp_provenance)
            wp_count += 1

            # Write Fulfillments — one per constituent demand
            for demand in batch:
                ful_id = _uid("fulfillment", demand["id"], wp_id)
                ful_qty = float(demand["quantity"]["value"])
                ful = Fulfillment(
                    id=ful_id,
                    snapshot_id=snapshot_id,
                    demand_ref=demand["id"],
                    workpackage_ref=wp_id,
                    allocated_quantity=Quantity(value=ful_qty, uom=uom),
                    decision_ref=decision.record_id,
                )
                ful_prov = _ful_provenance(ful_id, snapshot_id, demand["id"], wp_id)
                writer.write_entity(ful, ful_prov)
                ful_count += 1

        writer.finalize()
        return PlannerResult(
            workpackage_count=wp_count,
            operation_count=op_count,
            fulfillment_count=ful_count,
            merge_count=merge_count,
        )

    # ------------------------------------------------------------------
    # Merge grouping
    # ------------------------------------------------------------------

    def _merge_batches(
        self,
        demands: list[dict],
        products: dict[str, dict],
        suppressed_merge_ids: Optional[set[str]] = None,
    ) -> list[list[dict]]:
        """Group demands by (product_ref, setup_family) then by due-date window.

        Demands whose IDs are in suppressed_merge_ids are forced into solo batches,
        bypassing the merge policy entirely.
        """
        from datetime import datetime, timezone

        suppressed = set(suppressed_merge_ids or ())
        free_demands = [d for d in demands if d["id"] not in suppressed]
        forced_solo = [d for d in demands if d["id"] in suppressed]

        def _family(d: dict) -> str:
            prod = products.get(d["product_ref"], {})
            return prod.get("product_family") or ""

        groups: dict[tuple[str, str], list[dict]] = {}
        for d in free_demands:
            key = (d["product_ref"], _family(d))
            groups.setdefault(key, []).append(d)

        batches: list[list[dict]] = []
        for members in groups.values():
            members.sort(key=lambda d: d["due"])
            batches.extend(self._window_partition(members))

        # Forced solo batches (suppressed merges)
        batches.extend([[d] for d in forced_solo])
        return batches

    def _window_partition(self, demands: list[dict]) -> list[list[dict]]:
        """Partition a same-product/family list into merge groups."""
        from datetime import datetime, timezone, timedelta

        if not demands:
            return []

        batches: list[list[dict]] = []
        current_batch = [demands[0]]
        anchor_due = _parse_datetime(demands[0]["due"])

        for d in demands[1:]:
            d_due = _parse_datetime(d["due"])
            if (d_due - anchor_due).days <= self._window_days:
                current_batch.append(d)
            else:
                batches.append(current_batch)
                current_batch = [d]
                anchor_due = d_due

        if current_batch:
            batches.append(current_batch)
        return batches

    # ------------------------------------------------------------------
    # Rep 4 (docs/07 Phase 1): merge_by_family_v2 feasibility + risk gates
    # ------------------------------------------------------------------

    def _gate_merges_v2(
        self, candidate_batches, prod_to_process, specs,
        resources_by_id, calendars_by_id, snapshot_id, reporter,
    ) -> list[list[dict]]:
        """Run each candidate merge batch through the feasibility gate, then
        the risk gate. A rejection at either gate breaks the batch back into
        solo demands and records a merge_rejected Decision explaining why.

        Returns (final_batches, accepted_risk_evidence) — the latter keyed by
        the batch's sorted demand-id tuple, so the accepted merge's Decision
        (emitted later in run()) can reuse the exact evidence computed here
        rather than recomputing it against a possibly-different resource view."""
        final_batches: list[list[dict]] = []
        accepted_risk_ev: dict[tuple, dict] = {}
        for batch in candidate_batches:
            if len(batch) <= 1:
                final_batches.append(batch)
                continue

            proc = prod_to_process.get(batch[0]["product_ref"])
            spec_ids = proc.get("operation_specs", []) if proc else []

            feasible, feas_ev = self._check_merge_feasibility(
                batch, spec_ids, specs, resources_by_id, calendars_by_id,
            )
            if not feasible:
                self._emit_merge_rejected_decision(
                    batch, snapshot_id, reporter,
                    driver=DriverCode.CAPACITY_BLOCKED,
                    gate="feasibility", evidence=feas_ev,
                )
                final_batches.extend([[d] for d in batch])
                continue

            risk_ok, risk_ev = self._check_merge_risk(
                batch, spec_ids, specs, resources_by_id, calendars_by_id,
            )
            if not risk_ok:
                self._emit_merge_rejected_decision(
                    batch, snapshot_id, reporter,
                    driver=DriverCode.COST_TRADEOFF,
                    gate="risk", evidence=risk_ev,
                )
                final_batches.extend([[d] for d in batch])
                continue

            accepted_risk_ev[tuple(sorted(d["id"] for d in batch))] = risk_ev
            final_batches.append(batch)
        return final_batches, accepted_risk_ev

    @staticmethod
    def _eligible_resource_ids(spec: dict, resources_by_id: dict) -> list[str]:
        """Mirror the validator's eligible-resource walk (docs/05 R-C3)."""
        eligible: list[str] = []
        for req in spec.get("resource_requirements", []):
            if not isinstance(req, dict):
                continue
            mode = req.get("mode", "")
            if mode == "explicit_set":
                eligible.extend(req.get("resource_refs", []))
            elif mode == "capability":
                cap_ref = req.get("capability_ref", "")
                for rid, r in resources_by_id.items():
                    if cap_ref in (r.get("capabilities") or []):
                        eligible.append(rid)
        return eligible

    @classmethod
    def _best_calendar_minutes(
        cls, eligible_ids: list[str], resources_by_id: dict,
        calendars_by_id: dict, metric,
    ) -> float:
        best = 0.0
        for rid in eligible_ids:
            res = resources_by_id.get(rid)
            if not res:
                continue
            cal = calendars_by_id.get(res.get("calendar_ref"))
            if not cal:
                continue
            best = max(best, metric(cal))
        return best

    def _check_merge_feasibility(
        self, batch, spec_ids, specs, resources_by_id, calendars_by_id,
    ) -> tuple[bool, dict]:
        """Class-aware window-fit (docs/05 R-C3), applied to the MERGED batch's
        total quantity per operation spec — the check the validator cannot
        perform per-demand (it runs before the planner creates merged
        quantities). Non-resumable: merged operation must fit the longest
        contiguous window on some eligible resource. Resumable: merged
        operation's total working time must fit within the batch's own
        horizon (earliest release -> latest constituent due date) on the
        best eligible resource, even chunked."""
        total_qty = sum(float(d["quantity"]["value"]) for d in batch)
        releases = [d["earliest_start"] for d in batch if d.get("earliest_start")]
        dues = [d["due"] for d in batch if d.get("due")]
        earliest_release = min(releases) if releases else None
        latest_due = max(dues, key=_parse_datetime) if dues else None

        for spec_id in spec_ids:
            spec = specs.get(spec_id)
            if spec is None:
                continue
            run_rate_sec = _parse_td(spec.get("run_rate", "PT0S")).total_seconds()
            setup_sec = _parse_td(spec.get("base_setup", "PT0S")).total_seconds()
            total_minutes = (total_qty * run_rate_sec + setup_sec) / 60.0
            if total_minutes <= 0.0:
                continue

            eligible_ids = self._eligible_resource_ids(spec, resources_by_id)
            if not eligible_ids:
                continue

            if not bool(spec.get("splittable", False)):
                max_window = self._best_calendar_minutes(
                    eligible_ids, resources_by_id, calendars_by_id, longest_shift_minutes,
                )
                if max_window > 0.0 and total_minutes > max_window:
                    return False, {
                        "spec_id": spec_id,
                        "class": "non_resumable",
                        "estimated_duration_minutes": round(total_minutes, 1),
                        "max_window_minutes": max_window,
                        "reason": (
                            "Merged operation's estimated duration exceeds the longest "
                            "contiguous calendar window on every eligible resource"
                        ),
                    }
            else:
                if not earliest_release or not latest_due:
                    continue
                elapsed_days = max(
                    0.0,
                    (_parse_datetime(latest_due) - _parse_datetime(earliest_release)).total_seconds() / 86400.0,
                )
                best_weekly = self._best_calendar_minutes(
                    eligible_ids, resources_by_id, calendars_by_id, weekly_open_minutes,
                )
                available_minutes = best_weekly * (elapsed_days / 7.0)
                if best_weekly > 0.0 and total_minutes > available_minutes:
                    return False, {
                        "spec_id": spec_id,
                        "class": "resumable",
                        "estimated_duration_minutes": round(total_minutes, 1),
                        "available_minutes": round(available_minutes, 1),
                        "elapsed_days": round(elapsed_days, 2),
                        "reason": (
                            "Merged resumable operation's total working time exceeds "
                            "what is available across the batch's own horizon (earliest "
                            "release to latest constituent due date), even chunked"
                        ),
                    }
        return True, {}

    def _check_merge_risk(
        self, batch, spec_ids, specs, resources_by_id, calendars_by_id,
    ) -> tuple[bool, dict]:
        """Reject when estimated tardiness exposure (the earliest-due
        constituent's slack consumed by the merged batch's total duration,
        priced at that demand's weight) exceeds estimated setup benefit x
        risk_margin. This is what merge_by_family_v1 got wrong (2026-07-06
        docs/04 amendment, the $260 unbatch verdict): benefit there counted
        one avoided setup per merge, but the extractor bills one setup per
        OPERATION — the corrected formula is used here."""
        total_qty = sum(float(d["quantity"]["value"]) for d in batch)
        merged_duration_minutes = 0.0
        for spec_id in spec_ids:
            spec = specs.get(spec_id)
            if spec is None:
                continue
            run_rate_sec = _parse_td(spec.get("run_rate", "PT0S")).total_seconds()
            setup_sec = _parse_td(spec.get("base_setup", "PT0S")).total_seconds()
            merged_duration_minutes += (total_qty * run_rate_sec + setup_sec) / 60.0

        earliest_demand = min(batch, key=lambda d: _parse_datetime(d.get("due")))
        releases = [d["earliest_start"] for d in batch if d.get("earliest_start")]
        earliest_release = min(releases) if releases else None

        budget_minutes: Optional[float] = None
        tardiness_exposure_minutes = 0.0
        if earliest_release and earliest_demand.get("due") and spec_ids:
            elapsed_days = max(
                0.0,
                (_parse_datetime(earliest_demand["due"]) - _parse_datetime(earliest_release)).total_seconds() / 86400.0,
            )
            rep_spec = specs.get(spec_ids[0])
            if rep_spec is not None:
                eligible_ids = self._eligible_resource_ids(rep_spec, resources_by_id)
                best_weekly = self._best_calendar_minutes(
                    eligible_ids, resources_by_id, calendars_by_id, weekly_open_minutes,
                )
                budget_minutes = best_weekly * (elapsed_days / 7.0)
                tardiness_exposure_minutes = max(0.0, merged_duration_minutes - budget_minutes)

        customer_weight = float(earliest_demand.get("customer_weight") or 1.0)
        tardiness_exposure_cost = tardiness_exposure_minutes * customer_weight

        setups_avoided = len(batch) - 1
        n_ops = len(spec_ids)
        estimated_benefit = setups_avoided * n_ops * self._setup_cost

        risk_ok = tardiness_exposure_cost <= estimated_benefit * self._risk_margin
        evidence = {
            "earliest_demand_id": earliest_demand["id"],
            "merged_duration_minutes": round(merged_duration_minutes, 1),
            "budget_minutes": round(budget_minutes, 1) if budget_minutes is not None else None,
            "tardiness_exposure_minutes": round(tardiness_exposure_minutes, 1),
            "customer_weight": customer_weight,
            "estimated_risk": round(tardiness_exposure_cost, 2),
            "estimated_benefit": round(estimated_benefit, 2),
            "risk_margin": self._risk_margin,
            "reason": (
                "Estimated tardiness exposure exceeds estimated setup benefit x margin"
                if not risk_ok else ""
            ),
        }
        return risk_ok, evidence

    # ------------------------------------------------------------------
    # Decision emission
    # ------------------------------------------------------------------

    def _emit_batch_decision(self, batch, snapshot_id, reporter, is_merge):
        if is_merge:
            # Estimate benefit: setups_avoided × setup_cost
            setups_avoided = len(batch) - 1
            estimated_benefit = setups_avoided * self._setup_cost

            # Estimate risk: total run duration of the merged batch for the
            # earliest-due demand (a rough tardiness exposure)
            est_risk_msg = (
                f"Earliest constituent may become late by up to the combined "
                f"run duration if scheduled back-to-back on a single machine."
            )

            return reporter.record_decision(
                decision_type=DecisionType.DEMAND_MERGE,
                subjects=[
                    EntityRef(entity_id=d["id"], entity_type="demand")
                    for d in batch
                ],
                chosen={
                    "policy": "merge_by_family_v1",
                    "merge_window_days": self._window_days,
                    "constituent_demand_ids": [d["id"] for d in batch],
                    "estimated_benefit": estimated_benefit,
                    "setups_avoided": setups_avoided,
                    "compatibility_basis": "same_product_and_setup_family",
                },
                alternatives=[
                    DecisionAlternative(
                        option="identity_v1",
                        consequence=(
                            f"Would run {len(batch)} separate setups costing "
                            f"{setups_avoided * self._setup_cost:.2f} more."
                        ),
                    )
                ],
                driver=DriverCode.SETUP_AMORTIZATION,
                basis=DecisionBasis.POLICY_APPLIED,
                policy_ref="merge_by_family_v1",
                tier=RecordTier.SUPPORTING,
                message=(
                    f"Merged {len(batch)} demands "
                    f"(product={batch[0]['product_ref']}). "
                    f"Benefit: {estimated_benefit:.2f}. Risk: {est_risk_msg}"
                ),
            )
        else:
            # identity_v1 — emit an INTERPRETATION decision (1:1 mapping)
            return reporter.record_decision(
                decision_type=DecisionType.INTERPRETATION,
                subjects=[EntityRef(entity_id=batch[0]["id"], entity_type="demand")],
                chosen={"policy": "identity_v1"},
                alternatives=[],
                driver=DriverCode.DUE_DATE_PRESSURE,
                basis=DecisionBasis.POLICY_APPLIED,
                tier=RecordTier.SUPPORTING,
                message=f"identity_v1: demand {batch[0]['id']} → 1 WorkPackage",
            )

    def _emit_batch_decision_v2(self, batch, risk_ev, snapshot_id, reporter):
        """merge_by_family_v2's accepted-merge decision: corrected benefit
        formula (setups_avoided x n_ops, matching the extractor's per-operation
        setup billing — see the $260 unbatch verdict, docs/04 2026-07-06) and a
        numeric estimated_risk (docs/02 §4.2's benefit/risk counterfactual pair).
        risk_ev is the evidence already computed by the risk gate in
        _gate_merges_v2 — reused rather than recomputed, so the Decision and
        the gate that accepted the merge can never disagree."""
        setups_avoided = len(batch) - 1
        estimated_benefit = risk_ev["estimated_benefit"]

        return reporter.record_decision(
            decision_type=DecisionType.DEMAND_MERGE,
            subjects=[EntityRef(entity_id=d["id"], entity_type="demand") for d in batch],
            chosen={
                "policy": "merge_by_family_v2",
                "merge_window_days": self._window_days,
                "constituent_demand_ids": [d["id"] for d in batch],
                "estimated_benefit": estimated_benefit,
                "estimated_risk": risk_ev["estimated_risk"],
                "setups_avoided": setups_avoided,
                "risk_margin": self._risk_margin,
                "compatibility_basis": "same_product_and_setup_family",
            },
            alternatives=[
                DecisionAlternative(
                    option="identity_v1",
                    consequence=(
                        f"Would run {len(batch)} separate setups costing "
                        f"~{estimated_benefit:.2f} more, with no tardiness exposure "
                        f"from coupling the batch's completion."
                    ),
                )
            ],
            driver=DriverCode.SETUP_AMORTIZATION,
            basis=DecisionBasis.POLICY_APPLIED,
            policy_ref="merge_by_family_v2",
            tier=RecordTier.SUPPORTING,
            message=(
                f"Merged {len(batch)} demands (product={batch[0]['product_ref']}) — "
                f"passed feasibility + risk gates. Benefit: {estimated_benefit:.2f}. "
                f"Estimated risk: {risk_ev['estimated_risk']:.2f}."
            ),
        )

    def _emit_merge_rejected_decision(self, batch, snapshot_id, reporter, driver, gate, evidence):
        """Records why a candidate merge was rejected, so "why didn't these
        batch?" is answerable from evidence alone. decision_type stays
        DEMAND_MERGE (it is still fundamentally a merge decision); the
        rejection is distinguished by chosen.decision, not a new closed-vocab
        DecisionType member."""
        return reporter.record_decision(
            decision_type=DecisionType.DEMAND_MERGE,
            subjects=[EntityRef(entity_id=d["id"], entity_type="demand") for d in batch],
            chosen={
                "decision": "merge_rejected",
                "policy": "merge_by_family_v2",
                "gate": gate,
                "constituent_demand_ids": [d["id"] for d in batch],
                **evidence,
            },
            alternatives=[
                DecisionAlternative(
                    option="merge_by_family_v2 (merged)",
                    consequence=evidence.get("reason", f"Rejected at the {gate} gate."),
                )
            ],
            driver=driver,
            basis=DecisionBasis.POLICY_APPLIED,
            policy_ref="merge_by_family_v2",
            tier=RecordTier.SUPPORTING,
            message=(
                f"Rejected merge of {len(batch)} demands "
                f"(product={batch[0]['product_ref']}) at the {gate} gate: "
                f"{evidence.get('reason', '')}"
            ),
        )


# ---------------------------------------------------------------------------
# Provenance factories
# ---------------------------------------------------------------------------

def _op_provenance(
    op_id: str,
    snapshot_id: str,
    demand_ids: list[str],
    spec_id: str,
    run_duration_inputs: list[InputRef],
) -> list[ProvenanceSidecar]:
    def _drv(attr: str, formula: str, inputs: list[InputRef]) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=op_id, attribute_name=attr, snapshot_id=snapshot_id,
            provenance_class=ProvenanceClass.DERIVED,
            payload=DerivedProvenance(formula_id=formula, input_refs=inputs),
        )

    spec_inputs = [InputRef(entity_id=spec_id, attribute_name=attr, snapshot_id=snapshot_id)
                   for attr in ("sequence", "resource_requirements", "setup_family",
                                "base_setup", "splittable", "min_chunk")]

    return [
        _drv("spec_ref",    "planner.spec_ref",          [InputRef(entity_id=spec_id, attribute_name="id", snapshot_id=snapshot_id)]),
        _drv("workpackage_ref", "planner.wp_ref",        []),
        _drv("sequence",    "planner.copy_spec",         spec_inputs[:1]),
        _drv("resource_requirements", "planner.copy_spec", spec_inputs[1:2]),
        _drv("setup_family", "planner.copy_spec",        spec_inputs[2:3]),
        _drv("setup_duration", "planner.copy_base_setup", spec_inputs[3:4]),
        _drv("run_duration", "demand.quantity * spec.run_rate", run_duration_inputs),
        _drv("splittable",  "planner.copy_splittable",   spec_inputs[4:5]),
        _drv("min_chunk",   "planner.copy_min_chunk",    spec_inputs[5:6]),
    ]


def _wp_provenance(
    wp_id: str,
    snapshot_id: str,
    demand_ids: list[str],
    spec_ids: list[str],
    state_sidecar: Optional[ProvenanceSidecar] = None,
) -> list[ProvenanceSidecar]:
    demand_inputs = [
        InputRef(entity_id=did, attribute_name="quantity", snapshot_id=snapshot_id)
        for did in demand_ids
    ]

    def _drv(attr: str, inputs: list[InputRef]) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=wp_id, attribute_name=attr, snapshot_id=snapshot_id,
            provenance_class=ProvenanceClass.DERIVED,
            payload=DerivedProvenance(formula_id=f"planner.{attr}", input_refs=inputs),
        )

    def _dflt(attr: str) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=wp_id, attribute_name=attr, snapshot_id=snapshot_id,
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="planner default"),
        )

    # state: observed (WIP rollup, citing source rows) when the caller
    # derived one from WIP; planner default otherwise (docs/06 §5.13).
    state_prov = state_sidecar if state_sidecar is not None else _dflt("state")

    return [
        _drv("product_ref",     demand_inputs[:1]),
        _drv("quantity",        demand_inputs),
        _drv("earliest_start",  demand_inputs),
        _drv("operations",      [InputRef(entity_id=s, attribute_name="id", snapshot_id=snapshot_id) for s in spec_ids]),
        _dflt("process_version"),
        state_prov,
        _drv("created_by",      demand_inputs[:1]),
    ]


# ---------------------------------------------------------------------------
# WIP landing (docs/06 §5.13) — projecting observed execution state onto
# Operations and the WorkPackage state seam.
# ---------------------------------------------------------------------------

_WIP_OP_ATTRS = ("wip_status", "observed_start", "observed_resource_ref",
                 "remaining_duration")


def _wip_observed(entity_id: str, snapshot_id: str, attr: str, field: str,
                  source_rows: list[int], demand_id: Optional[str] = None
                  ) -> ProvenanceSidecar:
    """OBSERVED sidecar citing the actual wip_status.csv source rows — never
    a constant under an observed sidecar (the yield_factor false-observed
    anti-pattern, docs/04 2026-07-12)."""
    who = f"demand {demand_id}, " if demand_id else ""
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snapshot_id,
        provenance_class=ProvenanceClass.OBSERVED,
        payload=ObservedProvenance(
            source_system="wip_status",
            source_field=f"{field} ({who}wip_status.csv rows {list(source_rows)})",
            extract_ref="wip_status.csv"),
    )


def _wip_defaulted(entity_id: str, snapshot_id: str, attr: str, policy: str
                   ) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snapshot_id,
        provenance_class=ProvenanceClass.DEFAULTED,
        payload=DefaultedProvenance(policy=policy),
    )


def _wip_derived(entity_id: str, snapshot_id: str, attr: str, formula: str,
                 inputs: list[InputRef]) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snapshot_id,
        provenance_class=ProvenanceClass.DERIVED,
        payload=DerivedProvenance(formula_id=formula, input_refs=inputs),
    )


def _resolve_op_wip(
    op_id: str,
    snapshot_id: str,
    obs: Optional[dict],
    spec: dict,
    demand_qty: Optional[float],
    demand_id: Optional[str],
) -> tuple[dict, list[ProvenanceSidecar]]:
    """Project one operation's WIP observation (docs/06 §5.13) into its
    canonical fields + provenance. obs is the serialized
    WipOperationObservation dict from the Demand, or None (no observation).

    - complete: observed actuals; remaining_duration = 0 (DERIVED from status).
    - in_progress: observed start + resource; remaining_duration is OBSERVED
      when the plant reported remaining_minutes directly, or DERIVED when
      computed from observed quantity_complete (the remainder arithmetic).
    - not_started / no observation: fields None, DEFAULTED.
    """
    if obs is None:
        fields = {a: None for a in _WIP_OP_ATTRS}
        prov = [_wip_defaulted(op_id, snapshot_id, a, "no_wip_observation")
                for a in _WIP_OP_ATTRS]
        return fields, prov

    status = obs["status"]
    rows = obs.get("source_rows", [])
    fields: dict = {"wip_status": status, "observed_start": None,
                    "observed_resource_ref": None, "remaining_duration": None}
    prov = [_wip_observed(op_id, snapshot_id, "wip_status", "status", rows, demand_id)]

    if status == "not_started":
        prov += [_wip_defaulted(op_id, snapshot_id, a, "not_started_no_actuals")
                 for a in ("observed_start", "observed_resource_ref", "remaining_duration")]
        return fields, prov

    # in_progress or complete carry observed start + resource
    fields["observed_start"] = obs.get("actual_start")
    fields["observed_resource_ref"] = obs.get("actual_resource_ref")
    prov.append(_wip_observed(op_id, snapshot_id, "observed_start", "actual_start", rows, demand_id))
    prov.append(_wip_observed(op_id, snapshot_id, "observed_resource_ref", "actual_resource_id", rows, demand_id))

    if status == "complete":
        fields["remaining_duration"] = timedelta(0)
        prov.append(_wip_derived(
            op_id, snapshot_id, "remaining_duration", "wip_complete_zero_remaining",
            [InputRef(entity_id=demand_id, attribute_name="wip_operations", snapshot_id=snapshot_id)]
            if demand_id else [],
        ))
        return fields, prov

    # in_progress: remaining_minutes (observed) or quantity_complete (derived)
    rem_min = obs.get("remaining_minutes")
    if rem_min is not None:
        fields["remaining_duration"] = timedelta(minutes=float(rem_min))
        prov.append(_wip_observed(op_id, snapshot_id, "remaining_duration",
                                  "remaining_minutes", rows, demand_id))
    else:
        rate_td = _parse_td(spec.get("run_rate", "PT0S"))
        qty_complete = float(obs.get("quantity_complete") or 0.0)
        remaining_qty = max(0.0, (demand_qty or 0.0) - qty_complete)
        fields["remaining_duration"] = timedelta(
            seconds=remaining_qty * rate_td.total_seconds())
        prov.append(_wip_derived(
            op_id, snapshot_id, "remaining_duration",
            "wip_remaining = (quantity - quantity_complete) * run_rate",
            ([InputRef(entity_id=demand_id, attribute_name="quantity", snapshot_id=snapshot_id),
              InputRef(entity_id=demand_id, attribute_name="wip_operations", snapshot_id=snapshot_id)]
             if demand_id else [])
            + [InputRef(entity_id=spec["id"], attribute_name="run_rate", snapshot_id=snapshot_id)],
        ))
    return fields, prov


def _resolve_wp_state(
    wp_id: str,
    snapshot_id: str,
    op_statuses: list[str],
    source_rows: list[int],
) -> tuple[WorkPackageState, ProvenanceSidecar]:
    """Roll observed operation statuses up to the WorkPackage state seam
    (docs/06 §5.13). Observed provenance citing the wip source rows when any
    real observation exists (never a default under an observed sidecar);
    planner default (planned) otherwise."""
    if not source_rows:
        return (WorkPackageState.PLANNED,
                _wip_defaulted(wp_id, snapshot_id, "state", "planner default"))
    if all(s == "complete" for s in op_statuses):
        state = WorkPackageState.COMPLETE
    elif all(s == "not_started" for s in op_statuses):
        state = WorkPackageState.PLANNED
    else:
        state = WorkPackageState.IN_PROGRESS
    return state, _wip_observed(wp_id, snapshot_id, "state", "status", source_rows)


def _ful_provenance(
    ful_id: str,
    snapshot_id: str,
    demand_id: str,
    wp_id: str,
) -> list[ProvenanceSidecar]:
    d_input = InputRef(entity_id=demand_id, attribute_name="quantity", snapshot_id=snapshot_id)
    wp_input = InputRef(entity_id=wp_id, attribute_name="id", snapshot_id=snapshot_id)

    def _drv(attr: str, inputs: list[InputRef]) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=ful_id, attribute_name=attr, snapshot_id=snapshot_id,
            provenance_class=ProvenanceClass.DERIVED,
            payload=DerivedProvenance(formula_id=f"planner.fulfillment.{attr}", input_refs=inputs),
        )

    return [
        _drv("demand_ref",         [d_input]),
        _drv("workpackage_ref",    [wp_input]),
        _drv("allocated_quantity", [d_input]),
        _drv("decision_ref",       [wp_input]),
    ]


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------

def _compute_run_duration(total_qty: float, spec: dict) -> timedelta:
    """run_duration = total_qty × spec.run_rate."""
    rate_td = _parse_td(spec.get("run_rate", "PT0S"))
    rate_secs = rate_td.total_seconds()
    return timedelta(seconds=total_qty * rate_secs)


def _parse_td(s: str | None) -> timedelta:
    """Parse ISO 8601 duration string as returned by pydantic v2."""
    if not s:
        return timedelta(0)
    if isinstance(s, (int, float)):
        return timedelta(seconds=float(s))
    import re
    m = re.fullmatch(r"P(?:(\d+(?:\.\d+)?)D)?T?(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", s)
    if not m:
        return timedelta(0)
    days   = float(m.group(1) or 0)
    hours  = float(m.group(2) or 0)
    mins   = float(m.group(3) or 0)
    secs   = float(m.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=mins, seconds=secs)


def _parse_datetime(s: str | None):
    """Parse ISO datetime string."""
    from datetime import datetime, timezone
    if not s:
        return datetime(2099, 1, 1, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
