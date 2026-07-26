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

Session 4A.5b adds the SECOND TIER (R-AI5(2)): an unmatched intent no longer ends at
the honest unsupported bridge — it goes to labeled open synthesis over the read-only
tool surface, hardened claim by claim before it renders. The two tiers stay sealed
from each other in both directions:

    matched intent    -> contracted routes, ALWAYS. It can never fall to synthesis.
    unmatched intent  -> synthesis, ALWAYS. It never guesses a route.

with part 1's honest bridge remaining the floor when no synthesizer is available.
The provenance telemetry's Pareto and the promotion loop (R-AI5(5)/(7)) are 4A.5c.
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
                              # / synthesis / prove-it
    source: str               # parse | none
    confidence: Optional[float]
    register: str
    resolution_note: str = ""
    parsed: Optional[ParsedQuestion] = None
    #: The hardened SynthesisAnswer, when the second tier answered (R-AI5(2)).
    synthesis: Any = None


# ---------------------------------------------------------------------------
# The synthesis memory — our own last answer, per ask session.
#
# "Prove it" (R-AI5(4)) re-runs the grounding pass on a claim WE made a turn ago, so
# the claims have to survive the turn boundary. They are kept here, in process, for
# the lifetime of the ask session: a bounded cache of the AI layer's own output. It
# is emphatically NOT state in the canonical model or the evidence store (M10 has no
# write path); per-claim provenance is ALSO written to the question ledger, which is
# the durable record and the seed of R-AI5(5)'s telemetry.
# ---------------------------------------------------------------------------

class SynthesisMemory:
    """The last synthesis answer per session, bounded and oldest-first-evicted."""

    def __init__(self, limit: int = 32) -> None:
        self._limit = limit
        self._by_session: dict[str, Any] = {}

    def remember(self, session_id: Optional[str], answer: Any) -> None:
        if not session_id or answer is None:
            return
        self._by_session.pop(session_id, None)
        self._by_session[session_id] = answer
        while len(self._by_session) > self._limit:
            self._by_session.pop(next(iter(self._by_session)))

    def last(self, session_id: Optional[str]) -> Any:
        return self._by_session.get(session_id) if session_id else None

    def forget(self, session_id: Optional[str]) -> None:
        if session_id:
            self._by_session.pop(session_id, None)


#: The process-wide memory the API ask path uses. Tests construct their own.
SYNTHESIS_MEMORY = SynthesisMemory()


def pick_claim(answer: Any, question: str) -> Any:
    """Which of OUR OWN claims a "prove it" is about — decided locally and
    deterministically, never by another model call.

    Word overlap with the planner's words first (they usually quote a fragment of
    it); failing that the CONCLUSION, which is the claim a planner most often
    challenges; failing that the first claim. Note what this is not: it selects
    among sentences we already said, so it decides nothing about intent."""
    claims = list(getattr(answer, "claims", []) or [])
    if not claims:
        return None
    words = {w for w in re.findall(r"[a-z]{4,}", (question or "").lower())}
    stop = {"that", "this", "prove", "know", "says", "your", "what", "where",
            "which", "from", "come", "comes", "sure", "really", "says", "tell",
            "show", "about", "part", "claim", "said", "just", "with", "have"}
    words -= stop
    best, best_score = None, 0
    for c in claims:
        score = len(words & {w for w in re.findall(r"[a-z]{4,}", c.text.lower())})
        if score > best_score:
            best, best_score = c, score
    if best is not None:
        return best
    for c in claims:
        if getattr(c.kind, "value", c.kind) == "conclusion":
            return c
    for c in claims:
        if getattr(c.status, "value", c.status) == "interpretive":
            return c
    return claims[0]


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


def _clarify_leads_nowhere(parsed: ParsedQuestion, params: dict) -> bool:
    """True when asking the planner to disambiguate would be a DEAD END.

    4A.5a forbade a clarify on an `unmatched` parse for exactly this reason: there
    is no route behind the question, so asking which of two readings they meant
    buys nothing. Session 4A.5b generalizes it with the sweep's own specimen.
    "whats holding CUT-01" parsed as `start-reason` — an intent that needs an ORDER
    — with only the MACHINE bound, and hedged with `ambiguous-intent`. The planner
    was asked to choose between two framings of an answer that could not have been
    assembled either way, having just named a machine we can read directly.

    So: when the planner NAMED something that resolved, and the intent the parse
    reached for is missing a slot it requires, the honest destination is the second
    tier — which reads what they actually named — not a question back. When nothing
    resolved at all, asking IS the right move and this returns False."""
    if parsed.intent is Intent.UNMATCHED:
        return True
    if not any(s.resolved for s in parsed.subjects):
        return False
    return any(not params.get(slot)
               for slot in _required_slots(parsed.intent, params))


def _names_another_kind(explainer: Any, kind: SubjectKind, raw: str) -> bool:
    """True when the planner's words resolve to a real entity of the OTHER kind —
    the parse typed a machine as an order, or the reverse. Resolution only; it
    decides no intent."""
    if not raw:
        return False
    try:
        if kind is SubjectKind.ORDER:
            return bool(explainer.resolve_machine_value(raw))
        if kind is SubjectKind.MACHINE:
            return bool(explainer.resolve_order_value(raw))
    except Exception:  # noqa: BLE001 — resolution must never raise into dispatch
        return False
    return False


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
    synthesis: Any = None


def _synthesis_dispatch(explainer: Any, parsed: ParsedQuestion, note: str,
                        synthesizer: Any, context: Optional[dict],
                        memory: Any, session_id: Optional[str]) -> Dispatched:
    """The SECOND TIER (R-AI5(2)): labeled open synthesis over read-only evidence,
    hardened by claim-level verification before it renders (R-AI5(3)).

    Reached ONLY from the unmatched branch. When no synthesizer is available the
    honest floor is part 1's bridge — never a keyword guess, and never a route."""
    from mre.modules.evidence_tools import EvidenceToolbox

    answer = synthesizer.synthesize(
        parsed.question, explainer=explainer, context=context,
        toolbox=EvidenceToolbox(explainer))
    if answer is None:
        return _unmatched_bridge(explainer, parsed, note)
    if memory is not None and not answer.unanswerable:
        memory.remember(session_id, answer)
    return Dispatched("synthesis",
                      explainer.route("synthesis", {"question": parsed.question,
                                                    "answer": answer}),
                      note, parsed.question, synthesis=answer)


def _unmatched_bridge(explainer: Any, parsed: ParsedQuestion,
                      note: str) -> Dispatched:
    """Part 1's honest destination for an unmatched question: the nearest
    capabilities where the parse named some, the plain unsupported answer where it
    did not. Still the floor under the synthesis tier when no synthesizer is
    available — an honest non-answer, never a guessed route."""
    params = route_params(parsed, parsed.question)
    if not parsed.nearest:
        return Dispatched(
            "REFUSED", explainer.route("unsupported", {"question": parsed.question}),
            note, parsed.question)
    offers, routes = _nearest_offers(parsed, params)
    lead = NEAR_MISS_LEAD.format(q=parsed.question)
    return Dispatched(
        "NEAR_MISS",
        explainer.route("near-miss", {"question": parsed.question, "lead": lead,
                                      "offers": offers, "routes": routes}),
        note, parsed.question)


def dispatch(explainer: Any, parsed: ParsedQuestion, *,
             ledger: Any = None, synthesizer: Any = None,
             context: Optional[dict] = None, memory: Any = None,
             session_id: Optional[str] = None) -> Dispatched:
    """A parsed question → the assembled answer.

    A matched intent goes to the CONTRACTED deterministic evidence assembly — the
    routes, pre-computed facts, authored copy and validator floor, unchanged in
    authority (R-AI5(2)). An UNMATCHED one goes to the labeled synthesis tier. There
    is no silent path between them in either direction, and nothing here guesses.
    """
    note = _subject_note(parsed)

    def _second_tier() -> Dispatched:
        if synthesizer is not None and getattr(synthesizer, "available", False):
            return _synthesis_dispatch(explainer, parsed, note, synthesizer,
                                       context, memory, session_id)
        return _unmatched_bridge(explainer, parsed, note)

    # 1 — the parse could not commit. Ask; never guess — UNLESS asking leads
    # nowhere (see _clarify_leads_nowhere), in which case the honest destination is
    # the second tier, which can actually read the thing the planner named.
    if parsed.clarify is not None:
        if _clarify_leads_nowhere(parsed, route_params(parsed, parsed.question)):
            return _second_tier()
        return Dispatched("CLARIFY", _clarify_bundle(explainer, parsed), note,
                          parsed.question)

    # 2 — "prove it" (R-AI5(4)): the planner contests or probes a claim WE made.
    # Re-run the grounding pass on that claim conversationally — the record if it
    # has one, the honest "that part is my inference from A and B" if it does not.
    # Always available, and it precedes intent: what is being questioned is our own
    # sentence, not a status of the plan.
    if parsed.followup_of is FollowupKind.PROVE_IT or \
            parsed.intent is Intent.PROVE_IT:
        last = memory.last(session_id) if memory is not None else None
        claim = pick_claim(last, parsed.question) if last is not None else None
        # With NOTHING of ours open to ground, a prove-it that also names a real
        # intent is answered AS that intent — the grounding pass has nothing to do,
        # and the question is still a question. Falling through here is what stops
        # the fourth sweep's specimen from dead-ending: "but why" (a DEEPEN on
        # ORD-05, selected, one turn after its cause chain) read as prove-it and
        # answered "I don't have a claim of my own open to ground", which is the
        # exact class 4A.5a existed to kill. When the parse named prove-it and
        # nothing else, the no-target copy IS the honest answer and still stands.
        if claim is not None or parsed.intent in (Intent.PROVE_IT, Intent.UNMATCHED):
            return Dispatched(
                "prove-it",
                explainer.route("prove-it", {"question": parsed.question,
                                             "claim": claim, "answer": last}),
                note, parsed.question)

    # 3 — the planner confirmed OUR OWN take back at us. Name the gesture and the
    # sandbox: the bridge answer, not a near-miss (Session 4A.5a CU2).
    if parsed.followup_of is FollowupKind.CONFIRM_TAKE or \
            parsed.intent is Intent.CONFIRM_TAKE:
        params = route_params(parsed, parsed.question)
        return Dispatched("confirm-take", explainer.route("confirm-take", params),
                          note, parsed.question)

    # 4 — no contracted intent fits (or the parse is not confident enough to answer
    # AS one). R-AI5(2): this is where LABELED OPEN SYNTHESIS lives, and it is the
    # ONLY door into it. Part 1's honest bridge stays as the floor beneath it.
    if parsed.intent is Intent.UNMATCHED or parsed.confidence < CONF_MATCH:
        return _second_tier()

    # 5 — a matched intent. The question the assemblers see is the planner's own
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
        # UNLESS those words name something real of ANOTHER KIND: this session's
        # sweep parsed "whats holding CUT-01" as an order intent with CUT-01 as the
        # ORDER, and telling a planner that the machine they are looking at is not
        # in the schedule is the confident-wrong class, not honesty. The parse
        # mis-typed it; the second tier can read what they actually named.
        if _names_another_kind(explainer, kind, unresolved[0].raw):
            return _second_tier()
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
            session_id: Optional[str] = None,
            synthesizer: Any = None, memory: Any = None) -> AskResult:
    """parse → dispatch → assemble, then log one question-ledger entry.

    The single entry point the API ask path calls. With no parser the answer is the
    honest unsupported one — R-AI5(2) leaves no deterministic fallback to reach for.
    With no synthesizer the second tier is simply unavailable and an unmatched
    question gets part 1's honest bridge.
    """
    parsed = parser.parse(question, explainer=explainer, context=context) \
        if parser is not None else None
    if memory is None:
        memory = SYNTHESIS_MEMORY

    synthesis = None
    if parsed is None:
        bundle = explainer.route("unsupported", {"question": question})
        route_label, source, confidence, note = "REFUSED", "none", None, ""
        resolved_question = question
    else:
        d = dispatch(explainer, parsed, ledger=ledger, synthesizer=synthesizer,
                     context=context, memory=memory, session_id=session_id)
        route_label, bundle, note = d.route, d.bundle, d.note
        resolved_question = d.routed_question
        source, confidence = "parse", parsed.confidence
        synthesis = d.synthesis
        # A "prove it" grounds OUR LAST ANSWER. When a later turn was answered by a
        # contracted route, the remembered synthesis claims are STALE — grounding
        # them would open a record behind a sentence the planner is not asking
        # about. The sweep caught exactly that: "are you sure about that", two turns
        # after a synthesis answer, re-opened the older claim. Forget on any other
        # answer; prove-it then honestly says it has no claim of its own open.
        if memory is not None and d.route not in ("synthesis", "prove-it"):
            memory.forget(session_id)

    register = register_of(bundle)

    if ledger is not None:
        # CU1's logging requirement: a synthesis answer's per-claim provenance AND
        # every tool call with its arguments ride on the ledger entry — the durable
        # record of what the second tier consulted and what it could prove.
        provenance = None
        if synthesis is not None:
            from mre.contracts.synthesis import SynthesisProvenance
            provenance = SynthesisProvenance.of(synthesis)
        ledger.record(
            verbatim_question=question,
            resolved_question=resolved_question,
            route=route_label,
            source=source,
            confidence=confidence,
            answer_register=register,
            schedule_id=schedule_id,
            session_id=session_id,
            synthesis=provenance,
        )

    return AskResult(bundle=bundle, resolved_question=resolved_question,
                     route=route_label, source=source, confidence=confidence,
                     register=register, resolution_note=note, parsed=parsed,
                     synthesis=synthesis)
