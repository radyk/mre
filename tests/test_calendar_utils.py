"""Tests for flatten_calendar — derived from docs/01 §6.5.

Calendar flattening is a pure function: base_pattern + exceptions + horizon
→ concrete list of available TimeWindows. Tests verify the function itself,
not any persistence or entity structure.
"""
import pytest
from datetime import datetime, timezone

UTC = timezone.utc


def _make_window(start_str: str, end_str: str):
    from mre.contracts.entities import TimeWindow
    return TimeWindow(
        start=datetime.fromisoformat(start_str).replace(tzinfo=UTC),
        end=datetime.fromisoformat(end_str).replace(tzinfo=UTC),
    )


def _make_exception(start_str: str, end_str: str, exc_type="closure", reason="planned_maintenance"):
    from mre.contracts.entities import CalendarException, TimeWindow
    from mre.contracts.vocabularies import CalendarExceptionType, CalendarExceptionReason
    return CalendarException(
        window=TimeWindow(
            start=datetime.fromisoformat(start_str).replace(tzinfo=UTC),
            end=datetime.fromisoformat(end_str).replace(tzinfo=UTC),
        ),
        type=CalendarExceptionType(exc_type),
        reason=CalendarExceptionReason(reason),
    )


BASE_WEEKDAY = {
    "weekdays": [0, 1, 2, 3, 4],
    "shift_start": "07:00",
    "shift_end": "19:00",
}

# Horizon: Mon 2026-07-13 to Mon 2026-07-20 (one full week)
H_START = datetime(2026, 7, 13, 0, 0, 0, tzinfo=UTC)
H_END   = datetime(2026, 7, 20, 0, 0, 0, tzinfo=UTC)


class TestBasicFlattening:
    def test_weekdays_produce_windows(self):
        from mre.modules.calendar_utils import flatten_calendar
        windows = flatten_calendar(BASE_WEEKDAY, [], H_START, H_END)
        # Mon-Fri (5 days) within the one-week horizon
        assert len(windows) == 5

    def test_windows_have_correct_shift_times(self):
        from mre.modules.calendar_utils import flatten_calendar
        windows = flatten_calendar(BASE_WEEKDAY, [], H_START, H_END)
        for w in windows:
            assert w.start.hour == 7
            assert w.end.hour == 19

    def test_weekends_excluded(self):
        from mre.modules.calendar_utils import flatten_calendar
        windows = flatten_calendar(BASE_WEEKDAY, [], H_START, H_END)
        # All windows should be on weekdays (0-4)
        assert all(w.start.weekday() < 5 for w in windows)

    def test_weekend_only_pattern_skips_weekdays(self):
        from mre.modules.calendar_utils import flatten_calendar
        weekend_pattern = {"weekdays": [5, 6], "shift_start": "08:00", "shift_end": "14:00"}
        windows = flatten_calendar(weekend_pattern, [], H_START, H_END)
        # Sat (07-18) and Sun (07-19) within the horizon
        assert len(windows) == 2

    def test_empty_horizon_returns_no_windows(self):
        from mre.modules.calendar_utils import flatten_calendar
        windows = flatten_calendar(BASE_WEEKDAY, [], H_START, H_START)
        assert windows == []

    def test_windows_sorted_by_start(self):
        from mre.modules.calendar_utils import flatten_calendar
        windows = flatten_calendar(BASE_WEEKDAY, [], H_START, H_END)
        starts = [w.start for w in windows]
        assert starts == sorted(starts)


class TestClosureExceptions:
    def test_closure_removes_day(self):
        from mre.modules.calendar_utils import flatten_calendar
        # Close Monday 2026-07-13 (first day of horizon)
        exc = _make_exception("2026-07-13T00:00:00", "2026-07-14T00:00:00")
        windows = flatten_calendar(BASE_WEEKDAY, [exc], H_START, H_END)
        # 5 weekdays - 1 closed = 4
        assert len(windows) == 4
        # Monday 07-13 should not appear
        assert not any(w.start.day == 13 for w in windows)

    def test_closure_other_days_unaffected(self):
        from mre.modules.calendar_utils import flatten_calendar
        exc = _make_exception("2026-07-13T00:00:00", "2026-07-14T00:00:00")
        windows = flatten_calendar(BASE_WEEKDAY, [exc], H_START, H_END)
        # Tue-Fri should still be present
        days = {w.start.day for w in windows}
        assert 14 in days  # Tuesday
        assert 15 in days  # Wednesday
        assert 16 in days  # Thursday
        assert 17 in days  # Friday

    def test_multiple_closures(self):
        from mre.modules.calendar_utils import flatten_calendar
        exceptions = [
            _make_exception("2026-07-13T00:00:00", "2026-07-14T00:00:00"),
            _make_exception("2026-07-15T00:00:00", "2026-07-16T00:00:00"),
        ]
        windows = flatten_calendar(BASE_WEEKDAY, exceptions, H_START, H_END)
        # 5 weekdays - 2 closed = 3
        assert len(windows) == 3


class TestAddedExceptions:
    def test_added_exception_appends_window(self):
        from mre.modules.calendar_utils import flatten_calendar
        # Add an overtime window on Saturday
        exc = _make_exception(
            "2026-07-18T08:00:00", "2026-07-18T14:00:00",
            exc_type="added", reason="overtime",
        )
        windows = flatten_calendar(BASE_WEEKDAY, [exc], H_START, H_END)
        # 5 weekdays + 1 added Saturday = 6
        assert len(windows) == 6
        sat = [w for w in windows if w.start.weekday() == 5]
        assert len(sat) == 1
        assert sat[0].start.hour == 8
