"""CAUSAL SUFFICIENCY — a deterministic floor under every cited cause
(Session 4B.14 Item 1).

THE RULE, in one line:

    WHEN AN ANSWER EXPLAINS A QUANTITY BY CITING A CAUSE, THE CITED CAUSE MUST
    ACCOUNT FOR THAT QUANTITY.

THE SPECIMEN. On the pinned board (rolling-c362baa4-1b0) the explainer said:

    ORD-000013 starts Tue 2026-01-13 07:00 because CUT-01 was busy: held by
    ORD-000011 until 2026-01-08 19:00, so ORD-000013 took the next opening.

CUT-01's next opening after Jan 8 19:00 is Jan 9 07:00 — FOUR DAYS before the
start being explained — and CUT-01 carries three further placements in between.
Every clause is individually true. The sentence as a whole is false, because
"so it took the next opening" asserts an arithmetic identity that does not hold.

WHY THE VACUITY TRIPWIRE CANNOT CATCH IT. 4B.5 CU3's ``causal_vacuity`` asks
whether an answer names anything concrete — a driver phrase, an entity beyond
the question's own subjects, a quantity. This answer names an order, a machine
AND a timestamp, so it passes cleanly, and would pass just as cleanly if the
timestamp were off by a year. The two checks are complementary and neither
subsumes the other: vacuity asks whether the answer says anything, sufficiency
asks whether what it says adds up. Sufficiency needs no model judgment at all —
it is subtraction against the persisted document.

WHAT THE ANSWER MAY DO WHEN THE CAUSE IS PARTIAL. Three options, and suppression
is not among them: name the remaining blockers, state that the cited cause is
only part of it, or say nothing about "the next opening". What it may NOT do is
present a first link as the whole chain.

TWO ATTACHMENT POINTS, AND WHY BOTH. The assembler computes the arithmetic and
composes a sentence that is true (``Explainer._blocked_by`` carries
``accounts_for_start``). This module's rider is the FLOOR under that: the LLM
renderer rewords every non-authored answer, and a reword that reintroduces "so
it took the next opening" would put the claim back after the assembler had
removed it. Same discipline as the cost-proof and predicate-coverage riders —
one seam, both renderers, or it is not a floor.

THE ROOT CAUSE THIS SESSION ALSO FIXED, recorded because the arithmetic alone
would have hidden it. The cited timestamp was not a rounding error or a
mis-sorted list: ``Explainer._load_enriched_assignments`` read
``phase_windows["run"][0]`` — the FIRST chunk of a chunked operation — so
ORD-000011's end was reported as its first pause (Jan 8 19:00) rather than its
completion (Jan 12 15:37). 4B.13 fixed the same class in the document assembler
and on the board; the explainer's own row model was still first-chunk-only. A
sufficiency check would have flagged the sentence either way, which is the point
of having one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Sufficiency:
    """Does the cited cause account for the explained quantity?"""

    accounts: bool
    #: The first open moment on the resource at or after the cited end — what
    #: "took the next opening" actually resolves to.
    first_opening: Optional[datetime] = None
    #: Wall minutes between ``first_opening`` and the start being explained.
    #: Zero when the cause accounts for it.
    unexplained_min: float = 0.0
    #: The work that occupies the resource between the two — the blockers the
    #: answer did not name. Each is ``{"order", "start", "end"}``.
    remaining: tuple[dict, ...] = ()
    #: Stated reason when the check could not run at all (no calendar, no start).
    undetermined: str = ""

    @property
    def computed(self) -> bool:
        return not self.undetermined


def first_opening(open_windows: list[tuple[datetime, datetime]],
                  after: Optional[datetime]) -> Optional[datetime]:
    """The earliest open moment at or after ``after`` on a resource's calendar."""
    if after is None:
        return None
    best: Optional[datetime] = None
    for s, e in open_windows:
        if s is None or e is None or e <= after:
            continue
        cand = max(s, after)
        if best is None or cand < best:
            best = cand
    return best


def check_next_opening(*, cited_until: Optional[datetime],
                       explained_start: Optional[datetime],
                       open_windows: list[tuple[datetime, datetime]],
                       occupancy: Optional[list[dict]] = None,
                       tolerance_min: float = 1.0) -> Sufficiency:
    """The arithmetic behind "held until T, so it took the next opening".

    The claim is sufficient exactly when the explained start EQUALS the first
    open window on that resource at or after T. ``occupancy`` is every other
    placement on the resource (``{"order", "start", "end"}``); the ones falling
    between the first opening and the explained start are the blockers the
    answer left unnamed, and they are what an honest answer names instead.

    Tolerance is one minute — the document's grid is whole minutes, and a
    verdict flipping on a rounding artefact is worse than no verdict.
    """
    if cited_until is None or explained_start is None:
        return Sufficiency(accounts=False,
                           undetermined="no cited end or no explained start")
    if not open_windows:
        return Sufficiency(accounts=False,
                           undetermined="no calendar for this resource")
    opening = first_opening(open_windows, cited_until)
    if opening is None:
        return Sufficiency(accounts=False,
                           undetermined="no open window after the cited end")
    gap = (explained_start - opening).total_seconds() / 60.0
    if abs(gap) <= tolerance_min:
        return Sufficiency(accounts=True, first_opening=opening)
    remaining = []
    for row in occupancy or []:
        s, e = row.get("start"), row.get("end")
        if s is None or e is None:
            continue
        if e > opening and s < explained_start:
            remaining.append({"order": row.get("order") or "?",
                              "start": s, "end": e})
    remaining.sort(key=lambda r: r["start"])
    return Sufficiency(accounts=False, first_opening=opening,
                       unexplained_min=round(gap, 3),
                       remaining=tuple(remaining))


# ---------------------------------------------------------------------------
# The delivery-seam floor
# ---------------------------------------------------------------------------

#: The claim shape this guards. An answer using these words asserts that the
#: cited cause exhausts the delay; anything else is free to cite a partial cause
#: as long as it does not claim to be the whole one.
_NEXT_OPENING_CLAIM = re.compile(
    r"took the (?:next|first) opening|took the next available|"
    r"so it (?:then )?started (?:at )?the next", re.IGNORECASE)

#: Wording that already admits partiality. An answer that says this has done the
#: honest thing and must not be lectured a second time — the same
#: benefit-of-the-doubt rule ``predicate_coverage`` applies to the answer text.
_ALREADY_QUALIFIED = re.compile(
    r"only part of|part of the cause|partial|also held by|other work in between|"
    r"further placements|not the whole", re.IGNORECASE)


def sufficiency_rider(fact: Optional[dict], text: str) -> Optional[str]:
    """The admission to append when an answer claims a partial cause as whole.

    ``fact`` is the assembler's ``causal_sufficiency`` key_fact. Returns None —
    the common case — when there is nothing to say: no fact, the cause accounts
    for the quantity, the answer never made the claim, or the answer already
    qualified itself.
    """
    if not isinstance(fact, dict) or fact.get("accounts") is not False:
        return None
    if fact.get("undetermined"):
        return None
    body = text or ""
    if not _NEXT_OPENING_CLAIM.search(body) or _ALREADY_QUALIFIED.search(body):
        return None
    opening = fact.get("first_opening")
    remaining = fact.get("remaining") or []
    lead = ("That is only part of the cause. The machine's next opening after "
            f"the time I cited was {opening}")
    if remaining:
        names = ", ".join(str(r.get("order", "?")) for r in remaining[:3])
        more = f" and {len(remaining) - 3} more" if len(remaining) > 3 else ""
        return (f"{lead}, and it went to {names}{more} before this operation "
                "could have it.")
    return f"{lead}, so something else accounts for the rest of the wait."


def apply_sufficiency_rider(bundle, text: str) -> Optional[str]:
    """Attachment point for the ONE delivery seam both renderers share.

    Placed above the delivery footer, like every other rider, so the admission
    reads as part of the answer rather than as metadata about it."""
    kf = bundle.key_facts if isinstance(getattr(bundle, "key_facts", None),
                                        dict) else {}
    rider = sufficiency_rider(kf.get("causal_sufficiency"), text)
    if rider is None:
        return None
    marker = "\n[rendered by:"
    if marker in (text or ""):
        head, foot = text.split(marker, 1)
        return f"{head.rstrip()}\n\n{rider}\n{marker}{foot}"
    return f"{(text or '').rstrip()}\n\n{rider}"
