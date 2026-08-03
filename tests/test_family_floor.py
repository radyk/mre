"""THE FLOOR IS FAMILY-SCOPED — the founder listening round (Session 4A.y).

The listening docket (4A.x) built a mobility premise check and wired it to
`why-here`, which is where its four specimens landed. The founder then used the
product, and the same family of question landed somewhere else:

  F1  "why cant this be moved" [ORD-000128 op20 selected] -> what-would-change,
      answered the EARLIER side with no premise correction and no disclosure,
      while "is this stuck" one turn later -> why-here and produced the full
      R-LD3/R-LD4 shape. Same family, opposite outcomes, decided by the route.

  F2  "why is ORD-000126 op30 on CUT-01" — op30 is on FINISH-01, and the system
      had said so two answers earlier. Instead of the 4B.13 correction it
      CONFIRMED the false placement, rendering op10's decision record under the
      sentence "This is about op30 on CUT-01; the evidence below is that step's
      own assignment decision".

  F3  "when does ORD-000126 op30 finish" printed no interpreted-as block, in
      the cockpit AND in the exam report: both renderers gate the block on the
      question having been REWRITTEN, and a grain disclosure needs no rewrite.

  F4  "why is this bar trapped here" reached why-here — the floor's own route —
      and got the plain uncorrected chain, because "trapped" was not in the
      vocabulary.

  F5  "Same answer as a moment ago —" prefixed an answer about ORD-000073 when
      the previous question had been about ORD-000128. Different subject,
      different answer, detector fired on the question's TEXT alone.

THE CENSUS THAT OPENED ITEM 1, measured on the demo board `rolling-db5395dc-2ae`
through the live parse, 18 phrasings a planner might type:

    route               reached   floor at HEAD   floor after
    why-here                 11        6 of 11        11 of 11
    frozen                    5        0 of 5          5 of 5
    what-would-change         2        0 of 2          2 of 2

Six of the twelve HEAD misses were the VOCABULARY (Item 4) and six were the
ROUTE SCOPE (Item 1); one phrasing failed both. The full table and every
verbatim answer are in `docs/closeouts/4a-family-floor.md`.

WHAT IS AND IS NOT UNDER TEST. The world is `test_why_here_route`'s, for the
same reason the docket's guards use it: what is under test is the reasoning,
the disclosure and the words a planner reads — not the solver and not the
pricer. Nothing here prices.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from mre.contracts.parse import (
    Intent,
    MoveDirection,
    ParsedQuestion,
    SubjectKind,
)
from mre.modules import mobility_premise as mp
from mre.modules.explainer import Explainer
from mre.modules.interpreter import (
    _MOBILITY_FAMILY_INTENTS,
    _same_subject,
    bundle_repeat,
)
from mre.modules.renderers import TemplateRenderer

from tests.parse_doubles import parsed, resolve
from tests.test_why_here_route import _Index, _Store, _world

from mre.modules.interpreter import dispatch


#: The names the world's two machines answer to. Kept beside the world that
#: uses them so a rename cannot silently make `_machine_exists` say "no such
#: machine" and route every premise correction down the wrong branch.
_MACHINE_REFS = {"res-cut": "CUT-01", "res-paint": "PAINT-01"}


def _world_with_refs(**kw):
    """`test_why_here_route`'s world, plus the two things the premise machinery
    reads and that world never needed: `external_refs` on the RESOURCE entities
    (so `_machine_exists` can tell a mistyped name from a real one) and one
    assignment Decision per placement (so the BINDING SITE has records to bind,
    which is the whole of Item 2's second layer)."""
    reader = _world(**kw)
    for r in reader.iter_entities("resource"):
        r["external_refs"] = [{"type": "resource_id",
                               "value": _MACHINE_REFS[r["id"]]}]
    return reader


class _DecisionIndex:
    """One assignment Decision per operation, each naming its own operation —
    which is exactly the shape that made F2 possible: op10's record and op20's
    record are both "about ORD-000013 on a machine", and only the operation
    subject separates them."""

    _RECORDS = [
        {"record_type": "decision", "decision_type": "assignment",
         "record_id": "dec-13-10", "driver": "COST_TRADEOFF",
         "chosen": {"resource_id": "res-cut"}, "alternatives": [],
         "subjects": [{"entity_type": "operation", "entity_id": "op-13-10"}]},
        {"record_type": "decision", "decision_type": "assignment",
         "record_id": "dec-13-20", "driver": "NO_ALTERNATIVE",
         "chosen": {"resource_id": "res-paint"}, "alternatives": [],
         "subjects": [{"entity_type": "operation", "entity_id": "op-13-20"}]},
    ]

    _all_evidence: list = []

    def lineage_walk(self, *_a, **_k):
        return [dict(r) for r in self._RECORDS]

    def all_findings(self, *_a, **_k):
        return []


@pytest.fixture
def ex():
    return Explainer(_Store(_world_with_refs()), _DecisionIndex(),
                     snapshot_id="snap-test")


def _dispatched(explainer, p: ParsedQuestion, **context):
    """The REAL dispatch over a REALLY-RESOLVED parse. 4B.21 §5a.78: a guard
    that supplies its own arguments proves the assembler, not the path."""
    return dispatch(explainer, resolve(p, explainer, context or {}),
                    context=context or {})


def _text(explainer, p: ParsedQuestion, **context) -> str:
    return TemplateRenderer().render(_dispatched(explainer, p, **context).bundle)


#: The correction, in either shape it can arrive in: `why-here` renders it
#: inline as a two-direction answer, every other family member as a lead.
_CORRECTED = ("It can be moved", "On the premise first",
              "\"can't be moved\" is fair", "I can't tell you whether")


def _has_correction(text: str) -> bool:
    return any(m in text for m in _CORRECTED)


# ===========================================================================
# ITEM 1 — THE FLOOR ATTACHES TO THE FAMILY, NOT TO A ROUTE
# ===========================================================================

class TestTheFamilyIsTheScope:

    def test_the_family_is_the_three_routes_the_census_measured(self):
        """Named rather than derived: the set is a MEASUREMENT (18 phrasings on
        the demo board), and a set computed from something else would drift
        away from what was measured without anyone noticing."""
        assert _MOBILITY_FAMILY_INTENTS == {
            Intent.WHY_HERE, Intent.WHAT_WOULD_CHANGE, Intent.FROZEN}

    @pytest.mark.parametrize("intent", [
        Intent.WHY_HERE, Intent.WHAT_WOULD_CHANGE, Intent.FROZEN])
    def test_every_family_route_runs_the_premise_check(self, ex, intent):
        """F1's fix, stated as the invariant: which route answers is a MODEL's
        decision and is history-sensitive, so the check cannot live on one."""
        p = parsed("why cant this be moved", intent,
                   pointed=(SubjectKind.ORDER,))
        d = _dispatched(ex, p, selection={"order": "ORD-000013",
                                          "machine": "PAINT-01", "op_seq": 20})
        kf = d.bundle.key_facts
        assert kf.get("mobility") or kf.get("mobility_lead"), \
            f"{intent.value} answered a mobility question with no premise check"

    def test_the_non_why_here_members_render_the_correction_as_a_lead(self, ex):
        p = parsed("why cant this be moved", Intent.WHAT_WOULD_CHANGE,
                   pointed=(SubjectKind.ORDER,))
        text = _text(ex, p, selection={"order": "ORD-000013",
                                       "machine": "PAINT-01", "op_seq": 20})
        assert "On the premise first" in text

    def test_the_lead_never_claims_what_follows_it_is_about(self, ex):
        """`why-here`'s inline correction ends "and that is what I've explained
        below", which is true of `why-here` and false of the other two. Pasting
        it onto them would be this round's own disease."""
        p = parsed("why cant this be moved", Intent.FROZEN,
                   pointed=(SubjectKind.ORDER,))
        text = _text(ex, p, selection={"order": "ORD-000013",
                                       "machine": "PAINT-01", "op_seq": 20})
        assert "explained below" not in text

    def test_the_lead_names_the_operation_it_assessed(self, ex):
        """`frozen` answers at ORDER grain and the premise is about ONE BAR, so
        two grains share one answer. The lead names its own subject, which is
        what keeps that honest rather than ambiguous."""
        p = parsed("why cant this be moved", Intent.FROZEN,
                   pointed=(SubjectKind.ORDER,))
        text = _text(ex, p, selection={"order": "ORD-000013",
                                       "machine": "PAINT-01", "op_seq": 20})
        assert "ORD-000013 op20" in text

    def test_a_non_family_route_is_untouched(self, ex):
        """The floor may only ever ADD to a route that was going to run. A
        mobility-sounding question that landed elsewhere gets nothing."""
        p = parsed("why cant this be moved", Intent.ORDER_SCHEDULE,
                   pointed=(SubjectKind.ORDER,))
        d = _dispatched(ex, p, selection={"order": "ORD-000013", "op_seq": 20})
        assert "mobility_lead" not in (d.bundle.key_facts or {})

    def test_an_ordinary_question_on_a_family_route_gets_no_lead(self, ex):
        p = parsed("why is ORD-000013 op20 here", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        text = _text(ex, p)
        assert "On the premise first" not in text


class TestTheStatedDirectionIsNotRegressed:
    """The founder's round also produced a CORRECT answer — "why cant this move
    later" priced the later move. A stated direction assumes nothing, so it is
    owed no premise correction and no disclosure, and this is the guard that
    says so."""

    @pytest.mark.parametrize("q", [
        "why cant this move later", "why cant this be moved earlier",
        "why wont it budge sooner", "why cant this be pushed out"])
    def test_a_stated_direction_suppresses_the_floor(self, ex, q):
        assert mp.states_direction(q)
        p = parsed(q, Intent.WHAT_WOULD_CHANGE, orders=("ORD-000013",),
                   op_seq=20)
        d = _dispatched(ex, p)
        assert "mobility_lead" not in (d.bundle.key_facts or {})
        assert "read as EARLIER" not in d.note

    def test_a_named_target_is_a_stated_direction(self, ex):
        p = parsed("can this move to Friday", Intent.WHAT_WOULD_CHANGE,
                   orders=("ORD-000013",), op_seq=20,
                   move_direction=MoveDirection.UNSTATED, move_target="Friday")
        d = _dispatched(ex, p)
        assert "mobility_lead" not in (d.bundle.key_facts or {})

    def test_the_planners_words_decide_and_not_the_parse(self, ex):
        """MEASURED THIS ROUND: "this cant move can it" came back from the live
        parse with `move_direction=EARLIER` — a direction nobody stated. Trusting
        that field as a report of what was SAID skipped the check on exactly the
        question it exists for."""
        assert not mp.states_direction("this cant move can it")
        p = parsed("this cant move can it", Intent.WHAT_WOULD_CHANGE,
                   orders=("ORD-000013",), op_seq=20,
                   move_direction=MoveDirection.EARLIER)
        d = _dispatched(ex, p)
        assert d.bundle.key_facts.get("mobility_lead") is not None
        assert "read as EARLIER" in d.note

    def test_an_assumed_direction_is_never_disclosed_over_a_later_answer(self, ex):
        """A disclosure that states the WRONG direction is worse than the
        silence it replaces (R-LD2's own words)."""
        p = parsed("is this bar immovable", Intent.WHAT_WOULD_CHANGE,
                   orders=("ORD-000013",), op_seq=20,
                   move_direction=MoveDirection.LATER)
        assert "read as EARLIER" not in _dispatched(ex, p).note


# ===========================================================================
# ITEM 2 — THE PREMISE IS VERIFIED AT THE GRAIN IT WAS ASSERTED AT
# ===========================================================================

class TestTheGrainTruePlacementPremise:

    def test_an_op_grain_false_premise_is_corrected(self, ex):
        """F2, the round's highest-severity specimen. op20 is on PAINT-01;
        asking about it on CUT-01 (where op10 really is) must be corrected, not
        confirmed off op10's record."""
        bad = ex._verify_placement_premise("ORD-000013", "CUT-01", 20)
        assert bad is not None
        assert bad["kind"] == "wrong_machine_for_step"
        assert bad["claimed_op_seq"] == 20
        assert bad["actual_machines"] == ["PAINT-01"]

    def test_the_correction_speaks_at_the_asked_grain(self, ex):
        p = parsed("why is ORD-000013 op20 on CUT-01", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000013",), machines=("CUT-01",), op_seq=20)
        text = _text(ex, p)
        assert "ORD-000013 op20 isn't on CUT-01" in text
        assert "PAINT-01" in text

    def test_an_order_grain_false_premise_is_unchanged(self, ex):
        """4B.13's own specimen shape. A question that named no step is still
        corrected about the whole order, in the words it always used.
        ORD-000099 runs only on CUT-01, so PAINT-01 is a real machine carrying
        none of its work — the mistyped-off-the-board case, not the
        no-such-machine one."""
        bad = ex._verify_placement_premise("ORD-000099", "PAINT-01")
        assert bad is not None
        assert bad["kind"] == "wrong_machine"
        assert bad.get("claimed_op_seq") is None
        assert bad["claimed_machine_exists"] is True
        p = parsed("why is ORD-000099 on PAINT-01", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000099",), machines=("PAINT-01",))
        assert "ORD-000099 isn't on PAINT-01" in _text(ex, p)

    def test_a_machine_that_does_not_exist_keeps_its_own_correction(self, ex):
        """The third shape, unchanged: a stranger who mistypes a name entirely
        needs to be told which kind of wrong they were."""
        bad = ex._verify_placement_premise("ORD-000013", "HEAT-02", 20)
        assert bad is not None and bad["claimed_machine_exists"] is False
        p = parsed("why is ORD-000013 op20 on HEAT-02", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000013",), machines=("HEAT-02",), op_seq=20)
        assert "no machine called HEAT-02" in _text(ex, p)

    def test_a_TRUE_op_grain_premise_fires_nothing(self, ex):
        """The control that matters most: a correction that fires on a true
        premise is a worse defect than the one it was built for."""
        assert ex._verify_placement_premise("ORD-000013", "PAINT-01", 20) is None
        assert ex._verify_placement_premise("ORD-000013", "CUT-01", 10) is None

    def test_a_true_op_grain_question_still_answers_the_cause(self, ex):
        p = parsed("why is ORD-000013 op20 on PAINT-01", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000013",), machines=("PAINT-01",), op_seq=20)
        text = _text(ex, p)
        assert "isn't on" not in text
        assert "This is about op20 on PAINT-01" in text

    def test_a_step_the_order_does_not_have_is_its_own_correction(self, ex):
        """A DIFFERENT falsehood from the wrong machine, and telling the planner
        "it isn't on PAINT-01" would itself be false."""
        bad = ex._verify_placement_premise("ORD-000013", "PAINT-01", 99)
        assert bad is not None and bad["kind"] == "no_such_step"
        assert 20 in bad["known_op_seqs"]
        p = parsed("why is ORD-000013 op99 on PAINT-01", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000013",), machines=("PAINT-01",), op_seq=99)
        text = _text(ex, p)
        assert "has no op99" in text
        assert "isn't on PAINT-01" not in text

    def test_an_unreadable_grain_never_refutes(self, ex):
        """4B.23's fail-safe rule: what cannot be checked claims nothing."""
        assert ex._verify_placement_premise("ORD-000013", "PAINT-01",
                                            "twenty") is None


class TestTheBindingSiteNeverBindsAnotherGrain:
    """LAYER TWO. F2 showed one layer stitching a name onto a record, so the
    citation is guarded independently of the premise."""

    def test_the_named_step_binds_its_OWN_decision(self, ex):
        bundle = ex.route("why-on-machine",
                          {"question": "why is ORD-000013 op20 on PAINT-01",
                           "order": "ORD-000013", "machine": "PAINT-01",
                           "op_seq": 20})
        kf = bundle.key_facts
        assert kf["scoped_to_operation"] and not kf["grain_unmatched"]
        assert [r["record_id"] for r in bundle.ordered_records] == ["dec-13-20"]

    def test_a_different_steps_record_is_never_presented_as_this_ones(self, ex):
        """The assertion that would have caught F2 at the citation layer: every
        record cited under an op-scoped claim belongs to that op."""
        bundle = ex.route("why-on-machine",
                          {"question": "why is ORD-000013 op20 on PAINT-01",
                           "order": "ORD-000013", "machine": "PAINT-01",
                           "op_seq": 20})
        assert bundle.ordered_records
        for rec in bundle.ordered_records:
            assert ex._decision_op_seq(rec) == 20

    def test_a_named_step_with_no_decision_of_its_own_says_so(self, ex):
        """The residue after Item 2's first layer: the premise HOLDS at the
        asked grain and the step still has no assignment Decision of its own.
        Nothing is bound, and the answer says why rather than presenting the
        machine-matched record from another step — which is precisely the
        sentence F2 produced."""
        ex._index._RECORDS = [r for r in _DecisionIndex._RECORDS
                              if r["record_id"] != "dec-13-20"]
        bundle = ex.route("why-on-machine",
                          {"question": "why is ORD-000013 op20 on PAINT-01",
                           "order": "ORD-000013", "machine": "PAINT-01",
                           "op_seq": 20})
        assert bundle.key_facts["grain_unmatched"] is True
        text = TemplateRenderer().render(bundle)
        assert "won't present it as this one's" in text
        assert "This is about op20" not in text


# ===========================================================================
# ITEM 3 — THE DISCLOSURE IS NOT GATED ON THE REWRITE
# ===========================================================================

class TestTheDisclosureIsRendered:

    def test_a_no_rewrite_grain_question_still_carries_a_note(self, ex):
        """F3's own specimen shape: the planner named the order exactly, so
        nothing was rewritten — and the note says the route answered at order
        level. Gating on the rewrite hid exactly the disclosures 4A.x added."""
        p = parsed("when does ORD-000013 op20 finish", Intent.ORDER_SCHEDULE,
                   orders=("ORD-000013",), op_seq=20)
        d = _dispatched(ex, p)
        assert d.routed_question == p.question, "nothing was rewritten"
        assert "order level" in d.note, \
            "the note exists; the renderers must not hide it"

    @staticmethod
    def _transcript(question, resolved, note):
        from mre.ai_exam.report import render_transcript
        from mre.ai_exam.runner import ExamResult, TurnRecord

        t = TurnRecord(lineno=1, question=question, selection={})
        t.resolved_question = resolved
        t.resolution_note = note
        t.route = "order-schedule"
        return render_transcript(ExamResult(
            target_label="t", snapshot_id="s", llm_mode="deterministic",
            turns=[t]))

    def test_the_exam_report_prints_a_note_with_no_rewrite(self):
        q = "when does ORD-000126 op30 finish"
        out = self._transcript(q, q, (            # resolved == question
            "answered for the whole of ORD-000126 — you named op30 and this "
            "route answers at order level"))
        assert "order level" in out, \
            "report.py hid a resolution note because nothing was rewritten"

    def test_the_exam_report_still_prints_a_rewritten_question(self):
        out = self._transcript("and what about it?", "why is ORD-000012 late?",
                               "resolved against ORD-000012")
        assert "why is ORD-000012 late?" in out
        assert "resolved against ORD-000012" in out

    def test_a_turn_with_no_note_and_no_rewrite_prints_nothing(self):
        out = self._transcript("how many orders are late",
                               "how many orders are late", "")
        assert "interpreted as" not in out


# ===========================================================================
# ITEM 4 — THE VOCABULARY, WIDENED WHERE IT WAS MEASURED SHORT
# ===========================================================================

class TestTheFloorVocabulary:

    @pytest.mark.parametrize("q", [
        "why is this bar trapped here", "why is this trapped",
        "why is this wedged in here", "why is this bar pinned down here",
        "nothing can move this can it"])
    def test_the_measured_misses_are_recognised(self, q):
        assert mp.asks_about_moving(q)

    def test_jammed_is_excluded_and_that_is_a_decision(self):
        """A jam is a thing that happens to a MACHINE. Naming the exclusion
        keeps it a ruling rather than an oversight — and it is the one phrasing
        of the eighteen that still gets no premise check."""
        assert not mp.asks_about_moving("why is this jammed here")
        assert not mp.asks_about_moving("is CUT-01 jammed")

    def test_pinned_alone_is_not_a_mobility_claim(self):
        """4B.28 gave `frozen` the word "pinned", where it names an AUTHORITY a
        planner releases. "Why is ORD-000001 pinned?" is a true question with a
        true answer and nothing to correct."""
        assert not mp.asks_about_moving("why is ORD-000001 pinned")
        assert mp.asks_about_moving("why is ORD-000001 pinned down here")

    @pytest.mark.parametrize("q", [
        "why is this here", "what's holding it up", "why the wait",
        "when does ORD-000013 op20 finish", "how busy is PAINT-01"])
    def test_an_ordinary_question_is_not_in_the_family(self, q):
        assert not mp.asks_about_moving(q)

    def test_a_non_mobility_use_of_stuck_reaches_no_premise_check(self, ex):
        """THE TRUE-NEGATIVE CONTROL the brief asked for, asserted at the REAL
        gate. "the data seems stuck in December" matches the vocabulary — and
        the vocabulary is only half the gate: the floor also needs a
        family INTENT. A keyword test that tried to judge what a sentence is
        ABOUT would be the deterministic classifier R-AI5 forbids."""
        p = parsed("the data seems stuck in December", Intent.DATA_PROBLEMS)
        d = _dispatched(ex, p)
        assert "mobility_lead" not in (d.bundle.key_facts or {})
        assert not _has_correction(TemplateRenderer().render(d.bundle))


# ===========================================================================
# ITEM 5 — A REPEAT IS THE SAME QUESTION ABOUT THE SAME THING
# ===========================================================================

class _Bundle:
    def __init__(self):
        self.key_facts: dict = {}


def _repeat_of(prior_turns, question, order, op_seq, route=Intent.WHY_HERE):
    b = _Bundle()
    p = parsed(question, route, pointed=(SubjectKind.ORDER,))
    bundle_repeat(b, {"history": prior_turns}, p,
                  subject={"order": order, "op_seq": op_seq})
    return b.key_facts.get("repeat")


def _turn(question, order, op_seq, route="why-here"):
    return {"question": question, "route": route, "order": order,
            "op_seq": op_seq}


class TestTheRepeatDetectorIsSubjectAware:

    def test_the_same_question_about_a_different_order_is_not_a_repeat(self):
        """F5, measured live at HEAD on the demo board: three bars asked the
        same thing in sequence, and two answers opened by telling the planner
        nothing had changed."""
        prior = [_turn("why cant this be moved", "ORD-000128", 20)]
        assert _repeat_of(prior, "why cant this be moved",
                          "ORD-000073", 10) is None

    def test_the_same_question_about_a_different_STEP_is_not_a_repeat(self):
        prior = [_turn("why cant this be moved", "ORD-000073", 10)]
        assert _repeat_of(prior, "why cant this be moved",
                          "ORD-000073", 20) is None

    def test_a_genuine_re_ask_still_fires(self):
        """The behaviour that was RIGHT and must stay: the founder's own second
        ask of ORD-000073."""
        prior = [_turn("why cant this be moved", "ORD-000073", 10)]
        assert _repeat_of(prior, "why cant this be moved",
                          "ORD-000073", 10) == 1

    def test_a_turn_that_does_not_report_a_grain_compares_on_the_order(self):
        """Absent means UNKNOWN, and unknown does not refute — else an older
        client's silence would kill the rider this exists to preserve."""
        prior = [{"question": "why cant this be moved", "route": "why-here",
                  "order": "ORD-000073"}]
        assert _repeat_of(prior, "why cant this be moved",
                          "ORD-000073", 10) == 1

    def test_a_subjectless_question_asked_twice_is_a_repeat(self):
        prior = [_turn("how many orders are late", None, None,
                       route="late-orders")]
        assert _repeat_of(prior, "how many orders are late", None, None,
                          route=Intent.LATE_ORDERS) == 1

    def test_same_subject_different_question_is_not_a_repeat(self):
        prior = [_turn("why cant this be moved", "ORD-000073", 10)]
        assert _repeat_of(prior, "how long does this take",
                          "ORD-000073", 10) is None

    def test_the_comparison_itself(self):
        assert _same_subject({"order": "A", "op_seq": 10}, "A", 10)
        assert _same_subject({"order": "A", "op_seq": "10"}, "A", 10)
        assert not _same_subject({"order": "A", "op_seq": 10}, "A", 20)
        assert not _same_subject({"order": "A", "op_seq": 10}, "B", 10)
        assert _same_subject({"order": "A"}, "A", 10)          # grain unknown
        assert _same_subject({"order": None, "op_seq": None}, None, None)


# ===========================================================================
# THE PREMISE TESTS — the fixture really is what the guards above assume
# ===========================================================================

class TestTheFixturesPremises:

    def test_op20_really_is_on_paint_01_and_op10_on_cut_01(self, ex):
        rows = {r["op_seq"]: r["machine"] for r in ex._order_rows("ORD-000013")}
        assert rows[10] == "CUT-01"
        assert rows[20] == "PAINT-01"

    def test_the_order_really_has_no_op99(self, ex):
        seqs = {r["op_seq"] for r in ex._order_rows("ORD-000013")}
        assert 99 not in seqs

    def test_the_fixture_bar_really_has_a_mobility_verdict(self, ex):
        v = ex.mobility_verdict("ORD-000013", "PAINT-01", 20)
        assert v is not None and v["verdict"] in {
            mp.VERDICT_HELD, mp.VERDICT_BOXED_IN, mp.VERDICT_UNDECIDABLE,
            mp.VERDICT_LATER_OPEN, mp.VERDICT_EARLIER_OPEN}

    def test_the_verdict_is_the_same_object_why_here_computes(self, ex):
        """ONE DEFINITION: `mobility_verdict` wraps `_mobility_facts`, so the
        lead and `why-here`'s inline paragraph can never disagree about whether
        one bar can move."""
        p = parsed("why cant this be moved", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        inline = _dispatched(ex, p).bundle.key_facts.get("mobility")
        outside = ex.mobility_verdict("ORD-000013", "PAINT-01", 20)
        assert inline is not None and outside is not None
        assert inline["verdict"] == outside["verdict"]
