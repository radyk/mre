"""API endpoint tests (docs/07 Phase 2, session 2.1).

TestClient against a clean_small generated submission. One real solve per
module (the fixture), reused by every read test. Starlette's TestClient
executes background tasks before returning, so 202-accepted runs are
complete when the next request is made.

Guardrail coverage written from the session rules:
- REJECTED submissions return deficiencies and never solve;
- what-if scenarios never appear in the default GET /schedules listing;
- deterministic flag plumbs through to the solver (M6 RunContext config);
- the persisted document round-trips: rebuilt from the run == served.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.api.app import create_app
from mre.contracts.schedule_document import ScheduleDocument
from mre.modules.schedule_assembler import build_document_from_run
from tools.generate_erp_dataset import generate


def _data(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["api_version"] == "1"
    return body["data"]


def _error(resp, status):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["api_version"] == "1"
    assert body["error"]["code"] == status
    return body["error"]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    """Submission intake + one deterministic solve, shared by the module."""
    root = tmp_path_factory.mktemp("api_data")
    sub_src = tmp_path_factory.mktemp("sub") / "clean_small"
    generate(sub_src, scenario="clean_small", seed=7)

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
        client=client, root=root, submission=sub, run=run,
        schedule_id=run["result"]["schedule_id"],
    )


# ---------------------------------------------------------------------------
# Submission + certificate
# ---------------------------------------------------------------------------

class TestSubmissionIntake:
    def test_accepted_submission_reports_grades(self, api):
        assert api.submission["grade"] == "ACCEPTED"
        assert api.submission["costing_grade"] == "C1"
        assert api.submission["deficiencies"] == []

    def test_certificate_endpoint(self, api):
        sid = api.submission["submission_id"]
        data = _data(api.client.get(f"/submissions/{sid}/certificate"))
        assert data["certificate"]["grade"] == "ACCEPTED"
        assert Path(data["markdown_ref"]).exists()

    def test_multipart_upload_reaches_the_gate(self, api, tmp_path):
        src = tmp_path / "multi"
        generate(src, scenario="clean_small", seed=8)
        files = [
            ("files", (p.name, p.read_bytes()))
            for p in sorted(src.iterdir()) if p.is_file()
        ]
        data = _data(api.client.post("/submissions", files=files))
        assert data["grade"] == "ACCEPTED"

    def test_bad_path_is_a_client_error(self, api):
        _error(api.client.post(
            "/submissions", json={"path": "does/not/exist"}), 400)


class TestRejectedSubmission:
    def test_deficiencies_returned_and_solve_refused(self, api, tmp_path):
        src = tmp_path / "rejected"
        generate(src, scenario="rejected", seed=1)
        data = _data(api.client.post("/submissions", json={"path": str(src)}))
        assert data["grade"] == "REJECTED"
        assert data["deficiencies"], "REJECTED must carry its deficiency list"

        err = _error(api.client.post(
            f"/submissions/{data['submission_id']}/solve", json={}), 409)
        assert "REJECTED" in err["message"]


# ---------------------------------------------------------------------------
# Runs + schedule document
# ---------------------------------------------------------------------------

class TestSolveRun:
    def test_run_telemetry(self, api):
        assert api.run["kind"] == "solve"
        assert api.run["result"]["solver"]["status"] in ("OPTIMAL", "FEASIBLE")
        assert api.run["finished_at"] is not None

    def test_unknown_run_404_envelope(self, api):
        _error(api.client.get("/runs/nope"), 404)

    def test_deterministic_flag_plumbs_to_solver(self, api):
        """The M6 RunContext config in the run's own evidence must show the
        pinning — evidence, not the request echo, is the proof."""
        runs_dir = Path(api.run["out_dir"]) / "runs"
        m6_cfgs = []
        for f in runs_dir.glob("*.jsonl"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if (rec.get("record_type") == "run_context_open"
                        and rec.get("module") == "M6"):
                    m6_cfgs.append(rec["config_snapshot"])
        assert m6_cfgs, "solve run left no M6 evidence"
        assert m6_cfgs[-1]["num_search_workers"] == 1
        assert m6_cfgs[-1]["random_seed"] is not None


class TestScheduleDocument:
    def test_document_validates_against_contract(self, api):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        parsed = ScheduleDocument.model_validate(doc)
        assert parsed.contract_version == "1.1"
        assert parsed.schedule_id == api.schedule_id
        assert parsed.run_id == api.run["id"]
        assert parsed.solver.deterministic is True
        assert parsed.assignments and parsed.service_outcomes and parsed.resources
        assert parsed.annotations.scenario.is_scenario is False

    def test_every_assignment_has_chunks_and_work_orders(self, api):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        for a in doc["assignments"]:
            assert a["chunks"], a
            assert a["work_orders"], a
            assert a["decision_ref"], a

    def test_round_trip_rebuild_equals_served_document(self, api):
        """Document rebuilt from the persisted run == the one built at
        extraction time (the contract's round-trip rule)."""
        served = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        rebuilt = build_document_from_run(
            Path(api.run["out_dir"]), api.run["snapshot_id"], api.run["id"],
        )
        assert rebuilt.model_dump(mode="json") == served

    def test_unknown_schedule_404_envelope(self, api):
        _error(api.client.get("/schedules/nope"), 404)

    def test_listing_contains_the_base_schedule(self, api):
        rows = _data(api.client.get("/schedules"))["schedules"]
        assert api.schedule_id in [r["id"] for r in rows]


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------

class TestAsk:
    def test_ask_routes_through_the_explainer(self, api):
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/ask",
            json={"question": "summarize"},
        ))
        assert data["answer"].strip()
        assert data["bundle"]["snapshot_id"]

    def test_ask_why_late_names_a_work_order(self, api):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        wo = doc["service_outcomes"][0]["work_order"]
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/ask",
            json={"question": f"Why is {wo} late?"},
        ))
        assert data["answer"].strip()

    def test_ask_unknown_schedule_404(self, api):
        _error(api.client.post("/schedules/nope/ask",
                               json={"question": "summarize"}), 404)


# ---------------------------------------------------------------------------
# What-if
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scenario_run(api):
    doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
    wos = sorted({wo for a in doc["assignments"] for wo in a["work_orders"]})
    accepted = _data(api.client.post(
        f"/schedules/{api.schedule_id}/whatif",
        json={"modifications": [
            {"type": "suppress_merge", "demand_refs": wos[:2]},
        ]},
    ), status=202)
    run = _data(api.client.get(f"/runs/{accepted['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return run


class TestWhatIf:
    def test_whatif_produces_diff_and_scenario_document(self, api, scenario_run):
        diff = scenario_run["result"]["diff"]
        assert diff["cost_delta"]["_decomp_ok"] is True
        scen_doc = _data(api.client.get(
            f"/schedules/{scenario_run['result']['schedule_id']}"))
        parsed = ScheduleDocument.model_validate(scen_doc)
        assert parsed.annotations.scenario.is_scenario is True
        assert parsed.annotations.scenario.parent_schedule_id == api.schedule_id

    def test_scenario_excluded_from_default_listing(self, api, scenario_run):
        scen_id = scenario_run["result"]["schedule_id"]
        default_ids = [r["id"] for r in
                       _data(api.client.get("/schedules"))["schedules"]]
        assert scen_id not in default_ids
        opted_in = [r["id"] for r in
                    _data(api.client.get(
                        "/schedules?include_scenarios=true"))["schedules"]]
        assert scen_id in opted_in

    def test_scenario_run_is_run_scoped(self, api, scenario_run):
        """The scenario's snapshot and evidence live in ITS run dir, not the
        base run's (structural run-scoping)."""
        scen_out = Path(scenario_run["out_dir"])
        assert (scen_out / "scenario_runs").exists()
        base_snaps = Path(api.run["out_dir"]) / "snapshots"
        assert not any("--scenario-" in p.name for p in base_snaps.iterdir())

    def test_whatif_from_scenario_refused(self, api, scenario_run):
        scen_id = scenario_run["result"]["schedule_id"]
        _error(api.client.post(
            f"/schedules/{scen_id}/whatif",
            json={"modifications": [
                {"type": "set_cost_weight",
                 "path": "tardiness_weights.base_weight", "value": 2.0},
            ]}), 409)

    def test_unknown_modification_type_400(self, api):
        _error(api.client.post(
            f"/schedules/{api.schedule_id}/whatif",
            json={"modifications": [{"type": "teleport_orders"}]}), 400)

    def test_empty_modifications_400(self, api):
        _error(api.client.post(
            f"/schedules/{api.schedule_id}/whatif",
            json={"modifications": []}), 400)


# ---------------------------------------------------------------------------
# Solution pool (docs/07 Phase 2)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pool(api, scenario_run):
    """Warm a small pool for the base schedule (after the scenario tests'
    schedule exists, proving isolation both ways)."""
    accepted = _data(api.client.post(
        f"/schedules/{api.schedule_id}/pool",
        json={"k": 3, "member_time_limit": 10, "sync": True},
    ), status=202)
    return accepted["pool_id"]


class TestSolutionPool:
    def test_pool_summary_ready_with_measured_diversity(self, api, pool):
        data = _data(api.client.get(f"/schedules/{api.schedule_id}/pool"))
        assert data["id"] == pool
        assert data["status"] == "ready", data.get("error")
        assert data["members"], "pool warmed but has no members"
        assert data["summary"]["diversity"]["mean_hamming_from_incumbent"] >= 1
        assert data["summary"]["diversity"]["ops_with_alternative_positions"] >= 1

    def test_member_document_is_contract_11_and_marked(self, api, pool):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}/pool/0"))
        parsed = ScheduleDocument.model_validate(doc)  # cost decomposition dies here if broken
        assert parsed.annotations.pool is not None
        assert parsed.annotations.pool.is_pool_member is True
        assert parsed.annotations.pool.pool_id == pool
        assert parsed.annotations.pool.base_schedule_id == api.schedule_id
        assert parsed.annotations.pool.member_index == 0

    def test_members_within_objective_tolerance(self, api, pool):
        data = _data(api.client.get(f"/schedules/{api.schedule_id}/pool"))
        for m in data["members"]:
            if m["objective_delta_pct"] is not None:
                assert m["objective_delta_pct"] <= 10.0 + 1e-6

    def test_pool_members_never_in_schedule_listings(self, api, pool):
        """Structural isolation: members live in pool tables, so even the
        opt-in scenario listing cannot contain them."""
        rows = _data(api.client.get(
            "/schedules?include_scenarios=true"))["schedules"]
        data = _data(api.client.get(f"/schedules/{api.schedule_id}/pool"))
        member_docs = {m["document_path"] for m in data["members"]}
        assert member_docs  # sanity
        assert not member_docs & {r["document_path"] for r in rows}

    def test_pool_refused_for_scenario_schedules(self, api, scenario_run, pool):
        scen_id = scenario_run["result"]["schedule_id"]
        _error(api.client.post(f"/schedules/{scen_id}/pool", json={}), 409)

    def test_pool_404s(self, api):
        _error(api.client.get("/schedules/nope/pool"), 404)
        _error(api.client.get(f"/schedules/{api.schedule_id}/pool/99"), 404)

    def test_solve_with_pool_flag_auto_warms(self, api):
        """pool: true on the solve request warms the pool in the same
        background task, strictly after the schedule registers."""
        solve = _data(api.client.post(
            f"/submissions/{api.submission['submission_id']}/solve",
            json={"time_limit": 20, "deterministic": True,
                  "sync": True, "pool": True},
        ), status=202)
        run = _data(api.client.get(f"/runs/{solve['run_id']}"))
        assert run["status"] == "succeeded", run.get("error")
        data = _data(api.client.get(
            f"/schedules/{run['result']['schedule_id']}/pool"))
        assert data["status"] == "ready"
        assert data["members"]
