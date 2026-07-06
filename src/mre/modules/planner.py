"""M4 — Planner.

Reads Demands + Processes from a snapshot and produces WorkPackages,
Operations, and Fulfillments.

Two policies:
  identity_v1           one Demand → one WorkPackage (1:1)
  merge_by_family_v1    merge Demands sharing product + setup_family whose
                        due dates fall within a configurable window

Hard rules:
- WorkPackage has NO due date, NO priority (docs/01 §5.2).
- run_duration = quantity × spec.run_rate (DERIVED provenance with chain).
- Every Fulfillment and WorkPackage carries a created_by Decision ref.
- Merge Decision: type=demand_merge, driver=SETUP_AMORTIZATION, basis=policy_applied.
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
    DefaultedProvenance, DerivedProvenance, InputRef,
    ProvenanceClass, ProvenanceSidecar,
)
from mre.contracts.records import DecisionAlternative
from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode,
    ProcessStatus, RecordTier, WorkPackageState,
)
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
    ) -> None:
        if policy not in ("identity_v1", "merge_by_family_v1"):
            raise ValueError(f"Unknown policy: {policy!r}")
        self._policy = policy
        self._window_days = merge_window_days
        self._setup_cost = setup_cost_per_setup

    def run(
        self,
        snapshot_id: str,
        store: SnapshotStore,
        reporter: Reporter,
    ) -> PlannerResult:
        reader = store.load_snapshot(snapshot_id)
        writer = store.extend_snapshot(snapshot_id)

        # Load reference data from snapshot
        demands = {d["id"]: d for d in reader.iter_entities("demand")}
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
        else:
            batches = self._merge_batches(list(demands.values()), products)

        wp_count = op_count = ful_count = merge_count = 0

        for batch in batches:
            is_merge = len(batch) > 1
            if is_merge:
                merge_count += 1

            # Emit a Decision that authorises this WorkPackage
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
            for spec_id in spec_ids:
                spec = specs.get(spec_id)
                if spec is None:
                    continue
                op_id = _uid("op", wp_id, spec_id)
                run_duration = _compute_run_duration(total_qty, spec)

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
                    dwell_duration=_parse_td(spec.get("dwell_rule", "PT0S")),
                    splittable=bool(spec.get("splittable", False)),
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
                )
                writer.write_entity(op, op_provenance)
                op_ids.append(op_id)
                op_count += 1

            # Now write WorkPackage (with populated operations list)
            wp = wp.model_copy(update={"operations": op_ids})
            wp_provenance = _wp_provenance(
                wp_id, snapshot_id,
                demand_ids=[d["id"] for d in batch],
                spec_ids=spec_ids,
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
    ) -> list[list[dict]]:
        """Group demands by (product_ref, setup_family) then by due-date window."""
        from datetime import datetime, timezone

        # Determine setup_family from product's product_family field
        def _family(d: dict) -> str:
            prod = products.get(d["product_ref"], {})
            return prod.get("product_family") or ""

        # Group by (product_ref, family)
        groups: dict[tuple[str, str], list[dict]] = {}
        for d in demands:
            key = (d["product_ref"], _family(d))
            groups.setdefault(key, []).append(d)

        batches: list[list[dict]] = []
        for members in groups.values():
            # Sort by due date
            members.sort(key=lambda d: d["due"])
            batches.extend(self._window_partition(members))
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

    def _dflt(attr: str) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=op_id, attribute_name=attr, snapshot_id=snapshot_id,
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="planner default"),
        )

    spec_inputs = [InputRef(entity_id=spec_id, attribute_name=attr, snapshot_id=snapshot_id)
                   for attr in ("sequence", "resource_requirements", "setup_family",
                                "base_setup", "dwell_rule", "splittable")]

    return [
        _drv("spec_ref",    "planner.spec_ref",          [InputRef(entity_id=spec_id, attribute_name="id", snapshot_id=snapshot_id)]),
        _drv("workpackage_ref", "planner.wp_ref",        []),
        _drv("sequence",    "planner.copy_spec",         spec_inputs[:1]),
        _drv("resource_requirements", "planner.copy_spec", spec_inputs[1:2]),
        _drv("setup_family", "planner.copy_spec",        spec_inputs[2:3]),
        _drv("setup_duration", "planner.copy_base_setup", spec_inputs[3:4]),
        _drv("run_duration", "demand.quantity * spec.run_rate", run_duration_inputs),
        _drv("dwell_duration", "planner.copy_dwell",     spec_inputs[4:5]),
        _drv("splittable",  "planner.copy_splittable",   spec_inputs[5:6]),
        _dflt("predecessors"),
        _dflt("min_chunk"),
    ]


def _wp_provenance(
    wp_id: str,
    snapshot_id: str,
    demand_ids: list[str],
    spec_ids: list[str],
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

    return [
        _drv("product_ref",     demand_inputs[:1]),
        _drv("quantity",        demand_inputs),
        _drv("earliest_start",  demand_inputs),
        _drv("operations",      [InputRef(entity_id=s, attribute_name="id", snapshot_id=snapshot_id) for s in spec_ids]),
        _dflt("process_version"),
        _dflt("state"),
        _drv("created_by",      demand_inputs[:1]),
    ]


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
