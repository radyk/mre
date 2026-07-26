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

from pydantic import BaseModel, ConfigDict, Field

from mre.contracts.promotion import ShadowDiff
from mre.contracts.synthesis import SynthesisProvenance


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ParseProvenance(BaseModel):
    """What the PARSE named, recorded on the ledger entry (R-AI5(5), Session
    4A.5c).

    The ledger already carried the ROUTE an answer took. That is not enough to
    cluster synthesis residue: every second-tier answer takes the same route
    (``synthesis``), so a ledger of routes alone says only "these 32 questions were
    uncontracted" and nothing about WHICH SHAPES they were. The parse knows more
    than the route does — which contracted intents it thought were ADJACENT
    (``nearest``), and what KINDS of subject the planner named — and those two
    fields plus the tool-call pattern are the clustering signal the provenance
    report uses.

    Counts and closed-vocabulary ids only. No prose, no answer, nothing about the
    schedule: a ledger entry is a fact ABOUT the AI layer."""

    model_config = ConfigDict(extra="forbid")

    #: The intent the parse named (``Intent`` value). ``unmatched`` on a
    #: second-tier answer, which is exactly why ``nearest`` matters.
    intent: str = ""
    #: The contracted intents the parse judged closest, in its own order. On an
    #: unmatched parse this is the only statement of what NEIGHBOURHOOD the
    #: question sat in.
    nearest: list[str] = Field(default_factory=list)
    #: The KINDS of subject the parse bound (order / machine / customer /
    #: concept), de-duplicated and sorted. Not the refs — a cluster is a shape,
    #: and which order was named is not part of the shape.
    subject_kinds: list[str] = Field(default_factory=list)
    polarity: Optional[str] = None
    followup_of: str = "none"
    confidence: float = 0.0
    prompt_version: str = ""
    #: Session 4A.5c CU3(c): the parse reported that the planner stated a
    #: qualifier the matched route does not honour (a time scope, an "actually",
    #: a comparative). Recorded because a diverted turn is telemetry about the
    #: VOCABULARY's gaps, not about the planner.
    dropped_qualifier: str = ""


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
    - ``synthesis``          — present only on a SECOND-TIER answer (R-AI5(2)):
      the per-claim provenance and every tool call with its arguments. R-AI5(5)
      records per-claim provenance in this ledger; the frequency-weighted Pareto
      that consumes it is ``tools/provenance_report.py`` (Session 4A.5c). Still a
      fact ABOUT the AI layer, never schedule evidence.
    - ``parse``              — what the parse named (Session 4A.5c): intent,
      adjacency, subject kinds. The clustering signal; see ``ParseProvenance``.
    - ``shadow``             — present only on a turn a PROMOTED route answered
      while its probation window is open (R-AI5(7)): the diff between the route's
      answer and the synthesis shadow's. A fired divergence is the demotion
      trigger; see ``ShadowDiff``.
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
    synthesis: Optional[SynthesisProvenance] = None
    parse: Optional[ParseProvenance] = None
    shadow: Optional[ShadowDiff] = None

    @property
    def refused(self) -> bool:
        return self.route in ("REFUSED", "NEAR_MISS", "CLARIFY")
