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
