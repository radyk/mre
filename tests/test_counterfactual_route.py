"""THE COUNTERFACTUAL AS AN ANSWER (Session 4B.16 Item 1).

The bar the session brief set, on the same world 4B.14's blocker analysis was
measured against (op20: 431 non-splittable working minutes, 294 left on PAINT-01
after op10 finished at 14:06, a plant-wide closure on the day between):

    op20 needs 431 minutes in one piece and Tuesday had 294 left after op10.

    To fit Tuesday, one of these has to change:
      min_chunk_minutes <= 215 on this operation      [C3, docs/06 §5.3]
      op10 finishes by 11:49 instead of 14:06         [A1/A2]
      431 contiguous minutes free on an eligible machine  [B1]
      PAINT-01's Tuesday window extended by 137 minutes   [C1/C2]

    If min_chunk changed, the next bound would be B1 resource availability at
    2026-01-13 14:06 — so this removes the barrier, it does not place the
    operation there.

TWO PLACES THESE TESTS DEPART FROM THE BRIEF'S WORKED SPECIMEN, both because the
computed answer is the sharper one:

  * the min_chunk threshold is 215, not 240. R-C3's degenerate-split rule caps a
    resumable operation's minimum piece at HALF its duration (431/2 = 215): at
    216 the solver treats the operation as atomic again and Tuesday is out of
    reach. 240 would be a threshold that does not work.
  * the B1 line is COMPUTED rather than stated. "431 contiguous minutes free on
    an eligible machine" is the condition; this world's only other eligible lane
    is CUT-01, which does NOT have them any earlier, so the answer says so
    instead of offering a door that is already shut.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from mre.contracts.parse import INTENT_MEANINGS, Intent
from mre.modules.explainer import ROUTE_TAXONOMY, Explainer
from mre.modules.renderers import TemplateRenderer

from tests.test_why_here_route import _Index, _Store, _world

ROUTE = Intent.WHAT_WOULD_CHANGE.value


@pytest.fixture
def ex():
    return Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")


def _answer(explainer, **params) -> str:
    params.setdefault("question", "what would have to change?")
    return TemplateRenderer().render(explainer.route(ROUTE, params))


def _facts(explainer, **params) -> dict:
    params.setdefault("question", "what would have to change?")
    return explainer.route(ROUTE, params).key_facts


def _levers(explainer, **params) -> dict:
    return {l["key"]: l for l in _facts(explainer, **params)["levers"]}


# ---------------------------------------------------------------------------
# The vocabulary is paid in full (a route the parse cannot name is unreachable)
# ---------------------------------------------------------------------------

class TestVocabulary:

    def test_the_intent_has_a_route_a_meaning_and_an_offer(self):
        from mre.modules.ask_fallback_copy import ROUTE_OFFERS
        assert ROUTE in ROUTE_TAXONOMY
        assert Intent.WHAT_WOULD_CHANGE in INTENT_MEANINGS
        assert ROUTE in ROUTE_OFFERS

    def test_it_is_operation_scoped_like_the_blocker_analysis(self):
        """Asked with a bar selected it must answer about THAT bar (4B.14 Item
        5(d)'s lesson, inherited rather than re-learned)."""
        from mre.modules.interpreter import _OPERATION_SCOPED_INTENTS
        assert Intent.WHAT_WOULD_CHANGE in _OPERATION_SCOPED_INTENTS

    def test_the_meaning_separates_it_from_its_three_neighbours(self):
        meaning = INTENT_MEANINGS[Intent.WHAT_WOULD_CHANGE]
        for neighbour in ("why-here", "swap-move", "advice", "coaching"):
            assert neighbour in meaning

    def test_why_here_points_at_it(self):
        """Written as a PAIR: the diagnosis route says where the remedy lives."""
        assert "what-would-change" in INTENT_MEANINGS[Intent.WHY_HERE]


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------

class TestTheArithmetic:

    def test_it_states_the_requirement_the_room_and_the_shortfall(self, ex):
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "7h11m" in text            # 431 working minutes, needed
        assert "4h54m" in text            # 294 minutes, what was left
        assert "2h17m short" in text      # 137 minutes, the deficit

    def test_it_names_the_window_it_is_trying_to_fit(self, ex):
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "Tuesday 2026-01-13 14:06" in text
        assert "To fit Tuesday, one of these has to change:" in text

    def test_the_min_chunk_threshold_is_the_R_C3_CEILING_not_a_round_number(self, ex):
        """431/2 = 215. At 216 the operation is atomic again (R-C3's
        degenerate-split rule) and Tuesday is unreachable, so a threshold above
        the ceiling would be a change that does not work."""
        lever = _levers(ex, order="ORD-000013", machine="PAINT-01")["min_chunk"]
        assert lever["threshold_min"] == 215
        assert "431/2 = 215" in lever["effect"]

    def test_the_predecessor_threshold_is_computed_from_the_window_close(self, ex):
        """19:00 minus 7h11m = 11:49 — the instant op10 would have to finish for
        the whole operation to fit before PAINT-01 closes."""
        lever = _levers(ex, order="ORD-000013", machine="PAINT-01")["predecessor"]
        assert "2026-01-13 11:49" in lever["statement"]
        assert "2026-01-13 14:06" in lever["statement"]
        assert lever["threshold_min"] == pytest.approx(137.0)

    def test_the_calendar_threshold_is_the_deficit(self, ex):
        lever = _levers(ex, order="ORD-000013", machine="PAINT-01")["calendar"]
        assert lever["threshold_min"] == pytest.approx(137.0)
        assert "2h17m" in lever["statement"]

    def test_every_lever_cites_docs05_AND_where_the_field_is_declared(self, ex):
        """A1 of the brief: the min_chunk line wants to cite docs/06 §5.3. A
        family citation alone is advice nobody can act on — it does not say
        which column to change."""
        levers = _levers(ex, order="ORD-000013", machine="PAINT-01")
        assert levers["min_chunk"]["citation"] == "C3"
        assert "docs/06 §5.3" in levers["min_chunk"]["spec"]
        assert "min_chunk_minutes" in levers["min_chunk"]["spec"]
        assert "docs/06 §5.6" in levers["calendar"]["spec"]
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "docs/05 C3" in text and "docs/05 C1/C2" in text


# ---------------------------------------------------------------------------
# THE HARD RULE — necessary, never sufficient
# ---------------------------------------------------------------------------

class TestNecessaryNeverSufficient:

    def test_it_names_the_NEXT_bound_and_refuses_to_promise_a_placement(self, ex):
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "the next bound would be an earlier step [docs/05 A1/A2] at " \
               "Tuesday 2026-01-13 14:06" in text
        assert "that removes the barrier; it does not place the operation " \
               "there" in text

    def test_the_next_bound_is_the_runner_up_of_the_same_ladder(self, ex):
        nxt = _facts(ex, order="ORD-000013", machine="PAINT-01")["next_bound"]
        assert nxt["family"] == "precedence"
        assert nxt["at"] == "2026-01-13 14:06"

    def test_it_never_claims_the_solver_would_use_the_freed_time(self, ex):
        text = _answer(ex, order="ORD-000013", machine="PAINT-01").lower()
        for promise in ("then it can start", "it would start", "will start "):
            assert promise not in text

    def test_a_relaxation_that_needs_a_resolve_is_NAMED_not_estimated(self, ex):
        """The 4B.14 precedent on changeover, applied to relaxations."""
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "Can't be priced as a change (it would take a re-solve): B7/B8" \
            in text

    def test_it_carries_the_not_weighed_block(self, ex):
        """A counterfactual that ignores B3/B5, B7/B8, C4 and F3 is exactly as
        partial as the explanation was."""
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "Not weighed here (docs/05)" in text
        for family in ("B3/B5", "B7/B8", "C4", "F3"):
            assert family in text


# ---------------------------------------------------------------------------
# Verification: a threshold the same scan does not confirm is not stated
# ---------------------------------------------------------------------------

class TestVerification:

    def test_a_lever_is_verified_by_re_running_the_SAME_fit_scan(self):
        """Flip only the R-C3 class to what the lever proposes and the operation
        really does open in the window the answer named. That is what makes the
        threshold a number rather than arithmetic about arithmetic."""
        from mre.modules.blocker_analysis import _subtract, earliest_fit
        from mre.modules.counterfactual import resumable_fit

        e = Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")
        _analysis, _row, inputs = e._blocker_inputs("ORD-000013", "PAINT-01",
                                                    None)
        free = _subtract(inputs["open_windows"], inputs["occupied"])
        window = datetime(2026, 1, 13, 14, 6)
        assert earliest_fit(free, window, 431.0, splittable=False,
                            min_chunk_min=None)[0] > window          # today
        assert resumable_fit(free, window, 431.0, 215.0)[0] == window  # relaxed
        # R-C3's wall, and the reason the verification applies the degenerate
        # rule rather than trusting `splittable=True`: at 216 the solver treats
        # the operation as atomic again, so 216 is a change that does not work.
        assert resumable_fit(free, window, 431.0, 216.0)[0] > window

    def test_a_splittable_op_whose_FLOOR_is_too_high_is_told_to_lower_it(self):
        """The other C3 shape: the operation may split, and its minimum piece
        is bigger than what is left, so it cannot even OPEN in the window. The
        lever is a lowering, and the copy says what it buys — a start, not a
        finish."""
        reader = _world(op20_splittable=True, op20_min_chunk="PT3H20M")
        for a in reader._e["assignment"]:      # op10 runs on to 16:30
            if a["id"] == "a-13-10":
                a["phase_windows"]["run"][0]["end"] = "2026-01-13T16:30:00Z"
        e = Explainer(_Store(reader), _Index(), snapshot_id="snap-test")
        lever = _levers(e, order="ORD-000013", machine="PAINT-01")["min_chunk"]
        assert lever["threshold_min"] == 150         # what is left, not 431/2
        assert "lowered from 200 to 150 or less" in lever["statement"]
        assert "at 200 it cannot start at all" in lever["effect"]

    def test_an_already_split_operation_gets_no_min_chunk_lever_it_cannot_use(self):
        """Its min_chunk is already under the ceiling, so proposing a lower one
        would be a change that buys nothing."""
        e = Explainer(
            _Store(_world(op20_start=datetime(2026, 1, 13, 14, 6),
                          op20_splittable=True, op20_min_chunk="PT1H")),
            _Index(), snapshot_id="snap-test")
        assert "min_chunk" not in _levers(e, order="ORD-000013",
                                          machine="PAINT-01")


# ---------------------------------------------------------------------------
# A bound that is not the fit
# ---------------------------------------------------------------------------

class TestAnUpstreamBound:
    """Split the operation and chunk-fit stops binding: PRECEDENCE does. The
    lever changes shape with it — there is no window arithmetic to state, and
    the honest figure is how much earlier the change is worth before the next
    bound takes over."""

    @pytest.fixture
    def split(self):
        return Explainer(
            _Store(_world(op20_start=datetime(2026, 1, 13, 14, 6),
                          op20_splittable=True, op20_min_chunk="PT1H")),
            _Index(), snapshot_id="snap-test")

    def test_the_lever_is_the_predecessor_not_the_window(self, split):
        levers = _levers(split, order="ORD-000013", machine="PAINT-01")
        assert set(levers) == {"predecessor"}
        assert "finishes earlier than 2026-01-13 14:06" in \
            levers["predecessor"]["statement"]
        assert _facts(split, order="ORD-000013",
                      machine="PAINT-01")["window"] is None

    def test_the_next_bound_is_RECOMPUTED_not_the_runner_up(self, split):
        """The runner-up is the release date at 2026-01-05 00:00. Relaxing
        precedence does not get the operation there — PAINT-01's calendar does
        not open until 07:00 — so the answer names the CALENDAR, which the
        runner-up never mentioned. Promising the runner-up would be a claim
        about a placement nobody checked."""
        kf = _facts(split, order="ORD-000013", machine="PAINT-01")
        assert kf["binding"]["family"] == "precedence"
        assert kf["next_bound"]["family"] == "calendar"
        assert kf["next_bound"]["at"] == "2026-01-05 07:00"

    def test_the_threshold_is_measured_against_that_same_next_bound(self, split):
        """One paragraph cannot state two different instants: the lever's
        ceiling and the closing sentence are computed from the same figure."""
        levers = _levers(split, order="ORD-000013", machine="PAINT-01")
        from datetime import timedelta
        expected = (datetime(2026, 1, 13, 14, 6)
                    - datetime(2026, 1, 5, 7, 0)) / timedelta(minutes=1)
        assert levers["predecessor"]["threshold_min"] == pytest.approx(expected)
        assert "8d 7h earlier" in levers["predecessor"]["effect"]


# ---------------------------------------------------------------------------
# The other lane (B1), computed
# ---------------------------------------------------------------------------

class TestTheOtherLane:

    def test_a_shut_door_is_stated_rather_than_offered(self, ex):
        """CUT-01 is eligible in this world (the operations declare no
        requirements) and has no long-enough opening any earlier. Listing it as
        something that could change would be offering a door already shut."""
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "No other eligible machine (CUT-01) has 7h11m of open, unheld " \
               "time any earlier either." in text
        assert "alternate" not in _levers(ex, order="ORD-000013",
                                          machine="PAINT-01")

    def test_an_alternative_lane_is_never_scanned_before_the_upstream_bound(self, ex):
        """A machine's calendar opens long before this order was released and
        long before op10 finished. Reporting that time would be a true
        statement about the machine and a false one about the operation."""
        text = _answer(ex, order="ORD-000013", machine="PAINT-01")
        assert "2026-01-05" not in text
        assert "2025-" not in text


# ---------------------------------------------------------------------------
# The verdicts with nothing to relax
# ---------------------------------------------------------------------------

class TestNothingHasToChange:

    def test_a_chosen_placement_says_NOTHING_has_to_change(self):
        """The honest counterfactual for a free placement. Inventing a barrier
        to have something to offer is the same over-claim `why-here` was built
        to end, wearing a helpful face."""
        e = Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                      _Index(), snapshot_id="snap-test")
        text = _answer(e, order="ORD-000013", machine="PAINT-01")
        assert "Nothing has to change" in text
        assert "has to change:" not in text          # no lever list at all
        assert _facts(e, order="ORD-000013",
                      machine="PAINT-01")["levers"] == []

    def test_and_it_names_the_objective_as_the_thing_it_cannot_price(self):
        e = Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                      _Index(), snapshot_id="snap-test")
        text = _answer(e, order="ORD-000013", machine="PAINT-01")
        assert "the objective" in text
        assert "re-solve" in text

    def test_an_unplaced_order_has_nothing_to_move(self):
        """Its OWN floor: "there is no 'here' to explain" answers a question
        about a placement, and this one was asked about a change."""
        reader = _world()
        reader._e["assignment"] = [a for a in reader._e["assignment"]
                                   if a["id"] != "a-99-10"]
        e = Explainer(_Store(reader), _Index(), snapshot_id="snap-test")
        text = _answer(e, order="ORD-000099")
        assert "nothing to move earlier yet" in text
        assert "has to change:" not in text


# ---------------------------------------------------------------------------
# The predicate floors know about it
# ---------------------------------------------------------------------------

class TestFloors:

    def test_it_covers_the_temporal_alternative_and_disagreement_topics(self):
        """It answers "why can't it be earlier" and "surely it could go
        earlier" head-on, so the coverage rider must not fire on it."""
        from mre.modules.predicate_coverage import COVERED_BY, uncovered_topic
        assert ROUTE in COVERED_BY["temporal_alternative"]
        assert ROUTE in COVERED_BY["disagreement"]
        assert uncovered_topic("why can't it start earlier", ROUTE,
                               "because X") is None

    def test_the_answer_is_rendered_verbatim_never_reworded(self):
        """The closing paragraph IS the discipline of the route, and it is the
        first sentence an "answer in 2-3 sentences" reword drops."""
        from mre.modules.renderers import LLMRenderer
        assert "counterfactual" in LLMRenderer._AUTHORED_COPY_SUBJECTS
