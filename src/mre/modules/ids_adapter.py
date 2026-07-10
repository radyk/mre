"""M1 extension — IDS Adapter.

Translates an IDS-conformant submission (docs/06) into a canonical snapshot.
Manifest-driven semantics replace hardcoded rulings where the manifest
declares them. New doorways translate:

  customers.csv        -> customer_ref + customer_weight, via
                           cost_model.core.priority_multipliers and
                           manifest.semantics.priority_precedence
  setup_transitions.csv -> Constraint(SETUP_TRANSITION)
  locks.csv             -> Constraint(FROZEN_ASSIGNMENT / PINNED_WINDOW),
                           provenance_class=human_override, carries authority
  commitment_class      -> Demand.commitment_class
  calendars.csv 'added'/overtime rows -> CalendarException, priced via
                           cost_model.refinements.overtime_premium_multiplier

Unit note: docs/06 cost_model.json expresses rates per HOUR
(default_resource_rate_per_hour) and tardiness cost per HOUR
(tardiness_cost_per_hour). The solver (M5) prices in $/minute against
duration-in-minutes (legacy convention, see sample_data/costmodel.json).
This adapter is the one place that divides by 60 — CostModel.resource_rates,
Resource.cost_rate (the same effective value; single-source invariant, see
tests/test_resource_rates.py) and CostModel.tardiness_weights.base_weight are
stored in $/minute so no downstream module needs to know about the
hour/minute distinction.

Only the ERP-shape (IDS-shape) concerns live here; canonical entity shapes
are identical to those produced by Adapter/RawAdapter so the rest of the
pipeline (M3-M7) needs no IDS-specific branching.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.entities import (
    Calendar, CalendarException, Constraint, CostModel, Demand, EntityRef,
    ExternalRef, OperationSpec, PrecedenceEdge, Process, Product, Quantity,
    Resource, ResourceRequirement, SetupCostBasis, TardinessWeights, TimeWindow,
    WipOperationObservation,
)
from mre.contracts.provenance import (
    DefaultedProvenance, DerivedProvenance, InputRef, ObservedProvenance,
    ProvenanceClass, ProvenanceSidecar,
)
from mre.contracts.vocabularies import (
    CalendarExceptionReason, CalendarExceptionType, CommitmentClass,
    ConstraintHardness, ConstraintProvenance, ConstraintType, DemandStatus,
    FindingCode, FindingDisposition, FindingSeverity, ProcessStatus,
    RecordTier, ResourceRequirementMode, ResourceType, WipStatus,
)
from mre.modules.adapter import AdapterResult, _stable_id, _synthesize_precedence_pairs
from mre.modules.identity_map import IdentityMap
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

UTC = timezone.utc

_KNOWN_EXCEPTION_REASONS = {r.value for r in CalendarExceptionReason}
_COMMITMENT_MAP = {"standard": CommitmentClass.STANDARD, "rush": CommitmentClass.RUSH,
                    "firm": CommitmentClass.FIRM}


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _obs(entity_id: str, attr: str, snap: str, field: str) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id, attribute_name=attr, snapshot_id=snap,
        provenance_class=ProvenanceClass.OBSERVED,
        payload=ObservedProvenance(source_system="IDS", source_field=field, extract_ref="ids_submission"),
    )


def _obs_list(entity_id: str, attrs: list[str], snap: str,
              field_map: Optional[dict[str, str]] = None) -> list[ProvenanceSidecar]:
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


def _parse_due(raw: str, time_of_day: str) -> datetime:
    raw = (raw or "").strip()
    has_time = len(raw) > 10 and raw[10] in ("T", " ")
    try:
        if has_time:
            dt = datetime.fromisoformat(raw.replace(" ", "T", 1) if raw[10] == " " else raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        d = date.fromisoformat(raw[:10])
    except ValueError:
        return datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC)
    if time_of_day == "as_stated":
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=UTC)
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)


def _parse_dt(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw[:19])
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class IDSAdapter:
    """Translate an IDS submission directory into a canonical snapshot."""

    def __init__(self, submission_dir: Path, manifest: Optional[dict] = None) -> None:
        self._dir = Path(submission_dir)
        self._manifest = manifest

    def run(self, snapshot_id: str, store: SnapshotStore, reporter: Reporter) -> AdapterResult:
        writer = store.begin_snapshot(snapshot_id)
        identity_map = IdentityMap()

        manifest = self._manifest
        if manifest is None:
            manifest = json.loads((self._dir / "manifest.json").read_text(encoding="utf-8"))
        semantics = manifest.get("semantics", {})
        due_tod = semantics.get("due_date_time_of_day", "end_of_day")
        priority_precedence = semantics.get("priority_precedence", "customer_over_order")

        all_files = ("orders.csv", "routings.csv", "routing_lines.csv", "products.csv",
                     "resources.csv", "calendars.csv", "cost_model.json",
                     "customers.csv", "setup_transitions.csv", "locks.csv",
                     "wip_status.csv")
        for fname in all_files:
            p = self._dir / fname
            if p.exists():
                reporter.register_input(artifact_id=fname, artifact_hash=_file_hash(p), profile={})

        orders = _read_csv(self._dir / "orders.csv")
        routings = _read_csv(self._dir / "routings.csv")
        routing_lines = _read_csv(self._dir / "routing_lines.csv")
        products = _read_csv(self._dir / "products.csv")
        resources_rows = _read_csv(self._dir / "resources.csv")
        calendars_rows = _read_csv(self._dir / "calendars.csv")
        customers_rows = _read_csv(self._dir / "customers.csv") if (self._dir / "customers.csv").exists() else []
        transitions_rows = (_read_csv(self._dir / "setup_transitions.csv")
                             if (self._dir / "setup_transitions.csv").exists() else [])
        locks_rows = _read_csv(self._dir / "locks.csv") if (self._dir / "locks.csv").exists() else []
        wip_rows = (_read_csv(self._dir / "wip_status.csv")
                    if (self._dir / "wip_status.csv").exists() else [])
        wip_basis = semantics.get("wip_progress_basis", "remaining_minutes")
        cost_model_raw = json.loads((self._dir / "cost_model.json").read_text(encoding="utf-8"))

        product_map = {p["product_id"]: p for p in products if p.get("product_id")}
        routing_map = {r["route_id"]: r for r in routings if r.get("route_id")}
        lines_by_route: dict[str, list[dict]] = {}
        for rl in routing_lines:
            if str(rl.get("active", "0")).strip() == "1" and rl.get("route_id"):
                lines_by_route.setdefault(rl["route_id"], []).append(rl)
        for rid in lines_by_route:
            lines_by_route[rid].sort(key=lambda r: int(r.get("sequence", "0") or "0"))
        customer_map = {c["customer_id"]: c for c in customers_rows if c.get("customer_id")}

        core = cost_model_raw.get("core", {})
        priority_multipliers: dict[str, float] = dict(core.get("priority_multipliers", {}))

        # ------------------------------------------------------------
        # Resources + shared Calendars
        # ------------------------------------------------------------
        cal_rows_by_id: dict[str, list[dict]] = {}
        for row in calendars_rows:
            cid = row.get("calendar_id", "")
            if cid:
                cal_rows_by_id.setdefault(cid, []).append(row)

        cal_id_map: dict[str, str] = {}
        calendar_count = 0
        for cal_ext_id, rows in cal_rows_by_id.items():
            cal_id = _stable_id("calendar", cal_ext_id)
            cal_id_map[cal_ext_id] = cal_id

            pattern_rows = [r for r in rows if r.get("row_type", "pattern") == "pattern"]
            weekdays = sorted({int(r["day_of_week"]) for r in pattern_rows if r.get("day_of_week", "") != ""})
            shift_start = pattern_rows[0].get("start_time", "07:00") if pattern_rows else "07:00"
            shift_end = pattern_rows[0].get("end_time", "19:00") if pattern_rows else "19:00"

            exceptions: list[CalendarException] = []
            for r in rows:
                if r.get("row_type") != "exception" or not r.get("exception_date"):
                    continue
                try:
                    d = date.fromisoformat(r["exception_date"][:10])
                except ValueError:
                    continue
                st = r.get("start_time") or "00:00"
                et = r.get("end_time") or "23:59"
                sh, sm = (int(x) for x in st.split(":"))
                eh, em = (int(x) for x in et.split(":"))
                window = TimeWindow(
                    start=datetime(d.year, d.month, d.day, sh, sm, tzinfo=UTC),
                    end=datetime(d.year, d.month, d.day, eh, em, 59, tzinfo=UTC),
                )
                exc_type = (CalendarExceptionType.ADDED
                            if r.get("exception_type", "closure") == "added"
                            else CalendarExceptionType.CLOSURE)
                reason_raw = r.get("reason", "planned_maintenance") or "planned_maintenance"
                reason = (CalendarExceptionReason(reason_raw)
                          if reason_raw in _KNOWN_EXCEPTION_REASONS
                          else CalendarExceptionReason.PLANNED_MAINTENANCE)
                exceptions.append(CalendarException(window=window, type=exc_type, reason=reason))

            cal = Calendar(
                id=cal_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="IDS", type="calendar_id", value=cal_ext_id)],
                base_pattern={"weekdays": weekdays, "shift_start": shift_start, "shift_end": shift_end},
                exceptions=exceptions, horizon_resolved=[],
            )
            cal_prov = _obs_list(cal_id, ["base_pattern", "exceptions", "horizon_resolved"], snapshot_id,
                                {"base_pattern": "calendars.csv(pattern)", "exceptions": "calendars.csv(exception)",
                                 "horizon_resolved": "calendars.csv"})
            writer.write_entity(cal, cal_prov)
            identity_map.register(cal_id, "IDS", "calendar_id", cal_ext_id)
            calendar_count += 1

        # Effective per-resource rate, docs/06 §5.5 precedence: cost-model
        # default < resources.csv cost_rate override < refinements.resource_rates.
        # Resource.cost_rate carries the SAME effective value (canonical
        # $/minute) as the resource's CostModel.resource_rates entry — one
        # source, visible in both places, with provenance naming where the
        # value actually came from (the pre-fix code wrote a hardcoded 0.0
        # under an *observed* sidecar citing the cost_rate column).
        default_rate_per_hour = _num(core.get("default_resource_rate_per_hour"), 0.0)
        refinement_rates = cost_model_raw.get("refinements", {}).get("resource_rates", {}) or {}
        resource_rates: dict[str, float] = {}
        resource_count = 0
        for row in resources_rows:
            ext_id = row.get("resource_id", "")
            if not ext_id:
                continue
            res_id = _stable_id("resource", ext_id)
            cal_ext_id = row.get("calendar_id", "")
            cal_ref = cal_id_map.get(cal_ext_id)
            parallel = int(_num(row.get("parallel_units"), 1.0)) or 1

            override = _num(row.get("cost_rate"), -1.0)
            if ext_id in refinement_rates:
                rate_per_hour = _num(refinement_rates[ext_id])
                rate_prov = _drv(res_id, "cost_rate", snapshot_id,
                                 "ids_refinement_rate", [(res_id, "cost_rate")])
            elif override >= 0:
                rate_per_hour = override
                rate_prov = _obs(res_id, "cost_rate", snapshot_id, "cost_rate")
            else:
                rate_per_hour = default_rate_per_hour
                rate_prov = _def(res_id, "cost_rate", snapshot_id,
                                 "default_resource_rate_per_hour")
            rate_per_min = rate_per_hour / 60.0
            resource_rates[res_id] = rate_per_min

            res = Resource(
                id=res_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="IDS", type="resource_id", value=ext_id)],
                resource_type=ResourceType.MACHINE,
                capabilities=[],
                capacity=parallel,
                cost_rate=rate_per_min,
                calendar_ref=cal_ref,
                pool_refs=[],
            )
            res_prov = _obs_list(res_id, ["resource_type", "capabilities", "capacity",
                                          "calendar_ref", "pool_refs"], snapshot_id,
                                {"resource_type": "resources.csv", "capabilities": "resources.csv",
                                 "capacity": "parallel_units",
                                 "calendar_ref": "calendar_id", "pool_refs": "pool_id"})
            res_prov.append(rate_prov)
            writer.write_entity(res, res_prov)
            identity_map.register(res_id, "IDS", "resource_id", ext_id)
            resource_count += 1

        known_resource_ids = {row.get("resource_id", "") for row in resources_rows}
        for ext_id in refinement_rates:
            if ext_id not in known_resource_ids:
                reporter.record_finding(
                    code=FindingCode.LOW_CONFIDENCE_INPUT, severity=FindingSeverity.WARNING,
                    subjects=[], evidence={"unresolved_resource_rate_key": ext_id},
                    disposition=FindingDisposition.DEFAULTED,
                    disposition_detail="cost_model.refinements.resource_rates key not found in resources.csv",
                    tier=RecordTier.SUPPORTING,
                )

        # ------------------------------------------------------------
        # Products + Processes + OperationSpecs (per (route_id, product_id))
        # ------------------------------------------------------------
        # Pass 1: determine every (route_id, product_id) pair actually used by
        # an order, and the process_id each will get (deterministic, so this
        # can run before any entity is written). This lets Product.process_ref
        # be set correctly on write instead of backfilled after the fact —
        # the validator's INFEASIBLE_SUBSET check depends on Product.process_ref
        # resolving to a real Process, so a None here silently disables it.
        pairs_needed: set[tuple[str, str]] = set()
        for o in orders:
            rid, pid = o.get("route_id", ""), o.get("product_id", "")
            if rid in routing_map and pid in product_map:
                pairs_needed.add((rid, pid))

        process_id_for_pair: dict[tuple[str, str], str] = {
            (route_id, ext_pid): _stable_id("process", f"{route_id}:{ext_pid}")
            for route_id, ext_pid in pairs_needed
        }
        prod_first_process: dict[str, str] = {}
        for route_id, ext_pid in sorted(pairs_needed):
            prod_first_process.setdefault(ext_pid, process_id_for_pair[(route_id, ext_pid)])

        product_id_map: dict[str, str] = {}
        product_count = 0
        for ext_pid, prow in product_map.items():
            pid = _stable_id("product", ext_pid)
            product_id_map[ext_pid] = pid
            prod = Product(
                id=pid, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="IDS", type="product_id", value=ext_pid)],
                name=ext_pid, unit_of_measure=prow.get("uom", "EA") or "EA",
                process_ref=prod_first_process.get(ext_pid), product_family=(prow.get("product_group") or None),
            )
            prod_prov = _obs_list(pid, ["name", "unit_of_measure", "process_ref", "product_family"], snapshot_id,
                                  {"name": "product_id", "unit_of_measure": "uom",
                                   "process_ref": "routings.csv", "product_family": "product_group"})
            writer.write_entity(prod, prod_prov)
            identity_map.register(pid, "IDS", "product_id", ext_pid)
            product_count += 1

        process_count = 0
        op_spec_count = 0
        edge_count = 0
        # (route_id, ext_pid, sequence) → written spec id; the WIP doorway
        # resolves wip_status.csv sequences through this (only specs that
        # actually exist can carry an observation).
        spec_written: dict[tuple[str, str, int], str] = {}
        for route_id, ext_pid in pairs_needed:
            process_id = process_id_for_pair[(route_id, ext_pid)]
            prow = product_map[ext_pid]
            lot_size = _num(prow.get("costing_lot_size"))
            prod_minutes = _num(prow.get("production_minutes"))
            prod_setup = _num(prow.get("setup_minutes"))

            spec_ids: list[str] = []
            dwell_minutes_by_spec_id: dict[str, float] = {}
            for rl in lines_by_route.get(route_id, []):
                seq = int(rl.get("sequence", "0") or "0")
                res_ext = rl.get("resource_id", "")
                res_id = identity_map.resolve("IDS", "resource_id", res_ext)
                if res_id is None:
                    continue
                spec_id = _stable_id("operationspec", f"{route_id}:{ext_pid}:{seq}")

                override_run = _num(rl.get("run_minutes_per_unit"))
                override_setup = _num(rl.get("setup_minutes"))
                if override_run > 0:
                    run_rate = timedelta(minutes=override_run)
                    run_formula = "ids_routing_line_override"
                elif lot_size > 0 and prod_minutes > 0:
                    run_rate = timedelta(minutes=prod_minutes / lot_size)
                    run_formula = "legacy_author_definition_v1"
                else:
                    run_rate = timedelta(0)
                    run_formula = "unavailable"
                base_setup = timedelta(minutes=override_setup if override_setup > 0 else prod_setup)

                req = ResourceRequirement(mode=ResourceRequirementMode.EXPLICIT_SET, resource_refs=[res_id])
                min_chunk_raw = _num(rl.get("min_chunk_minutes"))
                spec = OperationSpec(
                    id=spec_id, snapshot_id=snapshot_id, sequence=seq,
                    resource_requirements=[req],
                    setup_family=rl.get("setup_family", "") or "",
                    base_setup=base_setup, run_rate=run_rate,
                    # splittable=true declares the RUN phase resumable (R-C3;
                    # setup defaults resumable too — it is folded into the
                    # same chunked working-duration total, see solver_builder).
                    splittable=str(rl.get("splittable", "false")).strip().lower() == "true",
                    min_chunk=timedelta(minutes=min_chunk_raw) if min_chunk_raw > 0 else None,
                )
                spec_prov = _obs_list(
                    spec_id, ["sequence", "resource_requirements", "setup_family",
                              "splittable", "min_chunk", "yield_factor"], snapshot_id,
                    {"sequence": "sequence", "resource_requirements": "resource_id",
                     "setup_family": "setup_family",
                     "splittable": "splittable", "min_chunk": "min_chunk_minutes",
                     "yield_factor": "routing_lines.csv"},
                )
                spec_prov += [
                    _drv(spec_id, "base_setup", snapshot_id, "ids_setup_resolution",
                         [(spec_id, "setup_minutes_override_or_product_setup")]),
                    _drv(spec_id, "run_rate", snapshot_id, run_formula,
                         [(spec_id, "run_minutes_per_unit_override_or_product_rate")]),
                ]
                writer.write_entity(spec, spec_prov)
                spec_ids.append(spec_id)
                spec_written[(route_id, ext_pid, seq)] = spec_id
                # dwell_minutes lands as min_lag on the OUTGOING PrecedenceEdge
                # per R-Dwell — dwell is no longer a phase anywhere.
                dwell_minutes_by_spec_id[spec_id] = _num(rl.get("dwell_minutes"))
                op_spec_count += 1

            if not spec_ids:
                continue

            for pred_spec_id, succ_spec_id in _synthesize_precedence_pairs(spec_ids):
                edge_id = _stable_id("precedenceedge", f"{pred_spec_id}:{succ_spec_id}")
                dwell_min = dwell_minutes_by_spec_id.get(pred_spec_id, 0.0)
                edge = PrecedenceEdge(
                    id=edge_id, snapshot_id=snapshot_id,
                    predecessor=pred_spec_id, successor=succ_spec_id,
                    min_lag=timedelta(minutes=dwell_min), max_lag=None,
                )
                edge_prov = _obs_list(edge_id, ["predecessor", "successor"], snapshot_id,
                                      {"predecessor": "sequence", "successor": "sequence"})
                edge_prov += [_drv(edge_id, "min_lag", snapshot_id, "ids_dwell_to_min_lag",
                                   [(pred_spec_id, "dwell_minutes")])]
                edge_prov += _def_list(edge_id, ["max_lag"], snapshot_id, "unconstrained_default_v1")
                writer.write_entity(edge, edge_prov)
                edge_count += 1

            process = Process(
                id=process_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="IDS", type="route_id", value=route_id)],
                product_ref=product_id_map[ext_pid], operation_specs=spec_ids,
                version=1, effective_from=None, status=ProcessStatus.ACTIVE,
            )
            proc_prov = _obs_list(process_id, ["product_ref", "operation_specs", "version",
                                               "effective_from", "status"], snapshot_id,
                                  {"product_ref": "product_id", "operation_specs": "routing_lines.csv",
                                   "version": "routings.csv", "effective_from": "effective_from",
                                   "status": "status"})
            writer.write_entity(process, proc_prov)
            process_count += 1

        # ------------------------------------------------------------
        # Demands
        # ------------------------------------------------------------
        # wip_status.csv rows grouped by order, keeping 1-based data row
        # numbers for provenance citation (docs/06 §5.13).
        wip_by_order: dict[str, list[tuple[int, dict]]] = {}
        for row_no, row in enumerate(wip_rows, start=1):
            ext = (row.get("order_id") or "").strip()
            if ext:
                wip_by_order.setdefault(ext, []).append((row_no, row))

        demand_count = 0
        seen_order_ids: set[str] = set()
        demand_id_for_order: dict[str, str] = {}

        for o in orders:
            ext_oid = o.get("order_id", "")
            if not ext_oid:
                continue
            if ext_oid in seen_order_ids:
                dup_id = _stable_id("demand_excluded", ext_oid + ":dup")
                reporter.record_finding(
                    code=FindingCode.DUPLICATE_IDENTITY, severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=dup_id, entity_type="demand")],
                    evidence={"order_id": ext_oid, "reason": "duplicate order_id; first occurrence kept"},
                    disposition=FindingDisposition.PROCEEDED_FLAGGED, tier=RecordTier.SUPPORTING,
                )
                continue
            seen_order_ids.add(ext_oid)

            ext_pid = o.get("product_id", "")
            route_id = o.get("route_id", "")
            if ext_pid not in product_map or route_id not in routing_map:
                excl_id = _stable_id("demand_excluded", ext_oid)
                reporter.record_finding(
                    code=FindingCode.ORPHAN_ENTITY, severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={"order_id": ext_oid, "product_id": ext_pid, "route_id": route_id,
                              "reason": "product_id or route_id does not resolve"},
                    disposition=FindingDisposition.EXCLUDED, tier=RecordTier.SUPPORTING,
                )
                continue
            if (route_id, ext_pid) not in process_id_for_pair:
                excl_id = _stable_id("demand_excluded", ext_oid)
                reporter.record_finding(
                    code=FindingCode.VALUE_OUT_OF_RANGE, severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=excl_id, entity_type="demand")],
                    evidence={"order_id": ext_oid, "product_id": ext_pid, "route_id": route_id,
                              "reason": "no computable operation duration (see gate duration_computability)"},
                    disposition=FindingDisposition.EXCLUDED, tier=RecordTier.SUPPORTING,
                )
                continue

            qty = _num(o.get("quantity"))
            demand_id = _stable_id("demand", ext_oid)
            demand_id_for_order[ext_oid] = demand_id

            due_dt = _parse_due(o.get("due_date", ""), due_tod)
            earliest_start = _parse_dt(o.get("release_date", "")) or _parse_dt(o.get("created_date", ""))

            cc_raw = (o.get("commitment_class") or "standard").strip().lower()
            commitment_class = _COMMITMENT_MAP.get(cc_raw, CommitmentClass.STANDARD)

            ext_cid = (o.get("customer_id") or "").strip()
            customer_ref = None
            if ext_cid and ext_cid in customer_map:
                customer_ref = _stable_id("customer", ext_cid)

            order_pclass = (o.get("priority_class") or "").strip()
            cust_pclass = (customer_map.get(ext_cid, {}).get("priority_class") or "").strip() if ext_cid else ""
            resolved_class = self._resolve_priority_class(
                order_pclass, cust_pclass, priority_precedence
            )
            weight = 1.0
            if resolved_class:
                if resolved_class in priority_multipliers:
                    weight = priority_multipliers[resolved_class]
                else:
                    reporter.record_finding(
                        code=FindingCode.UNMAPPABLE_VALUE, severity=FindingSeverity.WARNING,
                        subjects=[EntityRef(entity_id=demand_id, entity_type="demand")],
                        evidence={"order_id": ext_oid, "priority_class": resolved_class,
                                  "reason": "priority_class not covered by cost_model.core.priority_multipliers"},
                        disposition=FindingDisposition.DEFAULTED,
                        disposition_detail="customer_weight defaulted to 1.0", tier=RecordTier.SUPPORTING,
                    )

            wip_obs = self._build_wip_observations(
                wip_by_order.get(ext_oid, []), route_id, ext_pid, wip_basis,
                spec_written, identity_map, demand_id, ext_oid, reporter,
            )

            demand = Demand(
                id=demand_id, snapshot_id=snapshot_id,
                external_refs=[ExternalRef(system="IDS", type="order_id", value=ext_oid)],
                product_ref=product_id_map[ext_pid],
                quantity=Quantity(value=qty, uom=product_map[ext_pid].get("uom", "EA") or "EA"),
                due=due_dt, earliest_start=earliest_start,
                commitment_class=commitment_class, customer_weight=weight,
                customer_ref=customer_ref, status=DemandStatus.OPEN,
                wip_operations=wip_obs,
            )
            d_prov = _obs_list(demand_id, ["product_ref", "quantity", "due", "earliest_start",
                                          "customer_ref"], snapshot_id,
                              {"product_ref": "product_id", "quantity": "quantity", "due": "due_date",
                               "earliest_start": "release_date/created_date", "customer_ref": "customer_id"})
            if wip_obs:
                # TRUTHFUL observed provenance citing the source rows: the
                # observation structs carry their own wip_status.csv row
                # numbers (source_rows).
                rows_cited = sorted({r for o in wip_obs for r in o.source_rows})
                d_prov.append(_obs(
                    demand_id, "wip_operations", snapshot_id,
                    f"wip_status.csv rows {rows_cited}",
                ))
            else:
                d_prov += _def_list(demand_id, ["wip_operations"], snapshot_id,
                                    "no_wip_rows_blank_slate")
            d_prov += ([_drv(demand_id, "customer_weight", snapshot_id, "priority_multiplier_lookup",
                             [(demand_id, "priority_class")])]
                       if resolved_class else _def_list(demand_id, ["customer_weight"], snapshot_id, "no_priority_declared"))
            d_prov += _obs_list(demand_id, ["commitment_class"], snapshot_id, {"commitment_class": "commitment_class"})
            d_prov += _def_list(demand_id, ["status"], snapshot_id, "ids_adapter_default")
            writer.write_entity(demand, d_prov)
            identity_map.register(demand_id, "IDS", "order_id", ext_oid)
            demand_count += 1

        # ------------------------------------------------------------
        # CostModel
        # ------------------------------------------------------------
        cm_id = _stable_id("costmodel", cost_model_raw.get("version", "ids-v1"))
        refinements = cost_model_raw.get("refinements", {}) or {}
        cm = CostModel(
            id=cm_id, snapshot_id=snapshot_id, version=1, effective_from=None,
            resource_rates=resource_rates,
            setup_cost_basis=SetupCostBasis(
                fixed_per_setup=_num(core.get("setup_cost_per_setup")),
                scrap_cost_per_unit=_num(refinements.get("scrap_cost_per_unit")),
            ),
            tardiness_weights=TardinessWeights(
                base_weight=_num(core.get("tardiness_cost_per_hour")) / 60.0,
                commitment_class_multipliers={},
            ),
            overtime_premium=_num(refinements.get("overtime_premium_multiplier")),
            inventory_carrying=_num(refinements.get("inventory_carrying")),
        )
        cm_prov = _def_list(cm_id, ["version", "effective_from", "resource_rates", "setup_cost_basis",
                                   "tardiness_weights", "overtime_premium", "inventory_carrying"],
                            snapshot_id, "ids_cost_model_v1")
        writer.write_entity(cm, cm_prov)

        # ------------------------------------------------------------
        # setup_transitions.csv -> Constraint(SETUP_TRANSITION)
        # ------------------------------------------------------------
        constraint_id = None
        if transitions_rows:
            matrix: dict[str, dict[str, float]] = {}
            for row in transitions_rows:
                frm, to = row.get("from_family", ""), row.get("to_family", "")
                if frm and to:
                    matrix.setdefault(frm, {})[to] = _num(row.get("setup_minutes"))
            con_id = _stable_id("constraint", "setup_transition:ids")
            con = Constraint(
                id=con_id, snapshot_id=snapshot_id, constraint_type=ConstraintType.SETUP_TRANSITION,
                subjects=[cm_id],
                parameters={
                    "transition_minutes": {f"{f}->{t}": m for f, tm in matrix.items() for t, m in tm.items()},
                    "unlisted_transition_default": semantics.get("unlisted_transition_default", "base_setup"),
                },
                provenance_class=ConstraintProvenance.ERP_DATA, authority="setup_transitions.csv",
                hardness=ConstraintHardness.SOFT, penalty_weight=1.0,
            )
            con_prov = _def_list(con_id, ["constraint_type", "subjects", "parameters", "provenance_class",
                                         "authority", "hardness", "penalty_weight", "expiry"],
                                 snapshot_id, "setup_transitions.csv")
            writer.write_entity(con, con_prov)
            constraint_id = con_id

        # ------------------------------------------------------------
        # locks.csv -> Constraint(FROZEN_ASSIGNMENT / PINNED_WINDOW)
        # ------------------------------------------------------------
        for row in locks_rows:
            ext_oid = row.get("order_id", "")
            demand_id = demand_id_for_order.get(ext_oid)
            res_ext = row.get("resource_id", "")
            res_id = identity_map.resolve("IDS", "resource_id", res_ext)
            if demand_id is None or res_id is None:
                reporter.record_finding(
                    code=FindingCode.ORPHAN_ENTITY, severity=FindingSeverity.ERROR,
                    subjects=[], evidence={"order_id": ext_oid, "resource_id": res_ext,
                                           "reason": "lock references an unknown order or resource"},
                    disposition=FindingDisposition.EXCLUDED, tier=RecordTier.SUPPORTING,
                )
                continue
            lock_type = (row.get("lock_type") or "frozen").strip().lower()
            ctype = (ConstraintType.FROZEN_ASSIGNMENT if lock_type == "frozen"
                     else ConstraintType.PINNED_WINDOW)
            seq_raw = (row.get("sequence") or "").strip()
            start_dt = _parse_dt(row.get("start", ""))
            lock_con_id = _stable_id("constraint", f"lock:{ext_oid}:{seq_raw}:{res_ext}")
            lock_con = Constraint(
                id=lock_con_id, snapshot_id=snapshot_id, constraint_type=ctype,
                subjects=[demand_id, res_id],
                parameters={
                    "demand_ref": demand_id, "resource_ref": res_id,
                    "sequence": int(seq_raw) if seq_raw else None,
                    "start": start_dt.isoformat() if start_dt else None,
                    "lock_type": lock_type,
                },
                provenance_class=ConstraintProvenance.HUMAN_OVERRIDE,
                authority=row.get("authority", "") or "unknown",
                hardness=ConstraintHardness.HARD,
                expiry=_parse_dt(row.get("expiry", "")),
            )
            lock_prov = _def_list(lock_con_id, ["constraint_type", "subjects", "parameters",
                                                "provenance_class", "authority", "hardness",
                                                "penalty_weight", "expiry"],
                                  snapshot_id, "locks.csv")
            writer.write_entity(lock_con, lock_prov)

        writer.write_identity_map(identity_map)
        writer.finalize()

        reporter.register_output(
            artifact_ref="identity_map",
            artifact_hash=hashlib.sha256(
                str(sorted(identity_map._to_canonical.items())).encode()
            ).hexdigest()[:16],
        )

        return AdapterResult(
            demand_count=demand_count, product_count=product_count,
            resource_count=resource_count, operation_spec_count=op_spec_count,
            process_count=process_count, calendar_count=calendar_count,
            costmodel_id=cm_id, constraint_id=constraint_id,
            identity_map=identity_map, store=store,
            precedence_edge_count=edge_count,
        )

    @staticmethod
    def _build_wip_observations(
        order_rows: list[tuple[int, dict]],
        route_id: str,
        ext_pid: str,
        wip_basis: str,
        spec_written: dict[tuple[str, str, int], str],
        identity_map: IdentityMap,
        demand_id: str,
        ext_oid: str,
        reporter: Reporter,
    ) -> list[WipOperationObservation]:
        """Translate one order's wip_status.csv rows into canonical
        observations (docs/06 §5.13). Incoherent rows follow the gate's
        dispositions: unknown sequence/resource → excluded; in_progress
        missing its observed state → defaulted to not_started (an in-flight
        claim without observed start/resource/progress cannot be honored as
        a fixed interval). First row wins per sequence (the duplicate rule).
        """
        obs: list[WipOperationObservation] = []
        seen_seqs: set[int] = set()
        for row_no, row in order_rows:
            seq_raw = str(row.get("sequence", "")).strip()
            status_raw = (row.get("status") or "").strip()
            if not seq_raw.isdigit() or status_raw not in (
                    "not_started", "in_progress", "complete"):
                continue
            seq = int(seq_raw)
            spec_ref = spec_written.get((route_id, ext_pid, seq))
            if spec_ref is None or seq in seen_seqs:
                if spec_ref is None:
                    reporter.record_finding(
                        code=FindingCode.ORPHAN_ENTITY, severity=FindingSeverity.ERROR,
                        subjects=[EntityRef(entity_id=demand_id, entity_type="demand")],
                        evidence={"order_id": ext_oid, "sequence": seq, "row": row_no,
                                  "reason": "wip row references a sequence with no "
                                            "operation spec on the order's route"},
                        disposition=FindingDisposition.EXCLUDED, tier=RecordTier.SUPPORTING,
                    )
                continue
            seen_seqs.add(seq)

            status = WipStatus(status_raw)
            actual_start = _parse_dt(row.get("actual_start", ""))
            res_ext = (row.get("actual_resource_id") or "").strip()
            actual_resource_ref = (identity_map.resolve("IDS", "resource_id", res_ext)
                                   if res_ext else None)
            remaining = quantity_complete = None
            if status == WipStatus.IN_PROGRESS:
                # Normalize to the manifest-declared basis: exactly one
                # progress expression survives translation.
                raw_progress = (row.get(wip_basis) or "").strip()
                if wip_basis == "remaining_minutes" and raw_progress:
                    remaining = _num(raw_progress, -1.0)
                elif wip_basis == "quantity_complete" and raw_progress:
                    quantity_complete = _num(raw_progress, -1.0)
                progress_ok = (remaining is not None and remaining >= 0) or (
                    quantity_complete is not None and quantity_complete >= 0)
                if not (actual_start and actual_resource_ref and progress_ok):
                    reporter.record_finding(
                        code=FindingCode.MALFORMED_FIELD, severity=FindingSeverity.ERROR,
                        subjects=[EntityRef(entity_id=demand_id, entity_type="demand")],
                        evidence={"order_id": ext_oid, "sequence": seq, "row": row_no,
                                  "progress_basis": wip_basis,
                                  "reason": "in_progress wip row missing observed "
                                            "start, resource, or progress value"},
                        disposition=FindingDisposition.DEFAULTED,
                        disposition_detail="treated as not_started",
                        tier=RecordTier.SUPPORTING,
                    )
                    status = WipStatus.NOT_STARTED
                    actual_start = actual_resource_ref = None
                    remaining = quantity_complete = None

            obs.append(WipOperationObservation(
                sequence=seq, spec_ref=spec_ref, status=status,
                actual_start=actual_start,
                actual_resource_ref=actual_resource_ref,
                remaining_minutes=remaining,
                quantity_complete=quantity_complete,
                source_rows=[row_no],
            ))
        obs.sort(key=lambda o: o.sequence)
        return obs

    @staticmethod
    def _resolve_priority_class(order_class: str, customer_class: str, precedence: str) -> Optional[str]:
        if not order_class and not customer_class:
            return None
        if precedence == "order_over_customer":
            return order_class or customer_class
        if precedence == "customer_over_order":
            return customer_class or order_class
        if precedence in ("max", "multiply"):
            # Resolved to a single label only when one side is present;
            # numeric combination (max/multiply of multipliers) happens
            # in the caller once both classes map to known multipliers.
            return order_class or customer_class
        return customer_class or order_class
