"""The exam runner's own tests (Session 4A.3b, CU1/CU5).

Fast: script parsing (SELECT/RESET/comment/parse-errors), the mechanical sidecar
checks, the renderer-tag parse. Slow: an end-to-end conversation against a real
glass_box solve proving conversation-state persistence, SELECT/RESET, the sidecar
firing on a real answer, and the target-health guard (a dead target fires loud and
runs nothing).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.ai_exam.script import (
    Comment, Question, Reset, Select, parse_script,
)
from mre.ai_exam.runner import ExamRunner, RunTarget, TurnRecord
from mre.ai_exam.report import render_sidecar, render_transcript
from mre.ai_exam.sidecar import Finding, Vocab, check_turn, offered_questions

DATASET = Path(__file__).resolve().parents[2] / "datasets" / "glass_box"


# ===========================================================================
# Fast — script parsing
# ===========================================================================

class TestScript:
    def test_questions_comments_blank(self):
        ps = parse_script("# a note\n\nwhy is ORD-05 late\n")
        assert [type(i) for i in ps.items] == [Comment, Question]
        assert ps.items[1].text == "why is ORD-05 late"
        assert not ps.parse_errors

    def test_select_order_and_machine(self):
        ps = parse_script("SELECT order=ORD-05 machine=CUT-01")
        sel = ps.items[0]
        assert isinstance(sel, Select)
        assert sel.order == "ORD-05" and sel.machine == "CUT-01" and not sel.clear

    def test_select_op_sets_both_slots(self):
        ps = parse_script("SELECT op=ORD-05@CUT-01")
        sel = ps.items[0]
        assert sel.order == "ORD-05" and sel.machine == "CUT-01"

    def test_select_carries_the_operation_grain(self):
        """The listening docket. The cockpit's selection has carried `op_seq`
        since 4B.14 and this script could not express it, so the ONE channel
        that supplies an operation grain the planner did not type was
        unreachable from any exam — which is why S2's specimen had to be
        measured by hand against the live API."""
        ps = parse_script("SELECT order=ORD-05 machine=CUT-01 seq=20")
        sel = ps.items[0]
        assert sel.op_seq == 20

    def test_a_selection_with_no_seq_carries_no_grain(self):
        ps = parse_script("SELECT order=ORD-05 machine=CUT-01")
        assert ps.items[0].op_seq is None

    def test_an_unreadable_seq_is_a_parse_error_not_a_silent_drop(self):
        """A bank that thinks it selected op20 and did not would grade the
        wrong bar, and its transcript would say nothing about it."""
        ps = parse_script("SELECT order=ORD-05 seq=twenty")
        assert ps.items[0].op_seq is None
        assert any("seq=" in e[2] for e in ps.parse_errors)

    def test_select_clear_and_reset(self):
        ps = parse_script("SELECT clear\nRESET")
        assert isinstance(ps.items[0], Select) and ps.items[0].clear
        assert isinstance(ps.items[1], Reset)

    def test_malformed_select_is_a_parse_error_not_a_crash(self):
        ps = parse_script("SELECT nonsense here")
        assert not any(isinstance(i, Select) for i in ps.items)
        assert ps.parse_errors and ps.parse_errors[0][2].startswith("SELECT with no")

    def test_ids_and_typos_preserved_verbatim(self):
        ps = parse_script("why os ord-000038 not running")
        assert ps.items[0].text == "why os ord-000038 not running"


# ===========================================================================
# Fast — sidecar mechanical checks (synthetic turns + a lightweight vocab)
# ===========================================================================

class _FakeStore:
    def load_snapshot(self, snapshot_id):  # noqa: ANN001
        raise FileNotFoundError(snapshot_id)


@pytest.fixture(scope="module")
def vocab():
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    ex = Explainer(_FakeStore(), EvidenceIndex(), snapshot_id="x")
    ex._order_refs = {f"ORD-{i:02d}": f"ORD-{i:02d}" for i in range(1, 16)}
    ex._machine_refs = {m: m for m in ("CUT-01", "PRESS-FAST")}
    ex._order_shape_patterns = ex._build_order_shapes()
    ex._order_fuzzy = ex._build_order_fuzzy()
    return Vocab(ex)


@pytest.fixture()
def vocab_with_parser(vocab):
    """The same world with a PARSE layer attached, so the real-doors door check is
    live. The parser's client is a fake returning the emissions a live model would
    for these two probes — everything downstream (prompt, JSON, contract) is real."""
    from tests.parse_doubles import FakeClient, emission
    from mre.modules.question_parser import QuestionParser
    responses = [emission("unmatched", confidence=0.1),          # the nonsense probe
                 emission("late-order", [{"kind": "order", "raw": "ORD-05"}])]
    parser = QuestionParser(_client=FakeClient(responses))
    return Vocab(vocab._ex, parser=parser)


def _turn(**kw) -> TurnRecord:
    base = dict(lineno=1, question="q", selection={}, resolved_question="q",
                route="late-order", answer="body\n[rendered by: template | register: testimony]",
                renderer="template", record_count=1, lit_bars=2)
    base.update(kw)
    return TurnRecord(**base)


class TestSidecar:
    def test_clean_turn_no_findings(self, vocab):
        assert check_turn(_turn(), vocab) == []

    def test_exception_finding(self, vocab):
        f = check_turn(_turn(error="TimeoutError: x"), vocab)
        assert len(f) == 1 and f[0].kind == "exception"

    def test_empty_body_finding(self, vocab):
        f = check_turn(_turn(answer="[rendered by: template | register: testimony]"), vocab)
        assert any(x.kind == "empty" for x in f)

    def test_validator_finding(self, vocab):
        a = ("body\n[LLM validation failed: bad ts; fell back to template]\n"
             "[rendered by: template (LLM validated) | register: testimony]")
        f = check_turn(_turn(answer=a, renderer="template (LLM validated)"), vocab)
        assert any(x.kind == "validator" for x in f)

    def test_absent_entity_finding(self, vocab):
        # ORD-99 is order-shaped but not in the pinned vocabulary (1..15).
        f = check_turn(_turn(resolved_question="why is ORD-99 late"), vocab)
        assert any(x.kind == "absent-entity" for x in f)
        # a real ref does not fire it
        assert not any(x.kind == "absent-entity"
                       for x in check_turn(_turn(resolved_question="why is ORD-05 late"), vocab))

    def test_dark_evidence_finding(self, vocab):
        f = check_turn(_turn(route="late-order", record_count=0, lit_bars=0), vocab)
        assert any(x.kind == "dark-evidence" for x in f)
        # a header-only route is exempt (composes prose, cites nothing by design)
        assert not any(x.kind == "dark-evidence"
                       for x in check_turn(_turn(route="briefing", record_count=0,
                                                 lit_bars=0), vocab))

    def test_dead_door_finding(self, vocab_with_parser):
        # Session 4A.5a: the door check runs the REAL parse layer over each offered
        # follow-up (the classifier it used to run is retired). Here the parse layer
        # is a fake client returning the emissions a live model would.
        a = ('body\nWant nonsense? Ask "flibbertigibbet the widget"\n'
             "[rendered by: template | register: testimony]")
        f = check_turn(_turn(answer=a), vocab_with_parser)
        assert any(x.kind == "dead-door" for x in f)
        # a real door does not fire it
        good = ('body\nAsk "why is ORD-05 late?"\n'
                "[rendered by: template | register: testimony]")
        assert not any(x.kind == "dead-door"
                       for x in check_turn(_turn(answer=good), vocab_with_parser))

    def test_the_door_check_is_skipped_not_passed_without_a_parser(self, vocab):
        """No parser -> the honest state is "unchecked", never "clean"."""
        assert vocab.door_check_available is False
        a = ('body\nAsk "flibbertigibbet the widget"\n'
             "[rendered by: template | register: testimony]")
        assert not any(x.kind == "dead-door" for x in check_turn(_turn(answer=a), vocab))

    def test_the_door_check_is_memoized_across_a_sweep(self, vocab_with_parser):
        a = ('body\nAsk "why is ORD-05 late?"\n'
             "[rendered by: template | register: testimony]")
        check_turn(_turn(answer=a), vocab_with_parser)
        before = vocab_with_parser._parser.stats.calls
        check_turn(_turn(answer=a), vocab_with_parser)
        assert vocab_with_parser._parser.stats.calls == before

    def test_offered_questions_extraction(self):
        a = 'x Ask "why is ORD-05 late?" y Ask "what should I fix first?"'
        assert offered_questions(a) == ["why is ORD-05 late?", "what should I fix first?"]


# ===========================================================================
# Slow — end to end against a real glass_box solve
# ===========================================================================

@pytest.fixture(scope="module")
def gb_run(tmp_path_factory):
    from mre.__main__ import main as mre_main
    out = tmp_path_factory.mktemp("exam_gb")
    rc = mre_main(["--submission", str(DATASET), "--out", str(out),
                   "--snapshot-id", "snap-exam", "--solver-workers", "1",
                   "--solver-seed", "0"])
    assert rc == 0
    return out


# The parse each end-to-end turn assumes (Session 4A.5a). The runner drives the
# REAL ask path, which is LLM-first with no keyword fallback — so an offline
# end-to-end test supplies the parse layer the same way it supplies the solve.
# Whether a live model produces these parses is the sweep's measurement.
def _exam_parser():
    from mre.contracts.parse import FollowupKind, Intent, SubjectKind
    from tests.parse_doubles import ScriptedParser, parsed
    return ScriptedParser({
        "how many orders are late": parsed("", Intent.LATE_ORDERS),
        "can you list the numbers": parsed("", Intent.LATE_ORDERS,
                                           followup_of=FollowupKind.LIST_EXPAND),
        "whats the end time of this order": parsed(
            "", Intent.ORDER_SCHEDULE,
            pointed_words=((SubjectKind.ORDER, "this order"),)),
        "why not just swap ORD-04 and ORD-05": parsed("", Intent.SWAP_MOVE,
                                                      orders=("ORD-04", "ORD-05")),
        "why is ORD-05 late": parsed("", Intent.LATE_ORDER, orders=("ORD-05",)),
        "but why?": parsed("", Intent.LATE_ORDER, pointed=(SubjectKind.ORDER,),
                           followup_of=FollowupKind.DEEPEN),
        "whats the end time of ORD-05": parsed("", Intent.ORDER_SCHEDULE,
                                               orders=("ORD-05",)),
        "why does ORD-13 start when it does": parsed("", Intent.START_REASON,
                                                     orders=("ORD-13",)),
        "whats running on CUT-01": parsed("", Intent.MACHINE_SCHEDULE,
                                          machines=("CUT-01",)),
        "what should i worry about today": parsed("", Intent.BRIEFING),
    })


@pytest.mark.slow
class TestEndToEnd:
    def _target(self, out) -> RunTarget:
        return RunTarget.from_out_dir(out, "snap-exam", label="gb")

    def _runner(self, out) -> ExamRunner:
        return ExamRunner(self._target(out), use_llm=False, parser=_exam_parser())

    def test_target_loads_healthy(self, gb_run):
        assert self._target(gb_run).build_vocab().healthy

    def test_a_conversation_persists_state(self, gb_run):
        script = parse_script(
            "how many orders are late\n"
            "can you list the numbers\n"          # list-expansion off the prior route
            "SELECT order=ORD-05 machine=CUT-01\n"
            "whats the end time of this order\n"  # deixis resolved from selection
            "RESET\n"
            "why not just swap ORD-04 and ORD-05\n")
        res = self._runner(gb_run).run(script)
        routes = [t.route for t in res.turns]
        # the deictic turn resolved against the SELECTED order (state carried)
        deictic = res.turns[2]
        assert deictic.question.startswith("whats the end time")
        assert "ORD-05" in deictic.resolved_question
        assert "from board selection" in deictic.resolution_note
        # after RESET the swap is self-contained and routes correctly
        assert res.turns[3].route == "swap-move"
        # every turn answered (no exceptions)
        assert all(t.error is None for t in res.turns)

    def test_swap_lights_bars(self, gb_run):
        # the swap/move bridge cites both orders' assignment decisions -> lit bars.
        res = self._runner(gb_run).run(
            parse_script("why not just swap ORD-04 and ORD-05"))
        assert res.turns[0].lit_bars > 0

    def test_cu1_but_why_resolves_via_last_answered_subject(self, gb_run):
        # Session 4A.3c CU1 — the founder-register chain. A TYPED "why is ORD-05
        # late" (no board selection) then "but why?" must DEEPEN the cause chain,
        # not CLARIFY. The runner carries the prior answer's resolved subject the
        # way the panel does; the first sweep's failing sequence is the regression.
        res = self._runner(gb_run).run(
            parse_script("why is ORD-05 late\nbut why?\n"))
        assert res.turns[0].route == "late-order"
        follow = res.turns[1]
        assert follow.route == "late-order", "but why? must not CLARIFY"
        assert "ORD-05" in follow.resolved_question
        assert follow.error is None

    def test_cu2_narrating_routes_light_their_bars(self, gb_run):
        # Session 4A.3c CU2 — order-schedule / start-reason / machine-schedule
        # narrate specific placements, so they light bars (no dark evidence). The
        # sidecar's dark-evidence check must not fire for these on real placements.
        res = self._runner(gb_run).run(parse_script(
            "whats the end time of ORD-05\n"       # order-schedule
            "why does ORD-13 start when it does\n"  # start-reason
            "whats running on CUT-01\n"))           # machine-schedule
        for t in res.turns:
            assert t.lit_bars > 0, f"{t.route!r} lit no bars: {t.question!r}"
            assert not any(f.kind == "dark-evidence" for f in t.findings), t.question

    def test_transcript_and_sidecar_render(self, gb_run):
        res = self._runner(gb_run).run(
            parse_script("why is ORD-05 late\nwhat should i worry about today"))
        tx = render_transcript(res)
        assert "AI EXAM TRANSCRIPT" in tx and "ORD-05" in tx
        assert "route=" in tx and "lit-bars=" in tx and "interpreted as" not in tx.split(
            "\n")[0]
        # the transcript header block is plain ASCII (no box-drawing / emoji);
        # embedded answers may carry the renderers' own '−'/'…', not our frame's.
        header = tx.split("-" * 72)[0]
        header.encode("ascii")   # raises if the frame smuggled a non-ASCII glyph
        sc = render_sidecar(res)
        assert '"llm_mode"' in sc

    def test_dead_target_fires_loud_and_runs_nothing(self, tmp_path):
        # An out-dir with no snapshot -> empty vocabulary -> target-unloadable, no
        # questions fired (the instrument refuses to emit garbage).
        (tmp_path / "runs").mkdir()
        target = RunTarget.from_out_dir(tmp_path, "snap-missing", label="dead")
        res = ExamRunner(target, use_llm=False).run(
            parse_script("why is ORD-05 late"))
        assert res.turns == []
        assert any(f.kind == "target-unloadable" for f in res.parse_errors)
