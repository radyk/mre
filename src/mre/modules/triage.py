"""Grade-distance triage (handoff §5) — one deterministic fix-first ordering.

A pure function over a certificate's findings + Appendix A thresholds, so the
judgment register and any future UI consume exactly one ordering. Ruled in the
design thread:

  all `violated` first; then `degraded` ordered by proximity to the Appendix A
  threshold that escapes the band (closest escape first); then `flagged` with
  WARNING before INFO; quality flags last.

Ordering is outcome-driven (grade distance); the displayed severity is the
finding's own, honest severity (Session 4.5: severity derives from disposition,
so a proceeded flag is WARNING and a quality flag is INFO — no re-derivation
here). Judgment phrasing names the arithmetic the ordering rests on (rule,
measured value, threshold, distance); ``triage_arithmetic`` exposes it.
"""
from __future__ import annotations

from typing import Any, Optional

from mre.catalog import RemediationCatalog, load_catalog
from mre.contracts.ids_rules import (
    RULE_REGISTRY, RuleCategory, RuleId,
    resolve_threshold_band,
)

_OUTCOME_TIER = {"violated": 0, "degraded": 1, "flagged": 2}
_SEV_RANK = {"blocker": 0, "error": 1, "warning": 2, "info": 3}


def _rule_of(finding: dict) -> Optional[RuleId]:
    rid = finding.get("evidence", {}).get("rule_id")
    if rid is None:
        return None
    try:
        return RuleId(rid)
    except ValueError:
        return None


def escape_distance(finding: dict,
                    catalog: Optional[RemediationCatalog] = None) -> Optional[float]:
    """For a `degraded` banded finding, the distance from its measured value up
    to the Appendix A threshold that would escape the band (the conditional
    floor). None when the finding is not a banded degrade with a measured value
    — those carry no rate distance and sort after the ones that do."""
    ev = finding.get("evidence", {})
    if ev.get("outcome") != "degraded":
        return None
    rule_id = _rule_of(finding)
    if rule_id is None:
        return None
    catalog = catalog or load_catalog()
    note = catalog.note_for_rule(rule_id)
    band = resolve_threshold_band(note.thresholds_ref) if note else None
    measured = ev.get("measured")
    if band is None or not measured:
        return None
    return band.conditional - float(measured["value"])


def _sort_key(finding: dict, catalog: RemediationCatalog):
    ev = finding.get("evidence", {})
    outcome = ev.get("outcome", "flagged")
    tier = _OUTCOME_TIER.get(outcome, 3)
    dist = escape_distance(finding, catalog)
    dist_key = dist if dist is not None else float("inf")
    rule_id = _rule_of(finding)
    spec = RULE_REGISTRY.get(rule_id) if rule_id else None
    is_quality = spec is not None and spec.category == RuleCategory.QUALITY
    sev_rank = _SEV_RANK.get(finding.get("severity", "info"), 4)
    # rule_id (or code) as the final, stable tiebreak — the ordering is total.
    ident = ev.get("rule_id") or finding.get("code", "")
    return (tier, dist_key, sev_rank, is_quality, ident)


def triage_findings(findings: list[dict],
                    catalog: Optional[RemediationCatalog] = None) -> list[dict]:
    """Return the non-satisfied findings in deterministic fix-first order.

    Findings without a non-satisfied outcome (satisfied, or non-gate findings
    with no outcome in evidence) are dropped — triage answers "what should I fix
    first?" over the certificate's actual defects."""
    catalog = catalog or load_catalog()
    actionable = [
        f for f in findings
        if f.get("evidence", {}).get("outcome") in _OUTCOME_TIER
    ]
    return sorted(actionable, key=lambda f: _sort_key(f, catalog))


def triage_arithmetic(finding: dict,
                      catalog: Optional[RemediationCatalog] = None) -> dict[str, Any]:
    """The arithmetic the judgment register names: rule, outcome, measured
    value, escaping threshold, and distance. Values are None where the rule
    carries no rate band (structural/most conditional/quality rules)."""
    catalog = catalog or load_catalog()
    ev = finding.get("evidence", {})
    rule_id = _rule_of(finding)
    note = catalog.note_for_rule(rule_id) if rule_id else None
    band = resolve_threshold_band(note.thresholds_ref) if note else None
    measured = ev.get("measured")
    measured_value = float(measured["value"]) if measured else None
    outcome = ev.get("outcome")
    threshold = None
    if band is not None:
        threshold = band.reject if outcome == "violated" else band.conditional
    distance = escape_distance(finding, catalog)
    return {
        "rule_id": ev.get("rule_id"),
        "outcome": outcome,
        "measured": measured_value,
        "threshold": threshold,
        "distance": distance,
    }


def _severity_label(finding: dict) -> str:
    # The finding's own severity is now the honest consequence (Session 4.5);
    # display it directly rather than re-deriving from the outcome.
    return str(finding.get("severity", "info")).upper()


def render_triage_body(findings: list[dict],
                       catalog: Optional[RemediationCatalog] = None) -> str:
    """Judgment body: the fix-first order with the arithmetic named for each
    finding (rule, measured value, threshold, distance). Built purely from
    evidence values — it never computes a number the certificate did not
    record."""
    catalog = catalog or load_catalog()
    ordered = triage_findings(findings, catalog)
    if not ordered:
        return "Fix-first order: nothing to prioritize — no non-satisfied findings."
    lines = [f"Fix-first order ({len(ordered)} finding(s)); all `violated` first, "
             "then `degraded` by closest escape, then flags (WARNING before INFO, "
             "quality last):", ""]
    for i, f in enumerate(ordered, 1):
        arith = triage_arithmetic(f, catalog)
        rid = arith["rule_id"] or f.get("code", "?")
        sev = _severity_label(f)
        head = f"  {i}. [{rid}] {arith['outcome']} ({sev})"
        lines.append(head)
        if arith["measured"] is not None and arith["threshold"] is not None:
            m = f"{arith['measured'] * 100:.0f}%"
            t = f"{arith['threshold'] * 100:.0f}%"
            if arith["distance"] is not None:
                d = f"{arith['distance'] * 100:.1f} pts"
                lines.append(f"       measured {m}, needs {t} to clear the band "
                             f"— {d} short")
            else:
                lines.append(f"       measured {m} against {t} floor")
        elif arith["outcome"] == "degraded":
            lines.append("       count-based degrade — no Appendix A rate distance")
        elif sev == "INFO":
            lines.append("       quality flag — informational, cannot degrade the grade")
    return "\n".join(lines)
