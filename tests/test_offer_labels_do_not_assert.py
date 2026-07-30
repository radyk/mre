"""AN OFFER LABEL NAMES THE QUESTION IT WOULD ANSWER, NEVER THE ANSWER.

Session 4B.19, Items 1 and 2. The ruling is transcribed in
``docs/04-design-history.md`` (2026-07-30); this file is its guard.

THE DEFECT CLASS. Authored copy that is composed BEFORE any read of the board
and states a fact about the board anyway. 4B.17 measured two members on the
pinned exam world, 6/6 runs:

    ROUTE_OFFERS["machine-idle"] = "explain why {machine} carries no work"
        offered for CUT-01, which carries 18 of the board's 56 bars and is the
        BUSIEST machine in the plant. The same sweep answered "whats running on
        CUT-01" with eighteen bars.
    ROUTE_OFFERS["advice"] = "explain why each order is late and price a
        what-if move" — offerable on a board where nothing is late.

The census behind the fix (close-out 4B.19, Item 1) found fourteen in that table
plus one in ``explainer._planner_routes``, and established that THE ENTITY SLOT IS
NOT THE MECHANISM: `advice` carries no slot and is a member all the same. What
makes a label a defect is the ASSERTION.

----------------------------------------------------------------------------
HOW THIS GUARD DECIDES, AND WHAT IT CANNOT DO
----------------------------------------------------------------------------
Two checks, of different kinds, because neither alone is enough.

(1) SHAPE — ``_WHY_PRESUPPOSITION``. A label of the form "why <something> IS/ARE
    /CARRIES/HAS …" presupposes the predicate it asks about: the question it
    names cannot be answered "it isn't" without contradicting the label. This is
    a general shape, not a word list, and it is what catches both 4B.17
    specimens and most of the census.

(2) REGISTER — ``_ASSERTING_PHRASES``. An explicit register of the definite-
    article claims the census actually found ("the lateness across", "the
    submission's problems", "the move you have", "filling up", …).

    ***THIS HALF IS FRAGILE AND THAT IS STATED, NOT PAPERED OVER.*** A register
    of phrases catches the phrasings we have seen. A new label that asserts in
    words nobody has written yet passes it. It is here because it costs nothing
    and it pins the specimens; it is not a proof, and no one should read a green
    run as one. The structural half of the defence is that offer labels are a
    SMALL CLOSED SET in reviewed files — the ruling, not this test, is what makes
    the class impossible, and check (3) is what stops the set growing unwatched.

(3) COVERAGE — every slot-bearing authored table in ``ask_fallback_copy`` must be
    registered in ``_SURFACES`` below. A NEW table added to that module without
    being registered turns this test red, so the guard cannot silently stop
    covering the module it was written for.

INVITATIONS are governed differently and deliberately so: they are rendered AFTER
a board read, from the answer's own computed facts, so an invitation may name a
fact — INVITE_LATE_ORDERS says "why is {order} late?" about the order the route
just proved is the worst late one. What is checked there is that any asserting
invitation carries a required SLOT, which is what forces it to be filled from a
computed fact rather than composed out of nothing.
"""
from __future__ import annotations

import re

import pytest

from mre.modules import ask_fallback_copy as C
from mre.modules.explainer import Explainer, _SUPPORTED_ROUTES

# ---------------------------------------------------------------------------
# (1) THE SHAPE. "why X is/are/carries/has …" — a WHY over a presupposed
# predicate. Note what it deliberately does NOT match: "explain why {order}
# starts when it does" (start-reason), where the predicate is true of every
# placed order and the question has no false-premise reading.
# ---------------------------------------------------------------------------
_WHY_PRESUPPOSITION = re.compile(
    r"\bwhy\b.*?\b(is|are|isn't|aren't|is not|are not|was|were|"
    r"carries|carry|carried|has|have|had)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# (2) THE REGISTER. Definite-article claims about the board, verbatim from the
# 4B.19 census. Add a phrase here when a new one is found in the wild; never
# remove one to make a label pass.
# ---------------------------------------------------------------------------
_ASSERTING_PHRASES = (
    "the lateness across",
    "driving the lateness",
    "the submission's problems",
    "the edits you made",
    "the move you have",
    "your last move",
    "the binding constraint",
    "the gap before",
    "what's wrong with",
    "what is wrong with",
    "filling up",
    "carries no work",
    "carry no work",
    "each order is late",
)


def _assertion(label: str) -> str:
    """The reason a label asserts a board fact, or '' when it names a question."""
    low = (label or "").lower()
    for phrase in _ASSERTING_PHRASES:
        if phrase in low:
            return f"asserting phrase {phrase!r}"
    if _WHY_PRESUPPOSITION.search(label or ""):
        return "why-shape over a presupposed predicate"
    return ""


# ---------------------------------------------------------------------------
# (3) THE SURFACES. Every authored offer surface Item 1's census found, and the
# reason each is here. Registered by NAME so the coverage check can see them.
# ---------------------------------------------------------------------------
_SURFACES = {
    # composed before any board read — the offer table the near-miss bridge uses
    "ROUTE_OFFERS": lambda: list(C.ROUTE_OFFERS.items()),
    # the full-refusal capability menu (generic nouns, still a label)
    "_SUPPORTED_ROUTES": lambda: list(enumerate(_SUPPORTED_ROUTES)),
    # the near-miss/clarify fallback leads that name a subject
    "GENERIC_NOUNS": lambda: list(C.GENERIC_NOUNS.items()),
}

# The slot-bearing tables in ask_fallback_copy that are NOT offer labels: answer
# bodies, filled from facts the route already computed. Named so the coverage
# check can tell "reviewed and out of scope" from "nobody looked".
_ANSWER_BODY_TABLES = {"INVITATIONS"}


def _slotted(text: str) -> bool:
    return any(s in text for s in ("{order}", "{machine}", "{customer}"))


# ===========================================================================
# THE GUARD
# ===========================================================================

@pytest.mark.parametrize("surface", sorted(_SURFACES))
def test_no_offer_label_asserts_a_board_fact(surface):
    """No authored offer label states a fact about the board."""
    offenders = []
    for key, label in _SURFACES[surface]():
        why = _assertion(label)
        if why:
            offenders.append(f"{surface}[{key!r}] {label!r} — {why}")
    assert not offenders, (
        "an offer label is composed before any board read, so a label that "
        "asserts is a claim made without evidence (docs/04 2026-07-30):\n  "
        + "\n  ".join(offenders))


def test_asserting_invitation_must_carry_a_slot():
    """An invitation renders AFTER a board read, so it may name a fact — but only
    through a required slot, which is what forces the fact to be a computed one.
    An asserting invitation with ``slots=()`` could fire over nothing."""
    offenders = []
    for key, inv in C.INVITATIONS.items():
        if _assertion(inv.pattern) and not inv.slots:
            offenders.append(f"INVITATIONS[{key!r}] {inv.pattern!r}")
    assert not offenders, (
        "an invitation that asserts a board fact must carry a required slot so "
        "it can only be filled from the answer's own facts:\n  "
        + "\n  ".join(offenders))


def test_every_route_offer_is_covered_by_the_guard():
    """Coverage, structural half. Every key in the closed route-offer table is
    checked — the guard cannot pass by iterating a subset."""
    checked = {k for k, _ in _SURFACES["ROUTE_OFFERS"]()}
    assert checked == set(C.ROUTE_OFFERS), "ROUTE_OFFERS is not fully iterated"
    assert len(checked) >= 40, (
        f"only {len(checked)} offer labels — the taxonomy has not shrunk that "
        "far, so the table being read is the wrong one")


def test_slot_bearing_tables_in_ask_fallback_copy_are_all_registered():
    """Coverage, anti-drift half. A NEW slot-bearing authored TABLE added to
    ask_fallback_copy must be classified — registered in ``_SURFACES`` as an
    offer surface, or in ``_ANSWER_BODY_TABLES`` as a post-read answer body.
    Without this the guard would keep passing while the module grew a table it
    never looks at, which is exactly how 4B.17's two members survived review."""
    known = set(_SURFACES) | _ANSWER_BODY_TABLES
    unclassified = []
    for name in dir(C):
        if name.startswith("_") or name in known:
            continue
        value = getattr(C, name)
        if isinstance(value, dict):
            texts = [v for v in value.values() if isinstance(v, str)]
        elif isinstance(value, (list, tuple)):
            texts = [v for v in value if isinstance(v, str)]
        else:
            continue
        if any(_slotted(t) for t in texts):
            unclassified.append(name)
    assert not unclassified, (
        "slot-bearing authored table(s) in ask_fallback_copy with no "
        f"classification: {sorted(unclassified)}. Register each in _SURFACES "
        "(offered before a board read) or _ANSWER_BODY_TABLES (rendered after "
        "one) in tests/test_offer_labels_do_not_assert.py.")


def test_planner_routes_examples_do_not_assert():
    """``Explainer._planner_routes`` interpolates a REAL order and machine name,
    picked by ``min()`` of the external refs, into the full-refusal menu. No read
    of lateness enters it, so its first example used to tell a planner that an
    arbitrary on-time order was late (Item 1, member 15)."""
    ex = Explainer.__new__(Explainer)
    ex._order_refs = {"d1": "ORD-000001", "d2": "ORD-000002"}
    ex._machine_refs = {"r1": "CUT-01", "r2": "PAINT-01"}
    lines = ex._planner_routes()
    assert any("ORD-000001" in ln for ln in lines), (
        "premise: the menu must actually interpolate an order name, or this "
        "test proves nothing about interpolated labels")
    offenders = [ln for ln in lines if _assertion(ln)]
    assert not offenders, offenders


# ===========================================================================
# THE PREMISE TESTS
#
# 4B.18's lesson, applied verbatim: ``test_load_populates_all_evidence`` watched
# exactly the quantity its defect changed and PASSED for its entire life, because
# its fixture could not produce the condition. A guard that cannot fail is not a
# guard. These assert that this one's fixture and its detector can.
# ===========================================================================

def test_premise_the_tables_actually_contain_slot_bearing_labels():
    """If ROUTE_OFFERS ever stopped carrying entity slots, every check above
    would still pass while covering nothing that matters."""
    slotted = [k for k, v in C.ROUTE_OFFERS.items() if _slotted(v)]
    assert len(slotted) >= 10, (
        f"only {len(slotted)} slot-bearing offer labels ({slotted}) — the "
        "fixture no longer exercises the interpolation case")


def test_premise_the_detector_catches_the_two_measured_specimens():
    """The 4B.17 specimens, frozen verbatim. The detector must reject BOTH — one
    slot-bearing, one not, which is the pair that proved the slot is not the
    mechanism. Weakening _WHY_PRESUPPOSITION or trimming _ASSERTING_PHRASES to
    make some new label pass turns this red."""
    specimens = {
        # ask_fallback_copy.py:58 as measured, 6/6 runs
        "machine-idle": "explain why {machine} carries no work",
        # ask_fallback_copy.py:50 as measured — NO ENTITY SLOT
        "advice": "explain why each order is late and price a what-if move",
        # explainer._planner_routes, member 15
        "planner-routes": "why is ORD-000001 late — the lateness cause chain",
    }
    for key, label in specimens.items():
        assert _assertion(label), (
            f"the detector no longer rejects the {key} specimen {label!r} — "
            "the guard has been weakened past the defect it was built for")


def test_premise_the_detector_accepts_a_question_shaped_label():
    """The complement. A detector that rejected everything would also pass the
    guard above vacuously — by making the rewrite impossible rather than by
    proving it correct."""
    for label in (
        "check how much work {machine} carries, and what it is eligible to run",
        "check whether {order} is late, and what drove it",
        "explain why {order} starts when it does",
        "show what's running on {machine}",
        "say what would have to change for {order} to start earlier",
    ):
        assert not _assertion(label), (
            f"the detector rejects the question-shaped label {label!r} — it is "
            "over-broad and would force worse copy, not better")


# ===========================================================================
# THE NEGATIVE CONTROL
#
# Planting an asserting label must turn the guard red. Proven in-process here
# and re-proven out-of-process in the close-out (edit the live table, run, revert).
# ===========================================================================

def test_negative_control_a_planted_asserting_label_goes_red(monkeypatch):
    planted = dict(C.ROUTE_OFFERS)
    planted["machine-idle"] = "explain why {machine} carries no work"
    monkeypatch.setattr(C, "ROUTE_OFFERS", planted)
    with pytest.raises(AssertionError, match="without evidence"):
        test_no_offer_label_asserts_a_board_fact("ROUTE_OFFERS")


def test_negative_control_a_planted_unregistered_table_goes_red(monkeypatch):
    monkeypatch.setattr(C, "SOME_NEW_OFFERS",
                        {"x": "explain why {machine} is stopped"}, raising=False)
    with pytest.raises(AssertionError, match="no classification"):
        test_slot_bearing_tables_in_ask_fallback_copy_are_all_registered()
