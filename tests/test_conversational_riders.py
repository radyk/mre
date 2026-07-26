"""CU5 (Session 4B.5) — the conversational riders. Each one founder-caught, each
one small, and all four about the same failing: an assistant that answers the
sentence rather than the turn.

  (a) an advice push-back that NAMES a capability ("so you can't tell me if
      overtime will help") is a coaching question, not a second delivery of the
      advice template that prompted the push-back;
  (b) a route re-fired within two turns varies its LEAD — an answer delivered
      word-for-word twice reads as not having heard the second question;
  (c) a COUNT answered in the previous turn answers tersely on re-ask ("13 — want
      the list?"), because the planner already has the list;
  (d) per-claim read-from attribution in synthesis is genuinely PER CLAIM. It was
      not: every claim carried the answer-level consulted set, so the surface
      printed the same three record ids beside every interpretive sentence.

Riders (a)–(c) are about ROUTING and DELIVERY and are tested here; whether a live
model parses the push-back's capability as a concept subject is the sweep's
(R-AI4(2)), and the specimens for it are in the banks.
"""
from __future__ import annotations

import pytest

from mre.contracts.parse import Intent, SubjectKind
from mre.contracts.synthesis import (
    ClaimKind, ClaimStatus, DraftClaim, SynthesisAnswer, SynthesisProvenance,
    VerifiedClaim,
)
from mre.modules.explainer import Explainer, ExplanationBundle
from mre.modules.interpreter import REPEAT_WINDOW, _repeat_depth, dispatch
from mre.modules.renderers import (
    COUNT_SUBJECTS, TemplateRenderer, apply_repeat_riders, repeat_lead,
    terse_count_answer,
)
from tests.parse_doubles import parsed, resolve
from tests.test_interpreter import FakeStore, _make_index


@pytest.fixture()
def explainer(tmp_path):
    return Explainer(snapshot_store=FakeStore("snap-demo"),
                     index=_make_index(tmp_path), snapshot_id="snap-demo")


def _dispatch(explainer, p, context=None):
    context = context or {}
    return dispatch(explainer, resolve(p, explainer, context), context=context)


def _turns(*routes):
    return {"history": [{"question": "q", "route": r} for r in routes]}


# ===========================================================================
# (a) an advice push-back naming a capability is a coaching question
# ===========================================================================

class TestAdviceNamingACapability:
    def test_it_routes_to_that_concepts_coaching(self, explainer):
        d = _dispatch(explainer,
                      parsed("so you can't tell me if overtime will help",
                             Intent.ADVICE, concepts=("overtime",)))
        assert d.route == "coaching"
        assert d.bundle.subject_type == "coaching"

    def test_it_is_NOT_a_second_delivery_of_the_advice_template(self, explainer):
        """The founder's rider in one assertion: the push-back must not be
        answered with the answer that prompted it."""
        advice = TemplateRenderer().render(
            _dispatch(explainer, parsed("what should i do", Intent.ADVICE)).bundle)
        pushback = TemplateRenderer().render(
            _dispatch(explainer,
                      parsed("so you can't tell me if overtime will help",
                             Intent.ADVICE, concepts=("overtime",))).bundle)
        assert pushback != advice

    def test_an_advice_question_naming_NO_capability_is_still_advice(self, explainer):
        d = _dispatch(explainer, parsed("what should i do about the late orders",
                                        Intent.ADVICE))
        assert d.route == "advice"

    def test_an_unresolvable_capability_word_does_not_divert(self, explainer):
        # "throughput" is not a declarable capability — the concept does not
        # resolve, so nothing is diverted and advice answers, honestly.
        d = _dispatch(explainer, parsed("can we improve throughput", Intent.ADVICE,
                                        concepts=("throughput",)))
        assert d.route == "advice"


# ===========================================================================
# (b) a re-fired route varies its lead
# ===========================================================================

class TestRepeatLead:
    def test_the_depth_is_read_off_the_history_the_panel_already_sends(self):
        assert _repeat_depth(_turns("late-orders"), "late-orders") == 1
        assert _repeat_depth(_turns("late-orders", "late-orders"), "late-orders") == 2
        assert _repeat_depth(_turns("late-orders", "advice"), "late-orders") == 1
        assert _repeat_depth(_turns("advice", "advice"), "late-orders") == 0
        assert _repeat_depth({}, "late-orders") == 0
        assert _repeat_depth(None, "late-orders") == 0

    def test_the_window_is_two_turns_so_a_genuine_return_reads_as_fresh(self):
        assert REPEAT_WINDOW == 2
        # asked, then three unrelated turns, then asked again → fresh
        ctx = _turns("late-orders", "advice", "coaching", "briefing")
        assert _repeat_depth(ctx, "late-orders") == 0

    def test_a_fresh_question_carries_no_lead(self, explainer):
        d = _dispatch(explainer, parsed("what should i do", Intent.ADVICE))
        assert "repeat" not in (d.bundle.key_facts or {})
        assert repeat_lead(d.bundle) == ""

    def test_a_re_fire_varies_the_lead_and_a_third_ask_varies_again(self, explainer):
        first = _dispatch(explainer, parsed("what should i do", Intent.ADVICE),
                          _turns("advice"))
        second = _dispatch(explainer, parsed("what should i do", Intent.ADVICE),
                           _turns("advice", "advice"))
        l1, l2 = repeat_lead(first.bundle), repeat_lead(second.bundle)
        assert l1 and l2 and l1 != l2

    def test_the_lead_prefixes_the_answer_and_changes_not_one_fact(self, explainer):
        fresh = TemplateRenderer().render(
            _dispatch(explainer, parsed("what should i do", Intent.ADVICE)).bundle)
        again = TemplateRenderer().render(
            _dispatch(explainer, parsed("what should i do", Intent.ADVICE),
                      _turns("advice")).bundle)
        assert again != fresh
        assert again.endswith(fresh)          # the body is byte-identical beneath

    def test_the_lead_never_replaces_the_answer(self):
        b = ExplanationBundle(question="q", subject_id="", subject_type="advice",
                              subject_external_name="?", ordered_records=[],
                              key_facts={"repeat": 1}, snapshot_id="s",
                              identity_map=None)
        assert apply_repeat_riders(b, "the body").endswith("the body")


# ===========================================================================
# (c) a re-asked count answers tersely
# ===========================================================================

def _count_bundle(subject_type, key_facts):
    return ExplanationBundle(
        question="how many orders are late?", subject_id="all",
        subject_type=subject_type, subject_external_name="all demands",
        ordered_records=[], key_facts=key_facts, snapshot_id="s",
        identity_map=None)


class TestTerseCount:
    def test_a_re_asked_count_answers_with_the_number_and_a_door(self):
        b = _count_bundle("late_orders", {
            "repeat": 1, "late_count": 13,
            "late_orders": [f"ORD-{i} (+10 min)" for i in range(13)]})
        assert terse_count_answer(b) == "13 — want the list?"

    def test_terseness_never_costs_the_planner_the_detail(self):
        """The offer is the whole point: the answer gets shorter, the plan does
        not get less available."""
        b = _count_bundle("late_orders", {"repeat": 1, "late_count": 13,
                                          "late_orders": ["ORD-1"]})
        assert "want the list?" in terse_count_answer(b)

    def test_a_count_with_nothing_behind_it_offers_nothing(self):
        b = _count_bundle("machine_count", {"repeat": 1, "machine_count": 6})
        assert terse_count_answer(b) == "6, same as before."

    def test_a_FIRST_ask_is_never_terse(self):
        b = _count_bundle("late_orders", {"late_count": 13, "late_orders": ["a"]})
        assert terse_count_answer(b) is None

    def test_a_non_count_route_is_never_terse(self):
        b = _count_bundle("advice", {"repeat": 1, "late_count": 13})
        assert terse_count_answer(b) is None

    def test_the_terse_answer_KEEPS_the_rendered_by_footer(self):
        """The delivery metadata is not conversation and must survive: an operator
        reading a transcript still needs to know which path rendered it."""
        b = _count_bundle("late_orders", {"repeat": 1, "late_count": 13,
                                          "late_orders": ["a"]})
        out = apply_repeat_riders(
            b, "the full recitation\n[rendered by: template | register: testimony]")
        assert out.startswith("13 — want the list?")
        assert "rendered by: template" in out
        assert "recitation" not in out

    def test_the_count_class_is_a_closed_named_set(self):
        # add, never repurpose — a new count-shaped route gets an entry
        assert set(COUNT_SUBJECTS) == {"late_orders", "inventory", "machine_count"}

    def test_a_re_asked_count_really_shortens_the_answer(self, explainer):
        full = TemplateRenderer().render(
            _dispatch(explainer, parsed("which orders are late",
                                        Intent.LATE_ORDERS)).bundle)
        again = TemplateRenderer().render(
            _dispatch(explainer, parsed("which orders are late", Intent.LATE_ORDERS),
                      _turns("late-orders")).bundle)
        assert len(again) < len(full)


# ===========================================================================
# (d) per-claim read-from attribution
# ===========================================================================

class _FakeToolbox:
    """Two calls, two disjoint record sets — so an answer-level copy and a
    per-claim attribution are visibly different things."""

    def __init__(self):
        self.consulted = ["rec-a1", "rec-a2", "rec-b1"]
        self.call_tallies = [
            ("lateness_set", {"rec-a1", "rec-a2"}, {2.0}, {}),
            ("cost_ledger", {"rec-b1"}, {370.83}, {}),
        ]
        self.count_profile = {2.0, 370.83}
        self.enumerated = []
        self._ex = None

    def fetch_source(self, rid):
        if rid not in self.consulted:
            return None
        return ("metric", {"record_id": rid, "name": "lateness_minutes",
                           "unit": "minutes", "value": 890.0})

    def labels_for(self, payload):
        return []


class TestPerClaimProvenance:
    def _verify(self, record_ids):
        from mre.modules.claim_verifier import verify_claim
        return verify_claim(
            DraftClaim(text="ORD-05 is 890 minutes late.", record_ids=record_ids,
                       kind=ClaimKind.FACT),
            toolbox=_FakeToolbox())

    def test_a_cited_claim_is_checked_against_ITS_OWN_records(self):
        """The defect: this used to be the answer-level consulted set on every
        claim — answer-level provenance wearing per-claim clothes, which looks
        like an attribution and cannot be wrong, so nobody checks it."""
        v = self._verify(["rec-b1"])
        assert v.consulted_record_ids == ["rec-b1"]
        assert "rec-a1" not in v.consulted_record_ids

    def test_two_claims_in_one_answer_carry_DIFFERENT_provenance(self):
        a = self._verify(["rec-a1"])
        b = self._verify(["rec-b1"])
        assert a.consulted_record_ids != b.consulted_record_ids
        assert a.read_from != b.read_from

    def test_read_from_names_the_READINGS_not_the_record_ids(self):
        assert self._verify(["rec-b1"]).read_from == ["cost_ledger"]
        assert self._verify(["rec-a2"]).read_from == ["lateness_set"]
        assert self._verify(["rec-a1", "rec-b1"]).read_from == [
            "lateness_set", "cost_ledger"]

    def test_an_UNCITED_claim_is_honestly_scoped_to_everything_read(self):
        """Not a fudge: a claim that cites nothing really is checked against the
        whole consulted set, and saying so is the accurate label."""
        v = self._verify([])
        assert set(v.consulted_record_ids) == {"rec-a1", "rec-a2", "rec-b1"}
        assert set(v.read_from) == {"lateness_set", "cost_ledger"}

    def test_the_ledger_carries_the_per_claim_provenance(self):
        answer = SynthesisAnswer(question="q", claims=[
            VerifiedClaim(text="one", status=ClaimStatus.VERIFIED,
                          kind=ClaimKind.FACT, cited_record_ids=["rec-a1"],
                          consulted_record_ids=["rec-a1"],
                          read_from=["lateness_set"]),
            VerifiedClaim(text="two", status=ClaimStatus.INTERPRETIVE,
                          kind=ClaimKind.CONCLUSION, cited_record_ids=["rec-b1"],
                          consulted_record_ids=["rec-b1"],
                          read_from=["cost_ledger"]),
        ])
        rows = SynthesisProvenance.of(answer).claims
        assert [r["read_from"] for r in rows] == [["lateness_set"], ["cost_ledger"]]
        assert [r["consulted"] for r in rows] == [["rec-a1"], ["rec-b1"]]

    def test_prove_it_shows_the_readings_behind_THAT_sentence(self, explainer):
        claim = VerifiedClaim(
            text="Setup is the larger share.", status=ClaimStatus.INTERPRETIVE,
            kind=ClaimKind.CONCLUSION, consulted_record_ids=["rec-b1"],
            read_from=["cost_ledger", "lateness_set"])
        out = TemplateRenderer().render(
            explainer.route("prove-it", {"question": "prove it",
                                         "claim": claim.model_dump(mode="json")}))
        assert "Read from: cost_ledger, lateness_set." in out
