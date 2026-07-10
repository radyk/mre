"""Remediation catalog completeness + jurisdiction lint (handoff §1, §2).

Every test parametrizes over the registry / vocabulary data — never a
hand-maintained list — so a rule added to the registry or a code added to the
vocabulary without its catalog note fails CI by construction. The catalog is
FROZEN authored knowledge; these tests guard it against drift from the code
side, they do not license editing its prose.
"""
from __future__ import annotations

import re

import pytest

from mre.catalog import load_catalog
from mre.contracts.ids_rules import (
    RULE_REGISTRY, RuleCategory, RuleId, RuleOutcome, _ALLOWED_OUTCOMES,
)
from mre.contracts.vocabularies import FindingCode

CATALOG = load_catalog()

# §-references that resolve: any "§N" / "§N.N" heading present in docs/06, plus
# the eight §2 required filenames. Built once from the spec text so the lint
# tracks the document, not a frozen copy of it.
import pathlib

_DOCS06 = (pathlib.Path(__file__).resolve().parents[1] / "docs"
           / "06-incoming-data-spec.md").read_text(encoding="utf-8")
_SECTION_REFS = set(re.findall(r"§\d+(?:\.\d+)*", _DOCS06))
_REQUIRED_FILENAMES = {
    "manifest.json", "orders.csv", "routings.csv", "routing_lines.csv",
    "products.csv", "resources.csv", "calendars.csv", "cost_model.json",
    "setup_transitions.csv", "customers.csv", "locks.csv", "wip_status.csv",
}


# --------------------------------------------------------------------------
# §1 — completeness (parametrized over registry / vocabulary)
# --------------------------------------------------------------------------

class TestRuleNoteCompleteness:
    @pytest.mark.parametrize("rule_id", list(RuleId))
    def test_every_rule_has_exactly_one_note(self, rule_id):
        note = CATALOG.note_for_rule(rule_id)
        assert note is not None, f"no rule-level note for {rule_id.value}"
        assert note.rule_id == rule_id

    def test_note_count_equals_registry(self):
        assert len(CATALOG.rules) == len(RULE_REGISTRY) == 32

    def test_no_orphan_rule_notes(self):
        registry_ids = set(RULE_REGISTRY)
        for rid in CATALOG.rules:
            assert rid in registry_ids, f"note {rid.value} names no registry rule"

    @pytest.mark.parametrize("rule_id", list(RuleId))
    def test_phrasing_within_category_range(self, rule_id):
        """A quality note with a `degraded` phrasing is a construction error:
        outcome_phrasing keys ⊆ the outcomes the rule's category permits."""
        note = CATALOG.note_for_rule(rule_id)
        spec = RULE_REGISTRY[rule_id]
        allowed = _ALLOWED_OUTCOMES[spec.category] - {RuleOutcome.SATISFIED}
        assert set(note.outcome_phrasing) <= allowed, (
            f"{rule_id.value} ({spec.category.value}) phrases "
            f"{sorted(o.value for o in set(note.outcome_phrasing) - allowed)}")

    @pytest.mark.parametrize("rule_id", [
        rid for rid, spec in RULE_REGISTRY.items()
        if spec.category == RuleCategory.BANDED
    ])
    def test_banded_notes_carry_measures_and_thresholds(self, rule_id):
        """Banded notes carry a `measures` matching the registry row and a
        thresholds_ref (the registry's coarse "App A" and the note's Appendix-A
        anchor both point at the same band; equality of the anchor *name* is
        not required, presence + a matching measure is)."""
        note = CATALOG.note_for_rule(rule_id)
        spec = RULE_REGISTRY[rule_id]
        assert note.measures == spec.measures, (
            f"{rule_id.value}: note measures {note.measures!r} != registry "
            f"{spec.measures!r}")
        assert note.thresholds_ref, f"{rule_id.value}: banded note lacks thresholds_ref"
        assert spec.thresholds_ref, f"{rule_id.value}: banded registry row lacks thresholds_ref"


class TestFallbackCompleteness:
    @pytest.mark.parametrize("code", list(FindingCode))
    def test_every_finding_code_has_exactly_one_fallback(self, code):
        note = CATALOG.fallback_for_code(code)
        assert note is not None, f"no fallback note for {code.value}"
        assert note.finding_code == code

    def test_fallback_count_is_eighteen(self):
        assert len(CATALOG.fallbacks) == len(FindingCode) == 18


# --------------------------------------------------------------------------
# §2 — jurisdiction lint (positive half is automatable; negative half is
# review policy, not regex, per the handoff)
# --------------------------------------------------------------------------

# DESIGN-THREAD DEFECT (reported 2026-07-10, not fixed here): two frozen
# quality-rule notes carry a fix_looks_like with no resolvable IDS cite. Fixing
# them is a prose edit that bumps note_version — design-thread work, off-limits
# to this implement session (handoff §0). They are quarantined here so the lint
# stays real for the other 30 rules and the gap cannot silently grow; a
# separate test pins the set so a later catalog fix trips the guard.
_KNOWN_UNCITED_FIX = {
    RuleId.DECISION_RELEVANT_ATTRIBUTES_POPULATED,
    RuleId.OPTIONAL_COLUMNS_ARE_NOT_SPARSE,
}


def _fix_cite_hits(text: str) -> bool:
    section_hits = {s for s in re.findall(r"§\d+(?:\.\d+)*", text) if s in _SECTION_REFS}
    file_hits = {f for f in _REQUIRED_FILENAMES if f in text}
    return bool(section_hits or file_hits)


class TestJurisdictionLint:
    @pytest.mark.parametrize("rule_id", [r for r in RuleId if r not in _KNOWN_UNCITED_FIX])
    def test_fix_looks_like_carries_resolvable_ids_cite(self, rule_id):
        """Every rule-level fix_looks_like must contain ≥1 IDS citation that
        resolves — a §-reference present in docs/06 or a §2 filename."""
        note = CATALOG.note_for_rule(rule_id)
        assert _fix_cite_hits(note.fix_looks_like), (
            f"{rule_id.value}: fix_looks_like carries no resolvable IDS cite\n"
            f"  text: {note.fix_looks_like!r}")

    def test_quarantine_is_exactly_the_known_two(self):
        """Pin the uncited set: if a design-thread revision adds a cite to one
        of these (or a new note regresses), this guard fires and the quarantine
        must be re-derived — the gap is never allowed to drift silently."""
        actually_uncited = {
            rid for rid in RuleId
            if not _fix_cite_hits(CATALOG.note_for_rule(rid).fix_looks_like)
        }
        assert actually_uncited == _KNOWN_UNCITED_FIX, (
            f"uncited fix_looks_like set changed: {sorted(r.value for r in actually_uncited)}")

    @pytest.mark.parametrize("code", [
        c for c in FindingCode
        if not load_catalog().fallbacks[c].remediation_applies
    ])
    def test_non_applicable_fallbacks_are_structurally_exempt(self, code):
        """Fallbacks with remediation_applies: false carry no fix_looks_like at
        all (structural exemption), and a rationale instead."""
        note = CATALOG.fallback_for_code(code)
        assert note.fix_looks_like is None
        assert note.rationale, f"{code.value}: non-applicable fallback lacks a rationale"
