"""The ask chain, live through the API (Session 4A.1, R-AI1).

One deterministic solve, then the ask surface exercised end to end: a natural
(voice-shaped) question routes, the answer renders, and a question-ledger row is
written to its own stream under the data root (never inside a run's evidence).
A conversational chain resolves an ellipsis live; the DEV-gated refusal view is
gated. Deterministic-only (no ANTHROPIC_API_KEY): the interpreter is off, so the
chain proves the wrapper's zero-regression + logging + context path.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.api.app import create_app
from tools.generate_erp_dataset import generate


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
    def test_voice_shaped_question_routes_and_renders(self, solved):
        res = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                       json={"question": "are there any late orders?"}))
        assert res["answer"]
        b = res["bundle"]
        assert b["route"] == "late-orders"
        assert b["source"] == "deterministic"
        assert b["resolved_question"] == "are there any late orders?"

    def test_ask_writes_a_ledger_row_in_its_own_stream(self, solved):
        _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                 json={"question": "what data problems exist?",
                                       "session_id": "live-1"}))
        ledger = solved.root / "ledger" / "questions.jsonl"
        assert ledger.exists(), "the ask wrote no ledger row"
        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert any(r["verbatim_question"] == "what data problems exist?" for r in rows)
        # the ledger is its OWN stream — not inside any run evidence dir
        assert "runs" not in str(ledger)

    def test_conversational_followup_resolves_live(self, solved):
        if not solved.wo:
            pytest.skip("no work_order external ref in this fixture")
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

    def test_unresolvable_ellipsis_asks_to_clarify(self, solved):
        res = _data(solved.client.post(f"/schedules/{solved.sid}/ask",
                                       json={"question": "and what would fix it?"}))
        assert res["bundle"]["route"] == "CLARIFY"

    def test_meta_route_reads_the_ledger(self, solved):
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

    def test_injected_auth_failure_returns_200_template(self, solved, monkeypatch):
        pytest.importorskip("anthropic")
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
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.renderers import LLMRenderer
        monkeypatch.setattr(LLMRenderer, "_call_llm",
                            lambda _s, _p: (_ for _ in ()).throw(ValueError("boom")))
        res = self._ask(solved, "what data problems exist?")
        assert res.status_code == 200, res.text
        assert "[rendered by: template" in res.json()["data"]["answer"]

    def test_taxonomy_question_is_unbreakable_by_the_whole_ai_stack(self, solved, monkeypatch):
        """CU3 — the ordering guarantee: a taxonomy-shaped question routes and
        renders deterministically with the ENTIRE AI layer forcibly broken (both
        the interpreter and the renderer monkeypatched to raise). The deterministic
        route must be reached (classify fires before any LLM code can throw) and
        the answer must render (template)."""
        pytest.importorskip("anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._KEY)
        from mre.modules.interpreter import Interpreter
        from mre.modules.renderers import LLMRenderer
        boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("AI stack down"))
        monkeypatch.setattr(Interpreter, "interpret", boom)
        monkeypatch.setattr(LLMRenderer, "_call_llm", boom)

        res = self._ask(solved, "are there any late orders?")
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["bundle"]["route"] == "late-orders"          # deterministic route reached
        assert data["bundle"]["source"] == "deterministic"        # interpreter never authored it
        assert "[rendered by: template" in data["answer"]         # rendered despite broken LLM
