"""The question-ledger record shape (R-AI1(d)).

Every question asked of the AI layer is logged as one of these — its OWN record
stream, deliberately kept out of the canonical evidence contract (docs/02): a
ledger entry is a fact ABOUT the AI layer's behavior, never a fact about the
schedule, so it must never pollute schedule evidence. It still lives here because
the hard rule holds without exception: *nothing defines record shapes outside
`src/mre/contracts/`.*

Per R-AI1, unanswerable questions are themselves logged facts that feed a
human-curated improvement loop — the refusals in this stream are the labeled data
the interpreter's paraphrase table grows from. The system never rewrites its own
routing from this stream unreviewed; a human reads the refusal clusters (the
dev-panel view / the meta-route) and curates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuestionLedgerEntry(BaseModel):
    """One asked question, resolved and routed (or refused).

    Fields (R-AI1(d) — verbatim question, resolved question, route or REFUSED,
    confidence, register, schedule version, rephrase linkage):

    - ``verbatim_question``  — exactly what the planner typed / said.
    - ``resolved_question``  — after conversational-context resolution (CU2); the
      complete question that was actually routed. Equals ``verbatim_question``
      when no ellipsis resolution occurred.
    - ``route``              — the taxonomy route id that answered it, or the
      sentinel ``REFUSED`` (full refusal), ``NEAR_MISS`` (tiered bridge), or
      ``CLARIFY`` (unresolvable ellipsis). Never a free-form string outside these.
    - ``source``             — how the route was reached: ``deterministic`` (the
      router's exact/pattern match — zero LLM), ``llm`` (the interpreter mapped
      the phrasing), or ``none`` (refused/clarify).
    - ``confidence``         — the interpreter's confidence in [0, 1], or None for
      a deterministic route (certainty is implicit).
    - ``answer_register``    — the register rendered (testimony / judgment / a
      fallback marker), mirrored from the answer bundle.
    - ``schedule_id``        — the schedule version the question was asked against
      (the AI layer's answers are version-scoped).
    - ``session_id``         — the ask session, so a refusal and its later
      successful rephrase can be linked.
    - ``rephrase_of``        — set on a ROUTED entry when it followed a REFUSED
      entry in the same session within the rephrase window: the entry_id of that
      refusal. This is the free labeled pair (failed phrasing → phrasing that
      worked) the improvement loop consumes.
    """

    entry_id: str
    ts: datetime = Field(default_factory=_utc_now)
    verbatim_question: str
    resolved_question: str
    route: str
    source: str = "deterministic"
    confidence: Optional[float] = None
    answer_register: Optional[str] = None
    schedule_id: Optional[str] = None
    session_id: Optional[str] = None
    rephrase_of: Optional[str] = None

    @property
    def refused(self) -> bool:
        return self.route in ("REFUSED", "NEAR_MISS", "CLARIFY")
