"""WHERE IS "LATER"? — the target resolver (Session 4B.30 Item 2).

``later_move.resolve_target`` is pure: planner words plus three calendar views
in, one disclosed target out. These tests are written against the RULE, not
against the implementation:

  * a NAMED DAY resolves to the nearest FUTURE instance and says how many it
    chose between (4B.15 Item 0 — a weekday in a five-Tuesday horizon is not an
    anchor);
  * a MAGNITUDE lands current-start-plus-amount and snaps FORWARD over
    non-working hours, stating the snap;
  * "after the maintenance" reads the DECLARED closure and says which one;
  * a bare "later" finds the first opening with room for the whole operation;
  * A SHIFT BOUNDARY IS A SNAP AND A DECLARED CLOSURE IS AN ANSWER — a target
    that lands on a maintenance day STAYS there, carrying the closure, so the
    pricer can refuse it by name. Sliding a planner silently past the day they
    are asking about is the defect this rule exists to prevent.

STATED LIMIT. Nothing here prices anything: this module answers WHERE, and
``local_price`` answers WHAT IT COSTS. The route that joins them is guarded in
``tests/test_later_move_route.py``, and the live path in the session close-out.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mre.modules import later_move as lm

REF = datetime(2026, 1, 5)          # a Monday


def _days(n: int, *, closed: tuple[int, ...] = ()) -> list[tuple]:
    """A 07:00-19:00 weekday pattern over ``n`` days from REF. ``closed`` names
    day offsets to drop, which is how a fixture builds a RESOLVED calendar out
    of a PATTERN one."""
    out = []
    for d in range(n):
        day = REF + timedelta(days=d)
        if day.weekday() >= 5 or d in closed:
            continue
        out.append((day.replace(hour=7), day.replace(hour=19)))
    return out


PATTERN = _days(28)
#: Wednesday 2026-01-14 is day 9 — the maintenance day, dropped from the
#: RESOLVED view exactly as ``Explainer._open_windows`` drops it.
OPEN = _days(28, closed=(9,))
CLOSURES = [{"start": datetime(2026, 1, 14, 0, 0),
             "end": datetime(2026, 1, 14, 23, 59, 59),
             "reason": "planned_maintenance"}]


def _resolve(raw, *, start=datetime(2026, 1, 7, 9, 0), run=120.0,
             free=None, closures=None, pattern=None, open_windows=None):
    end = start + timedelta(minutes=run)
    return lm.resolve_target(
        raw, current_start=start, current_end=end,
        open_windows=OPEN if open_windows is None else open_windows,
        pattern_windows=PATTERN if pattern is None else pattern,
        free=OPEN if free is None else free,
        closures=CLOSURES if closures is None else closures,
        working_min=run, splittable=False, min_chunk_min=None)


# ---------------------------------------------------------------------------
# PREMISE — the fixture really does contain what the tests below read
# ---------------------------------------------------------------------------

class TestPremise:

    def test_the_pattern_is_open_on_the_maintenance_wednesday_and_the_resolved_view_is_not(self):
        """Every closure test below depends on the two views DISAGREEING on one
        day. If they ever agree, the tests would pass over a fixture that cannot
        express the distinction they exist to check."""
        wed = datetime(2026, 1, 14)
        in_pattern = any(s.date() == wed.date() for s, _e in PATTERN)
        in_open = any(s.date() == wed.date() for s, _e in OPEN)
        assert in_pattern and not in_open

    def test_the_horizon_holds_several_of_each_weekday(self):
        """The five-Tuesday problem needs more than one Tuesday to be a problem."""
        fridays = [s for s, _e in PATTERN if s.weekday() == 4]
        assert len(fridays) >= 3


# ---------------------------------------------------------------------------
# (a) A NAMED DAY
# ---------------------------------------------------------------------------

class TestNamedDay:

    def test_it_resolves_to_the_nearest_future_instance(self):
        t = _resolve("Friday")
        assert t.kind == lm.KIND_NAMED
        assert t.at == datetime(2026, 1, 9, 7, 0)
        assert t.at > datetime(2026, 1, 7, 9, 0)

    def test_it_reports_how_many_instances_it_chose_between(self):
        """DISCLOSURE, not resolution. The answer names the date it tested and
        says a different Friday can be named — it never silently picks one."""
        t = _resolve("Friday")
        assert t.ambiguous is True
        assert t.instances >= 3

    def test_a_day_that_never_comes_round_again_resolves_to_nothing(self):
        t = _resolve("Sunday")
        assert t.kind == lm.KIND_NAMED
        assert t.at is None and t.instances == 0

    def test_an_iso_date_is_the_one_unambiguous_form(self):
        t = _resolve("2026-01-09")
        assert t.at == datetime(2026, 1, 9, 7, 0)
        assert t.instances == 1

    def test_a_named_day_that_is_shut_LANDS_THERE_AND_CARRIES_THE_CLOSURE(self):
        """THE RULE. Asked for the maintenance Wednesday the resolver hands back
        the maintenance Wednesday, with the closure attached, so the answer can
        say WHY it is not available. Resolving to Thursday instead would answer
        a question about a different day and never mention the one asked about.

        The placement is moved past 2026-01-07 so that Jan 14 is the first
        Wednesday ahead of it — otherwise Jan 7's own Wednesday wins, correctly.
        """
        t = _resolve("Wednesday", start=datetime(2026, 1, 8, 9, 0))
        assert t.at is not None and t.at.date() == datetime(2026, 1, 14).date()
        assert t.closure is not None
        assert t.closure["reason"] == "planned_maintenance"


# ---------------------------------------------------------------------------
# (b) A MAGNITUDE
# ---------------------------------------------------------------------------

class TestMagnitude:

    @pytest.mark.parametrize("raw,minutes", [
        ("a week", 10080), ("two days", 2880), ("3 days", 4320),
        ("a day", 1440), ("two hours", 120), ("out a week", 10080),
    ])
    def test_the_amount_is_read_from_the_planners_words(self, raw, minutes):
        start = datetime(2026, 1, 7, 9, 0)
        t = _resolve(raw, start=start)
        assert t.kind == lm.KIND_MAGNITUDE
        literal = start + timedelta(minutes=minutes)
        # either it landed exactly there, or it snapped forward and said so
        assert t.at == literal or (t.snapped and t.snapped_from == literal
                                   and t.at > literal)

    def test_a_snap_over_non_working_time_is_stated(self):
        """22:00 on a Tuesday is not a shift; 07:00 Wednesday is. The move is
        made and DISCLOSED — a planner who asked for Tuesday evening and got
        Wednesday morning has to be told which one the number is about."""
        t = _resolve("two hours", start=datetime(2026, 1, 7, 18, 0))
        assert t.snapped is True
        assert t.snapped_from == datetime(2026, 1, 7, 20, 0)
        assert t.at == datetime(2026, 1, 8, 7, 0)

    def test_a_magnitude_that_lands_on_a_closure_stays_there(self):
        """The other half of the rule: a SNAP crosses a night, it does not cross
        a declared shutdown."""
        t = _resolve("a week", start=datetime(2026, 1, 7, 9, 0))
        assert t.at.date() == datetime(2026, 1, 14).date()
        assert t.closure is not None


# ---------------------------------------------------------------------------
# (c) THE REASON IS THE TARGET, and (d) the bare fallback
# ---------------------------------------------------------------------------

class TestClosureAndFallback:

    def test_after_the_maintenance_reads_the_declared_closure(self):
        t = _resolve("the day")          # "maintenance wants the machine for the day"
        assert t.kind == lm.KIND_AFTER_CLOSURE
        assert t.closure["reason"] == "planned_maintenance"
        assert t.at == datetime(2026, 1, 15, 7, 0)

    def test_it_names_the_closure_it_read(self):
        t = _resolve("after the maintenance")
        assert t.closure["start"] == CLOSURES[0]["start"]
        assert t.closure["end"] == CLOSURES[0]["end"]

    def test_a_closure_word_with_no_declared_closure_FALLS_BACK_AND_SAYS_SO(self):
        """A machine with nothing declared ahead of the placement has no
        maintenance to be after. Inventing one would be worse than falling back;
        falling back SILENTLY would be worse still."""
        t = _resolve("after the maintenance", closures=[])
        assert t.kind == lm.KIND_NEXT_FIT
        assert t.fell_back is True

    def test_bare_later_finds_the_first_opening_with_room(self):
        start = datetime(2026, 1, 7, 9, 0)
        free = [(datetime(2026, 1, 7, 9, 0), datetime(2026, 1, 7, 11, 0)),
                (datetime(2026, 1, 8, 7, 0), datetime(2026, 1, 8, 8, 0)),
                (datetime(2026, 1, 9, 7, 0), datetime(2026, 1, 9, 19, 0))]
        t = _resolve("", start=start, run=120.0, free=free)
        assert t.kind == lm.KIND_NEXT_FIT
        # Jan 8 has only 60 minutes free; the first stretch with 120 is Jan 9.
        assert t.at == datetime(2026, 1, 9, 7, 0)
        assert t.fell_back is False       # nothing was named, so nothing failed

    def test_no_later_room_at_all_resolves_to_nothing(self):
        t = _resolve("", free=[(datetime(2026, 1, 7, 7, 0),
                                datetime(2026, 1, 7, 9, 0))])
        assert t.at is None

    def test_words_it_cannot_read_fall_back_AND_SAY_THEY_FELL_BACK(self):
        t = _resolve("after the customer calls back")
        assert t.kind == lm.KIND_NEXT_FIT
        assert t.fell_back is True


class TestNextOpening:

    def test_the_alternative_is_computed_not_the_minute_after_the_obstacle(self):
        """(Item 4a) The minute past a collision is very often inside the next
        one. The offer is a scan, so it lands somewhere the whole operation
        fits."""
        free = [(datetime(2026, 1, 8, 7, 0), datetime(2026, 1, 8, 7, 30)),
                (datetime(2026, 1, 8, 15, 0), datetime(2026, 1, 8, 19, 0))]
        at = lm.next_opening_after(free, datetime(2026, 1, 8, 7, 0),
                                   working_min=120.0)
        assert at == datetime(2026, 1, 8, 15, 0)


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — each proven red against a specific reverted behaviour
# ---------------------------------------------------------------------------

class TestNegativeControls:

    def test_a_resolver_that_snapped_past_closures_would_answer_the_wrong_day(self):
        """REVERT: resolve a named day against the RESOLVED calendar (closures
        already subtracted) instead of the shift pattern — the first thing
        anyone would write, and what the first draft of this module did.

        The planner asks about the maintenance Wednesday and is handed the
        Monday after it, with nothing on the surface mentioning maintenance.
        Branch (b) becomes unreachable and the one fact the question is about
        never appears."""
        reverted = _resolve("Wednesday", start=datetime(2026, 1, 8, 9, 0),
                            pattern=OPEN)
        assert reverted.at.date() != datetime(2026, 1, 14).date()
        assert reverted.closure is None
        # the guard above, over the same words, on the same fixture
        ruled = _resolve("Wednesday", start=datetime(2026, 1, 8, 9, 0))
        assert ruled.at.date() == datetime(2026, 1, 14).date()
        assert ruled.closure is not None

    def test_a_resolver_that_took_the_LAST_instance_of_a_named_day_would_be_absurd(self):
        """REVERT: "the nearest future instance" to "some future instance".
        Both are later; only one is the answer, and a resolver with no rule
        would be free to hand back a Friday three weeks out."""
        t = _resolve("Friday")
        fridays = [s for s, _e in PATTERN
                   if s.weekday() == 4 and s > datetime(2026, 1, 7, 9, 0)]
        assert t.at == min(fridays)
        assert t.at != max(fridays)

    def test_a_snap_that_did_not_disclose_would_be_indistinguishable_from_a_hit(self):
        """REVERT: drop ``snapped_from``. The target is still right and the
        answer is still true — and a planner who asked for 20:00 and is quoted a
        price for 07:00 the next morning has no way to tell. Disclosure is the
        difference between a resolution and a substitution."""
        t = _resolve("two hours", start=datetime(2026, 1, 7, 18, 0))
        assert t.snapped_from is not None and t.snapped_from != t.at

    def test_a_fallback_that_did_not_say_so_would_read_as_a_resolution(self):
        """REVERT: drop ``fell_back``. "after the customer calls back" would
        return a perfectly good next-fit target and the answer would present it
        as though it had understood — the confident-wrong shape, wearing a
        correct date."""
        named = _resolve("after the customer calls back")
        bare = _resolve("")
        assert named.at == bare.at          # same instant …
        assert named.fell_back and not bare.fell_back   # … different claim
