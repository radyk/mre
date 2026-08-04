"""SESSION 4A TEACHING-GRAFT (d.1) — WHAT THE PRODUCT KEEPS FROM THE LAST TURN.

Two rulings and five defects out of the (d.0) multi-turn recon
(`docs/closeouts/4a-teaching-d0-multiturn-recon.md`). Everything here is about
state that has to survive — or must NOT survive — a turn boundary, which is why
almost every assertion below drives two or more consecutive `run_ask` calls
against one session id rather than calling an assembler with arguments in hand
(4B.21's rule: a guard that supplies its own arguments proves the assembler, not
the path).

======================================================================
R-MT1 — CARRIED ANSWER STATE IS SCHEDULE-SCOPED
======================================================================

MEASURED (d.0 P4). One conversation, one accept, two boards:

    planner [A]: how many orders are late and what is the total tardiness cost
    answer  [A]: 102 late order(s) ...
    -- the cockpit rebinds to board B: 56 bars, nothing late --
    planner [B]: show me the evidence for that
    answer  [B]: here is the whole record set it was assembled from
                 (102 record(s)): lateness_minutes = 5297.0 for ORD-000001 ...

Board A's record ids against a board that holds none of them. `ANSWER_MEMORY`,
`SYNTHESIS_MEMORY` and `_DELIVERED` were keyed by SESSION ID ALONE;
`ParseMemory.key` already carried the schedule, which is why the parse cache was
safe and these three were not.

Three clauses, and each is asserted here as its own thing:
  (1) the STORE KEY — a read against a different schedule is impossible;
  (2) the CLIENT CLEAR — asserted in a real browser, not here
      (`tests/cockpit/carriedstate.spec.mjs`);
  (3) the SENTENCE — where a gesture reaches for a carried answer and the board
      changed underneath it, the answer says so rather than falling to the
      never-answered floor.

======================================================================
R-LD5 — DISCLOSURE FOLLOWS THE SUBJECT, NOT THE RESOLVER
======================================================================

MEASURED (d.0 P2b). "why cant this be moved earlier", nothing selected, one turn
after "why is ORD-000073 op10 placed where it is" → a full counterfactual about
ORD-000073 op10, with `source: utterance` and an EMPTY disclosure line. Every
rung of the ladder was empty; the PARSE MODEL read the referent out of the RECENT
TURNS block and `bind_subjects`' fallback resolved it. The same subject recovered
by the LADDER is disclosed in full.

======================================================================
THE FOUR SMALLER ONES
======================================================================

  D-01  `drill-down` promised the previous answer in its declared meaning, took
        a `history` argument for it, and no caller ever passed one — so with no
        ordinal in the question it opened the board's most severe gate finding.
  D-06  a zero-record TESTIMONY answer was described by prove-it as "authored
        copy — it states what this product can and can't do".
  D-07  `deaf` fired on a legitimate deictic follow-up the parse had itself
        marked `followup_of: deepen`.
  D-11  `_DELIVERED` had no cap on the number of sessions.

======================================================================
NEGATIVE CONTROLS (run this session, recorded in the close-out)
======================================================================

Each reverts ONE mechanism in `src/` and must turn its own tests red while the
others stay green; every restore is proven byte-identical by sha256.

  (a) drop `schedule_id` from the three store keys      -> TestStoreKey red
  (b) drop `prior` from the drill-down's route_params   -> TestDrillDownWired red
  (c) restore the `findings[0]` fallback                -> TestDrillDownRefusal red
  (d) decide the prove-it branch from the record count  -> TestEmptyRead red
  (e) report CONVERSATION as UTTERANCE again            -> TestConversationSource red
  (f) drop the followup gate from `bundle_repeat`       -> the false-positive test red
  (f2) gate on `followup_of` ALONE — the FIRST DRAFT,
       which the sweep caught suppressing the one true
       positive this rider has ever produced           -> the true-positive test red
  (g) append an errored turn to harness history        -> TestHarnessParity red
  (h) `onVersionChange` clears nothing else (cockpit)  -> carriedstate.spec.mjs red

(a)-(g) run from `tools/spikes/teaching_graft_d1/controls.py`; (h) is driven
separately against the Playwright harness. Each also names a control SET that
must stay GREEN — a revert that reddens everything is a smoke test, not a
control.

======================================================================
ITS LIMIT, STATED
======================================================================

This file watches the PYTHON ask path with a SCRIPTED parse. It does not watch
the cockpit's JavaScript (clause 2 is asserted in Playwright), and it does not
assert that any live phrasing reaches any particular intent — that is measured
in the close-out, not pinned here, because pinning it would pin a model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tests"))

from parse_doubles import ScriptedParser, parsed  # noqa: E402

from mre.contracts.parse import (  # noqa: E402
    FollowupKind, Intent, ParsedQuestion, SubjectKind, SubjectRef,
    SubjectSource,
)
from mre.modules.explainer import Explainer  # noqa: E402
from mre.modules.interpreter import (  # noqa: E402
    _DELIVERED, _DELIVERED_SESSIONS, AnswerMemory, SynthesisMemory,
    bundle_repeat, forget_deliveries, remember_delivery, run_ask,
)
from mre.modules.evidence_index import EvidenceIndex  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402
from mre.modules.snapshot_store import SnapshotStore  # noqa: E402
from mre.__main__ import main as mre_main  # noqa: E402

BOARD_A = "sched-parent"
BOARD_B = "sched-child"
DATASET = REPO / "datasets" / "glass_box"
#: An order this world really carries, so a subject resolution is a real one.
ORDER = "ORD-05"


@pytest.fixture(scope="module")
def explainer(tmp_path_factory):
    """A REAL glass_box solve — the same world `test_ai_voice`'s `clean`
    fixture uses, and for the same reason: the subjects have to resolve and the
    records have to exist, or a test about what a second turn OPENS is asserting
    over an empty list."""
    out = tmp_path_factory.mktemp("carried")
    rc = mre_main(["--submission", str(DATASET), "--out", str(out),
                   "--snapshot-id", "snap-c", "--solver-workers", "1",
                   "--solver-seed", "0"])
    assert rc == 0
    return Explainer(SnapshotStore(out / "snapshots"),
                     EvidenceIndex.load(out / "evidence_index.json"),
                     snapshot_id="snap-c")


def _one_claim_answer():
    """A hardened synthesis answer with ONE interpretive claim — the object
    `SYNTHESIS_MEMORY` holds and `pick_claim` picks from."""
    from mre.contracts.synthesis import (
        ClaimStatus, SynthesisAnswer, VerifiedClaim,
    )
    return SynthesisAnswer(
        question="how does a frozen zone normally work",
        claims=[VerifiedClaim(text="ORD-05 is queued behind the cutting line.",
                              status=ClaimStatus.INTERPRETIVE)])


def _prove_it(question: str = "show me the evidence for that") -> ParsedQuestion:
    return parsed(question, Intent.PROVE_IT,
                  followup_of=FollowupKind.PROVE_IT)


def _drill(question: str = "can you show me that on my board") -> ParsedQuestion:
    return parsed(question, Intent.DRILL_DOWN)


class Panel:
    """The cockpit ask panel, in Python: one session id, a rolling history, a
    MUTABLE schedule binding, and nothing about the previous answer handed over
    by the caller. `rebind` is `main.js::onVersionChange`."""

    def __init__(self, explainer, table: dict, session: str,
                 schedule: str = BOARD_A) -> None:
        self._ex = explainer
        self._parser = ScriptedParser(table)
        self.session = session
        self.schedule = schedule
        self.history: list[dict] = []
        self.answers = AnswerMemory()
        self.synth = SynthesisMemory()

    def ask(self, question: str):
        res = run_ask(self._ex, question, parser=self._parser,
                      context={"history": self.history[-4:], "selection": {},
                               "last_answered_subject": {}, "card": {}},
                      session_id=self.session, schedule_id=self.schedule,
                      memory=self.synth, answer_memory=self.answers)
        self.history.append({"question": question, "route": res.route,
                             "order": None, "machine": None})
        res.text = TemplateRenderer().render(res.bundle)  # type: ignore[attr-defined]
        return res

    def rebind(self, schedule: str, *, clear_client: bool = True) -> None:
        """R-MT1 clauses 1 and 2, separable on purpose.

        `clear_client=False` is the gesture as the recon measured it — the
        schedule changes and the panel keeps everything — and it is the ONLY
        way to prove clause 1 on its own. With clause 2 shipped the browser
        also clears, but a store that is only safe because a client remembered
        to clear is safe by discipline, which is what the ruling refuses."""
        self.schedule = schedule
        if clear_client:
            self.history = []


# ===========================================================================
# R-MT1 clause 1 — the store key
# ===========================================================================

class TestStoreKey:
    """The three carried-answer stores, each on its own. NEGATIVE CONTROL (a)."""

    def test_the_answer_memory_is_unreadable_from_another_schedule(self):
        m = AnswerMemory()
        m.remember("s", BOARD_A, "late-orders", "how many are late",
                   [{"record_id": "r1"}])
        assert m.last("s", BOARD_A) is not None
        assert m.last("s", BOARD_B) is None, (
            "board A's answer is readable from board B — D-05, the defect")

    def test_the_synthesis_memory_is_unreadable_from_another_schedule(self):
        m = SynthesisMemory()
        m.remember("s", BOARD_A, object())
        assert m.last("s", BOARD_A) is not None
        assert m.last("s", BOARD_B) is None

    def test_the_delivery_memory_is_unreadable_from_another_schedule(self):
        forget_deliveries("s-deaf")
        answer = "26 orders on 15 machines."
        remember_delivery("s-deaf", BOARD_A, "briefing", "how does it look",
                          answer)

        class _B:
            key_facts: dict = {}

        # Same session, different question, same answer, SAME board -> deaf.
        same = _B()
        same.key_facts = {}
        bundle_repeat(same, {"history": []},
                      parsed("what should i worry about", Intent.BRIEFING),
                      answer, "s-deaf", schedule_id=BOARD_A)
        assert same.key_facts.get("deaf") == 1, "premise: deaf does not fire"

        other = _B()
        other.key_facts = {}
        bundle_repeat(other, {"history": []},
                      parsed("what should i worry about", Intent.BRIEFING),
                      answer, "s-deaf", schedule_id=BOARD_B)
        assert not other.key_facts, (
            "an answer given about board A made the product doubt itself about "
            "board B")
        forget_deliveries("s-deaf")

    def test_a_forget_takes_every_board_the_conversation_touched(self):
        """R-MT1: the key is (session, schedule) and the CLEAR is by session.
        A conversation that straddled two boards is the defect the key fixes;
        forgetting it must not leave half of it behind."""
        m = AnswerMemory()
        m.remember("s", BOARD_A, "late-orders", "q", [{"record_id": "r"}])
        m.remember("s", BOARD_B, "late-orders", "q", [{"record_id": "r"}])
        m.forget("s")
        assert m.last("s", BOARD_A) is None and m.last("s", BOARD_B) is None

    def test_forget_deliveries_reaches_all_three_stores(self):
        """4B.16a's lesson, and the third store it has been missing since
        4B.22: `forget_deliveries`' own docstring calls itself the ONE place
        that clears server-side conversation state, and it cleared two of
        three. A RESET therefore left the last synthesis answer's CLAIMS live
        across the boundary."""
        from mre.modules.interpreter import ANSWER_MEMORY, SYNTHESIS_MEMORY
        ANSWER_MEMORY.remember("s-all", BOARD_A, "late-orders", "q", [])
        SYNTHESIS_MEMORY.remember("s-all", BOARD_A, object())
        remember_delivery("s-all", BOARD_A, "late-orders", "q", "body")
        forget_deliveries("s-all")
        assert ANSWER_MEMORY.last("s-all", BOARD_A) is None
        assert SYNTHESIS_MEMORY.last("s-all", BOARD_A) is None
        assert not [k for k in _DELIVERED if k[0] == "s-all"]

    def test_a_session_less_caller_still_carries_nothing(self):
        """Unchanged behaviour, asserted so the new key cannot have made a
        session-less caller start sharing one bucket."""
        m = AnswerMemory()
        m.remember(None, BOARD_A, "late-orders", "q", [{"record_id": "r"}])
        assert m.last(None, BOARD_A) is None

    def test_the_delivery_store_is_bounded_by_session_now(self):
        """D-11. `AnswerMemory` and `SynthesisMemory` were LRU-32 and this one
        had a per-session row cap and NO cap on the number of sessions, so a
        long-lived API process accumulated an entry per browser tab forever."""
        for k in [k for k in _DELIVERED]:
            _DELIVERED.pop(k, None)
        for i in range(_DELIVERED_SESSIONS + 10):
            remember_delivery(f"s{i}", BOARD_A, "briefing", "q", "body")
        assert len(_DELIVERED) == _DELIVERED_SESSIONS
        for k in [k for k in _DELIVERED]:
            _DELIVERED.pop(k, None)


# ===========================================================================
# R-MT1 clause 3 — the sentence, over the live dispatch
# ===========================================================================

class TestPreviousVersionSentence:
    TABLE = {
        f"why is {ORDER} late": parsed(f"why is {ORDER} late", Intent.LATE_ORDER,
                                     orders=(ORDER,)),
        "show me the evidence for that": _prove_it(),
        "can you show me that on my board": _drill(),
    }

    def test_premise_the_first_answer_really_carries_records(self, explainer):
        p = Panel(explainer, self.TABLE, "s-premise")
        assert p.ask(f"why is {ORDER} late").bundle.ordered_records, (
            "premise: turn 1 cites nothing, so nothing below is about a carry")

    def test_a_prove_it_after_a_rebind_names_the_previous_version(self, explainer):
        from mre.modules.ask_fallback_copy import (
            PROVE_IT_NO_TARGET, PROVE_IT_PRIOR_OTHER_VERSION,
        )
        p = Panel(explainer, self.TABLE, "s-rebind-prove")
        p.ask(f"why is {ORDER} late")
        p.rebind(BOARD_B, clear_client=False)
        text = p.ask("show me the evidence for that").text
        assert PROVE_IT_PRIOR_OTHER_VERSION[:50] in text
        assert PROVE_IT_NO_TARGET[:40] not in text, (
            "'the board changed' and 'I have never answered you' are different "
            "facts and the product states one of them for both")

    def test_it_opens_nothing_from_the_board_the_planner_left(self, explainer):
        p = Panel(explainer, self.TABLE, "s-rebind-records")
        first = p.ask(f"why is {ORDER} late")
        assert first.bundle.ordered_records
        p.rebind(BOARD_B, clear_client=False)
        second = p.ask("show me the evidence for that")
        assert not second.bundle.ordered_records, (
            "the old board's records opened against the new one — D-05 verbatim")

    def test_a_drill_down_after_a_rebind_says_the_same_thing(self, explainer):
        from mre.modules.ask_fallback_copy import PROVE_IT_PRIOR_OTHER_VERSION
        p = Panel(explainer, self.TABLE, "s-rebind-drill")
        p.ask(f"why is {ORDER} late")
        p.rebind(BOARD_B, clear_client=False)
        text = p.ask("can you show me that on my board").text
        assert PROVE_IT_PRIOR_OTHER_VERSION[:50] in text

    def test_back_on_the_original_board_the_answer_is_still_there(self, explainer):
        """The key SCOPES; it does not destroy. A planner who publishes and then
        returns to the parent board (the picker's own path) finds the
        conversation they left, and clause 3's sentence is not sticky."""
        p = Panel(explainer, self.TABLE, "s-return")
        first = p.ask(f"why is {ORDER} late")
        p.rebind(BOARD_B, clear_client=False)
        p.ask("show me the evidence for that")
        p.rebind(BOARD_A, clear_client=False)
        again = p.ask("show me the evidence for that")
        assert ([r.get("record_id") for r in again.bundle.ordered_records]
                == [r.get("record_id") for r in first.bundle.ordered_records])


# ===========================================================================
# D-01 — the drill-down wire, and the refusal half
# ===========================================================================

class TestDrillDownWired:
    """NEGATIVE CONTROL (b). The gesture the parse calls `drill-down` grounds on
    the same store `prove-it` grounds on: two phrasings of one gesture."""

    TABLE = {
        f"why is {ORDER} late": parsed(f"why is {ORDER} late", Intent.LATE_ORDER,
                                     orders=(ORDER,)),
        "can you show me that on my board": _drill(),
        "show me the evidence for that": _prove_it(),
    }

    def test_it_opens_the_previous_answers_records(self, explainer):
        p = Panel(explainer, self.TABLE, "s-drill")
        first = p.ask(f"why is {ORDER} late")
        second = p.ask("can you show me that on my board")
        assert second.bundle.ordered_records, (
            "the drill-down opened NOTHING one turn after an answer that cited "
            "records — D-01")
        assert ([r.get("record_id") for r in second.bundle.ordered_records]
                == [r.get("record_id") for r in first.bundle.ordered_records])

    def test_it_names_the_question_it_is_behind(self, explainer):
        p = Panel(explainer, self.TABLE, "s-drill-names")
        p.ask(f"why is {ORDER} late")
        assert f"why is {ORDER} late" in p.ask(
            "can you show me that on my board").text

    def test_the_two_phrasings_open_the_same_thing(self, explainer):
        """The whole point of grounding both on one store. Before this, one was
        wired and one opened the board's most severe gate finding."""
        a = Panel(explainer, self.TABLE, "s-two-a")
        a.ask(f"why is {ORDER} late")
        drill = a.ask("can you show me that on my board")
        b = Panel(explainer, self.TABLE, "s-two-b")
        b.ask(f"why is {ORDER} late")
        prove = b.ask("show me the evidence for that")
        assert ([r.get("record_id") for r in drill.bundle.ordered_records]
                == [r.get("record_id") for r in prove.bundle.ordered_records])

    def test_a_drill_down_is_never_remembered_as_an_answer(self, explainer):
        """Else the second "show me that" drills the drill-down — 4B.22's own
        rule, which `drill-down` now inherits because it now reads the store."""
        p = Panel(explainer, self.TABLE, "s-drill-twice")
        first = p.ask(f"why is {ORDER} late")
        p.ask("can you show me that on my board")
        third = p.ask("can you show me that on my board")
        assert ([r.get("record_id") for r in third.bundle.ordered_records]
                == [r.get("record_id") for r in first.bundle.ordered_records])

    def test_it_reaches_for_the_synthesis_claim_first(self, explainer):
        """FOUND IN THIS SESSION'S OWN LIVE RUN, after the wire landed. With
        only the ANSWER memory wired, a drill-down onto a SYNTHESIS answer fell
        through to its record set — empty, because an R-TG1 general-knowledge
        claim carries no records by design — and told the planner their
        teaching answer had cited nothing.

        `prove-it` reaches for the synthesis CLAIM first and the answer memory
        second. Two phrasings of one gesture have to reach for the same things
        in the same order, or the phrasing still decides the answer."""
        from mre.modules.explainer import ProveItCase
        p = Panel(explainer, {}, "s-drill-claim")
        p.synth.remember(p.session, p.schedule, _one_claim_answer())
        p.answers.remember(p.session, p.schedule, "late-orders", "an earlier "
                           "question", [])
        from mre.contracts.parse import Intent as _I
        p._parser = ScriptedParser({"can you show me that on my board":
                                    parsed("can you show me that on my board",
                                           _I.DRILL_DOWN)})
        res = p.ask("can you show me that on my board")
        assert res.bundle.key_facts.get("case") == ProveItCase.CLAIM
        assert "queued behind the cutting line" in res.text

    def test_a_drill_down_does_not_make_the_claims_stale(self, explainer):
        """`run_ask` forgets the synthesis memory on any route that is not
        about our last answer. `drill-down` is about our last answer, so a
        first "show me that" must not be why the second one cannot."""
        p = Panel(explainer, {}, "s-drill-claim-twice")
        p.synth.remember(p.session, p.schedule, _one_claim_answer())
        from mre.contracts.parse import Intent as _I
        p._parser = ScriptedParser({"can you show me that on my board":
                                    parsed("can you show me that on my board",
                                           _I.DRILL_DOWN)})
        p.ask("can you show me that on my board")
        assert p.synth.last(p.session, p.schedule) is not None
        assert "queued behind the cutting line" in p.ask(
            "can you show me that on my board").text

    def test_an_ordinal_still_opens_that_finding(self, explainer):
        """The branch that always worked, kept: "tell me more about finding 1"
        names an item of a list a previous answer gave, and the ordinal is the
        planner's own."""
        table = dict(self.TABLE)
        table["tell me more about finding 1"] = parsed(
            "tell me more about finding 1", Intent.DRILL_DOWN)
        p = Panel(explainer, table, "s-ordinal")
        text = p.ask("tell me more about finding 1").text
        assert "[WARNING]" in text or "warning" in text.lower()


class TestDrillDownRefusal:
    """THE IMPORTANT HALF (negative control (c)). It holds even where the wire
    has nothing to deliver, because a default that ASSERTS manufactures a claim
    out of a gap."""

    TABLE = {"can you show me that on my board": _drill()}

    def test_a_cold_drill_down_refuses_and_offers_the_door(self, explainer):
        from mre.modules.ask_fallback_copy import PROVE_IT_NO_TARGET
        p = Panel(explainer, self.TABLE, "s-cold-drill")
        text = p.ask("can you show me that on my board").text
        assert PROVE_IT_NO_TARGET[:40] in text
        assert "ask me something first" in text.lower(), "no door was offered"

    def test_it_does_not_open_the_worst_finding_on_the_board(self, explainer):
        """The measured specimen (d.0 P8 T2): one turn after a good teaching
        answer about frozen zones, "can you show me that on my board" returned
        the board's most severe DATA-QUALITY finding, which had nothing to do
        with anything the conversation had said."""
        p = Panel(explainer, self.TABLE, "s-cold-nofinding")
        res = p.ask("can you show me that on my board")
        assert not res.bundle.ordered_records
        assert "[WARNING]" not in res.text
        assert res.bundle.key_facts.get("detail") is None

    def test_the_board_still_has_a_finding_to_have_fallen_to(self, explainer):
        """PREMISE. Without a finding on this fixture the test above passes for
        the wrong reason — it would be asserting that an empty list is empty."""
        assert explainer._index.all_findings(), (
            "premise: this fixture has no data-quality finding, so the "
            "findings[0] fallback could not have fired here anyway")


# ===========================================================================
# D-06 — which KIND of nothing
# ===========================================================================

class TestEmptyRead:
    """NEGATIVE CONTROL (d): decide the branch from the record count again and
    both halves collapse onto one sentence."""

    def test_the_case_function_is_the_one_definition(self):
        from mre.modules.explainer import ProveItCase, prove_it_case
        assert prove_it_case({"text": "x"}, None, 0) == ProveItCase.CLAIM
        assert prove_it_case(None, {"route": "late-orders"}, 3) == \
            ProveItCase.RECORDS
        assert prove_it_case(None, {"route": "coaching"}, 0) == \
            ProveItCase.PRODUCT_META
        assert prove_it_case(None, {"route": "late-orders"}, 0) == \
            ProveItCase.EMPTY_READ
        assert prove_it_case(None, None, 0, True) == ProveItCase.OTHER_VERSION
        assert prove_it_case(None, None, 0, False) == ProveItCase.NONE

    def test_a_carried_answer_here_outranks_a_note_about_another_board(self):
        """Order matters: a session that has answered on BOTH boards must open
        THIS board's answer, not announce that another one exists."""
        from mre.modules.explainer import ProveItCase, prove_it_case
        assert prove_it_case(None, {"route": "late-orders"}, 2, True) == \
            ProveItCase.RECORDS


# ===========================================================================
# R-LD5 — the disclosure follows the subject
# ===========================================================================

def _model_recovered(question: str, intent: Intent, order: str,
                     op_seq=None) -> ParsedQuestion:
    """The P2b shape: the model marked the subject POINTED (the planner said
    "this"/"it") and supplied usable WORDS it read out of the RECENT TURNS
    block. Every rung of the ladder is empty, so `bind_subjects`' fallback
    resolves those words."""
    return parsed(question, intent).model_copy(update={"subjects": [
        SubjectRef(kind=SubjectKind.ORDER, raw=order, ref=order,
                   source=SubjectSource.CONVERSATION, pointed=True,
                   op_seq=op_seq)]})


class TestConversationSource:
    """NEGATIVE CONTROL (e)."""

    def test_the_binder_reports_the_new_source(self, explainer):
        """The seam itself — `bind_subjects` line by line, no dispatch. This is
        the collapse point: it used to overwrite the ladder's verdict with
        UTTERANCE, the one value that means "the planner said this"."""
        from mre.modules.question_parser import bind_subjects
        out = bind_subjects(explainer,
                            [{"kind": "order", "raw": ORDER,
                              "from_context": True}],
                            {"history": [], "selection": {},
                             "last_answered_subject": {}, "card": {}})
        assert out[0].ref == ORDER
        assert out[0].source is SubjectSource.CONVERSATION

    def test_a_typed_subject_is_still_utterance(self, explainer):
        """THE TRUE NEGATIVE. A planner is never told back what they just said,
        which is what keeps the disclosure short enough to be read."""
        from mre.modules.question_parser import bind_subjects
        out = bind_subjects(explainer,
                            [{"kind": "order", "raw": ORDER,
                              "from_context": False}], {})
        assert out[0].ref == ORDER
        assert out[0].source is SubjectSource.UTTERANCE

    def test_the_answer_discloses_it(self, explainer):
        from mre.modules.interpreter import _subject_note
        note = _subject_note(_model_recovered("why cant this be moved earlier",
                                              Intent.WHY_HERE, ORDER))
        assert ORDER in note
        assert "earlier" in note.lower(), (
            "the note does not say the subject came from the conversation")

    def test_a_typed_subject_discloses_nothing(self, explainer):
        """THE TRUE NEGATIVE at the note. P2's three arms were byte-identical
        because the ladder resolved; a typed subject must stay silent too."""
        from mre.modules.interpreter import _subject_note
        assert _subject_note(parsed(f"why is {ORDER} late", Intent.LATE_ORDER,
                                    orders=(ORDER,)).model_copy(
            update={"subjects": [SubjectRef(kind=SubjectKind.ORDER,
                                            raw=ORDER, ref=ORDER)]})) == ""

    def test_a_ladder_resolution_keeps_its_own_wording(self, explainer):
        """R-LD2's four rungs are untouched — R-LD5 is a fifth resolver, not a
        rewrite of the four. The cockpit keys a badge off the literal phrase
        "board selection", so that wording is a contract with the client."""
        from mre.modules.interpreter import _subject_note
        note = _subject_note(parsed("why cant this be moved", Intent.WHY_HERE)
                             .model_copy(update={"subjects": [
                                 SubjectRef(kind=SubjectKind.ORDER, raw="",
                                            ref=ORDER, pointed=True,
                                            source=SubjectSource.SELECTION)]}))
        assert "board selection" in note

    def test_the_grain_is_disclosed_too(self, explainer):
        """P2b's sharpest half: `op_seq 10` existed nowhere but inside the
        PREVIOUS question's text, and was reported as the planner's own."""
        from mre.modules.interpreter import _with_assumptions, route_params
        p = _model_recovered("why cant this be moved earlier",
                             Intent.WHY_HERE, ORDER, op_seq=30)
        params = route_params(p, p.question)
        assert params.get("op_seq_source") == "conversation"
        note = _with_assumptions("", p, params)
        assert "op30" in note and "earlier question" in note
        assert "you named op30" not in note, (
            "the disclosure credits the planner with a grain they never typed")

    def test_a_typed_grain_is_still_credited_to_the_planner(self, explainer):
        from mre.modules.interpreter import route_params
        p = parsed(f"why is {ORDER} op30 late", Intent.LATE_ORDER,
                   orders=(ORDER,), op_seq=30).model_copy(update={
                       "subjects": [SubjectRef(kind=SubjectKind.ORDER,
                                               raw=ORDER, ref=ORDER,
                                               op_seq=30)]})
        assert route_params(p, p.question).get("op_seq_source") == "utterance"


# ===========================================================================
# D-07 — a follow-up is not deafness
# ===========================================================================

class _B:
    def __init__(self) -> None:
        self.key_facts: dict = {}


class TestDeafGate:
    """NEGATIVE CONTROL (f). The gate must not become a suppression: the ONE
    true positive the record has ever produced still has to fire."""

    ANSWER = "4 data-quality problem(s): CUT-01 is in a workload too dense ..."

    def test_a_deepen_follow_up_is_not_told_we_do_not_understand(self):
        forget_deliveries("s-gate")
        remember_delivery("s-gate", BOARD_A, "why-here",
                          f"why is {ORDER} placed there", self.ANSWER)
        b = _B()
        # Same ROUTE as the delivery being matched — the planner drilled into
        # the answer they just got, and the gate reads both halves.
        bundle_repeat(b, {"history": []},
                      parsed("but why", Intent.WHY_HERE,
                             followup_of=FollowupKind.DEEPEN),
                      self.ANSWER, "s-gate", schedule_id=BOARD_A)
        assert not b.key_facts, (
            "the planner drilled into the answer they just got and was told "
            "the product was not understanding them — D-07")
        forget_deliveries("s-gate")

    def test_the_true_positive_fires_even_when_the_parse_calls_it_a_deepen(self):
        """THE TEST THE FIRST VERSION OF THIS GATE PASSED AND THE SWEEP FAILED.

        `sweep_carried_state_v1` block E2, live: the parse marks "what does the
        certificate say", asked after "are there any data quality problems", as
        `followup=deepen` — reasonably, since it does follow — and a gate
        reading `followup_of` alone therefore SWALLOWED the one true positive
        this rider has ever produced. The unit test below passed the whole
        time, because it constructed `followup_of=NONE`.

        The route the prior delivery came from is the discriminator, and
        `_DELIVERED` has always carried it: same route means the planner
        deepened, different route means two questions collapsed onto one
        answer."""
        forget_deliveries("s-tp-deepen")
        remember_delivery("s-tp-deepen", BOARD_A, "data-problems",
                          "are there any data quality problems", self.ANSWER)
        b = _B()
        bundle_repeat(b, {"history": []},
                      parsed("what does the certificate say",
                             Intent.CERTIFICATE_TESTIMONY,
                             followup_of=FollowupKind.DEEPEN),
                      self.ANSWER, "s-tp-deepen", schedule_id=BOARD_A)
        assert b.key_facts.get("deaf") == 1, (
            "the gate became a suppression: a DIFFERENT question reaching a "
            "DIFFERENT route got one body and the rider stayed silent")
        forget_deliveries("s-tp-deepen")

    def test_the_P6_T7_true_positive_STILL_FIRES(self):
        """THE GUARD THAT MATTERS. (d.0) P6 T7 is the first true positive `deaf`
        has produced in the record (docs/07 §5a.42 and §5a.58 record six
        firings with zero): "what does the certificate say" after "are there any
        data quality problems" got the IDENTICAL body, because
        `certificate-testimony` and `data-problems` render the same answer.

        Different question, NO followup_of, same fingerprint. If the gate ever
        swallows this it has stopped being a gate. (The shared-body route defect
        itself is NOT fixed here — it is a single-turn finding filed to the
        census micro-session.)"""
        forget_deliveries("s-tp")
        remember_delivery("s-tp", BOARD_A, "data-problems",
                          "are there any data quality problems", self.ANSWER)
        b = _B()
        bundle_repeat(b, {"history": []},
                      parsed("what does the certificate say",
                             Intent.CERTIFICATE_TESTIMONY),
                      self.ANSWER, "s-tp", schedule_id=BOARD_A)
        assert b.key_facts.get("deaf") == 1
        assert "data quality" in b.key_facts.get("deaf_prior", "")
        forget_deliveries("s-tp")

    def test_a_correction_is_still_deafness(self):
        """CORRECTION is deliberately NOT gated: a planner re-binding a referent
        and getting the same answer back is the strongest deafness signal there
        is, and it is one of the four firings 4B.15 Item 4 measured."""
        forget_deliveries("s-corr")
        remember_delivery("s-corr", BOARD_A, "coaching",
                          "can I make just this one job splittable", self.ANSWER)
        b = _B()
        bundle_repeat(b, {"history": []},
                      parsed(f"no, I mean for {ORDER} specifically",
                             Intent.ATTRIBUTE_LOOKUP,
                             followup_of=FollowupKind.CORRECTION),
                      self.ANSWER, "s-corr", schedule_id=BOARD_A)
        assert b.key_facts.get("deaf") == 1
        forget_deliveries("s-corr")

    def test_a_genuine_re_ask_is_still_a_repeat(self):
        """The `repeat` half is untouched — the gate is on `deaf` alone, and
        the two were split apart deliberately in 4B.15 Item 4."""
        b = _B()
        bundle_repeat(b, {"history": [{"question": "how many orders are late?",
                                       "route": "late-orders"}]},
                      parsed("how many orders are late", Intent.LATE_ORDERS),
                      "13 orders are late.", "s-reask", schedule_id=BOARD_A)
        assert b.key_facts.get("repeat") == 1


# ===========================================================================
# D-09 — an outage is not an intent
# ===========================================================================

class TestOutageInThePromptSurface:
    def test_the_outage_turn_does_not_render_as_an_intent(self):
        from mre.modules.question_parser import render_context
        block = render_context({"history": [
            {"question": f"why is {ORDER} late", "route": "OUTAGE"}]})
        assert "intent: OUTAGE" not in block, (
            "a token outside the closed intent vocabulary is rendered into "
            "both prompts as though it named a route")
        assert "could not reach its language model" in block
        assert f"why is {ORDER} late" in block, (
            "the turn was dropped — the planner can still see it on screen, so "
            "the four-turn window they read and the one we send disagree")

    def test_a_real_route_is_untouched(self):
        from mre.modules.question_parser import render_context
        block = render_context({"history": [
            {"question": f"why is {ORDER} late", "route": "late-order"}]})
        assert "answered with intent: late-order" in block


# ===========================================================================
# D-08 — the harness carries what the panel carries
# ===========================================================================

class TestHarnessParity:
    def test_an_errored_turn_is_not_appended_to_history(self):
        """`askpanel.js`'s `askHistory.push` sits inside the `try`, after
        `appendAnswer`, so a turn that threw is never recorded (4B.14 Item
        5(a)). `runner.py` appended unconditionally, so the harness could
        present a failed turn to the next turn's parse and the product could
        not — a harness that carries more than the panel carries measures a
        product nobody ships."""
        source = (REPO / "src" / "mre" / "ai_exam" / "runner.py").read_text(
            encoding="utf-8")
        i = source.index("# Extend history exactly as the cockpit does")
        window = source[i:i + 1800]
        guard = window.index("if error is None:")
        append = window.index("history.append({")
        assert guard < append, (
            "the history append is not under the success guard the panel puts "
            "it under")
