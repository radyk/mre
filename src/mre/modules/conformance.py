"""M0 — IDS Conformance Gate.

Implements docs/06-incoming-data-spec.md §4 exactly: Tier 1 (structural,
rejecting) / Tier 2 (integrity, conditional) / Tier 3 (quality, informational)
checks, the costing-completeness grade (C0-C3), and the Submission
Certificate (REJECTED / CONDITIONAL / ACCEPTED).

The gate checks; it never repairs (docs/06 §1). The only mutations it makes
to submitted data are the "permitted normalizations" (§4): BOM stripping and
key whitespace trimming, both recorded on the certificate.

Every check emits a standard-vocabulary Finding through the Reporter (module
M0) so the gate run is itself a first-class evidence run, gradeable and
trendable like any other pipeline stage.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.entities import EntityRef
from mre.contracts.vocabularies import (
    FindingCode, FindingDisposition, FindingSeverity, RecordTier,
)
from mre.reporter import Reporter

UTC = timezone.utc

REQUIRED_FILES = (
    "orders.csv", "routings.csv", "routing_lines.csv", "products.csv",
    "resources.csv", "calendars.csv", "cost_model.json",
)
DOORWAY_FILES = ("customers.csv", "setup_transitions.csv", "locks.csv")

# Appendix A default thresholds (v0.2)
_REJECT_BAND = 0.60
_CONDITIONAL_BAND = 0.97
_STALE_DAYS = 365
_PLACEHOLDER_YEARS = 3

_GRADE_ORDER = {"REJECTED": 0, "CONDITIONAL": 1, "ACCEPTED": 2}


def _worse(a: str, b: str) -> str:
    return a if _GRADE_ORDER[a] <= _GRADE_ORDER[b] else b


def _band(rate: float) -> str:
    if rate < _REJECT_BAND:
        return "REJECTED"
    if rate < _CONDITIONAL_BAND:
        return "CONDITIONAL"
    return "ACCEPTED"


def _band_severity(band: str) -> FindingSeverity:
    return {
        "REJECTED": FindingSeverity.BLOCKER,
        "CONDITIONAL": FindingSeverity.ERROR,
        "ACCEPTED": FindingSeverity.WARNING,
    }[band]


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> tuple[list[dict], bool]:
    """Return (rows, had_bom). BOM stripping is a permitted normalization."""
    raw = path.read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    rows = [dict(r) for r in reader]
    return rows, had_bom


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


@dataclass
class GateResult:
    grade: str  # REJECTED / CONDITIONAL / ACCEPTED
    costing_grade: str  # C0..C3
    certificate: dict[str, Any]
    go: bool  # False only when grade == REJECTED


class ConformanceGate:
    """Grades an IDS submission directory against docs/06 §4."""

    def run(self, submission_dir: Path, reporter: Reporter) -> GateResult:
        submission_dir = Path(submission_dir)
        grade = "ACCEPTED"
        deficiencies: list[str] = []
        normalizations: list[str] = []
        findings: list[dict] = []

        def emit(code: FindingCode, severity: FindingSeverity, evidence: dict,
                  disposition: FindingDisposition, message: str,
                  tier: RecordTier = RecordTier.SUPPORTING) -> dict:
            rec = reporter.record_finding(
                code=code, severity=severity, subjects=[],
                evidence=evidence, disposition=disposition, message=message, tier=tier,
            )
            d = json.loads(rec.model_dump_json())
            findings.append(d)
            return d

        def bump_grade(new_grade: str) -> None:
            nonlocal grade
            grade = _worse(grade, new_grade)

        # ------------------------------------------------------------
        # Tier 1a: manifest present and valid JSON
        # ------------------------------------------------------------
        manifest_path = submission_dir / "manifest.json"
        manifest: Optional[dict] = None
        if not manifest_path.exists():
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"file": "manifest.json", "reason": "manifest is required"},
                 FindingDisposition.BLOCKED, "manifest.json is missing", RecordTier.HEADLINE)
            deficiencies.append("manifest.json missing")
            bump_grade("REJECTED")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                emit(FindingCode.MALFORMED_FIELD, FindingSeverity.BLOCKER,
                     {"file": "manifest.json", "error": str(e)},
                     FindingDisposition.BLOCKED, "manifest.json is not valid JSON", RecordTier.HEADLINE)
                deficiencies.append("manifest.json invalid JSON")
                bump_grade("REJECTED")

        # ------------------------------------------------------------
        # Tier 1b: required files present
        # ------------------------------------------------------------
        missing_files = [f for f in REQUIRED_FILES if not (submission_dir / f).exists()]
        for fname in missing_files:
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"file": fname, "reason": "required file absent"},
                 FindingDisposition.BLOCKED, f"Required file '{fname}' is missing", RecordTier.HEADLINE)
            deficiencies.append(f"required file missing: {fname}")
        if missing_files:
            bump_grade("REJECTED")

        # ------------------------------------------------------------
        # Load whatever is present
        # ------------------------------------------------------------
        tables: dict[str, list[dict]] = {}
        for fname in REQUIRED_FILES + DOORWAY_FILES:
            path = submission_dir / fname
            if fname.endswith(".csv") and path.exists():
                rows, had_bom = _read_csv(path)
                if had_bom:
                    normalizations.append(f"BOM stripped: {fname}")
                key_cols = [c for c in ("order_id", "product_id", "route_id", "resource_id",
                                        "calendar_id", "customer_id") if rows and c in rows[0]]
                if _trim_keys(rows, key_cols):
                    normalizations.append(f"key whitespace trimmed: {fname}")
                tables[fname] = rows

        cost_model: Optional[dict] = None
        cm_path = submission_dir / "cost_model.json"
        if cm_path.exists():
            try:
                cost_model = json.loads(cm_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                emit(FindingCode.MALFORMED_FIELD, FindingSeverity.BLOCKER,
                     {"file": "cost_model.json", "error": str(e)},
                     FindingDisposition.BLOCKED, "cost_model.json is not valid JSON", RecordTier.HEADLINE)
                deficiencies.append("cost_model.json invalid JSON")
                bump_grade("REJECTED")

        orders = tables.get("orders.csv", [])
        routings = tables.get("routings.csv", [])
        routing_lines = tables.get("routing_lines.csv", [])
        products = tables.get("products.csv", [])
        resources = tables.get("resources.csv", [])
        calendars = tables.get("calendars.csv", [])
        customers = tables.get("customers.csv", [])
        setup_transitions = tables.get("setup_transitions.csv", [])
        locks = tables.get("locks.csv", [])

        # ------------------------------------------------------------
        # Tier 1c: manifest semantics required-field checks
        # ------------------------------------------------------------
        if manifest is not None:
            semantics = manifest.get("semantics", {})
            has_customer_priority = any((c.get("priority_class") or "").strip() for c in customers)
            has_order_priority = any((o.get("priority_class") or "").strip() for o in orders)
            if has_customer_priority and has_order_priority and "priority_precedence" not in semantics:
                emit(FindingCode.MALFORMED_FIELD, FindingSeverity.BLOCKER,
                     {"field": "semantics.priority_precedence",
                      "reason": "required when both customer and order priorities are present"},
                     FindingDisposition.BLOCKED,
                     "manifest.semantics.priority_precedence missing", RecordTier.HEADLINE)
                deficiencies.append("manifest.semantics.priority_precedence missing")
                bump_grade("REJECTED")
            if setup_transitions and "unlisted_transition_default" not in semantics:
                emit(FindingCode.MALFORMED_FIELD, FindingSeverity.BLOCKER,
                     {"field": "semantics.unlisted_transition_default",
                      "reason": "required when setup_transitions.csv is present"},
                     FindingDisposition.BLOCKED,
                     "manifest.semantics.unlisted_transition_default missing", RecordTier.HEADLINE)
                deficiencies.append("manifest.semantics.unlisted_transition_default missing")
                bump_grade("REJECTED")

        # ------------------------------------------------------------
        # Tier 1d: cost model core present in full
        # ------------------------------------------------------------
        core = (cost_model or {}).get("core", {})
        required_core_fields = ("default_resource_rate_per_hour", "setup_cost_per_setup",
                                 "tardiness_cost_per_hour", "priority_multipliers")
        missing_core = [
            f for f in required_core_fields
            if f not in core or core.get(f) in (None, "", {})
        ]
        if cost_model is not None and missing_core:
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"missing_core_fields": missing_core},
                 FindingDisposition.BLOCKED,
                 f"cost_model.json core is incomplete: {missing_core}", RecordTier.HEADLINE)
            deficiencies.append(f"cost_model core incomplete: {missing_core}")
            bump_grade("REJECTED")

        # ------------------------------------------------------------
        # Tier 1e: >=1 in-scope order / resource / calendar pattern
        # ------------------------------------------------------------
        valid_orders = [
            o for o in orders
            if (o.get("order_id") or "").strip()
            and (o.get("product_id") or "").strip()
            and (o.get("route_id") or "").strip()
            and _num(o.get("quantity")) > 0
            and (o.get("due_date") or "").strip()
        ]
        if not valid_orders:
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"reason": "no order row has all required fields populated"},
                 FindingDisposition.BLOCKED, "Zero valid orders", RecordTier.HEADLINE)
            deficiencies.append("zero valid orders")
            bump_grade("REJECTED")

        if not resources:
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"reason": "resources.csv has no rows"},
                 FindingDisposition.BLOCKED, "Zero resources", RecordTier.HEADLINE)
            deficiencies.append("zero resources")
            bump_grade("REJECTED")

        pattern_rows = [c for c in calendars if c.get("row_type", "pattern") == "pattern"]
        if not pattern_rows:
            emit(FindingCode.MISSING_REFERENCE, FindingSeverity.BLOCKER,
                 {"reason": "calendars.csv has zero pattern rows; capacity is not optional"},
                 FindingDisposition.BLOCKED, "Zero calendar pattern rows", RecordTier.HEADLINE)
            deficiencies.append("zero calendar pattern rows")
            bump_grade("REJECTED")

        # ------------------------------------------------------------
        # Tier 1/2: reference-chain resolution rates (banded)
        # ------------------------------------------------------------
        product_ids = {p.get("product_id") for p in products if p.get("product_id")}
        route_ids_active = {
            r.get("route_id") for r in routings
            if r.get("route_id") and str(r.get("status", "")).strip().lower() == "active"
        }
        route_lines_by_route: dict[str, list[dict]] = {}
        for rl in routing_lines:
            if str(rl.get("active", "0")).strip() == "1":
                route_lines_by_route.setdefault(rl.get("route_id", ""), []).append(rl)
        routes_with_lines = {rid for rid, lines in route_lines_by_route.items() if lines}

        total = len(orders) or 1

        product_resolved = sum(1 for o in orders if o.get("product_id") in product_ids)
        product_rate = product_resolved / total
        product_band = _band(product_rate)
        emit(FindingCode.ORPHAN_ENTITY, _band_severity(product_band),
             {"resolved": product_resolved, "total": len(orders), "rate": round(product_rate, 4),
              "check": "order_to_product"},
             FindingDisposition.EXCLUDED if product_band != "ACCEPTED" or product_resolved < len(orders)
             else FindingDisposition.PROCEEDED_FLAGGED,
             f"order->product resolution rate {product_rate:.1%}", RecordTier.SUPPORTING)
        bump_grade(product_band)

        route_ids_all = {r.get("route_id") for r in routings if r.get("route_id")}
        route_resolved = sum(
            1 for o in orders
            if o.get("route_id") in route_ids_all and o.get("route_id") in routes_with_lines
        )
        route_rate = route_resolved / total
        route_band = _band(route_rate)
        emit(FindingCode.ORPHAN_ENTITY, _band_severity(route_band),
             {"resolved": route_resolved, "total": len(orders), "rate": round(route_rate, 4),
              "check": "order_to_route"},
             FindingDisposition.EXCLUDED if route_band != "ACCEPTED" or route_resolved < len(orders)
             else FindingDisposition.PROCEEDED_FLAGGED,
             f"order->route resolution rate {route_rate:.1%}", RecordTier.SUPPORTING)
        bump_grade(route_band)

        # Duration computability — only meaningful for orders whose product+route resolved
        products_by_id = {p.get("product_id"): p for p in products}

        def _order_duration_computable(order: dict) -> bool:
            pid, rid = order.get("product_id"), order.get("route_id")
            if pid not in product_ids or rid not in routes_with_lines:
                return True  # already counted by the resolution checks above
            prod = products_by_id.get(pid, {})
            lines = route_lines_by_route.get(rid, [])
            for line in lines:
                has_override = _num(line.get("run_minutes_per_unit")) > 0
                if has_override:
                    continue
                lot = _num(prod.get("costing_lot_size"))
                mins = _num(prod.get("production_minutes"))
                if lot <= 0 or mins <= 0:
                    return False
            return True

        computable = sum(1 for o in orders if _order_duration_computable(o))
        duration_rate = computable / total
        duration_band = _band(duration_rate)
        if computable < len(orders):
            emit(FindingCode.VALUE_OUT_OF_RANGE, _band_severity(duration_band),
                 {"computable": computable, "total": len(orders), "rate": round(duration_rate, 4),
                  "check": "duration_computability",
                  "reason": "product costing_lot_size/production_minutes is 0 or missing "
                            "and routing_lines carries no per-operation override"},
                 FindingDisposition.EXCLUDED,
                 f"duration computability rate {duration_rate:.1%}", RecordTier.SUPPORTING)
            bump_grade(duration_band)

        # ------------------------------------------------------------
        # Tier 2: duplicate order_id
        # ------------------------------------------------------------
        seen: dict[str, int] = {}
        for o in orders:
            oid = o.get("order_id", "")
            seen[oid] = seen.get(oid, 0) + 1
        dup_count = sum(c - 1 for c in seen.values() if c > 1)
        if dup_count > 0:
            emit(FindingCode.DUPLICATE_IDENTITY, FindingSeverity.ERROR,
                 {"duplicate_count": dup_count},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 f"{dup_count} duplicate order_id row(s); first occurrence kept", RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        # ------------------------------------------------------------
        # Tier 2: inactive/unapproved route usage
        # ------------------------------------------------------------
        inactive_routes = {
            r.get("route_id") for r in routings
            if str(r.get("status", "")).strip().lower() != "active"
            or str(r.get("approved", "Y")).strip().upper() == "R"
        }
        used_inactive = {o.get("route_id") for o in orders if o.get("route_id") in inactive_routes}
        if used_inactive:
            emit(FindingCode.LOW_CONFIDENCE_INPUT, FindingSeverity.WARNING,
                 {"inactive_routes_used": sorted(used_inactive), "count": len(used_inactive)},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 f"{len(used_inactive)} route(s) used by orders are inactive/unapproved",
                 RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        # ------------------------------------------------------------
        # Tier 2: doorway consistency
        # ------------------------------------------------------------
        used_setup_families = {rl.get("setup_family") for rl in routing_lines if rl.get("setup_family")}
        if used_setup_families and not setup_transitions:
            emit(FindingCode.AMBIGUOUS_SOURCE, FindingSeverity.WARNING,
                 {"setup_families": sorted(used_setup_families),
                  "reason": "setup_family populated in routing_lines.csv but setup_transitions.csv absent"},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 "setup_family used without a setup_transitions.csv matrix", RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")
        elif setup_transitions and not used_setup_families:
            emit(FindingCode.AMBIGUOUS_SOURCE, FindingSeverity.WARNING,
                 {"reason": "setup_transitions.csv present but no setup_family values are used"},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 "setup_transitions.csv matrix is unused", RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        has_customer_weighting_declared = bool(
            manifest and "priority_precedence" in manifest.get("semantics", {})
        )
        used_customer_ids = {o.get("customer_id") for o in orders if (o.get("customer_id") or "").strip()}
        if used_customer_ids and not customers and has_customer_weighting_declared:
            emit(FindingCode.AMBIGUOUS_SOURCE, FindingSeverity.WARNING,
                 {"customer_ids": sorted(used_customer_ids)[:10], "count": len(used_customer_ids)},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 "customer_id populated on orders but customers.csv is absent", RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        known_order_ids = {o.get("order_id") for o in orders if o.get("order_id")}
        known_resource_ids = {r.get("resource_id") for r in resources if r.get("resource_id")}
        unknown_locks = [
            lk for lk in locks
            if lk.get("order_id") not in known_order_ids
            or lk.get("resource_id") not in known_resource_ids
        ]
        if unknown_locks:
            emit(FindingCode.ORPHAN_ENTITY, FindingSeverity.ERROR,
                 {"unknown_lock_count": len(unknown_locks),
                  "order_ids": sorted({lk.get("order_id") for lk in unknown_locks})[:10]},
                 FindingDisposition.EXCLUDED,
                 f"{len(unknown_locks)} lock(s) reference an unknown order or resource",
                 RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        # ------------------------------------------------------------
        # Tier 2: priority_multipliers coverage
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
        if uncovered:
            emit(FindingCode.UNMAPPABLE_VALUE, FindingSeverity.ERROR,
                 {"uncovered_classes": uncovered, "known_classes": sorted(priority_multipliers)},
                 FindingDisposition.PROCEEDED_FLAGGED,
                 f"priority/commitment classes not covered by priority_multipliers: {uncovered}",
                 RecordTier.SUPPORTING)
            bump_grade("CONDITIONAL")

        # ------------------------------------------------------------
        # Tier 3: informational quality checks (never move grade below ACCEPTED)
        # ------------------------------------------------------------
        ref_date = date.fromisoformat(manifest["reference_date"]) if manifest and manifest.get("reference_date") else None
        if ref_date:
            stale_cutoff = ref_date - timedelta(days=_STALE_DAYS)
            placeholder_cutoff = date(ref_date.year + _PLACEHOLDER_YEARS, ref_date.month, ref_date.day)
            stale = []
            placeholder = []
            for o in orders:
                due_raw = (o.get("due_date") or "")[:10]
                try:
                    due = date.fromisoformat(due_raw)
                except ValueError:
                    continue
                if due < stale_cutoff:
                    stale.append(o.get("order_id"))
                elif due > placeholder_cutoff:
                    placeholder.append(o.get("order_id"))
            if stale:
                emit(FindingCode.VALUE_OUT_OF_RANGE, FindingSeverity.INFO,
                     {"stale_order_ids": stale[:10], "count": len(stale), "check": "stale_backlog"},
                     FindingDisposition.PROCEEDED_FLAGGED,
                     f"{len(stale)} order(s) with due_date > {_STALE_DAYS}d before reference_date",
                     RecordTier.DETAIL)
            if placeholder:
                emit(FindingCode.VALUE_OUT_OF_RANGE, FindingSeverity.INFO,
                     {"placeholder_order_ids": placeholder[:10], "count": len(placeholder),
                      "check": "placeholder_date"},
                     FindingDisposition.PROCEEDED_FLAGGED,
                     f"{len(placeholder)} order(s) with implausibly distant due_date "
                     f"(> {_PLACEHOLDER_YEARS}y after reference_date)",
                     RecordTier.DETAIL)

        # Tier 3: statistical outliers in product-level run rate, by product_group
        family_rates: dict[str, list[tuple[float, str]]] = {}
        for p in products:
            lot = _num(p.get("costing_lot_size"))
            mins = _num(p.get("production_minutes"))
            if lot <= 0 or mins <= 0:
                continue
            fam = p.get("product_group") or "unknown"
            rate = mins / lot
            family_rates.setdefault(fam, []).append((rate, p.get("product_id", "")))
        import statistics as _stats
        for fam, entries in family_rates.items():
            if len(entries) < 2:
                continue
            rates = [e[0] for e in entries]
            median = _stats.median(rates)
            if median <= 0:
                continue
            outliers = [pid for rate, pid in entries if rate > 10 * median]
            if outliers:
                emit(FindingCode.STATISTICAL_OUTLIER, FindingSeverity.INFO,
                     {"family": fam, "outlier_product_ids": outliers, "median": median,
                      "threshold": "10x"},
                     FindingDisposition.PROCEEDED_FLAGGED,
                     f"{len(outliers)} product(s) in family '{fam}' exceed 10x median run rate",
                     RecordTier.DETAIL)

        # ------------------------------------------------------------
        # Costing-completeness grade (C0-C3)
        # ------------------------------------------------------------
        costing_grade = self._costing_grade(cost_model, resources, setup_transitions)

        # ------------------------------------------------------------
        # Assemble certificate
        # ------------------------------------------------------------
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
            "counts": {
                "orders": len(orders), "valid_orders": len(valid_orders),
                "products": len(products), "routings": len(routings),
                "resources": len(resources), "customers": len(customers),
                "setup_transitions": len(setup_transitions), "locks": len(locks),
            },
        }

        return GateResult(
            grade=grade, costing_grade=costing_grade,
            certificate=certificate, go=(grade != "REJECTED"),
        )

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
            lines.append(f"- **{sev}** [{f['code']}] {f['message']} — disposition={f['disposition']}")
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
