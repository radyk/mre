"""M10 — Explainer.

Strictly read-only: this module has no import of Reporter or SnapshotWriter.
It assembles ExplanationBundles from the evidence index and snapshot store,
then renders them via TemplateRenderer (all tests) or LLMRenderer (--llm flag).

Entry points:
  explainer.answer("Why is WO-2001 late?")         -> ExplanationBundle
  explainer.summarize_run()                          -> ExplanationBundle
  explainer.snapshot_diff("snap-v1", "snap-v2")     -> dict

Keyword routing (no NLU, no embeddings):
  "late"           + WO ref  -> _explain_why_late
  "on" / "assign"  + WO+M    -> _explain_why_on_machine
  "data problem" / "finding" -> _explain_data_problems
  "changed" / "diff"         -> _explain_what_changed (snapshot diff)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from mre.modules.evidence_index import EvidenceIndex


@dataclass
class ExplanationBundle:
    """Structured, renderer-agnostic answer to a question.

    ordered_records  — evidence records in pipeline order (M1 < M7)
    key_facts        — scalar summary used by renderers as the headline
    identity_map     — for resolving UUIDs to external names (WO-XXXX, M-GEAR-01)
    """
    question: str
    subject_id: str
    subject_type: str                        # "demand", "run", "diff", "findings"
    subject_external_name: str
    ordered_records: list[dict]
    key_facts: dict[str, Any]
    snapshot_id: str
    identity_map: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

class Explainer:
    """Read-only answer engine.  No write path."""

    def __init__(
        self,
        snapshot_store: Any,
        index: EvidenceIndex,
        snapshot_id: str = "snap-run",
    ) -> None:
        self._store = snapshot_store
        self._index = index
        self._snap_id = snapshot_id
        self._reader = snapshot_store.load_snapshot(snapshot_id)
        self._identity_map = self._reader.read_identity_map()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, question: str) -> ExplanationBundle:
        """Route a natural-language question to the right assembler."""
        q = question.lower()
        wo_match = re.search(r'WO-[\w-]+', question, re.IGNORECASE)
        m_match = re.search(r'M-[A-Z0-9-]+', question, re.IGNORECASE)

        if ("late" in q or "delay" in q or "tardy" in q) and wo_match:
            return self._explain_why_late(wo_match.group().upper())
        if ("on" in q or "assign" in q or "why" in q) and wo_match and m_match:
            return self._explain_why_on_machine(
                wo_match.group().upper(), m_match.group().upper()
            )
        if "data problem" in q or "finding" in q or "quality" in q:
            return self._explain_data_problems()
        if ("change" in q or "diff" in q or "since" in q or "update" in q):
            return self._explain_what_changed(question)
        if wo_match:
            return self._explain_why_late(wo_match.group().upper())
        return self._explain_data_problems()

    def summarize_run(self, run_id: Optional[str] = None) -> ExplanationBundle:
        """High-level run summary: notable decisions + findings + late demands."""
        if run_id is None:
            # Most recent M7 run
            m7_runs = [r for r in self._index.runs() if r.get("module") == "M7"]
            if m7_runs:
                run_id = sorted(
                    m7_runs, key=lambda r: r.get("timestamp_close", "")
                )[-1]["run_id"]
            else:
                run_id = "unknown"

        all_ev = self._index._all_evidence
        run_records = [r for r in all_ev if r.get("run_id") == run_id]

        notable_decisions = [
            r for r in run_records
            if r.get("record_type") == "decision"
            and r.get("driver") in ("SETUP_AMORTIZATION", "CALENDAR_WINDOW", "DEMAND_MERGE")
        ]
        affecting_findings = [
            r for r in run_records
            if r.get("record_type") == "finding"
            and r.get("disposition") in ("defaulted", "excluded", "blocked")
        ]
        late_metrics = [
            r for r in run_records
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]

        ordered = sorted(
            notable_decisions + affecting_findings + late_metrics,
            key=lambda r: (
                {"M1": 1, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "M7": 7}.get(
                    r.get("module", ""), 9
                ),
                r.get("seq", 0),
            ),
        )

        return ExplanationBundle(
            question="Run summary",
            subject_id=run_id,
            subject_type="run",
            subject_external_name=run_id[:12] if run_id else "?",
            ordered_records=ordered,
            key_facts={
                "run_id": run_id,
                "notable_decision_count": len(notable_decisions),
                "affecting_finding_count": len(affecting_findings),
                "late_demand_count": len(late_metrics),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def snapshot_diff(self, snap_id_a: str, snap_id_b: str) -> dict:
        """Entity-level diff between two snapshots.

        Returns:
          added_demands    — WO external refs present in b but not a
          removed_demands  — WO external refs present in a but not b
          changed_demands  — [{work_order, field, from, to}, ...]
          costmodel_diff   — {version_a, version_b, rate_changes: {name: {from, to}}}
        """
        reader_a = self._store.load_snapshot(snap_id_a)
        reader_b = self._store.load_snapshot(snap_id_b)
        im_a = reader_a.read_identity_map()
        im_b = reader_b.read_identity_map()

        def _wo_map(reader) -> dict[str, dict]:
            result: dict[str, dict] = {}
            for d in reader.iter_entities("demand"):
                wo = next(
                    (r.get("value") for r in d.get("external_refs", [])
                     if r.get("type") == "work_order"),
                    None,
                )
                if wo:
                    result[wo] = d
            return result

        demands_a = _wo_map(reader_a)
        demands_b = _wo_map(reader_b)

        added = sorted(set(demands_b) - set(demands_a))
        removed = sorted(set(demands_a) - set(demands_b))

        changed: list[dict] = []
        for wo in sorted(set(demands_a) & set(demands_b)):
            d_a = demands_a[wo]
            d_b = demands_b[wo]
            for fld in ("due", "quantity", "commitment_class"):
                v_a = d_a.get(fld)
                v_b = d_b.get(fld)
                if v_a != v_b:
                    changed.append({"work_order": wo, "field": fld, "from": v_a, "to": v_b})

        # CostModel version diff
        costmodel_diff: dict = {}
        cms_a = list(reader_a.iter_entities("costmodel"))
        cms_b = list(reader_b.iter_entities("costmodel"))
        if cms_a and cms_b:
            cm_a = cms_a[0]
            cm_b = cms_b[0]
            rates_a: dict[str, float] = cm_a.get("resource_rates", {})
            rates_b: dict[str, float] = cm_b.get("resource_rates", {})
            rate_changes: dict[str, dict] = {}
            all_ids = set(rates_a) | set(rates_b)
            for rid in all_ids:
                r_a = rates_a.get(rid)
                r_b = rates_b.get(rid)
                if r_a != r_b:
                    # Resolve canonical UUID to machine_id for readability
                    name = rid
                    if im_a:
                        refs = im_a.external_refs(rid)
                        mname = next((r.value for r in refs if r.type == "machine_id"), None)
                        if mname:
                            name = mname
                    rate_changes[name] = {"from": r_a, "to": r_b}
            costmodel_diff = {
                "version_a": cm_a.get("version"),
                "version_b": cm_b.get("version"),
                "rate_changes": rate_changes,
            }

        return {
            "snapshot_a": snap_id_a,
            "snapshot_b": snap_id_b,
            "added_demands": added,
            "removed_demands": removed,
            "changed_demands": changed,
            "costmodel_diff": costmodel_diff,
        }

    # ------------------------------------------------------------------
    # Private assemblers
    # ------------------------------------------------------------------

    def _explain_why_late(self, wo_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} late?", wo_ref, "demand")

        demand = self._reader.get_entity(demand_id) or {}
        due_date = demand.get("due", "unknown")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        lateness = None
        for rec in records:
            if rec.get("record_type") == "metric" and rec.get("name") == "lateness_minutes":
                if any(s.get("entity_id") == demand_id for s in rec.get("subjects", [])):
                    lateness = rec.get("value")
                    break

        return ExplanationBundle(
            question=f"Why is {wo_ref} late?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=records,
            key_facts={"lateness_minutes": lateness, "due_date": due_date},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_on_machine(self, wo_ref: str, machine_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} on {machine_ref}?", wo_ref, "demand")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        # Filter to assignment decisions only
        assignment_records = [
            r for r in records
            if r.get("record_type") == "decision" and r.get("decision_type") == "assignment"
        ]

        return ExplanationBundle(
            question=f"Why is {wo_ref} on {machine_ref}?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=assignment_records or records,
            key_facts={"machine_ref": machine_ref},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_data_problems(self) -> ExplanationBundle:
        findings = sorted(
            self._index.all_findings(),
            key=lambda r: (
                {"blocker": 0, "error": 1, "warning": 2, "info": 3}.get(
                    r.get("severity", "info"), 9
                ),
                r.get("seq", 0),
            ),
        )
        codes = sorted({r.get("code", "") for r in findings})
        return ExplanationBundle(
            question="What data problems exist?",
            subject_id=self._snap_id,
            subject_type="findings",
            subject_external_name=self._snap_id,
            ordered_records=findings,
            key_facts={
                "total_findings": len(findings),
                "codes": codes,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_what_changed(self, question: str) -> ExplanationBundle:
        snap_match = re.findall(r'snap[\w-]+', question, re.IGNORECASE)
        if len(snap_match) >= 2:
            snap_a, snap_b = snap_match[0], snap_match[1]
        elif len(snap_match) == 1:
            snap_a, snap_b = snap_match[0], self._snap_id
        else:
            snap_a, snap_b = self._snap_id, self._snap_id

        try:
            diff = self.snapshot_diff(snap_a, snap_b)
        except FileNotFoundError as exc:
            diff = {"error": str(exc)}

        return ExplanationBundle(
            question=question,
            subject_id=f"{snap_a}->{snap_b}",
            subject_type="diff",
            subject_external_name=f"{snap_a} -> {snap_b}",
            ordered_records=[],
            key_facts=diff,
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _resolve_wo(self, wo_ref: str) -> Optional[str]:
        if self._identity_map is None:
            return None
        return self._identity_map.resolve("ERP", "work_order", wo_ref)

    def _unknown(self, question: str, ref: str, entity_type: str) -> ExplanationBundle:
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type=entity_type,
            subject_external_name=ref,
            ordered_records=[],
            key_facts={"error": f"Unknown {entity_type}: {ref}"},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )
