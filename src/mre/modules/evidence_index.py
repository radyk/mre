"""M9 — Evidence Index (L4).

Builds an in-memory index from JSONL run streams, then serves three primitives:
  entity_records(entity_id)    → all records mentioning that entity in subjects
  finding_occurrences(code)    → all Finding records with that code
  lineage_walk(entity_id)      → entity + transitive graph, ordered by pipeline stage

JSON persistence via save() / load().

THE FAITHFULNESS INVARIANT (Session 4B.18, docs/04 2026-07-30)
--------------------------------------------------------------
A PERSISTED EVIDENCE INDEX IS A FAITHFUL RECONSTRUCTION OF THE INDEX IT WAS
SAVED FROM. Any record class the builder places in ``_all_evidence`` is
recoverable after a round trip, or the load reports the index as INCOMPLETE and
names what is missing. Silence is forbidden: an answer surface may not be unable
to distinguish "this never happened" from "this was not persisted".

Schema 1 (through Session 4B.17) violated it. ``save()`` wrote three derived
indices and ``load()`` rebuilt ``_all_evidence`` from ``entity_records`` alone,
so **every record with no entity subject was silently dropped** — measured on a
real monolithic run, 25 of 236 records: all 12 Events (``record_event`` hardcodes
``subjects=[]``), all 8 Artifacts (so the input manifest — orders.csv, the cost
model, the identity map — vanished), the 4 M0 conformance rate Metrics that
``contracts/ids_rules.py`` names as what the C0–C3 rules MEASURE, and one
subject-less M6 Finding. That last one produced a contradiction INSIDE one loaded
index: ``finding_occurrences("SOLVER_NONOPTIMAL")`` returned it while
``all_findings()`` did not, because the former reads the persisted
``finding_index`` and the latter filters ``_all_evidence``.

Schema 2 fixes it at the root rather than per-class: ``_all_evidence`` is the
PRIMARY persisted structure and the three indices are DERIVED on load through
``_index_record`` — the same code path ``build`` uses, so they cannot diverge and
a future record class cannot go missing by being forgotten here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Optional

_MODULE_STAGE: dict[str, int] = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4,
    "M5": 5, "M6": 6, "M7": 7, "M9": 9, "M10": 10,
}

SCHEMA_VERSION = 2

# What a schema-1 file cannot be trusted to carry. Named as CLASSES rather than
# counted, because a v1 file gives no way to know how many were dropped — only
# which shapes could not have survived. Consumers name these to the planner.
_V1_LOST_CLASSES: tuple[str, ...] = (
    "event",                  # every Event: record_event() emits subjects=[]
    "artifact",               # every Artifact: register_input/_output emit subjects=[]
    "metric (subject-less)",  # e.g. M0's conformance rate metrics
    "finding (subject-less)",
)


class EvidenceIndex:
    """L4 evidence index.  Read-only after build().  Thread-safe for reads."""

    def __init__(self) -> None:
        self._entity_records: dict[str, list[dict]] = {}   # entity_id → records
        self._finding_index: dict[str, list[dict]] = {}    # code → findings
        self._run_registry: dict[str, dict] = {}           # run_id → run meta
        self._all_evidence: list[dict] = []                # flat, deduped
        # Record classes this index cannot vouch for. Empty on a built index and
        # on a schema-2 load; populated when loading a schema-1 artifact, which
        # dropped every subject-less record. See the module docstring.
        self.incomplete: tuple[str, ...] = ()

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

                self._index_record(rec)

        return self

    def _index_record(self, rec: dict) -> None:
        """Place ONE evidence record into the derived indices.

        The single definition of what ``entity_records`` and ``finding_index``
        mean, so ``build`` (from JSONL) and ``load`` (from a schema-2 file)
        produce identical indices by construction rather than by two
        implementations agreeing. Note what it deliberately does NOT do: it does
        not touch ``_all_evidence``, whose dedup is the caller's, and it does not
        drop a record for lacking subjects — a subject-less record is simply in
        no entity bucket, which is correct, and was the whole schema-1 defect
        only because ``_all_evidence`` was reconstructed FROM those buckets.
        """
        rid = rec.get("record_id", "")
        for subject in rec.get("subjects", []) or []:
            eid = subject.get("entity_id", "")
            if eid:
                bucket = self._entity_records.setdefault(eid, [])
                if not any(r.get("record_id") == rid for r in bucket):
                    bucket.append(rec)

        if rec.get("record_type", "") == "finding":
            code = rec.get("code", "")
            if code:
                bucket = self._finding_index.setdefault(code, [])
                if not any(r.get("record_id") == rid for r in bucket):
                    bucket.append(rec)

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

    def events(self) -> list[dict]:
        """All Event records, in index order (Session 4B.11 CU1).

        Added so the answer surface can read the M6 ``solve_complete`` payload —
        the SAME record ``schedule_assembler._solver_block`` builds the document's
        solver block from. The board and the answer agree about the cost proof
        because they read one record, not because two derivations were kept in
        step. Additive: no existing query changes."""
        return [r for r in self._all_evidence if r.get("record_type") == "event"]

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
        """Persist as schema 2: ``_all_evidence`` is the primary structure.

        ``entity_records`` and ``finding_index`` are NOT written — they are
        derived from these same records on load, which is what makes the round
        trip faithful. It is also smaller: schema 1 stored each record once per
        subject entity, so a record naming three entities was written three
        times.

        ``run_registry`` IS written, because it is not derivable from evidence
        records: it is folded from ``run_context_open``/``run_context_close``
        lines, which ``build`` consumes and never places in ``_all_evidence``.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": SCHEMA_VERSION,
                "all_evidence": self._all_evidence,
                "run_registry": self._run_registry,
            }, f, indent=None)

    @classmethod
    def load(cls, path: Path) -> "EvidenceIndex":
        """Load either schema. A schema-1 file loads and SAYS it is incomplete.

        Reading an old artifact silently was the defect: it answered "there is no
        solver report" about a solve that happened and was recorded. An old index
        still loads — nothing on disk is invalidated — but ``incomplete`` names
        the classes it cannot vouch for, and every consumer that can answer
        "absent" must consult it before doing so.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        idx = cls()
        idx._run_registry = data.get("run_registry", {})

        if int(data.get("schema_version", 1)) >= 2:
            idx._all_evidence = data.get("all_evidence", [])
            for rec in idx._all_evidence:
                idx._index_record(rec)
            return idx

        # ---- schema 1: derived indices only, subject-less records already gone.
        idx._entity_records = data.get("entity_records", {})
        idx._finding_index = data.get("finding_index", {})
        seen: set[str] = set()
        for recs in idx._entity_records.values():
            for r in recs:
                rid = r.get("record_id", "")
                if rid and rid not in seen:
                    seen.add(rid)
                    idx._all_evidence.append(r)
        # A subject-less finding survives in finding_index but never reached
        # _all_evidence, which is how one loaded index gave two answers about
        # itself. Recover what IS there; the marker below covers the rest.
        for recs in idx._finding_index.values():
            for r in recs:
                rid = r.get("record_id", "")
                if rid and rid not in seen:
                    seen.add(rid)
                    idx._all_evidence.append(r)
        idx.incomplete = _V1_LOST_CLASSES
        return idx
