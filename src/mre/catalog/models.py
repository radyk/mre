"""Typed models for the frozen remediation catalog (handoff §1).

The catalog (``remediation-catalog-v1.yaml``) is FROZEN authored knowledge:
notes are written in the design thread, rendered per-case, never improvised at
answer time. This module loads that YAML into validation-at-construction
Pydantic models so a malformed or drifted catalog dies at import, not at the
moment a user asks "how do I fix it?".

Two note kinds:
- ``RemediationNote`` keyed by ``RuleId`` — one per registry rule. Carries the
  authored fix guidance and the per-outcome band phrasing the renderer keys on.
- ``FallbackNote`` keyed by ``FindingCode`` — one per finding code, used only
  when a finding resolves to no rule-level note. Fallbacks with
  ``remediation_applies: false`` are structurally exempt from fix guidance
  (the out-with-rationale honesty pattern): they carry a ``rationale``, never a
  ``fix_looks_like``.

Nothing here defines a canonical record shape; these are the typed shape of the
authored catalog, so they live in their own package rather than in contracts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, model_validator

from mre.contracts.ids_rules import (
    RULE_REGISTRY, RuleCategory, RuleId, RuleOutcome, _ALLOWED_OUTCOMES,
)
from mre.contracts.vocabularies import FindingCode

_CATALOG_PATH = Path(__file__).parent / "remediation-catalog-v1.yaml"

# Outcomes a note may phrase: every category-permitted outcome except SATISFIED
# (a satisfied rule emits no finding, so it has no remediation phrasing).
_PHRASEABLE: dict[RuleCategory, frozenset[RuleOutcome]] = {
    cat: frozenset(outs - {RuleOutcome.SATISFIED})
    for cat, outs in _ALLOWED_OUTCOMES.items()
}


class RemediationNote(BaseModel):
    """One rule-level note (authored, per-outcome phrasing keyed to the rule)."""
    rule_id: RuleId
    meaning: str
    typical_causes: list[str]
    fix_looks_like: str
    verify: str
    outcome_phrasing: dict[RuleOutcome, str]
    note_version: int
    measures: Optional[str] = None
    thresholds_ref: Optional[str] = None

    @model_validator(mode="after")
    def _phrasing_in_category_range(self) -> "RemediationNote":
        spec = RULE_REGISTRY[self.rule_id]
        allowed = _PHRASEABLE[spec.category]
        stray = set(self.outcome_phrasing) - allowed
        if stray:
            raise ValueError(
                f"note {self.rule_id.value} ({spec.category.value}) has "
                f"outcome_phrasing for outcomes it cannot produce: "
                f"{sorted(o.value for o in stray)}")
        return self

    def phrasing_for(self, outcome: RuleOutcome) -> Optional[str]:
        return self.outcome_phrasing.get(outcome)


class FallbackNote(BaseModel):
    """One code-level fallback note (used when no rule-level note resolves)."""
    finding_code: FindingCode
    remediation_applies: bool
    note_version: int
    meaning: Optional[str] = None
    guidance: Optional[str] = None
    rationale: Optional[str] = None
    # Fallbacks never coach a specific fix — asserted structurally.
    fix_looks_like: Optional[str] = None

    @model_validator(mode="after")
    def _shape_matches_applicability(self) -> "FallbackNote":
        if self.fix_looks_like is not None:
            raise ValueError(
                f"fallback {self.finding_code.value} must not carry "
                f"fix_looks_like (fallbacks coach generically at most)")
        if not self.remediation_applies and self.rationale is None:
            raise ValueError(
                f"non-applicable fallback {self.finding_code.value} must carry "
                f"a rationale (out-with-rationale honesty pattern)")
        return self


class RemediationCatalog(BaseModel):
    """The whole frozen catalog, indexed for O(1) lookup by rule / code."""
    catalog_version: int
    reviewed: str
    rules: dict[RuleId, RemediationNote]
    fallbacks: dict[FindingCode, FallbackNote]

    def note_for_rule(self, rule_id: RuleId) -> Optional[RemediationNote]:
        return self.rules.get(rule_id)

    def fallback_for_code(self, code: FindingCode) -> Optional[FallbackNote]:
        return self.fallbacks.get(code)


def _load_from_path(path: Path) -> RemediationCatalog:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules: dict[RuleId, RemediationNote] = {}
    for row in data.get("rules", []):
        note = RemediationNote.model_validate(row)
        if note.rule_id in rules:
            raise ValueError(f"duplicate rule-level note for {note.rule_id.value}")
        rules[note.rule_id] = note
    fallbacks: dict[FindingCode, FallbackNote] = {}
    for row in data.get("fallbacks", []):
        note = FallbackNote.model_validate(row)
        if note.finding_code in fallbacks:
            raise ValueError(f"duplicate fallback note for {note.finding_code.value}")
        fallbacks[note.finding_code] = note
    return RemediationCatalog(
        catalog_version=data["catalog_version"],
        reviewed=str(data["reviewed"]),
        rules=rules,
        fallbacks=fallbacks,
    )


_CACHED: Optional[RemediationCatalog] = None


def load_catalog() -> RemediationCatalog:
    """Load (and cache) the frozen v1 catalog from the packaged YAML."""
    global _CACHED
    if _CACHED is None:
        _CACHED = _load_from_path(_CATALOG_PATH)
    return _CACHED
