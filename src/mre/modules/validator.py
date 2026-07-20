"""M3 — Validator.

Semantic quality checks against a canonical snapshot.  Produces go/no-go gate.

Checks performed:
1. TEMPORAL_IMPOSSIBILITY  — Demand.due < reference_date (historical-replay safe).
2. VALUE_OUT_OF_RANGE      — Demand.quantity == 0 (or other OOB values).
3. LOW_CONFIDENCE_INPUT    — Demand.customer_weight derived from defaulted/synthesized provenance.
4. STATISTICAL_OUTLIER     — OperationSpec.run_rate > threshold × median within product family.
                             Groups by product_family (via process→product chain); falls back
                             to setup_family if product_family not available (sample_data compat).
                             threshold is config-driven (outlier_threshold_ratio param, plant_config,
                             or --outlier-threshold); defaults to the gauntlet-calibrated value
                             (tools/calibrate_outliers.py, see _DEFAULT_OUTLIER_THRESHOLD_RATIO).
                             Evidence records the threshold and its basis so the DQ report can
                             say WHY something is flagged, not just that it was.
5. INFEASIBLE_SUBSET       — Class-aware window-fit (docs/05 R-C3). Non-resumable
                             (splittable=false) operations: estimated duration exceeds the
                             longest contiguous calendar window on every eligible resource.
                             Resumable (splittable=true) operations: estimated duration
                             exceeds the total working time available (best eligible
                             resource's weekly open minutes, scaled to the calendar time
                             between reference_date and the demand's own due date) — i.e.
                             excluded only when even chunked it cannot fit before due date.
   DENSITY_LIMIT             (warning, proceeded_flagged) — resumable operations per
                             eligible resource > 3: the chunk-boundary-interval encoding's
                             validated ceiling is ~4-4.5 resumable ops/resource
                             (tools/chunking_spike2_report.md); per-resource decomposition
                             is the mitigation if solves become slow. A distinct code from
                             STATISTICAL_OUTLIER (docs/02 §4.3, added 2026-07-12) — a
                             structural concentration signal, not a distributional one;
                             the two must trend separately.
6. PROVENANCE_GAP          — Entity attribute with no sidecar record.

reference_date defaults to datetime.now(UTC) when not supplied (backward compat with
sample_data pipeline). Pass a fixed reference_date for historical-replay runs against
real data so wall-clock drift never corrupts results.

The go/no-go gate returns go=False if any BLOCKER-severity finding exists in the
reporter at the time run() returns (including pre-existing blockers in the reporter).
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from mre.contracts.entities import EntityRef
from mre.contracts.vocabularies import (
    DecisionType, DecisionBasis, DriverCode,
    FindingCode, FindingDisposition, FindingSeverity,
    ModuleCode, RecordTier,
)
from mre.modules.calendar_utils import (
    is_effectively_resumable, longest_shift_minutes, weekly_open_minutes,
)
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

UTC = timezone.utc

_DEMAND_DECISION_ATTRS = {"customer_weight", "commitment_class", "due"}

# Rep 3 (docs/07 Phase 1): calibrated via tools/calibrate_outliers.py against
# the raw_data gauntlet snapshot (2026-07-12) — pooled log2(run_rate/family
# median) p99, converted back to a plain multiplier. At the old fixed 10x
# constant the gauntlet hit rate was 578/4007 = 14.4% specs; at this
# calibrated value it is 40/4007 = 1.00%. Config-overridable per deployment
# (plant_config "statistical_outlier_threshold_ratio" or --outlier-threshold);
# this is a starting point, not a universal constant — re-calibrate per
# real dataset.
_DEFAULT_OUTLIER_THRESHOLD_RATIO = 75.76
_OUTLIER_THRESHOLD_BASIS = "calibrated_v1"

_PT_RE = re.compile(
    r"^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
)


def _parse_duration_seconds(raw) -> float:
    """Parse pydantic-serialized timedelta (ISO 8601 PT string or float) to seconds."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return 0.0
    m = _PT_RE.match(raw)
    if not m:
        return 0.0
    days = float(m.group(1) or 0)
    hours = float(m.group(2) or 0)
    minutes = float(m.group(3) or 0)
    secs = float(m.group(4) or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + secs




@dataclass
class ValidationResult:
    go: bool
    blocker_count: int
    error_count: int
    warning_count: int
    excluded_demand_ids: set[str] = field(default_factory=set)


class Validator:
    def run(
        self,
        snapshot_id: str,
        store: SnapshotStore,
        reporter: Reporter,
        reference_date: Optional[datetime] = None,
        outlier_threshold_ratio: Optional[float] = None,
    ) -> ValidationResult:
        """outlier_threshold_ratio: STATISTICAL_OUTLIER multiplier (docs/02
        §4.3), config-driven (plant_config or CLI) per Rep 3. Defaults to
        the calibrated gauntlet value (tools/calibrate_outliers.py,
        pooled log2-ratio p99 -> ~1% hit rate; see the 2026-07-12 docs/04
        amendment). Not a claim that this value fits every plant's data —
        it is the value calibrated for the one real dataset this system
        has seen; re-run the calibration tool per deployment.
        """
        reader = store.load_snapshot(snapshot_id)
        now = reference_date if reference_date is not None else datetime.now(UTC)
        threshold_ratio = (
            outlier_threshold_ratio if outlier_threshold_ratio is not None
            else _DEFAULT_OUTLIER_THRESHOLD_RATIO
        )
        threshold_basis = (
            "config_override" if outlier_threshold_ratio is not None
            else _OUTLIER_THRESHOLD_BASIS
        )

        demands = list(reader.iter_entities("demand"))
        op_specs = list(reader.iter_entities("operationspec"))
        products = list(reader.iter_entities("product"))
        processes = list(reader.iter_entities("process"))
        resources_list = list(reader.iter_entities("resource"))
        calendars_list = list(reader.iter_entities("calendar"))

        # Build lookup tables
        op_specs_by_id = {s["id"]: s for s in op_specs}
        processes_by_id = {p["id"]: p for p in processes}
        calendars_by_id = {c["id"]: c for c in calendars_list}
        resources_by_id = {r["id"]: r for r in resources_list}

        # product_id → product_family
        prod_family: dict[str, str] = {
            p["id"]: (p.get("product_family") or "")
            for p in products
        }

        # product_id → process entity (via product.process_ref)
        prod_to_process: dict[str, dict] = {}
        for p in products:
            pref = p.get("process_ref")
            if pref and pref in processes_by_id:
                prod_to_process[p["id"]] = processes_by_id[pref]

        # spec_id → product_family (built from process → product chain)
        spec_to_family: dict[str, str] = {}
        for proc in processes:
            pid = proc.get("product_ref", "")
            fam = prod_family.get(pid, "")
            for spec_id in proc.get("operation_specs", []):
                if fam:
                    spec_to_family[spec_id] = fam

        # resource_id → longest shift window in minutes (non-resumable ops)
        # resource_id → total open minutes per week (resumable ops, docs/05 R-C3)
        res_window: dict[str, float] = {}
        res_weekly_minutes: dict[str, float] = {}
        for res in resources_list:
            cal_id = res.get("calendar_ref")
            if cal_id and cal_id in calendars_by_id:
                cal = calendars_by_id[cal_id]
                res_window[res["id"]] = longest_shift_minutes(cal)
                res_weekly_minutes[res["id"]] = weekly_open_minutes(cal)
            else:
                res_window[res["id"]] = 0.0
                res_weekly_minutes[res["id"]] = 0.0

        # --- Check 1: TEMPORAL_IMPOSSIBILITY ---
        excluded_demand_ids: set[str] = set()
        for d in demands:
            due_raw = d.get("due")
            if not due_raw:
                continue
            try:
                due = datetime.fromisoformat(due_raw)
                if due.tzinfo is None:
                    due = due.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                continue

            if due < now:
                # WIP exemption (docs/06 §5.13, the amended invariant): a
                # past-due demand that is actually underway on the floor is
                # NOT a ghost — excluding it would strand real in-flight work.
                # Only a past-due demand with no in-flight/complete observation
                # is a ghost job (the original fix, un-regressed).
                wip_ops = d.get("wip_operations") or []
                if any((w.get("status") in ("in_progress", "complete"))
                       for w in wip_ops):
                    continue
                excluded_demand_ids.add(d["id"])
                reporter.record_finding(
                    code=FindingCode.TEMPORAL_IMPOSSIBILITY,
                    severity=FindingSeverity.WARNING,
                    subjects=[EntityRef(entity_id=d["id"], entity_type="demand")],
                    evidence={
                        "demand_id": d["id"],
                        "due": due_raw,
                        "reference_date": now.isoformat(),
                        "reason": "Due date is before reference_date; demand excluded from planning",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )

        # --- Check 2: VALUE_OUT_OF_RANGE on Demand.quantity ---
        for d in demands:
            if d["id"] in excluded_demand_ids:
                continue
            qty_raw = d.get("quantity")
            if qty_raw is None:
                continue
            try:
                qty_value = (float(qty_raw.get("value", 1.0))
                             if isinstance(qty_raw, dict) else float(qty_raw))
            except (TypeError, ValueError):
                continue
            if qty_value <= 0.0:
                # Severity semantics (docs/02 §4.3, Session 4.5 CU3): a quantity
                # <= 0 is an invalid demand — you cannot make -60 units. This is
                # an ERROR, and an ERROR carries a consequence: the demand is
                # EXCLUDED from planning, never proceeded-flagged into a
                # floored-duration op that reads as an early fulfillment. The
                # named specimen the Glass Box audit caught (VALUE_OUT_OF_RANGE
                # emitted ERROR but disposition proceeded_flagged) is closed by
                # acting here.
                excluded_demand_ids.add(d["id"])
                reporter.record_finding(
                    code=FindingCode.VALUE_OUT_OF_RANGE,
                    severity=FindingSeverity.ERROR,
                    subjects=[EntityRef(entity_id=d["id"], entity_type="demand")],
                    evidence={
                        "demand_id": d["id"],
                        "quantity": qty_value,
                        "reason": "Demand quantity must be > 0; demand excluded from planning",
                    },
                    disposition=FindingDisposition.EXCLUDED,
                    tier=RecordTier.SUPPORTING,
                )

        # --- Check 3: LOW_CONFIDENCE_INPUT for synthesized/defaulted customer_weight ---
        affected_demands = []
        for d in demands:
            if d["id"] in excluded_demand_ids:
                continue
            prov = reader.get_provenance(d["id"], "customer_weight")
            if prov and prov.get("provenance_class") in ("defaulted", "synthesized"):
                affected_demands.append(d["id"])

        if affected_demands:
            reporter.record_finding(
                code=FindingCode.LOW_CONFIDENCE_INPUT,
                severity=FindingSeverity.WARNING,
                subjects=[
                    EntityRef(entity_id=eid, entity_type="demand")
                    for eid in affected_demands[:10]
                ],
                evidence={
                    "attribute": "customer_weight",
                    "affected_count": len(affected_demands),
                    "reason": (
                        f"customer_weight is defaulted/synthesized for {len(affected_demands)} "
                        "demands; tardiness priority is unreliable"
                    ),
                    "provenance_class": "synthesized",
                },
                disposition=FindingDisposition.PROCEEDED_FLAGGED,
                tier=RecordTier.SUPPORTING,
            )

        # --- Check 4: STATISTICAL_OUTLIER by product family ---
        # Group OperationSpec run_rates by product_family (via process→product chain).
        # Falls back to setup_family when product_family not available (sample_data compat).
        family_rates: dict[str, list[tuple[float, str]]] = {}
        for spec in op_specs:
            fam = spec_to_family.get(spec["id"]) or spec.get("setup_family") or "unknown"
            run_rate_raw = spec.get("run_rate")
            if run_rate_raw is None:
                continue
            seconds = _parse_duration_seconds(run_rate_raw)
            family_rates.setdefault(fam, []).append((seconds, spec["id"]))

        for fam, entries in family_rates.items():
            if len(entries) < 2:
                continue
            rates = [e[0] for e in entries]
            median = statistics.median(rates)
            if median <= 0:
                continue
            for secs, spec_id in entries:
                if secs > threshold_ratio * median:
                    reporter.record_finding(
                        code=FindingCode.STATISTICAL_OUTLIER,
                        severity=FindingSeverity.WARNING,
                        subjects=[EntityRef(entity_id=spec_id, entity_type="operationspec")],
                        evidence={
                            "family": fam,
                            "run_rate_seconds": secs,
                            "median_seconds": median,
                            "ratio": round(secs / median, 1),
                            "threshold": f"{threshold_ratio:g}x",
                            "threshold_basis": f"{threshold_basis} from snapshot {snapshot_id}",
                        },
                        disposition=FindingDisposition.PROCEEDED_FLAGGED,
                        tier=RecordTier.SUPPORTING,
                    )

        # --- Check 5: INFEASIBLE_SUBSET — class-aware pre-solve window-fit check ---
        # For each demand (not already excluded), estimate total operation duration
        # = quantity × run_rate + setup. Non-resumable (splittable=false) operations
        # must fit the longest available calendar window on some eligible resource, as
        # before. Resumable (splittable=true) operations can chunk across many windows
        # (docs/05 R-C3) — they are excluded only when even chunked they cannot fit the
        # working time available between reference_date and the demand's own due date.
        #
        # resumable_ops_by_resource tallies (demand, resource) pairs for the density
        # guard below — approximated at spec/demand granularity since Planner (which
        # would produce concrete Operations) has not run yet at validator time.
        resumable_ops_by_resource: dict[str, int] = {}

        for d in demands:
            if d["id"] in excluded_demand_ids:
                continue

            qty_raw = d.get("quantity")
            try:
                qty = (float(qty_raw.get("value", 0.0))
                       if isinstance(qty_raw, dict) else float(qty_raw or 0.0))
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0.0:
                continue

            process = prod_to_process.get(d.get("product_ref", ""))
            if process is None:
                continue

            due_raw = d.get("due")
            try:
                due_dt = datetime.fromisoformat(due_raw) if due_raw else None
                if due_dt is not None and due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                due_dt = None
            elapsed_days = max(0.0, (due_dt - now).total_seconds() / 86400.0) if due_dt else 0.0

            for spec_id in process.get("operation_specs", []):
                spec = op_specs_by_id.get(spec_id)
                if spec is None:
                    continue

                run_rate_sec = _parse_duration_seconds(spec.get("run_rate"))
                setup_sec = _parse_duration_seconds(spec.get("base_setup"))
                total_minutes = (qty * run_rate_sec + setup_sec) / 60.0
                if total_minutes <= 0.0:
                    continue

                # Collect eligible resource IDs
                eligible_ids: list[str] = []
                for req in spec.get("resource_requirements", []):
                    if isinstance(req, dict):
                        mode = req.get("mode", "")
                        if mode == "explicit_set":
                            eligible_ids.extend(req.get("resource_refs", []))
                        elif mode == "capability":
                            cap_ref = req.get("capability_ref", "")
                            for r in resources_list:
                                if cap_ref in (r.get("capabilities") or []):
                                    eligible_ids.append(r["id"])

                if not eligible_ids:
                    continue

                # Degenerate-split rule shared with SolverBuilder (docs/05
                # R-C3): working < 2 × min_chunk cannot split, so it is
                # window-fitted as a contiguous block. The two sides MUST
                # agree or the validator admits work the solver cannot place.
                min_chunk_min = _parse_duration_seconds(spec.get("min_chunk")) / 60.0
                resumable = is_effectively_resumable(
                    bool(spec.get("splittable", False)), total_minutes, min_chunk_min
                )

                if not resumable:
                    max_window = max(
                        (res_window.get(rid, 0.0) for rid in eligible_ids),
                        default=0.0,
                    )
                    if max_window <= 0.0:
                        continue
                    if total_minutes > max_window:
                        excluded_demand_ids.add(d["id"])
                        reporter.record_finding(
                            code=FindingCode.INFEASIBLE_SUBSET,
                            severity=FindingSeverity.ERROR,
                            subjects=[EntityRef(entity_id=d["id"], entity_type="demand")],
                            evidence={
                                "demand_id": d["id"],
                                "spec_id": spec_id,
                                "estimated_duration_minutes": round(total_minutes, 1),
                                "max_window_minutes": max_window,
                                "quantity": qty,
                                "run_rate_min_per_unit": round(run_rate_sec / 60.0, 6),
                                "setup_minutes": round(setup_sec / 60.0, 1),
                                "reason": (
                                    "Estimated operation duration exceeds the longest available "
                                    "calendar window on every eligible resource; "
                                    "demand cannot be scheduled without splitting"
                                ),
                            },
                            disposition=FindingDisposition.EXCLUDED,
                            tier=RecordTier.SUPPORTING,
                        )
                        break  # one infeasible operation is sufficient to exclude the demand
                    continue

                # Resumable: test total working time available before due date,
                # not a single window. Only infeasible if even chunked it can't fit.
                for rid in eligible_ids:
                    resumable_ops_by_resource[rid] = resumable_ops_by_resource.get(rid, 0) + 1

                best_weekly = max(
                    (res_weekly_minutes.get(rid, 0.0) for rid in eligible_ids),
                    default=0.0,
                )
                if best_weekly <= 0.0:
                    continue
                available_minutes = best_weekly * (elapsed_days / 7.0)
                if total_minutes > available_minutes:
                    excluded_demand_ids.add(d["id"])
                    reporter.record_finding(
                        code=FindingCode.INFEASIBLE_SUBSET,
                        severity=FindingSeverity.ERROR,
                        subjects=[EntityRef(entity_id=d["id"], entity_type="demand")],
                        evidence={
                            "demand_id": d["id"],
                            "spec_id": spec_id,
                            "estimated_duration_minutes": round(total_minutes, 1),
                            "available_minutes_before_due": round(available_minutes, 1),
                            "elapsed_days_to_due": round(elapsed_days, 2),
                            "quantity": qty,
                            "reason": (
                                "Resumable operation's total working time exceeds what is "
                                "available (best eligible resource) between reference_date "
                                "and the demand's due date, even chunked across every open "
                                "calendar window; demand cannot be scheduled"
                            ),
                        },
                        disposition=FindingDisposition.EXCLUDED,
                        tier=RecordTier.SUPPORTING,
                    )
                    break

        # --- Density guard: resumable ops per resource (docs/05, chunking_spike2) ---
        # The chunk-boundary-interval encoding's validated ceiling is ~4-4.5
        # resumable ops/resource (tools/chunking_spike2_report.md); above it,
        # CP-SAT's default search stopped finding feasible solutions within 60s
        # in the spike, though per-resource decomposition rescued it. This is a
        # proceed-but-flag warning, not an exclusion — the schedule is still
        # attempted globally.
        for rid, count in resumable_ops_by_resource.items():
            if count > 3:
                reporter.record_finding(
                    code=FindingCode.DENSITY_LIMIT,
                    severity=FindingSeverity.WARNING,
                    subjects=[EntityRef(entity_id=rid, entity_type="resource")],
                    evidence={
                        "resource_id": rid,
                        "resumable_op_count": count,
                        "threshold": 3,
                        "reason": (
                            "Resumable-operation density on this resource exceeds the "
                            "chunk-boundary-interval encoding's validated ceiling "
                            "(~4-4.5 ops/resource)"
                        ),
                    },
                    disposition=FindingDisposition.PROCEEDED_FLAGGED,
                    disposition_detail=(
                        "basis: spike-2 ceiling (~4-4.5 resumable ops/resource) — see "
                        "tools/chunking_spike2_report.md; per-resource decomposition is "
                        "the validated mitigation if solves become slow"
                    ),
                    tier=RecordTier.SUPPORTING,
                )

        # --- Check 6: PROVENANCE_GAP sweep ---
        _UNIVERSAL = frozenset({"id", "snapshot_id", "external_refs", "_entity_type"})

        for entity_type in ("demand", "product", "operationspec", "resource", "resourcepool"):
            for entity in reader.iter_entities(entity_type):
                eid = entity["id"]
                prov_attrs = {
                    p["attribute_name"]
                    for p in reader.iter_provenance_for_entity(eid)
                }
                for attr, val in entity.items():
                    if attr in _UNIVERSAL:
                        continue
                    if attr not in prov_attrs:
                        reporter.record_finding(
                            code=FindingCode.PROVENANCE_GAP,
                            severity=FindingSeverity.WARNING,
                            subjects=[EntityRef(entity_id=eid, entity_type=entity_type)],
                            evidence={
                                "entity_id": eid,
                                "entity_type": entity_type,
                                "attribute_name": attr,
                                "direction": "entity_attribute_missing_provenance",
                            },
                            disposition=FindingDisposition.PROCEEDED_FLAGGED,
                            tier=RecordTier.DETAIL,
                        )

        # --- Determine go/no-go ---
        counts = reporter.get_finding_counts()
        blocker_count = counts.get("blocker", 0)

        return ValidationResult(
            go=blocker_count == 0,
            blocker_count=blocker_count,
            error_count=counts.get("error", 0),
            warning_count=counts.get("warning", 0),
            excluded_demand_ids=excluded_demand_ids,
        )
