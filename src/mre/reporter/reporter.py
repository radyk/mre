"""Reporter — the object all modules touch (L2).

Eight verbs. Ambient capture (run_id, seq, timestamps, config hash,
parent-run linkage, exception capture) is entirely the Reporter's job.
Schema validation happens at every verb call — malformed records die here.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.entities import EntityRef
from mre.contracts.records import (
    Artifact,
    Decision,
    DecisionAlternative,
    Event,
    Finding,
    InputManifestEntry,
    Metric,
    OutputManifestEntry,
    RunContextClose,
    RunContextOpen,
)
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
from mre.reporter.consolidate import Consolidator
from mre.reporter.sink import JsonlSink

UTC = timezone.utc


class Reporter:
    """The cross-cutting reporter library.

    Obtain via Reporter.begin(). Use as a context manager for automatic
    end() and exception capture.
    """

    def __init__(
        self,
        run_id: str,
        module: ModuleCode,
        snapshot_id: str,
        sink: JsonlSink,
        started_at: datetime,
        config_hash: str,
        purpose: str,
        trigger: str,
        parent_run_id: Optional[str],
        config_snapshot: dict[str, Any],
    ) -> None:
        self.run_id = run_id
        self.module = module
        self.snapshot_id = snapshot_id
        self._sink = sink
        self._seq = 0
        self.started_at = started_at
        self.config_hash = config_hash
        self._purpose = purpose
        self._trigger = trigger
        self._parent_run_id = parent_run_id
        self._config_snapshot = config_snapshot
        self._input_manifest: list[InputManifestEntry] = []
        self._output_manifest: list[OutputManifestEntry] = []
        self.ended_at: Optional[datetime] = None
        self.run_status: Optional[RunStatus] = None
        self.exception_info: Optional[dict[str, str]] = None
        self.consolidated_doc: Optional[dict] = None

    # ------------------------------------------------------------------
    # Verb 1: begin (classmethod — mints the Reporter)
    # ------------------------------------------------------------------

    @classmethod
    def begin(
        cls,
        module: ModuleCode,
        purpose: str,
        config: dict[str, Any],
        trigger: str,
        snapshot_id: str,
        parent_run_id: Optional[str] = None,
        sink_dir: Optional[Path | str] = None,
    ) -> Reporter:
        if sink_dir is None:
            sink_dir = Path("runs")
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        config_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True, default=str).encode()
        ).hexdigest()
        sink = JsonlSink(run_id=run_id, directory=Path(sink_dir))
        reporter = cls(
            run_id=run_id,
            module=module,
            snapshot_id=snapshot_id,
            sink=sink,
            started_at=started_at,
            config_hash=config_hash,
            purpose=purpose,
            trigger=trigger,
            parent_run_id=parent_run_id,
            config_snapshot=config,
        )
        open_rec = RunContextOpen(
            run_id=run_id,
            module=module,
            snapshot_id=snapshot_id,
            purpose=purpose,
            trigger=trigger,
            parent_run_id=parent_run_id,
            config_snapshot=config,
            config_hash=config_hash,
            started_at=started_at,
        )
        sink.write(open_rec)
        return reporter

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _now(self) -> datetime:
        return datetime.now(UTC)

    # ------------------------------------------------------------------
    # Verb 2: register_input
    # ------------------------------------------------------------------

    def register_input(
        self,
        artifact_id: str,
        artifact_hash: Optional[str] = None,
        profile: Optional[dict[str, Any]] = None,
    ) -> None:
        entry = InputManifestEntry(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            profile=profile or {},
        )
        self._input_manifest.append(entry)
        record = Artifact(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=[],
            tier=RecordTier.SUPPORTING,
            message=f"Input registered: {artifact_id}",
            artifact_ref=artifact_id,
            artifact_hash=artifact_hash,
            artifact_direction="input",
            producing_run_id=None,
            consuming_run_ids=[self.run_id],
        )
        self._sink.write(record)

    # ------------------------------------------------------------------
    # Verb 3: record_decision
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_type: DecisionType,
        subjects: list[EntityRef],
        chosen: Any,
        alternatives: list[DecisionAlternative],
        driver: DriverCode,
        basis: DecisionBasis,
        policy_ref: Optional[str] = None,
        secondary_drivers: Optional[list[DriverCode]] = None,
        tier: RecordTier = RecordTier.SUPPORTING,
        message: str = "",
        authority: Optional[str] = None,
    ) -> Decision:
        record = Decision(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=subjects,
            tier=tier,
            message=message,
            decision_type=decision_type,
            chosen=chosen,
            alternatives=alternatives,
            driver=driver,
            secondary_drivers=secondary_drivers or [],
            basis=basis,
            policy_ref=policy_ref,
            authority=authority,
        )
        self._sink.write(record)
        return record

    # ------------------------------------------------------------------
    # Verb 4: record_finding
    # ------------------------------------------------------------------

    def record_finding(
        self,
        code: FindingCode,
        severity: FindingSeverity,
        subjects: list[EntityRef],
        evidence: dict[str, Any],
        disposition: FindingDisposition,
        disposition_detail: Optional[str] = None,
        tier: RecordTier = RecordTier.SUPPORTING,
        message: str = "",
    ) -> Finding:
        record = Finding(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=subjects,
            tier=tier,
            message=message,
            code=code,
            severity=severity,
            evidence=evidence,
            disposition=disposition,
            disposition_detail=disposition_detail,
        )
        self._sink.write(record)
        return record

    # ------------------------------------------------------------------
    # Verb 5: record_metric
    # ------------------------------------------------------------------

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str,
        subjects: Optional[list[EntityRef]] = None,
        rollup_of: Optional[list[str]] = None,
        tier: RecordTier = RecordTier.SUPPORTING,
        message: str = "",
    ) -> Metric:
        record = Metric(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=subjects or [],
            tier=tier,
            message=message,
            name=name,
            value=value,
            unit=unit,
            rollup_of=rollup_of,
        )
        self._sink.write(record)
        return record

    # ------------------------------------------------------------------
    # Verb 6: record_event
    # ------------------------------------------------------------------

    def record_event(
        self,
        status_text: str,
        payload: Optional[dict[str, Any]] = None,
        tier: RecordTier = RecordTier.DETAIL,
        message: str = "",
    ) -> Event:
        record = Event(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=[],
            tier=tier,
            message=message or status_text,
            status_text=status_text,
            payload=payload or {},
        )
        self._sink.write(record)
        return record

    # ------------------------------------------------------------------
    # Verb 7: register_output
    # ------------------------------------------------------------------

    def register_output(
        self,
        artifact_ref: str,
        artifact_hash: Optional[str] = None,
    ) -> None:
        entry = OutputManifestEntry(
            artifact_id=artifact_ref,
            artifact_hash=artifact_hash,
        )
        self._output_manifest.append(entry)
        record = Artifact(
            record_id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._next_seq(),
            module=self.module,
            timestamp=self._now(),
            snapshot_id=self.snapshot_id,
            subjects=[],
            tier=RecordTier.SUPPORTING,
            message=f"Output registered: {artifact_ref}",
            artifact_ref=artifact_ref,
            artifact_hash=artifact_hash,
            artifact_direction="output",
            producing_run_id=self.run_id,
            consuming_run_ids=[],
        )
        self._sink.write(record)

    # ------------------------------------------------------------------
    # Utility: severity counts (used by validator go/no-go gate)
    # ------------------------------------------------------------------

    def get_finding_counts(self) -> dict[str, int]:
        """Count findings by severity across all records written to this run's sink."""
        counts: dict[str, int] = {}
        for rec in self._sink.read_all():
            if rec.get("record_type") == "finding":
                sev = rec.get("severity", "unknown")
                counts[sev] = counts.get(sev, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Verb 8: end (or auto via context manager)
    # ------------------------------------------------------------------

    def end(self, status: RunStatus) -> None:
        self.ended_at = self._now()
        self.run_status = status
        duration = (self.ended_at - self.started_at).total_seconds()
        close_rec = RunContextClose(
            run_id=self.run_id,
            module=self.module,
            status=status,
            ended_at=self.ended_at,
            duration_seconds=duration,
            exception_info=self.exception_info,
            input_manifest=self._input_manifest,
            output_manifest=self._output_manifest,
        )
        self._sink.write(close_rec)
        consolidator = Consolidator(run_id=self.run_id, sink=self._sink)
        self.consolidated_doc = consolidator.consolidate()
        self._sink.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Reporter:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            self.exception_info = {
                "type": exc_type.__name__,
                "message": str(exc_val),
            }
        status = RunStatus.SUCCESS if exc_type is None else RunStatus.FAILURE
        self.end(status)
        return False
