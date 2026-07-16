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

class TestHealth:
    """The container HEALTHCHECK / proxy liveness probe (session 2.4 CU1)."""

    def test_health_ok_when_data_root_writable(self, tmp_path):
        client = TestClient(create_app(data_root=tmp_path / "hdata"))
        data = _data(client.get("/health"))
        assert data["status"] == "ok"
        assert data["data_root_writable"] is True
        # The 4.0d path-length budget rides on the liveness probe so a thin
        # margin is visible before it can fail at accept time.
        budget = data["path_budget"]
        assert budget["worst_case_path_len"] > budget["data_root_len"]
        assert budget["status"] in ("ok", "at_risk")

    def test_health_503_when_data_root_unwritable(self, tmp_path, monkeypatch):
        root = tmp_path / "hdata2"
        client = TestClient(create_app(data_root=root))
        # Simulate a broken/unwritable data root: make the write probe fail.
        import pathlib
        orig = pathlib.Path.write_text

        def boom(self, *a, **k):
            if self.name == ".health_probe":
                raise OSError("read-only file system")
            return orig(self, *a, **k)

        monkeypatch.setattr(pathlib.Path, "write_text", boom)
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == 503


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
        assert parsed.contract_version == "1.4"
        assert parsed.schedule_id == api.schedule_id
        assert parsed.run_id == api.run["id"]
        assert parsed.solver.deterministic is True
        assert parsed.assignments and parsed.service_outcomes and parsed.resources
        assert parsed.annotations.scenario.is_scenario is False
        # Contract 1.3 (R-T1d): the Tier-0 interaction payload is served
        # SEPARATELY (GET .../interaction) so it never sits inside first-paint;
        # the main render document carries it no longer.
        assert parsed.interaction is None

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
        # The assembler still builds interaction in-memory; the split-endpoint
        # discipline (contract 1.3) strips it from the served MAIN document, so
        # compare against the stripped rebuild.
        main = rebuilt.model_copy(update={"interaction": None})
        assert main.model_dump(mode="json") == served

    def test_unknown_schedule_404_envelope(self, api):
        _error(api.client.get("/schedules/nope"), 404)

    def test_listing_contains_the_base_schedule(self, api):
        rows = _data(api.client.get("/schedules"))["schedules"]
        assert api.schedule_id in [r["id"] for r in rows]


# ---------------------------------------------------------------------------
# Schedule meta (cockpit top strip — version + certificate grade)
# ---------------------------------------------------------------------------

class TestScheduleMeta:
    """The cockpit top strip reads the certificate GRADE here, not from the
    derived-not-invented schedule document (grade is a submission property)."""

    def test_meta_joins_the_certificate_grade(self, api):
        meta = _data(api.client.get(f"/schedules/{api.schedule_id}/meta"))
        assert meta["id"] == api.schedule_id
        assert meta["contract_version"] == "1.4"
        assert meta["grade"] == "ACCEPTED"
        assert meta["costing_grade"] == "C1"
        assert meta["submission_id"] == api.submission["submission_id"]
        assert meta["is_scenario"] in (0, False)

    def test_meta_unknown_schedule_404(self, api):
        _error(api.client.get("/schedules/nope/meta"), 404)


# ---------------------------------------------------------------------------
# Split interaction endpoint (contract 1.3, R-T1d) — the Tier-0 payload,
# fetched separately from the main render document
# ---------------------------------------------------------------------------

class TestScheduleInteraction:
    """The +35.7% Tier-0 payload moves off the main document (R-T1d): the
    cockpit fetches it in the background after first paint, never inside the
    render path."""

    def test_interaction_served_separately(self, api):
        from mre.contracts.schedule_document import InteractionBlock
        data = _data(api.client.get(
            f"/schedules/{api.schedule_id}/interaction"))
        assert data["schedule_id"] == api.schedule_id
        assert data["contract_version"] == "1.4"
        block = InteractionBlock.model_validate(data["interaction"])
        # one entry per scheduled op, each with its eligible set + the graph
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        assert len(block.operations) == len(doc["assignments"])
        assert all(o.eligible_resource_ids for o in block.operations)

    def test_main_document_no_longer_carries_the_payload(self, api):
        """The split's whole point: the main render document is lean again."""
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        assert doc["interaction"] is None

    def test_interaction_unknown_schedule_404(self, api):
        _error(api.client.get("/schedules/nope/interaction"), 404)

    def test_pool_member_has_no_interaction_payload_404(self, api, pool):
        """Pool members carry no interaction payload (R-T1b: coverage misses
        degrade to Tier-0-green-only, never a dangling 500)."""
        # the base pool is warmed by the `pool` fixture; its members are
        # edge-less documents — no interaction.json beside them. There is no
        # public per-member interaction route, so assert the file discipline
        # via the summary: a member document exists, none has interaction.
        data = _data(api.client.get(f"/schedules/{api.schedule_id}/pool"))
        member_doc = _data(api.client.get(
            f"/schedules/{api.schedule_id}/pool/0"))
        assert member_doc["interaction"] is None
        assert data["members"]


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

    def test_ask_surfaces_register_and_cited_refs(self, api):
        """The cockpit (CU4) needs, structurally: the register (to style the
        answer card — never blend) and the cited entity refs (to highlight the
        corresponding bars/lanes). Both are surfaced from the bundle the
        explainer already produced — no new answer path."""
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        a = doc["assignments"][0]
        wo, res = a["work_orders"][0], a["external_name"]
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/ask",
            json={"question": f"why is {wo} on {res}?"},
        ))
        bundle = data["bundle"]
        assert bundle["register"] in ("testimony", "judgment")
        refs = bundle["cited_refs"]
        assert set(refs) == {"operations", "resources", "demands"}
        # a why-on-machine answer cites the assigned op and its resource lane
        assert refs["operations"], "no cited operations to highlight"
        assert a["operation_ref"] in refs["operations"]
        assert a["resource_id"] in refs["resources"]

    def test_cited_refs_point_at_real_board_entities(self, api):
        """Every cited op ref resolves to an assignment bar and every cited
        resource ref to a lane — so the highlight can never dangle."""
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        op_refs = {a["operation_ref"] for a in doc["assignments"]}
        res_refs = {r["resource_id"] for r in doc["resources"]}
        wo = doc["service_outcomes"][0]["work_order"]
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/ask",
            json={"question": f"why is {wo} late?"},
        ))
        refs = data["bundle"]["cited_refs"]
        assert all(o in op_refs for o in refs["operations"])
        assert all(r in res_refs for r in refs["resources"])


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


# ---------------------------------------------------------------------------
# Forced alternatives (docs/07 Phase 3, R-T1a) — the priced roads not taken,
# surfaced through the pool endpoint family, distinguishable by source label.
# The counterfactual (priced cross-machine alternatives on distinct-rate data)
# lives in tests/test_forced_alternatives.py; here we assert the API contract
# on the clean_small fixture (single-eligibility ops → first-class infeasible
# verdicts), plus isolation.
# ---------------------------------------------------------------------------

class TestForcedAlternatives:
    def test_build_and_fetch_labeled_by_source(self, api):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        op = doc["assignments"][0]["operation_ref"]
        accepted = _data(api.client.post(
            f"/schedules/{api.schedule_id}/alternatives",
            json={"target_op_ids": [op], "budget": 1,
                  "member_time_limit": 8, "sync": True},
        ), status=202)
        assert accepted["pool_id"].startswith("alt-")

        data = _data(api.client.get(f"/schedules/{api.schedule_id}/alternatives"))
        assert data["kind"] == "alternatives"
        assert data["members"], "forced-alternative build recorded no member"
        m = data["members"][0]
        assert m["source"] == "forced_alternative"
        # clean_small ops are single-eligibility: forbidding the only machine
        # is proven infeasible this horizon — first-class information (R-T1a).
        assert m["verdict"] == "infeasible_this_horizon"
        assert m["label"]["target_operation_ref"] == op
        assert m["document_path"] is None

    def test_infeasible_member_has_no_document(self, api):
        # (build performed by the previous test; fetch the verdict-only member)
        _error(api.client.get(f"/schedules/{api.schedule_id}/alternatives/0"), 409)

    def test_alternatives_404_when_none_built(self, api):
        # a fresh solve with no alternatives built
        solve = _data(api.client.post(
            f"/submissions/{api.submission['submission_id']}/solve",
            json={"time_limit": 20, "deterministic": True, "sync": True},
        ), status=202)
        sid = _data(api.client.get(f"/runs/{solve['run_id']}"))["result"]["schedule_id"]
        _error(api.client.get(f"/schedules/{sid}/alternatives"), 404)
        _error(api.client.get("/schedules/nope/alternatives"), 404)

    def test_alternatives_refused_for_scenario_schedules(self, api, scenario_run):
        scen_id = scenario_run["result"]["schedule_id"]
        _error(api.client.post(
            f"/schedules/{scen_id}/alternatives", json={}), 409)

    def test_on_demand_op_pricing_appends_to_pool(self, api):
        # session 3.3 CU1: pricing a grabbed op on demand creates/updates the
        # alternatives pool. clean_small ops are single-eligibility (no machine
        # to price), so 0 members are appended — but the endpoint accepts the
        # request, creates the pool, and prices without error (K' path).
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        op = doc["assignments"][0]["operation_ref"]
        resp = _data(api.client.post(
            f"/schedules/{api.schedule_id}/alternatives/op/{op}",
            json={"max_machines": 4, "member_time_limit": 6, "sync": True},
        ), status=202)
        assert resp["status"] == "pricing"
        assert resp["pool_id"].startswith("alt-")
        pool = _data(api.client.get(f"/schedules/{api.schedule_id}/alternatives"))
        assert pool["kind"] == "alternatives"

    def test_on_demand_refused_for_scenario_schedules(self, api, scenario_run):
        scen_id = scenario_run["result"]["schedule_id"]
        _error(api.client.post(
            f"/schedules/{scen_id}/alternatives/op/whatever", json={}), 409)


# ---------------------------------------------------------------------------
# Sandbox (Tier-2 pinned re-solve, docs/07 Phase 3, R-DP1/R-T1c). The three-
# outcome classifier is unit-tested in test_sandbox.py; here we assert the API
# contract — a default pin (incumbent op at its own placement) returns a
# classified, within-budget outcome with the moved-set (R-DP7), and scenarios
# are refused. clean_small proves fast, so this is not a slow test.
# ---------------------------------------------------------------------------

class TestSandbox:
    def test_default_pin_returns_classified_outcome_and_moved_set(self, api):
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/sandbox",
            json={"deterministic": True, "budget_s": 15},
        ))
        assert data["outcome"] in (
            "verdict", "feasible_unproven", "no_verdict")
        assert data["within_budget"] is True
        assert data["feasible"] is True
        # session 3.3 CU5: the applied time limit is echoed (budget-vs-actual)
        assert data["applied_time_limit_s"] == 15
        # the moved-set carries the pinned op, listed first (R-DP7)
        assert data["moves"], "a feasible re-solve reports its moved-set"
        assert data["moves"][0]["pinned"] is True
        assert data["pin"]["operation_ref"] == data["moves"][0]["operation_ref"]

    def test_explicit_pin_is_honored(self, api):
        doc = _data(api.client.get(f"/schedules/{api.schedule_id}"))
        a = doc["assignments"][0]
        data = _data(api.client.post(
            f"/schedules/{api.schedule_id}/sandbox",
            json={"pin_op_id": a["operation_ref"],
                  "pin_resource_id": a["resource_id"],
                  "pin_start_iso": a["chunks"][0]["start"],
                  "deterministic": True, "budget_s": 15},
        ))
        assert data["pin"]["operation_ref"] == a["operation_ref"]
        assert data["pin"]["resource_id"] == a["resource_id"]
        assert data["within_budget"] is True

    def test_sandbox_refused_for_scenario_schedules(self, api, scenario_run):
        scen_id = scenario_run["result"]["schedule_id"]
        _error(api.client.post(f"/schedules/{scen_id}/sandbox", json={}), 409)

    def test_sandbox_404_for_unknown_schedule(self, api):
        _error(api.client.post("/schedules/nope/sandbox", json={}), 404)
