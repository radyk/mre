"""Micro-session 4A — the shared-body census and the certificate route.

`certificate-testimony` and `data-problems` rendered THE SAME BODY. Two intents
with different declared meanings, one answer: the Conformance Gate's own voice
could not state the Conformance Gate's grade. The `deaf` rider caught the pair
twice across two sessions ((d.0) P6 T7; (d.1) sweep block E2) and was right both
times — the only true positive that rider has ever produced.

These guards hold three separate things:

  1. THE BODIES DIFFER, and the certificate body states the grade. Byte-identity
     is what the defect was, so byte-difference is asserted directly.
  2. THE FOUR ARTIFACT STATES each get their own honest sentence, and the three
     that cannot state a grade never fall through to the findings list. A
     default that asserts manufactures a claim out of a gap.
  3. `deaf` IS SILENT on the pair — see `test_deaf_is_silent_on_the_pair`, whose
     comment explains why silence is now the correct reading.

The census predicate, applied uniformly and recorded here so a later reader can
re-apply it: two intents with DIFFERENT DECLARED MEANINGS (the
`contracts/parse.py` docstrings are the authority) whose rendered bodies are
identical, or differ only in framing, are one defect — a planner reading the
body cannot tell which question was answered.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.modules.explainer import Explainer
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.renderers import TemplateRenderer
from mre.modules.snapshot_store import SnapshotStore

PINNED = Path(__file__).resolve().parents[1] / "_ai_exam_scratch" / "gb_pinned"

pytestmark = pytest.mark.skipif(
    not (PINNED / "evidence_index.json").exists(),
    reason="the pinned glass_box run is not present in this tree",
)


def _explainer(out_dir: Path | None = None) -> Explainer:
    """The pinned run, READ-ONLY. `out_dir` is where the certificate is read
    from; passing a different one is how the degraded states are reached without
    touching the pinned board."""
    idx = EvidenceIndex.load(PINNED / "evidence_index.json")
    store = SnapshotStore(PINNED / "snapshots")
    return Explainer(store, idx, snapshot_id="snap-exam",
                     out_dir=PINNED if out_dir is None else out_dir)


def _body(explainer: Explainer, route_id: str) -> str:
    bundle = explainer._route_inner(route_id, {"question": "q"})
    return TemplateRenderer().render(bundle)


# ---------------------------------------------------------------------------
# 1. The bodies differ, and the certificate body states the certificate
# ---------------------------------------------------------------------------

def test_the_two_routes_no_longer_render_one_body():
    """THE DEFECT, DIRECTLY. Before this session both routes returned
    `_explain_data_problems`, so the two bodies were byte-identical (measured on
    the pinned run: sha256 39022447757c0386 for both)."""
    ex = _explainer()
    assert _body(ex, "certificate-testimony") != _body(ex, "data-problems")


def test_certificate_body_states_the_grade():
    ex = _explainer()
    body = _body(ex, "certificate-testimony")
    cert = json.loads((PINNED / "certificate.json").read_text(encoding="utf-8"))
    # The grade is QUOTED from the artifact, never recomputed here or there.
    assert cert["grade"] in body
    assert cert["costing_completeness_grade"] in body


def test_certificate_body_states_its_coverage():
    """A grade with no coverage is a verdict with no scope. The count comes off
    the artifact's own rule_outcomes."""
    ex = _explainer()
    body = _body(ex, "certificate-testimony")
    cert = json.loads((PINNED / "certificate.json").read_text(encoding="utf-8"))
    assert str(len(cert["rule_outcomes"])) in body
    assert "gate check(s) ran" in body


def test_data_problems_body_is_unchanged_and_states_no_grade():
    """The other half of the pair keeps ITS meaning: the findings ARE its body,
    and it must not start claiming the gate's verdict."""
    ex = _explainer()
    body = _body(ex, "data-problems")
    assert "data-quality problem(s)" in body
    assert "Intake review" not in body


def test_the_findings_detail_is_the_same_set_in_both():
    """4A.2b CU2 COHERENCE, PRESERVED DELIBERATELY. The certificate route leads
    with the grade and keeps `_report_findings()` underneath — the same set
    testimony, remediation and triage reason over. Narrowing this route to
    gate-only findings would have put the registers back into the contradiction
    that ruling ended, so what changed is the LEAD, never the evidence."""
    ex = _explainer()
    cert_bundle = ex._route_inner("certificate-testimony", {"question": "q"})
    dp_bundle = ex._route_inner("data-problems", {"question": "q"})
    assert ([r.get("record_id") for r in cert_bundle.ordered_records]
            == [r.get("record_id") for r in dp_bundle.ordered_records])


def test_an_accepted_grade_coexists_with_a_standing_advisory():
    """The specimen 4A.2b CU2 was written about, now visible in ONE answer: the
    gate passed all 29 of its checks (ACCEPTED, no deficiencies) while a
    validator advisory stands. Both true, from different layers — and a planner
    can now see which is which instead of reading the advisory as the grade."""
    ex = _explainer()
    body = _body(ex, "certificate-testimony")
    assert "ACCEPTED" in body
    assert "No deficiencies" in body
    assert "data-quality problem(s)" in body


# ---------------------------------------------------------------------------
# 2. The four artifact states
# ---------------------------------------------------------------------------

def test_state_present_on_the_pinned_run():
    assert _explainer()._read_certificate()["state"] == "present"


def test_state_absent_says_never_gated_and_states_no_grade(tmp_path):
    """A run directory with no certificate. NOT a pinned board — a tmp dir, so
    no board is mutated to reach this state."""
    ex = _explainer(out_dir=tmp_path)
    assert ex._read_certificate()["state"] == "absent"
    body = _body(ex, "certificate-testimony")
    assert "never went through the intake gate" in body
    for grade in ("ACCEPTED", "CONDITIONAL", "REJECTED"):
        assert grade not in body


def test_state_no_run_dir_says_nothing_was_looked_for():
    """Distinct from `absent`: nothing was searched. An Explainer built with no
    run directory and a store whose base is not a `snapshots/` dir cannot derive
    one — which is most module-level constructions."""
    idx = EvidenceIndex.load(PINNED / "evidence_index.json")

    class _StoreWithNoRunDir:
        """Loads snapshots normally, but its `_base` is not a `snapshots/` dir,
        so the Explainer's out_dir derivation correctly declines to guess."""

        _base = None

        def __init__(self) -> None:
            self._inner = SnapshotStore(PINNED / "snapshots")

        def load_snapshot(self, snapshot_id):
            return self._inner.load_snapshot(snapshot_id)

    ex = Explainer(_StoreWithNoRunDir(), idx, snapshot_id="snap-exam")
    assert ex._read_certificate()["state"] == "no_run_dir"
    body = _body(ex, "certificate-testimony")
    assert "without a run directory" in body


def test_state_unreadable_takes_priority_and_blames_storage(tmp_path):
    """4B.18's `unreadable` species. A corrupt certificate is NOT an absent one,
    and the answer must not read as a clean bill of health."""
    (tmp_path / "certificate.json").write_text("{not json", encoding="utf-8")
    ex = _explainer(out_dir=tmp_path)
    assert ex._read_certificate()["state"] == "unreadable"
    body = _body(ex, "certificate-testimony")
    assert "about our storage, not" in body
    assert "ACCEPTED" not in body


def test_a_present_certificate_with_no_grade_says_so(tmp_path):
    """The field is missing, not the file. Reported as its own fact rather than
    defaulted to a word."""
    (tmp_path / "certificate.json").write_text(
        json.dumps({"rule_outcomes": {"ids.x": "satisfied"}}), encoding="utf-8")
    ex = _explainer(out_dir=tmp_path)
    body = _body(ex, "certificate-testimony")
    assert "carries no grade" in body


def test_zero_findings_still_states_the_grade(tmp_path):
    """A clean submission. The certificate must still speak — an empty findings
    list is not an empty answer."""
    (tmp_path / "certificate.json").write_text(
        json.dumps({"grade": "ACCEPTED", "costing_completeness_grade": "C3",
                    "rule_outcomes": {"ids.a": "satisfied", "ids.b": "satisfied"}}),
        encoding="utf-8")
    idx = EvidenceIndex.load(PINNED / "evidence_index.json")
    ex = Explainer(SnapshotStore(PINNED / "snapshots"), idx,
                   snapshot_id="snap-exam", out_dir=tmp_path)
    bundle = ex._route_inner("certificate-testimony", {"question": "q"})
    bundle.ordered_records = []
    body = TemplateRenderer().render(bundle)
    assert "ACCEPTED" in body and "2 gate check(s) ran" in body


def test_a_rejected_certificate_leads_with_the_refusal(tmp_path):
    (tmp_path / "certificate.json").write_text(
        json.dumps({"grade": "REJECTED", "costing_completeness_grade": "C0",
                    "rule_outcomes": {"ids.a": "violated"},
                    "deficiencies": ["orders file missing"]}), encoding="utf-8")
    ex = _explainer(out_dir=tmp_path)
    body = _body(ex, "certificate-testimony")
    assert body.lstrip().startswith("Intake review: REJECTED")
    assert "1 deficiency(ies)" in body


# ---------------------------------------------------------------------------
# 3. The census property, and the deaf silence
# ---------------------------------------------------------------------------

def test_no_two_differently_meaning_intents_share_an_undiscriminated_assembler():
    """THE CENSUS AS A PROPERTY, not a one-route assertion.

    Of the three assemblers reached by more than one route, two receive a
    discriminator and branch on it (`_rolling_bundle` takes `route_id`;
    `_schedule_query` branches on a subject-derived filter). The third,
    `_explain_data_problems`, was handed only `entity_ref` — so it was
    STRUCTURALLY incapable of knowing which of two questions it was answering.
    That is the shape this test forbids coming back: the two routes must reach
    different assemblers, or one assembler that is told which route called it.
    """
    ex = _explainer()
    a = ex._route_inner("certificate-testimony", {"question": "q"})
    b = ex._route_inner("data-problems", {"question": "q"})
    assert a.subject_type != b.subject_type


def test_deaf_is_silent_on_the_pair():
    """THE RIDER'S ONE TRUE POSITIVE IS NOW EXTINCT, AND THAT IS THE POINT.

    Read this assertion carefully before changing it. `deaf` fires when two
    DIFFERENT questions produce the same answer fingerprint; it fired on this
    exact pair in (d.0) and (d.1) and was correct — the bodies really were one
    body. Silence here is NOT the gate being suppressed or weakened: the gate is
    untouched. It is silent because the condition it detects no longer holds.
    A true positive whose defect has been fixed SHOULD go quiet, and a future
    reader seeing this assert-silence must not "restore" the firing.

    If this test goes red, the two bodies have collapsed back together — which
    is the defect, not the rider.
    """
    from mre.contracts.parse import FollowupKind, Intent, ParsedQuestion
    from mre.modules.interpreter import (bundle_repeat, forget_deliveries,
                                         remember_delivery)

    session, schedule = "cert-census-guard", "sched-1"
    forget_deliveries(session)
    ex = _explainer()

    dp_text = _body(ex, "data-problems")
    remember_delivery(session, schedule, "data-problems",
                      "are there any data quality problems", dp_text)

    cert_bundle = ex._route_inner("certificate-testimony", {"question": "q"})
    cert_text = TemplateRenderer().render(cert_bundle)
    parsed = ParsedQuestion(
        question="what does the certificate say",
        intent=Intent.CERTIFICATE_TESTIMONY,
        confidence=0.95,
        # DEEPEN is what the LIVE parse reports on this turn — (d.1) measured it
        # — so the fixture supplies the real value rather than a convenient one.
        # The (d.1) deaf gate does not swallow it because the ROUTES differ,
        # which is why silence here proves the BODIES and not the gate.
        followup_of=FollowupKind.DEEPEN,
    )
    bundle_repeat(cert_bundle, {"history": []}, parsed, text=cert_text,
                  session_id=session, schedule_id=schedule)
    forget_deliveries(session)

    assert "deaf" not in cert_bundle.key_facts
