"""The sandbox/edit question domain (docs/07 Phase 3 CU2). The demo's closing
beat — "summarize what I changed and what it cost" — plus the cost-delta
decomposition ("why does this move cost N"), routed over the planner_edit
Decisions an accepted edit records. No new answer path: the Decision carries the
decomposed cost delta + moved-set as self-contained evidence (docs/02 §4.4).

The routing (which trigger → which register) is unit-tested WITHOUT a solve; the
end-to-end (accept → ask the new version) rides one deterministic solve.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.api.app import create_app
from tools.generate_erp_dataset import generate


def _data(resp, status=200):
    assert resp.status_code == status, (resp.status_code, resp.text)
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Routing — the triggers land in the right assembler (no solve)
# ---------------------------------------------------------------------------

class TestEditRouting:
    def _explainer(self):
        from mre.modules.explainer import Explainer

        class _Store:
            def load_snapshot(self, _):
                raise FileNotFoundError   # certificate-only mode: no snapshot

        class _Index:
            _all_evidence: list = []
            def runs(self): return []
            def all_findings(self): return []
        return Explainer(_Store(), _Index(), snapshot_id="snap-x")

    def test_summarize_my_changes_routes_to_the_edits_domain(self):
        ex = self._explainer()
        for q in ("summarize what I changed", "what did I change today",
                  "summarize my edits this session"):
            b = ex.answer(q)
            assert b.subject_type == "edits", q

    def test_cost_questions_route_to_edit_cost(self):
        ex = self._explainer()
        for q in ("why does this move cost 261", "what did that cost",
                  "why is this edit so expensive"):
            b = ex.answer(q)
            # no edits recorded → an honest refusal (unsupported), never a guess
            assert b.subject_type in ("edit_cost", "unsupported"), q

    def test_edit_cost_refuses_honestly_with_no_edits(self):
        ex = self._explainer()
        b = ex.answer("why does this move cost 261")
        assert b.subject_type == "unsupported"   # the records can't support it


# ---------------------------------------------------------------------------
# End-to-end — accept an edit, then ask the new version (slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def edited(tmp_path_factory):
    root = tmp_path_factory.mktemp("editq_data")
    sub_src = tmp_path_factory.mktemp("editq_sub") / "clean_small"
    generate(sub_src, scenario="clean_small", seed=13)
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(sub_src)}))
    solve = _data(client.post(f"/submissions/{sub['submission_id']}/solve",
                              json={"time_limit": 20, "deterministic": True}), status=202)
    base_id = _data(client.get(f"/runs/{solve['run_id']}"))["result"]["schedule_id"]
    base_doc = _data(client.get(f"/schedules/{base_id}"))
    a = base_doc["assignments"][0]
    acc = _data(client.post(f"/schedules/{base_id}/accept", json={
        "pin_op_id": a["operation_ref"], "pin_resource_id": a["resource_id"],
        "pin_start_iso": a["chunks"][0]["start"], "authority": "daryn",
    }), status=201)
    return SimpleNamespace(client=client, base_id=base_id, new_id=acc["schedule_id"])


@pytest.mark.slow
class TestEditDomainEndToEnd:
    def test_summarize_changes_names_the_edit_and_its_cost(self, edited):
        res = _data(edited.client.post(f"/schedules/{edited.new_id}/ask",
                                       json={"question": "summarize what I changed and what it cost"}))
        ans = res["answer"]
        assert "1 edit" in ans.lower() or "accepted 1" in ans.lower()
        assert "daryn" in ans.lower()          # the authority is named
        assert res["bundle"]["register"] == "testimony"

    def test_cost_question_decomposes_the_delta(self, edited):
        res = _data(edited.client.post(f"/schedules/{edited.new_id}/ask",
                                       json={"question": "why does this edit cost that much"}))
        ans = res["answer"].lower()
        assert "production" in ans and "setup" in ans and "tardiness" in ans

    def test_base_version_has_no_edits_to_summarize(self, edited):
        # the base carries no planner_edit Decision — the domain refuses honestly
        res = _data(edited.client.post(f"/schedules/{edited.base_id}/ask",
                                       json={"question": "summarize what I changed"}))
        assert "no edits" in res["answer"].lower()
