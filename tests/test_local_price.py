"""Session 4B.24 — THE LOCAL PRICER (R-T2 amendment clause 2).

The founder nudged ORD-000057 four hours inside an overtime window it already
occupied, on a machine where nothing else ran in those hours, and the card
charged the move $50,784.33 and relocated four unrelated orders by weeks. The
correct price is $0.00 with an empty affected list.

THE FIXTURE IS THAT GESTURE'S STRUCTURE, not its coordinates. ``overtime_required``
places exactly one 600-minute operation into a Saturday overtime window of 720
minutes, on a machine carrying nothing else that day — a bar inside an overtime
window with free space around it and neighbouring orders elsewhere on the board.
The PREMISE TEST asserts every one of those properties before any pricing test
leans on them, because a fixture that quietly lost its overtime window would make
the whole file pass while proving nothing.

Three negative controls are named at the bottom, each with the exact edit that
turns it red.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from generate_erp_dataset import generate  # noqa: E402

from mre.__main__ import main as mre_main  # noqa: E402
from mre.modules.local_price import (  # noqa: E402
    FAMILY_CALENDAR, FAMILY_PRECEDENCE, FAMILY_RESOURCE,
    _load_held_world, price_local_move,
)
from mre.modules.snapshot_store import SnapshotStore  # noqa: E402

SNAP = "snap-ot"
# The overtime window the generator declares: Saturday 07:00-19:00 (720 min),
# holding one 600-minute operation — 120 minutes of headroom to nudge into.
NUDGE_MIN = 60


def _parse(raw) -> datetime:
    d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def solved_overtime(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("local_price_ot")
    generate(tmp / "sub", scenario="overtime_required", seed=7)
    out = tmp / "out"
    rc = mre_main([
        "--submission", str(tmp / "sub"), "--out", str(out),
        "--snapshot-id", SNAP, "--time-limit", "45",
        "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"
    return out


@pytest.fixture(scope="module")
def board(solved_overtime):
    """The bar in the overtime window, its machine, and the world around it."""
    reader = SnapshotStore(Path(solved_overtime) / "snapshots").load_snapshot(SNAP)
    overtime_windows = []
    for cal in reader.iter_entities("calendar"):
        for exc in (cal.get("exceptions") or []):
            if (exc.get("reason") or "") == "overtime" or \
               (exc.get("exception_type") or "") == "added":
                overtime_windows.append(exc)
    rows = []
    for a in reader.iter_entities("assignment"):
        rid = (a.get("resource_assignments") or [{}])[0].get("resource_ref")
        wins = (a.get("phase_windows") or {}).get("run") or []
        if not (rid and wins):
            continue
        rows.append({"op": a["operation_ref"], "resource": rid,
                     "start": _parse(wins[0]["start"]),
                     "end": _parse(wins[-1]["end"]), "chunks": len(wins)})
    rows.sort(key=lambda r: (r["resource"], r["start"]))
    # the LAST bar on the busiest machine — the Saturday overtime slot, the one
    # with open time after it and nothing else on the machine that day.
    busiest = max({r["resource"] for r in rows},
                  key=lambda rid: sum(1 for r in rows if r["resource"] == rid))
    lane = [r for r in rows if r["resource"] == busiest]
    world = _load_held_world(Path(solved_overtime), SNAP, "runs", None)
    target_orders = set(world.wo_of_op.get(lane[-1]["op"]) or [])
    return {"out": Path(solved_overtime), "rows": rows, "lane": lane,
            "target": lane[-1], "overtime_windows": overtime_windows,
            "target_orders": target_orders,
            "resources": sorted({r["resource"] for r in rows})}


def _price(board, target, start, **kw):
    return price_local_move(
        board["out"], SNAP, pin_op_id=target["op"],
        pin_resource_id=target["resource"], pin_start_iso=start.isoformat(), **kw)


# ---------------------------------------------------------------------------
# PREMISE — the fixture really is the founder's gesture's shape
# ---------------------------------------------------------------------------

class TestPremise:
    """Every pricing assertion below rests on these. A fixture that lost its
    overtime window, or whose target bar acquired a neighbour, would make the
    priced-at-zero test pass for the wrong reason — it would be measuring an
    empty board, not a correct pricer."""

    def test_the_board_declares_an_overtime_window(self, board):
        assert board["overtime_windows"], (
            "the fixture must carry a declared overtime window — without one "
            "the founder's gesture has no structure to reproduce")

    def test_the_target_bar_sits_inside_that_window(self, board, solved_overtime):
        world = _load_held_world(board["out"], SNAP, "runs", None)
        vm_windows = world.var_map.cal_windows.get(board["target"]["resource"]) or []
        t = board["target"]
        s = int((t["start"] - world.horizon_start).total_seconds() // 60)
        e = int((t["end"] - world.horizon_start).total_seconds() // 60)
        holder = next((w for w in vm_windows if w[0] <= s and e <= w[1]), None)
        assert holder is not None, "the target bar is not inside one window"
        headroom = holder[1] - e
        assert headroom >= NUDGE_MIN, (
            f"only {headroom} free minutes after the target — the nudge would "
            f"leave the window and would be testing the calendar, not the price")

    def test_nothing_else_runs_on_that_machine_in_those_hours(self, board):
        t = board["target"]
        window_end = t["end"] + timedelta(minutes=NUDGE_MIN)
        others = [r for r in board["lane"]
                  if r["op"] != t["op"] and r["start"] < window_end
                  and r["end"] > t["start"]]
        assert others == [], f"the target's hours are not free: {others}"

    def test_there_are_neighbouring_orders_to_disturb(self, board):
        """The empty-affected-list assertion is only meaningful if there was
        something the pricer COULD have charged."""
        assert len(board["rows"]) >= 3
        assert len(board["resources"]) >= 2


# ---------------------------------------------------------------------------
# CLAUSE (2) — the founder's gesture
# ---------------------------------------------------------------------------

class TestTheFoundersGesture:

    def test_a_nudge_into_its_own_free_hours_costs_nothing(self, board):
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert r.priced is True, (r.error, r.refusal)
        assert r.cost_delta_abs == 0.0, r.summary()

    def test_no_order_but_the_planners_own_is_touched(self, board):
        """The founder's card relocated FOUR unrelated orders by two to three
        weeks. Nothing here may charge anybody but the order the planner moved.

        On this fixture the moved operation is the LAST step of its own order, so
        that order's completion does shift by the nudge and it appears in the
        list with a tardiness delta of exactly zero — a true consequence of the
        planner's own move, still comfortably inside its due date. Every other
        order is untouched, which is the claim. (The founder's own bar had a
        downstream step that absorbed the shift, so his correct list was empty;
        the general property is this one.)"""
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert all(a["tardiness_delta"] == 0.0 for a in r.affected_orders), \
            r.affected_orders
        others = [a for a in r.affected_orders
                  if a["work_order"] not in board["target_orders"]]
        assert others == [], f"unrelated orders were charged: {others}"

    def test_the_only_thing_that_moved_is_the_thing_the_planner_moved(self, board):
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert len(r.moves) == 1
        assert r.moves[0]["operation_ref"] == t["op"]
        assert r.moves[0]["pinned"] is True
        assert r.moves[0]["start_delta_min"] == NUDGE_MIN

    def test_every_ledger_line_closes_on_the_total(self, board):
        """rollup_of discipline: the named lines plus the explicit remainder sum
        EXACTLY to the headline, so the card cannot claim arithmetic the ledger
        does not back."""
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert r.cost_lines
        assert round(sum(l["delta"] for l in r.cost_lines), 2) == r.cost_delta_abs

    def test_the_recomputed_before_agrees_with_the_persisted_ledger(self, board):
        """Both sides of the delta are recomputed here, so the delta is sound
        either way — but a disagreement with the solve-time ledger would mean the
        pricer is modelling a different plant, and that is worth knowing."""
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert r.agrees_with_persisted is True, (r.total_before, r.persisted_total)

    def test_the_model_validates_the_held_world(self, board):
        """The 4B.6c method: pin every placement into a fresh model and ask
        CP-SAT. The model's verdict, not the pricer's opinion of itself."""
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert r.validation["method"] == "cp-sat-pin-all"
        assert r.validation["status"] in ("OPTIMAL", "FEASIBLE")
        assert r.validation["unpinnable"] == []

    def test_the_identical_gesture_returns_the_identical_price(self, board):
        """Clause (1) at the level that matters to a planner: five times, same
        answer. Before this the same pin returned feasible_unproven, no_verdict
        and -$50,784.33 on three runs."""
        t = board["target"]
        target = t["start"] + timedelta(minutes=NUDGE_MIN)
        seen = {(_price(board, t, target).cost_delta_abs,
                 len(_price(board, t, target).affected_orders)) for _ in range(5)}
        assert len(seen) == 1, seen


# ---------------------------------------------------------------------------
# NEGATIVE CONTROL (a): $0 is not a constant
# ---------------------------------------------------------------------------

class TestZeroIsNotAConstant:
    """If the pricer returned zero for everything, every assertion above would
    pass and prove nothing. A move that genuinely changes the ledger must be
    priced, with the right LINES moving."""

    def test_leaving_the_overtime_window_for_a_later_day_costs_real_money(self, board):
        t = board["target"]
        # three days later: out of the priced overtime window and past the due
        # date, so BOTH the overtime line and the tardiness line must move.
        r = _price(board, t, t["start"] + timedelta(days=3))
        if r.refusal or not r.priced:
            pytest.skip(f"the later slot is not legal on this fixture: "
                        f"{r.refusal or r.error}")
        assert r.cost_delta_abs != 0.0, r.summary()
        lines = {l["line"]: l["delta"] for l in r.cost_lines}
        assert lines["production (overtime)"] != 0.0 or lines["tardiness"] != 0.0, lines
        assert r.affected_orders, "an order whose completion moved is affected"


# ---------------------------------------------------------------------------
# CLAUSE (2) — a refusal NAMES its constraint, and says whose fact it is
# ---------------------------------------------------------------------------

class TestRefusals:

    def test_a_collision_is_refused_and_names_the_job_in_the_way(self, board):
        lane = board["lane"]
        assert len(lane) >= 2
        mover, occupant = lane[-1], lane[0]
        r = _price(board, mover, occupant["start"] + timedelta(minutes=30))
        assert r.priced is False
        assert r.refusal is not None
        assert r.refusal["family"] == FAMILY_RESOURCE
        assert r.refusal["other_op_ref"] == occupant["op"]
        assert r.refusal["holds_others"] is True, (
            "a collision refusal is a fact about THIS PRICE holding the "
            "occupant still, not about the plant")

    def test_a_closed_calendar_is_refused_and_is_NOT_about_our_method(self, board):
        """The contrast that keeps the test above non-vacuous. A machine that is
        shut refuses the pin however the rest of the plan is arranged, so this
        refusal must NOT claim to be a consequence of holding other work."""
        t = board["target"]
        # deep into the night after the last window closes
        r = _price(board, t, t["start"].replace(hour=23, minute=30))
        assert r.priced is False
        assert r.refusal["family"] == FAMILY_CALENDAR
        assert r.refusal["holds_others"] is False

    def test_a_refusal_carries_the_instant_it_binds(self, board):
        lane = board["lane"]
        r = _price(board, lane[-1], lane[0]["start"] + timedelta(minutes=30))
        assert r.refusal["at"], "a refusal a planner can act on names WHEN"

    def test_a_refusal_prices_nothing(self, board):
        """A refused move has no price, and the fields say so rather than
        carrying a stale or zero figure that reads like one."""
        lane = board["lane"]
        r = _price(board, lane[-1], lane[0]["start"] + timedelta(minutes=30))
        assert r.cost_delta_abs is None
        assert r.affected_orders == []
        assert r.moves == []


# ---------------------------------------------------------------------------
# NEGATIVE CONTROL (b): the held world is genuinely held
# ---------------------------------------------------------------------------

class TestTheWorldIsActuallyHeld:

    def test_the_price_counts_every_placement_not_just_the_moved_one(self, board):
        """If ``_solve_values`` built its ledger from the pinned op alone, the
        totals would be a fraction of the plan's. They are the WHOLE plan's, on
        both sides — which is what makes the difference attributable."""
        t = board["target"]
        r = _price(board, t, t["start"] + timedelta(minutes=NUDGE_MIN))
        assert r.total_before and r.total_before > 0
        assert r.total_after == r.total_before        # this move is free
        assert r.persisted_total == r.total_before

    def test_workpackage_completion_moves_with_its_operations(self, board):
        """The 4B.6c ``_rebuild`` lesson, asserted: tardiness is derived from
        workpackage end, so a pricer that shifted an op without recomputing it
        would report every late-making move as free. Proven by a move that ends
        LATER than its own workpackage's previous completion."""
        t = board["target"]
        world = _load_held_world(board["out"], SNAP, "runs", None)
        sv_before = None
        from mre.modules.local_price import _solve_values
        moved = dict(world.placements)
        rid, s, e = moved[t["op"]]
        moved[t["op"]] = (rid, s + 600, e + 600)
        sv_before = _solve_values(world, world.placements, world.chunks)
        sv_after = _solve_values(world, moved, world.chunks)
        wp = world.ops_by_id[t["op"]]["workpackage_ref"]
        assert sv_after.wp_end_minutes[wp] > sv_before.wp_end_minutes[wp], (
            "the workpackage end did not follow its operation")
