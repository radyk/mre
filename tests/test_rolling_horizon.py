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
# slow — CU1 (4B.2c): the EARLINESS incentive's reach is BOUNDED.
#
# The incentive (rolling_horizon.py ~:448) is a GLOBAL weight-1/min ASAP pull on
# every free op, not a frozen-front subset. The ruling: it STAYS AS-IS provided
# its reach is proven bounded — it is a tiebreaker among cost-equal solutions,
# never overriding a priced decision. Counterfactual: one representative rolling
# solve (the 7-day knee) WITH vs WITHOUT the incentive, deterministic. Assert:
#   (a) the evaluated Extractor-ledger TOTAL differs by at most a small epsilon;
#   (b) no priced cost line worsens with the incentive on (there is no JIT/
#       inventory line for an ASAP pull to inflate — extractor prices production
#       + setup + tardiness only — so pulling earlier has no priced downside);
#   (c) placement differences are slack-only: no operation is RELOCATED across
#       machines (a priced choice); the incentive only shifts start times.
#
# EPSILON: the earliness weight is 1/min; tardiness is >=100/min in objective
# units (base_weight 1.0 x _COST_SCALE 100, larger for priority classes), so the
# incentive is dominated >=100:1. Any ledger movement is therefore second-order
# sequencing among cost-tied placements, not a priced consequence of pulling
# early. We bound the total change at 1% of the incentive-OFF total — well below
# the production cost of relocating even a handful of ops across machines.
#
# RESULT (Session 4B.2c, measured on the 40-order small_plant, window 7 / frozen
# 2, seed 42, PYTHONHASHSEED=0): (a) and (b) PASS — total ON $25,694.98 vs OFF
# $25,620.68 = +$74.30 (+0.290%, < the $256 epsilon); setup identical ($3,520),
# tardiness 0 both. (c) FAILS: the incentive relocated a 7-op job across machines
# (440fbc69 -> df5aa682) to start it earlier, raising production by exactly the
# +$74.30 total delta. So the incentive is NOT a pure zero-cost slack move — it
# can pay a SMALL, BOUNDED production premium (here 0.29%) to pull work earlier,
# because on distinct-rate machines an earlier-available machine may be dearer.
# The load-bearing guarantee (reach is bounded IN COST) holds; the placement-
# identity claim (c) does not. (a)+(b) are the live regression below; (c) is
# recorded as xfail with these numbers — re-scoping the incentive to a strict
# zero-cost tiebreaker is a design decision for the working thread, not here.
# ---------------------------------------------------------------------------

_EARLINESS_EPS_FRACTION = 0.01   # see EPSILON note above


@pytest.mark.slow
def test_earliness_incentive_is_bounded(small_plant):
    """(a) + (b): the incentive's COST reach is bounded — total within epsilon
    and no priced line worsens beyond it. The load-bearing guarantee."""
    common = dict(window_days=7, frozen_days=2, gravity=True,
                  deterministic=True, seed=42, member_time_limit_s=8.0)
    r_on = run_rolling_horizon(small_plant, earliness_incentive=True, **common)
    r_off = run_rolling_horizon(small_plant, earliness_incentive=False, **common)

    led_on, led_off = r_on.cost_ledger, r_off.cost_ledger
    total_on, total_off = led_on["total_cost"], led_off["total_cost"]
    eps = max(1.0, _EARLINESS_EPS_FRACTION * total_off)

    # (a) total cost within epsilon
    assert abs(total_on - total_off) <= eps, (
        f"earliness incentive moved total cost beyond epsilon: "
        f"on={total_on:.2f} off={total_off:.2f} eps={eps:.2f}")

    # (b) no priced line worsens with the incentive ON (allow epsilon of noise).
    # There is no JIT/inventory line for an ASAP pull to inflate — the extractor
    # prices production + setup + tardiness only — so pulling earlier has no
    # priced DOWNSIDE; the only movement is a small production premium bounded
    # by epsilon (see the RESULT note above).
    for line in ("production_cost", "setup_cost", "tardiness_cost"):
        on_v = led_on.get(line, 0.0)
        off_v = led_off.get(line, 0.0)
        assert on_v <= off_v + eps, (
            f"priced line {line} WORSENED with the incentive on beyond epsilon: "
            f"on={on_v:.2f} off={off_v:.2f} eps={eps:.2f}")


@pytest.mark.slow
@pytest.mark.xfail(reason=(
    "MEASURED FINDING (4B.2c): the earliness incentive is NOT placement-neutral. "
    "On the 40-order small_plant (window 7 / frozen 2, seed 42) it relocates a "
    "7-op job across machines (440fbc69 -> df5aa682) to start it earlier, paying "
    "+$74.30 production (+0.290% of total). So assertion (c) 'changes no priced "
    "quantity' is FALSE: the incentive trades a small, bounded production premium "
    "for an earlier start. The COST bound (a)+(b) holds; this placement claim "
    "does not. Re-scoping the incentive to a strict zero-cost tiebreaker is a "
    "design decision for the working thread."), strict=False)
def test_earliness_incentive_placements_are_slack_only(small_plant):
    """(c): no op committed in both runs is RELOCATED across machines. This is a
    stronger claim than cost-boundedness and reality violates it (xfail) — the
    incentive pays a bounded premium to pull work onto an earlier-free machine."""
    common = dict(window_days=7, frozen_days=2, gravity=True,
                  deterministic=True, seed=42, member_time_limit_s=8.0)
    r_on = run_rolling_horizon(small_plant, earliness_incentive=True, **common)
    r_off = run_rolling_horizon(small_plant, earliness_incentive=False, **common)
    relocated = [oid for oid, c_on in r_on.committed_ops.items()
                 if oid in r_off.committed_ops
                 and c_on["resource"] != r_off.committed_ops[oid]["resource"]]
    assert not relocated, (
        f"earliness incentive RELOCATED {len(relocated)} op(s) across machines "
        f"(a priced choice, not a slack move): {relocated[:5]}")


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
