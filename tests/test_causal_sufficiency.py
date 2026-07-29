"""CAUSAL SUFFICIENCY (Session 4B.14 Item 1) and the specimens it was measured
on — pinned verbatim, as the session brief requires.

THE RULE: when an answer explains a quantity by citing a cause, the cited cause
must account for that quantity.

THE SPECIMEN, from the live board (rolling-c362baa4-1b0), pinned here verbatim
because the sentence is the artefact:

    ORD-000013 starts Tue 2026-01-13 07:00 because CUT-01 was busy: held by
    ORD-000011 until 2026-01-08 19:00, so ORD-000013 took the next opening.

CUT-01's next opening after Jan 8 19:00 is Jan 9 07:00. The start being
explained is Jan 13 07:00 — four days later — and CUT-01 carries ORD-000011's
own remaining chunks plus other work in between.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from mre.modules.causal_sufficiency import (
    check_next_opening,
    first_opening,
    sufficiency_rider,
)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


#: CUT-01's open calendar across the specimen: Mon-Fri 07:00-19:00, no weekend.
CUT01_OPEN = [
    (dt("2026-01-08T07:00"), dt("2026-01-08T19:00")),
    (dt("2026-01-09T07:00"), dt("2026-01-09T19:00")),
    # Jan 10-11: weekend, no window at all.
    (dt("2026-01-12T07:00"), dt("2026-01-12T19:00")),
    (dt("2026-01-13T07:00"), dt("2026-01-13T19:00")),
]

#: What CUT-01 actually carries between the cited end and the explained start.
CUT01_BETWEEN = [
    {"order": "ORD-000011", "start": dt("2026-01-09T07:00"),
     "end": dt("2026-01-09T19:00")},
    {"order": "ORD-000011", "start": dt("2026-01-12T07:00"),
     "end": dt("2026-01-12T15:37")},
]

#: THE ANSWER, verbatim as the live board produced it.
THE_SPECIMEN_ANSWER = (
    "ORD-000013 starts Tuesday (2026-01-13 07:00) because CUT-01 was busy: it "
    "was held by ORD-000011 until 2026-01-08 19:00, so ORD-000013 took the next "
    "opening.")


class TestTheSpecimen:

    def test_the_cited_cause_does_not_account_for_the_start(self):
        s = check_next_opening(
            cited_until=dt("2026-01-08T19:00"),
            explained_start=dt("2026-01-13T07:00"),
            open_windows=CUT01_OPEN, occupancy=CUT01_BETWEEN)
        assert s.accounts is False
        assert s.computed

    def test_the_next_opening_is_four_days_before_the_explained_start(self):
        s = check_next_opening(
            cited_until=dt("2026-01-08T19:00"),
            explained_start=dt("2026-01-13T07:00"),
            open_windows=CUT01_OPEN, occupancy=CUT01_BETWEEN)
        assert s.first_opening == dt("2026-01-09T07:00")
        assert s.unexplained_min == pytest.approx(4 * 1440.0)

    def test_the_blockers_it_did_not_name_are_named(self):
        s = check_next_opening(
            cited_until=dt("2026-01-08T19:00"),
            explained_start=dt("2026-01-13T07:00"),
            open_windows=CUT01_OPEN, occupancy=CUT01_BETWEEN)
        assert [r["order"] for r in s.remaining] == ["ORD-000011", "ORD-000011"]

    def test_the_specimen_answer_earns_the_rider(self):
        """End to end on the verbatim sentence: an answer making the
        next-opening claim on an insufficient cause is qualified."""
        fact = {"accounts": False, "first_opening": "2026-01-09 07:00",
                "remaining": [{"order": "ORD-000011"}]}
        rider = sufficiency_rider(fact, THE_SPECIMEN_ANSWER)
        assert rider is not None
        assert "only part of the cause" in rider
        assert "2026-01-09 07:00" in rider
        assert "ORD-000011" in rider


class TestTheArithmetic:

    def test_a_sufficient_cause_accounts_and_is_left_alone(self):
        """The machine frees at close of business and the work takes the next
        morning. Here "so it took the next opening" is exactly true."""
        s = check_next_opening(
            cited_until=dt("2026-01-12T19:00"),
            explained_start=dt("2026-01-13T07:00"),
            open_windows=CUT01_OPEN, occupancy=[])
        assert s.accounts is True
        assert s.first_opening == dt("2026-01-13T07:00")

    def test_fixing_the_timestamp_does_NOT_make_the_specimen_sufficient(self):
        """A finding worth keeping. The specimen's cited end was wrong for a
        concrete reason — the explainer's row model read the first CHUNK's end
        (Jan 8 19:00) instead of the operation's (Jan 12 15:37). Repair that
        alone and the sentence is STILL false: CUT-01 comes free mid-shift on
        Monday and the operation does not start until Tuesday morning, because
        the real cause is chunk-fit (docs/05 C3), not contention.

        So the two fixes this session made are genuinely independent. The chunk
        repair makes the cited number true; only the blocker analysis makes the
        CAUSE right, and only this check can tell that the corrected sentence is
        still over-claiming."""
        s = check_next_opening(
            cited_until=dt("2026-01-12T15:37"),          # the CORRECT end
            explained_start=dt("2026-01-13T07:00"),
            open_windows=CUT01_OPEN, occupancy=[])
        assert s.accounts is False
        assert s.first_opening == dt("2026-01-12T15:37")
        assert s.unexplained_min == pytest.approx(923.0)

    def test_a_cause_inside_an_open_window_resolves_to_that_instant(self):
        assert first_opening(CUT01_OPEN, dt("2026-01-12T15:37")) == \
            dt("2026-01-12T15:37")

    def test_a_cause_after_hours_resolves_to_the_next_window(self):
        assert first_opening(CUT01_OPEN, dt("2026-01-08T19:00")) == \
            dt("2026-01-09T07:00")

    def test_a_minute_of_slop_does_not_fail_the_check(self):
        s = check_next_opening(
            cited_until=dt("2026-01-12T19:00"),
            explained_start=dt("2026-01-13T07:01"),
            open_windows=CUT01_OPEN, occupancy=[])
        assert s.accounts is True

    def test_an_uncheckable_claim_is_undetermined_never_asserted_false(self):
        """No calendar means the check could not RUN. Reporting that as
        "the cause is insufficient" would be a claim we did not verify — the
        same species of over-claim this module exists to stop."""
        s = check_next_opening(cited_until=dt("2026-01-08T19:00"),
                               explained_start=dt("2026-01-13T07:00"),
                               open_windows=[], occupancy=[])
        assert s.computed is False
        assert s.undetermined


class TestTheRiderIsRare:
    """Every condition that keeps the rider off an answer that does not need it.
    A guard that fires on innocent answers is its own species of lying."""

    FACT = {"accounts": False, "first_opening": "2026-01-09 07:00",
            "remaining": [{"order": "ORD-000011"}]}

    def test_no_fact_no_rider(self):
        assert sufficiency_rider(None, THE_SPECIMEN_ANSWER) is None

    def test_a_sufficient_cause_gets_no_rider(self):
        assert sufficiency_rider({"accounts": True}, THE_SPECIMEN_ANSWER) is None

    def test_an_undetermined_check_gets_no_rider(self):
        fact = dict(self.FACT, undetermined="no calendar for this resource")
        assert sufficiency_rider(fact, THE_SPECIMEN_ANSWER) is None

    def test_an_answer_that_never_made_the_claim_gets_no_rider(self):
        text = "ORD-000013 runs on CUT-01 from 2026-01-13 07:00 to 14:06."
        assert sufficiency_rider(self.FACT, text) is None

    def test_an_answer_that_already_qualified_itself_is_not_lectured_twice(self):
        """The benefit of the doubt goes to the ANSWER, exactly as
        ``predicate_coverage`` gives it. A route that named the remaining
        blockers must not then be told it did not."""
        text = (THE_SPECIMEN_ANSWER +
                " That is only part of the cause; other work in between held it.")
        assert sufficiency_rider(self.FACT, text) is None

    def test_the_rider_sits_above_the_delivery_footer(self):
        from types import SimpleNamespace

        from mre.modules.causal_sufficiency import apply_sufficiency_rider
        bundle = SimpleNamespace(key_facts={"causal_sufficiency": self.FACT})
        text = THE_SPECIMEN_ANSWER + "\n[rendered by: template | register: testimony]"
        out = apply_sufficiency_rider(bundle, text)
        assert out is not None
        assert out.index("only part of the cause") < out.index("[rendered by:")
