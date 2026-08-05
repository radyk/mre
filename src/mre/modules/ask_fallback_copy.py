"""Authored fallback copy for the ask surface (R-AI1(c), Session 4A.1 CU4).

All copy the AI layer shows when it CANNOT fully answer lives here, authored —
never LLM-improvised. Per R-AI1(c), intelligence accrues only in reviewable
artifacts; this file is one of them (a human edits these strings, a model never
writes them). The interpreter/explainer import these; they compose no fallback
prose of their own.

Two tiers between "routed" and "refused":
  - NEAR-MISS (CU4): moderate interpreter confidence or params that only
    partially resolve → answer honestly and offer the two nearest routes as
    one-tap / one-phrase follow-ups. No dead end.
  - CLARIFY (CU2): an elliptical follow-up that cannot be resolved against the
    conversation → ask for the missing referent, never guess.
The FULL refusal keeps the planner-language capability list (the explainer's
``_planner_routes``); this module supplies only the framing lines.
"""
from __future__ import annotations

# The lead line of a near-miss answer. `{q}` is the verbatim question.
NEAR_MISS_LEAD = 'I can\'t answer that one exactly — "{q}".'

# The line introducing the offered nearest routes.
NEAR_MISS_OFFER = "Here's what I can do that's closest:"

# Human-readable, planner-language labels for each taxonomy route, used to phrase
# the near-miss offers as concrete follow-ups. `{order}` / `{machine}` /
# `{customer}` are filled from the interpreter's partially-resolved params where
# present, else a generic noun. Keep these in planner vocabulary — never a route
# id, never an id-shape.
#
# ---------------------------------------------------------------------------
# SESSION 4B.19 — AN OFFER LABEL NAMES THE QUESTION IT WOULD ANSWER, NEVER THE
# ANSWER (docs/04 2026-07-30 ruling).
#
# A door label is composed BEFORE any read of the board has happened — the slots
# above are filled from the interpreter's partially-resolved params, and nothing
# else enters. So a label that states a board fact states it without evidence, by
# construction, in the product's own voice, at the moment a planner is deciding
# what to trust.
#
# 4B.17 measured two of these. The census that produced this rewrite found
# fourteen HERE plus one more in `explainer._planner_routes()` — and it found
# that the ENTITY SLOT IS NOT THE MECHANISM: `advice` ("explain why each order is
# late…") carries no slot and was a member all the same. What makes a label a
# defect is the ASSERTION, not the interpolation.
#
# The rewrites below keep every door's usefulness — each still tells a planner
# what asking would get them — and drop the claim. Guarded by
# `tests/test_offer_labels_do_not_assert.py`; the guard's mechanism and its
# stated limit are documented there.
#
#   was                                          | now
#   "show why {order} is late"                   | check whether … and what drove it
#   "explain why {machine} carries no work"      | check how much work … carries
#   "explain why {order} is on {machine}"        | check which machine … is on
#   "explain the gap before {order}…"            | check what sits before …
#   "explain why {order} isn't scheduled yet"    | check whether … is scheduled yet
#   "name the binding constraint on {order}…"    | check what is holding … or whether
#                                                |   nothing was  (the COULDN'T /
#                                                |   CHOSE distinction, 4B.14)
# ---------------------------------------------------------------------------
ROUTE_OFFERS = {
    "late-order": "check whether {order} is late, and what drove it",
    "late-orders": "show every late order at a glance",
    "lateness-cause": "check how much of the plan is running late, and what is "
                      "driving it",
    "why-on-machine": "check which machine {order} is on, and how that machine "
                      "was chosen",
    "machine-schedule": "show what's running on {machine}",
    "order-schedule": "show when {order} starts and finishes",
    "customer-schedule": "show the schedule for {customer}",
    "schedule": "show the full schedule, machine by machine",
    "downtime": "show {machine}'s downtime (calendar closures)",
    "data-problems": "list the data-quality problems",
    "version-diff": "show what changed between two versions",
    "remediation": "show how to fix anything the intake review flagged",
    "triage": "show what to fix first",
    "certificate-testimony": "go through what the intake review found in the "
                             "submission",
    "edit-summary": "summarize any edits made in this session and what they cost",
    "edit-cost": "break down what the most recent move cost, if one was made",
    "open-card": "read back a priced move if one is open on the board",
    "ledger-refusals": "list the questions I couldn't answer recently",
    "advice": "check what, if anything, is running late and price a what-if move",
    "coaching": "show how to enable that capability in the submission",
    "solve-time": "tell you how long the solve took",
    "machine-count": "list the machines in the plan",
    "solve-optimality": "say whether this schedule's cost is proven optimal",
    "maintenance": "show one machine's downtime (calendar closures)",
    "swap-move": "weigh swapping {order} with another order and how to price it",
    "gap-between": "check what sits before {order} on its machine, and whether "
                   "it leaves a gap",
    "machine-idle": "check how much work {machine} carries, and what it is "
                    "eligible to run",
    "order-attributes": "show {order}'s details (product, quantity, customer, due)",
    "inventory": "count the orders and operations in the plan",
    "integrity-check": "check whether anything is double-booked",
    "start-reason": "explain why {order} starts when it does",
    "why-here": "check what is holding {order} where it sits, or whether nothing "
                "was",
    "what-would-change": "say what would have to change for {order} to start "
                         "earlier, and by how much",
    "excluded-orders": "list the orders excluded from the plan and why",
    "drill-down": "open the full record behind that",
    "briefing": "show what needs your attention today",
    "contested-fact": "walk the evidence for {order}'s status",
    "confirm-take": "name the board gesture that makes that move",
    "prove-it": "open the record behind what I just told you",
    "beyond-horizon": "show what lies beyond the planning horizon",
    "why-not-scheduled-yet": "check whether {order} is scheduled yet, and when "
                             "it will be",
    "frozen": "show what is frozen",
    # Session 4B.6 — the coarse zone (R-SC2 amendment).
    "coarse-fit": "check whether the work beyond the horizon fits",
    "bucket-load": "show how loaded a week beyond the horizon is",
}

# Generic planner nouns when a param slot has nothing resolved to fill it.
GENERIC_NOUNS = {"order": "an order", "machine": "a machine", "customer": "a customer"}

# The clarify (unresolvable-ellipsis) lead. `{q}` is the verbatim follow-up.
CLARIFY_LEAD = 'I need one more detail to answer "{q}".'

# The clarify body when there is no prior subject at all to hang the follow-up on.
CLARIFY_NO_SUBJECT = (
    "Which order, machine, or customer do you mean? Ask it again naming one, "
    "e.g. \"why is that order late?\" becomes \"why is <order> late?\"."
)

# CU5 (Session 4A.2b) — the rewrite-confidence guard's clarify bodies. A
# follow-up whose referent is a SET ("10 of those", "how many of them"), or that
# asks the assistant to confirm a prior claim ("is that correct"), must NOT be
# silently rewritten into a single-order question and answered. Name the ambiguity
# and offer the well-formed question, never a guess.
CLARIFY_SET_REFERENCE = (
    "\"{pron}\" looks like it refers to a group, not one order — I won't guess "
    "which. Did you mean the flagged orders? Ask e.g. \"which orders have "
    "issues?\" or name a specific order."
)
CLARIFY_VERIFICATION = (
    "I can't confirm a previous statement as \"correct\" — I answer from the "
    "evidence, not my own claims. Re-ask what you want checked, e.g. \"how many "
    "orders have data problems?\"."
)

# Session 4A.5a (R-AI5(1)) — the remaining closed clarify reasons. The parse picks
# a REASON from the closed set; the words are always ours.
CLARIFY_AMBIGUOUS_SUBJECT = (
    "More than one thing fits and I won't pick for you. Name it — an order, a "
    "machine, or a capability — and I'll answer, e.g. \"why is <order> late?\"."
)
CLARIFY_AMBIGUOUS_INTENT = (
    "I can read that two ways and the difference matters. Say which you want: "
    "the facts as they stand, or what to do about them."
)
CLARIFY_PARSE_FAILED = (
    "I couldn't make out what that one was asking. Try it again in a sentence — "
    "naming an order, a machine, or a customer if it's about one."
)

# ---------------------------------------------------------------------------
# Session 4A.5a (R-AI5 part 1) — the two authored branches the parse layer opens.
# ---------------------------------------------------------------------------

# CONFIRMATION OF A PRIOR TAKE. The planner repeats OUR OWN suggestion back as a
# question ("so move the first operation to an earlier start time?"). That is a
# confirmation, not a new instruction — the old router read a move phrasing with no
# second order and fell to a near-miss, which reads as the assistant forgetting what
# it just said one turn ago. Name the gesture, say plainly whose move it is (M10 has
# no write path), and point at the sandbox that prices it before acceptance.
CONFIRM_TAKE_LEAD = "Yes — that's the move I was pointing at."
CONFIRM_TAKE_LEAD_ORDER = (
    "Yes — that's the move I was pointing at: pulling {order} earlier.")
CONFIRM_TAKE_BODY = (
    "I can't make it for you: I read the plan and price changes, I don't change "
    "it. You make the move on the board and I'll cost it exactly before anything "
    "is accepted."
)
CONFIRM_TAKE_GESTURE = (
    "Drag {order}'s first operation to the earlier slot on {machine} — the "
    "sandbox re-solves around it and shows the production, setup, and tardiness "
    "delta, and nothing is committed until you accept."
)
CONFIRM_TAKE_GESTURE_GENERIC = (
    "Drag the operation to the slot you want on the board — the sandbox re-solves "
    "around it and shows the production, setup, and tardiness delta, and nothing "
    "is committed until you accept."
)

# ---------------------------------------------------------------------------
# THE REPEAT RIDERS (Session 4B.5 CU5b/c). An answer delivered word-for-word
# twice in a row reads as not having heard the second question. These vary the
# LEAD — never the facts, which are the same facts and must stay so.
#
# Authored variants, indexed by how many of the last two turns this route already
# answered, so a third ask does not get the second ask's line either.
# ---------------------------------------------------------------------------

REPEAT_LEADS = (
    "Same answer as a moment ago —",
    # Session 4B.15 Item 4: the second variant used to read "Still the same;
    # nothing has changed since you asked", which is the product telling the
    # planner off for its own deafness. It now only ever fires on a genuine
    # re-ask of the SAME question, and even there it does not scold.
    "Same answer — nothing in the plan has moved since you asked —",
)

# ---------------------------------------------------------------------------
# THE DEAFNESS RIDER (Session 4B.15 Item 4) — THE REVERSAL.
#
# Measured, the repeat detector fired four times with ZERO true positives: on a
# DIFFERENT question, on an EXPLICIT CORRECTION ("no, I mean for ORD-000013
# specifically"), on a factual lookup, and on the demo opener. In every case
# several DIFFERENT questions had collapsed onto one route.
#
# That is evidence about the ASSISTANT, not about the planner. When distinct
# questions keep producing one answer the correct inference is "I am not
# understanding you" — so this copy expresses doubt and offers to narrow, and
# it never rebukes. There is no variant of it that blames the planner, by
# design: the escalating second line is what made the original defect sting.
# ---------------------------------------------------------------------------

DEAF_LEAD = (
    "I've now given you this same answer for two different questions, which "
    "probably means I'm not understanding what you're asking."
)
DEAF_PRIOR = 'Last time you asked: "{prior}".'
DEAF_OFFER = (
    "If you're after a specific field on a specific job — whether an operation "
    "is splittable, how long it takes, its due date, which machines can run it "
    "— name the order and the field and I'll read it straight off the record."
)

# CU5(c): a COUNT answered in the previous turn does not want its recitation
# again. It wants the number, and an offer.
REPEAT_COUNT_WITH_LIST = "{count} — want the list?"
REPEAT_COUNT_BARE = "{count}, same as before."

# ---------------------------------------------------------------------------
# WHY-ON-MACHINE, CAPACITY-FORCED (Session 4B.5 CU3a). The founder's specimen:
# "why is ORD-000008 on PAINT-02?" -> "because the machine was busy with other
# work". That clause is `DRIVER_PHRASING["CAPACITY_BLOCKED"]` verbatim — authored
# copy, correctly carried, and useless here: it names no machine, no alternative
# and no quantity, and the machine it refers to is one the order is NOT on. A
# capacity-forced placement has a concrete story in the solved occupancy; these
# lines tell it, or say plainly that the occupancy does not carry one.
# ---------------------------------------------------------------------------

WHY_MACHINE_CAPACITY_LEAD = (
    "{order} is on {machine} because the machines that could have run it "
    "instead were occupied when it needed to run."
)
WHY_MACHINE_CAPACITY_ROW = "  {machine} was running {blocker} until {until}."
# Eligible alternatives exist, but the occupancy does not show any of them
# blocked over this step's window. An unattributable cause is NAMED as
# unattributable — never given an invented mechanism (the RUBRIC's own rule).
WHY_MACHINE_CAPACITY_UNATTRIBUTED = (
    "  I can see the placement was capacity-forced, but the solved occupancy "
    "doesn't show which alternative was blocked — so I won't name one."
)
# No eligible alternative at all: a CAPABILITY fact, not a capacity one, and
# worth saying because no rearrangement of the plan would have changed it.
WHY_MACHINE_CAPACITY_ONLY_OPTION = (
    "  In fact it is the only machine that can run this step, so nothing about "
    "the rest of the plan would have changed where it went."
)
# Session 4B.13 Item 1 — THE ONLY-OPTION CASE NEEDS ITS OWN LEAD, because the
# capacity lead above is FALSE here. Asked "why is ORD-000012 on PAINT-01" the
# answer read: "because the machines that could have run it instead were
# occupied when it needed to run. In fact it is the only machine that can run
# this step" — two sentences that cannot both be true, the first asserting
# occupied alternatives the second says do not exist. The driver code really is
# CAPACITY_BLOCKED, so the lead fired; but when eligibility resolves to a single
# machine the honest cause is CAPABILITY, and this file's own comment above
# already said so. The step's requirement is an explicit set of one — that is
# the whole story, and it is a better answer than the contradiction it replaces.
WHY_MACHINE_CAPABILITY_LEAD = (
    "{order} is on {machine} because that is the only machine qualified to run "
    "this step — there was no alternative to weigh."
)

# ---------------------------------------------------------------------------
# THE OPEN DELTA CARD (Session 4B.5 CU2). The planner has a priced move on
# screen and asks about IT. Every figure below comes off the sandbox result the
# card is already showing — this route re-derives nothing, so the answer can
# never disagree with the card the planner is looking at. That is the whole
# point: two surfaces, one set of numbers.
# ---------------------------------------------------------------------------

OPEN_CARD_LEAD = "The move you have open:"
OPEN_CARD_PLACEMENT = "{order} lands on {machine}{when}."
OPEN_CARD_PLACEMENT_BARE = "The dropped operation lands on {machine}{when}."
# The CU1 split, voiced. The card shows two rows; the sentence says which is
# which, because "your move" is the only part the planner can act on.
OPEN_CARD_SPLIT = (
    "It prices at {total} in total, and that total is two different things: "
    "{reopt} is the window re-optimizing under a fresh budget — the solver would "
    "have found that with or without you — and {move} is what your move itself "
    "adds."
)
OPEN_CARD_UNSPLIT = (
    "It prices at {total} in total. I couldn't separate out what your move "
    "itself added, so that figure still includes window re-optimization the "
    "solver would have found anyway."
)
OPEN_CARD_NO_PRICE = (
    "I don't have a dollar figure for it — the card shows the placement and its "
    "consequences, not a priced delta."
)
OPEN_CARD_AFFECTED_LEAD = "Orders it touches ({n}):"
OPEN_CARD_AFFECTED_ROW = "  {order} — {effect}"
# Session 4B.27 Item 2 — the read-back names the SAME two quantities the card
# does, in the same words. These three sentences report NET PLAN TARDINESS
# (clamped across every demand); the per-order rows above them report a signed
# FINISH SHIFT. Wording them alike is what made the pair read as a
# contradiction on a card where both were true.
OPEN_CARD_AFFECTED_NONE = "No order's finish or tardiness changes because of it."
OPEN_CARD_LATENESS_WORSE = (
    "Across every order it adds {hours}h of plan tardiness.")
OPEN_CARD_LATENESS_BETTER = (
    "Across every order it recovers {hours}h of plan tardiness.")
OPEN_CARD_LATENESS_NONE = (
    "Plan tardiness is unchanged across every order — an order can still shift "
    "inside its slack without adding any.")
OPEN_CARD_CONSEQUENCES = "{n} other operation(s) shift to make room."
OPEN_CARD_CONSEQUENCES_NONE = "Nothing else has to move."
OPEN_CARD_COMMITTED_SAFE = "No committed work changes."
OPEN_CARD_DRIVER = "Why it lands there: {phrase}"
OPEN_CARD_INFEASIBLE = (
    "That placement was refused — {message} Nothing was changed."
)
# The floor: the parse named the card, the card is gone. Never a re-derivation
# from a stale copy, and never a guess at which move they meant.
OPEN_CARD_CLOSED = (
    "There's no priced move open on the board right now, so I have nothing to "
    "read back. Make the move again and I'll answer from the card it prices."
)
# The standing boundary, carried on every card answer: what is on screen is a
# proposal, not the plan (M10 has no write path; the sandbox mints nothing).
OPEN_CARD_BOUNDARY = (
    "Nothing here is committed — this is the sandbox's price for the move, and "
    "the plan of record is unchanged until you accept it."
)

# EXPEDITE AN ALREADY-EARLY ORDER. The founder's round-four thread: four turns
# asking how to get an order done faster, on an order finishing 11.3 days ahead of
# its due date. A plan-wide lateness scope answers a question nobody asked; the
# truthful answer is that there is nothing to expedite, and what the floor is.
ADVICE_EXPEDITE_EARLY = (
    "{order} isn't waiting on anything I can shorten — it already finishes "
    "{days} day(s) ahead of its due date.")
ADVICE_EXPEDITE_FLOOR_RELEASE = (
    "The only thing that would let it run earlier is its release date "
    "({release}) — material can't be worked before it's available.")
ADVICE_EXPEDITE_FLOOR_GENERIC = (
    "The only thing that would let it run earlier is its release date — material "
    "can't be worked before it's available.")


# ---------------------------------------------------------------------------
# Session 4A.5b (R-AI5(2)/(3)/(4)) — the LABELED SYNTHESIS surface.
#
# The second tier's copy. The CLAIMS themselves are the synthesis model's sentences
# (verified claim by claim before they render); everything that FRAMES them —the
# provenance markers, the honesty notes, the couldn't-answer floor — is authored
# here, exactly like every other fallback string. A model never writes these.
# ---------------------------------------------------------------------------

# The per-claim provenance markers (R-AI5(4): provenance visible PER CLAIM). A
# verified claim carries a citation exactly like testimony; an interpretive claim
# carries the `synthesis` register tag and the records it was read from. The
# STRUCTURE is the contract; the visual treatment is tokens the founder tunes.
SYNTHESIS_CITE = "[record: {rid}...]"
SYNTHESIS_MARK = "[synthesis — read from: {rids}]"
SYNTHESIS_MARK_NO_RECORDS = "[synthesis — my reading, no record states this]"

# R-TG1 (Session 4A teaching-graft a) — THE GENERAL-KNOWLEDGE MARKER.
#
# It must name BOTH halves, and the second half is the one that was missing. Every
# other marker on this surface implies board grounding: `read from: <ids>` says the
# sentence came out of these records, and even `my reading, no record states this`
# says it is a reading OF THIS PLAN. A sentence about how scheduling works in
# general wore one of those, and it was the honest-looking label that made it
# unquestionable.
SYNTHESIS_MARK_GENERAL = (
    "[general knowledge — how scheduling works in general, not a fact about "
    "this plan]")

# Said ONCE per answer, after the claims, when any line carried that marker. The
# per-line label is the contract; this is the reader's orientation, so it states
# the consequence rather than repeating the label: a general line is not something
# to check against the board, because there is nothing on the board to check it
# against.
SYNTHESIS_GENERAL_NOTE = (
    "Where a line is marked general knowledge it draws on how scheduling and "
    "plants behave generally — not on this plan's records, so there is nothing "
    "here to check it against.")

# Named when a quantifying claim rests on a sample rather than an enumerated set.
SYNTHESIS_SAMPLE_NOTE = "based on the {n} row(s) {tool} returned, not the whole plan"

# The lead line of a synthesis answer: name the tier plainly, once, before the
# claims. The planner should never have to guess which tier answered them.
SYNTHESIS_LEAD = (
    "No contracted answer covers that one, so this is me reading the evidence "
    "directly — each line below says what backs it.")

# A load-bearing claim was cut because it could not be grounded. Say so; never
# quietly ship the remainder as though the reasoning were whole.
#
# Deliberately CONTENTLESS about the cut claim. The first bench run repeated the
# offending figure back inside the apology ("...contradicted: 250 minutes"), which
# puts an unproven number in front of the planner in the very sentence explaining
# that it could not be proven. What was cut is in the ledger, where a developer
# reads it; the planner gets the honest fact that something was.
SYNTHESIS_UNGROUNDED = (
    "One step of my reasoning didn't hold up against the records, so I couldn't "
    "ground part of it and I've left that step out rather than state it.")

# R-TG1. THE OTHER REASON A STEP GETS CUT, AND IT IS NOT A GROUNDING FAILURE.
#
# Enforcement direction (ii) drops a sentence that cites nothing, checks against
# nothing and is not about this board — and the line above is FALSE of it, in its
# first clause: the reasoning did not fail against the records, it never reached
# them. Measured live on the demo board within this session: the tier's own honest
# limit statement — "whether a large gap here reflects a genuinely weak schedule
# versus a loose bound is something I cannot check against this run" — was cut by
# (ii) and then reported as reasoning that did not hold up. A sentence about our
# own epistemic position is neither a board claim nor domain knowledge, and the
# taxonomy has no third home for it; that gap is REPORTED rather than papered
# over, and this line is what stops the gap being described dishonestly.
SYNTHESIS_UNPLACEABLE = (
    "Part of what I drafted was neither something I could check against your "
    "board nor general scheduling knowledge, so I left it out rather than state "
    "it with a label that would have been wrong either way.")

# R-TG6. THE THIRD REASON A STEP GETS CUT, AND IT IS THE STRONGEST OF THE THREE.
#
# The two lines above both say, in different words, "I could not establish this".
# This one says the opposite: the step WAS established, and it was established
# FALSE. A general rule about how this product works, refuted by the product's
# own deterministic floor — the founding specimen being "a job becomes immovable
# only through a lock", against a mobility floor that computes BOXED_IN for
# operations carrying no lock at all.
#
# "Didn't hold up against the records" is wrong here for the same reason it was
# wrong for an unplaceable sentence, and wrong in the OTHER direction: this did
# not fail to reach the records, it collided with something we compute. Saying
# so plainly matters more than either sibling, because this is the one cut where
# the planner was about to be told something untrue about the tool they are
# holding — the C9 founder round's whole finding is that a confident reader
# carried exactly such a rule out of the room.
SYNTHESIS_FLOOR_REFUTED = (
    "I drafted a general rule about how this product decides what can move, and "
    "it contradicted what this product actually computes — so I cut it. Ask me "
    "about a specific bar and I'll show you the verdict itself rather than a "
    "rule of thumb about it.")

# R-TG7 — AN EMPTY TEACHING DROP HAS A FLOOR (Session 4A teaching-graft (e2),
# docs/04 2026-08-05).
#
# The line above renders BESIDE surviving claims. Session (e) measured, live, the
# case where none survive: a teaching answer whose every claim the seam cut, and
# the answer then falls to the capability card — "I couldn't answer that one from
# the evidence. I read what I could and none of it grounds an answer I'd stand
# behind". Honest, and useless, and worse than useless in one exact way: THE
# COLLAPSE DELETES THE ONE THING THE PLANNER WAS OWED. A rule was drafted and
# refused because this product can show it wrong; the capability card says
# instead that nothing was found, which is a different fact and a false one here.
#
# THREE THINGS, AND NO MORE. (1) A draft existed and was REFUSED, and refused for
# contradicting what this product computes. (2) The per-bar door — the Lyon rule,
# a rejection holding a door handle: the rule of thumb was standing in for a
# verdict, and the verdict is the part that is actually checkable. (3) NOTHING
# ABOUT THE PLANT. This card is a statement about our own read, and the one thing
# it may never do is manufacture a claim about the plant out of the fact that we
# refused one.
#
# The wording says "including" rather than a count, and that is load-bearing: the
# card renders when ANY cut in the set is a floor refutation — the same
# precedence R-TG6 already gave the mixed-answer line, because two precedence
# rules for one fact is how the two drift apart — so a sentence saying "all of
# them" would be false on a mixed set and a sentence carrying a count would need
# to say which count it meant.
SYNTHESIS_FLOOR_REFUTED_EMPTY = (
    "I drafted an answer to that and cut every line of it — including a general "
    "rule about how this product decides what can move, which contradicted what "
    "this product actually computes. I'd rather leave the question open than "
    "teach you a rule I can show you is wrong.")
SYNTHESIS_FLOOR_REFUTED_EMPTY_DOOR = (
    "Name a bar — an order and an operation — and I'll show you the mobility "
    "verdict this run computed for it. That is what the rule of thumb was "
    "standing in for, and unlike the rule it is something you can check.")

# The budget ran out before the read was complete (CU1: an honest partial, never a
# stall). `{tools}` names what was consulted.
SYNTHESIS_PARTIAL = (
    "I stopped there — that is as far as this question's evidence budget goes. I "
    "consulted: {tools}.")

# ---------------------------------------------------------------------------
# R-TG3 — THE CLOSER (Session 4A teaching-graft (b)). The depth licence's
# honest half.
#
# The SHORT budget cuts an answer to the four claims that lead it. Brevity that
# silently discards substance is not brevity, it is loss — so the one thing the
# planner is never allowed to be left not knowing is that there WAS more.
#
# It names the COUNT, because "there's more" without a number is a sentence a
# planner cannot act on: two further points is a shrug and five is a second
# answer. And it is rendered IF AND ONLY IF something was actually withheld — a
# closer on an uncut answer tells a planner there is more when there is not,
# which is a false disclosure and is asserted against by its own guard.
#
# It does NOT say the points were unimportant, and it does not say they were
# less true. Every deferred claim passed the same verification the printed ones
# did; what it lost was a place in the first four.
SYNTHESIS_DEFERRED_ONE = (
    "I've kept this short — there is 1 more point behind it. Ask and I'll walk "
    "through the rest.")
SYNTHESIS_DEFERRED = (
    "I've kept this short — there are {n} more points behind it. Ask and I'll "
    "walk through the rest.")

# R-TG3 — THE LONG BUDGET'S OWN CLOSING LINE, on `teaching` answers only.
#
# R-AI3: an invitation completes the thought. A taught answer's thought is not
# complete at the last sentence, because the planner has a plant and I do not:
# domain knowledge is general BY DESIGN (R-TG1) and the person reading it is the
# one who knows whether it holds here. So the invitation is to PUSH BACK, not
# the generic "ask me more" — it names the asymmetry that makes it worth saying.
#
# It rides on the LONG licence rather than on the presence of a general claim,
# because a teaching question answered entirely from the board still asked to be
# taught, and the standing to disagree is the same either way.
TEACHING_INVITATION = (
    "That is how it works in general — you know this plant and I don't, so if "
    "any of it doesn't match what you see here, say so and I'll look at what "
    "your board actually does.")

# ---------------------------------------------------------------------------
# R-TG4 — AUDIENCE SHAPE (Session 4A teaching-graft (b)). The lead a goal
# question earns, and the offer that replaces the inventory.
#
# THE DISCLOSURE FIRST. The floor read the planner's words to decide this
# question names a person, and 4A.x's ruling is that every resolution the
# system made is disclosed — so the answer says what it heard rather than
# quietly serving a different shape.
AUDIENCE_LEAD = (
    "You asked what to say to {audience}. Here is the one-sentence version, and "
    "the one thing that would move it most.")

# (1) THE ACCOUNT — the sentence a person could say out loud. Composed from the
# route's own assembled figures; nothing here is computed a second time.
AUDIENCE_ACCOUNT_LATENESS = (
    "{late} of the {total} orders scheduled in this window finish after their "
    "due date.")
AUDIENCE_ACCOUNT_LATENESS_CAUSE = (
    "For {n} of them the recorded driver is the same one: {cause}.")

# (2) THE LEVER — promoted from afterthought to headline, and LABELLED, because
# "the biggest lever" is a ranking claim and R-AI3 requires a ranking to say
# what it ranked on. It ranks on MONEY, which is the axis the audience in the
# question is asking about.
AUDIENCE_LEVER_HEADER = "The single biggest lever this board evidences:"
AUDIENCE_LEVER_WORST = (
    "{order} carries the largest tardiness cost on the board at {cost} — more "
    "than any other single order.")
AUDIENCE_LEVER_HOLD = (
    "It was held on {machine} until {until} by {blocker}; that is the specific "
    "hold to attack if you want this number down.")

# (3) THE OFFER — the inventory offered, NEVER delivered. The records are still
# assembled and still cited on the bundle, so this is one gesture away and not
# gone: `ordered_records` is untouched and the drill-down opens exactly these.
AUDIENCE_OFFER_LATENESS = (
    "The order-by-order breakdown is behind this — {n} orders with a concrete "
    "hold recorded, plus the full evidence chain. Ask for it and I'll lay it "
    "out.")
AUDIENCE_OFFER_GENERIC = (
    "The detail behind this is available — ask for the full breakdown.")

# The floor: nothing survived, or the model could not answer from the evidence.
#
# Session 4B.27 Item 9 — A PROCESS CLAIM IS A CLAIM, AND IT IS GATED ON THE
# PROCESS. "I read what I could" asserts that a read happened. At ZERO tool
# calls none did, and the sentence shipped anyway: the honesty register stating
# a false fact about itself, which is worse than a wrong number because it is
# the sentence a planner uses to calibrate how much to trust the rest.
#
# The tell was already on the page. `SYNTHESIS_UNANSWERABLE_CONSULTED` right
# below has ALWAYS been gated on `consulted_tools` being non-empty, so the code
# has always KNOWN whether anything was read — the lead sentence simply never
# asked. Two sentences, one fact, one of them checking it.
#
# The zero-tool wording claims nothing about effort. It names the shape of the
# gap ("no tool of mine reaches that"), which is the actionable half, and it is
# deliberately NOT an apology for being lazy — the tier genuinely has no tool
# for a question about the cockpit's own colours, and saying so is correct.
SYNTHESIS_UNANSWERABLE = (
    "I couldn't answer that one from the evidence. I read what I could and none of "
    "it grounds an answer I'd stand behind, so I'd rather say so than guess.")
SYNTHESIS_UNANSWERABLE_NO_TOOLS = (
    "I couldn't answer that one: I don't have a tool that reaches it. Nothing I "
    "can read holds that, so I'd rather say so than guess.")
SYNTHESIS_UNANSWERABLE_CONSULTED = "I looked at: {tools}."

# Errand 4B.15a, rider — THE ZERO-TOOL-CALL FLOOR.
#
# 4B.15's tier bench produced exactly one fabricated answer: Opus, asked which
# machine carried the most work, named three machines that DO NOT EXIST in this
# plant and made ZERO tool calls to get them. Claim verification labelled every
# sentence unsupported and the answer SHIPPED ANYWAY, because the tier's contract
# is to label what it grounds, not to withhold what it cannot.
#
# An answer that read nothing and still names this plant's orders, machines,
# dates or money did not reason from evidence — it recalled a plausible shape. So
# it does not ship. Deliberately CONTENTLESS about what was withheld, for the
# same reason SYNTHESIS_UNGROUNDED is: repeating the invented machine names
# inside the apology puts them in front of the planner anyway.
SYNTHESIS_UNREAD = (
    "I drafted an answer to that without reading anything from this schedule — no "
    "evidence tool ran — so every name and figure in it would have been mine "
    "rather than the plan's, and I've held it back. Ask me again and I'll go to "
    "the records, or name one order or machine and I'll pull them directly.")

# Session 4A.5c CU3(b) — THE WARM FLOOR. RUBRIC precedent entry 6, ruled: the
# couldn't-answer keeps the nearest-capabilities offers.
#
# 4A.5b's sweep found the cost of not having them. "this is not helpful" used to
# reach the near-miss bridge and got two concrete doors; once the second tier took
# it, the same turn got an honest refusal and NOTHING to do next. Honest, and
# colder — and the two are not in tension. This is the same authored offer surface
# the bridge uses, appended to the floor, not a second authored body: the floor
# says what it could not do, and this says what it can.
SYNTHESIS_FLOOR_DOORS = "Here's what I can do that's closest:"

# ---------------------------------------------------------------------------
# MICRO-SESSION 4A — THE OUTAGE FLOOR. TWO FLOORS, AND AN OUTAGE MAY NEVER WEAR
# THE CAPABILITY CARD (docs/04, 2026-08-03).
#
# THE SPECIMEN, measured live with a credit-exhausted key: every question —
# "find order and highlight 126", "why cant ORD-000126 op30 start earlier",
# "why cant this be moved" — returned the identical capability card,
#
#     "I couldn't answer that one: I don't have a tool that reaches it.
#      Nothing I can read holds that, so I'd rather say so than guess.
#      Here's what I can do that's closest: …"
#     [rendered by: synthesis — 0 tool call(s)]
#
# and every clause of it is false in that failure mode. The tools are there. The
# evidence is there. What was missing was the language model, so the question
# was never read — and the product answered a question about ITS OWN REACH with
# a sentence about the PLANT's evidence. A planner reads that as "this product
# cannot do this"; the founder read it as grounds to abandon the AI layer. That
# is the price of the lie, and it is why the two floors are separate copy.
#
# THREE RULES the wording follows:
#
#   1. NAME THE MECHANISM. "outage on my side" / "not configured", never a
#      transport string and never a status code — 4B.23 §5a.91's register rule.
#   2. NO DOORS. `SYNTHESIS_FLOOR_DOORS` offers what we could do INSTEAD, which
#      presupposes the question was understood well enough to find a neighbour
#      for. Nothing was read. Offering alternatives here would be a second
#      capability claim in the card built to stop making one.
#   3. SAY WHAT STILL WORKS. The board, the schedule, the cards and every
#      gesture are untouched by an ask-layer outage, and a planner who has just
#      been told the assistant is down needs to know the plan is not.
# ---------------------------------------------------------------------------

#: The parse layer could not be reached: the question was never read at all.
OUTAGE_PARSE_LEAD = (
    "I can't reach my language model right now, so I couldn't read your "
    "question at all. This is an outage on my side, not a limit of what I can "
    "answer.")

#: No model is configured for this deployment — the same silence, a different
#: cause, and "try again in a moment" would be false, so it is not said.
OUTAGE_UNCONFIGURED_LEAD = (
    "I have no language model available on this deployment, so I couldn't read "
    "your question at all. That is a setup gap on my side, not a limit of what "
    "I can answer.")

#: The parse succeeded and the reasoning tier could not be reached. The question
#: WAS read, so the card does not claim otherwise.
OUTAGE_SYNTHESIS_LEAD = (
    "I read your question, but no contracted answer covers it and I couldn't "
    "reach my language model to reason it out. This is an outage on my side, "
    "not a limit of what I can answer.")

OUTAGE_BOARD_STILL_WORKS = (
    "The board, the schedule and everything you can click still work — nothing "
    "about the plan depends on me being able to talk.")

OUTAGE_RETRY = "Try me again in a moment."

#: Keyed by the stage that could not reach a model. `unconfigured` gets no retry
#: line: there is nothing to wait for.
OUTAGE_LEADS = {
    "parse": OUTAGE_PARSE_LEAD,
    "synthesis": OUTAGE_SYNTHESIS_LEAD,
    "unconfigured": OUTAGE_UNCONFIGURED_LEAD,
}

# ---------------------------------------------------------------------------
# Session 4A.5c CU3(a) — THE FIRST BEAT of the two-phase ask.
#
# Rider (c) of 4A.5b measured the thing this copy exists for: a contracted answer
# lands in ~1.3s, a reasoned one in ~10s. A planner will wait ten seconds for a
# reasoned answer — but not silently, and not without knowing which they are
# getting. So the ask two-phases: the preflight says which TIER will answer, the
# panel shows this line the moment it is synthesis, and the answer replaces it.
#
# THE TWO-BEAT PATTERN (R-T2), applied: beat one is an HONEST NON-ANSWER. It says
# what is happening and commits to nothing about what will be found. It must never
# be a fake answer, a progress bar with an invented percentage, or a promise the
# second beat might not keep.
# ---------------------------------------------------------------------------

WAITING_SYNTHESIS = (
    "Reading the evidence — no contracted answer covers that one, so I'm working "
    "it out from the records (up to {budget} reads).")
WAITING_SYNTHESIS_DIVERTED = (
    "Reading the evidence — I can answer close to that, but not \"{qualifier}\", "
    "so I'm working it out from the records (up to {budget} reads).")
# A contracted answer needs no waiting state: it lands before one could be read.
WAITING_ROUTE = ""

# ---------------------------------------------------------------------------
# Session 4A.5c CU3(c) rider — THE SCOPE NOTE the diverted question carries.
#
# The arc-close sweep found the guard's own failure mode. "how many orders will be
# late NEXT MONTH" diverted correctly, and the second tier then answered "One order
# will be late next month: ORD-05 ... past its due date of 2026-01-05" — playing the
# qualifier back as though the evidence covered it. 2026-01-05 is not next month.
# The figure grounded, so the claim VERIFIED; what was wrong was the SCOPE, which
# claim verification does not check because no record contradicts a frame.
#
# Diverting was right and answering as though the frame held was not. So the tier is
# TOLD what the qualifier was and what the evidence actually covers, and told to say
# so rather than play along. Authored here (a reviewable artifact); rendered into the
# CONTEXT block both governed prompts share.
# ---------------------------------------------------------------------------
SYNTHESIS_SCOPE_NOTE = (
    "  SCOPE THE PLANNER ASKED FOR, WHICH NO ROUTE COVERS: \"{qualifier}\".\n"
    "  The evidence you can read is THIS SOLVED PLAN and nothing else — it does\n"
    "  not extend past the schedule's own horizon, to another plan, or to a\n"
    "  scope the records do not carry. If that qualifier is outside what the\n"
    "  evidence covers, SAY SO plainly and answer what the plan DOES show,\n"
    "  labelled as such. Never restate the qualifier as though the records\n"
    "  supported it.")

# "PROVE IT" (R-AI5(4)) — the planner contests or probes one claim and the grounding
# pass re-runs on it, conversationally.
#: Session 4B.22 — REWRITTEN, because after the drill-down ruling this branch is
#: reachable only when there is NO prior answer at all, and the old second
#: sentence ("the records behind it are cited on it") then described a turn that
#: does not exist. Worse, it was the exact sentence a planner got after a CLARIFY,
#: which cites nothing: the copy sent them to look for citations that were not
#: there.
PROVE_IT_NO_TARGET = (
    "I haven't answered anything yet in this conversation, so there's nothing of "
    "mine to open. Ask me something first and then say \"show me the evidence for "
    "that\" — I'll walk what the answer was built from.")
#: The prior answer was a CONTRACTED route. It carries records but no per-sentence
#: claims, and the copy says so rather than implying a decomposition it never had.
PROVE_IT_PRIOR_LEAD = (
    "That was my answer to \"{question}\". It came from a contracted route, so it "
    "has no per-sentence claims to pick apart — here is the whole record set it "
    "was assembled from ({count}):")
#: The prior answer was AUTHORED COPY. Saying so is the answer. This is the
#: honest-negative case and it is NOT the same fact as having nothing open.
PROVE_IT_PRIOR_NO_RECORDS = (
    "My answer to \"{question}\" was authored copy — it states what this product "
    "can and can't do, not a fact read off a record — so there is nothing behind "
    "it to open. Ask me something about the plan itself and the answer will cite "
    "what it was built from.")
#: Session 4A teaching-graft (d.1), D-06 — THE FIFTH CASE, AND THE COPY ABOVE WAS
#: FALSE OF IT. A CONTRACTED route can answer with no record set: because its read
#: of the plan came back empty (the pinned exam board has nothing late, so
#: `late-orders` is a true answer citing nothing), or because it composes its body
#: from pre-computed facts. Measured in (d.0) — `zero-record-control.json`, one
#: board, two turns — a real testimony answer was described back to the planner as
#: "authored copy — it states what this product can and can't do".
#:
#: So the split is by the ROUTE THAT ANSWERED, never by the record count, and the
#: sentence claims only what is checkable on the record: which route, that it
#: reads the plan, and that it attached nothing to open. It deliberately does NOT
#: say "the read found nothing" — that is a claim about the board this branch
#: cannot tell from a route that simply carries no citations.
PROVE_IT_PRIOR_EMPTY_READ = (
    "My answer to \"{question}\" came from {route}, which answers from this plan "
    "— but it attached no records of its own, so there is nothing here for me to "
    "open. That is a different thing from it being a statement about what this "
    "product can do: it read the board and cited nothing. Ask about a particular "
    "order or machine and the answer will cite what it was built from.")
#: R-MT1 clause 3 (Session 4A teaching-graft (d.1)) — THE BOARD CHANGED UNDER THE
#: CONVERSATION. A carried answer exists for this session and it is about a
#: DIFFERENT schedule: an accept, a boundary move or a publish rebound the cockpit
#: between the two turns. Clause 1 makes that answer unreadable here by
#: construction; this is what gets SAID instead, and it is deliberately not the
#: no-prior-answer floor above — "I have never answered you" and "what you are
#: pointing at was about the plan you were looking at a moment ago" are different
#: facts, and only one of them tells a planner what happened.
PROVE_IT_PRIOR_OTHER_VERSION = (
    "The answer you're pointing at was about the PREVIOUS VERSION of this plan — "
    "the board was replaced between that turn and this one, so its records "
    "describe a schedule you are no longer looking at and I won't open them "
    "against this one. Ask it again here and I'll ground the answer on this "
    "version.")
# Session 4B.22 Item B1 — HOW BUSY ONE MACHINE IS, on the route that lists what it
# runs. Three clauses, and each is there for a reason a prior session paid for:
#   the FIGURE names the quantity      — working time, not elapsed span (4B.20)
#   the DENOMINATOR is on the surface  — open calendar minutes over the SAME
#                                        interval the working time is measured
#                                        across, so the percentage is checkable
#   the JUDGMENT IS DECLINED           — "overloaded" is a business threshold and
#                                        no plant here declares one. Inventing it
#                                        silently is the defect class R-PD1
#                                        clause (5) and the coarse derate are
#                                        both left open for.
MACHINE_LOAD_LINE = (
    "Load: {working} working minute(s) against {open} minute(s) of open calendar "
    "between its first placement ({first}) and its last ({last}) — {pct}% of the "
    "open time in that stretch.")
MACHINE_LOAD_NO_CALENDAR = (
    "Load: {working} working minute(s) across {spans} placement(s), from {first} "
    "to {last}. I can't state that as a percentage: this machine's calendar did "
    "not read, so I have no open-capacity figure to divide by.")
MACHINE_LOAD_NO_JUDGMENT = (
    "Whether that counts as overloaded is not mine to say — no utilisation "
    "threshold is declared for this plant, so the figure is stated, not judged.")

PROVE_IT_VERIFIED = "That one is on the record. Here is what it rests on:"
PROVE_IT_INTERPRETIVE = (
    "That part is my inference, not a record — here is each thing I read to get "
    "there:")
PROVE_IT_INTERPRETIVE_BARE = (
    "That part is my reading of the plan, and no single record states it. I have "
    "nothing further to show behind it.")
# R-TG1. A general-knowledge line drilled into. `PROVE_IT_INTERPRETIVE_BARE` is
# FALSE of it in its first clause — it is not a reading of the plan, it is not
# about the plan — and answering a "prove it" with a false account of what the
# sentence was would reopen, at the drill-down, exactly the confusion the marker
# closes at the line.
PROVE_IT_GENERAL = (
    "That line wasn't about this plan — it's general scheduling knowledge, so "
    "there is no record of yours behind it and nothing here to check it against. "
    "If you want the same question answered from this board, say so and I'll "
    "read it.")
PROVE_IT_RECORD_LINE = "  - {summary}  [record: {rid}...]"
# Session 4B.5 CU5(d): WHICH READINGS this one sentence came out of — per claim,
# derived from the toolbox's own per-call record sets, never a copy of the
# answer's whole tool list. "Read from" in the sense a planner means it: not which
# record ids, but which readings of the plan.
PROVE_IT_READ_FROM = "Read from: {tools}."


# ---------------------------------------------------------------------------
# Session 4A.5c (R-AI5(7)) — THE PROMOTED ROUTE's authored copy.
#
# `lateness-cause` is the one shape this session promoted out of synthesis
# residue, on the authority of docs/promotions/aggregate-lateness-2026-07-26.md.
# The dossier's draft deliberately generated NO copy: planner-facing wording is
# authored by a human (R-AI1(c)), and a promotion pipeline that wrote its own
# answer prose would put model sentences on the answer surface through the back
# door — the one thing the whole tier exists to prevent. These are that copy.
# ---------------------------------------------------------------------------

# THE PREMISE CHECK LEADS. Asked "why are so many orders late" of a plan with one
# late order, the honest answer says so first. The synthesis tier did exactly this
# before the promotion, and it was the most useful sentence in the answer; a
# contracted route that skipped to causes would be a worse answer than the one it
# replaced.
LATENESS_CAUSE_NONE = (
    "Nothing is late in this plan — every order finishes on or before its due "
    "date, so there is no lateness to account for.")
# Session 4B.21 — both of these carry a DENOMINATOR, and it is the SCHEDULED
# set. "The other 39 finish on time or early" was asserted on a board where 14
# of those 39 have no completion date at all.
LATENESS_CAUSE_PREMISE_ONE = (
    "There aren't many — exactly one order is late: {order}, by {amount}. "
    "The other {on_time} scheduled order(s) finish on time or early.")
LATENESS_CAUSE_LEAD = (
    "{late} of the {total} scheduled order(s) are late. Here is what is "
    "driving it.")
LATENESS_CAUSE_LEAD_NO_TOTAL = "{late} orders are late. Here is what is driving it."

# One line per repeated cause — the MIX is the answer, not the list. With ONE late
# order there is no mix to speak of, and "What they have in common:" over a single
# name reads as a template that did not notice (C4). Same facts, correct grammar.
LATENESS_CAUSE_MIX_HEADER = "What they have in common:"
LATENESS_CAUSE_MIX_HEADER_ONE = "What put it there:"
LATENESS_CAUSE_MIX_LINE = "  - {cause}: {orders}"
LATENESS_CAUSE_MIX_LINE_ONE = "  - {cause}"
LATENESS_CAUSE_BLOCKER = (
    "  - {order} was held on {machine} until {until} by {blocker}, and started "
    "at {start}.")
# Where the solved occupancy shows no preceding job, say so rather than reach for
# a cause. An unattributed order is a fact; an invented mechanism is a defect.
LATENESS_CAUSE_UNATTRIBUTED = (
    "I can't attribute {orders} to a specific hold — nothing directly precedes "
    "the first operation on its machine, so the cause is the order's own work "
    "content or its release, not a queue behind something else.")
LATENESS_CAUSE_MONEY = (
    "The lateness costs ${total} in tardiness charges{worst}.")
LATENESS_CAUSE_MONEY_WORST = ", ${cost} of it on {order}"


# The meta-route header (R-AI1(d) — the ledger answering about itself).
REFUSAL_META_EMPTY = "No unanswered questions have been logged recently."
REFUSAL_META_LEAD = "Questions I couldn't answer recently ({n}):"


# ---------------------------------------------------------------------------
# Invitations (Session 4A.3-pre, CU2 / R-AI3(3)). Where an OBVIOUS next question
# exists, an answer may END by offering it — as a QUESTION, proposing a SUPPORTED
# route, never an action, never an unbuilt capability. Authored here (never
# LLM-improvised), one per route, and rendered at most once (the register ladder's
# final rung: testimony, then take, then invitation). Frequency discipline: only
# the routes below carry one; lookups (counts, lists, one order's attributes) do
# NOT — an invitation on every turn is noise, not help.
INVITE_LATE_ORDERS = ('Want the cause chain for the worst one? Ask '
                      '"why is {order} late?"')
INVITE_WHY_LATE = ('Want to see what else queues behind {machine}? Ask '
                   '"what\'s running on {machine}?"')
INVITE_DATA_PROBLEMS = 'Want the fix-first ordering? Ask "what should I fix first?"'
# Session 4A.3b CU4 — invitation coverage extended to two more route families with
# a natural next link. Coaching (you named a capability; the obvious next question
# is what the submission already declares) and gap-between (you asked about a gap on
# a machine; the rest of that machine's schedule is the neighboring context). Both
# open a REAL door (data-problems / machine-schedule), asserted by the reverse-guard.
INVITE_COACHING = ('Want to check what the submission already declares? Ask '
                   '"what data problems exist?"')
INVITE_GAP = ('Want the rest of {machine}\'s schedule? Ask '
              '"what\'s running on {machine}?"')


# ---------------------------------------------------------------------------
# The invitation registry (Session 4A.3b, CU4 / R-AI4(3)). Invitations are
# AUTHORED PATTERNS per route family, slots filled from the answer's own
# pre-computed facts — never LLM-improvised, never static-generic where a
# contextual fact exists. Every pattern's PROBE (the proposed follow-up in
# isolation) maps to a live route (``expect_route``); a fast reverse-guard test
# (``tests/ai_exam/test_real_doors.py``) asserts each one classifies there, so no
# invitation offers a door into a wall (R-AI4(3)(c)). FLUENCY, NOT ENGAGEMENT: each
# offer is the evidence chain's next link, and lookups carry NONE (silence is the
# correct register when the thought is complete).
from dataclasses import dataclass


@dataclass(frozen=True)
class Invitation:
    key: str                    # the route family this invitation belongs to
    pattern: str                # the full authored line, with {slot} holes
    probe: str                  # the proposed follow-up alone (same slots)
    slots: tuple                # required fact slots; missing one -> no invitation
    expect_route: str           # the live route the probe opens (the guard checks)


INVITATIONS: dict = {
    "late-orders": Invitation(
        "late-orders", INVITE_LATE_ORDERS,
        "why is {order} late?", ("order",), "late-order"),
    "why-late": Invitation(
        "why-late", INVITE_WHY_LATE,
        "what's running on {machine}?", ("machine",), "machine-schedule"),
    "data-problems": Invitation(
        "data-problems", INVITE_DATA_PROBLEMS,
        "what should I fix first?", (), "triage"),
    "coaching": Invitation(
        "coaching", INVITE_COACHING,
        "what data problems exist?", (), "data-problems"),
    "gap-between": Invitation(
        "gap-between", INVITE_GAP,
        "what's running on {machine}?", ("machine",), "machine-schedule"),
}
# Session 4A.5a: ``expect_route`` names a member of the closed intent vocabulary
# (it used to name "schedule", the route()-level alias for the three schedule
# listings, which no intent could ever be parsed as). The reverse-guard now asserts
# taxonomy membership offline, and the live sweep asserts the PARSE of each probe
# lands on the declared intent — a door proven from both sides.


def invitation_line(key: str, **facts) -> "str | None":
    """The authored invitation line for a route family, slots filled from facts —
    or None when a required contextual fact is missing (never a half-filled offer).
    This is the single seam a renderer calls; it never composes prose of its own."""
    inv = INVITATIONS.get(key)
    if inv is None:
        return None
    if any(not facts.get(s) for s in inv.slots):
        return None
    try:
        return inv.pattern.format(**{s: facts[s] for s in inv.slots})
    except (KeyError, IndexError):
        return None


def invitation_probe(key: str, **facts) -> "str | None":
    """The proposed follow-up question (the door), for the reverse-guard test."""
    inv = INVITATIONS.get(key)
    if inv is None or any(not facts.get(s) for s in inv.slots):
        return None
    try:
        return inv.probe.format(**{s: facts[s] for s in inv.slots})
    except (KeyError, IndexError):
        return None


# CU2 (Session 4B.4) — a clarify/near-miss/refusal lead echoes the user's question
# verbatim ('… to answer "{q}"'). When the question carries FRUSTRATION or
# META-COMMENTARY ("this is not helpful. if i open up hours…") echoing it back reads
# as tone-deaf and repeats the complaint at the user. Detect those markers and drop
# the verbatim clause entirely (the lead then stands on its own); a plain question
# is echoed unchanged.
_FRUSTRATION_MARKERS = (
    "not helpful", "unhelpful", "useless", "that's wrong", "thats wrong",
    "you're wrong", "youre wrong", "no.", "stop", "come on", "seriously",
    "frustrat", "annoying", "terrible", "awful", "this is not", "that is not",
    "you keep", "you always", "again", "still wrong", "wtf", "ugh",
)


def _has_meta_commentary(q: str) -> bool:
    ql = (q or "").lower()
    return any(m in ql for m in _FRUSTRATION_MARKERS)


def safe_parsed(q: str) -> str:
    """The question to echo in a fallback lead, or '' to drop the echo. Empty when
    the question carries frustration / meta-commentary — never repeat a complaint
    back at the planner (CU2)."""
    return "" if _has_meta_commentary(q) else (q or "")


# Frustration-free variants of the fallback leads (used when the echo is dropped).
CLARIFY_LEAD_NO_ECHO = "I need one more detail to answer that."
NEAR_MISS_LEAD_NO_ECHO = "I can't answer that one exactly."
UNSUPPORTED_LEAD_NO_ECHO = "I can't answer that question yet."


def route_offer(route: str, params: dict | None = None) -> str:
    """A concrete one-phrase follow-up for a route, params substituted where the
    interpreter resolved them, generic nouns where it didn't. Unknown routes fall
    back to their id (should never happen — the taxonomy is closed)."""
    template = ROUTE_OFFERS.get(route)
    if template is None:
        return route
    params = params or {}
    fill = {slot: params.get(slot) or GENERIC_NOUNS[slot] for slot in GENERIC_NOUNS}
    try:
        return template.format(**fill)
    except (KeyError, IndexError):
        return template


# ---------------------------------------------------------------------------
# SESSION 4B.21 — A COUNT NAMES THE DISPOSITION IT COUNTS, AND A PREDICATE
# ASSERTED OVER A COUNT MUST APPLY TO EVERY MEMBER (docs/04 2026-07-30 ruling).
#
# The `inventory` route said "40 order(s) are in the plan, scheduled across 56
# operation(s). … Every order finishes on time." on a board where 26 orders are
# scheduled, 14 have no placement at all, the 56 operations belong to those 26
# (of 88 declared), and only the 26 have a projected completion for a universal
# to range over. Every number was true of its own set; the sentence was true of
# none, and three other surfaces on the same board said so.
#
# These strings exist so that the split is IN THE SENTENCE rather than left for
# a planner to reconstruct from a second question. Same discipline as the 4B.13
# late-orders scope clause and the R-PD1 clause (4) tardiness split: where a
# figure covers part of a set, the part is named where the figure is spoken.
# ---------------------------------------------------------------------------

# The rolling case: three dispositions, spoken as three.
INVENTORY_ROLLING = (
    "{known} order(s) are known to this plan. {scheduled} of them are scheduled "
    "in this window, across {placed_ops} placed operation(s); the other "
    "{beyond} sit beyond the horizon with no placement yet.")
# The monolithic case: no horizon, so the scheduled set IS the admitted set and
# there is nothing to split. Saying "of them" here would invent a distinction.
INVENTORY_MONOLITHIC = (
    "{scheduled} order(s) are scheduled in this plan, across {placed_ops} "
    "operation(s).")
# Excluded work is a separate disposition and never folded into either of the
# two above (R-PD1 clause 2: exclusion is a data-defect category only).
INVENTORY_EXCLUDED = (
    "{excluded} further order(s) were excluded by the conformance gate and are "
    "in neither figure.")

# THE SPLITTABLE LINE'S OWN DENOMINATOR. `splittable_declared` is counted over
# every DECLARED operation, which on a rolling board is a larger set than the
# placed operations named one line earlier — so the two are never left adjacent
# and unqualified.
INVENTORY_SPLITTABLE = (
    "{declared_split} of the {declared_ops} declared operation(s) can split "
    "across a pause (e.g. an overnight closure); {placed_split} of those are "
    "placed in this window.")
INVENTORY_SPLITTABLE_MONOLITHIC = (
    "{declared_split} operation(s) can split across a pause (e.g. an overnight "
    "closure).")
INVENTORY_SPLITTABLE_NONE = "No operations are set to split across a pause."

# THE UNIVERSAL, SCOPED TO THE SET THAT CAN SATISFY IT. An order with no
# placement has no projected completion, so it is neither late nor on time —
# the distinction `lateness_set` already states and that this sentence used to
# erase.
INVENTORY_ON_TIME_ROLLING = (
    "All {scheduled} scheduled order(s) finish on time. The {beyond} beyond the "
    "horizon have no completion date yet, so they are neither late nor on time.")
INVENTORY_ON_TIME_MONOLITHIC = "Every order finishes on time."
INVENTORY_LATE = "{late} of the {scheduled} scheduled order(s) finish late."

# Session 4B.22 Item B3 — ALL-IN OR ALL-OUT, PER ORDER. 4B.21 answered this
# question truly and about something else: asked whether an order can be
# PARTIALLY placed, the route said how many orders are placed. The two sentences
# below state the measurement; the third states its LIMIT, and it is not
# optional. "No order is partly placed" is a fact about this schedule.
# "Orders are never partly placed" would be a claim about the product, and
# nothing enforces it (see `OrderDisposition.placement_is_all_or_nothing`).
INVENTORY_ALL_OR_NOTHING = (
    "All in or all out, on this board: each of the {full} scheduled order(s) has "
    "every one of its declared operations placed in this window, and each of the "
    "{unplaced} beyond the horizon has none of them. No order is split across "
    "the boundary.")
INVENTORY_PARTLY_PLACED = (
    "Not all in or all out: {partly} order(s) are SPLIT across the boundary — "
    "some of their declared operations are placed in this window and some are "
    "not. {full} order(s) have all of theirs placed and {unplaced} have none.")
INVENTORY_ALL_OR_NOTHING_LIMIT = (
    "That is measured off this schedule, not a rule the product enforces: work "
    "is admitted a whole work package at a time, and an order served by more "
    "than one could in principle be split. None on this board is.")

# THE PARTITION FAILED. Scheduled + beyond + excluded did not add up to known,
# which means an order is in no bucket at all. The assembler raises on this at
# document build; if a count surface ever sees it, it says so rather than
# picking whichever number looks plausible.
INVENTORY_PARTITION_BROKEN = (
    "I can't give you a reliable total: the orders I can account for "
    "({scheduled} scheduled, {beyond} beyond the horizon, {excluded} excluded) "
    "do not add up to the {known} this plan knows about, so at least one order "
    "is unaccounted for. That is a defect in this schedule document, not a "
    "fact about the plant.")

# The lateness-cause route's own premise lines, re-scoped. `total` there was the
# KNOWN set, so "the other 39 finish on time or early" was asserted of 14 orders
# with no finish.
LATENESS_CAUSE_NONE_ROLLING = (
    "Nothing is late in this plan — all {scheduled} scheduled order(s) finish "
    "on or before their due date, so there is no lateness to account for. The "
    "{beyond} order(s) beyond the horizon have no completion date yet.")

# NO DOCUMENT REACHED THIS ANSWER, so the beyond-horizon region is UNREADABLE —
# which is not the same as empty. Found on this session's own live run: the
# route stated a monolithic total over a rolling board because `rolling` is
# itself read off the document it did not have. Same distinction as 4B.18's
# `CostProof.unreadable`: a fact about our reach never becomes a claim about
# the plant.
INVENTORY_UNREADABLE = (
    "{known} order(s) are known to this plan, and {scheduled} of them are "
    "scheduled across {placed_ops} placed operation(s). I can't tell you what "
    "became of the rest from here: the schedule document didn't reach this "
    "answer, and the beyond-horizon list lives on it. Ask \"what's beyond the "
    "horizon?\" and I'll read it directly.")

# NOTHING WAS EXCLUDED, AND WORK IS STILL ABSENT FROM THE SCHEDULE. Measured
# live: "why are some orders missing from the schedule entirely" answered "No
# data-quality problems -- the submission is clean" on a board with 14
# beyond-horizon orders. True about exclusions; silent about the disposition the
# question was actually about. Ruling clause (2): where a predicate covers only
# part of what was asked, the other part is named where the answer is spoken.
EXCLUDED_NONE_BUT_TRAY = (
    "That said, {beyond} order(s) have no placement in this window — not "
    "because anything rejected them, but because they sit beyond the current "
    "scheduling window and enter a later one as the plan rolls. Ask \"what's "
    "beyond the horizon?\" for the list.")
