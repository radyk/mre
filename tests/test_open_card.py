"""CU2 (Session 4B.5) — the OPEN DELTA CARD joins the resolution ladder.

THE FOUNDER'S FAILING EXCHANGE. With a priced delta card on screen — showing the
placement, the cost split, and the four orders it affects — the question "what
orders are affected in this move" parsed as `swap-move`: a route that weighs two
orders' slack against each other and has never heard of the card. The answer was
already computed and sitting in front of them, and the system went looking for a
different one.

So the card becomes a CONTEXT CHANNEL at the top of the resolution ladder (card >
board selection > last-answered subject > history), and `open-card` becomes the
route that reads it back. What is asserted here:

  * the ladder — a POINTED subject binds to the card first, and the answer says so;
  * the dispatch — `open-card` answers from the card, and NEVER from a stale one:
    the parse reports what it saw, the dispatch decides (R-AI5(8));
  * the voice — every figure in the answer came off the card, so the two surfaces
    can never state different numbers;
  * the specimen — the founder's own sentence, graded.

What a live model parses a given phrasing to is not asserted here; that is the
sweep's job (R-AI4(2)). What is asserted is that every field reaches the right
destination and that the honest floor stays honest.
"""
from __future__ import annotations

import pytest

from mre.contracts.parse import Intent, SubjectKind, SubjectSource
from mre.modules.explainer import ROUTE_TAXONOMY, register_of
from mre.modules.interpreter import dispatch, tier_of
from mre.modules.question_parser import _bind_from_context, describe_card
from mre.modules.renderers import TemplateRenderer, _signed_money
from tests.parse_doubles import parsed, resolve
from tests.test_interpreter import FakeStore, _make_index

from mre.modules.explainer import Explainer


# The card payload the cockpit sends — the founder's own numbers, split by CU1.
CARD = {
    "open": True,
    "operation_ref": "op-38-10",
    "order": "ORD-38",
    "machine": "MILL-01",
    "when": "Jan 8, 08:30",
    "outcome": "verdict",
    "feasible": True,
    "cost_delta_abs": -11975.83,
    "attribution": "split",
    "reopt_delta_abs": -11600.0,
    "move_delta_abs": -375.83,
    "attribution_note": "",
    "affected_orders": [
        {"work_order": "ORD-12", "tardiness_delta": -370.83, "lateness_delta_min": -120},
        {"work_order": "ORD-19", "tardiness_delta": 0.0, "lateness_delta_min": 45},
        {"work_order": "ORD-27", "tardiness_delta": -95.0, "lateness_delta_min": 0},
        {"work_order": "ORD-41", "tardiness_delta": 0.0, "lateness_delta_min": 0},
    ],
    "lateness_delta_min": -75,
    "moves": 5,
    "no_committed_work_changes": True,
    "dominant_driver": {"code": "EARLINESS_PREFERENCE",
                        "phrase": "a declared earliness preference paid a little "
                                  "more to start it sooner",
                        "hedge": "— though I'm attributing this by price alone"},
}

NO_CARD = {"open": False}


@pytest.fixture()
def explainer(tmp_path):
    return Explainer(snapshot_store=FakeStore("snap-demo"),
                     index=_make_index(tmp_path), snapshot_id="snap-demo")


def _dispatch(explainer, p, context=None):
    context = context or {}
    return dispatch(explainer, resolve(p, explainer, context), context=context)


def _answer(bundle) -> str:
    return TemplateRenderer().render(bundle)


# ===========================================================================
# The ladder — the card outranks every other channel
# ===========================================================================

class TestResolutionLadder:
    """The card is the narrowest channel there is: a selection persists after the
    planner has stopped thinking about it, but a card is open because a move is
    being weighed right now. Where they differ, "this" means the card."""

    def test_a_pointed_order_binds_to_the_card_first(self):
        ref, src = _bind_from_context(SubjectKind.ORDER, {
            "card": CARD,
            "selection": {"order": "ORD-99"},
            "last_answered_subject": {"order": "ORD-77"},
            "history": [{"order": "ORD-55"}],
        })
        assert ref == "ORD-38"
        assert src is SubjectSource.CARD

    def test_a_pointed_machine_binds_to_the_card_first(self):
        ref, src = _bind_from_context(SubjectKind.MACHINE, {
            "card": CARD, "selection": {"machine": "PRESS-02"}})
        assert (ref, src) == ("MILL-01", SubjectSource.CARD)

    def test_a_closed_card_yields_to_the_selection(self):
        ref, src = _bind_from_context(SubjectKind.ORDER, {
            "card": NO_CARD, "selection": {"order": "ORD-99"}})
        assert (ref, src) == ("ORD-99", SubjectSource.SELECTION)

    def test_the_ladder_below_the_card_is_unchanged(self):
        base = {"card": NO_CARD}
        assert _bind_from_context(SubjectKind.ORDER, {
            **base, "last_answered_subject": {"order": "A"},
            "history": [{"order": "B"}]})[1] is SubjectSource.LAST_ANSWER
        assert _bind_from_context(SubjectKind.ORDER, {
            **base, "history": [{"order": "B"}]})[1] is SubjectSource.HISTORY
        assert _bind_from_context(SubjectKind.ORDER, base)[0] is None

    def test_a_card_open_on_a_machine_never_binds_an_order(self):
        # the typed-binding rule the founder's confident-wrong bug produced: a
        # card whose move names only a machine supplies no order.
        ref, _src = _bind_from_context(
            SubjectKind.ORDER, {"card": {"open": True, "machine": "MILL-01"}})
        assert ref is None

    def test_the_note_names_the_card_rather_than_the_selection(self, explainer):
        d = _dispatch(explainer, parsed("why is it late?", Intent.LATE_ORDER,
                                        pointed=(SubjectKind.ORDER,)),
                      {"card": {"open": True, "order": "WO-2001"}})
        assert "from the move you have open" in d.note


# ===========================================================================
# The dispatch — answers from the card, never from a stale one
# ===========================================================================

class TestDispatch:
    def test_open_card_reaches_its_own_route(self, explainer):
        d = _dispatch(explainer, parsed("what does this move cost?",
                                        Intent.OPEN_CARD), {"card": CARD})
        assert d.route == "open-card"
        assert d.bundle.subject_type == "open_card"
        assert d.bundle.key_facts["card"] == CARD

    def test_the_card_is_the_subject_so_the_route_needs_no_slot(self):
        # a route that required an order would near-miss the moment the planner
        # said "these orders" instead of naming one.
        assert ROUTE_TAXONOMY["open-card"]["params"] == []

    def test_a_named_intent_with_NO_card_open_never_invents_one(self, explainer):
        """The parse reports what the context showed it; the DISPATCH decides
        whether the card is really there (R-AI5(8)). With none open the honest
        answer is that there is nothing to read back — never a guess at which
        move they meant, and never a re-derivation from a remembered one."""
        for ctx in ({}, {"card": NO_CARD}, {"card": {}}):
            d = _dispatch(explainer, parsed("the delta?", Intent.OPEN_CARD), ctx)
            assert d.route == "open-card"
            text = _answer(d.bundle)
            assert "no priced move open" in text
            # and it says how to get one back, rather than dead-ending
            assert "Make the move again" in text
            # nothing from any card leaks into the floor
            assert "$" not in text

    def test_it_runs_AHEAD_of_the_clarify_branch(self, explainer):
        """A clarify decides before everything below it, and "which orders do you
        mean" asked about the card in front of the planner is the dead end the
        clarify guard exists to prevent — but a card is not a resolved SUBJECT,
        so that guard cannot see it."""
        from mre.contracts.parse import ClarifyReason
        d = _dispatch(explainer, parsed("what orders are affected in this move",
                                        Intent.OPEN_CARD,
                                        clarify=ClarifyReason.SET_REFERENCE),
                      {"card": CARD})
        assert d.route == "open-card"

    def test_the_preflight_agrees_with_the_dispatch(self):
        # the two-phase ask must not promise a synthesis wait for an instant read
        assert tier_of(parsed("the delta?", Intent.OPEN_CARD)) == "route"

    def test_a_card_open_does_not_capture_every_other_intent(self, explainer):
        """The card is a channel, not a mode. A question that names a different
        intent is still answered as that intent while a card is showing."""
        d = _dispatch(explainer, parsed("which orders are late?",
                                        Intent.LATE_ORDERS), {"card": CARD})
        assert d.route == "late-orders"

    def test_the_answer_is_testimony_about_our_own_solve(self, explainer):
        d = _dispatch(explainer, parsed("q", Intent.OPEN_CARD), {"card": CARD})
        assert register_of(d.bundle) == "testimony"

    def test_it_carries_no_evidence_chain(self, explainer):
        # the card arrived on the context channel; there is nothing in the
        # canonical model this route reads, and it must not pretend otherwise.
        d = _dispatch(explainer, parsed("q", Intent.OPEN_CARD), {"card": CARD})
        assert d.bundle.ordered_records == []


# ===========================================================================
# The voice — every figure came off the card
# ===========================================================================

class TestVoice:
    def _text(self, explainer, card=CARD, q="what does this move do?"):
        return _answer(_dispatch(explainer, parsed(q, Intent.OPEN_CARD),
                                 {"card": card}).bundle)

    def test_it_states_the_placement_the_card_shows(self, explainer):
        text = self._text(explainer)
        assert "ORD-38" in text and "MILL-01" in text and "Jan 8, 08:30" in text

    def test_it_voices_the_CU1_SPLIT_not_just_the_total(self, explainer):
        """The whole point of CU1 rendered in the other surface: the planner is
        told which part of the number is theirs."""
        text = self._text(explainer)
        assert "−$11,975.83" in text          # the total
        assert "−$11,600.00" in text          # window re-optimization
        assert "−$375.83" in text             # their move
        assert "window re-optimizing" in text
        assert "your move itself adds" in text

    def test_an_unsplit_card_says_the_total_includes_re_optimization(self, explainer):
        text = self._text(explainer, {**CARD, "attribution": "unavailable",
                                      "reopt_delta_abs": None,
                                      "move_delta_abs": None})
        assert "−$11,975.83" in text
        assert "still includes window re-optimization" in text
        # and it never invents the part it could not measure
        assert "−$375.83" not in text

    def test_it_lists_the_affected_set_the_card_lists(self, explainer):
        text = self._text(explainer, q="what orders are affected in this move")
        assert "Orders it touches (4)" in text
        for order in ("ORD-12", "ORD-19", "ORD-27", "ORD-41"):
            assert order in text
        # per-Demand tardiness + lateness only — never a PRODUCTION figure per
        # order (the ledger does not roll one; the card's own header says so)
        assert "−$370.83 tardiness" in text
        assert "+45 min" in text
        assert "no lateness change" in text        # ORD-41 touches nothing

    def test_it_states_the_net_lateness_and_what_else_moved(self, explainer):
        text = self._text(explainer)
        assert "recovers 1.2h of lateness" in text
        # 5 moves in the card's moved-set, one of which IS the dropped op
        assert "4 other operation(s) shift" in text
        assert "No committed work changes." in text

    def test_a_move_that_displaces_nothing_says_so(self, explainer):
        text = self._text(explainer, {**CARD, "moves": 1})
        assert "Nothing else has to move." in text

    def test_it_carries_the_dominant_driver_WITH_its_hedge(self, explainer):
        text = self._text(explainer)
        assert "a declared earliness preference" in text
        # the hedge is never dropped — an attribution by price rank that reads as
        # a certainty is the defect class docs/02 §4.2 names
        assert "attributing this by price alone" in text

    def test_it_always_states_that_nothing_is_committed(self, explainer):
        assert "Nothing here is committed" in self._text(explainer)

    def test_a_refused_placement_reads_as_a_refusal_not_a_price(self, explainer):
        text = self._text(explainer, {
            "open": True, "order": "ORD-38", "machine": "MILL-01",
            "feasible": False, "outcome": "verdict",
            "message": "this placement conflicts with a commitment you already made",
            "cost_delta_abs": None,
        })
        assert "refused" in text and "Nothing was changed" in text
        assert "$" not in text

    def test_a_card_with_no_dollars_never_shows_a_dollar_figure(self, explainer):
        text = self._text(explainer, {**CARD, "cost_delta_abs": None,
                                      "attribution": "unavailable",
                                      "reopt_delta_abs": None,
                                      "move_delta_abs": None,
                                      "affected_orders": []})
        assert "don't have a dollar figure" in text
        assert "$" not in text

    def test_the_answer_is_authored_copy_and_never_the_LLMs_to_reword(self):
        """A reworded card answer is where the two surfaces would start
        disagreeing — the one failure this route exists to make impossible."""
        from mre.modules.renderers import LLMRenderer
        assert "open_card" in LLMRenderer._AUTHORED_COPY_SUBJECTS


# ===========================================================================
# The specimen, graded
# ===========================================================================

def test_the_founders_exchange(explainer):
    """"what orders are affected in this move" — asked with the card showing
    exactly that, and previously answered by `swap-move`.

    Graded on what the planner needed back: the orders, by name, with what
    happens to each, and no reasoning about a move they had not made."""
    d = _dispatch(explainer,
                  parsed("what orders are affected in this move", Intent.OPEN_CARD),
                  {"card": CARD})
    assert d.route == "open-card"
    text = _answer(d.bundle)
    for order in ("ORD-12", "ORD-19", "ORD-27", "ORD-41"):
        assert order in text
    # the swap-move vocabulary — the wrong answer's fingerprint — is absent
    assert "swap" not in text.lower()


# ===========================================================================
# The two surfaces state one set of numbers
# ===========================================================================

def test_money_reads_the_same_in_both_languages():
    """``renderers._signed_money`` (the answer) and ``sandboxui.signedMoney``
    (the card) format the same figure the same way. The JS side is pinned by
    tests/cockpit/attribution.spec.mjs; this is the Python half of the pair."""
    assert _signed_money(-11600) == "−$11,600.00"
    assert _signed_money(375.83) == "+$375.83"
    assert _signed_money(0) == "$0"
    assert _signed_money(0.004) == "$0"
    assert _signed_money(None) == ""


def test_the_parse_context_states_presence_and_subject_but_never_figures():
    """The model is told THAT a move is priced and what it is about — never what
    it costs. Handing it the numbers would invite it to answer from them, and the
    parse never answers (R-AI5(1))."""
    line = describe_card(CARD)
    assert "ORD-38" in line and "MILL-01" in line
    assert "11,975" not in line and "$" not in line
    assert describe_card(None).startswith("none")
    assert describe_card(NO_CARD).startswith("none")
