"""R-SG1 (Session R4.1) — the scope guard and the frame invariant.

R4.0 proved by measurement that both pool builders rebuilt the base model over
the WHOLE SNAPSHOT rather than the plan of record, and that such a model cannot
reproduce a plan the board already has: on the gen-3 demo board the rebuild was
INFEASIBLE **with no cut applied at all**, so ``infeasible_this_horizon`` was
never a statement about the alternative. Correctly scoped, 8 of 8 of that
pool's own targets came back FEASIBLE.

Underneath sits the missing invariant: nothing asserted that the minute grid a
pin is expressed in is the grid the model was built in. On an accept-derived
child the two origins were 35 days apart, so every pin a planner could express
landed before the first calendar window in the model's frame and beat one
answered "the machine is not open at that time" — always, about machines that
were open.

These are the regressions for both halves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from mre.modules.sandbox import correlation_id_for, plan_of_record_scope
from mre.modules.standing_pins import FrameMismatch, assert_frame

UTC = timezone.utc


def _dt(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


# ---------------------------------------------------------------------------
# R-SG1 clause (2) — the invariant itself
# ---------------------------------------------------------------------------

class TestFrameInvariant:
    """``assert_frame`` either passes silently or raises a typed error naming
    BOTH origins and the offset. There is deliberately no third behaviour — no
    "warn and continue" — because the defect class is a confident WRONG VERDICT
    rendered from a mis-framed model."""

    def _vm(self, origin):
        return SimpleNamespace(horizon_start=origin)

    def test_agreeing_frames_pass_silently(self):
        origin = _dt(2026, 1, 5)
        assert assert_frame(self._vm(origin), origin, site="test") is None

    def test_disagreeing_frames_raise_typed_error(self):
        """The live specimen: child b5daba66's builder origin was 2025-12-01
        against an evidence horizon of 2026-01-05."""
        evidence, builder = _dt(2026, 1, 5), _dt(2025, 12, 1)
        with pytest.raises(FrameMismatch) as exc:
            assert_frame(self._vm(builder), evidence, site="beat one")
        e = exc.value
        assert e.offset_minutes == -50400          # 35 days, in minutes
        assert e.evidence_origin == evidence
        assert e.builder_origin == builder
        # A mismatch a reader cannot diagnose from the message is a mismatch
        # reported twice: it names the site, both origins, and the offset.
        msg = str(e)
        assert "beat one" in msg
        assert "2026-01-05" in msg and "2025-12-01" in msg
        assert "50400" in msg

    def test_a_one_minute_offset_is_still_a_mismatch(self):
        """No tolerance. The grid is integer minutes and a pin binds on it
        exactly, so a 'small' offset is every pin misplaced by that much."""
        evidence = _dt(2026, 1, 5)
        with pytest.raises(FrameMismatch):
            assert_frame(self._vm(evidence + timedelta(minutes=1)),
                         evidence, site="test")

    @pytest.mark.parametrize("builder,evidence", [
        (None, _dt(2026, 1, 5)),
        (_dt(2026, 1, 5), None),
        (None, None),
    ])
    def test_an_unreadable_origin_fails_safe(self, builder, evidence):
        """The third-state law at the frame (``unreadable`` 4B.18): an origin
        that cannot be read says NOTHING about the plant, so it refuses rather
        than assuming agreement — which is precisely what "assumed" meant
        before this ruling."""
        with pytest.raises(FrameMismatch):
            assert_frame(self._vm(builder), evidence, site="test")

    def test_a_missing_origin_reports_no_offset_rather_than_zero(self):
        """No offset exists between a known instant and an unknown one.
        Reporting 0 would be a default that ASSERTS (4B.23)."""
        with pytest.raises(FrameMismatch) as exc:
            assert_frame(self._vm(None), _dt(2026, 1, 5), site="test")
        assert exc.value.offset_minutes is None

    def test_a_var_map_without_the_attribute_at_all_fails_safe(self):
        """Not every object handed here will be a VariableMap. An absent
        attribute is an unreadable origin, not an agreeing one."""
        with pytest.raises(FrameMismatch):
            assert_frame(object(), _dt(2026, 1, 5), site="test")


# ---------------------------------------------------------------------------
# R-SG1 clause (1) — the scope a rebuild derives for itself
# ---------------------------------------------------------------------------

class TestPlanOfRecordScope:
    """The scope is DERIVED from the plan, never handed in. These pin the
    contract the two pool builders now depend on."""

    def _asg(self, *op_ids):
        return [{"operation_ref": o} for o in op_ids]

    def test_the_scope_is_exactly_what_the_plan_places(self):
        assert plan_of_record_scope(self._asg("a", "b", "c")) == {"a", "b", "c"}

    def test_a_plan_that_places_nothing_has_no_scope(self):
        """None, not the empty set: restricting to the empty set is a
        different claim from having no plan of record to scope to."""
        assert plan_of_record_scope([]) is None
        assert plan_of_record_scope([{"operation_ref": ""}]) is None

    def test_the_scope_ignores_assignments_with_no_operation(self):
        assert plan_of_record_scope(
            self._asg("a") + [{"resource_id": "r"}]) == {"a"}

    def test_both_pool_builders_derive_it_rather_than_accept_it(self):
        """R-SG1 (1) is a statement about WHERE the scope comes from, so the
        regression is that neither builder exposes a scope parameter a caller
        could get wrong. 4B.31's lesson was that a restriction which exists but
        must be remembered is not a guarantee — it was wired to three of four
        surfaces for six sessions, and R4.0 found the census that fixed the
        fourth had stopped two seams short of these two."""
        import inspect

        from mre.modules.forced_alternatives import build_forced_alternatives
        from mre.modules.solution_pool import warm_solution_pool

        for fn in (build_forced_alternatives, warm_solution_pool):
            params = inspect.signature(fn).parameters
            assert "restrict_op_ids" not in params, (
                f"{fn.__name__} takes a caller-supplied scope again — "
                "R-SG1 (1) requires it be derived from the plan of record")


# ---------------------------------------------------------------------------
# R-T2 / the two-beat correlation (the errand's C4 item 5)
# ---------------------------------------------------------------------------

class TestCorrelationInstant:
    """A correlation id names a GESTURE — a (snapshot, op, resource, instant) a
    planner made. An instant is a point in time, not a spelling."""

    def test_the_two_spellings_of_one_instant_agree(self):
        """The live break: beat one round-trips the start through ``datetime``
        and emits ``+00:00``; beat two passes the document's own string
        through verbatim, which ends in ``Z``. Same instant, two ids, and the
        two-beat contract silently broken for every gesture whose start came
        off the board."""
        z = correlation_id_for("snap", "op-1", "res-1", "2026-01-12T17:33:00Z")
        off = correlation_id_for("snap", "op-1", "res-1",
                                 "2026-01-12T17:33:00+00:00")
        assert z == off

    def test_a_different_zone_spelling_of_the_same_instant_agrees(self):
        a = correlation_id_for("snap", "op-1", "res-1", "2026-01-12T17:33:00Z")
        b = correlation_id_for("snap", "op-1", "res-1",
                               "2026-01-12T12:33:00-05:00")
        assert a == b

    def test_different_instants_still_differ(self):
        a = correlation_id_for("snap", "op-1", "res-1", "2026-01-12T17:33:00Z")
        b = correlation_id_for("snap", "op-1", "res-1", "2026-01-12T17:34:00Z")
        assert a != b

    def test_different_pins_still_differ(self):
        base = correlation_id_for("snap", "op-1", "res-1", "2026-01-12T17:33:00Z")
        assert base != correlation_id_for("snap", "op-1", "res-2",
                                          "2026-01-12T17:33:00Z")
        assert base != correlation_id_for("snap", "op-2", "res-1",
                                          "2026-01-12T17:33:00Z")
        assert base != correlation_id_for("snap2", "op-1", "res-1",
                                          "2026-01-12T17:33:00Z")

    @pytest.mark.parametrize("bad", ["garbage", "", None])
    def test_an_unparseable_instant_does_not_raise(self, bad):
        """Correlating two beats is not the place to start throwing. Before
        R4.1 the raw text was hashed with no parse at all, so no caller could
        make this function raise; canonicalization must not change that."""
        assert correlation_id_for("snap", "op-1", "res-1", bad).startswith("corr-")


# ---------------------------------------------------------------------------
# R-SG1 clause (1) on a REAL rolling board — the regression R4.0's probes earn
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rolling_run(tmp_path_factory):
    """A real sliced (rolling) solve, so the plan of record is genuinely
    NARROWER than the snapshot — which is the only condition under which the
    unscoped rebuild and the scoped one differ at all. On a monolithic board
    every operation is placed and ``plan_of_record_scope`` is the identity."""
    from fastapi.testclient import TestClient

    from mre.api.app import create_app
    from tools.generate_erp_dataset import generate

    root = tmp_path_factory.mktemp("sg1_data")
    sub_src = tmp_path_factory.mktemp("sg1_sub") / "pilot"
    generate(sub_src, scenario="pilot_scale", orders=40, seed=1)
    client = TestClient(create_app(data_root=root))
    sub = client.post("/submissions", json={"path": str(sub_src)}).json()["data"]
    assert sub["grade"] == "ACCEPTED"
    solve = client.post(
        f"/submissions/{sub['submission_id']}/solve",
        json={"sliced": True, "window_days": 14, "frozen_days": 3,
              "time_limit": 10, "deterministic": True, "sync": True,
              "portfolio_k": 1},
    ).json()["data"]
    run = client.get(f"/runs/{solve['run_id']}").json()["data"]
    assert run["status"] == "succeeded", run.get("error")
    return SimpleNamespace(
        run_dir=root / "runs" / solve["run_id"],
        schedule_id=run["result"]["schedule_id"], run_id=solve["run_id"])


@pytest.mark.slow
class TestScopedRebuildOnARollingBoard:

    def _scope(self, rolling_run):
        from mre.modules.snapshot_store import SnapshotStore
        snap = next(p.name for p in (rolling_run.run_dir / "snapshots").iterdir()
                    if p.is_dir())
        reader = SnapshotStore(rolling_run.run_dir / "snapshots").load_snapshot(snap)
        ops = sum(1 for _ in reader.iter_entities("operation"))
        scope = plan_of_record_scope(list(reader.iter_entities("assignment")))
        return snap, ops, scope

    def test_the_plan_of_record_is_narrower_than_the_snapshot(self, rolling_run):
        """The precondition for everything else. If this ever stops holding,
        the tests below are passing vacuously and would say nothing — the
        empty-denominator law applied to the fixture itself."""
        _snap, ops, scope = self._scope(rolling_run)
        assert scope, "the board places nothing"
        assert len(scope) < ops, (
            f"the fixture places all {ops} operations, so scoped and unscoped "
            "rebuilds are the same model and this file proves nothing")

    def test_the_alternatives_pool_publishes_on_a_rolling_board(self, rolling_run):
        """R4.0's headline: 0 of 8 publishable on the gen-3 demo board, and
        8 of 8 feasible when scoped.

        **This test does NOT discriminate on this fixture, and says so rather
        than implying a proof it did not make.** Measured in R4.1: revert both
        scope derivations and this test still PASSES, because 40 orders over a
        14-day window leave the whole snapshot small enough to fit even
        unscoped. It is a POST-CONDITION — the pool must publish — not evidence
        that the guard is what makes it publish.

        The discriminating member of this file is
        ``test_the_near_optimal_pool_is_not_empty_on_a_rolling_board`` (proven
        red against physically reverted code). The discriminating evidence at
        DEMO density is the gen-3 measurement recorded in the close-out: 0 of 8
        publishable before, 4 of 8 at the default member budget after, 8 of 8
        when the budget is raised."""
        from mre.modules.forced_alternatives import build_forced_alternatives

        snap, _ops, _scope = self._scope(rolling_run)
        res = build_forced_alternatives(
            out_dir=rolling_run.run_dir, snapshot_id=snap,
            base_schedule_id=rolling_run.schedule_id, run_id=rolling_run.run_id,
            budget=4, member_time_limit_s=30.0,
        )
        assert res.members, "the heuristic selected no targets"
        priced = [m for m in res.members if m.verdict == "priced"]
        assert priced, (
            "every member refused — the rebuild cannot reproduce the plan of "
            f"record: {[(m.status, m.verdict) for m in res.members]}")

    def test_the_near_optimal_pool_is_not_empty_on_a_rolling_board(self, rolling_run):
        """The second consumer of the same unscoped rebuild. Measured `empty`,
        3 of 3 INFEASIBLE, on a scratch copy of gen-3 before R-SG1."""
        from mre.modules.solution_pool import warm_solution_pool

        snap, _ops, _scope = self._scope(rolling_run)
        pr = warm_solution_pool(
            out_dir=rolling_run.run_dir, snapshot_id=snap,
            base_schedule_id=rolling_run.schedule_id, run_id=rolling_run.run_id,
            k=2, member_time_limit_s=30.0)
        assert pr.status != "empty", (
            f"pool empty: {[(m.status) for m in pr.members]}")

    def test_the_scoped_rebuild_reproduces_the_incumbent(self, rolling_run):
        """The no-cut control (R4.0 P1). Scoped to the plan of record, the
        published plan is a feasible assignment of the rebuilt model BY
        CONSTRUCTION — so a rebuild with NO cut applied must be feasible. That
        is the property the whole ruling rests on, and it is what was false
        before: the unscoped rebuild of the gen-3 incumbent was INFEASIBLE with
        nothing cut at all (2.15s), which is how R4.0 proved the verdict rather
        than the alternative was wrong.

        **Like the test above, this one does not discriminate at this fixture's
        density** — reverted, the unscoped rebuild of a 40-order board is still
        feasible. It guards the post-condition; the gen-3 numbers in the
        close-out are what establish the counterfactual."""
        from mre.modules.forced_alternatives import _load_alt_context
        from mre.modules.solve_runner import SolveRunner
        from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
        from mre.reporter import Reporter
        from mre.contracts.vocabularies import ModuleCode, RunStatus

        snap, _ops, _scope = self._scope(rolling_run)
        actx = _load_alt_context(rolling_run.run_dir, snap, "runs")
        model, var_map = SolverBuilder(reference_date=actx.reference_date).build(
            actx.wps + actx.ops + actx.edges, actx.resources + actx.pools,
            actx.flattened_cals, actx.fuls + actx.demands, actx.constraints,
            actx.cost_model,
        )
        apply_solution_hints(model, var_map, actx.incumbent_assignments)
        rep = Reporter.begin(
            module=ModuleCode.M6, purpose="R-SG1 no-cut control", config={},
            trigger="test", snapshot_id=snap,
            sink_dir=rolling_run.run_dir / "sg1_control_runs")
        result = SolveRunner(time_limit_seconds=60.0, num_search_workers=1,
                             random_seed=0).solve(model, var_map, rep)
        rep.end(RunStatus.SUCCESS)
        assert result.status in ("OPTIMAL", "FEASIBLE"), (
            f"the scoped rebuild with NO cut is {result.status} — it cannot "
            "reproduce the plan the board already published, which is exactly "
            "the defect R-SG1 (1) exists to prevent")
