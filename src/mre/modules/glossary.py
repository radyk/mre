"""THE PRODUCT'S OWN WORDS — R-TE1's governed glossary.

Session 4A teaching-graft (d.3). The founding specimen, from the founder's
freewheel round on the demo board: a CONTRACTED route (`solve-optimality`)
answered with the word "seed" nine times — *"this board is the best of 3 seeded
searches, the one at seed 44"* — and the planner asked what it meant. Twice.
Both times the product refused, each refusal holding a door handle that opens on
the wrong room: an entity CLARIFY (*"name an order, a machine, or a
capability"*) and the capability coach (*"I don't recognize which capability you
mean"*). **The product could not explain its own vocabulary.**

WHAT THIS IS NOT, and the wall is the ruling rather than a caveat. This is not a
documentation browser, not search over docs, and not a general "define X"
feature. The TRIGGER CONTRACT is the wall: this route answers only about words
**this product has already said to this planner, on this board**
(`term_memory`), which is a property of the transcript and is checkable.

CLAUSE (2)'s CITATION BAR, and why every entry pays it. A definition of one of
our words is a claim about THIS PRODUCT's behaviour — R-TG6 (i)'s species
exactly — so it may never wear the general-knowledge label and may never be
offered uncited. Every entry below names the artifact that defines it, and
``tests/test_glossary.py`` resolves every one of those citations against the
real document. An entry whose citation target moves fails a test rather than
quietly becoming folklore, which is clause (4).

FIRST EDITION SCOPE IS THE C1 CENSUS, not judgement
(`tools/spikes/teaching_graft_d3/c1_vocabulary_census.py`): 53 committed
transcripts, 1,810 rendered answers, and a term the product has never emitted is
out by construction. Two measured consequences worth keeping:

  * `member` and `portfolio` — R-BK1's own words — are **never emitted**. The
    answer says "seeded searches" and "seed 44" instead, which is part of why
    the planner had to ask.
  * `calibrated` in R-CAL1's sense is **never emitted** either. Its single hit
    in 1,810 answers is the ordinary machine-shop sense ("tooling, fixtures,
    calibration, cleanup"), so it is OUT of this edition — putting it in would
    define a word the planner has not been shown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

#: Where a citation resolves. `RULING` and `SPEC` are checked against the real
#: document by test; `RUN` is resolved at answer time against this run's own
#: records, and the entry says which figure it will show.
CITE_RULING = "ruling"
CITE_SPEC = "spec"
CITE_RUN = "run"


@dataclass(frozen=True)
class GlossaryEntry:
    """One of our words, with the artifact that defines it.

    ``body`` is AUTHORED COPY — never model prose. ``patterns`` is how the word
    is recognised in a rendered answer (inflections included: a planner asking
    about "seeds" is asking about "seed").
    """
    term: str
    #: The one-line answer to "what do you mean X".
    body: str
    #: (kind, target, human phrase). Rendered as the citation line.
    citations: tuple[tuple[str, str, str], ...]
    #: Regex alternatives that count as an emission of this term.
    pattern: str
    #: Which run figure the answer additionally shows, when it has one.
    run_figure: Optional[str] = None
    #: Doors offered beneath the definition — real questions, checked by the
    #: exam's own dead-door guard.
    doors: tuple[str, ...] = field(default_factory=tuple)


GLOSSARY: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        term="seed",
        body=(
            "A seed is the starting number for the solver's search. The same "
            "plant solved twice with different seeds gives two different "
            "schedules, both legal, and usually not the same price — so this "
            "board is not \"the\" answer, it is the cheapest of several runs "
            "we made on purpose."),
        citations=(
            (CITE_RULING, "R-BK1",
             "the published board is a portfolio, not a draw: K deterministic "
             "runs at consecutive seeds, best by ledger, ties by lowest seed"),
            (CITE_RUN, "portfolio",
             "this run's own members and what each of them reached"),
        ),
        pattern=r"\bseed(?:s|ed|ing)?\b",
        run_figure="portfolio",
        # ONE DOOR, NOT TWO, AND THE EXAM'S OWN GUARD IS WHY. The first draft
        # also offered "what would change if the plan were re-solved", which
        # reads perfectly well and parses to NO INTENT — `dead-door` fired on it
        # three times in this route's first bank run. A door into a wall is the
        # defect that guard exists to catch, and it caught this session's own
        # new copy. One real door beats two where one of them is scenery.
        doors=("is this the cheapest possible plan",),
    ),
    GlossaryEntry(
        term="gap",
        body=(
            "The gap is how much room is left in the PROOF, not a score for "
            "the schedule. The solver holds a plan it found and a bound on "
            "what is conceivably possible; the gap is the distance between "
            "them. A large gap says we could not prove no cheaper plan "
            "exists — it does not say this one is bad."),
        citations=(
            (CITE_RUN, "gap", "this run's own solver telemetry"),
            (CITE_SPEC, "docs/05:Acceptance gates",
             "what this product treats as a proof obligation"),
        ),
        pattern=r"\bgap\b",
        run_figure="gap",
        doors=("is this the cheapest possible plan",
               "how long did the solve take"),
    ),
    GlossaryEntry(
        term="ledger",
        body=(
            "The ledger is the one total this product compares plans by — "
            "every priced consequence of a schedule in one number. Anything "
            "else the solver reports is telemetry about the search, not a "
            "price you can hold two plans against."),
        citations=(
            (CITE_RULING, "R-DP12",
             "the ledger is the only comparable number; the scaled objective "
             "survives only as labelled solver telemetry"),
        ),
        pattern=r"\bledger(?:s)?\b",
        doors=("what is this plan costing me",
               "where is the money going"),
    ),
    GlossaryEntry(
        term="frozen",
        body=(
            "Frozen work is already committed: it sits before this plan's "
            "frozen boundary, and the solver was not allowed to move it. It is "
            "a statement about AUTHORITY — who may still change it — not about "
            "whether the machine is busy."),
        citations=(
            (CITE_RULING, "R-F1",
             "the frozen boundary is planner-movable; a thaw changes authority, "
             "never position"),
            (CITE_RUN, "frozen_boundary", "where this board's boundary sits"),
        ),
        pattern=r"\bfroz(?:en)\b|\bfreeze\b",
        run_figure="frozen_boundary",
        doors=("what is in the frozen zone",),
    ),
    GlossaryEntry(
        term="pinned",
        body=(
            "A pinned operation was held to a particular resource or start "
            "time as an input to the solve — someone declared it, so the "
            "solver treated it as fixed rather than choosing it."),
        citations=(
            (CITE_SPEC, "docs/06:locks",
             "the declared doorway a pin arrives through"),
            (CITE_SPEC, "docs/05:Category F",
             "assignment overrides, provenance mandatory"),
        ),
        pattern=r"\bpin(?:ned|s|ning)?\b",
        doors=("what would have to change for it to move",),
    ),
    GlossaryEntry(
        term="driver",
        body=(
            "A driver is the recorded reason a placement decision went the way "
            "it did — one code per decision, chosen from a closed list, "
            "written down at solve time rather than reconstructed afterwards. "
            "It is what the run SAID, which is why an answer can disagree with "
            "its own scan and tell you so."),
        citations=(
            (CITE_SPEC, "docs/02:4.2",
             "the Decision record: exactly one mandatory driver code"),
            (CITE_RUN, "driver_codes", "how many codes the vocabulary holds"),
        ),
        pattern=r"\bdriver(?:s)?\b",
        run_figure="driver_codes",
        doors=("why is it on that machine",),
    ),
    GlossaryEntry(
        term="splittable",
        body=(
            "A splittable operation may be run in more than one sitting — the "
            "solver can break it into chunks and fit them into separate "
            "openings, subject to a minimum chunk size. An operation that is "
            "not splittable has to fit somewhere whole."),
        citations=(
            (CITE_SPEC, "docs/05:R-C3",
             "interruptibility: three classes, per phase"),
        ),
        pattern=r"\bsplittable\b",
        doors=("can this order be split",),
    ),
    GlossaryEntry(
        term="chunk",
        body=(
            "A chunk is one sitting of a splittable operation. The pieces "
            "belong to one operation and each has to be at least the declared "
            "minimum length, so a job is never shaved into slivers to make it "
            "fit."),
        citations=(
            (CITE_SPEC, "docs/05:R-C3",
             "interruptibility: three classes, per phase"),
        ),
        pattern=r"\bchunk(?:s|ed|ing)?\b",
        doors=("can this order be split",),
    ),
    GlossaryEntry(
        term="past-due",
        body=(
            "A past-due order was already late before this plan started — its "
            "due date is behind the plan's reference date. It is WORK, not a "
            "data defect: it is admitted, scheduled and priced from the due "
            "date that was declared for it."),
        citations=(
            (CITE_RULING, "R-PD1",
             "past-due is work, not a defect: admitted, scheduled, priced from "
             "its declared due date; exclusion is a data-defect category only"),
        ),
        pattern=r"\bpast[\s-]due\b",
        doors=("how many orders are late",),
    ),
    GlossaryEntry(
        term="coarse",
        body=(
            "The coarse zone is a rough look at work beyond the solved window "
            "— bucketed capacity against bucketed load, with a declared "
            "derate. It is a RELAXATION: it can tell you something will not "
            "fit, and it can never promise that something will."),
        citations=(
            (CITE_RULING, "R-SC3",
             "the coarse zone is a relaxation, always: only the negative is "
             "claimed, and the converse is never asserted"),
            (CITE_SPEC, "docs/06:coarse_horizon",
             "where the bucket size and the derate are declared"),
        ),
        pattern=r"\bcoarse\b|\bderat(?:e|ed|ing)\b",
        doors=("will the beyond-horizon work fit",),
    ),
)

GLOSSARY_BY_TERM: dict[str, GlossaryEntry] = {e.term: e for e in GLOSSARY}

#: Compiled once. Order is registry order, and `known_term` returns the FIRST
#: match, so a more specific entry must precede a more general one.
_COMPILED: tuple[tuple[GlossaryEntry, re.Pattern], ...] = tuple(
    (e, re.compile(e.pattern, re.IGNORECASE)) for e in GLOSSARY)


def known_term(raw: str) -> Optional[GlossaryEntry]:
    """The glossary entry a planner's words name, or None.

    Matched against the ENTRY's own pattern, so inflections resolve: "seeds"
    and "seeded" are "seed". Deliberately not fuzzy — a word we do not
    recognise is not a word we should improvise a definition for.
    """
    text = (raw or "").strip()
    if not text:
        return None
    for entry, rx in _COMPILED:
        if rx.search(text):
            return entry
    return None


def terms_in(answer: str) -> frozenset[str]:
    """Every glossary term this rendered answer actually used.

    THIS IS THE TRIGGER'S INPUT AND THE SCOPE WALL'S TEETH (R-TE1 clause (1)):
    the product explains words it SAID, and what it said is a property of the
    rendered text rather than of anything a model remembers. Read over the
    answer body with its `[rendered by: …]` footer left in — the footer is our
    own furniture and contains none of these words — and never over the
    QUESTION, which is the planner's vocabulary and not ours.
    """
    if not answer:
        return frozenset()
    return frozenset(e.term for e, rx in _COMPILED if rx.search(answer))
