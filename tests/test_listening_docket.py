"""THE LISTENING DOCKET — four specimens, one disease (Session 4A.x).

The disease is RELEVANCE UNVALIDATED: a confident answer to a question the
planner did not ask, delivered with the full apparatus of correctness. Each
item below is one instance, and all four were measured verbatim on the demo
board (`rolling-db5395dc-2ae`) at HEAD before a line was changed.

  S1  "why cant ORD-000126 op30 start earlier"
      -> "Answering about ORD-000126 op10 … the first of its 3 operations.
          Nothing prevented ORD-000126 op10 from starting earlier…"
      The GRAIN was dropped. `subjects[]` had nowhere to carry an operation, so
      the parse emitted "op30" as a second ORDER subject (measured: it did
      exactly that), which resolved to nothing; and `route_params` never set
      `op_seq` at all, so the eight assemblers that read it saw None from every
      question ever typed on the live ask path.

  S2  "why cant this be moved", ORD-000128 selected
      -> INTERPRETED AS: "why cant ORD-000128 be moved [from board selection]"
      Two assumptions made, one disclosed. The SUBJECT resolution was named;
      the DIRECTION ("moved" read as "moved EARLIER") and the GRAIN (op20, from
      the same selection) were silent.

  S3  the same question presupposes the bar cannot move. It can: MILL-01's next
      opening long enough for its 140 working minutes is 2026-01-23 16:21. The
      premise-correction machinery existed (4B.13) and covered exactly one
      claim shape — a stated PLACEMENT — so nothing checked this one.

  S4  even with S2/S3 fixed the question owes a TWO-direction answer: earlier is
      the blocking chain, later is where the room is plus the link to the route
      that PRICES it.

WHAT IS AND IS NOT UNDER TEST. The world is `test_why_here_route`'s — three
operations, two machines, one closure — because what is under test is the
reasoning, the disclosure and the words a planner reads, not the solver and not
the pricer. Nothing here prices: the LATER paragraph is a calendar fact by
construction (that is the ruling), and pricing has its own guards.

THE LIVE MEASUREMENTS behind every number quoted above are in
`docs/closeouts/4a-listening-docket.md` §2 and §5.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mre.contracts.parse import (
    Intent,
    MoveDirection,
    ParsedQuestion,
    SubjectKind,
    SubjectRef,
)
from mre.modules import mobility_premise as mp
from mre.modules.explainer import Explainer
from mre.modules.interpreter import dispatch, route_params
from mre.modules.renderers import TemplateRenderer

from tests.parse_doubles import parsed, resolve
from tests.test_why_here_route import _Index, _Store, _world

REF = datetime(2026, 1, 5)


@pytest.fixture
def ex():
    return Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")


@pytest.fixture
def free_ex():
    """The same world with op20 moved into space nothing was using — the
    `chose` verdict, which is what makes the EARLIER direction refutable."""
    return Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                     _Index(), snapshot_id="snap-test")


def _answer(explainer, route, **params):
    params.setdefault("question", "why is this here?")
    return TemplateRenderer().render(explainer.route(route, params))


def _dispatched(explainer, p: ParsedQuestion, **context):
    """Run the REAL dispatch over a REALLY-RESOLVED parse, so a guard proves the
    LIVE path rather than a hand-assembled param dict. 4B.21 §5a.78: a guard
    that supplies its own arguments proves the assembler, not the path — and
    `resolve` runs the same `bind_subjects` the live parser runs, so subject
    binding (and the grain riding on it) stays real here too."""
    return dispatch(explainer, resolve(p, explainer, context or {}),
                    context=context or {})


# ===========================================================================
# ITEM 1 — THE GRAIN CARRIES, OR THE ANSWER SAYS WHY NOT
# ===========================================================================

class TestTheGrainReachesTheRoute:
    """S1's mechanism, at each of the three seams it passes."""

    def test_the_contract_carries_an_operation_on_its_order_subject(self):
        s = SubjectRef(kind=SubjectKind.ORDER, raw="ORD-000013", ref="ORD-000013",
                       op_seq=20)
        assert s.op_seq == 20

    def test_an_operation_is_never_a_subject_of_its_own(self):
        """The parse's own workaround at HEAD, refused by the vocabulary: there
        is no SubjectKind an operation could be, so a model that emits one is
        emitting an ORDER that will not resolve."""
        assert not any(k.value == "operation" for k in SubjectKind)

    def test_route_params_carries_the_parsed_grain(self):
        p = parsed("why cant ORD-000013 op20 start earlier", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        assert route_params(p, p.question)["op_seq"] == 20

    def test_route_params_recovers_a_grain_the_parse_forgot(self):
        """The deterministic EXTRACTION, not a classifier: it reads a number the
        planner typed, after the route is already chosen. Measured need — the
        live parse set `op_seq` on some phrasings and not others."""
        p = parsed("why cant ORD-000013 op20 start earlier", Intent.WHY_HERE,
                   orders=("ORD-000013",))
        assert p.named_op_seq is None                    # the parse dropped it
        assert route_params(p, p.question)["op_seq"] == 20

    def test_a_question_naming_no_operation_carries_no_grain(self):
        p = parsed("why is ORD-000013 here", Intent.WHY_HERE,
                   orders=("ORD-000013",))
        assert route_params(p, p.question).get("op_seq") is None

    def test_the_answer_speaks_about_the_operation_that_was_named(self, ex):
        """S1's own shape: op20 named, op20 answered — and no bridging sentence
        announcing a fallback nobody fell back to."""
        p = parsed("why cant ORD-000013 op20 start earlier", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        text = TemplateRenderer().render(_dispatched(ex, p).bundle)
        assert "ORD-000013 op20" in text
        assert "the first of its" not in text

    def test_the_grain_is_read_before_the_board_selection(self, ex):
        """A typed op30 outranks a bar clicked earlier: a selection persists
        after the planner has stopped thinking about it, and a typed number
        cannot be stale."""
        p = parsed("why cant ORD-000013 op20 start earlier", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        d = _dispatched(ex, p, selection={"order": "ORD-000013", "op_seq": 10})
        assert d.bundle.key_facts["op_seq"] == 20


class TestARouteThatCannotHonourTheGrainSaysSo:

    def test_an_order_grain_route_discloses_that_it_dropped_the_step(self, ex):
        p = parsed("when does ORD-000013 op20 finish", Intent.ORDER_SCHEDULE,
                   orders=("ORD-000013",), op_seq=20)
        note = _dispatched(ex, p).note
        assert "op20" in note
        assert "order level" in note

    def test_a_grain_with_no_order_never_renders_an_empty_slot(self, ex):
        """A question can carry a step and no order ("what runs on op20 of
        PAINT-01"), and "answered for the whole of None" is the template
        nonsense C4 forbids."""
        p = parsed("what is running on op20 of PAINT-01",
                   Intent.MACHINE_SCHEDULE, machines=("PAINT-01",))
        note = _dispatched(ex, p).note
        assert "None" not in note
        if "order level" in note:
            assert "the whole order" in note

    def test_a_route_that_DOES_honour_it_says_nothing(self, ex):
        """`why-on-machine` takes a typed op (4B.21 Item 3) and is not
        selection-re-scopable — it is the member that separates the two sets,
        and reading the narrow one as the wide one is what made this
        disclosure's first version accuse it of dropping a grain it honoured."""
        p = parsed("why is ORD-000013 op20 on PAINT-01", Intent.WHY_ON_MACHINE,
                   orders=("ORD-000013",), machines=("PAINT-01",), op_seq=20)
        assert "order level" not in _dispatched(ex, p).note


# ===========================================================================
# ITEM 2 — EVERY DEFAULTED RESOLUTION IS DISCLOSED; A STATED ONE IS NOT
# ===========================================================================

class TestTheDisclosureIsComplete:

    def test_a_grain_taken_from_the_board_is_disclosed(self, ex):
        p = parsed("why cant this be moved", Intent.WHY_HERE,
                   pointed=(SubjectKind.ORDER,))
        d = _dispatched(ex, p, selection={"order": "ORD-000013",
                                          "machine": "PAINT-01", "op_seq": 20})
        assert "op20" in d.note
        assert "selected on the board" in d.note

    def test_an_assumed_direction_is_disclosed(self, ex):
        p = parsed("why cant this be moved", Intent.WHY_HERE,
                   pointed=(SubjectKind.ORDER,))
        d = _dispatched(ex, p, selection={"order": "ORD-000013",
                                          "machine": "PAINT-01", "op_seq": 20})
        assert "EARLIER" in d.note

    def test_a_STATED_direction_is_never_read_back(self, ex):
        """The rule that keeps the line short enough to be read: a planner is
        never told back what they just said."""
        p = parsed("what would it take to get ORD-000013 op20 earlier",
                   Intent.WHAT_WOULD_CHANGE, orders=("ORD-000013",), op_seq=20,
                   move_direction=MoveDirection.EARLIER)
        assert "read as EARLIER" not in _dispatched(ex, p).note

    def test_a_question_that_assumed_nothing_gets_no_extra_line(self, ex):
        """"why is this here" is not about moving, so nothing was defaulted and
        the note is exactly what it was before this session."""
        p = parsed("why is ORD-000013 op20 here", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        note = _dispatched(ex, p).note
        assert "read as EARLIER" not in note
        assert "selected on the board" not in note

    def test_a_named_target_never_gets_a_direction_disclosed(self, ex):
        """`what-would-change` resolves a NAMED DAY against the calendar inside
        the assembler, so the dispatch cannot promise which way it went — and a
        disclosure that states the wrong direction is worse than silence."""
        p = parsed("can ORD-000013 op20 move to Friday", Intent.WHAT_WOULD_CHANGE,
                   orders=("ORD-000013",), op_seq=20,
                   move_direction=MoveDirection.UNSTATED, move_target="Friday")
        assert "read as EARLIER" not in _dispatched(ex, p).note


# ===========================================================================
# ITEM 3 — THE PREMISE IS CHECKED, IN BOTH DIRECTIONS
# ===========================================================================

class TestTheMobilityFloor:
    """The parse reports; the dispatch decides (R-AI5(8)). Measured
    immediately after prompt v17: the live model set `move_direction` on
    `why-here` in 0 of 5 mobility phrasings, so the floor is what makes the
    check fire at all."""

    @pytest.mark.parametrize("q", [
        "why cant this be moved", "why can't this bar be moved",
        "why is this stuck", "why wont it budge",
        "why cant ORD-000128 op20 be moved", "is this one locked",
    ])
    def test_it_recognises_a_mobility_claim(self, q):
        assert mp.asks_about_moving(q)

    @pytest.mark.parametrize("q", [
        "why is this here", "whats holding it up", "why the wait",
        "why cant it be earlier", "when does ORD-000013 finish",
        "why is ORD-000013 late", "which machines are unlocked",
    ])
    def test_it_stays_silent_on_everything_else(self, q):
        """The vocabulary is MEASURED, not designed (`predicate_coverage`'s
        rule): a wrong entry fires a premise check on a question that assumed
        nothing. "why cant it be earlier" STATES its direction, so it has
        nothing to disclose and nothing to correct."""
        assert not mp.asks_about_moving(q)

    def test_the_floor_never_routes(self, ex):
        """It can only ever ADD a check to a route the parse already chose."""
        p = parsed("why cant this be moved", Intent.WHY_HERE,
                   pointed=(SubjectKind.ORDER,))
        d = _dispatched(ex, p, selection={"order": "ORD-000013",
                                          "machine": "PAINT-01", "op_seq": 20})
        assert d.route == Intent.WHY_HERE.value


class TestTheVerdictItself:
    """`mobility_premise.assess` — the ORDER of the tests is the ruling."""

    def test_a_later_opening_refutes_the_premise(self):
        v = mp.assess(later_at=datetime(2026, 1, 23, 16, 21),
                      earlier_verdict="could_not")
        assert v.verdict == mp.VERDICT_LATER_OPEN
        assert v.refutes and not v.holds

    def test_a_chose_verdict_refutes_it_from_the_other_side(self):
        v = mp.assess(earlier_verdict="chose")
        assert v.verdict == mp.VERDICT_EARLIER_OPEN
        assert v.refutes

    def test_bound_earlier_and_nothing_later_means_the_premise_HOLDS(self):
        v = mp.assess(earlier_verdict="could_not")
        assert v.verdict == mp.VERDICT_BOXED_IN
        assert v.holds and not v.refutes

    def test_a_held_bar_outranks_any_opening(self):
        """An opening past a committed front is a true fact about an irrelevant
        question — 4B.14's stale-true-fact rule, at this seam."""
        v = mp.assess(held_kind=mp.HELD_FROZEN, held_at=REF,
                      later_at=datetime(2026, 1, 23), earlier_verdict="chose")
        assert v.verdict == mp.VERDICT_HELD
        assert v.holds

    def test_a_chunked_op_is_UNDECIDABLE_and_is_neither(self):
        """The ruled species a sixth time (CostProof 4B.18, partitions 4B.21,
        FeasibilityGhost 4B.23): a claim about the PLANT is never manufactured
        from a limit of OUR METHOD."""
        v = mp.assess(chunk_count=3, later_at=datetime(2026, 1, 23),
                      earlier_verdict="chose")
        assert v.verdict == mp.VERDICT_UNDECIDABLE
        assert not v.holds and not v.refutes

    def test_an_unrecognised_earlier_verdict_claims_nothing(self):
        """4B.23's fail-safe rule: an unknown status fails to the state that
        claims least. Only `chose` refutes."""
        assert mp.assess(earlier_verdict="undetermined").verdict \
            == mp.VERDICT_BOXED_IN
        assert mp.assess(earlier_verdict=None).verdict == mp.VERDICT_BOXED_IN


class TestTheCorrectionFiresAndDoesNot:

    def test_a_movable_bar_asked_as_stuck_is_CORRECTED_FIRST(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        assert text.splitlines()[0].startswith("It can be moved")

    def test_the_correction_names_WHICH_direction_is_open(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        assert "room LATER" in text
        assert "blocked is moving it EARLIER" in text

    def test_the_explanation_still_follows_the_correction(self, ex):
        """A LEAD, not a replacement — unlike 4B.13's placement premise, the
        chain below is still correct and is still what was asked for."""
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        assert "couldn't start before" in text
        assert "docs/05 C3" in text

    def test_a_TRUE_premise_gets_NO_correction(self, ex):
        """The other half of the guard. Without it this grades nothing: a check
        that always fires is not a check."""
        world = _world()
        world._e["constraint"] = [{
            "id": "c-pin", "constraint_type": "pinned_window",
            "subjects": ["op-13-20"],
            "parameters": {"window": {"start": "2026-01-15T07:00:00Z"}}}]
        e = Explainer(_Store(world), _Index(), snapshot_id="snap-test")
        text = _answer(e, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        assert "It can be moved" not in text
        assert "\"can't be moved\" is fair" in text
        assert "docs/05 A7/F1" in text

    def test_a_question_that_is_not_about_moving_has_NO_premise_block(self, ex):
        """Absent by construction, never measured as nothing (4B.24's
        discipline): "why is this here?" keeps its answer to the character."""
        bundle = ex.route("why-here", {"order": "ORD-000013",
                                       "machine": "PAINT-01", "op_seq": 20,
                                       "question": "why is this here?"})
        assert bundle.key_facts["mobility"] is None
        text = TemplateRenderer().render(bundle)
        assert "Later:" not in text
        assert "Earlier — what's stopping it:" not in text


# ===========================================================================
# ITEM 4 — THE TWO-DIRECTION SHAPE
# ===========================================================================

class TestTheTwoDirectionAnswer:

    def _text(self, explainer):
        return _answer(explainer, "why-here", order="ORD-000013",
                       machine="PAINT-01", op_seq=20,
                       move_direction="unstated",
                       question="why cant this be moved")

    def test_both_directions_are_present_and_LABELLED(self, ex):
        text = self._text(ex)
        assert "Earlier — what's stopping it:" in text
        assert "Later:" in text
        assert text.index("Earlier — what's stopping it:") < text.index("Later:")

    def test_the_later_half_states_a_computed_instant(self, ex):
        text = self._text(ex)
        assert "The first opening on PAINT-01 where the whole operation fits" \
            in text

    def test_it_says_the_opening_is_not_a_price(self, ex):
        """4B.16's necessary-never-sufficient rule, carried. An opening a
        planner reads as permission is the failure this clause prevents."""
        text = self._text(ex)
        assert "WHERE it could go, not what it would cost" in text

    def test_it_INVITES_the_route_that_prices_it(self, ex):
        """R-AI3(3): the invitation completes the thought, and it names the
        machinery that actually verifies the claim it is pointing at."""
        text = self._text(ex)
        assert "what would pushing ORD-000013 op20 out cost?" in text
        assert "drag it on the board" in text

    def test_the_later_half_never_prices_anything_itself(self, ex):
        """The composition rule: every clause traces to a route that already
        verifies it. A currency figure here would be a fresh solver claim from
        a route with no pricer behind it."""
        text = self._text(ex)
        later = text.split("Later:", 1)[1]
        assert "$" not in later

    def test_a_boxed_in_bar_says_the_premise_was_FAIR(self):
        """BOXED-IN is asserted here and NOT observed live: the census over
        both pinned worlds (386 and 56 bars) found 0 of either this verdict or
        EARLIER-OPEN — see the close-out §6. Guarded by unit test precisely
        because it is unreachable on the boards we have."""
        v = mp.assess(earlier_verdict="could_not")
        assert v.verdict == mp.VERDICT_BOXED_IN and v.holds

    def test_a_chunked_bar_declines_in_BOTH_directions_by_name(self):
        v = mp.assess(chunk_count=3, earlier_verdict="chose")
        assert v.verdict == mp.VERDICT_UNDECIDABLE


# ===========================================================================
# NEGATIVE CONTROLS — each proves the guard above it can go red
# ===========================================================================

class TestNegativeControls:
    """Each of these asserts the DEFECT, so it fails the moment the fix is
    reverted and passes only against the pre-fix behaviour it describes. They
    are the reason the guards above are not vacuous — 4B.28 §5a.123: a control
    that calls past the broken line proves nothing."""

    def test_control_the_grain_is_lost_when_route_params_ignores_it(self):
        """Reverting Item 1 means `route_params` emits no `op_seq`. Asserted as
        the POSITIVE property, so this test is what goes red."""
        p = parsed("why cant ORD-000013 op20 start earlier", Intent.WHY_HERE,
                   orders=("ORD-000013",), op_seq=20)
        assert "op_seq" in route_params(p, p.question), (
            "route_params dropped the grain — this is exactly the HEAD defect")

    def test_control_a_silent_direction_is_the_defect(self, ex):
        p = parsed("why cant this be moved", Intent.WHY_HERE,
                   pointed=(SubjectKind.ORDER,))
        note = _dispatched(ex, p, selection={"order": "ORD-000013",
                                             "machine": "PAINT-01",
                                             "op_seq": 20}).note
        assert note.count(";") >= 2, (
            "the note carried one resolution where three were made")

    def test_control_the_uncorrected_premise_is_the_defect(self, ex):
        """ITS FIRST VERSION DID NOT FIRE, and the reason is worth keeping.

        It asserted `not text.startswith("ORD-000013 op20 couldn't start
        before")` — and with the correction physically reverted the answer
        STILL did not start with that line, because Item 4's "Earlier —" label
        sits above it. The control was calling past the broken line: 4B.28
        §5a.123's species, found the only way it can be found, by reverting the
        fix and looking. It now asserts the correction is in the text ABOVE the
        earlier half, which is the thing that goes away."""
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        head = text.split("Earlier — what's stopping it:")[0]
        assert "It can be moved" in head, (
            "the answer explained the chain and never corrected the premise")

    def test_control_a_one_direction_answer_is_the_defect(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       op_seq=20, move_direction="unstated",
                       question="why cant this be moved")
        assert "Later:" in text, "the answer spoke about one direction only"


# ===========================================================================
# PREMISE TESTS — the world really is what these guards assume
# ===========================================================================

class TestPremises:

    def test_the_fixture_bar_really_does_have_room_later(self, ex):
        """Every Item 3/4 assertion rests on this. If PAINT-01 had no later
        opening the correction would be wrong to fire and the guards would be
        green for the wrong reason."""
        kf = ex.route("why-here", {"order": "ORD-000013", "machine": "PAINT-01",
                                   "op_seq": 20, "move_direction": "unstated",
                                   "question": "q"}).key_facts
        assert kf["mobility"]["later_at"] is not None

    def test_the_fixture_bar_really_is_bound_EARLIER(self, ex):
        """…and the two halves of the answer are genuinely different facts."""
        kf = ex.route("why-here", {"order": "ORD-000013", "machine": "PAINT-01",
                                   "op_seq": 20, "question": "q"}).key_facts
        assert kf["verdict"] == "could_not"

    def test_the_fixture_order_really_has_more_than_one_operation(self, ex):
        """Item 1 is meaningless on a single-operation order."""
        kf = ex.route("why-here", {"order": "ORD-000013", "machine": "PAINT-01",
                                   "question": "q"}).key_facts
        assert kf["op_count"] > 1
