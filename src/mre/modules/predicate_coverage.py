"""CLAUSE (ii) OF THE RELEVANCE GUARD — PREDICATE COVERAGE (Session 4B.13 Item 1).

THE MEASURED FAILURE. Asked live on the pinned board, with ORD-000011 selected:

    Q: "why does this order go through downtime"
    A: "...CUT-01 was held by ORD-000019 until 14:36..."

Every word of that answer is true, it is correctly cited, it is in the right
register — and it does not address downtime at all. It explains why the order
STARTS when it starts. The parse printed its INTERPRETED AS and still landed on
start-time causation, because the nearest intent really is the nearest one.

That is the same species as the false premise this guard's first clause refutes:
an answer about the right SUBJECT and the wrong PREDICATE, delivered with the
full apparatus of correctness. A stranger has no way to tell it apart from an
answer to their question.

WHAT THIS IS, AND WHAT IT IS EMPHATICALLY NOT
---------------------------------------------
It is a FLOOR at the delivery seam: it can only ever append an honest admission
that something asked about was not addressed, plus a pointer to the route that
could address it. It NEVER selects a route, never suppresses an answer, never
changes a figure. Routing remains the parse's, exactly as R-AI5(8) requires —
"the model routes to facts and voices answers; it never grades its own claims",
and its converse here: this code grades coverage; it never routes.

That distinction is why this is not the return of a deterministic classifier
(``Explainer.classify`` / ``rolling_questions.classify_rolling``, both deleted
and both of which must stay deleted). Those chose the answer. This one reads an
answer that has already been chosen and asks whether a thing the planner named
went unmentioned. The nearest existing relative is ``claim_verifier``:
deterministic code, never a model, hardening what the model produced.

THE VOCABULARY IS DELIBERATELY ONE ENTRY LONG
---------------------------------------------
Every topic here costs an accurate ``covers`` declaration on ~40 routes, and a
wrong declaration fires a false rider — which is its own species of lying. So
the mechanism is general and the vocabulary is minimal: a topic is added when a
SPECIMEN has been measured, never speculatively. ``downtime_traversal`` is here
because it was measured. Adding the next one is a reviewed change, like any
vocabulary change (CLAUDE.md), and its specimen goes in the docstring.
"""
from __future__ import annotations

import re
from typing import Optional


class PredicateTopic:
    """One asked-about property of a subject, its surface forms, and the route
    that can actually speak to it."""

    __slots__ = ("key", "terms", "route", "label", "admission")

    def __init__(self, key: str, terms: tuple[str, ...], route: str,
                 label: str, admission: str) -> None:
        self.key = key
        self.terms = terms
        self.route = route
        self.label = label
        self.admission = admission


#: The closed vocabulary. One entry, by design — see the module docstring.
TOPICS: tuple[PredicateTopic, ...] = (
    PredicateTopic(
        key="downtime_traversal",
        # Deliberately narrow. These are words that can only be asking about
        # non-working time; "when", "late" and "start" are excluded precisely
        # because half the contracted vocabulary legitimately answers those.
        terms=("downtime", "down time", "closure", "closures", "closed",
               "off-shift", "off shift", "shut", "shutdown", "weekend",
               "overnight", "non-working", "nonworking"),
        route="downtime",
        label="downtime",
        admission=(
            "I haven't actually answered the downtime part of that — I don't "
            "have evidence about this operation's traversal of non-working "
            "time, and what I said above is about when it starts, not about "
            "the closures it spans."),
    ),
)

#: Routes that DO speak to each topic. A route listed here is trusted to have
#: addressed the topic and never gets the rider.
COVERED_BY: dict[str, frozenset[str]] = {
    "downtime_traversal": frozenset({
        "downtime", "maintenance", "machine-idle", "coaching",
        # The second tier reasons over the toolbox, which includes `calendars`;
        # it states its own grounding per claim, so it is not second-guessed.
        "synthesis", "unmatched",
        # Honest floors are not answers that dodged the predicate.
        "clarify", "CLARIFY", "unknown-entity", "near-miss", "NEAR_MISS",
        "premise-correction",
    }),
}


def _mentions(text: str, terms: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    return any(re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", low)
               for t in terms)


def uncovered_topic(question: str, route: str,
                    answer: str) -> Optional[PredicateTopic]:
    """The topic the QUESTION named that neither the ROUTE covers nor the
    ANSWER mentions — or None, which is the overwhelmingly common case.

    Three conditions, all required, and each one exists to keep the rider rare:

      1. the question names the topic (the closed vocabulary, word-bounded);
      2. the dispatched route is not declared to cover it;
      3. the delivered answer does not mention it either — so a route that
         happened to address the topic anyway is never contradicted by a rider
         claiming it did not. The ANSWER gets the benefit of the doubt over the
         declaration.
    """
    for topic in TOPICS:
        if not _mentions(question, topic.terms):
            continue
        if route in COVERED_BY.get(topic.key, frozenset()):
            continue
        if _mentions(answer, topic.terms):
            continue
        return topic
    return None


def apply_predicate_rider(question: str, route: str,
                          text: str) -> Optional[str]:
    """Append the honest admission when a named predicate went unaddressed.

    Returns the new text, or None when nothing applies (the caller keeps its
    own). Placed above the delivery footer so it reads as part of the answer
    rather than as metadata about it — the same placement rule the cost-proof
    rider uses.
    """
    topic = uncovered_topic(question, route, text)
    if topic is None:
        return None
    rider = (topic.admission + f" Ask \"how much {topic.label} does <machine> "
             f"have?\" and I can answer that directly.")
    marker = "\n[rendered by:"
    if marker in (text or ""):
        head, foot = text.split(marker, 1)
        return f"{head.rstrip()}\n\n{rider}\n{marker}{foot}"
    return f"{(text or '').rstrip()}\n\n{rider}"
