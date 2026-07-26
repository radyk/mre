"""The felt-bar residue: pacing, the warm floor, and the adjacent-match guard.

Session 4A.5c CU3. Three items the round-five review flagged, each of them a place
where the system was already HONEST and not yet KIND — or, in the guard's case,
confidently helpful about the wrong question.

  (a) SYNTHESIS PACING. Rider (c) measured it: a contracted answer lands in
      ~1.3s, a reasoned one in ~10s. A planner will wait ten seconds — but not
      silently, and not without knowing which they are getting.
  (b) THE WARM FLOOR. The couldn't-answer keeps the nearest-capabilities doors.
      Honest and warm are not in tension.
  (c) THE ADJACENT-MATCH GUARD. The last hiding place: the nearest intent really
      IS the nearest one and still cannot honour something the planner said.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from mre.contracts.parse import (
    ClarifyReason, FollowupKind, Intent, ParsedQuestion, SubjectKind,
)
from mre.contracts.synthesis import (
    ClaimStatus, SynthesisAnswer, ToolCallLog, VerifiedClaim,
)
from mre.modules.interpreter import ParseMemory, dispatch, tier_of
from mre.modules.renderers import TemplateRenderer

from tests.parse_doubles import parsed, resolve
from tests.test_interpreter import FakeStore, _make_index

# The pinned fake world's own vocabulary (test_interpreter's fixture). Subjects are
# bound through the REAL resolution path, so a test that names something the world
# does not carry is testing the relevance guard, not the guard under test.
ORDER = "WO-2001"
MACHINE = "M-GEAR-01"


@pytest.fixture()
def explainer(tmp_path):
    """The same pinned fake world the dispatch tests use — these are dispatch
    tests too, and a second world would be a second set of assumptions."""
    from mre.modules.explainer import Explainer
    return Explainer(snapshot_store=FakeStore("snap-demo"),
                     index=_make_index(tmp_path), snapshot_id="snap-demo")


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class FakeSynthesizer:
    """A synthesizer that always answers, recording what it was asked."""

    available = True

    def __init__(self, answer: SynthesisAnswer | None = None) -> None:
        self.answer = answer
        self.asked: list = []

    def synthesize(self, question, *, explainer, context=None, toolbox=None):
        self.asked.append(question)
        return self.answer or SynthesisAnswer(
            question=question,
            claims=[VerifiedClaim(text="a reasoned line.",
                                  status=ClaimStatus.INTERPRETIVE)],
            tool_calls=[ToolCallLog(tool="lateness_set")],
            model="test-model")


def unanswerable(question: str = "q") -> SynthesisAnswer:
    return SynthesisAnswer(question=question, claims=[], unanswerable=True,
                           tool_calls=[ToolCallLog(tool="lateness_set")],
                           model="test-model")


# ---------------------------------------------------------------------------
# (c) THE ADJACENT-MATCH GUARD
# ---------------------------------------------------------------------------

class TestAdjacentMatchGuard:
    """The two founder shapes that 4A.5b left UNMET, plus the negatives that stop
    the guard becoming a second way to lose a proven answer."""

    def test_a_stated_time_scope_the_route_cannot_honour_diverts(self, explainer):
        """"how many orders will be late NEXT MONTH" -> late-orders, which answers
        about THIS plan. The intent is right; the answer is to a question nobody
        asked, with perfect citations."""
        synth = FakeSynthesizer()
        p = parsed("how many orders will be late next month", Intent.LATE_ORDERS)
        p = p.model_copy(update={"dropped_qualifier": "next month"})
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "synthesis"
        assert synth.asked == ["how many orders will be late next month"]

    def test_an_actually_qualifier_diverts(self, explainer):
        """"how much of <machine>'s week is ACTUALLY working time" -> downtime,
        which answers the COMPLEMENT of what was asked."""
        synth = FakeSynthesizer()
        p = resolve(parsed(f"how much of {MACHINE}s week is actually working time",
                           Intent.DOWNTIME, machines=(MACHINE,)), explainer)
        p = p.model_copy(update={"dropped_qualifier": "actually working time"})
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "synthesis"

    def test_the_rendered_by_line_names_the_qualifier(self, explainer):
        """The planner is owed the reason in the same breath: it was their
        qualifier, not a failure to understand them."""
        synth = FakeSynthesizer()
        p = parsed("how many will be late next month", Intent.LATE_ORDERS)
        p = p.model_copy(update={"dropped_qualifier": "next month"})
        d = dispatch(explainer, p, synthesizer=synth)
        text = TemplateRenderer().render(d.bundle)
        assert "rendered by: synthesis" in text
        assert 'no route covers "next month"' in text

    # -- the negatives: a guard that fires too often is a second failure -----

    def test_a_qualifier_the_route_DOES_honour_must_not_divert(self, explainer):
        """`machine-schedule` reads the question's own date filter, so "tomorrow"
        is not a dropped qualifier. Nothing to report, nothing to divert."""
        synth = FakeSynthesizer()
        p = resolve(parsed(f"whats running on {MACHINE} tomorrow",
                           Intent.MACHINE_SCHEDULE, machines=(MACHINE,)),
                    explainer)
        assert p.dropped_qualifier == ""
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "machine-schedule"
        assert synth.asked == [], "a clean match never reaches the second tier"

    def test_a_plain_matched_intent_is_untouched(self, explainer):
        synth = FakeSynthesizer()
        p = resolve(parsed(f"why is {ORDER} late", Intent.LATE_ORDER,
                           orders=(ORDER,)), explainer)
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "late-order"
        assert synth.asked == []

    def test_the_parse_reports_but_never_decides(self):
        """R-AI5(8)'s discipline applied to routing. The field is words; the
        dispatch owns the diversion. An `unmatched` parse has no route to drop a
        qualifier FROM, so the field is cleared rather than carried as noise."""
        from mre.modules.question_parser import build_parsed
        e = {"intent": "unmatched", "subjects": [], "confidence": 0.9,
             "dropped_qualifier": "next month"}
        assert build_parsed("q", e, None, None).dropped_qualifier == ""

    def test_the_reported_qualifier_is_a_phrase_not_prose(self):
        """A model that starts explaining itself is emitting prose into a routing
        contract."""
        from mre.modules.question_parser import build_parsed
        e = {"intent": "late-orders", "subjects": [], "confidence": 0.9,
             "dropped_qualifier": "x" * 400}
        assert len(build_parsed("q", e, None, None).dropped_qualifier) == 80


# ---------------------------------------------------------------------------
# (b) THE WARM FLOOR
# ---------------------------------------------------------------------------

class TestWarmFloor:

    def test_the_couldnt_answer_keeps_its_doors(self, explainer):
        """RUBRIC precedent 6, ruled. Before this, an unmatched turn that the tier
        could not ground got an honest refusal and NOTHING to do next — colder
        than the near-miss bridge it replaced."""
        synth = FakeSynthesizer(unanswerable("this is not helpful"))
        p = parsed("this is not helpful", Intent.UNMATCHED,
                   nearest=(Intent.LATE_ORDERS, Intent.DATA_PROBLEMS))
        d = dispatch(explainer, p, synthesizer=synth)
        text = TemplateRenderer().render(d.bundle)
        assert "I couldn't answer that one from the evidence" in text
        assert "Here's what I can do that's closest:" in text
        assert text.count("\n  - ") >= 2

    def test_an_answer_that_grounded_gets_no_consolation_prize(self, explainer):
        """The doors ride on every synthesis bundle and render ONLY on the floor.
        An answer that said something needs no offer of something else."""
        synth = FakeSynthesizer()
        d = dispatch(explainer, parsed("why so many late", Intent.UNMATCHED,
                                       nearest=(Intent.LATE_ORDERS,)),
                     synthesizer=synth)
        text = TemplateRenderer().render(d.bundle)
        assert "Here's what I can do that's closest:" not in text

    def test_the_floor_ends_cleanly_when_there_are_no_doors(self):
        """Absence-tested: no dangling header when the dispatch could compute no
        offers."""
        from mre.modules.explainer import ExplanationBundle
        bundle = ExplanationBundle(
            question="q", subject_id="synthesis", subject_type="synthesis",
            subject_external_name="?", ordered_records=[],
            key_facts={"claims": [], "unanswerable": True, "offers": [],
                       "consulted_tools": [], "tool_call_count": 0},
            snapshot_id="s")
        text = TemplateRenderer().render(bundle)
        assert "I couldn't answer that one" in text
        assert "closest" not in text

    def test_a_clarify_about_a_mistyped_subject_reaches_the_tier_not_a_question(
            self, explainer):
        """The arc-close sweep's own find, and 4A.5b's other-kind rescue one
        branch further out.

        "whats holding <machine>" parsed as `start-reason` — an ORDER intent —
        with the MACHINE typed as an order (so unresolved) AND hedged with
        `ambiguous-subject`. Nothing resolved, so the clarify branch asked the
        planner which ORDER they meant — about the machine on their screen. The
        rescue in the matched branch would have caught it and never ran, because a
        clarify short-circuits ahead of it."""
        synth = FakeSynthesizer()
        p = resolve(parsed(f"whats holding {MACHINE}", Intent.START_REASON,
                           orders=(MACHINE,),
                           clarify=ClarifyReason.AMBIGUOUS_SUBJECT), explainer)
        assert not p.subjects[0].resolved, "the machine does not resolve as an order"
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "synthesis"
        assert synth.asked == [f"whats holding {MACHINE}"]

    def test_a_clarify_with_nothing_nameable_still_asks(self, explainer):
        """The negative, and it matters: when the planner named nothing this world
        carries, asking IS the right move and must survive the change above."""
        synth = FakeSynthesizer()
        p = resolve(parsed("why is that one late", Intent.LATE_ORDER,
                           pointed=(SubjectKind.ORDER,),
                           clarify=ClarifyReason.NO_SUBJECT), explainer)
        d = dispatch(explainer, p, synthesizer=synth)
        assert d.route == "CLARIFY"
        assert synth.asked == []

    def test_the_doors_are_chosen_by_what_the_planner_named(self, explainer):
        """The bridge's own rule, inherited: an offer that ignores the subject
        reads as not having listened."""
        synth = FakeSynthesizer(unanswerable())
        p = resolve(parsed(f"whats up with {MACHINE}", Intent.UNMATCHED,
                           machines=(MACHINE,), nearest=()), explainer)
        d = dispatch(explainer, p, synthesizer=synth)
        text = TemplateRenderer().render(d.bundle)
        assert MACHINE in text


# ---------------------------------------------------------------------------
# (a) THE PACING — the two-phase ask
# ---------------------------------------------------------------------------

class TestTierOf:
    """The preflight's whole output. It must be computed from the SAME rules the
    answer will follow — a first beat that predicts the wrong tier is worse than
    no first beat."""

    def test_an_unmatched_parse_is_the_synthesis_tier(self):
        assert tier_of(parsed("q", Intent.UNMATCHED)) == "synthesis"

    def test_a_low_confidence_match_is_the_synthesis_tier(self):
        assert tier_of(parsed("q", Intent.LATE_ORDERS, confidence=0.2)) == \
            "synthesis"

    def test_a_diverted_match_is_the_synthesis_tier(self):
        p = parsed("q", Intent.LATE_ORDERS).model_copy(
            update={"dropped_qualifier": "next month"})
        assert tier_of(p) == "synthesis"

    def test_a_clean_match_is_the_route_tier(self):
        assert tier_of(parsed("q", Intent.LATE_ORDERS)) == "route"

    def test_prove_it_is_the_route_tier(self):
        """It grounds a claim we already made — no agentic read, no long wait."""
        p = parsed("how do you know that", Intent.PROVE_IT,
                   followup_of=FollowupKind.PROVE_IT)
        assert tier_of(p) == "route"

    def test_a_clarify_that_can_help_is_the_floor(self):
        p = parsed("why is it late", Intent.LATE_ORDER,
                   clarify=ClarifyReason.NO_SUBJECT)
        assert tier_of(p) == "floor"

    def test_no_parse_is_the_floor(self):
        assert tier_of(None) == "floor"


class TestParseMemory:
    """What makes the two-phase ask FREE. A preflight that re-parsed would double
    every question's parse cost to buy a spinner on one question in ten."""

    def test_the_ask_reuses_the_preflights_parse(self):
        mem = ParseMemory()
        p = parsed("why so many late", Intent.UNMATCHED)
        key = ParseMemory.key("why so many late", None, "s1", "sched-1")
        mem.remember(key, p)
        assert mem.take(key) is p

    def test_a_parse_is_consumed_by_the_ask_it_was_made_for(self):
        """Read AND evict: leaving it behind would let a later identical question
        skip a parse that should have seen a changed world."""
        mem = ParseMemory()
        key = ParseMemory.key("q", None, "s1", "sched-1")
        mem.remember(key, parsed("q", Intent.LATE_ORDERS))
        assert mem.take(key) is not None
        assert mem.take(key) is None

    def test_a_different_context_is_a_different_key(self):
        """It is OUR parse being reused, not client-supplied routing: the same
        words with a different board selection re-parse."""
        a = ParseMemory.key("whats the end time", {"selection": {"order": "ORD-05"}},
                            "s1", "sched-1")
        b = ParseMemory.key("whats the end time", {"selection": {"order": "ORD-13"}},
                            "s1", "sched-1")
        c = ParseMemory.key("whats the end time", {"selection": {}}, "s1", "sched-1")
        assert len({a, b, c}) == 3

    def test_run_ask_uses_it_and_does_not_parse_again(self, explainer):
        """The integration, not just the cache: two-phasing must cost NO EXTRA
        MODEL CALL, or it is a spinner bought with a second of every planner's
        time."""
        from mre.modules.interpreter import run_ask
        from tests.parse_doubles import ScriptedParser

        parser = ScriptedParser({"why so many late": parsed(
            "why so many late", Intent.LATE_ORDERS)})
        mem = ParseMemory()
        key = ParseMemory.key("why so many late", None, "s1", None)
        mem.remember(key, parsed("why so many late", Intent.LATE_ORDERS))

        result = run_ask(explainer, "why so many late", parser=parser,
                         session_id="s1", parse_memory=mem)
        assert parser.calls == 0, "the preflight's parse was not reused"
        assert result.route == "late-orders"

    def test_run_ask_parses_normally_when_nothing_was_preflighted(self, explainer):
        """Calling /ask directly is unchanged and still correct — the preflight is
        an optimization of the WAIT, never a step the answer depends on."""
        from mre.modules.interpreter import run_ask
        from tests.parse_doubles import ScriptedParser

        parser = ScriptedParser({"why so many late": parsed(
            "why so many late", Intent.LATE_ORDERS)})
        result = run_ask(explainer, "why so many late", parser=parser,
                         session_id="s1", parse_memory=ParseMemory())
        assert parser.calls == 1
        assert result.route == "late-orders"

    def test_a_different_session_or_schedule_is_a_different_key(self):
        base = ParseMemory.key("q", None, "s1", "sched-1")
        assert base != ParseMemory.key("q", None, "s2", "sched-1")
        assert base != ParseMemory.key("q", None, "s1", "sched-2")

    def test_it_is_bounded(self):
        mem = ParseMemory(limit=4)
        for i in range(20):
            mem.remember(f"k{i}", parsed("q", Intent.LATE_ORDERS))
        assert len(mem._entries) <= 4
        assert mem.take("k0") is None, "oldest first out"
        assert mem.take("k19") is not None


class TestFirstBeatCopy:

    def test_the_first_beat_is_an_honest_non_answer(self):
        """R-T2's two-beat pattern: beat one says what is happening and commits to
        nothing about what will be found. Never a fake answer, never an invented
        progress figure."""
        from mre.contracts.synthesis import MAX_TOOL_CALLS
        from mre.modules.ask_fallback_copy import (
            WAITING_ROUTE, WAITING_SYNTHESIS, WAITING_SYNTHESIS_DIVERTED,
        )
        text = WAITING_SYNTHESIS.format(budget=MAX_TOOL_CALLS)
        assert "Reading the evidence" in text
        assert str(MAX_TOOL_CALLS) in text
        # it promises nothing about the ANSWER
        for promise in ("I found", "there are", "the answer is", "%"):
            assert promise not in text
        # a contracted answer gets no waiting state — it lands before one is read
        assert WAITING_ROUTE == ""
        diverted = WAITING_SYNTHESIS_DIVERTED.format(qualifier="next month",
                                                     budget=MAX_TOOL_CALLS)
        assert "next month" in diverted

    def test_the_preflight_is_fail_open(self, tmp_path):
        """A pacing hint must never be able to break an answer. With no parser,
        the preflight reports the route tier and empty copy, and the ask behaves
        exactly as it did before the endpoint existed."""
        from mre.api.app import _preflight
        out = _preflight(tmp_path, "snap-missing", "why so many late orders",
                         parser=None)
        assert out == {"tier": "route", "waiting": "", "intent": None}

    def test_the_preflight_survives_a_dead_target(self, tmp_path):
        from mre.api.app import _preflight

        class Boom:
            available = True

            def parse(self, *a, **kw):
                raise RuntimeError("the world did not load")

        out = _preflight(tmp_path, "snap-missing", "q", parser=Boom())
        assert out["tier"] == "route" and out["waiting"] == ""
