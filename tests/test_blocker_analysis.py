"""THE BLOCKER ANALYSIS (Session 4B.14 Item 2) — the pure ladder, and the two
verdicts it exists to tell apart.

The specimens are the pinned world's own operations (rolling-c362baa4-1b0),
transcribed as plain data so these tests are fast, offline and independent of
whether that run directory still exists. The figures are the ones measured from
its PERSISTED document — never a re-solve (R-AI4).

THE SPECIMEN THAT DROVE THE SESSION. ORD-000013 runs op10 on CUT-01 (Tue Jan 13
07:00-14:06) and op20 on PAINT-01 (Thu Jan 15 07:00-14:11). The board shows op10
finishing Tuesday with the shift still open and op20 not starting until
Thursday, after a hatched block covering Wednesday. The explainer's answer named
resource contention and cited a timestamp four days off. The true cause is
docs/05 C3: op20 is not splittable, needs 431 working minutes, and 294 remained
before PAINT-01 closed on Tuesday.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mre.modules.blocker_analysis import (
    FAMILY_KEYS,
    UNCOMPUTED_FAMILIES,
    analyze,
    earliest_fit,
)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


#: PAINT-01's resolved calendar over the specimen's span: Mon-Fri 07:00-19:00,
#: with Wednesday Jan 14 removed entirely (a plant-wide planned_maintenance
#: closure — measured: 13 of 15 machines, HEAT-01/02 excepted).
PAINT01_OPEN = [
    (dt("2026-01-12T07:00"), dt("2026-01-12T19:00")),
    (dt("2026-01-13T07:00"), dt("2026-01-13T19:00")),
    # Jan 14: closed.
    (dt("2026-01-15T07:00"), dt("2026-01-15T19:00")),
    (dt("2026-01-16T07:00"), dt("2026-01-16T19:00")),
]

PAINT01_CLOSURES = [{"start": dt("2026-01-14T00:00"),
                     "end": dt("2026-01-14T23:59:59"),
                     "reason": "planned_maintenance"}]


def op20(**over):
    """ORD-000013 op20 as the document records it."""
    kw = dict(
        order="ORD-000013", op_seq=20, machine="PAINT-01",
        actual_start=dt("2026-01-15T07:00"), actual_end=dt("2026-01-15T14:11"),
        working_min=431.0, splittable=False, min_chunk_min=None,
        open_windows=list(PAINT01_OPEN),
        occupied=[],                       # PAINT-01 carries nothing Tue or Thu
        predecessors=[{"op_seq": 10, "machine": "CUT-01",
                       "end": dt("2026-01-13T14:06"), "min_lag_min": 0.0}],
        release=dt("2026-01-05T00:00"),
        closures=list(PAINT01_CLOSURES),
    )
    kw.update(over)
    return analyze(**kw)


# ---------------------------------------------------------------------------
# Item 0's verdict, as a standing regression
# ---------------------------------------------------------------------------

class TestOp20Specimen:
    """Reading (A): the schedule is right, the explanation was wrong."""

    def test_binding_family_is_chunk_fit_not_resource_contention(self):
        a = op20()
        assert a.binding is not None
        assert a.binding.family == "chunkfit"
        assert a.binding.citation == "C3"

    def test_it_could_not_have_started_earlier(self):
        assert op20().verdict == "could_not"

    def test_the_arithmetic_of_the_target_sentence(self):
        """"it needs 7h11m ... and only 4h54m remained" — both halves checked.

        431 working minutes against the 294 that remained between op10's finish
        (14:06) and PAINT-01's close (19:00). If either number moves, the
        session's target sentence is no longer true and this must go red."""
        a = op20()
        sw = a.binding.facts["short_window"]
        assert sw["needed_min"] == pytest.approx(431.0)
        assert sw["available_min"] == pytest.approx(294.0)
        assert sw["start"] == dt("2026-01-13T14:06")
        assert sw["end"] == dt("2026-01-13T19:00")

    def test_the_runner_up_is_the_predecessor(self):
        a = op20()
        assert a.runner_up is not None
        assert a.runner_up.family == "precedence"
        assert a.runner_up.est == dt("2026-01-13T14:06")

    def test_the_wait_spans_the_declared_closure_and_names_its_reason(self):
        cl = op20().binding.facts["closure"]
        assert cl["reason"] == "planned_maintenance"
        assert cl["start"] == dt("2026-01-14T00:00")

    def test_a_closure_that_delayed_nothing_is_not_reported(self):
        """The negative control on the "after maintenance" clause. Same
        operation, same closure, but placed where the closure is irrelevant —
        the analysis must not reach for it just because it is on the calendar."""
        a = op20(actual_start=dt("2026-01-13T07:00"),
                 predecessors=[],
                 working_min=200.0)
        assert "closure" not in (a.binding.facts or {})

    def test_it_would_have_fit_on_tuesday_had_it_been_splittable(self):
        """The counterfactual that proves the binding family is the RIGHT one.

        Same operation, same machine, same predecessor — flip only the R-C3
        class, and Tuesday afternoon becomes usable. If this did not move, the
        analysis would be blaming chunk-fit for something else's doing."""
        a = op20(splittable=True, min_chunk_min=60.0,
                 actual_start=dt("2026-01-13T14:06"))
        assert a.binding.family == "precedence"
        assert a.verdict == "could_not"


# ---------------------------------------------------------------------------
# The distinction that matters most
# ---------------------------------------------------------------------------

class TestCouldNotVersusChose:

    def test_a_placement_later_than_every_bound_is_a_choice(self):
        a = op20(actual_start=dt("2026-01-16T07:00"),
                 actual_end=dt("2026-01-16T14:11"))
        assert a.verdict == "chose"
        assert a.slack_min == pytest.approx(1440.0)   # a full day later

    def test_a_placement_at_the_bound_is_not_a_choice(self):
        assert op20().verdict == "could_not"
        assert op20().slack_min is None

    def test_a_placement_before_every_bound_is_undetermined_never_asserted(self):
        """Our own reading contradicts itself. R-AI3(1): say nothing rather than
        pick a branch and sound certain."""
        a = op20(actual_start=dt("2026-01-12T07:00"))
        assert a.verdict == "undetermined"

    def test_a_minute_of_slop_does_not_flip_the_verdict(self):
        a = op20(actual_start=dt("2026-01-15T07:01"))
        assert a.verdict == "could_not"


# ---------------------------------------------------------------------------
# The ladder itself
# ---------------------------------------------------------------------------

class TestLadder:

    def test_every_family_is_reported_computed_or_not(self):
        assert [e.family for e in op20().estimates] == list(FAMILY_KEYS)

    def test_estimates_are_monotone_along_the_ladder(self):
        prev = None
        for e in op20().estimates:
            if not e.computed:
                continue
            if prev is not None:
                assert e.est >= prev
            prev = e.est

    def test_binding_is_the_earliest_family_attaining_the_maximum(self):
        """The tie rule, exercised where it bites: precedence and chunk-fit land
        on the same instant, and PRECEDENCE is what pushed it there — chunk-fit
        merely failed to push further. Naming chunk-fit would tell a planner to
        go looking for a window problem that does not exist."""
        a = op20(splittable=True, min_chunk_min=60.0,
                 actual_start=dt("2026-01-13T14:06"))
        chunk = a.est_of("chunkfit")
        assert chunk.est == a.binding.est          # both attain the maximum
        assert a.binding.family == "precedence"    # the earlier one wins

    def test_a_pin_binds_over_everything_below_it(self):
        a = op20(pin_start=dt("2026-01-16T09:00"),
                 actual_start=dt("2026-01-16T09:00"),
                 actual_end=dt("2026-01-16T16:11"))
        assert a.binding.family == "pin"
        assert a.verdict == "could_not"

    def test_the_frozen_boundary_binds_when_it_applies(self):
        a = op20(frozen_until=dt("2026-01-16T07:00"), frozen_applies=True,
                 actual_start=dt("2026-01-16T07:00"),
                 actual_end=dt("2026-01-16T14:11"))
        assert a.binding.family == "frozen"

    def test_the_frozen_boundary_is_ignored_when_it_does_not_apply(self):
        a = op20(frozen_until=dt("2026-01-16T07:00"), frozen_applies=False)
        assert a.est_of("frozen").est is None
        assert a.binding.family == "chunkfit"

    def test_a_min_lag_moves_the_precedence_bound(self):
        a = op20(predecessors=[{"op_seq": 10, "machine": "CUT-01",
                                "end": dt("2026-01-13T14:06"),
                                "min_lag_min": 120.0}],
                 splittable=True, min_chunk_min=30.0,
                 actual_start=dt("2026-01-13T16:06"))
        assert a.binding.family == "precedence"
        assert a.binding.est == dt("2026-01-13T16:06")

    def test_resource_occupancy_binds_and_names_its_holder(self):
        a = op20(occupied=[(dt("2026-01-13T14:06"), dt("2026-01-13T17:00"))],
                 holder={"order": "ORD-000028"},
                 splittable=True, min_chunk_min=30.0,
                 actual_start=dt("2026-01-13T17:00"))
        assert a.binding.family == "resource"
        assert "ORD-000028" in a.binding.because

    def test_the_pushers_chain_is_the_causal_story_in_order(self):
        assert [e.family for e in op20().pushers] == [
            "release", "precedence", "chunkfit"]

    def test_uncomputed_families_are_reported_never_silently_omitted(self):
        a = op20()
        assert a.uncomputed == UNCOMPUTED_FAMILIES
        cats = {c for c, _ in a.uncomputed}
        # The docs/05 items this analysis cannot weigh, each with a reason.
        assert {"B3/B5", "B7/B8", "C4", "F3"} <= cats
        assert all(why for _, why in a.uncomputed)


# ---------------------------------------------------------------------------
# earliest_fit — the R-C3 arithmetic, on its own
# ---------------------------------------------------------------------------

class TestEarliestFit:

    WINDOWS = [(dt("2026-01-12T07:00"), dt("2026-01-12T10:00")),   # 180m
               (dt("2026-01-13T07:00"), dt("2026-01-13T19:00"))]   # 720m

    def test_a_non_splittable_op_skips_a_window_too_short(self):
        start, facts = earliest_fit(self.WINDOWS, dt("2026-01-12T07:00"), 300.0,
                                    splittable=False, min_chunk_min=None)
        assert start == dt("2026-01-13T07:00")
        assert facts["short_window"]["available_min"] == pytest.approx(180.0)

    def test_a_non_splittable_op_takes_a_window_that_fits(self):
        start, _ = earliest_fit(self.WINDOWS, dt("2026-01-12T07:00"), 180.0,
                                splittable=False, min_chunk_min=None)
        assert start == dt("2026-01-12T07:00")

    def test_a_splittable_op_accumulates_across_windows(self):
        start, _ = earliest_fit(self.WINDOWS, dt("2026-01-12T07:00"), 300.0,
                                splittable=True, min_chunk_min=60.0)
        assert start == dt("2026-01-12T07:00")

    def test_min_chunk_forbids_opening_in_a_sliver(self):
        """The reason ORD-000011 could not open in the six minutes left at the
        end of Jan 5: a first piece below the floor is not a legal chunk."""
        windows = [(dt("2026-01-05T18:54"), dt("2026-01-05T19:00")),   # 6m
                   (dt("2026-01-06T07:00"), dt("2026-01-06T19:00"))]
        start, facts = earliest_fit(windows, dt("2026-01-05T18:54"), 600.0,
                                    splittable=True, min_chunk_min=60.0)
        assert start == dt("2026-01-06T07:00")
        assert facts["short_window"]["reason"] == "below min_chunk"

    def test_the_near_miss_reported_is_the_LAST_one_not_the_first(self):
        """The whole usefulness of the fact. The FIRST too-short window for
        ORD-000013's op10 is a six-minute sliver on Jan 5, which explains
        nothing; the LAST is Monday 15:37-19:00, which is exactly why it waited
        for Tuesday."""
        windows = [(dt("2026-01-05T18:54"), dt("2026-01-05T19:00")),
                   (dt("2026-01-12T15:37"), dt("2026-01-12T19:00")),
                   (dt("2026-01-13T07:00"), dt("2026-01-13T19:00"))]
        start, facts = earliest_fit(windows, dt("2026-01-05T18:54"), 426.0,
                                    splittable=False, min_chunk_min=None)
        assert start == dt("2026-01-13T07:00")
        assert facts["short_window"]["start"] == dt("2026-01-12T15:37")
        assert facts["short_window"]["available_min"] == pytest.approx(203.0)

    def test_no_fit_at_all_returns_none_rather_than_a_guess(self):
        start, _ = earliest_fit(self.WINDOWS, dt("2026-01-12T07:00"), 5000.0,
                                splittable=False, min_chunk_min=None)
        assert start is None

    def test_occupied_time_is_not_available_time(self):
        """The fit scans open time MINUS other work, so an operation is never
        told it could have gone where another one already is."""
        a = op20(occupied=[(dt("2026-01-12T07:00"), dt("2026-01-12T19:00")),
                           (dt("2026-01-13T07:00"), dt("2026-01-13T19:00")),
                           (dt("2026-01-15T07:00"), dt("2026-01-15T19:00"))],
                 predecessors=[], actual_start=dt("2026-01-16T07:00"),
                 actual_end=dt("2026-01-16T14:11"))
        assert a.binding.family == "chunkfit"
        assert a.binding.est == dt("2026-01-16T07:00")
        assert a.verdict == "could_not"
