"""Accepted placements are STANDING COMMITMENTS (docs/04 R-DP8).

The live specimen: a published edit was reverted by the NEXT edit's re-solve —
the delta card honestly listed the reverted op as a "consequence." An accepted
edit's pin must persist in the lineage as a hard constraint, compiled into every
subsequent sandbox/accept/scenario solve, so a decision the planner already made
is never silently undone.

This module holds:
  * fast unit tests for the shared ``standing_pins`` seam (pin accessors, lineage
    composition, structural moved-set exclusion, conflict detection) and the
    registry's cumulative-pins persistence — no solver;
  * the CU3 regression proper (slow, end-to-end on ``multi_route_distinct``): a
    two-edit chain where A is a cost-neutral cross-machine move the optimizer
    would otherwise revert — assert A's placement is unchanged in B's version AND
    A's op appears in no moved-set, and refuse a drop that conflicts with a
    standing commitment.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from mre.modules import standing_pins as sp


# ---------------------------------------------------------------------------
# Fast unit tests — the shared seam, no solver
# ---------------------------------------------------------------------------

class _FakeModel:
    def __init__(self): self.constraints = []
    def add(self, c): self.constraints.append(c); return c


class _FakeVar:
    """Stands in for an ortools IntVar/BoolVar: == returns a recordable token."""
    def __init__(self, name): self.name = name
    def __eq__(self, other): return (self.name, "==", other)
    def __hash__(self): return hash(self.name)


def _fake_var_map(op_starts, op_assign, durations=None):
    return SimpleNamespace(
        op_start={o: _FakeVar(f"s_{o}") for o in op_starts},
        op_assign={o: {r: _FakeVar(f"a_{o}_{r}") for r in rs}
                   for o, rs in op_assign.items()},
        op_durations=durations or {},
    )


class TestPinAccessors:
    def test_reads_both_record_shapes(self):
        canonical = {"operation_ref": "op1", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"}
        request = {"pin_op_id": "op1", "pin_resource_id": "r1", "pin_start_iso": "2026-01-05T00:00:00+00:00"}
        for p in (canonical, request):
            assert sp.pin_op_id(p) == "op1"
            assert sp.pin_resource_id(p) == "r1"
            assert sp.pin_start_iso(p) == "2026-01-05T00:00:00+00:00"

    def test_start_minutes_uses_the_canonical_grid(self):
        from datetime import datetime, timezone
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        assert sp.start_minutes("2026-01-05T02:30:00+00:00", h0) == 150


class TestComposeLineage:
    def test_a_fresh_op_appends(self):
        base = [{"operation_ref": "opA", "resource_id": "r1", "start": "s1"}]
        out = sp.compose_lineage_pins(base, {"operation_ref": "opB", "resource_id": "r2", "start": "s2"})
        assert [p["operation_ref"] for p in out] == ["opA", "opB"]

    def test_re_committing_an_op_replaces_in_place_never_duplicates(self):
        base = [{"operation_ref": "opA", "resource_id": "r1", "start": "s1"},
                {"operation_ref": "opB", "resource_id": "r2", "start": "s2"}]
        out = sp.compose_lineage_pins(base, {"operation_ref": "opA", "resource_id": "r9", "start": "s9"})
        assert [p["operation_ref"] for p in out] == ["opA", "opB"]   # order stable, no dup
        assert out[0]["resource_id"] == "r9" and out[0]["start"] == "s9"

    def test_root_lineage_is_just_the_new_pin(self):
        out = sp.compose_lineage_pins([], {"operation_ref": "opA", "resource_id": "r1", "start": "s1"})
        assert out == [{"operation_ref": "opA", "resource_id": "r1", "start": "s1"}]


class TestApplyPins:
    def test_apply_pin_binds_both_axes(self):
        m = _FakeModel()
        vm = _fake_var_map(["op1"], {"op1": ["r1", "r2"]})
        sp.apply_pin(m, vm, "op1", "r1", 150)
        assert (vm.op_start["op1"].name, "==", 150) in m.constraints
        assert (vm.op_assign["op1"]["r1"].name, "==", 1) in m.constraints

    def test_apply_pin_raises_on_missing_start(self):
        with pytest.raises(sp.PinUnsatisfiable):
            sp.apply_pin(_FakeModel(), _fake_var_map([], {}), "ghost", "r1", 0)

    def test_apply_pin_raises_on_ineligible_resource(self):
        vm = _fake_var_map(["op1"], {"op1": ["r1"]})
        with pytest.raises(sp.PinUnsatisfiable):
            sp.apply_pin(_FakeModel(), vm, "op1", "r2", 0)

    def test_apply_standing_pins_skips_the_fresh_op_and_missing_ops(self):
        from datetime import datetime, timezone
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        m = _FakeModel()
        vm = _fake_var_map(["opA", "opB"], {"opA": ["r1"], "opB": ["r2"]})
        pins = [
            {"operation_ref": "opA", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"},
            {"operation_ref": "opB", "resource_id": "r2", "start": "2026-01-05T01:00:00+00:00"},
            {"operation_ref": "gone", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"},
        ]
        applied = sp.apply_standing_pins(m, vm, pins, h0, skip_op="opA")
        assert applied == ["opB"]           # opA skipped (fresh), gone skipped (absent)


class TestDetectConflict:
    def test_names_an_overlapping_standing_pin_on_the_same_resource(self):
        from datetime import datetime, timezone
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        vm = _fake_var_map(["new", "held"], {}, durations={"new": 120, "held": 120})
        new = {"operation_ref": "new", "resource_id": "r1", "start": "2026-01-05T01:00:00+00:00"}
        standing = [{"operation_ref": "held", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"}]
        c = sp.detect_conflict(new, standing, vm, h0)   # held: [0,120), new: [60,180) → overlap
        assert c is not None and c.op_id == "held" and c.resource_id == "r1"

    def test_no_conflict_when_intervals_are_disjoint(self):
        from datetime import datetime, timezone
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        vm = _fake_var_map(["new", "held"], {}, durations={"new": 60, "held": 60})
        new = {"operation_ref": "new", "resource_id": "r1", "start": "2026-01-05T02:00:00+00:00"}
        standing = [{"operation_ref": "held", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"}]
        assert sp.detect_conflict(new, standing, vm, h0) is None

    def test_no_conflict_across_different_resources(self):
        from datetime import datetime, timezone
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        vm = _fake_var_map(["new", "held"], {}, durations={"new": 120, "held": 120})
        new = {"operation_ref": "new", "resource_id": "r1", "start": "2026-01-05T00:00:00+00:00"}
        standing = [{"operation_ref": "held", "resource_id": "r2", "start": "2026-01-05T00:00:00+00:00"}]
        assert sp.detect_conflict(new, standing, vm, h0) is None


class TestMovedSetExcludesStandingPins:
    def test_a_standing_pinned_op_is_never_a_moved_consequence(self):
        from datetime import datetime, timezone
        from mre.modules.sandbox import _moved_set
        h0 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        # held moved 60 min; if not excluded it WOULD appear in the moved-set.
        solve = SimpleNamespace(
            op_resource={"held": "r1", "dropped": "r1"},
            op_start_minutes={"held": 60, "dropped": 0},
        )
        incumbent = {"held": ("r1", h0), "dropped": ("r1", h0)}
        moves = _moved_set(solve, incumbent, h0, "dropped", exclude_ops={"held"})
        assert {m["operation_ref"] for m in moves} == {"dropped"}   # held structurally gone
        # the dropped op is exempt even if it is itself a standing pin
        moves2 = _moved_set(solve, incumbent, h0, "dropped", exclude_ops={"held", "dropped"})
        assert any(m["operation_ref"] == "dropped" for m in moves2)


class TestRegistryPinsPersistence:
    def test_pins_round_trip_and_default_empty(self, tmp_path):
        from mre.api.registry import Registry
        reg = Registry(tmp_path / "data")
        run = reg.create_run(kind="solve")
        reg.register_schedule(
            schedule_id="s-root", run_id=run["id"], snapshot_id=run["snapshot_id"],
            status="proposed", contract_version="1.5", document_path="x.json",
        )
        assert reg.schedule_pins("s-root") == []          # root solve: no pins
        pins = [{"operation_ref": "opA", "resource_id": "r1", "start": "s1"}]
        reg.register_schedule(
            schedule_id="s-child", run_id=run["id"], snapshot_id=run["snapshot_id"],
            status="proposed", contract_version="1.5", document_path="y.json",
            parent_schedule_id="s-root", pins=pins,
        )
        assert reg.schedule_pins("s-child") == pins
        assert reg.schedule_pins("unknown") == []

    def test_migration_adds_pins_column_to_a_preexisting_db(self, tmp_path):
        """A registry created before R-DP8 has no pins_json column; re-opening it
        must ALTER the table in, not crash — and old rows read as no-pins."""
        import sqlite3
        from mre.api.registry import Registry
        root = tmp_path / "data"
        root.mkdir()
        # a pre-4.0e schedules table (no pins_json column)
        con = sqlite3.connect(root / "registry.sqlite")
        con.execute(
            "CREATE TABLE schedules (id TEXT PRIMARY KEY, run_id TEXT, submission_id TEXT, "
            "snapshot_id TEXT, status TEXT, contract_version TEXT, is_scenario INTEGER, "
            "parent_schedule_id TEXT, document_path TEXT, created_at TEXT)")
        con.execute("INSERT INTO schedules (id, run_id, snapshot_id, status, "
                    "contract_version, is_scenario, document_path, created_at) "
                    "VALUES ('old','r','snap','proposed','1.4',0,'d.json','t')")
        con.commit(); con.close()

        reg = Registry(root)                              # __init__ runs the migration
        assert reg.schedule_pins("old") == []             # legacy row: reads as no-pins


# ---------------------------------------------------------------------------
# CU3 regression — end to end, the two-edit chain (slow)
# ---------------------------------------------------------------------------

def _data(resp, status=200):
    assert resp.status_code == status, (resp.status_code, resp.text)
    return resp.json()["data"]


def _error(resp, status):
    assert resp.status_code == status, (resp.status_code, resp.text)
    return resp.json()["error"]


@pytest.fixture(scope="module")
def multi_api(tmp_path_factory):
    """A solved ``multi_route_distinct`` submission — distinct rates + genuinely
    multi-eligible ops, so a cost-neutral CROSS-MACHINE move exists that the
    optimizer would revert on the next solve absent R-DP8."""
    from mre.api.app import create_app
    from tools.generate_erp_dataset import generate
    root = tmp_path_factory.mktemp("rdp8_data")
    sub_src = tmp_path_factory.mktemp("rdp8_sub") / "multi_route_distinct"
    generate(sub_src, scenario="multi_route_distinct", seed=7)
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(sub_src)}))
    assert sub["grade"] == "ACCEPTED"
    solve = _data(client.post(
        f"/submissions/{sub['submission_id']}/solve",
        json={"time_limit": 45, "deterministic": True}), status=202)
    run = _data(client.get(f"/runs/{solve['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return SimpleNamespace(client=client, root=root,
                           submission_id=sub["submission_id"],
                           schedule_id=run["result"]["schedule_id"])


@pytest.fixture
def fresh_base(multi_api):
    """A NEW deterministic solve of the shared submission → a fresh proposed base
    id. Each test needs its own: publishing an edit supersedes the base, which
    would poison a module-shared schedule for later tests."""
    solve = _data(multi_api.client.post(
        f"/submissions/{multi_api.submission_id}/solve",
        json={"time_limit": 45, "deterministic": True}), status=202)
    run = _data(multi_api.client.get(f"/runs/{solve['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return run["result"]["schedule_id"]


def _cross_machine_pin(client, sid):
    """A pin moving a placed multi-eligible op to a DIFFERENT eligible resource at
    its own incumbent start. Returns (pin, incumbent_resource_id)."""
    doc = _data(client.get(f"/schedules/{sid}"))
    inter = _data(client.get(f"/schedules/{sid}/interaction"))["interaction"]
    elig = {op["operation_ref"]: (op.get("eligible_resource_ids") or [])
            for op in inter["operations"]}
    placed = {a["operation_ref"]: a for a in doc["assignments"]}
    for op_ref, refs in elig.items():
        if op_ref not in placed:
            continue
        inc = placed[op_ref]["resource_id"]
        alts = [r for r in refs if r != inc]
        if alts:
            a = placed[op_ref]
            return ({"pin_op_id": op_ref, "pin_resource_id": alts[0],
                     "pin_start_iso": a["chunks"][0]["start"],
                     "authority": "dev-planner"}, inc)
    raise AssertionError("fixture has no cross-machine drop available")


def _pin_from_incumbent_excluding(doc, exclude_op):
    """Pin some OTHER placed op at its own incumbent placement (a trivially
    feasible second edit that is not the standing-pinned op)."""
    for a in doc["assignments"]:
        if a["operation_ref"] != exclude_op:
            return {"pin_op_id": a["operation_ref"], "pin_resource_id": a["resource_id"],
                    "pin_start_iso": a["chunks"][0]["start"], "authority": "dev-planner"}
    raise AssertionError("no second op to pin")


def _decisions_in_run(root, schedule_id):
    import sqlite3
    con = sqlite3.connect(Path(root) / "registry.sqlite")
    con.row_factory = sqlite3.Row
    out_dir = con.execute("SELECT r.out_dir FROM schedules s JOIN runs r ON r.id=s.run_id "
                          "WHERE s.id=?", (schedule_id,)).fetchone()["out_dir"]
    con.close()
    decisions = []
    for f in sorted((Path(out_dir) / "runs").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("record_type") == "decision":
                    decisions.append(rec)
    return decisions


@pytest.mark.slow
class TestTwoEditChainHoldsTheFirstCommitment:
    """The R-DP8 regression that was missing: edit A accepted + published, edit B
    accepted → A's placement is UNCHANGED in B's version AND A's op appears in no
    moved-set. Absent R-DP8, B's re-solve reverts A's cost-neutral cross-machine
    move (the live specimen)."""

    def test_a_published_edit_is_not_reverted_by_the_next_edit(self, multi_api, fresh_base):
        client, base = multi_api.client, fresh_base

        # Edit A: a genuine cross-machine move, accepted then published.
        pin_a, inc_a = _cross_machine_pin(client, base)
        assert pin_a["pin_resource_id"] != inc_a
        acc_a = _data(client.post(f"/schedules/{base}/accept", json=pin_a), status=201)
        v1 = acc_a["schedule_id"]
        _data(client.post(f"/schedules/{v1}/publish"))

        # v1 records A as a STANDING pin, and A's bar is marked in the document.
        v1_doc = _data(client.get(f"/schedules/{v1}"))
        a_in_v1 = next(x for x in v1_doc["assignments"]
                       if x["operation_ref"] == pin_a["pin_op_id"])
        assert a_in_v1["resource_id"] == pin_a["pin_resource_id"]
        assert a_in_v1["standing_pin"] is True

        # Edit B: pin a DIFFERENT op at its incumbent (trivially feasible). Its
        # re-solve is where A would be reverted absent the standing pin.
        pin_b = _pin_from_incumbent_excluding(v1_doc, pin_a["pin_op_id"])
        assert pin_b["pin_op_id"] != pin_a["pin_op_id"]
        acc_b = _data(client.post(f"/schedules/{v1}/accept", json=pin_b), status=201)
        v2 = acc_b["schedule_id"]

        # THE ASSERTION: A's placement is unchanged in v2 (never reverted).
        v2_doc = _data(client.get(f"/schedules/{v2}"))
        a_in_v2 = next(x for x in v2_doc["assignments"]
                       if x["operation_ref"] == pin_a["pin_op_id"])
        assert a_in_v2["resource_id"] == pin_a["pin_resource_id"], (
            "R-DP8 violated: edit B's re-solve reverted a published commitment")
        assert a_in_v2["chunks"][0]["start"] == pin_a["pin_start_iso"]
        # A stays a standing pin on v2 (the commitment carries down the lineage).
        assert a_in_v2["standing_pin"] is True

        # AND A's op appears in NO moved-set of edit B (structurally excluded).
        edit_b_decisions = [d for d in _decisions_in_run(multi_api.root, v2)
                            if d["decision_type"] == "planner_edit"]
        assert edit_b_decisions, "edit B recorded a planner_edit Decision"
        moves = edit_b_decisions[-1]["chosen"].get("moves", [])
        assert all(m["operation_ref"] != pin_a["pin_op_id"] for m in moves), (
            "a standing-pinned op must never be listed as a moved consequence")

    def test_a_drop_conflicting_with_a_standing_commitment_is_refused(self, multi_api, fresh_base):
        """A drop that lands ON a standing commitment's slot (same resource +
        start) is refused with a conflict, never accepted by sacrificing the older
        pin. Uses a fresh base so the module base schedule is untouched."""
        client, base = multi_api.client, fresh_base

        pin_a, _ = _cross_machine_pin(client, base)
        acc_a = _data(client.post(f"/schedules/{base}/accept", json=pin_a), status=201)
        v1 = acc_a["schedule_id"]

        # Try to drop a DIFFERENT op onto op-A's exact committed (resource, start).
        v1_doc = _data(client.get(f"/schedules/{v1}"))
        other = next(a for a in v1_doc["assignments"]
                     if a["operation_ref"] != pin_a["pin_op_id"])
        inter = _data(client.get(f"/schedules/{v1}/interaction"))["interaction"]
        elig = {op["operation_ref"]: set(op.get("eligible_resource_ids") or [])
                for op in inter["operations"]}
        # only meaningful if `other` is eligible on A's committed machine
        if pin_a["pin_resource_id"] not in elig.get(other["operation_ref"], set()):
            pytest.skip("no second op eligible on the committed machine to force a conflict")
        conflicting = {"pin_op_id": other["operation_ref"],
                       "pin_resource_id": pin_a["pin_resource_id"],
                       "pin_start_iso": pin_a["pin_start_iso"],
                       "authority": "dev-planner"}
        # sandbox: an honest infeasible verdict (never a happy delta)
        sb = _data(client.post(f"/schedules/{v1}/sandbox", json=conflicting))
        assert sb["feasible"] is False
        # accept: refused 409, the base stands
        _error(client.post(f"/schedules/{v1}/accept", json=conflicting), 409)
