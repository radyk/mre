"""The interpreter + conversational context + ask orchestration (Session 4A.1).

Three things, in front of the M10 explainer's deterministic router (which stays
untouched — zero regression):

  CU1 — the interpreter: free-form phrasing → (route, params, confidence),
        mapping ONLY onto the explainer's existing taxonomy (ROUTE_TAXONOMY). It
        is invoked ONLY when the deterministic router already failed, so working
        phrasings pay zero latency / zero cost. LLM-backed with a strict JSON
        contract; fail-closed (no key / malformed / low confidence → the honest
        refusal path). The LLM never authors an answer — it only names a route.

  CU2 — conversational context: an elliptical follow-up ("and what would fix
        it?", "how much?") is rewritten into a complete question BEFORE routing,
        against the recent history + board selection. Resolution is deterministic
        and VISIBLE (the resolved question rides back to the renderer).
        Unresolvable ellipsis → ask for clarification, never a guess.

  Orchestration — run_ask(): resolve → deterministic route → (on miss) interpret
        → route / near-miss / refuse, then log one question-ledger entry (CU3).

R-AI1(c): all intelligence here accrues in reviewable artifacts — ROUTE_TAXONOMY,
the paraphrase test table, the authored fallback copy. The model is a swappable
renderer behind the validation armor; it maps phrasing to a closed route set and
nothing it returns is trusted beyond that set.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from mre.modules.ask_fallback_copy import (
    CLARIFY_NO_SUBJECT,
    CLARIFY_SET_REFERENCE,
    CLARIFY_VERIFICATION,
    NEAR_MISS_LEAD,
    route_offer,
)
from mre.modules.explainer import ROUTE_TAXONOMY, canonical_question, register_of

# Confidence gates (design tokens): at/above HIGH the interpreter's route answers
# directly (params permitting); in [MODERATE, HIGH) it becomes a near-miss bridge
# (CU4); below MODERATE it refuses. Tunable; the paraphrase table pins behavior.
CONF_HIGH = 0.75
CONF_MODERATE = 0.45

# Ellipsis signals (CU2): a follow-up referring back to a prior subject. NB
# "there" is deliberately excluded — "are there any late orders?" is not a
# follow-up (a false positive that would send a fresh question to clarify).
_ELLIPSIS_PRONOUNS = ("it", "that", "this", "them", "those", "these")
_COST_FOLLOWUP = ("how much", "what did it cost", "what's the cost", "whats the cost",
                   "and the cost", "the cost", "cost?")
_EDIT_ROUTES = ("edit-summary", "edit-cost")

# CU5 (Session 4A.2b) — the rewrite-confidence guard. Three shapes a naive
# pronoun substitution would mangle into a confident-wrong answer:
#   bare-why      — "but why?" is not a fresh question; it asks for the LAST
#                   subject's cause-chain (its lateness reason), not a refusal.
#   verification  — "is that correct?" asks the assistant to confirm its own prior
#                   claim; it can't be routed to schedule data — clarify.
#   set-reference — "10 of those" refers to a GROUP; substituting one order id
#                   ("10 of ORD-05") is nonsense — clarify, never guess.
_BARE_WHY_RE = re.compile(
    r"^(?:but|so|and|ok(?:ay)?|well|hmm|wait)?\s*(?:but\s+)?(?:why|how come)"
    r"(?:\s+is\s+(?:that|this|it))?(?:\s+though)?\s*\??$", re.IGNORECASE)
_VERIFY_RE = re.compile(
    r"\b(?:is|are|was|were)\s+(?:that|this|those|these|it)\s+"
    r"(?:correct|right|true|accurate|ok|okay)\b|\bare you sure\b", re.IGNORECASE)
_SET_PRONOUN_RE = re.compile(
    r"\b(?:\d+|some|many|few|several|most|all|how many|which|any)\s+of\s+"
    r"(those|them|these)\b", re.IGNORECASE)


@dataclass
class Interpretation:
    """The interpreter's structured output (the strict JSON contract)."""
    route: str
    params: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    nearest: list[str] = field(default_factory=list)


@dataclass
class ResolvedQuestion:
    """A question after conversational-context resolution (CU2)."""
    text: str                       # the complete question actually routed
    resolved: bool = False          # was an ellipsis rewritten?
    needs_clarification: bool = False
    note: str = ""                  # human-readable "resolved against ORD-12"


# ---------------------------------------------------------------------------
# CU2 — conversational context resolution (deterministic)
# ---------------------------------------------------------------------------

def _last_subject(history: list[dict], selection: dict) -> dict:
    """The most recent order/machine subject in the conversation: newest history
    turn that named one, else the current board selection."""
    for turn in reversed(history or []):
        if turn.get("order") or turn.get("machine"):
            return {"order": turn.get("order"), "machine": turn.get("machine")}
    if selection and (selection.get("order") or selection.get("machine")):
        return {"order": selection.get("order"), "machine": selection.get("machine")}
    return {}


def _last_route(history: list[dict]) -> Optional[str]:
    for turn in reversed(history or []):
        if turn.get("route"):
            return turn["route"]
    return None


def _has_ellipsis(ql: str) -> bool:
    words = re.findall(r"[a-z']+", ql)
    if any(p in words for p in _ELLIPSIS_PRONOUNS):
        return True
    # bare continuations: "and …", "what about …", "how about …"
    return ql.startswith(("and ", "what about", "how about", "also "))


def _substitute_pronoun(question: str, ref: str) -> str:
    """Replace the first back-reference pronoun with the external ref; if there is
    no pronoun (a bare 'what about …'), append 'for <ref>'."""
    def repl(m: re.Match) -> str:
        return ref
    for p in _ELLIPSIS_PRONOUNS:
        new, n = re.subn(rf"\b{p}\b", repl, question, count=1, flags=re.IGNORECASE)
        if n:
            return new
    return f"{question.rstrip(' ?')} for {ref}?"


def resolve_followup(question: str, context: Optional[dict], explainer: Any) -> ResolvedQuestion:
    """Rewrite an elliptical follow-up into a complete question BEFORE routing.

    Self-contained questions pass through unchanged. A cost follow-up after an
    edit answer resolves into the edit-cost domain. A pronoun/fragment follow-up
    resolves against the last order/machine subject. An ellipsis with no prior
    subject at all → needs_clarification (never a guess)."""
    q = (question or "").strip()
    ql = q.lower()
    context = context or {}
    history = context.get("history") or []
    selection = context.get("selection") or {}

    # CU6 — fuzzy id tolerance, BEFORE any exact-resolution check: a near-miss id
    # (ord-o5 / ORD-5 / ord 05) is rewritten to its canonical ref with a visible
    # assumption. An id matching nothing here is left alone (→ the relevance
    # guard's honest "isn't in this schedule").
    fq, fnotes = explainer.rewrite_fuzzy_orders(q)
    if fnotes:
        refs = ", ".join(dict.fromkeys(r for _t, r in fnotes))
        return ResolvedQuestion(text=fq, resolved=True, note=f"assuming {refs}")

    # Already names a resolvable ref → nothing to resolve.
    if explainer._find_order_ref(q) or explainer._find_machine_ref(q):
        return ResolvedQuestion(text=q, resolved=False)

    # CU5 — bare "but why?" resolves to the last subject's cause-chain (why-late),
    # never a refusal; with no prior subject it clarifies.
    if _BARE_WHY_RE.match(ql):
        last = _last_subject(history, selection)
        ref = last.get("order")
        if ref:
            return ResolvedQuestion(text=f"why is {ref} late?", resolved=True,
                                    note=f"resolved against {ref}")
        return ResolvedQuestion(text=q, resolved=False, needs_clarification=True,
                                note=CLARIFY_NO_SUBJECT)

    # CU5 — a verification of a prior claim ("is that correct?") can't be routed to
    # schedule data; ask what to check rather than answer the wrong order.
    if _VERIFY_RE.search(ql):
        return ResolvedQuestion(text=q, resolved=False, needs_clarification=True,
                                note=CLARIFY_VERIFICATION)

    # CU5 — a SET-referring follow-up ("10 of those") must not be rewritten into a
    # single-order question; name the ambiguity, offer the well-formed question.
    m_set = _SET_PRONOUN_RE.search(ql)
    if m_set:
        return ResolvedQuestion(
            text=q, resolved=False, needs_clarification=True,
            note=CLARIFY_SET_REFERENCE.format(pron=m_set.group(1)))

    # If the deterministic router ALREADY handles the raw question, never touch
    # it — otherwise a question that merely CONTAINS a pronoun ("summarize what I
    # changed and what IT cost", "why does THIS edit cost that much") would be
    # misread as an elliptical follow-up. Ellipsis resolution is strictly a
    # fallback for questions the router cannot route on their own.
    route_id, _ = explainer.classify(q)
    if route_id != "unsupported":
        return ResolvedQuestion(text=q, resolved=False)

    # "how much?" after an edit answer → the edit-cost domain (CU2 example).
    if any(c in ql for c in _COST_FOLLOWUP) and _last_route(history) in _EDIT_ROUTES:
        return ResolvedQuestion(
            text=canonical_question("edit-cost"), resolved=True,
            note="resolved to your last edit",
        )

    if _has_ellipsis(ql):
        last = _last_subject(history, selection)
        ref = last.get("order") or last.get("machine")
        if ref:
            return ResolvedQuestion(
                text=_substitute_pronoun(q, ref), resolved=True,
                note=f"resolved against {ref}",
            )
        return ResolvedQuestion(
            text=q, resolved=False, needs_clarification=True,
            note=CLARIFY_NO_SUBJECT,
        )

    return ResolvedQuestion(text=q, resolved=False)


# ---------------------------------------------------------------------------
# CU1 — the interpreter (LLM phrasing → route), fail-closed
# ---------------------------------------------------------------------------

class Interpreter:
    """Maps free-form phrasing onto the route taxonomy. LLM-backed, fail-closed.

    Construct with a client (real Anthropic or a test double exposing
    ``messages.create``); with no client and no key it is simply unavailable and
    ``interpret`` returns None (→ the honest refusal path). It NEVER answers — it
    only returns a route id from the closed taxonomy + extracted params."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001",
                 api_key: Optional[str] = None, _client: Any = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = _client
        self.available = False
        if _client is not None:
            self.available = True
        elif self._api_key:
            # Construction is fail-closed: no package OR any other client-build
            # failure leaves the interpreter simply UNAVAILABLE (→ the honest
            # refusal path), never a raise. interpret() is likewise fail-closed
            # (returns None on any exception), so the whole interpreter surface is
            # incapable of surfacing as a 5xx (4A.1b).
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self.available = True
            except Exception:  # noqa: BLE001 — construction must never raise
                self.available = False

    def _prompt(self, question: str) -> str:
        lines = ["Map the planner's question onto exactly ONE route id from this "
                 "closed list. Extract any order / machine / customer named "
                 "(in the planner's own words). Return STRICT JSON only.\n",
                 "ROUTES (id — meaning):"]
        meanings = {
            "late-order": "why one order is late",
            "late-orders": "which orders are late (all)",
            "why-on-machine": "why an order is on a machine",
            "machine-schedule": "what is running on a machine",
            "order-schedule": "when an order starts/finishes",
            "customer-schedule": "a customer's whole schedule",
            "downtime": "a machine's calendar closures / downtime",
            "data-problems": "data-quality problems",
            "version-diff": "what changed between versions",
            "remediation": "how to fix the submission's problems",
            "triage": "what to fix first",
            "certificate-testimony": "what is wrong with the submission",
            "edit-summary": "summary of edits the planner made",
            "edit-cost": "what the planner's last move cost",
            "ledger-refusals": "questions the system couldn't answer",
        }
        for rid in ROUTE_TAXONOMY:
            lines.append(f"  {rid} — {meanings.get(rid, rid)}")
        lines.append("")
        lines.append('JSON shape: {"route": "<id>", "params": {"order": "...", '
                     '"machine": "...", "customer": "..."}, "confidence": 0.0-1.0, '
                     '"nearest": ["<id>", "<id>"]}')
        lines.append("Omit params you cannot extract. If no route fits, use "
                     'route "none" with low confidence.')
        lines.append(f"\nQUESTION: {question}")
        return "\n".join(lines)

    def interpret(self, question: str) -> Optional[Interpretation]:
        """Return an Interpretation, or None (unavailable / malformed / no fit).
        Fail-closed at every step — a bad model response never raises."""
        if not self.available or self._client is None:
            return None
        try:
            resp = self._client.messages.create(
                model=self._model, max_tokens=256,
                messages=[{"role": "user", "content": self._prompt(question)}],
            )
            text = resp.content[0].text
        except Exception:
            return None
        return parse_interpretation(text)


def parse_interpretation(text: str) -> Optional[Interpretation]:
    """Parse the interpreter's JSON. Tolerant of a code fence / surrounding prose;
    strict about the route being in the taxonomy. None on anything malformed."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    route = obj.get("route")
    if route not in ROUTE_TAXONOMY:
        return None
    raw_params = obj.get("params") or {}
    params = {k: str(v) for k, v in raw_params.items()
              if k in ("order", "machine", "customer") and v}
    try:
        conf = float(obj.get("confidence", 0.0))
    except (ValueError, TypeError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    nearest = [r for r in (obj.get("nearest") or []) if r in ROUTE_TAXONOMY]
    return Interpretation(route=route, params=params, confidence=conf, nearest=nearest)


# ---------------------------------------------------------------------------
# param resolution (external refs in, canonical resolution inside)
# ---------------------------------------------------------------------------

def resolve_params(explainer: Any, interp: Interpretation) -> tuple[dict, bool]:
    """Resolve the interpreter's raw param strings to external refs the taxonomy
    route needs. Returns (resolved, all_required_resolved)."""
    needed = ROUTE_TAXONOMY.get(interp.route, {}).get("params", [])
    resolved: dict[str, str] = {}
    all_ok = True
    for slot in needed:
        raw = interp.params.get(slot)
        if slot == "order":
            val = explainer.resolve_order_value(raw) if raw else None
        elif slot == "machine":
            val = explainer.resolve_machine_value(raw) if raw else None
        else:  # customer — the schedule filter substring-matches, pass through
            val = raw
        if val:
            resolved[slot] = val
        else:
            all_ok = False
    return resolved, all_ok


def _nearest_offers(interp: Interpretation, resolved: dict) -> tuple[list[str], list[str]]:
    """The near-miss follow-ups (CU4): the interpreted route + one sibling, as
    authored one-phrase offers. At most two."""
    routes: list[str] = []
    for r in [interp.route, *interp.nearest]:
        if r in ROUTE_TAXONOMY and r not in routes:
            routes.append(r)
        if len(routes) >= 2:
            break
    if len(routes) < 2:
        # a broadly-useful default sibling that is never a dead end
        for d in ("late-orders", "data-problems"):
            if d not in routes:
                routes.append(d)
                break
    routes = routes[:2]
    offers = [route_offer(r, resolved) for r in routes]
    return offers, routes


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class AskResult:
    bundle: Any
    resolved_question: str
    route: str                # taxonomy route id, or REFUSED / NEAR_MISS / CLARIFY
    source: str               # deterministic | llm | none
    confidence: Optional[float]
    register: str
    resolution_note: str = ""


def run_ask(explainer: Any, question: str, *, context: Optional[dict] = None,
            interpreter: Optional[Interpreter] = None,
            ledger: Any = None, schedule_id: Optional[str] = None,
            session_id: Optional[str] = None) -> AskResult:
    """Resolve → route (deterministic, then interpreter) → near-miss/refuse, then
    log one ledger entry. The single entry point the API ask path calls."""
    resolved = resolve_followup(question, context, explainer)

    if resolved.needs_clarification:
        bundle = explainer.route("clarify", {"question": question,
                                             "reason": resolved.note})
        route_label, source, confidence = "CLARIFY", "none", None
    else:
        route_id, params = explainer.classify(resolved.text)
        if route_id == "ledger-refusals" and ledger is not None:
            params = {**params, "refusals": [r.model_dump(mode="json")
                                             for r in ledger.recent_refusals()]}
        if route_id != "unsupported":
            bundle = explainer.route(route_id, params)
            route_label, source, confidence = route_id, "deterministic", None
        else:
            route_label, source, confidence, bundle = _interpret_and_route(
                explainer, resolved.text, interpreter)

    register = register_of(bundle)
    # Make the resolution visible (CU2): the answer shows the question it answered.
    if resolved.resolved:
        bundle.question = resolved.text

    if ledger is not None:
        ledger.record(
            verbatim_question=question,
            resolved_question=resolved.text,
            route=route_label,
            source=source,
            confidence=confidence,
            answer_register=register,
            schedule_id=schedule_id,
            session_id=session_id,
        )

    return AskResult(bundle=bundle, resolved_question=resolved.text,
                     route=route_label, source=source, confidence=confidence,
                     register=register, resolution_note=resolved.note)


def _interpret_and_route(explainer: Any, question: str,
                         interpreter: Optional[Interpreter]):
    """The interpreter fallback (CU1) + the tiered bridge (CU4). Returns
    (route_label, source, confidence, bundle)."""
    interp = interpreter.interpret(question) if interpreter is not None else None
    if interp is None or interp.route == "none" or interp.confidence < CONF_MODERATE:
        return "REFUSED", "none", (interp.confidence if interp else None), \
            explainer.route("unsupported", {"question": question})

    resolved_params, all_ok = resolve_params(explainer, interp)
    if interp.confidence >= CONF_HIGH and all_ok:
        params = {**resolved_params,
                  "question": canonical_question(interp.route, resolved_params)}
        bundle = explainer.route(interp.route, params)
        # A route whose assembler still couldn't resolve (e.g. an unknown order)
        # degrades to a near-miss rather than a bare "unknown" dead end.
        if bundle.subject_type not in ("unsupported",):
            return interp.route, "llm", interp.confidence, bundle

    # Moderate confidence OR partial params → the near-miss bridge (CU4).
    offers, routes = _nearest_offers(interp, resolved_params)
    lead = NEAR_MISS_LEAD.format(q=question)
    bundle = explainer.route("near-miss", {"question": question, "lead": lead,
                                           "offers": offers, "routes": routes})
    return "NEAR_MISS", "llm", interp.confidence, bundle
