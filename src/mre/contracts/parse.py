"""L1 — The question-parse contract (R-AI5(1), Session 4A.5a).

The closed contract the LLM-first parse layer emits. Per R-AI5(1) the parse names
an INTENT and its SUBJECTS; it never authors an answer, and nothing it returns is
trusted beyond this contract.

Two closed vocabularies live here (add, never repurpose — a change is reviewed like
any other vocabulary change, with the spec update in the same commit):

  ``Intent``           — the intent vocabulary. It IS the explainer's route
                         taxonomy (``ROUTE_TAXONOMY``), which survives R-AI5 as the
                         closed set a matched parse dispatches into, plus two
                         members the taxonomy does not carry:
                           ``unmatched``    — no contracted intent fits. Part 1
                                              answers honestly (shape recognized,
                                              nearest capabilities offered);
                                              R-AI5(2)'s labeled open synthesis is
                                              Session 4A.5b.
                           ``confirm-take`` — the planner confirms the assistant's
                                              prior take back at it ("so move the
                                              first operation to an earlier start
                                              time?"). An authored acknowledgment
                                              that names the gesture and the
                                              sandbox, never a near-miss.
  ``INTENT_MEANINGS``  — the one-line meaning of every model-selectable intent.
                         This is what the governed parse prompt renders; a new
                         route without a meaning fails the parity test.

A parity test (``tests/test_parse_contract.py``) asserts ``Intent`` and the
explainer's ``ROUTE_TAXONOMY`` name the same set, so the vocabulary can never drift
from the routes it dispatches into.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, Enum):
    """The closed intent vocabulary (R-AI5(1)). Values are the route ids."""

    # -- the entity / evidence routes ---------------------------------------
    LATE_ORDER = "late-order"
    LATE_ORDERS = "late-orders"
    WHY_ON_MACHINE = "why-on-machine"
    MACHINE_SCHEDULE = "machine-schedule"
    ORDER_SCHEDULE = "order-schedule"
    SCHEDULE = "schedule"
    CUSTOMER_SCHEDULE = "customer-schedule"
    DOWNTIME = "downtime"
    ORDER_ATTRIBUTES = "order-attributes"
    INVENTORY = "inventory"
    INTEGRITY_CHECK = "integrity-check"
    START_REASON = "start-reason"
    CONTESTED_FACT = "contested-fact"
    SWAP_MOVE = "swap-move"
    GAP_BETWEEN = "gap-between"
    MACHINE_IDLE = "machine-idle"
    # -- the certificate / submission routes --------------------------------
    DATA_PROBLEMS = "data-problems"
    REMEDIATION = "remediation"
    TRIAGE = "triage"
    CERTIFICATE_TESTIMONY = "certificate-testimony"
    EXCLUDED_ORDERS = "excluded-orders"
    # -- the meta / document routes -----------------------------------------
    # Session 4A.5c (R-AI5(7)) — THE ONE PROMOTED SHAPE. `lateness-cause` did not
    # come from a designer: it is the `aggregate-lateness` cluster of the 4A.5b
    # sweep's synthesis residue, the most frequent uncontracted shape in the
    # ledger, promoted through the pipeline R-AI5(7) specifies — dossier
    # (docs/promotions/aggregate-lateness-2026-07-26.md), working-thread review,
    # then this line. It answers "why are so many orders late" / "what is driving
    # the lateness": the CAUSE mix across the late set, not the list (that is
    # `late-orders`) and not one order's chain (that is `late-order`). It is on
    # PROBATION (contracts.promotion.PROMOTIONS) and demotable by a flag flip.
    LATENESS_CAUSE = "lateness-cause"
    VERSION_DIFF = "version-diff"
    EDIT_SUMMARY = "edit-summary"
    EDIT_COST = "edit-cost"
    LEDGER_REFUSALS = "ledger-refusals"
    DRILL_DOWN = "drill-down"
    BRIEFING = "briefing"
    ADVICE = "advice"
    COACHING = "coaching"
    SOLVE_TIME = "solve-time"
    MACHINE_COUNT = "machine-count"
    MAINTENANCE = "maintenance"
    # -- the rolling (sliced-world) routes ----------------------------------
    BEYOND_HORIZON = "beyond-horizon"
    WHY_NOT_SCHEDULED_YET = "why-not-scheduled-yet"
    FROZEN = "frozen"
    # -- dispatch outcomes, not planner intents (never offered to the model) --
    UNKNOWN_ENTITY = "unknown-entity"
    # -- R-AI5 additions -----------------------------------------------------
    CONFIRM_TAKE = "confirm-take"
    # Session 4A.5b: `prove-it` is BOTH a follow-up kind and an intent, exactly as
    # `confirm-take` is. The 4A.5b sweep showed why the pair is needed: asked "how
    # do you know that", the model correctly recognized the gesture and emitted
    # `"intent": "prove-it"` — an id the vocabulary did not carry — so the whole
    # parse was discarded as malformed, twice, and the planner got "I couldn't make
    # out what that one was asking" for the one question the system is best at
    # answering. A gesture the model can name must be nameable.
    PROVE_IT = "prove-it"
    UNMATCHED = "unmatched"


class SubjectKind(str, Enum):
    """The TYPE of a parsed subject. A subject parameterizes an intent; it never
    picks one (the founder's round-four terminal bug was a bound subject
    short-circuiting intent classification entirely)."""

    ORDER = "order"
    MACHINE = "machine"
    CUSTOMER = "customer"
    CONCEPT = "concept"          # a capability/config concept (coaching)


class SubjectSource(str, Enum):
    """Where a subject's referent came from. The answer surface says which context
    won (RUBRIC C3) — a live board selection outranks the last answered subject,
    which outranks conversation history."""

    UTTERANCE = "utterance"
    SELECTION = "selection"
    LAST_ANSWER = "last-answer"
    HISTORY = "history"


class Polarity(str, Enum):
    """The direction the question asks about, where the intent carries one.

    POSITIVE — explain the property as it stands ("why is ORD-05 late", "why does
               ORD-13 start so early").
    NEGATIVE — explain the inverse / the absence ("why is ORD-13 NOT late", "why
               can't ORD-05 start sooner", "why is nothing running on CUT-01").
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"


class FollowupKind(str, Enum):
    """How this question links to the one before it (R-AI5(1) follow-up linkage).

    NONE        — self-contained.
    DEEPEN      — asks for more of the prior answer's subject ("but why?").
    CORRECTION  — re-binds a referent and re-asks the prior question ("no, I meant
                  ORD-05").
    LIST_EXPAND — asks the prior answer to enumerate ("list them", "the numbers").
    MENU_SELECT — names an item from a menu the prior answer listed ("what about
                  wip").
    CONFIRM_TAKE— repeats the assistant's own prior take back as a question ("so
                  move the first operation to an earlier start time?").
    PROVE_IT    — contests or probes a claim the assistant JUST made and asks for
                  its grounds ("prove it", "how do you know that?", "says who?",
                  "which record says that?"). Session 4A.5b (R-AI5(4)): "prove it"
                  is always available and re-runs the grounding pass on that claim
                  conversationally.
    """

    NONE = "none"
    DEEPEN = "deepen"
    CORRECTION = "correction"
    LIST_EXPAND = "list-expand"
    MENU_SELECT = "menu-select"
    CONFIRM_TAKE = "confirm-take"
    PROVE_IT = "prove-it"


class ClarifyReason(str, Enum):
    """Why the parse could not commit. A closed set: the planner-facing wording is
    AUTHORED copy keyed by these codes (``ask_fallback_copy``), never model prose —
    the model chooses a reason, it never writes the clarification."""

    NO_SUBJECT = "no-subject"
    AMBIGUOUS_SUBJECT = "ambiguous-subject"
    SET_REFERENCE = "set-reference"
    VERIFICATION = "verification"
    AMBIGUOUS_INTENT = "ambiguous-intent"
    PARSE_FAILED = "parse-failed"


class SubjectDisposition(str, Enum):
    """WHERE a resolved subject lives in a sliced (rolling) world — Session 4A.5c
    CU4, the prerequisite the 4A.5b rolling ruling named.

    On a rolling run the Explainer's snapshot is WINDOW 0 ONLY. Before this, an
    order sitting in the beyond-horizon tray resolved to nothing and was answered
    as ABSENT — a confident-wrong answer ("that order isn't in this schedule")
    replacing a correct one ("it's known, it just hasn't been pulled into a window
    yet"). Subject resolution now reads the rolling document's vocabulary as well,
    and says WHICH of the three sliced regions the subject came from.

    IN_WINDOW       — placed in the active window (the monolithic default).
    COMMITTED       — placed AND frozen: it will not move as the schedule rolls.
    BEYOND_HORIZON  — in the tray: admitted, due-dated, not yet windowed. A real
                      subject with a real disposition. NEVER "not in this
                      schedule".
    """

    IN_WINDOW = "in-window"
    COMMITTED = "committed"
    BEYOND_HORIZON = "beyond-horizon"


class SubjectRef(BaseModel):
    """One typed subject, as the planner named it and as it resolves here."""

    model_config = ConfigDict(extra="forbid")

    kind: SubjectKind
    raw: str = ""                       # the planner's own words
    ref: Optional[str] = None           # the external ref it resolved to, or None
    source: SubjectSource = SubjectSource.UTTERANCE
    # True when the planner POINTED instead of naming ("this order", "it", or an
    # intent that plainly applies to whatever is selected). A pointed subject that
    # binds to nothing CLARIFIES; a NAMED one that resolves to nothing is answered
    # as absent. The two are different honesty failures and get different answers.
    pointed: bool = False
    # Where the subject lives in a sliced world (Session 4A.5c CU4). None on a
    # monolithic run, where there is one region and naming it would be noise.
    disposition: Optional[SubjectDisposition] = None

    @property
    def resolved(self) -> bool:
        return bool(self.ref)

    @property
    def beyond_horizon(self) -> bool:
        return self.disposition is SubjectDisposition.BEYOND_HORIZON


class ClarifyPayload(BaseModel):
    """The clarify path: the parse cannot commit, so it asks — never guesses."""

    model_config = ConfigDict(extra="forbid")

    reason: ClarifyReason
    detail: str = ""


class ParsedQuestion(BaseModel):
    """The closed contract one parse emits (R-AI5(1)). Never an answer.

    Validation-at-construction: a malformed model emission dies here, at the source,
    and the parser retries once then yields the clarify path (never a guess, never a
    crash)."""

    model_config = ConfigDict(extra="forbid")

    question: str
    intent: Intent = Intent.UNMATCHED
    subjects: list[SubjectRef] = Field(default_factory=list)
    polarity: Optional[Polarity] = None
    followup_of: FollowupKind = FollowupKind.NONE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    nearest: list[Intent] = Field(default_factory=list)
    clarify: Optional[ClarifyPayload] = None
    # -- Session 4A.5c CU3(c): THE ADJACENT-MATCH GUARD ----------------------
    # The words of a qualifier the planner STATED that the matched intent does not
    # honour — a time scope ("next month"), an "actually", a comparative. Empty
    # when the match is clean.
    #
    # This is the last hiding place the round-five review named. Both remaining
    # unmet expectations from 4A.5b are the same shape: "how many orders will be
    # late NEXT MONTH" matched `late-orders`, which answers about THIS plan; "how
    # much of CUT-01s week is ACTUALLY working time" matched `downtime`, which
    # answers the complement. Neither is a mis-parse — the intent really is the
    # nearest one — and both answer a question the planner did not ask, with
    # perfect citations. The dispatch reads this field and diverts to the second
    # tier, which can answer the qualified question or say honestly that it
    # cannot. The model REPORTS the dropped qualifier; it never decides the
    # diversion (R-AI5(8)'s discipline applied to routing).
    dropped_qualifier: str = ""
    # Instrumentation (the sweep's parse-specific counts; never read by a route).
    prompt_version: str = ""
    retries: int = 0
    latency_ms: Optional[float] = None

    # -- convenience readers the dispatch uses ------------------------------

    def of_kind(self, kind: SubjectKind) -> list[SubjectRef]:
        return [s for s in self.subjects if s.kind == kind]

    def first(self, kind: SubjectKind) -> Optional[SubjectRef]:
        hits = self.of_kind(kind)
        return hits[0] if hits else None

    def ref(self, kind: SubjectKind) -> Optional[str]:
        s = self.first(kind)
        return s.ref if s is not None else None

    def refs(self, kind: SubjectKind) -> list[str]:
        return [s.ref for s in self.of_kind(kind) if s.ref]

    def unresolved(self, kind: SubjectKind) -> list[SubjectRef]:
        return [s for s in self.of_kind(kind) if not s.resolved]


# ---------------------------------------------------------------------------
# The authored intent meanings — what the governed parse prompt renders.
# ---------------------------------------------------------------------------

#: One line per model-selectable intent, in planner language. These are the closed
#: vocabulary's DEFINITIONS: the parse prompt is built from them, so a route added
#: without a meaning is a parity failure, not a silently-unreachable intent.
INTENT_MEANINGS: dict[Intent, str] = {
    Intent.LATE_ORDER:
        "why ONE order is late (its cause chain) — the order the planner named, "
        "or the one the conversation is already about. A follow-up like \"but "
        "why\" after one order's cause chain is THIS, not a plan-wide question",
    Intent.LATE_ORDERS:
        "which orders are late / how many are late (the whole plan) — the LIST or "
        "the COUNT. NOT \"why are so many late\" (that is `lateness-cause`)",
    # Session 4A.5c: the meaning is written to SEPARATE the intent from its two
    # neighbours, because that is where a promotion costs something. Its first
    # sweep proved it: `lateness-cause` immediately over-attracted "but why" — a
    # DEEPEN follow-up on one selected order, one turn after that order's cause
    # chain — the same way `prove-it` over-attracted the same question the moment
    # 4A.5b made it nameable (parse prompt v6). A new vocabulary member perturbs
    # its neighbours; the cure is the same one, applied at the same place.
    Intent.LATENESS_CAUSE:
        "why the PLAN AS A WHOLE has the lateness it has — the cause mix across "
        "the WHOLE late set (\"why are so many orders late\", \"whats driving the "
        "lateness in this plan\", \"what is making these orders late\"). It takes "
        "NO subject and is never about one order: if the question is about a "
        "named order, a selected order, or the order the previous answer was "
        "about — including a bare \"but why\" — it is `late-order`. It is also "
        "not the list or the count (`late-orders`)",
    Intent.WHY_ON_MACHINE:
        "why an order was assigned to a particular machine",
    Intent.MACHINE_SCHEDULE:
        "what is running (or next) on a machine",
    Intent.ORDER_SCHEDULE:
        "when one order starts / finishes (its timeline)",
    Intent.CUSTOMER_SCHEDULE:
        "every job for a named customer",
    Intent.SCHEDULE:
        "the whole schedule, machine by machine (no single subject)",
    Intent.DOWNTIME:
        "a machine's calendar closures / downtime hours",
    Intent.ORDER_ATTRIBUTES:
        "one order's details (product, quantity, customer, due date, release)",
    Intent.INVENTORY:
        "counts of orders / jobs / operations, or which orders were split",
    Intent.INTEGRITY_CHECK:
        "is anything double-booked / overlapping on a machine",
    Intent.START_REASON:
        "why an order starts when it does, or why it cannot start earlier, or "
        "why it is running so early",
    Intent.CONTESTED_FACT:
        "the planner CONTESTS a status the assistant stated (\"isn't ORD-05 on "
        "time?\", \"I thought that one was fine\")",
    Intent.SWAP_MOVE:
        "should/could two orders swap slots, or one order move earlier / to "
        "another machine (the board gesture)",
    Intent.GAP_BETWEEN:
        "why there is a gap or slack between two jobs on a machine, or why one "
        "does not run right after another",
    Intent.MACHINE_IDLE:
        "why a machine carries no work / sits idle",
    Intent.DATA_PROBLEMS:
        "what data-quality problems / findings the submission has",
    Intent.REMEDIATION:
        "how to FIX the submission's data problems",
    Intent.TRIAGE:
        "what to fix FIRST / what matters most",
    Intent.CERTIFICATE_TESTIMONY:
        "what is wrong with the submission / why it was rejected or conditional",
    Intent.EXCLUDED_ORDERS:
        "which orders were excluded / dropped from the plan and why",
    Intent.VERSION_DIFF:
        "what changed between two schedule versions",
    Intent.EDIT_SUMMARY:
        "summarize the edits the planner made this session",
    Intent.EDIT_COST:
        "what the planner's last move / edit cost",
    Intent.LEDGER_REFUSALS:
        "which questions the assistant could not answer recently",
    Intent.DRILL_DOWN:
        "open the full record behind something the assistant JUST said, when the "
        "question adds no subject of its own (\"tell me more\", \"expand that\"). "
        "NOT for \"tell me about <a thing>\" — that is a question about the thing",
    Intent.BRIEFING:
        "what should I worry about today / what needs my attention",
    Intent.ADVICE:
        "what should I DO about lateness or capacity — a recommendation, an "
        "intervention, or a hypothesis about changing the plant (\"if we ran "
        "overtime...\", \"can I get this done faster\")",
    Intent.COACHING:
        "how do I enable / configure a capability in the submission (splitting, "
        "overtime, alternates, customers, earliness, spanning downtime, WIP)",
    Intent.SOLVE_TIME:
        "how long the solve took",
    Intent.MACHINE_COUNT:
        "how many machines / list the machines",
    Intent.MAINTENANCE:
        "maintenance, shifts, or calendar questions across the plant",
    # The three ROLLING (sliced-world) meanings, sharpened in Session 4A.5c from
    # the rolling bank's own miss. They were authored in 4B.3c for a keyword
    # pre-route, where "beyond the horizon" and "why isn't X scheduled" were
    # separated by which trigger tuple matched. Under a parse they were separated
    # by nothing: "what work is coming that isnt scheduled yet" — a question about
    # the WHOLE TRAY, naming no order — reached `why-not-scheduled-yet`, which
    # needs one, and the planner was asked which order they meant after asking
    # about all of them. The distinction is SET vs ONE, and it is now said.
    Intent.BEYOND_HORIZON:
        "what lies beyond the planning horizon — the WHOLE SET of known orders "
        "not yet pulled into a scheduling window (\"what's beyond the horizon\", "
        "\"what work is coming that isn't scheduled yet\", \"what's still to "
        "come\"). No subject: it is about all of them (rolling runs)",
    Intent.WHY_NOT_SCHEDULED_YET:
        "why ONE NAMED order is not scheduled yet. Only when the planner names a "
        "specific order — a question about the unscheduled work in general is "
        "`beyond-horizon` (rolling runs)",
    Intent.FROZEN:
        "what is frozen / committed / locked in and will not move as the plan "
        "rolls forward (rolling runs)",
    Intent.CONFIRM_TAKE:
        "the planner is repeating the assistant's OWN prior suggestion back as a "
        "question, to confirm it (\"so move the first operation earlier?\")",
    Intent.PROVE_IT:
        "the planner asks for the GROUNDS of something the assistant just said — "
        "\"prove it\", \"how do you know that?\", \"where does that come from?\", "
        "\"which record says that?\". Set `followup_of` to `prove-it` as well",
    Intent.UNMATCHED:
        "no intent above fits this question",
}

#: The intents the parse prompt offers the model, BEFORE demotion. ``unknown-entity``
#: is a DISPATCH outcome (a named order that resolves to nothing), never something a
#: planner expresses, so it is never offered.
#:
#: Read ``model_selectable_intents()`` rather than this tuple: a DEMOTED promotion
#: (R-AI5(7)) leaves the live vocabulary, and this constant does not know about it.
#: It is kept as the un-demoted baseline the parity test checks the taxonomy against.
MODEL_SELECTABLE_INTENTS: tuple[Intent, ...] = tuple(
    i for i in Intent if i is not Intent.UNKNOWN_ENTITY
)


def model_selectable_intents() -> tuple[Intent, ...]:
    """The intents the parse prompt offers RIGHT NOW (R-AI5(7)).

    Demotion is "a mechanical flag flip": an intent whose ``Promotion`` is DEMOTED
    is subtracted here, so the prompt stops offering the id, the parse can no
    longer name it, and the shape it used to serve returns to the second tier. That
    is the entire demotion path — there is no second switch to remember, and no
    dead route left reachable by a stale phrasing.

    The import is deferred because ``contracts.promotion`` names ``Intent``: the
    dependency runs one way, and this function is the only place it turns around."""
    from mre.contracts.promotion import demoted_intents
    demoted = demoted_intents()
    return tuple(i for i in MODEL_SELECTABLE_INTENTS if i not in demoted)
