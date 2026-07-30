"""THE FAITHFULNESS GUARD — Session 4B.18, docs/04 2026-07-30, docs/07 §5a.63.

THE INVARIANT UNDER TEST:

  A PERSISTED EVIDENCE INDEX IS A FAITHFUL RECONSTRUCTION OF THE INDEX IT WAS
  SAVED FROM. Any record class the builder places in ``_all_evidence`` is
  recoverable after a round trip, or the load reports the index as INCOMPLETE
  and names what is missing. Silence is forbidden: an answer surface may not be
  unable to distinguish "this never happened" from "this was not persisted".

WHY IT ASSERTS BY KIND AND COUNT, NOT BY LOOKING FOR ONE STRING. The defect that
produced this guard was found as a missing ``solve_complete`` event, and a guard
written to that specimen would check for that string and pass while the input
manifest, the M0 conformance metrics and a subject-less finding stayed lost —
which is exactly what schema 1 also did to 25 of 236 records on a real run. The
guard therefore compares the FULL (record_type, module) census before and after.
A record class nobody has thought of yet is covered on the day it is emitted.

THE FIRST TEST EMITS THROUGH THE REAL REPORTER, all eight verbs, rather than
hand-writing dicts. That is what makes it a guard on the SYSTEM rather than on
the fixture: ``record_event`` and ``register_input``/``register_output`` hardcode
``subjects=[]``, so a subject-less record is produced the way production produces
one, not the way a test author remembered to.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from mre.contracts.entities import EntityRef
from mre.contracts.vocabularies import (
    DecisionBasis,
    DecisionType,
    DriverCode,
    FindingCode,
    FindingDisposition,
    FindingSeverity,
    ModuleCode,
    RunStatus,
)
from mre.modules.evidence_index import SCHEMA_VERSION, EvidenceIndex
from mre.reporter.reporter import Reporter


# ---------------------------------------------------------------------------
# The census: what the invariant is stated in terms of
# ---------------------------------------------------------------------------

def _census(index: EvidenceIndex) -> collections.Counter:
    """(record_type, module) -> count over ``_all_evidence``.

    Deliberately coarser than record identity and deliberately finer than a
    total: a total hides a swap, and identity would make the guard fail on
    incidental ordering. Kind and count is the level the invariant is written at.
    """
    return collections.Counter(
        (r.get("record_type", "?"), r.get("module", "?"))
        for r in index._all_evidence
    )


def _emit_full_run(runs_dir: Path) -> None:
    """Every Reporter verb, through the Reporter, into a real JSONL sink."""
    rep = Reporter.begin(
        module=ModuleCode.M6,
        purpose="roundtrip-guard",
        config={"guard": True},
        trigger="test",
        snapshot_id="snap-guard",
        sink_dir=runs_dir,
    )
    subj = [EntityRef(entity_id="op-guard-1", entity_type="operation")]

    # --- WITH subjects: these survived schema 1, and must keep surviving.
    rep.record_decision(
        decision_type=DecisionType.ASSIGNMENT,
        subjects=subj,
        chosen="MACH-01",
        alternatives=[],
        driver=DriverCode.CAPACITY_BLOCKED,
        basis=DecisionBasis.RECONSTRUCTED,
        message="guard decision",
    )
    rep.record_metric(name="guard_rate", value=1.0, unit="ratio", subjects=subj)
    rep.record_finding(
        code=FindingCode.SOLVER_NONOPTIMAL,
        severity=FindingSeverity.WARNING,
        subjects=subj,
        evidence={"gap": 0.1},
        disposition=FindingDisposition.PROCEEDED_FLAGGED,
    )

    # --- WITHOUT subjects: the whole schema-1 casualty list, emitted the way
    #     production emits it. Note none of these PASSES subjects=[] explicitly;
    #     the Reporter does, which is why the class was invisible.
    rep.register_input(artifact_id="orders.csv", artifact_hash="deadbeef")
    rep.register_output(artifact_ref="schedule.csv", artifact_hash="cafe")
    rep.record_event(status_text="solve_complete",
                     payload={"status": "OPTIMAL", "gap": 0.0})
    rep.record_event(status_text="improving_solution", payload={"obj": 12.0})
    rep.record_metric(name="duration_computability_rate", value=1.0, unit="ratio")
    rep.record_finding(
        code=FindingCode.SOLVER_NONOPTIMAL,
        severity=FindingSeverity.WARNING,
        subjects=[],                      # a run-level finding: no entity subject
        evidence={"gap": 0.5692},
        disposition=FindingDisposition.PROCEEDED_FLAGGED,
    )
    rep.end(status=RunStatus.SUCCESS)


@pytest.fixture()
def built_index(tmp_path: Path) -> EvidenceIndex:
    runs = tmp_path / "runs"
    _emit_full_run(runs)
    return EvidenceIndex().build(runs)


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

class TestRoundTripFaithfulness:

    def test_fixture_actually_contains_subject_less_records(self, built_index):
        """The guard's own premise. Without this, everything below could pass on
        a fixture where every record has a subject — which is precisely why the
        pre-existing ``test_load_populates_all_evidence`` passed throughout the
        defect's life."""
        bare = [r for r in built_index._all_evidence if not r.get("subjects")]
        kinds = {r.get("record_type") for r in bare}
        assert kinds == {"event", "artifact", "metric", "finding"}, (
            "the fixture must exercise every subject-less record class")

    def test_all_evidence_survives_by_kind_and_count(self, built_index, tmp_path):
        """THE INVARIANT. Not a total, not a string search: the full census."""
        p = tmp_path / "idx.json"
        built_index.save(p)
        loaded = EvidenceIndex.load(p)

        before, after = _census(built_index), _census(loaded)
        assert after == before, (
            "records lost or altered across a save/load round trip: "
            f"{ {k: (before.get(k, 0), after.get(k, 0)) for k in set(before) | set(after) if before.get(k, 0) != after.get(k, 0)} }")

    def test_record_ids_survive_exactly(self, built_index, tmp_path):
        """Kind and count cannot see a substitution that preserves both."""
        p = tmp_path / "idx.json"
        built_index.save(p)
        loaded = EvidenceIndex.load(p)
        assert ({r.get("record_id") for r in loaded._all_evidence}
                == {r.get("record_id") for r in built_index._all_evidence})

    def test_derived_queries_agree_across_the_trip(self, built_index, tmp_path):
        p = tmp_path / "idx.json"
        built_index.save(p)
        loaded = EvidenceIndex.load(p)
        assert len(loaded.events()) == len(built_index.events()) == 2
        assert len(loaded.all_findings()) == len(built_index.all_findings()) == 2
        assert len(loaded.all_decisions()) == len(built_index.all_decisions())
        for eid in built_index._entity_records:
            assert (len(loaded.entity_records(eid))
                    == len(built_index.entity_records(eid)))

    def test_no_intra_index_contradiction(self, built_index, tmp_path):
        """One loaded index, one answer. Schema 1 gave two: a subject-less
        finding was in ``finding_index`` and absent from ``_all_evidence``, so
        ``finding_occurrences`` found it and ``all_findings`` did not."""
        p = tmp_path / "idx.json"
        built_index.save(p)
        loaded = EvidenceIndex.load(p)
        via_code = len(loaded.finding_occurrences("SOLVER_NONOPTIMAL"))
        via_all = sum(1 for f in loaded.all_findings()
                      if f.get("code") == "SOLVER_NONOPTIMAL")
        assert via_code == via_all == 2

    def test_a_built_index_is_never_incomplete(self, built_index, tmp_path):
        assert built_index.incomplete == ()
        p = tmp_path / "idx.json"
        built_index.save(p)
        assert EvidenceIndex.load(p).incomplete == ()

    def test_saved_file_declares_its_schema(self, built_index, tmp_path):
        p = tmp_path / "idx.json"
        built_index.save(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["schema_version"] == SCHEMA_VERSION
        assert "all_evidence" in data and "run_registry" in data


# ---------------------------------------------------------------------------
# Real runs, when this working copy has any
# ---------------------------------------------------------------------------

def _real_run_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[1] / "_data" / "runs"
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir() if (d / "runs").is_dir())


@pytest.mark.parametrize("run_dir", _real_run_dirs(),
                         ids=lambda d: d.name[:8])
def test_roundtrip_on_a_real_run(run_dir: Path, tmp_path: Path):
    """The same invariant against records this repo actually produced.

    Skipped where ``_data/`` is absent (a fresh clone, CI), which is why the
    Reporter-driven guard above is the one that must never be deleted."""
    built = EvidenceIndex().build(run_dir / "runs")
    if not built._all_evidence:
        pytest.skip("no evidence records in this run")
    p = tmp_path / "idx.json"
    built.save(p)
    loaded = EvidenceIndex.load(p)
    assert _census(loaded) == _census(built)


# ---------------------------------------------------------------------------
# Schema 1: loads, and SAYS it is incomplete
# ---------------------------------------------------------------------------

class TestLegacySchemaIsDetectable:
    """An old artifact on disk is not invalidated — but it never answers
    'that never happened' out of a fact about our storage."""

    def _write_schema1(self, built: EvidenceIndex, path: Path) -> None:
        """Exactly what ``save()`` wrote through Session 4B.17."""
        path.write_text(json.dumps({
            "entity_records": built._entity_records,
            "finding_index": built._finding_index,
            "run_registry": built._run_registry,
        }), encoding="utf-8")

    def test_legacy_file_still_loads(self, built_index, tmp_path):
        p = tmp_path / "old.json"
        self._write_schema1(built_index, p)
        loaded = EvidenceIndex.load(p)
        assert loaded.all_decisions()          # the subject-bearing side is intact
        assert loaded.runs()

    def test_legacy_file_reports_itself_incomplete(self, built_index, tmp_path):
        p = tmp_path / "old.json"
        self._write_schema1(built_index, p)
        loaded = EvidenceIndex.load(p)
        assert loaded.incomplete, "a schema-1 load must declare what it cannot vouch for"
        assert "event" in loaded.incomplete
        assert "artifact" in loaded.incomplete

    def test_legacy_cost_proof_is_unreadable_not_no_solve(self, built_index, tmp_path):
        """THE DEFECT ITSELF, pinned. The board said PROVED and the answer said
        'no solver report I can read'; ``_proof_items`` returned [] because
        ``no_solve`` was True, and a band-1 money item vanished."""
        from mre.modules import cost_proof as cp

        p = tmp_path / "old.json"
        self._write_schema1(built_index, p)
        proof = cp.from_evidence(EvidenceIndex.load(p))

        assert proof.unreadable is True
        assert proof.no_solve is False, (
            "an unpersisted proof must never be reported as 'nothing was solved'")
        assert proof.unproved is False, "nor may it fire the unproved money rider"
        # But it may NOT be silent either: on this surface silence means "proved",
        # because proved is the only other state that says nothing.
        rider = proof.rider()
        assert rider is not None
        assert "unknown, not as proved" in rider
        assert "gap" not in rider, "an unreadable proof has no gap to claim"
        assert proof.chip()["state"] == "unreadable"
        assert "not saved" in proof.chip()["title"]

    def test_legacy_board_still_raises_the_item(self, built_index, tmp_path):
        """The opener must NOT go silent. Silence is the thing forbidden."""
        from mre.modules import cost_proof as cp
        from mre.modules.board_opener import _proof_items

        p = tmp_path / "old.json"
        self._write_schema1(built_index, p)
        proof = cp.from_evidence(EvidenceIndex.load(p))
        items = _proof_items(proof, {"total": 51637.18})
        assert len(items) == 1
        assert "CANNOT BE READ" in items[0].headline

    def test_current_schema_reads_the_proof(self, built_index, tmp_path):
        """The other side of the same coin: a schema-2 round trip answers."""
        from mre.modules import cost_proof as cp

        p = tmp_path / "new.json"
        built_index.save(p)
        proof = cp.from_evidence(EvidenceIndex.load(p))
        assert proof.unreadable is False
        assert proof.proved is True
        assert proof.status == "OPTIMAL"
