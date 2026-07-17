"""Interpreter + conversational context + tiered fallback (Session 4A.1, R-AI1).

The paraphrase table below is the growing asset R-AI1(d) describes — the question
ledger's refusals feed new rows into it. Two disciplines it pins:

  - Deterministic phrasings route WITHOUT ever calling the interpreter (a
    call-counting mock asserts zero LLM calls) — zero regression, zero cost.
  - Everything else routes via a MOCKED interpreter response (no network), so the
    LLM→route→resolve→answer path is exercised deterministically.

The LLM never authors an answer here: the mock only returns a route id from the
closed taxonomy + params; run_ask does the routing and resolution.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer
from mre.modules.interpreter import (
    Interpretation,
    Interpreter,
    parse_interpretation,
    resolve_followup,
    resolve_params,
    run_ask,
)

# ---------------------------------------------------------------------------
# A compact fake snapshot + evidence fixture (self-contained; mirrors the
# test_explainer fake). Registers WO-2001 / M-GEAR-01 / M-GEAR-02 so classify()
# and param resolution have real external refs to match against.
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


# ---------------------------------------------------------------------------
# A mock interpreter: a lookup table + a call counter (asserts no LLM on the
# deterministic path).
# ---------------------------------------------------------------------------

class MockInterpreter(Interpreter):
    def __init__(self, table: dict[str, Optional[Interpretation]]):
        # Deliberately skip the base __init__: no key, no client, but AVAILABLE.
        self._table = table
        self.available = True
        self.calls = 0

    def interpret(self, question: str) -> Optional[Interpretation]:
        self.calls += 1
        return self._table.get(question)


# ---------------------------------------------------------------------------
# CU1 — the paraphrase table
# ---------------------------------------------------------------------------

# (question, expected route id/subject signal). These route with NO interpreter.
DETERMINISTIC = [
    ("why is WO-2001 late?", "late-order"),
    ("why is WO-2001 delayed?", "late-order"),
    ("which orders are late?", "late-orders"),
    ("are there any late orders?", "late-orders"),
    ("why is WO-2001 on M-GEAR-01?", "why-on-machine"),
    ("what's running on M-GEAR-01?", "schedule"),
    ("what's next on M-GEAR-01?", "schedule"),
    ("when does WO-2001 finish?", "schedule"),
    ("what data problems exist?", "data-problems"),
    ("how much downtime does M-GEAR-01 have?", "downtime"),
    ("what changed since the last version?", "version-diff"),
    ("how do I fix it?", "remediation"),
    ("what should I fix first?", "triage"),
    ("what's wrong with the submission?", "certificate-testimony"),
    ("summarize my changes", "edit-summary"),
    ("what did this move cost?", "edit-cost"),
    ("what questions couldn't you answer recently?", "ledger-refusals"),
]


@pytest.mark.parametrize("question,expected_route", DETERMINISTIC)
def test_deterministic_routes_without_llm(explainer, question, expected_route):
    route_id, _params = explainer.classify(question)
    assert route_id == expected_route


def test_deterministic_path_never_calls_the_interpreter(explainer):
    # A mock that would explode if any deterministic case reached it.
    mock = MockInterpreter({})
    for question, _ in DETERMINISTIC:
        run_ask(explainer, question, interpreter=mock)
    assert mock.calls == 0, "a deterministic phrasing reached the interpreter"


# Non-deterministic paraphrases → a mocked interpreter maps them onto the
# taxonomy. Params use resolvable substrings ('2001' ⊂ 'WO-2001', 'GEAR-01' ⊂
# 'M-GEAR-01') so the full resolve path runs.
LLM_TABLE = {
    "which orders are in trouble":
        Interpretation("late-orders", {}, 0.92),
    "is anything going to miss its deadline":
        Interpretation("late-orders", {}, 0.88),
    "what's cooking on the gear machine":
        Interpretation("machine-schedule", {"machine": "GEAR-01"}, 0.85),
    "give me the finish time for order 2001":
        Interpretation("order-schedule", {"order": "2001"}, 0.83),
    "break down my last edit's price":
        Interpretation("edit-cost", {}, 0.80),
    "show everything for acme corp":
        Interpretation("customer-schedule", {"customer": "acme"}, 0.78),
}

# (question, expected subject_type after routing)
LLM_EXPECT = {
    "which orders are in trouble": "late_orders",
    "is anything going to miss its deadline": "late_orders",
    "what's cooking on the gear machine": "schedule",
    "give me the finish time for order 2001": "schedule",
    "break down my last edit's price": "edit_cost",
    "show everything for acme corp": "schedule",
}


@pytest.mark.parametrize("question", list(LLM_TABLE))
def test_llm_paraphrases_route_via_mocked_interpreter(explainer, question):
    mock = MockInterpreter(LLM_TABLE)
    result = run_ask(explainer, question, interpreter=mock)
    assert mock.calls == 1, "the interpreter was expected exactly once"
    assert result.source == "llm"
    assert result.route == LLM_TABLE[question].route
    assert result.bundle.subject_type == LLM_EXPECT[question]


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------

def test_optimality_question_does_not_route_to_the_schedule_listing(explainer):
    """4A.1c: "is there a better schedule" contains the bare word "schedule" and
    used to route to the schedule LISTING (prose). It asks whether a better plan
    EXISTS — the deterministic surface can't answer that, so it must fall through
    to unsupported (→ the honest refusal / interpreter bridge), never a listing."""
    route_id, _ = explainer.classify("is there a better schedule")
    assert route_id == "unsupported"
    # a normal schedule listing still routes
    assert explainer.classify("what's the schedule for M-GEAR-01")[0] == "schedule"


def test_optimality_question_refuses_deterministically(explainer):
    # With no interpreter (deterministic-only), the better-schedule question
    # reaches the honest refusal — not a schedule listing rendered as an answer.
    result = run_ask(explainer, "is there a better schedule", interpreter=None)
    assert result.route == "REFUSED"
    assert result.bundle.subject_type == "unsupported"


def test_no_interpreter_refuses_honestly(explainer):
    result = run_ask(explainer, "what's cooking on the gear machine", interpreter=None)
    assert result.route == "REFUSED"
    assert result.source == "none"
    assert result.bundle.subject_type == "unsupported"


def test_interpreter_returning_none_refuses(explainer):
    mock = MockInterpreter({"gobbledygook": None})
    result = run_ask(explainer, "gobbledygook", interpreter=mock)
    assert result.route == "REFUSED"
    assert result.bundle.subject_type == "unsupported"


def test_parse_interpretation_rejects_unknown_route():
    assert parse_interpretation('{"route": "not-a-route", "confidence": 0.9}') is None


def test_parse_interpretation_rejects_malformed():
    assert parse_interpretation("not json at all") is None
    assert parse_interpretation("") is None


def test_parse_interpretation_tolerates_fenced_json():
    interp = parse_interpretation('```json\n{"route":"late-orders","confidence":0.7}\n```')
    assert interp is not None and interp.route == "late-orders"


def test_parse_interpretation_clamps_confidence():
    interp = parse_interpretation('{"route":"late-orders","confidence":5}')
    assert interp is not None and interp.confidence == 1.0


# ---------------------------------------------------------------------------
# CU4 — tiered fallback (near-miss / refuse)
# ---------------------------------------------------------------------------

def test_moderate_confidence_is_a_near_miss(explainer):
    mock = MockInterpreter({"tell me about stuff":
                            Interpretation("late-orders", {}, 0.55)})
    result = run_ask(explainer, "tell me about stuff", interpreter=mock)
    assert result.route == "NEAR_MISS"
    assert result.bundle.subject_type == "near_miss"
    # offers are authored, concrete, and at most two
    offers = result.bundle.key_facts["offers"]
    assert 1 <= len(offers) <= 2


def test_unresolvable_params_become_a_near_miss(explainer):
    mock = MockInterpreter({"what's cooking on the mystery machine":
                            Interpretation("machine-schedule",
                                           {"machine": "does-not-exist"}, 0.95)})
    result = run_ask(explainer, "what's cooking on the mystery machine", interpreter=mock)
    assert result.route == "NEAR_MISS"
    assert result.bundle.subject_type == "near_miss"


def test_low_confidence_refuses(explainer):
    mock = MockInterpreter({"???": Interpretation("late-orders", {}, 0.20)})
    result = run_ask(explainer, "???", interpreter=mock)
    assert result.route == "REFUSED"


# ---------------------------------------------------------------------------
# param resolution (external refs in, canonical resolution inside)
# ---------------------------------------------------------------------------

def test_resolve_params_substring_matches_identity(explainer):
    interp = Interpretation("machine-schedule", {"machine": "GEAR-01"}, 0.9)
    resolved, ok = resolve_params(explainer, interp)
    assert ok and resolved["machine"] == "M-GEAR-01"


def test_resolve_params_reports_partial(explainer):
    interp = Interpretation("why-on-machine",
                            {"order": "2001", "machine": "nope"}, 0.9)
    resolved, ok = resolve_params(explainer, interp)
    assert ok is False
    assert resolved.get("order") == "WO-2001"


# ---------------------------------------------------------------------------
# CU2 — conversational context (follow-ups)
# ---------------------------------------------------------------------------

def test_self_contained_question_is_not_resolved(explainer):
    rq = resolve_followup("why is WO-2001 late?", {}, explainer)
    assert rq.resolved is False and rq.text == "why is WO-2001 late?"


def test_pronoun_followup_resolves_against_last_order(explainer):
    ctx = {"history": [{"order": "WO-2001", "route": "late-order"}]}
    rq = resolve_followup("and what would fix it?", ctx, explainer)
    assert rq.resolved is True
    assert "WO-2001" in rq.text


def test_cost_followup_after_edit_resolves_to_edit_cost(explainer):
    ctx = {"history": [{"route": "edit-summary"}]}
    rq = resolve_followup("how much?", ctx, explainer)
    assert rq.resolved is True
    route_id, _ = explainer.classify(rq.text)
    assert route_id == "edit-cost"


def test_selection_supplies_the_referent(explainer):
    ctx = {"selection": {"order": "WO-2001"}}
    rq = resolve_followup("and what about it?", ctx, explainer)
    assert rq.resolved is True and "WO-2001" in rq.text


def test_unresolvable_ellipsis_asks_for_clarification(explainer):
    result = run_ask(explainer, "and what would fix it?", context={})
    assert result.route == "CLARIFY"
    assert result.bundle.subject_type == "clarify"


def test_three_turn_chain_through_run_ask(explainer):
    # turn 1: a full question establishes the subject.
    r1 = run_ask(explainer, "why is WO-2001 late?")
    assert r1.route == "late-order"
    history = [{"question": "why is WO-2001 late?", "order": "WO-2001",
                "route": r1.route}]
    # turn 2: an elliptical follow-up resolves against WO-2001 and routes.
    r2 = run_ask(explainer, "and what about it?",
                 context={"history": history})
    assert r2.resolved_question != "and what about it?"
    assert "WO-2001" in r2.resolved_question
    assert r2.route != "unsupported" and r2.route != "CLARIFY"
    # the answer is visible about what it answered
    assert r2.bundle.question == r2.resolved_question


def test_resolution_is_visible_on_the_bundle(explainer):
    ctx = {"history": [{"order": "WO-2001", "route": "late-order"}]}
    result = run_ask(explainer, "and what would fix it?", context=ctx)
    assert result.bundle.question == result.resolved_question
    assert "WO-2001" in result.bundle.question
