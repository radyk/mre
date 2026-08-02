"""THE LATER DIRECTION — where "later" is, and what it costs to go there.

Session 4B.30. "Can I move ORD-000057 later, maintenance wants the machine for
the day" is the question a planner asks every day, and since the counterfactual
shipped (4B.16) it has been answered with three ways to move the order EARLIER.
The census that opens 4B.30 measured seven direction-bearing phrasings on the
demo board: six returned a byte-identical paragraph about starting earlier, and
one of those six was the question that actually asked for earlier — so the two
opposite questions were literally indistinguishable in the output.

THIS MODULE IS THE TARGET HALF. It answers one question and nothing else: given
the planner's own words, WHERE IS "LATER"? The pricing half already exists and
is the right machinery — ``local_price.price_local_move`` (4B.24) holds every
other placement, moves the one bar, recomputes the ledger and REVALIDATES it
against a freshly built model, and its refusals already name the occupant.

WHY A TARGET NEEDS ITS OWN MODULE, AND ITS OWN DISCLOSURE
---------------------------------------------------------
"Later" is not one thing. Three planner shapes reach here and they resolve
differently, so the answer must say WHICH ONE IT READ:

  NAMED     "move it to Friday", "can it wait until Monday". A weekday in a
            horizon with five of them is not an anchor (4B.15 Item 0 — a true
            fact about the wrong Tuesday). Resolved to the nearest FUTURE
            instance past the current placement, and the answer names the
            weekday AND the date it tested.
  MAGNITUDE "push it out a week", "a day later". Current start plus the amount,
            snapped FORWARD to the next open moment when that instant is inside
            a closed calendar — and the snap is stated, because a planner who
            asked for Thursday 14:00 and got Friday 07:00 is entitled to know
            which of those two the number is about.
  NEXT-FIT  bare "later", usually carrying a reason ("maintenance wants the
            machine"). The honest target is the first open, unheld stretch after
            the current placement where the whole operation FITS, computed with
            ``earliest_fit`` under the same R-C3 chunk discipline the blocker
            analysis and the SolverBuilder use.

WHERE THE REASON NAMES AN INTERVAL, THE INTERVAL IS READ. "after the
maintenance" is a target: the answer finds the declared closure it means, says
which one it read (kind, start, end), and puts the target after it. A closure is
DECLARED data (docs/05 C2, ``exceptions`` with a reason) — never a gap in a
window list, because a night shift and a shutdown look identical in a window
list and only one of them is a thing the plant decided (the 4B.14 rule, carried).

A SHIFT BOUNDARY IS A SNAP; A DECLARED CLOSURE IS AN ANSWER
-----------------------------------------------------------
The two are different facts and this module refuses to treat them alike. A
planner who asks for "a week later" and lands at 22:40 on a Tuesday means the
next working moment — snapping to Wednesday 07:00 is help, and it is stated. A
planner who lands on the maintenance day means the maintenance day, and quietly
sliding them past it hides the one fact their question is usually ABOUT.

So a named day and a magnitude resolve against the machine's SHIFT PATTERN
(``pattern_windows`` — closures NOT subtracted): a closed day is reachable, a
night is not. The target then goes to the pricer, which refuses it in docs/05
C1/C2 terms, and the refusal names the closure and offers the next opening —
computed, and priced. Only the bare-"later" fallback resolves against free time,
because that shape is asking WHERE IT COULD GO rather than testing a place.

This is 4B.23's rule at another seam: empty is not open, and shut-for-a-reason
is not merely not-a-working-hour.

THE PARSE NEVER RESOLVES ANY OF THIS. It reports the planner's raw words
(``ParsedQuestion.move_target``); the calendar answers. A model that worked out
which Friday would be authoring a date nobody can check.

PURE: plain data in, a dataclass out. No I/O, no snapshot reader, no model, no
solver. The Explainer supplies the calendar; ``local_price`` prices the result.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from mre.modules.blocker_analysis import _first_moment_inside, earliest_fit

#: The resolution shapes, in the order the resolver tries them. NAMED beats
#: MAGNITUDE ("push it to Friday week" is a day, not an amount) and both beat
#: the fallback, which is what a bare "later" gets.
KIND_NAMED = "named-day"
KIND_MAGNITUDE = "magnitude"
KIND_AFTER_CLOSURE = "after-closure"
KIND_NEXT_FIT = "next-fit"

#: THE BRANCHES, and every one of them has authored copy (Item 4). A later move
#: on a real board is USUALLY A REFUSAL — both of 4B.27's attempts were — so the
#: refusals are the route, not its edge cases, and a version that handled only
#: ``PRICED`` would answer the easy question and go quiet on the common one.
#:
#: The distinction that governs the wording: CHUNKED and UNPRICEABLE are facts
#: about OUR PROCESS; COLLISION, CLOSURE, FROZEN and NO_LATER_FIT are facts
#: about the PLANT. A planner acts on those differently, and 4B.18's
#: ``unreadable`` / 4B.23's ``undetermined`` are the same rule at other seams:
#: never manufacture a claim about the plant out of a limit of ours.
BRANCH_PRICED = "priced"
BRANCH_COLLISION = "collision"
BRANCH_PRECEDENCE = "precedence"
BRANCH_CLOSURE = "closure"
BRANCH_CHUNKED = "chunked"
BRANCH_FROZEN = "frozen"
BRANCH_NO_LATER_FIT = "no-later-fit"
# NOT the rolling window: the MODEL HORIZON. The two are different and
# conflating them cost this session a wrong refusal — the demo board's
# window closes 2026-01-15 while its schedule places work in detail into
# February. A window bounds what a planner is looking at; a horizon bounds
# what there is a variable for, and only the second bounds a price.
BRANCH_BEYOND_GRID = "beyond-grid"
BRANCH_UNPRICEABLE = "unpriceable"
BRANCH_UNPLACED = "unplaced"
BRANCH_MODEL = "model-refused"

_WEEKDAYS: dict[str, int] = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2,
    "wed": 2, "weds": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

#: The words that mean "after the declared closure", not "on a named day". The
#: planner's reason IS the target in this shape — the whole point of "maintenance
#: wants the machine for the day" is that the day is unavailable.
_CLOSURE_WORDS = ("maintenance", "shutdown", "shut down", "closure", "closed",
                  "outage", "downtime", "the day")

_MAGNITUDE_UNITS: dict[str, int] = {
    "minute": 1, "minutes": 1, "min": 1, "mins": 1,
    "hour": 60, "hours": 60, "hr": 60, "hrs": 60,
    "day": 1440, "days": 1440,
    "week": 10080, "weeks": 10080,
    "fortnight": 20160,
    "month": 43200, "months": 43200,
}

_WORD_NUMBERS: dict[str, int] = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2,
    "few": 3,
}

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_MAGNITUDE = re.compile(
    r"\b(\d+|" + "|".join(_WORD_NUMBERS) + r")\s+"
    r"(" + "|".join(sorted(_MAGNITUDE_UNITS, key=len, reverse=True)) + r")\b")


@dataclass(frozen=True)
class LaterTarget:
    """WHERE "later" resolved to, and how — always with the disclosure.

    ``at`` is None only when no later target exists at all inside the material
    the resolver was given; the caller renders that as its own branch (Item 4e),
    never as a silent absence."""

    kind: str
    at: Optional[datetime]
    #: The planner's own words, carried so the answer can quote what it read.
    raw: str = ""
    #: The instant the literal reading landed on, when a snap moved it.
    snapped_from: Optional[datetime] = None
    #: The DECLARED closure this target was placed after, when one was read:
    #: {"start", "end", "reason"}. Reported so "after the maintenance" can say
    #: WHICH maintenance.
    closure: Optional[dict] = None
    #: True when a NAMED day matched more than one date in the material scanned
    #: — the five-Tuesday problem, disclosed rather than resolved silently.
    ambiguous: bool = False
    #: How many later instances of a named weekday were available.
    instances: int = 0
    #: True when the resolver fell back because the planner's words named
    #: something it could not read. The answer SAYS SO — a fallback that reads
    #: as a resolution is the failure this module exists to end.
    fell_back: bool = False

    @property
    def snapped(self) -> bool:
        return self.snapped_from is not None

    @property
    def resolved(self) -> bool:
        return self.at is not None


def _open_at_or_after(open_windows: list[tuple[datetime, datetime]],
                      at: datetime) -> Optional[datetime]:
    """The first moment at or after ``at`` that the machine is open. ``None``
    when the calendar has nothing left — which is a real answer, not an error."""
    return _first_moment_inside(open_windows, at)


def _next_fit(free: list[tuple[datetime, datetime]], at: datetime, *,
              working_min: float, splittable: bool,
              min_chunk_min: Optional[float]) -> Optional[datetime]:
    """The first moment from ``at`` where the WHOLE operation fits in open,
    unheld time — the same scan the blocker analysis uses, pointed forward."""
    start, _facts = earliest_fit(free, at, working_min, splittable=splittable,
                                 min_chunk_min=min_chunk_min)
    return start


def _closure_after(closures: list[dict], at: datetime,
                   on_day: Optional[datetime] = None) -> Optional[dict]:
    """The DECLARED closure the planner means. With a day named, the one that
    overlaps that day; otherwise the first one that has not already ended.

    Never inferred from a gap: docs/05 draws C1 (the pattern) and C2 (the
    declared exception) apart, and only C2 carries a reason a planner would
    recognise."""
    live = [c for c in closures if c.get("end") and c["end"] > at]
    live.sort(key=lambda c: c["start"])
    if on_day is not None:
        day = on_day.date()
        for c in live:
            if c["start"].date() <= day <= c["end"].date():
                return c
    return live[0] if live else None


def _named_day(raw: str) -> Optional[str]:
    low = raw.lower()
    for word in sorted(_WEEKDAYS, key=len, reverse=True):
        if re.search(rf"\b{word}\b", low):
            return word
    return None


def _magnitude_minutes(raw: str) -> Optional[int]:
    low = raw.lower()
    m = _MAGNITUDE.search(low)
    if m is None:
        # Bare "a week" / "a day" without the article captured, and the common
        # elided forms ("out a week" is caught above; "a week later" is not).
        for unit, mins in _MAGNITUDE_UNITS.items():
            if re.search(rf"\b(a|an|another)\s+{unit}\b", low):
                return mins
        return None
    count = m.group(1)
    n = int(count) if count.isdigit() else _WORD_NUMBERS.get(count, 1)
    return n * _MAGNITUDE_UNITS[m.group(2)]


def _weekday_instances(open_windows: list[tuple[datetime, datetime]],
                       weekday: int, after: datetime) -> list[datetime]:
    """Every FUTURE date in the machine's own open calendar falling on this
    weekday, earliest first. Reading the dates off the calendar rather than
    counting forward from the reference date is what keeps a named day from
    resolving onto a day the machine is shut."""
    seen: dict = {}
    for s, e in open_windows:
        if e <= after or s.weekday() != weekday:
            continue
        start = max(s, after)
        if start.weekday() != weekday or start >= e:
            continue
        seen.setdefault(start.date(), start)
    return [seen[d] for d in sorted(seen)]


def _closure_covering(closures: list[dict],
                      at: Optional[datetime]) -> Optional[dict]:
    """The DECLARED closure an instant falls inside, if any. This is what stops
    a snap from sliding a planner past a maintenance day without saying so."""
    if at is None:
        return None
    for c in closures:
        if c.get("start") and c.get("end") and c["start"] <= at < c["end"]:
            return dict(c)
    return None


def resolve_target(raw: str, *,
                   current_start: datetime,
                   current_end: datetime,
                   open_windows: list[tuple[datetime, datetime]],
                   free: list[tuple[datetime, datetime]],
                   closures: list[dict],
                   working_min: float,
                   splittable: bool = False,
                   min_chunk_min: Optional[float] = None,
                   pattern_windows: Optional[
                       list[tuple[datetime, datetime]]] = None) -> LaterTarget:
    """Resolve the planner's words for "later" against the plant's calendar.

    ``open_windows`` is the machine's RESOLVED open calendar (declared closures
    already subtracted); ``pattern_windows`` is the SHIFT PATTERN before that
    subtraction, and ``free`` is the resolved calendar minus everything else
    already placed on the machine. Three views because three questions: where
    the plant nominally works, where it actually works, and where there is room.

    A named day or a magnitude resolves against the PATTERN, so that landing on
    a declared closure is a result and not something the resolver quietly
    corrects; the target then carries the closure it landed in, and the pricer
    refuses it by name. Only a bare "later" resolves against free time, because
    that shape asks where the operation COULD go rather than testing a place.

    EVERY RETURN DISCLOSES. A snap carries what it snapped from, a named day
    carries how many instances it had to choose between, a fallback says it fell
    back. There is no shape of this function that resolves silently.
    """
    raw = (raw or "").strip()
    low = raw.lower()
    pattern = pattern_windows if pattern_windows else open_windows

    # -- (a) an explicit ISO date, the one unambiguous form ------------------
    iso = _ISO_DATE.search(low)
    if iso:
        want = datetime(int(iso.group(1)), int(iso.group(2)),
                        int(iso.group(3)), tzinfo=current_start.tzinfo)
        at = _open_at_or_after(pattern, want)
        return LaterTarget(kind=KIND_NAMED, at=at, raw=raw,
                           snapped_from=(want if at is not None and at != want
                                         else None), instances=1,
                           closure=_closure_covering(closures, at))

    # -- (b) "after the maintenance" — the reason IS the target -------------
    # Tried BEFORE the named day, because "maintenance wants the machine for the
    # day" names a day that is precisely the day it must not go on.
    if any(w in low for w in _CLOSURE_WORDS):
        day = None
        word = _named_day(raw)
        if word is not None:
            insts = _weekday_instances(pattern, _WEEKDAYS[word], current_start)
            day = insts[0] if insts else None
        clo = _closure_after(closures, current_start, on_day=day)
        if clo is not None:
            at = _open_at_or_after(open_windows, clo["end"])
            return LaterTarget(kind=KIND_AFTER_CLOSURE, at=at, raw=raw,
                               closure=dict(clo))
        # The planner named a closure and this machine has none declared ahead
        # of the placement. That is a FACT about the calendar, and pretending to
        # have found one would be worse than falling back and saying so.
        at = _next_fit(free, current_end, working_min=working_min,
                       splittable=splittable, min_chunk_min=min_chunk_min)
        return LaterTarget(kind=KIND_NEXT_FIT, at=at, raw=raw, fell_back=True)

    # -- (c) a named weekday ------------------------------------------------
    word = _named_day(raw)
    if word is not None:
        insts = _weekday_instances(pattern, _WEEKDAYS[word], current_start)
        if insts:
            return LaterTarget(kind=KIND_NAMED, at=insts[0], raw=raw,
                               ambiguous=len(insts) > 1, instances=len(insts),
                               closure=_closure_covering(closures, insts[0]))
        return LaterTarget(kind=KIND_NAMED, at=None, raw=raw, instances=0)

    # -- (d) a magnitude ----------------------------------------------------
    mins = _magnitude_minutes(raw)
    if mins:
        want = current_start + timedelta(minutes=mins)
        at = _open_at_or_after(pattern, want)
        return LaterTarget(kind=KIND_MAGNITUDE, at=at, raw=raw,
                           snapped_from=(want if at is not None and at != want
                                         else None),
                           closure=_closure_covering(closures, at))

    # -- (e) bare "later" ---------------------------------------------------
    at = _next_fit(free, current_end, working_min=working_min,
                   splittable=splittable, min_chunk_min=min_chunk_min)
    return LaterTarget(kind=KIND_NEXT_FIT, at=at, raw=raw,
                       fell_back=bool(raw))


def next_opening_after(free: list[tuple[datetime, datetime]],
                       after: datetime, *, working_min: float,
                       splittable: bool = False,
                       min_chunk_min: Optional[float] = None
                       ) -> Optional[datetime]:
    """The RECOMPUTED alternative a refusal offers (Item 4a/4b): the first open,
    unheld stretch after ``after`` where the whole operation fits.

    Computed, never assumed to be "just after the occupant" — the minute past a
    collision is very often inside the next one, and offering a slot nobody
    checked would repeat the mistake the refusal just caught."""
    return _next_fit(free, after, working_min=working_min,
                     splittable=splittable, min_chunk_min=min_chunk_min)
