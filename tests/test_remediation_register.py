"""Remediation register + grade-distance triage — unit level (handoff §3, §5).

Synthetic finding dicts (the same shape the certificate stores) so the renderer,
the fail-closed number validator, the fallback-resolution order, and the pure
triage function are pinned precisely and fast.
"""
from __future__ import annotations

from mre.modules.remediation import (
    allowed_numbers, build_remediation_item, render_remediation_body,
    unverifiable_numbers,
)
from mre.modules.triage import (
    escape_distance, triage_arithmetic, triage_findings,
)


def _banded(rule_id, outcome, value, code="ORPHAN_ENTITY", severity="error"):
    return {
        "record_type": "finding", "code": code, "severity": severity,
        "disposition": "excluded", "message": f"{rule_id} {outcome}",
        "subjects": [{"entity_id": "ORD-1", "entity_type": "order_id", "system": "IDS"}],
        "evidence": {
            "rule_id": rule_id, "outcome": outcome,
            "measured": {"name": "rate", "value": value, "unit": "ratio"},
            "thresholds_ref": "App A",
        },
    }


def _plain(rule_id, outcome, code, severity):
    return {
        "record_type": "finding", "code": code, "severity": severity,
        "disposition": "proceeded_flagged", "message": f"{rule_id} {outcome}",
        "subjects": [{"entity_id": "ORD-9", "entity_type": "order_id", "system": "IDS"}],
        "evidence": {"rule_id": rule_id, "outcome": outcome, "count": 3},
    }


# --------------------------------------------------------------------------
# Number validator — single source of truth, fail closed
# --------------------------------------------------------------------------

class TestNumberValidator:
    def test_allowed_numbers_extracts_all_tokens(self):
        assert allowed_numbers("55% at 60 and 0.97") == {"55%", "60", "0.97"}

    def test_unverifiable_flags_invented_number(self):
        allowed = allowed_numbers("resolution 96% below 97%")
        assert unverifiable_numbers("it is 96% not 12%", allowed) == ["12%"]

    def test_clean_render_invents_nothing(self):
        f = _banded("ids.orders_resolve_to_products", "degraded", 0.96)
        item = build_remediation_item(f)
        assert item.validate() == []


# --------------------------------------------------------------------------
# Rule-level rendering
# --------------------------------------------------------------------------

class TestRuleRendering:
    def test_banded_degraded_shows_measure_threshold_note_and_ref(self):
        f = _banded("ids.orders_resolve_to_products", "degraded", 0.96)
        item = build_remediation_item(f)
        assert item.kind == "rule"
        assert item.rule_id == "ids.orders_resolve_to_products"
        assert "96%" in item.text and "97%" in item.text and "60%" in item.text
        assert "catalog note v1" in item.text
        assert "§5.1, App A" in item.text            # registry ids_ref
        assert "triage is required" in item.text      # degraded band phrasing

    def test_phrasing_keys_on_the_findings_outcome(self):
        viol = build_remediation_item(
            _banded("ids.orders_resolve_to_products", "violated", 0.4, severity="blocker"))
        assert "cannot proceed" in viol.text


# --------------------------------------------------------------------------
# Fallback resolution order
# --------------------------------------------------------------------------

class TestFallbackResolution:
    def test_unknown_rule_falls_back_to_code(self):
        # rule_id not in the registry → resolve by finding code fallback
        f = {
            "record_type": "finding", "code": "INFEASIBLE_SUBSET",
            "severity": "error", "disposition": "excluded", "message": "x",
            "subjects": [], "evidence": {"rule_id": "ids.not_a_real_rule",
                                          "outcome": "degraded"},
        }
        item = build_remediation_item(f)
        assert item.kind == "fallback_no_fix"
        assert item.finding_code == "INFEASIBLE_SUBSET"
        assert "nothing in the submission is at fault" in item.text

    def test_applicable_fallback_gives_generic_guidance(self):
        f = {
            "record_type": "finding", "code": "MISSING_REFERENCE",
            "severity": "blocker", "disposition": "blocked", "message": "x",
            "subjects": [], "evidence": {},  # no rule_id at all
        }
        item = build_remediation_item(f)
        assert item.kind == "fallback"
        assert "Guidance:" in item.text


# --------------------------------------------------------------------------
# Triage — pure grade-distance ordering
# --------------------------------------------------------------------------

class TestTriageOrdering:
    def _mix(self):
        return [
            _plain("ids.backlog_is_current", "flagged", "VALUE_OUT_OF_RANGE", "info"),
            _banded("ids.orders_resolve_to_products", "degraded", 0.70),  # far
            _banded("ids.orders_resolve_to_routes", "degraded", 0.96),    # near
            _plain("ids.order_identities_unique", "degraded",
                   "DUPLICATE_IDENTITY", "error"),                        # no rate
            _banded("ids.orders_resolve_to_products", "violated", 0.4, severity="blocker"),
        ]

    def test_full_order(self):
        order = [f["evidence"]["rule_id"] for f in triage_findings(self._mix())]
        assert order == [
            "ids.orders_resolve_to_products",   # violated first
            "ids.orders_resolve_to_routes",     # degraded, closest escape (0.96)
            "ids.orders_resolve_to_products",   # degraded, farther (0.70)
            "ids.order_identities_unique",      # degraded, no rate distance → last
            "ids.backlog_is_current",           # flagged quality last
        ]

    def test_escape_distance_math(self):
        near = _banded("ids.orders_resolve_to_routes", "degraded", 0.96)
        assert abs(escape_distance(near, None) - 0.01) < 1e-9

    def test_arithmetic_names_rule_measured_threshold_distance(self):
        near = _banded("ids.orders_resolve_to_routes", "degraded", 0.96)
        a = triage_arithmetic(near)
        assert a["rule_id"] == "ids.orders_resolve_to_routes"
        assert abs(a["measured"] - 0.96) < 1e-9
        assert abs(a["threshold"] - 0.97) < 1e-9
        assert abs(a["distance"] - 0.01) < 1e-9

    def test_satisfied_findings_dropped(self):
        sat = _banded("ids.orders_resolve_to_products", "satisfied", 1.0)
        assert triage_findings([sat]) == []
