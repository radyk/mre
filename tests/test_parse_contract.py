"""The parse contract + the parser (R-AI5(1), Session 4A.5a CU1).

What is asserted here is everything about the parse layer that is DETERMINISTIC:

  * the closed vocabulary and the explainer's route taxonomy name the same set,
    and every model-selectable intent carries an authored meaning;
  * the governed prompt artifact renders that vocabulary, the live context, and the
    question — and never asks the model for an answer;
  * an emission becomes a validated contract, or it does not become one at all
    (a malformed emission retries ONCE and then clarifies — never a guess, never a
    crash);
  * SUBJECT RESOLUTION: the planner's words resolve against THIS run's vocabulary
    (exact, near-miss, "order N"), and a POINTED subject binds typed at the fixed
    priority selection > last answered subject > history.

What is NOT asserted here is whether a live model picks the right intent for a
given phrasing — that is the exam sweep's job against the pinned world (R-AI4(2)).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.contracts.parse import (
    ClarifyReason,
    FollowupKind,
    Intent,
    INTENT_MEANINGS,
    MODEL_SELECTABLE_INTENTS,
    ParsedQuestion,
    Polarity,
    SubjectKind,
    SubjectSource,
)
from mre.modules.explainer import ROUTE_TAXONOMY
from mre.modules.question_parser import (
    QuestionParser,
    bind_subjects,
    build_parsed,
    extract_json,
    load_prompt,
    render_context,
    render_intents,
)
from tests.parse_doubles import FakeClient, emission, parser_with

from tests.test_interpreter import explainer  # noqa: F401 — the shared fixture


# ===========================================================================
# The closed vocabulary
# ===========================================================================

class TestVocabulary:
    def test_intents_and_routes_name_the_same_set(self):
        """The intent vocabulary IS the route taxonomy (plus `unmatched`). A route
        the parse cannot name is unreachable; an intent with no route is a wall."""
        intents = {i.value for i in Intent} - {Intent.UNMATCHED.value}
        assert intents == set(ROUTE_TAXONOMY)

    def test_every_selectable_intent_has_an_authored_meaning(self):
        missing = [i.value for i in MODEL_SELECTABLE_INTENTS
                   if not INTENT_MEANINGS.get(i)]
        assert missing == []

    def test_unknown_entity_is_never_offered_to_the_model(self):
        # It is a DISPATCH outcome (a named order that resolves to nothing), not
        # something a planner ever expresses.
        assert Intent.UNKNOWN_ENTITY not in MODEL_SELECTABLE_INTENTS

    def test_an_unknown_intent_is_not_coerced(self):
        assert build_parsed("q", {"intent": "not-an-intent"}, None, None) is None
        assert build_parsed("q", {"intent": "unknown-entity"}, None, None) is None

    def test_a_followup_kind_in_the_intent_field_is_a_misfiling_not_garbage(self):
        """Session 4A.5b, from the sweep's malformed-emission samples: the model
        named the GESTURE correctly and put it in the wrong field. Discarding a
        correct reading over a misfiled field is waste, not strictness — the intent
        becomes `unmatched` (which now answers) and the linkage is kept."""
        out = build_parsed("q", {"intent": "list-expand",
                                 "followup_of": "list-expand"}, None, None)
        assert out is not None
        assert out.intent is Intent.UNMATCHED
        assert out.followup_of.value == "list-expand"
        # and a genuinely out-of-vocabulary id is still malformed
        assert build_parsed("q", {"intent": "solve-the-halting-problem"},
                            None, None) is None


# ===========================================================================
# The governed prompt artifact
# ===========================================================================

class TestPromptArtifact:
    def test_header_names_the_ruling_and_the_review_discipline(self):
        text = Path(load_prompt.__globals__["_PROMPT_PATH"]).read_text(encoding="utf-8")
        head = text.split("## PROMPT")[0]
        assert "R-AI5(1)" in head
        assert "prompt_version" in head
        assert "reviewed" in head.lower()

    def test_body_carries_the_three_placeholders(self):
        body, version = load_prompt()
        assert version
        for slot in ("{INTENTS}", "{CONTEXT}", "{QUESTION}"):
            assert slot in body

    def test_rendered_prompt_carries_every_selectable_intent(self):
        rendered = render_intents()
        for i in MODEL_SELECTABLE_INTENTS:
            assert f"  {i.value} — " in rendered

    def test_prompt_never_asks_for_an_answer(self):
        body, _ = load_prompt()
        assert "never answer" in body.lower() or "You never answer" in body

    def test_context_renders_the_three_channels(self):
        ctx = {"selection": {"order": "ORD-05", "machine": "CUT-01"},
               "last_answered_subject": {"order": "ORD-13"},
               "history": [{"question": "why is ORD-13 late", "route": "late-order"}]}
        out = render_context(ctx)
        assert "ORD-05" in out and "CUT-01" in out
        assert "ORD-13" in out
        assert "why is ORD-13 late" in out and "late-order" in out

    def test_context_with_nothing_live_says_so(self):
        out = render_context({})
        assert "none" in out and "first question" in out


# ===========================================================================
# Emission -> contract
# ===========================================================================

class TestEmission:
    def test_extract_json_tolerates_a_fence(self):
        assert extract_json('```json\n{"intent":"late-orders"}\n```') == {
            "intent": "late-orders"}

    def test_extract_json_rejects_non_objects(self):
        assert extract_json("not json") is None
        assert extract_json("[1,2,3]") is None
        assert extract_json("") is None

    def test_confidence_is_clamped(self, explainer):
        p = build_parsed("q", json.loads(emission("late-orders", confidence=5)),
                         explainer, None)
        assert p is not None and p.confidence == 1.0

    def test_bad_enum_members_degrade_without_raising(self, explainer):
        p = build_parsed("q", {"intent": "late-orders", "polarity": "sideways",
                               "followup_of": "telepathy", "confidence": "abc",
                               "nearest": ["nonsense", "triage"]},
                         explainer, None)
        assert p is not None
        assert p.polarity is None
        assert p.followup_of is FollowupKind.NONE
        assert p.confidence == 0.0
        assert p.nearest == [Intent.TRIAGE]

    def test_clarify_reason_must_be_in_the_closed_set(self, explainer):
        p = build_parsed("q", {"intent": "late-orders",
                               "clarify": {"reason": "because-i-said-so"}},
                         explainer, None)
        assert p is not None and p.clarify is None
        p2 = build_parsed("q", {"intent": "late-order",
                                "clarify": {"reason": "no-subject"}},
                          explainer, None)
        assert p2.clarify.reason is ClarifyReason.NO_SUBJECT

    def test_contract_forbids_unknown_fields(self):
        with pytest.raises(Exception):
            ParsedQuestion(question="q", intent=Intent.LATE_ORDERS, smuggled=1)


# ===========================================================================
# Subject resolution (deterministic, local — never the model's)
# ===========================================================================

class TestSubjectResolution:
    def test_a_named_order_resolves_against_the_run_vocabulary(self, explainer):
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "WO-2001"}], None)
        assert subs[0].ref == "WO-2001" and subs[0].source is SubjectSource.UTTERANCE

    def test_the_order_N_register_resolves_by_numeric_inference(self, explainer):
        """The founder's live register ("swap order 5 and order 4"): the noun plus
        a bare number resolves against the PINNED world's real ids, never string
        synthesis — and the raw differs from the ref, so the dispatch surfaces the
        assumption ("assuming ...")."""
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "order 2001"}], None)
        assert subs[0].ref == "WO-2001"
        assert subs[0].raw != subs[0].ref

    def test_an_absent_order_stays_unresolved(self, explainer):
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "WO-9999"}], None)
        assert subs[0].ref is None and not subs[0].resolved

    def test_a_machine_resolves_by_unique_substring(self, explainer):
        subs = bind_subjects(explainer, [{"kind": "machine", "raw": "GEAR-01"}], None)
        assert subs[0].ref == "M-GEAR-01"

    def test_a_pointed_subject_binds_from_the_board_selection_first(self, explainer):
        ctx = {"selection": {"order": "WO-2001"},
               "last_answered_subject": {"order": "WO-OTHER"},
               "history": [{"order": "WO-STALE"}]}
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "this order",
                                          "from_context": True}], ctx)
        assert subs[0].ref == "WO-2001"
        assert subs[0].source is SubjectSource.SELECTION

    def test_a_pointed_subject_falls_to_the_last_answered_subject(self, explainer):
        ctx = {"last_answered_subject": {"order": "WO-2001"},
               "history": [{"order": "WO-STALE"}]}
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "it",
                                          "from_context": True}], ctx)
        assert subs[0].ref == "WO-2001"
        assert subs[0].source is SubjectSource.LAST_ANSWER

    def test_a_pointed_subject_falls_to_history_last(self, explainer):
        ctx = {"history": [{"order": "WO-2001"}]}
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "it",
                                          "from_context": True}], ctx)
        assert subs[0].ref == "WO-2001"
        assert subs[0].source is SubjectSource.HISTORY

    def test_binding_is_TYPED_never_cross_type(self, explainer):
        """"that machine" must never bind to an order four turns back."""
        ctx = {"selection": {"order": "WO-2001"}, "history": [{"order": "WO-2001"}]}
        subs = bind_subjects(explainer, [{"kind": "machine", "raw": "that machine",
                                          "from_context": True}], ctx)
        assert subs[0].ref is None

    def test_nothing_live_leaves_a_pointed_subject_unresolved(self, explainer):
        subs = bind_subjects(explainer, [{"kind": "order", "raw": "this order",
                                          "from_context": True}], {})
        assert subs[0].ref is None

    def test_a_concept_resolves_through_the_capability_registry(self, explainer):
        subs = bind_subjects(explainer, [{"kind": "concept", "raw": "splitting"}], None)
        assert subs[0].ref is not None

    def test_a_malformed_subject_entry_is_dropped_not_raised(self, explainer):
        subs = bind_subjects(explainer, ["nonsense", {"kind": "nope", "raw": "x"},
                                         {"kind": "order", "raw": "WO-2001"}], None)
        assert [s.ref for s in subs] == ["WO-2001"]


# ===========================================================================
# The parser: one call, one retry, then clarify
# ===========================================================================

class TestParser:
    def test_a_clean_emission_parses(self, explainer):
        p = parser_with([emission("late-order", [{"kind": "order",
                                                  "raw": "WO-2001"}])])
        out = p.parse("why is WO-2001 late", explainer=explainer)
        assert out.intent is Intent.LATE_ORDER
        assert out.ref(SubjectKind.ORDER) == "WO-2001"
        assert out.prompt_version and out.latency_ms is not None
        assert p.stats.calls == 1 and p.stats.retries == 0

    def test_the_prompt_carries_the_vocabulary_and_the_question(self, explainer):
        client = FakeClient([emission("late-orders")])
        QuestionParser(_client=client).parse("which orders are late",
                                             explainer=explainer)
        sent = client.calls[0]["messages"][0]["content"]
        assert "late-order — " in sent
        assert "which orders are late" in sent
        assert client.calls[0]["temperature"] == 0

    def test_a_malformed_emission_retries_once_then_succeeds(self, explainer):
        p = parser_with(["not json at all", emission("late-orders")])
        out = p.parse("q", explainer=explainer)
        assert out.intent is Intent.LATE_ORDERS
        assert p.stats.calls == 2 and p.stats.retries == 1 and p.stats.malformed == 1

    def test_two_malformed_emissions_clarify_never_guess(self, explainer):
        p = parser_with(["garbage", "still garbage"])
        out = p.parse("q", explainer=explainer)
        assert out.intent is Intent.UNMATCHED
        assert out.clarify.reason is ClarifyReason.PARSE_FAILED
        assert p.stats.calls == 2 and p.stats.clarifies == 1

    def test_an_out_of_vocabulary_intent_is_malformed(self, explainer):
        p = parser_with([emission("solve-the-halting-problem"), "junk"])
        out = p.parse("q", explainer=explainer)
        assert out.clarify.reason is ClarifyReason.PARSE_FAILED

    def test_a_raising_client_never_escapes_and_names_the_outage(self, explainer):
        """Micro-session 4A (R-OF1) SHARPENS this, it does not relax it: a raising
        client still never escapes, and the reason is no longer `parse-failed`.

        `parse-failed` means a model ANSWERED and we could not make a parse out
        of what it said — a fact about the emission, which is what the two tests
        above assert. A client that raises was never reached, and the two facts
        get two floors: telling a planner "I don't have a tool that reaches it"
        because an HTTP call failed is the defect this session exists for."""
        class Boom:
            def __init__(self):
                self.messages = self

            def create(self, **kw):
                raise RuntimeError("network")
        p = QuestionParser(_client=Boom())
        out = p.parse("q", explainer=explainer)
        assert out.clarify.reason is ClarifyReason.MODEL_UNREACHABLE
        assert p.stats.unreachable == 1 and p.stats.malformed == 0

    def test_no_key_and_no_client_is_simply_unavailable(self, explainer, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        p = QuestionParser()
        assert p.available is False
        assert p.parse("q", explainer=explainer) is None
        assert p.stats.unavailable == 1

    def test_stats_report_a_median_latency(self, explainer):
        p = parser_with([emission("late-orders"), emission("late-orders")])
        p.parse("a", explainer=explainer)
        p.parse("b", explainer=explainer)
        assert p.stats.parses == 2
        assert p.stats.as_dict()["median_latency_ms"] is not None

    def test_polarity_and_followup_survive_the_round_trip(self, explainer):
        p = parser_with([emission("start-reason",
                                  [{"kind": "order", "raw": "WO-2001"}],
                                  polarity="negative", followup_of="deepen")])
        out = p.parse("why can't it start sooner", explainer=explainer)
        assert out.polarity is Polarity.NEGATIVE
        assert out.followup_of is FollowupKind.DEEPEN
