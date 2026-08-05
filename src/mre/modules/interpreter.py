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

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Optional

from mre.contracts.parse import (
    ClarifyReason,
    FollowupKind,
    Intent,
    MoveDirection,
    ParsedQuestion,
    Polarity,
    SECOND_TIER_INTENTS,
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
    # `MODEL_UNREACHABLE` is deliberately ABSENT, as `SET_REFERENCE` is: it never
    # reaches the clarify bundle. The dispatch answers it with the OUTAGE floor
    # before anything here can run, because it is not a question back — there is
    # nothing to ask about a question that was never read (micro-session 4A).
}

# Intents whose assemblers reason over TWO orders (the swap/move bridge and the
# absence pair) — the dispatch hands them the subject list in the planner's order.
_TWO_ORDER_INTENTS = frozenset({Intent.SWAP_MOVE, Intent.GAP_BETWEEN})

#: Session 4B.27 Item 4 — the intents that must NOT carry the silent-drop note.
#:
#: The two-order routes use both subjects, so there is nothing to disclose. The
#: plan-wide ones (`late-orders`, `inventory`, the opener…) are about the whole
#: book and a named order is a filter, not a dropped subject. Everything else
#: gets the note when it hears more orders than it can weigh — the default is
#: DISCLOSE, so a route added later inherits the honesty rather than having to
#: remember it.
_UNUSED_SUBJECT_INTENTS_EXEMPT = _TWO_ORDER_INTENTS | frozenset({
    Intent.LATE_ORDERS, Intent.INVENTORY, Intent.LATENESS_CAUSE,
    Intent.EXCLUDED_ORDERS, Intent.BRIEFING, Intent.SCHEDULE,
    Intent.CUSTOMER_SCHEDULE, Intent.INTEGRITY_CHECK, Intent.DATA_PROBLEMS,
    Intent.UNKNOWN_ENTITY, Intent.PROVE_IT, Intent.DRILL_DOWN,
})

#: Session 4B.14 Item 5(d) — the intents whose answer is about ONE OPERATION, and
#: therefore the only ones that may read the board selection's operation scope.
#: Kept narrow deliberately: a selection that could re-scope `downtime` or
#: `late-orders` would change what a plant-wide question means without saying so.
_OPERATION_SCOPED_INTENTS = frozenset(
    {Intent.WHY_HERE, Intent.START_REASON, Intent.CONTESTED_FACT,
     # Session 4B.16 Item 1: the counterfactual is scoped to ONE operation for
     # exactly the reason the blocker analysis is — asked with a bar selected,
     # it must answer about THAT bar and not the order's first operation.
     Intent.WHAT_WOULD_CHANGE,
     # Session 4B.15 Item 3: "is this one splittable" asked with an operation
     # selected must read THAT operation, not the order's first one — the same
     # mis-scoping 4B.14 Item 5(d) fixed for the other three.
     Intent.ATTRIBUTE_LOOKUP})

#: Session 4A.x (the listening docket) Item 1 — the intents whose ASSEMBLER
#: READS ``op_seq`` at all, whatever channel supplied it. This is a DIFFERENT
#: question from the one above and the difference is deliberate:
#:
#:   _OPERATION_SCOPED_INTENTS  — may a BOARD SELECTION re-scope this answer?
#:                                Narrow, because a selection persists after the
#:                                planner has stopped thinking about it.
#:   _GRAIN_HONOURING_INTENTS   — can this route answer about ONE OPERATION when
#:                                the planner TYPED one? Wider, because a typed
#:                                "op30" is explicit and can never be stale.
#:
#: `why-on-machine` is exactly the member that separates them (4B.21 Item 3 gave
#: it an `op_seq`; it takes a typed one and is not selection-re-scopable), and
#: reading the narrow set as though it answered the wide question is what made
#: the first version of this disclosure tell a planner that `why-on-machine` had
#: dropped a grain it had in fact honoured. A route OUTSIDE this set discloses
#: that it answered at order level; a route inside it says nothing, because it
#: did what was asked.
_GRAIN_HONOURING_INTENTS = _OPERATION_SCOPED_INTENTS | frozenset(
    {Intent.WHY_ON_MACHINE})

# The rolling (sliced-world) intents. On a monolithic run these degrade through the
# normal route table; the rolling document pre-route is upstream in the API.
ROLLING_INTENTS = frozenset(
    {Intent.BEYOND_HORIZON, Intent.WHY_NOT_SCHEDULED_YET, Intent.FROZEN,
     # Session 4B.6 — the coarse zone's two shapes are rolling intents for the
     # same reason the other three are: they speak about the sliced world, whose
     # state lives in the document's RollingBlock and not in the window-0
     # snapshot the Explainer reads.
     Intent.COARSE_FIT, Intent.BUCKET_LOAD})


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
    #: The probation comparison, when a promoted route on probation answered and
    #: the caller supplied a shadow runner (R-AI5(7)).
    shadow: Any = None


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

# ---------------------------------------------------------------------------
# R-MT1 (Session 4A teaching-graft (d.1), docs/04 2026-08-04) — CARRIED ANSWER
# STATE IS SCHEDULE-SCOPED.
#
# THE MEASURED FAILURE. The (d.0) recon drove one conversation across an
# in-place version rebind — what `main.js::onVersionChange` does after an
# accepted edit, a boundary move or a publish: it rebinds the schedule id,
# clears the board selection, and touches nothing else. Board A (386 bars, 102
# late orders), then board B (56 bars, nothing late at all):
#
#     planner [A]: how many orders are late and what is the total tardiness cost
#     answer  [A]: 102 late order(s): Of the 280 orders known to this plan ...
#     -- accept: the cockpit rebinds to board B --
#     planner [B]: show me the evidence for that
#     answer  [B]: here is the whole record set it was assembled from
#                  (102 record(s)):
#                  - lateness_minutes = 5297.0 min for ORD-000001 [record: 2aafb20c]
#                  ... 101 more
#
# Board A's record ids, with board A's figures, served to a planner looking at
# board B — on which every one of those ids is absent from the evidence index
# and no order is late. Confirmed in a real browser in (d.1): after a real
# `drag.accept()` the next /ask went to the CHILD's url carrying the PARENT's
# conversation turn verbatim (`tests/cockpit/carriedstate.spec.mjs`).
#
# THE CAUSE IS THE KEY. All three answer-bearing stores were keyed by SESSION
# ID ALONE. `ParseMemory.key` already carried `"sched"` — which is why the parse
# cache was safe and these three were not.
#
# So: every store that carries a prior ANSWER or its records is keyed by
# (session_id, schedule_id). A read against a different schedule id is
# impossible BY CONSTRUCTION — the key does not exist — rather than by a caller
# remembering to check. `forget` still takes a SESSION and clears every schedule
# under it: "forget what we were talking about" is about the conversation, and a
# conversation that straddled two boards (the defect above) must still clear
# whole.
# ---------------------------------------------------------------------------

#: The key every carried-answer store uses. ``None`` when there is no session to
#: key on, which every writer treats as "do not remember" and every reader as
#: "nothing carried" — the pre-R-MT1 behaviour for a session-less caller,
#: unchanged.
def _carry_key(session_id: Optional[str],
               schedule_id: Optional[str]) -> Optional[tuple[str, str]]:
    if not session_id:
        return None
    return (session_id, schedule_id or "")


def _forget_session(store: dict, session_id: Optional[str]) -> None:
    """Drop EVERY schedule's entry for one session. See the clause above."""
    if not session_id:
        return
    for key in [k for k in store if k[0] == session_id]:
        store.pop(key, None)


def _held_elsewhere(store: dict, session_id: Optional[str],
                    schedule_id: Optional[str]) -> bool:
    """Does this session carry an answer, but about a DIFFERENT schedule?

    R-MT1 clause 3's input. It is the one question the composite key cannot
    answer by itself: a miss is a miss, and "there was never an answer" and
    "the answer was about the plan you were looking at a moment ago" are
    different things to say to a planner."""
    if not session_id:
        return False
    want = schedule_id or ""
    return any(k[0] == session_id and k[1] != want for k in store)


class SynthesisMemory:
    """The last synthesis answer per (session, schedule), bounded and
    oldest-first-evicted. Keyed per R-MT1 clause 1 — see the block above."""

    def __init__(self, limit: int = 32) -> None:
        self._limit = limit
        self._by_session: dict[tuple[str, str], Any] = {}

    def remember(self, session_id: Optional[str], schedule_id: Optional[str],
                 answer: Any) -> None:
        key = _carry_key(session_id, schedule_id)
        if key is None or answer is None:
            return
        self._by_session.pop(key, None)
        self._by_session[key] = answer
        while len(self._by_session) > self._limit:
            self._by_session.pop(next(iter(self._by_session)))

    def last(self, session_id: Optional[str],
             schedule_id: Optional[str]) -> Any:
        key = _carry_key(session_id, schedule_id)
        return self._by_session.get(key) if key is not None else None

    def forget(self, session_id: Optional[str]) -> None:
        _forget_session(self._by_session, session_id)

    def held_elsewhere(self, session_id: Optional[str],
                       schedule_id: Optional[str]) -> bool:
        return _held_elsewhere(self._by_session, session_id, schedule_id)


#: The process-wide memory the API ask path uses. Tests construct their own.
SYNTHESIS_MEMORY = SynthesisMemory()


# ---------------------------------------------------------------------------
# The ANSWER memory — the last answer of ANY register, per ask session
# (Session 4B.22, docs/04 2026-07-31 drill-down ruling).
#
# WHY THIS EXISTS, AND WHY ``SynthesisMemory`` WAS NOT ENOUGH. A stranger's second
# question is a follow-up, and the most obvious follow-up in an interrogable
# product is "show me the evidence for that". Measured on the pinned board, one
# turn after an answer that cited a real record and lit three bars:
#
#     planner: why is ORD-000013 op20 on PAINT-01
#     answer : ... there was no alternative to weigh [record: 47f106af...]
#     planner: show me the evidence for that
#     answer : I don't have a claim of my own open to ground.
#
# The citation was on the previous turn. Nothing kept it. ``SynthesisMemory``
# holds the second tier's CLAIMS, and a contracted route has no claims — worse,
# `run_ask` deliberately FORGETS the synthesis memory the moment a contracted
# route answers, so after any route turn there is provably nothing to ground.
# The resolution ladder (4B.5: card > selection > last-subject > history) has no
# rung for a citation SET either: it resolves WHO the question is about, never
# WHAT WE SAID. So "that" bound ORD-000013 correctly and still grounded nothing.
#
# This is the missing rung. It remembers the last DELIVERED answer's records —
# not its text, not its claims — so a drill-down can open them. It is read-only
# derived state about our own output: no write path into the canonical model or
# the evidence store (M10), bounded, in-process, and cleared by the same gesture
# that clears every other server-side conversation channel.
# ---------------------------------------------------------------------------

class AnswerMemory:
    """The last answer per session — its route, its question and its records.

    Records are kept as the raw evidence dicts the bundle carried, because that
    is what the prove-it assembler already knows how to summarize. An answer
    with NO records is remembered too, and that is the point: "this answer was
    authored copy and cites nothing" is a different, honest answer from "I have
    no answer of my own open", and the product could not tell them apart.
    """

    def __init__(self, limit: int = 32) -> None:
        self._limit = limit
        self._by_session: dict[tuple[str, str], dict] = {}

    def remember(self, session_id: Optional[str], schedule_id: Optional[str],
                 route: str, question: str, records: Any,
                 register: str = "") -> None:
        key = _carry_key(session_id, schedule_id)
        if key is None:
            return
        rows = [r for r in (records or []) if isinstance(r, dict)]
        self._by_session.pop(key, None)
        self._by_session[key] = {
            "route": route or "?", "question": question or "",
            # Session 4A teaching-graft (d.1), D-06: the REGISTER of the answer
            # that is being remembered. A prove-it on an answer with no records
            # has to say which KIND of nothing it is, and record count alone
            # cannot tell a capability statement from a board read that came
            # back empty — see `_prove_it_bundle`.
            "register": register or "",
            "records": rows, "record_count": len(rows)}
        while len(self._by_session) > self._limit:
            self._by_session.pop(next(iter(self._by_session)))

    def last(self, session_id: Optional[str],
             schedule_id: Optional[str]) -> Optional[dict]:
        key = _carry_key(session_id, schedule_id)
        return self._by_session.get(key) if key is not None else None

    def forget(self, session_id: Optional[str]) -> None:
        _forget_session(self._by_session, session_id)

    def held_elsewhere(self, session_id: Optional[str],
                       schedule_id: Optional[str]) -> bool:
        return _held_elsewhere(self._by_session, session_id, schedule_id)


#: The process-wide answer memory the API ask path uses. Tests construct their own.
ANSWER_MEMORY = AnswerMemory()


# ---------------------------------------------------------------------------
# THE TERM MEMORY — which of OUR WORDS this planner has actually been shown
# (R-TE1 clause (1), Session 4A teaching-graft (d.3)).
#
# THE FOUNDING SPECIMEN. A contracted route said "seed" nine times and the
# planner asked what it meant; the entity clarify and the capability coach each
# refused, because neither could hear a question about the product's own
# vocabulary. What makes this answerable WITHOUT becoming a documentation
# browser is the trigger contract: **we explain words we said**, and what we
# said is a property of the RENDERED TEXT rather than of anything a model
# remembers.
#
# WHY A STORE RATHER THAN A CONTEXT FIELD. The client already carries history,
# and the obvious cheap move is to have the panel compute the terms and send
# them. That is a rule living in the client — the precise defect R-LD6 clause
# (5) had just finished removing from three places. The rule lives here; the
# clients send nothing new.
#
# KEYED (session, schedule) ON R-MT1's OWN KEY, and cleared by the ONE clear.
# A term from a PREVIOUS BOARD's answers must not confirm the intent after a
# rebind: the planner is looking at a different plan, and "you said seed" would
# be citing a conversation about something else. 4B.16a's lesson is that a store
# with its own separate clear is a store that outlives the conversation, so this
# one is forgotten by `forget_deliveries` beside the other three.
# ---------------------------------------------------------------------------

class TermMemory:
    """The glossary terms this session has been SHOWN, per (session, schedule).

    Bounded twice over: by the LRU on sessions, and by the glossary itself —
    the value is a subset of a closed authored vocabulary, so it cannot grow
    with the conversation the way an answer store can.
    """

    def __init__(self, limit: int = 32) -> None:
        self._limit = limit
        self._by_session: dict[tuple[str, str], set[str]] = {}

    def remember(self, session_id: Optional[str], schedule_id: Optional[str],
                 terms: Any) -> None:
        key = _carry_key(session_id, schedule_id)
        if key is None or not terms:
            return
        seen = self._by_session.pop(key, set())
        seen |= set(terms)
        self._by_session[key] = seen
        while len(self._by_session) > self._limit:
            self._by_session.pop(next(iter(self._by_session)))

    def seen(self, session_id: Optional[str],
             schedule_id: Optional[str]) -> frozenset[str]:
        key = _carry_key(session_id, schedule_id)
        return frozenset(self._by_session.get(key, ()) if key is not None else ())

    def forget(self, session_id: Optional[str]) -> None:
        _forget_session(self._by_session, session_id)


#: The process-wide term memory the API ask path writes after every render.
TERM_MEMORY = TermMemory()


def remember_terms(session_id: Optional[str], schedule_id: Optional[str],
                   answer: str) -> frozenset[str]:
    """Record which of our words this RENDERED answer showed the planner.

    Called with the text the planner actually saw — after the renderer, not
    before — because the trigger contract is about what was SAID. Returns what
    it recorded, so a harness can assert on it.
    """
    from mre.modules.glossary import terms_in
    found = terms_in(answer or "")
    TERM_MEMORY.remember(session_id, schedule_id, found)
    return found

#: Routes whose answer is ABOUT a previous answer rather than about the plan.
#: Remembering one would make a second "show me the evidence" drill into the
#: drill-down instead of into the answer the planner is still looking at.
#:
#: Session 4A teaching-graft (d.1): `drill-down` joins it, now that D-01 has
#: wired it to the same store. Its declared meaning is *"open the full record
#: behind something the assistant JUST said"* — it is never a fresh read of the
#: plan, including on its ordinal branch, where it opens item N of a list a
#: previous answer gave. Remembering it would make the second "show me that"
#: drill the drill-down, which is the exact behaviour this tuple exists to
#: prevent and which 4B.22 already asserts for `prove-it` over two turns.
_NOT_REMEMBERED = ("prove-it", "drill-down")


# ---------------------------------------------------------------------------
# THE LAST-ANSWER RUNG'S CONTENT — R-LD6 clause (5), Session 4A teaching-graft
# (d.2).
#
# The resolution ladder's third rung is fed by ONE question: *what was the last
# turn about?* Until now the only thing that could answer it was the ANSWER's
# own rendered subject, through the five `subject_type` literals below — five of
# the **45** this codebase emits (censused this session; the (d.0) dossier's
# "5 of 33" undercounted the denominator, not the gap).
#
# THE FOUNDER'S SPECIMEN, AND WHAT IT PROVED. Measured 3/3 as a held pair on the
# demo board, one word apart:
#
#   A  "why is ORD-000252 on CUT-01 WHEN IT IS"  -> CLARIFY; carry {}
#   B  "why is ORD-000252 on CUT-01"             -> why-on-machine; carry {order}
#   both then: "why is it scheduled when it is"
#
# In BOTH arms the parse RESOLVED `ORD-000252` from the planner's own typing. In
# arm A the clarify bundle renders `subject_external_name="?"` — truthfully, it
# could not answer — and the carry channel, which reads the BUNDLE, therefore
# took nothing. The planner named an order, the product resolved it, and one
# turn later the deterministic memory of it was empty. Arm A's follow-up landed
# on a DIFFERENT ROUTE from arm B's, 3 runs of 3, and only got there at all
# because the parse model re-read it out of the RECENT TURNS block (R-LD5's
# `conversation` source) — a model behaviour standing in for the deterministic
# rung that was supposed to be underneath it.
#
# THE RULE, AND IT IS R-LD5's LOGIC ONE STEP EARLIER: a subject is a property of
# the planner's SENTENCE and survives the route that sentence drew. A route that
# could not answer still had a subject.
#
# ADDITIVE BY CONSTRUCTION, which is what makes it provable: clause (1) is the
# shipped behaviour, unchanged and first. Clause (2) can only fill a carry that
# would otherwise have been EMPTY. No carry that is populated today changes.
#
# NEVER GUESSED. Two distinct resolved orders in one question carry NO order —
# the same refusal `_resolve_machine` already makes on an ambiguous token. A
# question about two orders is not a question about the first one.
# ---------------------------------------------------------------------------

#: Kept in lockstep with `askpanel.js` ORDER_SUBJECTS / MACHINE_SUBJECTS and
#: `ai_exam.runner`'s copies — clause (1) is those sets, and they move together
#: or the harness measures a product nobody ships.
CARRIED_ORDER_SUBJECT_TYPES = frozenset(
    {"demand", "start_reason", "contested_fact", "order_attributes"})
CARRIED_MACHINE_SUBJECT_TYPES = frozenset({"machine_idle"})

#: Placeholder subject names that mean "no subject", not a subject called that.
_SUBJECT_PLACEHOLDERS = frozenset({"", "?", "all"})


def _unique_parsed_ref(parsed: Any, kind_value: str) -> Optional[str]:
    """The ONE ref of this kind the parse resolved, or None (including when it
    resolved two different ones — ambiguity carries nothing)."""
    refs = {s.ref for s in (getattr(parsed, "subjects", None) or [])
            if getattr(getattr(s, "kind", None), "value", None) == kind_value
            and s.ref}
    return next(iter(refs)) if len(refs) == 1 else None


def carry_subject(bundle: Any, parsed: Any = None) -> dict:
    """What this turn contributes to the next turn's LAST-ANSWER rung.

    R-LD6 clause (5). Clause (1) — the answer's own subject, where the bundle
    names one of the five carried types — is unchanged and wins. Clause (2) — the
    subject the PARSE resolved for this question — applies only where clause (1)
    is empty, so this can add a carry and can never alter one.

    Returns ``{}``, ``{"order": ref}``, ``{"machine": ref}`` or both. The panel
    and the exam runner both read this ONE definition rather than each holding
    their own (the F3 discipline: one definition, three sites).
    """
    subject_type = getattr(bundle, "subject_type", "") or ""
    name = (getattr(bundle, "subject_external_name", "") or "").strip()
    if name.lower() not in _SUBJECT_PLACEHOLDERS:
        if subject_type in CARRIED_ORDER_SUBJECT_TYPES:
            return {"order": name}
        if subject_type in CARRIED_MACHINE_SUBJECT_TYPES:
            return {"machine": name}
    if parsed is None:
        return {}
    out: dict = {}
    order = _unique_parsed_ref(parsed, "order")
    machine = _unique_parsed_ref(parsed, "machine")
    if order:
        out["order"] = order
    if machine:
        out["machine"] = machine
    return out


# ---------------------------------------------------------------------------
# The parse memory — what makes the two-phase ask FREE (Session 4A.5c CU3a).
# ---------------------------------------------------------------------------

class ParseMemory:
    """A bounded, short-lived cache of PARSES, keyed by exactly what produced them.

    Why it exists. CU3(a) wants the panel to show an honest waiting state the
    moment the second tier starts, because a planner who waits ~1.3s for a proven
    answer will wait ~10s for a reasoned one — but not silently, and not without
    knowing which they are getting (4A.5b rider c). Knowing WHICH TIER will answer
    means running the parse first, and a preflight that re-parses would double
    every question's parse cost to buy a spinner on one question in ten.

    So the preflight parses ONCE and remembers; the ask that follows finds the same
    parse and skips its own. Total model calls are unchanged.

    What this is NOT: it is not client-supplied routing. The cache holds OUR parse,
    computed server-side, and the key includes the full context — a question asked
    again with a different board selection is a different key and is re-parsed. A
    client can at worst cause its own parse to be reused within seconds of itself.
    Like ``SynthesisMemory`` this is the AI layer's own output held in process; it
    is not state in the canonical model or the evidence store (M10 has no write
    path)."""

    def __init__(self, limit: int = 64) -> None:
        self._limit = limit
        self._entries: dict[str, Any] = {}

    @staticmethod
    def key(question: str, context: Optional[dict], session_id: Optional[str],
            schedule_id: Optional[str]) -> str:
        import hashlib
        import json as _json
        context = context or {}
        card = context.get("card") or {}
        payload = _json.dumps({
            "q": (question or "").strip().lower(),
            "sel": context.get("selection") or {},
            "last": context.get("last_answered_subject") or {},
            "hist": [t.get("question") for t in (context.get("history") or [])][-4:],
            "sid": session_id or "",
            "sched": schedule_id or "",
            # Session 4B.5 CU2: the card is part of what produced the parse — the
            # same words asked with a card open and with it dismissed are two
            # different questions, so they must be two different keys.
            "card": [bool(card.get("open")), card.get("order"),
                     card.get("machine"), card.get("correlation_id")],
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def remember(self, key: str, parsed: Any) -> None:
        if parsed is None:
            return
        self._entries.pop(key, None)
        self._entries[key] = parsed
        while len(self._entries) > self._limit:
            self._entries.pop(next(iter(self._entries)))

    def take(self, key: str) -> Any:
        """Read AND evict. A parse is consumed by the ask it was made for; leaving
        it behind would let a later identical question skip a parse that should
        have seen a changed world."""
        return self._entries.pop(key, None)


#: The process-wide parse memory the API preflight/ask pair uses.
PARSE_MEMORY = ParseMemory()


#: Which TIER a parse will be answered by — the preflight's whole output, and the
#: only thing the panel needs to choose a waiting state. Derived from the SAME
#: dispatch rules the answer will follow, never re-decided.
def tier_of(parsed: Any, explainer: Any = None) -> str:
    """"route" | "synthesis" | "floor". Computed from the parse contract.

    ``explainer`` is optional because the preflight is a PACING HINT and must never
    be the reason an answer fails. Without it the other-kind rescue cannot be
    evaluated and a clarify reads as the floor — the conservative miss, since it
    only means a waiting state is not shown for a turn that turns out to reason."""
    if parsed is None:
        return "floor"
    # Micro-session 4A: an unreachable model answers with the OUTAGE floor, and
    # the floor tier is what makes the panel show NO waiting state. Without this
    # the preflight reads it as `synthesis` (the clarify leads nowhere, the
    # intent is unmatched) and a planner watches "Reading the evidence…" for a
    # read that cannot happen, then gets a card saying nothing was read.
    if (parsed.clarify is not None
            and parsed.clarify.reason is ClarifyReason.MODEL_UNREACHABLE):
        return "floor"
    # Session 4B.5 CU2: the open-card route answers from the card, always and
    # instantly — ahead of the clarify test, exactly as the dispatch does it.
    if parsed.intent is Intent.OPEN_CARD:
        return "route"
    if parsed.clarify is not None and not _clarify_leads_nowhere(
            explainer, parsed, route_params(parsed, parsed.question)):
        return "floor"
    if parsed.followup_of is FollowupKind.PROVE_IT or \
            parsed.intent is Intent.PROVE_IT:
        return "route"
    # R-TG2: `teaching` reasons over the evidence exactly as `unmatched` does —
    # it is the same tier under a longer budget — so the pacing hint must show
    # the same waiting state. Reading it as `route` would promise an instant
    # answer for the one intent whose answer is deliberately the longest.
    if parsed.intent in SECOND_TIER_INTENTS or parsed.confidence < CONF_MATCH:
        return "synthesis"
    if parsed.dropped_qualifier:
        return "synthesis"
    return "route"


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
        # Session 4B.5 CU2 — the top of the ladder. Named explicitly rather than
        # folded into the selection wording: "from the move you have open" is a
        # different claim about why we chose this subject, and the planner should
        # be able to disagree with it.
        if s.source is SubjectSource.CARD:
            bits.append(f"resolved against {s.ref} (from the move you have open)")
        elif s.source is SubjectSource.SELECTION:
            bits.append(f"resolved against {s.ref} (from board selection)")
        elif s.source is SubjectSource.LAST_ANSWER:
            bits.append(f"resolved against {s.ref}")
        elif s.source is SubjectSource.HISTORY:
            bits.append(f"resolved against {s.ref} (from earlier in this conversation)")
        # R-LD5 (Session 4A teaching-graft (d.1)) — DISCLOSURE FOLLOWS THE
        # SUBJECT, NOT THE RESOLVER. The four rungs above are the LADDER's
        # resolutions; this one is the PARSE MODEL's, read out of the RECENT
        # TURNS block when every rung was empty. R-LD2's rule ("every resolution
        # the ladder made is disclosed") is the special case, not the boundary:
        # what a planner needs to know is that a subject they did not supply in
        # this sentence was supplied for them, and by what.
        #
        # Same surface, same prominence, different wording — "from what you
        # asked earlier" is a different claim from "from earlier in this
        # conversation" (the HISTORY rung reads the turn's SUBJECT REFS, which
        # come off the board selection; this reads the previous question's
        # WORDS), and a planner should be able to disagree with each on its own
        # terms.
        elif s.source is SubjectSource.CONVERSATION:
            bits.append(f"resolved against {s.ref} (read from what you asked "
                        f"earlier — you didn't name it in this question)")
        elif s.raw and s.raw.upper() != s.ref.upper():
            bits.append(f"assuming {s.ref}")
    # Session 4B.27 Item 4 — A SUBJECT WE HEARD AND CANNOT USE IS NAMED.
    #
    # "why can't ord-11 start right after ord-19" resolved BOTH orders and was
    # answered about one, with nothing on the surface saying the other had been
    # dropped. `route_params` carries `orders[0]` and 11 of the 13 order-taking
    # routes have no second slot (the census), so this is the shape of every
    # two-subject question outside `gap-between` and `swap-move`.
    #
    # The remedy is not to make eleven assemblers two-subject — most of them
    # genuinely answer about one thing. It is that a planner must never be left
    # believing we weighed a relation we never looked at. Computed HERE, at the
    # one seam every route passes, so no assembler can forget it.
    if len(_UNUSED_SUBJECT_INTENTS_EXEMPT & {parsed.intent}) == 0:
        extra = [s.ref for s in parsed.of_kind(SubjectKind.ORDER) if s.resolved][1:]
        if extra:
            bits.append(
                f"answered about the first subject only — {', '.join(extra)} "
                f"was named too and this route weighs one order at a time")
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


#: The intents whose EARLIER default is certain once `move_direction` is
#: `unstated` — i.e. where the dispatch can promise which way the answer went.
#: `swap-move` is absent because its take reads the direction itself, and
#: `what-would-change` is conditional (a NAMED TARGET may resolve LATER against
#: the calendar, inside the assembler), so it is admitted below only when the
#: planner named no target. A disclosure that states the wrong direction is
#: worse than the silence it replaces.
_EARLIER_BY_DEFAULT = frozenset({Intent.WHY_HERE, Intent.WHAT_WOULD_CHANGE})

#: THE MOBILITY FAMILY — every intent a "this can't be moved" question is known
#: to reach (Session 4A.y Item 1, the founder listening round).
#:
#: MEASURED, NOT DESIGNED, and the measurement is the reason the set exists.
#: The listening docket put the premise check on `why-here` because that is
#: where its four specimens landed. The founder's round then landed the same
#: family on `what-would-change` and got an uncorrected earlier-only answer, and
#: an 18-phrasing census on the demo board (`rolling-db5395dc-2ae`) put numbers
#: on it:
#:
#:     why-here            11   floor runs
#:     frozen               5   floor never ran
#:     what-would-change    2   floor never ran
#:
#: So the route a mobility question reaches is a MODEL's decision, made per
#: turn, sensitive to the conversation before it — and a check wired to one
#: route is a check that fires when the model happens to agree with it. The
#: family is the invariant; the route is not.
#:
#: WHY NOT BAR THE OTHER TWO INSTEAD (the brief's option (b)): barring an intent
#: on the strength of the question's words is a deterministic classifier
#: deciding a route, which R-AI5 forbids and which this codebase has deleted
#: three times. The parse reports; the dispatch decides what to ADD. So every
#: member runs the floor, and each renders it in its own shape.
#:
#: Adding a member is cheap and safe (a premise check and a lead); omitting one
#: is the defect. `start-reason` and `swap-move` are deliberately ABSENT — the
#: census never saw the family reach either, and a member added on a hunch would
#: make this list an argument wearing a measurement's clothes (R-CAL1's rule).
_MOBILITY_FAMILY_INTENTS = frozenset({
    Intent.WHY_HERE, Intent.WHAT_WOULD_CHANGE, Intent.FROZEN,
})

def _apply_mobility_floor(parsed: ParsedQuestion, params: dict,
                          selection: Optional[dict] = None) -> None:
    """THE FLOOR, for whichever family route is about to run (4A.y Item 1).

    Called from BOTH dispatch paths — the ordinary matched-intent path and the
    ROLLING early return, which `frozen` takes. That second call site is the
    whole point: `frozen` returns before the matched-intent path is reached, so
    a floor written once, in the obvious place, would have covered two of the
    family's three members and looked complete.
    """
    if parsed.intent not in _MOBILITY_FAMILY_INTENTS:
        return
    from mre.modules.mobility_premise import asks_about_moving, states_direction
    if not asks_about_moving(parsed.question):
        return
    # THE PLANNER'S OWN WORDS DECIDE WHETHER ANYTHING WAS ASSUMED — never the
    # parse's `move_direction`, which this round measured INVENTING a direction
    # ("this cant move can it" -> EARLIER) as surely as the last one measured it
    # omitting one. A named target is a stated direction too: the calendar
    # resolves "can this move to Friday", and the planner did point somewhere.
    if states_direction(parsed.question) or parsed.move_target:
        return
    params["mobility_family"] = True
    params["move_direction_assumed"] = True
    # The bar the LEAD is about. `frozen` answers at ORDER grain and is not
    # selection-re-scopable (`_OPERATION_SCOPED_INTENTS` is narrow for a good
    # reason), but a premise about mobility is a premise about ONE BAR, and the
    # bar in question is the one under the pointer. Kept in its own keys so no
    # route's own scope is touched, and the lead NAMES the operation it assessed
    # so the two grains in one answer are never ambiguous.
    sel = selection or {}
    params["mobility_op_seq"] = params.get("op_seq") if \
        params.get("op_seq") is not None else sel.get("op_seq")
    params["mobility_machine"] = params.get("machine") or sel.get("machine")
    # The EARLIER default is `why-here`'s alone: it is the only member whose
    # answer IS a direction. Claiming one for the other two would be the
    # over-disclosure R-LD2 narrowed against.
    if parsed.intent is Intent.WHY_HERE and not params.get("move_direction"):
        params["move_direction"] = MoveDirection.UNSTATED.value
        params["move_direction_source"] = "floor"


def _apply_audience_floor(parsed: ParsedQuestion, params: dict) -> None:
    """R-TG4 — DOES THIS QUESTION NAME A PERSON WHO HAS TO BE TOLD?

    The parse REPORTS ``audience`` (prompt v18); this is the floor under the
    report, for the reason 4A.y measured and named: a freshly-prompted field was
    reported 0 times in 5 on the phrasings planners actually use, and a
    disclosure that depends on a model remembering a field will silently stop.
    The planner's own words win where the model supplied none.

    Like the mobility floor it can only ever ADD to a route that was already
    going to run — nothing here can change WHICH route answers (R-AI5(2): no
    deterministic classifier returns).
    """
    from mre.modules.audience_shape import names_an_audience
    audience = (parsed.audience or "").strip() or names_an_audience(
        parsed.question)
    if audience:
        params["audience"] = audience


def _attach_audience_shape(bundle: Any, params: dict) -> None:
    """Compose the audience shape from what the route ACTUALLY assembled, and
    hang it on the bundle under a key of its own (R-TG4).

    Composed AFTER the route ran, never before, so the account and the lever are
    read off the figures that route computed rather than derived a second time
    (4B.21's discipline). Where nothing composes, nothing is attached and the
    answer renders exactly as it does today."""
    if not params.get("audience"):
        return
    if not isinstance(getattr(bundle, "key_facts", None), dict):
        return
    from mre.modules.audience_shape import compose
    shape = compose(getattr(bundle, "subject_type", ""), bundle.key_facts,
                    params["audience"])
    if shape is not None and shape.usable:
        bundle.key_facts["audience_shape"] = shape


def _attach_mobility_lead(explainer: Any, bundle: Any, params: dict) -> None:
    """Hand a family route that did not compute its own verdict the one the
    dispatch computed, under a key of its own (4A.y Item 1).

    ``"mobility" in key_facts`` is the test rather than its truthiness: a
    `why-here` bundle that computed None has ANSWERED whether it could assess
    this bar, and re-asking here would be reaching for a second opinion after
    the first said "I can't tell"."""
    if not params.get("mobility_family"):
        return
    if not isinstance(getattr(bundle, "key_facts", None), dict):
        return
    if "mobility" in bundle.key_facts:
        return
    seq = params.get("mobility_op_seq")
    if seq is None:
        seq = params.get("op_seq")
    lead = explainer.mobility_verdict(
        params.get("order"),
        params.get("mobility_machine") or params.get("machine"),
        seq, params.get("document"))
    if lead is not None:
        bundle.key_facts["mobility_lead"] = lead


def _with_assumptions(note: str, parsed: ParsedQuestion, params: dict) -> str:
    """The resolution note, plus every OTHER resolution the ladder DEFAULTED.

    THE MEASURED FAILURE (the listening docket, Item 2). "why cant this be
    moved", with ORD-000128 selected on the demo board:

        INTERPRETED AS: "why cant ORD-000128 be moved [from board selection]"

    Two assumptions were made and one was disclosed. The SUBJECT came from the
    board and the line says so. The DIRECTION — "moved" read as "moved EARLIER",
    because that is the only direction `why-here` computes — was silent, and the
    answer then served the earliest-start chain. The GRAIN was silent too: op20
    came from the same selection, and a planner reading "ORD-000128" has no way
    to know which of its four operations they were told about.

    THE RULE: A FIELD THE PLANNER STATED IS NEVER READ BACK TO THEM. Only a
    DEFAULTED resolution earns a line, which is what keeps the disclosure short
    enough to be read — and what makes its presence informative rather than
    decorative. `MoveDirection.UNSTATED` and `op_seq_source != "utterance"` are
    the two markings; both are facts the contract already carries.
    """
    bits: list[str] = []

    # -- THE GRAIN ---------------------------------------------------------
    seq = params.get("op_seq")
    src = params.get("op_seq_source") or ""
    if seq is not None and src == "selection":
        bits.append(f"and about op{seq}, the operation selected on the board")
    elif seq is not None and src == "utterance" \
            and parsed.intent not in _GRAIN_HONOURING_INTENTS:
        # ITEM 1's OTHER HALF: a route that answers at ORDER grain SAYS SO
        # rather than substituting. The remedy is not to make every assembler
        # operation-scoped — most of them genuinely answer about the whole
        # order — it is that a planner must never believe we looked at the step
        # they named when we looked at all of them. 4B.27 Item 4's shape, on
        # the grain axis instead of the second-subject axis.
        # Named rather than composed around a slot that can be empty: a question
        # can carry a step and no order ("what runs on op20 of CUT-01"), and
        # "answered for the whole of None" is the template nonsense R-AI3's C4
        # forbids.
        whole = f"the whole of {params['order']}" if params.get("order") \
            else "the whole order"
        bits.append(f"answered for {whole} — you named op{seq} and this route "
                    f"answers at order level")
    elif seq is not None and src == "conversation":
        # R-LD5 on the grain axis. Two shapes, because the honest sentence
        # differs: a route that HONOURS the grain has to say where the grain
        # came from, and one that does not has to say both that and that it
        # answered wider. Neither may say "you named op{seq}" — the planner
        # did not.
        if parsed.intent in _GRAIN_HONOURING_INTENTS:
            bits.append(f"and about op{seq}, read from your earlier question")
        else:
            whole = f"the whole of {params['order']}" if params.get("order") \
                else "the whole order"
            bits.append(f"answered for {whole} — op{seq} came from your earlier "
                        f"question and this route answers at order level")

    # -- THE DIRECTION -----------------------------------------------------
    # Read from PARAMS, not from the parse: the mobility floor above may have
    # supplied a direction the model did not report, and a disclosure that only
    # covers what the model remembered is the silence this item exists to end.
    # Session 4A.y Item 1: `unstated` OR the floor's own finding that the
    # planner's sentence named no direction. The second is needed because the
    # parse sometimes reports a direction nobody stated, and a disclosure that
    # only covers what the model admitted to assuming covers the wrong half.
    # It is still never claimed over a LATER answer — that would state the
    # wrong direction, which R-LD2 called worse than the silence it replaces.
    direction = params.get("move_direction")
    if (direction == MoveDirection.UNSTATED.value
            or params.get("move_direction_assumed")) \
            and direction != MoveDirection.LATER.value \
            and parsed.intent in _EARLIER_BY_DEFAULT \
            and not (parsed.intent is Intent.WHAT_WOULD_CHANGE
                     and parsed.move_target):
        bits.append("read as EARLIER — you didn't say which way, and this is "
                    "the direction I can compute a bound for")

    if not bits:
        return note
    return "; ".join([b for b in ([note] if note else []) + bits])


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
    # Session 4B.30 Item 1/2: WHICH WAY, and the planner's raw words for WHERE.
    # Carried, never interpreted here — the parse reports and the assembler
    # resolves against the calendar. `unstated` and absent are the same thing
    # to every assembler, which is what keeps the widening free for the
    # phrasings that have always meant "earlier".
    if parsed.move_direction is not None:
        params["move_direction"] = parsed.move_direction.value
    if parsed.move_target:
        params["move_target"] = parsed.move_target
    # Session 4B.14 Item 3: the parse's report of WHICH claim a contest disputes.
    # Carried, never interpreted here — the assembler decides what to do with it.
    if parsed.contested_claim is not None:
        params["contested_claim"] = parsed.contested_claim.value
        # A challenge that named its own route (`why-here` usually does) still
        # has to be ANSWERED as a challenge. The route reads this to say plainly
        # where the planner is right, per R-AI3(4); without it the answer is
        # correct, complete and reads as though nobody said anything.
        if parsed.intent is Intent.WHY_HERE:
            params["challenge"] = {"kind": parsed.contested_claim.value,
                                   "said": parsed.question}
    # Session 4A.x (the listening docket) Item 1 — THE GRAIN REACHES THE ROUTE.
    #
    # Eight assemblers read `params["op_seq"]` and NOTHING HERE HAD EVER SET IT.
    # On the live ask path the value came from exactly two places: the board
    # SELECTION (filled below, in `dispatch`, for five intents) and two routes
    # that re-scan the question text for themselves. So a planner who TYPED
    # "op30" was answered about op10 with a bridging sentence announcing the
    # fallback — the measured specimen, verbatim.
    #
    # Two sources, in this order, and the order is the ruling:
    #   1. THE PARSE (`subjects[].op_seq`, prompt v17). What the planner said.
    #   2. THE TEXT (`op_seq_in`). A deterministic EXTRACTION of a number the
    #      planner typed — never a route decision, so it is not the return of a
    #      deterministic classifier (R-AI5(2)); the nearest relatives are
    #      `claim_verifier` and `predicate_coverage`, both of which read an
    #      utterance after the route is already chosen. It exists because a
    #      grain silently dropped is the defect, and a model that forgets one
    #      field must not re-open it.
    # The board SELECTION is deliberately NOT here: it is the weakest channel,
    # it belongs to the dispatch (which knows which intents may be re-scoped by
    # it), and a typed "op30" must outrank a bar the planner clicked earlier.
    from mre.modules.attribute_lookup import op_seq_in
    named_seq = parsed.named_op_seq
    # R-LD5 — the grain travels with the subject, INCLUDING where it came from.
    # A grain the parse read out of an earlier question is not one the planner
    # typed here, and labelling it `utterance` is D-02 on the grain axis.
    seq_source = ("conversation"
                  if parsed.named_op_seq_source is SubjectSource.CONVERSATION
                  else "utterance")
    if named_seq is None:
        seq_source = "utterance"
        named_seq = op_seq_in(question_text)
        if named_seq is None and question_text != parsed.question:
            # A REWRITTEN question can lose the words (`routed_text` substitutes
            # canonical refs, and a canonical question names no step at all), so
            # the planner's own sentence is the fallback reading.
            named_seq = op_seq_in(parsed.question)
    if named_seq is not None:
        params["op_seq"] = named_seq
        # WHERE THE GRAIN CAME FROM, carried so the disclosure can tell an
        # assumption from a statement (Item 2). A planner is never told back
        # what they just said.
        params["op_seq_source"] = seq_source
    # Session 4B.27 Item 4 — EVERY RESOLVED SUBJECT IS CARRIED, not only the
    # first. `params["order"]` keeps its exact meaning (the primary subject), so
    # no existing assembler changes behaviour; this is the channel through which
    # a route that CAN use a counterpart gets one, and the evidence the
    # dispatch's silent-drop note is computed from.
    params["orders"] = list(orders)
    params["machines"] = list(parsed.refs(SubjectKind.MACHINE))
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
    # Session 4B.15 Item 3: an attribute lookup takes an ORDER, but a RESOURCE
    # field ("what is PAINT-01's capacity") is named by a machine instead. Same
    # shape as the gap explainer: either subject satisfies it.
    if intent is Intent.ATTRIBUTE_LOOKUP:
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


def _clarify_leads_nowhere(explainer: Any, parsed: ParsedQuestion,
                           params: dict) -> bool:
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
    resolved at all, asking IS the right move and this returns False.

    Session 4A.5c adds the case the arc-close sweep found, which is 4A.5b's
    other-kind rescue one branch further out. "whats holding CUT-01" parsed as
    `start-reason` with CUT-01 typed as an ORDER (unresolved, because it is a
    MACHINE) and hedged with `ambiguous-subject`. Nothing resolved, so the rule
    above said "asking is right" and the planner was asked which order they meant —
    about the machine on their screen. The rescue in the matched branch below would
    have caught it, and never ran, because a clarify short-circuits ahead of it.
    So an unresolved subject whose WORDS name a real entity of another kind counts
    as resolved for this decision: the second tier can read what they named, and
    asking cannot help."""
    if parsed.intent is Intent.UNMATCHED:
        return True
    if not any(s.resolved or _names_another_kind(explainer, s.kind, s.raw)
               for s in parsed.subjects):
        return False
    return any(not params.get(slot)
               for slot in _required_slots(parsed.intent, params))


def _names_another_kind(explainer: Any, kind: SubjectKind, raw: str) -> bool:
    """True when the planner's words resolve to a real entity of the OTHER kind —
    the parse typed a machine as an order, or the reverse. Resolution only; it
    decides no intent."""
    if not raw or explainer is None:
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


#: How far back a re-fire counts as a repeat (Session 4B.5 CU5b/c). Two turns:
#: long enough to catch "…" / "sorry, again?" and short enough that returning to a
#: question after a genuine detour reads as a fresh ask, not a nag.
REPEAT_WINDOW = 2


# Session 4A teaching-graft (d.1), D-10 — `_repeat_depth` IS GONE.
#
# It counted how many of the last REPEAT_WINDOW turns one route answered, and
# 4B.15 Item 4 reversed the inference it encoded ("several different questions
# reaching one route" is evidence about US, not about the planner repeating
# themselves). Its own docstring then said *"Callers must use `bundle_repeat`"*
# — and after that split it had NO caller under `src/` at all, only a test
# exercising the function directly. A declared-but-never-consumed helper with a
# deprecating docstring is a standing bug species in this repo: it reads as a
# live signal to whoever finds it next. Removed rather than preserved; the
# counting `bundle_repeat` actually does is inline and split by question.


def _normalize_q(text: str) -> str:
    """A question reduced to its content words, for same-question comparison.
    Punctuation, filler and word order survive nothing here: "how many are
    late?" and "how many are late" are the same ask; "is op20 splittable" and
    "can I make this one splittable" are not."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    drop = {"a", "an", "the", "is", "are", "do", "does", "did", "can", "could",
            "would", "will", "please", "tell", "me", "you", "i", "we", "so",
            "just", "again", "and", "of", "to", "for", "on", "in", "it",
            "that", "this", "what", "whats"}
    return " ".join(sorted(w for w in words if w not in drop))


def _same_question(a: str, b: str) -> bool:
    """True when two turns are the SAME ask. Deliberately strict: a Jaccard
    overlap above 0.8 on content words. Anything less is a different question,
    and a different question reaching the same route is the signal Item 4
    cares about."""
    sa, sb = set(_normalize_q(a).split()), set(_normalize_q(b).split())
    if not sa or not sb:
        return False
    return len(sa & sb) / max(len(sa | sb), 1) >= 0.8


#: Server-side memory of what was actually DELIVERED, per session. Keyed by
#: session id, holding the last few (route, question, answer fingerprint).
#:
#: It lives here rather than on the context channel because the panel's history
#: carries the question and the route but NOT the answer — and the answer is the
#: whole signal. "Several different questions produced ONE ANSWER" cannot be
#: read off a route id: turns 4 and 5 of the measured transcript share a route
#: and, once the route works, say completely different things.
#:
#: R-MT1 clause 1 (Session 4A teaching-graft (d.1)): keyed by (session,
#: schedule) like the other two carried-answer stores, so the `deaf` rider can
#: never compare an answer given about one board with an answer given about
#: another. D-11, same session: it is BOUNDED now. It kept 4 rows per session
#: and had no cap on the NUMBER of sessions, so a long-lived API process
#: accumulated one entry per browser tab forever while `AnswerMemory` and
#: `SynthesisMemory` beside it were LRU-32. Bounded is not a feature; unbounded
#: was the bug.
_DELIVERED: dict[tuple[str, str], list[dict]] = {}
_DELIVERED_KEEP = 4
_DELIVERED_SESSIONS = 32


def _answer_fingerprint(text: str) -> str:
    """A stable hash of the DELIVERED BODY, ignoring the riders this very
    mechanism adds (else the second delivery never matches the first) and
    ignoring the rendered-by footer."""
    body = (text or "").split("\n[rendered by:")[0]
    words = re.findall(r"[a-z0-9]+", body.lower())
    return hashlib.sha1(" ".join(words).encode("utf-8")).hexdigest()


def remember_delivery(session_id: Optional[str], schedule_id: Optional[str],
                      route: str, question: str, text: str) -> None:
    """Record what was delivered, so the next turn can tell whether it is about
    to say the same thing again."""
    key = _carry_key(session_id, schedule_id)
    if key is None:
        return
    row = {"route": route, "question": question,
           "fp": _answer_fingerprint(text)}
    seq = _DELIVERED.pop(key, [])
    seq.append(row)
    del seq[:-_DELIVERED_KEEP]
    _DELIVERED[key] = seq
    while len(_DELIVERED) > _DELIVERED_SESSIONS:
        _DELIVERED.pop(next(iter(_DELIVERED)))


def forget_deliveries(session_id: Optional[str]) -> None:
    """Drop a session's delivery memory — the SYMMETRIC clear for
    ``remember_delivery`` (Errand 4B.16a).

    ``deaf`` is evidence about a CONVERSATION: different questions inside one
    exchange collapsing onto one answer. When the conversation is cleared, that
    evidence expires with it. It did not, because this store is module-level and
    keyed by session id while every "start over" gesture cleared only the history
    channel — so the exam harness's ``RESET`` cleared history, selection,
    last-answered and the card, and the rider went on scolding across the
    boundary. Measured: seven consecutive turns in Item 2's sweep opened with
    "I've now given you this same answer for two different questions" naming a
    question from a conversation that had already been thrown away.

    Every gesture that means "forget what we were talking about" must call this.

    Session 4B.22: it clears the ANSWER MEMORY too, and this function is
    deliberately the ONE place that clears server-side conversation state. The
    4B.16a defect was a RESET that cleared four channels and missed a fifth;
    adding a sixth store with its own separate clear would reproduce it exactly.

    SESSION 4A TEACHING-GRAFT (d.1) — AND THE SYNTHESIS MEMORY, WHICH THIS
    FUNCTION HAS CLAIMED TO CLEAR SINCE 4B.22 AND DID NOT. Found while taking
    the R-MT1 census: the paragraph above says "the ONE place that clears
    server-side conversation state" and there were three such stores, of which
    this cleared two. A RESET therefore left the last synthesis answer's CLAIMS
    live, so a `prove it` on the first synthesis turn of the NEXT conversation
    could ground a claim from a conversation the bank had already thrown away —
    4B.16a's fifth channel exactly, at the store that was added after it.

    R-MT1 clause 1: every clear is by SESSION and takes every schedule with it.
    A conversation that straddled two boards is the defect the key fixes; it is
    still one conversation, and forgetting it must not leave half of it behind.
    """
    if session_id:
        _forget_session(_DELIVERED, session_id)
        ANSWER_MEMORY.forget(session_id)
        SYNTHESIS_MEMORY.forget(session_id)
        # R-TE1 (d.3): the FOURTH store, added here in the same breath as the
        # store itself. 4B.16a was a RESET that cleared four channels and missed
        # a fifth, and (d.1) found this function claiming to clear three while
        # clearing two — a new store whose clear is written later is the same
        # defect queued up.
        TERM_MEMORY.forget(session_id)


def _same_subject(turn: dict, order: Optional[str],
                  op_seq: Optional[Any]) -> bool:
    """Is a history turn about the SAME thing as the turn being answered?

    Session 4A.y Item 5 (the founder listening round). ``repeat`` fired on
    IDENTITY OF THE QUESTION TEXT and never looked at what the question was
    about, so a planner clicking down a row of bars and asking each one the same
    thing got told they were repeating themselves. Measured on the demo board,
    at HEAD, three turns of one sequence:

        "why cant this be moved"  [ORD-000128 op20]  -> answer
        "why cant this be moved"  [ORD-000073 op10]  -> "Same answer as a
                                                        moment ago —"
        "why cant this be moved"  [ORD-000177 op10]  -> "Same answer — nothing
                                                        in the plan has moved
                                                        since you asked —"

    Three different bars, three genuinely different answers, and two of them
    opened by telling the planner nothing had changed. Asking the same question
    of a different subject is not a repeat; it is the most ordinary thing a
    planner does with a board.

    THE GRAIN IS COMPARED ONLY WHERE THE TURN CARRIES IT. A client that predates
    the op_seq key says nothing about the grain, and treating its silence as
    "op_seq is None" would kill the genuine re-ask this rider exists for. Absent
    means unknown, and unknown does not refute.
    """
    if (turn.get("order") or None) != (order or None):
        return False
    if "op_seq" not in turn:
        return True
    a, b = turn.get("op_seq"), op_seq
    if a is None or b is None:
        return a is None and b is None
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def bundle_repeat(bundle: Any, context: Optional[dict],
                  parsed: ParsedQuestion, text: str = "",
                  session_id: Optional[str] = None,
                  subject: Optional[dict] = None,
                  schedule_id: Optional[str] = None) -> None:
    """Stamp the repeat signal on a bundle — REVERSED (Session 4B.15 Item 4).

    Two different facts were fused into one counter, and the fused counter fired
    four times measured with ZERO true positives:

      ``repeat``  the planner asked the SAME question again. Their intent, their
                  words. Terse is right here, and it never rebukes.
      ``deaf``    DIFFERENT questions produced THE SAME ANSWER. That is evidence
                  about ME. The correct inference is "I am not understanding
                  you", and the correct response is self-doubt and an offer to
                  narrow — never "nothing has changed since you asked".

    THE SIGNAL IS THE OUTPUT, NOT THE ROUTE. Two different questions reaching
    one route and getting two good answers is the route working; the defect is
    two different questions getting one answer. So ``deaf`` requires a matching
    answer FINGERPRINT, which is why deliveries are remembered.

    Session 4A.y Item 5: ``repeat`` additionally requires the same SUBJECT — see
    :func:`_same_subject`. ``deaf`` is left alone deliberately: it already keys
    on the delivered answer, and two bars' answers name their own bars, so a
    changed subject changes the fingerprint without any help from here.
    """
    if not isinstance(getattr(bundle, "key_facts", None), dict):
        return
    route = parsed.intent.value
    history = (context or {}).get("history") or []
    subj = subject or {}
    order, op_seq = subj.get("order"), subj.get("op_seq")
    same = sum(1 for t in history[-REPEAT_WINDOW:]
               if (t.get("route") or "") == route
               and _same_question(t.get("question") or "", parsed.question)
               and _same_subject(t, order, op_seq))
    if same:
        bundle.key_facts["repeat"] = same
        return
    if not text or not session_id:
        return
    # Session 4A teaching-graft (d.1), D-07 — A FOLLOW-UP INSIDE ONE ROUTE IS
    # NOT DEAFNESS.
    #
    # `deaf` says "I'm not understanding what you're asking", and it says it
    # because DIFFERENT questions produced one answer. A turn the parse marked
    # DEEPEN or LIST_EXPAND *that landed on the route which just answered* is
    # not a different question in that sense — it is the planner drilling into
    # the answer they just got, and re-delivering it is the correct response to
    # "but why" / "say more". Measured cold in (d.0) (`deaf-control.json` T2): a
    # deictic follow-up that correctly re-resolved to the same subject and
    # correctly got the same answer was told the product was not understanding
    # it.
    #
    # BOTH HALVES ARE NEEDED AND THE SWEEP IS WHY. The first version of this
    # gate read `followup_of` ALONE, and `sweep_carried_state_v1` block E2
    # showed it swallowing the one true positive this rider has ever produced:
    # the live parse marks "what does the certificate say", asked after "are
    # there any data quality problems", as `followup=deepen` — reasonably, since
    # it does follow — and the two are nonetheless DIFFERENT questions reaching
    # DIFFERENT routes and getting one body. The unit test did not see it
    # because the unit test constructed `followup_of=NONE`; a guard that
    # supplies its own arguments proves the assembler, not the path
    # (4B.21 §5a.78, at a seam that had just been built).
    #
    # So the gate is per-row and reads the ROUTE the prior delivery came from,
    # which `_DELIVERED` has always carried. Same route -> the planner deepened
    # and the answer is correctly the same. Different route -> two questions
    # collapsed onto one answer, which is exactly what this rider is for.
    #
    # Read from the PARSE, which already reports it (R-AI5(8)): the rider does
    # not decide what kind of follow-up this is, it only declines to scold one
    # the parse has already named. CORRECTION is deliberately NOT here — a
    # correction that gets the same answer back is the strongest deafness
    # signal there is, and it is one of the four firings 4B.15 Item 4 measured.
    deepening = parsed.followup_of in (FollowupKind.DEEPEN,
                                       FollowupKind.LIST_EXPAND)
    fp = _answer_fingerprint(text)
    key = _carry_key(session_id, schedule_id)
    prior = [row for row in (_DELIVERED.get(key, []) if key else [])[-REPEAT_WINDOW:]
             if row["fp"] == fp
             and not _same_question(row["question"], parsed.question)
             and not (deepening and (row.get("route") or "") == route)]
    if prior:
        bundle.key_facts["deaf"] = len(prior)
        bundle.key_facts["deaf_prior"] = prior[-1]["question"][:120]


def _template_text(bundle: Any) -> str:
    """The deterministic rendering of an assembled bundle — computed ONCE per
    dispatch and read by both the falsifiability check and the repeat signal.

    It is the template path deliberately: pure, cheap, faithful to the assembled
    facts, and computed BEFORE any LLM render, so neither decision can depend on
    prose a model happened to write. Returns "" on any failure, which both
    readers treat as "no signal"."""
    try:
        from mre.modules.renderers import TemplateRenderer
        return TemplateRenderer().render(bundle)
    except Exception:  # noqa: BLE001
        return ""


def _falsified(parsed: ParsedQuestion, text: str) -> Any:
    """Run the route-falsifiability check against the deterministic rendering.

    Fails OPEN in every direction: a missing module or an unexpected shape
    yields "no failure", because a check that can break an answer path is worse
    than the defect it guards."""
    if not text:
        return None
    try:
        from mre.modules.route_falsifiability import falsify
        return falsify(parsed.question, parsed.intent.value, text, parsed)
    except Exception:  # noqa: BLE001
        return None


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
                        memory: Any, session_id: Optional[str],
                        diverted_qualifier: str = "",
                        document: Any = None,
                        schedule_id: Optional[str] = None) -> Dispatched:
    """The SECOND TIER (R-AI5(2)): labeled open synthesis over read-only evidence,
    hardened by claim-level verification before it renders (R-AI5(3)).

    Reached from the unmatched branch, and — since Session 4A.5c — from the
    ADJACENT-MATCH GUARD, which is the only way a MATCHED intent ever arrives
    here. When no synthesizer is available the honest floor is part 1's bridge —
    never a keyword guess, and never a route."""
    from mre.modules.evidence_tools import EvidenceToolbox

    # The scope note rides on the context channel when the ADJACENT-MATCH GUARD
    # sent us here: the tier is told what the planner asked for that no route
    # covers, and that the evidence is this plan only. Without it the tier plays
    # the qualifier back — the arc-close sweep's own specimen, "one order will be
    # late next month: ORD-05 ... due 2026-01-05", where the figure grounded and
    # the FRAME did not, which claim verification cannot catch.
    if diverted_qualifier:
        context = {**(context or {}), "dropped_qualifier": diverted_qualifier}
    # Session 4B.15 Item 0 — THE CALENDAR ANCHOR. The tier had no idea what day
    # it was, so "Tuesday" bound to the first Tuesday in the data rather than
    # the one under discussion. The document carries the reference date and the
    # horizon; ``render_calendar`` turns them into two lines of context.
    if document is not None:
        context = {**(context or {}), "document": document}

    answer = synthesizer.synthesize(
        parsed.question, explainer=explainer, context=context,
        toolbox=EvidenceToolbox(explainer))
    if answer is None:
        return _unmatched_bridge(explainer, parsed, note)
    # R-TG3 — THE DEPTH LICENCE, AT THE DISPATCH SEAM (Session 4A
    # teaching-graft (b)). AFTER the model drafted and AFTER the verifier
    # labelled, so a trimmed answer is trimmed from claims that already earned
    # their status — and so nothing here can affect what a claim is, only how
    # many of them reach the page. TEACHING gets the long budget; every other
    # question that reaches this tier gets the short one.
    #
    # It runs BEFORE `explainer.route`, which reads `answer.claims`, so the
    # bundle carries exactly what will render and the citation list is scoped to
    # the claims a planner can actually see.
    from mre.modules import answer_budget
    licence = answer_budget.licence_for(parsed.intent)
    answer_budget.apply(answer, licence)
    # Micro-session 4A — THE SECOND TIER'S OWN OUTAGE. The parse succeeded, so
    # the question WAS read; what failed is the reach to the model that would
    # have reasoned over the evidence. Without this branch the answer is the
    # capability floor — "I don't have a tool that reaches it" — assembled from
    # zero tool calls that never happened, which is the founder's specimen
    # arriving by the second of its two routes.
    if getattr(answer, "model_unreachable", False):
        return Dispatched(
            "OUTAGE",
            explainer.route("outage", {"question": parsed.question,
                                       "stage": "synthesis"}),
            note, parsed.question)
    # W6 (the founder's felt-bar ruling, 2026-08-05) — IS THIS THE FIRST
    # SYNTHESIS ANSWER OF THIS CONVERSATION? Read BEFORE `remember` writes this
    # one, or the answer would always find itself and never be first. The two
    # framing lines the ruling scopes — what a general-knowledge label means,
    # and the invitation to push back — are orientation for a planner meeting
    # this register, and orientation repeated every turn stops being orientation
    # and becomes furniture. Per-line labels and the cut disclosures are NOT
    # scoped by this: those are facts about THIS answer.
    #
    # It rides on the SAME (session, schedule) key R-MT1 gave the memory, so a
    # rebind to another board correctly makes the next answer first again — the
    # planner is meeting this register on a board they have not seen it on.
    first_synthesis = (memory is None
                       or memory.last(session_id, schedule_id) is None)
    if memory is not None and not answer.unanswerable:
        memory.remember(session_id, schedule_id, answer)
    # CU3(b) — the warm floor's doors, computed HERE (the same offers part 1's
    # bridge would have made, chosen by what the planner named) and rendered only
    # if the tier could not ground an answer.
    offers, _routes = _nearest_offers(parsed, route_params(parsed, parsed.question))
    return Dispatched("synthesis",
                      explainer.route("synthesis",
                                      {"question": parsed.question,
                                       "answer": answer,
                                       "diverted_qualifier": diverted_qualifier,
                                       "offers": offers,
                                       "licence": licence.name,
                                       "first_synthesis": first_synthesis}),
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
             session_id: Optional[str] = None,
             document: Any = None, answer_memory: Any = None,
             schedule_id: Optional[str] = None) -> Dispatched:
    """A parsed question → the assembled answer.

    A matched intent goes to the CONTRACTED deterministic evidence assembly — the
    routes, pre-computed facts, authored copy and validator floor, unchanged in
    authority (R-AI5(2)). An UNMATCHED one goes to the labeled synthesis tier. There
    is no silent path between them in either direction, and nothing here guesses.
    """
    note = _subject_note(parsed)

    # -1 — THE OUTAGE FLOOR, BEFORE EVERYTHING (micro-session 4A).
    #
    # The parse layer could not reach its language model, so this question was
    # never read. There is no subject to resolve, no tray to pre-empt, no card to
    # read back and no intent to honour — every branch below reasons about a
    # parse that does not exist. It runs first so that no branch can answer as
    # though it did, and so that the ONE thing we know (our own reach failed) is
    # the one thing the planner is told.
    #
    # It is deliberately NOT the clarify branch. A clarify asks the planner
    # something; there is nothing to ask, and "which order did you mean?" would
    # imply we got far enough to have a question about their words.
    if (parsed.clarify is not None
            and parsed.clarify.reason is ClarifyReason.MODEL_UNREACHABLE):
        return Dispatched(
            "OUTAGE",
            explainer.route("outage", {"question": parsed.question,
                                       "stage": "parse"}),
            "", parsed.question)

    def _second_tier(diverted: str = "") -> Dispatched:
        if synthesizer is not None and getattr(synthesizer, "available", False):
            return _synthesis_dispatch(explainer, parsed, note, synthesizer,
                                       context, memory, session_id,
                                       diverted_qualifier=diverted,
                                       document=document,
                                       schedule_id=schedule_id)
        return _unmatched_bridge(explainer, parsed, note)

    # 0 — THE TRAY, before anything else (Session 4A.5c CU4).
    #
    # When the planner NAMES an order that sits in the beyond-horizon tray, the
    # document already answers every placement question about it the same way: it
    # has no placement yet, and here is when it is expected to get one. That answer
    # outranks the intent the parse reached for, because the window-0 snapshot
    # every placement assembler reads does not contain the order at all — so each
    # of those intents would find nothing and say something wrong in its own way.
    #
    # It runs FIRST because the rolling bank found the branches that pre-empted it.
    # "what machine is ORD-000007 on" parsed as `machine-schedule` (which needs a
    # MACHINE, not an order) with an `ambiguous-intent` clarify; the clarify branch
    # below sent it to the second tier, which read `placements_for_order` for a
    # tray order, found nothing, and honestly could not answer — a correct process
    # producing a useless answer to a question the document could answer outright.
    #
    # Three exclusions, each for a reason: the ROLLING intents already speak about
    # the sliced world; `prove-it` and `confirm-take` are gestures about OUR OWN
    # sentence, not about the order's placement; and a POINTED subject is excluded
    # by construction, since a tray order has no bar to point at.
    tray = [s for s in parsed.of_kind(SubjectKind.ORDER)
            if s.beyond_horizon and not s.pointed]
    if (tray and document is not None
            and parsed.intent not in ROLLING_INTENTS
            and parsed.intent not in (Intent.PROVE_IT, Intent.CONFIRM_TAKE)
            and parsed.followup_of not in (FollowupKind.PROVE_IT,
                                           FollowupKind.CONFIRM_TAKE)):
        params = route_params(parsed, parsed.question)
        params["order"] = tray[0].ref
        params["document"] = document
        # Session 4B.27 Item 4 — THE PRE-EMPTION IS ALSO A DROP, AND SAYS SO.
        #
        # This branch REWRITES the intent, so a two-order question ("why can't
        # ord-11 start right after ord-19", which the parse sends to
        # `gap-between` with both subjects) arrives at a one-order route about
        # the tray. The exemption list correctly leaves `gap-between` alone —
        # that route DOES use both — but the exemption is computed from the
        # parse's intent, and by here the intent is no longer the one being
        # answered. Without this the planner is told about ORD-000011 and never
        # learns ORD-000019 went unweighed, which is the whole defect.
        others = [s.ref for s in parsed.of_kind(SubjectKind.ORDER)
                  if s.resolved and s.ref != tray[0].ref]
        tray_note = note
        if others and parsed.intent in _UNUSED_SUBJECT_INTENTS_EXEMPT:
            extra = (f"answered about {tray[0].ref} only — {', '.join(others)} "
                     f"was named too, and there is no placement for "
                     f"{tray[0].ref} yet to compare it against")
            tray_note = f"{note}; {extra}" if note else extra
        return Dispatched(
            Intent.WHY_NOT_SCHEDULED_YET.value,
            explainer.route(Intent.WHY_NOT_SCHEDULED_YET.value, params),
            tray_note, parsed.question)

    # 0b — THE OPEN DELTA CARD (Session 4B.5 CU2), ahead of the clarify branch.
    #
    # A priced move is showing and the planner asked about IT. The answer is
    # already computed and on screen; what was missing was a way to read it back.
    # The founder's exchange is the specimen: "what orders are affected in this
    # move", asked with the affected set visible on the card, parsed as
    # `swap-move` — a route about two orders' slack that has never heard of the
    # card — and answered a question nobody asked.
    #
    # It runs ahead of the clarify branch for the same reason the tray check does:
    # a clarify decides before anything below it, and asking "which orders do you
    # mean" about the card in front of them is the dead end `_clarify_leads_
    # nowhere` exists to prevent — but the card is not a resolved SUBJECT, so that
    # test cannot see it.
    #
    # The dispatch DECIDES; the parse only reported (R-AI5(8)). An `open-card`
    # parse with no card in context is not answered as one — it falls through to
    # the honest floor below, which says there is nothing open to read back rather
    # than inventing which move they meant.
    card = (context or {}).get("card") or {}
    if parsed.intent is Intent.OPEN_CARD:
        if card.get("open"):
            params = route_params(parsed, parsed.question)
            params["card"] = card
            return Dispatched("open-card", explainer.route("open-card", params),
                              note, parsed.question)
        return Dispatched("open-card",
                          explainer.route("open-card", {"question": parsed.question,
                                                        "card": {}}),
                          note, parsed.question)

    # 1 — the parse could not commit. Ask; never guess — UNLESS asking leads
    # nowhere (see _clarify_leads_nowhere), in which case the honest destination is
    # the second tier, which can actually read the thing the planner named.
    if parsed.clarify is not None:
        if _clarify_leads_nowhere(explainer, parsed,
                                  route_params(parsed, parsed.question)):
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
        last = (memory.last(session_id, schedule_id)
                if memory is not None else None)
        claim = pick_claim(last, parsed.question) if last is not None else None
        # With NOTHING of ours open to ground, a prove-it that also names a real
        # intent is answered AS that intent — the grounding pass has nothing to do,
        # and the question is still a question. Falling through here is what stops
        # the fourth sweep's specimen from dead-ending: "but why" (a DEEPEN on
        # ORD-05, selected, one turn after its cause chain) read as prove-it and
        # answered "I don't have a claim of my own open to ground", which is the
        # exact class 4A.5a existed to kill. When the parse named prove-it and
        # nothing else, the no-target copy IS the honest answer and still stands.
        #
        # Session 4B.22 — AND THE PRIOR ANSWER IS THE THIRD THING TO REACH FOR.
        # With no synthesis claim open, a drill-down that named no other intent
        # used to dead-end on "I don't have a claim of my own open to ground"
        # even when the immediately previous turn cited records and lit bars.
        # The prior answer is looked up ONLY on that branch — the fall-through
        # above (a prove-it gesture that ALSO named a real intent, e.g. "but
        # why" after a cause chain) is untouched, because what the planner wants
        # there is the question answered, not our last sentence re-opened.
        #
        # R-MT1 clause 3 (Session 4A teaching-graft (d.1)): with nothing carried
        # for THIS board, ask whether this session carries one for another. A
        # rebind clears the client channels (clause 2) so this should be
        # unreachable in the shipped cockpit — it is defense in depth for the
        # window where a server has clause 1 and a browser has not yet reloaded,
        # and for any future rebind path that forgets to clear.
        prior = (answer_memory.last(session_id, schedule_id)
                 if answer_memory is not None else None)
        elsewhere = bool(
            prior is None and claim is None and answer_memory is not None
            and answer_memory.held_elsewhere(session_id, schedule_id))
        if claim is not None or parsed.intent in (Intent.PROVE_IT, Intent.UNMATCHED):
            return Dispatched(
                "prove-it",
                explainer.route("prove-it", {"question": parsed.question,
                                             "claim": claim, "answer": last,
                                             "prior": None if claim is not None
                                             else prior,
                                             "prior_elsewhere": elsewhere}),
                note, parsed.question)

    # 3 — the planner confirmed OUR OWN take back at us. Name the gesture and the
    # sandbox: the bridge answer, not a near-miss (Session 4A.5a CU2).
    if parsed.followup_of is FollowupKind.CONFIRM_TAKE or \
            parsed.intent is Intent.CONFIRM_TAKE:
        params = route_params(parsed, parsed.question)
        return Dispatched("confirm-take", explainer.route("confirm-take", params),
                          note, parsed.question)

    # 3b — R-TE1 (Session 4A teaching-graft (d.3)): THE PRODUCT EXPLAINS ITS OWN
    # WORDS, and the DETERMINISTIC SEAM DECIDES WHETHER IT DOES.
    #
    # The parse PROPOSES the intent and the term; this disposes (R-AI5(8)). The
    # intent is confirmed only when the word is one of ours AND this planner has
    # actually been shown it, on THIS board — which is a property of the rendered
    # transcript, not of anything a model remembers, and it is the whole scope
    # wall. Without it this route is a documentation browser that will answer
    # "what is a bottleneck" as though we had defined the term.
    #
    # AN UNCONFIRMED PROPOSAL IS NOT A MATCHED INTENT, so sending it onward is
    # not a fall and the R-AI5(2) seal is untouched. The dispatch decided this is
    # not term-explanation; what is left is a question we did not match, and
    # unmatched has exactly one door. That is also where the (d.3) census found
    # most of these questions already going — 15 of 25 phrasings reached the
    # second tier before this route existed — so the unconfirmed path is the
    # measured status quo rather than a new behaviour.
    if parsed.intent is Intent.TERM_EXPLANATION:
        from mre.modules.glossary import known_term
        raw = next((s.raw for s in parsed.subjects
                    if s.kind is SubjectKind.CONCEPT and s.raw), "")
        # The concept subject first — the model marks the word it read as the
        # question's object. The QUESTION is the fallback, never the reverse: a
        # question mentioning two of our words means the model's pick wins.
        entry = known_term(raw) or known_term(parsed.question)
        seen = TERM_MEMORY.seen(session_id, schedule_id)
        if entry is not None and entry.term in seen:
            params = route_params(parsed, parsed.question)
            params["term"] = entry.term
            params["term_seen"] = sorted(seen)
            params["document"] = document
            return Dispatched(
                "term-explanation",
                explainer.route("term-explanation", params),
                note, parsed.question)
        return _second_tier()

    # 4 — no contracted intent fits (or the parse is not confident enough to answer
    # AS one). R-AI5(2): this is where LABELED OPEN SYNTHESIS lives, and it is the
    # ONLY door into it. Part 1's honest bridge stays as the floor beneath it.
    #
    # Session 4A teaching-graft (b), R-TG2: `teaching` comes through the SAME
    # door, by name. It is a DECLARED second-tier intent (`SECOND_TIER_INTENTS`)
    # rather than a route, because teaching is synthesis with a second claim
    # class and a depth licence and not a new rung — and because there is no
    # contracted evidence assembly for "how does this normally work". What it
    # changes is the BUDGET, which `_synthesis_dispatch` reads off the intent.
    #
    # The seal is untouched: no CONTRACTED route falls here (this intent never
    # was one), and the tier still never guesses a route.
    if (parsed.intent in SECOND_TIER_INTENTS
            or parsed.confidence < CONF_MATCH):
        return _second_tier()

    # 4b — THE ADJACENT-MATCH GUARD (Session 4A.5c CU3(c)). The last hiding place.
    #
    # Rule 7 of the parse prompt already forbids stretching a question into a
    # NEARBY route. This is the same failure one step further in, where the route
    # genuinely IS the nearest one and still cannot honour something the planner
    # said. Both of 4A.5b's surviving unmet expectations were this shape:
    #
    #   "how many orders will be late NEXT MONTH"  -> late-orders, which answers
    #                                                 about THIS plan
    #   "how much of CUT-01s week is ACTUALLY working time"
    #                                              -> downtime, which answers the
    #                                                 complement of what was asked
    #
    # Neither is a mis-parse. Both answer a question nobody asked, with perfect
    # citations — which is worse than not answering, because the citations make it
    # look right. The parse REPORTS the dropped qualifier (it never decides); the
    # dispatch diverts to the tier that can either answer the qualified question or
    # say honestly that it cannot, and the rendered-by line names the qualifier so
    # the planner knows it was heard.
    #
    # Deliberately conservative in three ways: the parse must have NAMED the
    # dropped words (an empty field never diverts); a low-confidence match already
    # went to the tier above; and a qualifier the route DOES honour must not be
    # reported at all, which is what the prompt's negative examples are for.
    if parsed.dropped_qualifier:
        return _second_tier(diverted=parsed.dropped_qualifier)

    # 4c — THE ROLLING (SLICED-WORLD) INTENTS (Session 4A.5c CU4). These three were
    # in the closed vocabulary all along; what they lacked was a way to be REACHED,
    # because a keyword pre-route upstream in the API answered them before the
    # parse ever ran. That matcher is deleted. The answers still come from the
    # document's RollingBlock — the Explainer's snapshot is window 0 — so the
    # document rides in as a route param.
    if parsed.intent in ROLLING_INTENTS:
        params = route_params(parsed, parsed.question)
        params["document"] = document
        # Session 4A.y Item 1 — THIS RETURN IS BEFORE THE FLOOR AND BEFORE THE
        # DISCLOSURE SEAM, and `frozen` is a mobility-family member that takes
        # it. Measured at HEAD: five of eighteen census phrasings routed here
        # and got neither a premise check nor a word about what was assumed —
        # including the grain, which the listening docket had just built.
        # 4B.21 §5a.78's mechanism a third time: a seam every route passes,
        # except the ones that return early.
        _apply_mobility_floor(parsed, params, (context or {}).get("selection"))
        # R-TG4 at the ROLLING early return too — 4A.y Item 1's lesson, which
        # this branch is the standing specimen of. A floor written once at the
        # obvious seam covers every route except the ones that return before it.
        _apply_audience_floor(parsed, params)
        note = _with_assumptions(note, parsed, params)
        bundle = explainer.route(parsed.intent.value, params)
        _attach_mobility_lead(explainer, bundle, params)
        _attach_audience_shape(bundle, params)
        return Dispatched(parsed.intent.value, bundle, note, parsed.question)

    # 5 — a matched intent. The question the assemblers see is the planner's own
    # text unless the parse rewrote the subject (context bind / near-miss id /
    # re-fired question), in which case it is the canonical question — re-parsed by
    # the same assemblers, so identity resolution stays inside (Phase-1 lesson).
    params = route_params(parsed, parsed.question)
    routed_question, rewritten = routed_text(parsed, params)
    params["question"] = routed_question
    # Session 4B.13 — THE PLANNER'S OWN WORDS, carried alongside the routed
    # question. Assemblers legitimately overwrite `bundle.question` with their
    # canonical phrasing, so by the time an answer reaches the delivery seam the
    # words the planner actually typed are gone. The predicate-coverage floor
    # needs them: "why does ORD-000011 go through downtime" is answered by
    # start-time causation, and the only place "downtime" still appears is the
    # original utterance. Never used for routing — routing already happened.
    params["asked_question"] = parsed.question
    # Session 4A teaching-graft (d.1), D-01 — THE CARRIED ANSWER REACHES THE
    # DRILL-DOWN, from the SAME store `prove-it` grounds on. Wired here rather
    # than inside `route_params` because the store is the dispatch's to read (it
    # holds `session_id` and, since R-MT1, `schedule_id`), and because the two
    # gestures must never be able to ground on two different objects.
    #
    # `prior_elsewhere` is R-MT1 clause 3's input on this branch too: a
    # drill-down after a rebind says the board changed rather than falling to
    # the never-answered floor.
    if parsed.intent is Intent.DRILL_DOWN:
        # THE SYNTHESIS CLAIM FIRST, exactly as the prove-it branch reaches for
        # it — same store, same order, same `pick_claim`. Found in this
        # session's own live run: with only the ANSWER memory wired, a
        # drill-down onto a SYNTHESIS answer fell to the record set (empty,
        # because a general-knowledge claim carries none by R-TG1) and told the
        # planner their teaching answer had cited nothing. A gesture that is
        # "two phrasings of one thing" has to reach for the same things in the
        # same order, or the phrasing still decides the answer.
        last_synth = memory.last(session_id, schedule_id) \
            if memory is not None else None
        params["claim"] = (pick_claim(last_synth, parsed.question)
                           if last_synth is not None else None)
        if answer_memory is not None:
            params["prior"] = (None if params["claim"] is not None
                               else answer_memory.last(session_id, schedule_id))
            params["prior_elsewhere"] = (
                params["claim"] is None and params["prior"] is None
                and answer_memory.held_elsewhere(session_id, schedule_id))
    # And the DOCUMENT for the routes whose honesty depends on the sliced world.
    # `late-orders` is one: "no late orders" is true of the SCHEDULED orders, and
    # on a rolling board the tray has to be named beside it or a stranger reads
    # it as a clean bill of health for the whole book. Rolling intents get this
    # at their own branch above; this is the non-rolling route that needs it too.
    # Session 4B.21: INVENTORY and LATENESS_CAUSE join it, and for the same
    # reason one step further in. Both report counts of orders, and the
    # BEYOND-HORIZON region exists only in the document — without it `inventory`
    # can see 40 known and 26 placed and has no way to learn that the other 14
    # are admitted work waiting for a later window. This was found on the LIVE
    # ask path while the cross-surface guard, which passes a document
    # explicitly, stayed green: the allow-list is exactly the kind of seam that
    # is proven from one side only.
    if parsed.intent in (Intent.LATE_ORDERS, Intent.INVENTORY,
                         Intent.LATENESS_CAUSE, Intent.EXCLUDED_ORDERS):
        params["document"] = document
    # Session 4B.14 Item 2: the blocker analysis reads the FROZEN BOUNDARY (R-F1)
    # from the rolling block, so its ladder is missing a family without the
    # document. `contested-fact` takes it for the same reason: a `timing` contest
    # is answered BY the blocker analysis.
    # Session 4B.16: the counterfactual reads the same ladder, so it needs the
    # same frozen boundary. And the OPENER (Item 2) is a whole-board read whose
    # proof status, tray, closures and derate provenance live in the document —
    # without it the route degrades to the pre-4B.16 briefing and says so.
    # Session 4B.22 Item B2: ADVICE joins them, and for the opener's reason.
    # "if I could fix one thing what should it be" lands here, and the answer to
    # the half of it this product CAN answer is the opener's top-ranked item —
    # which lives in the document. Without it the route degrades to the bare
    # intervention refusal it gave before, which is honest but is not the answer.
    # Session 4B.27 Items 8 and 10: SOLVE_TIME and SOLVE_OPTIMALITY join them.
    # Both answer questions about OUR SEARCH, and since 4B.25 the search may be
    # a declared PORTFOLIO whose member ledgers, spread and wall live only in
    # the document's `solver.portfolio`. Without it "is this the best schedule
    # you found" can speak about the gap and cannot speak about the other seeds
    # — and with K=3 the default since 4B.29, that is every new board.
    if parsed.intent in (Intent.WHY_HERE, Intent.CONTESTED_FACT,
                         Intent.WHAT_WOULD_CHANGE, Intent.BRIEFING,
                         Intent.ADVICE, Intent.SOLVE_TIME,
                         Intent.SOLVE_OPTIMALITY):
        params["document"] = document
    # And the SELECTED OPERATION (Item 5(d)). The board selection carries the
    # operation the planner is pointing at; without it an order-level question
    # resolves to the order's FIRST operation, which is how a question asked with
    # ORD-000013 selected on PAINT-01 was answered about CUT-01, with no bridging
    # sentence. Narrow on purpose: only the three routes that speak about ONE
    # operation read it, so a selection can never silently re-scope a plant-wide
    # answer. It runs BEFORE the subject-resolution guard below and still cannot
    # satisfy a required slot, because all three of these routes require an
    # ORDER and none of them requires a machine — a selection can sharpen which
    # operation is answered about, never conjure the subject itself.
    # Session 4B.15 Item 3 — THE PREVIOUS TURN'S WORDS, for the one route that
    # needs a PREDICATE carried forward. "no, I mean for ORD-000013
    # specifically" re-binds the subject and inherits the field from the turn
    # before it; without this the correction names no field and is answered as
    # though nothing was asked — which is how an explicit correction got the
    # same wrong answer twice in the measured transcript. Read only when this
    # question names no field of its own.
    if parsed.intent is Intent.ATTRIBUTE_LOOKUP:
        history = (context or {}).get("history") or []
        if history:
            params["prior_question"] = history[-1].get("question") or ""

    if parsed.intent in _OPERATION_SCOPED_INTENTS:
        sel = (context or {}).get("selection") or {}
        if params.get("op_seq") is None and sel.get("op_seq") is not None:
            try:
                params["op_seq"] = int(sel["op_seq"])
                params["op_seq_source"] = "selection"
            except (TypeError, ValueError):
                pass
        if not params.get("machine") and sel.get("machine"):
            params["machine"] = sel["machine"]

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
                            {**params, "mention": unresolved[0].raw,
                             # Session 4B.13 — WHICH KIND was not found. Without
                             # it this route answers every miss as an order and
                             # offers orders back: a mistyped MACHINE name got
                             # "MILL-99 isn't in this schedule — I don't see it
                             # among the planned orders", which mislabels the
                             # thing the planner named. The kind comes from the
                             # parse; nothing here infers it from the string.
                             "mention_kind": kind.value}),
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

    # 5a — CU5(a), Session 4B.5: AN ADVICE TURN THAT NAMES A CAPABILITY IS A
    # COACHING QUESTION.
    #
    # The founder's rider: "so you can't tell me if overtime will help", asked
    # after the advice route's scoping answer. It parsed as `advice` again and
    # re-fired the same template verbatim — the assistant reading its own last
    # answer back to someone who had just told it that answer was insufficient.
    # But the sentence names a CONCEPT the submission can declare, and there IS a
    # contracted answer for that: how to turn overtime on, and what it would let
    # the solver do. The concept is the parse's, not a keyword's; the dispatch
    # only reads whether one resolved.
    # 4y — THE MOBILITY FLOOR (the listening docket, Item 3). Prompt v17 asks
    # the model to report `move_direction` on `why-here`; measured immediately
    # after the bump it did so 0 times in 5 on the phrasings planners use. The
    # parse's report is left exactly as the model made it — it is the record of
    # what was said — and the DISPATCH decides, which is R-AI5(8) rather than a
    # departure from it. It can only ever ADD a premise check to a route that
    # was already going to run; it can never route.
    #
    # SESSION 4A.y ITEM 1 — THE FLOOR IS SCOPED TO THE FAMILY, NOT TO A ROUTE.
    # See `_MOBILITY_FAMILY_INTENTS` for the census that decided the set. The
    # direction default is still `why-here`'s alone, because it is the only one
    # of the three whose answer IS a direction (see `_EARLIER_BY_DEFAULT`); the
    # other two get the premise check and no claim about which way they read.
    _apply_mobility_floor(parsed, params, (context or {}).get("selection"))
    # 4y-bis — R-TG4's FLOOR (Session 4A teaching-graft (b)). Does this question
    # name a person who has to be told? Same shape as the mobility floor above,
    # same discipline: it may only reshape a route that was already going to
    # answer, and it decides no route.
    _apply_audience_floor(parsed, params)

    # 4z — EVERY RESOLUTION THE LADDER MADE IS DISCLOSED, NOT ONLY THE SUBJECT
    # (the listening docket, Item 2). Computed HERE, at the one seam every
    # answered route passes, for 4B.27 Item 4's reason: an assembler that has to
    # remember to disclose is an assembler that will forget.
    note = _with_assumptions(note, parsed, params)

    if parsed.intent is Intent.ADVICE and params.get("concept"):
        coaching = explainer.route("coaching", params)
        _attach_audience_shape(coaching, params)
        return Dispatched("coaching", coaching, note, routed_question)

    bundle = explainer.route(parsed.intent.value, params)

    # 4z-bis — THE FLOOR RUNS FOR WHICHEVER ROUTE ANSWERED (Session 4A.y Item 1).
    # `why-here` computes its own verdict inline (it renders both directions in
    # its own shape); the other members get it here and render it as a lead.
    _attach_mobility_lead(explainer, bundle, params)
    # R-TG4 — and so does the audience shape, composed from what THIS route
    # assembled. The census measured the goal family reaching three different
    # routes, so it attaches to whichever one answered rather than to the one
    # the founder's question happened to hit.
    _attach_audience_shape(bundle, params)

    # 5a-bis — ROUTE FALSIFIABILITY (Session 4B.15 Item 2). A matched route
    # could not be wrong: once the parse named an intent above the confidence
    # floor, that route's canned copy shipped whatever it said, and five
    # consecutive measured turns were swallowed by `coaching` that way.
    #
    # The check runs on the TEMPLATE rendering — pure, cheap, faithful to the
    # assembled facts, and computed BEFORE any LLM render, so a fall-through
    # costs nothing it would not have cost anyway. It can only REJECT the route
    # the parse chose; it can never name one, and rejection has exactly one
    # destination, which is the tier that reasons from evidence and labels what
    # it grounds.
    draft = _template_text(bundle)
    failure = _falsified(parsed, draft)
    if failure is not None and synthesizer is not None \
            and getattr(synthesizer, "available", False):
        return _synthesis_dispatch(explainer, parsed, note, synthesizer,
                                   context, memory, session_id,
                                   diverted_qualifier=failure.note,
                                   document=document,
                                   schedule_id=schedule_id)

    # 5b — CU5(b)/(c) as REVERSED by Session 4B.15 Item 4.
    #
    # THE MEASURED FAILURE: the old signal counted how many of the last two
    # turns THIS ROUTE answered, and read that as "the planner is repeating
    # themselves". It fired four times measured — on a DIFFERENT question, on an
    # EXPLICIT CORRECTION, on a factual lookup and on the demo opener — with
    # ZERO true positives, and it escalated: "Still the same; nothing has
    # changed since you asked" is the product blaming the planner for its own
    # deafness.
    #
    # THE INFERENCE WAS BACKWARDS. Several DIFFERENT questions collapsing onto
    # one route is evidence that I AM NOT UNDERSTANDING YOU, not that you are
    # repeating yourself. So the signal is now split by whether the QUESTIONS
    # differ, and only a genuine re-ask keeps the old terse behaviour.
    #
    # Session 4A.y Item 5: and the SUBJECT, read from the params the route was
    # actually answered with rather than from the parse — the ladder may have
    # resolved it off the board, and a rider about repetition must compare what
    # was answered about, not what was typed.
    bundle_repeat(bundle, context, parsed, draft, session_id,
                  subject={"order": params.get("order"),
                           "op_seq": params.get("op_seq")},
                  schedule_id=schedule_id)
    remember_delivery(session_id, schedule_id, parsed.intent.value,
                      parsed.question, draft)
    # Make the resolution visible (RUBRIC C3): the answer shows the question it
    # actually answered, whenever the parse rewrote it.
    if rewritten:
        bundle.question = routed_question
    return Dispatched(parsed.intent.value, bundle, note, routed_question)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def parse_provenance(parsed: Optional[ParsedQuestion]) -> Any:
    """The parse contract → the ledger's ``ParseProvenance`` (R-AI5(5)).

    Ids and counts only, and deliberately NOT the resolved refs: a cluster is a
    SHAPE, and which order the planner named is not part of the shape. Keeping the
    refs out is also what lets the report be read by anyone — a ledger row says
    "an order-shaped question that consulted lateness_set and cost_ledger", never
    "ORD-05"."""
    if parsed is None:
        return None
    from mre.contracts.question_ledger import ParseProvenance
    return ParseProvenance(
        intent=parsed.intent.value,
        nearest=[i.value for i in parsed.nearest],
        subject_kinds=sorted({s.kind.value for s in parsed.subjects}),
        polarity=parsed.polarity.value if parsed.polarity else None,
        followup_of=parsed.followup_of.value,
        confidence=parsed.confidence,
        prompt_version=parsed.prompt_version,
        dropped_qualifier=parsed.dropped_qualifier,
    )

def run_ask(explainer: Any, question: str, *, context: Optional[dict] = None,
            parser: Optional[QuestionParser] = None,
            ledger: Any = None, schedule_id: Optional[str] = None,
            session_id: Optional[str] = None,
            synthesizer: Any = None, memory: Any = None,
            shadow: Any = None, document: Any = None,
            parse_memory: Any = None, answer_memory: Any = None) -> AskResult:
    """parse → dispatch → assemble, then log one question-ledger entry.

    The single entry point the API ask path calls. With no parser the answer is the
    honest unsupported one — R-AI5(2) leaves no deterministic fallback to reach for.
    With no synthesizer the second tier is simply unavailable and an unmatched
    question gets part 1's honest bridge.

    ``shadow`` (Session 4A.5c, R-AI5(7)) is an optional callable run AFTER a
    promoted route on probation answers: it answers the same question again
    through the synthesis tier and diffs the two. It is a PARAMETER rather than a
    default because a shadow costs a full synthesis, and making every planner pay
    ten seconds so a promotion can be audited would be charging the user for our
    own quality control. The exam sweep supplies it; the live ask path does not.
    """
    # Session 4A.5c CU4 — the sliced world's order vocabulary, so subject
    # resolution sees the beyond-horizon tray and the committed front, not just
    # window 0. On a monolithic document this is falsy and costs nothing.
    rolling = None
    if document is not None:
        from mre.modules.rolling_questions import RollingVocabulary
        rolling = RollingVocabulary(document) or None

    # A parse the PREFLIGHT already made for exactly this question and context is
    # reused (CU3a) — one parse per question whether or not the panel two-phased.
    parsed = None
    cache_key = None
    if parse_memory is not None:
        cache_key = ParseMemory.key(question, context, session_id, schedule_id)
        parsed = parse_memory.take(cache_key)
    if parsed is None and parser is not None:
        parsed = parser.parse(question, explainer=explainer, context=context,
                              rolling=rolling)
    if memory is None:
        memory = SYNTHESIS_MEMORY
    if answer_memory is None:
        answer_memory = ANSWER_MEMORY

    synthesis = None
    if parsed is None and parser is not None:
        # Micro-session 4A — A PARSER THAT EXISTS AND CANNOT REACH A MODEL IS AN
        # OUTAGE, NOT A CAPABILITY LIMIT. `parse` returns None only when the
        # layer is UNAVAILABLE: no key, no `anthropic` package, a client that
        # would not build. Nothing read the question, so the honest card is the
        # same one a failed call gets, with the mechanism named as a setup gap
        # rather than a network one — "try again in a moment" would be false.
        #
        # The `parser is None` case below is untouched and stays the pre-existing
        # bridge: a CALLER that passed no parser at all made a deliberate choice
        # (the API's degraded re-run, and every test that asserts R-AI5(2)'s "no
        # keyword fallback"), and nothing here can tell whether an AI layer was
        # ever meant to be there.
        bundle = explainer.route("outage", {"question": question,
                                            "stage": "unconfigured"})
        route_label, source, confidence, note = "OUTAGE", "none", None, ""
        resolved_question = question
    elif parsed is None:
        bundle = explainer.route("unsupported", {"question": question})
        route_label, source, confidence, note = "REFUSED", "none", None, ""
        resolved_question = question
    else:
        d = dispatch(explainer, parsed, ledger=ledger, synthesizer=synthesizer,
                     context=context, memory=memory, session_id=session_id,
                     document=document, answer_memory=answer_memory,
                     schedule_id=schedule_id)
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
        # Session 4A teaching-graft (d.1): `drill-down` joins the exemption for
        # the same reason `prove-it` has it. A turn that OPENS our last answer
        # is not a later answer that makes it stale — and now that D-01 has
        # wired the drill-down to the same two stores, forgetting here would
        # mean the first "show me that" opened the claims and the second could
        # not.
        if memory is not None and d.route not in ("synthesis", "prove-it",
                                                  "drill-down"):
            memory.forget(session_id)

    register = register_of(bundle)

    # Session 4B.22 — REMEMBER WHAT WE JUST SAID, at the ONE seam every live
    # answer passes through. Not in `dispatch`: `remember_delivery` lives on the
    # matched-route branch only, so a rolling route, a tray answer or a CLARIFY
    # never reaches it — and a CLARIFY is precisely the specimen that made the
    # old copy lie ("the records behind it are cited on it", said about an
    # answer that cites nothing). An UNREADABLE parse is remembered too: the
    # honest floor is still an answer, and it still has no records.
    #
    # R-OF1 RIDER (Session 4A teaching-graft a): AN OUTAGE CARD IS NOT AN ANSWER,
    # SO IT NEVER BECOMES ONE TO GROUND. The `system` register exists because
    # nothing was read, nothing was reasoned and nothing is advised — and a
    # drill-down onto it would open "the records behind" a card whose whole
    # content is that no record was reached. Worse, it would ERASE the last real
    # answer, which is the one the planner is still looking at and the only one
    # a "show me the evidence" could mean. Keyed on the REGISTER, not on a route
    # name: `system` is the vocabulary member that means this, so a future card
    # that earns it inherits the rule instead of having to remember it.
    if (answer_memory is not None and route_label not in _NOT_REMEMBERED
            and register != "system"):
        answer_memory.remember(session_id, schedule_id, route_label, question,
                               getattr(bundle, "ordered_records", None),
                               register=register)

    # R-AI5(7) — the probation shadow. Runs only when a caller asked for it AND
    # the route that answered is a promotion still on probation (the callable
    # itself returns None otherwise), so it is bounded twice over.
    shadow_diff = None
    if shadow is not None and parsed is not None:
        try:
            shadow_diff = shadow(explainer, question, bundle, route_label)
        except Exception:  # noqa: BLE001 — auditing must never break the answer
            shadow_diff = None

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
            # R-AI5(5), Session 4A.5c: what the PARSE named rides too. Without it
            # the ledger's synthesis entries are 32 rows all reading `synthesis`,
            # and no clustering can tell an aggregate-cause question from a
            # cross-entity comparison.
            parse=parse_provenance(parsed),
            shadow=shadow_diff,
        )

    return AskResult(bundle=bundle, resolved_question=resolved_question,
                     route=route_label, source=source, confidence=confidence,
                     register=register, resolution_note=note, parsed=parsed,
                     synthesis=synthesis, shadow=shadow_diff)
