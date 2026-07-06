"""M1 — ERP Adapter.

The only ERP-aware code in the system. Reads CSV extracts in legacy ERP shapes,
translates to canonical entities, writes to a SnapshotStore, and emits evidence
records (findings + decisions) via the Reporter.

ERP shapes (from legacy/Formatnewjobs.py):
    openworkorder: Wono, RouteCode, ScheduleDate, WoQuantity, CustomerNo, Priority, ReleaseDate
    routing:       RouteCode, ProductNo, Description
    routinglines:  RoutingCode, Sequence, Workcenter, Active, Description
    product:       ProductNo, ProductName, ProductFamily, CostingLotSize,
                   SetUpMinutes, ProductionMinutes, UnitOfMeasure
    machines:      MachineID, MachineName, Capability, CostRate
    workcenters:   WorkcenterID, WorkcenterName, Machines, Capacity, CapabilityCode

Hard rules:
- ERP identifiers appear only inside external_refs.
- run_rate is stored as a per-unit timedelta; never pre-multiplied.
- No attribute write without its provenance record.
- Every finding/decision for an entity carries non-empty subjects.
"""
from __future__ import annotations

import csv
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from mre.contracts.entities import (
    Capability, Demand, ExternalRef, EntityRef, OperationSpec, Product,
    Quantity, Resource, ResourcePool, ResourceRequirement,
)
from mre.contracts.provenance import (
    ProvenanceSidecar, SynthesizedProvenance, ObservedProvenance, ProvenanceClass,
)
from mre.contracts.vocabularies import (
    CommitmentClass, DemandStatus, DriverCode, FindingCode, FindingDisposition,
    FindingSeverity, ModuleCode, RecordTier, ResourceRequirementMode, ResourceType,
    DecisionType, DecisionBasis,
)
from mre.modules.snapshot_store import SnapshotStore, SnapshotWriter
from mre.reporter import Reporter

UTC = timezone.utc

# Fallback run_rate used when CostingLotSize=0 (avoids division by zero).
_FALLBACK_RUN_RATE_SECONDS = 600  # 10 minutes per unit


class IdentityMap:
    """Bidirectional map: (system, type, value) ↔ canonical_id."""

    def __init__(self) -> None:
        self._to_canonical: dict[tuple[str, str, str], str] = {}
        self._from_canonical: dict[str, list[tuple[str, str, str]]] = {}

    def register(self, canonical_id: str, system: str, ref_type: str, value: str) -> None:
        key = (system, ref_type, value)
        self._to_canonical[key] = canonical_id
        self._from_canonical.setdefault(canonical_id, []).append(key)

    def resolve(self, system: str, ref_type: str, value: str) -> Optional[str]:
        return self._to_canonical.get((system, ref_type, value))

    def external_refs(self, canonical_id: str) -> list[ExternalRef]:
        return [
            ExternalRef(system=s, type=t, value=v)
            for s, t, v in self._from_canonical.get(canonical_id, [])
        ]


@dataclass
class AdapterResult:
    demand_count: int
    product_count: int
    resource_count: int
    operation_spec_count: int
    identity_map: IdentityMap
    store: SnapshotStore


def _stable_id(namespace: str, value: str) -> str:
    """Deterministic UUID5 from a namespace+value pair."""
    ns = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
    return str(uuid.uuid5(ns, f"{namespace}:{value}"))


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _priority_to_commitment(priority: str) -> CommitmentClass:
    mapping = {"Rush": CommitmentClass.RUSH, "Firm": CommitmentClass.FIRM}
    return mapping.get(priority, CommitmentClass.STANDARD)


class Adapter:
    """Translate ERP CSV extracts into a canonical snapshot + evidence records."""

    def __init__(
        self,
        extract_dir: Path,
        synthesized_generator: Optional[str] = None,
    ) -> None:
        self._dir = Path(extract_dir)
        self._gen = synthesized_generator

    # ------------------------------------------------------------------
    # Provenance factory
    # ------------------------------------------------------------------
    def _prov(
        self,
        entity_id: str,
        attribute_name: str,
        snapshot_id: str,
        source_field: str = "",
        extract_ref: str = "",
    ) -> ProvenanceSidecar:
        if self._gen:
            payload = SynthesizedProvenance(generator_id=self._gen)
            pclass = ProvenanceClass.SYNTHESIZED
        else:
            payload = ObservedProvenance(
                source_system="ERP",
                source_field=source_field or attribute_name,
                extract_ref=extract_ref or "erp_extract",
            )
            pclass = ProvenanceClass.OBSERVED
        return ProvenanceSidecar(
            entity_id=entity_id,
            attribute_name=attribute_name,
            snapshot_id=snapshot_id,
            provenance_class=pclass,
            payload=payload,
        )

    def _prov_list(
        self,
        entity_id: str,
        attrs: list[str],
        snapshot_id: str,
        extract_ref: str = "",
    ) -> list[ProvenanceSidecar]:
        return [self._prov(entity_id, a, snapshot_id, extract_ref=extract_ref) for a in attrs]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        snapshot_id: str,
        store: SnapshotStore,
        reporter: Reporter,
    ) -> AdapterResult:
        writer = store.begin_snapshot(snapshot_id)
        identity_map = IdentityMap()

        # Register input manifests
        for fname in ("openworkorder.csv", "routing.csv", "routinglines.csv",
                       "product.csv", "machines.csv", "workcenters.csv"):
            path = self._dir / fname
            if path.exists():
                reporter.register_input(
                    artifact_id=fname,
                    artifact_hash=_file_hash(path),
                    profile={"row_count": sum(1 for _ in open(path)) - 1},
                )

        # Load all CSVs
        wo_rows = _read_csv(self._dir / "openworkorder.csv")
        routing_rows = _read_csv(self._dir / "routing.csv")
        routinglines_rows = _read_csv(self._dir / "routinglines.csv")
        product_rows = _read_csv(self._dir / "product.csv")
        machine_rows = _read_csv(self._dir / "machines.csv")
        workcenter_rows = _read_csv(self._dir / "workcenters.csv")

        # Build lookup tables
        routing_map: dict[str, str] = {}  # RouteCode → ProductNo
        for r in routing_rows:
            routing_map[r["RouteCode"]] = r["ProductNo"]

        product_map: dict[str, dict] = {}  # ProductNo → row dict
        for p in product_rows:
            product_map[p["ProductNo"]] = p

        routinglines_map: dict[str, list[dict]] = {}  # RoutingCode → [active rows sorted by seq]
        for rl in routinglines_rows:
            if str(rl.get("Active", "0")) == "1":
                routinglines_map.setdefault(rl["RoutingCode"], []).append(rl)
        for code in routinglines_map:
            routinglines_map[code].sort(key=lambda r: int(r["Sequence"]))

        workcenter_map: dict[str, dict] = {}  # WorkcenterID → row
        for wc in workcenter_rows:
            workcenter_map[wc["WorkcenterID"]] = wc

        machine_map: dict[str, dict] = {}  # MachineID → row
        for m in machine_rows:
            machine_map[m["MachineID"]] = m

        # ------------------------------------------------------------------
        # Phase 1: Translate Products, Capabilities, Resources, ResourcePools
        # ------------------------------------------------------------------
        product_count = 0
        resource_count = 0
        op_spec_count = 0
        canonical_products: dict[str, Product] = {}  # ProductNo → Product

        # Capabilities by code (one per unique capability string)
        capabilities_written: set[str] = set()

        def _ensure_capability(cap_code: str, snap_id: str) -> str:
            cap_id = _stable_id("capability", cap_code)
            if cap_code not in capabilities_written:
                cap = Capability(
                    id=cap_id, snapshot_id=snap_id,
                    name=cap_code,
                    description=cap_code.replace("_", " ").title(),
                )
                cap_attrs = ["name", "description", "parameters"]
                writer.write_entity(cap, self._prov_list(cap_id, cap_attrs, snap_id))
                capabilities_written.add(cap_code)
            return cap_id

        # Resources (machines)
        for row in machine_rows:
            mid = row["MachineID"]
            rid = _stable_id("resource", mid)
            cap_code = row.get("Capability", "").strip()
            cap_id = _ensure_capability(cap_code, snapshot_id) if cap_code else None
            res = Resource(
                id=rid,
                snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="machine_id", value=mid)],
                resource_type=ResourceType.MACHINE,
                capabilities=[cap_code] if cap_code else [],
                capacity=1,
                cost_rate=float(row.get("CostRate", 0.0)),
                calendar_ref=None,
                pool_refs=[],
            )
            attrs = ["resource_type", "capabilities", "capacity", "cost_rate",
                     "calendar_ref", "pool_refs"]
            writer.write_entity(res, self._prov_list(rid, attrs, snapshot_id))
            identity_map.register(rid, "ERP", "machine_id", mid)
            resource_count += 1

        # ResourcePools (workcenters) — three-way split per docs/01 §5.4
        for row in workcenter_rows:
            wc_id = row["WorkcenterID"]
            pool_id = _stable_id("resourcepool", wc_id)
            cap_code = row.get("CapabilityCode", "").strip()
            machine_names = [m.strip() for m in row.get("Machines", "").split(";") if m.strip()]
            member_ids = [
                _stable_id("resource", m) for m in machine_names if m in machine_map
            ]
            pool = ResourcePool(
                id=pool_id,
                snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="workcenter_id", value=wc_id)],
                members=member_ids,
                concurrent_capacity=int(row.get("Capacity", len(member_ids))),
                calendar_ref=None,
            )
            attrs = ["members", "concurrent_capacity", "calendar_ref", "limit_reason"]
            writer.write_entity(pool, self._prov_list(pool_id, attrs, snapshot_id))
            identity_map.register(pool_id, "ERP", "workcenter_id", wc_id)

        # Products (includes OperationSpecs per routing)
        for row in product_rows:
            pno = row["ProductNo"]
            prod_id = _stable_id("product", pno)
            uom = row.get("UnitOfMeasure", "EA")
            family = row.get("ProductFamily", "").strip() or None

            prod = Product(
                id=prod_id,
                snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="product_no", value=pno)],
                name=row.get("ProductName", pno),
                unit_of_measure=uom,
                process_ref=None,
                product_family=family,
            )
            prod_attrs = ["name", "unit_of_measure", "process_ref", "product_family"]
            writer.write_entity(prod, self._prov_list(prod_id, prod_attrs, snapshot_id))
            identity_map.register(prod_id, "ERP", "product_no", pno)
            canonical_products[pno] = prod
            product_count += 1

            # Build OperationSpecs from routinglines for this product
            route_code = next(
                (rc for rc, pn in routing_map.items() if pn == pno), None
            )
            if route_code and route_code in routinglines_map:
                lot_size_str = row.get("CostingLotSize", "0")
                try:
                    lot_size = float(lot_size_str)
                except (ValueError, TypeError):
                    lot_size = 0.0

                prod_minutes_str = row.get("ProductionMinutes", "0")
                try:
                    prod_minutes = float(prod_minutes_str)
                except (ValueError, TypeError):
                    prod_minutes = 0.0

                setup_minutes_str = row.get("SetUpMinutes", "0")
                try:
                    setup_minutes = float(setup_minutes_str)
                except (ValueError, TypeError):
                    setup_minutes = 0.0

                use_fallback = lot_size <= 0.0
                if use_fallback:
                    run_rate = timedelta(seconds=_FALLBACK_RUN_RATE_SECONDS)
                    # LOW_CONFIDENCE_INPUT for each affected OperationSpec
                    reporter.record_finding(
                        code=FindingCode.LOW_CONFIDENCE_INPUT,
                        severity=FindingSeverity.WARNING,
                        subjects=[EntityRef(entity_id=prod_id, entity_type="product")],
                        evidence={
                            "product_no": pno,
                            "costing_lot_size": lot_size,
                            "reason": "CostingLotSize=0; run_rate cannot be derived; fallback applied",
                            "fallback_seconds": _FALLBACK_RUN_RATE_SECONDS,
                        },
                        disposition=FindingDisposition.DEFAULTED,
                        tier=RecordTier.SUPPORTING,
                    )
                else:
                    run_rate = timedelta(seconds=(prod_minutes / lot_size) * 60)

                for rl in routinglines_map[route_code]:
                    seq = int(rl["Sequence"])
                    wc = rl["Workcenter"].strip()
                    spec_id = _stable_id("operationspec", f"{route_code}:{seq}")

                    # Resolve workcenter to ResourceRequirement
                    if wc in workcenter_map:
                        wc_row = workcenter_map[wc]
                        cap_code = wc_row.get("CapabilityCode", "").strip()
                        if cap_code:
                            _ensure_capability(cap_code, snapshot_id)
                            req = ResourceRequirement(
                                mode=ResourceRequirementMode.CAPABILITY,
                                capability_ref=_stable_id("capability", cap_code),
                            )
                        else:
                            machine_names_wc = [
                                m.strip() for m in wc_row.get("Machines", "").split(";")
                                if m.strip()
                            ]
                            req = ResourceRequirement(
                                mode=ResourceRequirementMode.EXPLICIT_SET,
                                resource_refs=[_stable_id("resource", m)
                                               for m in machine_names_wc
                                               if m in machine_map],
                            )
                    else:
                        # Unknown workcenter → UNMAPPABLE_VALUE
                        reporter.record_finding(
                            code=FindingCode.UNMAPPABLE_VALUE,
                            severity=FindingSeverity.WARNING,
                            subjects=[EntityRef(entity_id=prod_id, entity_type="product")],
                            evidence={
                                "routing_code": route_code,
                                "sequence": seq,
                                "workcenter": wc,
                                "reason": f"Workcenter '{wc}' not found in workcenter reference",
                            },
                            disposition=FindingDisposition.PROCEEDED_FLAGGED,
                            tier=RecordTier.SUPPORTING,
                        )
                        # No ResourceRequirement — workcenter is unresolvable.
                        # NO_CAPABLE_RESOURCE will flag this at validation time.
                        req = None

                    reqs = [req] if req is not None else []
                    spec = OperationSpec(
                        id=spec_id,
                        snapshot_id=snapshot_id,
                        sequence=seq,
                        resource_requirements=reqs,
                        setup_family=family or "",
                        base_setup=timedelta(minutes=setup_minutes),
                        run_rate=run_rate,
                    )
                    spec_attrs = [
                        "sequence", "resource_requirements", "setup_family",
                        "base_setup", "run_rate", "dwell_rule", "splittable",
                        "min_chunk", "yield_factor",
                    ]
                    writer.write_entity(spec, self._prov_list(spec_id, spec_attrs, snapshot_id))
                    op_spec_count += 1

        # ------------------------------------------------------------------
        # Phase 2: Translate Work Orders → Demands
        # ------------------------------------------------------------------
        demand_count = 0
        seen_wonos: dict[str, str] = {}  # Wono → canonical demand_id (first occurrence)

        for row in wo_rows:
            wono = row["Wono"].strip()
            route_code = row["RouteCode"].strip()
            schedule_date_str = row.get("ScheduleDate", "").strip()
            qty_str = row.get("WoQuantity", "0").strip()
            customer_no = row.get("CustomerNo", "").strip() or None
            priority = row.get("Priority", "Normal").strip()
            release_date_str = row.get("ReleaseDate", "").strip()

            # --- Defect 6: DUPLICATE_IDENTITY ---
            if wono in seen_wonos:
                # Mint a temporary id for the finding subject
                dup_id = _stable_id("demand_excluded", wono + ":dup")
                reporter.record_finding(
                    code=FindingCode.DUPLICATE_IDENTITY,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=dup_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "kept_canonical_id": seen_wonos[wono],
                        "reason": f"Work order '{wono}' appears more than once; second occurrence excluded",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                reporter.record_decision(
                    decision_type=DecisionType.IDENTITY_RESOLUTION,
                    chosen=seen_wonos[wono],
                    alternatives=[],
                    subjects=[EntityRef(entity_id=seen_wonos[wono], entity_type="demand")],
                    driver=DriverCode.DATA_EXCLUSION,
                    basis=DecisionBasis.POLICY_APPLIED,
                    message=f"Duplicate WO '{wono}': first occurrence kept",
                    tier=RecordTier.SUPPORTING,
                )
                continue

            # --- Defect 1: MISSING_REFERENCE ---
            if route_code not in routing_map:
                excluded_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.MISSING_REFERENCE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excluded_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "route_code": route_code,
                        "reason": f"RouteCode '{route_code}' not found in routing reference",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            pno = routing_map[route_code]
            if pno not in product_map:
                excluded_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.MISSING_REFERENCE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excluded_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "product_no": pno,
                        "reason": f"ProductNo '{pno}' from routing not found in product reference",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            # Parse fields
            try:
                qty = float(qty_str)
            except (ValueError, TypeError):
                qty = 0.0

            try:
                due_dt = datetime.fromisoformat(schedule_date_str).replace(
                    hour=23, minute=59, second=59, tzinfo=UTC
                )
            except (ValueError, TypeError):
                due_dt = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

            earliest_start: Optional[datetime] = None
            if release_date_str:
                try:
                    earliest_start = datetime.fromisoformat(release_date_str).replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    pass

            prod_id = _stable_id("product", pno)
            demand_id = _stable_id("demand", wono)
            uom = product_map[pno].get("UnitOfMeasure", "EA")

            demand = Demand(
                id=demand_id,
                snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="work_order", value=wono)],
                product_ref=prod_id,
                quantity=Quantity(value=qty, uom=uom),
                due=due_dt,
                earliest_start=earliest_start,
                commitment_class=_priority_to_commitment(priority),
                customer_weight=1.0,
                customer_ref=customer_no,
                status=DemandStatus.OPEN,
            )

            d_attrs = [
                "product_ref", "quantity", "due", "earliest_start",
                "commitment_class", "customer_weight", "customer_ref", "status",
            ]
            writer.write_entity(demand, self._prov_list(demand_id, d_attrs, snapshot_id))
            identity_map.register(demand_id, "ERP", "work_order", wono)
            seen_wonos[wono] = demand_id
            demand_count += 1

        writer.finalize()

        # Register identity map as an output artifact
        reporter.register_output(
            artifact_ref="identity_map",
            artifact_hash=hashlib.sha256(
                str(sorted(identity_map._to_canonical.items())).encode()
            ).hexdigest()[:16],
        )

        return AdapterResult(
            demand_count=demand_count,
            product_count=product_count,
            resource_count=resource_count,
            operation_spec_count=op_spec_count,
            identity_map=identity_map,
            store=store,
        )
