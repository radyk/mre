"""THE MOBILITY PREMISE — is "this can't be moved" true in EITHER direction?

Session 4A.x (the listening docket), Item 3. A question of the form "why can't
this be moved" / "why is this stuck" ASSERTS a fact about the world before it
asks for a reason. The measured specimen, live on the demo board with
ORD-000128 op20 selected:

    Q: "why cant this be moved"
    A: "ORD-000128 op20 couldn't start before Tuesday 2026-01-13 16:09: op10
        finishes at 2026-01-13 16:08."

Every word true. The premise the planner stated is false: MILL-01's next
opening long enough for those 140 working minutes is 2026-01-23 16:21, and a
later drag on this board's siblings prices at $75. The bar can move. What
cannot move is the bar EARLIER, and the answer explained that without ever
saying it was answering a narrower question than the one asked.

THIS IS 4B.13's PREMISE GUARD AT A SECOND SEAM AND A DIFFERENT SHAPE.
``Explainer._verify_placement_premise`` refutes a stated RELATION ("why is X on
Y" where X is not on Y) and REPLACES the answer, because a cause built on a
false placement inherits the falsehood. A mobility premise is not like that:
the explanation that follows is CORRECT, it is simply an answer about one
direction. So the correction is a LEAD, not a replacement — the planner is told
where they are right, and then gets the chain they asked for. R-AI3(4): where
the planner is right, say so plainly and first.

WHAT MAKES A PREMISE TRUE HERE
------------------------------
"Can't be moved" is a claim about what a PLANNER can do to this bar, so the
verdict is keyed to the things that actually stop one:

  HELD      — the bar is inside the committed (frozen) front, or carries a pin
              (docs/05 R-F1, A7/F1). A planner cannot move it without moving
              the boundary or releasing the pin. The premise is TRUE and this
              module says so; no correction fires.
  CHUNKED   — the operation runs in pieces. ``local_price`` declines a chunked
              move BY NAME (4B.24 close-out §7), so this product cannot price
              one either way. The premise is UNDECIDABLE here — recorded as its
              own verdict, never converted into a "yes it can" we have not
              tested and never into a "no it can't" about the plant.
  BOXED IN  — nothing prevented it going earlier is FALSE (the blocker analysis
              says ``could_not``) AND no later opening fits. The premise is
              TRUE, and the answer is the chain that was already there.

Anything else refutes it, in one of two ways, and the answer names WHICH:

  LATER OPEN    — a later opening exists that the whole operation fits inside.
  EARLIER OPEN  — the blocker analysis's verdict is ``chose``: nothing prevented
                  it starting earlier and the solver placed it here anyway.

Both may hold at once; both are reported.

NECESSARY, NEVER SUFFICIENT — 4B.16's rule, carried verbatim
------------------------------------------------------------
``later_at`` is a CALENDAR fact computed from open windows minus occupancy,
under the same R-C3 chunk discipline ``earliest_fit`` uses. It says the room
exists. It does NOT say the move is free, that the successors survive it, or
that the ledger tolerates it — those need the pricer (``local_price``, reached
through ``what-would-change``), and this module's answer must say so rather
than let a planner read an opening as a permission. ``holds_others`` is the
same discipline at the refusal register (4B.24): a fact about OUR scan is never
dressed as a fact about the plant.

PURE: plain data in, a dataclass out. No I/O, no reader, no model, no solver.
The Explainer supplies the calendar and the blocker verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# IS THIS QUESTION ABOUT THE BAR MOVING? — the floor under the parse
# ---------------------------------------------------------------------------
#
# THE PARSE REPORTS; THIS DECIDES (R-AI5(8), applied the way `predicate_coverage`
# applies it). Prompt v17 asks the model to set `move_direction` on `why-here`
# whenever the question is about the bar moving. MEASURED IMMEDIATELY AFTER THE
# BUMP, on the demo board: 0 OF 5 mobility phrasings set it — "why cant this be
# moved", "why can't this bar be moved", "why is this stuck", "why wont it
# budge" and "why cant ORD-000128 op20 be moved" all came back `null`, while
# `swap-move`, where the field has been asked for since 4B.30, set it correctly.
# The model is not refusing the field; it does not reliably see a mobility
# question as a MOVE question, and the same phrasings are the ones a planner
# actually types.
#
# A DISCLOSURE THAT DEPENDS ON A MODEL REMEMBERING A FIELD IS A DISCLOSURE THAT
# WILL SILENTLY STOP — and silence is the entire defect this module answers. So
# the parse's report is kept verbatim as the record of what the model said, and
# this floor decides whether the premise gets checked.
#
# WHAT IT IS NOT: a deterministic classifier. `Explainer.classify` and
# `rolling_questions.classify_rolling` are deleted and must stay deleted; those
# CHOSE THE ANSWER. This runs after the parse has already chosen `why-here`, it
# can only ever add a premise check and a disclosure line to a route that was
# going to run anyway, and it can never send a question anywhere. Its nearest
# relatives are `predicate_coverage` (reads an utterance after routing, to say
# what went unaddressed) and `Explainer._verify_placement_premise` (checks a
# claim the question asserts).
#
# THE VOCABULARY IS MEASURED, NOT DESIGNED — `predicate_coverage`'s rule, and
# for its reason: every phrase here fires a premise check and a disclosure, and
# a wrong one fires them on a question that assumed nothing. Each entry is a
# phrase that can only be ASSERTING that the bar is immobile. Deliberately
# absent: "what's holding it up" and "why the wait", which are ordinary
# `why-here` cause questions this route has always answered, and "why can't it
# be earlier", which STATES its direction and therefore has nothing to disclose.
#
# SESSION 4A.y (the founder listening round) — THE MEASURED MISSES. An 18-phrasing
# census on the demo board found six phrasings a planner typed that this
# vocabulary did not recognise, and the founder's own was one of them:
#
#     "why is this bar trapped here"      -> why-here, no premise check
#     "why is this trapped"               -> why-here, no premise check
#     "why is this wedged in here"        -> why-here, no premise check
#     "why is this bar pinned down here"  -> frozen,   no premise check
#     "nothing can move this can it"      -> why-here, no premise check
#     "why is this jammed here"           -> why-here, no premise check
#
# Five of the six are added below. "jammed" IS NOT, and the exclusion is the
# interesting one: a jam is a thing that happens to a MACHINE, and "why is
# CUT-01 jammed" asserts a plant fact rather than a claim about a bar's
# mobility. The rule this vocabulary is held to — a phrase that can ONLY be
# asserting immobility — excludes it, and a phrase-shaped workaround
# ("jammed here", "jammed in") would be fitting the vocabulary to one probe's
# wording rather than to the language. Named here so it is a decision and not
# an oversight.
#
# "PINNED DOWN" IS ADDED AND "PINNED" IS NOT, for the same reason from the other
# side: 4B.28 gave `frozen` the word "pinned", where it names an AUTHORITY a
# planner releases — "why is ORD-000001 pinned?" is a true question with a true
# answer and nothing to correct. "Pinned down" is the idiom for immobile and
# asserts something else entirely.
_MOBILITY_PHRASES: tuple[str, ...] = (
    "be moved", "been moved", "moved at all", "move at all",
    "cant move", "can't move", "cannot move", "wont move", "won't move",
    "will not move", "cant be moved", "can't be moved", "cannot be moved",
    "cant it move", "can't it move", "cant this move", "can't this move",
    "budge", "immovable", "unmovable",
    "stuck", "locked in place", "locked down", "nailed",
    # Session 4A.y — the measured misses.
    "pinned down", "nothing can move", "nothing will move",
    "nothing moves it", "no way to move",
)

#: Single words that need word boundaries — "locked" must not fire on
#: "unlocked" and "fixed" is excluded entirely (a fixed schedule, a fixed
#: quantity and a fixed bar are three different things). "trapped" and "wedged"
#: joined in 4A.y: both can only be predicated of a thing that cannot move, and
#: neither has the machine-fault reading that keeps "jammed" out.
_MOBILITY_WORDS: tuple[str, ...] = ("locked", "immobile", "frozen",
                                    "trapped", "wedged")

_WORD_RE = re.compile(
    r"(?<![a-z])(" + "|".join(_MOBILITY_WORDS) + r")(?![a-z])", re.IGNORECASE)


def asks_about_moving(question: str) -> bool:
    """Does this question ASSERT that the bar cannot move?

    True only for the closed vocabulary above. False on everything else,
    including every phrasing that names a direction — a stated direction is not
    an assumption and gets no disclosure.

    THIS IS ONE HALF OF THE GATE, NOT THE GATE (stated because it is easy to
    read as the whole of it). The floor fires only where this is True AND the
    parse chose an intent in the mobility family AND a placed operation
    resolved. So "the data seems stuck in December" matches this vocabulary and
    still gets no premise check anywhere: it is a question about the submission,
    it routes nowhere near the family, and there is no bar to assess. The
    vocabulary is deliberately not asked to carry a judgement about what the
    sentence is ABOUT — that is the parse's job, and a keyword test that tried
    to do it would be the deterministic classifier R-AI5 forbids."""
    low = (question or "").lower()
    if any(p in low for p in _MOBILITY_PHRASES):
        return True
    return bool(_WORD_RE.search(low))

#: Words that STATE which way. Closed, deterministic, and narrow on purpose:
#: every entry has to be a direction and nothing else, so "before" (before
#: WHAT), "back" (back where) and "ahead" (ahead of what) are all excluded.
#: A question carrying one of these has stated its direction and is owed no
#: disclosure about which way it was read.
_DIRECTION_WORDS: tuple[str, ...] = (
    "earlier", "sooner", "later", "push out", "pushed out", "pushing out",
    "bring forward", "brought forward", "move up", "moved up",
    "postpone", "delay", "further out", "sooner than", "ahead of schedule",
)


def states_direction(question: str) -> bool:
    """Did the planner say WHICH WAY, in their own words?

    SESSION 4A.y ITEM 1 — WHY THIS IS NOT READ OFF THE PARSE. The listening
    docket measured the model failing to report a direction on 5 of 5 mobility
    phrasings; this round measured the OPPOSITE failure on the same family:

        "this cant move can it"  ->  what-would-change, move_direction=EARLIER

    The planner named no direction. The model supplied one, and because the
    dispatch trusted `move_direction` as a report of what was SAID, a stated
    direction and an invented one were indistinguishable — so the premise check
    was skipped on a question that had assumed everything.

    Both failures have one cure: the direction the planner STATED is a property
    of their sentence, and their sentence is right here. The parse's report is
    still kept verbatim (it is the record of what the model said, and
    `what-would-change` still branches on it — nothing here overwrites a route's
    choice); what this decides is only whether a DISCLOSURE and a PREMISE CHECK
    are owed. R-AI5(8) exactly: the parse reports, the dispatch decides.
    """
    low = (question or "").lower()
    return any(w in low for w in _DIRECTION_WORDS)


#: The verdicts. Two say the planner's premise HOLDS, one says we cannot tell,
#: two REFUTE it — and a refutation names the direction that is open, because
#: "it can move" without a direction is the same silence this module exists to
#: end.
VERDICT_HELD = "held"                  # committed / pinned — premise TRUE
VERDICT_BOXED_IN = "boxed-in"          # earlier bound, nothing later — TRUE
VERDICT_UNDECIDABLE = "undecidable"    # chunked — we cannot price it either way
VERDICT_LATER_OPEN = "later-open"      # premise FALSE: later fits
VERDICT_EARLIER_OPEN = "earlier-open"  # premise FALSE: nothing bound it earlier

#: The verdicts that REFUTE the planner's premise. Read this rather than
#: comparing strings at a call site: a verdict added later inherits the
#: classification here instead of being silently treated as "holds".
REFUTING = frozenset({VERDICT_LATER_OPEN, VERDICT_EARLIER_OPEN})

#: Why a HELD bar is held. Two declared authorities, never blended: a frozen
#: front is a property of the ROLLING PLAN (R-F1) and a pin is a property of
#: THIS OPERATION (A7/F1), and a planner acts on them differently — one is a
#: boundary drag, the other a release.
HELD_FROZEN = "committed"
HELD_PINNED = "pinned"


@dataclass(frozen=True)
class MobilityVerdict:
    """What this product can say about whether one placed operation can move.

    ``holds`` is the planner's premise, not ours: True means "can't be moved"
    was a fair thing to say. ``undecidable`` is deliberately NOT folded into
    either — 4B.18's fourth state and 4B.23's tri-state, the ruled species
    again: a claim about the PLANT is never manufactured from a limit of OUR
    METHOD.
    """

    verdict: str
    #: The first later instant where the WHOLE operation fits, or None. A
    #: calendar fact; never a price and never a promise (see the module note).
    later_at: Optional[datetime] = None
    #: The blocker analysis's verdict for the EARLIER direction, verbatim
    #: ("could_not" / "chose" / anything else it reports), or None when it
    #: could not be computed at all.
    earlier_verdict: Optional[str] = None
    #: Set only on VERDICT_HELD — HELD_FROZEN or HELD_PINNED.
    held_kind: str = ""
    #: The instant the hold runs to (the frozen boundary) or at (the pin).
    held_at: Optional[datetime] = None
    #: Set only on VERDICT_UNDECIDABLE — how many pieces the operation runs in.
    chunk_count: int = 0
    #: Every direction this verdict found open, in the order a planner would
    #: act on them. Empty when the premise holds.
    open_directions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def holds(self) -> bool:
        """True when "it can't be moved" was a fair thing for the planner to
        say. UNDECIDABLE is False here and False in ``refutes`` too — it is
        neither, and a caller that treats "not holds" as "refuted" would be
        manufacturing the claim this dataclass refuses to make."""
        return self.verdict in (VERDICT_HELD, VERDICT_BOXED_IN)

    @property
    def refutes(self) -> bool:
        return self.verdict in REFUTING


def assess(*, held_kind: str = "", held_at: Optional[datetime] = None,
           chunk_count: int = 0,
           later_at: Optional[datetime] = None,
           earlier_verdict: Optional[str] = None) -> MobilityVerdict:
    """Decide the mobility premise from facts the caller has already computed.

    The order of the tests is the whole ruling and it is not arbitrary:

      1. HELD first. A committed or pinned bar cannot be moved by a planner
         whatever the calendar says, so an opening past it is a true fact about
         an irrelevant question — exactly the "stale true fact" 4B.14 refused
         to pad a causal answer with.
      2. CHUNKED second, before any opening is read AND before the earlier
         direction. The pricer declines a chunked move by name, so an opening
         we could never price is not an answer; saying "it can go there" would
         be a claim about the plant this product has not tested. It outranks
         the EARLIER refutation for a second, independent reason 4B.14 already
         named: a ``chose`` verdict on a splittable operation is a LOWER BOUND
         — the fit scan treats working minutes as one divisible quantity, so
         "nothing prevented it" is weaker there than it is on an atomic op, and
         a premise CORRECTION is too strong a thing to build on a lower bound.
         The earlier half of the answer still states the ``chose`` verdict in
         its own words; what it does not do is lead with it.
      3. Only then the two open directions, LATER first because it is the one
         the question is usually about and the one the product can price.

    ``earlier_verdict`` is passed through verbatim rather than being reduced to
    a boolean: "chose" and "could_not" are different facts, and an
    UNRECOGNISED value must not become either (4B.23's fail-safe rule — an
    unknown status fails to the state that claims least).
    """
    if held_kind:
        return MobilityVerdict(verdict=VERDICT_HELD, held_kind=held_kind,
                               held_at=held_at,
                               earlier_verdict=earlier_verdict)
    if chunk_count > 1:
        return MobilityVerdict(verdict=VERDICT_UNDECIDABLE,
                               chunk_count=chunk_count,
                               earlier_verdict=earlier_verdict)
    directions: list[str] = []
    if later_at is not None:
        directions.append("later")
    # ONLY `chose` refutes the earlier direction. `could_not` says a family
    # bound it; anything else — including the blocker analysis's own
    # can't-attribute verdict and None — claims nothing, which is the honest
    # floor when the ladder did not line up.
    if earlier_verdict == "chose":
        directions.append("earlier")
    if not directions:
        return MobilityVerdict(verdict=VERDICT_BOXED_IN, later_at=None,
                               earlier_verdict=earlier_verdict)
    return MobilityVerdict(
        verdict=VERDICT_LATER_OPEN if later_at is not None
        else VERDICT_EARLIER_OPEN,
        later_at=later_at, earlier_verdict=earlier_verdict,
        open_directions=tuple(directions))
