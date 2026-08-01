"""SESSION 4B.27 — THE CONVERSATIONAL BATCH.

Guards for the fixes measured this session. Every assertion that can run over
the LIVE DISPATCH (``interpreter.run_ask``) does — 4B.21's lesson (§5a.78) is
that a guard supplying its own arguments proves the assembler and not the path,
and three of this session's items are exactly allow-list / param-plumbing
defects that a hand-fed assembler test would have been green over.

======================================================================
WHAT EACH CLASS WATCHES
======================================================================

  A  (item 9)  A PROCESS CLAIM IS GATED ON THE PROCESS. "I read what I could"
               shipped at ZERO tool calls. The adjacent "I looked at: {tools}"
               line had always been gated on the same fact, so the code knew;
               the lead sentence never asked.

  B  (item 2)  THE CARD'S TWO TIME QUANTITIES ARE NAMED. The total line is
               CLAMPED plan tardiness (max(0,l_new)-max(0,l_old) summed over
               every demand); the per-order rows are a SIGNED finish shift.
               "no change to lateness" beside "ORD-000040 +1440min" was both
               true and unreadable.

  C  (item 6)  `frozen` ANSWERS ABOUT A NAMED ORDER. It declared no params and
               recited the whole board.

  D  (item 5)  THE BOARD'S "TIGHT" BAND IS EXPLAINABLE, and it is the BOARD's
               band (`board.js latenessBand`, threshold -1440) and NOT the
               opener's at-risk arithmetic. Those are different sets; answering
               one for the other is the defect class this session exists to
               catch, so the threshold is asserted against the cockpit source.

  E  (item 8)  THE SOLVE'S TIMING IS RECORDED AND READ, as TWO quantities.
               The old reader subtracted RunContext timestamps under field
               names that record does not carry — and the M6 RunContext closes
               in ~1.4ms because it is the REPORTING context, not the search.
               Fixing only the names would have produced a confident wrong
               number, so the guard asserts the SOURCE as well as the read.

  F  (item 10) R-BK1's PORTFOLIO IS REACHABLE FROM THE ASK PATH. K=1 (block
               ABSENT by construction) and K>1 are DIFFERENT answers and
               neither may be silent.

  G  (item 4)  A SUBJECT WE HEARD AND CANNOT WEIGH IS NAMED. 11 of the 13
               order-taking routes have no second slot (the census); the
               remedy is disclosure at the one seam every route passes.

======================================================================
THE PREMISE TESTS
======================================================================

Every assertion is conditional on the fixture actually producing its
condition. ``test_premise_*`` asserts each separately: a board that really has
a tight bar, a rolling document that really has all three regions, an evidence
index that really carries a timed solve_complete, and a portfolio document that
really has more than one member.

======================================================================
NEGATIVE CONTROLS (run this session, recorded in docs/closeouts/4B.27.md)
======================================================================

  (a) revert `SYNTHESIS_UNANSWERABLE_NO_TOOLS` to the ungated sentence
      -> class A red; B..G GREEN.
  (b) revert `answer_frozen` to ignore its order argument
      -> class C red; A, B, D..G GREEN.
  (c) drop `wall_time_s`/`det_consumed` from the rolling `solve_complete`
      payload -> class E red; the rest GREEN.
  (d) drop the silent-drop note from `_subject_note`
      -> class G red; the rest GREEN.

Each half is red only for its own defect, which is what makes them controls
rather than a smoke test.

======================================================================
ITS LIMIT, STATED
======================================================================

This file watches the ask path and the two Python surfaces that compose card
copy. It does NOT watch the cockpit's JavaScript — `sandboxui.js` is asserted
only by the source-level checks in class B/D, which is a weaker claim than the
Playwright harness makes and is stated as such. It does not assert that any
particular phrasing reaches any particular intent: that is measured live and
recorded in the close-out, never pinned, because pinning it would pin a model.
"""
from __future__ import annotations

import re
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
# the world
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def board(tmp_path_factory):
    """A REAL solved rolling board: some work committed, some active, some in
    the tray — class C needs all three regions to exist, not be mocked."""
    from generate_erp_dataset import generate
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    d = tmp_path_factory.mktemp("batch4b27")
    generate(d / "sub", scenario="pilot_scale", orders=18, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=10, frozen_days=3, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=60.0, det_total=2.0,
                              persist=True)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-4b27",
                                    run_id=str(uuid.uuid4()), identity_map=idmap)
    dd = doc.model_dump(mode="json")
    index = EvidenceIndex().build(plant.out_dir / "runs")
    ex = Explainer(plant.store, index, snapshot_id=plant.snapshot_id)
    return ex, dd


def _p(question: str, intent: Intent, *, orders=(), machine=None,
       followup=FollowupKind.NONE, confidence=0.95) -> ParsedQuestion:
    subjects = [SubjectRef(kind=SubjectKind.ORDER, raw=o, ref=o) for o in orders]
    if machine:
        subjects.append(SubjectRef(kind=SubjectKind.MACHINE, raw=machine,
                                   ref=machine))
    return ParsedQuestion(question=question, intent=intent, subjects=subjects,
                          followup_of=followup, confidence=confidence)


def _ask(board, question: str, parsed: ParsedQuestion, *, session: str):
    """One turn through the LIVE dispatch, rendered by the template."""
    from mre.modules.interpreter import AnswerMemory, SynthesisMemory, run_ask
    from mre.modules.renderers import TemplateRenderer
    ex, doc = board
    res = run_ask(ex, question, parser=ScriptedParser({question: parsed}),
                  context={"history": [], "selection": {},
                           "last_answered_subject": {}, "card": {}},
                  session_id=session, document=doc,
                  memory=SynthesisMemory(), answer_memory=AnswerMemory())
    return res, TemplateRenderer().render(res.bundle)


# ---------------------------------------------------------------------------
# CLASS A (item 9) — a process claim is gated on the process
# ---------------------------------------------------------------------------

def _synth_bundle(consulted):
    from mre.modules.explainer import ExplanationBundle
    return ExplanationBundle(
        question="what colour is the tray", subject_id="x",
        subject_type="synthesis", subject_external_name="x",
        ordered_records=[],
        key_facts={"unanswerable": True, "claims": [],
                   "consulted_tools": list(consulted), "offers": []},
        snapshot_id="snap", identity_map=None)


def test_a_zero_tool_calls_claims_no_read():
    """AT ZERO TOOL CALLS THE ANSWER DOES NOT SAY IT READ ANYTHING."""
    from mre.modules.renderers import TemplateRenderer
    text = TemplateRenderer().render(_synth_bundle([]))
    assert "I read what I could" not in text, (
        "the floor claimed a read that did not happen")
    assert "don't have a tool that reaches it" in text


def test_a_with_tool_calls_the_read_claim_survives():
    """The gate is on the FACT, not a blanket removal — a real read still says
    so, or the fix would have cost the honest sentence its meaning."""
    from mre.modules.renderers import TemplateRenderer
    text = TemplateRenderer().render(_synth_bundle(["placements_for_order"]))
    assert "I read what I could" in text
    assert "I looked at: placements_for_order." in text


def test_a_premise_the_two_branches_differ():
    """PREMISE: the two renderings are actually different text. A gate whose
    branches say the same thing guards nothing."""
    from mre.modules.renderers import TemplateRenderer
    r = TemplateRenderer()
    assert r.render(_synth_bundle([])) != r.render(_synth_bundle(["x"]))


# ---------------------------------------------------------------------------
# CLASS B (item 2) — the card's two time quantities are named
# ---------------------------------------------------------------------------

SANDBOXUI = REPO / "src" / "cockpit" / "src" / "drag" / "sandboxui.js"


def test_b_readback_names_plan_tardiness_not_bare_lateness():
    """The `open-card` read-back must not call the CLAMPED plan total
    'lateness' — that is the per-order rows' quantity."""
    from mre.modules.ask_fallback_copy import (
        OPEN_CARD_LATENESS_BETTER, OPEN_CARD_LATENESS_NONE,
        OPEN_CARD_LATENESS_WORSE,
    )
    for s in (OPEN_CARD_LATENESS_WORSE, OPEN_CARD_LATENESS_BETTER,
              OPEN_CARD_LATENESS_NONE):
        assert "plan tardiness" in s.lower(), f"unnamed quantity: {s!r}"
    # and it names the SET it is summed over
    assert "every order" in OPEN_CARD_LATENESS_NONE


def test_b_per_order_row_names_a_finish_shift():
    """The row is a SIGNED finish shift and says so — it is not the clamped
    plan tardiness above it, and the two used to share a word."""
    from mre.modules.renderers import _affected_effect
    later = _affected_effect({"tardiness_delta": 0.0, "lateness_delta_min": 1440})
    earlier = _affected_effect({"tardiness_delta": 0.0, "lateness_delta_min": -60})
    none = _affected_effect({"tardiness_delta": 0.0, "lateness_delta_min": 0})
    assert "finishes 1440 min later" in later
    assert "finishes 60 min earlier" in earlier
    assert none == "finish unchanged"
    assert "lateness" not in later and "lateness" not in none


def test_b_card_js_names_both_quantities():
    """The cockpit card itself. A weaker claim than the Playwright harness
    makes (this reads source, not a rendered DOM) and stated as such — but the
    two surfaces must not drift apart, and this is what catches that."""
    src = SANDBOXUI.read_text("utf-8")
    assert "plan tardiness" in src, "the card's total line names no quantity"
    assert "finish shift" in src, "the card's affected-order header names none"
    assert not re.search(r">no change to lateness<", src), (
        "the fused wording is still rendered")


def test_b_card_driver_is_labelled_as_recorded():
    """Item 3 — 4B.21's remedy applied to the eighth site, not a ninth
    mechanism. `why:` claimed to be THE REASON; it is the driver the decision
    record carries."""
    src = SANDBOXUI.read_text("utf-8")
    assert "recorded driver:" in src
    assert 'dc-driver">why:' not in src


# ---------------------------------------------------------------------------
# CLASS C (item 6) — `frozen` answers about a named order
# ---------------------------------------------------------------------------

def _regions(doc):
    from mre.modules.rolling_questions import RollingVocabulary
    v = RollingVocabulary(doc)
    out: dict[str, list[str]] = {}
    for wo, region in v._by_order.items():
        out.setdefault(region, []).append(wo)
    return out


def test_c_premise_the_board_has_more_than_one_region(board):
    """PREMISE: class C is vacuous on a board where everything is in one
    region — the three answers would be untestable."""
    _ex, doc = board
    regions = _regions(doc)
    assert len(regions) >= 2, f"only one region on this board: {list(regions)}"


def test_c_named_order_gets_a_boundary_comparison(board):
    """THE LIVE DISPATCH. `frozen` used to declare `params: []`, so this is a
    plumbing test as much as a copy test: the subject has to survive
    route_params -> dispatch -> _rolling_bundle -> answer_frozen."""
    _ex, doc = board
    regions = _regions(doc)
    for region, orders in regions.items():
        if not orders:
            continue
        order = sorted(orders)[0]
        res, text = _ask(board, "is that order frozen",
                         _p("is that order frozen", Intent.FROZEN,
                            orders=(order,)),
                         session=f"4b27-frozen-{region}")
        assert res.route == "frozen"
        assert order in text, (
            f"the {region} order {order} is not named in its own answer: {text}")
        # and it is NOT the whole-board recitation
        assert "operations are frozen and committed" not in text or order in text


def test_c_no_order_still_gets_the_census(board):
    """The plant-wide question is a legitimate scope and must not have become a
    near-miss when the route gained a param."""
    res, text = _ask(board, "what's frozen",
                     _p("what's frozen", Intent.FROZEN),
                     session="4b27-frozen-all")
    assert res.route == "frozen"
    assert "frozen" in text.lower()


def test_c_unknown_order_falls_back_rather_than_asserting(board):
    """An order the document does not carry must not produce a confident
    sentence about it — the fallback is the census, never an invention."""
    _ex, doc = board
    from mre.modules.rolling_questions import answer_frozen
    text = answer_frozen(doc, "ORD-DOES-NOT-EXIST")
    assert "ORD-DOES-NOT-EXIST" not in text


# ---------------------------------------------------------------------------
# CLASS D (item 5) — the BOARD's tight band, and it is the board's
# ---------------------------------------------------------------------------

BOARD_JS = REPO / "src" / "cockpit" / "src" / "board.js"


def test_d_threshold_matches_the_cockpit_source():
    """THE ANSWER AND THE COLOUR ARE ONE NUMBER.

    Census D found that the board's `tight` is a lateness band and NOT the
    opener's at-risk arithmetic (slack vs longest step) — different sets. This
    asserts the explainer's constant against the value `board.js` actually
    draws with, so the two cannot drift into answering about different sets.
    """
    from mre.modules.explainer import TIGHT_BAND_MINUTES
    src = BOARD_JS.read_text("utf-8")
    m = re.search(r"BANDS\s*=\s*\{\s*tightMin:\s*(-?\d+)", src)
    assert m, "board.js no longer declares BANDS.tightMin in the expected shape"
    assert int(m.group(1)) == TIGHT_BAND_MINUTES


def test_d_band_facts_partition_the_line():
    """Three bands, no gaps, no overlap — and an unknown lateness yields NO
    band rather than a default one (a colour asserted from a missing number)."""
    from mre.modules.explainer import _lateness_band_facts as f
    assert f(1)["board_band"] == "late"
    assert f(0)["board_band"] == "tight"
    assert f(-1439)["board_band"] == "tight"
    assert f(-1440)["board_band"] == "ontime"
    assert f(None) == {}


def test_d_tight_answer_names_the_band_and_the_slack():
    """The rendered answer uses the planner's own word and states the room."""
    from mre.modules.explainer import ExplanationBundle
    from mre.modules.renderers import TemplateRenderer
    b = ExplanationBundle(
        question="why is ORD-1 tight", subject_id="d1", subject_type="demand",
        subject_external_name="ORD-1", ordered_records=[],
        key_facts={"lateness_minutes": -299, "lateness_hours": -5.0,
                   "due_date": "2026-01-28", "board_band": "tight",
                   "board_band_threshold_min": -1440,
                   "slack_minutes": 299, "slack_hours": 5.0},
        snapshot_id="s", identity_map=None)
    text = TemplateRenderer().render(b)
    assert "TIGHT" in text
    assert "5.0h" in text
    assert "is not late" in text


def test_d_comfortably_early_is_not_called_tight():
    """The negative half: a bar well clear of its due date keeps the plain
    on-time sentence, or the band would be decoration."""
    from mre.modules.explainer import ExplanationBundle
    from mre.modules.renderers import TemplateRenderer
    b = ExplanationBundle(
        question="is ORD-2 ok", subject_id="d2", subject_type="demand",
        subject_external_name="ORD-2", ordered_records=[],
        key_facts={"lateness_minutes": -5000, "lateness_hours": -83.3,
                   "due_date": "2026-01-28", "board_band": "ontime",
                   "board_band_threshold_min": -1440},
        snapshot_id="s", identity_map=None)
    text = TemplateRenderer().render(b)
    assert "TIGHT" not in text
    assert "is on time" in text


# ---------------------------------------------------------------------------
# CLASS E (item 8) — the solve's timing is recorded, and read as two things
# ---------------------------------------------------------------------------

def test_e_premise_the_rolling_solve_records_its_timing(board):
    """PREMISE, and the half the naive repair would have missed: the ROLLING
    `solve_complete` must actually carry the figures. The monolithic path has
    carried `wall_time_s` since solve_runner was written; this one never did,
    and the M6 RunContext beside it closes in about a millisecond."""
    ex, _doc = board
    payloads = [r.get("payload") or {} for r in ex._index.events()
                if r.get("status_text") == "solve_complete"]
    assert payloads, "no solve_complete event on this board"
    assert any(p.get("wall_time_s") is not None for p in payloads)
    assert any(p.get("det_consumed") is not None for p in payloads)


def test_e_timing_reader_returns_both_quantities(board):
    from mre.modules.cost_proof import timing_from_evidence
    ex, _doc = board
    t = timing_from_evidence(ex._index)
    assert t.readable and t.recorded
    assert t.wall_s is not None and t.det_consumed is not None
    assert t.seconds_per_unit is not None


def test_e_unreadable_and_untimed_are_different_answers():
    """4B.18's discipline: a fact about OUR STORAGE is never rendered as a fact
    about the solve, and 'no record' is not 'a record with no timing'."""
    from mre.modules.cost_proof import SolveTiming

    class _Empty:
        def runs(self): return []
        def events(self): return []

    class _Untimed:
        def runs(self): return [{"module": "M6", "run_id": "r"}]
        def events(self):
            return [{"status_text": "solve_complete", "run_id": "r",
                     "payload": {"status": "FEASIBLE"}}]

    from mre.modules.cost_proof import timing_from_evidence
    a = timing_from_evidence(_Empty())
    b = timing_from_evidence(_Untimed())
    assert (a.readable, a.recorded) == (False, False)
    assert (b.readable, b.recorded) == (True, False)
    assert SolveTiming().seconds_per_unit is None


def test_e_answer_states_work_and_wall_separately(board):
    """THE LIVE DISPATCH. The two quantities are named and not fused."""
    res, text = _ask(board, "how long did the solver spend",
                     _p("how long did the solver spend", Intent.SOLVE_TIME),
                     session="4b27-time")
    assert res.route == "solve-time"
    assert "deterministic units" in text
    assert "seconds on this machine" in text
    assert "I don't have the solve's timing recorded" not in text


def test_e_answer_says_which_figure_is_hardware(board):
    """The distinction is the answer, not a footnote: a planner must be able to
    tell which number travels to other hardware."""
    res, text = _ask(board, "how long did the solver spend",
                     _p("how long did the solver spend", Intent.SOLVE_TIME),
                     session="4b27-time2")
    assert "reproduce anywhere" in text or "this machine's speed" in text


# ---------------------------------------------------------------------------
# CLASS F (item 10) — the portfolio is reachable from the ask path
# ---------------------------------------------------------------------------

def test_f_k1_answers_the_single_draw_fact(board):
    """K=1: the block is ABSENT BY CONSTRUCTION (R-BK1 clause 2), and absence
    gets its own sentence. Never 'a portfolio of one', never silence.

    WHICH sentence depends on the proof: a proved board gets the one that says
    a closed bound outranks the seed (see the guard below). Both branches must
    state that there was ONE search — that is the fact absence carries — so
    this asserts the fact and lets the register follow the board."""
    res, text = _ask(board, "is this the best schedule you found",
                     _p("is this the best schedule you found",
                        Intent.SOLVE_OPTIMALITY),
                     session="4b27-opt1")
    assert res.route == "solve-optimality"
    assert "one seeded search" in text.lower()
    assert "seed" in text
    # never described as a portfolio
    assert "best of" not in text


def _portfolio_doc(doc, members, *, spread_abs=None, spread_pct=None):
    d = dict(doc)
    solver = dict(d.get("solver") or {})
    solver["portfolio"] = {
        "k": len(members), "k_provenance": "declared", "det_time_s": 10.0,
        "det_time_s_provenance": "declared", "seed0": 42, "workers": 3,
        "execution": "processes", "declaration": "", "agreement": "",
        "unpublished": "", "winner_seed": members[0]["seed"],
        "winner_ledger_total": members[0]["ledger_total"],
        "spread_abs": spread_abs, "spread_pct": spread_pct,
        "members": members, "wall_time_s": 311.1,
    }
    d["solver"] = solver
    return d


def test_f_portfolio_members_and_spread_are_stated(board):
    """K>1: every member's ledger, and the clause-(4) sentence that stops the
    winner reading as the answer."""
    ex, doc = board
    members = [{"seed": 44, "ledger_total": 1667467.80, "status": "FEASIBLE",
                "selectable": True, "reason": ""},
               {"seed": 43, "ledger_total": 1801222.70, "status": "FEASIBLE",
                "selectable": True, "reason": ""},
               {"seed": 42, "ledger_total": 2135369.63, "status": "FEASIBLE",
                "selectable": True, "reason": ""}]
    res, text = _ask((ex, _portfolio_doc(doc, members, spread_abs=467901.83,
                                         spread_pct=28.0606)),
                     "is this the best schedule you found",
                     _p("is this the best schedule you found",
                        Intent.SOLVE_OPTIMALITY),
                     session="4b27-opt3")
    assert "best of 3 seeded searches" in text
    assert "seed 44" in text and "seed 42" in text
    assert "28.06%" in text
    assert "far from settled" in text
    assert "ONE seeded search" not in text


def test_f_unpublishable_member_is_named_never_dropped(board):
    """R-BK1 clause (4). 4B.25 measured two of five seeds returning an EMPTY
    BOARD at the shipped budget; dropping them makes the spread look tighter
    than the evidence supports."""
    ex, doc = board
    members = [{"seed": 42, "ledger_total": 2127482.58, "status": "FEASIBLE",
                "selectable": True, "reason": ""},
               {"seed": 43, "ledger_total": None, "status": "UNKNOWN",
                "selectable": False, "reason": "no ledger"}]
    _res, text = _ask((ex, _portfolio_doc(doc, members)),
                      "is this the best schedule you found",
                      _p("is this the best schedule you found",
                         Intent.SOLVE_OPTIMALITY),
                      session="4b27-opt4")
    assert "seed 43" in text
    assert "published no board" in text
    # one publishable member => NO spread, and never 0.00
    assert "0.00%" not in text
    assert "no spread to quote" in text


def test_f_single_number_is_not_called_agreement(board):
    """The tri-state again (4B.21): fewer than two publishable members means
    the answer must decline to call it agreement."""
    ex, doc = board
    members = [{"seed": 42, "ledger_total": 100.0, "status": "FEASIBLE",
                "selectable": True, "reason": ""},
               {"seed": 43, "ledger_total": None, "status": "UNKNOWN",
                "selectable": False, "reason": ""}]
    _res, text = _ask((ex, _portfolio_doc(doc, members)),
                      "is this the best schedule you found",
                      _p("is this the best schedule you found",
                         Intent.SOLVE_OPTIMALITY),
                      session="4b27-opt5")
    assert "won't call that agreement" in text


# ---------------------------------------------------------------------------
# CLASS G (item 4) — a subject we heard and cannot weigh is named
# ---------------------------------------------------------------------------

def test_g_second_order_is_disclosed_on_a_one_subject_route(board):
    """THE LIVE DISPATCH. 11 of 13 order-taking routes have no second slot; the
    planner must never be left believing we weighed a relation we never
    looked at."""
    _ex, doc = board
    orders = sorted({wo for wos in _regions(doc).values() for wo in wos})[:2]
    if len(orders) < 2:
        pytest.skip("this board carries fewer than two orders")
    res, _text = _ask(board, "why can't A start right after B",
                      _p("why can't A start right after B", Intent.WHY_HERE,
                         orders=tuple(orders)),
                      session="4b27-two")
    assert orders[1] in (res.resolution_note or ""), (
        f"the second subject was dropped silently: {res.resolution_note!r}")
    assert "one order at a time" in (res.resolution_note or "")


def test_g_single_subject_gets_no_note(board):
    """The negative half: the disclosure must not fire when there is nothing to
    disclose, or every answer grows a caveat that means nothing."""
    _ex, doc = board
    orders = sorted({wo for wos in _regions(doc).values() for wo in wos})
    res, _text = _ask(board, "why is A here",
                      _p("why is A here", Intent.WHY_HERE,
                         orders=(orders[0],)),
                      session="4b27-one")
    assert "one order at a time" not in (res.resolution_note or "")


def test_g_two_order_route_is_exempt(board):
    """`gap-between` USES both subjects, so disclosing a drop there would be a
    false statement about our own behaviour."""
    _ex, doc = board
    orders = sorted({wo for wos in _regions(doc).values() for wo in wos})[:2]
    if len(orders) < 2:
        pytest.skip("this board carries fewer than two orders")
    res, _text = _ask(board, "why the gap between A and B",
                      _p("why the gap between A and B", Intent.GAP_BETWEEN,
                         orders=tuple(orders)),
                      session="4b27-gap")
    assert "one order at a time" not in (res.resolution_note or "")


def test_g_route_params_carries_every_resolved_subject():
    """The channel itself. `params["order"]` keeps its exact meaning; `orders`
    is the new one, so no existing assembler changes behaviour."""
    from mre.modules.interpreter import route_params
    parsed = _p("q", Intent.WHY_HERE, orders=("ORD-1", "ORD-2"),
                machine="CUT-01")
    params = route_params(parsed, "q")
    assert params["order"] == "ORD-1"
    assert params["orders"] == ["ORD-1", "ORD-2"]
    assert params["machines"] == ["CUT-01"]


def test_g_tray_preemption_discloses_the_other_order(board):
    """THE PRE-EMPTION IS ALSO A DROP.

    Dispatch branch 0 rewrites the intent when a named order is in the tray, so
    a two-order question arrives at a one-order route. `gap-between` is exempt
    from the general disclosure because it USES both subjects — but by the time
    the tray branch has run, that is no longer the route answering. Measured
    live this session: "why can't ord-11 start right after ord-19" parsed to
    `gap-between` with both orders and was answered about ORD-000011 alone.
    """
    from mre.modules.rolling_questions import RollingVocabulary
    _ex, doc = board
    v = RollingVocabulary(doc)
    tray = sorted([o for o, r in v._by_order.items() if r == "beyond-horizon"])
    placed = sorted([o for o, r in v._by_order.items() if r != "beyond-horizon"])
    if not tray or not placed:
        pytest.skip("this board has no tray/placed pair to contrast")
    res, _text = _ask(board, "why can't A start right after B",
                      _p("why can't A start right after B", Intent.GAP_BETWEEN,
                         orders=(tray[0], placed[0])),
                      session="4b27-traydrop")
    assert res.route == "why-not-scheduled-yet"
    assert placed[0] in (res.resolution_note or ""), (
        f"the pre-emption dropped the second subject silently: "
        f"{res.resolution_note!r}")


def test_g_tray_preemption_single_subject_gets_no_note(board):
    """The negative half, again: one order in the tray and nothing else named
    must not grow a caveat."""
    from mre.modules.rolling_questions import RollingVocabulary
    _ex, doc = board
    v = RollingVocabulary(doc)
    tray = sorted([o for o, r in v._by_order.items() if r == "beyond-horizon"])
    if not tray:
        pytest.skip("this board has an empty tray")
    res, _text = _ask(board, "when will A be scheduled",
                      _p("when will A be scheduled",
                         Intent.WHY_NOT_SCHEDULED_YET, orders=(tray[0],)),
                      session="4b27-tray1")
    assert "was named too" not in (res.resolution_note or "")


def test_f_a_proved_board_does_not_get_the_seed_caveat():
    """A CLOSED BOUND OUTRANKS THE SEED.

    Caught on the pinned world during this session's own verification: the
    first version of the K=1 sentence told a planner that another seed "can
    land somewhere quite different" about a board whose cost is PROVED OPTIMAL.
    Nothing can be cheaper than proved. This session's own defect class, found
    in its own new copy — hence a guard rather than a note.
    """
    from mre.modules.renderers import _portfolio_clause
    proved = "\n".join(_portfolio_clause(
        {"portfolio_present": False, "proved": True}))
    unproved = "\n".join(_portfolio_clause(
        {"portfolio_present": False, "proved": False}))
    assert "no other seed could have found anything cheaper" in proved
    assert "land somewhere quite different" not in proved
    assert "land somewhere quite different" in unproved
    # and the proved branch still says something true about SHAPE
    assert "same cost" in proved
