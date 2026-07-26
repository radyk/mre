"""Probation shadowing and the fact-agreement diff (R-AI5(7), Session 4A.5c CU2c).

R-AI5(7): *"promoted routes run shadowed for a probation window; demotion to
synthesis on divergence is automatic."* This module is the diff that decides what
"divergence" means, and it is deliberately the most conservative thing in the
session — a false positive here DEMOTES A CORRECT ROUTE, silently making the
product worse in the name of safety.

THE COMPARISON, STATED IN FULL.

A promoted route answers from PRE-COMPUTED FACTS: its bundle carries ``key_facts``,
a dict of labelled values it assembled deterministically. The synthesis shadow
answers in sentences, each carrying a verification status. So the diff runs between
two things that are actually comparable:

    the route's LABELLED numeric facts   vs   the numbers in the shadow's claims

For each numeric ``key_fact``:

  1. Its label is tokenized (``late_count`` -> {late}), stopwords dropped.
  2. In each shadow claim, every number is located — with entity refs stripped
     FIRST, so the "05" in "ORD-05" is never mistaken for a quantity — and small
     spelled-out numerals ("one", "three") read as numbers, because a sentence that
     says "only one order is late" is stating the count.
  3. A number is a CANDIDATE for that fact only if a label token appears within
     ``WINDOW`` tokens of it AND THE UNITS AGREE (below).
  4. If ANY candidate equals the fact -> AGREED. If candidates exist and NONE
     equals it -> CONTRADICTED. If there are no candidates, the two sides simply
     did not both speak to that quantity, and nothing is recorded.

AGREEMENT WINS INSIDE A SENTENCE. A claim that states the figure correctly
somewhere has not contradicted it, whatever else the sentence also counts.

UNITS GATE THE MATCH, and this is the rule that stops the diff being useless.
Proximity alone fires constantly. The real specimen, from this session's own
dossier validation: the shadow's verified claim

    "ORD-05 is the only late order, finishing 890 minutes (nearly 15 hours) past
     its due date"

sits four tokens from the word "late", so a proximity-only rule offered 890 and 15
as candidates for ``late_count`` = 1, found neither equal, and reported the route
as CONTRADICTING a claim that agrees with it perfectly. A figure carrying a unit
the label does not have is not that label's figure: 890 MINUTES is not a count of
orders. So a number followed by a unit word matches only labels naming that unit,
a currency figure matches only money labels, and a bare number matches any label
whose tokens are in the window. The claim above then offers NO candidate for
``late_count`` and the two sides are simply recorded as not both having spoken to
it — which is the truth.

WHAT IS NOT A DIVERGENCE, and why the list matters more than the rule:

  * A figure only ONE side mentions. The route answers in its authored shape and
    the shadow reasons in its own; demanding they say the same words would fire on
    every turn and teach everyone to ignore the signal.
  * An INTERPRETIVE claim. It is a labeled reading, not a competing fact — the
    whole point of promoting a shape is that the route can PROVE what synthesis
    could only read. Interpretive claims are used for ``provenance_strengthened``,
    never for divergence.
  * A CUT claim. It never reached a planner and never will.

Only a contradiction between the route's pre-computed fact and a VERIFIED shadow
claim fires. That is a real disagreement between two independent readings of the
same evidence, which is exactly the thing a probation exists to catch.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from mre.contracts.promotion import ShadowDiff


#: How many tokens either side of a number a label token must appear within for
#: that number to be a candidate for that fact.
WINDOW = 6

#: Label tokens that carry no meaning and would match anything.
_LABEL_STOP = frozenset({
    "count", "total", "totals", "value", "values", "list", "summary", "id",
    "ref", "refs", "the", "of", "a", "an", "is", "are", "minutes", "hours",
    "days", "iso", "code", "phrase", "name", "names", "all",
})

#: Spelled-out numerals a planner-voiced sentence actually uses.
_WORD_NUMBERS = {
    "zero": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}

#: An entity ref, stripped before numbers are read (ORD-05, CUT-01, M-GEAR-01).
_ENTITY_REF = re.compile(r"\b[A-Za-z][A-Za-z]*(?:-[A-Za-z0-9]+)+\b")

#: Dates and clock times, stripped for the same reason entity refs are: they are
#: not QUANTITIES. A claim's timestamps are checked by the claim verifier, which
#: reads them as minute tuples; this diff is about counts, durations and money,
#: and left in they are a false-positive factory. The specimen that forced this,
#: from the dossier's own validation: "...its due date is 2026-01-05 at 23:59:59
#: UTC, already past by the time it runs" put the 59 of a clock time six tokens
#: from the word "time" and reported it as contradicting on_time_count = 14.
_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{1,2}:\d{2}(?::\d{2})?Z?)?\b"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\b")

#: A number, with thousands separators and a currency prefix tolerated. The 4A.5b
#: verifier calibration learned this one the hard way: "$5,906" split into two
#: numbers and cut three true claims.
_NUMBER = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?")

#: Relative tolerance for comparing a route fact against a claim's figure. A claim
#: rounds ("nearly 15 hours", "$370.83" vs 370.8333) and rounding is not
#: disagreement.
TOLERANCE = 0.01

#: Unit words that may follow a figure, grouped to the unit they name.
_UNIT_WORDS = {
    "minute": "minutes", "minutes": "minutes", "min": "minutes",
    "mins": "minutes",
    "hour": "hours", "hours": "hours", "h": "hours", "hrs": "hours",
    "day": "days", "days": "days",
    "percent": "percent",
}

#: Label words that mean the figure is MONEY.
_MONEY_WORDS = frozenset({"cost", "costs", "charge", "charges", "price",
                          "tardiness", "money", "dollars", "spend"})


def _label_tokens(label: str) -> set:
    parts = re.split(r"[_\s\-]+", str(label).lower())
    return {p for p in parts if p and p not in _LABEL_STOP and len(p) > 2}


def _label_unit(label: str) -> Optional[str]:
    """The unit a LABEL names, or None for a bare count / unitless figure.

    Read from the label's own words — ``lateness_minutes`` is minutes,
    ``tardiness_total`` is money, ``late_count`` is neither."""
    parts = set(re.split(r"[_\s\-]+", str(label).lower()))
    for word in parts:
        if word in _UNIT_WORDS:
            return _UNIT_WORDS[word]
    if parts & _MONEY_WORDS:
        return "money"
    return None


def _tokenize(text: str) -> list:
    """The claim as tokens, with entity refs and timestamps removed so their
    digits cannot be read as quantities."""
    cleaned = _TIMESTAMP.sub(" ", text or "")
    cleaned = _ENTITY_REF.sub(" ", cleaned)
    return re.findall(r"[A-Za-z]+|-?\$?\d[\d,]*(?:\.\d+)?", cleaned)


def _as_number(token: str) -> Optional[float]:
    low = token.lower()
    if low in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[low])
    if not _NUMBER.fullmatch(token):
        return None
    try:
        return float(token.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _units_agree(want: Optional[str], figure: Optional[str]) -> bool:
    """Whether a figure carrying ``figure`` units can be the value of a label
    naming ``want`` units.

    Asymmetric on purpose. A COUNT accepts only bare figures — "890 minutes" is
    never a count of orders. MONEY accepts a currency figure or a bare one,
    because planner prose writes both "$370.83" and "370.83 in tardiness cost". A
    TIME unit accepts only the same time unit, since minutes and hours are the two
    the answers actually mix up."""
    if want is None:
        return figure is None
    if want == "money":
        return figure in (None, "money")
    return figure == want


def _close(a: float, b: float) -> bool:
    if a == b:
        return True
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale <= TOLERANCE


def numeric_facts(key_facts: dict) -> dict:
    """The route's labelled numeric facts — the only side of the diff that has
    labels, which is why the comparison runs FROM here.

    SCALARS ONLY, and nested scalars one level down. Lists are deliberately NOT
    reduced to a ``<label>_count``: the route does not STATE "there is 1 tardiness
    line", so there is nothing for the shadow to agree or disagree with, and the
    synthesized label collides with the real quantities that share its words —
    ``tardiness_lines_count`` = 1 was reported as contradicting the perfectly
    correct claim "a tardiness cost of $370.83" in this session's first dossier
    validation. A fact nobody asserts cannot be contradicted."""
    out: dict = {}
    for label, value in (key_facts or {}).items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[str(label)] = float(value)
        elif isinstance(value, dict):
            for sub, sv in value.items():
                if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                    out[f"{label}_{sub}"] = float(sv)
    return out


def candidates_for(claim_text: str, label: str) -> list:
    """Every number in ``claim_text`` that could be ``label``'s figure: a token of
    the label sits within ``WINDOW`` tokens of it, AND the units agree."""
    tokens = _tokenize(claim_text)
    wanted = _label_tokens(label)
    if not wanted:
        return []
    want_unit = _label_unit(label)
    lowered = [t.lower() for t in tokens]
    out: list = []
    for i, tok in enumerate(tokens):
        n = _as_number(tok)
        if n is None:
            continue
        # The unit this FIGURE carries: a following unit word, or a currency
        # prefix. A figure whose unit the label does not name is not the label's
        # figure, however close the words happen to sit.
        nxt = lowered[i + 1] if i + 1 < len(tokens) else ""
        figure_unit = _UNIT_WORDS.get(nxt)
        if figure_unit is None and tok.strip().startswith("$"):
            figure_unit = "money"
        if not _units_agree(want_unit, figure_unit):
            continue
        lo, hi = max(0, i - WINDOW), min(len(tokens), i + WINDOW + 1)
        if wanted & set(lowered[lo:hi]):
            out.append(n)
    return out


def claim_dicts(synthesis: Any) -> list:
    """A ``SynthesisAnswer`` OR a ledger entry's recorded claims -> one shape.

    Both callers of the diff must apply the SAME rule. The probation shadow holds
    a live ``SynthesisAnswer``; the dossier's harness validation holds the claims
    as the ledger recorded them, dicts. Normalizing here is what stops the two
    from drifting into two different definitions of "divergence" — which they had
    already done once, the dossier counting INTERPRETIVE claims as contradictions
    that the probation would have ignored."""
    if synthesis is None:
        return []
    if isinstance(synthesis, list):
        return [c for c in synthesis if isinstance(c, dict)]
    out = []
    for c in getattr(synthesis, "claims", []) or []:
        out.append({"text": c.text,
                    "status": getattr(c.status, "value", c.status)})
    return out


def diff_claims(bundle: Any, claims: list, *, question: str = "",
                intent: str = "") -> ShadowDiff:
    """THE ONE DIFF. Both the probation shadow and the dossier's harness
    validation come through here, so "divergence" means one thing."""
    facts = numeric_facts(getattr(bundle, "key_facts", {}) or {})
    verified = [c for c in claims if c.get("status") == "verified"]
    interpretive = [c for c in claims if c.get("status") == "interpretive"]

    agreed: list = []
    contradicted: list = []
    spoken_to: set = set()
    for label, value in facts.items():
        matched = False
        conflicted = False
        for claim in verified:
            cands = candidates_for(claim.get("text", ""), label)
            if not cands:
                continue
            spoken_to.add(label)
            if any(_close(value, c) for c in cands):
                matched = True
                break              # agreement wins; stop looking
            conflicted = True
        if matched:
            agreed.append(label)
        elif conflicted:
            contradicted.append(label)

    # A verified claim that shares no labelled quantity with the route's facts.
    # Reported for the reviewer — the shadow found something the route does not
    # say — and never a trigger.
    shadow_only: list = []
    for claim in verified:
        text = claim.get("text", "")
        if not any(candidates_for(text, label) for label in facts):
            shadow_only.append(text if len(text) <= 160 else text[:157] + "...")

    # The promotion's own claim: the route CITES what synthesis could only read.
    strengthened = bool(
        getattr(bundle, "ordered_records", None)
        and any(candidates_for(c.get("text", ""), label)
                for c in interpretive for label in facts))

    return ShadowDiff(
        question=question, intent=intent,
        agreed=sorted(agreed), contradicted=sorted(contradicted),
        shadow_only=shadow_only[:5],
        provenance_strengthened=strengthened,
    )


def shadow_diff(bundle: Any, synthesis: Any, *, question: str = "",
                intent: str = "") -> ShadowDiff:
    """Diff a promoted route's bundle against its synthesis shadow.

    ``synthesis`` may be None (no synthesizer available), in which case the diff is
    UNCHECKED — reported as such, never as clean. That is the 4A.5a door-check
    discipline: an instrument that cannot run says so."""
    if synthesis is None:
        return ShadowDiff(question=question, intent=intent, unchecked=True)
    return diff_claims(bundle, claim_dicts(synthesis),
                       question=question, intent=intent)


# ---------------------------------------------------------------------------
# Running the shadow
# ---------------------------------------------------------------------------

def run_shadow(explainer: Any, question: str, bundle: Any, intent: str, *,
               synthesizer: Any = None, context: Optional[dict] = None
               ) -> Optional[ShadowDiff]:
    """Answer ``question`` a SECOND time through the synthesis tier and diff it
    against the promoted route's bundle.

    Returns None when ``intent`` is not on probation — the shadow is not a
    permanent tax on every answer, it is what a probation IS. Costs one full
    synthesis (roughly 10s and a dozen model calls), which is why it runs in the
    sweep and not on the planner's turn."""
    from mre.contracts.parse import Intent
    from mre.contracts.promotion import shadowed_intents

    try:
        as_intent = Intent(intent)
    except ValueError:
        return None
    if as_intent not in shadowed_intents():
        return None
    if synthesizer is None or not getattr(synthesizer, "available", False):
        return ShadowDiff(question=question, intent=intent, unchecked=True)

    import time
    from mre.modules.evidence_tools import EvidenceToolbox
    started = time.perf_counter()
    try:
        answer = synthesizer.synthesize(
            question, explainer=explainer, context=context,
            toolbox=EvidenceToolbox(explainer))
    except Exception:  # noqa: BLE001 — a shadow failure must never break the turn
        return ShadowDiff(question=question, intent=intent, unchecked=True,
                          latency_ms=(time.perf_counter() - started) * 1000.0)
    diff = shadow_diff(bundle, answer, question=question, intent=intent)
    return diff.model_copy(
        update={"latency_ms": (time.perf_counter() - started) * 1000.0})
