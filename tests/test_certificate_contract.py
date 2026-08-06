"""Session S-02 + S-03 — the certificate contract.

TWO ITEMS, from the shared-body census's ledger (`docs/closeouts/
4a-micro-shared-body-census.md` §9).

**S-02 — the gate's verdict was in no evidence record.** `ConformanceGate.record`
emits a Finding only when a rule is NOT satisfied, which is correct: every
finding code names a defect and a satisfied rule is not one. The unnoticed
consequence is that an ACCEPTED submission with no deficiencies left the
evidence store COMPLETELY SILENT about its own certificate — the grade was
computed, written to `certificate.json`, and never reported. Every surface that
reads evidence alone was therefore structurally unable to state the grade
(`Explainer._opener_certificate` returns `{"grade": None}` and says so), and the
certificate route had to reach past the store to the artifact.

**S-03 — the answer told a planner about a signing step that does not exist.**
"…and it is unsigned — nobody has countersigned it" is true of the artifact and
false as an implication: this product has no certificate-countersigning concept,
so the sentence invents a missing step. The manufacture rule's quieter cousin —
ASSERTING THE ABSENCE OF SOMETHING IMPLIES THE SOMETHING.

The guards below hold four things:

  1. THE VERDICT IS IN THE EVIDENCE, with its envelope, its provenance and its
     decomposable coverage counts, on BOTH of the gate's exits.
  2. THE ROUTE GROUNDS EVIDENCE-FIRST, and the artifact fallback is retained —
     evidence is append-only, so boards gated before this change have no record
     and never will.
  3. THE TWO READINGS CANNOT DRIFT: the record's grade and the artifact's grade
     are one computation read twice.
  4. NO SIGNING VOCABULARY reaches a rendered certificate body, by either path.

A note on where the tests point. The evidence-path tests drive a REAL gate run
over the committed fenced dataset (`datasets/mobility_box`) into `tmp_path` —
never a hand-fed assembler, which would prove the assembler and not the path
(4B.21 §5a.78). The artifact-path tests read the pinned `gb_pinned` board
READ-ONLY, because that board was gated before this change and is the specimen
of the fallback.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import (
    GATE_VERDICT_STATUS, GRADE_FORMULA, ConformanceGate, write_certificate_json,
)
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer
from mre.modules.renderers import TemplateRenderer
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

ROOT = Path(__file__).resolve().parents[1]
FENCED = ROOT / "datasets" / "mobility_box"
PINNED = ROOT / "_ai_exam_scratch" / "gb_pinned"

#: The whole S-03 vocabulary. `sign` alone is NOT here on purpose: it is a real
#: word in this codebase for the direction of a number ("a signed delta"), and a
#: guard that fired on it would be a guard about arithmetic.
SIGNING_WORDS = ("unsigned", "countersign", "countersigned", "signature",
                 "signatory", "signed")


# ---------------------------------------------------------------------------
# Fixtures — one real gate run, reused
# ---------------------------------------------------------------------------

def _gate_run(out_dir: Path, submission: Path = FENCED,
              write_artifact: bool = True) -> dict:
    """Run the M0 gate for real into `out_dir`, exactly as `__main__` does:
    write-and-register BEFORE `end()`, because the output manifest is sealed
    into the close record."""
    runs = out_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="IDS conformance gate",
        config={"submission_dir": str(submission)}, trigger="test",
        snapshot_id="snap-gate", sink_dir=runs,
    )
    result = ConformanceGate().run(submission, reporter)
    if write_artifact:
        write_certificate_json(result.certificate, out_dir / "certificate.json",
                               reporter=reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    index = EvidenceIndex().build(runs)
    return {"result": result, "index": index, "out_dir": out_dir,
            "runs": runs, "reporter": reporter}


@pytest.fixture(scope="module")
def gated(tmp_path_factory) -> dict:
    return _gate_run(tmp_path_factory.mktemp("gated"))


def _verdicts(index: EvidenceIndex) -> list[dict]:
    return [e for e in index.events()
            if e.get("status_text") == GATE_VERDICT_STATUS]


def _explainer(out_dir: Path, index: EvidenceIndex,
               snapshot_id: str = "snap-gate") -> Explainer:
    return Explainer(SnapshotStore(out_dir / "snapshots"), index,
                     snapshot_id=snapshot_id, out_dir=out_dir)


def _body(explainer: Explainer, route_id: str = "certificate-testimony") -> str:
    return TemplateRenderer().render(
        explainer._route_inner(route_id, {"question": "what does the certificate say"}))


# ---------------------------------------------------------------------------
# 1. S-02 — the verdict is in the evidence
# ---------------------------------------------------------------------------

def test_an_accepted_submission_reports_its_own_grade(gated):
    """THE GAP, DIRECTLY. This submission grades ACCEPTED with every rule
    satisfied — the exact case that emitted NOTHING before."""
    assert gated["result"].grade == "ACCEPTED"
    assert gated["result"].certificate["findings"] == []
    verdicts = _verdicts(gated["index"])
    assert len(verdicts) == 1, "exactly one verdict per gate run"
    assert verdicts[0]["payload"]["grade"] == "ACCEPTED"


def test_the_verdict_carries_the_common_envelope(gated):
    """docs/02 §3: subjects are part of the envelope, and §8(1) requires M0 to
    name its subject as a typed submission-space ref so the record is reachable
    by key. `record_event` hardcoded `subjects=[]` until this session."""
    rec = _verdicts(gated["index"])[0]
    assert rec["module"] == "M0"
    assert rec["tier"] == "headline"
    assert rec["snapshot_id"] == "snap-gate"
    assert [s["entity_id"] for s in rec["subjects"]] == ["mobility_box"]
    assert rec["subjects"][0]["system"] == "IDS"
    assert rec["subjects"][0]["entity_type"] == "submission"


def test_the_verdict_states_grade_costing_and_coverage(gated):
    p = _verdicts(gated["index"])[0]["payload"]
    cert = gated["result"].certificate
    assert p["grade"] == cert["grade"]
    assert p["costing_completeness_grade"] == cert["costing_completeness_grade"]
    assert p["rules_checked"] == len(cert["rule_outcomes"])
    assert sum(p["outcome_tally"].values()) == p["rules_checked"]


def test_the_grade_provenance_is_derived_and_walkable(gated):
    """TRUTHFUL PROVENANCE. The grade is COMPUTED by a named formula from
    observed rule outcomes. Writing it as `observed` would be the defect class
    the 2026-07-12 amendments name — and the formula id is asserted to resolve,
    so the provenance is walkable rather than decorative."""
    prov = _verdicts(gated["index"])[0]["payload"]["grade_provenance"]
    assert prov["provenance_class"] == "derived"
    assert prov["formula_id"] == GRADE_FORMULA
    module_path, _, func = GRADE_FORMULA.rpartition(".")
    import importlib
    assert callable(getattr(importlib.import_module(module_path), func))


def test_the_coverage_metrics_decompose_exactly(gated):
    """docs/02 §4.4. The four components are emitted EVEN AT ZERO: a rollup
    whose components are conditionally present cannot be verified, and an absent
    component reads as an unasked question rather than a measured nought."""
    metrics = [r for r in gated["index"]._all_evidence
               if r.get("record_type") == "metric"
               and str(r.get("name", "")).startswith("gate.")]
    by_name = {m["name"]: m for m in metrics}
    assert set(by_name) == {"gate.rules_checked", "gate.rules_satisfied",
                            "gate.rules_flagged", "gate.rules_degraded",
                            "gate.rules_violated"}
    rollup = by_name["gate.rules_checked"]
    components = [by_name[n] for n in ("gate.rules_satisfied", "gate.rules_flagged",
                                       "gate.rules_degraded", "gate.rules_violated")]
    assert rollup["value"] == sum(c["value"] for c in components)
    assert set(rollup["rollup_of"]) == {c["record_id"] for c in components}
    assert all(m["unit"] == "rules" for m in metrics)
    assert all(m["subjects"] for m in metrics), "coverage is reachable by key"


def test_end_ran_the_decomposability_check_without_raising(gated):
    """`Reporter.end()` consolidates, and the consolidator RAISES on a rollup
    that does not decompose. The fixture already called it — this names why that
    is an assertion and not an accident."""
    assert gated["reporter"]._output_manifest  # the run closed normally


def test_the_certificate_artifact_is_registered_with_its_hash(gated):
    artifacts = [r for r in gated["index"]._all_evidence
                 if r.get("record_type") == "artifact"
                 and r.get("artifact_ref", "").endswith("certificate.json")]
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art["artifact_direction"] == "output"
    body = (gated["out_dir"] / "certificate.json").read_bytes()
    assert art["artifact_hash"] == hashlib.sha256(body).hexdigest()


def test_the_record_and_the_artifact_are_one_computation(gated):
    """`grade_from_outcomes` is called ONCE in the module. If a second call ever
    appears, these two can disagree — which is the whole reason the verdict is
    emitted from the same locals that build the certificate dict."""
    p = _verdicts(gated["index"])[0]["payload"]
    on_disk = json.loads((gated["out_dir"] / "certificate.json").read_text(encoding="utf-8"))
    assert p["grade"] == on_disk["grade"]
    assert p["generated_at"] == on_disk["generated_at"]
    assert p["rules_checked"] == len(on_disk["rule_outcomes"])


def test_the_intake_refusal_also_reports_a_verdict(tmp_path):
    """"I was pointed at nothing" is still a grade. A verdict record present on
    only one of the gate's two exits would be a gap shaped exactly like the one
    it was built to close."""
    empty = tmp_path / "nothing_here"
    empty.mkdir()
    run = _gate_run(tmp_path / "intake", submission=empty)
    assert run["result"].grade == "REJECTED"
    payload = _verdicts(run["index"])[0]["payload"]
    assert payload["grade"] == "REJECTED"
    assert payload["intake_error"] == "empty_directory"
    assert payload["rules_checked"] == 1
    assert payload["deficiency_count"] == 1


# ---------------------------------------------------------------------------
# 2. S-02 — the route grounds evidence-first, and the fallback is retained
# ---------------------------------------------------------------------------

def test_the_route_grounds_on_the_evidence_record(gated):
    cert = _explainer(gated["out_dir"], gated["index"])._read_certificate()
    assert cert["source"] == "evidence"
    assert cert["record_id"] == _verdicts(gated["index"])[0]["record_id"]
    assert cert["grade"] == "ACCEPTED"
    assert cert["rules_checked"] == 29


def test_the_evidence_reading_answers_with_no_artifact_at_all(tmp_path):
    """A board whose certificate file is gone can still state its grade. This is
    the S-02 gap inverted: the store is now the primary, not the workaround."""
    run = _gate_run(tmp_path / "no_artifact", write_artifact=False)
    assert not (run["out_dir"] / "certificate.json").exists()
    cert = _explainer(run["out_dir"], run["index"])._read_certificate()
    assert cert["source"] == "evidence"
    assert cert["grade"] == "ACCEPTED"


def test_the_artifact_fallback_is_retained_for_boards_gated_before_this(gated):
    """NO RETROACTIVE WRITES. Evidence is append-only, so a board gated before
    this change has no verdict record and never will. Reached by an index whose
    events are empty — the same shape those boards present."""
    empty_index = EvidenceIndex()
    empty_index._all_evidence = [
        r for r in gated["index"]._all_evidence if r.get("record_type") != "event"]
    cert = _explainer(gated["out_dir"], empty_index)._read_certificate()
    assert cert["source"] == "artifact"
    assert cert["grade"] == "ACCEPTED"
    assert cert.get("record_id") is None


@pytest.mark.skipif(not (PINNED / "evidence_index.json").exists(),
                    reason="the pinned glass_box run is not present in this tree")
def test_the_pinned_board_falls_on_the_artifact_side():
    """THE LINE, DRAWN ON A REAL BOARD. `gb_pinned` was gated on 2026-07-26,
    before the verdict record existed. It reads from the artifact, and its body
    still states the grade."""
    index = EvidenceIndex.load(PINNED / "evidence_index.json")
    assert _verdicts(index) == []
    ex = Explainer(SnapshotStore(PINNED / "snapshots"), index,
                   snapshot_id="snap-exam", out_dir=PINNED)
    cert = ex._read_certificate()
    assert cert["source"] == "artifact"
    assert cert["grade"] == "ACCEPTED"
    assert "ACCEPTED" in _body(ex)


def test_a_malformed_verdict_payload_falls_back_rather_than_half_reading(gated):
    """A record we cannot read is not a grade we can state. Falling through to
    the artifact is right (it may well be intact); manufacturing a state out of
    our own storage failure is what 4B.18 ruled against."""
    broken = EvidenceIndex()
    broken._all_evidence = [dict(r) for r in gated["index"]._all_evidence]
    for rec in broken._all_evidence:
        if rec.get("status_text") == GATE_VERDICT_STATUS:
            rec["payload"] = {"grade": None}
    cert = _explainer(gated["out_dir"], broken)._read_certificate()
    assert cert["source"] == "artifact"
    assert cert["grade"] == "ACCEPTED"


def test_the_most_recent_verdict_stands(tmp_path):
    """A resubmit re-gates the same submission into the same runs dir. The
    verdict that stands is the latest — the same rule the registry applies to
    schedules.

    ASSERTED AGAINST THE CLOCK, NOT AGAINST LIST POSITION. `EvidenceIndex.build`
    walks `sorted(runs_dir.glob("*.jsonl"))` and run files are named
    `<uuid4>.jsonl`, so index order across runs is effectively random; a test
    that asserted `verdicts[-1]` would be checking the implementation against
    itself and would pass on either rule. This one names the newest record by
    its own timestamp and requires the route to have chosen that one."""
    out = tmp_path / "twice"
    _gate_run(out)
    second = _gate_run(out, submission=FENCED)
    verdicts = _verdicts(second["index"])
    assert len(verdicts) == 2
    stamps = [str(v["timestamp"]) for v in verdicts]
    assert stamps[0] != stamps[1], "the two runs must be distinguishable in time"
    newest = max(verdicts, key=lambda v: str(v["timestamp"]))
    cert = _explainer(out, second["index"])._read_certificate()
    assert cert["record_id"] == newest["record_id"]


# ---------------------------------------------------------------------------
# 3. S-03 — no signing vocabulary, and what replaced it
# ---------------------------------------------------------------------------

def test_the_certificate_body_says_nothing_about_signing(gated):
    """THE GUARD S-03 EXISTS FOR. Red against the copy as it stood: the sentence
    ended "…and it is unsigned — nobody has countersigned it"."""
    body = _body(_explainer(gated["out_dir"], gated["index"])).lower()
    for word in SIGNING_WORDS:
        assert word not in body, f"signing vocabulary in the certificate body: {word!r}"


@pytest.mark.skipif(not (PINNED / "evidence_index.json").exists(),
                    reason="the pinned glass_box run is not present in this tree")
def test_no_signing_vocabulary_on_the_artifact_path_either():
    """BOTH READINGS. The removed sentence lived in the `present` branch, which
    both paths reach — a fix proven on one of them is not proven."""
    index = EvidenceIndex.load(PINNED / "evidence_index.json")
    ex = Explainer(SnapshotStore(PINNED / "snapshots"), index,
                   snapshot_id="snap-exam", out_dir=PINNED)
    body = _body(ex).lower()
    for word in SIGNING_WORDS:
        assert word not in body


def test_the_body_states_what_the_certificate_contains(gated):
    """The removal is not a deletion: the answer says what the record IS. Grade,
    costing completeness, coverage, provenance, findings as supporting detail."""
    body = _body(_explainer(gated["out_dir"], gated["index"]))
    assert "Intake review: ACCEPTED" in body
    assert "costing completeness C2" in body
    assert "29 gate check(s) ran" in body
    assert "the gate's own record" in body
    assert "computed from those rule outcomes" in body


def test_the_provenance_sentence_is_not_claimed_without_the_provenance(gated):
    """A board read from the artifact has no provenance to quote, so it does not
    quote one. Stating how the grade was made is only honest where the record
    says so."""
    empty_index = EvidenceIndex()
    empty_index._all_evidence = [
        r for r in gated["index"]._all_evidence if r.get("record_type") != "event"]
    body = _body(_explainer(gated["out_dir"], empty_index))
    assert "the gate's own record" in body
    assert "computed from those rule outcomes" not in body


def test_r_cal1_is_untouched_by_s03(tmp_path):
    """THE ONE-LINER THAT STOPS S-03 BEING READ AS PRECEDENT. A
    CalibrationProfile signature is a DIFFERENT artifact with a defined
    attestation — a human accepting a measurement they are answerable for. Rule
    (2) still holds: no `by`, no acceptance."""
    from mre.modules.calibration import ProfileStore
    store = ProfileStore(tmp_path)
    with pytest.raises(Exception):
        store.accept("some-plant", by="")


# ---------------------------------------------------------------------------
# 4. The pair the census repaired must stay repaired
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (PINNED / "evidence_index.json").exists(),
                    reason="the pinned glass_box run is not present in this tree")
def test_the_two_bodies_still_differ():
    """The census's repair, re-asserted from this session's side: whatever S-02
    and S-03 changed about the certificate body, it must not collapse back onto
    `data-problems`."""
    index = EvidenceIndex.load(PINNED / "evidence_index.json")
    ex = Explainer(SnapshotStore(PINNED / "snapshots"), index,
                   snapshot_id="snap-exam", out_dir=PINNED)
    assert _body(ex, "certificate-testimony") != _body(ex, "data-problems")
