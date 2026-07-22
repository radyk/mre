"""Session 4B.2 — rolling-horizon runner (R-SC2) regression tests.

Fast units cover the pure pieces (duration parsing, gravity admission reasons).
The slow ladder proves the two guarantees the ruling turns on:
  * the roll converges and its committed schedule prices out (decomposing);
  * GRAVITY BOUGHT SOMETHING — a monster job whose must-start precedes its
    due-window finishes on time WITH admission and goes tardy WITHOUT it
    (the price-bought-something rule applied to look-ahead).
"""
from __future__ import annotations

import json
import os
import subprocess
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
GOLDEN = Path(__file__).parent / "fixtures" / "baselines" / "rolling_pilot_golden.json"


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


def test_manned_idle_metric_matches_hand_computation():
    """CU5 (R-SC3): per-resource manned-idle = calendar-open (to the last
    committed placement) minus busy. Hand-checked on a two-machine one-day fixture:
    ref Mon 2026-01-05, shift 07:00-19:00; op1 fills R1 07:00-11:00 (240 min), op2
    runs R2 07:00-08:00 (60 min). sched_end = 11:00 => open window per machine is
    240 min; R1 idle 0, R2 idle 180."""
    from mre.modules.rolling_horizon import compute_manned_idle_metrics
    from datetime import timedelta
    ref = datetime(2026, 1, 5, tzinfo=timezone.utc)   # a Monday, midnight
    calendars = [{"id": "CAL", "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
                  "shift_start": "07:00", "shift_end": "19:00"}, "exceptions": []}]
    resources = [{"id": "R1", "calendar_ref": "CAL"},
                 {"id": "R2", "calendar_ref": "CAL"}]

    def iso(h, m=0):
        return (ref + timedelta(hours=h, minutes=m)).isoformat()
    committed = {
        "op1": {"resource": "R1", "start": iso(7), "end": iso(11)},   # 240 min
        "op2": {"resource": "R2", "start": iso(7), "end": iso(8)},    # 60 min
    }
    metrics = compute_manned_idle_metrics(resources, calendars, committed, ref,
                                          ref + timedelta(days=2))
    by_res = {m["resource_id"]: m for m in metrics}
    assert by_res["R1"]["calendar_open_minutes"] == 240
    assert by_res["R1"]["busy_minutes"] == 240
    assert by_res["R1"]["manned_idle_minutes"] == 0
    assert by_res["R2"]["calendar_open_minutes"] == 240
    assert by_res["R2"]["busy_minutes"] == 60
    assert by_res["R2"]["manned_idle_minutes"] == 180


# ---------------------------------------------------------------------------
# CU4 (4B.2c) — the untested rolling mechanisms (audit Q7).
#   (a) frozen-front commit: ops STARTING inside the frozen zone commit this
#       roll; ops outside do NOT (assert the split, not eventual commitment).
#   (b) absolute origin: a committed op is fixed in the past for later windows,
#       never re-placed, and NO pin RECORDS are minted (frozen commit is a bare
#       placement, not an R-DP8 standing-pin Decision).
#   (c) deterministic budget: covered by CU3 (test_rolling_determinism_*).
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_frozen_front_commit_splits_inside_from_outside(small_plant):
    """(a) In every solved window, EXACTLY the ops whose solved start falls
    inside [t0, frozen_end) are committed this window; ops starting at/after
    frozen_end are NOT committed this window. At least one window must exhibit
    the split (both an inside and an outside op) so the assertion has teeth."""
    windows = []
    run_rolling_horizon(small_plant, window_days=7, frozen_days=2, gravity=True,
                        deterministic=True, seed=42, member_time_limit_s=8.0,
                        window_observer=lambda b: windows.append(b))

    saw_split = False
    for w in windows:
        if w["solve_status"] not in ("OPTIMAL", "FEASIBLE"):
            continue
        fe = w["frozen_end_min"]
        committed_this = set(w["committed_this_ids"])
        inside = {oid for oid, s in w["win_starts"].items() if s < fe}
        outside = {oid for oid, s in w["win_starts"].items() if s >= fe}
        # the commit set is EXACTLY the inside set (op-level frozen front)
        assert committed_this == inside, (
            f"window {w['index']}: committed-this != inside-frozen-zone "
            f"(extra={committed_this - inside}, missing={inside - committed_this})")
        # nothing outside the frozen zone was committed this window
        assert not (committed_this & outside)
        if inside and outside:
            saw_split = True
    assert saw_split, "no window exhibited both an inside and an outside op"


@pytest.mark.slow
def test_absolute_origin_no_replacement_no_pin_records(small_plant, monkeypatch):
    """(b) A committed op is never re-placed in a later window, a committed op
    fully in the past never re-enters as free work, and NO external standing-pin
    machinery is invoked (the frozen commit mints no pin RECORDS)."""
    from mre.modules import standing_pins as sp

    # spy: the external-pin / record-minting entry points must never fire during
    # a plain roll (standing_pins=None). apply_pin (an in-model CONSTRAINT on a
    # carried commitment) is allowed; apply_standing_pins / normalize_pin /
    # compose_lineage_pins (which carry or mint PERSISTED pins) must not be.
    calls = {"apply_standing_pins": 0, "normalize_pin": 0, "compose_lineage_pins": 0}
    for name in list(calls):
        if hasattr(sp, name):
            orig = getattr(sp, name)
            def _wrap(*a, _n=name, _o=orig, **k):
                calls[_n] += 1
                return _o(*a, **k)
            monkeypatch.setattr(sp, name, _wrap)

    windows = []
    r = run_rolling_horizon(small_plant, window_days=7, frozen_days=2, gravity=True,
                            deterministic=True, seed=42, member_time_limit_s=8.0,
                            window_observer=lambda b: windows.append(b))

    # no persisted-pin machinery fired
    assert calls == {"apply_standing_pins": 0, "normalize_pin": 0,
                     "compose_lineage_pins": 0}, calls

    # a committed op is never re-placed, and never re-enters as free work
    placement_seen: dict = {}
    for w in windows:
        free_ids = {op["id"] for op in w["free_ops"]}
        for oid, c in w["committed"].items():   # committed BEFORE this window
            assert oid not in free_ids, f"committed op {oid} re-entered as free work"
            key = (c["resource"], c["start"], c["end"])
            if oid in placement_seen:
                assert placement_seen[oid] == key, (
                    f"committed op {oid} was RE-PLACED: "
                    f"{placement_seen[oid]} -> {key}")
            placement_seen[oid] = key

    # the frozen commit is a bare PLACEMENT (no authority/basis/decision_type —
    # not an R-DP8 pin Decision record)
    for oid, c in r.committed_ops.items():
        assert set(c.keys()) <= {"resource", "start", "end"}, c


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
# CU3 (4B.2c) — the rolling-horizon DETERMINISM golden.
#
# Fast smoke: two IN-PROCESS rolls of a truncated horizon agree bit-for-bit
# (intra-run determinism). Slow golden: two SUBPROCESS rolls (PYTHONHASHSEED=0 +
# workers 1 + fixed seed + det-time budget) agree with each other AND with a
# COMMITTED golden — so a future session detects DRIFT, not just intra-run
# nondeterminism. Mirrors test_defaults_reproduce_baseline's subprocess pattern.
# ---------------------------------------------------------------------------

def test_rolling_determinism_smoke():
    """Fast: a truncated roll is bit-identical across two in-process runs."""
    from rolling_golden import run
    a = run(orders=8, window=4, frozen=2, det_time=0.2, seed=42, max_windows=2)
    b = run(orders=8, window=4, frozen=2, det_time=0.2, seed=42, max_windows=2)
    assert a["schedule_digest"] == b["schedule_digest"]
    assert a["total_cost"] == b["total_cost"]
    assert a["n_committed"] == b["n_committed"]


def _run_golden_driver() -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "rolling_golden.py"),
         "--orders", "24", "--window", "7", "--frozen", "3",
         "--det-time", "0.5", "--seed", "42"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"driver failed:\n{proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_rolling_determinism_golden():
    """Slow: two deterministic subprocess rolls agree with each other and with
    the committed golden (schedule digest + cost ledger). Detects drift."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    run1 = _run_golden_driver()
    run2 = _run_golden_driver()
    assert run1 == run2, "two deterministic subprocess rolls diverged"
    # compare against the committed golden, key by key (clearer diff than ==)
    for k in ("schedule_digest", "n_committed", "on_time", "late",
              "total_cost", "production_cost", "setup_cost", "tardiness_cost"):
        assert run1[k] == golden[k], (
            f"rolling golden DRIFT on {k}: got {run1[k]!r}, golden {golden[k]!r}. "
            f"If intentional (ortools/solver change), regenerate via "
            f"tools/rolling_golden.py and re-commit the fixture.")


# ---------------------------------------------------------------------------
# slow — CU4 (R-SC3): the FLOOR is cost-neutral; PAID earliness buys what it says.
#
# R-SC3 replaced the 4B.2 hidden weight-1/min incentive with a two-stage solve:
# stage 1 minimizes cost (+ priced earliness at the declared earliness_value);
# stage 2 caps the stage-1 objective and re-minimizes op-start earliness (the
# zero-cost lexicographic tiebreak). These tests flip 4B.2c's xfail into two hard
# passes, measured on a small pilot MONOLITH where cost-invariance of the FLOOR is
# PROVABLE (a single solve capping cost at its optimum can only reshuffle starts,
# never change cost — unlike a rolling roll, whose frozen choices propagate).
#
# (a) coefficient = 0 — the FLOOR is placement-neutral IN MONEY: two-stage vs a
#     plain cost-only solve (stage 1 only) have IDENTICAL Extractor-ledger costs
#     (epsilon 0, not 1%); any placement delta is earlier-at-equal-cost only.
#     This is 4B.2c's assertion (c) finally passing — the corrected, honest claim.
# (b) coefficient > 0 (the pilot_scale demo value) — PAID earliness bought what it
#     says: (i) total earliness-minutes strictly improve; (ii) the cost increase is
#     <= earliness_value x earliness-minutes-gained (bounded by construction:
#     stage 1 minimizes cost + coeff*earliness, so any accepted (cost, earliness)
#     obeys cost + coeff*earliness <= the coeff=0 pair's — rearranged, the bound);
#     (iii) >=1 purchased placement's Decision cites the CU3 EARLINESS_PREFERENCE
#     driver.
#
# MEASURED (Session 4B.2d, 8-order pilot monolith, seed 42, PYTHONHASHSEED=0, demo
# earliness_value 0.05 $/min): (a) cost-only == floor == $5,719.83 to the cent
# (production 4,999.83 / setup 720 / tardiness 0, all identical); the floor's
# start-sum falls 36,544 -> 23,549 min (earlier, free). (b) demo total $5,753.43 =
# +$33.60; start-sum 23,549 -> 16,452 (gained 7,097 min); 33.60 <= 0.05*7097 =
# 354.85; 2 placements cite EARLINESS_PREFERENCE.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tiny_plant(tmp_path_factory):
    """An 8-order pilot_scale plant — small enough to solve as ONE monolith (no
    rolling), so the FLOOR's cost-invariance is provable, not merely bounded."""
    from generate_erp_dataset import generate
    d = tmp_path_factory.mktemp("pilot_tiny")
    generate(d / "sub", scenario="pilot_scale", orders=8, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


def _start_minutes_sum(placements) -> int:
    return sum(int((_dt(c["start"]) - REF).total_seconds() / 60)
              for c in placements.values())


@pytest.mark.slow
def test_earliness_floor_is_placement_neutral_in_money(tiny_plant):
    """(a): coefficient 0 — the two-stage FLOOR and a plain cost-only solve have
    IDENTICAL ledger costs (epsilon 0); placement deltas are earlier-at-equal-cost
    only. 4B.2c's assertion (c), corrected and passing."""
    from mre.modules.rolling_horizon import reference_solve

    led_cost, _, _, tot_cost, pl_cost = reference_solve(
        tiny_plant, earliness_value=0.0, two_stage=False, seed=42, det_time=4.0)
    led_floor, _, _, tot_floor, pl_floor = reference_solve(
        tiny_plant, earliness_value=0.0, two_stage=True, seed=42, det_time=4.0)

    assert abs(tot_cost - tot_floor) < 1e-6, (
        f"floor moved total cost: cost-only={tot_cost:.4f} floor={tot_floor:.4f}")
    for line in ("production_cost", "setup_cost", "tardiness_cost"):
        assert abs(led_cost.get(line, 0.0) - led_floor.get(line, 0.0)) < 1e-6, (
            f"floor changed priced line {line}: "
            f"{led_cost.get(line)} vs {led_floor.get(line)}")
    # any placement delta is earlier-at-equal-cost only (never later on net).
    assert _start_minutes_sum(pl_floor) <= _start_minutes_sum(pl_cost)


@pytest.mark.slow
def test_earliness_coefficient_bought_earliness(tiny_plant):
    """(b): coefficient > 0 (the demo value) — paid earliness bought what it says:
    (i) earliness-minutes strictly improve, (ii) the cost increase is bounded by
    coeff x earliness-minutes-gained, (iii) >=1 placement cites the driver."""
    from mre.contracts.vocabularies import DriverCode
    from mre.modules.rolling_horizon import reference_solve

    coeff = float(tiny_plant.cost_model.get("earliness_value", 0.0))
    assert coeff > 0, "pilot_scale must declare a positive demo earliness_value"

    _, _, _, tot_off, pl_off = reference_solve(
        tiny_plant, earliness_value=0.0, two_stage=True, seed=42, det_time=4.0)
    _, _, drivers_on, tot_on, pl_on = reference_solve(
        tiny_plant, earliness_value=None, two_stage=True, seed=42, det_time=4.0)

    gained = _start_minutes_sum(pl_off) - _start_minutes_sum(pl_on)
    # (i) earliness-minutes strictly improve — the price bought something.
    assert gained > 0, f"paid earliness did not improve start-sum (gained={gained})"
    # (ii) the cost increase is at most coeff x earliness-minutes-gained.
    cost_increase = tot_on - tot_off
    assert cost_increase <= coeff * gained + 1e-6, (
        f"cost increase {cost_increase:.2f} exceeds coeff*gained "
        f"{coeff * gained:.2f} (coeff={coeff}, gained={gained})")
    # (iii) at least one purchased placement is attributed to the driver.
    purchased = [oid for oid, d in drivers_on.items()
                 if d == DriverCode.EARLINESS_PREFERENCE.value]
    assert purchased, "no placement cited EARLINESS_PREFERENCE (raise the demo value)"


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
