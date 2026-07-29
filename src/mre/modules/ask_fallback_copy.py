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
ROUTE_OFFERS = {
    "late-order": "show why {order} is late",
    "late-orders": "show every late order at a glance",
    "lateness-cause": "explain what is driving the lateness across the plan",
    "why-on-machine": "explain why {order} is on {machine}",
    "machine-schedule": "show what's running on {machine}",
    "order-schedule": "show when {order} starts and finishes",
    "customer-schedule": "show the schedule for {customer}",
    "schedule": "show the full schedule, machine by machine",
    "downtime": "show {machine}'s downtime (calendar closures)",
    "data-problems": "list the data-quality problems",
    "version-diff": "show what changed between two versions",
    "remediation": "show how to fix the submission's problems",
    "triage": "show what to fix first",
    "certificate-testimony": "explain what's wrong with the submission",
    "edit-summary": "summarize the edits you made and what they cost",
    "edit-cost": "break down what your last move cost",
    "open-card": "read back the move you have priced on the board",
    "ledger-refusals": "list the questions I couldn't answer recently",
    "advice": "explain why each order is late and price a what-if move",
    "coaching": "show how to enable that capability in the submission",
    "solve-time": "tell you how long the solve took",
    "machine-count": "list the machines in the plan",
    "solve-optimality": "say whether this schedule's cost is proven optimal",
    "maintenance": "show one machine's downtime (calendar closures)",
    "swap-move": "weigh swapping {order} with another order and how to price it",
    "gap-between": "explain the gap before {order} on its machine",
    "machine-idle": "explain why {machine} carries no work",
    "order-attributes": "show {order}'s details (product, quantity, customer, due)",
    "inventory": "count the orders and operations in the plan",
    "integrity-check": "check whether anything is double-booked",
    "start-reason": "explain why {order} starts when it does",
    "why-here": "name the binding constraint on {order} starting earlier",
    "excluded-orders": "list the orders excluded from the plan and why",
    "drill-down": "open the full record behind that",
    "briefing": "show what needs your attention today",
    "contested-fact": "walk the evidence for {order}'s status",
    "confirm-take": "name the board gesture that makes that move",
    "prove-it": "open the record behind what I just told you",
    "beyond-horizon": "show what lies beyond the planning horizon",
    "why-not-scheduled-yet": "explain why {order} isn't scheduled yet",
    "frozen": "show what is frozen",
    # Session 4B.6 — the coarse zone (R-SC2 amendment).
    "coarse-fit": "check whether the work beyond the horizon fits",
    "bucket-load": "show what is filling up a week beyond the horizon",
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
OPEN_CARD_AFFECTED_NONE = "No order's lateness or tardiness changes because of it."
OPEN_CARD_LATENESS_WORSE = "Across the plan it introduces {hours}h of lateness."
OPEN_CARD_LATENESS_BETTER = "Across the plan it recovers {hours}h of lateness."
OPEN_CARD_LATENESS_NONE = "Nothing's lateness changes across the plan."
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

# The budget ran out before the read was complete (CU1: an honest partial, never a
# stall). `{tools}` names what was consulted.
SYNTHESIS_PARTIAL = (
    "I stopped there — that is as far as this question's evidence budget goes. I "
    "consulted: {tools}.")

# The floor: nothing survived, or the model could not answer from the evidence.
SYNTHESIS_UNANSWERABLE = (
    "I couldn't answer that one from the evidence. I read what I could and none of "
    "it grounds an answer I'd stand behind, so I'd rather say so than guess.")
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
PROVE_IT_NO_TARGET = (
    "I don't have a claim of my own open to ground. If it's my last answer you're "
    "asking about, the records behind it are cited on it — name the part you want "
    "walked and I'll open that one.")
PROVE_IT_VERIFIED = "That one is on the record. Here is what it rests on:"
PROVE_IT_INTERPRETIVE = (
    "That part is my inference, not a record — here is each thing I read to get "
    "there:")
PROVE_IT_INTERPRETIVE_BARE = (
    "That part is my reading of the plan, and no single record states it. I have "
    "nothing further to show behind it.")
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
LATENESS_CAUSE_PREMISE_ONE = (
    "There aren't many — exactly one order is late: {order}, by {amount}. "
    "The other {on_time} finish on time or early.")
LATENESS_CAUSE_LEAD = (
    "{late} of {total} orders are late. Here is what is driving it.")
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
