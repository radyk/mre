"""Route falsifiability and the reversed repeat signal
(Session 4B.15 Items 2 and 4).

Both are written from the MEASURED transcript. Item 2's specimens are the five
consecutive turns the capability-coaching route swallowed; Item 4's are the four
false positives the old repeat detector fired on.
"""
from __future__ import annotations

import pytest

from mre.contracts.parse import (
    Intent, ParsedQuestion, SubjectKind, SubjectRef,
)
from mre.modules.interpreter import (
    _answer_fingerprint, _same_question, bundle_repeat, forget_deliveries,
    remember_delivery,
)
from mre.modules.route_falsifiability import EXEMPT_ROUTES, _disjunction, falsify


def _parsed(question: str, intent: Intent = Intent.COACHING,
            order: str | None = None) -> ParsedQuestion:
    subjects = []
    if order:
        subjects.append(SubjectRef(kind=SubjectKind.ORDER, raw=order, ref=order))
    return ParsedQuestion(question=question, intent=intent, subjects=subjects,
                          confidence=0.92)


class TestDiscardedDisjunction:
    """SPECIMEN: "is that set per machine or per operation" was answered as
    "how do I enable that?" — the disjunction discarded and replaced."""

    def test_the_alternatives_carry_the_preposition(self):
        assert _disjunction("is that set per machine or per operation") == (
            "per machine", "per operation")

    def test_an_answer_naming_neither_falls_through(self):
        f = falsify("is that set per machine or per operation", "coaching",
                    "To enable it: set splittable=true on the routing line.",
                    _parsed("is that set per machine or per operation"))
        assert f is not None
        assert f.rule == "discarded-disjunction"
        assert "per machine or per operation" in f.note

    def test_containing_the_fact_without_surfacing_it_is_still_a_fall_through(self):
        """The brief is explicit: "that OPERATION'S routing line" answers
        per-operation-not-per-machine and is a FALL-THROUGH, not a pass. The
        planner asked to be told, not to infer."""
        text = ("To enable it: set splittable=true on that operation's routing "
                "line in routing_lines.csv.")
        f = falsify("is that set per machine or per operation", "coaching",
                    text, _parsed("is that set per machine or per operation"))
        assert f is not None and f.rule == "discarded-disjunction"

    def test_an_answer_that_chooses_passes(self):
        text = ("Setup family is assigned per operation, not per machine — the "
                "same machine runs operations with different families.")
        assert falsify("is that set per machine or per operation", "coaching",
                       text,
                       _parsed("is that set per machine or per operation")) is None

    def test_an_ordinary_or_is_not_a_disjunction(self):
        for q in ("is ORD-05 late or on time",           # no preposition frame
                  "why is it late",
                  "what is running on CUT-01 or nearby"):
            assert _disjunction(q) is None or falsify(
                q, "late-order", "ORD-05 finishes 890 minutes past its due date.",
                _parsed(q, Intent.LATE_ORDER, "ORD-05")) is None


class TestSubjectSilence:
    """SPECIMEN: "can I make just this one job splittable" resolved correctly to
    ORD-000013 and was answered generically; then "no, I mean for ORD-000013
    specifically" — an explicit correction — got the same generic answer."""

    def test_an_answer_that_never_names_the_subject_falls_through(self):
        f = falsify("can I make just this one job splittable", "coaching",
                    "Yes — set splittable=true on the routing line. See §5.3.",
                    _parsed("can I make just this one job splittable",
                            order="ORD-000013"))
        assert f is not None
        assert f.rule == "subject-silence"
        assert "ORD-000013" in f.note

    def test_naming_the_subject_passes(self):
        f = falsify("is ORD-000013 op20 splittable", "attribute-lookup",
                    "ORD-000013 op20 — splittable: no.",
                    _parsed("is ORD-000013 op20 splittable",
                            Intent.ATTRIBUTE_LOOKUP, "ORD-000013"))
        assert f is None

    def test_a_shorter_spelling_of_the_same_id_passes(self):
        """A correctly-scoped answer written "ORD-13" or "order 13" is not
        silent, and must not be re-routed for a spelling."""
        for text in ("ORD-13 is not splittable.", "Order 13 cannot be split."):
            assert falsify("is it splittable", "attribute-lookup", text,
                           _parsed("is it splittable", Intent.ATTRIBUTE_LOOKUP,
                                   "ORD-000013")) is None

    def test_an_unresolved_subject_never_fires(self):
        p = ParsedQuestion(question="is it splittable", intent=Intent.COACHING,
                           subjects=[SubjectRef(kind=SubjectKind.ORDER,
                                                raw="it", ref=None)])
        assert falsify("is it splittable", "coaching", "Set splittable=true.",
                       p) is None


class TestSafety:
    """The check can only REJECT a route. Every guard that keeps it rare."""

    @pytest.mark.parametrize("route", sorted(EXEMPT_ROUTES))
    def test_floors_and_the_second_tier_are_exempt(self, route):
        assert falsify("can I make ORD-000013 splittable", route,
                       "some answer that names nothing",
                       _parsed("can I make ORD-000013 splittable",
                               order="ORD-000013")) is None

    def test_an_empty_answer_never_fires(self):
        assert falsify("anything", "coaching", "",
                       _parsed("anything", order="ORD-05")) is None

    def test_no_parse_means_no_subject_rule(self):
        assert falsify("is it splittable", "coaching", "Set it true.",
                       None) is None

    def test_it_fails_open_on_a_broken_parse(self):
        class Exploding:
            def of_kind(self, _kind):
                raise RuntimeError("boom")
        assert falsify("q", "coaching", "text", Exploding()) is None


# ---------------------------------------------------------------------------
# Item 4 — the reversed repeat signal
# ---------------------------------------------------------------------------

class _Bundle:
    def __init__(self):
        self.key_facts: dict = {}


class TestRepeatReversal:
    """THE MEASURED FAILURE: the old detector fired four times with ZERO true
    positives, and it escalated — "Still the same; nothing has changed since you
    asked" is the product blaming the planner for its own deafness."""

    def test_the_scolding_line_is_gone(self):
        from mre.modules.ask_fallback_copy import REPEAT_LEADS
        joined = " ".join(REPEAT_LEADS).lower()
        assert "nothing has changed since you asked" not in joined

    def test_the_deaf_copy_never_rebukes(self):
        from mre.modules.ask_fallback_copy import (
            DEAF_LEAD, DEAF_OFFER, DEAF_PRIOR,
        )
        blob = " ".join((DEAF_LEAD, DEAF_PRIOR, DEAF_OFFER)).lower()
        # Quoting the planner's PREVIOUS QUESTION back is showing what was
        # heard, and stays. What must never appear is fault placed on them.
        for rebuke in ("still the same", "nothing has changed since",
                       "already told", "as i said", "as i mentioned",
                       "you keep", "you're repeating", "you are repeating",
                       "same question", "asked me that"):
            assert rebuke not in blob, f"the deafness copy scolds: {rebuke!r}"
        # And the inference must be about the ASSISTANT, not the planner.
        assert "not understanding" in DEAF_LEAD
        assert DEAF_LEAD.lower().index("i") < DEAF_LEAD.lower().index("you")

    def test_a_genuine_re_ask_is_a_repeat_not_deafness(self):
        b = _Bundle()
        p = _parsed("how many orders are late", Intent.LATE_ORDERS)
        ctx = {"history": [{"question": "how many orders are late?",
                            "route": "late-orders"}]}
        bundle_repeat(b, ctx, p, "13 orders are late.", "sess-a")
        assert b.key_facts.get("repeat") == 1
        assert "deaf" not in b.key_facts

    def test_different_questions_with_the_same_answer_are_deafness(self):
        """The reversal. Several DIFFERENT questions producing ONE ANSWER means
        I am not understanding you."""
        answer = "Set splittable=true on the routing line. See §5.3."
        remember_delivery("sess-b", "coaching",
                          "can I make just this one job splittable", answer)
        b = _Bundle()
        p = _parsed("no, I mean for ORD-000013 specifically")
        bundle_repeat(b, {"history": []}, p, answer, "sess-b")
        assert b.key_facts.get("deaf") == 1
        assert "repeat" not in b.key_facts
        assert "splittable" in b.key_facts["deaf_prior"]

    def test_different_questions_with_different_answers_are_neither(self):
        """THE SIGNAL IS THE OUTPUT, NOT THE ROUTE. Two questions reaching one
        route and getting two good answers is the route WORKING — the case the
        old counter could not distinguish and always got wrong."""
        remember_delivery("sess-c", "attribute-lookup",
                          "is ORD-000013 op20 splittable",
                          "ORD-000013 op20 — splittable: no.")
        b = _Bundle()
        p = _parsed("how long does op20 take", Intent.ATTRIBUTE_LOOKUP)
        bundle_repeat(b, {"history": []}, p,
                      "ORD-000013 op20 — working time: 7h 11m.", "sess-c")
        assert not b.key_facts

    def test_the_demo_opener_is_never_a_repeat(self):
        b = _Bundle()
        p = _parsed("why is ORD-000004 late", Intent.LATE_ORDER)
        bundle_repeat(b, {"history": []}, p, "Because ...", "sess-d")
        assert not b.key_facts

    def test_the_fingerprint_ignores_the_riders_it_adds(self):
        """Else the second delivery never matches the first and the signal can
        only ever fire once."""
        body = "ORD-05 is late by 890 minutes."
        assert _answer_fingerprint(body) == _answer_fingerprint(
            body + "\n[rendered by: template | register: testimony]")

    @pytest.mark.parametrize("a,b,same", [
        ("how many orders are late", "how many orders are late?", True),
        ("how many are late", "How Many Are Late!", True),
        ("is ORD-000013 op20 splittable",
         "can I make just this one job splittable", False),
        ("no, I mean for ORD-000013 specifically",
         "is that set per machine or per operation", False),
    ])
    def test_same_question(self, a, b, same):
        assert _same_question(a, b) is same

    def test_no_session_means_no_deafness_signal(self):
        b = _Bundle()
        bundle_repeat(b, {"history": []}, _parsed("q"), "text", None)
        assert not b.key_facts

    def test_clearing_the_conversation_expires_the_deafness_evidence(self):
        """Errand 4B.16a — the leak this found. ``deaf`` is evidence about a
        CONVERSATION, so it must expire when the conversation is thrown away.

        The delivery store is module-level and keyed by session id, while every
        "start over" gesture cleared only the history channel — so the exam
        harness's RESET cleared history, selection, last-answered and the card,
        and the rider went on citing a question from a conversation that no
        longer existed. Measured before the fix: seven consecutive turns of one
        sweep opened with "I've now given you this same answer for two different
        questions", each naming a discarded conversation's question.
        """
        answer = "26 orders on 15 machines. 4 things worth your attention."
        remember_delivery("sess-reset", "briefing",
                          "what should I be worried about", answer)

        # Same session, different question, same answer -> deaf, as designed.
        b = _Bundle()
        bundle_repeat(b, {"history": []}, _parsed("how does this schedule look"),
                      answer, "sess-reset")
        assert b.key_facts.get("deaf") == 1

        # Now the conversation is cleared. The same pair must be silent.
        forget_deliveries("sess-reset")
        b2 = _Bundle()
        bundle_repeat(b2, {"history": []}, _parsed("how does this schedule look"),
                      answer, "sess-reset")
        assert not b2.key_facts, (
            "the deafness evidence outlived the conversation it was about")

    def test_forget_deliveries_is_safe_on_an_unknown_session(self):
        forget_deliveries("sess-never-seen")
        forget_deliveries(None)

    def test_the_exam_runner_clears_deliveries_on_reset(self):
        """The instrument fix is pinned at its call site: a RESET that clears
        four channels and misses the fifth contaminates every bank that starts a
        second conversation, which is most of them."""
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "src" / "mre" / "ai_exam"
               / "runner.py").read_text(encoding="utf-8")
        head, _, tail = src.partition("isinstance(item, Reset)")
        assert tail, "the runner no longer handles Reset"
        block = tail.split("continue")[0]
        assert "forget_deliveries" in block, (
            "RESET must expire the delivery memory along with the history")
