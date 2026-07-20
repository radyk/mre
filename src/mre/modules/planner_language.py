"""Planner-language layer (Session 4A.2, CU2 + CU4 + CU6).

The audit's core presentation finding: the conversation stops at machine
vocabulary — driver codes (``CAPACITY_BLOCKED``), finding codes
(``VALUE_OUT_OF_RANGE``), and module ids (``M3``, ``identity_v1``) leak into
answers a planner reads. This module is the single authored bridge from that
vocabulary to plain planner language, per R-AI1(c): intelligence accrues in a
reviewable artifact (this file), never in model state.

Three authored dictionaries + two composers:
  - ``DRIVER_PHRASING``  — the 12 DriverCodes → plain cause (CU4).
  - ``FINDING_PHRASING`` — the 18 FindingCodes → plain cause (CU2).
  - ``JARGON`` / ``strip_jargon`` — module/provenance tokens a planner
    should never see in an answer (CU6).
  - ``compose_finding_sentence`` — the (subject, offending value, plain cause,
    catalog fix) tuple the dq_report already composes, made reusable so the
    conversation is never blinder than the document (CU2).

Every string here is authored by a human and edited in review — a model never
writes them. Add, never repurpose (the vocabulary-change rule): a new code gets
a new entry in the same commit that adds it to ``vocabularies.py``.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Driver codes → plain cause (CU4). One clause per code, planner-voiced,
# present tense, no id-shapes. The 12 DriverCodes (vocabularies.DriverCode).
# ---------------------------------------------------------------------------
DRIVER_PHRASING: dict[str, str] = {
    "COST_TRADEOFF": "it was the cheaper option once every cost was weighed",
    "DUE_DATE_PRESSURE": "its due date was driving the schedule",
    "CAPACITY_BLOCKED": "the machine was busy with other work",
    "CAPABILITY_LIMITED": "only certain machines can run this step",
    "SETUP_AMORTIZATION": "grouping similar jobs together saved changeover time",
    "SEQUENCE_DEPENDENCY": "an earlier step had to finish first",
    "CALENDAR_WINDOW": "the machine's working hours (a shift or a closure) constrained it",
    "FROZEN_COMMITMENT": "this placement was already committed and held in place",
    "DATA_EXCLUSION": "the order was left out of the plan over a data problem",
    "POLICY_RULE": "a scheduling policy required it",
    "SOLVER_LIMIT": "the solver reached its time budget before improving further",
    "NO_ALTERNATIVE": "there was no other feasible option",
}

# ---------------------------------------------------------------------------
# Finding codes → plain cause (CU2). Reads as "<subject> <this clause>". The 18
# FindingCodes (vocabularies.FindingCode).
# ---------------------------------------------------------------------------
FINDING_PHRASING: dict[str, str] = {
    "MISSING_REFERENCE": "points to something that isn't in the data",
    "UNMAPPABLE_VALUE": "has a value the system couldn't interpret",
    "AMBIGUOUS_SOURCE": "has two rows that disagree about the same thing",
    "MALFORMED_FIELD": "is missing a required field or has it malformed",
    "DUPLICATE_IDENTITY": "appears more than once under the same id",
    "IDENTITY_CHANGED": "changed its id between extracts",
    "TEMPORAL_IMPOSSIBILITY": "has dates that can't both be true",
    "NO_CAPABLE_RESOURCE": "has no machine able to run one of its steps",
    "ORPHAN_ENTITY": "has no working route to any machine",
    "VALUE_OUT_OF_RANGE": "has a number outside the plausible range",
    "STATISTICAL_OUTLIER": "has a value that stands out sharply from its peers",
    "PROVENANCE_GAP": "carries a value the system couldn't trace to a source",
    "LOW_CONFIDENCE_INPUT": "rests on an input the system is only weakly sure of",
    "BATCH_CONFLICT": "can't be batched with the orders it was grouped with",
    "INFEASIBLE_SUBSET": "belongs to a set of orders that can't all be met",
    "HORIZON_EXCEEDED": "runs past the end of the planning horizon",
    "SOLVER_NONOPTIMAL": "was scheduled before the solver could prove the best plan",
    "DENSITY_LIMIT": "is in a workload too dense to schedule cleanly",
}


# Module ids → the pipeline stage a planner would recognize (CU6). The raw
# "M4"/"M7" tags are jargon; the stage is provenance worth keeping in plain words.
STAGE_NAMES: dict[str, str] = {
    "M0": "intake check", "M1": "intake", "M2": "modeling", "M3": "validation",
    "M4": "planning", "M5": "batching", "M6": "sequencing", "M7": "scheduling",
    "M9": "index", "M10": "explanation",
}


def stage_name(module: Optional[str]) -> str:
    """Friendly pipeline-stage label for a module id, or a neutral 'the system'."""
    if not module:
        return "the system"
    return STAGE_NAMES.get(str(module).upper(), "the system")


def driver_phrase(code: Optional[str]) -> Optional[str]:
    """Plain-language clause for a driver code, or None if unknown/absent."""
    if not code:
        return None
    return DRIVER_PHRASING.get(str(code).upper())


def finding_phrase(code: Optional[str]) -> str:
    """Plain-language clause for a finding code. Falls back to a neutral clause
    (never leaks the raw code as the whole cause) for an unmapped code."""
    if not code:
        return "has a data-quality problem"
    return FINDING_PHRASING.get(str(code).upper(), "has a data-quality problem")


# ---------------------------------------------------------------------------
# Jargon strip (CU6). Module ids, provenance-scheme names, and internal
# resolver labels that must never appear in a planner-facing answer. Used to
# scrub decision messages ("identity_v1: demand <uuid> -> 1 WorkPackage") that
# the raw evidence chain would otherwise leak.
# ---------------------------------------------------------------------------
_JARGON_RE = re.compile(
    r"\b(?:M0|M1|M2|M3|M4|M5|M6|M7|M9|M10|identity_v\d+|merge_by_family_v\d+|"
    r"snap-[\w-]+|op_assign|op_eligible|WorkPackage|ServiceOutcome|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b"
)


def has_jargon(text: str) -> bool:
    return bool(_JARGON_RE.search(text or ""))


def strip_jargon(text: str) -> str:
    """Remove module/provenance/uuid tokens from a line and tidy the residue.
    Conservative: only drops the known-jargon tokens, leaves planner words."""
    if not text:
        return ""
    out = _JARGON_RE.sub("", text)
    # collapse the punctuation/space debris a removed token leaves behind
    out = re.sub(r"\s*[:>\-]\s*(?=$|\s)", " ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" :->→")
    return out.strip()


# ---------------------------------------------------------------------------
# The finding sentence composer (CU2). The dq_report generator already renders
# (subject, offending value, cause, disposition); this makes the SAME four-part
# composition reusable so the conversation is never blinder than the document.
# The catalog fix is added when a catalog is supplied (the document doesn't have
# it; the conversation should).
# ---------------------------------------------------------------------------

def finding_subject_label(finding: dict, identity_map: Any = None) -> str:
    """The offending entity in the planner's own vocabulary: the identity-map
    external ref for a resolvable subject, else the IDS-space order/entity id the
    finding evidence already carries (the only identity a REJECTED run has).
    Never an id-shape regex (Phase-1 audit lesson) — evidence values only."""
    labels: list[str] = []
    for s in finding.get("subjects", []) or []:
        eid = s.get("entity_id") if isinstance(s, dict) else getattr(s, "entity_id", "")
        if not eid:
            continue
        label = None
        if identity_map is not None:
            erefs = identity_map.external_refs(eid)
            if erefs:
                label = erefs[0].value
        labels.append(label or eid[:12])
    ev = finding.get("evidence", {}) or {}
    erp = (ev.get("order_id") or ev.get("wono") or ev.get("product_no")
           or ev.get("machine_id") or ev.get("demand_id") or "")
    if erp and erp not in labels:
        labels.append(str(erp))
    if not labels:
        return "a record"
    # A finding touching many orders summarizes rather than listing all of them
    # (CU2/CU6 — a 10-order wall is a statistic, not a subject).
    if len(labels) > 3:
        return f"{len(labels)} orders"
    return ", ".join(labels)


def finding_offending_value(finding: dict) -> Optional[str]:
    """The concrete offending value the finding recorded, if any — the number,
    the blank, the two disagreeing values. Pulled from evidence; None when the
    finding carries no scalar specimen (structural findings)."""
    ev = finding.get("evidence", {}) or {}
    for key in ("value", "measured_value", "offending_value", "bad_value",
                "quantity", "actual"):
        if key in ev and ev[key] is not None:
            return str(ev[key])
    measured = ev.get("measured")
    if isinstance(measured, dict) and measured.get("value") is not None:
        return str(measured["value"])
    return None


def compose_finding_sentence(finding: dict, identity_map: Any = None,
                             catalog: Any = None) -> dict:
    """The four mandatory parts of any finding render (CU2): subject, offending
    value, plain-language cause, catalog fix. Statistics are supporting cast, not
    the sentence. Returns a structured dict the renderers turn into prose.

      subject  — the offending order/machine in planner vocabulary
      value    — the concrete offending value (may be None)
      cause    — plain language, from FINDING_PHRASING (never the raw code)
      fix      — the catalog's authored one-line fix (when a catalog is given)
      severity — the finding's own honest severity (Session 4.5)
    """
    code = finding.get("code", "")
    subject = finding_subject_label(finding, identity_map)
    value = finding_offending_value(finding)
    cause = f"{subject} {finding_phrase(code)}"
    if value is not None:
        cause += f" ({value})"
    fix = None
    if catalog is not None:
        fix = _catalog_fix(finding, catalog)
    return {
        "subject": subject,
        "value": value,
        "code": code,
        "cause": cause,
        "fix": fix,
        "severity": finding.get("severity", "info"),
        "disposition": finding.get("disposition", ""),
    }


_SEV_RANK = {"blocker": 0, "error": 1, "warning": 2, "info": 3}


def compose_findings(findings: list[dict], identity_map: Any = None,
                     catalog: Any = None) -> list[dict]:
    """Compose a list of findings into planner-language sentences, COALESCING the
    same defect seen at multiple layers into one (CU6). Two findings coalesce
    when they share (subject, code) — the same order failing the same way, caught
    by the gate AND the adapter, is ONE problem 'confirmed at N layers', not two
    entries that make the count lie. Ordered most-severe first."""
    composed: list[dict] = []
    index: dict[tuple, dict] = {}
    for f in findings:
        c = compose_finding_sentence(f, identity_map, catalog)
        key = (c["subject"], c["code"])
        module = f.get("module", "")
        if key in index:
            item = index[key]
            item["layers"].add(module)
            # keep the most severe severity across the coalesced layers
            if _SEV_RANK.get(c["severity"], 9) < _SEV_RANK.get(item["severity"], 9):
                item["severity"] = c["severity"]
            continue
        c["layers"] = {module} if module else set()
        index[key] = c
        composed.append(c)
    for c in composed:
        c["layer_count"] = len(c["layers"])
        c["layers"] = sorted(x for x in c["layers"] if x)
    composed.sort(key=lambda c: (_SEV_RANK.get(c["severity"], 9), c["subject"]))
    return composed


def _catalog_fix(finding: dict, catalog: Any) -> Optional[str]:
    """The frozen catalog's authored one-line fix for a finding's rule, if the
    finding carries a registry rule_id and the catalog has a note for it."""
    ev = finding.get("evidence", {}) or {}
    rid = ev.get("rule_id")
    if not rid:
        return None
    try:
        from mre.contracts.ids_rules import RuleId
        note = catalog.note_for_rule(RuleId(rid))
    except Exception:
        return None
    if note is None:
        return None
    fix = getattr(note, "fix_looks_like", None) or getattr(note, "how_to_fix", None)
    if fix:
        return re.sub(r"\s+", " ", str(fix)).strip()
    return None
