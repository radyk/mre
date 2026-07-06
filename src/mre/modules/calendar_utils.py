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


# ---------------------------------------------------------------------------
# Pipeline-level helpers (used by both __main__.py and scenario runner)
# ---------------------------------------------------------------------------

UTC = timezone.utc


def compute_horizon(
    demands: list[dict],
    excluded_ids: "set[str] | None" = None,
) -> "tuple[datetime, datetime]":
    """Return (horizon_start, horizon_end) from schedulable demands."""
    excluded = excluded_ids or set()
    schedulable = [d for d in demands if d["id"] not in excluded]

    all_earliest = [
        datetime.fromisoformat(d["earliest_start"]).replace(tzinfo=UTC)
        for d in schedulable if d.get("earliest_start")
    ]
    all_due = [
        datetime.fromisoformat(d["due"]).replace(tzinfo=UTC)
        for d in schedulable if d.get("due")
    ]
    horizon_start = min(all_earliest) if all_earliest else datetime(2026, 7, 13, tzinfo=UTC)
    horizon_start = horizon_start.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = (max(all_due) if all_due else horizon_start).replace(
        hour=23, minute=59, second=59
    ) + timedelta(days=14)
    return horizon_start, horizon_end


def flatten_all_calendars(
    calendars: list[dict],
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[dict]:
    """Flatten each calendar's horizon_resolved for the solver.

    Returns a copy of each calendar dict with 'horizon_resolved' populated.
    """
    from mre.contracts.entities import CalendarException as CalExc, TimeWindow as TW
    from mre.contracts.vocabularies import CalendarExceptionReason, CalendarExceptionType

    result = []
    for cal in calendars:
        excs: list[CalExc] = []
        for e in cal.get("exceptions", []):
            if isinstance(e, dict) and "window" in e:
                tw = TW(
                    start=datetime.fromisoformat(e["window"]["start"]).replace(tzinfo=UTC),
                    end=datetime.fromisoformat(e["window"]["end"]).replace(tzinfo=UTC),
                )
                excs.append(CalExc(
                    window=tw,
                    type=CalendarExceptionType(e.get("type", "closure")),
                    reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                ))
        windows = flatten_calendar(cal.get("base_pattern", {}), excs, horizon_start, horizon_end)
        cal_copy = dict(cal)
        cal_copy["horizon_resolved"] = [
            {"start": w.start.isoformat(), "end": w.end.isoformat()}
            for w in windows
        ]
        result.append(cal_copy)
    return result
