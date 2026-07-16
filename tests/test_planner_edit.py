"""Accepted cockpit edits become real schedule versions (docs/07 Phase 3 CU1;
R-DP2 "accept CREATES, never overwrites"; R-DP7; docs/02 planner_edit Decision).

The spec, as executable acceptance criteria:
  * accept mints a NEW proposed version whose parent is the base; the base is
    NEVER mutated (still proposed, still listed, same document bytes);
  * the accept records exactly one ``planner_edit`` Decision — basis=observed,
    authority mandatory, subjects naming the pinned op + resource;
  * publish is a SECOND, explicit act: proposed → published, superseding the
    prior version and invalidating its pools;
  * sequential edits before publish work (an edit on the proposed version
    re-enters the accept path against it);
  * a published/superseded version cannot be re-published.

These run one real deterministic solve (module fixture) + a pin re-solve per
accept, so they are marked slow.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.api.app import create_app
from tools.generate_erp_dataset import generate

pytestmark = pytest.mark.slow

SNAP = "snap-edit"


def _data(resp, status=200):
    assert resp.status_code == status, (resp.status_code, resp.text)
    body = resp.json()
    assert "data" in body, body
    return body["data"]


def _error(resp, status):
    assert resp.status_code == status, (resp.status_code, resp.text)
    return resp.json()["error"]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    root = tmp_path_factory.mktemp("edit_api_data")
    sub_src = tmp_path_factory.mktemp("edit_sub") / "clean_small"
    generate(sub_src, scenario="clean_small", seed=11)

    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(sub_src)}))
    assert sub["grade"] == "ACCEPTED"
    solve = _data(client.post(
        f"/submissions/{sub['submission_id']}/solve",
        json={"time_limit": 20, "deterministic": True},
    ), status=202)
    run = _data(client.get(f"/runs/{solve['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return SimpleNamespace(
        client=client, root=root, submission=sub,
        schedule_id=run["result"]["schedule_id"],
    )


@pytest.fixture
def fresh_base(api):
    """A NEW deterministic solve of the shared submission → a fresh proposed base
    schedule id. Tests that PUBLISH need this: publish supersedes the base, which
    would poison the module-shared schedule for later tests."""
    solve = _data(api.client.post(
        f"/submissions/{api.submission['submission_id']}/solve",
        json={"time_limit": 20, "deterministic": True},
    ), status=202)
    run = _data(api.client.get(f"/runs/{solve['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return run["result"]["schedule_id"]


def _pin_from_incumbent(doc: dict) -> dict:
    """Pin an op at its OWN incumbent placement — a trivially feasible edit that
    exercises the whole accept mechanism (mint version + Decision + publish)
    without depending on a cross-machine move existing in the fixture."""
    a = doc["assignments"][0]
    return {"pin_op_id": a["operation_ref"], "pin_resource_id": a["resource_id"],
            "pin_start_iso": a["chunks"][0]["start"], "authority": "dev-planner"}


class TestAcceptCreatesNeverOverwrites:
    def test_accept_mints_a_new_proposed_version_leaving_base_untouched(self, api):
        base_doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        base_bytes = json.dumps(base_doc, sort_keys=True)
        pin = _pin_from_incumbent(base_doc)

        acc = _data(api.client.post(
            f"/schedules/{api.schedule_id}/accept", json=pin), status=201)
        new_id = acc["schedule_id"]

        assert new_id != api.schedule_id
        assert acc["parent_schedule_id"] == api.schedule_id
        assert acc["status"] == "proposed"
        assert acc["decision"]["authority"] == "dev-planner"
        assert acc["decision"]["record_id"]

        # the base is UNCHANGED: still proposed, byte-identical document
        base_after = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        assert base_after["status"] == "proposed"
        assert json.dumps(base_after, sort_keys=True) == base_bytes

        # the new version is a real, listable proposed schedule with assignments
        new_doc = _data(api.client.get(f"/schedules/{new_id}"))
        assert new_doc["status"] == "proposed"
        assert new_doc["annotations"]["scenario"]["is_scenario"] is False
        assert new_doc["annotations"]["scenario"]["parent_schedule_id"] == api.schedule_id
        assert new_doc["assignments"], "the accepted version carries a full schedule"
        # it keeps a Tier-0 interaction payload so the rebound board stays draggable
        assert _data(api.client.get(f"/schedules/{new_id}/interaction"))["interaction"]

    def test_new_version_appears_in_the_listing_and_is_not_a_scenario(self, api):
        base_doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        acc = _data(api.client.post(
            f"/schedules/{api.schedule_id}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        rows = _data(api.client.get("/schedules"))["schedules"]
        ids = {r["id"] for r in rows}
        assert acc["schedule_id"] in ids and api.schedule_id in ids

    def test_the_planner_edit_decision_is_recorded_with_authority(self, api):
        base_doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        acc = _data(api.client.post(
            f"/schedules/{api.schedule_id}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        new_id = acc["schedule_id"]
        run_row = _find_run_for_schedule(api.root, new_id)
        decisions = _decisions_in_run(Path(run_row))
        edits = [d for d in decisions if d["decision_type"] == "planner_edit"]
        assert len(edits) == 1, "exactly one planner_edit Decision per accept"
        d = edits[0]
        assert d["basis"] == "observed"          # a human command, not reconstructed
        assert d["authority"] == "dev-planner"   # mandatory on a planner_edit
        subj_types = {s["entity_type"] for s in d["subjects"]}
        assert {"operation", "resource"} <= subj_types


class TestPublish:
    def test_publish_supersedes_the_prior_version_and_invalidates_its_pools(self, api, fresh_base):
        base_doc = _data(api.client.get(f"/schedules/{fresh_base}"))
        # warm a pool on the base so we can prove publish invalidates it
        _data(api.client.post(f"/schedules/{fresh_base}/pool",
                              json={"k": 2, "sync": True}), status=202)
        acc = _data(api.client.post(
            f"/schedules/{fresh_base}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        new_id = acc["schedule_id"]

        pub = _data(api.client.post(f"/schedules/{new_id}/publish"))
        assert pub["status"] == "published"
        assert fresh_base in pub["superseded"]

        # the registry is the live-lifecycle source of truth (the served document's
        # status is frozen at assembly; /meta reflects the current state, which is
        # what the cockpit strip reads).
        assert _data(api.client.get(f"/schedules/{new_id}/meta"))["status"] == "published"
        base_meta = _data(api.client.get(f"/schedules/{fresh_base}/meta"))
        assert base_meta["status"] == "superseded"
        pool = _data(api.client.get(f"/schedules/{fresh_base}/pool"))
        assert pool["status"] == "invalidated"

    def test_superseded_meta_carries_its_live_successor(self, api, fresh_base):
        """A superseded version's /meta names the live successor (session 3.8
        CU3), so a deep link can offer "view current" instead of a raw error."""
        base_doc = _data(api.client.get(f"/schedules/{fresh_base}"))
        acc = _data(api.client.post(
            f"/schedules/{fresh_base}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        new_id = acc["schedule_id"]
        _data(api.client.post(f"/schedules/{new_id}/publish"))

        base_meta = _data(api.client.get(f"/schedules/{fresh_base}/meta"))
        assert base_meta["status"] == "superseded"
        assert base_meta["successor_id"] == new_id
        # a live (non-superseded) version carries no successor pointer
        assert "successor_id" not in _data(api.client.get(f"/schedules/{new_id}/meta"))

    def test_cannot_publish_twice_or_publish_superseded(self, api, fresh_base):
        base_doc = _data(api.client.get(f"/schedules/{fresh_base}"))
        acc = _data(api.client.post(
            f"/schedules/{fresh_base}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        new_id = acc["schedule_id"]
        _data(api.client.post(f"/schedules/{new_id}/publish"))
        _error(api.client.post(f"/schedules/{new_id}/publish"), 409)      # already published
        # the superseded base cannot be published either
        _error(api.client.post(f"/schedules/{fresh_base}/publish"), 409)


class TestSequentialEdits:
    def test_edit_on_a_proposed_version_re_enters_the_accept_path(self, api):
        base_doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        acc1 = _data(api.client.post(
            f"/schedules/{api.schedule_id}/accept",
            json=_pin_from_incumbent(base_doc)), status=201)
        v1 = acc1["schedule_id"]

        v1_doc = _data(api.client.get(f"/schedules/{v1}"))
        acc2 = _data(api.client.post(
            f"/schedules/{v1}/accept", json=_pin_from_incumbent(v1_doc)), status=201)
        v2 = acc2["schedule_id"]
        assert v2 not in (v1, api.schedule_id)
        assert acc2["parent_schedule_id"] == v1
        assert _data(api.client.get(f"/schedules/{v2}"))["status"] == "proposed"


# ---------------------------------------------------------------------------
# Evidence readers (the store is filesystem truth; the registry only indexes)
# ---------------------------------------------------------------------------

def _find_run_for_schedule(root: Path, schedule_id: str) -> str:
    import sqlite3
    con = sqlite3.connect(Path(root) / "registry.sqlite")
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT r.out_dir FROM schedules s JOIN runs r ON r.id=s.run_id "
                      "WHERE s.id=?", (schedule_id,)).fetchone()
    con.close()
    return row["out_dir"]


def _decisions_in_run(out_dir: Path) -> list[dict]:
    decisions: list[dict] = []
    runs_dir = Path(out_dir) / "runs"
    for f in sorted(runs_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") == "decision":
                decisions.append(rec)
    return decisions
