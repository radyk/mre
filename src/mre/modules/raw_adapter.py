"""M1 — ERP Adapter for real raw_data/ CSV extracts.

Handles the real-data schema (OpenWorkOrder, Routing, RoutingLines, Product, BOM)
via plant_config.json for workcenter calendars and reference_date.

Key rules (all from the user spec):
- Demand ← OpenWorkOrder rows with ScheduleDate >= reference_date only.
  Out-of-window rows are counted in a Decision, not individual findings.
- Product resolved via WO.ProductNo directly (NOT via Routing.ProductNo).
  This fixes the legacy silent-drop of generic-route WOs.
- Process keyed by (route_code, product_no) to support generic routes.
- Duration: run_rate = ProductionMinutes / CostingLotSize min/unit (per-op, full rate).
  Setup: SetUpMinutes per op. Provenance policy: legacy_author_definition_v1.
- Resources: one per distinct Workcenter string "F001/D3001" (EXPLICIT_SET).
- EXCLUSIONS (error+excluded): missing product, zero lot size or zero production
  minutes, route missing or no active lines.
- PROCEEDED_FLAGGED: route Status=0, ApprovedStatus='R', WO.ProductNo !=
  Routing.ProductNo when routing is product-specific (ProductNo != '0').
- BOM: registered as input artifact only; no canonical entities.
- SalesOrder: out of scope for round one; not read.
"""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from mre.contracts.entities import (
    Calendar, Capability, CostModel, Demand, EntityRef, ExternalRef,
    OperationSpec, PrecedenceEdge, Process, Product, Quantity, Resource,
    ResourcePool, ResourceRequirement, SetupCostBasis, TardinessWeights, TimeWindow,
)
from mre.contracts.provenance import (
    DefaultedProvenance, DerivedProvenance, InputRef, ObservedProvenance,
    ProvenanceClass, ProvenanceSidecar,
)
from mre.contracts.vocabularies import (
    CommitmentClass, DecisionBasis, DecisionType, DemandStatus,
    DriverCode, FindingCode, FindingDisposition, FindingSeverity,
    LimitReason, ModuleCode, ProcessStatus, RecordTier,
    ResourceRequirementMode, ResourceType, RunStatus,
)
from mre.modules.adapter import AdapterResult, _stable_id, _synthesize_precedence_pairs
from mre.modules.identity_map import IdentityMap
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Plant config helpers
# ---------------------------------------------------------------------------

def load_plant_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _reference_date(config: dict) -> date:
    return date.fromisoformat(config["reference_date"])


def _reference_datetime(config: dict) -> datetime:
    d = _reference_date(config)
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=UTC)


def _workcenter_shift(config: dict, wc_full: str) -> dict:
    """Return the effective shift spec for a full workcenter string 'F001/D3001'."""
    overrides = config.get("facility_overrides", {})
    if wc_full in overrides:
        return {**config.get("workcenter_defaults", {}), **overrides[wc_full]}
    parts = wc_full.split("/", 1)
    wc_code = parts[1] if len(parts) == 2 else wc_full
    workcenters = config.get("workcenters", {})
    if wc_code in workcenters:
        return {**config.get("workcenter_defaults", {}), **workcenters[wc_code]}
    return config.get("workcenter_defaults", {})


def _shift_to_base_pattern(shift: dict) -> dict:
    return {
        "weekdays": shift.get("shift_days", [0, 1, 2, 3, 4, 5]),
        "shift_start": shift.get("shift_start", "07:00"),
        "shift_end": shift.get("shift_end", "19:00"),
    }


# ---------------------------------------------------------------------------
# CSV helpers (streaming-safe)
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Provenance factories
# ---------------------------------------------------------------------------

def _obs(entity_id: str, attr: str, snap: str, field: str, source: str = "ERP") -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snap,
        provenance_class=ProvenanceClass.OBSERVED,
        payload=ObservedProvenance(source_system=source, source_field=field,
                                   extract_ref="erp_extract"),
    )


def _obs_list(entity_id: str, attrs: list[str], snap: str,
              field_map: dict[str, str] | None = None) -> list[ProvenanceSidecar]:
    return [_obs(entity_id, a, snap, (field_map or {}).get(a, a)) for a in attrs]


def _def(entity_id: str, attr: str, snap: str, policy: str) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snap,
        provenance_class=ProvenanceClass.DEFAULTED,
        payload=DefaultedProvenance(policy=policy),
    )


def _def_list(entity_id: str, attrs: list[str], snap: str, policy: str) -> list[ProvenanceSidecar]:
    return [_def(entity_id, a, snap, policy) for a in attrs]


def _drv(entity_id: str, attr: str, snap: str, formula: str,
         inputs: list[tuple[str, str]]) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snap,
        provenance_class=ProvenanceClass.DERIVED,
        payload=DerivedProvenance(
            formula_id=formula,
            input_refs=[InputRef(entity_id=eid, attribute_name=aname, snapshot_id=snap)
                        for eid, aname in inputs],
        ),
    )


# ---------------------------------------------------------------------------
# RawAdapter
# ---------------------------------------------------------------------------

class RawAdapter:
    """Translate raw_data/ CSVs into a canonical snapshot + evidence records."""

    def __init__(self, raw_data_dir: Path, plant_config: dict) -> None:
        self._dir = Path(raw_data_dir)
        self._cfg = plant_config

    def run(
        self,
        snapshot_id: str,
        store: SnapshotStore,
        reporter: Reporter,
    ) -> AdapterResult:
        writer = store.begin_snapshot(snapshot_id)
        identity_map = IdentityMap()
        cfg = self._cfg
        ref_date = _reference_date(cfg)

        # Register input artifacts
        for fname in ("OpenWorkOrder.csv", "Routing.csv", "RoutingLines.csv",
                      "Product.csv", "BOM.csv"):
            p = self._dir / fname
            if p.exists():
                reporter.register_input(
                    artifact_id=fname,
                    artifact_hash=_file_hash(p),
                    profile={},
                )

        # ------------------------------------------------------------------
        # Load raw tables into memory
        # ------------------------------------------------------------------
        wo_rows = _read_csv(self._dir / "OpenWorkOrder.csv")
        routing_rows = _read_csv(self._dir / "Routing.csv")
        rl_rows = _read_csv(self._dir / "RoutingLines.csv")
        product_rows = _read_csv(self._dir / "Product.csv")

        # routing_map: RouteCode → {ProductNo, Status, ApprovedStatus}
        routing_map: dict[str, dict] = {r["RouteCode"].strip(): r for r in routing_rows}

        # product_map: ProductNo → row
        product_map: dict[str, dict] = {}
        for p in product_rows:
            pno = p.get("ProductNo", "").strip()
            if pno:
                product_map[pno] = p

        # routinglines_map: RoutingCode → [active rows sorted by Sequence]
        rl_map: dict[str, list[dict]] = {}
        for rl in rl_rows:
            rc = rl.get("RoutingCode", "").strip()
            if str(rl.get("Active", "0")).strip() == "1" and rc:
                rl_map.setdefault(rc, []).append(rl)
        for rc in rl_map:
            rl_map[rc].sort(key=lambda r: int(r.get("Sequence", "0") or "0"))

        # ------------------------------------------------------------------
        # Pre-pass: categorise WOs
        # ------------------------------------------------------------------
        out_of_window: list[dict] = []
        in_scope: list[dict] = []

        for row in wo_rows:
            sdate_str = row.get("ScheduleDate", "").strip()[:10]
            try:
                sdate = date.fromisoformat(sdate_str)
            except ValueError:
                out_of_window.append(row)
                continue
            if sdate < ref_date:
                out_of_window.append(row)
            else:
                in_scope.append(row)

        out_of_window_count = len(out_of_window)

        # Record the demand-selection policy as a single Decision
        reporter.record_decision(
            decision_type=DecisionType.INTERPRETATION,
            subjects=[],
            chosen=f"Include WOs with ScheduleDate >= {ref_date} ({len(in_scope)} rows)",
            alternatives=[
                {"option": "include all WOs",
                 "consequence": f"{out_of_window_count} historical WOs would inflate schedule"},
            ],
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
            policy_ref="plant_config_v1",
            message=(
                f"Demand selection: {len(in_scope)} in-scope, "
                f"{out_of_window_count} out-of-window (counted, not excluded as findings)"
            ),
            tier=RecordTier.HEADLINE,
        )

        # ------------------------------------------------------------------
        # Validate in-scope WOs; collect valid (route_code, product_no) pairs
        # ------------------------------------------------------------------
        ValidWO = tuple  # (row, route_code, product_no, product_row)
        valid_wos: list[tuple[dict, str, str, dict]] = []
        seen_wonos: set[str] = set()

        for row in in_scope:
            wono = row.get("Wono", "").strip()
            route_code = row.get("RouteCode", "").strip()
            wo_product_no = row.get("ProductNo", "").strip()

            # Dedup
            if wono in seen_wonos:
                dup_id = _stable_id("demand_excluded", wono + ":dup")
                reporter.record_finding(
                    code=FindingCode.DUPLICATE_IDENTITY,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=dup_id, entity_type="demand")],
                    evidence={"wono": wono, "reason": "duplicate Wono in extract"},
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue
            seen_wonos.add(wono)

            # Product resolution via WO.ProductNo (CORRECTION: not via routing)
            if wo_product_no not in product_map:
                excl_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.MISSING_REFERENCE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "product_no": wo_product_no,
                        "reason": "WO.ProductNo not found in Product.csv",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            prod_row = product_map[wo_product_no]

            # Duration data: CostingLotSize and ProductionMinutes on product
            try:
                lot_size = float(prod_row.get("CostingLotSize", "0") or "0")
            except ValueError:
                lot_size = 0.0
            try:
                prod_minutes = float(prod_row.get("ProductionMinutes", "0") or "0")
            except ValueError:
                prod_minutes = 0.0

            if lot_size <= 0.0 or prod_minutes <= 0.0:
                excl_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.VALUE_OUT_OF_RANGE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "product_no": wo_product_no,
                        "costing_lot_size": lot_size,
                        "production_minutes": prod_minutes,
                        "reason": "CostingLotSize or ProductionMinutes is 0; run_rate undefined",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            # Route existence
            if route_code not in routing_map:
                excl_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.MISSING_REFERENCE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "route_code": route_code,
                        "reason": "RouteCode not found in Routing.csv",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            # Active routing lines
            if route_code not in rl_map:
                excl_id = _stable_id("demand_excluded", wono)
                reporter.record_finding(
                    code=FindingCode.MISSING_REFERENCE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "route_code": route_code,
                        "reason": "No active RoutingLines for RouteCode",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )
                continue

            # Proceeded-flagged: route quality flags
            route_row = routing_map[route_code]
            demand_id_for_finding = _stable_id("demand", wono)

            if str(route_row.get("Status", "1")).strip() == "0":
                reporter.record_finding(
                    code=FindingCode.LOW_CONFIDENCE_INPUT,
                    severity=FindingSeverity.WARNING,
                    subjects=[EntityRef(entity_id=demand_id_for_finding, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "route_code": route_code,
                        "route_status": "0",
                        "reason": "Route Status=0 (inactive route); WO included but flagged",
                    },
                    disposition=FindingDisposition.PROCEEDED_FLAGGED,
                    tier=RecordTier.SUPPORTING,
                )

            if str(route_row.get("ApprovedStatus", "A")).strip() == "R":
                reporter.record_finding(
                    code=FindingCode.LOW_CONFIDENCE_INPUT,
                    severity=FindingSeverity.WARNING,
                    subjects=[EntityRef(entity_id=demand_id_for_finding, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "route_code": route_code,
                        "approved_status": "R",
                        "reason": "Route ApprovedStatus=R (rejected); WO included but flagged",
                    },
                    disposition=FindingDisposition.PROCEEDED_FLAGGED,
                    tier=RecordTier.SUPPORTING,
                )

            # ProductNo mismatch for product-specific routes (Routing.ProductNo != '0')
            routing_product_no = str(route_row.get("ProductNo", "0")).strip()
            if routing_product_no not in ("0", "") and routing_product_no != wo_product_no:
                reporter.record_finding(
                    code=FindingCode.AMBIGUOUS_SOURCE,
                    severity=FindingSeverity.WARNING,
                    subjects=[EntityRef(entity_id=demand_id_for_finding, entity_type="demand")],
                    evidence={
                        "wono": wono,
                        "wo_product_no": wo_product_no,
                        "routing_product_no": routing_product_no,
                        "route_code": route_code,
                        "reason": "WO.ProductNo differs from product-specific Routing.ProductNo",
                    },
                    disposition=FindingDisposition.PROCEEDED_FLAGGED,
                    tier=RecordTier.SUPPORTING,
                )

            valid_wos.append((row, route_code, wo_product_no, prod_row))

        # ------------------------------------------------------------------
        # Collect distinct workcenters from valid routes
        # ------------------------------------------------------------------
        valid_route_codes = {rc for _, rc, _, _ in valid_wos}
        wc_full_set: set[str] = set()
        for rc in valid_route_codes:
            for rl in rl_map.get(rc, []):
                wc = rl.get("Workcenter", "").strip()
                if wc:
                    wc_full_set.add(wc)

        # ------------------------------------------------------------------
        # Phase 1: Capabilities (one per workcenter_code)
        # ------------------------------------------------------------------
        wc_code_to_cap_id: dict[str, str] = {}
        for wc_full in wc_full_set:
            parts = wc_full.split("/", 1)
            wc_code = parts[1] if len(parts) == 2 else wc_full
            if wc_code not in wc_code_to_cap_id:
                cap_id = _stable_id("capability", wc_code)
                wc_code_to_cap_id[wc_code] = cap_id
                from mre.contracts.entities import Capability as Cap
                cap = Cap(
                    id=cap_id, snapshot_id=snapshot_id,
                    name=wc_code,
                    description=f"Workcenter code {wc_code}",
                )
                writer.write_entity(cap, _obs_list(cap_id, ["name", "description", "parameters"],
                                                   snapshot_id,
                                                   {"name": "Workcenter", "description": "Workcenter",
                                                    "parameters": "Workcenter"}))

        # ------------------------------------------------------------------
        # Phase 2: Calendars + Resources (one per full workcenter string)
        # ------------------------------------------------------------------
        wc_full_to_res_id: dict[str, str] = {}
        wc_full_to_cal_id: dict[str, str] = {}
        resource_rates: dict[str, float] = {}  # canonical id → $/min (plant_config.cost_model)
        resource_count = 0
        calendar_count = 0

        for wc_full in sorted(wc_full_set):
            parts = wc_full.split("/", 1)
            facility = parts[0] if len(parts) == 2 else ""
            wc_code = parts[1] if len(parts) == 2 else wc_full
            cap_id = wc_code_to_cap_id[wc_code]

            shift = _workcenter_shift(cfg, wc_full)
            parallel_units = shift.get("parallel_units", 1)
            base_pattern = _shift_to_base_pattern(shift)

            cal_id = _stable_id("calendar", f"wc:{wc_full}")
            cal = Calendar(
                id=cal_id, snapshot_id=snapshot_id,
                base_pattern=base_pattern,
                exceptions=[],
                horizon_resolved=[],
            )
            cal_prov = _def_list(cal_id,
                                 ["base_pattern", "exceptions", "horizon_resolved"],
                                 snapshot_id, "plant_config_v1")
            writer.write_entity(cal, cal_prov)
            wc_full_to_cal_id[wc_full] = cal_id
            calendar_count += 1

            res_id = _stable_id("resource", wc_full)
            wc_full_to_res_id[wc_full] = res_id

            # Cost-rate doorway (docs/06 §5.9 semantics on the raw path):
            # plant_config.cost_model supplies default_resource_rate_per_hour
            # plus optional per-workcenter overrides in resource_rates (keyed
            # by full 'F001/D3001' or bare code). Resource.cost_rate carries
            # the effective canonical $/minute value — the SAME value its
            # CostModel.resource_rates entry gets (single-source invariant,
            # tests/test_resource_rates.py). No cost_model key ⇒ 0.0,
            # exactly the pre-doorway behavior.
            cm_cfg = self._cfg.get("cost_model") or {}
            cfg_rates = cm_cfg.get("resource_rates") or {}
            rate_per_hour = cfg_rates.get(wc_full, cfg_rates.get(
                wc_code, cm_cfg.get("default_resource_rate_per_hour", 0.0)))
            rate_per_min = float(rate_per_hour or 0.0) / 60.0
            resource_rates[res_id] = rate_per_min

            res = Resource(
                id=res_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="workcenter", value=wc_full)],
                resource_type=ResourceType.MACHINE,
                capabilities=[wc_code],
                capacity=parallel_units,
                cost_rate=rate_per_min,
                calendar_ref=cal_id,
                pool_refs=[],
            )
            # Provenance: derived from RoutingLines references; cost_rate is
            # plant-config policy (or the absent-source zero default).
            res_attrs = ["resource_type", "capabilities", "capacity",
                         "calendar_ref", "pool_refs"]
            res_prov = [
                _drv(res_id, a, snapshot_id,
                     "referenced_by_routing_lines",
                     [(res_id, "workcenter_string")])
                for a in res_attrs
            ]
            res_prov.append(_def(
                res_id, "cost_rate", snapshot_id,
                "plant_config.cost_model" if cm_cfg else "raw_no_rate_source_default_zero",
            ))
            writer.write_entity(res, res_prov)
            identity_map.register(res_id, "ERP", "workcenter", wc_full)
            resource_count += 1

        # ------------------------------------------------------------------
        # Phase 3: ResourcePools (one per workcenter_code, reporting-only)
        # ------------------------------------------------------------------
        wc_code_to_members: dict[str, list[str]] = {}
        for wc_full, res_id in wc_full_to_res_id.items():
            parts = wc_full.split("/", 1)
            wc_code = parts[1] if len(parts) == 2 else wc_full
            wc_code_to_members.setdefault(wc_code, []).append(res_id)

        for wc_code, members in wc_code_to_members.items():
            pool_id = _stable_id("resourcepool", f"pool:{wc_code}")
            pool = ResourcePool(
                id=pool_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="workcenter_code", value=wc_code)],
                members=members,
                concurrent_capacity=None,
                calendar_ref=None,
                limit_reason=LimitReason.UNKNOWN,
            )
            pool_prov = _def_list(pool_id,
                                  ["members", "concurrent_capacity", "calendar_ref", "limit_reason"],
                                  snapshot_id, "plant_config_v1")
            writer.write_entity(pool, pool_prov)

        # ------------------------------------------------------------------
        # Phase 4: Products + Processes + OperationSpecs
        # ------------------------------------------------------------------
        # We need one (route_code, product_no) pair → Process + OperationSpecs.
        # For products that appear on multiple routes, the first route encountered
        # becomes the canonical process; subsequent routes get secondary Processes.
        written_processes: set[tuple[str, str]] = set()  # (route_code, product_no)
        prod_primary_process: dict[str, str] = {}  # product_no → first process_id
        product_count = 0
        process_count = 0
        op_spec_count = 0
        edge_count = 0

        # Collect unique (route_code, product_no) pairs
        pairs_needed: list[tuple[str, str, dict]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for _, rc, pno, prod_row in valid_wos:
            key = (rc, pno)
            if key not in seen_pairs:
                seen_pairs.add(key)
                pairs_needed.append((rc, pno, prod_row))

        # Write Products first (need process_ref; use first pair per product)
        products_written: set[str] = set()
        prod_first_process: dict[str, str] = {}  # pno → process_id for first route

        for rc, pno, prod_row in pairs_needed:
            process_id = _stable_id("process", f"{rc}:{pno}")
            if pno not in prod_first_process:
                prod_first_process[pno] = process_id

        for rc, pno, prod_row in pairs_needed:
            if pno in products_written:
                continue
            products_written.add(pno)
            prod_id = _stable_id("product", pno)
            process_id = prod_first_process[pno]
            family = (prod_row.get("ProductGroup") or "").strip() or None

            prod = Product(
                id=prod_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="product_no", value=pno)],
                name=prod_row.get("ProductNo", pno),
                unit_of_measure=prod_row.get("UOM", "PCS"),
                process_ref=process_id,
                product_family=family,
            )
            prod_prov = _obs_list(prod_id,
                                  ["name", "unit_of_measure", "process_ref", "product_family"],
                                  snapshot_id,
                                  {"name": "ProductNo", "unit_of_measure": "UOM",
                                   "process_ref": "RouteCode", "product_family": "ProductGroup"})
            writer.write_entity(prod, prod_prov)
            identity_map.register(prod_id, "ERP", "product_no", pno)
            product_count += 1

        # Write Processes + OperationSpecs
        for rc, pno, prod_row in pairs_needed:
            if (rc, pno) in written_processes:
                continue
            written_processes.add((rc, pno))

            prod_id = _stable_id("product", pno)
            process_id = _stable_id("process", f"{rc}:{pno}")

            try:
                lot_size = float(prod_row.get("CostingLotSize", "0") or "0")
                prod_minutes = float(prod_row.get("ProductionMinutes", "0") or "0")
                setup_minutes = float(prod_row.get("SetUpMinutes", "0") or "0")
            except ValueError:
                continue  # already excluded in pre-pass

            run_rate = timedelta(minutes=prod_minutes / lot_size)
            base_setup = timedelta(minutes=setup_minutes)

            spec_ids: list[str] = []
            for rl in rl_map.get(rc, []):
                seq = int(rl.get("Sequence", "0") or "0")
                wc_full = rl.get("Workcenter", "").strip()
                spec_id = _stable_id("operationspec", f"{rc}:{pno}:{seq}")

                res_id = wc_full_to_res_id.get(wc_full)
                if res_id is None:
                    continue  # workcenter not in scope

                req = ResourceRequirement(
                    mode=ResourceRequirementMode.EXPLICIT_SET,
                    resource_refs=[res_id],
                )

                # Splittability doorway (docs/05 R-C3): raw routing lines
                # carry no splittable column, so resumability is a plant-
                # config declaration per workcenter ("operations at this
                # workcenter may pause at calendar boundaries"), with an
                # optional min_chunk_minutes. Undeclared -> false, exactly
                # the pre-doorway behavior.
                wc_shift = _workcenter_shift(self._cfg, wc_full)
                wc_splittable = bool(wc_shift.get("splittable", False))
                wc_min_chunk = float(wc_shift.get("min_chunk_minutes", 0) or 0)

                spec = OperationSpec(
                    id=spec_id, snapshot_id=snapshot_id,
                    sequence=seq,
                    resource_requirements=[req],
                    setup_family="",  # no setup transitions in real data
                    base_setup=base_setup,
                    run_rate=run_rate,
                    splittable=wc_splittable,
                    min_chunk=(timedelta(minutes=wc_min_chunk)
                               if wc_splittable and wc_min_chunk > 0 else None),
                )
                # Provenance: run_rate derived from product data (RULING: legacy_author_definition_v1)
                spec_attrs_obs = ["sequence", "resource_requirements", "setup_family",
                                  "yield_factor"]
                spec_prov = _obs_list(spec_id, spec_attrs_obs, snapshot_id,
                                      {"sequence": "Sequence",
                                       "resource_requirements": "Workcenter",
                                       "setup_family": "Workcenter",
                                       "yield_factor": "RoutingLines"})
                # splittable/min_chunk are plant-config policy (or the
                # absent-source default) — never observed from RoutingLines,
                # which has no such column. (The pre-doorway code wrote
                # observed sidecars citing RoutingLines for these: false.)
                splittable_policy = ("plant_config.workcenters.splittable"
                                     if wc_splittable else "raw_no_splittable_source_default_false")
                spec_prov += [
                    _def(spec_id, "splittable", snapshot_id, splittable_policy),
                    _def(spec_id, "min_chunk", snapshot_id, splittable_policy),
                ]
                spec_prov += [
                    _drv(spec_id, "base_setup", snapshot_id,
                         "legacy_author_definition_v1",
                         [(prod_id, "SetUpMinutes")]),
                    _drv(spec_id, "run_rate", snapshot_id,
                         "legacy_author_definition_v1",
                         [(prod_id, "ProductionMinutes"), (prod_id, "CostingLotSize")]),
                ]
                writer.write_entity(spec, spec_prov)
                spec_ids.append(spec_id)
                op_spec_count += 1

            if not spec_ids:
                continue

            process = Process(
                id=process_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="route_code", value=rc)],
                product_ref=prod_id,
                operation_specs=spec_ids,
                version=1,
                effective_from=None,
                status=ProcessStatus.ACTIVE,
            )
            proc_prov = _obs_list(process_id,
                                  ["product_ref", "operation_specs", "version",
                                   "effective_from", "status"],
                                  snapshot_id,
                                  {"product_ref": "ProductNo", "operation_specs": "RoutingLines",
                                   "version": "Routing", "effective_from": "ApprovedDate",
                                   "status": "Status"})
            writer.write_entity(process, proc_prov)
            process_count += 1

            # PrecedenceEdges: linear chain synthesized from RoutingLines
            # Sequence (docs/05 A1). No Dwell column in the real extract
            # (RoutingLines carries TargetTime, unpopulated) so min_lag is 0 —
            # same effective behavior as the old implicit sequence model.
            for pred_spec_id, succ_spec_id in _synthesize_precedence_pairs(spec_ids):
                edge_id = _stable_id("precedenceedge", f"{pred_spec_id}:{succ_spec_id}")
                edge = PrecedenceEdge(
                    id=edge_id, snapshot_id=snapshot_id,
                    predecessor=pred_spec_id, successor=succ_spec_id,
                    min_lag=timedelta(0), max_lag=None,
                )
                writer.write_entity(
                    edge,
                    _obs_list(edge_id, ["predecessor", "successor"], snapshot_id,
                             {"predecessor": "Sequence", "successor": "Sequence"})
                    + _def_list(edge_id, ["min_lag", "max_lag"], snapshot_id,
                               "no_dwell_source_in_raw_data"),
                )
                edge_count += 1

        # ------------------------------------------------------------------
        # Phase 5: Demands
        # ------------------------------------------------------------------
        demand_count = 0

        for row, route_code, wo_product_no, prod_row in valid_wos:
            wono = row.get("Wono", "").strip()
            demand_id = _stable_id("demand", wono)
            prod_id = _stable_id("product", wo_product_no)

            try:
                qty = float(row.get("WoQuantity", "0") or "0")
            except ValueError:
                qty = 0.0

            # due: ScheduleDate as end-of-day UTC
            sdate_str = row.get("ScheduleDate", "").strip()[:10]
            try:
                sd = date.fromisoformat(sdate_str)
                due_dt = datetime(sd.year, sd.month, sd.day, 23, 59, 59, tzinfo=UTC)
            except ValueError:
                due_dt = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

            # earliest_start: CreatedDate floor
            earliest_start: Optional[datetime] = None
            cd_str = row.get("CreatedDate", "").strip()
            if cd_str:
                try:
                    earliest_start = datetime.fromisoformat(cd_str[:19]).replace(tzinfo=UTC)
                except ValueError:
                    pass

            uom = prod_row.get("UOM", "PCS")
            demand = Demand(
                id=demand_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="ERP", type="work_order", value=wono)],
                product_ref=prod_id,
                quantity=Quantity(value=qty, uom=uom),
                due=due_dt,
                earliest_start=earliest_start,
                commitment_class=CommitmentClass.STANDARD,
                customer_weight=1.0,
                customer_ref=None,
                status=DemandStatus.OPEN,
            )
            d_prov = _obs_list(demand_id,
                               ["product_ref", "quantity", "due", "earliest_start"],
                               snapshot_id,
                               {"product_ref": "ProductNo", "quantity": "WoQuantity",
                                "due": "ScheduleDate", "earliest_start": "CreatedDate"})
            d_prov += _def_list(demand_id,
                                ["commitment_class", "customer_weight", "customer_ref", "status"],
                                snapshot_id, "plant_config_v1")
            writer.write_entity(demand, d_prov)
            identity_map.register(demand_id, "ERP", "work_order", wono)
            demand_count += 1

        # Also record FacilityCode as attribute metadata in the identity map
        # (opaque attribute on demands — not a canonical field)
        for row, _, _, _ in valid_wos:
            wono = row.get("Wono", "").strip()
            demand_id = _stable_id("demand", wono)
            identity_map.register(demand_id, "ERP", "facility_code",
                                  row.get("FacilityCode", "").strip())

        # ------------------------------------------------------------------
        # Phase 6: Minimal defaulted CostModel
        # ------------------------------------------------------------------
        # plant_config.cost_model (docs/06 §5.9 semantics on the raw path):
        # hour-denominated economics translated to canonical $/minute here —
        # the same one-place-divides-by-60 rule the IDS adapter follows.
        # Absent ⇒ the historical zero-rate default, warned as before.
        cm_cfg = self._cfg.get("cost_model") or {}
        cm_version_label = "plant_config_cost_model_v1" if cm_cfg else "raw_data_default_v1"
        cm_id = _stable_id("costmodel", cm_version_label)
        tard_per_hour = cm_cfg.get("tardiness_cost_per_hour")
        cm = CostModel(
            id=cm_id, snapshot_id=snapshot_id,
            version=1,
            effective_from=None,
            resource_rates={rid: r for rid, r in resource_rates.items()} if cm_cfg else {},
            setup_cost_basis=SetupCostBasis(
                fixed_per_setup=float(cm_cfg.get("setup_cost_per_setup", 0.0) or 0.0),
                scrap_cost_per_unit=0.0,
            ),
            tardiness_weights=TardinessWeights(
                base_weight=(float(tard_per_hour) / 60.0
                             if tard_per_hour is not None else 1.0),
            ),
            overtime_premium=float(cm_cfg.get("overtime_premium_multiplier", 0.0) or 0.0),
            inventory_carrying=0.0,
        )
        cm_prov = _def_list(cm_id,
                            ["version", "effective_from", "resource_rates",
                             "setup_cost_basis", "tardiness_weights",
                             "overtime_premium", "inventory_carrying"],
                            snapshot_id, cm_version_label)
        writer.write_entity(cm, cm_prov)
        if not cm_cfg:
            reporter.record_finding(
                code=FindingCode.LOW_CONFIDENCE_INPUT,
                severity=FindingSeverity.WARNING,
                subjects=[EntityRef(entity_id=cm_id, entity_type="costmodel")],
                evidence={
                    "reason": "No cost rates in raw_data; all resource rates default to 0.0",
                    "affected_resources": resource_count,
                },
                disposition=FindingDisposition.DEFAULTED,
                disposition_detail=("CostModel version raw_data_default_v1 — add a "
                                    "cost_model section to plant_config to price the plant"),
                tier=RecordTier.HEADLINE,
            )

        # ------------------------------------------------------------------
        # Phase 7: BOM — opaque input, no canonical entities
        # ------------------------------------------------------------------
        bom_path = self._dir / "BOM.csv"
        if bom_path.exists():
            bom_rows = _read_csv(bom_path)
            reporter.record_metric(
                name="bom_row_count",
                value=len(bom_rows),
                unit="rows",
                subjects=[],
            )
            reporter.record_event(
                status_text="bom_ingested_as_opaque",
                message=(
                    f"BOM.csv ({len(bom_rows)} rows) registered as input; "
                    "no scheduling role in round one"
                ),
            )

        # ------------------------------------------------------------------
        # Finalize
        # ------------------------------------------------------------------
        writer.write_identity_map(identity_map)
        writer.finalize()

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
            process_count=process_count,
            calendar_count=calendar_count,
            costmodel_id=cm_id,
            constraint_id=None,
            identity_map=identity_map,
            store=store,
            out_of_window_count=out_of_window_count,
            precedence_edge_count=edge_count,
        )
