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
    "why-on-machine": "explain why {order} is on {machine}",
    "machine-schedule": "show what's running on {machine}",
    "order-schedule": "show when {order} starts and finishes",
    "customer-schedule": "show the schedule for {customer}",
    "downtime": "show {machine}'s downtime (calendar closures)",
    "data-problems": "list the data-quality problems",
    "version-diff": "show what changed between two versions",
    "remediation": "show how to fix the submission's problems",
    "triage": "show what to fix first",
    "certificate-testimony": "explain what's wrong with the submission",
    "edit-summary": "summarize the edits you made and what they cost",
    "edit-cost": "break down what your last move cost",
    "ledger-refusals": "list the questions I couldn't answer recently",
    "advice": "explain why each order is late and price a what-if move",
    "coaching": "show how to enable that capability in the submission",
    "solve-time": "tell you how long the solve took",
    "machine-count": "list the machines in the plan",
    "maintenance": "show one machine's downtime (calendar closures)",
    "swap-move": "weigh swapping {order} with another order and how to price it",
    "gap-between": "explain the gap before {order} on its machine",
    "machine-idle": "explain why {machine} carries no work",
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
