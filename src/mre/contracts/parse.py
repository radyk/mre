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
    # Session 4B.16 Item 1 — THE COUNTERFACTUAL. `why-here` names the binding
    # constraint; this names what would have to be DIFFERENT for the operation
    # to go earlier, with the threshold and the arithmetic, over the SAME
    # computed bounds and no new ones.
    #
    # It is a distinct intent rather than a paragraph on the blocker analysis
    # because it is a different PREDICATE about the same subject, and the two
    # answers are acted on differently: one is a diagnosis, the other is a list
    # of changes a planner could go and make in the submission. Appending it to
    # every `why-here` would also make the diagnosis longer every time, for the
    # majority of turns that never asked for a remedy.
    #
    # THE HARD RULE it carries: what it reports is NECESSARY, never sufficient.
    # Each lever removes the bound that binds; whether the solver would then
    # place the operation there needs a re-solve, which R-AI4 forbids. Every
    # answer names the NEXT bound that would apply.
    WHAT_WOULD_CHANGE = "what-would-change"
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
    # -- Session 4A teaching-graft (b), R-TG2: THE TEACHING INTENT ------------
    # A question whose goal is UNDERSTANDING rather than a fact off this board:
    # "in general, what makes a scheduling problem hard to prove optimal", "how
    # does a rolling horizon normally work", "what is a bottleneck machine".
    #
    # THE MEASURED SCATTER (census (a), 10 domain probes, live parse, demo
    # board, prompt v17): `coaching` 5 / `unmatched` 4 / `lateness-cause` 1.
    # Half of them reached `coaching`, whose meaning is WHAT THE SYSTEM CAN AND
    # CANNOT MODEL and whose answer is a capability lookup against docs/05 — a
    # 3-line answer (measured: median 3, max 3 content lines over 102 turns) to
    # a question that asked to be taught something. The other four reached the
    # second tier, which answered them WELL, and got the SHORT budget every
    # other synthesis question gets, because no budget distinguished them.
    #
    # IT IS NOT A ROUTE, AND THAT IS THE RULING RATHER THAN AN OMISSION.
    # Teaching is SYNTHESIS WITH A SECOND CLAIM CLASS AND A DEPTH LICENCE, not
    # a new rung (R-TG1 built the class in session (a); R-TG3 grants the
    # licence). There is no contracted evidence assembly for "how does this
    # normally work" and inventing one would be authoring domain prose as
    # testimony — the exact failure R-TG1 exists to end, one layer up. So it
    # joins ``SECOND_TIER_INTENTS``: a DECLARED door to the tier that already
    # reasons, carrying a budget the door decides.
    #
    # The seal (R-AI5(2)) is untouched in both directions. No CONTRACTED route
    # can fall to synthesis; this intent never was one. And synthesis still
    # never guesses a route — a teaching parse dispatches to the tier by name.
    TEACHING = "teaching"
    # -- Session 4A teaching-graft (d.3), R-TE1: THE PRODUCT'S OWN WORDS -------
    # A question about a word THIS PRODUCT SAID: "what do you mean seed", "what
    # is a gap", "you mentioned seed 44 — what does it mean to change seeds".
    #
    # THE FOUNDING SPECIMEN, reproduced live before anything was built. The
    # `solve-optimality` route — a CONTRACTED one — answers the cost-optimum
    # question with the word "seed" nine times, and the two most natural
    # follow-ups a planner can type reached two different refusals:
    #
    #   "what do you mean seed"       -> parse proposed `prove-it`, bound NO
    #                                    subjects, and the dispatch's
    #                                    subject-resolution guard CLARIFIED
    #   "...what does it mean to      -> parse proposed `coaching` with a
    #    change seeds"                   CONCEPT subject raw="seed" that
    #                                    resolved to None, so the capability
    #                                    coach said "I don't recognize which
    #                                    capability you mean"
    #
    # THE SECOND ONE IS THE INTERESTING HALF: the model had already identified
    # the gesture AND extracted the term. Nothing was missing from the parse —
    # what was missing was an intent for it to name, so the nearest neighbour
    # took it and answered a question nobody asked.
    #
    # IT IS A CONTRACTED ROUTE, NOT A SECOND-TIER INTENT, and that is the
    # ruling rather than a convenience. `teaching` went to the tier because
    # there is no contracted evidence assembly for "how does this normally
    # work". Here there is: a definition of OUR word is a claim about THIS
    # PRODUCT's behaviour — R-TG6 (i)'s species — so it must cite the artifact
    # that defines it, and a model improvising a definition of our own
    # vocabulary is exactly the uncited product claim R-TG6 (i) DROPS. Authored
    # copy with a resolved citation is the only shape that can be right.
    TERM_EXPLANATION = "term-explanation"
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


#: THE INTENTS WHOSE DESTINATION IS THE SECOND TIER, NOT A CONTRACTED ROUTE
#: (Session 4A teaching-graft (b), R-TG2).
#:
#: ``unmatched`` was always such a door — the parity test
#: (``tests/test_parse_contract.py``) subtracted it from the vocabulary before
#: comparing against ``ROUTE_TAXONOMY``, with a comment where a name should have
#: been. ``teaching`` is the second member and the reason to name the set: both
#: mean "this intent is answered by reasoning over evidence under a stated
#: budget", and neither has — or should have — an entry in the route taxonomy.
#:
#: A member here is NOT a wall. It is reachable, by the one door R-AI5(2) opens;
#: what it lacks is a contracted assembler, which is the whole point.
SECOND_TIER_INTENTS: frozenset[Intent] = frozenset(
    {Intent.UNMATCHED, Intent.TEACHING})


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

    R-LD5 (Session 4A teaching-graft (d.1), docs/04 2026-08-04) — AND ONE MORE,
    BECAUSE THE LADDER IS NOT THE ONLY RESOLVER.

      CONVERSATION — the PARSE MODEL read the referent out of the RECENT TURNS
                     block. Every rung of the ladder was empty and the model
                     still produced usable words, which `bind_subjects` then
                     resolved.

    Measured in the (d.0) recon (P2b, D-02): *"why cant this be moved earlier"*
    with nothing selected, one turn after *"why is ORD-000073 op10 placed where
    it is"*, came back as a full counterfactual **about ORD-000073 op10** — an
    order the planner had not named in that sentence and a grain that existed
    nowhere but inside the previous question's text. It reported
    `source: utterance`, so it was indistinguishable from a subject the planner
    had typed, and the disclosure line was EMPTY. The same subject recovered by
    the LADDER is disclosed in full.

    UTTERANCE now means what it says: the planner's own words, this turn.
    """

    UTTERANCE = "utterance"
    CARD = "card"
    SELECTION = "selection"
    LAST_ANSWER = "last-answer"
    HISTORY = "history"
    CONVERSATION = "conversation"


class Polarity(str, Enum):
    """The direction the question asks about, where the intent carries one.

    POSITIVE — explain the property as it stands ("why is ORD-05 late", "why does
               ORD-13 start so early").
    NEGATIVE — explain the inverse / the absence ("why is ORD-13 NOT late", "why
               can't ORD-05 start sooner", "why is nothing running on CUT-01").
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"


class MoveDirection(str, Enum):
    """WHICH WAY a move question wants an operation to go (Session 4B.30 Item 1).

    THE MEASURED FAILURE — A DIRECTIONAL QUESTION ANSWERED BACKWARDS. Measured
    twice on the demo board (4B.22 live, 4B.27 turn 1, re-measured verbatim at
    the head of 4B.30): "can i move ORD-000057 later, maintenance wants the
    machine for the day" was answered with three ways to move it EARLIER. The
    census that opens 4B.30 found the failure is not a near miss — six of seven
    direction-bearing phrasings, "later" and "earlier" alike, returned a
    BYTE-IDENTICAL paragraph about starting earlier. The deafness rider fired on
    the repetition, which is the product noticing what the route could not.

    `what-would-change` was built (4B.16) as the inverse of `why-here` over the
    SAME computed bounds, and those bounds are all earliest-start floors — so
    the route had no later direction to reach for. Adding one is a MEANING
    widening, not a new intent: the question is still "what would have to be
    different about this one operation's placement".

    EARLIER  — "how do I get this earlier", "what would it take to move this up".
    LATER    — "can I move this later", "push it out a week", "delay it to
               Friday", "maintenance wants the machine".
    UNSTATED — the question supposes a condition being different without naming
               a direction ("what if it were splittable", "what would have to
               change"). Treated as EARLIER, which is what the route has always
               answered and what those phrasings have always meant here.

    THE PARSE REPORTS THE DIRECTION; IT NEVER DECIDES THE ROUTE (R-AI5(8)), and
    it never resolves the target — see :attr:`ParsedQuestion.move_target`.

    Session 4A.x (the listening docket) Item 2 — THIS FIELD IS THE MOBILITY
    FAMILY'S DIRECTION MARKER, AND `why-here` CARRIES IT TOO. It was reported on
    `what-would-change` and `swap-move` only, so a mobility question that landed
    on `why-here` — which is every "why can't this be moved" — had its direction
    decided by the ROUTE'S MEANING and disclosed nowhere. The measured specimen,
    with ORD-000128 selected on the demo board:

        Q: "why cant this be moved"
        INTERPRETED AS: "why cant ORD-000128 be moved [from board selection]"

    The SUBJECT resolution was disclosed. The DIRECTION resolution — "moved"
    read as "moved EARLIER", which is the only direction `why-here` computes —
    was not, and the answer served the earliest-start chain. One assumption
    named, one silent, in the same line.

    NOTHING WIDENS HERE EXCEPT WHAT IS REPORTED. `why-here` still answers the
    earlier direction; what changes is that the answer now SAYS the direction
    was assumed, and that `unstated` is what makes an assumption visible. Hence
    the discipline this enum already carries is load-bearing in a second place:

      None      — the question is not about MOVING at all ("why is this here?",
                  "why is it late"). Nothing is assumed, so nothing is
                  disclosed, and every pre-existing phrasing keeps its exact
                  answer.
      UNSTATED  — about moving, direction not said. DEFAULTED to earlier, and
                  the disclosure line says so.
      EARLIER /
      LATER     — STATED. Disclosure unchanged: a planner is never told back
                  what they just said.
    """

    EARLIER = "earlier"
    LATER = "later"
    UNSTATED = "unstated"


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
    #: Micro-session 4A — THE OUTAGE, and it is not a question back.
    #:
    #: Every other member here is a reason to ASK the planner something. This
    #: one is a reason there is nothing to ask: the parse layer could not reach
    #: its language model, so the question was never read at all. It is minted
    #: LOCALLY (like `parse-failed`, never by the model — a model that cannot be
    #: reached emits nothing) and the dispatch answers it with the OUTAGE floor
    #: rather than the clarify bundle, because "which order did you mean?" is a
    #: capability sentence and this is an infrastructure fact.
    MODEL_UNREACHABLE = "model-unreachable"


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
    # -- Session 4A.x (the listening docket) Item 1: THE GRAIN -----------------
    # WHICH OPERATION of this order the planner named ("ORD-000126 op30"). An
    # operation is not a subject of its own: it does not resolve independently,
    # it has no identity a planner would type on its own, and making it a
    # `SubjectKind` would let a parse bind an op with no order. It is the GRAIN
    # of an order subject, so it lives here.
    #
    # THE MEASURED FAILURE it exists to end. "why cant ORD-000126 op30 start
    # earlier", live on the demo board, was answered:
    #
    #     "Answering about ORD-000126 op10 on CUT-01 — the first of its 3
    #      operations. Nothing prevented ORD-000126 op10 from starting earlier…"
    #
    # The vocabulary had no way to carry "op30", so the parse — correctly
    # refusing to drop words it had heard — emitted it as a SECOND ORDER
    # subject, which resolved to nothing and was discarded. Downstream,
    # `route_params` never set `op_seq` at all, so on the LIVE ask path the
    # eight routes that read it saw None from every question ever typed; the
    # only channels that ever supplied it were the board SELECTION and two
    # per-route re-scans of the question text. The route then fell back to the
    # order's first operation and announced the fallback as though nobody had
    # named one.
    #
    # None means the planner named no operation — NOT "operation 0". A route
    # that can only answer at order grain says so rather than substituting
    # (the dispatch computes that note; no assembler has to remember it).
    op_seq: Optional[int] = None
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
    # -- Session 4B.30 Item 1/2: WHICH WAY, and TOWARDS WHAT ------------------
    # Reported on `what-would-change`, `swap-move` and — since the listening
    # docket — `why-here`. None from an older parse
    # or a non-move intent, which every assembler treats as EARLIER — the
    # behaviour before these fields existed, so no parse becomes unanswerable by
    # upgrading (the `contested_claim` precedent, 4B.14, deliberately followed).
    move_direction: Optional[MoveDirection] = None
    # The planner's OWN WORDS for where they want it moved to — "Friday", "a
    # week", "after the maintenance", "the day". RAW, never resolved: which
    # Friday, and whether that instant is inside an open window, are calendar
    # questions this repo answers with the calendar (`later_move.resolve_target`)
    # and DISCLOSES in the answer. A model that resolved them would be authoring
    # a date, and 4B.15 Item 0 is what happens when a date is authored from
    # whichever row appeared first. Empty when the question named no target.
    move_target: str = ""
    # -- Session 4A teaching-graft (b), R-TG4: WHO MUST BE TOLD ---------------
    # The planner's OWN WORDS for the HUMAN AUDIENCE a question names — "my
    # boss", "the customer", "the production meeting". Empty on the great
    # majority of questions, which name nobody.
    #
    # THE MEASURED FAILURE. "there are a lot of orders late what reason can i
    # give my boss and what will help lessen the impact" was answered, at HEAD,
    # with ~95 hold-pair lines, a 614-record evidence chain header and 134
    # content lines — the longest answer in every committed sweep, by a factor
    # of three and a half. Every line of it is TRUE. The planner asked for a
    # sentence they could say to a person and a lever they could pull; they got
    # an inventory. The goal was audience-shaped and the answer was
    # completeness-shaped.
    #
    # RAW, NEVER RESOLVED — the `move_target` precedent, deliberately followed.
    # WHO the boss is, what they already know and what they are entitled to hear
    # are not facts this product holds, and a model that resolved them would be
    # authoring a business relationship. All this field does is say that a
    # PERSON is on the other end of the answer.
    #
    # THE PARSE REPORTS; THE DISPATCH DECIDES (R-AI5(8)), and a deterministic
    # floor stands under the report — 4A.y measured a freshly-prompted field
    # reported 0 times in 5 on the phrasings planners use, and a disclosure that
    # depends on a model remembering a field will silently stop. See
    # `modules/audience_shape.py`: the floor can only ever RESHAPE a route that
    # was already going to run, and can never route.
    audience: str = ""
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

    @property
    def named_op_seq(self) -> Optional[int]:
        """The operation grain the planner NAMED, or None.

        Read off the order subjects in order, so the grain travels with the
        PRIMARY subject the way ``ref(SubjectKind.ORDER)`` does. It is
        deliberately not "the first non-None anywhere": a two-order question
        naming an op on the second one must not silently re-scope the answer
        about the first."""
        for s in self.of_kind(SubjectKind.ORDER):
            if s.resolved:
                return s.op_seq
        return None

    @property
    def named_op_seq_source(self) -> Optional[SubjectSource]:
        """Where :attr:`named_op_seq` came from — the SAME subject, by the same
        walk, so the grain and the order can never be attributed to different
        channels.

        R-LD5 (Session 4A teaching-graft (d.1)). The grain is part of the
        subject, and the P2b specimen's sharpest half was the grain: `op_seq 10`
        existed nowhere in the planner's sentence and nowhere in the payload
        except inside the PREVIOUS QUESTION'S TEXT, and it was reported as the
        planner's own. `route_params` reads this so the disclosure can tell an
        assumption from a statement."""
        for s in self.of_kind(SubjectKind.ORDER):
            if s.resolved:
                return s.source if s.op_seq is not None else None
        return None


# ---------------------------------------------------------------------------
# The authored intent meanings — what the governed parse prompt renders.
# ---------------------------------------------------------------------------

#: One line per model-selectable intent, in planner language. These are the closed
#: vocabulary's DEFINITIONS: the parse prompt is built from them, so a route added
#: without a meaning is a parity failure, not a silently-unreachable intent.
INTENT_MEANINGS: dict[Intent, str] = {
    # Session 4B.27 Item 5 — AND "TIGHT" IS THE SAME QUESTION.
    # "tight" is a word the BOARD puts on a bar: it means the order lands within
    # one working day of its due date without passing it. A planner asking "why
    # is this one tight" is asking about its position against its due date,
    # which is this route's own arithmetic — it went to `why-here` instead and
    # got a placement analysis that never used the word.
    Intent.LATE_ORDER:
        "why ONE order is late (its cause chain) — the order the planner named, "
        "or the one the conversation is already about. A follow-up like \"but "
        "why\" after one order's cause chain is THIS, not a plan-wide question. "
        "It ALSO owns questions about an order being TIGHT, close to its due "
        "date, or cutting it fine (\"why is this order tight\", \"why is this "
        "one so close\") — those ask where the order sits against its due date, "
        "which is this route's own answer. A question about what is BLOCKING an "
        "operation from starting earlier is still `why-here`",
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
        "space between TWO named orders. It is the DIAGNOSIS — a question "
        "about what would have to CHANGE, or what it would TAKE, is "
        "`what-would-change`",
    # Session 4B.16 Item 1. Written as the PAIR of `why-here`, the way 4B.14
    # wrote `why-here` as the pair of `start-reason`: the boundary is where a
    # new vocabulary member costs something, and here the boundary is
    # diagnosis versus remedy about the same operation.
    #
    # Session 4B.30 Item 1 — THE LATER DIRECTION, and it is a WIDENING, not a
    # new member. The meaning below said "to start earlier" and the route
    # obeyed it: "can i move ORD-000057 later, maintenance wants the machine"
    # came back with three ways to move it up. Both directions are the same
    # question about the same operation's placement, so both live here; what
    # changes is that the parse now REPORTS which way, and the raw words for
    # where.
    Intent.WHAT_WOULD_CHANGE:
        "what would have to be DIFFERENT about ONE operation's placement — "
        "EITHER DIRECTION. Earlier: \"what would have to change\", \"how do I "
        "get this earlier\", \"what would it take to move this up\", \"why "
        "can't it be earlier\", \"what if it were splittable\". LATER: \"can I "
        "move ORD-57 later\", \"push it out a week\", \"can we delay this to "
        "Friday\", \"push it back until after the maintenance\", \"maintenance "
        "wants the machine\", \"what would pushing this out cost\", \"can it "
        "wait until Monday\". A named day with no direction (\"can this move "
        "to Monday\") is also this. It asks for the CHANGE and how much of it, "
        "where `why-here` asks what is blocking it today. Prefer this whenever "
        "the question supposes a condition being different, asks what the "
        "planner could DO about one operation's placement, or asks what it "
        "would take — INCLUDING when the planner wants it moved OUT of the way "
        "rather than brought forward. It is NOT `swap-move` (a board move "
        "weighed between two orders, or a move to another MACHINE), NOT "
        "`advice` (about the plan or the plant, not one operation), and NOT "
        "`coaching` (about what the product can model at all). "
        "ALWAYS set `move_direction` on this intent — `later` when the planner "
        "wants it pushed out, delayed, moved back or off a machine someone "
        "else needs; `earlier` when they want it brought forward; `unstated` "
        "when the question names no direction. And set `move_target` to the "
        "planner's OWN WORDS for where they want it — \"Friday\", \"a week\", "
        "\"after the maintenance\", \"the day\" — verbatim and unresolved; "
        "leave it empty when they named no target. Never work out which Friday "
        "or what time: the calendar answers that",
    Intent.CONTESTED_FACT:
        "the planner DISPUTES something the assistant just said — a status "
        "(\"isn't ORD-05 on time?\", \"I thought that one was fine\") or, just "
        "as often, the assistant's REASONING (\"it seems it should be able to "
        "start on tuesday after op10 finishes\", \"that can't be right\", \"but "
        "the machine was free\"). Set `contested_claim` to say WHICH kind: "
        "`lateness` for a status, `timing` for a challenge to when or why "
        "something was placed, `other` when it is neither",
    # Session 4B.30 Item 1 — the census found this route direction-blind too:
    # its single-order take reads "the move worth pricing is the one that gives
    # it an EARLIER opening" whatever was asked. The boundary is stated here so
    # a LATER move of one operation lands on `what-would-change`, which prices
    # it; where the parse still sends one here, the take reads `move_direction`.
    Intent.SWAP_MOVE:
        "should/could two orders swap slots, or one order move to another "
        "MACHINE (the board gesture). A question about moving ONE operation "
        "EARLIER OR LATER IN TIME on the machine it is already on is "
        "`what-would-change`, not this. Set `move_direction` when the question "
        "carries one",
    # Session 4B.27 Item 4 — THE BOUNDARY IS THE NUMBER OF ORDERS NAMED.
    # "why can't ord-11 start right after ord-19" went to `why-here`, a
    # single-subject route, which answered about ORD-000011 and dropped
    # ORD-000019 without a word. This is the route that has slots for both, and
    # the meaning now says plainly that TWO NAMED ORDERS is what selects it.
    Intent.GAP_BETWEEN:
        "why there is a gap or slack between two jobs on a machine, or why one "
        "does not run right after another. WHENEVER THE QUESTION NAMES TWO "
        "ORDERS and asks about the timing of one RELATIVE TO THE OTHER — "
        "\"right after\", \"before\", \"straight after\", \"between them\", "
        "\"why the wait between\" — this is the intent, and BOTH orders are "
        "named as subjects, the one being asked about first. A question naming "
        "one order only is never this",
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
    # Session 4B.16 Item 2 — THE OPENER, widened from "what should I worry
    # about" to the whole family of first questions a planner asks of a board
    # they have just opened. The answer is the same either way: everything on
    # this board worth knowing, ranked by consequence, each line carrying its
    # number — including "three things, and none of them are on fire".
    Intent.BRIEFING:
        "what should I be looking at on this board — \"what should I worry "
        "about\", \"how does this schedule look\", \"anything I should know\", "
        "\"what's the state of things\", \"what needs my attention\". A "
        "whole-board read, ranked by what costs most. It takes no subject; a "
        "question about ONE order or ONE machine is that order's or that "
        "machine's route",
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
    # Session 4B.27 Item 6 — IT TAKES AN ORDER, and always could. The route
    # answered a whole-board census to "ord-11 is not in the frozen zone, why
    # not?" because the meaning named no subject, so the parse extracted none
    # and the assembler had nothing to be about. The vocabulary cost is paid
    # here and in the prompt version; no new intent was added, because the
    # intent was never the missing part.
    Intent.FROZEN:
        "what is frozen / committed / locked in and will not move as the plan "
        "rolls forward (rolling runs). It may be asked about ONE ORDER — \"is "
        "ORD-000142 frozen\", \"why isn't ord-11 in the frozen zone\", \"is this "
        "one committed\" — in which case NAME THAT ORDER as the subject; asked "
        "with no order it is the whole board's committed state. IT ALSO OWNS "
        "\"PINNED\" AND \"HELD\" — \"why is ORD-000142 pinned\", \"why is this "
        "bar held\", \"why can't the solver move this one\" — because on a "
        "rolling board a placement is planner-held for exactly one reason (the "
        "frozen boundary was pulled back past it, R-F1) and this route is where "
        "that answer lives. \"Pinned\" is NOT a declared field, so it is never "
        "`attribute-lookup`",
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
    # Session 4A teaching-graft (b), R-TG2. Written to SEPARATE it from
    # `coaching` and from `unmatched`, because the census says that is exactly
    # where the new member costs something: five of ten domain probes reached
    # `coaching` and four reached `unmatched`, and the two neighbours fail
    # differently. `coaching` answers a CAPABILITY question from docs/05 in
    # three lines; `unmatched` answers WELL and under the short budget.
    Intent.TEACHING:
        "the planner wants to UNDERSTAND SOMETHING, not to be told a fact off "
        "this board — \"in general, what makes a scheduling problem hard to "
        "prove optimal\", \"how do schedulers normally decide which job to run "
        "first\", \"explain what the optimality gap means\", \"what is a "
        "bottleneck machine\", \"why do setup times matter\", \"how does a "
        "rolling horizon normally work\", \"what does it mean when a schedule "
        "is infeasible\". The answer is an EXPLANATION, and it is allowed to "
        "be long. It is NOT `coaching` — that asks whether THIS PRODUCT can "
        "model something and how to declare it (\"can it handle shared "
        "operators?\", \"how do I turn on overtime?\"), which is a lookup "
        "against the constraint catalog. It is NOT `attribute-lookup` (a value "
        "on one job) and NOT `briefing` (a read of this board). A question "
        "that ALSO names an order, a machine or this plan is still this "
        "intent — name the subject too, and the answer grounds on the board "
        "before it teaches",
    Intent.TERM_EXPLANATION:
        "the planner is asking what one of OUR OWN WORDS means — a word that "
        "appeared in an answer they were just given. \"what do you mean "
        "seed\", \"what is a gap\", \"you mentioned seed 44 — what does it "
        "mean to change seeds\", \"i don't know what the ledger is\". Put the "
        "word itself in a `concept` subject, in the planner's own spelling. "
        "It is NOT `teaching` — that explains how the WORLD works and would "
        "read the same at any plant with any software; this explains a word "
        "THIS SYSTEM chose. It is NOT `coaching` — that is how to DECLARE a "
        "capability in a submission. It is NOT `prove-it`: \"what do you mean\" "
        "is this intent when the object is a WORD and `prove-it` when the "
        "object is a CLAIM (\"what do you mean it can't be moved\")",
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
