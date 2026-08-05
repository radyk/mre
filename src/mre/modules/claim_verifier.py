"""M10 — claim-level verification (R-AI5(3)/(8), Session 4A.5b CU3).

The hardening pass every synthesis draft goes through before it can render.

DETERMINISTIC CODE, NEVER A MODEL. For each drafted claim this module independently
re-fetches the records the claim cites — from the evidence index and the snapshot,
through ``EvidenceToolbox.fetch_source``, not from the loop's transcript — and checks
the claim's specific assertions against them with the same discipline the render
validator applies to LLM testimony (``renderers._validate_testimony``): timestamps
compared as minute tuples, durations normalized across minutes / hours / days, entity
names resolved through the identity map, citations required to name a REAL record.

THE OUTCOME TAXONOMY (``ClaimStatus``), and exactly what earns each:

  VERIFIED      EVERY checkable assertion grounds in the cited records; at least
                one of them is a FIGURE or a TIME rather than a name (a sentence
                proven only by mentioning a real machine is not proven); any
                quantifier it makes was enumerable from a single tool call; and it
                is not the draft's own conclusion. Renders as cited, in the proven
                register.
  INTERPRETIVE  the claim carries no checkable assertion (an aggregate read, an
                inference, a mechanism), or part of it is not spoken to by the
                cited records, or it grounds but cites nothing, or it quantifies
                over a set nobody enumerated (the sample is then named), or it is
                the conclusion. Renders labeled, with its consulted records listed.
                First-class conversation (R-AI5(6)), not a failure.
  FAILED        a checkable assertion CONTRADICTS the cited evidence — and nothing
                else the loop read carries it either — or the claim cites a record
                that does not exist, or it names an entity this run does not have,
                or (R-TG1 direction (ii)) it cites nothing, grounds nothing and
                names nothing on this board while not being offered as general
                knowledge. The claim is CUT.
  GENERAL_KNOWLEDGE
                the model OFFERED the claim as domain knowledge and deterministic
                code confirmed it carries no board content at all. Verification is
                SKIPPED — not passed, not failed. This is the one outcome in the
                taxonomy that is not a verdict about grounding; it is a statement
                about what the sentence is ABOUT, and it is the only one a claim
                can be refused (see ``gk_disqualifiers``).

The distinction between the first three matters and is deliberate. An assertion
the records simply do not speak to is NOT a contradiction — it is unproven, and
unproven means labeled, not deleted (R-AI5(3): "remain visibly synthesis or are
softened or cut"). A contradiction is narrower: the cited records DO carry that
kind of quantity and it does not match. That is the fabricated-adjacency class
the round-three exam found, and it is cut.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from mre.contracts.synthesis import (
    Assertion,
    ClaimKind,
    ClaimStatus,
    DraftClaim,
    SynthesisAnswer,
    VerifiedClaim,
)
from mre.modules.renderers import (
    _TS_FULL_RE, _to_minute_tuple, _ts_matches,
)

#: The reason a claim is cut by R-TG1 enforcement direction (ii). A CONSTANT
#: because the surface has to tell this cut apart from a grounding failure: the
#: two are cut for opposite reasons and the planner is owed the right one. "My
#: reasoning didn't hold up against the records" is FALSE of a sentence that
#: never touched the records — measured live on the demo board, where the tier's
#: own honest limit statement ("whether a large gap here reflects a weak schedule
#: versus a loose bound is something I cannot check against this run") was cut
#: here and then reported as a failed grounding.
UNPLACEABLE_REASON = (
    "it cites no record, states nothing this run's evidence can check, and names "
    "nothing on this board — so it is not a reading of this plan, and it was not "
    "offered as general knowledge")

# Outcomes of checking ONE assertion against a scope of fetched evidence.
_GROUNDED = "grounded"
_CONTRADICTED = "contradicted"
_UNCHECKED = "unchecked"

# A duration with its unit, as a planner writes it. Wider than the render
# validator's minutes/hours pair in three ways a synthesis answer needs: days,
# thousands separators ("2,120 minutes"), and ONE intervening qualifier, because
# aggregates are written "2,120 busy minutes", not "2120 minutes".
_QUALIFIER = r"(?:busy|working|idle|running|scheduled|total|elapsed|late|early)"
_DURATION_RE = re.compile(
    rf"\b(\d[\d,]*(?:\.\d+)?)\s*(?:{_QUALIFIER}\s+)?"
    r"(minutes?|mins?|hours?|hrs?|h|days?|d)\b", re.IGNORECASE)

# A currency figure. Unambiguous where a bare number is not, so it is extracted
# always (a bare number is only read as a count when the claim quantifies).
_MONEY_RE = re.compile(r"[$£€]\s?(\d[\d,]*(?:\.\d+)?)")

# How close a tally or a money figure must be to count as the same figure. A
# synthesis answer rounds ("$371" for 370.83); the check survives that without
# waving through a different number.
_FIGURE_ABS_TOL = 0.5
_FIGURE_REL_TOL = 0.005

# Set-quantifying language. A claim carrying one of these is only VERIFIED when a
# single tool call enumerated the set it quantifies over (completeness honesty).
_QUANTIFIER_RE = re.compile(
    r"\b(all|every|each|both|most|none|majority|no other|only one|"
    r"\d+\s+of\s+(?:the\s+)?\d+|\d+\s+(?:orders?|jobs?|machines?|operations?))\b",
    re.IGNORECASE)

# Keys whose numeric leaves are durations — the "same kind of quantity" test for a
# duration assertion (see the module docstring's three-way rule).
_DURATION_KEYS = ("minute", "duration", "lateness", "second", "hour", "elapsed")

# Record METADATA — the audit trail's own fields, never a fact about the schedule.
# A Metric's `timestamp` is when the run wrote it, not when anything ran; comparing
# a claim's schedule timestamp against it produced a false contradiction in the
# first live run ("ORD-05 was due 2026-01-05 23:59" cut against the run's clock).
# Excluded from every profile: they are not what a claim is ever about.
_METADATA_KEYS = frozenset({
    "timestamp", "ended_at", "started_at", "seq", "run_id", "record_id",
    "snapshot_id", "module", "tier", "version", "schema_version",
})

# Comparative qualifiers in front of a figure. "over 9 days" is an INEQUALITY, and
# checking it as an equality is simply the wrong test — it must be satisfied by
# SOME value in scope, and it is contradicted only when no value in a scope full of
# durations satisfies it (which is how an overstated superlative gets caught).
_MORE = ("over", "more than", "at least", "longer than", "greater than", "above",
         "upwards of", "north of", "beyond")
_LESS = ("under", "less than", "at most", "shorter than", "below", "within",
         "no more than", "up to")

_UNIT_TO_MINUTES = {"m": 1.0, "min": 1.0, "mins": 1.0, "minute": 1.0, "minutes": 1.0,
                    "h": 60.0, "hr": 60.0, "hrs": 60.0, "hour": 60.0, "hours": 60.0,
                    "d": 1440.0, "day": 1440.0, "days": 1440.0}

# How close two durations must be to count as the same figure. A synthesis answer
# rounds ("14.8 hours" for 890 minutes); the check must survive rounding without
# waving through a different number. The tolerance is taken from the CLAIM's own
# value, never the record's: a record full of epoch seconds would otherwise carry a
# tolerance of weeks and wave everything through (caught in the first bench run).
_DURATION_TOL_MIN = 1.0
_DURATION_REL_TOL = 0.02
_DURATION_TOL_CAP = 60.0


class _Scope:
    """The independently re-fetched evidence one claim is checked against."""

    def __init__(self, toolbox: Any, ids: list[str]) -> None:
        self.toolbox = toolbox
        self.ids = list(ids)
        self.counts: set[float] = set(getattr(toolbox, "count_profile", set()) or set())
        # The figures the TOOLBOX computed over the very rows this claim cites: a
        # machine's busy minutes, a cost total, a row count. They live in a result's
        # summary rather than in any single record, and they are our own arithmetic
        # over the pinned run — so a claim citing those rows may rest on them. The
        # named limit is the same one _covering_call carries: this checks that a
        # figure IS one we computed there, not that it is the right one for the
        # words around it.
        self.tallies: set[float] = set()
        self.missing: list[str] = []
        self.numbers: set[float] = set()
        self.duration_minutes: set[float] = set()
        self.timestamps: set[tuple] = set()
        self.labels: set[str] = set()
        self.has_durations = False
        self.has_timestamps = False
        # The summaries of the calls this claim's citations came from, absorbed the
        # same way a record is: their timestamps and figures are ours, computed over
        # the pinned run, and a claim resting on the rows may rest on them too.
        wanted = set(ids)
        for entry in getattr(toolbox, "call_tallies", []) or []:
            tool, call_ids, call_tallies = entry[0], entry[1], entry[2]
            if not (wanted & call_ids):
                continue
            self.tallies |= call_tallies
            if len(entry) > 3 and isinstance(entry[3], dict):
                self._absorb(entry[3], "summary")
        for rid in self.ids:
            src = toolbox.fetch_source(rid)
            if src is None:
                self.missing.append(rid)
                continue
            _, payload = src
            self._absorb(payload)
            self.labels |= {str(v).upper() for v in toolbox.labels_for(payload)}

    def _absorb(self, payload: Any, key: str = "", depth: int = 0) -> None:
        if depth > 7:
            return
        if isinstance(payload, dict):
            # A Metric names its own quantity: {"name": "lateness_minutes",
            # "unit": "minutes", "value": 890.0}. Read the NAME, not just the key —
            # otherwise the duration lands under the key "value", the record looks
            # like it carries no duration at all, and a wrong figure quoted against
            # it reads as merely unproven instead of contradicted.
            unit_words = f"{payload.get('name', '')} {payload.get('unit', '')}".lower()
            val = payload.get("value")
            if isinstance(val, (int, float)) and not isinstance(val, bool) \
                    and any(k in unit_words for k in _DURATION_KEYS):
                self.has_durations = True
                minutes = float(val)
                if "hour" in unit_words:
                    minutes *= 60.0
                elif "second" in unit_words:
                    minutes /= 60.0
                self.duration_minutes.add(abs(minutes))
            for k, v in payload.items():
                if str(k) in _METADATA_KEYS:
                    continue                 # the audit trail's own fields
                self._absorb(v, str(k), depth + 1)
            return
        if isinstance(payload, (list, tuple)):
            for v in payload:
                self._absorb(v, key, depth + 1)
            return
        if isinstance(payload, bool):
            return
        if isinstance(payload, (int, float)):
            val = float(payload)
            self.numbers.add(val)
            if any(k in key.lower() for k in _DURATION_KEYS):
                self.has_durations = True
                minutes = val / 60.0 if "second" in key.lower() else val
                if "hour" in key.lower():
                    minutes = val * 60.0
                self.duration_minutes.add(abs(minutes))
            return
        if isinstance(payload, str):
            for ts in _TS_FULL_RE.findall(payload):
                tup = _to_minute_tuple(ts)
                if tup is not None:
                    self.timestamps.add(tup)
                    self.has_timestamps = True
            iso = _iso_duration_minutes(payload)
            if iso is not None:
                self.has_durations = True
                self.duration_minutes.add(abs(iso))
            if _NUM_STR_RE.fullmatch(payload.strip()):
                try:
                    self.numbers.add(float(payload.strip()))
                except ValueError:
                    pass


_NUM_STR_RE = re.compile(r"-?\d+(?:\.\d+)?")
_ISO_DUR_RE = re.compile(
    r"^-?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?$")


def _iso_duration_minutes(s: str) -> Optional[float]:
    m = _ISO_DUR_RE.match((s or "").strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, sec = (float(g or 0) for g in m.groups())
    return d * 1440.0 + h * 60.0 + mi + sec / 60.0


# ---------------------------------------------------------------------------
# Assertion extraction
# ---------------------------------------------------------------------------

def extract_assertions(text: str, *, order_refs: dict, machine_refs: dict,
                       order_shapes: list) -> list[Assertion]:
    """The checkable things one claim asserts.

    Four kinds, and the ORDER matters: entity tokens are consumed first so that the
    digits inside ``ORD-05`` / ``CUT-01`` are never read as a number."""
    out: list[Assertion] = []
    upper = (text or "").upper()
    consumed = text or ""

    known = {}
    known.update({k: "order" for k in order_refs})
    known.update({k: "machine" for k in machine_refs})
    for name in sorted(known, key=len, reverse=True):
        if re.search(rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])", upper):
            out.append(Assertion(kind="entity", text=name, detail=known[name]))
            consumed = re.sub(re.escape(name), " ", consumed, flags=re.IGNORECASE)

    # An entity-SHAPED token that this run does not have is a fabrication, not an
    # unknown: the same shape check the exam sidecar applies to a resolved question.
    for tok in re.findall(r"[A-Za-z][\w./-]*\d[\w./-]*", consumed):
        u = tok.upper().strip(".,?!")
        if u in order_refs or u in machine_refs:
            continue
        if any(p.match(u) for p in order_shapes or []):
            out.append(Assertion(kind="entity", text=u, detail="absent"))
            consumed = consumed.replace(tok, " ")

    for m in _TS_FULL_RE.finditer(consumed):
        out.append(Assertion(kind="timestamp", text=m.group(0)))
    consumed_no_ts = _TS_FULL_RE.sub(" ", consumed)

    for m in _DURATION_RE.finditer(consumed_no_ts):
        lead = consumed_no_ts[max(0, m.start() - 18):m.start()].lower()
        rel = ("gt" if any(w in lead for w in _MORE)
               else "lt" if any(w in lead for w in _LESS) else "eq")
        out.append(Assertion(kind="duration", text=m.group(0).strip(), detail=rel))
    left = _DURATION_RE.sub(" ", consumed_no_ts)

    for m in _MONEY_RE.finditer(left):
        out.append(Assertion(kind="money", text=m.group(1)))
    left = _MONEY_RE.sub(" ", left)

    # A BARE number is only read as a count when the claim actually quantifies.
    # Extracting every loose figure looked stricter and was in fact noisier: the
    # "5" in "5 January" and the "85" in "85%" are not tallies anybody computed,
    # and demoting true claims over them taught nothing. The fabrication guards
    # that matter — durations, timestamps, entity names, citations — are unchanged.
    quant = _QUANTIFIER_RE.search(text or "")
    if quant:
        for m in re.finditer(r"(?<![\w.$-])(\d[\d,]*(?:\.\d+)?)(?![\w.-])", left):
            out.append(Assertion(kind="count", text=m.group(1)))
        out.append(Assertion(kind="quantifier", text=quant.group(0)))
    return out


# ---------------------------------------------------------------------------
# R-TG1 — BOARD CONTENT. The one predicate both enforcement directions turn on.
# ---------------------------------------------------------------------------

#: Every bare figure in a sentence, however it is written: "90%", "1,667,467.80",
#: "431 minutes", "3". Deliberately WIDER than ``extract_assertions``' bare-number
#: rule, which only reads a loose number as a count when the claim quantifies.
#: That narrowness is right for grounding a board claim (the "5" in "5 January" is
#: not a tally anybody computed, and demoting a true sentence over it teaches
#: nothing). It is exactly wrong here: the question this predicate answers is not
#: "does this figure ground" but "does this sentence look like it is about the
#: board", and for that a bare number IS the signal.
_BARE_FIGURE_RE = re.compile(r"(?<![\w.-])(\d[\d,]*(?:\.\d+)?)(?![\w.-])")


def _bare_figures(text: str) -> list[float]:
    out: list[float] = []
    for m in _BARE_FIGURE_RE.finditer(text or ""):
        value = _figure(m.group(1))
        if value is not None:
            out.append(value)
    return out


def gk_disqualifiers(claim: DraftClaim, assertions: list[Assertion],
                     scope: _Scope, wide: Optional[_Scope] = None) -> list[str]:
    """Why this claim may NOT wear the general-knowledge label — or [] if it may.

    R-TG1's core, and it is DETERMINISTIC: the model's own classification is a
    PROPOSAL, and this function is the check that runs BOTH ways over it. A claim
    is disqualified by any board content at all, because the general-knowledge
    class is unverifiable by design and a class nobody verifies must not be
    reachable by a sentence anybody could have checked. That would be the exact
    inverse abuse — verification escaped by assertion.

    Board content is five things, and each is here for its own reason:

      a CITATION      claiming a record backs the sentence IS claiming the sentence
                      is about this plan; nothing general needs one.
      an ENTITY       an order or a machine — known to this run, or entity-SHAPED
                      and absent from it, which is a fabrication either way.
      a TIMESTAMP     a placement time is a fact about this schedule.
      MONEY           a currency figure on this board is a ledger figure.
      OUR OWN FIGURE  a number this run computed. This is the clause that closes
                      the escape hatch: "85% utilization is generally healthy" is
                      a general sentence right up until 85 is what PRESS-FAST
                      measures, at which point it is an unverified board claim
                      wearing a label that forbids checking it.

    The last clause is deliberately conservative — it rejects on a MATCH against
    anything the loop read, so a general sentence quoting an unrelated small
    integer is sent back to board verification too. Rejection is not a cut: it
    means the claim is checked the ordinary way, which is what happened to it
    before this class existed. Over-rejection therefore fails toward today's
    behaviour, and under-rejection is the escape hatch, so the asymmetry is taken
    on purpose.
    """
    reasons: list[str] = []
    if [r for r in claim.record_ids if r]:
        reasons.append("it cites this run's records")
    named = [a.text for a in assertions if a.kind == "entity"]
    if named:
        reasons.append("it names " + ", ".join(named[:3]))
    if any(a.kind == "timestamp" for a in assertions):
        reasons.append("it states a time on this schedule")
    if any(a.kind == "money" for a in assertions):
        reasons.append("it states a currency figure")
    known: set[float] = set()
    for src in (scope, wide):
        if src is None:
            continue
        known |= {abs(n) for n in src.numbers}
        known |= {abs(n) for n in src.tallies}
        known |= {abs(n) for n in src.counts}
        known |= {abs(n) for n in src.duration_minutes}
    hits = [v for v in _bare_figures(claim.text) if _near(abs(v), known)]
    if hits:
        reasons.append("it states a figure this run computed ("
                       + ", ".join(f"{v:g}" for v in hits[:3]) + ")")
    return reasons


def _has_board_content(claim: DraftClaim, assertions: list[Assertion],
                       scope: _Scope, wide: Optional[_Scope]) -> bool:
    """The same predicate, read the other way — for enforcement direction (ii)."""
    return bool(gk_disqualifiers(claim, assertions, scope, wide))


# ---------------------------------------------------------------------------
# R-TG6 — THE PRODUCT-BEHAVIOR CLAIM. A SECOND AXIS, AND DELIBERATELY NOT THE
# FIRST ONE.
# ---------------------------------------------------------------------------
#
# THE FOUNDING SPECIMEN (C9 founder round, 2026-08-05, fenced world). A teaching
# answer shipped this, wearing the general-knowledge label:
#
#   "In this product, a job becomes immovable only through a frozen_assignment
#    or pinned constraint declared in locks.csv ... nothing else in the catalog
#    removes an operation's mobility outright."
#
# It is FALSE of this product, and this product had PROVEN it false on the same
# board three questions earlier: `mobility_premise` computes BOXED_IN — earlier
# bound, nothing later — with no lock anywhere in it, and the founder had just
# read exactly that verdict about ORD-BOX op20. The founder read the teaching
# answer and reported himself satisfied, which is the harm profile: a confident
# reader carrying a wrong rule out of the room.
#
# WHY THIS IS NOT A SIXTH CLAUSE IN `gk_disqualifiers`. That function is the
# BOARD-CONTENT predicate and BOTH R-TG1 directions read it — direction (ii)
# drops a claim precisely when it has NO board content. A product-behavior claim
# has no board content: it names no order, no time, no money, no figure we
# computed. So folding it in would make direction (ii) see board content where
# there is none, and the Q9 sentence would stop being dropped and start shipping
# as INTERPRETIVE — "my reading, no record states this" — which is a DIFFERENT
# false label on the same false sentence. One predicate read two ways was right
# for R-TG1 because both directions ask one question. This asks another question
# ("is this sentence about our PRODUCT") about a disjoint axis, so it is its own
# predicate and they cannot drift into each other: neither is defined in terms
# of the other.
#
# THE TAXONOMY GAP THIS FILLS, NAMED. R-TG1(a) closed with "the taxonomy still
# has no home for a sentence about our own epistemic position". This is the
# neighbouring gap and the same shape: a sentence about our own BEHAVIOR was
# forced to choose between two labels that both misdescribe it — `synthesis`
# says "I read this off your board" and `general knowledge` says "this is how
# scheduling works generally, there is nothing here to check it against". The
# second is the more dangerous, because it is the label that FORBIDS checking.

#: Phrases that mark a sentence as asserting what THIS PRODUCT does, rather than
#: how scheduling works. Each is here because it can only be said about us.
#:
#: THE PATTERN SET IS DELIBERATELY TIGHT, AND THE ASYMMETRY IS THE OPPOSITE OF
#: `gk_disqualifiers`'. There, over-rejection was free: a rejected claim fell
#: through to ordinary verification, which is what happened to it before the
#: class existed. Here, rejection is a DROP — a true general sentence lost is a
#: real cost to a teaching answer — so these match self-reference and our own
#: declared vocabulary, and NOTHING that a sentence about scheduling in general
#: would reach for. In particular there is no bare "the solver": every board
#: claim on this surface says "the solver chose", and reading that as a claim
#: about the product would drop the plainest true sentences we render.
_PRODUCT_BEHAVIOR_PATTERNS: tuple[tuple[str, str], ...] = (
    # (a) Naming us. "In this product X" is a claim about X in this product.
    #
    # WIDENED BY MEASUREMENT, 4A teaching-graft (e2) F1 — AND THE SPECIMEN IS
    # (e)'S OWN HEADLINE SUCCESS. The (e) close-out §4 quotes, as proof that the
    # fix worked, a run-1 claim that shipped UNCITED under `[general knowledge]`:
    #
    #     "A job becomes impossible to move for one of a small number of
    #      specific reasons THIS PRODUCT ACTUALLY COMPUTES, not just a lock: ..."
    #
    # It is TRUE, and being true is not the discriminator — both of (e)'s own
    # 2-of-99 census specimens were true too. It enumerates what WE compute,
    # while wearing the one label that means "there is nothing here to check
    # this against", and there is: the docs/05 catalog and the mobility floor's
    # own verdict vocabulary both speak to it. So it is the species (i) refuses,
    # and the shipped pattern missed it TWICE OVER — no "computes" in the verb
    # list, and the verb required to sit immediately after the noun where this
    # sentence has an adverb in between.
    #
    # The widening is therefore exactly two things and no more: the verbs that
    # assert a COMPUTATION we perform, and ONE intervening word. Measured over
    # the whole committed claim corpus (50 transcripts, 522 unique claim lines,
    # 121 of them general-knowledge) it adds exactly ONE further firing — "The
    # scheduler itself does not pick a tiebreak rule from a menu — it is the
    # solver's objective (tardiness, setup cost, overtime) plus hard
    # constraints..." — which names our ledger's own components and is the same
    # species, found independently. Firings on the 401 non-general-knowledge
    # claim lines are UNCHANGED at 2.
    ("it states what this product does",
     r"\b(?:in|on|with|for|within)\s+th(?:is|e)\s+product\b"
     r"|\bth(?:is|e)\s+(?:product|system|engine|scheduler)\s+"
     r"(?:\w+\s+)?"
     r"(?:can|cannot|can't|does|doesn't|will|won't|only|never|always|"
     r"treats?|models?|supports?|comput\w+|calculat\w+|determin\w+|"
     r"decid\w+|enforc\w+|recogni[sz]\w+|consider\w+|distinguish\w+)\b"
     r"|\bwe\s+(?:only|never|always)\s+\w+\b"
     # THE POSTPOSED DEICTIC, added by (d.3)'s rider R2 and found by (d.2)'s
     # standing predicate audit over (e2)'s OWN sweeps:
     #
     #   "a mixed-integer or constraint-based SCHEDULER LIKE THIS ONE instead
     #    searches globally ... the ordering is an output of the optimization,
     #    not an input rule it followed"                    [general knowledge]
     #
     # A third construction, independent of both (e2) widenings: the pointer
     # sits AFTER the noun, so every alternation above — all of which want
     # "this/the <noun>" — misses it. The claim is as much about this product
     # as any of them, and it is as checkable (docs/05, the solver builder).
     #
     # BOUNDED THE SAME WAY THE OTHERS ARE: a closed noun list, the same
     # one-intervening-word allowance, and the same closed verb list, so it
     # widens the SHAPE and not the reach. "A scheduler like this one decides"
     # fires; "a plant like this one runs hot" does not.
     r"|\b(?:product|system|engine|scheduler|solver)s?\s+like\s+th(?:is|ese)\s+"
     r"(?:one|ones)?\s*"
     r"(?:\w+\s+)?"
     r"(?:can|cannot|can't|does|doesn't|will|won't|only|never|always|"
     r"treats?|models?|supports?|comput\w+|calculat\w+|determin\w+|"
     r"decid\w+|enforc\w+|recogni[sz]\w+|consider\w+|distinguish\w+|"
     r"search\w+|instead)\b"),
    # (b) docs/05's own vocabulary. "proven in core" is a STATUS COLUMN value in
    #     the constraint catalog — a fact about what we have built and verified,
    #     which no general statement about scheduling has any use for.
    ("it cites this product's constraint catalog",
     r"\bdocs?/05\b|\bproven[\s-]in[\s-]core\b|\bin[\s-]core\b"
     r"|\b(?:the\s+)?constraint\s+catalog\b|\bin\s+the\s+catalog\b"),
    # (c) Our declared schema. A sentence naming an IDS table or column is
    #     asserting the shape of the data WE accept, not a fact about plants.
    ("it names this product's declared schema",
     r"\b\w+\.csv\b|\bmanifest\.json\b|\block_type\b|\bfrozen_assignment\b"
     r"|\bpinned_(?:resource|start)\b"),
)

_PRODUCT_BEHAVIOR_RES = tuple(
    (why, re.compile(rx, re.IGNORECASE)) for why, rx in _PRODUCT_BEHAVIOR_PATTERNS)

#: The drop reason for R-TG6 (i). It names the SHAPE of the failure, because a
#: drop whose reason is "it was wrong" teaches nobody anything.
#: The prefix every R-TG6 floor refutation carries, so the render seam can tell
#: a REFUTED claim from an UNGROUNDED one without matching prose. A cut that
#: cannot be told apart from its siblings gets described as one of them, which
#: is the defect R-TG1 fixed once already at this same seam.
FLOOR_REFUTED_PREFIX = "contradicted by this product's own floor: "


PRODUCT_BEHAVIOR_REASON = (
    "it asserts what this product does, which is not general knowledge and is "
    "not something this run's records can speak to either — a claim about our "
    "own behaviour is checkable against the constraint catalog or a floor's own "
    "computation, and it was offered with neither")


def product_behavior_disqualifiers(claim: DraftClaim) -> list[str]:
    """Why this claim asserts THIS PRODUCT's behavior — or [] if it does not.

    R-TG6 (i). Deterministic, and it reads the claim TEXT alone: whether a
    sentence is about our product is a property of the sentence, not of what the
    loop happened to read.
    """
    return [why for why, rx in _PRODUCT_BEHAVIOR_RES if rx.search(claim.text or "")]


# --- R-TG6 (iii): the floor contradiction map ------------------------------
#
# THE SMALLEST HONEST VERSION, AND WHAT IT DELIBERATELY IS NOT. This is not an
# entailment checker and must never become one — scoring whether a general
# sentence follows from a verdict vocabulary is exactly the LLM-judge R-EX1
# wrote down and refused, because the weights that wrote the answer would be
# marking it. What it IS: an authored map from a floor's OWN verdict vocabulary
# to the sentence shape that vocabulary falsifies. One entry today.
#
# THE ENTRY IS FALSIFIED BY THE VOCABULARY, NOT BY THE BOARD, AND THAT IS THE
# STRONGER CLAIM. `VERDICT_BOXED_IN` is a verdict this product computes for an
# operation that is bound earlier and has no opening later — with no lock in it
# anywhere. Its mere EXISTENCE in `mobility_premise` refutes "only a lock can
# make a job immovable", on every board, whether or not today's board happens to
# hold a specimen. Checking the board instead would make the rule true on a
# board with no boxed-in bar, which it is not; and it would cost a census.
_IMMOBILITY_RE = re.compile(
    r"\bimmovable\b|\bimmobili\w+|\bimpossible\s+to\s+move\b"
    r"|\b(?:can(?:'t|not)|could\s+not|unable\s+to)\s+(?:be\s+)?move\w*"
    r"|\bfix(?:ed|ing)\s+(?:it\s+)?(?:in\s+place|to\s+one\s+spot)\b"
    r"|\bremoves?\s+(?:an?\s+)?\w*\s*mobility\b", re.IGNORECASE)

#: EXCLUSIVITY, IN THE SHAPES THAT HAVE ACTUALLY BEEN MEASURED. The first three
#: alternations came from the founding specimen ("only ... nothing else"); the
#: last two were added after the fix's OWN first live run, where the model said
#: the same wrong thing in a construction the map did not hold —
#:
#:   "the immovability comes from a lock or the frozen zone, NOT FROM anything
#:    intrinsic to a job's lateness or timing"
#:
#: — which is the same claim, exclusive by contrast rather than by "only". That
#: is the honest character of this map and the close-out says so: it holds the
#: shapes we have seen a model use, it is not an entailment checker, and a
#: paraphrase outside it ships. A smaller true gate beats a large leaky one.
_EXCLUSIVITY_RE = re.compile(
    r"\bonly\b|\bsolely\b|\bexclusively\b|\bnothing\s+else\b"
    r"|\bthe\s+(?:one\s+)?(?:mechanism|way|thing)\b|\bsole\b"
    r"|\bnot\s+from\b|\brather\s+than\s+(?:from|because|any)\b", re.IGNORECASE)

_LOCK_TERM_RE = re.compile(
    r"\block\w*|\bfrozen[\s_-]?assignment\b|\bpin(?:ned|s)?\b", re.IGNORECASE)

#: The reason names the verdict that falsifies the sentence, so a planner (and a
#: drill-down) can go and look at it.
FLOOR_CONTRADICTION_REASON = (
    "it says a lock is the only thing that can make a job immovable, and this "
    "product's own mobility floor computes a \"" + "boxed-in"
    + "\" verdict — bound earlier, no opening later — for operations that carry "
      "no lock at all")


def floor_contradictions(claim: DraftClaim) -> list[str]:
    """Where this claim's general rule is falsified by a floor's own verdict
    vocabulary — or [] where it is not.

    R-TG6 (iii). Applies to EVERY claim regardless of the label it wears: a
    false statement about what this product can compute is false in the
    `synthesis` register too, and the founding specimen's first line proves it
    (a CITED board claim carrying the same wrong rule).
    """
    text = claim.text or ""
    if (_IMMOBILITY_RE.search(text) and _EXCLUSIVITY_RE.search(text)
            and _LOCK_TERM_RE.search(text)):
        return [FLOOR_CONTRADICTION_REASON]
    return []


# --- R-TG6 (ii): an entity-named mobility claim meets the floor -------------
#
# The general rule above is one half of the specimen. The other half is the
# EXAMPLE the same answer hung on it — "ORD-BOX likewise shows no lock, just two
# sequential operations" — offered as an instance of a job that is not stuck,
# about the one bar on the board the floor had computed BOXED_IN.
#
# THE CHECK ASKS THE FLOOR, IT DOES NOT RE-DERIVE THE ANSWER (R-FF1). It calls
# the same `mobility_verdict` the routes call, so a teaching answer and a
# testimony answer about one bar can never state different verdicts — which was
# the whole defect: Q7 and Q9 DID.
#
# UNDECIDABLE CONTRADICTS NOTHING, and that is load-bearing. The same claim
# names ORD-SPAN, whose operation is chunked and whose verdict is UNDECIDABLE —
# neither `holds` nor `refutes`. Reading it as a contradiction would manufacture
# a claim about the plant out of a limit of our own method, which is the ruled
# species this codebase has now refused at six seams.
_FREE_TO_MOVE_RE = re.compile(
    r"\bfree\s+to\s+move\b|\bcan\s+(?:still\s+)?(?:be\s+)?moved?\b"
    r"|\bcould\s+(?:be\s+)?moved?\b|\bable\s+to\s+move\b"
    r"|\b(?:is|are|isn't|aren't)\s+not\s+stuck\b|\bnot\s+(?:stuck|immovable|locked)\b"
    r"|\bnothing\s+(?:is\s+)?hold\w+\b|\bmovable\b", re.IGNORECASE)


def mobility_contradictions(claim: DraftClaim, assertions: list[Assertion], *,
                            toolbox: Any) -> list[str]:
    """Where this claim says a named order can move and the floor says it cannot.

    R-TG6 (ii). Returns [] unless the claim BOTH asserts free mobility AND names
    an order this run knows — so the (expensive) floor read is paid only on the
    rare sentence that has earned it.
    """
    if not _FREE_TO_MOVE_RE.search(claim.text or ""):
        return []
    orders = [a.text for a in assertions
              if a.kind == "entity" and a.detail == "order"]
    if not orders:
        return []
    ex = getattr(toolbox, "_ex", None)
    reader = getattr(ex, "order_mobility_verdicts", None)
    if reader is None:
        return []
    out: list[str] = []
    for ref in orders[:3]:
        try:
            verdicts = reader(ref)
        except Exception:  # noqa: BLE001 — a premise check never takes an answer down
            continue
        for facts in verdicts or []:
            if not facts.get("holds"):
                continue
            seq = facts.get("op_seq")
            out.append(
                f"it says {ref} can move, and this product's mobility floor "
                f"computes \"{facts.get('verdict')}\" for "
                f"{ref}{f' op{seq}' if seq is not None else ''} — the premise "
                f"\"can't be moved\" holds on that operation")
            break
    return out


def _figure(text: str) -> Optional[float]:
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _near(value: float, known: set) -> bool:
    tol = max(_FIGURE_ABS_TOL, abs(value) * _FIGURE_REL_TOL)
    return any(abs(value - k) <= tol for k in known)


def _duration_minutes(text: str) -> Optional[float]:
    m = _DURATION_RE.search(text)
    if not m:
        return None
    value = _figure(m.group(1))
    if value is None:
        return None
    unit = m.group(2).lower().rstrip(".")
    return value * _UNIT_TO_MINUTES.get(unit, _UNIT_TO_MINUTES.get(
        unit.rstrip("s"), 1.0))


def _check(assertion: Assertion, scope: _Scope,
           wide: Optional[_Scope] = None) -> str:
    """One assertion against the cited scope, with the WIDE scope as the appeal.

    A figure or a time the CITED records do not carry is only a contradiction if
    nothing the loop read carries it either. If a sibling row of the same call
    carries it, the claim is under-cited, not wrong — and cutting a true sentence
    for a citation habit teaches the model to say less rather than cite better
    (the first live run cut three true claims exactly this way)."""
    verdict = _check_against(assertion, scope)
    if verdict != _CONTRADICTED or wide is None:
        return verdict
    return _UNCHECKED if _check_against(assertion, wide) == _GROUNDED else verdict


def _check_against(assertion: Assertion, scope: _Scope) -> str:
    if assertion.kind == "entity":
        if assertion.detail == "absent":
            return _CONTRADICTED          # names something this run does not have
        if assertion.text.upper() in scope.labels:
            return _GROUNDED
        # A REAL entity of this run that the cited records do not name is not a
        # contradiction — it is an under-citation. The claim stays visibly
        # synthesis rather than being cut for mentioning a neighbour. Cutting here
        # (the first live run did) throws away true sentences for a citation
        # habit, which teaches the model to say less rather than cite better.
        return _UNCHECKED
    if assertion.kind == "timestamp":
        tup = _to_minute_tuple(assertion.text)
        if tup is None:
            return _UNCHECKED
        if _ts_matches(tup, scope.timestamps):
            return _GROUNDED
        return _CONTRADICTED if scope.has_timestamps else _UNCHECKED
    if assertion.kind == "duration":
        minutes = _duration_minutes(assertion.text)
        if minutes is None:
            return _UNCHECKED
        tol = min(_DURATION_TOL_CAP,
                  max(_DURATION_TOL_MIN, abs(minutes) * _DURATION_REL_TOL))
        known_all = (scope.duration_minutes | {abs(n) for n in scope.numbers}
                     | {abs(n) for n in scope.tallies})
        rel = assertion.detail if assertion.detail in ("gt", "lt") else "eq"
        for known in known_all:
            k, v = abs(known), abs(minutes)
            if (k >= v - tol if rel == "gt"
                    else k <= v + tol if rel == "lt"
                    else abs(k - v) <= tol):
                return _GROUNDED
        return _CONTRADICTED if scope.has_durations else _UNCHECKED
    if assertion.kind in ("count", "money"):
        # A tally or a money figure is checked against what the TOOLBOX computed
        # (row counts, result summaries) and what the cited records carry — the
        # arithmetic is ours, deterministic, over the pinned run. A figure we did
        # not compute is UNCHECKED, never contradicted: we cannot tell a wrong
        # tally from one over a set we never tallied, and cutting on that guess
        # would be dishonest.
        value = _figure(assertion.text)
        if value is None:
            return _UNCHECKED
        known = scope.tallies | (scope.counts if assertion.kind == "count"
                                 else set(scope.numbers))
        return _GROUNDED if _near(value, known) else _UNCHECKED
    return _UNCHECKED                      # a quantifier is judged by enumerability


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

def _read_from(toolbox: Any, scope_ids: list[str]) -> list[str]:
    """Which TOOL CALLS surfaced the records this claim rests on (Session 4B.5
    CU5(d)) — per claim, in call order, de-duplicated.

    This is the "read from" a planner actually means: not a list of record ids,
    but which readings of the plan the sentence came out of. Derived from the
    toolbox's own per-call record sets, so it is a fact about what happened, not a
    label the model chose. Empty when nothing intersects — an honest blank rather
    than the whole call list."""
    wanted = set(scope_ids or ())
    if not wanted:
        return []
    out: list[str] = []
    for entry in getattr(toolbox, "call_tallies", []) or []:
        tool, call_ids = entry[0], entry[1]
        if (wanted & call_ids) and tool not in out:
            out.append(tool)
    return out


def verify_claim(claim: DraftClaim, *, toolbox: Any,
                 wide: Optional[_Scope] = None) -> VerifiedClaim:
    """One drafted claim → its verdict. The model's citations are INPUT here; the
    STATUS is this function's, always (R-AI5(8)).

    R-TG1: so is the model's CLASS. A claim offered as general knowledge and
    refused the label does not fail for it — it is verified the ordinary way, and
    the record says the offer was made and why it was refused, because a
    disqualification that leaves no trace is a check nobody can audit."""
    blocked: list[str] = []
    out = _verify_one(claim, toolbox=toolbox, wide=wide, gk_blocked_out=blocked)
    if blocked and out.status is not ClaimStatus.GENERAL_KNOWLEDGE:
        out.reason = ("offered as general knowledge and refused the label because "
                      + "; ".join(blocked) + " — checked as a claim about this "
                      "plan instead: " + out.reason)
    return out


def _verify_one(claim: DraftClaim, *, toolbox: Any,
                wide: Optional[_Scope] = None,
                gk_blocked_out: Optional[list] = None) -> VerifiedClaim:
    ex = toolbox._ex
    if wide is None:
        wide = _Scope(toolbox, list(getattr(toolbox, "consulted", []) or []))
    cited = [r for r in claim.record_ids if r]
    consulted = list(getattr(toolbox, "consulted", []) or [])
    scope_ids = cited or consulted
    scope = _Scope(toolbox, scope_ids)

    # Session 4B.5 CU5(d) — PER-CLAIM provenance, not an answer-level copy.
    #
    # This was ``consulted[:12]`` — the whole answer's consulted set, identical on
    # every claim — and the surface printed the first three of it beside each
    # interpretive sentence as that sentence's "read from". Answer-level
    # provenance wearing per-claim clothes is worse than none: it looks like an
    # attribution and cannot be wrong, so nobody checks it.
    #
    # What each claim was ACTUALLY checked against is ``scope_ids``: its own
    # citations when it made any, the whole consulted set when it made none. The
    # second case is not a fudge — an uncited claim really is checked against
    # everything the loop read, and saying so is the honest label.
    base = dict(text=claim.text, kind=claim.kind, cited_record_ids=cited,
                consulted_record_ids=list(scope_ids)[:12],
                read_from=_read_from(toolbox, scope_ids))

    # 1 — a citation that names nothing real. The ordinal disease: a list position,
    # a made-up id, a record from another run. Never softened; always cut.
    if cited and scope.missing:
        return VerifiedClaim(
            status=ClaimStatus.FAILED,
            reason=("cites record id(s) that do not exist in this run: "
                    + ", ".join(scope.missing[:3])),
            **base)

    assertions = extract_assertions(
        claim.text,
        order_refs=getattr(ex, "_order_refs", {}) or {},
        machine_refs=getattr(ex, "_machine_refs", {}) or {},
        order_shapes=getattr(ex, "_order_shape_patterns", []) or [])

    # 1a-i — R-TG6 (iii). A general rule this product's own floor vocabulary
    # falsifies. Checked on EVERY claim, whatever label it wears: the founding
    # specimen's first line carried the same wrong rule as a CITED board claim,
    # so a check that ran only on general-knowledge claims would have caught one
    # of the two sentences that said it.
    floor_bad = floor_contradictions(claim)
    if floor_bad:
        return VerifiedClaim(
            status=ClaimStatus.FAILED, assertions=assertions,
            reason=FLOOR_REFUTED_PREFIX + floor_bad[0],
            **base)

    # 1a-ii — R-TG6 (ii). A named order this claim says can move, against the
    # mobility floor's verdict for that order's operations. The floor is ASKED
    # (`order_mobility_verdicts`), never re-derived.
    mob_bad = mobility_contradictions(claim, assertions, toolbox=toolbox)
    if mob_bad:
        return VerifiedClaim(
            status=ClaimStatus.FAILED, assertions=assertions,
            reason=FLOOR_REFUTED_PREFIX + mob_bad[0],
            **base)

    # 1a-iii — R-TG6 (i). A sentence about what THIS PRODUCT does, offered with
    # no citation. It is not general knowledge (it is about us) and it is not a
    # reading of this plan (there is no record of our own behaviour in a run's
    # evidence), so neither available label describes it and both would mislead.
    #
    # A CITED product claim is UNTOUCHED and that is deliberate: 4B.15 §5a.43
    # built exactly one honest path for a capability claim — ground it in the
    # docs/05 catalog through the `constraint_catalog` tool — and this check
    # must push toward that path, never close it. So the discriminator is the
    # citation, and the drop lands only on the sentence that asserted our
    # behaviour from nothing.
    if not cited:
        pb = product_behavior_disqualifiers(claim)
        if pb:
            return VerifiedClaim(
                status=ClaimStatus.FAILED, assertions=assertions,
                reason=PRODUCT_BEHAVIOR_REASON + " (" + "; ".join(pb[:2]) + ")",
                **base)

    # 1b — R-TG1, ENFORCEMENT DIRECTION (i). The model proposed this sentence as
    # domain knowledge rather than a read of the board. That proposal is INPUT
    # (R-AI5(8)); the check below is what decides, and it can only ever DEMOTE.
    #
    # Clean: the claim carries no board content, so there is nothing here a record
    # could speak to. Verification is SKIPPED — not passed, not failed — and the
    # sentence is labeled for what it is. This is the one status in the taxonomy
    # that is not a verdict about grounding.
    #
    # Disqualified: it named an order, a time, a figure we computed, or it cited a
    # record. It falls straight through to ordinary board-claim verification and
    # is verified or dropped on the usual terms. It is NEVER shipped labeled —
    # a class nobody verifies must not be reachable by assertion.
    if claim.kind is ClaimKind.GENERAL_KNOWLEDGE:
        gk_blocked = gk_disqualifiers(claim, assertions, scope, wide)
        if gk_blocked_out is not None:
            gk_blocked_out.extend(gk_blocked)
        if not gk_blocked:
            # NO PROVENANCE FIELDS. `base` would carry the whole consulted set and
            # every tool the loop called, because an uncited claim is checked
            # against everything read — but this claim was checked against
            # NOTHING, and a durable record saying it was read from four tool
            # calls is the very defect the class exists to end (4B.5 CU5(d)'s
            # answer-level-provenance-in-per-claim-clothes, one seam further on).
            return VerifiedClaim(
                text=claim.text, kind=claim.kind,
                status=ClaimStatus.GENERAL_KNOWLEDGE, assertions=assertions,
                reason="domain knowledge — it makes no claim about this plan, so "
                       "there is nothing in this run's records to check it against")

    # A QUANTIFYING claim's figures are checked against the tallies of the single
    # call that enumerated the set — not against every tally the session happens to
    # have produced. "3 of 15 orders are late" must not pass because some unrelated
    # read returned three rows.
    quant = next((a for a in assertions if a.kind == "quantifier"), None)
    cover = _covering_call(toolbox, cited)
    if quant is not None:
        # Tighten: a quantifying claim's figures must be the ENUMERATING call's own
        # tallies, not any tally the session happens to have produced.
        scope.counts = set(cover[2]) if cover else set()
        scope.tallies = set(cover[2]) if cover else set()

    checkable = [a for a in assertions if a.kind != "quantifier"]
    results = []
    for a in checkable:
        verdict = _check(a, scope, wide)
        a.grounded = verdict == _GROUNDED
        a.detail = a.detail or verdict
        results.append(verdict)

    # 2 — a checkable assertion that contradicts the evidence. Cut.
    if _CONTRADICTED in results:
        bad = [a.text for a, v in zip(checkable, results) if v == _CONTRADICTED]
        return VerifiedClaim(
            status=ClaimStatus.FAILED, assertions=assertions,
            reason="contradicted by the cited evidence: " + ", ".join(bad[:3]),
            **base)

    # 2b — R-TG1, ENFORCEMENT DIRECTION (ii). THE THIRD STATE IS CLOSED.
    #
    # A claim that cites no record, grounds no checkable assertion, and carries no
    # board content whatever is not a reading of this plan — there is nothing of
    # this plan in it to read. Before R-TG1 it shipped anyway, labeled
    # `[synthesis — read from: <ids>]` or `[synthesis — my reading, no record
    # states this]`, and both of those assert that the sentence came out of this
    # board's evidence. Measured on the demo board, seven such sentences shipped
    # across seven synthesis answers, four of them pure textbook optimization.
    #
    # It is DROPPED, not auto-labeled, and that is the hard call. Auto-labeling
    # would be more generous to a true sentence — but the verifier can only prove
    # the label's SECOND half ("not a fact about this plan"); the first half
    # ("this is how scheduling works generally") is a claim about the sentence
    # that only the author can make. "Things are pretty tight right now" carries
    # no board content either, and it is a vague assertion about the plant, not
    # domain knowledge. The verifier may REFUTE a proposal and may not
    # MANUFACTURE one — the parse layer's discipline (R-AI5(8)) at this seam.
    # `load_bearing` then tells the planner something was left out.
    if (claim.kind is not ClaimKind.GENERAL_KNOWLEDGE and not cited
            and _GROUNDED not in results
            and not _has_board_content(claim, assertions, scope, wide)):
        return VerifiedClaim(
            status=ClaimStatus.FAILED, assertions=assertions,
            reason=UNPLACEABLE_REASON, **base)

    # 3 — nothing checkable at all: an aggregate read, a mechanism, an inference.
    if not checkable or _GROUNDED not in results:
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason=("no assertion this run's records can check"
                    if not checkable else
                    "its specifics are not spoken to by the cited records"),
            sample_note=_sample_note(toolbox) if quant is not None else "",
            **base)

    # 4 — completeness honesty: a claim quantifying over a set is proven only when
    # ONE tool call enumerated that set AND the figures are that call's own tallies.
    # Otherwise it is a reading of a SAMPLE, and the sample is named.
    if quant is not None and cover is None:
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason=f"quantifies ({quant.text}) over a set no single read enumerated",
            sample_note=_sample_note(toolbox), **base)

    # 5 — VERIFIED means EVERY checkable assertion grounds. One the records simply
    # do not speak to is not a contradiction, but it is not proof either: the claim
    # stays visibly synthesis rather than being promoted on its neighbours' backs.
    if _UNCHECKED in results:
        loose = [a.text for a, v in zip(checkable, results) if v == _UNCHECKED]
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason=("part of it is not spoken to by the cited records: "
                    + ", ".join(loose[:3])),
            sample_note=_sample_note(toolbox) if quant is not None else "",
            **base)

    # 6 — a sentence whose ONLY grounded assertion is a name is not proven. "ORD-01
    # sits behind the queue on the cutting line" mentions a real order and asserts a
    # mechanism no record states; promoting it because the name resolves would put
    # the proven register behind an unchecked claim. A citation promises the FIGURE
    # or the TIME grounds, not that the sentence names something that exists.
    if not any(a.grounded for a in assertions if a.kind != "entity"):
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason="its only checkable content is a name; the substance is my "
                   "reading", **base)

    # 7 — the model called this its CONCLUSION. A structural annotation, not a
    # provenance one (R-AI5(8) forbids the model GRADING its claims; saying which
    # sentence is the conclusion is a statement about the answer's shape, and it can
    # only ever demote). A conclusion is a reading by construction — it renders in
    # the synthesis register with the records it was read from.
    if claim.kind is ClaimKind.CONCLUSION:
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason="this is the answer's conclusion — a reading of the records, "
                   "not something one of them states", **base)

    # 8 — grounded, but the model cited nothing: correct is not the same as proven.
    # Never silently promoted (CU3's named test).
    if not cited:
        return VerifiedClaim(
            status=ClaimStatus.INTERPRETIVE, assertions=assertions,
            reason="grounded in what I consulted, but the claim cites no record",
            **base)

    return VerifiedClaim(status=ClaimStatus.VERIFIED, assertions=assertions,
                         reason="every checkable assertion grounds in the cited "
                                "records", **base)


def _covering_call(toolbox: Any, cited: list[str]) -> Optional[tuple]:
    """The enumerating tool call a quantifying claim rests on, or None.

    "Can the verifier enumerate the set from a single tool call" (CU3's
    completeness-honesty rule), made operational: EVERY citation must come from a
    call that enumerated its whole set — one filtered read among them and the claim
    is a sample — and the covering call is the enumerating one it cites most of.
    Its own tallies are then what the claim's figures are checked against.

    A NAMED LIMIT: this checks that a figure is one the toolbox itself computed
    over an enumerated set, not that it is the RIGHT tally for the words around it.
    A count semantically attached to the wrong tally of the same call can still
    pass. Typing a count to its predicate is a semantic problem this pass does not
    solve, and it is stated here rather than implied away."""
    entries = list(getattr(toolbox, "enumerated", []) or [])
    if not cited or not entries:
        return None
    enumerated_ids: set = set()
    for entry in entries:
        enumerated_ids |= entry[1]
    if not all(c in enumerated_ids for c in cited):
        return None                    # something came from a filtered read
    best, best_overlap = None, 0
    for entry in entries:
        overlap = sum(1 for c in cited if c in entry[1])
        if overlap > best_overlap:
            best, best_overlap = entry, overlap
    return best


def _sample_note(toolbox: Any) -> str:
    """The authored note naming what the claim actually rests on."""
    from mre.modules.ask_fallback_copy import SYNTHESIS_SAMPLE_NOTE
    best = None
    for call in getattr(toolbox, "calls", []) or []:
        if call.ok and call.rows and (best is None or call.rows > best.rows):
            best = call
    if best is None:
        return ""
    return SYNTHESIS_SAMPLE_NOTE.format(n=best.rows, tool=best.tool)


def verify_draft(question: str, claims: list[DraftClaim], *,
                 toolbox: Any) -> SynthesisAnswer:
    """The whole hardening pass: verify every claim, cut what failed, and decide
    whether what was cut was LOAD-BEARING (the honest "I couldn't ground part of my
    reasoning" trigger — computed here, never asserted by the model)."""
    # Assembled ONCE for the whole draft: everything the loop read, independently
    # re-fetched. It is the appeal an under-cited claim gets (see ``_check``).
    wide = _Scope(toolbox, list(getattr(toolbox, "consulted", []) or []))
    verdicts = [verify_claim(c, toolbox=toolbox, wide=wide) for c in claims]
    kept = [v for v in verdicts if v.status is not ClaimStatus.FAILED]
    cut = [v for v in verdicts if v.status is ClaimStatus.FAILED]
    any_verified = any(v.status is ClaimStatus.VERIFIED for v in kept)
    for v in cut:
        v.load_bearing = (v.kind is ClaimKind.CONCLUSION) or not any_verified
    return SynthesisAnswer(question=question, claims=kept, cut=cut,
                           unanswerable=not kept)
