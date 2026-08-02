"""THE MOVABLE FROZEN BOUNDARY — R-F1's mechanics (Session 4B.28 Item 1).

R-F1 was ruled on 2026-07-26 (Session 4B.5 CU6) and nothing has ever built it.
It says the frozen boundary is PLANNER-MOVABLE, and it says exactly what each
direction means:

  PULLING IT EARLIER — a THAW.  Every committed assignment the boundary uncovers
  CONVERTS TO A STANDING PIN at its exact placement.  Nothing becomes
  free-floating.  A thaw changes AUTHORITY (solver-untouchable -> planner-held),
  never POSITION.  That is the whole ruling in one line, and it is the reason
  this module contains no solver: there is nothing to re-solve, because nothing
  moves.

  PUSHING IT LATER — a FREEZE.  Active work before the new boundary becomes
  committed.  A standing pin the boundary crosses is ABSORBED into the
  commitment and recorded as absorbed — the placement is still held, by a
  stronger authority, and the pin leaves the register rather than silently
  co-existing with a commitment that already binds it.

WHY THERE IS A PLAN OBJECT AND NOT JUST AN APPLY.

An accidental three-day thaw of forty assignments must not happen from a slip of
the wrist (R-F1's confirmation beat).  So the ceremony is two calls, and the
count the planner is asked to confirm is computed HERE, by the same function the
apply uses — never by the UI counting bars for itself.  ``BoundaryPlan.digest``
is what ties them together: the apply is handed the digest it confirmed and
REFUSES if the world it described is no longer the world in front of it.  That
is 4B.25's ``expect_delta_abs`` discipline (an offer carries its own promise
back) at a second seam.

WHAT THIS MODULE DELIBERATELY DOES NOT DO.

It never re-solves and it never moves a bar.  A boundary move that changed a
placement would be a different ruling from the one R-F1 made.  Every assignment
comes out of ``apply`` with the chunks it went in with; the guard asserts it.

NAMED LIMIT (docs/07 §5a, this session's close-out): standing pins DO NOT
SURVIVE A SLICE ROLL.  Splicing seam 3 is unbuilt, so the objects a thaw mints
are exactly the objects seam 3 must learn to carry forward.  Within one board's
life the ceremony is complete; across a re-solve it is not.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from mre.modules import standing_pins as sp

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class BoundaryRefused(Exception):
    """The boundary cannot move as asked, for a reason the planner should read.

    Carries a ``code`` so the surface can pick its own wording, and a
    ``sentence`` so a surface that has none is never left composing one from an
    exception's ``str()`` (4B.23: no raw transport string on a planner surface).
    """

    def __init__(self, code: str, sentence: str) -> None:
        self.code = code
        self.sentence = sentence
        super().__init__(sentence)


@dataclass
class BoundaryPlan:
    """What a boundary move WOULD do — computed, never guessed, and identical to
    what the apply will do because the apply calls this first.

    ``direction`` is ``thaw`` (earlier), ``freeze`` (later) or ``none`` (the
    boundary is already there).  ``none`` is a real answer and not an error: the
    confirmation beat says "that is where it already sits", the same register
    R-DP9's no-op drop uses since this session.
    """
    direction: str                                    # thaw | freeze | none
    from_instant: datetime
    to_instant: datetime
    changed: list[dict] = field(default_factory=list)  # per-assignment transitions
    digest: str = ""

    # -- convenience the surfaces read, so nobody re-derives a count ---------
    @property
    def count(self) -> int:
        return len(self.changed)

    @property
    def changed_ops(self) -> list[str]:
        return [c["operation_ref"] for c in self.changed]

    @property
    def pinned_ops(self) -> list[str]:
        return [c["operation_ref"] for c in self.changed if c.get("becomes_pin")]

    @property
    def absorbed_pins(self) -> list[str]:
        return [c["operation_ref"] for c in self.changed if c.get("absorbs_pin")]

    def sentence(self) -> str:
        """The confirmation beat's own words, composed server-side so the count
        on screen and the count that applies are the same number."""
        n = self.count
        if self.direction == "none":
            return ("The frozen boundary is already there — nothing would "
                    "change.")
        bars = f"{n} placement{'s' if n != 1 else ''}"
        if self.direction == "thaw":
            if n == 0:
                return ("Pulling the boundary back to "
                        f"{_human(self.to_instant)} uncovers no committed work "
                        "— the boundary moves and nothing is restyled.")
            return (f"Pulling the boundary back to {_human(self.to_instant)} "
                    f"thaws {bars}. They keep their exact times and machines "
                    "and become pins you hold, instead of commitments the "
                    "solver cannot touch.")
        if n == 0:
            return (f"Pushing the boundary out to {_human(self.to_instant)} "
                    "commits no new work — there is nothing placed in the span "
                    "it crosses.")
        absorbed = len(self.absorbed_pins)
        tail = ""
        if absorbed:
            tail = (f" {absorbed} of them {'is a pin' if absorbed == 1 else 'are pins'} "
                    "you placed; the commitment absorbs "
                    f"{'it' if absorbed == 1 else 'them'}.")
        return (f"Pushing the boundary out to {_human(self.to_instant)} commits "
                f"{bars}. Committed work does not move as the schedule rolls, "
                f"and you cannot drag it.{tail}")

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "from_instant": _iso(self.from_instant),
            "to_instant": _iso(self.to_instant),
            "count": self.count,
            "changed": self.changed,
            "changed_ops": self.changed_ops,
            "pinned_ops": self.pinned_ops,
            "absorbed_pins": self.absorbed_pins,
            "digest": self.digest,
            "sentence": self.sentence(),
        }


def plan_move(document: dict, new_frozen_iso: str,
              standing_pins: Optional[list[dict]] = None) -> BoundaryPlan:
    """Compute the boundary move WITHOUT applying it (the confirmation beat).

    Raises :class:`BoundaryRefused` when the move is not one this board can make
    — a monolithic document (no frozen zone exists), an unparseable instant, or
    a target outside the window the boundary lives in.  Each refusal is a
    statement about the BOARD, and each says which.
    """
    rolling = (document or {}).get("rolling")
    if not rolling:
        raise BoundaryRefused(
            "not_rolling",
            "This board has no frozen boundary to move — it is a single "
            "whole-plan solve, not a rolling window.")
    old = _dt(rolling.get("frozen_until"))
    new = _dt(new_frozen_iso)
    if old is None or new is None:
        raise BoundaryRefused(
            "unreadable_instant",
            "I could not read that as a moment in time, so I did not move the "
            "boundary.")
    win_start = _dt(rolling.get("window_start")) or _dt(rolling.get("reference_origin"))
    win_end = _dt(rolling.get("window_end"))
    # THE BOUNDARY LIVES INSIDE THE WINDOW, AND THE LIMITS ARE DIFFERENT FACTS.
    # Before the window start there is no committed work to thaw and no earlier
    # moment the board renders; past the window end there is nothing solved to
    # freeze. Both are refusals about the BOARD, and each names its own edge
    # rather than reporting one generic "out of range".
    if win_start is not None and new < win_start:
        raise BoundaryRefused(
            "before_window",
            f"The boundary cannot go earlier than the start of this window "
            f"({_human(win_start)}) — there is nothing before it on this board.")
    if win_end is not None and new > win_end:
        raise BoundaryRefused(
            "after_window",
            f"The boundary cannot go past the end of this window "
            f"({_human(win_end)}) — nothing beyond it has been solved yet, so "
            f"there is nothing there to commit.")

    pinned_now = sp.standing_pin_ops(standing_pins)
    changed: list[dict] = []
    direction = "none" if new == old else ("thaw" if new < old else "freeze")

    for a in (document or {}).get("assignments", []) or []:
        op = a.get("operation_ref")
        chunks = a.get("chunks") or []
        if not op or not chunks:
            continue
        start = _dt(chunks[0].get("start"))
        if start is None:
            continue
        state = a.get("commitment_state")
        if direction == "thaw":
            # committed work the boundary no longer covers
            if state != "committed" or not (new <= start < old):
                continue
            changed.append({
                "operation_ref": op,
                "work_orders": list(a.get("work_orders") or []),
                "resource_id": a.get("resource_id"),
                "start": chunks[0].get("start"),
                "from_state": "committed",
                "to_state": "active_window",
                "becomes_pin": True,
                "absorbs_pin": False,
            })
        elif direction == "freeze":
            # active work the boundary now covers
            if state != "active_window" or not (old <= start < new):
                continue
            changed.append({
                "operation_ref": op,
                "work_orders": list(a.get("work_orders") or []),
                "resource_id": a.get("resource_id"),
                "start": chunks[0].get("start"),
                "from_state": "active_window",
                "to_state": "committed",
                "becomes_pin": False,
                "absorbs_pin": op in pinned_now,
            })

    changed.sort(key=lambda c: (str(c["start"]), c["operation_ref"]))
    plan = BoundaryPlan(direction=direction, from_instant=old, to_instant=new,
                        changed=changed)
    plan.digest = _digest(plan)
    return plan


def _digest(plan: BoundaryPlan) -> str:
    """A stable fingerprint of (where it was, where it goes, exactly what
    changes).  The apply is handed the digest the planner confirmed and refuses
    on a mismatch — so a board that moved under the dialog can never be edited
    by a confirmation that described a different one."""
    payload = json.dumps({
        "direction": plan.direction,
        "from": _iso(plan.from_instant),
        "to": _iso(plan.to_instant),
        "changed": [[c["operation_ref"], c["from_state"], c["to_state"]]
                    for c in plan.changed],
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


@dataclass
class BoundaryResult:
    plan: BoundaryPlan
    document: dict                     # the rewritten document (a NEW dict)
    pins: list[dict]                   # the new lineage standing pins
    move_block: dict                   # the contract-1.15 BoundaryMoveBlock


def apply_move(document: dict, new_frozen_iso: str, *,
               standing_pins: Optional[list[dict]] = None,
               authority: str = "",
               expect_digest: Optional[str] = None,
               at: Optional[datetime] = None,
               schedule_id: Optional[str] = None) -> BoundaryResult:
    """Apply the boundary move to a document, returning a NEW document.

    NOTHING MOVES.  Chunks, resources, phases, service outcomes and the ledger
    are carried through untouched; only ``commitment_state``, ``standing_pin``,
    the rolling counts, ``frozen_until`` and the new ``boundary_moves`` entry
    differ.  ``tests/test_frozen_boundary.py`` asserts the placement identity as
    a property, because "authority changed, position did not" is the ruling and
    a comment is not a guard.
    """
    plan = plan_move(document, new_frozen_iso, standing_pins=standing_pins)
    if expect_digest is not None and expect_digest != plan.digest:
        raise BoundaryRefused(
            "stale_confirmation",
            "The board changed between showing you that and this click, so I "
            "did not move the boundary. Try the drag again and you will see "
            "the current numbers.")
    if plan.direction == "none":
        raise BoundaryRefused(
            "no_change",
            "That is where the boundary already sits — nothing to change.")

    changed_by_op = {c["operation_ref"]: c for c in plan.changed}
    doc = json.loads(json.dumps(document))       # deep copy; never mutate input

    for a in doc.get("assignments", []) or []:
        c = changed_by_op.get(a.get("operation_ref"))
        if c is None:
            continue
        a["commitment_state"] = c["to_state"]
        if c["becomes_pin"]:
            # R-F1(b): the thawed placement is now PLANNER-HELD. The board must
            # restyle it, so the flag the board already reads is what carries it.
            a["standing_pin"] = True
        elif c["absorbs_pin"]:
            # R-F1(c): commitment is the stronger authority and it takes over.
            # Leaving the pin flag on would show a planner two claims about one
            # bar, and the register would keep re-applying a constraint the
            # frozen front already binds.
            a["standing_pin"] = False

    rolling = doc.get("rolling") or {}
    rolling["frozen_until"] = _iso(plan.to_instant)
    states = [a.get("commitment_state") for a in doc.get("assignments", []) or []]
    rolling["committed_count"] = sum(1 for s in states if s == "committed")
    rolling["active_count"] = sum(1 for s in states if s == "active_window")

    move_block = {
        "at": _iso(at or datetime.now(UTC)),
        "direction": plan.direction,
        "from_instant": _iso(plan.from_instant),
        "to_instant": _iso(plan.to_instant),
        "authority": authority,
        "changed_ops": plan.changed_ops,
        "pinned_ops": plan.pinned_ops,
        "absorbed_pins": plan.absorbed_pins,
    }
    rolling["boundary_moves"] = list(rolling.get("boundary_moves") or []) + [move_block]
    doc["rolling"] = rolling
    if schedule_id:
        doc["schedule_id"] = schedule_id

    pins = compose_pins(standing_pins, plan)
    return BoundaryResult(plan=plan, document=doc, pins=pins,
                          move_block=move_block)


def compose_pins(standing_pins: Optional[list[dict]],
                 plan: BoundaryPlan) -> list[dict]:
    """The lineage's standing pins after the move.

    A THAW ADDS: every uncovered commitment becomes a pin at its exact
    placement (R-F1(b)).  A FREEZE REMOVES the pins commitment absorbed
    (R-F1(c)) — the first release of a standing pin this product has ever
    performed, and it is deliberately narrow: it releases ONLY pins the frozen
    front now binds anyway, so no placement is ever left unheld.  The general
    ``unpin`` verb remains a named carry-forward and is NOT this.
    """
    existing = list(standing_pins or [])
    if plan.direction == "thaw":
        have = sp.standing_pin_ops(existing)
        out = list(existing)
        for c in plan.changed:
            op = c["operation_ref"]
            if op in have:
                continue
            out.append(sp.normalize_pin(op, c.get("resource_id") or "",
                                        c.get("start") or ""))
        return out
    absorbed = set(plan.absorbed_pins)
    return [p for p in existing if sp.pin_op_id(p) not in absorbed]


# ---------------------------------------------------------------------------
# Why is this bar pinned? — read by the 4B.27 frozen route, never by a second
# reader (R-F1(d)).
# ---------------------------------------------------------------------------


def thaw_origin(document: Any, operation_ref: str) -> Optional[dict]:
    """The boundary move that made ``operation_ref`` a standing pin, or None.

    Reads ``rolling.boundary_moves`` — the contract field, not the registry —
    so the ask path answers from the same document the board renders.  The
    LATEST thaw naming the op wins: a bar thawed, re-frozen and thawed again is
    pinned by the most recent act, and reporting the first one would be a true
    fact about the wrong event (4B.15 Item 0's shape).
    """
    rolling = _rolling_of(document)
    if not rolling:
        return None
    found = None
    for mv in rolling.get("boundary_moves") or []:
        if mv.get("direction") != "thaw":
            continue
        if operation_ref in (mv.get("pinned_ops") or []):
            found = mv
    return found


def _rolling_of(document: Any) -> Optional[dict]:
    if document is None:
        return None
    if isinstance(document, dict):
        return document.get("rolling")
    r = getattr(document, "rolling", None)
    if r is None:
        return None
    return r if isinstance(r, dict) else r.model_dump(mode="json")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    try:
        dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(
            str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return None if dt is None else dt.isoformat()


def _human(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%a %d %b, %H:%M")
