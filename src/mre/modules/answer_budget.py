"""M10 — THE DEPTH LICENCE (R-TG3, Session 4A teaching-graft (b)).

Depth is GRANTED BY THE QUESTION'S INTENT, never assumed and never earned by the
answering model's enthusiasm. Two budgets:

  LONG   — ``Intent.TEACHING`` only. The planner asked to be taught something;
           an explanation is what they asked for and it is allowed to be long.
  SHORT  — everything else that reaches the second tier. Lead with the answer;
           the rest is offered, not delivered.

WHY THE SEAM AND NOT THE PROMPT. Synthesis prompt rule 6 has said "between three
and six claims is usually right; one is thin and ten is a report" since v1, and
the measured distribution is 2..6 with 38% of real answers at 5 or 6 — so the
exhortation is followed loosely and bounds nothing. 4A.y's lesson is the general
form: a behaviour that depends on a model remembering an instruction will
silently stop. The prompt still ASKS for brevity, because a model that drafts
four good claims beats one that drafts six and has two thrown away; the seam
ENFORCES it, so the bound holds whatever the model does.

WHAT IT MAY AND MAY NOT DO — three clauses, each load-bearing.

  (1) IT TRIMS, IT NEVER REWRITES. No sentence is shortened, merged or reworded.
      A budget that edited prose would be a second author with no verification
      pass behind it, and every claim here has already been through one.

  (2) THE CONCLUSION IS NEVER TRIMMED. The model says which of its sentences is
      the conclusion — a STRUCTURAL statement it is allowed to make (R-AI5(8),
      ``ClaimKind``) — and an answer whose conclusion was dropped for length is
      worse than one line longer. A conclusion falling outside the budget
      replaces the last claim inside it, and the displaced claim is deferred.
      Draft order is otherwise preserved exactly, because the model chose it and
      re-ranking claims would be a judgement about value this module has no
      basis for.

  (3) WHAT IT WITHHOLDS, IT DISCLOSES. A deferred claim is not cut: it passed
      verification and it is true. It goes to ``SynthesisAnswer.deferred``, the
      count reaches the page (``SYNTHESIS_DEFERRED``), and the offer to walk
      through the rest is the licence's honest half. Brevity must never silently
      discard substance; it defers it visibly.

  And the negative of (3), asserted by its own guard: THE CLOSER IS ABSENT WHEN
  NOTHING WAS WITHHELD. A closer on an uncut answer is a false disclosure — it
  tells a planner there is more when there is not.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mre.contracts.parse import Intent
from mre.contracts.synthesis import (
    ClaimKind,
    LONG_CLAIM_BUDGET,
    SHORT_CLAIM_BUDGET,
    SynthesisAnswer,
)


@dataclass(frozen=True)
class Licence:
    """One granted budget, and the words for what granted it."""

    name: str                  # "long" | "short"
    max_claims: int
    granted_by: str            # the intent id that decided it


LONG = Licence("long", LONG_CLAIM_BUDGET, Intent.TEACHING.value)


def licence_for(intent: Optional[Intent]) -> Licence:
    """The budget one intent is granted.

    TEACHING and nothing else gets the long budget. Stated as an equality rather
    than a set so that a new intent inherits the SHORT budget by default: depth
    is granted, and a route added later that wants it has to come and ask.
    """
    if intent is Intent.TEACHING:
        return LONG
    return Licence("short", SHORT_CLAIM_BUDGET,
                   intent.value if intent is not None else "unmatched")


def _is_conclusion(claim: Any) -> bool:
    kind = getattr(claim, "kind", None)
    return getattr(kind, "value", kind) == ClaimKind.CONCLUSION.value


def apply(answer: SynthesisAnswer, licence: Licence) -> SynthesisAnswer:
    """Trim ``answer`` to ``licence`` IN PLACE, moving the surplus to ``deferred``.

    Returns the same object, so a caller can read it either way. Idempotent: a
    second application over an already-trimmed answer defers nothing more.

    An answer already inside its budget is not touched AT ALL — not re-ordered,
    not re-listed — which is what makes the "closer absent when nothing was
    withheld" guard a property of this function rather than of the renderer.
    """
    claims = list(answer.claims)
    if len(claims) <= licence.max_claims:
        return answer

    keep = claims[:licence.max_claims]
    surplus = claims[licence.max_claims:]

    # Clause (2). The conclusion, if the trim would have dropped it, takes the
    # last kept slot — and the claim it displaces joins the surplus IN ITS OWN
    # DRAFT POSITION, so the deferred list still reads in the order it was
    # written.
    if not any(_is_conclusion(c) for c in keep):
        conclusion = next((c for c in surplus if _is_conclusion(c)), None)
        if conclusion is not None:
            keep = keep[:-1] + [conclusion]
            # Everything from the displaced claim onwards, minus the conclusion
            # that was promoted out of it. The slice starts one earlier than the
            # budget so the displaced claim (``claims[max - 1]``) is deferred
            # rather than lost.
            surplus = [c for c in claims[licence.max_claims - 1:]
                       if c is not conclusion]

    answer.claims = keep
    answer.deferred = list(answer.deferred) + surplus
    return answer
