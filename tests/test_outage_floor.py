"""THE TWO FLOORS: an outage may never wear the capability card (4A, R-OF1).

THE SPECIMEN this file exists for, measured live on 2026-08-03 with a
credit-exhausted key. Three different questions — "find order and highlight
126", "why cant ORD-000126 op30 start earlier", "why cant this be moved" — came
back as one identical card:

    "I couldn't answer that one: I don't have a tool that reaches it. Nothing I
     can read holds that, so I'd rather say so than guess.
     Here's what I can do that's closest: …"
    [rendered by: synthesis — 0 tool call(s)]

Every clause of that is false in that failure mode. The tools were there, the
evidence was there, and the question was never read at all, because the parse
layer could not reach its language model. An infrastructure outage was wearing
the sentence for a capability gap — and a planner reads that as "the product
can't do this", which is what the founder read.

WHAT IS ASSERTED HERE, and why each one is a separate test:

  * the CLASSIFICATION — an unreachable call and an unusable answer are
    different facts at the one seam that can still tell them apart
    (`llm_compat`), because everything downstream inherits that distinction;
  * the three OUTAGE PATHS — parse-call failure, synthesis-call failure, and a
    parse layer with no model at all — each render the outage card;
  * the CAPABILITY FLOOR IS UNTOUCHED where the model is up and the question is
    genuinely outside our scope. That is the control: a fix that turned every
    honest refusal into an outage would pass every other test in this file;
  * NO SILENT RETRY, no queue, no degraded keyword guess;
  * the FOOTER names no tier that did not run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.contracts.parse import ClarifyReason, Intent
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer, register_of
from mre.modules.interpreter import dispatch, run_ask, tier_of
from mre.modules.question_parser import QuestionParser
from mre.modules.renderers import TemplateRenderer
from tests.parse_doubles import (
    DeadSynthesizer,
    UnreachableClient,
    UnreachableSynthesizer,
    emission,
    parsed,
    parser_with,
    resolve,
    synthesizer_with,
)

DEMAND_ID = "85342968-6107-58db-95d3-256cd6765fec"


def _make_index(tmp_path: Path) -> EvidenceIndex:
    records = [
        {"record_type": "run_context_open", "run_id": "run-m7", "module": "M7",
         "snapshot_id": "snap-demo", "purpose": "t",
         "timestamp": "2026-07-06T00:00:00Z"},
        {"record_type": "metric", "record_id": "met-late-001", "run_id": "run-m7",
         "module": "M7", "seq": 8, "snapshot_id": "snap-demo",
         "subjects": [{"entity_id": DEMAND_ID, "entity_type": "demand"}],
         "tier": "supporting", "message": "", "name": "lateness_minutes",
         "value": 840.0, "unit": "minutes", "rollup_of": []},
        {"record_type": "run_context_close", "run_id": "run-m7",
         "status": "success", "ended_at": "2026-07-06T00:03:00Z"},
    ]
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "demo.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return EvidenceIndex().build(runs_dir)


class _Reader:
    def get_entity(self, entity_id):
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
        return m


class _Store:
    def load_snapshot(self, snap_id):
        return _Reader()


@pytest.fixture()
def explainer(tmp_path):
    return Explainer(snapshot_store=_Store(), index=_make_index(tmp_path),
                     snapshot_id="snap-demo")


def _text(bundle) -> str:
    return TemplateRenderer().render(bundle)


# ===========================================================================
# 1 — THE CLASSIFICATION. Everything else inherits it.
# ===========================================================================

class TestTheCallNamesItsFailure:
    def test_a_call_that_could_not_be_made_is_unreachable(self):
        from mre.modules.llm_compat import UNREACHABLE, call_text_outcome
        client = UnreachableClient()
        out = call_text_outcome(client, "claude-haiku-4-5-20251001", 100,
                                [{"role": "user", "content": "hi"}])
        assert out.text is None
        assert out.unreachable and out.failure.kind == UNREACHABLE

    def test_a_call_that_answered_unusably_is_NOT_unreachable(self):
        """The distinction the whole session turns on. A model that replied with
        prose instead of JSON was REACHED; that is a quality failure and it keeps
        the pre-existing floor."""
        from tests.parse_doubles import FakeClient
        from mre.modules.llm_compat import call_text_outcome
        out = call_text_outcome(FakeClient(["not json at all"]),
                                "claude-haiku-4-5-20251001", 100,
                                [{"role": "user", "content": "hi"}])
        assert out.text == "not json at all"
        assert not out.unreachable and out.failure is None

    def test_the_transport_detail_never_reaches_a_planner_surface(self, explainer):
        """4B.23 §5a.91: no raw transport string on a planner surface. The status
        code and the provider's wording are for the log."""
        parser = QuestionParser(_client=UnreachableClient())
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        text = _text(result.bundle)
        for leak in ("400", "credit balance", "RuntimeError", "Error code"):
            assert leak not in text, leak


# ===========================================================================
# 2 — THE THREE OUTAGE PATHS
# ===========================================================================

class TestTheOutageFloor:
    def test_a_parse_that_could_not_reach_a_model_says_so(self, explainer):
        parser = QuestionParser(_client=UnreachableClient())
        result = run_ask(explainer, "why cant ORD-000126 op30 start earlier",
                         parser=parser)
        assert result.route == "OUTAGE"
        assert result.bundle.subject_type == "outage"
        assert result.parsed.clarify.reason is ClarifyReason.MODEL_UNREACHABLE
        text = _text(result.bundle)
        assert "can't reach my language model" in text
        assert "outage on my side" in text

    def test_a_synthesis_tier_that_could_not_reach_a_model_says_so(self,
                                                                  explainer):
        """The second route to the same specimen: the question WAS read, and the
        reach that failed is the reasoning tier's."""
        d = dispatch(explainer,
                     resolve(parsed("is there a better schedule",
                                    Intent.UNMATCHED, confidence=0.2), explainer),
                     synthesizer=UnreachableSynthesizer())
        assert d.route == "OUTAGE"
        text = _text(d.bundle)
        assert "I read your question" in text
        assert "couldn't reach my language model" in text

    def test_no_model_configured_is_an_outage_not_a_capability_limit(self,
                                                                     explainer,
                                                                     monkeypatch):
        """A parser that EXISTS and has no model is the founder's other case (a
        missing key). Before this it answered "I can't answer this question yet"
        — a claim about the question, made by a layer that never read it."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = run_ask(explainer, "why is WO-2001 late?",
                         parser=QuestionParser())
        assert result.route == "OUTAGE"
        text = _text(result.bundle)
        assert "no language model available" in text
        # Nothing to wait for: there is no outage to pass.
        assert "Try me again" not in text

    def test_every_outage_card_says_the_board_still_works(self, explainer):
        parser = QuestionParser(_client=UnreachableClient())
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert "The board, the schedule and everything you can click still work" \
            in _text(result.bundle)


# ===========================================================================
# 3 — WHAT THE CARD MAY NOT SAY OR DO
# ===========================================================================

class TestTheCardClaimsNothingItCannotKnow:
    @pytest.fixture()
    def outage_text(self, explainer):
        parser = QuestionParser(_client=UnreachableClient())
        return _text(run_ask(explainer, "why cant this be moved",
                             parser=parser).bundle)

    def test_it_never_claims_a_tool_gap(self, outage_text):
        """The exact sentence the founder was shown."""
        assert "don't have a tool that reaches it" not in outage_text
        assert "Nothing I can read holds that" not in outage_text

    def test_it_offers_no_nearest_capabilities(self, outage_text):
        """`SYNTHESIS_FLOOR_DOORS` presupposes the question was understood well
        enough to find a neighbour for it. Nothing read this one."""
        assert "Here's what I can do that's closest" not in outage_text

    def test_it_lists_no_supported_question_types(self, outage_text):
        assert "Supported question types" not in outage_text

    def test_it_cites_no_records_and_claims_no_look_up(self, outage_text):
        assert "[record:" not in outage_text
        assert "no evidence records found" not in outage_text

    def test_the_footer_names_no_tier_that_did_not_run(self, outage_text):
        assert "rendered by: synthesis" not in outage_text
        assert "tool call(s)" not in outage_text
        assert "[rendered by: authored copy — the language model was " \
               "unreachable | register: system]" in outage_text

    def test_no_rider_qualifies_an_answer_that_does_not_exist(self, explainer):
        """FOUND IN THE LIVE CONFIRMATION, not here. The first outage card served
        from the demo board carried the predicate-coverage rider — *"I haven't
        addressed the time you named — what I said above is when it does start"*
        — about a card whose whole content is that nothing was read. Every rider
        on the delivery seam qualifies an ANSWER; there is none here."""
        from mre.modules.explainer import Explainer
        parser = QuestionParser(_client=UnreachableClient())
        text = _text(run_ask(explainer, "why cant ORD-000126 op30 start earlier",
                             parser=parser).bundle)
        assert "what I said above" not in text
        assert "I haven't addressed" not in text
        # And the card is exactly the authored copy plus its footer: four lines,
        # nothing appended by anything.
        assert len([ln for ln in text.strip().splitlines() if ln.strip()]) == 4

    def test_both_renderers_withhold_the_riders(self, explainer):
        """A floor one render path can skip is not a floor."""
        from mre.modules.renderers import LLMRenderer
        parser = QuestionParser(_client=UnreachableClient())
        bundle = run_ask(explainer, "why cant this be moved",
                         parser=parser).bundle
        assert LLMRenderer().render(bundle) == _text(bundle)

    def test_the_register_is_not_testimony(self, explainer):
        parser = QuestionParser(_client=UnreachableClient())
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert register_of(result.bundle) == "system"
        assert result.register == "system"


class TestItDoesNotRetryOrGuess:
    def test_an_unreachable_parse_is_not_retried(self, explainer):
        """The parse retries ONCE on a malformed emission. A transport that is
        down is not answered by asking it twice, and counting it as malformed
        would file an outage as a quality failure."""
        client = UnreachableClient()
        parser = QuestionParser(_client=client)
        run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert len(client.calls) == 1
        assert parser.stats.unreachable == 1
        assert parser.stats.malformed == 0

    def test_a_keyword_shaped_question_still_gets_no_keyword_answer(self,
                                                                    explainer):
        """R-AI5(2) is untouched: the outage floor is an honest non-answer, never
        a degraded classifier."""
        parser = QuestionParser(_client=UnreachableClient())
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert result.route == "OUTAGE"
        assert result.source == "none" or result.parsed.intent is Intent.UNMATCHED
        assert "840" not in _text(result.bundle)

    def test_the_preflight_shows_no_reading_beat_for_an_outage(self, explainer):
        """Beat one must not promise a read that cannot happen."""
        parser = QuestionParser(_client=UnreachableClient())
        p = parser.parse("why is WO-2001 late?", explainer=explainer)
        assert tier_of(p, explainer) == "floor"


# ===========================================================================
# 4 — THE CONTROL. The capability floor must NOT regress.
# ===========================================================================

class TestTheCapabilityFloorIsUntouched:
    def test_a_live_model_with_an_out_of_scope_question_keeps_the_old_card(
            self, explainer):
        """The model is UP, the question genuinely reaches no route and the tier
        grounded nothing. That is a capability fact and it keeps its words."""
        synth = synthesizer_with([json.dumps(
            {"cannot_answer": "no tool of mine reaches the cockpit's colours"})])
        d = dispatch(explainer,
                     resolve(parsed("what colour is the tray",
                                    Intent.UNMATCHED, confidence=0.2), explainer),
                     synthesizer=synth)
        assert d.route == "synthesis"
        text = _text(d.bundle)
        assert "I couldn't answer that one" in text
        assert "register: synthesis" in text

    def test_a_malformed_emission_still_reaches_the_parse_failed_floor(
            self, explainer):
        """A model that ANSWERED unusably keeps `parse-failed`, retry and all."""
        parser = parser_with(["not json", "still not json"])
        p = parser.parse("why is WO-2001 late?", explainer=explainer)
        assert p.clarify.reason is ClarifyReason.PARSE_FAILED
        assert parser.stats.malformed == 2

    def test_an_unavailable_synthesizer_keeps_the_bridge(self, explainer):
        """A tier that is not there is not an outage of one: the question was
        read, and the bridge's offers are computed from that real parse."""
        d = dispatch(explainer,
                     resolve(parsed("is there a better schedule", Intent.UNMATCHED,
                                    confidence=0.2,
                                    nearest=(Intent.LATE_ORDERS,)), explainer),
                     synthesizer=DeadSynthesizer())
        assert d.route == "NEAR_MISS"

    def test_a_caller_that_passed_no_parser_at_all_keeps_the_bridge(self,
                                                                    explainer):
        """The deliberate no-parser call (the API's degraded re-run, and every
        R-AI5(2) test): nothing here can tell whether an AI layer was ever meant
        to be present, so it may not assert an outage."""
        result = run_ask(explainer, "why is WO-2001 late?", parser=None)
        assert result.route == "REFUSED"
        assert result.bundle.subject_type == "unsupported"

    def test_a_working_parser_still_answers_the_question(self, explainer):
        """The premise test: with a reachable model nothing about this session's
        change is visible at all."""
        parser = parser_with([emission(
            "late-order", [{"kind": "order", "raw": "WO-2001"}])])
        result = run_ask(explainer, "why is WO-2001 late?", parser=parser)
        assert result.route == "late-order"
        assert result.register == "testimony"
