"""Tests derived from docs/02 §3-4: evidence record shapes and the common envelope."""
import pytest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from mre.contracts.entities import EntityRef
from mre.contracts.records import (
    Artifact, Decision, DecisionAlternative, Event, Finding, Metric,
    RunContextClose, RunContextOpen,
)
from mre.contracts.vocabularies import (
    DecisionBasis, DecisionType, DriverCode, FindingCode, FindingDisposition,
    FindingSeverity, ModuleCode, RecordTier, RunStatus,
)

UTC = timezone.utc
NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
RUN_ID = "run-test-001"
SNAP_ID = "snap-test-001"


def _envelope(**overrides) -> dict:
    base = dict(
        record_id=str(uuid.uuid4()),
        run_id=RUN_ID,
        seq=1,
        module=ModuleCode.M1,
        timestamp=NOW,
        snapshot_id=SNAP_ID,
        subjects=[],
        tier=RecordTier.SUPPORTING,
        message="test",
    )
    return base | overrides


class TestCommonEnvelope:
    """Every evidence record carries all common envelope fields (docs/02 §3)."""

    def test_decision_has_all_envelope_fields(self):
        d = Decision(
            **_envelope(),
            decision_type=DecisionType.INTERPRETATION,
            chosen="option A",
            alternatives=[],
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
        )
        assert d.record_id is not None
        assert d.run_id == RUN_ID
        assert d.seq == 1
        assert d.module == ModuleCode.M1
        assert d.snapshot_id == SNAP_ID

    def test_finding_has_all_envelope_fields(self):
        f = Finding(
            **_envelope(),
            code=FindingCode.MISSING_REFERENCE,
            severity=FindingSeverity.ERROR,
            evidence={"ref": "R-001"},
            disposition=FindingDisposition.EXCLUDED,
        )
        assert f.record_id is not None
        assert f.snapshot_id == SNAP_ID

    def test_metric_has_all_envelope_fields(self):
        m = Metric(
            **_envelope(),
            name="total_cost", value=500.0, unit="USD",
        )
        assert m.record_id is not None

    def test_event_has_all_envelope_fields(self):
        e = Event(
            **_envelope(),
            status_text="solver started",
        )
        assert e.record_id is not None

    def test_artifact_has_all_envelope_fields(self):
        a = Artifact(
            **_envelope(),
            artifact_ref="file.csv",
            artifact_direction="input",
        )
        assert a.record_id is not None


class TestDecision:
    def test_basis_is_mandatory(self):
        with pytest.raises(ValidationError):
            Decision(
                **_envelope(),
                decision_type=DecisionType.INTERPRETATION,
                chosen="x",
                alternatives=[],
                driver=DriverCode.POLICY_RULE,
                # basis omitted
            )

    def test_driver_is_mandatory(self):
        with pytest.raises(ValidationError):
            Decision(
                **_envelope(),
                decision_type=DecisionType.INTERPRETATION,
                chosen="x",
                alternatives=[],
                # driver omitted
                basis=DecisionBasis.OBSERVED,
            )

    def test_invalid_driver_raises(self):
        with pytest.raises(ValidationError):
            Decision(
                **_envelope(),
                decision_type=DecisionType.INTERPRETATION,
                chosen="x",
                alternatives=[],
                driver="NOT_A_DRIVER_CODE",
                basis=DecisionBasis.OBSERVED,
            )

    def test_invalid_basis_raises(self):
        with pytest.raises(ValidationError):
            Decision(
                **_envelope(),
                decision_type=DecisionType.INTERPRETATION,
                chosen="x",
                alternatives=[],
                driver=DriverCode.POLICY_RULE,
                basis="invented_basis",
            )

    def test_alternatives_structure(self):
        alt = DecisionAlternative(option="exclude", consequence="demand dropped")
        d = Decision(
            **_envelope(),
            decision_type=DecisionType.INTERPRETATION,
            chosen="keep",
            alternatives=[alt],
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
        )
        assert d.alternatives[0].option == "exclude"

    def test_secondary_drivers_optional(self):
        d = Decision(
            **_envelope(),
            decision_type=DecisionType.ASSIGNMENT,
            chosen="CNC-1",
            alternatives=[],
            driver=DriverCode.CAPACITY_BLOCKED,
            secondary_drivers=[DriverCode.CALENDAR_WINDOW],
            basis=DecisionBasis.RECONSTRUCTED,
        )
        assert DriverCode.CALENDAR_WINDOW in d.secondary_drivers

    def test_record_type_is_decision(self):
        d = Decision(
            **_envelope(),
            decision_type=DecisionType.INTERPRETATION,
            chosen="x",
            alternatives=[],
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
        )
        assert d.record_type == "decision"


class TestFinding:
    def test_invalid_code_raises(self):
        with pytest.raises(ValidationError):
            Finding(
                **_envelope(),
                code="NOT_A_CODE",
                severity=FindingSeverity.ERROR,
                evidence={},
                disposition=FindingDisposition.EXCLUDED,
            )

    def test_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            Finding(
                **_envelope(),
                code=FindingCode.MISSING_REFERENCE,
                severity="super_critical",
                evidence={},
                disposition=FindingDisposition.EXCLUDED,
            )

    def test_disposition_detail_optional(self):
        f = Finding(
            **_envelope(),
            code=FindingCode.VALUE_OUT_OF_RANGE,
            severity=FindingSeverity.WARNING,
            evidence={"actual": 0, "expected": "> 0"},
            disposition=FindingDisposition.DEFAULTED,
        )
        assert f.disposition_detail is None

    def test_record_type_is_finding(self):
        f = Finding(
            **_envelope(),
            code=FindingCode.MISSING_REFERENCE,
            severity=FindingSeverity.ERROR,
            evidence={},
            disposition=FindingDisposition.EXCLUDED,
        )
        assert f.record_type == "finding"


class TestMetric:
    def test_rollup_of_is_list_of_record_ids(self):
        m = Metric(
            **_envelope(),
            name="total_cost",
            value=100.0,
            unit="USD",
            rollup_of=["rec-1", "rec-2"],
        )
        assert m.rollup_of == ["rec-1", "rec-2"]

    def test_rollup_of_optional(self):
        m = Metric(**_envelope(), name="cost_a", value=30.0, unit="USD")
        assert m.rollup_of is None

    def test_record_type_is_metric(self):
        m = Metric(**_envelope(), name="x", value=1.0, unit="units")
        assert m.record_type == "metric"


class TestEvent:
    def test_payload_optional(self):
        e = Event(**_envelope(), status_text="done")
        assert e.payload == {}

    def test_record_type_is_event(self):
        e = Event(**_envelope(), status_text="done")
        assert e.record_type == "event"


class TestArtifact:
    def test_artifact_direction_input(self):
        a = Artifact(
            **_envelope(),
            artifact_ref="file.csv",
            artifact_direction="input",
        )
        assert a.artifact_direction == "input"

    def test_artifact_direction_output(self):
        a = Artifact(
            **_envelope(),
            artifact_ref="out.json",
            artifact_direction="output",
            producing_run_id=RUN_ID,
        )
        assert a.artifact_direction == "output"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValidationError):
            Artifact(
                **_envelope(),
                artifact_ref="x",
                artifact_direction="sideways",
            )

    def test_record_type_is_artifact(self):
        a = Artifact(**_envelope(), artifact_ref="x", artifact_direction="input")
        assert a.record_type == "artifact"


class TestRunContext:
    def test_run_context_open_fields(self):
        rc = RunContextOpen(
            run_id=RUN_ID,
            module=ModuleCode.M1,
            snapshot_id=SNAP_ID,
            purpose="test",
            trigger="harness",
            config_hash="abc",
            started_at=NOW,
        )
        assert rc.run_id == RUN_ID
        assert rc.record_type == "run_context_open"

    def test_run_context_close_fields(self):
        rc = RunContextClose(
            run_id=RUN_ID,
            module=ModuleCode.M1,
            status=RunStatus.SUCCESS,
            ended_at=NOW,
            duration_seconds=1.23,
        )
        assert rc.status == RunStatus.SUCCESS
        assert rc.record_type == "run_context_close"
        assert rc.exception_info is None
