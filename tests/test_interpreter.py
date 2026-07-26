"""Dispatch: the parse contract becomes an answer (R-AI5(2), Session 4A.5a CU2).

This file used to hold the paraphrase table that proved the deterministic
keyword/precedence router mapped working phrasings onto routes without an LLM, plus
the ellipsis/correction/menu rewrite rules. R-AI5 retires that layer whole: intent
arrives on the parse contract, and the behaviours those rules encoded are now FIELDS
of the contract that this dispatch honours. So the tests are re-pointed — each one
is now "a parse contract (+ live context) in, a route and its params out".

What a live model actually parses a given phrasing to is NOT asserted here; it is
the exam sweep's job against the pinned world (R-AI4(2)). What is asserted here is
that every field of the contract reaches the right destination, and that every
honest destination stays honest: never a guess, never a global answer to a question
about something absent, never a keyword fallback.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.contracts.parse import (
    ClarifyReason,
    FollowupKind,
    Intent,
    Polarity,
    SubjectKind,
)
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer, ROUTE_TAXONOMY
from mre.modules.interpreter import dispatch, route_params, run_ask
from tests.parse_doubles import ScriptedParser, parsed, resolve

# ---------------------------------------------------------------------------
# A compact fake snapshot + evidence fixture (self-contained; mirrors the
# test_explainer fake). Registers WO-2001 / M-GEAR-01 / M-GEAR-02 so subject
# resolution has real external refs to match against.
# ---------------------------------------------------------------------------

DEMAND_ID = "85342968-6107-58db-95d3-256cd6765fec"
GEAR_MACHINE_ID = "cdef1234-0000-0000-0000-000000000001"  # M-GEAR-02
ALT_MACHINE_ID = "abcd5678-0000-0000-0000-000000000002"   # M-GEAR-01


def _make_index(tmp_path: Path) -> EvidenceIndex:
    records = [
        {"record_type": "run_context_open", "run_id": "run-m7", "module": "M7",
         "snapshot_id": "snap-demo", "purpose": "t", "timestamp": "2026-07-06T00:00:00Z"},
        {"record_type": "metric", "record_id": "met-late-001", "run_id": "run-m7",
         "module": "M7", "seq": 8, "snapshot_id": "snap-demo",
         "subjects": [{"entity_id": DEMAND_ID, "entity_type": "demand"}],
         "tier": "supporting", "message": "", "name": "lateness_minutes",
         "value": 840.0, "unit": "minutes", "rollup_of": []},
        # A planner_edit Decision so the edit-cost / edit-summary domains resolve.
        {"record_type": "decision", "record_id": "dec-edit-001", "run_id": "run-m7",
         "module": "M7", "seq": 9, "snapshot_id": "snap-demo", "subjects": [],
         "tier": "headline", "message": "pinned an op", "decision_type": "planner_edit",
         "basis": "observed", "authority": "dev-planner", "driver": "SETUP_AMORTIZATION",
         "alternatives": [], "timestamp": "2026-07-06T00:02:30Z",
         "chosen": {"pin": {"operation_ref": "op-1", "resource_id": ALT_MACHINE_ID,
                            "start": "2026-07-06T01:00:00Z"},
                    "cost_delta": {"total_delta": 5.0, "production_delta": 2.0,
                                   "setup_delta": 1.0, "tardiness_delta": 2.0},
                    "delta_abs": 5.0, "moved_count": 1, "moves": []}},
        {"record_type": "run_context_close", "run_id": "run-m7",
         "status": "success", "ended_at": "2026-07-06T00:03:00Z"},
    ]
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "demo.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return EvidenceIndex().build(runs_dir)


class FakeSnapshotReader:
    def get_entity(self, entity_id):
        if entity_id == DEMAND_ID:
            return {"id": DEMAND_ID, "due": "2026-07-13T23:59:00+00:00"}
        return None

    def iter_entities(self, entity_type):
        if entity_type == "demand":
            yield {"id": DEMAND_ID, "due": "2026-07-13T23:59:00+00:00",
                   "external_refs": [{"system": "ERP", "type": "work_order",
                                      "value": "WO-2001"}]}

    def read_identity_map(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register(DEMAND_ID, "ERP", "work_order", "WO-2001")
        m.register(GEAR_MACHINE_ID, "ERP", "machine_id", "M-GEAR-02")
        m.register(ALT_MACHINE_ID, "ERP", "machine_id", "M-GEAR-01")
        return m


class FakeStore:
    def __init__(self, snap_id):
        self._snap_id = snap_id

    def load_snapshot(self, snap_id):
        return FakeSnapshotReader()


@pytest.fixture()
def explainer(tmp_path):
    index = _make_index(tmp_path)
    return Explainer(snapshot_store=FakeStore("snap-demo"), index=index,
                     snapshot_id="snap-demo")


def _dispatch(explainer, p, context=None, ledger=None):
    return dispatch(explainer, resolve(p, explainer, context), ledger=ledger)


# ===========================================================================
# A matched intent reaches its EXISTING assembler, unchanged in authority
# ===========================================================================

# (intent, subject words, the assembler's subject_type) — one per route family the
# founder exams exercise. The route table itself is untouched by R-AI5; what these
# pin is that the contract's fields carry into it correctly.
MATCHED = [
    (Intent.LATE_ORDER, {"orders": ("WO-2001",)}, "demand"),
    (Intent.LATE_ORDERS, {}, "late_orders"),
    (Intent.WHY_ON_MACHINE, {"orders": ("WO-2001",), "machines": ("M-GEAR-01",)},
     "demand"),
    (Intent.MACHINE_SCHEDULE, {"machines": ("M-GEAR-01",)}, "schedule"),
    (Intent.ORDER_SCHEDULE, {"orders": ("WO-2001",)}, "schedule"),
    (Intent.CUSTOMER_SCHEDULE, {"customers": ("acme",)}, "schedule"),
    (Intent.DATA_PROBLEMS, {}, "findings"),
    (Intent.TRIAGE, {}, "triage"),
    (Intent.REMEDIATION, {}, "remediation"),
    (Intent.EDIT_SUMMARY, {}, "edits"),
    (Intent.EDIT_COST, {}, "edit_cost"),
    (Intent.ADVICE, {}, "advice"),
    (Intent.COACHING, {"concepts": ("splitting",)}, "coaching"),
    (Intent.INVENTORY, {}, "inventory"),
    (Intent.BRIEFING, {}, "briefing"),
    (Intent.SOLVE_TIME, {}, "solve_time"),
    (Intent.MACHINE_COUNT, {}, "machine_count"),
    (Intent.MAINTENANCE, {}, "maintenance"),
]


@pytest.mark.parametrize("intent,subjects,subject_type", MATCHED)
def test_a_matched_intent_reaches_its_assembler(explainer, intent, subjects,
                                                subject_type):
    d = _dispatch(explainer, parsed("q", intent, **subjects))
    assert d.route == intent.value
    assert d.bundle.subject_type == subject_type


def test_route_params_carry_typed_subjects(explainer):
    p = resolve(parsed("q", Intent.WHY_ON_MACHINE, orders=("WO-2001",),
                       machines=("M-GEAR-01",)), explainer)
    params = route_params(p, "q")
    assert params["order"] == "WO-2001" and params["machine"] == "M-GEAR-01"


def test_two_order_intents_get_both_orders_in_the_planners_order(explainer):
    p = resolve(parsed("q", Intent.SWAP_MOVE, orders=("M-GEAR-01", "WO-2001")),
                explainer)
    # only WO-2001 is an order here; the machine-shaped word does not resolve as one
    params = route_params(p, "q")
    assert "order_a" in params and "order_b" in params


def test_polarity_reaches_the_start_reason_assembler(explainer):
    p = resolve(parsed("why cant it start sooner", Intent.START_REASON,
                       orders=("WO-2001",), polarity=Polarity.NEGATIVE), explainer)
    assert route_params(p, p.question)["polarity"] == "negative"


# ===========================================================================
# Honest destinations — never a guess
# ===========================================================================

class TestHonestDestinations:
    def test_a_clarify_payload_asks_and_carries_authored_copy(self, explainer):
        d = _dispatch(explainer, parsed("but why?", Intent.LATE_ORDER,
                                        clarify=ClarifyReason.NO_SUBJECT))
        assert d.route == "CLARIFY"
        assert d.bundle.subject_type == "clarify"
        assert "order, machine, or customer" in d.bundle.key_facts["reason"]

    @pytest.mark.parametrize("reason", list(ClarifyReason))
    def test_every_clarify_reason_has_authored_words(self, explainer, reason):
        d = _dispatch(explainer, parsed("q", Intent.LATE_ORDERS, clarify=reason,
                                        clarify_detail="those"))
        assert d.route == "CLARIFY"
        assert d.bundle.key_facts["reason"].strip()

    def test_unmatched_with_nearest_offers_the_nearest_capabilities(self, explainer):
        d = _dispatch(explainer, parsed(
            "is there a better schedule", Intent.UNMATCHED, confidence=0.2,
            nearest=(Intent.LATE_ORDERS, Intent.ADVICE)))
        assert d.route == "NEAR_MISS"
        offers = d.bundle.key_facts["offers"]
        assert 1 <= len(offers) <= 2

    def test_unmatched_with_nothing_near_refuses_honestly(self, explainer):
        d = _dispatch(explainer, parsed("flibbertigibbet", Intent.UNMATCHED,
                                        confidence=0.1))
        assert d.route == "REFUSED"
        assert d.bundle.subject_type == "unsupported"

    def test_a_low_confidence_match_is_not_answered_as_that_intent(self, explainer):
        d = _dispatch(explainer, parsed("tell me about stuff", Intent.LATE_ORDERS,
                                        confidence=0.2, nearest=(Intent.LATE_ORDERS,)))
        assert d.route == "NEAR_MISS"

    def test_a_named_but_absent_order_is_answered_as_absent(self, explainer):
        d = _dispatch(explainer, parsed("why is WO-9999 late", Intent.LATE_ORDER,
                                        orders=("WO-9999",)))
        assert d.route == "unknown-entity"
        assert d.bundle.subject_type == "unknown_entity"

    def test_a_pointed_subject_with_nothing_live_clarifies(self, explainer):
        """The planner pointed and there was nothing to point at — ask."""
        d = _dispatch(explainer, parsed("why is it late", Intent.LATE_ORDER,
                                        pointed=(SubjectKind.ORDER,)), context={})
        assert d.route == "CLARIFY"

    def test_a_required_slot_nobody_mentioned_bridges(self, explainer):
        """Nothing was pointed at and nothing was named — offer the nearest doors,
        never a global answer to a question about one thing."""
        d = _dispatch(explainer, parsed("why is it late", Intent.LATE_ORDER,
                                        nearest=(Intent.LATE_ORDERS,)), context={})
        assert d.route == "NEAR_MISS"

    def test_the_taxonomy_is_closed_at_dispatch(self, explainer):
        for intent in Intent:
            if intent is Intent.UNMATCHED:
                continue
            assert intent.value in ROUTE_TAXONOMY


# ===========================================================================
# Follow-up linkage — the retired rewrite rules, now contract fields
# ===========================================================================

class TestFollowupLinkage:
    def test_a_pointed_subject_binds_from_the_board_selection_and_says_so(
            self, explainer):
        d = _dispatch(explainer, parsed("whats the end time of this order",
                                        Intent.ORDER_SCHEDULE,
                                        pointed=(SubjectKind.ORDER,)),
                      context={"selection": {"order": "WO-2001"}})
        assert d.route == "order-schedule"
        assert "board selection" in d.note        # the cockpit keys its badge on this
        assert "WO-2001" in d.routed_question

    def test_deepen_binds_the_previous_answers_subject(self, explainer):
        d = _dispatch(explainer, parsed("but why?", Intent.LATE_ORDER,
                                        pointed=(SubjectKind.ORDER,),
                                        followup_of=FollowupKind.DEEPEN),
                      context={"last_answered_subject": {"order": "WO-2001"}})
        assert d.route == "late-order"
        assert "WO-2001" in d.routed_question

    def test_a_live_selection_outranks_stale_history(self, explainer):
        d = _dispatch(explainer, parsed("why is this order late", Intent.LATE_ORDER,
                                        pointed=(SubjectKind.ORDER,)),
                      context={"selection": {"order": "WO-2001"},
                               "history": [{"order": "WO-STALE"}]})
        assert "WO-2001" in d.routed_question and "board selection" in d.note

    def test_a_correction_re_answers_the_prior_question(self, explainer):
        d = _dispatch(explainer, parsed("no I meant WO-2001", Intent.LATE_ORDER,
                                        orders=("WO-2001",),
                                        followup_of=FollowupKind.CORRECTION))
        assert d.route == "late-order"
        assert d.note.startswith("corrected to WO-2001")
        assert d.routed_question == "why is WO-2001 late?"

    def test_list_expansion_re_fires_the_prior_intent_canonically(self, explainer):
        d = _dispatch(explainer, parsed("list them", Intent.LATE_ORDERS,
                                        followup_of=FollowupKind.LIST_EXPAND))
        assert d.route == "late-orders"
        assert d.routed_question == "which orders are late?"
        assert "listing the previous answer" in d.note

    def test_a_menu_selection_is_a_concept_not_an_entity_bind(self, explainer):
        """The founder's "what about wip" after a capability menu bound to an ORDER
        and dumped its operations. A menu item is a concept — and a live selection
        must not drag the answer back to an entity."""
        d = _dispatch(explainer, parsed("what about wip", Intent.COACHING,
                                        concepts=("wip",),
                                        followup_of=FollowupKind.MENU_SELECT),
                      context={"selection": {"order": "WO-2001"}})
        assert d.route == "coaching"
        assert d.bundle.key_facts.get("concept")
        assert "coaching on" in d.note

    def test_a_bound_subject_never_picks_the_intent(self, explainer):
        """The round-four terminal bug: a selected order short-circuited intent
        classification, so "is there any way I can get this done faster" op-dumped.
        A subject parameterizes; it never picks."""
        d = _dispatch(explainer, parsed("is there any way i can get this done faster",
                                        Intent.ADVICE, pointed=(SubjectKind.ORDER,)),
                      context={"selection": {"order": "WO-2001"}})
        assert d.route == "advice"
        assert d.bundle.subject_type == "advice"

    def test_confirmation_of_a_take_gets_the_bridge_not_a_near_miss(self, explainer):
        d = _dispatch(explainer, parsed(
            "so move the first operation to an earlier start time?",
            Intent.SWAP_MOVE, orders=("WO-2001",),
            followup_of=FollowupKind.CONFIRM_TAKE))
        assert d.route == "confirm-take"
        assert d.bundle.subject_type == "confirm_take"

    def test_the_confirm_take_answer_names_the_gesture_and_the_boundary(self,
                                                                       explainer):
        from mre.modules.renderers import TemplateRenderer
        d = _dispatch(explainer, parsed("so move it earlier?", Intent.CONFIRM_TAKE,
                                        orders=("WO-2001",),
                                        followup_of=FollowupKind.CONFIRM_TAKE))
        text = TemplateRenderer().render(d.bundle).lower()
        assert "drag" in text
        assert "accept" in text
        assert "i can't make it for you" in text


# ===========================================================================
# run_ask — the single entry point
# ===========================================================================

class TestRunAsk:
    def test_every_question_is_parsed_exactly_once(self, explainer):
        parser = ScriptedParser({"why is WO-2001 late":
                                 parsed("", Intent.LATE_ORDER, orders=("WO-2001",))})
        run_ask(explainer, "why is WO-2001 late", parser=parser)
        assert parser.calls == 1

    def test_without_a_parser_the_answer_is_honest_never_a_keyword_guess(self,
                                                                        explainer):
        """R-AI5(2): there is no deterministic-classifier fallback. A phrasing the
        old router matched by keyword ("why is WO-2001 late?") does NOT route."""
        result = run_ask(explainer, "why is WO-2001 late?", parser=None)
        assert result.route == "REFUSED"
        assert result.source == "none"
        assert result.bundle.subject_type == "unsupported"

    def test_an_unavailable_parser_is_the_same_honest_answer(self, explainer,
                                                             monkeypatch):
        from mre.modules.question_parser import QuestionParser
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = run_ask(explainer, "why is WO-2001 late?",
                         parser=QuestionParser())
        assert result.route == "REFUSED"

    def test_the_resolution_is_visible_on_the_bundle(self, explainer):
        parser = ScriptedParser({"why is this order late":
                                 parsed("", Intent.LATE_ORDER,
                                        pointed=(SubjectKind.ORDER,))})
        result = run_ask(explainer, "why is this order late", parser=parser,
                         context={"selection": {"order": "WO-2001"}})
        assert "WO-2001" in result.bundle.question
        assert result.resolved_question == result.bundle.question

    def test_the_ledger_records_the_parse_as_the_source(self, explainer, tmp_path):
        from mre.modules.question_ledger import QuestionLedger
        ledger = QuestionLedger(tmp_path / "ledger.jsonl")
        parser = ScriptedParser({"which orders are late":
                                 parsed("", Intent.LATE_ORDERS)})
        run_ask(explainer, "which orders are late", parser=parser, ledger=ledger,
                schedule_id="sched-1", session_id="sess-1")
        entries = ledger.recent(limit=5)
        assert entries and entries[0].route == "late-orders"
        assert entries[0].source == "parse"

    def test_the_parse_contract_rides_back_on_the_result(self, explainer):
        parser = ScriptedParser({"q": parsed("", Intent.LATE_ORDERS)})
        result = run_ask(explainer, "q", parser=parser)
        assert result.parsed is not None
        assert result.parsed.intent is Intent.LATE_ORDERS
        assert result.confidence == result.parsed.confidence

    def test_an_unscripted_question_is_unmatched_never_a_keyword_match(self,
                                                                      explainer):
        parser = ScriptedParser({})
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert result.route in ("REFUSED", "NEAR_MISS")
