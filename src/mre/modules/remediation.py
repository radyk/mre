"""Remediation register (handoff §3) — renderer + fail-closed number validator.

The third answer register, alongside testimony and judgment. Rendering a
remediation is the frozen catalog note's *authored* text instantiated with one
finding's evidence values (subjects, measured value, threshold from
thresholds_ref, band phrasing keyed by the finding's outcome). The catalog is
the source of the words; the finding is the source of the numbers. Nothing is
invented at answer time — the register assembles and cites, it does not author.

Post-render validator (the 2026-07-06 single-source-of-truth lesson): the
allowed-number set is derived from *exactly* the material used to render — note
prose + finding evidence + the threshold/measured values formatted for display
— in one derivation, and the rendered text is validated against it. A number
not in the set fails closed (the LLM path then falls back to this deterministic
template). Register phrasing introduces the output as authored guidance, with
the catalog note_version as a footnote — never as testimony.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from mre.catalog import RemediationCatalog, load_catalog
from mre.contracts.ids_rules import (
    RULE_REGISTRY, RuleId, RuleOutcome, resolve_threshold_band,
)
from mre.contracts.vocabularies import FindingCode
from mre.modules.triage import (
    _advisory_meaning, _render_advisory_only, advisory_findings, triage_findings,
)

_NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")


def _collapse(text: str) -> str:
    """Folded-scalar YAML leaves single spaces but a trailing newline; also
    normalize any residual internal whitespace runs for one-line rendering."""
    return re.sub(r"\s+", " ", (text or "").strip())


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def allowed_numbers(material: str) -> set[str]:
    """The single derivation: every numeric token appearing in the render
    material. `material` must be exactly what was placed in front of the
    renderer (note prose + evidence + formatted thresholds), nothing more."""
    return set(_NUM_RE.findall(material))


def unverifiable_numbers(rendered: str, allowed: set[str]) -> list[str]:
    """Numbers in the rendered text absent from the allowed set — a non-empty
    return means the render invented a value and must fail closed."""
    return [t for t in _NUM_RE.findall(rendered) if t not in allowed]


@dataclass
class RemediationItem:
    """One finding's rendered remediation + the material it was built from."""
    rule_id: Optional[str]
    finding_code: str
    outcome: Optional[str]
    ids_ref: Optional[str]
    note_version: int
    kind: str                 # "rule" | "fallback" | "fallback_no_fix"
    text: str
    material: str = field(repr=False, default="")

    def validate(self) -> list[str]:
        return unverifiable_numbers(self.text, allowed_numbers(self.material))


def _measured_and_threshold_material(finding: dict, note) -> tuple[str, str]:
    """Return (measured_line, extra_material). The measured line is rendered
    only for banded findings that carry a measurement; extra_material carries
    the formatted numbers so the validator whitelists exactly what we showed."""
    ev = finding.get("evidence", {})
    measured = ev.get("measured")
    band = resolve_threshold_band(note.thresholds_ref) if note else None
    if not measured or band is None:
        return "", ""
    m_pct = _pct(float(measured["value"]))
    reject_pct = _pct(band.reject)
    cond_pct = _pct(band.conditional)
    line = (f"    Measured: {m_pct} "
            f"(rejection floor {reject_pct}, accepted floor {cond_pct})")
    return line, f"{m_pct} {reject_pct} {cond_pct}"


def _render_rule_item(finding: dict, note, spec) -> RemediationItem:
    ev = finding.get("evidence", {})
    outcome_str = ev.get("outcome")
    outcome = RuleOutcome(outcome_str) if outcome_str else None
    phrasing = note.phrasing_for(outcome) if outcome else None

    meaning = _collapse(note.meaning)
    fix = _collapse(note.fix_looks_like)
    verify = _collapse(note.verify)
    causes = [_collapse(c) for c in note.typical_causes]
    measured_line, measured_material = _measured_and_threshold_material(finding, note)

    lines = [f"[{note.rule_id.value}] {_collapse(phrasing) if phrasing else meaning}"]
    lines.append(f"    What this checks: {meaning}")
    if measured_line:
        lines.append(measured_line)
    lines.append("    Likely causes:")
    lines.extend(f"      - {c}" for c in causes)
    lines.append(f"    How to fix: {fix}")
    lines.append(f"    Verify: {verify}")
    lines.append(f"    — remediation guidance, catalog note v{note.note_version}; "
                 f"cites IDS {spec.ids_ref}")
    text = "\n".join(lines)

    material = " ".join([
        _collapse(phrasing or ""), meaning, fix, verify, " ".join(causes),
        measured_material, spec.ids_ref, str(note.note_version),
        # evidence numbers (counts etc.) are the gate's own, never invented
        " ".join(str(v) for v in _flatten_evidence_numbers(ev)),
    ])
    return RemediationItem(
        rule_id=note.rule_id.value, finding_code=finding.get("code", ""),
        outcome=outcome_str, ids_ref=spec.ids_ref, note_version=note.note_version,
        kind="rule", text=text, material=material,
    )


def _render_fallback_item(finding: dict, fb) -> RemediationItem:
    meaning = _collapse(fb.meaning or "")
    if fb.remediation_applies:
        guidance = _collapse(fb.guidance or "")
        lines = [f"[{fb.finding_code.value}] {meaning}",
                 f"    Guidance: {guidance}",
                 f"    — remediation guidance (generic fallback), catalog note "
                 f"v{fb.note_version}; consult the finding's rule for specifics"]
        kind = "fallback"
        material = " ".join([meaning, guidance, str(fb.note_version)])
    else:
        rationale = _collapse(fb.rationale or "")
        lines = [f"[{fb.finding_code.value}] {rationale}",
                 f"    — nothing in the submission is at fault here; no fix note "
                 f"is authored (catalog fallback v{fb.note_version})"]
        kind = "fallback_no_fix"
        material = " ".join([rationale, str(fb.note_version)])
    material += " " + " ".join(str(v) for v in _flatten_evidence_numbers(
        finding.get("evidence", {})))
    return RemediationItem(
        rule_id=None, finding_code=fb.finding_code.value,
        outcome=finding.get("evidence", {}).get("outcome"),
        ids_ref=None, note_version=fb.note_version, kind=kind,
        text="\n".join(lines), material=material,
    )


def _flatten_evidence_numbers(ev: Any) -> list:
    out: list = []
    if isinstance(ev, dict):
        for v in ev.values():
            out.extend(_flatten_evidence_numbers(v))
    elif isinstance(ev, list):
        for v in ev:
            out.extend(_flatten_evidence_numbers(v))
    elif isinstance(ev, (int, float)) and not isinstance(ev, bool):
        out.append(ev)
    elif isinstance(ev, str):
        out.extend(_NUM_RE.findall(ev))
    return out


def build_remediation_item(finding: dict,
                           catalog: Optional[RemediationCatalog] = None
                           ) -> RemediationItem:
    """Resolve one finding to its remediation: rule-level note first, code-level
    fallback only when no rule note applies (the resolution order the catalog's
    governance names)."""
    catalog = catalog or load_catalog()
    ev = finding.get("evidence", {})
    rid = ev.get("rule_id")
    if rid is not None:
        try:
            rule_id = RuleId(rid)
        except ValueError:
            rule_id = None
        if rule_id is not None:
            note = catalog.note_for_rule(rule_id)
            if note is not None:
                return _render_rule_item(finding, note, RULE_REGISTRY[rule_id])
    # fallback by finding code
    code = finding.get("code", "")
    try:
        fb = catalog.fallback_for_code(FindingCode(code))
    except ValueError:
        fb = None
    if fb is not None:
        return _render_fallback_item(finding, fb)
    return RemediationItem(
        rule_id=None, finding_code=code, outcome=ev.get("outcome"),
        ids_ref=None, note_version=0, kind="unknown",
        text=f"[{code}] no remediation note resolves for this finding.",
        material=code,
    )


def build_remediation_items(findings: list[dict],
                            catalog: Optional[RemediationCatalog] = None,
                            limit: Optional[int] = None) -> list[RemediationItem]:
    """Triage-ordered remediation for a certificate's findings (worst first)."""
    catalog = catalog or load_catalog()
    ordered = triage_findings(findings, catalog)
    if limit is not None:
        ordered = ordered[:limit]
    return [build_remediation_item(f, catalog) for f in ordered]


def render_remediation_body(findings: list[dict], *,
                            catalog: Optional[RemediationCatalog] = None,
                            limit: Optional[int] = None,
                            heading: str = "How to fix") -> str:
    """Deterministic remediation body (no register tag). Used in all tests and
    as the LLM path's fail-closed fallback."""
    catalog = catalog or load_catalog()
    items = build_remediation_items(findings, catalog, limit=limit)
    advisory = advisory_findings(findings, catalog)
    if not items:
        # CU2 — coherent with testimony: acknowledge advisory findings rather than
        # claim there is nothing to remediate opposite a reported problem.
        if advisory:
            return _render_advisory_only(advisory)
        return f"{heading}: nothing to remediate — no non-satisfied findings."
    n = len(items)
    header = (f"{heading} — {n} finding(s), worst first:"
              if limit is None else f"{heading} — top {n} finding(s):")
    blocks = [header, ""]
    for i, item in enumerate(items, 1):
        blocks.append(f"{i}. {item.text}")
        blocks.append("")
    body = "\n".join(blocks).rstrip()
    if advisory and limit is None:
        body += ("\n\n" + f"Plus {len(advisory)} advisory finding(s) "
                 "(no action required):")
        for f in advisory:
            body += f"\n  - {_advisory_meaning(f)}"
    return body
