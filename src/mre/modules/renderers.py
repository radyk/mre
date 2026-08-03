"""Renderers for ExplanationBundle -> text.

TemplateRenderer    - deterministic, footnoted record IDs.  Used in all tests.
LLMRenderer         - Anthropic API.  Falls back to TemplateRenderer if no key.

Rendering rules (from CLAUDE.md / docs/03):
- Use planner vocabulary (WO-2001, M-GEAR-01), never UUIDs.
- basis=reconstructed -> "X was assigned to Y; Z would have cost more / was unavailable"
- Every cited claim gets a footnoted record ID.
- Do not add information not present in the evidence bundle.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from mre.modules.explainer import ExplanationBundle
from mre.modules.planner_language import (
    driver_phrase, elapsed_minutes, has_jargon, stage_name, strip_formatting,
    strip_jargon,
)

_LOG = logging.getLogger("mre.renderers")

# ---------------------------------------------------------------------------
# SESSION 4B.21 ITEM 5(a) — WHAT A PLANNER IS TOLD WHEN A RENDER FAILS CLOSED.
#
# The census of diagnostic strings that could reach the answer surface found
# five, all of them written for whoever maintains the check that emitted them:
#
#   [LLM validation failed: <the check's own verdict>; fell back to template]
#   [LLM validation failed: invented a value; fell back to authored text]
#   [LLM error: <PythonExceptionClassName>; fell back to template]
#   [LLM error: <PythonExceptionClassName>; fell back to authored text]
#   [rendered by: template (LLM error) | register: …]
#
# Every one of them says the same thing to a planner — the answer you are
# reading is the deterministic text, not the model's prose — and says it in
# vocabulary that belongs in a log. These two constants are that fact, phrased
# once, for the answer surface. The detail is kept on the renderer's
# `last_diagnostics` and logged at DEBUG.
#
# THE RENDERED-BY TAG CHANGED, DELIBERATELY. "template (LLM validated)" read as
# though the model had validated the answer; it meant the opposite. The exam
# sidecar keys its `validator` tripwire on this tag and was updated in the same
# commit — the instrument follows the vocabulary, not the reverse.
# ---------------------------------------------------------------------------

#: The model drafted an answer and it did not pass verification.
DRAFT_REJECTED_FOOTER = (
    "[rendered by: template (model draft rejected) | register: {register}]")
#: The model could not be reached at all.
MODEL_UNAVAILABLE = "the model was unavailable"

# Patterns for post-render validation
# Captures full timestamp: date + optional time + optional timezone
_TS_FULL_RE = re.compile(
    r'\b(\d{4}-\d{2}-\d{2}'                         # YYYY-MM-DD
    r'(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?'   # optional T/space HH:MM[:SS[.fff]]
    r'(?:Z|[+-]\d{2}:?\d{2}|\s*UTC)?)',              # optional timezone
    re.IGNORECASE,
)
# Time-unit numbers: "840 min", "14h", "14.0 hours", etc.
_TIME_NUM_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(min(?:utes?)?|h(?:ours?)?)\b', re.IGNORECASE)
_MACHINE_RE = re.compile(r'\bM-[A-Z][A-Z0-9-]*')


def _to_minute_tuple(s: str) -> Optional[tuple]:
    """Parse timestamp string to (year, month, day, hour, minute), or None.

    Strips Z / UTC / ±HH:MM suffixes and converts T-separator to space so
    strptime sees a clean 'YYYY-MM-DD HH:MM[:SS]' or 'YYYY-MM-DD' string.
    Returns hour=minute=-1 for date-only forms.
    """
    clean = s.strip()
    clean = re.sub(r'Z\s*$', '', clean)
    clean = re.sub(r'\s*UTC\s*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[+-]\d{2}:?\d{2}\s*$', '', clean)
    clean = clean.strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            dt = datetime.strptime(clean, fmt)
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        except ValueError:
            pass
    try:
        dt = datetime.strptime(clean, '%Y-%m-%d')
        return (dt.year, dt.month, dt.day, -1, -1)
    except ValueError:
        pass
    return None


def _ts_matches(prose_tup: tuple, bundle_tuples: set) -> bool:
    """True if prose timestamp matches any bundle timestamp at minute granularity.
    Date-only prose (hour=-1) matches any bundle timestamp with the same date.
    """
    if prose_tup[3] == -1:
        return any(bt[:3] == prose_tup[:3] for bt in bundle_tuples)
    return prose_tup in bundle_tuples


def _signed(v: Any) -> str:
    """A signed dollar amount for a cost-delta component (CU2). None → '—'."""
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else '−'}${abs(v):,.0f}"


def _to_minutes(value: float, unit: str) -> float:
    """Convert a time value to minutes based on its unit string."""
    return value * 60.0 if unit.lower().startswith('h') else value


def _append_take(text: str, bundle: ExplanationBundle) -> str:
    """R-AI3(1,2,5) — a labeled judgment rides AFTER the testimony, never inside
    it. The take is AUTHORED (composed on the bundle from evidence, `key_facts`),
    so appending it deterministically here — rather than trusting the LLM to keep
    it — is what stops the testimony prompt's no-opinion rules from paraphrasing
    it away (the 4A.2d detachment: the take rode the TEMPLATE floor only, and the
    live LLM path showed it merely inside the evidence chain and dropped it). The
    label is the boundary; nothing above it may masquerade as fact."""
    take = bundle.key_facts.get("take") if bundle.key_facts else None
    if not take or "My take:" in text:
        return text
    return f"{text.rstrip()}\n\nMy take: {take}"




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_name(entity_id: str, entity_type: str, identity_map: Any) -> str:
    """Resolve canonical UUID to human-readable external name."""
    if not entity_id:
        return "?"
    if identity_map is None:
        return entity_id[:12]
    preferred = {
        "demand": "work_order",
        "resource": "machine_id",
        "product": "product_no",
    }
    pref = preferred.get(entity_type, "")
    refs = identity_map.external_refs(entity_id)
    for ref in refs:
        if ref.type == pref:
            return ref.value
    return refs[0].value if refs else entity_id[:12]


def _did_you_mean(names: list[str]) -> str:
    """The near-match offer for an unknown entity (Session 4B.19 Item 3(c)).

    Authored copy, one seam, so the machine and order branches cannot phrase the
    same correction two ways. The caller has already decided these are CLOSE
    (explainer._nearest_names); this only words them."""
    if len(names) == 1:
        return f"Did you mean {names[0]}?"
    return "Did you mean " + ", ".join(names[:-1]) + f" or {names[-1]}?"


# ---------------------------------------------------------------------------
# TemplateRenderer
# ---------------------------------------------------------------------------

# The register the rendered footer (the envelope) declares — resolved through
# the SAME single source the API metadata (the chip) uses, so chip == envelope
# always (Session 4A.2 CU6 — the register-tag seam).
def _register_for(bundle: ExplanationBundle) -> str:
    from mre.modules.explainer import register_of
    return register_of(bundle)


# Session 4A.5b (R-AI5(4)) — the rendered-by line NAMES THE TIER and the tool-call
# count for a synthesis answer. A planner reading "[rendered by: synthesis …]" knows
# immediately that no contracted route covered their question, and how much evidence
# the answer actually cost to assemble.
def _rendered_by(bundle: ExplanationBundle, default: str) -> str:
    if bundle.subject_type == "synthesis":
        kf = bundle.key_facts or {}
        model = kf.get("model") or ""
        tier = f"synthesis ({model})" if model else "synthesis"
        n = kf.get("tool_call_count", 0)
        # Session 4A.5c CU3(c) — when the ADJACENT-MATCH GUARD diverted a matched
        # intent here, the rendered-by says WHY. A planner who asked about next
        # month and got a reasoned answer instead of a proven one is owed the
        # reason in the same breath: it was their qualifier, not a failure to
        # understand them.
        diverted = kf.get("diverted_qualifier") or ""
        if diverted:
            tier = f"{tier} — no route covers \"{diverted}\""
        return f"[rendered by: {tier} — {n} tool call(s) | register: synthesis]"
    if bundle.subject_type == "prove_it":
        return "[rendered by: synthesis (grounding pass) | register: synthesis]"
    return f"[rendered by: {default} | register: {_register_for(bundle)}]"


# Subject types whose whole answer is composed in the header in planner language
# (Session 4A.2). They never dump the raw evidence chain.
_HEADER_ONLY_SUBJECTS = frozenset({
    "findings", "order_attributes", "inventory", "integrity", "start_reason",
    "unknown_entity", "drill_down", "briefing", "contested_fact",
    # Session 4B.14 Item 2 — the blocker analysis composes its whole answer from
    # pre-computed key_facts (the ladder, the binding family, its arithmetic).
    # Session 4B.16 Item 1 — and its inverse, the counterfactual, likewise.
    # Session 4B.30 — and the LATER direction likewise: its whole answer is the
    # resolved target, the price and the branch, all computed before render.
    "why_here", "counterfactual", "later_move",
    # Session 4A.3 — the swap/move bridge + the absence pair compose their whole
    # answer in the header (the R-AI3 ladder in planner language).
    "swap_move", "gap_between", "machine_idle",
    # Session 4A.5c CU4 — the rolling answers compose their whole body in the
    # header (they are read from the document, not from evidence records).
    "rolling",
    # Session 4A.3c CU2 — a schedule listing renders its table in the header; it now
    # carries ordered_records (real assignment Decisions) to LIGHT the narrated bars
    # (cited_refs), but header-only keeps the prose the clean table it was — no
    # redundant raw evidence-chain dump under a table that already shows the rows.
    "schedule",
    # Session 4A.5b — the labeled-synthesis surface composes its whole answer as
    # CLAIM BLOCKS with per-claim provenance; the raw chain under it would repeat
    # the same records the claims already cite, unlabeled.
    "synthesis", "prove_it",
    # Session 4B.5 CU2 — the open delta card is VOICED, not re-derived: its whole
    # answer is the card's own figures in sentences, and it carries no evidence
    # chain by construction (the card arrived on the context channel).
    "open_card",
})

# The citation-breadth cap (CU6): a schedule-wide answer shows at most this many
# raw records before summarizing "… and N more".
CITATION_CAP = 8


# ---------------------------------------------------------------------------
# THE VACUOUS-CAUSAL TRIPWIRE (Session 4B.5 CU3b).
#
# The founder's specimen: "why is ORD-000008 on PAINT-02?" -> "because the
# machine was busy with other work [record: bafa03f1…]". Every existing check
# passed it, and they were right to: the record is real, the citation is real,
# there is no fabricated timestamp, number or machine name. The testimony
# validator asks "is anything here made up"; nothing was. What nobody asked is
# whether the sentence SAYS anything — and an unfalsifiable sentence fabricates
# nothing by construction, so it sails through a fabrication check every time.
#
# So the causal routes get a check of the other kind. It is deliberately a FLOOR,
# not a judgment of quality: three ways to say something, any one of which is
# enough, and an answer with none of them is not an answer.
# ---------------------------------------------------------------------------

#: The subject types whose answers CLAIM A CAUSE — why-on-machine and why-late
#: (both "demand"), start-reason, and the gap explainer. These are the answers a
#: planner acts on, and the ones where saying nothing convincingly is possible.
CAUSAL_SUBJECT_TYPES = frozenset({"demand", "start_reason", "gap_between"})

# Quantity: any digit. A date, a duration, a count and a dollar figure are all
# concrete and all checkable, and a causal answer carrying one of them is not the
# thing this tripwire is for.
_QUANTITY_RE = re.compile(r"\d")


def causal_vacuity(text: str, *, subjects=(), entities=(),
                   driver_phrases=None) -> Optional[str]:
    """Is this causal answer VACUOUS? None when it says something; a stated reason
    when it does not — the caller then fails closed (Session 4B.5 CU3b).

    An answer is NOT vacuous if it does any one of these:

      * names a DRIVER PHRASE from the authored vocabulary — the plant's own
        causal language, which is at least a claim about a mechanism;
      * names a CONCRETE ENTITY BEYOND the question's own subjects — another
        order, another machine. Repeating back the two nouns the planner just
        said is not an answer to why;
      * states a QUANTITY — a time, a duration, a count, a cost.

    Record citations and the rendered-by footer are stripped first: a footnote is
    provenance for a claim, never the claim, and an answer that is nothing but
    citations is the exact shape this catches.

    NAMED LIMIT (quantities). A quantity is a DIGIT. "Two other jobs were ahead
    of it" states a real one and is not detected, so it fails closed to the
    template — the safe direction for a floor, and cheaper than teaching a
    tripwire to read numerals in words.

    NAMED LIMIT, stated rather than implied. The founder's own specimen PASSES
    this check — "the machine was busy with other work" IS a driver phrase — and
    it is fixed at its assembler (CU3a), not here. That is the honest division:
    this tripwire is a floor under the whole causal class, and a floor cannot
    also be the ceiling. A vacuous answer that reaches for the driver vocabulary
    is a vocabulary problem, and the place to fix a vocabulary problem is the
    vocabulary."""
    if driver_phrases is None:
        from mre.modules.planner_language import DRIVER_PHRASING
        driver_phrases = set(DRIVER_PHRASING.values())
    body = re.sub(r"\n\[rendered by:.*", "", text or "", flags=re.DOTALL)
    body = re.sub(r"\[record:[^\]]*\]", " ", body)
    stripped = body.strip()
    if not stripped:
        return "empty answer"
    low = stripped.lower()
    for phrase in driver_phrases:
        if phrase and phrase.lower() in low:
            return None
    own = {str(s).upper() for s in subjects if s}
    for name in entities:
        if not name or str(name).upper() in own:
            continue
        if str(name).lower() in low:
            return None
    # The subjects come OUT before the quantity scan. Entity refs carry digits
    # ("ORD-000008", "PAINT-02"), so scanning the raw text would let every answer
    # that merely repeats the question's own nouns count as stating a quantity —
    # which is precisely the shape this exists to catch.
    quantities = stripped
    for name in sorted(own, key=len, reverse=True):
        quantities = re.sub(re.escape(name), " ", quantities, flags=re.IGNORECASE)
    if _QUANTITY_RE.search(quantities):
        return None
    return ("names no driver, no entity beyond the question's own subjects, "
            "and no quantity")


# ---------------------------------------------------------------------------
# THE REPEAT RIDERS (Session 4B.5 CU5b/c).
#
# The dispatch counts how many of the last two turns this same route already
# answered and puts the number on the bundle. The renderer does the rest, because
# how an answer READS is the renderer's job — and because doing it here means
# every route gets it, rather than each route learning the rule separately.
#
# The FACTS never vary. Only the lead does, and only when the planner has just
# been given them.
# ---------------------------------------------------------------------------

#: Subject types whose headline IS a count, and the key_facts slot it lives in.
#: On a re-ask these answer with the number and an offer, not the full recitation
#: (CU5c). Add, never repurpose — a new count-shaped route gets an entry here.
COUNT_SUBJECTS: dict[str, str] = {
    "late_orders": "late_count",
    "inventory": "order_count",
    "machine_count": "machine_count",
}


def terse_count_answer(bundle) -> Optional[str]:
    """The TERSE re-ask answer for a count-shaped route, or None when this is not
    one (Session 4B.5 CU5c).

    "How many orders are late" answered "13", then asked again, used to recite
    all thirteen a second time. The planner already has the list; what a re-ask
    wants is the number — and a door back to the detail, so terseness never costs
    them anything."""
    from mre.modules.ask_fallback_copy import (
        REPEAT_COUNT_BARE, REPEAT_COUNT_WITH_LIST,
    )
    kf = bundle.key_facts or {}
    if not kf.get("repeat"):
        return None
    slot = COUNT_SUBJECTS.get(bundle.subject_type or "")
    if slot is None:
        return None
    count = kf.get(slot)
    if not isinstance(count, int):
        return None
    # the offer is only honest when there IS a list behind the number
    listed = any(isinstance(v, list) and v for k, v in kf.items()
                 if k != "excluded_summary")
    return (REPEAT_COUNT_WITH_LIST if listed else REPEAT_COUNT_BARE).format(
        count=count)


def repeat_lead(bundle) -> str:
    """The authored variant lead for a re-fired route, or "" (Session 4B.5 CU5b).

    Indexed by repeat depth, so a third ask does not get the second ask's line
    either. It prefixes the answer; it never replaces a word of it."""
    from mre.modules.ask_fallback_copy import REPEAT_LEADS
    depth = (bundle.key_facts or {}).get("repeat") or 0
    if not isinstance(depth, int) or depth < 1:
        return ""
    return REPEAT_LEADS[min(depth, len(REPEAT_LEADS)) - 1]


def deafness_rider(bundle, text: str) -> Optional[str]:
    """Session 4B.15 Item 4 — THE REVERSAL. Several DIFFERENT questions have
    landed on this one route, so the answer opens by DOUBTING ITSELF and offers
    a narrower way in. It never rebukes the planner, and there is no escalating
    variant: the escalation is what made the original defect sting.

    Returns the new text, or None when this is an ordinary turn."""
    from mre.modules.ask_fallback_copy import DEAF_LEAD, DEAF_OFFER, DEAF_PRIOR
    kf = bundle.key_facts or {}
    if not kf.get("deaf"):
        return None
    lead = [DEAF_LEAD]
    prior = (kf.get("deaf_prior") or "").strip()
    if prior:
        lead.append(DEAF_PRIOR.format(prior=prior))
    head = " ".join(lead)
    marker = "\n[rendered by:"
    if marker in (text or ""):
        body, foot = text.split(marker, 1)
        return f"{head}\n\n{body.rstrip()}\n\n{DEAF_OFFER}\n{marker}{foot}"
    return f"{head}\n\n{(text or '').rstrip()}\n\n{DEAF_OFFER}"


def apply_repeat_riders(bundle, text: str) -> str:
    """The single delivery seam for the repeat riders — called from BOTH
    renderers' ``render``, so the template and the LLM path can never disagree
    about whether the planner just asked this.

    Since 4B.15 there are TWO different signals here and they mean opposite
    things: ``repeat`` is the planner asking the same thing again (terse is
    right), ``deaf`` is different questions collapsing onto one route (self-
    doubt is right). They are mutually exclusive by construction in
    ``interpreter.bundle_repeat``."""
    deaf = deafness_rider(bundle, text)
    if deaf is not None:
        return deaf
    terse = terse_count_answer(bundle)
    if terse is not None:
        footer = ""
        marker = "\n[rendered by:"
        if marker in text:
            footer = text[text.index(marker):]
        return terse + footer
    lead = repeat_lead(bundle)
    if not lead:
        return text
    return f"{lead}\n{text}" if text else lead


#: Session 4B.11 CU1 — the marker that an answer STATES MONEY. Every currency
#: figure the answer surface emits is formatted with a dollar sign (``$1,234.56``
#: / ``+$375.83`` / ``$0``), so its presence in the delivered text is the test for
#: "does the cost proof bear on this answer?". Deterministic and inspectable; no
#: route list to keep in step with the assemblers.
_MONEY_MARK = "$"


def apply_coverage_rider(bundle, text: str) -> Optional[str]:
    """Session 4B.13 Item 1, clause (ii) — the predicate-coverage floor, at the
    ONE delivery seam both renderers share, for the same reason the other two
    riders are here: the template path and the LLM path must not be able to
    disagree about whether the question was actually answered.

    Reads the route stamped by ``Explainer.route``. All the judgment lives in
    ``predicate_coverage``; this is only the attachment point. Returns the new
    text, or None when nothing applies — which is the common case."""
    from mre.modules.predicate_coverage import apply_predicate_rider
    kf = bundle.key_facts if isinstance(bundle.key_facts, dict) else {}
    route = str(kf.get("route_id") or "")
    # The PLANNER'S words first. `bundle.question` is routinely the assembler's
    # canonical phrasing ("Why does ORD-11 start when it does?"), which has
    # already dropped the predicate the planner asked about — checking coverage
    # against it would ask whether the answer covers its own paraphrase.
    question = str(kf.get("asked_question") or getattr(bundle, "question", "") or "")
    if not route or not question:
        return None
    try:
        return apply_predicate_rider(question, route, text)
    except Exception:  # noqa: BLE001 — a guard never breaks an answer
        return None


def apply_sufficiency_rider(bundle, text: str) -> Optional[str]:
    """Session 4B.14 Item 1 — the causal-sufficiency floor, at the ONE delivery
    seam both renderers share. All the arithmetic lives in
    ``causal_sufficiency``; this is only the attachment point."""
    from mre.modules.causal_sufficiency import apply_sufficiency_rider as _apply
    try:
        return _apply(bundle, text)
    except Exception:  # noqa: BLE001 — a guard never breaks an answer
        return None


def apply_unread_guard(bundle, text: str) -> Optional[str]:
    """Errand 4B.15a — the ZERO-TOOL-CALL guard, at the ONE delivery seam both
    renderers share. All the judgment (and there is none of the model kind) lives
    in ``ungrounded_guard``; this is only the attachment point.

    It is the one thing here that REPLACES an answer instead of qualifying it,
    because the defect it catches is not an under-stated qualification — it is an
    answer with nothing behind it at all."""
    from mre.modules.ungrounded_guard import apply_unread_guard as _apply
    try:
        return _apply(bundle, text)
    except Exception:  # noqa: BLE001 — a guard never breaks an answer
        return None


def apply_cost_proof_rider(bundle, text: str) -> Optional[str]:
    """Append the cost-proof qualifier to an answer that states money on a board
    whose cost optimum was NOT proved (Session 4B.11 CU1, docs/07 §5a.23).

    Called from the ONE delivery seam both renderers share, for the same reason
    ``apply_repeat_riders`` is: the template path and the LLM path must not be
    able to disagree about whether this schedule's numbers are proven.

    THE RULE, and it is narrow on purpose:

      * the bundle carries a ``cost_proof`` (every bundle does — ``Explainer.route``
        stamps it), and that proof is UNPROVED — a solve ran and did not close
        the bound. A PROVED board adds nothing: the strip already says so and a
        rider on every answer is noise.
      * the delivered text states money. "This schedule costs X" on an
        11.47%-gap board is the true-but-miscredited species 4B.10 measured;
        "ORD-14 is on M-02" is not a cost claim and gets no rider.

    Returns the new text, or None when nothing applies (the caller keeps its own).
    """
    from mre.modules.cost_proof import CostProof
    proof = (bundle.key_facts or {}).get("cost_proof")
    if isinstance(proof, dict):
        proof = CostProof(**{k: proof.get(k) for k in
                             ("status", "gap", "objective", "tiebreak_status",
                              "tiebreak_skipped_reason")})
    if not isinstance(proof, CostProof):
        return None
    rider = proof.rider()
    if not rider or _MONEY_MARK not in (text or ""):
        return None
    # Above the delivery footer, so the qualifier reads as part of the answer
    # rather than as metadata about it.
    marker = "\n[rendered by:"
    if marker in text:
        head, foot = text.split(marker, 1)
        return f"{head.rstrip()}\n\n{rider}\n{marker}{foot}"
    return f"{text.rstrip()}\n\n{rider}"


def _dur_min(minutes) -> str:
    """A duration in the register a planner reads — "7h11m", "1d 1h", "45m".
    Mirrors the cockpit job card's ``fmtDur`` so a figure reads the same whether
    it arrives in an answer or on a hover (Session 4B.14 Item 4)."""
    if minutes is None:
        return "?"
    m = int(round(float(minutes)))
    if m < 60:
        return f"{m}m"
    h, r = divmod(m, 60)
    # Deliberately no days: these are WORKING minutes, and "1d 1h" of work
    # invites the reader to ask a day of what — calendar or shift. Hours stay
    # unambiguous however many of them there are.
    return f"{h}h" if r == 0 else f"{h}h{r:02d}m"


def _span_min(minutes) -> str:
    """An ELAPSED amount — lateness, a delay, how far past a due date something
    lands. Days past 48h, because "475h late" is a number nobody can picture.

    THE COMPANION OF ``_dur_min``, AND THE DISTINCTION IS 4B.20's RULING: working
    time and elapsed span are different quantities and are never interchangeable.
    ``_dur_min`` deliberately refuses days because a day of WORK invites the
    question "a day of what — calendar or shift"; here a day is wall-clock and
    unambiguous. One definition, reused from the counterfactual rather than
    written twice, so the two routes cannot drift apart on the same figure."""
    if minutes is None:
        return "?"
    from mre.modules.counterfactual import _span
    return _span(minutes)


def _machine_load_lines(load: Any) -> list[str]:
    """The load clause for a single-machine listing (Session 4B.22 Item B1).

    Returns [] when there is no load to state — an absent figure prints nothing
    rather than a zero. Two shapes, and the split is the point: WITH a readable
    calendar the percentage and its denominator are both on the surface; WITHOUT
    one the working time is still stated and the percentage is REFUSED, because a
    ratio whose denominator we could not read is not a smaller claim, it is an
    unfounded one.

    The judgment clause rides on both: "overloaded" needs a declared threshold
    this plant does not have (the same shape as R-PD1 clause (5)'s age threshold
    and the undeclared coarse derate), so the figure is stated and not judged.
    """
    if not isinstance(load, dict) or load.get("working_minutes") is None:
        return []
    from mre.modules.ask_fallback_copy import (
        MACHINE_LOAD_LINE, MACHINE_LOAD_NO_CALENDAR, MACHINE_LOAD_NO_JUDGMENT,
    )
    working = f"{load['working_minutes']:,.0f}"
    first, last = load.get("first_start") or "?", load.get("last_end") or "?"
    oc, pct = load.get("open_capacity_minutes"), load.get("utilization_pct")
    if oc is None or pct is None:
        return [MACHINE_LOAD_NO_CALENDAR.format(
            working=working, spans=load.get("spans", "?"),
            first=first, last=last), MACHINE_LOAD_NO_JUDGMENT]
    return [MACHINE_LOAD_LINE.format(working=working, open=f"{oc:,.0f}",
                                     first=first, last=last, pct=f"{pct:g}"),
            MACHINE_LOAD_NO_JUDGMENT]


def _family_gist(why: str) -> str:
    """The short name of an uncomputed docs/05 family, from its own recorded
    reason (Session 4B.14). The full sentence lives in ``blocker_analysis`` and
    is the authority; this is the clause a planner reads in a one-line list."""
    return (why or "").split(" — ")[0].split(" - ")[0].strip() or "not computed"


def causal_material(bundle) -> tuple[set, set]:
    """``(subjects, entities)`` for :func:`causal_vacuity`, read off a bundle.

    ``subjects`` are the nouns the QUESTION already carried — naming them back is
    not an answer. ``entities`` are the external names the bundle's own evidence
    records could legitimately let an answer name."""
    kf = bundle.key_facts or {}
    subjects = {bundle.subject_external_name}
    for slot in ("machine_ref", "machine", "order", "order_a", "order_b"):
        if kf.get(slot):
            subjects.add(kf[slot])
    entities: set = set()
    for rec in bundle.ordered_records or []:
        for s in rec.get("subjects", []) or []:
            name = _resolve_name(s.get("entity_id", ""), s.get("entity_type", ""),
                                 bundle.identity_map)
            if name and name != s.get("entity_id"):
                entities.add(name)
    return {s for s in subjects if s}, entities


def _signed_money(v) -> str:
    """"+$1,234.56" / "−$375.83" / "$0" — the delta card's own money format, in
    Python (Session 4B.5 CU2). The card answer and the card must read the same;
    the JS side is ``sandboxui.signedMoney`` and the two are pinned to each other
    by ``test_open_card``. Below half a cent is "$0": a sign on a rounding
    residue is noise dressed as information."""
    if v is None:
        return ""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if abs(v) < 0.005:
        return "$0"
    return f"{'+' if v > 0 else '−'}${abs(v):,.2f}"


def _portfolio_clause(kf: dict) -> list[str]:
    """R-BK1's portfolio, in planner language (Session 4B.27 Item 10).

    Three shapes, and none of them silent:

    * NO BLOCK — K=1, absent by construction (clause 2). The honest fact is that
      this board is ONE seeded search, and 4B.25 measured why that matters: on
      this very plant two of five seeds returned an EMPTY BOARD at the shipped
      budget. A single draw is not a portfolio of one and is not described as
      agreement.
    * A SPREAD — several members published and they disagree. The number is
      stated and so is what it means: far from settled. This is the sentence
      4B.25 wrote to stop a planner reading the winner as the answer.
    * NO SPREAD — fewer than two publishable members, so `spread_*` is None and
      never 0.00 (clause 4, 4B.21's tri-state). Saying "they agreed" here would
      claim an agreement nobody observed.

    The declaration/agreement/unpublished sentences are the assembler's own,
    composed server-side; they are quoted, not re-worded, so the certificate and
    the answer cannot state one fact two ways.
    """
    out: list[str] = []
    if not kf.get("portfolio_present"):
        out.append("")
        if kf.get("proved"):
            # A CLOSED BOUND OUTRANKS THE SEED, and saying otherwise here would
            # be this session's own defect class: caught on the pinned world,
            # where the first version of this sentence told a planner that
            # another seed "can land somewhere quite different" about a board
            # whose cost is PROVED OPTIMAL. Nothing can be cheaper than proved,
            # so the single-draw caveat is simply false there. What is still
            # true — and worth saying — is that OTHER equally-cheap schedules
            # may exist, which is a claim about shape, not about price.
            out.append(
                "And on \"found\": this board came from one seeded search, but "
                "that doesn't limit the answer here — the bound is closed, so "
                "no other seed could have found anything cheaper. A different "
                "search might well have found a differently-SHAPED schedule at "
                "the same cost.")
        else:
            out.append(
                "And on \"found\": this board came from ONE seeded search, so "
                "there are no others to compare it with. A different seed can "
                "land somewhere quite different on a board this size — that is "
                "measured, not hypothetical — so treat this as one draw rather "
                "than the best of several.")
        return out

    k = kf.get("portfolio_k")
    published = kf.get("portfolio_published") or 0
    winner = kf.get("portfolio_winner_seed")
    spread_abs, spread_pct = (kf.get("portfolio_spread_abs"),
                              kf.get("portfolio_spread_pct"))
    out.append("")
    lead = (f"On \"found\": this board is the best of {int(k)} seeded searches"
            if k else "On \"found\": this board is the best of several seeded "
                      "searches")
    if winner is not None:
        lead += f", the one at seed {winner}"
    out.append(lead + ".")

    members = kf.get("portfolio_members") or []
    shown = [m for m in members if m.get("ledger_total") is not None]
    if shown:
        rows = ", ".join(
            f"seed {m['seed']} ${float(m['ledger_total']):,.2f}" for m in shown)
        out.append(f"What each reached: {rows}.")
    missing = [m for m in members if m.get("ledger_total") is None]
    if missing:
        # Clause (4): an unpublishable member is NAMED, never dropped — dropping
        # it makes the spread look tighter than the evidence supports.
        out.append(
            f"{len(missing)} of them published no board at all "
            f"({', '.join('seed ' + str(m['seed']) for m in missing)}), so they "
            f"are not in that comparison.")

    if spread_pct is not None and spread_abs is not None:
        out.append(
            # The certificate's own words for this ("far from settled") — one
            # phrase for one fact, so the board and the answer agree.
            f"They land ${float(spread_abs):,.2f} apart — "
            f"{float(spread_pct):.2f}% — which is far from settled: the seed "
            f"decides more here than the budget does, so read this total as a "
            f"good one we found, not as the answer.")
    elif published < 2:
        out.append(
            "Only one of them produced a board, so there is no spread to quote "
            "— I won't call that agreement.")
    return out


def _affected_effect(a: dict) -> str:
    """One affected order's effect, in the card's own vocabulary: its per-Demand
    tardiness dollars and/or its lateness minutes. Never a PRODUCTION figure —
    the ledger does not roll production dollars per order (a named debt), and the
    card's own column header says the same thing."""
    bits = []
    t = a.get("tardiness_delta")
    if t is not None and abs(float(t)) >= 0.005:
        bits.append(f"{_signed_money(t)} tardiness")
    lm = a.get("lateness_delta_min")
    if lm:
        # Session 4B.27 Item 2: this is the order's own SIGNED FINISH SHIFT, not
        # the clamped plan tardiness the card's total line reports. Naming it
        # here is what lets the two figures sit beside each other honestly.
        lm = int(lm)
        bits.append(f"finishes {abs(lm)} min "
                    f"{'later' if lm > 0 else 'earlier'}")
    return " · ".join(bits) if bits else "finish unchanged"


class TemplateRenderer:
    """Deterministic text renderer.  No external calls."""

    def render(self, bundle: ExplanationBundle) -> str:
        # CU3 — the single delivery seam: strip markdown/backticks from every
        # register's output here, so no register can leak formatting.
        text = apply_repeat_riders(bundle, strip_formatting(
            self._render_body(bundle) + "\n" + _rendered_by(bundle, "template")))
        # 4B.11 CU1 — an unproved board's money claims carry their gap, here,
        # once, for every route (docs/07 §5a.23).
        text = apply_cost_proof_rider(bundle, text) or text
        # 4B.14 Item 1 — a cited cause that does not account for the quantity it
        # explains says so, before anything else can read it as the whole cause.
        text = apply_sufficiency_rider(bundle, text) or text
        # 4B.13 Item 1(ii) — and a predicate the answer never addressed is
        # admitted rather than left for the planner to notice.
        text = apply_coverage_rider(bundle, text) or text
        # Errand 4B.15a — LAST, and the only one here that WITHHOLDS rather than
        # qualifies: a synthesis answer that read nothing and still names this
        # plant's entities does not ship at all.
        return apply_unread_guard(bundle, text) or text

    def _render_body(self, bundle: ExplanationBundle) -> str:
        # R-AI2(d) (Session 4A.2d) — the transcript convention dies: no "=== q ==="
        # header echoing the question back at the planner. The answer opens with
        # the answer. (The [rendered by: … | register: …] footer is delivery
        # metadata — the cockpit surfaces the register as a chip; hiding the
        # literal footer line in the cockpit view is a named 4A.3 follow-up.)
        lines: list[str] = []

        self._render_header(lines, bundle)

        if bundle.subject_type in ("remediation", "triage"):
            # Register bodies are assembled by their own modules from the
            # certificate findings on the bundle (authored catalog text /
            # grade-distance arithmetic), never from the testimony templater.
            return "\n".join(lines) + self._render_register_body(bundle)

        # The edit domain (CU2) renders its whole answer in the header (the
        # planner narrative over planner_edit Decisions); the Decisions ARE the
        # citations, already summarized, so no separate raw evidence chain.
        if bundle.subject_type in ("edits", "edit_cost"):
            return "\n".join(lines)

        # Session 4A.2 — these subject types compose their whole answer in the
        # header in planner language (CU2/CU4/CU5/CU7). They never dump the raw
        # M1<M7 evidence chain, whose module ids and uuids are exactly the jargon
        # the audit flagged (CU6).
        if bundle.subject_type in _HEADER_ONLY_SUBJECTS:
            return "\n".join(lines).rstrip()

        if not bundle.ordered_records:
            if bundle.subject_type == "diff":
                self._render_diff(lines, bundle.key_facts)
            elif bundle.subject_type in (
                "downtime", "unsupported", "schedule", "scenario_diff",
                "near_miss", "clarify", "refusals",
                "advice", "solve_time", "machine_count", "maintenance", "coaching",
                # Item 2: the optimality answer IS the solver's own report; it
                # cites the M6 solve_complete event rather than a record list.
                "optimality",
                # Item 1: a premise correction renders the order's REAL
                # placements inline — that IS its evidence, and appending
                # "(no evidence records found)" under it would read as a failure
                # to check rather than as the check that just fired.
                "premise_correction",
                # Session 4A.5a CU2 — the confirmation-of-take bridge.
                "confirm_take",
                # Session 4B.13 Item 3 (errand C3). A late_orders bundle reaches
                # here ONLY when no order carries a lateness metric — i.e. when
                # nothing is late, which the sentence above has just said. The
                # old "(no evidence records found)" read to a stranger as the
                # system failing rather than as a clean bill of health. With one
                # or more late orders the bundle carries their metrics and this
                # branch is never taken, so no citation is ever suppressed.
                "late_orders",
                # Session 4B.15 Item 3: an attribute lookup CITES ITS SOURCE IN
                # THE SENTENCE — the submission column and the provenance class
                # are the answer, not a footnote — so an evidence-chain stub
                # under it would read as a failure to check.
                "attribute_lookup",
            ):
                pass  # header already rendered all content
            elif "error" in bundle.key_facts:
                lines.append(f"  Error: {bundle.key_facts['error']}")
            else:
                lines.append("  (no evidence records found)")
            return "\n".join(lines)

        # Citation-breadth cap (CU6): a schedule-wide subject cited dozens of
        # records — a wall of footnotes, never 13 highlighted bars. Show the
        # first CITATION_CAP and name how many more, rather than dump everything.
        records = bundle.ordered_records
        capped = len(records) > CITATION_CAP
        shown = records[:CITATION_CAP] if capped else records
        lines.append(f"Evidence chain ({len(records)} record(s)):")
        lines.append("")
        # Session 4B.21 Item 3(b) — when the LEAD replaced the recorded driver
        # with a computed reading, the chain must not re-assert the bare driver
        # underneath it as a competing reason. The flag says so once, on the
        # record it applies to.
        superseded = (bundle.key_facts.get("driver_code") == "CAPACITY_BLOCKED"
                      and bundle.key_facts.get("blocked_alternatives") is not None)
        for i, rec in enumerate(shown, 1):
            self._render_record(lines, i, rec, bundle.identity_map,
                                driver_superseded=superseded)
        if capped:
            lines.append(f"  … and {len(records) - CITATION_CAP} more record(s) "
                         "(ask about a specific order to narrow this).")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_header(self, lines: list[str], bundle: ExplanationBundle) -> None:
        if bundle.subject_type == "demand":
            kf = bundle.key_facts
            # why-on-machine (Session 4A.2d): lead with a sentence naming the order,
            # the machine, and the cause; the assignment decision supplements below.
            if kf.get("machine_ref"):
                name = bundle.subject_external_name
                cause = kf.get("cause")
                # Session 4B.5 CU3(a) — a CAPACITY_BLOCKED placement gets its
                # CONCRETE story or an explicit admission that the occupancy does
                # not carry one. "the machine was busy with other work" alone is
                # unfalsifiable, and on a why-on-MACHINE question it points at a
                # machine the order is not even on.
                alts = kf.get("blocked_alternatives")
                if kf.get("driver_code") == "CAPACITY_BLOCKED" and alts is not None:
                    from mre.modules.ask_fallback_copy import (
                        WHY_MACHINE_CAPABILITY_LEAD,
                        WHY_MACHINE_CAPACITY_LEAD, WHY_MACHINE_CAPACITY_ONLY_OPTION,
                        WHY_MACHINE_CAPACITY_ROW, WHY_MACHINE_CAPACITY_UNATTRIBUTED,
                    )
                    # Item 1: with NO eligible alternative the capacity lead is
                    # false — it asserts occupied alternatives that do not
                    # exist. That case is a capability fact and gets its own
                    # lead, said once, instead of a contradiction said twice.
                    if not alts and kf.get("only_option"):
                        lines.append(WHY_MACHINE_CAPABILITY_LEAD.format(
                            order=name, machine=kf["machine_ref"]))
                        self._render_why_machine_scope(lines, kf)
                        lines.append("")
                        return
                    lines.append(WHY_MACHINE_CAPACITY_LEAD.format(
                        order=name, machine=kf["machine_ref"]))
                    if alts:
                        for a in alts:
                            lines.append(WHY_MACHINE_CAPACITY_ROW.format(
                                machine=a["machine"], blocker=a["blocker_order"],
                                until=a["until"]))
                    else:
                        lines.append(WHY_MACHINE_CAPACITY_UNATTRIBUTED)
                    self._render_why_machine_scope(lines, kf)
                    lines.append("")
                    return
                because = f" because {cause}" if cause else ""
                lines.append(f"{name} is on {kf['machine_ref']}{because}.")
                self._render_why_machine_scope(lines, kf)
                lines.append("")
                return
            lateness = kf.get("lateness_minutes")
            due = kf.get("due_date", "unknown")
            name = bundle.subject_external_name
            if lateness is not None and float(lateness) > 0:
                hrs = kf.get("lateness_hours")
                span = f"{int(lateness)} minutes" + (f" ({hrs}h)" if hrs else "")
                lines.append(f"{name} finished {span} past its due date ({due}).")
                # CU4 — the causal story, not the bare driver code.
                blk = kf.get("blocked_by")
                if blk:
                    prio = f", {blk['blocker_priority']}" if blk.get("blocker_priority") else ""
                    lines.append(
                        f"It couldn't start until {blk['my_start']} because "
                        f"{blk['machine']} was held by {blk['blocker_order']}"
                        f"{prio} until {blk['until']}.")
                elif kf.get("driver_phrase"):
                    lines.append(f"The binding cause: {kf['driver_phrase']}.")
                # R-AI2(c) — a labeled judgment, offered (never blended into the
                # testimony above), only where the evidence grounds the tradeoff.
                if kf.get("take"):
                    lines.append("")
                    lines.append(f"My take: {kf['take']}")
                # CU2 (R-AI3(3)) — the register ladder's final rung: an invitation
                # to the obvious next question. Only when a blocking machine is
                # named (a concrete follow-up exists), at most one.
                if blk and blk.get("machine"):
                    from mre.modules.ask_fallback_copy import INVITE_WHY_LATE
                    lines.append("")
                    lines.append(INVITE_WHY_LATE.format(machine=blk["machine"]))
            elif lateness is not None:
                early = abs(int(lateness))
                span = (f"{round(early / 1440, 1)} days" if early >= 1440
                        else f"{round(early / 60, 1)}h" if early >= 60
                        else f"{early} minutes")
                # Session 4B.27 Item 5 — NAME THE BAND THE PLANNER IS POINTING
                # AT. A bar inside one working day of its due date is drawn
                # TIGHT, and "on time, finished 5h early" is a true sentence
                # that does not answer "why is this one tight". The band comes
                # from the board's own threshold (`_lateness_band_facts`), so
                # the word here and the colour on screen are one number.
                if kf.get("board_band") == "tight":
                    lines.append(
                        f"{name} is drawn TIGHT rather than late: it finishes "
                        f"{span} before its due date ({due}), and anything "
                        f"landing within a working day of its due date gets "
                        f"that band. It is not late — it has {span} of room and "
                        f"no more.")
                else:
                    lines.append(
                        f"No — {name} is on time. It finished {span} early "
                        f"(due {due}).")
            lines.append("")

        elif bundle.subject_type == "run":
            kf = bundle.key_facts
            lines.append(f"Run: {bundle.subject_external_name}")
            lines.append(
                f"  Notable decisions : {kf.get('notable_decision_count', '?')}"
            )
            lines.append(
                f"  Schedule findings : {kf.get('affecting_finding_count', '?')}"
            )
            lines.append(
                f"  Late demands      : {kf.get('late_demand_count', '?')}"
            )
            lines.append("")

        elif bundle.subject_type == "late_orders":
            kf = bundle.key_facts
            count = kf.get("late_count", 0)
            orders = kf.get("late_orders", [])
            # Session 4B.13 Item 3 — WHICH ORDERS THE CLAIM IS ABOUT. On a
            # rolling board "no late orders" is true of the SCHEDULED ones; the
            # tray has no service outcome at all and is neither late nor on
            # time. Absent (None) on a monolithic board, where the claim really
            # does cover the whole plan.
            sched_n = kf.get("scheduled_order_count")
            tray_n = kf.get("not_scheduled_order_count")
            scope = ""
            if sched_n is not None and tray_n:
                # Session 4B.21 — "known to this plan", not "on this plan".
                # 4B.13 named the two SUBSETS and left their TOTAL bare, which
                # the cross-surface guard caught on its first run: the one
                # figure in this sentence that matches `inventory`'s headline
                # count was the one with no disposition on it.
                scope = (f" Of the {sched_n + tray_n} orders known to this plan, "
                         f"that covers the {sched_n} scheduled in this window — "
                         f"the other {tray_n} sit beyond the horizon with no "
                         f"placement yet, so they are neither late nor on time.")
            if count == 0:
                lines.append(
                    "No late orders found in this schedule." + scope)
            else:
                lines.append(f"{count} late order(s):" + scope)
                for item in orders:
                    lines.append(f"  - {item}")
                # R-PD1 clause (4)/(6), Session 4B.11 CU4(b) — the two totals,
                # stated separately. A planner reading "285,143 minutes late"
                # would take all of it as this schedule's doing; on the specimen
                # 96.4% of it was on the clock before the window opened. The
                # split is spoken BEFORE any invitation to drill in, because it
                # changes what the drill-down is about.
                pd_n = kf.get("past_due_at_intake_count") or 0
                if pd_n:
                    floor = int(kf.get("tardiness_floor_minutes") or 0)
                    ctrl = int(kf.get("tardiness_controllable_minutes") or 0)
                    lines.append("")
                    lines.append(
                        f"{pd_n} of those {'was' if pd_n == 1 else 'were'} "
                        f"ALREADY PAST DUE before this window opened — that is the "
                        f"plant's position, not a data problem, and the work is "
                        f"scheduled. Of the total lateness, {floor} minute(s) were "
                        f"unavoidable at the start and {ctrl} minute(s) are what "
                        f"this schedule adds.")
            self._render_excluded_note(lines, bundle)
            if count and kf.get("worst_late_order"):
                from mre.modules.ask_fallback_copy import INVITE_LATE_ORDERS
                lines.append("")
                lines.append(INVITE_LATE_ORDERS.format(order=kf["worst_late_order"]))
            lines.append("")

        elif bundle.subject_type == "downtime":
            kf = bundle.key_facts
            subject = kf.get("subject", "?")
            closures = kf.get("closures", [])
            total = kf.get("total_hours", 0.0)
            if not closures:
                # CU4 (Session 4A.3-pre) — correct grammar: no closures are
                # DECLARED for the resource(s), not "found for all resources".
                if subject == "all resources":
                    lines.append("No downtime is declared for any resource.")
                else:
                    lines.append(f"No downtime is declared for {subject}.")
            else:
                lines.append(f"Downtime for {subject}:")
                for c in closures:
                    lines.append(
                        f"  {c['resource']}: {c['duration_hours']}h"
                        f" — {c['reason']} on {c['date']}"
                    )
                res_count = kf.get("resource_count", len({c["resource"] for c in closures}))
                lines.append(f"  Total: {total}h across {res_count} resource(s)")
            lines.append("")

        elif bundle.subject_type == "edits":
            kf = bundle.key_facts
            edits = kf.get("edits", [])
            n = kf.get("edit_count", len(edits))
            if not n:
                lines.append("No edits have been accepted on this version yet.")
            else:
                total = kf.get("total_cost_delta", 0.0)
                sign = "+" if total >= 0 else "−"
                lines.append(f"You accepted {n} edit(s) on this version "
                             f"({sign}${abs(total):,.0f} total):")
                lines.append("")
                for e in edits:
                    cd = e.get("cost_delta", {})
                    td = cd.get("total_delta")
                    dstr = (f"{'+' if (td or 0) >= 0 else '−'}${abs(td):,.0f}"
                            if td is not None else "cost unknown")
                    lines.append(f"  - pinned op {e.get('op_ref8', '?')} to "
                                 f"{e.get('machine', '?')} · {dstr}"
                                 f" · moved {e.get('moved_count', 0)} op(s)"
                                 f" · by {e.get('authority', '?')}")
            lines.append("")

        elif bundle.subject_type == "edit_cost":
            kf = bundle.key_facts
            cd = kf.get("cost_delta", {})
            total = cd.get("total_delta")
            if total is None:
                lines.append("This edit's cost delta was not recorded.")
            else:
                sign = "+" if total >= 0 else "−"
                lines.append(f"This edit costs {sign}${abs(total):,.0f}, decomposed:")
                lines.append(f"  production  {_signed(cd.get('production_delta'))}")
                lines.append(f"  setup       {_signed(cd.get('setup_delta'))}")
                lines.append(f"  tardiness   {_signed(cd.get('tardiness_delta'))}")
                # per-consequence reasons (3.3 CU3), where the edit annotated them
                reasoned = [m for m in kf.get("moves", []) if m.get("reason")]
                if reasoned:
                    lines.append("")
                    lines.append("Why the surroundings moved:")
                    for m in reasoned[:5]:
                        r = m.get("reason", {})
                        if r.get("kind") == "displaced_by_drop":
                            why = "displaced by the dropped op"
                        else:
                            why = f"blocked on a busy machine until {(r.get('until') or '')[:16]}"
                        lines.append(f"  - op {m.get('operation_ref', '')[:8]} "
                                     f"(+{m.get('start_delta_min', 0)}min): {why}")
                    # Session 4B.19 Item 3(b): the head slice above is fine; the
                    # SILENCE about it was not. A planner reading five rows under
                    # "Why the surroundings moved" reads them as the surroundings.
                    if len(reasoned) > 5:
                        lines.append(f"  …and {len(reasoned) - 5} more operation(s) "
                                     f"moved for a recorded reason "
                                     f"({len(reasoned)} in all).")
            lines.append("")

        elif bundle.subject_type == "unsupported":
            from mre.modules.ask_fallback_copy import (
                safe_parsed, UNSUPPORTED_LEAD_NO_ECHO,
            )
            kf = bundle.key_facts
            echo = safe_parsed(kf.get("parsed", ""))
            lines.append(f"I can't answer this question yet: \"{echo}\"" if echo
                         else UNSUPPORTED_LEAD_NO_ECHO)
            lines.append("")
            lines.append("Supported question types:")
            for route in kf.get("supported_routes", []):
                lines.append(f"  - {route}")
            lines.append("")

        elif bundle.subject_type == "near_miss":
            # The tiered-fallback bridge (CU4): honest miss + the two nearest
            # routes as concrete follow-ups. All copy is authored (never LLM).
            from mre.modules.ask_fallback_copy import (
                NEAR_MISS_LEAD, NEAR_MISS_LEAD_NO_ECHO, NEAR_MISS_OFFER, safe_parsed,
            )
            kf = bundle.key_facts
            echo = safe_parsed(kf.get("parsed", ""))
            lines.append(NEAR_MISS_LEAD.format(q=echo) if echo
                         else NEAR_MISS_LEAD_NO_ECHO)
            lines.append("")
            lines.append(NEAR_MISS_OFFER)
            for offer in kf.get("offers", []):
                lines.append(f"  - {offer}")
            lines.append("")

        elif bundle.subject_type == "clarify":
            # Unresolvable ellipsis (CU2): ask for the missing referent, never
            # guess. The reason is authored fallback copy carried on the bundle.
            from mre.modules.ask_fallback_copy import (
                CLARIFY_LEAD, CLARIFY_LEAD_NO_ECHO, safe_parsed,
            )
            kf = bundle.key_facts
            echo = safe_parsed(kf.get("parsed", ""))
            lines.append(CLARIFY_LEAD.format(q=echo) if echo
                         else CLARIFY_LEAD_NO_ECHO)
            reason = kf.get("reason")
            if reason:
                lines.append(reason)
            lines.append("")

        elif bundle.subject_type == "synthesis":
            self._render_synthesis(lines, bundle)

        elif bundle.subject_type == "prove_it":
            self._render_prove_it(lines, bundle)

        elif bundle.subject_type == "refusals":
            # The meta-route (R-AI1(d)): the ledger answering about itself.
            from mre.modules.ask_fallback_copy import (
                REFUSAL_META_EMPTY, REFUSAL_META_LEAD,
            )
            kf = bundle.key_facts
            refusals = kf.get("refusals", [])
            if not refusals:
                lines.append(REFUSAL_META_EMPTY)
            else:
                lines.append(REFUSAL_META_LEAD.format(n=len(refusals)))
                for r in refusals:
                    q = r.get("verbatim_question", "?")
                    kind = r.get("route", "REFUSED")
                    lines.append(f"  - \"{q}\"  [{kind}]")
            lines.append("")

        elif bundle.subject_type == "schedule":
            kf = bundle.key_facts
            rows = kf.get("rows", [])
            label = kf.get("filter_label", "all")
            direct = kf.get("direct_answer")
            # CU3 — a direct timing question leads with the completion; the table
            # below only supplements it (R-AI2(a): a table never replaces a
            # sentence).
            if direct and direct.get("finish"):
                dd = direct.get("delta_days")
                if dd is None:
                    span = ""
                else:
                    mag = abs(dd)
                    span = (f" — {mag:g} day(s) {'late' if direct['late'] else 'early'}"
                            if mag >= 0.05 else " — right on its due date")
                due = f" (due {direct['due']})" if direct.get("due") else ""
                lines.append(
                    f"{direct['order']} completes {direct['finish']}{span}{due}.")
                if direct.get("begin"):
                    lines.append(f"It starts {direct['begin']}.")
                lines.append("")
            if not rows:
                lines.append(kf.get("empty_message")
                             or "I don't see any scheduled operations matching that.")
            else:
                # A conversational lead, then the table as supplement. Full listing
                # vs a single row-scope read differently.
                m = kf.get("machine_count", len({r["machine"] for r in rows}))
                if direct:
                    lead = (f"{label} runs across {len(rows)} operation(s):"
                            if len(rows) > 1 else "Its schedule:")
                elif label == "all":
                    lead = (f"The full schedule — {len(rows)} operation(s) across "
                            f"{m} machine(s), machine by machine:")
                else:
                    lead = (f"{label}: {len(rows)} operation(s)"
                            + (f" across {m} machine(s)" if m > 1 else "") + ":")
                lines.append(lead)
                # Session 4B.22 Item B1 — THE LOAD, BEFORE THE LISTING. "is CUT-01
                # overloaded" asks for a judgment and got eighteen rows; the
                # figure now leads, names its denominator (4B.20), and DECLINES
                # THE JUDGMENT rather than inventing a threshold.
                for ln in _machine_load_lines(kf.get("machine_load")):
                    lines.append("")
                    lines.append(ln)
                lines.append("")
                # CU6a (Session 4B.4): an order-schedule repeats the SAME order-
                # completion lateness on every segment ("-13536min early" ×N) — the
                # header already states it once. Show per-row lateness only when the
                # rows actually DIFFER (a full listing across orders); suppress it
                # when every row carries the same value (one order's segments).
                _lat_values = {row.get("lateness_minutes") for row in rows}
                _show_row_lat = len(rows) == 1 or len(_lat_values) > 1
                cur_machine = None
                for row in rows:
                    if row["machine"] != cur_machine:
                        cur_machine = row["machine"]
                        lines.append(f"  [{cur_machine}]")
                    lateness = row.get("lateness_minutes")
                    lat_str = ""
                    if lateness is not None and _show_row_lat:
                        # Session 4B.21 Item 5(b) — THE SAME FORMATTER AS EVERY
                        # OTHER SURFACE. This printed "-13817min early": a
                        # NEGATIVE number and the word "early" together, each
                        # encoding the same direction, at 1,440 of the unit to
                        # the day. The opener has said "8h22m of slack" since
                        # 4B.16 and the job card "97h 1m" since 4B.14, off a
                        # formatter this listing did not use. The magnitude is
                        # passed unsigned because the word does the direction.
                        lat_str = (
                            f"  {elapsed_minutes(abs(lateness))} LATE"
                            if lateness > 0
                            else f"  {elapsed_minutes(abs(lateness))} early"
                        )
                    lines.append(
                        f"    seq={row['op_seq']:>3}  "
                        f"{row['start']} -> {row['end']}  "
                        f"{row['work_orders']}{lat_str}"
                    )
            lines.append("")

        elif bundle.subject_type == "scenario_diff":
            kf = bundle.key_facts
            lines.append(f"Scenario: {kf.get('description', '?')}")
            lines.append("")
            service_deltas = kf.get("service_deltas", [])
            if service_deltas:
                lines.append("Service changes:")
                for d in service_deltas:
                    wo = d["work_order"]
                    lb = d["lateness_before"]
                    la = d["lateness_after"]
                    delta = d.get("lateness_delta")
                    lb_str = f"{int(lb):+d} min" if lb is not None else "N/A"
                    la_str = f"{int(la):+d} min" if la is not None else "N/A"
                    delta_str = f"  [d{int(delta):+d} min]" if delta is not None else ""
                    lines.append(f"  {wo}: {lb_str} -> {la_str}{delta_str}")
                lines.append("")
            cd = kf.get("cost_delta", {})
            if cd:
                lines.append(
                    f"Cost: {cd.get('total_before', 0):.2f}"
                    f" -> {cd.get('total_after', 0):.2f}"
                    f"  (d {cd.get('total_delta', 0):+.2f})"
                )
                lines.append(f"  production d: {cd.get('production_delta', 0):+.2f}")
                lines.append(f"  setup       d: {cd.get('setup_delta', 0):+.2f}")
                lines.append(f"  tardiness   d: {cd.get('tardiness_delta', 0):+.2f}")
                lines.append("")
            am = kf.get("assignment_moves", {})
            if am.get("total_changed", 0) > 0:
                lines.append(f"Assignment moves: {am['total_changed']}")
                for move in am.get("notable", []):
                    lines.append(f"  {move}")
                lines.append("")

        elif bundle.subject_type == "findings":
            self._render_findings(lines, bundle)

        elif bundle.subject_type == "order_attributes":
            kf = bundle.key_facts
            lines.append(f"{kf.get('order', '?')}:")
            lines.append(f"  Product   : {kf.get('product', '?')}")
            qty = kf.get("quantity")
            if qty is not None:
                lines.append(f"  Quantity  : {int(qty) if float(qty).is_integer() else qty}"
                             f" {kf.get('quantity_uom', '')}".rstrip())
            if kf.get("customer"):
                lines.append(f"  Customer  : {kf.get('customer')}")
            else:
                # CU6b (Session 4B.4) — coach the IDS requirement (jurisdiction
                # rule), never fault the ERP: a customer only appears when the
                # submission declares one via the customers doorway.
                lines.append("  Customer  : not specified — declare customers in "
                             "the submission's customers file to see one here")
            lines.append(f"  Due       : {kf.get('due') or 'unknown'}")
            if kf.get("release"):
                lines.append(f"  Released  : {kf.get('release')}")
            lines.append(f"  Priority  : {kf.get('priority', 'standard priority')}")
            lines.append("")

        elif bundle.subject_type == "inventory":
            self._render_inventory(lines, bundle)

        elif bundle.subject_type == "integrity":
            kf = bundle.key_facts
            overlaps = kf.get("overlaps", [])
            scope = kf.get("checked_machine") or "any machine"
            if not overlaps:
                lines.append(
                    f"No double-booking on {scope}: no two operations are "
                    f"scheduled on the same machine at the same time "
                    f"({kf.get('op_count', 0)} operation(s) checked). The "
                    "schedule is conflict-free by construction — the solver "
                    "enforces one job per machine at a time.")
            else:
                lines.append(f"Found {len(overlaps)} overlap(s):")
                for o in overlaps:
                    lines.append(f"  {o['a']} and {o['b']} both on {o['machine']} "
                                 f"— {o['a']} runs to {o['a_end']}, "
                                 f"{o['b']} starts {o['b_start']}")
            lines.append("")

        elif bundle.subject_type == "start_reason":
            self._render_start_reason(lines, bundle)

        elif bundle.subject_type == "why_here":
            self._render_why_here(lines, bundle)
        elif bundle.subject_type == "counterfactual":
            self._render_counterfactual(lines, bundle)
        elif bundle.subject_type == "later_move":
            self._render_later_move(lines, bundle)

        elif bundle.subject_type == "unknown_entity":
            self._render_unknown_entity(lines, bundle)

        elif bundle.subject_type == "drill_down":
            kf = bundle.key_facts
            detail = kf.get("detail")
            if not detail:
                lines.append("There's nothing more to show — no finding or record "
                             "matched.")
            else:
                self._render_finding_detail(lines, detail)
            lines.append("")

        elif bundle.subject_type == "briefing":
            self._render_briefing(lines, bundle)

        elif bundle.subject_type == "contested_fact":
            self._render_contested(lines, bundle)

        elif bundle.subject_type == "confirm_take":
            # Session 4A.5a CU2 — the planner confirmed OUR OWN take back at us.
            # Name the gesture, name whose move it is, name the sandbox. Authored
            # copy carried verbatim; the renderer composes nothing of its own.
            from mre.modules.ask_fallback_copy import (
                CONFIRM_TAKE_BODY, CONFIRM_TAKE_GESTURE,
                CONFIRM_TAKE_GESTURE_GENERIC, CONFIRM_TAKE_LEAD,
                CONFIRM_TAKE_LEAD_ORDER,
            )
            kf = bundle.key_facts
            order, machine = kf.get("order"), kf.get("machine")
            lines.append(CONFIRM_TAKE_LEAD_ORDER.format(order=order) if order
                         else CONFIRM_TAKE_LEAD)
            lines.append("")
            lines.append(CONFIRM_TAKE_BODY)
            lines.append("")
            lines.append(CONFIRM_TAKE_GESTURE.format(order=order, machine=machine)
                         if order and machine else CONFIRM_TAKE_GESTURE_GENERIC)
            lines.append("")

        elif bundle.subject_type == "open_card":
            self._render_open_card(lines, bundle.key_facts.get("card") or {})

        elif bundle.subject_type == "advice":
            # CU2 (Session 4B.4) — the honest SCOPING answer. Conversational,
            # never a status recital, never an invented intervention.
            kf = bundle.key_facts
            # Session 4A.5a CU2 — the EXPEDITE-AN-EARLY-ORDER branch. Asked how to
            # get a specific order done faster when that order already finishes
            # ahead of its due date, lead with THAT, not a plan-wide scope.
            early = kf.get("expedite_early")
            if early:
                from mre.modules.ask_fallback_copy import (
                    ADVICE_EXPEDITE_EARLY, ADVICE_EXPEDITE_FLOOR_GENERIC,
                    ADVICE_EXPEDITE_FLOOR_RELEASE,
                )
                lines.append(ADVICE_EXPEDITE_EARLY.format(
                    order=early.get("order"), days=early.get("days_early")))
                lines.append(
                    ADVICE_EXPEDITE_FLOOR_RELEASE.format(release=early["release"])
                    if early.get("release") else ADVICE_EXPEDITE_FLOOR_GENERIC)
                lines.append("")
                lines.append("If the goal is a different order, name it and I'll "
                             "walk what its start is waiting on.")
                lines.append("")
                return
            # Session 4B.22 Item B2 — THE ANSWER FIRST, THEN THE BOUNDARY.
            # The opener has already ranked this board by consequence; the top
            # worry IS "what should I look at first", and refusing it while
            # holding it computed is the deafness this session exists to end.
            # The two questions are named apart in the same breath, because
            # "look at first" and "what should I do" are not the same ask and
            # answering one as the other is how this route got here.
            top = kf.get("opener_top")
            if top:
                lines.append(
                    "The first thing worth your attention on this board, ranked "
                    f"by consequence out of {top.get('rank_of', '?')}:")
                lines.append("")
                lines.append(f"  {top.get('headline')}")
                for d in top.get("detail") or []:
                    lines.append(f"    {d}")
                if top.get("pointer"):
                    lines.append(f"    -> {top['pointer']}")
                lines.append("")
                lines.append(
                    "That is a ranking of what is worth looking at, not a "
                    "recommendation of what to do about it.")
                lines.append("")
            late = kf.get("late_count", 0)
            if late:
                lines.append(
                    f"{late} order(s) finish late in this plan. I can't recommend "
                    "an intervention yet — deciding whether to open overtime, add a "
                    "machine, or re-prioritise isn't a question I answer today.")
            else:
                lines.append(
                    "I can't recommend an intervention yet — deciding whether to "
                    "open overtime, add a machine, or re-prioritise isn't a "
                    "question I answer today.")
            lines.append("")
            lines.append("Here's what I can do to help you decide:")
            lines.append("  - explain why any order is late (\"why is <order> late?\")")
            lines.append("  - show what an order is waiting on (\"why can't "
                         "<order> start earlier?\")")
            lines.append("  - price a what-if on the board: drag a job and I'll "
                         "cost the move exactly.")
            # R-AI3(2) — end with a GROUNDED judgment where the evidence supports
            # one. The disclaimer above covers the action BRIDGE only; the take
            # names the biggest lever from the same occupancy evidence.
            take = kf.get("take")
            if take:
                lines.append("")
                lines.append(f"My take: {take}")
            lines.append("")

        elif bundle.subject_type == "solve_time":
            # Session 4B.27 Item 8 — TWO TIMES, NAMED, NEVER FUSED.
            #
            # The deterministic figure is WORK: reproducible, machine-
            # independent, and the unit our budget is written in. The wall is
            # what that work cost on the machine that ran it. A planner asking
            # "how long did the solver spend" is owed both, because only one of
            # them is a property of the plan.
            kf = bundle.key_facts
            wall, det = kf.get("wall_s"), kf.get("det_consumed")
            if not kf.get("readable"):
                lines.append(
                    "I can't tell you, and the reason is on our side: I can't "
                    "find this schedule's solve record, so there is no timing "
                    "to read. That says nothing about the schedule itself.")
            elif not kf.get("recorded"):
                lines.append(
                    "This schedule's solve record doesn't carry its timing — "
                    "boards built before we started recording it don't have the "
                    "figures, and I won't estimate them from anything else. "
                    "Re-solving records them.")
            else:
                if det is not None and wall is not None:
                    rate = kf.get("seconds_per_unit")
                    lines.append(
                        f"The search did {det:.3g} deterministic units of work, "
                        f"and that took {wall:.1f} seconds on this machine"
                        + (f" — about {rate:g}s per unit here." if rate
                           else "."))
                    lines.append("")
                    lines.append(
                        "Those are different quantities on purpose. The "
                        "deterministic units are the work itself and reproduce "
                        "anywhere; the seconds are this machine's speed, and "
                        "the same search on other hardware takes a different "
                        "number of them.")
                elif det is not None:
                    lines.append(f"The search did {det:.3g} deterministic units "
                                 f"of work. Its wall time wasn't recorded, so I "
                                 f"can't tell you what that cost in seconds.")
                else:
                    lines.append(f"The search took {wall:.1f} seconds on this "
                                 f"machine. Its deterministic time wasn't "
                                 f"recorded, so I can't tell you how much WORK "
                                 f"that was — only how long it ran here.")
                budget = kf.get("det_budget")
                if budget:
                    lines.append("")
                    lines.append(f"Its budget was {budget:g} units.")
                if kf.get("wall_truncated"):
                    lines.append(
                        "It was stopped by the clock rather than by that "
                        "budget, so this particular result isn't reproducible.")
            # R-BK1: the board is the WINNER of a portfolio. The wall a planner
            # waited is not the winner's alone, and saying only the winner's
            # would understate it by the member count.
            k = kf.get("portfolio_k")
            if k and int(k) > 1:
                lines.append("")
                pw = kf.get("portfolio_wall_s")
                lines.append(
                    f"That is the WINNING search. This board was published from "
                    f"{int(k)} seeded searches, and the figures above are the "
                    f"one that won"
                    + (f"; all {int(k)} together took {float(pw):.0f} seconds"
                       f"{' (run side by side)' if kf.get('portfolio_parallel') else ''}."
                       if pw else "."))
            lines.append("")

        elif bundle.subject_type == "premise_correction":
            # Session 4B.13 Item 1, clause (i). R-AI3's register ladder: the
            # disagreement is met with evidence and a way forward, never a
            # refusal and never a lecture. The planner is far more likely to
            # have mistyped than to be wrong about their own plant.
            kf = bundle.key_facts
            order = kf.get("order", "?")
            claimed = kf.get("claimed_machine", "?")
            actual = kf.get("actual_machines") or []
            if len(actual) == 1:
                runs = f"it runs on {actual[0]}"
            elif actual:
                runs = ("it runs " + ", ".join(actual[:-1]) + f" and {actual[-1]}")
            else:
                runs = "I can't see any placement for it"
            if not kf.get("claimed_machine_exists"):
                lines.append(
                    f"There's no machine called {claimed} in this plant, so I "
                    f"can't answer that as asked — but {order} is scheduled, and "
                    f"{runs}.")
            else:
                lines.append(
                    f"{order} isn't on {claimed} — {runs}.")
            placements = kf.get("placements") or []
            if placements:
                lines.append("")
                for p in placements:
                    seq = p.get("seq")
                    when = ""
                    if p.get("start") and p.get("end"):
                        when = f"  {p['start']} -> {p['end']}"
                    lines.append(
                        f"  - {p.get('machine', '?')}"
                        + (f"  (op {seq})" if seq else "") + when)
            if actual:
                lines.append("")
                lines.append(
                    "Did you mean one of those? Ask \"why is " + order + " on "
                    + actual[0] + "?\" and I'll give you the cause.")
            lines.append("")

        elif bundle.subject_type == "optimality":
            # Session 4B.13 Item 2 — the cost proof, ASKED FOR and answered.
            # Every figure here comes from cost_proof; nothing is recomputed.
            kf = bundle.key_facts
            tb = kf.get("tiebreak_clause") or ""
            if kf.get("unknown") and kf.get("unavailable_reason"):
                # Session 4B.18. The bare "no solver report I can read" above is
                # true but leaves the planner unable to act; when the reason is
                # our storage rather than the run, saying so is what separates
                # "this never happened" from "this was not persisted".
                lines.append(
                    "I can't tell you, and the reason is on our side: this "
                    "schedule's solver report was not saved with its evidence, "
                    "so I can't read whether its cost was proved optimal. I "
                    "won't guess either way — and note this says nothing about "
                    "the schedule itself.")
                lines.append("")
                lines.append(
                    "Re-running the solve records it. The board's own strip "
                    "still shows what the solver reported at the time, so if it "
                    "states a status there, trust that over my silence here.")
            elif kf.get("unknown"):
                lines.append(
                    "I can't tell you — this schedule carries no solver report "
                    "I can read, so I don't know whether its cost was proved "
                    "optimal. I won't guess either way.")
            elif kf.get("no_solve"):
                lines.append(
                    "There was no solve to prove anything about — nothing was "
                    "admitted to this window, so the question doesn't arise yet.")
            elif kf.get("proved"):
                lines.append(
                    "Yes — and this is proved, not asserted. The solver closed "
                    "the bound: no cheaper schedule exists for this window under "
                    "the declared cost model." + tb)
                lines.append("")
                lines.append(
                    "To be exact about what that covers: it is the COST optimum. "
                    "It doesn't mean every order is on time, or that you'd like "
                    "the shape of it — only that no arrangement of this work is "
                    "cheaper.")
            else:
                g = kf.get("gap_text") or ""
                lines.append(
                    "I can't prove it, and I'd rather say so than guess. The "
                    "solver ran out of budget before it could close the bound"
                    + (f", with a gap of {g} still open." if g else
                       " and reported no gap, so the distance to the cheapest "
                       "schedule is unknown.") + tb)
                lines.append("")
                if g:
                    lines.append(
                        f"That gap is the limit of the PROOF, not a measure of "
                        f"how good the schedule is: it says a cheaper plan may "
                        f"exist and could be up to {g} cheaper. On large plants "
                        f"we have measured wide gaps over schedules whose actual "
                        f"cost barely moved.")
                else:
                    lines.append(
                        "That is a statement about the proof, not about the "
                        "schedule's quality — the plan in front of you places "
                        "every operation it admitted.")
            # Session 4B.27 Item 10 — THE OTHER SEEDS. "the best schedule you
            # FOUND" is a question about our search, and since R-BK1 the search
            # may be several. The gap says how far the PROOF got; the spread
            # says what independent searches actually reached. Both, or the
            # answer is half of one.
            #
            # Skipped where there is no solve to compare against at all — a
            # portfolio sentence under "there was no solve" would be noise.
            if not kf.get("unknown") and not kf.get("no_solve"):
                lines.extend(_portfolio_clause(kf))
            lines.append("")

        elif bundle.subject_type == "machine_count":
            kf = bundle.key_facts
            machines = kf.get("machines", [])
            n = kf.get("machine_count", len(machines))
            # Session 4B.13 Item 4 — SAY WHAT IS COUNTED. This line used to read
            # "N machine(s) carry work in this plan" over a count of DECLARED
            # resources, which a stranger falsifies by counting bars on a board
            # with idle rows. Declared and working are different facts; both are
            # said, each labelled, and the idle ones are named rather than left
            # for the reader to difference.
            working = kf.get("working_machine_count")
            idle = kf.get("idle_machines") or []
            if working is None:
                lines.append(f"{n} machine(s) in this plant.")
            elif working == n:
                lines.append(f"{n} machine(s) in this plant, and all {n} carry "
                             f"work in this plan.")
            else:
                lines.append(f"{n} machine(s) in this plant; {working} of them "
                             f"carry work in this plan.")
            if machines:
                lines.append("")
                for m in machines:
                    lines.append(f"  - {m}")
            if idle:
                lines.append("")
                lines.append("Carrying no work in this window: "
                             + ", ".join(idle) + ".")
            lines.append("")

        elif bundle.subject_type == "maintenance":
            kf = bundle.key_facts
            ex = kf.get("example_machine")
            lines.append(
                "I can't yet answer maintenance, shift, or calendar questions "
                "across the whole plan — that's on the roadmap, not built yet.")
            lines.append(
                "What I can show is one machine's downtime and closures — ask "
                + (f"\"how much downtime does {ex} have?\"" if ex
                   else "\"how much downtime does <machine> have?\"") + ".")
            lines.append("")

        elif bundle.subject_type == "attribute_lookup":
            # Session 4B.15 Item 3 — the value first, its source second, and
            # nothing else. A lookup that opens with a paragraph is a lookup
            # that lost.
            from mre.modules.attribute_lookup import render as _render_attrs
            ans = (bundle.key_facts or {}).get("attribute_answer")
            if ans is not None and ans.answered:
                lines.append(_render_attrs(ans))
            else:
                subject = (bundle.key_facts or {}).get("subject") or "that"
                lines.append(
                    f"I couldn't find that field on {subject} in this run. I "
                    "can read any field the submission declared — splittable, "
                    "minimum chunk, setup family, durations, due date, "
                    "quantity, customer, eligible machines — if you name the "
                    "order (and the operation, where it matters).")
            lines.append("")

        elif bundle.subject_type == "coaching":
            # CU4 (Session 4A.3-pre) — the retrieved capability answer: what the
            # knob enables, how to declare it (the submission field), and the spec
            # § it cites. Jurisdiction rule: coach the IDS requirement, never ERP
            # surgery. An unrecognized capability question lists what CAN be coached.
            kf = bundle.key_facts
            how = kf.get("how")
            cap = kf.get("capability")
            if cap is not None:
                # Session 4B.15 Item 5 — GROUNDED IN docs/05. The catalog's own
                # verdict / proof-status / doorway columns, composed by authored
                # copy keyed to the derived register. This wins over the
                # registry's "Yes — ..." lead, which carries no verdict and no
                # proof status and therefore cannot say "not today".
                from mre.modules.capability_answer import render as _render_cap
                lines.append(_render_cap(cap))
                from mre.modules.ask_fallback_copy import invitation_line
                inv = invitation_line("coaching")
                if inv:
                    lines.append("")
                    lines.append(inv)
            elif how:
                lines.append(f"Yes — {kf.get('enables')}.")
                lines.append("")
                lines.append(f"To enable it: {how}. See the incoming-data spec "
                             f"{kf.get('ids_ref')}.")
                # CU4 (R-AI4(3)) — the register ladder's invitation: the obvious
                # next question after "how do I enable X" is what the submission
                # already declares (a live door: data-problems). Silent on the
                # unknown-concept menu (that answer is itself a menu, not complete).
                from mre.modules.ask_fallback_copy import invitation_line
                inv = invitation_line("coaching")
                if inv:
                    lines.append("")
                    lines.append(inv)
            else:
                coachable = kf.get("coachable") or []
                lines.append(
                    "That's a configuration question, and I can point you to the "
                    "submission setting for it — but I don't recognize which "
                    "capability you mean.")
                if coachable:
                    lines.append("")
                    lines.append("Capabilities I can coach today (each names the "
                                 "submission field and its spec section):")
                    lines.append("  - " + ", ".join(coachable))
            lines.append("")

        elif bundle.subject_type == "swap_move":
            self._render_swap_move(lines, bundle)

        elif bundle.subject_type == "gap_between":
            self._render_gap(lines, bundle)

        elif bundle.subject_type == "rolling":
            # Session 4A.5c CU4 — the sliced-world answers, authored in
            # rolling_questions and rendered verbatim. They carry the hedge that
            # makes them honest ("that's an estimate, not a committed placement");
            # an LLM reword is exactly where that hedge goes missing.
            lines.append(bundle.key_facts.get("body", ""))
            lines.append("")

        elif bundle.subject_type == "lateness_cause":
            self._render_lateness_cause(lines, bundle)

        elif bundle.subject_type == "machine_idle":
            self._render_machine_idle(lines, bundle)

    # ------------------------------------------------------------------
    # Session 4A.5b (R-AI5(4)) — the labeled-synthesis answer surface.
    # ------------------------------------------------------------------

    def _render_synthesis(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CLAIM BLOCKS with per-claim provenance visible.

        A VERIFIED claim carries a citation exactly like testimony. An INTERPRETIVE
        claim carries the `synthesis` marker and the records it was read from. Mixed
        answers are expected and correct — that is what an honest reading of the
        evidence looks like when part of it is a reading. The STRUCTURE (which claims
        are which) is the contract here; the colour/badge treatment ships as cockpit
        tokens for the founder to tune."""
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_CITE, SYNTHESIS_FLOOR_DOORS, SYNTHESIS_LEAD, SYNTHESIS_MARK,
            SYNTHESIS_MARK_NO_RECORDS, SYNTHESIS_PARTIAL, SYNTHESIS_UNANSWERABLE,
            SYNTHESIS_UNANSWERABLE_CONSULTED, SYNTHESIS_UNANSWERABLE_NO_TOOLS,
            SYNTHESIS_UNGROUNDED,
        )
        kf = bundle.key_facts or {}
        claims = kf.get("claims") or []
        consulted = kf.get("consulted_tools") or []
        tools = ", ".join(consulted) or "nothing"

        if kf.get("unanswerable") or not claims:
            # Session 4B.27 Item 9 — the lead sentence is gated on the SAME fact
            # the line below it has always been gated on. A read that did not
            # happen is not described as a read.
            lines.append(SYNTHESIS_UNANSWERABLE if consulted
                         else SYNTHESIS_UNANSWERABLE_NO_TOOLS)
            if consulted:
                lines.append(SYNTHESIS_UNANSWERABLE_CONSULTED.format(tools=tools))
            # CU3(b) — THE WARM FLOOR. The honest non-answer keeps the doors part
            # 1's bridge offered. Absence-tested: when the dispatch could compute
            # no offers, the floor ends here rather than on a dangling header.
            offers = kf.get("offers") or []
            if offers:
                lines.append("")
                lines.append(SYNTHESIS_FLOOR_DOORS)
                for offer in offers:
                    lines.append(f"  - {offer}")
            lines.append("")
            return

        lines.append(SYNTHESIS_LEAD)
        lines.append("")
        for claim in claims:
            text = (claim.get("text") or "").strip()
            note = claim.get("sample_note") or ""
            if note:
                text = f"{text} ({note})"
            if claim.get("status") == "verified":
                rid = (claim.get("cited_record_ids") or ["?"])[0]
                lines.append(f"{text}  {SYNTHESIS_CITE.format(rid=str(rid)[:8])}")
            else:
                seen = claim.get("cited_record_ids") or claim.get(
                    "consulted_record_ids") or []
                if seen:
                    rids = ", ".join(str(r)[:8] for r in seen[:3])
                    lines.append(f"{text}  {SYNTHESIS_MARK.format(rids=rids)}")
                else:
                    lines.append(f"{text}  {SYNTHESIS_MARK_NO_RECORDS}")

        if any(c.get("load_bearing") for c in (kf.get("cut") or [])):
            lines.append("")
            lines.append(SYNTHESIS_UNGROUNDED)
        if kf.get("budget_exhausted") or kf.get("timed_out"):
            lines.append("")
            lines.append(SYNTHESIS_PARTIAL.format(tools=tools))
        lines.append("")

    def _render_prove_it(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """"Prove it" (R-AI5(4)) — the grounding pass, conversationally: either the
        record behind the claim, or the honest "that part is my inference from A and
        B, here's each"."""
        from mre.modules.ask_fallback_copy import (
            PROVE_IT_INTERPRETIVE, PROVE_IT_INTERPRETIVE_BARE, PROVE_IT_NO_TARGET,
            PROVE_IT_PRIOR_LEAD, PROVE_IT_PRIOR_NO_RECORDS, PROVE_IT_READ_FROM,
            PROVE_IT_RECORD_LINE, PROVE_IT_VERIFIED,
        )
        kf = bundle.key_facts or {}
        claim = kf.get("claim")
        if not claim:
            # Session 4B.22 — THE DRILL-DOWN RULING. Three authored branches, none
            # silent: the prior answer's records open; a prior answer with none
            # says it was authored copy; only a conversation with no prior answer
            # at all gets the no-target floor.
            prior = kf.get("prior_answer")
            if prior:
                rows = kf.get("lines") or []
                if rows:
                    lines.append(PROVE_IT_PRIOR_LEAD.format(
                        question=(prior.get("question") or "").strip(),
                        count=f"{len(rows)} record(s)"))
                    lines.append("")
                    for row in rows:
                        lines.append(PROVE_IT_RECORD_LINE.format(
                            summary=row.get("summary", "?"),
                            rid=row.get("rid", "?")))
                else:
                    lines.append(PROVE_IT_PRIOR_NO_RECORDS.format(
                        question=(prior.get("question") or "").strip()))
                lines.append("")
                return
            lines.append(PROVE_IT_NO_TARGET)
            lines.append("")
            return
        rows = kf.get("lines") or []
        verified = claim.get("status") == "verified"
        if verified:
            lines.append(PROVE_IT_VERIFIED)
        elif rows:
            lines.append(PROVE_IT_INTERPRETIVE)
        else:
            lines.append(PROVE_IT_INTERPRETIVE_BARE)
        lines.append("")
        lines.append(f'The claim: "{(claim.get("text") or "").strip()}"')
        if rows:
            lines.append("")
            for row in rows:
                lines.append(PROVE_IT_RECORD_LINE.format(
                    summary=row.get("summary", "?"), rid=row.get("rid", "?")))
        # Session 4B.5 CU5(d): the READINGS this one sentence came out of. Per
        # claim by construction — the verifier derives it from which tool calls
        # surfaced the records the claim was checked against, so two claims in one
        # answer can and do carry different lines.
        read_from = [t for t in (claim.get("read_from") or []) if t]
        if read_from:
            lines.append("")
            lines.append(PROVE_IT_READ_FROM.format(tools=", ".join(read_from)))
        lines.append("")

    # ------------------------------------------------------------------
    # Session 4A.3 composed-answer helpers (the swap/move bridge + absence pair)
    # ------------------------------------------------------------------

    def _render_swap_move(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU1 — the R-AI3 ladder: TESTIMONY (both orders' facts) -> a labeled TAKE
        -> the BRIDGE to the board gesture. The label is the boundary; the panel
        proposes the move, it never executes it (M10 has no write path)."""
        kf = bundle.key_facts
        a = kf.get("a") or {}
        b = kf.get("b")

        def _fact_line(f: dict) -> str:
            o = f.get("order", "?")
            p = f.get("placement") or {}
            where = (f" on {p['machine']} (starts {p['start']})"
                     if p.get("machine") else "")
            if f.get("late"):
                # Item 5(b): same formatter as the listing and the opener.
                status = f"{elapsed_minutes(abs(f['lateness']))} late"
            elif f.get("slack_days") is not None and f["slack_days"] > 0.05:
                status = f"{f['slack_days']:g} day(s) early"
            elif f.get("slack_days") is not None:
                status = "right on its due date"
            else:
                status = "scheduled"
            return f"  {o}: {status}{where}."

        lines.append(_fact_line(a))
        if b:
            lines.append(_fact_line(b))
        take = kf.get("take")
        if take:
            lines.append("")
            lines.append(f"My take: {take}")
        bridge = kf.get("bridge")
        if bridge:
            lines.append("")
            lines.append(bridge)
            lines.append("I can't drag bars or change the plan myself — you make the "
                         "gesture and I'll read what the sandbox says.")
        lines.append("")

    def _render_gap(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU2 — name the cause of the gap between two ops on their shared machine,
        or report it honestly when nothing gates it (never vouch a cause)."""
        kf = bundle.key_facts
        a, b = kf.get("order_a"), kf.get("order_b")
        if kf.get("no_orders"):
            lines.append("Tell me which two orders and I'll read the gap between them "
                         "on their shared machine — e.g. \"why is there a gap between "
                         "ORD-04 and ORD-05?\".")
            lines.append("")
            return
        if kf.get("no_second"):
            lines.append(f"I read the gap between two jobs on a shared machine — name "
                         f"the other order too, e.g. \"why is there a gap between {a} "
                         "and <other order>?\".")
            lines.append("")
            return
        cause = kf.get("cause")
        m = kf.get("machine")
        gap = kf.get("gap_min")
        if cause == "no_shared_machine":
            lines.append(f"{a} and {b} don't run on the same machine, so there's no "
                         "shared-machine gap between them to explain.")
        elif cause == "adjacent":
            lines.append(f"There's essentially no gap — {kf['earlier_order']} finishes "
                         f"{kf['earlier_end']} on {m} and {kf['later_order']} starts "
                         f"right after ({kf['later_start']}).")
        elif cause == "occupied":
            lines.append(f"The gap on {m} between {kf['earlier_order']} "
                         f"({kf['earlier_end']}) and {kf['later_order']} "
                         f"({kf['later_start']}) isn't idle — {kf['occupier']} runs "
                         f"there ({kf['occupier_window']}).")
        elif cause == "closure":
            c = kf["closure"]
            lines.append(f"The ~{int(gap)} min gap on {m} is a calendar closure — "
                         f"{c['reason']} from {c['start']} to {c['end']} — so no work "
                         "can run there.")
        elif cause == "off_shift":
            lines.append(f"The gap on {m} between {kf['earlier_order']} "
                         f"({kf['earlier_end']}) and {kf['later_order']} "
                         f"({kf['later_start']}) is off-shift — {m} is closed then and "
                         f"reopens at {kf['reopen']}, which is when {kf['later_order']} "
                         "takes the next opening.")
        elif cause == "release":
            lines.append(f"{kf.get('later_order', b)} can't move up because it isn't "
                         f"released until {kf['release']}; nothing runs before its "
                         f"release date, so {m} sits open until then.")
        elif cause == "upstream":
            lines.append(f"{kf.get('later_order', b)} can't move up because its earlier "
                         f"step doesn't finish on {kf['upstream_machine']} until "
                         f"{kf['upstream_until']} — {m} waits for that hand-off.")
        else:  # unexplained
            lines.append(f"There's about a {int(gap)} min gap on {m} between "
                         f"{kf['earlier_order']} ({kf['earlier_end']}) and "
                         f"{kf['later_order']} ({kf['later_start']}), and I can't tie "
                         "it to another job, a closure, or a release on the evidence I "
                         "have. Post-R-SC3 the schedule doesn't leave cost-equal slack, "
                         "so a gap with no visible gate is worth flagging — drag one "
                         "bar into it and the sandbox will say if the move is feasible.")
        # CU4 (R-AI4(3)) — where a real gap was explained on a known machine, the
        # neighboring context is the rest of that machine's schedule (a live door:
        # machine-schedule). Silent on 'adjacent' (no gap — the thought is complete)
        # and 'no_shared_machine' (no machine to schedule).
        if m and cause in ("occupied", "closure", "off_shift", "release",
                           "upstream", "unexplained"):
            from mre.modules.ask_fallback_copy import invitation_line
            inv = invitation_line("gap-between", machine=m)
            if inv:
                lines.append("")
                lines.append(inv)
        lines.append("")

    def _render_machine_idle(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU2 — a machine that carries work is not idle (redirect to its schedule,
        no order names); a genuinely idle machine gets an eligibility-honest scope."""
        kf = bundle.key_facts
        m = kf.get("machine", "?")
        n = kf.get("op_count", 0)
        if n:
            span = (f", running from {kf['first']} to {kf['last']}"
                    if kf.get("first") and kf.get("last") else "")
            lines.append(f"{m} isn't idle — it carries {n} operation(s){span}. Ask "
                         f"\"what's running on {m}?\" for the list.")
        else:
            lines.append(f"No work landed on {m} in this plan.")
            mih = kf.get("manned_idle_hours")
            if mih is not None:
                lines.append(f"Its manned calendar sat open about {mih:g}h with "
                             "nothing booked.")
            lines.append("Usually that means every operation it could run was cheaper "
                         "or freer on another machine, or nothing in this book was "
                         "eligible for it. Ask \"what's running on <machine>?\" to see "
                         "where the work went.")
        lines.append("")

    def _render_lateness_cause(self, lines: list[str],
                               bundle: ExplanationBundle) -> None:
        """THE PROMOTED ROUTE (Session 4A.5c, R-AI5(7)) — the cause mix across the
        late set. Authority: docs/promotions/aggregate-lateness-2026-07-26.md.

        Composed authored copy, rendered verbatim: the shape it replaces was
        answered by verified synthesis claims, and handing a proven cause mix to
        the rendering model to reword is how a hedge goes missing."""
        from mre.modules.ask_fallback_copy import (
            LATENESS_CAUSE_BLOCKER, LATENESS_CAUSE_LEAD,
            LATENESS_CAUSE_LEAD_NO_TOTAL, LATENESS_CAUSE_MIX_HEADER,
            LATENESS_CAUSE_MIX_HEADER_ONE, LATENESS_CAUSE_MIX_LINE,
            LATENESS_CAUSE_MIX_LINE_ONE, LATENESS_CAUSE_MONEY,
            LATENESS_CAUSE_MONEY_WORST, LATENESS_CAUSE_NONE,
            LATENESS_CAUSE_PREMISE_ONE, LATENESS_CAUSE_UNATTRIBUTED,
        )
        kf = bundle.key_facts
        late = int(kf.get("late_count", 0) or 0)
        # Session 4B.21 — THE DENOMINATOR IS THE SCHEDULED SET, not the known
        # one. An order with no placement has no completion date, so it can be
        # neither late nor "on time or early"; counting it in either direction
        # is the category fusion this ruling ends.
        sched = kf.get("scheduled_order_count")
        beyond = kf.get("beyond_horizon_order_count")
        total = int(sched if sched is not None else (kf.get("total_orders") or 0))
        causes = kf.get("causes") or []

        # 1 — THE PREMISE, first. "Why are so many late" on a plan with one late
        # order is answered by saying so; the causes still follow, but the planner
        # is not left believing a premise the evidence does not support.
        if late == 0:
            if beyond:
                from mre.modules.ask_fallback_copy import (
                    LATENESS_CAUSE_NONE_ROLLING)
                lines.append(LATENESS_CAUSE_NONE_ROLLING.format(
                    scheduled=total, beyond=beyond))
            else:
                lines.append(LATENESS_CAUSE_NONE)
            lines.append("")
            return
        if late == 1:
            c = causes[0] if causes else {}
            mins = c.get("lateness_minutes")
            amount = (f"{int(mins)} minutes" if mins and mins < 120
                      else f"{round((mins or 0) / 60, 1)} hours")
            lines.append(LATENESS_CAUSE_PREMISE_ONE.format(
                order=c.get("order", "?"), amount=amount,
                on_time=(total - 1) if total else "rest"))
        elif total:
            lines.append(LATENESS_CAUSE_LEAD.format(late=late, total=total))
        else:
            lines.append(LATENESS_CAUSE_LEAD_NO_TOTAL.format(late=late))
        lines.append("")

        # 2 — THE MIX. Which chains repeat is the question; one order's chain is
        # `late-order`.
        mix = [m for m in (kf.get("cause_mix") or [])
               if m.get("cause") != "no recorded driver"]
        if mix:
            lines.append(LATENESS_CAUSE_MIX_HEADER if late > 1
                         else LATENESS_CAUSE_MIX_HEADER_ONE)
            for m in mix:
                lines.append(
                    LATENESS_CAUSE_MIX_LINE.format(
                        cause=m["cause"], orders=", ".join(m["orders"]))
                    if late > 1 else
                    LATENESS_CAUSE_MIX_LINE_ONE.format(cause=m["cause"]))
            lines.append("")

        # 3 — THE CONCRETE HOLDS, from the solved occupancy. Only where there is
        # one: a named blocker is evidence, an assumed one is a fabrication.
        blocked = [c for c in causes if c.get("blocked_by")]
        if blocked:
            lines.append("Where the hold is concrete:")
            for c in blocked:
                b = c["blocked_by"]
                lines.append(LATENESS_CAUSE_BLOCKER.format(
                    order=c["order"], machine=b.get("machine", "?"),
                    until=b.get("until", "?"), blocker=b.get("blocker_order", "?"),
                    start=b.get("my_start", "?")))
            lines.append("")

        # 4 — WHAT CANNOT BE ATTRIBUTED, said out loud rather than papered over.
        unattributed = [c["order"] for c in causes if not c.get("blocked_by")]
        if unattributed:
            lines.append(LATENESS_CAUSE_UNATTRIBUTED.format(
                orders=", ".join(unattributed)))
            lines.append("")

        # 5 — the money.
        total_cost = kf.get("tardiness_total") or 0.0
        if total_cost:
            worstline = ""
            worst = (kf.get("tardiness_lines") or [None])[0]
            if worst and len(kf.get("tardiness_lines") or []) > 1:
                worstline = LATENESS_CAUSE_MONEY_WORST.format(
                    cost=f"{worst['cost']:,.2f}", order=worst["order"])
            lines.append(LATENESS_CAUSE_MONEY.format(
                total=f"{total_cost:,.2f}", worst=worstline))
            lines.append("")

        self._render_excluded_note(lines, bundle)

    # ------------------------------------------------------------------
    # Session 4A.2 composed-answer helpers
    # ------------------------------------------------------------------

    def _render_findings(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU2 — every finding as (subject, offending value, plain cause, catalog
        fix), coalesced across layers (CU6). Statistics are supporting cast."""
        from mre.modules.explainer import _load_catalog_safe
        from mre.modules.planner_language import compose_findings
        composed = compose_findings(bundle.ordered_records, bundle.identity_map,
                                    _load_catalog_safe())
        entity = bundle.key_facts.get("entity_ref")
        if not composed:
            if entity:
                # R-PD1 clause (6), Session 4B.11 CU4(d) — "why was ORD-X
                # excluded?" about an order that was NOT excluded is answered
                # about THAT ORDER, and says where it actually is. The bare
                # "no data-quality problems found for ORD-X" left a planner who
                # had just been told "nothing scheduled" with two negatives and
                # no fact.
                sched = bundle.key_facts.get("subject_is_scheduled")
                if sched:
                    lines.append(
                        f"{entity} wasn't excluded — it IS in this schedule. "
                        f"Ask \"where is {entity}?\" for its operation timeline.")
                elif sched is False:
                    lines.append(
                        f"{entity} wasn't excluded by any check, and it isn't "
                        f"placed in this schedule either — so nothing in the "
                        f"record explains its absence. That is a gap worth "
                        f"reporting, not a data-quality problem.")
                else:
                    lines.append(f"No data-quality problems found for {entity}.")
            else:
                lines.append("No data-quality problems — the submission is clean.")
                # Session 4B.21, found by this session's own live verification:
                # "why are some orders missing from the schedule entirely"
                # answered exactly the line above, on a board where 14 orders
                # have no placement. True about EXCLUSIONS and silent about the
                # disposition the question was about. Ruling clause (2).
                beyond = bundle.key_facts.get("beyond_horizon_order_count")
                if beyond:
                    from mre.modules.ask_fallback_copy import (
                        EXCLUDED_NONE_BUT_TRAY)
                    lines.append(EXCLUDED_NONE_BUT_TRAY.format(beyond=beyond))
            lines.append("")
            self._render_excluded_note(lines, bundle)
            return
        head = (f"{len(composed)} data-quality problem(s)"
                + (f" for {entity}" if entity else "") + ":")
        lines.append(head)
        lines.append("")
        for i, c in enumerate(composed, 1):
            self._render_finding_detail(lines, c, ordinal=i)
        self._render_excluded_note(lines, bundle)
        # CU2 (R-AI3(3)) — invite the obvious next question (the fix-first order),
        # only on a general data-problems answer with more than one problem to rank.
        if len(composed) > 1 and not entity:
            from mre.modules.ask_fallback_copy import INVITE_DATA_PROBLEMS
            lines.append("")
            lines.append(INVITE_DATA_PROBLEMS)

    def _render_finding_detail(self, lines: list[str], c: dict,
                               ordinal: Optional[int] = None) -> None:
        prefix = f"  {ordinal}. " if ordinal else "  "
        sev = str(c.get("severity", "info")).upper()
        lines.append(f"{prefix}{c['cause']}  [{sev}]")
        # CU4 — name the affected orders (a capped sample, never bare indices),
        # so a finding that names an input still points at the orders it touched.
        aff = c.get("affected") or {}
        sample = aff.get("sample") or []
        if sample:
            more = ""
            if aff.get("count") and aff["count"] > len(sample):
                more = f" … {aff['count']} in all"
            lines.append(f"       Affected: {', '.join(sample)}{more}")
        if c.get("layer_count", 0) > 1:
            where = ", ".join(c.get("layers", [])) or f"{c['layer_count']} layers"
            lines.append(f"       confirmed at {c['layer_count']} layers ({where})")
        if c.get("fix"):
            lines.append(f"       Fix: {c['fix']}")

    def _render_start_reason(self, lines: list[str], bundle: ExplanationBundle) -> None:
        kf = bundle.key_facts
        name = bundle.subject_external_name
        start = kf.get("start")
        wd = kf.get("start_weekday")
        when = f"{wd} ({start})" if wd and start else (start or "when it does")
        blk = kf.get("blocked_by")
        # CU3 (Session 4A.3-pre) — a why-EARLY question is answered with the R-SC3
        # floor (finishing early is free; cost-equal work is placed as early as it
        # can go to bank slack), NOT a lower-bound cause. The concrete lower bound
        # (release / first opening / a blocker) supports it as testimony.
        if kf.get("why_early"):
            eb = kf.get("early_by_days")
            span = ""
            if eb is not None and eb >= 0.05:
                span = f" — it finishes about {eb:g} day(s) ahead of its due date" + (
                    f" ({kf['due']})" if kf.get("due") else "")
            lines.append(
                f"{name} starts {when} because finishing early costs nothing here: "
                "among equally-cheap options the schedule starts work as soon as it "
                f"can, banking slack{span}.")
            if kf.get("earliness_priced"):
                lines.append(
                    "A declared earliness preference also paid a little to pull it "
                    "onto a machine that was free earlier.")
            # the concrete lower bound, as supporting testimony
            if kf.get("release_binds") and kf.get("release"):
                rwd = kf.get("release_weekday")
                rel = f"{rwd} {kf['release']}" if rwd else kf["release"]
                lines.append(f"The earliest it could begin is its release date, {rel}.")
            elif blk:
                lines.append(
                    f"The earliest opening on {blk['machine']} came free at "
                    f"{blk['until']} (held before that by {blk['blocker_order']}).")
            lines.append("")
            return
        if kf.get("release_binds") and kf.get("release"):
            rwd = kf.get("release_weekday")
            rel = f"{rwd} {kf['release']}" if rwd else kf["release"]
            lines.append(
                f"{name} starts {when} because it isn't released for production "
                f"until {rel} — nothing can begin before its release date.")
        elif blk:
            prio = f", {blk['blocker_priority']}" if blk.get("blocker_priority") else ""
            lines.append(
                f"{name} starts {when} because {blk['machine']} was busy: it was "
                f"held by {blk['blocker_order']}{prio} until {blk['until']}, so "
                f"{name} took the next opening.")
        elif start:
            lines.append(f"{name} starts {when}; it takes the first opening its "
                         "machine and its earlier steps allow.")
        else:
            lines.append(f"{name} isn't scheduled, so it has no start to explain.")
        lines.append("")

    def _render_why_here(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """THE BLOCKER ANALYSIS, voiced (Session 4B.14 Item 2).

        The bar this copy is written against, from the session brief:

            "op20 couldn't start Tuesday afternoon: it needs 6h and 3h remain
             before PAINT-01 closes, and it can't be split. The next window long
             enough is Thursday, after maintenance."

        Three things that sentence does and the old start-reason copy did not: it
        says COULDN'T rather than implying it, it states the arithmetic that makes
        it true, and it names what the operation was waiting FOR. Authored, not
        LLM-reworded, because a reword that softens "couldn't" into "took the next
        opening" is precisely the failure this route exists to end."""
        kf = bundle.key_facts
        name = bundle.subject_external_name
        seq = kf.get("op_seq")
        op = f"op{seq}" if seq is not None else "this operation"
        machine = kf.get("machine")
        verdict = kf.get("verdict")

        if verdict == "unplaced":
            lines.append(f"{name} has no placement in this window, so there is no "
                         "'here' to explain yet. Ask \"why isn't "
                         f"{name} scheduled yet?\" and I'll answer that instead.")
            lines.append("")
            return

        # Item 5(d) — say WHICH operation this is about when the planner named an
        # order and the order has more than one. A bridging sentence is cheap; a
        # planner silently answered about a different bar is not.
        if (kf.get("op_count") or 0) > 1 and not kf.get("op_named"):
            lines.append(f"Answering about {name} {op} on {machine} — the first of "
                         f"its {kf['op_count']} operations.")

        binding = kf.get("binding") or {}
        start = kf.get("start")
        wd = kf.get("start_weekday")
        when = f"{wd} {start}" if wd and start else (start or "when it does")

        # Session 4B.14 Item 3 — WHEN THE PLANNER IS PUSHING BACK, ANSWER THE
        # PUSH-BACK. R-AI3(4): disagreement is met with warm evidence, never
        # capitulation and never a curt re-assertion; where the planner is RIGHT,
        # say so plainly and correct the record. The measured failure was an
        # answer that addressed nothing that was said and still read as
        # agreement, so silence here is not neutral — it is the defect.
        if kf.get("challenge"):
            lines.append(self._challenge_lead(kf, verdict, binding))

        # THE PREMISE, BEFORE THE EXPLANATION (the listening docket, Item 3).
        # "why can't this be moved" asserts something before it asks anything,
        # and where that assertion is false the honest answer opens by saying
        # so — R-AI3(4), where the planner is right say so plainly and FIRST.
        # It is a LEAD and not a replacement, because unlike 4B.13's placement
        # premise the explanation that follows is still correct: it is simply
        # about one direction, and the correction is what makes that visible.
        mob = kf.get("mobility") or {}
        if mob.get("refutes"):
            lines.append(self._mobility_correction(kf, mob))
        if mob:
            # Item 4 — the parts are LABELLED. A two-direction answer whose
            # halves run together reads as one claim about "moving", which is
            # the ambiguity the whole item exists to remove. The blank line is
            # a SEPARATOR, so it is written only when there is something above
            # to separate from — an answer that opens on an empty line reads as
            # a rendering fault.
            if lines:
                lines.append("")
            lines.append("Earlier — what's stopping it:")

        if verdict == "could_not":
            lead = (f"{name} {op} couldn't start before {when}: "
                    f"{binding.get('because', 'a constraint bound it there')}.")
            if not kf.get("splittable") and binding.get("family") == "chunkfit":
                lead = lead[:-1] + ", and it can't be split."
            lines.append(lead)
            # The runner-up earns its line only when it is at least as recent as
            # the near miss the lead already described. Otherwise it is a true
            # sentence about a constraint that stopped mattering days earlier
            # ("CUT-01 is closed until Jan 5 07:00" under an answer about Jan 13),
            # and padding a causal answer with stale true facts is how the
            # original defect read as thorough.
            runner = kf.get("runner_up") or {}
            near = (binding.get("facts") or {}).get("short_window") or {}
            recent = (not near.get("start")
                      or (runner.get("at") or "") >= near["start"])
            if (runner.get("because") and recent
                    and runner.get("family") != binding.get("family")):
                lines.append(f"Before that: {runner['because']}.")
            closure = self._closure_note(kf)
            if closure:
                lines.append(closure)
        elif verdict == "chose":
            at = binding.get("at")
            lines.append(
                f"Nothing prevented {name} {op} from starting earlier. Holding "
                f"every other placement where it is, {machine} had open, unheld "
                f"time from {at} — the solver chose {when} rather than being "
                "forced into it.")
            driver = kf.get("chosen_driver")
            if driver:
                lines.append(f"The assignment decision records its driver as "
                             f"{driver}.")
            else:
                lines.append("No decision record states a cost reason for the "
                             "later placement, so I can't tell you why it "
                             "preferred it — only that it was not forced.")
        else:
            lines.append(
                f"I can't attribute {name} {op}'s placement at {when} to a "
                "binding constraint: the earliest-start estimates I can compute "
                "don't line up with where it actually sits. Rather than pick one "
                "and sound certain, I'd rather say I don't know.")

        # Session 4B.14 Item 4, voiced. A chunked operation's RUN TIME and its
        # ELAPSED SPAN are different numbers and the gap between them is where
        # the pauses live. Stating it here is what makes this route an honest
        # answer to "why does it go through downtime" rather than merely a
        # word-match on "closed": every chunk is placed inside open calendar
        # time by construction (4B.13's closure sweep proved zero exceptions),
        # so the pauses ARE non-working time, and that is a fact, not a guess.
        chunks = kf.get("chunk_count") or 0
        run_min, span_min = kf.get("run_min"), kf.get("span_min")
        if chunks > 1 and run_min and span_min:
            # The span is stated as its wall-clock bracket rather than as a
            # duration: "97h" is a true number a planner cannot picture, and
            # rendering working minutes as DAYS would be worse — a day of what,
            # calendar or shift? The dates are unambiguous and the answer
            # already carries them.
            lines.append(
                f"It runs in {chunks} pieces between {start} and {kf.get('end')}, "
                f"{_dur_min(run_min)} of actual work — it pauses when {machine} "
                f"closes and resumes when it reopens, which is what it means for "
                f"this operation to be splittable.")

        # The chain, when there is more than one link — the planner's own audit.
        chain = [c for c in (kf.get("chain") or []) if c]
        if len(chain) > 1:
            lines.append("")
            lines.append("What pushed it, in order:")
            for c in chain:
                lines.append(f"  {c.get('at')}  {c.get('label')} "
                             f"[docs/05 {c.get('citation')}] — {c.get('because')}")

        # R-AI3(1): what this reading did NOT weigh, so the planner can price the
        # answer's confidence themselves.
        unc = kf.get("uncomputed") or []
        if unc and verdict in ("could_not", "chose"):
            lines.append("")
            lines.append("Not weighed here (docs/05): "
                         + "; ".join(f"{u.get('catalog', '?')} "
                                     f"{_family_gist(u.get('why', ''))}"
                                     for u in unc) + ".")

        # THE OTHER DIRECTION (the listening docket, Item 4). "Why can't this
        # be moved" owes a two-direction answer: everything above is the
        # EARLIER half, and this is what the product can say about LATER.
        if mob:
            self._render_mobility_later(lines, kf, mob)
        lines.append("")

    @staticmethod
    def _mobility_subject(kf: dict, name: str) -> str:
        seq = kf.get("op_seq")
        return f"{name} op{seq}" if seq is not None else name

    def _mobility_correction(self, kf: dict, mob: dict) -> str:
        """The premise correction, as a LEAD (the listening docket, Item 3).

        Authored, not composed from a template with a slot for "direction",
        because the two refutations are different facts and read differently to
        a planner. LATER-OPEN is a statement about the calendar: there is room
        over there. EARLIER-OPEN is a statement about the SOLVER: nothing was
        stopping it, and the placement was a choice. Blending them into one
        sentence about "it can move" would be the category fusion 4B.21 §5a.72
        named the mechanism of: a name written once, by whoever needed it, and
        never re-read as a claim."""
        name = self._mobility_subject(kf, kf.get("order") or "it")
        machine = kf.get("machine")
        dirs = mob.get("open_directions") or []
        if "later" in dirs:
            at = mob.get("later_at")
            wd = mob.get("later_weekday")
            when = f"{wd} {at}" if wd and at else at
            also = (" It also had open time earlier — see below."
                    if "earlier" in dirs else "")
            return (f"It can be moved — {name} has room LATER: the next "
                    f"opening on {machine} long enough for the whole operation "
                    f"is {when}. What's blocked is moving it EARLIER, and "
                    f"that is what I've explained below.{also}")
        return (f"It can be moved — nothing was holding {name} back. "
                f"{machine} had open, unheld time before where it sits, so "
                f"this placement was the solver's choice rather than the only "
                f"option. Here is what that looks like.")

    def _render_mobility_later(self, lines: list[str], kf: dict,
                               mob: dict) -> None:
        """The LATER half of a two-direction mobility answer (Item 4).

        EVERY CLAUSE TRACES TO SOMETHING THAT ALREADY VERIFIES IT. The opening
        is `later_move.next_opening_after` over free time — the same scan, under
        the same R-C3 chunk discipline, that the blocker analysis and the
        SolverBuilder use. The hold is the frozen boundary (R-F1) or the pin
        (A7/F1). Nothing here re-solves and nothing here PRICES: what a later
        move costs is `what-would-change`'s answer and the delta card's, and
        this paragraph links to both rather than becoming a second pricer with
        no validation behind it. 4B.16's rule, carried: an opening is NECESSARY,
        never sufficient."""
        from mre.modules import mobility_premise as mp

        name = self._mobility_subject(kf, kf.get("order") or "it")
        machine = kf.get("machine")
        v = mob.get("verdict")
        lines.append("")

        if v == mp.VERDICT_HELD:
            kind = mob.get("held_kind")
            at = mob.get("held_at")
            if kind == mp.HELD_FROZEN:
                lines.append(
                    f"Later: it can't go there either, and \"can't be moved\" "
                    f"is fair — {name} sits inside the committed front "
                    f"(frozen through {at}). Committed work is moved by moving "
                    f"the frozen boundary, not by moving the bar [docs/05 "
                    f"R-F1].")
            else:
                lines.append(
                    f"Later: it can't go there either, and \"can't be moved\" "
                    f"is fair — {name} carries a pin at {at}, so the solver "
                    f"holds it where it is until the pin is released "
                    f"[docs/05 A7/F1].")
            return

        if v == mp.VERDICT_UNDECIDABLE:
            lines.append(
                f"Later: I can't tell you. {name} runs in "
                f"{mob.get('chunk_count')} pieces, and a chunked operation "
                f"can't be priced as a local move in either direction — the "
                f"pauses are closures the solver placed, and shifting the bar "
                f"doesn't re-derive them. That is a limit of what I can "
                f"compute, not a statement that the plant has no room.")
            return

        if v == mp.VERDICT_LATER_OPEN:
            at = mob.get("later_at")
            wd = mob.get("later_weekday")
            when = f"{wd} {at}" if wd and at else at
            lines.append(
                f"Later: there is room. The first opening on {machine} where "
                f"the whole operation fits after where it sits now is {when} "
                f"— computed from {machine}'s open calendar minus everything "
                f"already placed on it, under the same minimum-piece rule the "
                f"solver applies [docs/05 C1/C2, C3].")
            lines.append(
                "That is WHERE it could go, not what it would cost. Ask "
                f"\"what would pushing {name} out cost?\" and I'll hold every "
                "other placement, move that one bar and price the difference "
                "— or drag it on the board and the card prices the same move.")
            return

        # BOXED_IN — the premise HOLDS in both directions, and says so.
        lines.append(
            f"Later: no opening on {machine} fits the whole operation after "
            f"where it sits now either — so \"can't be moved\" is fair, and "
            f"the reason above is the whole of it. This counts free time on "
            f"{machine} only; a move to another machine is a different "
            "question, and one I'd answer as a swap.")

    def _render_counterfactual(self, lines: list[str],
                               bundle: ExplanationBundle) -> None:
        """THE COUNTERFACTUAL, voiced (Session 4B.16 Item 1).

        The bar, from the session brief:

            op20 needs 431 minutes in one piece and Tuesday had 294 left
            after op10.

            To fit Tuesday, one of these has to change:
              min_chunk_minutes <= 215 on this operation      [C3, docs/06 §5.3]
              op10 finishes by 11:49 instead of 14:06         [A1/A2]
              431 contiguous minutes free on an eligible machine  [B1]
              PAINT-01's Tuesday window extended by 137 minutes   [C1/C2]

            If min_chunk changed, the next bound would be B1 resource
            availability at 2026-01-13 14:06 — so this removes the barrier,
            it does not place the operation there.

        Authored, not LLM-reworded, for the same reason the blocker analysis is:
        the last paragraph is the whole discipline of the route, and it is
        exactly the sentence a "answer in 2-3 sentences" reword drops first.
        Dropping it turns a necessary condition into a promise."""
        kf = bundle.key_facts
        name = bundle.subject_external_name
        seq = kf.get("op_seq")
        op = f"op{seq}" if seq is not None else "this operation"
        machine = kf.get("machine")
        verdict = kf.get("verdict")

        if verdict == "unplaced":
            lines.append(f"{name} has no placement in this window, so there is "
                         "nothing to move earlier yet. Ask \"why isn't "
                         f"{name} scheduled yet?\" and I'll answer that instead.")
            lines.append("")
            return

        if (kf.get("op_count") or 0) > 1 and not kf.get("op_named"):
            lines.append(f"Answering about {name} {op} on {machine} — the first "
                         f"of its {kf['op_count']} operations.")

        # NOTHING HAS TO CHANGE. The `chose` verdict's honest counterfactual:
        # the barrier the planner is asking me to remove does not exist, and
        # inventing one to have something to offer would be the same over-claim
        # `why-here` was built to end, wearing a helpful face.
        if verdict == "chose":
            binding = kf.get("binding") or {}
            lines.append(
                f"Nothing has to change for {name} {op} to start earlier: "
                f"holding every other placement where it is, {machine} had "
                f"open, unheld time from {binding.get('at')}"
                + (f", {_dur_min(kf.get('slack_min'))} before it started"
                   if kf.get("slack_min") else "")
                + ". It was not prevented from going earlier — the solver "
                  "preferred this placement.")
            driver = kf.get("chosen_driver")
            if driver:
                lines.append(f"The assignment decision records its driver as "
                             f"{driver}.")
            self._render_unpriceable(lines, kf)
            self._render_not_weighed(lines, kf)
            lines.append("")
            return

        if verdict != "could_not":
            lines.append(
                f"I can't tell you what would move {name} {op}: the "
                "earliest-start estimates I can compute don't line up with "
                "where it actually sits, so I don't know which of them to "
                "relax. Rather than pick one and sound certain, I'd rather say "
                "I don't know.")
            self._render_not_weighed(lines, kf)
            lines.append("")
            return

        # -- the arithmetic the levers are about ---------------------------
        window = kf.get("window") or {}
        binding = kf.get("binding") or {}
        needed = _dur_min(kf.get("needed_min"))
        if window:
            avail = window.get("available_min") or 0.0
            short_by = (kf.get("needed_min") or 0.0) - float(avail)
            piece = ("in one piece" if not kf.get("splittable")
                     else "of open time")
            lines.append(
                f"{name} {op} needs {needed} {piece}. The last stretch before "
                f"where it sits that was too short ran "
                f"{window.get('weekday')} {str(window.get('start'))[:10]} "
                f"{str(window.get('start'))[11:]}–{str(window.get('end'))[11:]} "
                f"on {machine} — {_dur_min(avail)}, "
                f"{_dur_min(short_by)} short.")
            target = f"fit {window.get('weekday')}"
        else:
            lines.append(
                f"{name} {op} is held at {binding.get('at')} by "
                f"{binding.get('label')} [docs/05 {binding.get('citation')}].")
            target = "move it earlier"

        levers = [l for l in (kf.get("levers") or []) if l]
        if not levers:
            lines.append(
                f"I can't name a change that would move it: the bound is real "
                f"and every relaxation I know how to compute either doesn't "
                f"apply here or didn't check out when I re-ran the placement "
                f"under it.")
        else:
            lines.append("")
            lines.append(f"To {target}, one of these has to change:")
            for lev in levers:
                cite = f"docs/05 {lev.get('citation')}"
                if lev.get("spec"):
                    cite += f" · {lev['spec']}"
                lines.append(f"  {lev.get('statement')}  [{cite}]")
                lines.append(f"      {lev.get('effect')}")

            # THE HARD RULE, said out loud on every answer that carries a
            # lever. A necessary condition is not a sufficient one, and the
            # next bound is the proof of the difference.
            nxt = kf.get("next_bound") or {}
            lines.append("")
            if nxt.get("at"):
                lines.append(
                    f"If any of these changed, the next bound would be "
                    f"{nxt.get('label')} [docs/05 {nxt.get('citation')}] at "
                    f"{nxt.get('at_weekday') or ''} {nxt['at']}".rstrip()
                    + " — that removes the barrier; it does not place the "
                      "operation there.")
            else:
                lines.append(
                    "Each of these removes the barrier; none of them places "
                    "the operation earlier. Where it would actually land is a "
                    "question only a re-solve can answer, and I don't re-solve.")

        # A DECLARED CLOSURE IN THE WAY: reported, deliberately not priced.
        # Lifting a maintenance day would plainly move this operation, so
        # saying nothing would leave a hole in the disjunction above — but
        # pricing it means asserting what the machine's open hours WOULD be on
        # a day the calendar declares shut, which is an invention.
        closure = kf.get("closure")
        if closure:
            lines.append("")
            lines.append(
                f"Between that window and where it sits, {machine} is closed "
                f"for {str(closure.get('reason', 'a closure')).replace('_', ' ')} "
                f"from {closure.get('start')} to {closure.get('end')}. Lifting "
                "it would plainly move this, and I haven't priced it: I can't "
                "say what the machine's open hours would be on a day the "
                "calendar declares shut.")

        # The eligibility fact, stated whichever way it falls (a shut door is a
        # finding; an unknown one is not the same thing as a shut one).
        if not kf.get("eligibility_known"):
            lines.append("")
            lines.append("I couldn't resolve which other machines are capable "
                         "of this operation, so I can't tell you whether "
                         "moving it to another lane is even an option.")
        elif kf.get("only_eligible"):
            lines.append("")
            lines.append(f"{machine} is the only machine capable of this "
                         "operation, so there is no other lane to move it to.")
        elif kf.get("alternatives") and not any(
                l.get("key") == "alternate" for l in levers):
            names = ", ".join(a.get("machine") for a in kf["alternatives"]
                              if a.get("machine"))
            lines.append("")
            lines.append(f"No other eligible machine ({names}) has {needed} of "
                         "open, unheld time any earlier either.")

        self._render_unpriceable(lines, kf)
        self._render_not_weighed(lines, kf)
        lines.append("")

    # -----------------------------------------------------------------
    # Session 4B.30 — THE LATER DIRECTION, voiced
    # -----------------------------------------------------------------

    def _render_later_move(self, lines: list[str],
                           bundle: ExplanationBundle) -> None:
        """"Can I move this later?" — the answer, or the refusal that says which.

        THE BAR — MEASURED, not authored. Live on the demo board, ORD-000208
        op30 on PAINT-01, a past-due order pushed out a day:

            Pushing ORD-000208 op30 out by "a day" puts it at Thursday
            2026-01-22 16:49 on PAINT-01.

            It costs +$600.00 (+0.028% of the plan's $2,127,482.58).
            Nothing else moves — every other job stays exactly where it is,
            which is the only reading under which this number is about YOUR
            move. …

            ORD-000208 finishes 2026-01-22 19:00 — 19d 19h past its due date
            (2026-01-02 23:59). 2d of that was already sunk before this plan
            opened and no placement can move it [R-PD1]; 17d 19h is what this
            schedule decides, against 16d 19h today.

        Everything above the fold is a FACT, not a hypothetical: the price holds
        every other placement exactly where it is, recomputes the whole ledger
        and re-validates the result by pinning all of it into a fresh model
        (4B.24). That is why this route may say "it costs" where the
        counterfactual must say "that removes the barrier" — a lever is a
        necessary condition, and a priced pin is a measurement.

        Authored, never LLM-reworded, and the reason is the refusal branches: a
        reword flattens SHUT into OCCUPIED and "we can't compute this" into "the
        plant won't take it", which are the two confusions this whole route
        exists to stop making."""
        kf = bundle.key_facts
        name = bundle.subject_external_name
        seq = kf.get("op_seq")
        op = f"op{seq}" if seq is not None else "this operation"
        machine = kf.get("machine")
        branch = kf.get("branch")

        if branch == "unplaced":
            lines.append(
                f"{name} has no placement in this window, so there is nothing "
                f"to push out. Ask \"why isn't {name} scheduled yet?\" and I'll "
                "answer that instead.")
            lines.append("")
            return

        if (kf.get("op_count") or 0) > 1 and not kf.get("op_named"):
            lines.append(f"Answering about {name} {op} on {machine} — the first "
                         f"of its {kf['op_count']} operations.")

        # -- (c) A LIMIT OF OURS, SAID AS ONE -------------------------------
        # The pricer declines a chunked move because the pauses are calendar
        # closures the solver placed and a local shift cannot re-derive them.
        # That is a fact about this product, and the sentence says so — a
        # planner told "it can't go there" would act on a claim about their
        # plant that nobody has tested (the CostProof `unreadable` species,
        # 4B.18; FeasibilityGhost `undetermined`, 4B.23).
        if branch == "chunked":
            n = kf.get("chunk_count") or 0
            lines.append(
                f"{name} {op} runs in {n} pieces on {machine} around calendar "
                f"closures, and I can't re-place split work as one move yet — "
                "the pauses are placements the solver made, and shifting the "
                "bar wouldn't tell me where the new ones go.")
            # Session 4B.28 Item 4(a): this used to end "Dragging the bar on the
            # board runs the full re-solve, which can." It does not, and it never
            # has — the board's drag was inert on a chunked bar (it panned), and
            # since this session it declines in these same words. ONE limit, said
            # the same way on both surfaces; pointing a planner at a second
            # surface that shares the limit is a redirection into the same wall.
            lines.append(
                "That is a limit of mine, not a ruling about your plant: I am "
                "not telling you the move is impossible, I am telling you I "
                "can't price it. Dragging the bar on the board declines for the "
                "same reason — it is one limit, not two surfaces disagreeing.")
            lines.append("")
            return

        # -- (d) COMMITTED / PINNED ----------------------------------------
        if branch == "frozen":
            if kf.get("frozen_reason") == "pinned":
                lines.append(
                    f"{name} {op} is pinned at {kf.get('frozen_until')} "
                    "[docs/05 A7/F1]. A pin is a decision somebody made about "
                    "this operation, and I won't quietly move work that is "
                    "being held on purpose — lift or move the pin and ask me "
                    "again.")
            else:
                lines.append(
                    f"{name} {op} starts {kf.get('start')}, inside the "
                    f"committed front of the plan (frozen until "
                    f"{kf.get('frozen_until')}) [docs/05 R-F1]. Committed work "
                    "does not move as the plan rolls — that is what committing "
                    "it means — so there is no later slot for me to price. "
                    "Moving the frozen boundary is the gesture that changes "
                    "this, and it makes standing pins, not free work.")
            lines.append("")
            return

        target = kf.get("target") or {}
        self._render_later_target(lines, kf, target, name, op, machine)

        if branch == "priced":
            self._render_later_price(lines, kf, name, op)
        elif branch == "collision":
            self._render_later_collision(lines, kf, machine)
        elif branch == "precedence":
            self._render_later_precedence(lines, kf, name)
        elif branch == "closure":
            self._render_later_closure(lines, kf, machine)
        elif branch == "no-later-fit":
            lines.append(
                f"There is no later stretch of open, unheld time on {machine} "
                f"big enough for {_dur_min(kf.get('run_min'))} of work — not "
                "between where it sits and the end of what this schedule "
                "covers. Every opening after it is either shut, already taken, "
                "or too short.")
        elif branch == "beyond-grid":
            lines.append(
                f"But that is past the end of the grid this plan is laid out on "
                f"({kf.get('horizon_end')}), which is as far as anything is "
                "placed to the minute. Beyond that line work is carried in the "
                "coarse look-ahead a week at a time, so I can tell you the "
                "operation would sit out there and I cannot price it to the "
                "cent — the detail a price is made of does not exist there.")
        elif branch == "model-refused":
            lines.append(
                "The scheduler refuses that placement with every other job "
                "held where it is, and no rule I check explains why. The "
                "refusal is real; the reason is one I can't name, and I would "
                "rather say that than invent one.")
        else:
            lines.append(
                "I couldn't price that move: "
                + (kf.get("price_error") or "the plan I price against could "
                   "not be loaded")
                + ". That is a failure of mine, not a verdict on the move.")
        lines.append("")

    @staticmethod
    def _render_later_target(lines: list[str], kf: dict, target: dict,
                             name: str, op: str, machine: str) -> None:
        """WHICH INSTANT I TESTED, and how I got there from what you said.

        The 4B.16 precedent, and 4B.15 Item 0's cost: a weekday in a five-Monday
        horizon is not an anchor, so the answer names the weekday AND the date,
        every time. A snap, an ambiguity and a fallback each say so — there is
        no shape of this paragraph that resolves silently."""
        if not target or not target.get("at"):
            return
        kind = target.get("kind")
        when = f"{target.get('at_weekday')} {target.get('at')}"
        raw = target.get("raw") or ""

        if kind == "after-closure":
            clo = target.get("closure") or {}
            reason = str(clo.get("reason", "closure")).replace("_", " ")
            lines.append(
                f"Pushing {name} {op} out to {when} — the first time {machine} "
                f"is open after the {reason} it would be waiting on "
                f"({clo.get('start')} to {clo.get('end')}).")
        elif kind == "named-day":
            lines.append(f"Testing {name} {op} at {when} on {machine}"
                         + (f" — you said \"{raw}\"." if raw else "."))
            if target.get("ambiguous"):
                lines.append(
                    f"There are {target.get('instances')} of that weekday "
                    "still ahead of where it sits, and I took the first one. "
                    "Name a date if you meant a different one.")
        elif kind == "magnitude":
            lines.append(f"Pushing {name} {op} out by \"{raw}\" puts it at "
                         f"{when} on {machine}.")
        else:
            lines.append(
                f"The next place {name} {op} could sit on {machine} is {when} "
                "— the first opening after where it is now with room for the "
                "whole operation.")
            if target.get("fell_back") and raw:
                lines.append(
                    f"I could not resolve \"{raw}\" against this machine's "
                    "calendar, so that is the target I tested — not the one "
                    "you named.")

        if target.get("snapped_from"):
            lines.append(
                f"That is a snap forward: {target.get('snapped_from_weekday')} "
                f"{target.get('snapped_from')} is the literal reading and "
                f"{machine} is not open then, so the figures below are about "
                f"{when}.")
        lines.append("")

    @staticmethod
    def _render_later_price(lines: list[str], kf: dict, name: str,
                            op: str) -> None:
        """The three things a priceable later move states (Item 3)."""
        delta = kf.get("cost_delta_abs")
        lines.append(f"It costs {_signed_money(delta)}"
                     + (f" ({kf.get('cost_delta_pct'):+.3f}% of the plan's "
                        f"{_signed_money(kf.get('total_before')).lstrip('+')})"
                        if kf.get("cost_delta_pct") is not None
                        and kf.get("total_before") else "")
                     + ".")

        # WHAT IT DISPLACES. Under a held-world price this is usually empty, and
        # that is worth a sentence rather than a silence: the slot it leaves is
        # unused in THIS price because nothing was allowed to move into it, and
        # a deeper search might well refill it. An honest pointer at "search
        # deeper", never a promise about what it would find.
        affected = [a for a in (kf.get("affected_orders") or [])
                    if a.get("work_order") != name]
        if affected:
            lines.append("")
            lines.append(f"{len(affected)} other order(s) change:")
            for a in affected[:5]:
                lines.append(
                    f"  {a.get('work_order') or a.get('demand_ref')}  "
                    f"{_signed_money(a.get('tardiness_delta'))} tardiness, "
                    f"{a.get('lateness_delta_min'):+d} min")
        else:
            lines.append(
                "Nothing else moves — every other job stays exactly where it "
                "is, which is the only reading under which this number is "
                "about YOUR move. The slot it leaves behind is simply unused "
                "in this price; a deeper search might refill it, and that is a "
                "different question with a different answer.")

        # WHETHER THE DUE DATE SURVIVES — R-PD1 clause (4) vocabulary, and the
        # floor stated ONCE. A move cannot change what was already sunk when
        # the plan opened, so reporting the floor before and after would invite
        # a planner to subtract two equal numbers and read a decision into it.
        for s in (kf.get("subject_outcomes") or []):
            lines.append("")
            late_after = int(s.get("lateness_after_min") or 0)
            late_before = int(s.get("lateness_before_min") or 0)
            wo = s.get("work_order") or name
            if late_after <= 0:
                lines.append(
                    f"{wo} still finishes on time: {s.get('completion_after')}, "
                    f"{_span_min(-late_after)} before its due date "
                    f"({s.get('due')}).")
                continue
            floor = int(s.get("tardiness_floor_min") or 0)
            controllable_after = max(0, late_after - floor)
            controllable_before = max(0, late_before - floor)
            lines.append(
                f"{wo} finishes {s.get('completion_after')} — "
                f"{_span_min(late_after)} past its due date ({s.get('due')}).")
            if floor:
                lines.append(
                    f"  {_span_min(floor)} of that was already sunk before this "
                    "plan opened and no placement can move it [R-PD1]; "
                    f"{_span_min(controllable_after)} is what this schedule "
                    f"decides, against {_span_min(controllable_before)} today.")
            else:
                lines.append(
                    f"  All of it is controllable — it was due inside this "
                    f"plan. Today it is {_span_min(late_before)} late.")
            lines.append(
                f"  Tardiness on this order: "
                f"{_signed_money(round(float(s.get('tardiness_after') or 0.0) - float(s.get('tardiness_before') or 0.0), 2))}"
                f" (${float(s.get('tardiness_before') or 0.0):,.2f} → "
                f"${float(s.get('tardiness_after') or 0.0):,.2f}).")

        lines.append("")
        lines.append(
            "Held-world price: every other placement pinned where it is, the "
            "whole ledger recomputed, and the result re-checked against the "
            f"scheduler ({kf.get('validation_status')}). It is what this move "
            "costs, not what the best plan containing it would cost.")

    @staticmethod
    def _render_later_collision(lines: list[str], kf: dict,
                                machine: str) -> None:
        """(a) SOMETHING IS ALREADY THERE — with its name, and a real offer."""
        ref = kf.get("refusal") or {}
        who = ", ".join(ref.get("other_work_orders") or []) or "another job"
        lines.append(
            f"Not there: {machine} is already carrying {who} at that time.")
        # SHUT IS NOT OCCUPIED (4B.24, R-T2 amendment clause 2's discipline).
        # This refusal exists only because the price holds the occupant still —
        # so it is "not without moving other work", never "no".
        if ref.get("holds_others"):
            lines.append(
                "That is a refusal about this price, not about your plant: I "
                "hold every other job exactly where it is, so a slot somebody "
                "else is in is closed to me. The full re-solve is free to move "
                "them, and might.")
        TemplateRenderer._render_later_alternative(lines, kf, machine)

    @staticmethod
    def _render_later_precedence(lines: list[str], kf: dict,
                                 name: str) -> None:
        """The order's own next step is already booked in front of it."""
        ref = kf.get("refusal") or {}
        lines.append(
            f"Not there: a later start would run {name} straight into the next "
            f"step of its own routing, which is already scheduled from "
            f"{ref.get('at')} [docs/05 A1/A2].")
        lines.append(
            "Offering you a still-later slot would make that worse, not "
            "better, so I am not offering one. What moves this is moving the "
            "downstream step too — a two-operation change I price one bar at a "
            "time and therefore cannot price as one gesture.")

    @staticmethod
    def _render_later_closure(lines: list[str], kf: dict,
                              machine: str) -> None:
        """(b) THE MACHINE IS SHUT — and shut is a different fact from busy."""
        ref = kf.get("refusal") or {}
        target = kf.get("target") or {}
        clo = target.get("closure") or {}
        reason = str(clo.get("reason", "")).replace("_", " ")
        lines.append(
            f"Not there: {machine} is not open then"
            + (f" — {reason} from {clo.get('start')} to {clo.get('end')}."
               if reason else ". " + str(ref.get("sentence", "")).strip() + "."))
        lines.append(
            "That is the calendar, not congestion: nobody is in the way, the "
            "machine simply is not running. Declared overtime or a shift "
            "extension is what changes it, and I won't guess what hours the "
            "plant would open on a day it has declared shut.")
        TemplateRenderer._render_later_alternative(lines, kf, machine)

    @staticmethod
    def _render_later_alternative(lines: list[str], kf: dict,
                                  machine: str) -> None:
        """The RECOMPUTED next opening, priced — or an honest account of why it
        is not on offer. Computed from the calendar, never assumed to be the
        minute after the obstacle."""
        at = kf.get("alternative_at")
        if not at:
            beyond = kf.get("alternative_beyond_window")
            lines.append("")
            if beyond:
                lines.append(
                    f"The next opening that would take it is {beyond}, past "
                    f"the end of the planned grid ({kf.get('horizon_end')}) — "
                    "out where the plan is coarse and I can't price to the "
                    "cent.")
            else:
                lines.append(
                    f"And there is no later opening on {machine} with room "
                    "for the whole operation, so I have nothing else to offer "
                    "you here.")
            return
        alt = kf.get("alternative") or {}
        lines.append("")
        lines.append(
            f"The next opening that WOULD take it is "
            f"{kf.get('alternative_weekday')} {at}"
            + (f", and that one costs "
               f"{_signed_money(alt.get('cost_delta_abs'))}."
               if alt else "."))
        if alt:
            subject = kf.get("order")
            others = [a for a in (alt.get("affected_orders") or [])
                      if a.get("work_order") != subject]
            lines.append(
                f"  {len(others)} other order(s) change there."
                if others else "  Nothing else moves there either.")
        elif kf.get("alternative_refusal") or kf.get("alternative_error"):
            lines.append(
                "  I could not price that one either: "
                + ((kf.get("alternative_refusal") or {}).get("sentence")
                   or kf.get("alternative_error") or "no reason given") + ".")

    @staticmethod
    def _render_unpriceable(lines: list[str], kf: dict) -> None:
        """What this route will NOT put a number on, and why (Session 4B.16).

        The 4B.14 precedent, applied to relaxations: a change whose effect can
        only be known by re-solving is NAMED rather than estimated. Saying
        nothing would let the list of levers read as exhaustive."""
        unp = kf.get("unpriceable") or []
        if not unp:
            return
        lines.append("")
        lines.append("Can't be priced as a change (it would take a re-solve): "
                     + "; ".join(f"{u.get('catalog', '?')} "
                                 f"{_family_gist(u.get('why', ''))}"
                                 for u in unp) + ".")

    @staticmethod
    def _render_not_weighed(lines: list[str], kf: dict) -> None:
        """R-AI3(1): the families this reading did not weigh. Carried verbatim
        from the blocker analysis, because a counterfactual that ignores
        B3/B5, B7/B8, C4 and F3 is exactly as partial as the explanation was."""
        unc = kf.get("uncomputed") or []
        if not unc:
            return
        lines.append("")
        lines.append("Not weighed here (docs/05): "
                     + "; ".join(f"{u.get('catalog', '?')} "
                                 f"{_family_gist(u.get('why', ''))}"
                                 for u in unc) + ".")

    @staticmethod
    def _challenge_lead(kf: dict, verdict: str, binding: dict) -> str:
        """The opening sentence of an answer to a CHALLENGE (Item 3).

        It concedes exactly what the analysis concedes and no more. Three cases,
        and the concession in each is computed, never a courtesy:

          * verdict `chose` — the planner is RIGHT. Nothing prevented an earlier
            start. Say it first and plainly; burying a correction under a
            paragraph of agreement-shaped prose is the same failure in a
            politer register.
          * the binding family is NOT `resource` — then contention was not the
            cause, so "the machine was free" is TRUE and is conceded with the
            instant it was free from. That is the specimen's own case: the
            planner said op20 should be able to start Tuesday after op10, and
            PAINT-01 genuinely was free all Tuesday afternoon.
          * otherwise the machine really was held, and the honest lead says the
            record does not agree rather than manufacturing something to concede.
        """
        machine = kf.get("machine")
        if verdict == "chose":
            return ("You're right, and I'll correct what I said: nothing in the "
                    "plan prevented an earlier start.")
        if verdict == "undetermined":
            return ("I can't settle this one either way — my own earliest-start "
                    "estimates don't line up with where it actually sits.")
        est = {e.get("family"): e for e in (kf.get("estimates") or []) if e}
        res = est.get("resource") or {}
        if binding.get("family") != "resource" and res.get("at"):
            return (f"You're right about the machine: {machine} wasn't busy — it "
                    f"was free from {res['at']}. That isn't what held this up.")
        return (f"The record doesn't agree, and here is what it shows — "
                f"{machine} really was held.")

    @staticmethod
    def _closure_note(kf: dict) -> str:
        """"...after maintenance" — the target sentence's closing clause.

        Only stated when a DECLARED closure actually stands between the near miss
        and the placement (the analysis puts it there and nowhere else). A
        maintenance day that delayed nothing is not part of the cause, and naming
        it would be the same over-claim this route exists to end."""
        binding = kf.get("binding") or {}
        cl = (binding.get("facts") or {}).get("closure") or {}
        if not cl.get("start"):
            return ""
        reason = str(cl.get("reason") or "closure").replace("_", " ")
        return (f"The wait spans {reason} on {kf.get('machine')}, "
                f"{cl['start']} to {cl['end']}.")

    def _render_unknown_entity(self, lines: list[str], bundle: ExplanationBundle) -> None:
        kf = bundle.key_facts
        token = kf.get("mention", "that order")
        if kf.get("excluded") and kf.get("finding"):
            c = kf["finding"]
            lines.append(
                f"{token} isn't in this schedule — it was excluded before the "
                f"solve. {c['cause']}.")
            if c.get("fix"):
                lines.append(f"Fix: {c['fix']}")
        elif kf.get("mention_kind") == "machine":
            # 4B.13: name the right vocabulary. Calling an unknown MACHINE an
            # unknown order, and then listing orders, tells the planner their
            # machine name is an order id.
            #
            # Session 4B.19 Item 3. This block used to read "The machines here
            # are: " over a HEAD SLICE of eight — a sentence that claims to be
            # the plant while naming barely half of it, and on the measured
            # specimen it dropped both the machine the asked order runs on and
            # the two the planner most plausibly meant. Now: near matches where
            # there are any, the TOTAL always, and a pointer at the route that
            # does enumerate. No truncated list is presented as complete.
            lines.append(f"There's no machine called {token} in this plant.")
            near = kf.get("known_machines") or []
            total = kf.get("machine_total") or 0
            if near:
                lines.append(_did_you_mean(near))
            if total:
                lines.append(f"There are {total} machines here — ask \"list the "
                             f"machines\" for all of them.")
        else:
            lines.append(f"{token} isn't in this schedule — I don't see it among "
                         "the planned orders.")
            near = kf.get("known_orders") or []
            total = kf.get("order_total") or 0
            if near:
                lines.append(_did_you_mean(near))
            if total:
                # Session 4B.19 Item 3(b). "Orders I do have include: …" over a
                # [:6] head slice never claimed completeness, but it never gave
                # the total either, so a planner had no way to tell six from six
                # hundred. The count is the cheap half of the floor.
                # Session 4B.21 — "known" names the set. This is every demand
                # the plan carries, placed or not; the opener's count on the
                # same board is the placed subset, and the two disagree by
                # design rather than by accident.
                lines.append(f"There are {total} known orders in this plan — "
                             f"ask \"how many orders are in the plan?\" for the "
                             f"breakdown and \"show the full schedule\" for the "
                             f"list.")
        lines.append("")

    def _render_briefing(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """THE OPENER, voiced (Session 4B.16 Item 2).

        Ranked by consequence, every line carrying its number, and the pointer
        that opens each item up. The clean case is a real answer — "three
        things, and none of them are on fire" — because a board with nothing
        wrong deserves to be told so rather than to receive a silence a planner
        has to interpret."""
        kf = bundle.key_facts
        opener = kf.get("opener")
        if opener:
            self._render_opener(lines, kf, opener)
            return
        fires = kf.get("fires", [])
        if not fires:
            # Session 4B.21 — SCOPED. This branch is reached only when the
            # opener could not be built at all, which does not make a
            # plan-wide universal any safer: on a rolling board the orders
            # beyond the horizon have no completion date to be on track for.
            lines.append("Nothing is late today — every order with a "
                         "placement is on track.")
        else:
            lines.append(f"{len(fires)} order(s) need attention today, worst first:")
            lines.append("")
            for f in fires:
                mins = int(f["lateness_minutes"])
                tag = f" · {f['priority']}" if f.get("priority") and f["priority"] != "standard" else ""
                # Item 5(b): same formatter.
                line = f"  • {f['order']} — {elapsed_minutes(mins)} late{tag}"
                blk = f.get("blocked_by")
                if blk:
                    line += (f" (held behind {blk['blocker_order']} on "
                             f"{blk['machine']})")
                lines.append(line)
            if kf.get("common_cause"):
                lines.append("")
                lines.append(f"Common thread: {kf['common_cause']}.")
        # the one data-quality item that matters
        dq = kf.get("top_data_quality")
        if dq:
            lines.append("")
            extra = ""
            if kf.get("finding_count", 0) > 1:
                extra = f" (plus {kf['finding_count'] - 1} more)"
            lines.append(f"Data to watch: {dq['cause']}{extra}.")
            if dq.get("fix"):
                lines.append(f"  Fix: {dq['fix']}")
        self._render_excluded_note(lines, bundle)
        lines.append("")

    @staticmethod
    def _render_opener(lines: list[str], kf: dict, items: list[dict]) -> None:
        """The ranked board read. Worries first, in rank order; the reassurance
        after them; then what could not be computed at all."""
        worries = [i for i in items if not i.get("clean")]
        clean = [i for i in items if i.get("clean")]
        scope = kf.get("opener_scope") or {}
        where = ""
        if scope.get("window_start") and scope.get("window_end"):
            where = (f" over {scope['window_start']} to "
                     f"{scope['window_end']}")
        counts = ""
        if scope.get("orders") and scope.get("machines"):
            # Session 4B.21 — the word "scheduled" is load-bearing. This figure
            # is the PLACED order count; `inventory` states the KNOWN one, and
            # a planner reading "26 orders" here and "40 orders" there had
            # nothing on either surface telling them the sets differ.
            counts = (f"{scope['orders']} scheduled orders on "
                      f"{scope['machines']} machines{where}. ")

        if not worries:
            lines.append(f"{counts}Nothing on this board needs your attention "
                         "— and that is a real answer, not a silence:")
        else:
            n = len(worries)
            lines.append(f"{counts}{n} thing{'s' if n != 1 else ''} worth your "
                         f"attention, worst first:")
        lines.append("")
        for n, item in enumerate(worries, start=1):
            lines.append(f"{n}. {item.get('headline')}")
            for d in item.get("detail") or []:
                lines.append(f"     {d}")
            if item.get("pointer"):
                lines.append(f"     -> {item['pointer']}")
            lines.append("")
        if clean:
            if worries:
                lines.append("And what is going right:")
            for item in clean:
                lines.append(f"  · {item.get('headline')}")
            lines.append("")

        # WHAT THIS READ COULD NOT SEE. An opener that silently drops a
        # category reads as a clean bill of health for it, which is the exact
        # failure this session is about.
        gaps = kf.get("opener_unavailable") or []
        if gaps:
            lines.append("Not covered by this read:")
            for g in gaps:
                lines.append(f"  · {g.get('what')} — {g.get('why')}.")
            lines.append("")

    def _render_open_card(self, lines: list[str], card: dict) -> None:
        """Session 4B.5 CU2 — the OPEN DELTA CARD, read back.

        Every number here came off the sandbox result the card is already showing.
        Nothing is recomputed, nothing is looked up, and the composition order is
        the card's own — so the answer and the surface can never drift apart. If
        they ever do, one of them is wrong, and this renderer is the reason it
        cannot be this one.

        Which PART of the card the planner asked about is deliberately not
        classified: "the delta", "these orders" and "this move" would need a
        keyword table to separate, and the card is small enough to say whole."""
        from mre.modules.ask_fallback_copy import (
            OPEN_CARD_AFFECTED_LEAD, OPEN_CARD_AFFECTED_NONE,
            OPEN_CARD_AFFECTED_ROW, OPEN_CARD_BOUNDARY,
            OPEN_CARD_CLOSED, OPEN_CARD_COMMITTED_SAFE,
            OPEN_CARD_CONSEQUENCES, OPEN_CARD_CONSEQUENCES_NONE,
            OPEN_CARD_DRIVER, OPEN_CARD_INFEASIBLE, OPEN_CARD_LATENESS_BETTER,
            OPEN_CARD_LATENESS_NONE, OPEN_CARD_LATENESS_WORSE, OPEN_CARD_LEAD,
            OPEN_CARD_NO_PRICE, OPEN_CARD_PLACEMENT, OPEN_CARD_PLACEMENT_BARE,
            OPEN_CARD_SPLIT, OPEN_CARD_UNSPLIT,
        )
        if not card or not card.get("open"):
            lines.append(OPEN_CARD_CLOSED)
            lines.append("")
            return

        # A refused placement has no price and no consequences to read back — the
        # card's whole content is the refusal and the fact that nothing changed.
        if card.get("feasible") is False or card.get("outcome") == "no_verdict":
            msg = (card.get("message") or "").strip()
            lines.append(OPEN_CARD_INFEASIBLE.format(
                message=(msg + "." if msg and not msg.endswith(".") else msg)
                        or "the sandbox could not place it there."))
            lines.append("")
            return

        lines.append(OPEN_CARD_LEAD)
        machine = card.get("machine")
        when = f" at {card['when']}" if card.get("when") else ""
        if machine:
            order = card.get("order")
            lines.append(OPEN_CARD_PLACEMENT.format(
                order=order, machine=machine, when=when) if order
                else OPEN_CARD_PLACEMENT_BARE.format(machine=machine, when=when))

        total = card.get("cost_delta_abs")
        if total is None:
            lines.append(OPEN_CARD_NO_PRICE)
        elif (card.get("attribution") == "split"
              and card.get("reopt_delta_abs") is not None
              and card.get("move_delta_abs") is not None):
            lines.append(OPEN_CARD_SPLIT.format(
                total=_signed_money(total),
                reopt=_signed_money(card["reopt_delta_abs"]),
                move=_signed_money(card["move_delta_abs"])))
        else:
            lines.append(OPEN_CARD_UNSPLIT.format(total=_signed_money(total)))

        lines.append("")
        affected = [a for a in (card.get("affected_orders") or []) if a]
        if affected:
            lines.append(OPEN_CARD_AFFECTED_LEAD.format(n=len(affected)))
            for a in affected:
                lines.append(OPEN_CARD_AFFECTED_ROW.format(
                    order=a.get("work_order") or "an order",
                    effect=_affected_effect(a)))
        else:
            lines.append(OPEN_CARD_AFFECTED_NONE)

        lateness = card.get("lateness_delta_min")
        if lateness:
            hours = round(abs(int(lateness)) / 60.0, 1)
            lines.append(OPEN_CARD_LATENESS_WORSE.format(hours=hours)
                         if lateness > 0
                         else OPEN_CARD_LATENESS_BETTER.format(hours=hours))
        else:
            lines.append(OPEN_CARD_LATENESS_NONE)

        moves = card.get("moves")
        if isinstance(moves, int):
            # the card counts the PINNED op among its moved-set; the planner's
            # "what else moved" is the rest of it.
            others = max(0, moves - 1)
            lines.append(OPEN_CARD_CONSEQUENCES.format(n=others) if others
                         else OPEN_CARD_CONSEQUENCES_NONE)
        if card.get("no_committed_work_changes"):
            lines.append(OPEN_CARD_COMMITTED_SAFE)

        driver = card.get("dominant_driver") or {}
        if driver.get("phrase"):
            phrase = driver["phrase"]
            hedge = (driver.get("hedge") or "").strip()
            lines.append("")
            lines.append(OPEN_CARD_DRIVER.format(
                phrase=phrase + (f" {hedge}" if hedge else "")))

        lines.append("")
        lines.append(OPEN_CARD_BOUNDARY)
        lines.append("")

    def _render_contested(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU6 / R-AI3(4) — warm evidence, never capitulation, never hardening.
        Restate what the record shows and offer to walk the chain."""
        kf = bundle.key_facts
        order = kf.get("order", "that order")
        lateness = kf.get("lateness_minutes")
        due = kf.get("due")
        due_clause = f" (due {due})" if due else ""
        if kf.get("is_late") and kf.get("claims_not_late"):
            # contested-wrong: hold, warmly, on the evidence.
            mins = int(lateness) if lateness is not None else 0
            lines.append(
                f"I can see why you'd hope so, but the record has {order} finishing "
                f"{mins} minutes past its due date{due_clause} — I'm not going to "
                "call it on time when the evidence says otherwise.")
            lines.append(
                f"Happy to walk the chain with you though: ask \"why is {order} "
                "late?\" and I'll show exactly what held it up.")
        elif (not kf.get("is_late")) and (not kf.get("claims_not_late")) \
                and lateness is not None:
            # the user thinks it's late; the record says it isn't — good news, warmly.
            early = abs(int(lateness))
            span = (f"{round(early / 1440, 1)} day(s)" if early >= 1440
                    else f"{round(early / 60, 1)}h" if early >= 60
                    else f"{early} minute(s)")
            lines.append(
                f"Good news — the record actually has {order} finishing on time, "
                f"{span} early{due_clause}, not late.")
            lines.append(
                f"Want the detail? Ask \"when does {order} finish?\" and I'll show "
                "the timeline.")
        else:
            # the record AGREES with the user — confirm plainly, still offer the chain.
            if kf.get("is_late"):
                mins = int(lateness) if lateness is not None else 0
                lines.append(
                    f"Yes — the record agrees: {order} finishes {mins} minutes "
                    f"late{due_clause}.")
                lines.append(f"Ask \"why is {order} late?\" for the cause chain.")
            else:
                lines.append(
                    f"Yes — the record agrees: {order} finishes on time{due_clause}.")
        lines.append("")

    @staticmethod
    def _render_why_machine_scope(lines: list[str], kf: dict) -> None:
        """WHAT THIS ANSWER IS ABOUT, AND WHAT IT LEFT OUT (Session 4B.21 Item 3).

        The chain under a why-on-machine lead is now scoped to the ONE
        operation the lead explains. Narrowing silently is the same defect as
        widening silently — a planner who asked about a two-step order and got
        one record has no way to tell a scoped answer from a thin one. So the
        scope is stated, with the question that opens the rest."""
        if not kf.get("scoped_to_operation"):
            return
        seq = kf.get("op_seq")
        others = int(kf.get("other_step_count") or 0)
        if seq is not None:
            lines.append(
                f"This is about op{seq} on {kf.get('machine_ref', '?')}; the "
                f"evidence below is that step's own assignment decision.")
        if others:
            lines.append(
                f"{kf.get('order', 'This order')} has {others} other step(s) "
                f"in this window, each with its own machine and its own reason "
                f"— ask about one by naming it (e.g. \"why is "
                f"{kf.get('order', '<order>')} op<seq> on <machine>?\").")

    def _render_inventory(self, lines: list[str],
                          bundle: ExplanationBundle) -> None:
        """THE COUNTS, EACH NAMING ITS DISPOSITION (Session 4B.21).

        Three sentences that used to carry three different denominators with
        none of them named, plus a universal quantified over a set 14 of whose
        members have no completion date. Each figure now arrives from
        ``order_disposition.census`` under a field that states its set, and the
        prose says which set it is speaking about.

        THE MONOLITHIC BRANCH IS NOT A DEGRADED ROLLING BRANCH. With no horizon
        there is no beyond-horizon region, the scheduled set IS the admitted
        set, and a plan-wide universal is honest — so it is said plainly rather
        than hedged with a distinction that does not exist there."""
        from mre.modules.ask_fallback_copy import (
            INVENTORY_EXCLUDED, INVENTORY_LATE, INVENTORY_MONOLITHIC,
            INVENTORY_ON_TIME_MONOLITHIC, INVENTORY_ON_TIME_ROLLING,
            INVENTORY_PARTITION_BROKEN, INVENTORY_ROLLING,
            INVENTORY_SPLITTABLE, INVENTORY_SPLITTABLE_MONOLITHIC,
            INVENTORY_SPLITTABLE_NONE, INVENTORY_UNREADABLE,
        )
        kf = bundle.key_facts
        known = int(kf.get("known_order_count") or 0)
        sched = int(kf.get("scheduled_order_count") or 0)
        beyond = kf.get("beyond_horizon_order_count")
        excluded = int(kf.get("excluded_order_count") or 0)
        placed_ops = int(kf.get("placed_operation_count") or 0)
        declared_ops = int(kf.get("declared_operation_count") or 0)
        d_split = int(kf.get("splittable_declared_count") or 0)
        p_split = int(kf.get("splittable_placed_count") or 0)
        rolling = bool(kf.get("rolling")) and beyond is not None
        # Session 4B.21, found live: a route reached WITHOUT the document
        # cannot read the beyond-horizon region at all, and "cannot read" is
        # not "empty". Saying "26 orders are scheduled in this plan" there
        # would be the same fusion in reverse — a monolithic sentence over a
        # rolling board, silently dropping 14 admitted orders.
        if kf.get("dispositions_partition") is None:
            lines.append(INVENTORY_UNREADABLE.format(
                scheduled=sched, placed_ops=placed_ops, known=known))
            lines.append("")
            return

        # The partition is checked BEFORE any figure is spoken. A total that
        # does not add up is a fact about this document, and saying it plainly
        # is the honest floor — picking one of the numbers is not.
        if kf.get("dispositions_partition") is False:
            lines.append(INVENTORY_PARTITION_BROKEN.format(
                scheduled=sched, beyond=beyond or 0, excluded=excluded,
                known=known))
            lines.append("")
            return

        if rolling and beyond:
            lines.append(INVENTORY_ROLLING.format(
                known=known, scheduled=sched, placed_ops=placed_ops,
                beyond=beyond))
        else:
            lines.append(INVENTORY_MONOLITHIC.format(
                scheduled=sched, placed_ops=placed_ops))
        if excluded:
            lines.append(INVENTORY_EXCLUDED.format(excluded=excluded))

        if not d_split:
            lines.append(INVENTORY_SPLITTABLE_NONE)
        elif declared_ops and declared_ops != placed_ops:
            # The declared set is larger than the placed set, so the two
            # denominators are genuinely different and both are named.
            lines.append(INVENTORY_SPLITTABLE.format(
                declared_split=d_split, declared_ops=declared_ops,
                placed_split=p_split))
        else:
            lines.append(INVENTORY_SPLITTABLE_MONOLITHIC.format(
                declared_split=d_split))

        late = int(kf.get("late_count") or 0)
        if late:
            lines.append(INVENTORY_LATE.format(late=late, scheduled=sched))
        elif rolling and beyond:
            lines.append(INVENTORY_ON_TIME_ROLLING.format(
                scheduled=sched, beyond=beyond))
        else:
            lines.append(INVENTORY_ON_TIME_MONOLITHIC)
        self._render_partial_placement(lines, kf)
        self._render_excluded_note(lines, bundle)
        lines.append("")

    @staticmethod
    def _render_partial_placement(lines: list[str], kf: dict) -> None:
        """IS IT ALL-IN OR ALL-OUT PER ORDER (Session 4B.22 Item B3).

        4B.21 measured this question live and recorded that the answer given was
        true and about something else: the planner asked whether an order can be
        PARTIALLY placed, and `inventory` answered how many orders are placed. The
        figures are now computed per order, and the sentence keeps the one
        distinction that matters — MEASURED ON THIS BOARD is not INVARIANT, and
        4B.21's whole ruling is that a surface says which.

        Silent when unreadable. Three absent figures are not three zeros, and
        "no order is partly placed" is exactly the claim that must not be
        manufactured out of a chain we could not walk."""
        from mre.modules.ask_fallback_copy import (
            INVENTORY_ALL_OR_NOTHING, INVENTORY_ALL_OR_NOTHING_LIMIT,
            INVENTORY_PARTLY_PLACED,
        )
        aon = kf.get("placement_all_or_nothing")
        if aon is None:
            return
        full = int(kf.get("fully_placed_order_count") or 0)
        part = int(kf.get("partly_placed_order_count") or 0)
        none_ = int(kf.get("unplaced_order_count") or 0)
        lines.append("")
        if aon:
            lines.append(INVENTORY_ALL_OR_NOTHING.format(
                full=full, unplaced=none_))
        else:
            lines.append(INVENTORY_PARTLY_PLACED.format(
                partly=part, full=full, unplaced=none_))
        lines.append(INVENTORY_ALL_OR_NOTHING_LIMIT)

    def _render_excluded_note(self, lines: list[str], bundle: ExplanationBundle) -> None:
        """CU9 — a schedule with exclusions volunteers them in relevant answers
        so the certificate silence is inverted into a trust feature."""
        kf = bundle.key_facts
        ex = kf.get("excluded_summary")
        if ex and ex.get("count"):
            lines.append("")
            names = ", ".join(ex.get("orders", [])[:4])
            more = "" if len(ex.get("orders", [])) <= 4 else " …"
            lines.append(
                f"Note: {ex['scheduled']} of {ex['total']} orders are scheduled; "
                f"{ex['count']} excluded ({names}{more}) — ask \"why was "
                f"{ex['orders'][0]} excluded?\" for the reason.")

    def _render_register_body(self, bundle: ExplanationBundle) -> str:
        from mre.modules.remediation import render_remediation_body
        from mre.modules.triage import render_triage_body

        findings = bundle.ordered_records
        if bundle.subject_type == "remediation":
            limit = bundle.key_facts.get("limit")
            return "\n" + render_remediation_body(findings, limit=limit)
        return "\n" + render_triage_body(findings)

    def _render_diff(self, lines: list[str], kf: dict) -> None:
        snap_a = kf.get("snapshot_a", "?")
        snap_b = kf.get("snapshot_b", "?")
        lines.append(f"Comparing {snap_a} -> {snap_b}")
        lines.append("")

        removed = kf.get("removed_demands", [])
        added = kf.get("added_demands", [])
        changed = kf.get("changed_demands", [])
        cm = kf.get("costmodel_diff", {})

        if removed:
            lines.append(f"Removed demands ({len(removed)}):")
            for wo in removed:
                lines.append(f"  - {wo}")
        if added:
            lines.append(f"Added demands ({len(added)}):")
            for wo in added:
                lines.append(f"  + {wo}")
        if changed:
            lines.append(f"Changed demands ({len(changed)}):")
            for c in changed:
                lines.append(
                    f"  ~ {c['work_order']}  | {c['field']}: "
                    f"{c['from']} -> {c['to']}"
                )

        if cm.get("rate_changes"):
            v_a = cm.get("version_a")
            v_b = cm.get("version_b")
            lines.append(
                f"Cost model v{v_a} -> v{v_b} "
                f"({len(cm['rate_changes'])} rate change(s)):"
            )
            for name, chg in sorted(cm["rate_changes"].items()):
                lines.append(f"  ~ {name}: {chg['from']} -> {chg['to']}")

        if not (removed or added or changed or cm.get("rate_changes")):
            lines.append("  (no differences found)")

    def _render_record(
        self,
        lines: list[str],
        idx: int,
        rec: dict,
        identity_map: Any,
        driver_superseded: bool = False,
    ) -> None:
        rt = rec.get("record_type", "?")
        module = rec.get("module", "?")
        rid_short = (rec.get("record_id") or "?")[:8]

        if rt == "decision":
            self._render_decision(lines, idx, rec, module, rid_short, identity_map,
                                  driver_superseded=driver_superseded)
        elif rt == "metric":
            self._render_metric(lines, idx, rec, module, rid_short, identity_map)
        elif rt == "finding":
            self._render_finding(lines, idx, rec, module, rid_short)
        elif rt == "event":
            lines.append(f"[{idx}] EVENT ({stage_name(module)})")
            msg = (rec.get("message") or "")[:120]
            if msg:
                lines.append(f"    {msg}")
            lines.append(f"    [record: {rid_short}...]")
        else:
            lines.append(f"[{idx}] {rt.upper()} ({stage_name(module)})")
            lines.append(f"    [record: {rid_short}...]")
        lines.append("")

    def _render_decision(
        self, lines, idx, rec, module, rid_short, identity_map,
        driver_superseded: bool = False,
    ) -> None:
        dt = (rec.get("decision_type") or "?").upper()
        driver = rec.get("driver", "?")
        basis = rec.get("basis", "?")
        lines.append(f"[{idx}] DECISION  | {dt}  ({stage_name(module)})")

        if dt == "DEMAND_MERGE":
            subjects = rec.get("subjects", [])
            wo_names = [
                _resolve_name(s.get("entity_id", ""), "demand", identity_map)
                for s in subjects
            ]
            if wo_names:
                lines.append(f"    Batched: {', '.join(wo_names)}")
            chosen = rec.get("chosen") or {}
            benefit = chosen.get("estimated_benefit") or chosen.get("estimated_saving")
            if benefit is not None:
                lines.append(f"    Driver: {driver}  - estimated benefit: {float(benefit):.1f}")
            else:
                lines.append(f"    Driver: {driver}")
            alts = rec.get("alternatives") or []
            for alt in alts[:3]:
                lines.append(
                    f"    Alternative: {alt.get('option','?')}  - {alt.get('consequence','?')}"
                )
            # Session 4B.19 Item 3(b): the decision record weighed more options
            # than the chain shows. Say how many, or the chain understates what
            # was considered without saying it did.
            if len(alts) > 3:
                lines.append(f"    …and {len(alts) - 3} further alternative(s) "
                             f"recorded ({len(alts)} in all).")

        elif dt == "ASSIGNMENT":
            chosen = rec.get("chosen") or {}
            resource_id = chosen.get("resource_id", "")
            resource_name = _resolve_name(resource_id, "resource", identity_map)
            lines.append(f"    Assigned to: {resource_name}")
            phrase = driver_phrase(driver)
            # SESSION 4B.21 ITEM 3(b) — "Why:" CLAIMED THIS WAS THE REASON.
            #
            # It is a transcription of the record's `driver` field, and the
            # third seam of a class fixed twice already (4B.5 CU3 at the
            # assembler, 4B.13 at the lead). Under a lead that had just said
            # "there was no alternative to weigh", the chain read "Why: the
            # machine was busy with other work" — two incompatible reasons for
            # one placement, one line apart, each in the product's own voice.
            #
            # The label now claims only what is checkable: this is the driver
            # code the assignment Decision carries. A bare DRIVER_PHRASING
            # clause is not an explanation and no longer poses as one.
            lines.append(f"    Recorded driver: {phrase}" if phrase
                         else f"    Recorded driver: {driver}")
            if driver_superseded:
                # The lead was computed from the solved occupancy and the
                # capability registry; the code above is what the extractor
                # attributed. Where they disagree the reader is told which is
                # which rather than left to reconcile two sentences.
                lines.append(
                    "    (the sentence above this chain is computed from the "
                    "solved occupancy and supersedes this code)")
            if basis == "reconstructed":
                lines.append(
                    "    Note: This is a reconstruction from the solved schedule."
                )
            alts = rec.get("alternatives") or []
            for alt in alts[:4]:
                opt = alt.get("option", "")
                alt_id = opt.replace("resource:", "")
                alt_name = _resolve_name(alt_id, "resource", identity_map) if alt_id else opt
                consequence = alt.get("consequence", "")
                lines.append(f"    Alternative: {alt_name}  - {consequence}")
            # Session 4B.19 Item 3(b) — same floor on the eligible-machine list.
            if len(alts) > 4:
                lines.append(f"    …and {len(alts) - 4} further eligible "
                             f"machine(s) recorded ({len(alts)} in all).")

        else:
            # Same relabelling as the ASSIGNMENT branch above, for the same
            # reason: this is the record's driver field, not an explanation
            # anyone composed for this question.
            phrase = driver_phrase(driver)
            lines.append(f"    Recorded driver: {phrase}" if phrase
                         else f"    Recorded driver: {driver}")
            # CU6 — an INTERPRETATION decision's message is internal identity
            # plumbing ("identity_v1: demand <uuid> -> 1 WorkPackage"); it says
            # nothing a planner needs and only leaks jargon. Render a message
            # only when it survives the jargon strip as real planner content.
            msg = strip_jargon((rec.get("message") or "")[:160])
            if msg and len(re.sub(r"[^A-Za-z]", "", msg)) > 6 and not has_jargon(msg):
                lines.append(f"    {msg}")

        lines.append(f"    [record: {rid_short}...]")

    def _render_metric(self, lines, idx, rec, module, rid_short, identity_map) -> None:
        name = rec.get("name", "?")
        value = rec.get("value")
        unit = rec.get("unit", "")

        # Pre-convert epoch metrics → ISO so LLM never sees raw epoch numbers
        display_value: Any = value
        display_unit = unit
        if name.endswith("_epoch") and isinstance(value, (int, float)):
            display_value = datetime.fromtimestamp(value, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            display_unit = ""
        elif unit == "minutes" and isinstance(value, (int, float)) and abs(value) >= 60:
            display_value = f"{value:.0f} min ({value / 60:.1f}h)"
            display_unit = ""

        subjects = rec.get("subjects", [])
        subject_name = ""
        if subjects:
            s = subjects[0]
            subject_name = _resolve_name(
                s.get("entity_id", ""), s.get("entity_type", ""), identity_map
            )
        lines.append(f"[{idx}] METRIC  | {name}  ({stage_name(module)})")
        subj_part = f" ({subject_name})" if subject_name else ""
        sep = " " if display_unit else ""
        lines.append(f"    Value: {display_value}{sep}{display_unit}{subj_part}")
        lines.append(f"    [record: {rid_short}...]")

    def _render_finding(self, lines, idx, rec, module, rid_short) -> None:
        code = rec.get("code", "?")
        severity = rec.get("severity", "?")
        lines.append(f"[{idx}] FINDING  | {code}  | {severity}  ({stage_name(module)})")
        detail = rec.get("disposition_detail") or rec.get("message") or ""
        if detail:
            lines.append(f"    {str(detail)[:160]}")
        lines.append(f"    [record: {rid_short}...]")


# ---------------------------------------------------------------------------
# LLMRenderer
# ---------------------------------------------------------------------------

class LLMRenderer:
    """Anthropic API renderer.  Falls back to TemplateRenderer if no key/package."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        _client: Any = None,
    ) -> None:
        # Errand 4B.15a — the VOICE tier, a third constant in `llm_compat` and
        # deliberately not either of the two governed ones. This model rewords an
        # answer that was already assembled and validated; it was not in 4B.15's
        # bench and this errand does not move it.
        from mre.modules.llm_compat import voice_model
        self._model = model or voice_model()
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        self._available = False
        self._fallback_reason = ""
        #: Item 5(a) — the last fail-closed render's INTERNAL reasons, kept off
        #: the answer surface. A dev view, the question ledger or a test reads
        #: them; a planner never does.
        self.last_diagnostics: list[str] = []
        if _client is not None:
            self._client = _client
            self._available = True
        elif not self._api_key:
            self._fallback_reason = "ANTHROPIC_API_KEY not set"
        else:
            # Construction is fail-closed: ImportError (no package) OR any other
            # exception the SDK might raise while building a client (a malformed
            # proxy env, an eager-validation change in a future SDK) degrades to
            # the template, never propagates. (4A.1b: the real-key path was never
            # exercised, so an `except ImportError` was mistaken for a full seal.)
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self._available = True
            except ImportError:
                self._fallback_reason = "anthropic package not installed"
            except Exception as exc:  # noqa: BLE001 — construction must never raise
                self._fallback_reason = f"client construction failed: {type(exc).__name__}"

    def _template_fallback(self, bundle: ExplanationBundle, reason: str,
                           register: Optional[str] = None) -> str:
        """The single degradation target: render the deterministic template body
        and mark WHY the LLM path was not used. Every fail-closed exit routes
        here so an operator always sees an honest ``[rendered by: template …]``."""
        body = TemplateRenderer()._render_body(bundle)
        if bundle.subject_type in ("synthesis", "prove_it"):
            # The tier line wins: a synthesis answer must never claim to have been
            # "rendered by template" when what a planner needs to know is which TIER
            # answered them (R-AI5(4)).
            return f"{body}\n{_rendered_by(bundle, 'template')}"
        reg = register or _register_for(bundle)
        return f"{body}\n[rendered by: template — {reason} | register: {reg}]"

    # Refusal / fallback bundles are AUTHORED copy — the honest refusal, the
    # near-miss bridge, the clarify prompt, the ledger meta-listing. There is
    # nothing to testify FROM and nothing for the model to improve; the authored
    # header IS the answer. These short-circuit to the template with NO LLM
    # round-trip, regardless of whether the bundle happens to carry records
    # (Session 4B.0 Fix-B extension of the 4A.1c no-evidence guard — defense in
    # depth: an unresolvable question must never reach the LLM renderer).
    _AUTHORED_COPY_SUBJECTS = frozenset({
        "unsupported", "near_miss", "clarify", "refusals",
        # Session 4B.4: the scoping / meta-read answers are authored copy too — the
        # header IS the answer; nothing to testify from, never the LLM's to rewrite.
        "advice", "solve_time", "machine_count", "maintenance",
        # Session 4A.3-pre CU4: the coaching answer is retrieved authored copy.
        # Session 4B.15 Item 5 makes that stricter, not looser: the capability
        # body is composed from docs/05's own verdict, proof status and doorway
        # columns, and a reword that softens "not today" into "not currently
        # supported out of the box" is the exact failure it was built to end. A
        # planner acts on a capability claim by AUTHORING DATA, so there is no
        # board to check a fluent overstatement against.
        "coaching",
        # Session 4B.15 Item 3: an attribute lookup is a VALUE and its SOURCE.
        # There is nothing to testify from and nothing to improve — a reword can
        # only blur "not declared" into "none" or drop the provenance clause,
        # which is the whole answer.
        "attribute_lookup",
        # Session 4A.5a CU2: the confirmation-of-take bridge is authored copy — it
        # names a gesture and a boundary (M10 has no write path). An LLM reword is
        # exactly where "I'll move it for you" would come from.
        "confirm_take",
        # Session 4B.5 CU2: the open delta card is read BACK, verbatim from the
        # card's own figures. An LLM reword is where the answer would start
        # disagreeing with the surface the planner is looking at — the one failure
        # this route exists to make impossible.
        "open_card",
        # Session 4A.5a CU5: drill_down renders a composed FINDING detail — the
        # same authored, planner-voiced body `findings` renders — and the LLM kept
        # footnoting its list ordinal as a record ("[record: EVIDENCE CHAIN]"),
        # failing the citation floor and falling back anyway. The recurring disease
        # has the recurring cure (4A.3c CU3): composed authored copy renders
        # verbatim. The floor's strictness is never the variable.
        "drill_down",
        # Session 4A.3-pre CU6: the contested-fact restatement is authored warmth
        # over a pinned fact — the LLM must never soften it into capitulation.
        "contested_fact",
        # Session 4B.14 Item 2: the blocker analysis. Two reasons, and the second
        # is the load-bearing one. (a) Its body is composed entirely from
        # pre-computed key_facts and carries docs/05 citations, which the
        # testimony validator correctly reads as fabricated record ids — the
        # recurring disease with the recurring cure (4A.3c CU3). (b) The verb is
        # the answer. "Couldn't" and "the solver chose" are the distinction this
        # route exists to draw, and a reword that softens either into "took the
        # next opening" would put back exactly the failure it was built to end.
        "why_here",
        # Session 4B.16 Item 1: the counterfactual, for the same two reasons and
        # a third. Its closing paragraph — "that removes the barrier; it does
        # not place the operation there" — is the entire discipline of the
        # route, and it is the first sentence an "answer in 2-3 sentences"
        # reword drops. Without it a necessary condition reads as a promise.
        "counterfactual",
        # Session 4B.30: the LATER direction, for a fourth reason on top of
        # those three. Its refusals are the common case on a real board, and
        # each one draws a distinction a reword flattens: SHUT is not OCCUPIED,
        # and "I can't re-place split work as one move" is about US while
        # "that time is taken" is about the PLANT. Flattening either is the
        # confident-wrong answer this route was built to stop giving.
        "later_move",
        # Session 4A.3: the swap/move bridge + the absence pair are authored — the
        # take + gesture bridge are composed on the evidence, never LLM-improvised.
        "swap_move", "gap_between", "machine_idle",
        # Session 4A.3c CU2: a schedule listing (order/machine/customer) and the
        # start-reason answer are composed authored copy — a table of placements,
        # the R-SC3 polarity floor. They now carry ordered_records to LIGHT the
        # narrated bars (cited_refs), but the prose must stay deterministic: handing
        # a multi-row table to the "answer in 2-3 sentences" LLM would drop rows.
        # Verbatim render + a lit-bars channel, never an LLM rewrite of the table.
        "schedule", "start_reason",
        # Session 4A.3c CU3: the findings / certificate-testimony answer is
        # compose_findings() — authored composed sentences (subject, offending
        # value, plain cause, catalog fix), already planner-voiced. The LLM reword
        # kept footnoting the list ORDINAL as a record ("[record: 1]"), failing the
        # citation floor ~11% of live renders and falling back anyway. Render the
        # composed findings verbatim: the same treatment every other composed
        # authored register gets, and a deterministic ~zero validator-fallback rate.
        "findings",
        # Session 4A.5b: a SYNTHESIS answer's claims were verified SENTENCE BY
        # SENTENCE before they got here (R-AI5(3)). Handing them to the rendering
        # model to reword would dissolve the very thing that was verified — the
        # words the provenance label is attached to. Rendered verbatim, always.
        "synthesis", "prove_it",
        # Session 4B.16 Item 2: THE OPENER is a ranked list of composed authored
        # items, each carrying its own number and its own pointer. The
        # "answer in 2-3 sentences" reword drops items — and an opener that
        # drops an item reads as a clean bill of health for it, which is the
        # failure the route exists to end. Same recurring cure (4A.3c CU3).
        "briefing",
        # Session 4A.5c: the PROMOTED route's cause mix is composed authored copy
        # over pre-computed facts, and it carries the two hedges the dossier made
        # conditions of promotion — the premise check and the named-unattributed
        # line. Both are exactly the sentences an "answer in 2-3 sentences" reword
        # drops first, and dropping either turns a proven answer into a confident
        # wrong one. Rendered verbatim.
        "lateness_cause",
        # Session 4A.5c CU4: the rolling answers are authored, ID-free and HEDGED
        # (the beyond-horizon estimate is explicitly not a placement). Rendered
        # verbatim — a reword that drops "that's an estimate" turns an honest
        # answer into a commitment the solver never made.
        "rolling",
    })

    def render(self, bundle: ExplanationBundle) -> str:
        # CU3 — the single delivery seam (mirrors TemplateRenderer.render): every
        # register — testimony, remediation, judgment, the authored fallbacks —
        # returns through _render_inner and is stripped of markdown/backticks here.
        text = apply_repeat_riders(bundle, strip_formatting(
            self._render_inner(bundle)))
        # 4B.11 CU1 — same seam, same rule: a reworded answer that still states
        # money on an unproved board still carries the gap.
        text = apply_cost_proof_rider(bundle, text) or text
        # 4B.14 Item 1 — same seam, same rule: a REWORD is exactly how "so it
        # took the next opening" comes back after the assembler removed it.
        text = apply_sufficiency_rider(bundle, text) or text
        # 4B.13 Item 1(ii) — and same seam, same rule again: a reworded answer
        # that still never addressed the predicate says so. Both renderers or
        # neither; a floor one path can skip is not a floor.
        text = apply_coverage_rider(bundle, text) or text
        # Errand 4B.15a — same seam, same rule. A reword cannot launder an answer
        # that read nothing, so the withholding guard runs on both paths.
        return apply_unread_guard(bundle, text) or text

    def _render_inner(self, bundle: ExplanationBundle) -> str:
        if bundle.subject_type in ("remediation", "triage"):
            return self._render_register(bundle)
        if bundle.subject_type in self._AUTHORED_COPY_SUBJECTS:
            return self._template_fallback(
                bundle, "authored copy — rendered verbatim", "testimony")
        if not self._available:
            return self._template_fallback(
                bundle, f"--llm requested but {self._fallback_reason}", "testimony")

        # A bundle with no evidence chain has nothing to testify FROM: an honest
        # refusal / near-miss / clarify (authored copy), or a header-only summary
        # (an empty schedule listing — "Nothing scheduled for all"). Handing such a
        # bundle to the model only invites FABRICATED citations and prose in place
        # of the authored refusal (4A.1c: screenshots showed
        # "[record: Nothing scheduled for all]"). Render the template body verbatim
        # — it IS the answer — and never let an unresolvable question reach the LLM.
        if not bundle.ordered_records:
            return self._template_fallback(
                bundle, "no evidence chain — rendered verbatim", "testimony")

        # The LLM-touching body is wrapped so that ANY runtime failure — network,
        # auth (a bad/expired key), rate-limit, a malformed response, a parsing
        # error — degrades to the deterministic template. This method NEVER raises
        # (4A.1b: fail-closed armor, made real for the unmocked API path).
        try:
            prompt, known_ts, known_time, known_machines, known_records = \
                self._build_prompt_material(bundle)
            text = self._call_llm(prompt)
            issues = self._validate_testimony(
                text, known_ts, known_time, known_machines, known_records)
            if issues:
                regen_prompt, *_ = self._build_prompt_material(bundle, regen_note=issues)
                text = self._call_llm(regen_prompt)
                # Validate against the ORIGINAL known sets — not the regen prompt,
                # which contains the rejected output in its header and must not
                # whitelist itself.
                issues2 = self._validate_testimony(
                    text, known_ts, known_time, known_machines, known_records)
                if issues2:
                    return self._validated_template_fallback(bundle, issues2)
            # Session 4B.5 CU3(b) — THE VACUOUS-CAUSAL TRIPWIRE. Everything above
            # asks whether anything here is MADE UP. On a causal route there is a
            # second way to be wrong: to say nothing at all, convincingly. An
            # answer that names no driver, no entity beyond the question's own
            # subjects and no quantity is unfalsifiable — which is why every
            # fabrication check passes it — and it FAILS CLOSED to the template,
            # whose causal clause is composed from the evidence rather than
            # written.
            if bundle.subject_type in CAUSAL_SUBJECT_TYPES:
                subjects, entities = causal_material(bundle)
                why = causal_vacuity(text, subjects=subjects, entities=entities)
                if why:
                    return self._validated_template_fallback(
                        bundle, [f"vacuous causal answer: {why}"])
            return (_append_take(text, bundle)
                    + f"\n[rendered by: LLM ({self._model}) | register: testimony]")
        except Exception as exc:  # noqa: BLE001 — render must never raise
            # Item 5(a): the exception CLASS NAME was the planner-visible
            # reason. It is now on `last_diagnostics`; the surface states the
            # part that bears on the answer they are reading.
            self.last_diagnostics = [f"LLM error: {type(exc).__name__}"]
            _LOG.debug("validated render failed", exc_info=True)
            return self._template_fallback(bundle, MODEL_UNAVAILABLE, "testimony")

    def _validated_template_fallback(self, bundle: ExplanationBundle,
                                     issues: list[str]) -> str:
        """The validated-render fail-closed exit: the deterministic template body,
        the reason it was used, and the rendered-by line that names the path.
        One implementation, so a new check can never fall back differently from an
        old one (Session 4B.5 CU3b factored this out of ``render``)."""
        body = TemplateRenderer()._render_body(bundle)
        # SESSION 4B.21 ITEM 5(a) — THE VERDICT WAS DEVELOPER OUTPUT AND IT
        # REACHED THE PLANNER. This used to print, verbatim, above the answer:
        #
        #     [LLM validation failed: vacuous causal answer: names no driver,
        #      no entity beyond the question's own subjects, and no quantity;
        #      fell back to template]
        #
        # The tripwire firing is correct and the fallback is correct. Printing
        # an internal check's reasoning to a planner is not: it is written for
        # whoever maintains the check, it names mechanisms that mean nothing at
        # a plant, and it landed on the one answer that already contradicted
        # itself (4B.17's A5).
        #
        # What a planner needs from this line is ONE fact — the answer they are
        # reading is the deterministic template, not the model's prose — and
        # the rendered-by footer states it. The verdict is kept on
        # `last_diagnostics` for the dev surfaces and logged. Routed, not
        # deleted.
        self.last_diagnostics = list(issues)
        _LOG.debug("validated render rejected (%s): %s",
                   bundle.subject_type, "; ".join(issues[:2]))
        return body + "\n" + DRAFT_REJECTED_FOOTER.format(register="testimony")

    def _render_register(self, bundle: ExplanationBundle) -> str:
        """Remediation / judgment-triage register (handoff §3): the deterministic
        authored body is the ground truth; the LLM may only reword it for
        fluency. The allowed-number set is derived from exactly that body (the
        single derivation), and any invented number fails closed to the body."""
        from mre.modules.remediation import (
            allowed_numbers, render_remediation_body, unverifiable_numbers,
        )
        from mre.modules.triage import render_triage_body

        register = _register_for(bundle)
        if bundle.subject_type == "remediation":
            body = render_remediation_body(
                bundle.ordered_records, limit=bundle.key_facts.get("limit"))
            intro = ("This is authored remediation guidance from the frozen "
                     "catalog. Reword it for fluency ONLY.")
        else:
            body = render_triage_body(bundle.ordered_records)
            intro = ("This is a grade-distance triage. Reword it for fluency "
                     "ONLY, keeping the fix-first order and the named arithmetic.")

        if not self._available:
            return (body + f"\n[rendered by: template — {self._fallback_reason} "
                    f"| register: {register}]")

        # Same fail-closed seal as render(): the authored body is ground truth, so
        # any LLM failure degrades to it — never a 5xx.
        try:
            allowed = allowed_numbers(body)
            prompt = (
                f"{intro}\n\n"
                "RULES (violating any causes fallback to the source text):\n"
                "1. Do NOT introduce any number, percentage, or § reference not "
                "present below.\n"
                "2. Do NOT invent causes, thresholds, or fixes — only what appears "
                "below.\n"
                "3. Keep every rule_id, catalog note version, and § citation.\n\n"
                f"SOURCE (authored):\n{body}\n"
            )
            text = self._call_llm(prompt)
            if unverifiable_numbers(text, allowed):
                # Item 5(a), same routing: the planner is told the authored
                # text is what they are reading; "invented a value" is a note
                # to whoever maintains the check.
                self.last_diagnostics = [
                    "invented a value not present in the authored source"]
                _LOG.debug("register render rejected: invented a value")
                return body + "\n" + DRAFT_REJECTED_FOOTER.format(
                    register=register)
            return text + f"\n[rendered by: LLM ({self._model}) | register: {register}]"
        except Exception as exc:  # noqa: BLE001 — register render must never raise
            # Item 5(a): a Python exception class name is not planner content.
            self.last_diagnostics = [f"LLM error: {type(exc).__name__}"]
            _LOG.debug("register render failed", exc_info=True)
            return (body + f"\n[rendered by: template — {MODEL_UNAVAILABLE} "
                    f"| register: {register}]")

    def render_judgment(self, question: str, history: Any, fallback_bundle: ExplanationBundle) -> str:
        return strip_formatting(
            self._render_judgment_inner(question, history, fallback_bundle))

    def _render_judgment_inner(self, question: str, history: Any, fallback_bundle: ExplanationBundle) -> str:
        """Conversational turn in dialogue mode — reasons over prior evidence bundles."""
        if not self._available:
            body = TemplateRenderer()._render_body(fallback_bundle)
            return (
                body
                + f"\n[rendered by: template — {self._fallback_reason} | register: testimony]"
            )
        try:
            text = self._llm_judgment(question, history)
            return text + f"\n[rendered by: LLM ({self._model}) | register: judgment]"
        except Exception as exc:  # noqa: BLE001 — judgment render must never raise
            body = TemplateRenderer()._render_body(fallback_bundle)
            # Item 5(a): routed, not printed.
            self.last_diagnostics = [f"LLM error: {type(exc).__name__}"]
            _LOG.debug("judgment render failed", exc_info=True)
            return (body + f"\n[rendered by: template — {MODEL_UNAVAILABLE} "
                    "| register: testimony]")

    def _build_prompt_material(
        self,
        bundle: ExplanationBundle,
        regen_note: Optional[list[str]] = None,
    ) -> tuple:
        """Return (prompt_text, known_ts, known_time, known_machines, known_records).

        The verifiable-value sets are extracted from the base evidence text (prompt
        without the regen_note header) — except known_records, taken straight from
        the bundle's real record ids.  This guarantees:
        - anything shown to the LLM in the evidence section is verifiable,
        - rejected values in a regen_note header cannot whitelist themselves, and
        - every [record: …] citation must name a REAL record in the bundle (4A.1c).
        """
        context = TemplateRenderer()._render_body(bundle)
        facts = self._extract_precomputed_facts(bundle)
        facts_section = "\n".join(f"  {k}: {v}" for k, v in facts.items()) or "  (none)"

        base_evidence = (
            "You are a manufacturing scheduling assistant. "
            "Report on the solved schedule using ONLY the evidence below.\n\n"
            "PRE-COMPUTED FACTS (copy these values exactly — never recompute):\n"
            + facts_section + "\n\n"
            + "EVIDENCE CHAIN:\n" + context + "\n\n"
            + "RULES (violating any rule causes regeneration):\n"
            "1. Quote every timestamp, number, and name EXACTLY as it appears above.\n"
            "   Never perform arithmetic or unit conversions.\n"
            "2. End every factual sentence with [record: XXXX] citing the record_id.\n"
            "3. Do not use causal language ('cascading', 'shifted', 'compressed', 'because of')\n"
            "   unless a record explicitly states it.\n"
            "4. Do not mention any machine, WO, date, or number absent from the evidence.\n"
            "5. Answer in 2-3 sentences.\n\n"
            + "QUESTION: " + bundle.question + "\n"
        )

        header = ""
        if regen_note:
            header = (
                "PREVIOUS ATTEMPT REJECTED — issues found:\n"
                + "\n".join(f"  - {i}" for i in regen_note)
                + "\nFix every issue. Do NOT compute values; quote only from evidence below.\n\n"
            )

        prompt_text = header + base_evidence

        # Extract verifiable sets from base_evidence only — not from the regen header.
        known_ts: set = set()
        for ts_str in _TS_FULL_RE.findall(base_evidence):
            tup = _to_minute_tuple(ts_str)
            if tup is not None:
                known_ts.add(tup)

        known_time: set = set()
        for m in _TIME_NUM_RE.finditer(base_evidence):
            val = float(m.group(1))
            normalized = _to_minutes(val, m.group(2))
            known_time.add(val)
            known_time.add(normalized)

        known_machines: set = set(_MACHINE_RE.findall(base_evidence))

        # The REAL record ids the answer is allowed to cite. The template footnotes
        # an 8-char prefix ("[record: abcd1234...]"); the LLM is told to cite the
        # record_id, so a citation is valid iff it is a prefix of a real id.
        known_records: set = {
            str(rec.get("record_id")) for rec in bundle.ordered_records
            if rec.get("record_id")
        }

        return prompt_text, known_ts, known_time, known_machines, known_records

    def _call_llm(self, prompt_text: str) -> str:
        # No `import anthropic` here: the client is already built (or injected)
        # by __init__, so this path must not require the SDK to be importable.
        # The stray import made an injected-client call fail with
        # ModuleNotFoundError wherever the package is absent — masked on any dev
        # host that happened to have it installed (session 2.4b, in-container).
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return response.content[0].text

    def _extract_precomputed_facts(self, bundle: ExplanationBundle) -> dict[str, str]:
        """Return string-valued facts for the LLM to quote verbatim."""
        facts: dict[str, str] = {}
        kf = bundle.key_facts
        if kf.get("completion_iso"):
            facts["projected_completion"] = kf["completion_iso"]
        if kf.get("lateness_minutes") is not None:
            mins = kf["lateness_minutes"]
            facts["lateness"] = f"{int(mins)} min"
            if kf.get("lateness_hours") is not None:
                facts["lateness_hours"] = f"{kf['lateness_hours']}h"
        if kf.get("due_date"):
            facts["due_date"] = str(kf["due_date"])
        # CU1 — the blocked-by chain, pinned as facts the model must QUOTE, never
        # compress. Live, the LLM rewrote "held by ORD-04 until Mon 14:50" down to
        # "busy with other work" (the driver phrase). Enumerate the culprit order,
        # its machine, the release time, and its priority so it cannot be dropped.
        blk = kf.get("blocked_by")
        if blk:
            facts["blocking_machine"] = str(blk.get("machine", ""))
            facts["blocked_by_order"] = str(blk.get("blocker_order", ""))
            facts["blocking_until"] = str(blk.get("until", ""))
            facts["blocked_start"] = str(blk.get("my_start", ""))
            if blk.get("blocker_priority"):
                facts["blocking_order_priority"] = str(blk["blocker_priority"])
        return facts

    def _validate_testimony(
        self,
        text: str,
        known_ts: set,
        known_time: set,
        known_machines: set,
        known_records: Optional[set] = None,
    ) -> list[str]:
        """Return validation issues; empty list means text is acceptable.

        All known-value sets must come from _build_prompt_material so that only
        values actually shown to the LLM are considered verifiable.
        """
        issues: list[str] = []
        known_records = known_records or set()

        # 1. Timestamps: parse both sides to (year,month,day,hour,minute) and compare.
        #    Tolerates dropped seconds, dropped Z, space-vs-T, UTC suffix, date-only.
        for ts_str in _TS_FULL_RE.findall(text):
            tup = _to_minute_tuple(ts_str)
            if tup is not None and not _ts_matches(tup, known_ts):
                issues.append(f"unverifiable timestamp '{ts_str}'")

        # 2. Time-unit numbers: normalize min/h/hours to minutes before comparing.
        #    "14h", "14.0 hours", "840 min", "840.0 min" all pass against a 840-min prompt.
        for m in _TIME_NUM_RE.finditer(text):
            val = float(m.group(1))
            normalized = _to_minutes(val, m.group(2))
            if val not in known_time and normalized not in known_time:
                issues.append(f"unverifiable time value '{m.group(0).strip()}'")

        # 3. Machine names: every M-XXXX in prose must appear in the prompt.
        for machine in _MACHINE_RE.findall(text):
            if machine not in known_machines:
                issues.append(f"unverifiable machine name '{machine}'")

        # 4. Footnotes: if any factual sentence exists, at least one must be footnoted.
        prose = re.sub(r'\n\[rendered by:.*', '', text, flags=re.DOTALL)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', prose) if s.strip()]
        factual = [s for s in sentences if re.search(r'\d|M-[A-Z]|WO-', s)]
        if factual and not any('[record:' in s for s in factual):
            issues.append("no [record:] footnotes on factual sentences")

        # 5. Record citations: every [record: X] must name a REAL record in the
        #    bundle (4A.1c — the LLM fabricated "[record: Nothing scheduled for
        #    all]" and "[record: evidence_chain_001]"). The template footnotes an
        #    8-char prefix, so a citation is valid iff it prefixes a real id.
        for cite in re.findall(r'\[record:\s*([^\]]*?)\s*\]', text):
            cid = cite.strip().rstrip('.').strip()   # drop the template's trailing "..."
            if cid in ("", "?"):
                continue                             # template placeholder, not a claim
            if not any(rid == cid or rid.startswith(cid) for rid in known_records):
                issues.append(f"fabricated record citation '{cite.strip()}'")

        return issues

    def _llm_judgment(self, question: str, history: Any) -> str:
        prompt = self._build_judgment_prompt(question, history)
        # See _call_llm: the client is already built/injected; no SDK import here.
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _build_judgment_prompt(self, question: str, history: Any) -> str:
        lines = [
            "You are a manufacturing scheduling assistant in dialogue mode.",
            "",
            "PRIOR TURNS (read-only evidence — do not invent facts beyond these):",
        ]
        for i, turn in enumerate(history.turns(), 1):
            lines.append(f"\n[Turn {i}] User: {turn.question}")
            if turn.bundle is not None:
                lines.append(f"  Key facts: {turn.bundle.key_facts}")
                body = TemplateRenderer()._render_body(turn.bundle)
                lines.append(f"  Evidence (excerpt):\n{body[:800]}")
            else:
                lines.append("  (judgment turn — no evidence bundle)")
            lines.append(f"  Answer: {turn.rendered[:400]}")
        lines.extend([
            f"\nNEW MESSAGE: {question}",
            "",
            "INSTRUCTIONS:",
            "- Open your response with 'My take:' or a natural equivalent.",
            "- Reason ONLY over facts from the prior turns above.",
            "  Do not invent schedule facts, assignments, or records.",
            "- When you extrapolate or suggest, name the specific record or metric.",
            "- If the question is testable by re-running the solver with changed parameters,",
            "  say it can be run and name the specific command or phrase, e.g.:",
            "  '\"what if we unbatch WO-2001 and WO-2002\" runs in the REPL,",
            "   or: python -m mre.whatif --suppress-merge WO-2001,WO-2002'.",
            "  Do NOT say 'not wired up yet'.",
            "- Keep your answer to 2-3 paragraphs.",
        ])
        return "\n".join(lines)
