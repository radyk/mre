"""THE LATER DIRECTION AS AN ANSWER (Session 4B.30 Items 1, 3, 4, 5).

The defect, measured twice live before this session and re-measured verbatim at
its head: "can i move ORD-000057 later, maintenance wants the machine for the
day" was answered with three ways to move the order EARLIER. Six of seven
direction-bearing phrasings returned one byte-identical paragraph.

These exercise the assembled route end to end over a purpose-built world that
CONTAINS, on purpose, every obstacle a later move meets on a real board:

  * a COLLISION — another order parked on the same machine the day after
  * a DECLARED CLOSURE — a maintenance Wednesday, so "shut" can be told apart
    from "busy"
  * a CHUNKED operation — two pieces around a closure, which the local pricer
    declines by name
  * a COMMITTED front and a PIN — R-F1 and A7/F1, asserted rather than assumed
    unreachable

WHAT IS AND IS NOT UNDER TEST HERE (the stated limit). The PRICER is not: it has
its own guards (``tests/test_local_price.py``, 4B.24) and it needs a real run
directory, which a hand-built snapshot does not have. What is under test is the
ROUTE — which branch is chosen, what each one is allowed to claim, and the words
a planner reads. The pricer is therefore stubbed at the two seams the Explainer
calls it through, with canned ``LocalPrice`` values of exactly the shapes the
real one returns. The LIVE path, real pricer and all, is measured in
``docs/closeouts/4B.30.md`` §5.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mre.contracts.parse import INTENT_MEANINGS, Intent, MoveDirection
from mre.modules import later_move as lm
from mre.modules.explainer import ROUTE_TAXONOMY, Explainer
from mre.modules.local_price import LocalPrice, LocalRefusal
from mre.modules.renderers import TemplateRenderer

from tests.test_why_here_route import _Reader, _Store, _iso

ROUTE = Intent.WHAT_WOULD_CHANGE.value
REF = datetime(2026, 1, 5)                       # a Monday
FROZEN_UNTIL = datetime(2026, 1, 6)
MAINT_START = datetime(2026, 1, 14, 0, 0)
MAINT_END = datetime(2026, 1, 14, 23, 59, 59)


class _Index:
    _all_evidence: list = []

    def lineage_walk(self, *_a, **_k):
        return []


class _IdMap:
    _PAIRS = {
        "dem-mv": ("order_id", "ORD-000100"),      # the order being moved
        "dem-blk": ("order_id", "ORD-000200"),     # the collision
        "dem-chk": ("order_id", "ORD-000300"),     # the chunked one
        "dem-frz": ("order_id", "ORD-000400"),     # committed
        "dem-pin": ("order_id", "ORD-000500"),     # pinned
        "res-a": ("resource_id", "MILL-01"),
        "res-b": ("resource_id", "MILL-02"),
    }

    def __init__(self):
        self._to_canonical = {("IDS", t, v): cid
                              for cid, (t, v) in self._PAIRS.items()}

    def resolve(self, system, ref_type, value):
        return self._to_canonical.get((system, ref_type, value))

    def external_refs(self, cid):
        class _R:
            def __init__(s, t, v):
                s.type, s.value = t, v
        pair = self._PAIRS.get(cid)
        return [_R(*pair)] if pair else []


class _R2(_Reader):
    def read_identity_map(self):
        return _IdMap()


def _cal():
    return {"id": "cal-1",
            "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
                             "shift_start": "07:00", "shift_end": "19:00"},
            "exceptions": [{"type": "closure",
                            "window": {"start": _iso(MAINT_START),
                                       "end": _iso(MAINT_END)},
                            "reason": "planned_maintenance"}],
            "horizon_resolved": []}


def _op(oid, wp, seq, *, splittable=False, min_chunk=None):
    return {"id": oid, "workpackage_ref": wp, "sequence": seq,
            "splittable": splittable, "min_chunk": min_chunk,
            "setup_duration": "PT10M", "run_duration": "PT2H",
            "setup_family": ""}


def _asgn(aid, op, wp, res, windows):
    return {"id": aid, "operation_ref": op, "workpackage_ref": wp,
            "resource_assignments": [{"resource_ref": res}],
            "phase_windows": {"run": [{"start": _iso(s), "end": _iso(e)}
                                      for s, e in windows]},
            "decision_ref": ""}


def _demand(did, order):
    return {"id": did, "external_refs": [{"type": "order_id", "value": order}],
            "due": _iso(datetime(2026, 1, 22)), "customer_weight": 1.0,
            "earliest_start": _iso(REF)}


def _world():
    """Five orders, two machines, one maintenance Wednesday.

    ORD-000100 op10 runs MILL-01 Thu 2026-01-08 09:00-11:00. The day after, at
    exactly the same clock time, ORD-000200 sits in the way — so "push it out a
    day" is a COLLISION and "move it to Wednesday" is a CLOSURE, on one fixture.
    """
    ops = [_op("op-mv", "wp-mv", 10),
           _op("op-blk", "wp-blk", 10),
           _op("op-chk", "wp-chk", 10, splittable=True, min_chunk="PT1H"),
           _op("op-frz", "wp-frz", 10),
           _op("op-pin", "wp-pin", 10)]
    return _R2({
        "calendar": [_cal()],
        "resource": [{"id": "res-a", "calendar_ref": "cal-1"},
                     {"id": "res-b", "calendar_ref": "cal-1"}],
        "operation": ops,
        "precedenceedge": [],
        "constraint": [],
        "demand": [_demand("dem-mv", "ORD-000100"),
                   _demand("dem-blk", "ORD-000200"),
                   _demand("dem-chk", "ORD-000300"),
                   _demand("dem-frz", "ORD-000400"),
                   _demand("dem-pin", "ORD-000500")],
        "fulfillment": [{"workpackage_ref": "wp-mv", "demand_ref": "dem-mv"},
                        {"workpackage_ref": "wp-blk", "demand_ref": "dem-blk"},
                        {"workpackage_ref": "wp-chk", "demand_ref": "dem-chk"},
                        {"workpackage_ref": "wp-frz", "demand_ref": "dem-frz"},
                        {"workpackage_ref": "wp-pin", "demand_ref": "dem-pin"}],
        "serviceoutcome": [],
        "assignment": [
            _asgn("a-mv", "op-mv", "wp-mv", "res-a",
                  [(datetime(2026, 1, 8, 9, 0), datetime(2026, 1, 8, 11, 0))]),
            # THE COLLISION: same machine, same clock time, one day later.
            _asgn("a-blk", "op-blk", "wp-blk", "res-a",
                  [(datetime(2026, 1, 9, 9, 0), datetime(2026, 1, 9, 11, 0))]),
            # THE CHUNKED ONE: two pieces around the maintenance Wednesday.
            _asgn("a-chk", "op-chk", "wp-chk", "res-b",
                  [(datetime(2026, 1, 13, 18, 0), datetime(2026, 1, 13, 19, 0)),
                   (datetime(2026, 1, 15, 7, 0), datetime(2026, 1, 15, 8, 0))]),
            # COMMITTED: inside the frozen front.
            _asgn("a-frz", "op-frz", "wp-frz", "res-b",
                  [(datetime(2026, 1, 5, 9, 0), datetime(2026, 1, 5, 11, 0))]),
            # PINNED: outside the frozen front, held by an explicit lock.
            _asgn("a-pin", "op-pin", "wp-pin", "res-b",
                  [(datetime(2026, 1, 8, 13, 0), datetime(2026, 1, 8, 15, 0))]),
        ],
    })


DOC = {"rolling": {"frozen_until": _iso(FROZEN_UNTIL),
                   "window_start": _iso(REF),
                   "window_end": _iso(datetime(2026, 1, 15))},
       "assignments": []}


@pytest.fixture
def ex(monkeypatch):
    e = Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")
    # ORD-000500's lock — the A7/F1 branch's own premise.
    monkeypatch.setattr(
        Explainer, "_pin_start_for",
        lambda self, op: (datetime(2026, 1, 8, 13, 0) if op == "op-pin"
                          else None))
    return e


def _stub_price(monkeypatch, price, alt=None):
    """Stand the pricer up with a canned verdict. ``alt`` is the SECOND call's
    answer — the recomputed alternative a refusal offers."""
    calls = {"n": 0}

    def _at(self, world, op_ref, rid, at, dem_refs, **_k):
        calls["n"] += 1
        return alt if (calls["n"] > 1 and alt is not None) else price

    class _World:
        """Just enough of ``_HeldWorld`` for the route: the grid's far end,
        which is where the beyond-horizon branch is decided."""
        horizon_end = datetime(2026, 3, 1)

    monkeypatch.setattr(Explainer, "_held_world",
                        lambda self, restrict=None: _World())
    monkeypatch.setattr("mre.modules.local_price.demands_of_operation",
                        lambda world, op: ["dem-mv"])
    monkeypatch.setattr(Explainer, "_price_at", _at)
    return calls


def _answer(explainer, order="ORD-000100", target="", direction="later",
            **params) -> str:
    params.setdefault("question", "can it move later?")
    params["order"] = order
    params["move_direction"] = direction
    params["move_target"] = target
    params["document"] = DOC
    return TemplateRenderer().render(explainer.route(ROUTE, params))


def _facts(explainer, order="ORD-000100", target="", direction="later",
           **params) -> dict:
    params.setdefault("question", "can it move later?")
    params["order"] = order
    params["move_direction"] = direction
    params["move_target"] = target
    params["document"] = DOC
    return explainer.route(ROUTE, params).key_facts


PRICED = LocalPrice(
    priced=True, cost_delta_abs=1234.5, cost_delta_pct=0.5,
    total_before=250_000.0, total_after=251_234.5,
    cost_lines=[], affected_orders=[], lateness_delta_min=180,
    validation={"status": "OPTIMAL"},
    subject_outcomes=[{
        "demand_ref": "dem-mv", "work_order": "ORD-000100",
        "due": "2026-01-22T00:00:00Z",
        "completion_before": "2026-01-20T11:00:00Z",
        "completion_after": "2026-01-23T11:00:00Z",
        "lateness_before_min": -2820, "lateness_after_min": 1500,
        "tardiness_before": 0.0, "tardiness_after": 1234.5,
        "tardiness_floor_min": 0, "tardiness_floor_cost": 0.0}])

COLLISION = LocalPrice(priced=False, refusal=LocalRefusal(
    family="B1", resource_id="res-a", other_op_ref="op-blk",
    other_work_orders=["ORD-000200"], holds_others=True,
    at="2026-01-09T09:00:00Z",
    sentence="that time is already taken on this machine").summary())

CLOSED = LocalPrice(priced=False, refusal=LocalRefusal(
    family="C1/C2", resource_id="res-a", at="2026-01-14T00:00:00Z",
    holds_others=False,
    sentence="the machine is not open at that time").summary())

BOXED_IN = LocalPrice(priced=False, refusal=LocalRefusal(
    family="A1/A2", other_op_ref="op-next", other_work_orders=["ORD-000100"],
    holds_others=True, at="2026-01-09T07:00:00Z",
    sentence="the next step in this order is already scheduled "
             "before this one would finish").summary())


# ---------------------------------------------------------------------------
# PREMISE — the fixture really contains the three obstacles
# ---------------------------------------------------------------------------

class TestPremise:

    def test_the_collision_sits_exactly_one_day_after_the_moved_bar(self, ex):
        rows = {r["assignment_id"]: r for r in ex._load_enriched_assignments()}
        mv, blk = rows["a-mv"], rows["a-blk"]
        assert blk["machine"] == mv["machine"]
        assert (datetime.fromisoformat(blk["start"].replace("Z", "+00:00"))
                - datetime.fromisoformat(mv["start"].replace("Z", "+00:00"))
                == timedelta(days=1))

    def test_the_closure_is_declared_with_a_reason(self, ex):
        clo = ex._closures("MILL-01")
        assert len(clo) == 1 and clo[0]["reason"] == "planned_maintenance"

    def test_the_chunked_operation_really_runs_in_two_pieces(self, ex):
        row = ex._pick_op_row("ORD-000300", None, None)
        assert len(row["chunks"]) == 2

    def test_the_committed_bar_starts_inside_the_frozen_front(self, ex):
        row = ex._pick_op_row("ORD-000400", None, None)
        assert row["start"] < _iso(FROZEN_UNTIL)

    def test_the_moved_bar_is_NOT_committed_and_NOT_chunked(self, ex):
        """Without this the priceable tests would pass through a refusal branch
        and prove nothing about pricing."""
        row = ex._pick_op_row("ORD-000100", None, None)
        assert row["start"] > _iso(FROZEN_UNTIL)
        assert len(row["chunks"]) == 1


# ---------------------------------------------------------------------------
# THE WIDENING IS PAID IN FULL — and costs no new vocabulary
# ---------------------------------------------------------------------------

class TestVocabulary:

    def test_no_new_intent_was_minted(self):
        """Item 1's whole premise. The later direction is a MEANING widening on
        an intent that already exists; a second vocabulary member would buy a
        second way to reach an answer we already have."""
        assert ROUTE in ROUTE_TAXONOMY
        assert not any(i.value in ("move-later", "later-move", "delay")
                       for i in Intent)

    def test_the_meaning_owns_both_directions(self):
        meaning = INTENT_MEANINGS[Intent.WHAT_WOULD_CHANGE].lower()
        assert "later" in meaning and "earlier" in meaning
        assert "move_direction" in meaning and "move_target" in meaning

    def test_the_canonical_question_no_longer_says_earlier(self):
        """A canonical that names one half of a widened meaning prints the
        question we heard back at a planner who asked the other one."""
        assert "earlier" not in ROUTE_TAXONOMY[ROUTE]["canonical"]

    def test_swap_move_hands_the_time_direction_over(self):
        """The census found `swap-move` answering a later question with "the
        move worth pricing is the one that gives it an EARLIER opening"."""
        assert "what-would-change" in INTENT_MEANINGS[Intent.SWAP_MOVE]

    def test_the_parse_carries_the_two_fields(self):
        from mre.contracts.parse import ParsedQuestion
        p = ParsedQuestion(question="q", move_direction=MoveDirection.LATER,
                           move_target="Friday")
        assert p.move_direction is MoveDirection.LATER
        assert p.move_target == "Friday"

    def test_an_older_parse_still_means_earlier(self):
        from mre.contracts.parse import ParsedQuestion
        assert ParsedQuestion(question="q").move_direction is None

    def test_the_swap_move_take_is_no_longer_hard_coded_to_earlier(self, ex):
        """The census's turn 5. `swap-move`'s single-order branch said "the move
        worth pricing is the one that gives it an EARLIER opening" and "drag it
        to the EARLIER slot you have in mind", whatever was asked. The MEANING
        now sends a later move of one operation to `what-would-change`, so the
        live parse no longer lands here — which is exactly why this guard exists.
        A route the parse stopped visiting is a route whose wrong sentence stops
        being measured."""
        later = TemplateRenderer().render(ex.route(
            Intent.SWAP_MOVE.value,
            {"question": "push ORD-000100 back", "order": "ORD-000100",
             "move_direction": "later"}))
        assert "earlier opening" not in later
        assert "asking to push ORD-000100 OUT" in later
        # and the unchanged behaviour where no direction was reported
        plain = TemplateRenderer().render(ex.route(
            Intent.SWAP_MOVE.value,
            {"question": "why not swap it", "order": "ORD-000100"}))
        assert "earlier slot you have in mind" in plain


# ---------------------------------------------------------------------------
# THE DIRECTION DECIDES THE ANSWER (Item 1)
# ---------------------------------------------------------------------------

class TestDirection:

    def test_earlier_still_reaches_the_counterfactual(self, ex):
        assert _facts(ex, direction="earlier")["verdict"] in (
            "could_not", "chose", "undetermined", "unplaced")

    def test_an_absent_direction_still_reaches_the_counterfactual(self, ex):
        kf = _facts(ex, direction=None)
        assert "branch" not in kf

    def test_later_reaches_the_later_route(self, ex, monkeypatch):
        _stub_price(monkeypatch, PRICED)
        assert _facts(ex, target="a day")["branch"] == lm.BRANCH_PRICED

    def test_the_two_directions_do_not_produce_the_same_paragraph(self, ex,
                                                                  monkeypatch):
        """The census's sharpest finding: "how do I get this earlier" and "can I
        move this later" returned BYTE-IDENTICAL text, so the deafness rider —
        which watches for one answer serving two questions — fired on it."""
        _stub_price(monkeypatch, PRICED)
        assert _answer(ex, target="a day") != _answer(ex, direction="earlier")


# ---------------------------------------------------------------------------
# ITEM 3 — the priceable answer says all three things
# ---------------------------------------------------------------------------

class TestPricedAnswer:

    def test_it_states_what_the_delay_costs(self, ex, monkeypatch):
        _stub_price(monkeypatch, PRICED)
        assert "+$1,234.50" in _answer(ex, target="a day")

    def test_it_states_what_it_displaces_even_when_that_is_nothing(self, ex,
                                                                   monkeypatch):
        """An empty affected list is the USUAL case under a held-world price and
        is never a silence. It also points honestly at the deeper search without
        promising what it would find."""
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="a day")
        assert "Nothing else moves" in text
        assert "deeper search might refill it" in text

    def test_it_states_whether_the_due_date_survives_with_the_number(self, ex,
                                                                     monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="a day")
        assert "2026-01-23 11:00" in text          # the completion, formatted
        assert "past its due date" in text
        # 1500 minutes. `_span`'s rule: hours up to 48, days beyond, so this
        # one reads "25h" and the FLOOR test below is what exercises days.
        assert "25h past its due date" in text

    def test_a_past_due_order_names_the_floor_and_the_controllable_part(
            self, ex, monkeypatch):
        """R-PD1 clause (4). The floor is stated ONCE, as unmovable: reporting
        it before AND after would invite a planner to subtract two equal numbers
        and read a decision into it."""
        late = LocalPrice(**{**PRICED.__dict__})
        late.subject_outcomes = [{**PRICED.subject_outcomes[0],
                                  "lateness_before_min": 40_000,
                                  "lateness_after_min": 41_440,
                                  "tardiness_floor_min": 2880,
                                  "tardiness_floor_cost": 600.0}]
        _stub_price(monkeypatch, late)
        text = _answer(ex, target="a day")
        assert "already sunk before this plan opened" in text
        assert "R-PD1" in text
        assert "2d" in text                        # the floor, 2880 minutes

    def test_it_says_the_price_holds_the_world_still(self, ex, monkeypatch):
        """The claim is exact BECAUSE nothing else moved, and a reader who does
        not know that will read it as "the cheapest plan containing this move"."""
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="a day")
        assert "every other placement pinned where it is" in text
        assert "not what the best plan containing it would cost" in text

    def test_it_names_the_instant_it_tested(self, ex, monkeypatch):
        """The 4B.16 precedent: a weekday alone is not an anchor."""
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="a day")
        assert "Friday 2026-01-09" in text


# ---------------------------------------------------------------------------
# ITEM 4 — the five refusal branches, which on a real board are the common case
# ---------------------------------------------------------------------------

class TestRefusalBranches:

    def test_a_collision_names_the_occupant(self, ex, monkeypatch):
        _stub_price(monkeypatch, COLLISION)
        text = _answer(ex, target="a day")
        assert "ORD-000200" in text
        assert "already carrying" in text

    def test_a_collision_says_it_is_about_the_price_and_not_the_plant(
            self, ex, monkeypatch):
        """SHUT IS NOT OCCUPIED. This refusal exists only because the price
        holds the occupant still, so it is "not without moving other work" and
        never "no" — the distinction 4B.24 built ``holds_others`` for, ruled a
        fifth time there and honoured a sixth here."""
        _stub_price(monkeypatch, COLLISION)
        text = _answer(ex, target="a day")
        assert "not about your plant" in text
        assert "free to move them" in text

    def test_a_collision_offers_a_recomputed_alternative_and_prices_it(
            self, ex, monkeypatch):
        _stub_price(monkeypatch, COLLISION, alt=PRICED)
        text = _answer(ex, target="a day")
        assert "The next opening that WOULD take it" in text
        assert "+$1,234.50" in text

    def test_a_closed_calendar_names_the_closure_kind(self, ex, monkeypatch):
        _stub_price(monkeypatch, CLOSED)
        text = _answer(ex, target="Wednesday", order="ORD-000100")
        assert "planned maintenance" in text
        assert "not open" in text

    def test_a_closed_calendar_says_nobody_is_in_the_way(self, ex, monkeypatch):
        """A planner acts on "shut" and on "busy" completely differently, and
        the two are one branch in every surface that reports only feasibility
        (4B.23's ruled species, at another seam)."""
        _stub_price(monkeypatch, CLOSED)
        text = _answer(ex, target="Wednesday")
        assert "the calendar, not congestion" in text
        assert "nobody is in the way" in text

    def test_a_closed_calendar_refuses_to_invent_the_hours(self, ex,
                                                           monkeypatch):
        _stub_price(monkeypatch, CLOSED)
        assert "won't guess what hours" in _answer(ex, target="Wednesday")

    def test_a_chunked_operation_declines_as_a_PROCESS_limit(self, ex):
        """(c) The sentence is about US. A planner told "it can't go there"
        would act on a claim about their plant that nobody has tested — the
        `CostProof.unreadable` / `FeasibilityGhost.undetermined` species."""
        text = _answer(ex, order="ORD-000300", target="a day")
        assert "can't re-place split work as one move yet" in text
        assert "limit of mine, not a ruling about your plant" in text
        assert "not telling you the move is impossible" in text

    def test_a_chunked_operation_never_reaches_the_pricer(self, ex,
                                                          monkeypatch):
        """Checked from the ROW, before the model build. The pricer declines it
        anyway; paying ~6.5 s to be told what the row already says is waste."""
        def _boom(*_a, **_k):
            raise AssertionError("the pricer was called for a chunked op")
        monkeypatch.setattr(Explainer, "_held_world", _boom)
        assert _facts(ex, order="ORD-000300",
                      target="a day")["branch"] == lm.BRANCH_CHUNKED

    def test_committed_work_is_refused_by_name(self, ex):
        text = _answer(ex, order="ORD-000400", target="a day")
        assert "R-F1" in text and "committed front" in text
        assert "standing pins, not free work" in text

    def test_a_pinned_operation_is_refused_by_name(self, ex):
        text = _answer(ex, order="ORD-000500", target="a day")
        assert "A7/F1" in text and "pinned" in text

    def test_precedence_refuses_AND_DECLINES_TO_OFFER_A_LATER_SLOT(
            self, ex, monkeypatch):
        """The remedy inverts. A later alternative unblocks a busy slot and
        makes a boxed-in one worse, so this branch offers none and says why —
        an offer that helps nothing is worse than no offer."""
        _stub_price(monkeypatch, BOXED_IN)
        text = _answer(ex, target="a day")
        assert "next step of its own routing" in text
        assert "would make that worse" in text
        assert "The next opening that WOULD take it" not in text

    def test_nothing_later_at_all_says_so(self, ex, monkeypatch):
        """(e) There is no later stretch big enough. Measured from the machine's
        own free time, and reported rather than dressed as a refusal."""
        real = Explainer._later_calendar
        monkeypatch.setattr(
            Explainer, "_later_calendar",
            lambda self, row: {**real(self, row), "free": [],
                               "open_windows": [], "pattern_windows": []})
        kf = _facts(ex, target="")
        assert kf["branch"] == lm.BRANCH_NO_LATER_FIT

    def test_a_target_past_the_PLANNED_GRID_is_refused_against_the_HORIZON(
            self, ex, monkeypatch):
        """(e), the other half — and the line is the MODEL HORIZON, not the
        rolling window. This session's first version measured it against
        `window_end` and refused a target four days INSIDE the placed grid: the
        demo board's window closes 2026-01-15 while its schedule places work in
        detail into February. A window bounds what a planner is looking at; a
        horizon bounds what there is a variable for."""
        class _Tiny:
            horizon_end = datetime(2026, 1, 8, 12, 0)   # inside the window

        monkeypatch.setattr(Explainer, "_held_world",
                            lambda self, restrict=None: _Tiny())
        kf = _facts(ex, target="a day")
        assert kf["branch"] == lm.BRANCH_BEYOND_GRID
        assert kf["horizon_end"] == "2026-01-08 12:00"

    def test_the_window_end_is_NOT_what_bounds_a_price(self, ex, monkeypatch):
        """The same fixture, with the rolling window closing BEFORE the target
        and the horizon comfortably after it. The answer must price."""
        assert DOC["rolling"]["window_end"] < _iso(datetime(2026, 1, 20))
        _stub_price(monkeypatch, PRICED)
        assert _facts(ex, target="two weeks")["branch"] != lm.BRANCH_BEYOND_GRID

    def test_an_unpriceable_world_says_it_is_OUR_failure(self, ex,
                                                         monkeypatch):
        """No run directory to price against. The sentence must not read as a
        verdict on the move."""
        monkeypatch.setattr(Explainer, "_held_world",
                            lambda self, restrict=None: None)
        text = _answer(ex, target="a day")
        assert "failure of mine, not a verdict on the move" in text

    def test_an_unplaced_order_has_nothing_to_push_out(self, ex, monkeypatch):
        monkeypatch.setattr(Explainer, "_pick_op_row",
                            lambda self, *a, **k: None)
        text = _answer(ex, target="a day")
        assert "nothing to push out" in text


# ---------------------------------------------------------------------------
# EVERY ANSWER DISCLOSES HOW IT READ THE TARGET (Item 2)
# ---------------------------------------------------------------------------

class TestDisclosure:

    def test_a_named_day_says_which_date_it_tested(self, ex, monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="Friday")
        assert "Friday 2026-01-09" in text

    def test_a_named_day_with_several_instances_says_how_many(self, ex,
                                                              monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="Friday")
        assert "of that weekday still ahead" in text
        assert "Name a date if you meant a different one" in text

    def test_a_reason_that_names_an_interval_says_which_interval(self, ex,
                                                                 monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="after the maintenance")
        assert "planned maintenance" in text
        assert "2026-01-14 00:00" in text

    def test_a_snap_forward_is_stated(self, ex, monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="two hours")   # 11:00 Thu, inside the shift
        # nothing to snap here; the disclosure fires on the closed instant
        assert "Pushing ORD-000100 op10 out by" in text

    def test_a_target_it_could_not_read_says_it_fell_back(self, ex,
                                                          monkeypatch):
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="when the customer calls back")
        assert "could not resolve" in text
        assert "not the one you named" in text


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — each proven red against a specific reverted behaviour
# ---------------------------------------------------------------------------

class TestNegativeControls:

    def test_a_route_that_ignored_the_direction_gives_one_paragraph_for_both(
            self, ex, monkeypatch):
        """REVERT (branch class: DIRECTION): drop the `move_direction` check in
        `route()`, which is HEAD's behaviour exactly. Both questions reach the
        counterfactual and the answers are byte-identical — the census's
        measurement, reproduced as a test."""
        _stub_price(monkeypatch, PRICED)
        reverted_later = _answer(ex, target="a day", direction=None)
        reverted_earlier = _answer(ex, direction="earlier")
        assert reverted_later == reverted_earlier
        # and the guard, over the same two questions
        assert _answer(ex, target="a day") != _answer(ex, direction="earlier")

    def test_a_collision_reported_as_a_plant_fact_would_read_as_no(
            self, ex, monkeypatch):
        """REVERT (branch class: REFUSAL ABOUT THE PLANT VS ABOUT THE PRICE):
        drop `holds_others` from the collision copy. The remaining sentence is
        true and a planner reads it as "the plant will not take this", when what
        it means is "not without moving other work"."""
        _stub_price(monkeypatch, COLLISION)
        with_flag = _answer(ex, target="a day")
        flagless = LocalPrice(priced=False, refusal={
            **COLLISION.refusal, "holds_others": False})
        _stub_price(monkeypatch, flagless)
        without = _answer(ex, target="a day")
        assert "not about your plant" in with_flag
        assert "not about your plant" not in without

    def test_a_chunked_decline_worded_as_a_plant_fact_would_be_a_claim_we_never_tested(
            self, ex):
        """REVERT (branch class: OUR LIMIT VS THEIR PLANT): word branch (c) as
        "it can't go there". The guard is that the copy names the limit as ours
        and explicitly denies the plant claim."""
        text = _answer(ex, order="ORD-000300", target="a day")
        assert "limit of mine" in text
        for forbidden in ("that is not possible", "the plant cannot",
                          "it can't go there"):
            assert forbidden not in text.lower()

    def test_an_offer_taken_as_the_minute_after_the_obstacle_would_land_inside_the_next_one(
            self):
        """REVERT (branch class: THE RECOMPUTED ALTERNATIVE): offer
        `occupant_end` instead of scanning. On this fixture the minute after the
        collision is inside a stretch too short for the operation, so the
        reverted offer is a slot the work does not fit in."""
        free = [(datetime(2026, 1, 9, 11, 0), datetime(2026, 1, 9, 11, 30)),
                (datetime(2026, 1, 9, 15, 0), datetime(2026, 1, 9, 19, 0))]
        naive = datetime(2026, 1, 9, 11, 0)              # the occupant's end
        computed = lm.next_opening_after(free, naive, working_min=120.0)
        assert computed == datetime(2026, 1, 9, 15, 0) != naive

    def test_a_price_that_did_not_state_the_held_world_would_read_as_optimal(
            self, ex, monkeypatch):
        """REVERT (branch class: WHAT THE NUMBER IS ABOUT): drop the closing
        paragraph. The figure is then indistinguishable from "the cost of the
        best plan containing this move", which is the reading 4B.24 spent a
        whole session proving false."""
        _stub_price(monkeypatch, PRICED)
        text = _answer(ex, target="a day")
        assert "not what the best plan containing it would cost" in text
