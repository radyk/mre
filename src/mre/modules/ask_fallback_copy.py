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

# The meta-route header (R-AI1(d) — the ledger answering about itself).
REFUSAL_META_EMPTY = "No unanswered questions have been logged recently."
REFUSAL_META_LEAD = "Questions I couldn't answer recently ({n}):"


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
