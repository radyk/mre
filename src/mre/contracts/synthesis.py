"""L1 — The labeled-synthesis contract (R-AI5(2)/(3)/(8), Session 4A.5b).

The second tier of the ask path. R-AI5(2): a matched intent dispatches to contracted
deterministic evidence assembly; an UNMATCHED intent "receives labeled open synthesis
over read-only evidence access". R-AI5(3): every synthesis answer is hardened before
rendering by automatic claim-level verification. R-AI5(8): the provenance label is
assigned by that verification against independently assembled evidence — never by the
answering model's self-assessment.

Three closed vocabularies live here (add, never repurpose — a change is reviewed like
any other vocabulary change, with the doc update in the same commit):

  ``ToolName``    — the CLOSED read-only evidence-query surface the synthesis model
                    may call. No tool executes an arbitrary query; a name outside
                    this enum is not a tool, it is a malformed emission.
  ``TOOL_MEANINGS`` / ``TOOL_ARGS``
                  — the authored one-line meaning and typed argument list of every
                    tool. The governed synthesis prompt is BUILT from these, so a
                    tool added without a meaning fails the parity test rather than
                    silently becoming uncallable (the ``INTENT_MEANINGS`` discipline).
  ``ClaimStatus`` — the verification outcome taxonomy: VERIFIED / INTERPRETIVE /
                    FAILED. Nothing else may label a claim.

Everything here is a SHAPE. The readers live in ``modules/evidence_tools.py``, the
loop in ``modules/synthesizer.py``, and the verifier — deterministic code, never a
model — in ``modules/claim_verifier.py``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# The budget (CU1). Stated, deterministic, and enforced by the toolbox.
# ---------------------------------------------------------------------------

#: The per-question tool-call cap. Exhaustion yields an honest PARTIAL answer that
#: says what it consulted — never a stall and never an unbounded loop.
MAX_TOOL_CALLS = 12

#: The overall wall-clock ceiling for one synthesis (seconds), measured from the
#: first model call. Deterministic in the sense that matters: it is a fixed number
#: stated in the contract, not a heuristic the model can talk its way past.
SYNTHESIS_TIMEOUT_S = 90.0

#: The most rows any single tool result returns. A truncated result says so, and a
#: claim quantifying over a truncated set can never be VERIFIED (completeness
#: honesty, CU3).
MAX_ROWS = 60


# ---------------------------------------------------------------------------
# The closed tool surface
# ---------------------------------------------------------------------------

class ToolName(str, Enum):
    """The closed read-only evidence-query surface (R-AI5(2)).

    Every member is a THIN WRAPPER over the same reader a contracted route uses —
    one truth, two consumers. M10 has no write path, so there is deliberately no
    tool here that mutates, re-solves, or prices anything."""

    PLACEMENTS_FOR_ORDER = "placements_for_order"
    PLACEMENTS_FOR_MACHINE = "placements_for_machine"
    PLACEMENTS_IN_WINDOW = "placements_in_window"
    MACHINE_OCCUPANCY = "machine_occupancy"
    LATENESS_SET = "lateness_set"
    COST_LEDGER = "cost_ledger"
    GATE_FINDINGS = "gate_findings"
    CALENDARS = "calendars"
    CAPABILITY_REGISTRY = "capability_registry"
    ENTITY_VOCABULARY = "entity_vocabulary"
    FETCH_RECORD = "fetch_record"
    # Session 4B.15 Items 1 + 5 — THE MANUAL. Measured live, "can two machines
    # share one operator" came back a confident YES describing alternates,
    # because the tier could reach a nine-entry capability registry and could
    # NOT reach the constraint catalog, which answers the question exactly. Two
    # tools, deliberately separate:
    #
    #   CONSTRAINT_CATALOG — docs/05's catalog rows AS RECORDS: verdict, plane,
    #       proof status, IDS doorway, plus the locked rulings and the global
    #       exclusions. The authority on what the product does and does not
    #       model.
    #   SPEC_LOOKUP — prose from the CURRENT tier only (docs/01, 05, 06). It
    #       cannot reach docs/07 (intent, not behaviour) or docs/04 (history,
    #       carrying superseded rulings as first-class text) — that boundary is
    #       enforced in `corpus.TIERS_FOR_PURPOSE`, not asked for here.
    CONSTRAINT_CATALOG = "constraint_catalog"
    SPEC_LOOKUP = "spec_lookup"


class ToolArg(BaseModel):
    """One typed argument of one tool. Rendered into the governed prompt."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str                       # "order" | "machine" | "timestamp" | "id"
    required: bool = False
    meaning: str = ""


#: The authored meaning of every tool — what the governed synthesis prompt renders.
#: A tool without a meaning is a parity failure (``tests/test_synthesis_tools.py``).
TOOL_MEANINGS: dict[ToolName, str] = {
    # WORKING TIME AND ELAPSED SPAN ARE DIFFERENT QUANTITIES (Session 4B.20).
    # These three rows carried one unqualified `duration_minutes` that was the
    # SPAN; on a chunked operation it read 5821 where the work is 1501, and the
    # second tier reported "a single 5821-minute operation" because the row
    # gave it no truer number to quote. Every meaning below now names which
    # quantity is which, because the prompt is built from this text and a
    # reasoner that cannot tell them apart will pick whichever is larger.
    ToolName.PLACEMENTS_FOR_ORDER:
        "every scheduled operation of one order: machine, start, end, and BOTH "
        "time figures — working_minutes (the work) and elapsed_span_minutes "
        "(start to end, including any pause). They differ on a SPLIT operation "
        "(pieces > 1, paused_minutes stated); never use the span as the duration",
    ToolName.PLACEMENTS_FOR_MACHINE:
        "every scheduled operation on one machine, earliest first, with "
        "working_minutes and elapsed_span_minutes stated separately",
    ToolName.PLACEMENTS_IN_WINDOW:
        "every scheduled operation overlapping a time window, across all "
        "machines, with working_minutes and elapsed_span_minutes stated "
        "separately",
    ToolName.MACHINE_OCCUPANCY:
        "how busy one machine is: per operation its working_minutes vs its "
        "elapsed_span_minutes, the gap before it (gap_before_minutes) and how "
        "much of that gap was OPEN capacity (idle_open_minutes_before). The "
        "summary carries working_minutes, open_capacity_minutes and "
        "utilization_pct — use those for 'how busy', never a sum of spans, "
        "which can exceed the machine's whole open capacity",
    ToolName.LATENESS_SET:
        "every order's lateness in minutes (positive = late, negative = early) — "
        "the WHOLE set, so counts over it are enumerable. THREE disjoint states, "
        "never two: 'late', 'on_time_or_early', and 'not_scheduled' (an order "
        "with no placement in this schedule, e.g. beyond the rolling horizon). "
        "An unscheduled order is NOT on time — it has no service outcome at all. "
        "Read summary.scheduled before saying anything about 'all orders'",
    ToolName.COST_LEDGER:
        "the schedule's cost ledger: the totals (production, setup, tardiness, "
        "overtime) and the per-order tardiness lines",
    ToolName.GATE_FINDINGS:
        "the data-quality findings on the submission (code, severity, subject)",
    ToolName.CALENDARS:
        "the working calendars and their closures / exceptions, per machine",
    ToolName.CAPABILITY_REGISTRY:
        "what the product can be told to do and how it is declared (the coaching "
        "registry, with its spec citations)",
    ToolName.ENTITY_VOCABULARY:
        "the orders, machines and customers that exist in THIS run — ask first if "
        "you are unsure whether something the planner named is here. "
        "summary.known_orders is EVERY order this plan knows about, placed or "
        "not; it is NOT the number scheduled in this window",
    ToolName.FETCH_RECORD:
        "one evidence record or entity by id, in full",
    ToolName.CONSTRAINT_CATALOG:
        "WHAT THE SYSTEM MODELS AND WHAT IT DELIBERATELY DOES NOT — the "
        "constraint catalog, as records: each item's verdict (in-core / "
        "later-slot / out), its proof status (proven end to end / model only / "
        "unbuilt), where it is declared in a submission, and the rulings and "
        "exclusions behind it. CALL THIS BEFORE ANY CLAIM ABOUT WHAT THE "
        "PRODUCT CAN DO — a capability answer you reasoned out is one a planner "
        "will act on by authoring data that may be silently ignored",
    ToolName.SPEC_LOOKUP:
        "the specifications themselves, in prose: the canonical model, the "
        "constraint catalog and the incoming-data spec (every submission field "
        "and how to declare it). CURRENT specs only — the roadmap and the "
        "design history are deliberately out of reach",
}


#: The typed argument list of every tool. Derived nowhere else: the prompt renders
#: THIS, and the toolbox validates against it, so the two cannot drift.
TOOL_ARGS: dict[ToolName, tuple[ToolArg, ...]] = {
    ToolName.PLACEMENTS_FOR_ORDER: (
        ToolArg(name="order", type="order", required=True,
                meaning="the order id, exactly as this run names it"),
    ),
    ToolName.PLACEMENTS_FOR_MACHINE: (
        ToolArg(name="machine", type="machine", required=True,
                meaning="the machine id, exactly as this run names it"),
    ),
    ToolName.PLACEMENTS_IN_WINDOW: (
        ToolArg(name="start", type="timestamp", required=True,
                meaning="ISO-8601 window start, e.g. 2026-01-05T00:00:00Z"),
        ToolArg(name="end", type="timestamp", required=True,
                meaning="ISO-8601 window end"),
    ),
    ToolName.MACHINE_OCCUPANCY: (
        ToolArg(name="machine", type="machine", required=True,
                meaning="the machine id"),
        ToolArg(name="start", type="timestamp",
                meaning="optional ISO-8601 window start (default: the whole plan)"),
        ToolArg(name="end", type="timestamp",
                meaning="optional ISO-8601 window end"),
    ),
    ToolName.LATENESS_SET: (),
    ToolName.COST_LEDGER: (),
    ToolName.GATE_FINDINGS: (),
    ToolName.CALENDARS: (
        ToolArg(name="machine", type="machine",
                meaning="optional — one machine's calendar; omit for all"),
    ),
    ToolName.CAPABILITY_REGISTRY: (),
    ToolName.ENTITY_VOCABULARY: (),
    ToolName.FETCH_RECORD: (
        ToolArg(name="id", type="id", required=True,
                meaning="an evidence record id or a canonical entity id"),
    ),
    ToolName.CONSTRAINT_CATALOG: (
        ToolArg(name="topic", type="text", required=False,
                meaning="what the planner asked about, in their own words "
                        "(\"share one operator\", \"oven cycle\", \"day shift "
                        "only\"); omit to list every catalog item"),
    ),
    ToolName.SPEC_LOOKUP: (
        ToolArg(name="query", type="text", required=True,
                meaning="what to look up, in a few words"),
    ),
}


# ---------------------------------------------------------------------------
# Tool results — typed, and they CARRY THEIR RECORD IDS (CU1)
# ---------------------------------------------------------------------------

class ToolResult(BaseModel):
    """One tool call's typed result.

    ``rows`` are planner-readable dicts; every row carries a ``record_ids`` list —
    the evidence record ids / canonical entity ids that back it. That list is what a
    claim cites and what the verifier independently re-fetches (R-AI5(8)); without
    it a synthesis answer could only ever be interpretive."""

    model_config = ConfigDict(extra="forbid")

    tool: ToolName
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    note: str = ""                        # the honest one-liner on an empty/failed read
    rows: list[dict] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    truncated: bool = False
    #: True when this ONE call enumerates its whole set (no filter, no truncation),
    #: which is exactly the condition a quantifying claim needs to be VERIFIED.
    enumerates_set: bool = False

    @property
    def record_ids(self) -> list[str]:
        out: list[str] = []
        for row in self.rows:
            for rid in row.get("record_ids") or []:
                if rid not in out:
                    out.append(str(rid))
        return out


class ToolCallLog(BaseModel):
    """One logged call — the question-ledger entry's grain (CU1: every call is
    logged with its arguments)."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    rows: int = 0
    note: str = ""


# ---------------------------------------------------------------------------
# Claims and their verification outcome
# ---------------------------------------------------------------------------

class ClaimKind(str, Enum):
    """The claim's role in the answer. STRUCTURAL only — the model may say which of
    its sentences is the conclusion; it may never say whether one is grounded
    (R-AI5(8)).

    ``GENERAL_KNOWLEDGE`` joins in Session 4A teaching-graft (a), R-TG1. It is a
    PROPOSAL about the sentence's SUBJECT — "this is about how scheduling works,
    not about this plan" — in the same family as saying which sentence is the
    conclusion, and it is checked BOTH WAYS by deterministic code before it can
    become a label (``claim_verifier.gk_disqualifiers``). A proposal that names an
    order, a machine, a time or a figure this run computed is REJECTED back to
    ordinary board-claim verification, so the class can never be an escape hatch
    from grounding; and a claim carrying no board content that the model did NOT
    propose as general knowledge is dropped rather than labeled, because the
    verifier may refute a proposal and may not manufacture one.
    """

    FACT = "fact"
    CONCLUSION = "conclusion"
    GENERAL_KNOWLEDGE = "general_knowledge"


class DraftClaim(BaseModel):
    """One claim as the synthesis model drafted it: a sentence, plus the record ids
    it BELIEVES support it. Its beliefs are input to verification, never the label."""

    model_config = ConfigDict(extra="forbid")

    text: str
    record_ids: list[str] = Field(default_factory=list)
    kind: ClaimKind = ClaimKind.FACT


class ClaimStatus(str, Enum):
    """The verification outcome taxonomy (R-AI5(3)). Closed.

    VERIFIED      — EVERY checkable assertion grounds in the cited records, at least
                    one of them a FIGURE or a TIME rather than a name, no quantifier
                    the verifier could not enumerate, and not the draft's own
                    conclusion. Renders as cited, in the proven register, exactly
                    like testimony.
    INTERPRETIVE  — no checkable assertion (an aggregate read or an inference), or
                    part of it unspoken-to by the cited records, or a quantifier the
                    verifier could not enumerate, or a claim that grounds but cites
                    nothing, or the conclusion. Renders labeled, with its consulted
                    records listed. First-class conversation (R-AI5(6)), not a
                    failure.
    FAILED        — a checkable assertion contradicts the evidence, or the claim
                    cites a record that does not exist, or it names an entity this
                    run does not have, or it cites nothing, grounds nothing and
                    carries no board content while claiming to be about this plan.
                    The claim is CUT.
    GENERAL_KNOWLEDGE
                  — the model proposed the claim as domain knowledge (how
                    scheduling, optimization and plants behave in general) and
                    deterministic code confirmed it carries NO board content:
                    no order, no machine, no timestamp, no money, no figure this
                    run computed, and no citation. UNVERIFIABLE BY DESIGN — this
                    status is never earned by checking and never lost by failing a
                    check; it is a statement about what the sentence is ABOUT.
                    Renders with its own label naming both halves (what it is,
                    what it is not) and never with a record marker.
    """

    VERIFIED = "verified"
    INTERPRETIVE = "interpretive"
    FAILED = "failed"
    GENERAL_KNOWLEDGE = "general_knowledge"


class Assertion(BaseModel):
    """One checkable thing a claim asserts, as the verifier extracted it."""

    model_config = ConfigDict(extra="forbid")

    kind: str                 # "number" | "timestamp" | "entity" | "quantifier"
    text: str                 # the literal words in the claim
    grounded: bool = False
    detail: str = ""


class VerifiedClaim(BaseModel):
    """One claim after the hardening pass. The STATUS is the verifier's, always."""

    model_config = ConfigDict(extra="forbid")

    text: str
    status: ClaimStatus
    kind: ClaimKind = ClaimKind.FACT
    cited_record_ids: list[str] = Field(default_factory=list)
    #: The records THIS CLAIM was checked against — its own citations when it made
    #: any, the whole consulted set when it made none (which is the honest answer:
    #: an uncited claim really is checked against everything the loop read).
    #:
    #: Session 4B.5 CU5(d) FIXED A DEFECT HERE. This used to be the answer-level
    #: consulted list on EVERY claim, so the surface's "read from" line showed the
    #: same three record ids beside every interpretive sentence regardless of what
    #: each rested on — answer-level provenance wearing per-claim clothes.
    consulted_record_ids: list[str] = Field(default_factory=list)
    #: The TOOL CALLS whose results this claim's scope came from (Session 4B.5
    #: CU5(d)) — per claim, derived from which calls surfaced the records in
    #: ``consulted_record_ids``. This is the "read from" a planner actually means:
    #: not which record ids, but which readings of the plan.
    read_from: list[str] = Field(default_factory=list)
    assertions: list[Assertion] = Field(default_factory=list)
    reason: str = ""
    #: Set on an INTERPRETIVE claim whose quantifier could not be enumerated: the
    #: sample the claim actually rests on ("of the 13 late orders I examined").
    sample_note: str = ""
    #: True when cutting this claim would leave the answer without its conclusion or
    #: without any proven support — the "I couldn't ground part of my reasoning"
    #: trigger. Computed by the verifier over the whole draft, never by the model.
    load_bearing: bool = False


class SynthesisAnswer(BaseModel):
    """One hardened synthesis answer — the thing the surface renders (CU4)."""

    model_config = ConfigDict(extra="forbid")

    question: str
    claims: list[VerifiedClaim] = Field(default_factory=list)
    cut: list[VerifiedClaim] = Field(default_factory=list)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    budget_exhausted: bool = False
    timed_out: bool = False
    #: The honest floor: the model produced nothing usable, or everything failed.
    unanswerable: bool = False
    #: Micro-session 4A — the tier could not REACH its language model. A strictly
    #: different fact from `unanswerable`, which says the evidence did not carry
    #: an answer: here no evidence was ever read, because no reasoning ran. The
    #: surface renders the OUTAGE floor for this and the capability floor for the
    #: other, and they may never wear each other's words.
    model_unreachable: bool = False
    model: str = ""
    prompt_version: str = ""
    latency_ms: Optional[float] = None

    # -- readers the surface and the sidecar use ----------------------------

    @property
    def verified(self) -> list[VerifiedClaim]:
        return [c for c in self.claims if c.status is ClaimStatus.VERIFIED]

    @property
    def interpretive(self) -> list[VerifiedClaim]:
        return [c for c in self.claims if c.status is ClaimStatus.INTERPRETIVE]

    @property
    def general_knowledge(self) -> list[VerifiedClaim]:
        """R-TG1 — the claims labeled as domain knowledge rather than board reads.
        Counted separately from ``interpretive`` and never folded into it: an
        interpretive claim is a reading OF THIS PLAN that could not be proven, and
        a general-knowledge claim is not about this plan at all. Folding them
        would put the two back in the one bucket this class exists to split."""
        return [c for c in self.claims
                if c.status is ClaimStatus.GENERAL_KNOWLEDGE]

    @property
    def ungrounded_load_bearing(self) -> int:
        return sum(1 for c in self.cut if c.load_bearing)

    def counts(self) -> dict[str, int]:
        return {
            "claims": len(self.claims) + len(self.cut),
            "verified": len(self.verified),
            "interpretive": len(self.interpretive),
            "general_knowledge": len(self.general_knowledge),
            "failed_and_cut": len(self.cut),
            "ungrounded_load_bearing": self.ungrounded_load_bearing,
            "tool_calls": len(self.tool_calls),
        }


class SynthesisProvenance(BaseModel):
    """The per-claim provenance a question-ledger entry carries (CU1's logging
    requirement; the seed of R-AI5(5)'s telemetry, whose Pareto/promotion loop is
    4A.5c). Counts and labels only — never the schedule evidence store."""

    model_config = ConfigDict(extra="forbid")

    claims: list[dict] = Field(default_factory=list)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    budget_exhausted: bool = False
    unanswerable: bool = False

    @classmethod
    def of(cls, answer: SynthesisAnswer) -> "SynthesisProvenance":
        # ``kind`` rides from Session 4A.5c: the provenance report has to tell a
        # cluster whose residue is FACTS the tools could ground (promotable) from
        # one whose residue is CONCLUSIONS (a take, protected by R-AI5(6)), and
        # status alone cannot — an interpretive fact and an interpretive
        # conclusion wear the same label for different reasons.
        return cls(
            claims=[{"text": c.text, "status": c.status.value,
                     "kind": c.kind.value,
                     "record_ids": c.cited_record_ids,
                     # Session 4B.5 CU5(d): the ledger carries PER-CLAIM
                     # provenance — which records this sentence was checked
                     # against and which tool calls surfaced them. Before this it
                     # carried the claim's own citations beside an answer-level
                     # consulted set, so the durable record could not tell what
                     # any one sentence rested on.
                     "consulted": c.consulted_record_ids,
                     "read_from": c.read_from,
                     "load_bearing": c.load_bearing}
                    for c in (list(answer.claims) + list(answer.cut))],
            tool_calls=list(answer.tool_calls),
            budget_exhausted=answer.budget_exhausted,
            unanswerable=answer.unanswerable,
        )
