"""Session 4B.2 — rolling-horizon runner (R-SC2) regression tests.

Fast units cover the pure pieces (duration parsing, gravity admission reasons).
The slow ladder proves the two guarantees the ruling turns on:
  * the roll converges and its committed schedule prices out (decomposing);
  * GRAVITY BOUGHT SOMETHING — a monster job whose must-start precedes its
    due-window finishes on time WITH admission and goes tardy WITHOUT it
    (the price-bought-something rule applied to look-ahead).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.rolling_horizon import (
    prepare_plant, run_rolling_horizon, parse_iso_duration_minutes,
    _admit, _latest_feasible_start, _dt)

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# fast units
# ---------------------------------------------------------------------------

def test_parse_iso_duration_minutes():
    assert parse_iso_duration_minutes("PT1H45M") == 105
    assert parse_iso_duration_minutes("PT30M") == 30
    assert parse_iso_duration_minutes("PT2H") == 120
    assert parse_iso_duration_minutes("") == 0
    assert parse_iso_duration_minutes(None) == 0


@pytest.fixture(scope="module")
def small_plant(tmp_path_factory):
    from generate_erp_dataset import generate
    d = tmp_path_factory.mktemp("pilot_small")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


def test_prepare_plant_loads_canonical(small_plant):
    assert len(small_plant.schedulable_demands) > 30
    assert len(small_plant.operations) > len(small_plant.schedulable_demands)
    assert len(small_plant.resources) == 15
    assert small_plant.priority_multipliers.get("critical", 0) > \
        small_plant.priority_multipliers.get("standard", 0)


def test_gravity_admits_more_than_base(small_plant):
    p = small_plant
    ws, we = REF, REF.replace(day=9)   # a 4-day window
    base_only, _ = _admit(p, p.schedulable_demands, ws, we, gravity=False, crit_threshold=3.0)
    with_grav, reasons = _admit(p, p.schedulable_demands, ws, we, gravity=True, crit_threshold=3.0)
    # gravity is a superset of base, and reports which pull admitted each extra
    assert base_only <= with_grav
    assert reasons["base"] == len(base_only)
    assert sum(reasons.values()) == len(with_grav)


def test_latest_feasible_start_precedes_due(small_plant):
    p = small_plant
    for d in p.schedulable_demands[:5]:
        assert _latest_feasible_start(p, d) <= _dt(d["due"])


# ---------------------------------------------------------------------------
# slow — the roll converges and prices out
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_roll_converges_and_prices(small_plant):
    r = run_rolling_horizon(small_plant, window_days=4, frozen_days=2,
                            gravity=True, deterministic=True, seed=0,
                            member_time_limit_s=6.0)
    # every operation ends up committed (rolling front + final resolve)
    assert len(r.committed_ops) == len(small_plant.operations)
    assert r.total_cost is not None and r.total_cost > 0
    # the ledger decomposes exactly (production + setup + tardiness == total)
    led = r.cost_ledger
    parts = (led.get("production_cost", 0) + led.get("setup_cost", 0)
             + led.get("tardiness_cost", 0) + led.get("sunk_setup_cost", 0))
    assert abs(parts - led["total_cost"]) < 1.0
    assert r.on_time + r.late == len(r.service_outcomes)


# ---------------------------------------------------------------------------
# slow — GRAVITY BOUGHT SOMETHING (the price-bought-something counterfactual)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_gravity_counterfactual(tmp_path):
    from pilot_measurements import write_gravity_submission
    sub = tmp_path / "gravity"
    write_gravity_submission(sub, chain_len=8, op_minutes=600, due_day=12)

    p_on = prepare_plant(sub, tmp_path / "on", reference_date=REF)
    r_on = run_rolling_horizon(p_on, window_days=6, frozen_days=2, gravity=True,
                               deterministic=True, seed=0, member_time_limit_s=8.0)
    p_off = prepare_plant(sub, tmp_path / "off", reference_date=REF)
    r_off = run_rolling_horizon(p_off, window_days=6, frozen_days=2, gravity=False,
                                deterministic=True, seed=0, member_time_limit_s=8.0)

    # WITH gravity the monster is admitted early (must-start-by pull) and lands
    # on time; WITHOUT it the monster is admitted only when its due enters the
    # window, starts too late, and goes tardy. Gravity must reduce tardiness.
    assert r_off.total_tardiness_minutes > r_on.total_tardiness_minutes
    assert r_on.late < r_off.late
    assert r_on.total_tardiness_minutes == 0
