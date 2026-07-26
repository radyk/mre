"""The ask chain, live through the API (Session 4A.1, R-AI1).

One deterministic solve, then the ask surface exercised end to end: a natural
(voice-shaped) question routes, the answer renders, and a question-ledger row is
written to its own stream under the data root (never inside a run's evidence).
A conversational chain resolves an ellipsis live; the DEV-gated refusal view is
gated.

Session 4A.5a: the ask path is LLM-first (R-AI5(1)) with no keyword fallback, so
these tests SCRIPT the parse layer (``_script_the_parse``) and keep asserting what
they were always about — the endpoint, the ledger stream, the context channels, and
the fail-closed render boundary. What a live model parses a phrasing to is the exam
sweep's measurement, not this file's.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.api.app import create_app
from tools.generate_erp_dataset import generate


def _script_the_parse(monkeypatch, table):
    """Make the ask ENDPOINT use a scripted parse layer. Everything downstream —
    dispatch, assembler, renderer, validator, ledger — stays real."""
    from tests.parse_doubles import ScriptedParser
    parser = ScriptedParser(table)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-never-used")
    monkeypatch.setattr("mre.modules.question_parser.QuestionParser",
                        lambda *a, **k: parser)
    return parser


def _data(resp, status=200):
    assert resp.status_code == status, (resp.status_code, resp.text)
    return resp.json()["data"]


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    root = tmp_path_factory.mktemp("askchain_data")
    sub_src = tmp_path_factory.mktemp("askchain_sub") / "clean_small"
    generate(sub_src, scenario="clean_small", seed=13)
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(sub_src)}))
    solve = _data(client.post(f"/submissions/{sub['submission_id']}/solve",
                              json={"time_limit": 20, "deterministic": True}), status=202)
    sid = _data(client.get(f"/runs/{solve['run_id']}"))["result"]["schedule_id"]
    doc = _data(client.get(f"/schedules/{sid}"))
    # a real order external ref to drive a voice-shaped question
    wo = None
    for a in doc["assignments"]:
        if a.get("work_orders"):
            wo = a["work_orders"][0]
            break
    return SimpleNamespace(client=client, sid=sid, root=Path(root), wo=wo)


@pytest.mark.slow
class TestAskChainLive:
    def test_voice_shaped_question_routes_and_renders(self, solved, monkeypatch):
        from tests.parse_doubles import Intent, parsed
        _script_the_parse(monkeypatch, {
            "are there any late orders?": parsed("", Intent.LATE_ORDERS)})
        res = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                       json={"question": "are there any late orders?"}))
        assert res["answer"]
        b = res["bundle"]
        assert b["route"] == "late-orders"
        assert b["source"] == "parse"
        assert b["resolved_question"] == "are there any late orders?"
        assert b["parse"]["intent"] == "late-orders"

    def test_ask_writes_a_ledger_row_in_its_own_stream(self, solved, monkeypatch):
        from tests.parse_doubles import Intent, parsed
        _script_the_parse(monkeypatch, {
            "what data problems exist?": parsed("", Intent.DATA_PROBLEMS)})
        _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                 json={"question": "what data problems exist?",
                                       "session_id": "live-1"}))
        ledger = solved.root / "ledger" / "questions.jsonl"
        assert ledger.exists(), "the ask wrote no ledger row"
        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert any(r["verbatim_question"] == "what data problems exist?" for r in rows)
        # the ledger is its OWN stream — not inside any run evidence dir
        assert "runs" not in str(ledger)

    def test_conversational_followup_resolves_live(self, solved, monkeypatch):
        from tests.parse_doubles import (
            FollowupKind, Intent, SubjectKind, parsed,
        )
        if not solved.wo:
            pytest.skip("no work_order external ref in this fixture")
        _script_the_parse(monkeypatch, {
            f"why is {solved.wo} late?": parsed("", Intent.LATE_ORDER,
                                                orders=(solved.wo,)),
            "and what about it?": parsed("", Intent.ORDER_SCHEDULE,
                                         pointed=(SubjectKind.ORDER,),
                                         followup_of=FollowupKind.DEEPEN),
        })
        # turn 1 establishes the subject
        r1 = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                      json={"question": f"why is {solved.wo} late?"}))
        # turn 2: an elliptical follow-up + history → resolved against the order
        r2 = _data(solved.client.post(f"/schedules/{solved.sid}/ask", json={
            "question": "and what about it?",
            "history": [{"question": f"why is {solved.wo} late?",
                         "order": solved.wo, "route": r1["bundle"]["route"]}],
        }))
        assert solved.wo in r2["bundle"]["resolved_question"]
        assert r2["bundle"]["resolved_question"] != "and what about it?"

    def test_unresolvable_ellipsis_asks_to_clarify(self, solved, monkeypatch):
        from tests.parse_doubles import Intent, SubjectKind, parsed
        _script_the_parse(monkeypatch, {
            "and what would fix it?": parsed("", Intent.LATE_ORDER,
                                             pointed=(SubjectKind.ORDER,))})
        res = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                       json={"question": "and what would fix it?"}))
        assert res["bundle"]["route"] == "CLARIFY"

    def test_meta_route_reads_the_ledger(self, solved, monkeypatch):
        from tests.parse_doubles import Intent, SubjectKind, parsed
        _script_the_parse(monkeypatch, {
            "and what would fix it?": parsed("", Intent.LATE_ORDER,
                                             pointed=(SubjectKind.ORDER,)),
            "what questions couldn't you answer recently?":
                parsed("", Intent.LEDGER_REFUSALS),
        })
        # seed a refusal-shaped ask, then ask the ledger about itself
        _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                 json={"question": "and what would fix it?"}))
        res = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                       json={"question": "what questions couldn't you answer recently?"}))
        assert res["bundle"]["route"] == "ledger-refusals"
        # the answer names at least the CLARIFY we just logged
        assert "CLARIFY" in res["answer"] or "couldn't" in res["answer"].lower()

    def test_dev_refusal_view_is_gated(self, solved, monkeypatch):
        monkeypatch.delenv("MRE_DEV", raising=False)
        r = solved.client.get("/ledger/refusals")
        assert r.status_code == 404
        monkeypatch.setenv("MRE_DEV", "1")
        data = _data(solved.client.get("/ledger/refusals"))
        assert "clusters" in data and "recent" in data


@pytest.mark.slow
class TestAskFailClosedWithRealKey:
    """The gap 4A.1b closed: a taxonomy-shaped question with a real ANTHROPIC_API_KEY
    set (so the interpreter AND the LLM renderer construct for real, and the DEV
    build's ``llm: true`` is honored) 500'd at RENDER time — ``_call_llm`` had no
    exception boundary. NO failure in the interpreter or LLM renderer path may ever
    surface as a 5xx; the contract is silent degradation to the template render.

    These drive the endpoint with a genuine (invalid) key and inject the three
    failure modes at the single call seam. All must return 200 + [rendered by:
    template]. The 4A.1 tests mocked the client, so this real path was never run.
    """

    _KEY = "sk-ant-invalid-DEADBEEF"

    def _ask(self, solved, question):
        return solved.client.post(f"/schedules/{solved.sid}/ask",
                                  json={"question": question, "llm": True})

    @staticmethod
    def _script(monkeypatch, table):
        return _script_the_parse(monkeypatch, table)

    @staticmethod
    def _late_orders(monkeypatch):
        from tests.parse_doubles import Intent, parsed
        return _script_the_parse(monkeypatch, {
            "are there any late orders?": parsed("", Intent.LATE_ORDERS),
            "what data problems exist?": parsed("", Intent.DATA_PROBLEMS)})

    def test_injected_auth_failure_returns_200_template(self, solved, monkeypatch):
        pytest.importorskip("anthropic")
        self._late_orders(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)  # real construction
        from mre.modules.renderers import LLMRenderer

        def _auth_raise(_self, _prompt):
            raise RuntimeError("401 authentication_error: invalid x-api-key")

        monkeypatch.setattr(LLMRenderer, "_call_llm", _auth_raise)
        res = self._ask(solved, "are there any late orders?")
        assert res.status_code == 200, res.text
        assert "[rendered by: template" in res.json()["data"]["answer"]

    def test_garbage_response_returns_200_template(self, solved, monkeypatch):
        pytest.importorskip("anthropic")
        self._late_orders(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.renderers import LLMRenderer

        # invented machine + number + timestamp: validation rejects, regen fails,
        # falls back to the template (no exception).
        monkeypatch.setattr(LLMRenderer, "_call_llm", lambda _s, _p: (
            "WO-9999 ran on M-ZZZ-99 and finished 4321 min late on 2099-01-01. "
            "[record: zzz]"))
        res = self._ask(solved, "are there any late orders?")
        assert res.status_code == 200, res.text
        assert "[rendered by: template" in res.json()["data"]["answer"]

    def test_raised_exception_returns_200_template(self, solved, monkeypatch):
        pytest.importorskip("anthropic")
        self._late_orders(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.renderers import LLMRenderer
        monkeypatch.setattr(LLMRenderer, "_call_llm",
                            lambda _s, _p: (_ for _ in ()).throw(ValueError("boom")))
        res = self._ask(solved, "what data problems exist?")
        assert res.status_code == 200, res.text
        assert "[rendered by: template" in res.json()["data"]["answer"]

    def test_better_schedule_question_refuses_not_a_listing(self, solved,
                                                            monkeypatch):
        """4A.1c issue 2: "is there a better schedule" produced prose (a schedule
        listing) instead of a refusal. The invariant is the SCHEDULE ROUTE: an
        optimality question must never be answered by listing the plan.
        Session 4A.5a: an optimality question is `unmatched` by the parse.
        Session 4A.5b: `unmatched` now has a second destination — the labeled
        synthesis tier — so the honest set is four, not three. What has not moved
        is the floor: never the schedule listing, and a REFUSAL still cites
        nothing (a synthesis answer may cite, because every citation on one has
        been verified against the record it names)."""
        from tests.parse_doubles import Intent, parsed
        self._script(monkeypatch, {
            "is there a better schedule": parsed("", Intent.UNMATCHED,
                                                 confidence=0.2)})
        res = self._ask_no_llm(solved, "is there a better schedule")
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["bundle"]["route"] in ("REFUSED", "NEAR_MISS", "CLARIFY",
                                           "synthesis")
        assert data["bundle"]["subject_type"] in ("unsupported", "near_miss",
                                                  "clarify", "synthesis")
        if data["bundle"]["route"] != "synthesis":
            assert "[record:" not in data["answer"], "a refusal must cite no records"

    def test_fabricated_citation_falls_back_to_template(self, solved, monkeypatch):
        """4A.1c issue 1: an LLM answer that cites a non-existent record id must be
        rejected (fabricated "[record: evidence_chain_001]") — validation catches
        it and the answer degrades to the deterministic template."""
        if not solved.wo:
            pytest.skip("no work_order external ref in this fixture")
        pytest.importorskip("anthropic")
        from tests.parse_doubles import Intent, parsed
        self._script(monkeypatch, {
            f"why is {solved.wo} late?": parsed("", Intent.LATE_ORDER,
                                                orders=(solved.wo,))})
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.renderers import LLMRenderer
        monkeypatch.setattr(LLMRenderer, "_call_llm", lambda _s, _p: (
            f"{solved.wo} finished 840 min late. [record: evidence_chain_001]"))
        res = solved.client.post(f"/schedules/{solved.sid}/ask",
                                 json={"question": f"why is {solved.wo} late?", "llm": True})
        assert res.status_code == 200, res.text
        answer = res.json()["data"]["answer"]
        assert "[rendered by: template" in answer
        # the fabricated citation is not presented as a live footnote (it may be
        # NAMED in the honest "validation failed" reason — that is the point)
        assert "[record: evidence_chain_001]" not in answer

    def _ask_no_llm(self, solved, question):
        return solved.client.post(f"/schedules/{solved.sid}/ask",
                                  json={"question": question})

    def test_a_broken_ai_stack_answers_honestly_never_a_5xx(self, solved,
                                                             monkeypatch):
        """The guarantee, restated for R-AI5. It used to be "a taxonomy-shaped
        question routes DETERMINISTICALLY even with the whole AI layer broken",
        because a keyword classifier ran first. R-AI5(2) removes that fallback on
        purpose: interpretation is the model's job, and a broken model means the
        product cannot know what was asked. What is unbreakable is the HONESTY —
        with both the parse layer and the renderer forcibly raising, the endpoint
        still returns 200 and a rendered answer, never a 5xx and never a guess."""
        pytest.importorskip("anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.question_parser import QuestionParser
        from mre.modules.renderers import LLMRenderer
        boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("AI stack down"))
        monkeypatch.setattr(QuestionParser, "parse", boom)
        monkeypatch.setattr(LLMRenderer, "_call_llm", boom)

        res = self._ask(solved, "are there any late orders?")
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["bundle"]["route"] == "REFUSED"        # honest: it cannot know
        assert data["bundle"]["source"] == "none"           # nothing authored it
        assert "[rendered by: template" in data["answer"]   # rendered despite it all
        assert "[record:" not in data["answer"]             # and it cites nothing
