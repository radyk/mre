"""Session 4B.6a CU3 — THE BINDING BEHAVIOUR OF THE COARSE MODEL, PINNED.

4B.6 measured the coarse model actually WORKING — at 200 orders: 404 ops
modeled, 123 buckets of tardiness, machine-weeks at ~100% of capacity, and
rho = 0.5 INFEASIBLE. Those numbers existed only in prose.

The committed 40-order guard runs over a plant loaded to roughly 8% of derated
capacity, where nothing binds: tardiness is 0, no cell is at capacity, and the
model would look exactly the same if its capacity constraints were removed. So
the entire BINDING behaviour of this model had no regression behind it — the
suite could not have caught a coarse zone that quietly stopped constraining
anything.

This file is that regression. It asserts SHAPE and THRESHOLDS, not exact figures
(a coarse solve is a real CP-SAT search and its objective ties are its own), but
tightly enough that a model which stops binding goes red.

MEASURED on pilot_scale at 200 orders, window 7 / frozen 2, REF 2026-01-05
(2026-07-27, deterministic, seed 42, PYTHONHASHSEED=0):

    beyond-horizon demands 157, coarse ops 408 (404 modeled, 4 unmodelable)
    rho 1.00  FEASIBLE   tardiness 123 buckets  9 binding cells  peak util 0.998
    rho 0.85  FEASIBLE   tardiness 164 buckets  9 binding cells  peak util 0.999
    rho 0.50  INFEASIBLE (404 still modeled — an aggregate-capacity refutation)
    rho 0.15  INFEASIBLE (393 modeled, 15 unmodelable)
    rho 0.10  INFEASIBLE (357 modeled, 51 unmodelable)

Every run here is deterministic with a generous WALL CEILING, because the wall
is a ceiling and never the budget: a wall-truncated coarse run is a lottery
wearing a determinism label, and each test asserts it did not happen.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.coarse_horizon import (
    BINDING_UTILIZATION, CoarseCoefficients, build_coarse_zone,
)

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)

ORDERS = 200
WINDOW_DAYS, FROZEN_DAYS = 7, 2
# TWO BUDGETS, TWO QUANTITIES, and they are not interchangeable (the 4B.8 CU2
# rename, re-learned in 4B.25 Item 4b). DET_TIME is what ONE coarse solve gets
# (``build_coarse_zone(det_time=...)``); DET_TOTAL is the rolling window-0
# solve's budget for BOTH R-SC3 stages together
# (``build_rolling_view(det_total=...)``). This file passed ``det_time`` to both
# for six sessions — invisibly, because its fixtures are ``--runslow``-gated.
DET_TIME = 4.0
DET_TOTAL = 6.0                 # = the historical 4.0 stage-1 + the old 2.0 stage-2
SAFETY_CEILING_S = 300.0        # a CEILING, never the budget

# Thresholds, set well below the measured figures so an ordinary solver tie
# cannot move them, and well above zero so a model that stops binding fails.
MIN_OPS_MODELED = 300           # measured 404
MIN_TARDINESS_BUCKETS = 50      # measured 123
MIN_BINDING_CELLS = 3           # measured 9
MIN_PEAK_UTILIZATION = 0.95     # measured 0.998


@pytest.fixture(scope="module")
def plant200(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant
    d = tmp_path_factory.mktemp("coarse200")
    generate(d / "sub", scenario="pilot_scale", orders=ORDERS, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


@pytest.fixture(scope="module")
def view200(plant200):
    from mre.modules.rolling_horizon import build_rolling_view
    v = build_rolling_view(plant200, window_days=WINDOW_DAYS,
                           frozen_days=FROZEN_DAYS, gravity=True,
                           deterministic=True, seed=42,
                           member_time_limit_s=600.0, det_total=DET_TOTAL)
    assert not v.wall_truncated, (
        "the window solve hit the WALL ceiling — this whole file would be "
        "measuring a lottery")
    return v


def _zone(plant, view, rho):
    return build_coarse_zone(
        plant, view, coefficients=CoarseCoefficients(7, rho, True, True),
        deterministic=True, seed=42, det_time=DET_TIME,
        safety_ceiling_s=SAFETY_CEILING_S)


@pytest.fixture(scope="module")
def zone_full(plant200, view200):
    return _zone(plant200, view200, 1.0)


def _peak_utilization(run) -> float:
    return max([run.density.get(k, 0) / v
                for k, v in run.capacity.items() if v > 0] or [0.0])


@pytest.mark.slow
def test_the_population_is_large_enough_to_bind(view200, zone_full):
    """A binding test over a light plant proves nothing. The population is
    asserted first, and printed, so a future generator change that thins the
    tray fails HERE rather than turning every assertion below into a tautology."""
    run = zone_full.planning
    n_scope = run.n_ops_modeled + len(run.unmodelable)
    assert len(view200.beyond_demand_ids) >= 100
    assert run.n_ops_modeled >= MIN_OPS_MODELED, (
        f"only {run.n_ops_modeled} ops modeled — too few for the capacity "
        f"constraints to be doing anything")
    assert not run.wall_truncated
    print(f"\n[4B.6a CU3] 200 orders: beyond-horizon demands="
          f"{len(view200.beyond_demand_ids)} coarse ops={n_scope} "
          f"modeled={run.n_ops_modeled} unmodelable={len(run.unmodelable)} "
          f"status={run.status}")


@pytest.mark.slow
def test_machine_weeks_actually_reach_capacity(zone_full):
    """CELLS REACH CAPACITY. At demo density the peak cell sits around 40% and
    the capacity constraint never binds; here it does, and the binding list —
    the raw material for "why is week N full?" — is non-empty."""
    run = zone_full.planning
    peak = _peak_utilization(run)
    assert peak >= MIN_PEAK_UTILIZATION, (
        f"peak machine-week utilization is only {peak:.3f} — no cell is near "
        f"capacity, so the coarse model's capacity constraints are not binding "
        f"and this suite would pass with them removed")
    assert len(run.binding) >= MIN_BINDING_CELLS, (
        f"only {len(run.binding)} cell(s) at or above the "
        f"{BINDING_UTILIZATION:g} reporting threshold")
    for (rid, wk, load, cap) in run.binding:
        assert cap > 0 and load >= BINDING_UTILIZATION * cap
    print(f"\n[4B.6a CU3] peak utilization={peak:.3f} "
          f"binding cells={len(run.binding)}")


@pytest.mark.slow
def test_the_boundary_stops_being_free(zone_full):
    """BUCKET TARDINESS IS NONZERO. The objective exists to stop the horizon
    boundary being free; at demo density it is 0 and the objective is inert."""
    run = zone_full.planning
    total = sum(run.demand_tardiness_buckets.values())
    assert total >= MIN_TARDINESS_BUCKETS, (
        f"total coarse tardiness is {total} bucket(s) — the objective is inert "
        f"at this density and nothing pins that it works")
    assert all(v > 0 for v in run.demand_tardiness_buckets.values()), (
        "a zero tardiness was recorded as a tardiness entry")
    print(f"\n[4B.6a CU3] coarse tardiness={total} buckets over "
          f"{len(run.demand_tardiness_buckets)} demand(s); status={run.status} "
          f"(upper bounds={run.status == 'FEASIBLE'})")


@pytest.mark.slow
def test_a_half_derate_is_infeasible_on_aggregate_capacity(plant200, view200,
                                                           zone_full):
    """rho = 0.5 GOES INFEASIBLE — and for the right reason. The op population
    is UNCHANGED at that derate, so the refutation is about aggregate capacity
    rather than about ops quietly leaving the model as unmodelable (which is the
    non-monotonicity below, a different phenomenon).

    And it proves NOTHING (clause 2): a planning run's INFEASIBLE is planning
    signal, never a refutation of the fine model."""
    z = _zone(plant200, view200, 0.5)
    assert z.planning.status == "INFEASIBLE", (
        f"rho = 0.5 returned {z.planning.status} on a plant where the proof run "
        f"places the book — the derate has stopped tightening the model")
    assert z.planning.n_ops_modeled == zone_full.planning.n_ops_modeled, (
        "ops left the model at rho = 0.5, so the INFEASIBLE is about the "
        "leftovers rather than about aggregate capacity")
    assert not z.planning.wall_truncated
    assert not z.planning.proves_infeasible, (
        "a PLANNING run claimed to prove infeasibility — clause (2) violated")
    assert z.proof.placed, "the proof run must still place this book at rho = 1.0"
    print(f"\n[4B.6a CU3] rho=0.5: planning={z.planning.status} "
          f"modeled={z.planning.n_ops_modeled} proof={z.proof.status}")


@pytest.mark.slow
def test_the_non_monotonicity_mechanism_still_holds_at_this_density(plant200,
                                                                    view200):
    """The measured non-monotonicity, re-checked where the model binds.

    STATED PRECISELY, because it does not carry over whole. At 40 orders the
    STATUS ladder reads OPTIMAL / INFEASIBLE / OPTIMAL across rho 0.20 / 0.15 /
    0.10 — the plant is light enough that dropping ops out of the model can make
    the remainder satisfiable again. At 200 orders all three are INFEASIBLE: the
    book is far too heavy for the leftovers to fit either.

    What the 40-order test actually PINS is the MECHANISM, and both of its
    assertions hold here: rho 0.15 is INFEASIBLE, and lowering rho to 0.10
    pushes MORE ops out as ``exceeds_bucket_capacity``. That is why the
    unmodelable set is NAMED and COUNTED rather than silently dropped — without
    the count, a model that has quietly shed a quarter of its work reads as a
    model that fits."""
    seen = {}
    for rho in (0.15, 0.10):
        z = _zone(plant200, view200, rho)
        seen[rho] = (z.planning.status, z.planning.n_ops_modeled,
                     sum(1 for u in z.planning.unmodelable
                         if u.reason == "exceeds_bucket_capacity"),
                     z.planning.wall_truncated)
    print(f"\n[4B.6a CU3] rho ladder at 200 orders "
          f"(status, modeled, exceeds_bucket, truncated): {seen}")
    assert seen[0.15][0] == "INFEASIBLE"
    assert not seen[0.15][3] and not seen[0.10][3]
    assert seen[0.10][2] > seen[0.15][2], (
        "the lower rho did not push more ops out as unmodelable — the "
        "non-monotonicity explanation no longer holds and must be re-derived")
