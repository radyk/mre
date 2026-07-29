"""ROUTE FALSIFIABILITY — A CONTRACTED ROUTE CAN BE WRONG (Session 4B.15 Item 2).

THE MEASURED FAILURE, and it is the largest one this session found. FIVE
CONSECUTIVE TURNS were swallowed by the capability-coaching route:

    "is that set per machine or per operation"
        -> answered as "how do I enable that?" — the DISJUNCTION discarded and
           replaced by a question the planner did not ask
    "can I make just this one job splittable"
        -> resolved correctly to ORD-000013, then answered generically
    "no, I mean for ORD-000013 specifically"
        -> "how do I enable that?" AGAIN. An explicit correction reparsed into
           the same wrong intent.
    "is ORD-000013 op20 splittable"
        -> capability documentation

The structural fact underneath: A MATCHED ROUTE CURRENTLY CANNOT BE WRONG. Once
the parse names an intent above the confidence floor, that route's canned copy
ships, whatever it says. That inverts R-AI5 — tier one over-claims and tier two
is never reached — and the measurement rubs it in, because synthesis
OUTPERFORMED the routes everywhere it was allowed to run.

WHAT THIS IS
------------
A FALSIFICATION CHECK at the dispatch seam: before a contracted answer is
delivered, does it ADDRESS THE ASKED PREDICATE? Failing that, the question FALLS
THROUGH TO SYNTHESIS rather than shipping canned copy.

``predicate_coverage`` is already this idea, pointed at TOPICS and appending an
honest admission at the delivery seam. This points the same idea at ROUTES, and
its remedy is different in kind: it can re-route. That is a real widening of
jurisdiction and it is why every rule here is narrow, measured, and carries its
specimen.

THE LINE THIS DOES NOT CROSS. It never SELECTS a route. It can only reject the
one the parse chose, and rejection has exactly one destination — the second
tier, which reasons from evidence and labels what it grounds. So no
deterministic classifier returns: this code cannot name a route, only refuse
one. (``Explainer.classify`` and ``rolling_questions.classify_rolling`` are
deleted and must stay deleted; both CHOSE an answer.)

WHY DETERMINISTIC TEXT. The check runs against the TEMPLATE rendering, which is
pure, cheap and faithful to the assembled facts. It runs BEFORE any LLM render,
so a fall-through costs nothing it would not have cost anyway, and the decision
cannot depend on prose a model happened to write.

FAIL OPEN, ALWAYS. Any error here returns "no failure found". A falsifiability
check that can break an answer path is worse than the defect it guards.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

#: Routes exempt by construction. The honest floors and the second tier either
#: said plainly that they could not answer, or stated their own grounding per
#: claim — neither can "fail to address the predicate" in the sense meant here.
#: Kept in step with ``predicate_coverage.COVERED_BY['_floors']``.
EXEMPT_ROUTES: frozenset[str] = frozenset({
    "synthesis", "unmatched", "clarify", "CLARIFY", "unknown-entity",
    "near-miss", "NEAR_MISS", "premise-correction", "prove-it", "REFUSED",
    "confirm-take", "open-card",
})


@dataclass(frozen=True)
class Failure:
    """One falsification. ``rule`` is the check that fired; ``detail`` is what
    the planner said that went unaddressed."""

    rule: str
    detail: str
    #: One clause, appended to the rendered-by line, so a fall-through is never
    #: silent: the planner sees that the contracted answer was rejected and why.
    note: str


# ---------------------------------------------------------------------------
# Rule 1 — SUBJECT SILENCE
# ---------------------------------------------------------------------------
#
# SPECIMEN: "can I make just this one job splittable" resolved to ORD-000013 and
# was answered with generic splitting documentation that never mentioned
# ORD-000013. Then "no, I mean for ORD-000013 specifically" — an explicit
# correction, naming the order outright — got the same generic answer again.
#
# The rule: the parse RESOLVED a subject and the delivered answer never names
# it. An answer about everything is not an answer about the thing they named,
# and the planner has no way to tell those apart when the copy is fluent.

_ID_TAIL_RE = re.compile(r"(\d{2,})\s*$")


def _names(text: str, ref: str) -> bool:
    """Does the answer name this entity? Exact ref first, then the numeric tail
    (``ORD-000013`` is legitimately written ``ORD-13`` or "order 13"), so a
    correctly-scoped answer in a shorter spelling is never called silent."""
    if not ref:
        return True
    low = (text or "").lower()
    if ref.lower() in low:
        return True
    m = _ID_TAIL_RE.search(ref)
    if m:
        digits = m.group(1).lstrip("0") or "0"
        if re.search(rf"(?<!\d){re.escape(digits)}(?!\d)", low):
            return True
    return False


# ---------------------------------------------------------------------------
# Rule 2 — DISCARDED DISJUNCTION
# ---------------------------------------------------------------------------
#
# SPECIMEN: "is that set per machine or per operation" was answered as "how do I
# enable that?". The question offers two alternatives and asks which holds; an
# answer naming NEITHER has not engaged with the question at all. And per the
# brief, an answer that CONTAINS the fact without surfacing it — "that
# OPERATION'S routing line", which does answer per-operation-not-per-machine —
# is still a fall-through, not a pass: the planner asked to be told, not to
# infer.
#
# Deliberately narrow: the alternatives must be short noun phrases either side
# of a bare "or", and BOTH must go unmentioned. One named alternative is a
# choice; zero is a change of subject.

_DISJ_RE = re.compile(
    r"\b(?:is|are|does|do|should|would|will|can)\b[^?]*?"
    r"\b(per|by|at|for|on)\s+([a-z][a-z _-]{1,20}?)\s+or\s+(?:\1\s+)?"
    r"([a-z][a-z _-]{1,20}?)(?=[\s,.?]|$)",
    re.IGNORECASE)


def _disjunction(question: str) -> Optional[tuple[str, str]]:
    """The two alternatives, EACH CARRYING THE QUESTION'S OWN PREPOSITION —
    ("per machine", "per operation"), not ("machine", "operation").

    That distinction is the rule. The coaching answer for splitting says "that
    OPERATION'S routing line", which contains the fact and does not surface the
    choice; a planner who asked "per machine or per operation" has to infer the
    answer from a possessive in a how-to. Per the session brief that is a
    fall-through, not a pass — so the check requires the answer to say "per
    operation" (or "per machine"), which is what choosing looks like."""
    m = _DISJ_RE.search(question or "")
    if not m:
        return None
    prep = m.group(1).strip().lower()
    a, b = m.group(2).strip().lower(), m.group(3).strip().lower()
    if not a or not b or a == b:
        return None
    return f"{prep} {a}", f"{prep} {b}"


def _mentions_word(text: str, phrase: str) -> bool:
    """Is this alternative SURFACED in the answer? The whole phrase, allowing
    only a plural or possessive on its final word."""
    low = " ".join((text or "").lower().split())
    head = phrase.rsplit(" ", 1)
    if len(head) == 1:
        return bool(re.search(rf"(?<![a-z]){re.escape(phrase)}", low))
    lead, last = head
    return bool(re.search(
        rf"(?<![a-z]){re.escape(lead)}\s+{re.escape(last)}(?:s|'s|s')?(?![a-z])",
        low))


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def falsify(question: str, route: str, text: str,
            parsed: Any = None) -> Optional[Failure]:
    """Does this contracted answer fail to address what was asked?

    Returns a ``Failure`` when the answer should FALL THROUGH to synthesis, or
    None — which is the overwhelmingly common case and the only safe default.
    """
    try:
        return _falsify(question, route, text, parsed)
    except Exception:  # noqa: BLE001 — FAIL OPEN. Never break an answer path.
        return None


def _falsify(question: str, route: str, text: str,
             parsed: Any) -> Optional[Failure]:
    if not route or route in EXEMPT_ROUTES or not (text or "").strip():
        return None

    # -- Rule 2: a disjunction where NEITHER alternative is named ----------
    pair = _disjunction(question)
    if pair and not any(_mentions_word(text, p) for p in pair):
        return Failure(
            rule="discarded-disjunction",
            detail=f"{pair[0]} or {pair[1]}",
            note=(f"you asked whether it is {pair[0]} or {pair[1]}, and the "
                  "contracted answer named neither"))

    # -- Rule 1: a resolved subject the answer never names ------------------
    if parsed is not None:
        from mre.contracts.parse import SubjectKind
        for kind in (SubjectKind.ORDER, SubjectKind.MACHINE):
            for subject in parsed.of_kind(kind):
                if not subject.ref:
                    continue
                # A BEYOND-HORIZON subject is answered by the tray route, which
                # legitimately speaks about the window rather than the bar.
                if getattr(subject, "beyond_horizon", False):
                    continue
                if _names(text, subject.ref):
                    continue
                if subject.raw and _names(text, subject.raw):
                    continue
                return Failure(
                    rule="subject-silence",
                    detail=subject.ref,
                    note=(f"you asked about {subject.ref} and the contracted "
                          "answer never mentioned it"))
    return None
