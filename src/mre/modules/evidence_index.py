"""M9 — Evidence Index (L4).

Builds an in-memory index from JSONL run streams, then serves three primitives:
  entity_records(entity_id)    → all records mentioning that entity in subjects
  finding_occurrences(code)    → all Finding records with that code
  lineage_walk(entity_id)      → entity + transitive graph, ordered by pipeline stage

JSON persistence via save() / load().
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Optional

_MODULE_STAGE: dict[str, int] = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4,
    "M5": 5, "M6": 6, "M7": 7, "M9": 9, "M10": 10,
}


class EvidenceIndex:
    """L4 evidence index.  Read-only after build().  Thread-safe for reads."""

    def __init__(self) -> None:
        self._entity_records: dict[str, list[dict]] = {}   # entity_id → records
        self._finding_index: dict[str, list[dict]] = {}    # code → findings
        self._run_registry: dict[str, dict] = {}           # run_id → run meta
        self._all_evidence: list[dict] = []                # flat, deduped

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, runs_dir: Path) -> "EvidenceIndex":
        """Scan every *.jsonl in runs_dir and index records.  Resets prior state."""
        self._entity_records.clear()
        self._finding_index.clear()
        self._run_registry.clear()
        self._all_evidence.clear()
        seen_record_ids: set[str] = set()

        for jsonl_path in sorted(Path(runs_dir).glob("*.jsonl")):
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                rt = rec.get("record_type", "")

                if rt == "run_context_open":
                    run_id = rec.get("run_id", "")
                    self._run_registry.setdefault(run_id, {}).update({
                        "run_id": run_id,
                        "module": rec.get("module"),
                        "snapshot_id": rec.get("snapshot_id"),
                        "purpose": rec.get("purpose"),
                        "timestamp_open": rec.get("timestamp"),
                    })
                    continue

                if rt == "run_context_close":
                    run_id = rec.get("run_id", "")
                    self._run_registry.setdefault(run_id, {}).update({
                        "status": rec.get("status"),
                        "timestamp_close": rec.get("ended_at"),
                    })
                    continue

                # Evidence record
                rid = rec.get("record_id", "")
                if rid and rid not in seen_record_ids:
                    seen_record_ids.add(rid)
                    self._all_evidence.append(rec)

                for subject in rec.get("subjects", []):
                    eid = subject.get("entity_id", "")
                    if eid:
                        bucket = self._entity_records.setdefault(eid, [])
                        if not any(r.get("record_id") == rid for r in bucket):
                            bucket.append(rec)

                if rt == "finding":
                    code = rec.get("code", "")
                    if code:
                        bucket = self._finding_index.setdefault(code, [])
                        if not any(r.get("record_id") == rid for r in bucket):
                            bucket.append(rec)

        return self

    # ------------------------------------------------------------------
    # Query primitives
    # ------------------------------------------------------------------

    def entity_records(self, entity_id: str) -> list[dict]:
        """All evidence records (any type) whose subjects include entity_id."""
        return list(self._entity_records.get(entity_id, []))

    def finding_occurrences(self, code: str) -> list[dict]:
        """All Finding records with the given code."""
        return list(self._finding_index.get(code, []))

    def all_findings(self) -> list[dict]:
        return [r for r in self._all_evidence if r.get("record_type") == "finding"]

    def all_decisions(self) -> list[dict]:
        return [r for r in self._all_evidence if r.get("record_type") == "decision"]

    def runs(self) -> list[dict]:
        return list(self._run_registry.values())

    def lineage_walk(
        self,
        entity_id: str,
        snapshot_reader: Any = None,
    ) -> list[dict]:
        """All evidence records touching entity_id and its transitive dependents.

        For demand entities: also follows demand → fulfillment → workpackage →
        operations via the snapshot reader (if provided).

        Records are ordered by pipeline stage (M1 first) then by seq within stage.
        """
        entity_ids: set[str] = {entity_id}

        if snapshot_reader is not None:
            # Determine entity type by checking snapshot
            entity = snapshot_reader.get_entity(entity_id)
            if entity is not None:
                entity_type = self._infer_entity_type(entity_id, entity)
                if entity_type == "demand":
                    self._expand_demand_chain(entity_id, snapshot_reader, entity_ids)

        # Gather and deduplicate records for all entity IDs
        seen_rids: set[str] = set()
        records: list[dict] = []
        for eid in entity_ids:
            for rec in self._entity_records.get(eid, []):
                rid = rec.get("record_id", "")
                if rid not in seen_rids:
                    seen_rids.add(rid)
                    records.append(rec)

        records.sort(key=lambda r: (
            _MODULE_STAGE.get(r.get("module", ""), 99),
            r.get("seq", 0),
        ))
        return records

    def _infer_entity_type(self, entity_id: str, entity: dict) -> str:
        """Guess entity type from shape when no explicit type tag is stored."""
        if "demand_ref" in entity and "workpackage_ref" in entity:
            return "fulfillment"
        if "workpackage_ref" in entity and "spec_ref" in entity:
            return "operation"
        if "demand_ref" in entity and "workpackage_ref" not in entity:
            return "demand"
        # Check subjects of direct records for type hints
        for rec in self._entity_records.get(entity_id, [])[:3]:
            for s in rec.get("subjects", []):
                if s.get("entity_id") == entity_id and s.get("entity_type"):
                    return s["entity_type"]
        return "unknown"

    def _expand_demand_chain(
        self,
        demand_id: str,
        reader: Any,
        entity_ids: set[str],
    ) -> None:
        """Add fulfillment → workpackage → operation IDs to the set."""
        for ful in reader.iter_entities("fulfillment"):
            if ful.get("demand_ref") != demand_id:
                continue
            ful_id = ful.get("id", "")
            if ful_id:
                entity_ids.add(ful_id)
            wp_id = ful.get("workpackage_ref", "")
            if not wp_id:
                continue
            entity_ids.add(wp_id)
            for op in reader.iter_entities("operation"):
                if op.get("workpackage_ref") == wp_id:
                    op_id = op.get("id", "")
                    if op_id:
                        entity_ids.add(op_id)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "entity_records": self._entity_records,
                "finding_index": self._finding_index,
                "run_registry": self._run_registry,
            }, f, indent=None)

    @classmethod
    def load(cls, path: Path) -> "EvidenceIndex":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        idx = cls()
        idx._entity_records = data.get("entity_records", {})
        idx._finding_index = data.get("finding_index", {})
        idx._run_registry = data.get("run_registry", {})
        # Rebuild _all_evidence from entity_records (dedup by record_id)
        seen: set[str] = set()
        for recs in idx._entity_records.values():
            for r in recs:
                rid = r.get("record_id", "")
                if rid and rid not in seen:
                    seen.add(rid)
                    idx._all_evidence.append(r)
        return idx
