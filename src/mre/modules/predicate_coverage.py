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

THE VOCABULARY IS MEASURED, NOT DESIGNED
----------------------------------------
Every topic here costs an accurate ``covers`` declaration on ~40 routes, and a
wrong declaration fires a false rider — which is its own species of lying. So
the mechanism is general and the vocabulary is minimal: a topic is added when a
SPECIMEN has been measured, never speculatively. Adding one is a reviewed
change, like any vocabulary change (CLAUDE.md), and its specimen goes here.

THE SECOND ENTRY (Session 4B.14 Item 3) — ``disagreement``. Measured live on
the pinned board:

    Q: "it seems it should be able to start on tuesday after op10 finishes"
    A: "Is ORD-000013 really on time? Yes - the record agrees."

The planner CHALLENGED the system's causal claim and offered the correct
hypothesis. The parse read a contest, which is right; the contested-fact
assembler knew exactly one proposition, lateness, and answered that. An
affirmative that reads as agreement while addressing nothing that was said.
Call it what it is: DISAGREEMENT LAUNDERING. For a product whose pitch is
"interrogate the schedule" it is the worst available failure — worse than a
wrong number, because the planner cannot tell they were ignored.

Item 3 fixed the ROUTE: `ContestedClaim` lets the parse say which claim is
disputed, and a `timing` contest is answered by the blocker analysis on its own
terms. This entry is the FLOOR under that fix, for the case where the parse
reads a challenge as an ordinary question and no route ever registers that
someone pushed back. It cannot re-route — nothing here can — but it can stop an
answer from sailing past a disagreement in silence.

THE THIRD ENTRY (Session 4B.14 Item 5(b)) — ``temporal_alternative``. Also
measured live: "why can't this order start on Monday" was answered with when it
DOES start. Monday is never addressed. The same predicate swap 4B.13 guarded,
missed because the vocabulary was one entry long and that entry was downtime.
Item 2's `why-here` is the real answer and the parse meaning now points there;
this entry catches the case where an older route answers anyway.
"""
from __future__ import annotations

import re
from typing import Optional


class PredicateTopic:
    """One asked-about property of a subject, its surface forms, and the route
    that can actually speak to it."""

    __slots__ = ("key", "terms", "route", "label", "admission", "pointer",
                 "phrases")

    def __init__(self, key: str, terms: tuple[str, ...], route: str,
                 label: str, admission: str, pointer: str = "",
                 phrases: tuple[str, ...] = ()) -> None:
        self.key = key
        self.terms = terms
        self.route = route
        self.label = label
        self.admission = admission
        #: The authored follow-up sentence. The first topic composed its pointer
        #: from ``label`` ("how much downtime does <machine> have?"), which does
        #: not generalize: the second topic's honest next step is not a question
        #: of that shape. Authored per topic, defaulting to the old composition
        #: so the downtime specimen's wording is unchanged to the character.
        self.pointer = pointer
        #: Multi-word surface forms, matched as substrings rather than as
        #: word-bounded single tokens. A disagreement is recognizable by phrases
        #: ("it seems", "shouldn't it") far more reliably than by any one word.
        self.phrases = phrases


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
    PredicateTopic(
        key="disagreement",
        # Deliberately phrase-led. A single word cannot tell a challenge from a
        # question — "should" appears in half the advice vocabulary — but "it
        # seems", "shouldn't it" and "that can't be right" cannot be anything
        # else. Every form here is something a planner says only when pushing
        # back on a sentence that already exists.
        terms=(),
        phrases=("it seems", "it should be able", "shouldn't it", "shouldnt it",
                 "surely it", "that can't be right", "that cant be right",
                 "that's not right", "thats not right", "i don't think that",
                 "i dont think that", "but it should", "but the machine",
                 "you said", "that doesn't sound right",
                 "that doesnt sound right", "i disagree"),
        route="why-here",
        label="disagreement",
        admission=(
            "I don't think I've engaged with what you actually said — you're "
            "challenging my account, not asking me to repeat it, and the answer "
            "above doesn't address the point you raised."),
        pointer=("Ask \"why is it here?\" with that operation selected and I'll "
                 "give you the binding constraint, so you can check my reasoning "
                 "against yours."),
    ),
    PredicateTopic(
        key="temporal_alternative",
        terms=(),
        # "on monday" / "on tuesday afternoon" / "earlier" / "before that" — a
        # named ALTERNATIVE time. A route that answers with the actual start has
        # not addressed the alternative, which is the whole question.
        phrases=("start on monday", "start on tuesday", "start on wednesday",
                 "start on thursday", "start on friday", "start on saturday",
                 "start on sunday", "start monday", "start tuesday",
                 "start wednesday", "start thursday", "start friday",
                 "go earlier", "start earlier", "start sooner", "run earlier",
                 "why not earlier", "before that"),
        route="why-here",
        label="the alternative time you named",
        admission=(
            "I haven't addressed the time you named — what I said above is when "
            "it does start, not whether it could have started then."),
        pointer=("Ask \"why is it here?\" and I'll give you the binding "
                 "constraint, which is what decides whether that time was "
                 "available."),
    ),
)

#: Routes that DO speak to each topic. A route listed here is trusted to have
#: addressed the topic and never gets the rider.
COVERED_BY: dict[str, frozenset[str]] = {
    #: The floors and the second tier are never treated as having dodged a
    #: predicate: they either said honestly that they could not answer, or they
    #: reasoned over the toolbox and stated their own grounding per claim.
    "_floors": frozenset({
        "synthesis", "unmatched", "clarify", "CLARIFY", "unknown-entity",
        "near-miss", "NEAR_MISS", "premise-correction", "prove-it",
    }),
    "disagreement": frozenset({
        # The blocker analysis IS the answer to a timing challenge (Item 3), and
        # contested-fact is the route whose whole job is meeting a contest.
        # Session 4B.16: so is the counterfactual — "surely it could go earlier"
        # is met head-on by what would have to change for it to.
        "why-here", "contested-fact", "what-would-change",
    }),
    "temporal_alternative": frozenset({
        "why-here", "contested-fact", "gap-between", "coaching",
        "what-would-change",
    }),
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


def _mentions(text: str, topic_or_terms) -> bool:
    """Does the text name this topic? Single tokens are matched word-bounded;
    multi-word PHRASES are matched as substrings, because a phrase already
    carries its own boundaries and word-bounding one would only make it brittle
    about punctuation."""
    low = (text or "").lower()
    terms = getattr(topic_or_terms, "terms", topic_or_terms)
    phrases = getattr(topic_or_terms, "phrases", ())
    if any(re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", low)
           for t in terms if t):
        return True
    return any(p in low for p in phrases if p)


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
    floors = COVERED_BY.get("_floors", frozenset())
    for topic in TOPICS:
        if not _mentions(question, topic):
            continue
        if route in floors or route in COVERED_BY.get(topic.key, frozenset()):
            continue
        if _mentions(answer, topic):
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
    pointer = topic.pointer or (
        f"Ask \"how much {topic.label} does <machine> have?\" and I can answer "
        "that directly.")
    rider = f"{topic.admission} {pointer}"
    marker = "\n[rendered by:"
    if marker in (text or ""):
        head, foot = text.split(marker, 1)
        return f"{head.rstrip()}\n\n{rider}\n{marker}{foot}"
    return f"{(text or '').rstrip()}\n\n{rider}"
