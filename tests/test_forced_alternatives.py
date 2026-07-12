"""Forced-alternative service (docs/07 Phase 3, R-T1a/b, session 3.2a CU3).

The counterfactual (price-bought-something): on multi_route with DISTINCT rates
— the economically realistic case that motivated R-T1 — the plain solution pool
CONVERGES on machine placement and yields ~0 cross-machine ghosts, while the
forced-alternative service yields PRICED cross-machine alternatives (the true
cost of each road not taken). Both halves are asserted, deterministically
(--solver-workers 1 --solver-seed 42):

  * POOL HALF  — the plain pool on the distinct-rate fixture crosses machines
    ~0 times (the pool-only ghost degradation R-T1 names).
  * FORCED HALF — the forced-alternative service produces ≥1 feasible
    cross-machine alternative carrying a nonzero price, MORE than the pool.

Plus: infeasibility is first-class (a single-eligibility target yields a
"not feasible this horizon" verdict, no document), and the selection heuristic
picks the at-risk demands' multi-eligible ops.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.forced_alternatives import (
    build_forced_alternatives,
    select_target_ops,
)
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.solution_pool import warm_solution_pool
from tools.generate_erp_dataset import generate

SNAP = "snap-mrd"


def _run_pipeline(sub: Path, out: Path, snap: str = SNAP) -> None:
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", "45", "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"


@pytest.fixture(scope="module")
def distinct(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("multi_route_distinct")
    sub = tmp / "sub"
    truth = generate(sub, scenario="multi_route_distinct", seed=7)["multi_route"]
    out = tmp / "out"
    _run_pipeline(sub, out)
    reader = SnapshotStore(out / "snapshots").load_snapshot(SNAP)
    return truth, sub, out, reader


# ---------------------------------------------------------------------------
# Structure — the distinct-rate fixture is what we think it is
# ---------------------------------------------------------------------------

def test_distinct_fixture_has_all_distinct_rates(distinct):
    truth, _, _, _ = distinct
    assert truth["distinct_rates"] is True
    rates = list(truth["resource_rates"].values())
    assert len(set(rates)) == len(rates), "rates are not all distinct"


def test_forced_cut_is_a_noop_without_the_incumbent_literal():
    """The mechanism behind the infeasible_this_horizon verdict: forcing an op
    off a machine it cannot run on (no assignment literal) is a no-op — the
    service records it as 'not feasible this horizon', never a silent drop."""
    from ortools.sat.python import cp_model

    from mre.modules.solver_builder import VariableMap, add_forced_alternative_cut
    m = cp_model.CpModel()
    vm = VariableMap(horizon_start=None)
    vm.op_assign["op-x"] = {"R0": m.new_bool_var("op-x@R0")}
    # no literal for R1 → nothing to forbid → False (→ infeasible verdict)
    assert add_forced_alternative_cut(m, vm, "op-x", "R1") is False
    # a real incumbent literal → the "not on this machine" cut is added
    assert add_forced_alternative_cut(m, vm, "op-x", "R0") is True


def test_selection_picks_multi_eligible_ops(distinct):
    _, _, _, reader = distinct
    ops = list(reader.iter_entities("operation"))
    from mre.modules.solution_pool import _placements
    placement = _placements(list(reader.iter_entities("assignment")))
    picked = select_target_ops(
        operations=ops,
        fulfillments=list(reader.iter_entities("fulfillment")),
        demands=list(reader.iter_entities("demand")),
        service_outcomes=list(reader.iter_entities("serviceoutcome")),
        incumbent_placement=placement, budget=4,
    )
    assert picked, "heuristic selected no target ops"
    eligible = {op["id"]: (op.get("resource_requirements") or [{}])[0].get("resource_refs") or []
                for op in ops}
    for oid in picked:
        assert len(eligible[oid]) > 1, "a selected op is not multi-eligible"


# ---------------------------------------------------------------------------
# The counterfactual — both halves (slow: pool + forced re-solves)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pool(distinct):
    _, _, out, _ = distinct
    return warm_solution_pool(
        out_dir=out, snapshot_id=SNAP, base_schedule_id="s", run_id="run-mrd",
        k=5, member_time_limit_s=8.0,
    )


@pytest.fixture(scope="module")
def forced(distinct):
    _, _, out, _ = distinct
    return build_forced_alternatives(
        out_dir=out, snapshot_id=SNAP, base_schedule_id="s", run_id="run-mrd",
        budget=4, member_time_limit_s=8.0,
    )


@pytest.mark.slow
def test_pool_converges_on_distinct_rates(distinct, pool):
    """POOL HALF: with distinct rates + a light load the near-optimal pool
    converges on machine placement — cross-machine ghosts ~0."""
    assert pool.status == "ready"
    assert pool.diversity["cross_machine_ops"] <= 1, (
        f"pool cross_machine_ops={pool.diversity['cross_machine_ops']} — the "
        "distinct-rate pool should converge on machine placement, not spread"
    )


@pytest.mark.slow
def test_forced_service_prices_cross_machine_alternatives(distinct, forced):
    """FORCED HALF: the forced-alternative service delivers ≥1 feasible
    cross-machine alternative carrying a nonzero price — the road not taken,
    priced."""
    assert forced.status == "ready"
    priced = forced.priced_cross_machine()
    assert priced, "forced-alternative service surfaced no priced cross-machine ghost"
    for m in priced:
        assert m.alternative_resource_ref != m.forbidden_resource_ref
        assert m.objective_delta_pct is not None
        # the compact ghost placement the cockpit renders (CU2): the moved op
        # sits on its alternative machine, with a start/end bar.
        p = m.alternative_placement
        assert p and p["resource_id"] == m.alternative_resource_ref
        assert p["start"] and p["end"]
        # moving an op off its (cheapest) incumbent machine costs MORE
        assert m.objective_delta_pct > 0, (
            f"forced move off {m.forbidden_resource_ref} priced at "
            f"{m.objective_delta_pct}% — expected a positive premium"
        )


@pytest.mark.slow
def test_forced_beats_pool_on_cross_machine_ghosts(distinct, pool, forced):
    """The price-bought-something contrast: the forced-alternative service
    surfaces MORE priced cross-machine ghosts than the plain pool does on the
    same economically realistic (distinct-rate) data."""
    n_forced = len(forced.priced_cross_machine())
    n_pool = pool.diversity["cross_machine_ops"]
    assert n_forced >= 1
    assert n_forced > n_pool, (
        f"forced priced cross-machine={n_forced} is not more than the pool's "
        f"cross_machine_ops={n_pool} — the service bought nothing"
    )


@pytest.mark.slow
def test_infeasibility_is_first_class(distinct):
    """R-T1a: a forced solve with nothing to move (a single-eligibility target)
    is stored as a 'not feasible this horizon' verdict, not dropped."""
    _, _, out, reader = distinct
    # find a SINGLE-eligibility op (if any) — its forced cut is a no-op, so the
    # verdict is infeasible_this_horizon with no document.
    single = None
    from mre.modules.solution_pool import _placements
    placement = _placements(list(reader.iter_entities("assignment")))
    for op in reader.iter_entities("operation"):
        refs = (op.get("resource_requirements") or [{}])[0].get("resource_refs") or []
        if len(refs) <= 1 and op["id"] in placement:
            single = op["id"]
            break
    if single is None:
        pytest.skip("distinct fixture has no single-eligibility scheduled op")
    result = build_forced_alternatives(
        out_dir=out, snapshot_id=SNAP, base_schedule_id="s", run_id="run-mrd",
        target_op_ids=[single], budget=1, member_time_limit_s=8.0,
    )
    assert result.members
    m = result.members[0]
    assert m.verdict == "infeasible_this_horizon"
    assert m.document_path is None
