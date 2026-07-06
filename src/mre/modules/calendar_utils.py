"""Calendar flattening utility — pure function, no I/O.

Converts a Calendar entity's base_pattern + exceptions into a list of
concrete available TimeWindows over a given planning horizon.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mre.contracts.entities import CalendarException, TimeWindow
from mre.contracts.vocabularies import CalendarExceptionType


def flatten_calendar(
    base_pattern: dict[str, Any],
    exceptions: list[CalendarException],
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[TimeWindow]:
    """Return available TimeWindows within [horizon_start, horizon_end).

    base_pattern keys:
        weekdays    list[int]  0=Monday … 6=Sunday
        shift_start str        "HH:MM"
        shift_end   str        "HH:MM"
    """
    weekdays: list[int] = base_pattern.get("weekdays", [0, 1, 2, 3, 4])
    sh_h, sh_m = _parse_time(base_pattern.get("shift_start", "07:00"))
    se_h, se_m = _parse_time(base_pattern.get("shift_end", "19:00"))

    tz = horizon_start.tzinfo or timezone.utc

    # Build closure and added windows from exceptions
    closures: list[TimeWindow] = []
    added: list[TimeWindow] = []
    for exc in exceptions:
        if exc.type == CalendarExceptionType.CLOSURE:
            closures.append(exc.window)
        else:
            added.append(exc.window)

    result: list[TimeWindow] = []

    # Walk day by day from horizon_start to horizon_end
    day = horizon_start.replace(hour=0, minute=0, second=0, microsecond=0)
    if day.tzinfo is None:
        day = day.replace(tzinfo=tz)

    while day < horizon_end:
        if day.weekday() in weekdays:
            w_start = day.replace(hour=sh_h, minute=sh_m, second=0, microsecond=0)
            w_end   = day.replace(hour=se_h, minute=se_m, second=0, microsecond=0)

            if not _is_closed(w_start, w_end, closures):
                result.append(TimeWindow(start=w_start, end=w_end))

        day += timedelta(days=1)

    # Append "added" windows that fall within the horizon
    for w in added:
        if w.start >= horizon_start and w.end <= horizon_end:
            result.append(w)

    result.sort(key=lambda w: w.start)
    return result


def _parse_time(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _is_closed(
    shift_start: datetime,
    shift_end: datetime,
    closures: list[TimeWindow],
) -> bool:
    """Return True if any closure window fully covers [shift_start, shift_end)."""
    for cw in closures:
        if cw.start <= shift_start and cw.end >= shift_end:
            return True
    return False
