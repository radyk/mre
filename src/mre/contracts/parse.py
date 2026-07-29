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
    # Session 4B.14 Item 2 — THE BLOCKER ANALYSIS. `start-reason` answers "why
    # does it start when it does" from ONE causal story, resource contention:
    # the last job on the machine before it. The plant has at least six stories
    # (docs/05 A4, A1/A2, R-F1, A7/F1, B1, C1/C2, C3) and when the true cause was
    # one of the other five the route reached for the only one it had and
    # rendered it fluently, with citations. The measured specimen: ORD-000013's
    # op20 waited for Thursday because it needs 7h11m in one piece and 4h54m
    # remained before PAINT-01 closed — a chunk-fit cause, explained as
    # contention, citing a timestamp four days off.
    #
    # `why-here` computes an earliest-feasible-start per FAMILY and names the one
    # that binds. It also draws the distinction `start-reason` cannot: whether
    # the operation COULD NOT have gone earlier, or whether nothing prevented it
    # and the solver CHOSE this placement. Those are different facts to a
    # planner and the product asserted the first for both.
    WHY_HERE = "why-here"
    # Session 4B.15 Item 3 — ATTRIBUTE LOOKUP. There was no route that reads a
    # declared field off an entity and states it, so "is ORD-000013 op20
    # splittable" returned capability documentation with a scold and "how long
    # does op20 take" returned the order card — while the blocker analysis, one
    # exchange later, quoted both answers off the same snapshot. The facts were
    # loaded; nothing asked for them.
    #
    # The rule is deliberately broad rather than an enumeration: ANY declared
    # field on ANY entity in the persisted run is askable and answerable,
    # verbatim, with its source. Operation-scoped where the entity is an
    # operation.
    ATTRIBUTE_LOOKUP = "attribute-lookup"
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
    # Session 4B.5 CU2 — the OPEN DELTA CARD. A priced move is showing on the
    # board and the planner asks about IT ("what orders are affected in this
    # move", "these orders", "the delta"). Before this the question had nowhere
    # to go: the founder's own exchange parsed as `swap-move`, which reasons about
    # two orders' slack and knows nothing about the card on screen — a guess where
    # the answer was already computed and sitting in front of them. The card is a
    # CONTEXT CHANNEL (highest priority in the resolution ladder) and this is the
    # route that voices it. Reachable ONLY when a card is open; the dispatch
    # enforces that, because the model reports and never decides (R-AI5(8)).
    OPEN_CARD = "open-card"
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
    # Session 4B.13 Item 2 — THE OPTIMALITY QUESTION GETS A ROUTE (discharges
    # docs/07 §5a.29). 4B.11 rendered the cost proof on the strip and as an
    # unprompted rider, but nobody could ASK for it: "is this schedule optimal?"
    # — the most obvious question a stranger asks after seeing the badge — fell
    # to synthesis, which cannot see `solver.status`, so it invented its own
    # definition of optimal from a bar count and reached the right verdict by
    # the wrong road, from a false premise. The proof existed, was correct, and
    # was unreachable by asking.
    SOLVE_OPTIMALITY = "solve-optimality"
    MAINTENANCE = "maintenance"
    # -- the rolling (sliced-world) routes ----------------------------------
    BEYOND_HORIZON = "beyond-horizon"
    WHY_NOT_SCHEDULED_YET = "why-not-scheduled-yet"
    FROZEN = "frozen"
    # Session 4B.6 (R-SC2 coarse-zone amendment) — THE COARSE ZONE reaches the
    # ask path (R-AI1). Beyond-horizon work is now coarsely PLACED, not merely
    # listed, so two questions became answerable that previously had no route
    # and would have fallen to synthesis for want of a vocabulary entry:
    #
    #   COARSE_FIT  — "will it fit?" / "can we take this on?". Answered from the
    #                 PROOF run ONLY (clause 2), and only the NEGATIVE is ever
    #                 claimed: a complete proof-run INFEASIBLE names the
    #                 resource-week that refutes it. A proof run that PLACES the
    #                 book proves nothing about the fine model, and the answer
    #                 says exactly that rather than converting it into a yes.
    #   BUCKET_LOAD — "why is week N full?". Answered from the binding capacity
    #                 constraint: the resource-week, its load, and its DERATED
    #                 capacity, with rho and its provenance stated.
    #
    # "When will ORD-X start?" deliberately gets NO new intent: it is already
    # `why-not-scheduled-yet`, whose answer now carries the coarse bucket beside
    # the due-date heuristic. Adding a route for it would have been the ad-hoc
    # bolt-on the session brief forbids.
    COARSE_FIT = "coarse-fit"
    BUCKET_LOAD = "bucket-load"
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
    won (RUBRIC C3).

    The ladder, highest priority first (Session 4B.5 CU2 puts CARD at the top):

      CARD        — an OPEN DELTA CARD is showing a priced move. Nothing outranks
                    it: the planner is looking at one thing, they asked about one
                    thing, and every other channel is a weaker guess about what.
      SELECTION   — a live board selection.
      LAST_ANSWER — the subject of the previous answer.
      HISTORY     — earlier in the conversation.
    """

    UTTERANCE = "utterance"
    CARD = "card"
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


class ContestedClaim(str, Enum):
    """WHAT a `contested-fact` turn is disputing (Session 4B.14 Item 3).

    THE MEASURED FAILURE — DISAGREEMENT LAUNDERING. Live on the pinned board the
    planner said "it seems it should be able to start on tuesday after op10
    finishes": a challenge to the system's causal reasoning, carrying the correct
    hypothesis. The parse turned it into "is ORD-000013 really on time?" and
    answered "Yes - the record agrees."

    A challenge to the reasoning became a question about lateness, and the
    affirmative reads as agreement while addressing nothing that was said. For a
    product whose pitch is "interrogate the schedule" that is the worst available
    failure — worse than a wrong number, because the planner cannot tell they
    were ignored.

    The intent was never the problem: it IS a contest. The ASSEMBLER knew one
    proposition, lateness, and its canonical question was literally "is {order}
    really on time?". This enum is what the parse REPORTS so the dispatch can
    answer on the planner's own terms (R-AI5(8): the parse reports, the dispatch
    decides).

    LATENESS — a status the assistant stated ("isn't ORD-05 on time?").
    TIMING   — the assistant's account of WHEN or WHY something was placed ("it
               should be able to start Tuesday", "but the machine was free").
    OTHER    — a dispute this vocabulary cannot classify. Answered by saying the
               challenge could not be evaluated, never by substituting a
               question that could.
    """

    LATENESS = "lateness"
    TIMING = "timing"
    OTHER = "other"


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
    # -- Session 4B.14 Item 3: WHICH claim a contest disputes ----------------
    # Reported only on `contested-fact`. The dispatch reads it to answer the
    # challenge on its own terms instead of re-parsing it into the one
    # proposition the assembler happened to know. None from an older parse or a
    # non-contest intent, which the assembler treats as LATENESS — the behaviour
    # before this field existed, so no parse becomes unanswerable by upgrading.
    contested_claim: Optional[ContestedClaim] = None
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
    # Session 4B.5 CU2 — reachable ONLY when the context block shows an OPEN
    # DELTA CARD. The meaning says so, and the dispatch enforces it: an
    # `open-card` parse with no card in context is not answered as one.
    Intent.OPEN_CARD:
        "a question about the PRICED MOVE the delta card is showing right now — "
        "\"what orders are affected in this move\", \"what does this move cost\", "
        "\"the delta\", \"these orders\", \"what else moved\", \"is this worth "
        "it\". Only when the context block says a delta card is OPEN; with no "
        "card open the same words are about the plan, not about a card",
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
        "why an order starts when it does at all, or why it is running so EARLY "
        "(ahead of its due date). A question about what is HOLDING IT BACK, or "
        "why it could not go earlier / on a named earlier day, is `why-here`",
    Intent.WHY_HERE:
        "what is BLOCKING this operation from starting earlier — \"why is this "
        "here?\", \"why can't it start Monday?\", \"what's holding it up?\", "
        "\"why not earlier?\", \"why the wait?\", \"couldn't it go before "
        "that?\". The question asks for the BINDING CONSTRAINT on a placement, "
        "which may be an earlier step, the machine being held, the calendar, a "
        "window too short for the work, a pin or the frozen boundary — or "
        "nothing at all. Prefer this over `start-reason` whenever the question "
        "names an earlier time, an alternative day, or asks what prevents "
        "something; prefer `gap-between` only when the planner asks about the "
        "space between TWO named orders",
    Intent.CONTESTED_FACT:
        "the planner DISPUTES something the assistant just said — a status "
        "(\"isn't ORD-05 on time?\", \"I thought that one was fine\") or, just "
        "as often, the assistant's REASONING (\"it seems it should be able to "
        "start on tuesday after op10 finishes\", \"that can't be right\", \"but "
        "the machine was free\"). Set `contested_claim` to say WHICH kind: "
        "`lateness` for a status, `timing` for a challenge to when or why "
        "something was placed, `other` when it is neither",
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
        "overtime...\", \"can I get this done faster\"). If the question NAMES a "
        "capability the submission can declare (overtime, splitting, alternates, "
        "customers, earliness, spanning downtime, WIP), carry it as a concept "
        "subject — including in a push-back like \"so you can't tell me if "
        "overtime will help\", where the capability is what they actually want",
    # Session 4B.15 Item 3. Written to SEPARATE it from `coaching` and
    # `order-attributes`, because that is where a new vocabulary member costs
    # something: all five measured turns that `coaching` swallowed are this
    # intent, and two of them name a field outright.
    Intent.ATTRIBUTE_LOOKUP:
        "what does the record SAY about a specific job — one declared field on "
        "one order or operation, read off and stated. \"is ORD-13 op20 "
        "splittable?\", \"what's the minimum chunk on that operation?\", \"how "
        "long does op20 take?\", \"what's its setup family / due date / "
        "quantity / which machines can run it?\". It asks for a VALUE, not for "
        "how to change one (`coaching`) and not for a whole order's card "
        "(`order-attributes`). Prefer this whenever the question names a field "
        "and a job, however the planner phrases it",
    # Session 4B.15 Item 5 — WIDENED from "how do I enable X" to cover "can it
    # handle X" as well. Both are answered from the same place now: the
    # constraint catalog says what is modeled, what is deliberately excluded and
    # what is designed-but-unbuilt, and the registry says how to declare the
    # ones you can declare. Before this, a capability question the registry did
    # not recognize fell to synthesis, which had no catalog and answered "can
    # two machines share one operator" with a confident yes about alternates.
    Intent.COACHING:
        "WHAT THE SYSTEM CAN AND CANNOT MODEL, and how to declare it — \"can it "
        "handle X?\", \"does it support Y?\", \"can two machines share one "
        "operator?\", \"can two orders share an oven cycle?\", \"how do I "
        "enable splitting / overtime / alternates / customers / WIP?\". About "
        "the PRODUCT'S CAPABILITIES, not about a value in this plan (that is "
        "`attribute-lookup`)",
    Intent.SOLVE_TIME:
        "how long the solve took",
    Intent.MACHINE_COUNT:
        "how many machines / list the machines",
    Intent.SOLVE_OPTIMALITY:
        "is this schedule optimal / is this the best/cheapest plan / could it be "
        "cheaper / did the solver finish — a question about the SOLVER'S OWN "
        "PROOF of the cost optimum, answered from what the solve reported. Not "
        "about whether the plan is good or whether orders are late",
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
    Intent.COARSE_FIT:
        "whether known future work FITS — \"will it fit\", \"can we take this "
        "on\", \"is there room for this\", \"can the plant absorb the backlog\". "
        "About CAPACITY over the coming weeks, not about one order's placement "
        "(that is `why-not-scheduled-yet`) and not about lateness in the current "
        "window (that is `late-orders`) (rolling runs)",
    Intent.BUCKET_LOAD:
        "why a future WEEK or period is full / saturated / has no room — \"why "
        "is week 3 full\", \"what's filling up March\", \"which machine is the "
        "bottleneck beyond the horizon\". About a coarse time bucket's capacity, "
        "not about a machine's current-window schedule (that is "
        "`machine-schedule`) (rolling runs)",
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
