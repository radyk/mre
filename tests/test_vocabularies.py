"""Tests derived from docs/02 §4-5: controlled vocabulary membership and counts."""
import pytest

from mre.contracts.vocabularies import (
    DecisionBasis,
    DriverCode,
    FindingCode,
    FindingDisposition,
    FindingSeverity,
    ModuleCode,
    ProvenanceClass,
    RecordTier,
    RunStatus,
)

ADAPTER_FINDING_CODES = {
    "MISSING_REFERENCE",
    "UNMAPPABLE_VALUE",
    "AMBIGUOUS_SOURCE",
    "MALFORMED_FIELD",
    "DUPLICATE_IDENTITY",
    "IDENTITY_CHANGED",
}
VALIDATION_FINDING_CODES = {
    "TEMPORAL_IMPOSSIBILITY",
    "NO_CAPABLE_RESOURCE",
    "ORPHAN_ENTITY",
    "VALUE_OUT_OF_RANGE",
    "STATISTICAL_OUTLIER",
    "PROVENANCE_GAP",
    "LOW_CONFIDENCE_INPUT",
}
PLAN_SOLVE_FINDING_CODES = {
    "BATCH_CONFLICT",
    "INFEASIBLE_SUBSET",
    "HORIZON_EXCEEDED",
    "SOLVER_NONOPTIMAL",
}


class TestDriverCodes:
    def test_exactly_12(self):
        assert len(DriverCode) == 12

    def test_all_names_present(self):
        names = {d.value for d in DriverCode}
        expected = {
            "COST_TRADEOFF", "DUE_DATE_PRESSURE", "CAPACITY_BLOCKED",
            "CAPABILITY_LIMITED", "SETUP_AMORTIZATION", "SEQUENCE_DEPENDENCY",
            "CALENDAR_WINDOW", "FROZEN_COMMITMENT", "DATA_EXCLUSION",
            "POLICY_RULE", "SOLVER_LIMIT", "NO_ALTERNATIVE",
        }
        assert names == expected


class TestFindingCodes:
    def test_exactly_17(self):
        # spec says "~16" but the exhaustive list in docs/02 §4.3 enumerates
        # 6 adapter + 7 validation + 4 plan/solve = 17 codes
        assert len(FindingCode) == 17

    def test_adapter_layer_codes(self):
        values = {c.value for c in FindingCode}
        assert ADAPTER_FINDING_CODES <= values

    def test_validation_layer_codes(self):
        values = {c.value for c in FindingCode}
        assert VALIDATION_FINDING_CODES <= values

    def test_plan_solve_layer_codes(self):
        values = {c.value for c in FindingCode}
        assert PLAN_SOLVE_FINDING_CODES <= values

    def test_all_layers_account_for_all_codes(self):
        all_expected = ADAPTER_FINDING_CODES | VALIDATION_FINDING_CODES | PLAN_SOLVE_FINDING_CODES
        # 6 + 7 + 4 = 17 per the exhaustive enumeration in docs/02 §4.3
        assert len(all_expected) == 17


class TestProvenanceClass:
    def test_exactly_4(self):
        assert len(ProvenanceClass) == 4

    def test_values(self):
        values = {c.value for c in ProvenanceClass}
        assert values == {"observed", "derived", "defaulted", "synthesized"}


class TestDecisionBasis:
    def test_values(self):
        values = {b.value for b in DecisionBasis}
        assert values == {"observed", "reconstructed", "policy_applied"}


class TestRecordTier:
    def test_exactly_3(self):
        assert len(RecordTier) == 3

    def test_values(self):
        values = {t.value for t in RecordTier}
        assert values == {"headline", "supporting", "detail"}


class TestFindingSeverity:
    def test_4_levels(self):
        assert len(FindingSeverity) == 4

    def test_values(self):
        values = {s.value for s in FindingSeverity}
        assert values == {"blocker", "error", "warning", "info"}


class TestFindingDisposition:
    def test_exactly_5(self):
        assert len(FindingDisposition) == 5

    def test_values(self):
        values = {d.value for d in FindingDisposition}
        assert values == {
            "blocked", "excluded", "defaulted",
            "proceeded_flagged", "auto_corrected",
        }


class TestModuleCode:
    def test_m1_through_m10(self):
        values = {m.value for m in ModuleCode}
        for n in range(1, 11):
            assert f"M{n}" in values

    def test_exactly_10(self):
        assert len(ModuleCode) == 10


class TestRunStatus:
    def test_values(self):
        values = {s.value for s in RunStatus}
        assert values == {"success", "failure", "partial"}
