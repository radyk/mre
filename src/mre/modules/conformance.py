"""M0 — IDS Conformance Gate.

Implements docs/06-incoming-data-spec.md §4: the Rule Registry (32 rules,
grouped structural / banded / conditional-integrity / quality), the
costing-completeness grade (C0-C3), and the Submission Certificate
(REJECTED / CONDITIONAL / ACCEPTED).

Rule identity, finding code, category, and thresholds live in
``mre.contracts.ids_rules`` (the single source that also renders docs/06 §4);
this module only *evaluates* the conditions. Every emit site carries a
``rule_id`` from that registry — there are no anonymous checks. Grade is a
pure function of rule outcomes (``grade_from_outcomes``); finding severity
derives from the DISPOSITION — what the system did — via ``finding_severity``
(Session 4.5), so an error/blocker finding always carries an acting disposition.
Banded rules always record their
measurement as a Metric and emit a Finding only on a non-satisfied outcome, so
a clean submission carries no spurious "100% resolved" findings.

The gate checks; it never repairs (docs/06 §1). The only mutations it makes to
submitted data are the "permitted normalizations" (§4): BOM stripping and key
whitespace trimming, both recorded on the certificate.

Every non-satisfied outcome emits a standard-vocabulary Finding through the
Reporter (module M0) so the gate run is itself a first-class evidence run,
gradeable and trendable like any other pipeline stage. Findings name their
subjects as typed submission-space refs (system="IDS"); the M1 adapter
registers those refs in the identity map when it mints canonical entities,
making gate findings reachable by canonical key (docs/02 boundary rule 1).
"""
from __future__ import annotations

import csv
import json
import statistics as _stats
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from mre.contracts.entities import EntityRef
from mre.contracts.ids_rules import (
    RULE_REGISTRY, GateFindingEvidence, Measured, RuleId, RuleOutcome,
    finding_severity, grade_from_outcomes,
)
from mre.contracts.vocabularies import (
    FindingDisposition, FindingSeverity, RecordTier,
)
from mre.reporter import Reporter

UTC = timezone.utc

REQUIRED_FILES = (
    "orders.csv", "routings.csv", "routing_lines.csv", "products.csv",
    "resources.csv", "calendars.csv", "cost_model.json",
)
DOORWAY_FILES = ("customers.csv", "setup_transitions.csv", "locks.csv",
                 "wip_status.csv")

# Required columns per file (docs/06 §5). Absence is a Tier-1 violation
# (rule ids.required_columns_parse) — no more silent .get() fall-through.
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "orders.csv": ("order_id", "product_id", "route_id", "quantity",
                   "due_date", "facility_id"),
    "routings.csv": ("route_id", "facility_id", "status"),
    "routing_lines.csv": ("route_id", "sequence", "resource_id", "active"),
    "products.csv": ("product_id", "uom"),
    "resources.csv": ("resource_id", "facility_id", "parallel_units", "calendar_id"),
    "calendars.csv": ("calendar_id",),
}
# Key columns whose values must be non-blank on every row (ids.key_fields_populated).
KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "orders.csv": ("order_id", "product_id", "route_id"),
    "routings.csv": ("route_id",),
    "routing_lines.csv": ("route_id", "sequence", "resource_id"),
    "products.csv": ("product_id",),
    "resources.csv": ("resource_id", "calendar_id"),
}
# Present-but-optional order columns whose sparse (but non-empty) population is
# a Tier-3 quality flag (ids.optional_columns_are_not_sparse).
OPTIONAL_DENSITY_COLUMNS = ("release_date", "priority_class")
_SPARSE_FLOOR = 0.10

# Appendix A default thresholds (v0.2)
_REJECT_BAND = 0.60
_CONDITIONAL_BAND = 0.97
_STALE_DAYS = 365
_PLACEHOLDER_YEARS = 3


def _band_outcome(rate: float) -> RuleOutcome:
    """Map a banded resolution rate onto a rule outcome (Appendix A)."""
    if rate < _REJECT_BAND:
        return RuleOutcome.VIOLATED
    if rate < _CONDITIONAL_BAND:
        return RuleOutcome.DEGRADED
    return RuleOutcome.SATISFIED


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> tuple[list[dict], bool, list[str]]:
    """Return (rows, had_bom, header). BOM stripping is a permitted normalization."""
    raw = path.read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    header = list(reader.fieldnames or [])
    rows = [dict(r) for r in reader]
    return rows, had_bom, header


def _trim_keys(rows: list[dict], key_cols: list[str]) -> bool:
    """Trim whitespace on key columns in place. Returns True if anything changed."""
    changed = False
    for row in rows:
        for col in key_cols:
            v = row.get(col)
            if isinstance(v, str) and v != v.strip():
                row[col] = v.strip()
                changed = True
    return changed


class IDSManifest(BaseModel):
    """Minimal manifest schema (docs/06 §3) for ids.manifest_schema_valid.

    Submission-space schema, not a canonical record shape: this is the M0
    intake surface, so it lives with the gate. Extra keys are permitted
    (forward-compatibility); the required fields must be present and typed."""
    ids_version: str
    reference_date: str
    semantics: dict[str, Any]
    facility_scope: list[str] = []


@dataclass
class GateResult:
    grade: str  # REJECTED / CONDITIONAL / ACCEPTED
    costing_grade: str  # C0..C3
    certificate: dict[str, Any]
    go: bool  # False only when grade == REJECTED


# Ordering for "worst outcome per rule" bookkeeping on the certificate.
_OUTCOME_RANK = {RuleOutcome.SATISFIED: 0, RuleOutcome.FLAGGED: 1,
                 RuleOutcome.DEGRADED: 2, RuleOutcome.VIOLATED: 3}


class ConformanceGate:
    """Grades an IDS submission directory against docs/06 §4 (the Rule Registry)."""

    def run(self, submission_dir: Path, reporter: Reporter) -> GateResult:
        submission_dir = Path(submission_dir)
        deficiencies: list[str] = []
        normalizations: list[str] = []
        findings: list[dict] = []
        outcomes: list[RuleOutcome] = []
        rule_outcome: dict[str, str] = {}

        def _subjects(entity_type: str, ids, cap: int = 50) -> list[EntityRef]:
            out = []
            for i in list(ids)[:cap]:
                out.append(EntityRef(entity_id=str(i), entity_type=entity_type, system="IDS"))
            return out

        def _submission_subject() -> list[EntityRef]:
            return [EntityRef(entity_id=submission_dir.name or "submission",
                              entity_type="submission", system="IDS")]

        def record(rule_id: RuleId, outcome: RuleOutcome, subjects: list[EntityRef],
                   message: str, *, disposition: FindingDisposition,
                   measured: Optional[Measured] = None,
                   detail: Optional[dict] = None, check: Optional[str] = None,
                   deficiency: Optional[str] = None,
                   tier: RecordTier = RecordTier.SUPPORTING) -> Optional[dict]:
            """Register a rule outcome. Emits a Finding only when outcome is not
            satisfied; appends a deficiency only for a violated structural rule."""
            outcomes.append(outcome)
            rid = rule_id.value
            if _OUTCOME_RANK[outcome] >= _OUTCOME_RANK.get(
                    RuleOutcome(rule_outcome[rid]) if rid in rule_outcome else RuleOutcome.SATISFIED, 0):
                rule_outcome[rid] = outcome.value
            if outcome == RuleOutcome.SATISFIED:
                return None
            spec = RULE_REGISTRY[rule_id]
            ev = GateFindingEvidence(
                rule_id=rule_id, outcome=outcome, measured=measured,
                thresholds_ref=spec.thresholds_ref, check=check, detail=detail or {},
            )
            rec = reporter.record_finding(
                code=spec.finding_code,
                severity=finding_severity(spec.category, disposition),
                subjects=subjects, evidence=ev.as_evidence(),
                disposition=disposition, message=message, tier=tier,
            )
            findings.append(json.loads(rec.model_dump_json()))
            if outcome == RuleOutcome.VIOLATED and deficiency:
                deficiencies.append(deficiency)
            return rec

        def metric(name: str, value: float, unit: str,
                   subjects: Optional[list[EntityRef]] = None) -> None:
            reporter.record_metric(name=name, value=value, unit=unit,
                                   subjects=subjects or [], tier=RecordTier.SUPPORTING)

        # ------------------------------------------------------------
        # Structural 1: submission files + manifest present
        # ------------------------------------------------------------
        manifest_path = submission_dir / "manifest.json"
        manifest: Optional[dict] = None
        missing_files = [f for f in REQUIRED_FILES if not (submission_dir / f).exists()]
        manifest_present = manifest_path.exists()
        if not manifest_present:
            missing_files = ["manifest.json"] + missing_files
        record(
            RuleId.SUBMISSION_FILES_PRESENT,
            RuleOutcome.VIOLATED if missing_files else RuleOutcome.SATISFIED,
            _submission_subject(),
            f"missing required submission files: {missing_files}" if missing_files
            else "all required submission files present",
            disposition=FindingDisposition.BLOCKED,
            detail={"missing_files": missing_files},
            deficiency=f"required files missing: {missing_files}" if missing_files else None,
            tier=RecordTier.HEADLINE,
        )

        # ------------------------------------------------------------
        # Structural 2: manifest schema valid (parses + required fields typed)
        # ------------------------------------------------------------
        manifest_schema_ok = True
        if manifest_present:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                manifest_schema_ok = False
                record(RuleId.MANIFEST_SCHEMA_VALID, RuleOutcome.VIOLATED,
                       _submission_subject(), "manifest.json is not valid JSON",
                       disposition=FindingDisposition.BLOCKED, detail={"error": str(e)},
                       deficiency="manifest.json invalid JSON", tier=RecordTier.HEADLINE)
            if manifest is not None:
                try:
                    IDSManifest.model_validate(manifest)
                except ValidationError as e:
                    manifest_schema_ok = False
                    record(RuleId.MANIFEST_SCHEMA_VALID, RuleOutcome.VIOLATED,
                           _submission_subject(),
                           "manifest.json is missing required fields or has wrong types",
                           disposition=FindingDisposition.BLOCKED,
                           detail={"errors": json.loads(e.json())},
                           deficiency="manifest.json schema invalid", tier=RecordTier.HEADLINE)
                else:
                    record(RuleId.MANIFEST_SCHEMA_VALID, RuleOutcome.SATISFIED,
                           _submission_subject(), "manifest.json schema valid",
                           disposition=FindingDisposition.PROCEEDED_FLAGGED)
        # (manifest absent → submission_files_present already violated; no
        #  schema outcome recorded, which is correct — nothing to validate.)

        # ------------------------------------------------------------
        # Load whatever tables are present; check required columns + key fields
        # ------------------------------------------------------------
        tables: dict[str, list[dict]] = {}
        headers: dict[str, list[str]] = {}
        missing_columns: dict[str, list[str]] = {}
        for fname in REQUIRED_FILES + DOORWAY_FILES:
            path = submission_dir / fname
            if fname.endswith(".csv") and path.exists():
                rows, had_bom, header = _read_csv(path)
                if had_bom:
                    normalizations.append(f"BOM stripped: {fname}")
                key_cols = [c for c in ("order_id", "product_id", "route_id", "resource_id",
                                        "calendar_id", "customer_id", "actual_resource_id")
                            if header and c in header]
                if _trim_keys(rows, key_cols):
                    normalizations.append(f"key whitespace trimmed: {fname}")
                tables[fname] = rows
                headers[fname] = header
                req = REQUIRED_COLUMNS.get(fname, ())
                absent = [c for c in req if c not in header]
                if absent:
                    missing_columns[fname] = absent

        # Structural 3: required columns parse (present)
        record(
            RuleId.REQUIRED_COLUMNS_PARSE,
            RuleOutcome.VIOLATED if missing_columns else RuleOutcome.SATISFIED,
            _submission_subject(),
            f"required columns absent: {missing_columns}" if missing_columns
            else "all required columns present",
            disposition=FindingDisposition.BLOCKED,
            detail={"missing_columns": missing_columns},
            deficiency=f"required columns missing: {missing_columns}" if missing_columns else None,
            tier=RecordTier.HEADLINE,
        )

        cost_model: Optional[dict] = None
        cm_path = submission_dir / "cost_model.json"
        cost_model_bad_json = False
        if cm_path.exists():
            try:
                cost_model = json.loads(cm_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                cost_model_bad_json = True
                # The core is unreadable, not merely absent — a MISSING_REFERENCE
                # for cost_model_core_present is the topical rule (there is no
                # separate cost_model-parses rule).
                record(RuleId.COST_MODEL_CORE_PRESENT, RuleOutcome.VIOLATED,
                       _submission_subject(), "cost_model.json is not valid JSON",
                       disposition=FindingDisposition.BLOCKED,
                       detail={"file": "cost_model.json", "error": str(e)},
                       deficiency="cost_model.json invalid JSON", tier=RecordTier.HEADLINE)

        orders = tables.get("orders.csv", [])
        routings = tables.get("routings.csv", [])
        routing_lines = tables.get("routing_lines.csv", [])
        products = tables.get("products.csv", [])
        resources = tables.get("resources.csv", [])
        calendars = tables.get("calendars.csv", [])
        customers = tables.get("customers.csv", [])
        setup_transitions = tables.get("setup_transitions.csv", [])
        locks = tables.get("locks.csv", [])
        wip_rows = tables.get("wip_status.csv", [])

        # Structural 4: key fields populated (per-field non-blank scan)
        blank_key_hits: dict[str, int] = {}
        blank_key_ids: list[str] = []
        for fname, key_cols in KEY_COLUMNS.items():
            if fname not in tables:
                continue
            for row in tables[fname]:
                for col in key_cols:
                    if not (row.get(col) or "").strip():
                        blank_key_hits[f"{fname}:{col}"] = blank_key_hits.get(f"{fname}:{col}", 0) + 1
                        oid = (row.get("order_id") or row.get("route_id")
                               or row.get("resource_id") or row.get("product_id") or "")
                        if oid:
                            blank_key_ids.append(oid)
        record(
            RuleId.KEY_FIELDS_POPULATED,
            RuleOutcome.VIOLATED if blank_key_hits else RuleOutcome.SATISFIED,
            _subjects("order_id", blank_key_ids) or _submission_subject(),
            f"blank key fields: {blank_key_hits}" if blank_key_hits
            else "all key fields populated",
            disposition=FindingDisposition.BLOCKED,
            detail={"blank_counts": blank_key_hits},
            deficiency=f"blank key fields: {sorted(blank_key_hits)}" if blank_key_hits else None,
            tier=RecordTier.HEADLINE,
        )

        # ------------------------------------------------------------
        # Structural 5: manifest semantics declared (docs/06 §3)
        # (code AMBIGUOUS_SOURCE — an undeclared semantics field malforms
        #  nothing; the source cannot be interpreted, §3's stated purpose.)
        # ------------------------------------------------------------
        if manifest is not None:
            semantics = manifest.get("semantics", {})
            has_customer_priority = any((c.get("priority_class") or "").strip() for c in customers)
            has_order_priority = any((o.get("priority_class") or "").strip() for o in orders)
            missing_sem: list[str] = []
            if has_customer_priority and has_order_priority and "priority_precedence" not in semantics:
                missing_sem.append("priority_precedence")
            if setup_transitions and "unlisted_transition_default" not in semantics:
                missing_sem.append("unlisted_transition_default")
            if wip_rows and "wip_progress_basis" not in semantics:
                missing_sem.append("wip_progress_basis")
            record(
                RuleId.MANIFEST_SEMANTICS_DECLARED,
                RuleOutcome.VIOLATED if missing_sem else RuleOutcome.SATISFIED,
                _submission_subject(),
                f"required manifest semantics undeclared: {missing_sem}" if missing_sem
                else "required manifest semantics declared",
                disposition=FindingDisposition.BLOCKED,
                detail={"missing_semantics": missing_sem},
                deficiency=("manifest.semantics missing: " + ", ".join(missing_sem))
                if missing_sem else None,
                tier=RecordTier.HEADLINE,
            )

        # ------------------------------------------------------------
        # Structural 6: cost model core present in full
        # ------------------------------------------------------------
        core = (cost_model or {}).get("core", {})
        required_core_fields = ("default_resource_rate_per_hour", "setup_cost_per_setup",
                                 "tardiness_cost_per_hour", "priority_multipliers")
        missing_core = [
            f for f in required_core_fields
            if f not in core or core.get(f) in (None, "", {})
        ]
        if cost_model is not None and not cost_model_bad_json:
            record(
                RuleId.COST_MODEL_CORE_PRESENT,
                RuleOutcome.VIOLATED if missing_core else RuleOutcome.SATISFIED,
                _submission_subject(),
                f"cost_model.json core is incomplete: {missing_core}" if missing_core
                else "cost_model.json core present",
                disposition=FindingDisposition.BLOCKED,
                detail={"missing_core_fields": missing_core},
                deficiency=f"cost_model core incomplete: {missing_core}" if missing_core else None,
                tier=RecordTier.HEADLINE,
            )

        # ------------------------------------------------------------
        # Structural 7/8/9: >=1 in-scope order / resource / calendar pattern
        # ------------------------------------------------------------
        valid_orders = [
            o for o in orders
            if (o.get("order_id") or "").strip()
            and (o.get("product_id") or "").strip()
            and (o.get("route_id") or "").strip()
            and _num(o.get("quantity")) > 0
            and (o.get("due_date") or "").strip()
        ]
        record(RuleId.IN_SCOPE_ORDERS_EXIST,
               RuleOutcome.SATISFIED if valid_orders else RuleOutcome.VIOLATED,
               _submission_subject(),
               "at least one valid order" if valid_orders else "Zero valid orders",
               disposition=FindingDisposition.BLOCKED,
               detail={"valid_orders": len(valid_orders)},
               deficiency=None if valid_orders else "zero valid orders",
               tier=RecordTier.HEADLINE)

        record(RuleId.IN_SCOPE_RESOURCES_EXIST,
               RuleOutcome.SATISFIED if resources else RuleOutcome.VIOLATED,
               _submission_subject(),
               "resources present" if resources else "Zero resources",
               disposition=FindingDisposition.BLOCKED,
               deficiency=None if resources else "zero resources",
               tier=RecordTier.HEADLINE)

        pattern_rows = [c for c in calendars if c.get("row_type", "pattern") == "pattern"]
        record(RuleId.CALENDAR_PATTERNS_EXIST,
               RuleOutcome.SATISFIED if pattern_rows else RuleOutcome.VIOLATED,
               _submission_subject(),
               "calendar pattern rows present" if pattern_rows
               else "Zero calendar pattern rows; capacity is not optional",
               disposition=FindingDisposition.BLOCKED,
               deficiency=None if pattern_rows else "zero calendar pattern rows",
               tier=RecordTier.HEADLINE)

        # ------------------------------------------------------------
        # Banded: reference-chain resolution rates
        # ------------------------------------------------------------
        product_ids = {p.get("product_id") for p in products if p.get("product_id")}
        route_ids_all = {r.get("route_id") for r in routings if r.get("route_id")}
        route_lines_by_route: dict[str, list[dict]] = {}
        for rl in routing_lines:
            if str(rl.get("active", "0")).strip() == "1":
                route_lines_by_route.setdefault(rl.get("route_id", ""), []).append(rl)
        routes_with_lines = {rid for rid, lines in route_lines_by_route.items() if lines}

        total = len(orders) or 1

        product_resolved = sum(1 for o in orders if o.get("product_id") in product_ids)
        product_rate = product_resolved / total
        product_outcome = _band_outcome(product_rate)
        metric("order_product_resolution_rate", round(product_rate, 6), "ratio")
        unresolved_products = [o.get("order_id") for o in orders if o.get("product_id") not in product_ids]
        record(RuleId.ORDERS_RESOLVE_TO_PRODUCTS, product_outcome,
               _subjects("order_id", unresolved_products) or _submission_subject(),
               f"order->product resolution rate {product_rate:.1%}",
               disposition=FindingDisposition.EXCLUDED,
               measured=Measured(name="order_product_resolution_rate",
                                 value=round(product_rate, 6), unit="ratio"),
               detail={"resolved": product_resolved, "total": len(orders),
                       "unresolved_count": len(unresolved_products)},
               check="order_to_product",
               deficiency=f"order->product resolution below reject threshold ({product_rate:.1%})"
               if product_outcome == RuleOutcome.VIOLATED else None,
               tier=RecordTier.HEADLINE if product_outcome == RuleOutcome.VIOLATED
               else RecordTier.SUPPORTING)

        # Re-scoped to pure order->route-header resolution (the route→lines
        # leg is its own rule below, unfolded 2026-07-10).
        route_resolved = sum(1 for o in orders if o.get("route_id") in route_ids_all)
        route_rate = route_resolved / total
        route_outcome = _band_outcome(route_rate)
        metric("order_route_resolution_rate", round(route_rate, 6), "ratio")
        unresolved_routes = [o.get("order_id") for o in orders if o.get("route_id") not in route_ids_all]
        record(RuleId.ORDERS_RESOLVE_TO_ROUTES, route_outcome,
               _subjects("order_id", unresolved_routes) or _submission_subject(),
               f"order->route resolution rate {route_rate:.1%}",
               disposition=FindingDisposition.EXCLUDED,
               measured=Measured(name="order_route_resolution_rate",
                                 value=round(route_rate, 6), unit="ratio"),
               detail={"resolved": route_resolved, "total": len(orders),
                       "unresolved_count": len(unresolved_routes)},
               check="order_to_route",
               deficiency=f"order->route resolution below reject threshold ({route_rate:.1%})"
               if route_outcome == RuleOutcome.VIOLATED else None,
               tier=RecordTier.HEADLINE if route_outcome == RuleOutcome.VIOLATED
               else RecordTier.SUPPORTING)

        # Banded: referenced routes resolve to >=1 active routing line.
        referenced_routes = {o.get("route_id") for o in orders
                             if o.get("route_id") in route_ids_all}
        if referenced_routes:
            routes_ok = sum(1 for rid in referenced_routes if rid in routes_with_lines)
            line_rate = routes_ok / len(referenced_routes)
        else:
            line_rate = 1.0
        line_outcome = _band_outcome(line_rate)
        metric("route_line_resolution_rate", round(line_rate, 6), "ratio")
        lineless = [rid for rid in referenced_routes if rid not in routes_with_lines]
        record(RuleId.ROUTES_RESOLVE_TO_LINES, line_outcome,
               _subjects("route_id", lineless) or _submission_subject(),
               f"route->line resolution rate {line_rate:.1%}",
               disposition=FindingDisposition.EXCLUDED,
               measured=Measured(name="route_line_resolution_rate",
                                 value=round(line_rate, 6), unit="ratio"),
               detail={"routes_with_lines": len(routes_with_lines),
                       "referenced_routes": len(referenced_routes),
                       "lineless_count": len(lineless)},
               check="route_to_line",
               deficiency=f"route->line resolution below reject threshold ({line_rate:.1%})"
               if line_outcome == RuleOutcome.VIOLATED else None,
               tier=RecordTier.HEADLINE if line_outcome == RuleOutcome.VIOLATED
               else RecordTier.SUPPORTING)

        # Banded: operation duration computability
        products_by_id = {p.get("product_id"): p for p in products}

        def _order_duration_computable(order: dict) -> bool:
            pid, rid = order.get("product_id"), order.get("route_id")
            if pid not in product_ids or rid not in routes_with_lines:
                return True  # already counted by the resolution checks above
            prod = products_by_id.get(pid, {})
            lines = route_lines_by_route.get(rid, [])
            for line in lines:
                if _num(line.get("run_minutes_per_unit")) > 0:
                    continue
                lot = _num(prod.get("costing_lot_size"))
                mins = _num(prod.get("production_minutes"))
                if lot <= 0 or mins <= 0:
                    return False
            return True

        computable = sum(1 for o in orders if _order_duration_computable(o))
        duration_rate = computable / total
        duration_outcome = _band_outcome(duration_rate)
        metric("duration_computability_rate", round(duration_rate, 6), "ratio")
        uncomputable = [o.get("order_id") for o in orders if not _order_duration_computable(o)]
        record(RuleId.OPERATION_DURATIONS_COMPUTABLE, duration_outcome,
               _subjects("order_id", uncomputable) or _submission_subject(),
               f"duration computability rate {duration_rate:.1%}",
               disposition=FindingDisposition.EXCLUDED,
               measured=Measured(name="duration_computability_rate",
                                 value=round(duration_rate, 6), unit="ratio"),
               detail={"computable": computable, "total": len(orders),
                       "uncomputable_count": len(uncomputable),
                       "reason": "product costing_lot_size/production_minutes is 0 or missing "
                                 "and routing_lines carries no per-operation override"},
               check="duration_computability",
               deficiency=f"duration computability below reject threshold ({duration_rate:.1%})"
               if duration_outcome == RuleOutcome.VIOLATED else None,
               tier=RecordTier.HEADLINE if duration_outcome == RuleOutcome.VIOLATED
               else RecordTier.SUPPORTING)

        # ------------------------------------------------------------
        # Conditional integrity: duplicate order_id
        # ------------------------------------------------------------
        seen: dict[str, int] = {}
        for o in orders:
            oid = o.get("order_id", "")
            seen[oid] = seen.get(oid, 0) + 1
        dup_ids = [oid for oid, c in seen.items() if c > 1]
        dup_count = sum(c - 1 for c in seen.values() if c > 1)
        record(RuleId.ORDER_IDENTITIES_UNIQUE,
               RuleOutcome.DEGRADED if dup_count > 0 else RuleOutcome.SATISFIED,
               _subjects("order_id", dup_ids),
               f"{dup_count} duplicate order_id row(s); first occurrence kept"
               if dup_count else "order identities unique",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"duplicate_count": dup_count})

        # ------------------------------------------------------------
        # Conditional integrity: order quantities are positive (rule #34,
        # docs/06 §5.1). A zero/negative order quantity is an invalid demand —
        # you cannot make -60 units. Distinct from in_scope_orders_exist (which
        # asks whether ANY valid order remains): this names each offending order
        # so the certificate can point at it, degrades the grade, and the demand
        # is excluded downstream (validator VALUE_OUT_OF_RANGE). The gate checks;
        # it never repairs — the disposition is EXCLUDED (the demand does not
        # survive planning), so the finding is an honest ERROR.
        # ------------------------------------------------------------
        nonpositive_qty = [
            o.get("order_id") for o in orders
            if (o.get("order_id") or "").strip()
            and (o.get("quantity") or "").strip()
            and _num(o.get("quantity")) <= 0
        ]
        record(RuleId.ORDER_QUANTITIES_ARE_POSITIVE,
               RuleOutcome.DEGRADED if nonpositive_qty else RuleOutcome.SATISFIED,
               _subjects("order_id", nonpositive_qty),
               f"{len(nonpositive_qty)} order(s) have a quantity <= 0 "
               "(invalid demand; excluded from planning)"
               if nonpositive_qty else "order quantities are positive",
               disposition=FindingDisposition.EXCLUDED,
               detail={"count": len(nonpositive_qty)})

        # ------------------------------------------------------------
        # Conditional integrity: order dates internally consistent
        # (due >= release/created)
        # ------------------------------------------------------------
        def _d(raw: str) -> Optional[date]:
            raw = (raw or "").strip()
            if not raw:
                return None
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                return None

        inverted = []
        for o in orders:
            due = _d(o.get("due_date", ""))
            floor = _d(o.get("release_date", "")) or _d(o.get("created_date", ""))
            if due is not None and floor is not None and due < floor:
                inverted.append(o.get("order_id"))
        record(RuleId.ORDER_DATES_INTERNALLY_CONSISTENT,
               RuleOutcome.DEGRADED if inverted else RuleOutcome.SATISFIED,
               _subjects("order_id", inverted),
               f"{len(inverted)} order(s) have due_date before release/created date"
               if inverted else "order dates internally consistent",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"count": len(inverted)})

        # ------------------------------------------------------------
        # Conditional integrity: facility references consistent
        # ------------------------------------------------------------
        declared_facilities = set()
        if manifest is not None:
            declared_facilities = {str(f) for f in (manifest.get("facility_scope") or [])}
        # Facilities that actually appear anywhere are also "declared" if the
        # manifest scope is empty (some submitters omit scope).
        if not declared_facilities:
            declared_facilities = ({(r.get("facility_id") or "").strip() for r in resources}
                                   | {(p.get("facility_id") or "").strip() for p in products})
            declared_facilities.discard("")
        foreign_facility_orders = [
            o.get("order_id") for o in orders
            if (o.get("facility_id") or "").strip()
            and (o.get("facility_id") or "").strip() not in declared_facilities
        ]
        foreign_facility_res = [
            r.get("resource_id") for r in resources
            if (r.get("facility_id") or "").strip()
            and (r.get("facility_id") or "").strip() not in declared_facilities
        ]
        n_foreign = len(foreign_facility_orders) + len(foreign_facility_res)
        record(RuleId.FACILITY_REFERENCES_CONSISTENT,
               RuleOutcome.DEGRADED if n_foreign else RuleOutcome.SATISFIED,
               (_subjects("order_id", foreign_facility_orders)
                + _subjects("resource_id", foreign_facility_res)),
               f"{n_foreign} facility reference(s) outside declared facility scope"
               if n_foreign else "facility references consistent",
               disposition=FindingDisposition.EXCLUDED,
               detail={"orders": len(foreign_facility_orders),
                       "resources": len(foreign_facility_res),
                       "declared": sorted(declared_facilities)[:10]})

        # ------------------------------------------------------------
        # Conditional integrity: orders use active/approved routes
        # ------------------------------------------------------------
        inactive_routes = {
            r.get("route_id") for r in routings
            if str(r.get("status", "")).strip().lower() != "active"
            or str(r.get("approved", "Y")).strip().upper() == "R"
        }
        used_inactive = {o.get("route_id") for o in orders if o.get("route_id") in inactive_routes}
        record(RuleId.ORDERS_USE_ACTIVE_ROUTES,
               RuleOutcome.DEGRADED if used_inactive else RuleOutcome.SATISFIED,
               _subjects("route_id", sorted(used_inactive)),
               f"{len(used_inactive)} route(s) used by orders are inactive/unapproved"
               if used_inactive else "orders use active routes",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"inactive_routes_used": sorted(used_inactive), "count": len(used_inactive)})

        # ------------------------------------------------------------
        # Conditional integrity: setup-family transition matrix (two rules)
        # ------------------------------------------------------------
        used_setup_families = {rl.get("setup_family") for rl in routing_lines if rl.get("setup_family")}
        record(RuleId.SETUP_FAMILIES_HAVE_TRANSITION_MATRIX,
               RuleOutcome.DEGRADED if (used_setup_families and not setup_transitions)
               else RuleOutcome.SATISFIED,
               _subjects("setup_family", sorted(used_setup_families)),
               "setup_family used without a setup_transitions.csv matrix"
               if (used_setup_families and not setup_transitions)
               else "setup families have a transition matrix",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"setup_families": sorted(used_setup_families)})
        record(RuleId.TRANSITION_MATRIX_REFERENCES_DECLARED_FAMILIES,
               RuleOutcome.DEGRADED if (setup_transitions and not used_setup_families)
               else RuleOutcome.SATISFIED,
               _submission_subject(),
               "setup_transitions.csv matrix is unused (no setup_family values)"
               if (setup_transitions and not used_setup_families)
               else "transition matrix references declared families",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"transition_rows": len(setup_transitions)})

        # ------------------------------------------------------------
        # Conditional integrity: alternative-group step attributes agree
        # (docs/06 §5.3). Rows sharing one (route_id, sequence) are ONE
        # operation's eligible set; per-alternative setup_minutes/
        # run_minutes_per_unit are legitimate, but setup_family / dwell /
        # splittable / min_chunk are STEP properties of the operation and must
        # match across the group. Disagreement is resolved first-row-wins
        # downstream (the adapter); the gate flags it so the discrepancy is
        # visible on the certificate rather than silently absorbed.
        _STEP_ATTRS = ("setup_family", "dwell_minutes", "splittable", "min_chunk_minutes")
        alt_groups: dict[tuple[str, str], list[dict]] = {}
        for rl in routing_lines:
            if str(rl.get("active", "0")).strip() != "1":
                continue
            key = (rl.get("route_id", ""), str(rl.get("sequence", "")).strip())
            alt_groups.setdefault(key, []).append(rl)

        def _norm(v: object) -> str:
            return str(v if v is not None else "").strip().lower()

        disagreeing: list[str] = []
        for (route_id, seq), rows in alt_groups.items():
            if len(rows) < 2:
                continue
            for attr in _STEP_ATTRS:
                if len({_norm(r.get(attr)) for r in rows}) > 1:
                    disagreeing.append(f"{route_id}:{seq}:{attr}")
        record(RuleId.ALTERNATIVE_STEP_ATTRIBUTES_AGREE,
               RuleOutcome.DEGRADED if disagreeing else RuleOutcome.SATISFIED,
               _subjects("route_line", sorted(disagreeing)) if disagreeing
               else _submission_subject(),
               f"{len(disagreeing)} alternative-group step-attribute disagreement(s); "
               "first row wins" if disagreeing
               else "alternative-group step attributes agree",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"disagreements": sorted(disagreeing)})

        # ------------------------------------------------------------
        # Conditional integrity: customer references have a master
        # (fires only when customer weighting is declared — §3-correct silence)
        # ------------------------------------------------------------
        has_customer_weighting_declared = bool(
            manifest and "priority_precedence" in manifest.get("semantics", {})
        )
        used_customer_ids = {o.get("customer_id") for o in orders if (o.get("customer_id") or "").strip()}
        customer_master_missing = bool(used_customer_ids and not customers
                                       and has_customer_weighting_declared)
        record(RuleId.CUSTOMER_REFERENCES_HAVE_MASTER,
               RuleOutcome.DEGRADED if customer_master_missing else RuleOutcome.SATISFIED,
               _subjects("customer_id", sorted(used_customer_ids)),
               "customer_id populated on orders but customers.csv is absent"
               if customer_master_missing else "customer references have a master",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"customer_ids": sorted(used_customer_ids)[:10],
                       "count": len(used_customer_ids)})

        # ------------------------------------------------------------
        # Conditional integrity: locks reference known entities
        # ------------------------------------------------------------
        known_order_ids = {o.get("order_id") for o in orders if o.get("order_id")}
        known_resource_ids = {r.get("resource_id") for r in resources if r.get("resource_id")}
        unknown_locks = [
            lk for lk in locks
            if lk.get("order_id") not in known_order_ids
            or lk.get("resource_id") not in known_resource_ids
        ]
        record(RuleId.LOCKS_REFERENCE_KNOWN_ENTITIES,
               RuleOutcome.DEGRADED if unknown_locks else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({lk.get("order_id") for lk in unknown_locks})),
               f"{len(unknown_locks)} lock(s) reference an unknown order or resource"
               if unknown_locks else "locks reference known entities",
               disposition=FindingDisposition.EXCLUDED,
               detail={"unknown_lock_count": len(unknown_locks)})

        # ------------------------------------------------------------
        # Conditional integrity: WIP coherence (docs/06 §5.13)
        # ------------------------------------------------------------
        self._wip_checks(wip_rows, orders, manifest, route_lines_by_route,
                         known_order_ids, known_resource_ids, record, _subjects)

        # ------------------------------------------------------------
        # Conditional integrity: priority classes priced
        # ------------------------------------------------------------
        priority_multipliers = core.get("priority_multipliers", {}) if core else {}
        used_classes = {
            (o.get("priority_class") or "").strip() for o in orders
        } | {
            (o.get("commitment_class") or "").strip() for o in orders
        } | {
            (c.get("priority_class") or "").strip() for c in customers
        }
        used_classes.discard("")
        uncovered = sorted(c for c in used_classes if c not in priority_multipliers)
        # subject the orders that use an uncovered class
        uncovered_order_ids = [
            o.get("order_id") for o in orders
            if (o.get("priority_class") or "").strip() in uncovered
            or (o.get("commitment_class") or "").strip() in uncovered
        ]
        record(RuleId.PRIORITY_CLASSES_PRICED,
               RuleOutcome.DEGRADED if uncovered else RuleOutcome.SATISFIED,
               _subjects("order_id", uncovered_order_ids) or _submission_subject(),
               f"priority/commitment classes not covered by priority_multipliers: {uncovered}"
               if uncovered else "priority classes priced",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"uncovered_classes": uncovered, "known_classes": sorted(priority_multipliers)})

        # ------------------------------------------------------------
        # Quality (informational; never degrades a grade)
        # ------------------------------------------------------------
        ref_date = (date.fromisoformat(manifest["reference_date"][:10])
                    if manifest and manifest.get("reference_date") else None)
        if ref_date:
            stale_cutoff = ref_date - timedelta(days=_STALE_DAYS)
            placeholder_cutoff = date(ref_date.year + _PLACEHOLDER_YEARS, ref_date.month, ref_date.day)
            stale: list[str] = []
            placeholder: list[str] = []
            for o in orders:
                due = _d(o.get("due_date", ""))
                if due is None:
                    continue
                if due < stale_cutoff:
                    stale.append(o.get("order_id"))
                elif due > placeholder_cutoff:
                    placeholder.append(o.get("order_id"))
            record(RuleId.BACKLOG_IS_CURRENT,
                   RuleOutcome.FLAGGED if stale else RuleOutcome.SATISFIED,
                   _subjects("order_id", stale),
                   f"{len(stale)} order(s) with due_date > {_STALE_DAYS}d before reference_date"
                   if stale else "backlog is current",
                   disposition=FindingDisposition.PROCEEDED_FLAGGED,
                   detail={"count": len(stale)}, check="stale_backlog", tier=RecordTier.DETAIL)
            record(RuleId.DUE_DATES_WITHIN_PLANNING_HORIZON,
                   RuleOutcome.FLAGGED if placeholder else RuleOutcome.SATISFIED,
                   _subjects("order_id", placeholder),
                   f"{len(placeholder)} order(s) with implausibly distant due_date "
                   f"(> {_PLACEHOLDER_YEARS}y after reference_date)"
                   if placeholder else "due dates within planning horizon",
                   disposition=FindingDisposition.PROCEEDED_FLAGGED,
                   detail={"count": len(placeholder)}, check="placeholder_date",
                   tier=RecordTier.DETAIL)

        # Quality: statistical outliers in product-level run rate, by product_group
        family_rates: dict[str, list[tuple[float, str]]] = {}
        for p in products:
            lot = _num(p.get("costing_lot_size"))
            mins = _num(p.get("production_minutes"))
            if lot <= 0 or mins <= 0:
                continue
            fam = p.get("product_group") or "unknown"
            family_rates.setdefault(fam, []).append((mins / lot, p.get("product_id", "")))
        outlier_pids: list[str] = []
        for fam, entries in family_rates.items():
            if len(entries) < 2:
                continue
            median = _stats.median([e[0] for e in entries])
            if median <= 0:
                continue
            outlier_pids.extend(pid for rate, pid in entries if rate > 10 * median)
        record(RuleId.DURATIONS_WITHIN_PLAUSIBLE_RANGE,
               RuleOutcome.FLAGGED if outlier_pids else RuleOutcome.SATISFIED,
               _subjects("product_id", outlier_pids),
               f"{len(outlier_pids)} product(s) exceed 10x their family median run rate"
               if outlier_pids else "durations within plausible range",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"outlier_product_ids": outlier_pids[:20], "threshold": "10x"},
               tier=RecordTier.DETAIL)

        # Quality: decision-relevant attributes populated (priority signal)
        no_priority_signal = [
            o.get("order_id") for o in orders
            if not (o.get("priority_class") or "").strip()
            and not (o.get("commitment_class") or "").strip()
        ]
        record(RuleId.DECISION_RELEVANT_ATTRIBUTES_POPULATED,
               RuleOutcome.FLAGGED if no_priority_signal else RuleOutcome.SATISFIED,
               _subjects("order_id", no_priority_signal),
               f"{len(no_priority_signal)} order(s) carry no priority or commitment class"
               if no_priority_signal else "decision-relevant attributes populated",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"count": len(no_priority_signal)}, tier=RecordTier.DETAIL)

        # Quality: optional columns not sparse (present, populated, but below floor)
        sparse_cols: dict[str, float] = {}
        n_orders = len(orders)
        if n_orders:
            for col in OPTIONAL_DENSITY_COLUMNS:
                if col not in headers.get("orders.csv", []):
                    continue
                populated = sum(1 for o in orders if (o.get(col) or "").strip())
                rate = populated / n_orders
                if 0 < rate < _SPARSE_FLOOR:
                    sparse_cols[col] = round(rate, 4)
        record(RuleId.OPTIONAL_COLUMNS_ARE_NOT_SPARSE,
               RuleOutcome.FLAGGED if sparse_cols else RuleOutcome.SATISFIED,
               _submission_subject(),
               f"optional columns sparsely populated below {_SPARSE_FLOOR:.0%}: {sparse_cols}"
               if sparse_cols else "optional columns are not sparse",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"sparse_columns": sparse_cols, "floor": _SPARSE_FLOOR},
               tier=RecordTier.DETAIL)

        # ------------------------------------------------------------
        # Grade = pure function of rule outcomes; costing grade; certificate
        # ------------------------------------------------------------
        grade = grade_from_outcomes(outcomes)
        costing_grade = self._costing_grade(cost_model, resources, setup_transitions)

        flagged = sorted({f["evidence"]["rule_id"] for f in findings
                          if f["evidence"].get("outcome") == "flagged"})
        certificate = {
            "submission_dir": str(submission_dir),
            "run_id": reporter.run_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "grade": grade,
            "costing_completeness_grade": costing_grade,
            "manifest": manifest,
            "deficiencies": deficiencies,
            "normalizations": normalizations,
            "findings": findings,
            "rule_outcomes": rule_outcome,
            "flags_disclosed": flagged,
            "counts": {
                "orders": len(orders), "valid_orders": len(valid_orders),
                "products": len(products), "routings": len(routings),
                "resources": len(resources), "customers": len(customers),
                "setup_transitions": len(setup_transitions), "locks": len(locks),
                "wip_status": len(wip_rows),
            },
        }

        return GateResult(
            grade=grade, costing_grade=costing_grade,
            certificate=certificate, go=(grade != "REJECTED"),
        )

    # ------------------------------------------------------------------
    # WIP coherence (docs/06 §5.13). Findings, never crashes.
    # ------------------------------------------------------------------
    @staticmethod
    def _wip_checks(wip_rows, orders, manifest, route_lines_by_route,
                    known_order_ids, known_resource_ids, record, _subjects) -> None:
        if not wip_rows:
            return
        semantics = (manifest or {}).get("semantics", {})
        wip_basis = semantics.get("wip_progress_basis", "remaining_minutes")
        order_by_id = {o.get("order_id"): o for o in orders if o.get("order_id")}
        route_seqs: dict[str, set[str]] = {
            rid: {str(rl.get("sequence", "")).strip() for rl in lines}
            for rid, lines in route_lines_by_route.items()
        }
        ref_dt = None
        if manifest and manifest.get("reference_date"):
            try:
                ref_dt = date.fromisoformat(manifest["reference_date"][:10])
            except ValueError:
                ref_dt = None

        def _order_seqs(row: dict) -> set[str]:
            order = order_by_id.get(row.get("order_id"))
            return route_seqs.get(order.get("route_id", ""), set()) if order else set()

        # 1) unknown order / sequence / resource refs
        unknown_wip = [
            row for row in wip_rows
            if row.get("order_id") not in known_order_ids
            or str(row.get("sequence", "")).strip() not in _order_seqs(row)
            or ((row.get("actual_resource_id") or "").strip()
                and row["actual_resource_id"].strip() not in known_resource_ids)
        ]
        record(RuleId.WIP_REFERENCES_KNOWN_ENTITIES,
               RuleOutcome.DEGRADED if unknown_wip else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({str(r.get("order_id")) for r in unknown_wip})),
               f"{len(unknown_wip)} wip_status row(s) reference an unknown order, "
               "sequence, or resource" if unknown_wip else "wip references known entities",
               disposition=FindingDisposition.EXCLUDED,
               detail={"count": len(unknown_wip)}, check="wip_unknown_refs")

        # 2) in_progress rows missing observed start/resource/progress
        def _progress_missing(row: dict) -> bool:
            col = ("remaining_minutes" if wip_basis == "remaining_minutes"
                   else "quantity_complete")
            return not (row.get(col) or "").strip()

        incomplete = [
            row for row in wip_rows
            if (row.get("status") or "").strip() == "in_progress"
            and (not (row.get("actual_start") or "").strip()
                 or not (row.get("actual_resource_id") or "").strip()
                 or _progress_missing(row))
        ]
        record(RuleId.WIP_IN_PROGRESS_ROWS_CARRY_PROGRESS,
               RuleOutcome.DEGRADED if incomplete else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({str(r.get("order_id")) for r in incomplete})),
               f"{len(incomplete)} in_progress wip row(s) missing observed start, "
               "resource, or progress value; in-flight state excluded, treated as "
               "not_started" if incomplete
               else "wip in_progress rows carry progress",
               # EXCLUDED, not DEFAULTED: no progress value is invented — the
               # unverifiable in-flight claim is dropped and the operation is
               # scheduled as not_started (errand-a audit 2026-07-10; the charter
               # forbids inventing semantics, so the honest disposition is
               # exclusion, matching wip_references_known_entities).
               disposition=FindingDisposition.EXCLUDED,
               detail={"count": len(incomplete), "progress_basis": wip_basis},
               check="wip_in_progress_incomplete")

        # 3) sequence-order violations
        status_by_order_seq: dict[tuple[str, str], str] = {
            (row.get("order_id", ""), str(row.get("sequence", "")).strip()):
                (row.get("status") or "").strip()
            for row in wip_rows
        }
        violations = []
        for row in wip_rows:
            if (row.get("status") or "").strip() not in ("in_progress", "complete"):
                continue
            oid_w = row.get("order_id", "")
            seq_raw = str(row.get("sequence", "")).strip()
            seqs = _order_seqs(row)
            if not seq_raw.isdigit() or seq_raw not in seqs:
                continue
            for pred in seqs:
                if pred.isdigit() and int(pred) < int(seq_raw):
                    if status_by_order_seq.get((oid_w, pred), "not_started") == "not_started":
                        violations.append((oid_w, seq_raw, pred))
                        break
        record(RuleId.WIP_PROGRESSION_RESPECTS_SEQUENCE,
               RuleOutcome.DEGRADED if violations else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({v[0] for v in violations})),
               f"{len(violations)} wip row(s) report an operation underway while a "
               "predecessor is not_started (shop-floor reporting quality signal)"
               if violations else "wip progression respects sequence",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"count": len(violations),
                       "examples": [f"{o}: seq {s} active while seq {p} not_started"
                                    for o, s, p in violations[:5]]},
               check="wip_sequence_order_violation")

        # 4a) completed op with remaining work — completion wins
        def _remaining_claimed(row: dict) -> bool:
            if _num(row.get("remaining_minutes"), 0.0) > 0:
                return True
            if wip_basis == "quantity_complete" and (row.get("quantity_complete") or "").strip():
                order = order_by_id.get(row.get("order_id"), {})
                qty = _num(order.get("quantity"), 0.0)
                return qty > 0 and _num(row.get("quantity_complete")) < qty
            return False

        complete_with_remaining = [
            row for row in wip_rows
            if (row.get("status") or "").strip() == "complete" and _remaining_claimed(row)
        ]
        record(RuleId.WIP_COMPLETION_IS_INTERNALLY_CONSISTENT,
               RuleOutcome.DEGRADED if complete_with_remaining else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({str(r.get("order_id")) for r in complete_with_remaining})),
               f"{len(complete_with_remaining)} completed wip row(s) still carry remaining "
               "work; completion wins" if complete_with_remaining
               else "wip completion is internally consistent",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"count": len(complete_with_remaining)}, check="wip_complete_with_remaining")

        # 4b) observed start after THIS submission's reference_date
        future_starts = []
        if ref_dt is not None:
            for row in wip_rows:
                raw = (row.get("actual_start") or "").strip()
                if not raw:
                    continue
                try:
                    start_d = date.fromisoformat(raw[:10])
                except ValueError:
                    continue
                if start_d > ref_dt:
                    future_starts.append(row)
        record(RuleId.WIP_ACTUAL_STARTS_ARE_AT_OR_BEFORE_REFERENCE_DATE,
               RuleOutcome.DEGRADED if future_starts else RuleOutcome.SATISFIED,
               _subjects("order_id", sorted({str(r.get("order_id")) for r in future_starts})),
               f"{len(future_starts)} wip row(s) observed to start after reference_date"
               if future_starts else "wip actual starts are at or before reference_date",
               disposition=FindingDisposition.PROCEEDED_FLAGGED,
               detail={"count": len(future_starts),
                       "reference_date": ref_dt.isoformat() if ref_dt else None},
               check="wip_start_after_reference")

    @staticmethod
    def _costing_grade(cost_model: Optional[dict], resources: list[dict],
                        setup_transitions: list[dict]) -> str:
        if not cost_model:
            return "C0"
        refinements = cost_model.get("refinements", {}) or {}

        c1 = bool(refinements.get("resource_rates")) or any(
            _num(r.get("cost_rate")) > 0 for r in resources
        )
        if not c1:
            return "C0"

        has_overtime = refinements.get("overtime_premium_multiplier") is not None
        has_transition_costs = any(
            _num(t.get("setup_cost")) > 0 for t in setup_transitions
        )
        c2 = has_overtime or has_transition_costs
        if not c2:
            return "C1"

        c3 = (
            refinements.get("scrap_cost_per_unit") is not None
            or refinements.get("inventory_carrying") is not None
        )
        if not c3:
            return "C2"
        return "C3"


# ---------------------------------------------------------------------------
# Certificate writers
# ---------------------------------------------------------------------------

def write_certificate_json(certificate: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(certificate, indent=2, default=str), encoding="utf-8")


def write_certificate_markdown(certificate: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append("# Submission Certificate")
    lines.append("")
    lines.append(f"**Grade:** **{certificate['grade']}**  ")
    lines.append(f"**Costing completeness:** {certificate['costing_completeness_grade']}  ")
    lines.append(f"**Submission:** `{certificate['submission_dir']}`  ")
    lines.append(f"**Run:** `{certificate['run_id']}`  ")
    lines.append(f"**Generated:** {certificate['generated_at']}")
    lines.append("")

    if certificate["deficiencies"]:
        lines.append("## Deficiencies (REJECTED)")
        lines.append("")
        for d in certificate["deficiencies"]:
            lines.append(f"- {d}")
        lines.append("")

    if certificate.get("flags_disclosed"):
        lines.append("## Flags disclosed")
        lines.append("")
        for r in certificate["flags_disclosed"]:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("## Counts")
    lines.append("")
    lines.append("| Table | Count |")
    lines.append("|---|---|")
    for k, v in certificate["counts"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    by_sev: dict[str, list[dict]] = {}
    for f in certificate["findings"]:
        by_sev.setdefault(f["severity"], []).append(f)
    for sev in ("blocker", "error", "warning", "info"):
        for f in by_sev.get(sev, []):
            rid = f.get("evidence", {}).get("rule_id", f["code"])
            lines.append(f"- **{sev}** [{rid}] {f['message']} — disposition={f['disposition']}")
    if not certificate["findings"]:
        lines.append("*(none)*")
    lines.append("")

    if certificate["normalizations"]:
        lines.append("## Permitted Normalizations Applied")
        lines.append("")
        for n in certificate["normalizations"]:
            lines.append(f"- {n}")
        lines.append("")

    Path(path).write_text("\n".join(lines), encoding="utf-8")
