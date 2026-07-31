"""SESSION 4B.22 — THE SECOND QUESTION.

Four measured defects, two classes, and every guard here runs over the LIVE
DISPATCH (``interpreter.run_ask``) rather than over ``Explainer.route``.

======================================================================
WHY THE LIVE DISPATCH, AND NOT THE ASSEMBLER
======================================================================

4B.21's own close-out (Item 7): A GUARD THAT SUPPLIES ITS OWN ARGUMENTS PROVES
THE ASSEMBLER, NOT THE PATH. Every cross-surface test in this repo was green
while a planner asking "how many orders are in this plan" got a route that could
not see the beyond-horizon region, because the tests passed a document in hand
and the ask path injects one from an INTENT ALLOW-LIST that route was not on.

Class A here is worse than an allow-list: it is a piece of state that has to
survive a TURN BOUNDARY. A single-turn test cannot see it at all. So every Class
A assertion drives two consecutive ``run_ask`` calls against one session id,
exactly as the cockpit and the exam harness do, and reads the SECOND answer.

======================================================================
CLASS A — "show me the evidence for that"
======================================================================

MEASURED, on the pinned board, one turn after an answer citing a real record:

    planner: why is ORD-000013 op20 on PAINT-01
    answer : ... there was no alternative to weigh [record: 47f106af...]
    planner: show me the evidence for that
    answer : I don't have a claim of my own open to ground.

THE RULING (docs/04, 2026-07-31): "that" following an answer resolves to THAT
ANSWER. Three cases, all authored, none silent:

    cited     the prior answer carried records -> they open
    authored  it carried none -> say so plainly; that is a different fact from
              having nothing open, and the old copy actively misdirected here
              ("the records behind it are cited on it", said about a CLARIFY)
    synthesis its per-claim provenance opens, unchanged (4B.5 CU5)

======================================================================
CLASS B — the answer exists and no route reached it
======================================================================

    B1  "is CUT-01 overloaded" -> `machine-schedule` listed 18 placements and
        stated no utilisation figure, while 4B.20's working-time figure sat on
        the synthesis toolbox alone (docs/07 §5a.69).
    B2  "if I could fix one thing what should it be" -> a bare refusal on a
        board where the opener had already ranked four things by consequence.
    B3  "are orders all-in or all-out" -> answered truly, about something else.

======================================================================
THE PREMISE TESTS
======================================================================

Every assertion below is conditional on the fixture actually producing the
condition. `test_premise_*` asserts each one separately: a first turn that
really cites records, a first turn that really cites none, a machine that
really has a readable calendar and placements, an opener that really ranks
something, and a board whose declared-vs-placed split is genuinely non-trivial.

======================================================================
NEGATIVE CONTROLS (run this session, recorded in docs/closeouts/4B.22.md)
======================================================================

  (a) make `run_ask` skip the answer-memory write -> the two Class A cited
      tests fail; the authored-copy test fails; B1/B2/B3 GREEN.
  (b) drop `machine_load` from the `machine-schedule` key_facts -> the two B1
      tests fail; Class A and B2/B3 GREEN.

Each half is red only for its own defect, which is what makes them controls
rather than a smoke test.

======================================================================
ITS LIMIT, STATED (the 4B.19/4B.20/4B.21 discipline)
======================================================================

This file watches the ASK PATH: parse contract in, dispatched route out,
template rendering read. It does NOT watch the cockpit's JavaScript, the LLM
renderer's reword (prove_it and briefing are rendered verbatim by construction,
asserted elsewhere), or whether the LIVE PARSE sends any particular phrasing to
any particular intent — that is measured, not asserted, and this session's
measurement is in the close-out. A guard that pinned the parse would be pinning
a model's output.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests"))

from parse_doubles import ScriptedParser  # noqa: E402

from mre.contracts.parse import (  # noqa: E402
    FollowupKind, Intent, ParsedQuestion, SubjectKind, SubjectRef,
)

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the world: a REAL solved rolling board with a REAL split
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def board(tmp_path_factory):
    """18 orders in a 10-day window — the same shape 4B.21's guard uses, for
    the same reason: some orders placed, some not, more operations declared
    than placed. Deterministic mode (workers 1, seed 42)."""
    from generate_erp_dataset import generate
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    d = tmp_path_factory.mktemp("secondq")
    generate(d / "sub", scenario="pilot_scale", orders=18, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=10, frozen_days=3, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=60.0, det_total=2.0,
                              persist=True)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id="sched-sq",
                                    run_id=str(uuid.uuid4()), identity_map=idmap)
    dd = doc.model_dump(mode="json")
    index = EvidenceIndex().build(plant.out_dir / "runs")
    ex = Explainer(plant.store, index, snapshot_id=plant.snapshot_id)
    return ex, dd


@pytest.fixture(scope="module")
def busiest(board):
    """The machine carrying the most work, and its load — the B1 subject."""
    from mre.modules.evidence_tools import machine_load
    ex, _doc = board
    loads = []
    for name in sorted(set((ex._machine_refs or {}).values())):
        ml = machine_load(ex, name)
        if ml:
            loads.append(ml)
    loads.sort(key=lambda m: -(m.get("working_minutes") or 0))
    assert loads, "no machine on this board carries any work"
    return loads[0]


@pytest.fixture(scope="module")
def disposition(board):
    from mre.modules.order_disposition import census
    ex, doc = board
    return census(ex, doc)


# ---------------------------------------------------------------------------
# driving the LIVE dispatch
# ---------------------------------------------------------------------------

def _p(question: str, intent: Intent, *, order=None, machine=None,
       followup=FollowupKind.NONE, confidence=0.95) -> ParsedQuestion:
    subjects = []
    if order:
        subjects.append(SubjectRef(kind=SubjectKind.ORDER, raw=order, ref=order))
    if machine:
        subjects.append(SubjectRef(kind=SubjectKind.MACHINE, raw=machine,
                                   ref=machine))
    return ParsedQuestion(question=question, intent=intent, subjects=subjects,
                          followup_of=followup, confidence=confidence)


class Conversation:
    """A live two-turn (or n-turn) ask session, driven exactly as the cockpit
    drives it: one session id, the history channel carried forward, the
    document threaded in, and NOTHING about the previous answer passed by hand.

    That last clause is the whole point of this harness. If a turn can only
    resolve by reading state the server kept for itself, this is the only shape
    of test that can prove it."""

    def __init__(self, board, table: dict, session: str):
        from mre.modules.interpreter import AnswerMemory, SynthesisMemory
        self._ex, self._doc = board
        self._parser = ScriptedParser(table)
        self._session = session
        self._history: list[dict] = []
        # FRESH per conversation. The live stores are module singletons; sharing
        # them across tests would make one test's last answer another's context.
        self._answers = AnswerMemory()
        self._synth = SynthesisMemory()
        self.results: list = []

    def ask(self, question: str):
        from mre.modules.interpreter import run_ask
        from mre.modules.renderers import TemplateRenderer
        res = run_ask(self._ex, question, parser=self._parser,
                      context={"history": self._history[-4:], "selection": {},
                               "last_answered_subject": {}, "card": {}},
                      session_id=self._session, document=self._doc,
                      memory=self._synth, answer_memory=self._answers)
        self._history.append({"question": question, "route": res.route,
                              "order": None, "machine": None})
        res.text = TemplateRenderer().render(res.bundle)  # type: ignore[attr-defined]
        self.results.append(res)
        return res


def _why_here_table(order: str, machine: str) -> dict:
    return {
        "why is that order on that machine":
            _p("why is that order on that machine", Intent.WHY_ON_MACHINE,
               order=order, machine=machine),
        "show me the evidence for that":
            _p("show me the evidence for that", Intent.PROVE_IT,
               followup=FollowupKind.PROVE_IT),
    }


@pytest.fixture(scope="module")
def a_cited_order(board):
    """An order+machine pair whose `why-on-machine` answer carries records WHEN
    ASKED THROUGH THE LIVE DISPATCH — the premise Class A's cited branch stands
    on.

    THE FIXTURE'S OWN FIRST RUN IS THE LESSON AGAIN. Choosing the pair off
    ``Explainer.route`` alone picked a BEYOND-HORIZON order, whose answer carries
    records when the assembler is called directly and which the live dispatch
    diverts to `why-not-scheduled-yet` before the route is ever reached. The
    premise was true of the assembler and false of the path — 4B.21's Item 7, in
    the fixture of the test written to avoid it. So the pair is taken from the
    document's own assignments AND confirmed through ``dispatch``.
    """
    from mre.modules.interpreter import dispatch
    ex, doc = board
    pairs = []
    for a in doc.get("assignments") or []:
        for wo in a.get("work_orders") or []:
            if a.get("external_name"):
                pairs.append((str(wo), str(a["external_name"])))
    for order, machine in sorted(set(pairs)):
        d = dispatch(ex, _p("q", Intent.WHY_ON_MACHINE, order=order,
                            machine=machine), document=doc)
        if d.route == "why-on-machine" and d.bundle.ordered_records:
            return order, machine
    pytest.skip("no why-on-machine answer reachable through dispatch cites a "
                "record on this board")


# ---------------------------------------------------------------------------
# PREMISE — without these, every assertion below passes vacuously
# ---------------------------------------------------------------------------

def test_premise_a_first_turn_really_cites_records(board, a_cited_order):
    """4B.18's failure mode refused in advance: if turn 1 cited nothing, the
    cited branch of the drill-down would be tested by a fixture that can only
    exercise the authored branch, and both would look green.

    Asserted THROUGH THE DISPATCH, not through the assembler — the two disagree
    on a tray order, which is how this fixture's first version was wrong."""
    from mre.modules.interpreter import dispatch
    ex, doc = board
    order, machine = a_cited_order
    d = dispatch(ex, _p("q", Intent.WHY_ON_MACHINE, order=order,
                        machine=machine), document=doc)
    assert d.route == "why-on-machine", (
        f"the dispatch diverted this pair to {d.route!r}; turn 1 is not the "
        "answer the cited branch needs")
    assert d.bundle.ordered_records, (
        "turn 1 cites nothing — the cited branch is moot")


def test_premise_a_first_turn_really_cites_nothing(board):
    """And the OTHER half: the authored-copy branch needs an answer that
    genuinely carries no records. `advice` is one, on every board."""
    ex, doc = board
    b = ex.route("advice", {"question": "what should I do", "document": doc})
    assert not b.ordered_records, (
        "the advice route now carries records — the authored-copy branch of "
        "the drill-down has no specimen on this fixture")


def test_premise_the_busiest_machine_has_a_readable_calendar(busiest):
    """B1 asserts a percentage. Without a readable calendar there is no
    denominator, the route takes its OTHER branch, and the percentage
    assertions would never run."""
    assert busiest.get("working_minutes"), "the busiest machine carries no work"
    assert busiest.get("open_capacity_minutes"), (
        "no open-capacity figure — the calendar did not read, so B1's "
        "percentage branch is unexercised")
    assert busiest.get("utilization_pct") is not None


def test_premise_the_opener_ranks_something(board):
    """B2 leads with the opener's top worry. On a board with no worries at all
    there is nothing to lead with and the assertion is vacuous."""
    ex, doc = board
    opener = ex._build_opener(doc)
    assert opener.worries, "the opener ranks nothing on this board"


def test_premise_the_placement_split_is_non_trivial(disposition):
    """B3 distinguishes fully / partly / not placed. All three counts equal to
    the same number, or two of them zero, would make the sentence unfalsifiable."""
    d = disposition
    assert d.fully_placed_orders is not None, (
        "the per-order chain did not read — B3 is silent on this fixture")
    assert d.fully_placed_orders > 0, "nothing is fully placed"
    assert d.unplaced_orders > 0, (
        "nothing is unplaced — 'all in or all out' has no boundary to be "
        "all-out of, and the sentence cannot be wrong here")
    assert d.declared_operations > d.placed_operations


# ---------------------------------------------------------------------------
# CLASS A — the drill-down, over the LIVE dispatch, two turns
# ---------------------------------------------------------------------------

class TestDrillDownOpensThePriorAnswer:

    def test_a_drill_down_after_a_cited_answer_opens_its_records(
            self, board, a_cited_order):
        order, machine = a_cited_order
        c = Conversation(board, _why_here_table(order, machine), "sess-cited")
        first = c.ask("why is that order on that machine")
        assert first.bundle.ordered_records, "premise: turn 1 cited nothing"
        second = c.ask("show me the evidence for that")
        assert second.route == "prove-it"
        assert second.bundle.ordered_records, (
            "the drill-down opened NOTHING one turn after an answer that cited "
            f"{len(first.bundle.ordered_records)} record(s)")
        # The SAME records, not a re-derivation: what opens is what lit the bars.
        assert ([r.get("record_id") for r in second.bundle.ordered_records]
                == [r.get("record_id") for r in first.bundle.ordered_records])

    def test_it_names_the_question_it_is_grounding(self, board, a_cited_order):
        order, machine = a_cited_order
        c = Conversation(board, _why_here_table(order, machine), "sess-names")
        c.ask("why is that order on that machine")
        text = c.ask("show me the evidence for that").text
        assert "why is that order on that machine" in text, (
            "the drill-down opened records without saying which answer they "
            "are behind — a planner two turns in cannot tell")

    def test_it_never_claims_per_sentence_claims_a_route_does_not_have(
            self, board, a_cited_order):
        """A contracted route has no claim decomposition. Implying one would be
        the 4B.19 label defect: the label is a claim, and this one would assert
        a structure the answer never had."""
        order, machine = a_cited_order
        c = Conversation(board, _why_here_table(order, machine), "sess-nodecomp")
        c.ask("why is that order on that machine")
        text = c.ask("show me the evidence for that").text.lower()
        assert "no per-sentence claims" in text

    def test_the_no_target_floor_is_unreachable_once_anything_was_answered(
            self, board, a_cited_order):
        from mre.modules.ask_fallback_copy import PROVE_IT_NO_TARGET
        order, machine = a_cited_order
        c = Conversation(board, _why_here_table(order, machine), "sess-floor")
        c.ask("why is that order on that machine")
        assert PROVE_IT_NO_TARGET[:40] not in c.ask(
            "show me the evidence for that").text

    def test_the_no_target_floor_IS_the_answer_on_a_cold_first_turn(self, board):
        """It is still reachable, and it must be: with no prior answer at all
        there is genuinely nothing of ours to open. The rewritten copy says
        that, and no longer points at citations that do not exist."""
        from mre.modules.ask_fallback_copy import PROVE_IT_NO_TARGET
        c = Conversation(board, {"show me the evidence for that":
                                 _p("show me the evidence for that",
                                    Intent.PROVE_IT,
                                    followup=FollowupKind.PROVE_IT)},
                         "sess-cold")
        text = c.ask("show me the evidence for that").text
        assert PROVE_IT_NO_TARGET[:40] in text
        assert "cited on it" not in text, (
            "the floor still tells a planner to look for citations on an "
            "answer that does not exist")


class TestDrillDownAfterAnAnswerThatCitesNothing:
    """THE HONEST-NEGATIVE CASE, and it matters as much as the other one. The
    old copy told the planner the records were "cited on it" — about a CLARIFY,
    which cites nothing. It sent them looking for something that was not there."""

    TABLE = {
        "what should i do": _p("what should i do", Intent.ADVICE),
        "show me the evidence for that":
            _p("show me the evidence for that", Intent.PROVE_IT,
               followup=FollowupKind.PROVE_IT),
    }

    def test_it_says_the_answer_was_authored_copy(self, board):
        c = Conversation(board, self.TABLE, "sess-authored")
        first = c.ask("what should i do")
        assert not first.bundle.ordered_records, "premise: turn 1 cited something"
        text = c.ask("show me the evidence for that").text.lower()
        assert "authored copy" in text
        assert "nothing behind it to open" in text

    def test_it_is_not_the_same_answer_as_having_nothing_open(self, board):
        from mre.modules.ask_fallback_copy import PROVE_IT_NO_TARGET
        c = Conversation(board, self.TABLE, "sess-distinct")
        c.ask("what should i do")
        text = c.ask("show me the evidence for that").text
        assert PROVE_IT_NO_TARGET[:40] not in text, (
            "'this answer cites nothing' and 'I have no answer open' are "
            "different facts and the product states one of them for both")

    def test_it_names_the_question_too(self, board):
        c = Conversation(board, self.TABLE, "sess-authored-names")
        c.ask("what should i do")
        assert "what should i do" in c.ask("show me the evidence for that").text


class TestDrillDownMemoryHygiene:

    def test_a_second_drill_down_still_points_at_the_original_answer(
            self, board, a_cited_order):
        """A prove-it turn is ABOUT a previous answer, so remembering it would
        make the next drill-down drill the drill-down."""
        order, machine = a_cited_order
        c = Conversation(board, _why_here_table(order, machine), "sess-twice")
        first = c.ask("why is that order on that machine")
        c.ask("show me the evidence for that")
        third = c.ask("show me the evidence for that")
        assert ([r.get("record_id") for r in third.bundle.ordered_records]
                == [r.get("record_id") for r in first.bundle.ordered_records])

    def test_forgetting_the_conversation_forgets_the_last_answer(
            self, board, a_cited_order):
        """4B.16a's lesson: a RESET that clears four channels and misses a
        fifth. ``forget_deliveries`` is the ONE clear, and it must reach here."""
        from mre.modules.interpreter import (
            ANSWER_MEMORY, forget_deliveries, run_ask,
        )
        ex, doc = board
        order, machine = a_cited_order
        parser = ScriptedParser(_why_here_table(order, machine))
        run_ask(ex, "why is that order on that machine", parser=parser,
                session_id="sess-reset-4b22", document=doc)
        assert ANSWER_MEMORY.last("sess-reset-4b22") is not None
        forget_deliveries("sess-reset-4b22")
        assert ANSWER_MEMORY.last("sess-reset-4b22") is None

    def test_the_module_singleton_is_what_the_live_path_uses(self, board,
                                                             a_cited_order):
        """`run_ask` with no memory injected must fall back to the process-wide
        store, or the API — which injects nothing — keeps no memory at all and
        this whole feature is dead on the only path that matters."""
        from mre.modules.interpreter import ANSWER_MEMORY, run_ask
        ex, doc = board
        order, machine = a_cited_order
        ANSWER_MEMORY.forget("sess-singleton-4b22")
        run_ask(ex, "why is that order on that machine",
                parser=ScriptedParser(_why_here_table(order, machine)),
                session_id="sess-singleton-4b22", document=doc)
        last = ANSWER_MEMORY.last("sess-singleton-4b22")
        assert last is not None and last["records"]
        ANSWER_MEMORY.forget("sess-singleton-4b22")

    def test_a_prove_it_that_also_names_a_real_intent_still_falls_through(
            self, board, a_cited_order):
        """The 4A.5a specimen, pinned: "but why" one turn after a cause chain
        reads as prove-it AND names a real intent. It must be answered as that
        intent — the planner wants the question answered, not our last sentence
        re-opened. Adding the prior-answer rung must not have taken this."""
        order, machine = a_cited_order
        table = dict(_why_here_table(order, machine))
        table["but why"] = _p("but why", Intent.WHY_ON_MACHINE, order=order,
                              machine=machine, followup=FollowupKind.PROVE_IT)
        c = Conversation(board, table, "sess-fallthrough")
        c.ask("why is that order on that machine")
        assert c.ask("but why").route == "why-on-machine"


# ---------------------------------------------------------------------------
# B1 — the load figure on the route that lists the machine
# ---------------------------------------------------------------------------

class TestMachineLoadIsReachableFromTheRoute:

    def _ask(self, board, machine):
        table = {"is that machine overloaded":
                 _p("is that machine overloaded", Intent.MACHINE_SCHEDULE,
                    machine=machine)}
        c = Conversation(board, table, f"sess-load-{machine}")
        return c.ask("is that machine overloaded")

    def test_the_route_states_the_figure_and_its_denominator(self, board,
                                                             busiest):
        res = self._ask(board, busiest["machine"])
        assert res.route == "machine-schedule"
        text = res.text
        assert f"{busiest['working_minutes']:,.0f}" in text, (
            "the route still lists placements and states no working-time "
            "figure — docs/07 §5a.69, unchanged")
        assert f"{busiest['open_capacity_minutes']:,.0f}" in text, (
            "a percentage with no denominator on the surface — 4B.20's second "
            "clause, which is exactly why the toolbox reports both")
        assert f"{busiest['utilization_pct']:g}%" in text
        assert "working minute" in text

    def test_it_refuses_the_judgment_rather_than_inventing_a_threshold(
            self, board, busiest):
        text = self._ask(board, busiest["machine"]).text.lower()
        assert "no utilisation threshold is declared" in text
        assert "stated, not judged" in text

    def test_the_route_and_the_toolbox_cannot_state_different_numbers(
            self, board, busiest):
        """ONE DEFINITION (4B.21's ruling, one level down). The route and the
        synthesis toolbox read the same function, so this is true by
        construction — and asserted anyway, because "by construction" is what
        the last four sessions each believed."""
        from mre.modules.evidence_tools import EvidenceToolbox
        ex, _doc = board
        summary = EvidenceToolbox(ex).call(
            "machine_occupancy", {"machine": busiest["machine"]}).summary
        for key in ("working_minutes", "open_capacity_minutes",
                    "utilization_pct", "elapsed_span_minutes"):
            assert summary.get(key) == busiest.get(key), (
                f"{key}: toolbox says {summary.get(key)}, the route's "
                f"definition says {busiest.get(key)}")

    def test_a_multi_machine_listing_states_no_load_at_all(self, board):
        """There is no honest single denominator over a mixed listing, and
        stating the first machine's would be the fused denominator 4B.20 and
        4B.21 both ruled against."""
        table = {"show me the whole schedule":
                 _p("show me the whole schedule", Intent.SCHEDULE)}
        c = Conversation(board, table, "sess-load-all")
        res = c.ask("show me the whole schedule")
        assert res.bundle.key_facts.get("machine_load") is None
        assert "working minute(s) against" not in res.text

    def test_working_time_is_never_the_elapsed_span(self, board, busiest):
        """4B.20's ruling, on the new surface. On a chunked machine the span
        exceeds the open capacity; printing it as the numerator is the 3.9x
        error, and it must not be the number on the page."""
        text = self._ask(board, busiest["machine"]).text
        span = busiest.get("elapsed_span_minutes")
        if span and abs(span - busiest["working_minutes"]) > 1:
            assert f"{span:,.0f} working minute" not in text


# ---------------------------------------------------------------------------
# B2 — "what should I look at first" is the opener's top item
# ---------------------------------------------------------------------------

class TestAdviceLeadsWithTheRankedItem:

    def _ask(self, board, session):
        table = {"if i could fix one thing what should it be":
                 _p("if i could fix one thing what should it be", Intent.ADVICE)}
        c = Conversation(board, table, session)
        return c.ask("if i could fix one thing what should it be")

    def test_it_leads_with_the_openers_top_worry(self, board):
        ex, doc = board
        top = ex._build_opener(doc).worries[0]
        text = self._ask(board, "sess-advice-top").text
        assert top.headline in text, (
            "the route refused while the opener had already ranked this board "
            "by consequence — the answer existed and no route reached it")

    def test_it_carries_the_pointer_that_opens_the_item(self, board):
        ex, doc = board
        top = ex._build_opener(doc).worries[0]
        if not top.pointer:
            pytest.skip("the top worry carries no pointer on this board")
        assert top.pointer in self._ask(board, "sess-advice-ptr").text

    def test_it_still_refuses_to_recommend_an_intervention(self, board):
        """The boundary 4B.4 drew is CORRECT and is kept. What changed is that
        the route no longer answers a question it can answer by refusing a
        different one."""
        text = self._ask(board, "sess-advice-refuse").text.lower()
        assert "can't recommend an intervention" in text
        assert "overtime" in text

    def test_it_names_which_of_the_two_questions_it_answered(self, board):
        text = self._ask(board, "sess-advice-names").text.lower()
        assert "not a recommendation of what to do" in text

    def test_the_ask_path_hands_advice_the_document(self, board):
        """THE 4B.21 SEAM, closed for this route. Without the document the
        opener cannot be built and the route degrades silently to the old bare
        refusal — which is precisely the failure, wearing a green test."""
        from mre.contracts.parse import Intent as I
        from mre.modules.interpreter import dispatch
        ex, doc = board
        d = dispatch(ex, _p("what should I do", I.ADVICE), document=doc)
        assert d.bundle.key_facts.get("opener_top"), (
            "`advice` did not receive the document through the live dispatch")

    def test_without_a_document_it_degrades_to_the_refusal_not_to_a_guess(
            self, board):
        ex, _doc = board
        b = ex.route("advice", {"question": "what should I do"})
        assert b.key_facts.get("opener_top") is None
        from mre.modules.renderers import TemplateRenderer
        assert "can't recommend an intervention" in TemplateRenderer().render(b)


# ---------------------------------------------------------------------------
# B3 — all in or all out, per order
# ---------------------------------------------------------------------------

class TestPartialPlacementIsAnswered:

    def _ask(self, board, session):
        table = {"are orders all in or all out":
                 _p("are orders all in or all out", Intent.INVENTORY)}
        c = Conversation(board, table, session)
        return c.ask("are orders all in or all out")

    def test_the_route_answers_the_question_that_was_asked(self, board,
                                                           disposition):
        text = self._ask(board, "sess-b3").text.lower()
        assert "all in or all out" in text, (
            "the route still answers HOW MANY are placed, which is true and "
            "is about something else (4B.21's own measurement)")

    def test_it_states_the_measurement_not_an_invariant(self, board):
        """4B.21's ruling one level down: "no order is partly placed" is a fact
        about THIS SCHEDULE; "orders are never partly placed" would be a claim
        about the product, and nothing enforces it."""
        text = self._ask(board, "sess-b3-limit").text.lower()
        assert "not a rule the product enforces" in text
        assert "work package" in text

    def test_the_counts_partition_the_known_orders(self, disposition):
        d = disposition
        assert (d.fully_placed_orders + d.partly_placed_orders
                + d.unplaced_orders) == d.known_orders

    def test_the_per_order_walk_agrees_with_the_disposition_arithmetic(
            self, disposition):
        """Two independent computations of the same set. ``unscheduled_orders``
        is derived (known − scheduled − excluded); ``unplaced_orders`` is
        counted per order off the fulfillment chain. They must agree, and if
        they ever do not, one of the two is measuring something else."""
        d = disposition
        assert d.unplaced_orders == d.unscheduled_orders
        assert d.fully_placed_orders + d.partly_placed_orders == d.scheduled_orders

    def test_an_unreadable_chain_says_nothing_rather_than_zero(self, board):
        """"No order is partly placed" must never be manufactured out of a
        failed read. Three absent figures, not three zeros."""
        from mre.modules.order_disposition import _placement_completeness
        assert _placement_completeness([], [{"id": "d"}], [{"id": "o"}],
                                       set()) == (None, None, None)
        assert _placement_completeness([{"demand_ref": "d",
                                         "workpackage_ref": "w"}],
                                       [], [], set()) == (None, None, None)

    def test_a_partly_placed_board_says_SPLIT_and_not_all_or_nothing(self):
        """The other branch, exercised directly: the fixture cannot produce a
        partial order (the admission unit is the whole work package), so the
        copy that would fire on one is rendered from a constructed census
        rather than left unproven."""
        from mre.modules.ask_fallback_copy import (
            INVENTORY_ALL_OR_NOTHING, INVENTORY_PARTLY_PLACED,
        )
        from mre.modules.renderers import TemplateRenderer
        lines: list[str] = []
        TemplateRenderer._render_partial_placement(lines, {
            "placement_all_or_nothing": False, "fully_placed_order_count": 20,
            "partly_placed_order_count": 3, "unplaced_order_count": 17})
        body = "\n".join(lines)
        assert INVENTORY_PARTLY_PLACED.format(partly=3, full=20, unplaced=17) in body
        assert INVENTORY_ALL_OR_NOTHING.split(":")[0] not in body

    def test_it_is_silent_when_the_figure_is_absent(self):
        from mre.modules.renderers import TemplateRenderer
        lines: list[str] = []
        TemplateRenderer._render_partial_placement(
            lines, {"placement_all_or_nothing": None})
        assert lines == []
