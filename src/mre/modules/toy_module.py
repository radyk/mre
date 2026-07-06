"""Phase 0 deliverable: toy module.

Begins a run, emits one of each evidence record type, ends, and returns
the valid consolidated run document. No real manufacturing logic — this
module exists solely to verify the evidence backbone end-to-end.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from mre.contracts.vocabularies import (
    DecisionBasis,
    DecisionType,
    DriverCode,
    FindingCode,
    FindingDisposition,
    FindingSeverity,
    ModuleCode,
    RecordTier,
    RunStatus,
)
from mre.contracts.records import DecisionAlternative
from mre.reporter import Reporter


def run_toy_module(
    snapshot_id: str = "snap-phase0-demo",
    sink_dir: Optional[Path | str] = None,
) -> dict:
    """Run the toy module and return the consolidated run document."""
    reporter = Reporter.begin(
        module=ModuleCode.M1,
        purpose="Phase 0 evidence-backbone smoke test",
        config={"phase": 0, "toy": True},
        trigger="test_harness",
        snapshot_id=snapshot_id,
        sink_dir=sink_dir,
    )

    # Artifact (input)
    reporter.register_input(
        artifact_id="extract-2026-01-01.csv",
        artifact_hash="abc123",
        profile={"row_count": 42, "date_range": "2026-01-01/2026-03-31"},
    )

    # Event
    reporter.record_event(
        status_text="toy module started",
        payload={"phase": 0},
        tier=RecordTier.DETAIL,
    )

    # Finding
    reporter.record_finding(
        code=FindingCode.VALUE_OUT_OF_RANGE,
        severity=FindingSeverity.WARNING,
        subjects=[],
        evidence={"field": "customer_weight", "expected": "> 0", "actual": 0},
        disposition=FindingDisposition.DEFAULTED,
        disposition_detail="default_customer_weight_1.0",
        tier=RecordTier.SUPPORTING,
        message="customer_weight was zero; defaulted to 1.0",
    )

    # Decision
    reporter.record_decision(
        decision_type=DecisionType.INTERPRETATION,
        subjects=[],
        chosen={"interpretation": "treat zero weight as default 1.0"},
        alternatives=[
            DecisionAlternative(
                option="exclude demand",
                consequence="demand dropped from schedule",
            )
        ],
        driver=DriverCode.POLICY_RULE,
        basis=DecisionBasis.POLICY_APPLIED,
        policy_ref="default_weight_policy_v1",
        tier=RecordTier.SUPPORTING,
        message="zero customer_weight interpreted as 1.0 per policy",
    )

    # Metrics with decomposability
    m_a = reporter.record_metric(
        name="demand_count_open",
        value=30.0,
        unit="demands",
        tier=RecordTier.HEADLINE,
        message="open demands in snapshot",
    )
    m_b = reporter.record_metric(
        name="demand_count_cancelled",
        value=12.0,
        unit="demands",
        tier=RecordTier.SUPPORTING,
        message="cancelled demands in snapshot",
    )
    reporter.record_metric(
        name="demand_count_total",
        value=42.0,
        unit="demands",
        rollup_of=[m_a.record_id, m_b.record_id],
        tier=RecordTier.HEADLINE,
        message="total demands in snapshot (open + cancelled)",
    )

    # Artifact (output)
    reporter.register_output(
        artifact_ref="phase0-run-summary.json",
        artifact_hash="def456",
    )

    reporter.end(RunStatus.SUCCESS)
    return reporter.consolidated_doc
