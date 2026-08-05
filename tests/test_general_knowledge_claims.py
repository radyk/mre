"""R-TG1 — THE GENERAL-KNOWLEDGE CLAIM CLASS (Session 4A teaching-graft (a)).

Written from the ruling, not from the implementation.

WHAT THE RULING SAYS. Open synthesis draws three kinds of sentence, and until
this session only two of them had anywhere to live. A BOARD CLAIM is about this
plan and is verified claim by claim against the evidence store. A BOARD-DERIVED
INFERENCE reasons from cited reads and is labeled as a reading. A
GENERAL-KNOWLEDGE CLAIM is domain knowledge — how scheduling, optimization and
plants behave in general — and it is UNVERIFIABLE BY DESIGN: the verifier must
never fail it and must never let it pass unlabeled.

Measured at HEAD before any of this existed, on the demo board: SEVEN
general-knowledge sentences shipped across seven synthesis answers, every one of
them wearing a marker that asserts board grounding. The class exists to end that.

THE TWO DIRECTIONS, which are the item's core and are the reason it is not merely
a new label:

  (i)  A claim that names an order, a machine, a time, money, or a figure this
       run computed may NOT wear the label — whatever the model proposed. It is
       refused and verified as an ordinary board claim. Without this the class is
       a verification escape hatch, the exact inverse abuse.
  (ii) A claim that cites no record, grounds nothing and carries no board content
       is not shippable unless it was PROPOSED as general knowledge. It is
       dropped. No third state — that third state is what shipped the seven.

Both directions turn on ONE deterministic predicate (``gk_disqualifiers``), read
forwards for (i) and backwards for (ii), so they cannot drift apart.

WHAT THIS FILE DOES NOT PROVE. That the model proposes the class WELL — that is
the prompt's job and the exam bank's measurement. These guards prove that the
proposal is checked, in both directions, and that a checked proposal renders as
what it is.
"""
from __future__ import annotations

import json

import pytest

from mre.contracts.parse import Intent
from mre.contracts.synthesis import ClaimKind, ClaimStatus, DraftClaim
from mre.modules.claim_verifier import gk_disqualifiers, verify_claim, verify_draft
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.evidence_tools import EvidenceToolbox
from mre.modules.explainer import Explainer
from mre.modules.interpreter import AnswerMemory, forget_deliveries, run_ask
from mre.modules.renderers import TemplateRenderer
from tests.parse_doubles import ScriptedParser, claim, claims, parsed, synthesizer_with
from tests.test_synthesis import _late_ids, _records, _Store

# A sentence of real domain knowledge, carrying nothing of anybody's board.
GENERAL = "Tardiness objectives tend to give weak lower bounds."


@pytest.fixture()
def world(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with open(runs / "t.jsonl", "w", encoding="utf-8") as fh:
        for r in _records():
            fh.write(json.dumps(r) + "\n")
    return Explainer(_Store(), EvidenceIndex().build(runs), snapshot_id="snap-t")


@pytest.fixture()
def read_box(world):
    """A toolbox that has already read the world, the way the loop would."""
    box = EvidenceToolbox(world)
    box.call("lateness_set")
    box.call("machine_occupancy", {"machine": "CUT-01"})
    return box


def _ids(box, tool, args=None, row=0):
    return box.call(tool, args or {}).rows[row]["record_ids"]


def _verify(text, box, *, kind=ClaimKind.GENERAL_KNOWLEDGE, record_ids=()):
    return verify_claim(DraftClaim(text=text, record_ids=list(record_ids),
                                   kind=kind), toolbox=box)


# ===========================================================================
# The class itself
# ===========================================================================

class TestTheClass:
    def test_a_clean_proposal_is_labeled_not_verified(self, read_box):
        """The status is not a verdict about grounding — it is a statement about
        what the sentence is ABOUT. It must never be VERIFIED (nothing checked it)
        and never FAILED (nothing could)."""
        v = _verify(GENERAL, read_box)
        assert v.status is ClaimStatus.GENERAL_KNOWLEDGE

    def test_it_carries_no_provenance_at_all(self, read_box):
        """A general line rests on nothing of this plan's, so the durable record
        must not say it was read from four tool calls. `base` would have carried
        the whole consulted set, because an uncited claim is normally checked
        against everything read — and this one was checked against nothing."""
        v = _verify(GENERAL, read_box)
        assert v.cited_record_ids == []
        assert v.consulted_record_ids == []
        assert v.read_from == []
        assert v.sample_note == ""

    def test_it_is_counted_apart_from_interpretive(self, read_box):
        """An interpretive claim is a reading OF THIS PLAN that could not be
        proven; a general one is not about this plan at all. Folding them puts
        the two back in the single bucket this class exists to split."""
        answer = verify_draft("why", [
            DraftClaim(text="ORD-01 finished 890 minutes past its due date.",
                       record_ids=_ids(read_box, "lateness_set")),
            DraftClaim(text=GENERAL, kind=ClaimKind.GENERAL_KNOWLEDGE),
        ], toolbox=read_box)
        assert len(answer.general_knowledge) == 1
        assert len(answer.interpretive) == 0
        assert answer.counts()["general_knowledge"] == 1

    def test_it_is_not_proven_support_for_the_rest(self, read_box):
        """A cut claim is load-bearing when nothing VERIFIED survives. A general
        line is not verified support — it grounds nothing — so an answer made of
        general knowledge plus a cut fact must still say something was cut."""
        answer = verify_draft("why", [
            DraftClaim(text=GENERAL, kind=ClaimKind.GENERAL_KNOWLEDGE),
            DraftClaim(text="ORD-01 is 250 minutes late.",
                       record_ids=_ids(read_box, "lateness_set")),
        ], toolbox=read_box)
        assert answer.cut and answer.cut[0].load_bearing


# ===========================================================================
# ENFORCEMENT DIRECTION (i) — the label is refused to a board sentence
# ===========================================================================

class TestDirectionOne:
    @pytest.mark.parametrize("text", [
        "ORD-01 is the kind of order that tends to run late.",
        "CUT-01 is the kind of machine that becomes a bottleneck.",
    ])
    def test_a_named_entity_refuses_the_label(self, read_box, text):
        v = _verify(text, read_box)
        assert v.status is not ClaimStatus.GENERAL_KNOWLEDGE

    def test_a_figure_this_run_computed_refuses_the_label(self, read_box):
        """THE ESCAPE-HATCH CLAUSE. "890 minutes is a typical amount of lateness"
        is a general sentence right up until 890 is what ORD-01 measures, at which
        point it is an unverified board claim wearing a label that forbids
        checking it."""
        v = _verify("890 minutes of lateness is typical for work of this shape.",
                    read_box)
        assert v.status is not ClaimStatus.GENERAL_KNOWLEDGE

    def test_a_citation_refuses_the_label(self, read_box):
        """Claiming a record backs the sentence IS claiming the sentence is about
        this plan. Nothing general needs one."""
        v = _verify(GENERAL, read_box,
                    record_ids=_ids(read_box, "lateness_set"))
        assert v.status is not ClaimStatus.GENERAL_KNOWLEDGE

    def test_a_refused_proposal_is_verified_the_ordinary_way(self, read_box):
        """Refusal is not a cut. The claim is checked exactly as it would have
        been before the class existed — which is why over-refusing is the safe
        direction and under-refusing is the hatch."""
        ids = _ids(read_box, "lateness_set")
        as_gk = _verify("ORD-01 finished 890 minutes past its due date.", read_box,
                        record_ids=ids)
        as_fact = _verify("ORD-01 finished 890 minutes past its due date.",
                          read_box, kind=ClaimKind.FACT, record_ids=ids)
        assert as_gk.status is as_fact.status is ClaimStatus.VERIFIED

    def test_the_refusal_is_recorded_with_its_reason(self, read_box):
        """A disqualification that leaves no trace is a check nobody can audit."""
        v = _verify("ORD-01 is the kind of order that tends to run late.",
                    read_box)
        assert "general knowledge" in v.reason and "refused" in v.reason
        assert "ORD-01" in v.reason

    def test_the_predicate_is_shared_by_both_directions(self, read_box):
        """One predicate, read forwards and backwards. Two would drift."""
        box_scope_claim = DraftClaim(text="ORD-01 tends to run late.",
                                     kind=ClaimKind.GENERAL_KNOWLEDGE)
        from mre.modules.claim_verifier import _Scope, extract_assertions
        ex = read_box._ex
        scope = _Scope(read_box, list(read_box.consulted))
        assertions = extract_assertions(
            box_scope_claim.text,
            order_refs=getattr(ex, "_order_refs", {}) or {},
            machine_refs=getattr(ex, "_machine_refs", {}) or {},
            order_shapes=getattr(ex, "_order_shape_patterns", []) or [])
        assert gk_disqualifiers(box_scope_claim, assertions, scope, scope)
        assert not gk_disqualifiers(
            DraftClaim(text=GENERAL, kind=ClaimKind.GENERAL_KNOWLEDGE),
            [], scope, scope)


# ===========================================================================
# ENFORCEMENT DIRECTION (ii) — the third state is closed
# ===========================================================================

class TestDirectionTwo:
    def test_an_unlabeled_uncited_ungrounded_claim_is_dropped(self, read_box):
        """This is the sentence that shipped seven times at HEAD, labeled
        `[synthesis — read from: <ids>]` or `[synthesis — my reading]`, both of
        which assert it came out of this board's evidence."""
        v = _verify("Most real solvers settle for provably-good bounds.",
                    read_box, kind=ClaimKind.FACT)
        assert v.status is ClaimStatus.FAILED

    def test_a_conclusion_gets_no_exemption(self, read_box):
        """The escape hatch reopens if a conclusion is exempt: the model calls its
        general sentence a conclusion and ships it unlabeled, which is exactly
        what two of the four measured pure-domain sentences did."""
        v = _verify("Exact methods scale poorly on problems of this shape.",
                    read_box, kind=ClaimKind.CONCLUSION)
        assert v.status is ClaimStatus.FAILED

    def test_the_verifier_refutes_a_proposal_and_never_manufactures_one(
            self, read_box):
        """WHY IT IS A DROP AND NOT AN AUTO-LABEL. The verifier can prove the
        label's second half ("not a fact about this plan"); only the author can
        make the first ("this is how scheduling works"). "Things are pretty tight
        right now" carries no board content either, and it is a vague assertion
        about the plant, not domain knowledge — auto-labeling would call it
        one."""
        v = _verify("Things are pretty tight right now.", read_box,
                    kind=ClaimKind.FACT)
        assert v.status is ClaimStatus.FAILED

    def test_the_cut_says_which_kind_of_cut_it_was(self, world):
        """FOUND LIVE ON THE DEMO BOARD, IN THIS SESSION, AFTER THE FIX WENT IN.

        Direction (ii) cuts the tier's own honest limit statements — "whether a
        large gap here reflects a genuinely weak schedule versus a loose bound is
        something I cannot check against this run" — because a sentence about our
        epistemic position is neither a board claim nor domain knowledge. The
        answer then said "one step of my reasoning didn't hold up against the
        records", which is false in its first clause: the step never reached the
        records. A cut names WHY it was cut."""
        text, _ = _render(world, claims(
            claim(GENERAL, [], kind="general_knowledge"),
            claim("I cannot check that against this run.", [],
                  kind="conclusion")))
        assert "neither something I could check against your board nor general" \
            in text
        assert "didn't hold up against the records" not in text, (
            "an unplaceable sentence was reported as a failed grounding — the "
            "reasoning never reached the records to fail against them")

    def test_a_real_grounding_failure_still_says_so(self, world):
        """The other half: a genuine contradiction is the stronger fact and must
        keep its own line, including in an answer that also lost an unplaceable
        sentence."""
        ids = _late_ids(world)
        text, _ = _render(world, claims(
            claim(GENERAL, [], kind="general_knowledge"),   # survives, unverified
            claim("ORD-01 is 250 minutes late.", ids),      # CONTRADICTED -> cut
            claim("I cannot check that against this run.", [],
                  kind="conclusion")))                       # unplaceable -> cut
        assert "didn't hold up against the records" in text
        assert "neither something I could check against your board" not in text

    def test_a_claim_with_board_content_still_ships_as_a_reading(self, read_box):
        """The drop must not swallow the ordinary uncited inference. A conclusion
        that names what it is about is a reading of this plan and stays one."""
        v = _verify("ORD-01 is what the cutting line is queued behind.", read_box,
                    kind=ClaimKind.CONCLUSION)
        assert v.status is ClaimStatus.INTERPRETIVE

    def test_a_grounded_uncited_claim_still_ships(self, read_box):
        """"Verifies as a board claim" is one of the three legal outcomes. A claim
        that grounds against what the loop read but cites nothing is under-cited,
        not unshippable — cutting it teaches the model to say less rather than
        cite better."""
        v = _verify("ORD-01 finished 890 minutes past its due date.", read_box,
                    kind=ClaimKind.FACT)
        assert v.status is ClaimStatus.INTERPRETIVE


# ===========================================================================
# RENDERING — the label, both halves, and the footer
# ===========================================================================

def _render(world, *responses, session="gk"):
    # EACH RENDER HERE IS A FRESH CONVERSATION, and since W6 that is a claim the
    # product reads: the general-knowledge footer and the teaching invitation
    # are orientation and render on a conversation's FIRST synthesis answer
    # only. These tests share one session id against a process-wide memory, so
    # without this the second render in the file would be judged a follow-up and
    # the footer correctly withheld. Clearing is what a new conversation does.
    forget_deliveries(session)
    synth = synthesizer_with(list(responses))
    parser = ScriptedParser({})            # everything is UNMATCHED here
    res = run_ask(world, "why does this happen", parser=parser,
                  synthesizer=synth, session_id=session)
    return TemplateRenderer().render(res.bundle), res


class TestRendering:
    def test_the_label_names_both_halves(self, world):
        text, _ = _render(world, claims(claim(GENERAL, [], kind="general_knowledge")))
        assert "general knowledge" in text, "the label does not say what it is"
        assert "not a fact about this plan" in text, \
            "the label does not say what it is NOT — the half that was missing"

    def test_it_never_wears_a_board_marker(self, world):
        text, _ = _render(world, claims(claim(GENERAL, [], kind="general_knowledge")))
        assert "read from:" not in text
        assert "no record states this" not in text

    def test_the_footer_note_fires_once(self, world):
        text, _ = _render(world, claims(
            claim(GENERAL, [], kind="general_knowledge"),
            claim("Sequence-dependent setups reward grouping similar jobs.", [],
                  kind="general_knowledge")))
        assert text.count("Where a line is marked general knowledge") == 1

    def test_the_footer_note_is_absent_without_a_general_line(self, world):
        text, _ = _render(world, claims(
            claim("ORD-01 finished 890 minutes past its due date.",
                  _late_ids(world))))
        assert "Where a line is marked general knowledge" not in text

    def test_a_mixed_answer_labels_each_line_for_what_it_is(self, world):
        text, _ = _render(world, claims(
            claim("ORD-01 finished 890 minutes past its due date.",
                  _late_ids(world)),
            claim(GENERAL, [], kind="general_knowledge")))
        assert "[record:" in text, "the board claim lost its citation"
        assert "not a fact about this plan" in text, "the general line lost its label"

    def test_the_register_is_still_synthesis(self, world):
        """R-TG1 adds a CLAIM CLASS, not a rung. The answer is still the second
        tier's and still says so."""
        _, res = _render(world, claims(claim(GENERAL, [], kind="general_knowledge")))
        from mre.modules.explainer import register_of
        assert register_of(res.bundle) == "synthesis"

    def test_a_drill_down_onto_it_does_not_call_it_a_reading_of_the_plan(
            self, world):
        """`PROVE_IT_INTERPRETIVE_BARE` says "that part is my reading of the
        plan", which is false of a general line in its first clause. Answering a
        drill-down with a false account of what the sentence was would reopen at
        the drill-down exactly what the marker closes at the line."""
        from mre.contracts.parse import FollowupKind
        from mre.modules.interpreter import SynthesisMemory, dispatch
        memory = SynthesisMemory()
        synth = synthesizer_with([claims(claim(GENERAL, [],
                                               kind="general_knowledge"))])
        run_ask(world, "why does this happen", parser=ScriptedParser({}),
                synthesizer=synth, memory=memory, session_id="gk-drill")
        d = dispatch(world, parsed("prove it", Intent.UNMATCHED,
                                   followup_of=FollowupKind.PROVE_IT,
                                   confidence=0.9),
                     memory=memory, session_id="gk-drill")
        text = TemplateRenderer().render(d.bundle)
        assert "general scheduling knowledge" in text
        assert "my reading of the plan" not in text


# ===========================================================================
# CONTROLS — the machinery must be unreachable from everything else
# ===========================================================================

class TestControls:
    def test_an_all_board_answer_is_unchanged(self, world):
        """The control the ruling has to survive: an answer with no general line
        renders exactly as it did before the class existed."""
        ids = _late_ids(world)
        text, _ = _render(world, claims(
            claim("ORD-01 finished 890 minutes past its due date.", ids),
            claim("ORD-01 is what the cutting line is queued behind.", ids,
                  kind="conclusion")))
        assert "general knowledge" not in text
        assert "[record:" in text and "read from:" in text

    def test_a_contracted_route_never_renders_a_general_label(self, world):
        """Testimony is assembled by deterministic route code from this plan's own
        records. The general-knowledge machinery must be unreachable from it —
        there is no model drafting claims on that path at all."""
        res = run_ask(world, "why is ORD-01 late",
                      parser=ScriptedParser({"why is ORD-01 late": parsed(
                          "", Intent.LATE_ORDER, orders=("ORD-01",))}),
                      session_id="ctl")
        text = TemplateRenderer().render(res.bundle)
        assert "general knowledge" not in text
        assert "not a fact about this plan" not in text

    def test_the_kind_vocabulary_is_closed(self):
        """ADD, never repurpose. A fourth kind arriving without a ruling is what
        this asserts against."""
        assert {k.value for k in ClaimKind} == {
            "fact", "conclusion", "general_knowledge"}

    def test_the_status_vocabulary_is_closed(self):
        assert {s.value for s in ClaimStatus} == {
            "verified", "interpretive", "failed", "general_knowledge"}


# ===========================================================================
# THE R-OF1 RIDER — an outage card is not an answer
# ===========================================================================

class TestOutageIsNotAnAnswer:
    def _outage_turn(self, world, answers, session):
        """A SYNTHESIS-STAGE outage: the parse succeeded, the tier WAS called and
        could not reach its model. That is the card R-OF1 authored, in the
        `system` register — distinct from an unavailable synthesizer, which is
        the capability floor and a different card entirely."""
        from tests.parse_doubles import UnreachableSynthesizer
        return run_ask(world, "why does this happen", parser=ScriptedParser({}),
                       synthesizer=UnreachableSynthesizer(), session_id=session,
                       answer_memory=answers)

    def test_the_outage_card_is_in_the_system_register(self, world):
        from mre.modules.explainer import register_of
        answers = AnswerMemory()
        res = self._outage_turn(world, answers, "of1")
        assert register_of(res.bundle) == "system"

    def test_it_never_enters_answer_memory(self, world):
        """Nothing was read, nothing was reasoned — so nothing may ground a
        drill-down."""
        answers = AnswerMemory()
        self._outage_turn(world, answers, "of1-a")
        assert answers.last("of1-a", None) is None

    def test_it_does_not_erase_the_last_real_answer(self, world):
        """The sharper half. A drill-down after an outage must open the answer the
        planner is still looking at — not the card, and not nothing."""
        answers = AnswerMemory()
        run_ask(world, "why is ORD-01 late",
                parser=ScriptedParser({"why is ORD-01 late": parsed(
                    "", Intent.LATE_ORDER, orders=("ORD-01",))}),
                session_id="of1-b", answer_memory=answers)
        before = answers.last("of1-b", None)
        assert before is not None
        self._outage_turn(world, answers, "of1-b")
        after = answers.last("of1-b", None)
        assert after is not None and after["question"] == before["question"], (
            "the outage card displaced the last real answer — a drill-down would "
            "now ground a card whose content is that nothing was reached")

    def test_the_rule_is_keyed_on_the_register_not_a_route_name(self):
        """`system` is the vocabulary member that means "the product reporting on
        itself". A future card that earns it inherits the rule rather than having
        to remember it."""
        import inspect

        from mre.modules import interpreter
        src = inspect.getsource(interpreter.run_ask)
        assert 'register != "system"' in src, (
            "the rider is keyed on something other than the register — a route "
            "list has to be maintained and will be forgotten")
