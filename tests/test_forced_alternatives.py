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
    build_op_alternatives,
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


def test_selection_widens_to_top_n_expensive():
    """Session 3.3 CU1: the widening buys the most-EXPENSIVE multi-eligible op
    even when its demand isn't late. Pure (no solve): one late demand + two
    on-time, budget 2. Phase A takes the late op; the widening's phase B then
    buys the expensive op — where the pre-widening slack walk would have taken a
    cheap on-time op instead."""
    ops = [{"id": f"op{i}", "workpackage_ref": f"wp{i}",
            "resource_requirements": [{"resource_refs": ["R0", "R1"]}]}
           for i in range(3)]
    fuls = [{"demand_ref": f"d{i}", "workpackage_ref": f"wp{i}"} for i in range(3)]
    demands = [{"id": f"d{i}"} for i in range(3)]
    svc = [{"demand_ref": "d0", "lateness_minutes": 100},   # late
           {"demand_ref": "d1", "lateness_minutes": -50},   # on time (cheap op)
           {"demand_ref": "d2", "lateness_minutes": -50}]   # on time (EXPENSIVE op)
    placement = {f"op{i}": ("R0", None) for i in range(3)}
    cost = {"op0": 10.0, "op1": 20.0, "op2": 300.0}
    common = dict(operations=ops, fulfillments=fuls, demands=demands,
                  service_outcomes=svc, incumbent_placement=placement, budget=2)

    widened = select_target_ops(**common, incumbent_cost=cost, top_n_expensive=6)
    plain = select_target_ops(**common, top_n_expensive=0)   # widening off

    assert widened[0] == "op0", "the late op still leads"
    assert "op2" in widened and "op1" not in widened, "widening bought the expensive op"
    assert "op2" not in plain and "op1" in plain, "without widening the cheap op wins"


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
        # planner vocabulary end-to-end (session 3.3 CU2): the ghost names its
        # work order(s) — the empty-work_orders bug is fixed.
        assert p["work_orders"], "ghost placement carries no work order name"
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
def test_on_demand_prices_every_eligible_machine(distinct):
    """Session 3.3 CU1 (R-T1a K'): the on-demand path prices EVERY eligible
    machine for one grabbed op — not just the solver's single cheapest escape.
    Each priced member pins the op to its own machine and carries the incumbent
    as forbidden; each placement names its work order (CU2)."""
    _, _, out, reader = distinct
    from mre.modules.solution_pool import _placements
    ops = list(reader.iter_entities("operation"))
    placement = _placements(list(reader.iter_entities("assignment")))
    op = next((o for o in ops if o["id"] in placement
               and len((o.get("resource_requirements") or [{}])[0].get("resource_refs") or []) > 1),
              None)
    assert op is not None, "distinct fixture has a multi-eligible scheduled op"
    op_id = op["id"]
    incumbent = placement[op_id][0]
    eligible = (op.get("resource_requirements") or [{}])[0]["resource_refs"]
    expected_machines = [r for r in eligible if r != incumbent][:4]

    res = build_op_alternatives(
        out_dir=out, snapshot_id=SNAP, base_schedule_id="s", run_id="run-mrd",
        op_id=op_id, max_machines=4, member_time_limit_s=8.0,
    )
    # one member per targeted machine — none silently dropped (priced OR a
    # first-class infeasible verdict)
    assert len(res.members) == len(expected_machines)
    priced_machines = set()
    for m in res.members:
        assert m.forbidden_resource_ref == incumbent
        assert m.verdict in ("priced", "infeasible_this_horizon")
        if m.verdict == "priced":
            assert m.alternative_resource_ref in expected_machines
            assert m.alternative_placement["resource_id"] == m.alternative_resource_ref
            assert m.alternative_placement["work_orders"], "no work order on ghost"
            priced_machines.add(m.alternative_resource_ref)
    # the roads are distinct machines (every eligible one got its own price)
    assert len(priced_machines) == sum(
        1 for m in res.members if m.verdict == "priced")


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
