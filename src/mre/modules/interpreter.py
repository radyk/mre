"""The ask orchestration: parse -> dispatch -> assemble (R-AI5, Session 4A.5a CU2).

R-AI5 retires the deterministic interpretation layer. What used to live here — the
keyword/precedence classifier's companion (``resolve_followup``'s deictic,
correction, menu-selection and list-expansion rewrite rules) and the confidence-
tiered LLM *fallback* — is gone. Its BEHAVIOURS survive as fields of the parse
contract (``mre.contracts.parse.ParsedQuestion``) which this dispatch honours:

    followup_of=deepen        the subject carries; the intent is the planner's
    followup_of=correction    re-answer the corrected question
    followup_of=list-expand   re-fire the prior intent in list form
    followup_of=menu-select   a named menu item is a CONCEPT, not an entity bind
    followup_of=confirm-take  the planner confirms our own take -> the bridge answer
    subjects[].source         selection > last answer > history, and the answer says
                              which context won

The pipeline is now exactly:

    parse (one LLM call, closed vocabulary)  ->  dispatch(intent)
      ->  the EXISTING route assembly  ->  the EXISTING render + validator

with no deterministic-classifier fallback and no silent path between the tiers
(R-AI5(2)). Without a parser the ask path answers honestly that it could not
interpret the question — it never keyword-guesses.

SCOPE (part 1 of the R-AI5 arc). An unmatched intent gets the honest unsupported /
nearest-capabilities answer. R-AI5(2)'s labeled open SYNTHESIS and R-AI5(3)'s
claim-level verification are Session 4A.5b; the provenance telemetry, the per-claim
surface and the promotion loop (R-AI5(4)-(7)) are 4A.5c.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from mre.contracts.parse import (
    ClarifyReason,
    FollowupKind,
    Intent,
    ParsedQuestion,
    Polarity,
    SubjectKind,
    SubjectSource,
)
from mre.modules.ask_fallback_copy import (
    CLARIFY_AMBIGUOUS_INTENT,
    CLARIFY_AMBIGUOUS_SUBJECT,
    CLARIFY_NO_SUBJECT,
    CLARIFY_PARSE_FAILED,
    CLARIFY_SET_REFERENCE,
    CLARIFY_VERIFICATION,
    NEAR_MISS_LEAD,
    route_offer,
)
from mre.modules.explainer import ROUTE_TAXONOMY, canonical_question, register_of
from mre.modules.question_parser import QuestionParser

# Below this the parse is not confident enough to answer AS that intent; the honest
# destination is the unmatched bridge (nearest capabilities), never a guess.
CONF_MATCH = 0.45

# The authored clarify body for each closed clarify reason. The MODEL picks a
# reason from the closed set; the WORDS are always ours (R-AI1(c)).
_CLARIFY_COPY: dict[ClarifyReason, str] = {
    ClarifyReason.NO_SUBJECT: CLARIFY_NO_SUBJECT,
    ClarifyReason.AMBIGUOUS_SUBJECT: CLARIFY_AMBIGUOUS_SUBJECT,
    ClarifyReason.VERIFICATION: CLARIFY_VERIFICATION,
    ClarifyReason.AMBIGUOUS_INTENT: CLARIFY_AMBIGUOUS_INTENT,
    ClarifyReason.PARSE_FAILED: CLARIFY_PARSE_FAILED,
}

# Intents whose assemblers reason over TWO orders (the swap/move bridge and the
# absence pair) — the dispatch hands them the subject list in the planner's order.
_TWO_ORDER_INTENTS = frozenset({Intent.SWAP_MOVE, Intent.GAP_BETWEEN})

# The rolling (sliced-world) intents. On a monolithic run these degrade through the
# normal route table; the rolling document pre-route is upstream in the API.
ROLLING_INTENTS = frozenset(
    {Intent.BEYOND_HORIZON, Intent.WHY_NOT_SCHEDULED_YET, Intent.FROZEN})


@dataclass
class AskResult:
    bundle: Any
    resolved_question: str
    route: str                # taxonomy route id, or REFUSED / NEAR_MISS / CLARIFY
    source: str               # parse | none
    confidence: Optional[float]
    register: str
    resolution_note: str = ""
    parsed: Optional[ParsedQuestion] = None


# ---------------------------------------------------------------------------
# Dispatch — the parse contract becomes route params
# ---------------------------------------------------------------------------

def _subject_note(parsed: ParsedQuestion) -> str:
    """The visible resolution note (RUBRIC C3: the answer says which context won).

    The cockpit panel keys its "[from board selection]" badge off the literal
    phrase "board selection", so that wording is a contract with the client."""
    bits: list[str] = []
    for s in parsed.subjects:
        if not s.resolved:
            continue
        if s.source is SubjectSource.SELECTION:
            bits.append(f"resolved against {s.ref} (from board selection)")
        elif s.source is SubjectSource.LAST_ANSWER:
            bits.append(f"resolved against {s.ref}")
        elif s.source is SubjectSource.HISTORY:
            bits.append(f"resolved against {s.ref} (from earlier in this conversation)")
        elif s.raw and s.raw.upper() != s.ref.upper():
            bits.append(f"assuming {s.ref}")
    if parsed.followup_of is FollowupKind.CORRECTION and parsed.subjects:
        refs = ", ".join(s.ref for s in parsed.subjects if s.resolved)
        if refs:
            return f"corrected to {refs}"
    if parsed.followup_of is FollowupKind.LIST_EXPAND:
        bits.insert(0, "listing the previous answer")
    if parsed.followup_of is FollowupKind.MENU_SELECT:
        concept = parsed.ref(SubjectKind.CONCEPT)
        if concept:
            return f"coaching on {concept}"
    return "; ".join(dict.fromkeys(bits))


def routed_text(parsed: ParsedQuestion, params: dict) -> tuple[str, bool]:
    """The question the assemblers actually see, and whether it was rewritten.

    Three cases, in the order they are decided:

      * the turn RE-FIRES a previous question (a correction, a list expansion) —
        the canonical question for the intent, so the same assemblers re-resolve it;
      * a subject was POINTED at with no usable words ("but why?") — likewise
        canonical, since there is nothing in the text to substitute into;
      * otherwise the planner's OWN sentence with each resolved subject's words
        replaced by its canonical ref ("why ir ord-o5 late" -> "why ir ORD-05
        late"). Keeping the planner's phrasing keeps what the canonical template
        would drop (a second order, a date filter, the wording itself).

    Identity resolution still happens INSIDE the assemblers either way (the Phase-1
    audit lesson): what changes here is only which words they are given."""
    text = parsed.question
    changed = False
    needs_canonical = parsed.followup_of in (FollowupKind.CORRECTION,
                                             FollowupKind.LIST_EXPAND)
    for s in parsed.subjects:
        if not s.resolved:
            continue
        raw = (s.raw or "").strip()
        if raw and raw.upper() == s.ref.upper():
            continue                       # named exactly — nothing to rewrite
        if raw and re.search(re.escape(raw), text, re.IGNORECASE):
            text = re.sub(re.escape(raw), s.ref, text, count=1, flags=re.IGNORECASE)
            changed = True
        else:
            needs_canonical = True
    if needs_canonical:
        return canonical_question(parsed.intent.value, params), True
    return text, changed


def route_params(parsed: ParsedQuestion, question_text: str) -> dict:
    """The parse contract → the params the EXISTING route assembly already takes.
    Nothing here re-interprets the question; it only carries resolved subjects."""
    orders = parsed.refs(SubjectKind.ORDER)
    params: dict = {
        "question": question_text,
        "order": orders[0] if orders else None,
        "machine": parsed.ref(SubjectKind.MACHINE),
    }
    customer = parsed.ref(SubjectKind.CUSTOMER)
    if customer:
        params["customer"] = customer
    concept = parsed.ref(SubjectKind.CONCEPT)
    if concept:
        params["concept"] = concept
    if parsed.polarity is not None:
        params["polarity"] = parsed.polarity.value
    if parsed.intent in _TWO_ORDER_INTENTS:
        params["order_a"] = orders[0] if orders else None
        params["order_b"] = orders[1] if len(orders) >= 2 else None
    if parsed.intent is Intent.DRILL_DOWN:
        params["target"] = question_text
    return params


def _required_slots(intent: Intent, params: dict) -> list[str]:
    """The slots WITHOUT WHICH the assembler cannot answer.

    The taxonomy's ``params`` names the slots a route CAN take; a few of those
    routes answer a plant-wide question perfectly well with none of them (the
    calendar read, the double-booking check), and the gap explainer needs either an
    order or the machine. Requiring a slot the assembler does not need would turn a
    good answer into a near-miss bridge."""
    slots = list(ROUTE_TAXONOMY.get(intent.value, {}).get("params", []))
    if intent in (Intent.INTEGRITY_CHECK, Intent.DOWNTIME):
        return []                       # plant-wide is a legitimate scope
    if intent is Intent.GAP_BETWEEN:
        return [] if params.get("machine") else slots
    return slots


def _nearest_offers(parsed: ParsedQuestion, params: dict) -> tuple[list[str], list[str]]:
    """The unmatched bridge's authored offers: the nearest intents as concrete
    one-phrase follow-ups. At most two, never a dead end."""
    routes: list[str] = []
    for i in parsed.nearest:
        if i.value in ROUTE_TAXONOMY and i.value not in routes:
            routes.append(i.value)
        if len(routes) >= 2:
            break
    # The defaults are chosen by WHAT THE PLANNER NAMED, not by a fixed pair. The
    # first sweep's "whats holding CUT-01" bridged to "every late order" and "the
    # data-quality problems" — neither of which is about the machine they just
    # named. An offer that ignores the subject reads as not having listened.
    if params.get("machine"):
        defaults = ("machine-schedule", "machine-idle", "downtime")
    elif params.get("order"):
        defaults = ("late-order", "order-schedule", "start-reason")
    else:
        defaults = ("late-orders", "data-problems")
    for default in defaults:
        if len(routes) >= 2:
            break
        if default not in routes:
            routes.append(default)
    routes = routes[:2]
    return [route_offer(r, params) for r in routes], routes


def _clarify_bundle(explainer: Any, parsed: ParsedQuestion):
    reason = parsed.clarify.reason if parsed.clarify else ClarifyReason.NO_SUBJECT
    if reason is ClarifyReason.SET_REFERENCE:
        pron = (parsed.clarify.detail if parsed.clarify else "") or "those"
        body = CLARIFY_SET_REFERENCE.format(pron=pron.strip()[:40])
    else:
        body = _CLARIFY_COPY.get(reason, CLARIFY_NO_SUBJECT)
    return explainer.route("clarify", {"question": parsed.question, "reason": body})


@dataclass
class Dispatched:
    """One dispatched parse: where it went, what it assembled, and the two visible
    strings the cockpit and the exam transcript show."""
    route: str
    bundle: Any
    note: str
    routed_question: str


def dispatch(explainer: Any, parsed: ParsedQuestion, *,
             ledger: Any = None) -> Dispatched:
    """A parsed question → the assembled answer.

    A matched intent goes to the CONTRACTED deterministic evidence assembly — the
    routes, pre-computed facts, authored copy and validator floor, unchanged in
    authority (R-AI5(2)). Everything else is an honest destination, never a guess.
    """
    note = _subject_note(parsed)

    # 1 — the parse could not commit. Ask; never guess.
    if parsed.clarify is not None:
        return Dispatched("CLARIFY", _clarify_bundle(explainer, parsed), note,
                          parsed.question)

    # 2 — the planner confirmed OUR OWN take back at us. Name the gesture and the
    # sandbox: the bridge answer, not a near-miss (Session 4A.5a CU2).
    if parsed.followup_of is FollowupKind.CONFIRM_TAKE or \
            parsed.intent is Intent.CONFIRM_TAKE:
        params = route_params(parsed, parsed.question)
        return Dispatched("confirm-take", explainer.route("confirm-take", params),
                          note, parsed.question)

    # 3 — no contracted intent fits (or the parse is not confident enough to answer
    # AS one). Part 1: the honest unsupported answer with the nearest capabilities
    # offered. R-AI5(2)'s labeled synthesis is Session 4A.5b.
    if parsed.intent is Intent.UNMATCHED or parsed.confidence < CONF_MATCH:
        params = route_params(parsed, parsed.question)
        offers, routes = _nearest_offers(parsed, params)
        if not parsed.nearest:
            return Dispatched(
                "REFUSED",
                explainer.route("unsupported", {"question": parsed.question}),
                note, parsed.question)
        lead = NEAR_MISS_LEAD.format(q=parsed.question)
        return Dispatched(
            "NEAR_MISS",
            explainer.route("near-miss", {"question": parsed.question,
                                          "lead": lead, "offers": offers,
                                          "routes": routes}),
            note, parsed.question)

    # 4 — a matched intent. The question the assemblers see is the planner's own
    # text unless the parse rewrote the subject (context bind / near-miss id /
    # re-fired question), in which case it is the canonical question — re-parsed by
    # the same assemblers, so identity resolution stays inside (Phase-1 lesson).
    params = route_params(parsed, parsed.question)
    routed_question, rewritten = routed_text(parsed, params)
    params["question"] = routed_question

    required = _required_slots(parsed.intent, params)

    # Three different failures to resolve a subject, three different honest
    # answers — never one blended "sorry":
    for kind in (SubjectKind.ORDER, SubjectKind.MACHINE):
        unresolved = parsed.unresolved(kind)
        if not unresolved or kind.value not in required or params.get(kind.value):
            continue
        # (a) the planner POINTED and nothing was live to point at → ask.
        if unresolved[0].pointed or not unresolved[0].raw:
            return Dispatched(
                "CLARIFY",
                explainer.route("clarify", {"question": parsed.question,
                                            "reason": CLARIFY_NO_SUBJECT}),
                note, parsed.question)
        # (b) the planner NAMED something that is not here → say it is not here,
        # never answer globally (the relevance guard, now driven by the parse).
        return Dispatched(
            "unknown-entity",
            explainer.route("unknown-entity",
                            {**params, "mention": unresolved[0].raw}),
            note, routed_question)

    # (c) a required slot nothing mentioned at all → the nearest-capabilities bridge.
    missing = [s for s in required if not params.get(s)]
    if missing:
        offers, routes = _nearest_offers(parsed, params)
        lead = NEAR_MISS_LEAD.format(q=parsed.question)
        return Dispatched(
            "NEAR_MISS",
            explainer.route("near-miss", {"question": parsed.question,
                                          "lead": lead, "offers": offers,
                                          "routes": routes}),
            note, routed_question)

    if parsed.intent is Intent.LEDGER_REFUSALS and ledger is not None:
        params["refusals"] = [r.model_dump(mode="json")
                              for r in ledger.recent_refusals()]

    bundle = explainer.route(parsed.intent.value, params)
    # Make the resolution visible (RUBRIC C3): the answer shows the question it
    # actually answered, whenever the parse rewrote it.
    if rewritten:
        bundle.question = routed_question
    return Dispatched(parsed.intent.value, bundle, note, routed_question)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_ask(explainer: Any, question: str, *, context: Optional[dict] = None,
            parser: Optional[QuestionParser] = None,
            ledger: Any = None, schedule_id: Optional[str] = None,
            session_id: Optional[str] = None) -> AskResult:
    """parse → dispatch → assemble, then log one question-ledger entry.

    The single entry point the API ask path calls. With no parser the answer is the
    honest unsupported one — R-AI5(2) leaves no deterministic fallback to reach for.
    """
    parsed = parser.parse(question, explainer=explainer, context=context) \
        if parser is not None else None

    if parsed is None:
        bundle = explainer.route("unsupported", {"question": question})
        route_label, source, confidence, note = "REFUSED", "none", None, ""
        resolved_question = question
    else:
        d = dispatch(explainer, parsed, ledger=ledger)
        route_label, bundle, note = d.route, d.bundle, d.note
        resolved_question = d.routed_question
        source, confidence = "parse", parsed.confidence

    register = register_of(bundle)

    if ledger is not None:
        ledger.record(
            verbatim_question=question,
            resolved_question=resolved_question,
            route=route_label,
            source=source,
            confidence=confidence,
            answer_register=register,
            schedule_id=schedule_id,
            session_id=session_id,
        )

    return AskResult(bundle=bundle, resolved_question=resolved_question,
                     route=route_label, source=source, confidence=confidence,
                     register=register, resolution_note=note, parsed=parsed)
