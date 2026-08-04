"""M10 — AUDIENCE SHAPE FOR GOAL QUESTIONS (R-TG4, Session 4A teaching-graft (b)).

THE MEASURED SPECIMEN. On the demo board, at HEAD:

    Q: "there are a lot of orders late what reason can i give my boss and
        what will help lessen the impact"

    A: 134 content lines — a three-line cause mix, then ~95 "ORD-000002 was held
       on CUT-02 until 2026-01-09 12:51 by ORD-000248" lines, then the
       unattributed list, then the money, then "Evidence chain (614 record(s)):"
       and the first fifty of them.

It is the longest answer in every committed sweep, by a factor of three and a
half over the next one. **Every line of it is true.** The planner asked for a
sentence they could say to a person and a lever they could pull; they got an
inventory. The goal was AUDIENCE-SHAPED and the answer was COMPLETENESS-SHAPED.

THE RULE. When a question names a HUMAN GOAL — tell my boss, explain to the
customer, what do I say in the meeting — the answer leads with

    (1) THE ACCOUNT   the one-sentence version a person could say out loud;
    (2) THE LEVER     the single biggest lever this board evidences, promoted
                      from afterthought to headline and labelled for what it is;
    (3) THE OFFER     the inventory OFFERED, never delivered.

WHAT DOES NOT CHANGE, AND THIS IS THE HALF THAT MATTERS. Evidence discipline is
untouched: every sentence still cites or carries its label, the same records are
assembled, ``ordered_records`` is NOT cleared, so the bars still light and a
"show me the evidence" (4B.22's drill-down) opens exactly the records the offer
is offering. What changes is ORDER and BUDGET. The detail is one gesture away,
not gone.

THE FLOOR IS FAMILY-SCOPED, NOT ROUTE-SCOPED — 4A.y's lesson, paid forward. The
census measured the four goal probes reaching THREE different routes
(`lateness-cause`, `advice` twice, `briefing`), so a rule wired to the route the
founder's question happened to hit would have covered one third of its own
family and looked finished. It attaches to the QUESTION and composes from
whichever route answered.

AND IT FAILS OPEN. Where no account and no lever can be composed from what the
route assembled, the shape does not fire at all and the answer renders exactly
as it does today. A floor that could blank an answer would be worse than the
verbosity it exists to fix.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

#: The deterministic marker for a named human audience.
#:
#: MEASURED (census (a), 24 live probes on the demo board): 3 of the 4 goal
#: probes, and 0 of the other 20 — 0/10 teaching, 0/4 mixed, 0/6 board. Perfect
#: specificity on the measured set, 75% sensitivity. That asymmetry is the right
#: one and it is deliberate: a MISSED audience leaves today's answer exactly as
#: it is, and a FALSE one reshapes an answer nobody asked to have reshaped.
#:
#: It can only ever RESHAPE a route that was already going to run. It can never
#: route, and no deterministic classifier returns (R-AI5(2)).
#: IT MATCHES A PERSON, NOT AN ASK. "What do I say about the late orders" names
#: nobody and could be a planner thinking out loud; "what do I say to my boss"
#: puts a human on the other end of the answer. Only the second fires — the
#: conservative side, for the reason above, and it is what the measured 3-of-4
#: sensitivity comes from (the fourth goal probe, "what should i do about all
#: this lateness", names nobody and correctly does not fire).
_AUDIENCE = re.compile(
    r"\b(?:tell|say to|explain (?:this|it|that) to|report (?:this|it) to)\s+"
    r"(them|him|her)\b"
    r"|\b((?:my|the|our)\s+(?:boss|manager|supervisor|director|customer|"
    r"client|team|plant manager|production meeting|morning meeting|meeting|"
    r"stand[- ]?up))\b", re.I)


def names_an_audience(question: str) -> str:
    """The planner's OWN WORDS for who must be told, or "".

    Returns the matched words rather than a bool for the same reason
    ``move_target`` is raw: the answer discloses what it heard, and a floor that
    returned only True would leave the disclosure with nothing to quote.
    """
    m = _AUDIENCE.search(question or "")
    if m is None:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


@dataclass(frozen=True)
class AudienceShape:
    """The three parts of an audience-shaped answer, composed from the route's
    own assembled facts. Nothing here is derived a second time (4B.21's
    discipline): every figure is read off ``key_facts``."""

    audience: str
    account: str
    #: Lines that elaborate the ACCOUNT. Kept apart from ``lever_detail``
    #: because they answer a different question, and rendering them under the
    #: lever's header was a live defect: the `advice` shape put "against a
    #: ledger of 1,667,467.80, that bound leaves up to 1,494,205.31 on the
    #: table" — a fact about the optimality BOUND — directly under "the single
    #: biggest lever this board evidences", beside a sentence about ORD-000112.
    #: Two true lines, one header, and the header was wrong about the second.
    account_detail: tuple[str, ...] = ()
    lever: str = ""
    lever_detail: tuple[str, ...] = ()
    #: A short name for what is being OFFERED rather than delivered ("the
    #: order-by-order breakdown"). Empty when the route had no inventory to
    #: defer, in which case no offer line renders — an offer of nothing is a
    #: false promise.
    offer: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.account)


# ---------------------------------------------------------------------------
# Composition, per assembled shape. Small readers, deliberately: the three
# routes carry different key_facts and pretending otherwise would mean deriving
# a fourth version of figures each of them already computed.
# ---------------------------------------------------------------------------

def _money(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return ""


def _lateness_cause(kf: dict, audience: str) -> Optional[AudienceShape]:
    from mre.modules.ask_fallback_copy import (
        AUDIENCE_ACCOUNT_LATENESS, AUDIENCE_ACCOUNT_LATENESS_CAUSE,
        AUDIENCE_LEVER_HOLD, AUDIENCE_LEVER_WORST, AUDIENCE_OFFER_LATENESS,
    )
    late = int(kf.get("late_count") or 0)
    if late <= 0:
        return None
    sched = kf.get("scheduled_order_count")
    total = int(sched if sched is not None else (kf.get("total_orders") or 0))
    account = (AUDIENCE_ACCOUNT_LATENESS.format(late=late, total=total)
               if total else "")
    if not account:
        return None
    # THE DOMINANT CAUSE, if the mix has one. `cause_mix` is already ranked by
    # the assembler; the leading entry is the one the most orders share, and the
    # sentence says how many rather than implying all of them.
    mix = [m for m in (kf.get("cause_mix") or [])
           if m.get("cause") != "no recorded driver"]
    if mix:
        top = max(mix, key=lambda m: len(m.get("orders") or []))
        account += " " + AUDIENCE_ACCOUNT_LATENESS_CAUSE.format(
            n=len(top.get("orders") or []), cause=top.get("cause", "?"))

    # THE LEVER: the costliest late order, and the concrete hold on it where the
    # occupancy recorded one. Chosen because it is the only candidate the board
    # both RANKS and can name a specific thing to move for — and because money
    # is the axis the audience in the question actually asks about.
    lever, detail = "", []
    lines = kf.get("tardiness_lines") or []
    if lines:
        worst = lines[0]
        cost = _money(worst.get("cost"))
        if cost:
            lever = AUDIENCE_LEVER_WORST.format(order=worst.get("order", "?"),
                                                cost=cost)
            hold = next((c.get("blocked_by") for c in (kf.get("causes") or [])
                         if c.get("order") == worst.get("order")
                         and c.get("blocked_by")), None)
            if hold:
                detail.append(AUDIENCE_LEVER_HOLD.format(
                    machine=hold.get("machine", "?"),
                    blocker=hold.get("blocker_order", "?"),
                    until=hold.get("until", "?")))

    deferred = len([c for c in (kf.get("causes") or []) if c.get("blocked_by")])
    return AudienceShape(
        audience=audience, account=account, lever=lever,
        lever_detail=tuple(detail),
        offer=AUDIENCE_OFFER_LATENESS.format(n=deferred) if deferred else "")


def _from_opener_item(item: dict, audience: str, *,
                      take: str = "") -> Optional[AudienceShape]:
    """`advice` and `briefing` both rank this board by CONSEQUENCE and hand the
    renderer the winning item. That ranked headline IS the account: already
    authored, already computed, and already the thing the route leads with —
    which is why neither needs a second computation (4B.21's discipline).

    THE LEVER IS THE ROUTE'S OWN "My take:", PROMOTED FROM AFTERTHOUGHT TO
    HEADLINE, and that is R-TG4 in one line. Measured on the demo board, the
    `advice` take reads:

        "ORD-000112's 27060-minute slip traces to ORD-000252 holding CUT-01
         until 2026-01-27 19:00 — pulling that earlier is the single biggest
         lever the board gives you today."

    which is exactly the sentence the founder's boss question needed and exactly
    the sentence that was the TWELFTH line of the answer. `_advice_take` reads
    the same solved occupancy the why-late chain does; nothing new is derived.

    A ROUTE WITH NO TAKE CLAIMS NO LEVER. `briefing` has none, so its detail
    lines stand alone rather than being announced as the biggest lever — a
    ranking claim over facts nothing ranked is the assertion R-AI3 forbids.
    """
    headline = (item or {}).get("headline")
    if not headline:
        return None
    # The item's DETAIL lines elaborate the HEADLINE, so they ride with the
    # account. The take is its own claim about a different order entirely.
    return AudienceShape(audience=audience, account=str(headline),
                         account_detail=tuple((item.get("detail") or [])[:2]),
                         lever=str(take or ""),
                         offer=str(item.get("pointer") or ""))


def compose(subject_type: str, key_facts: dict,
            audience: str) -> Optional[AudienceShape]:
    """The shape for one assembled bundle, or None to leave the answer alone.

    None is the common case and the safe one: three routes are covered because
    three routes are what the census measured the family reaching, and a shape
    invented for a route whose facts do not support one would be authored
    copy over evidence nobody assembled."""
    if not audience or not isinstance(key_facts, dict):
        return None
    if subject_type == "lateness_cause":
        return _lateness_cause(key_facts, audience)
    if subject_type == "advice":
        top = key_facts.get("opener_top")
        if isinstance(top, dict):
            return _from_opener_item(top, audience,
                                     take=key_facts.get("take") or "")
        return None
    if subject_type == "briefing":
        # NOT RE-RANKED. The account is the opener's own top worry, whatever the
        # question's words are about. Choosing a different item because the
        # planner said "late orders" would be a relevance classifier reading the
        # question text, which R-AI5(2) forbids and which no amount of
        # usefulness would make legal here. Where the top worry is not what a
        # planner would say in the room, that is a finding about the OPENER's
        # ranking and it is recorded as one.
        items = [i for i in (key_facts.get("opener") or [])
                 if isinstance(i, dict) and not i.get("clean")]
        if items:
            return _from_opener_item(items[0], audience,
                                     take=key_facts.get("take") or "")
        return None
    return None
