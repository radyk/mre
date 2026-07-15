"""Evidence record types for the manufacturing reasoning engine.

All modules emit into the evidence store through these shapes.
Common envelope fields (docs/02 §3) appear on every record.
Nothing defines record shapes outside src/mre/contracts/.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

from mre.contracts.entities import EntityRef
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


# ---------------------------------------------------------------------------
# Sub-structures for record payloads
# ---------------------------------------------------------------------------


class DecisionAlternative(BaseModel):
    """One rejected option and its consequence."""
    option: str
    consequence: str


class InputManifestEntry(BaseModel):
    """One input artifact/snapshot registered with the run."""
    artifact_id: str
    artifact_hash: Optional[str] = None
    profile: dict[str, Any] = {}


class OutputManifestEntry(BaseModel):
    """One output artifact registered with the run."""
    artifact_id: str
    artifact_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# RunContext open / close (written by Reporter.begin / .end)
# ---------------------------------------------------------------------------


class RunContextOpen(BaseModel):
    """Written at Reporter.begin(). Identity + config; no outcome yet."""
    record_type: Literal["run_context_open"] = "run_context_open"
    run_id: str
    module: ModuleCode
    snapshot_id: str
    purpose: str
    trigger: str
    parent_run_id: Optional[str] = None
    config_snapshot: dict[str, Any] = {}
    config_hash: str
    started_at: datetime


class RunContextClose(BaseModel):
    """Written at Reporter.end(). Outcome, timing, manifests."""
    record_type: Literal["run_context_close"] = "run_context_close"
    run_id: str
    module: ModuleCode
    status: RunStatus
    ended_at: datetime
    duration_seconds: float
    exception_info: Optional[dict[str, str]] = None
    input_manifest: list[InputManifestEntry] = []
    output_manifest: list[OutputManifestEntry] = []
    solver_telemetry: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Evidence records — all carry the common envelope (docs/02 §3)
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    """A choice made by any module: interpretation, merge, assignment, simplification.

    basis is mandatory (the honesty flag).
    driver is mandatory and exactly one primary code.
    Solution-extraction assignments are always basis=reconstructed.
    """
    record_type: Literal["decision"] = "decision"
    record_id: str
    run_id: str
    seq: int
    module: ModuleCode
    timestamp: datetime
    snapshot_id: str
    subjects: list[EntityRef]
    tier: RecordTier
    message: str
    decision_type: DecisionType
    chosen: Any
    alternatives: list[DecisionAlternative] = []
    driver: DriverCode
    secondary_drivers: list[DriverCode] = []
    basis: DecisionBasis
    policy_ref: Optional[str] = None
    # WHO authored this decision (docs/02 §4.2, Phase 3 planner-edit addition).
    # None for machine-authored decisions (adapter/planner/solver reconstruction);
    # MANDATORY for a ``planner_edit`` — an accepted cockpit edit is a human act
    # and must name its authority. A dev identity token now; real auth post-pilot.
    authority: Optional[str] = None


class Finding(BaseModel):
    """Data quality or feasibility issue found by any pipeline stage.

    disposition records what the system actually did in response.
    code + subjects + snapshot_id enables cross-run trend queries.
    """
    record_type: Literal["finding"] = "finding"
    record_id: str
    run_id: str
    seq: int
    module: ModuleCode
    timestamp: datetime
    snapshot_id: str
    subjects: list[EntityRef]
    tier: RecordTier
    message: str
    code: FindingCode
    severity: FindingSeverity
    evidence: dict[str, Any]
    disposition: FindingDisposition
    disposition_detail: Optional[str] = None


class Metric(BaseModel):
    """A reported number. rollup_of ties totals to their components.

    Decomposability: if rollup_of is non-empty, value must equal the sum of
    the referenced Metric records' values. The consolidator enforces this.
    """
    record_type: Literal["metric"] = "metric"
    record_id: str
    run_id: str
    seq: int
    module: ModuleCode
    timestamp: datetime
    snapshot_id: str
    subjects: list[EntityRef]
    tier: RecordTier
    message: str
    name: str
    value: float
    unit: str
    rollup_of: Optional[list[str]] = None


class Event(BaseModel):
    """Progress and status signal. Long solves stream improving solutions here."""
    record_type: Literal["event"] = "event"
    record_id: str
    run_id: str
    seq: int
    module: ModuleCode
    timestamp: datetime
    snapshot_id: str
    subjects: list[EntityRef]
    tier: RecordTier
    message: str
    status_text: str
    payload: dict[str, Any] = {}


class Artifact(BaseModel):
    """Registered input or output artifact. Lineage for cross-run identity."""
    record_type: Literal["artifact"] = "artifact"
    record_id: str
    run_id: str
    seq: int
    module: ModuleCode
    timestamp: datetime
    snapshot_id: str
    subjects: list[EntityRef]
    tier: RecordTier
    message: str
    artifact_ref: str
    artifact_hash: Optional[str] = None
    artifact_direction: Literal["input", "output"]
    producing_run_id: Optional[str] = None
    consuming_run_ids: list[str] = []
