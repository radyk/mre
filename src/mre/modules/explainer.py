"""M10 — Explainer.

Strictly read-only: this module has no import of Reporter or SnapshotWriter.
It assembles ExplanationBundles from the evidence index and snapshot store,
then renders them via TemplateRenderer (all tests) or LLMRenderer (--llm flag).

Entry points:
  explainer.answer("Why is WO-2001 late?")         -> ExplanationBundle
  explainer.summarize_run()                          -> ExplanationBundle
  explainer.snapshot_diff("snap-v1", "snap-v2")     -> dict

Keyword routing (no NLU, no embeddings):
  "late"           + WO ref  -> _explain_why_late
  "on" / "assign"  + WO+M    -> _explain_why_on_machine
  "data problem" / "finding" -> _explain_data_problems
  "changed" / "diff"         -> _explain_what_changed (snapshot diff)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mre.modules.evidence_index import EvidenceIndex
from mre.modules.capabilities import (
    CAPABILITIES, coaching_concept, coaching_intent, is_capability_question,
    note_for_concept, wants_capability,
)
from mre.modules.planner_language import (
    compose_finding_sentence, driver_phrase, driver_hedge,
)

# The fallback menu shown when a question doesn't route. Worded in the PLANNER'S
# language — "an order", "a machine", "a customer" — never the developer's
# id-shapes (WO-XXXX / M-YYYY / snap-a vs snap-b). Router capabilities are
# unchanged; this is wording only (CU4). _planner_routes() below substitutes a
# real order / machine from the loaded schedule where one is cheaply available.
_SUPPORTED_ROUTES = [
    'why is an order late — the lateness cause chain',
    'are there any late orders — every late order at a glance',
    'why is an order on a machine — the assignment reason',
    "what's running on a machine — that machine's schedule",
    "what's next on a machine — its upcoming jobs",
    'when does an order start or finish — one order\'s schedule',
    'schedule for a customer — every job for that customer',
    'how much downtime a machine has — its calendar closures',
    'what data problems exist — data-quality findings',
    'what changed between two schedule versions — a version diff',
    'show the full schedule — everything, machine by machine',
]

_SCHEDULE_TRIGGERS = frozenset({
    "schedule", "scheduled", "running on", "next on",
    "when does", "when will", "when is",
    "when start", "when finish", "when complete",
    "start on", "finish on",
})

# Optimality / quality phrasings (4A.1c). "is there a BETTER schedule" contains the
# bare word "schedule" and would otherwise route to the schedule LISTING and answer
# with prose — but it asks whether a cheaper/better plan EXISTS, a re-optimization
# question the deterministic surface cannot answer. When present, the schedule
# listing route is suppressed so the question falls through to the interpreter /
# honest refusal-bridge, never a listing masquerading as an answer.
_OPTIMALITY_TRIGGERS = frozenset({
    "better", "best", "optimal", "improve", "improvement", "cheaper", "cheapest",
    "worse", "suboptimal", "more efficient",
})

# External-ref types that name an order / a machine across the three adapter
# vocabularies (sample ERP, raw_data, IDS). The explainer routes questions in
# the CUSTOMER'S vocabulary by matching against the identity map — never by
# assuming an id shape.
_ORDER_REF_TYPES = frozenset({"work_order", "order_id"})
_MACHINE_REF_TYPES = frozenset({"machine_id", "resource_id", "workcenter", "workcenter_id"})

# Certificate question domain (handoff §4). Three registers:
#   testimony  — "why rejected?" / "what's wrong?"  (findings, evidence)
#   remediation — "how do I fix it?"                 (authored catalog guidance)
#   judgment   — "what should I fix first?" / "does this matter?" (grade triage)
_CERT_TESTIMONY_TRIGGERS = (
    "what's wrong", "whats wrong", "what is wrong", "went wrong",
    "why reject", "why was it reject", "why was this reject", "why rejected",
    "certificate", "why conditional", "why was it conditional",
)
_TRIAGE_TRIGGERS = (
    "fix first", "what to fix first", "prioriti", "does this matter",
    "does it matter", "what matters", "worth fixing", "most important",
    "which first", "biggest problem",
)
_REMEDIATION_TRIGGERS = ("how do i fix", "how to fix", "how do we fix",
                         "how can i fix", "remediat", "how do i resolve",
                         "how to resolve")
# The excluded-orders story (Session 4.5 CU4): which orders were dropped from
# the plan and why — enumerated from ALL layers (gate, adapter, validator), so
# the certificate conversation is never blinder than dq_report.md.
_EXCLUDED_ORDERS_TRIGGERS = ("exclud", "left out", "dropped from the plan",
                             "which orders were left", "left off the plan",
                             "what was left out", "orders were dropped")

# The sandbox/edit question domain (Phase 3 CU2) — over the planner_edit
# Decisions an accepted edit records (docs/02 planner_edit, basis=observed).
# "summarize what I changed and what it cost" is the demo's closing beat; the
# cost question decomposes one edit's delta (production/setup/tardiness Δ). These
# are checked BEFORE the snapshot-diff "changed" route so edit phrasing routes
# here, not into a version diff.
_EDIT_SUMMARY_TRIGGERS = (
    "my changes", "my edits", "did i change", "did i do", "i changed",
    "i've changed", "changes i made", "edits i made", "what i changed",
    "this session", "summarize my", "summarise my",
)
_EDIT_COST_TRIGGERS = (
    "this move cost", "this edit cost", "that cost", "cost of this",
    "cost of my", "cost of the edit", "cost of the move", "why does this cost",
    "why does this move cost", "what did this cost", "what did that cost",
    "what did this move cost", "why does that cost", "why so expensive",
)

# The meta-route (Session 4A.1 CU3 / R-AI1(d)): the ledger answering questions
# ABOUT itself — "what questions couldn't you answer recently?". Checked first in
# classify() so this exact phrasing never falls into the schedule/diff handlers.
_LEDGER_TRIGGERS = (
    "couldn't you answer", "couldn't answer", "could not answer",
    "questions you can't answer", "questions you cannot answer",
    "what couldn't you", "unanswered questions", "what have you refused",
    "what did you refuse", "recent refusals",
)

# Session 4A.2 route families (CU5) + the morning briefing (CU7) + drill-down
# (CU3). Checked in classify() BEFORE the broad late/schedule handlers so a
# differently-SHAPED question about a resolved order (the audit's answer-the-noun
# defect) reaches its own route, not late-order.
_BRIEFING_TRIGGERS = (
    "worry about", "worry about today", "what should i worry", "morning briefing",
    "briefing", "what needs my attention", "what's on fire", "whats on fire",
    "what should i look at", "start my day",
)
_INVENTORY_TRIGGERS = (
    "how many order", "how many job", "how many operation", "how many op",
    "number of order", "number of job", "count of", "how many are there",
    "any split", "split job", "any splits", "are there splits", "which orders split",
    "how many total", "total number", "jobs in total", "orders in total",
)
_INTEGRITY_TRIGGERS = (
    "double book", "double-book", "doublebook", "same machine at the same time",
    "same time on the same machine", "overlap", "conflict", "two orders at once",
    "running at the same time", "at the same time",
)
# Attribute lookups (the hover card, askable): product / quantity / customer /
# due. NB these are checked only WITH a resolved order — a bare "what's the due
# date" with no order falls through.
_ATTRIBUTE_TRIGGERS = (
    "what product", "which product", "what part", "which part", "what item",
    "what customer", "which customer", "who is the customer", "whose order",
    "what quantity", "what qty", "how many units", "how many pieces", "how much of",
    "what's the due", "whats the due", "what is the due", "due date for",
    "when is it due", "when's it due", "release date", "what are the details",
    "tell me about", "details of", "details for", "info on", "attributes",
)
# Drill-down (CU3): open the full finding / record behind a citation.
_DRILLDOWN_TRIGGERS = (
    "tell me more", "more about", "more detail", "expand on", "expand that",
    "the full finding", "full record", "show the record", "what's the record",
    "elaborate", "go deeper", "dig into", "unpack",
)
# Start-reason (CU5 release/due reasoning + CU4 blocked-by): why an order starts
# when it does / why it can't start earlier.
_START_REASON_TRIGGERS = (
    "why does", "why is", "start earlier", "start sooner", "begin earlier",
    "why start", "why does it start", "start on", "why so late to start",
    "cant we start", "can't we start", "cannot start", "cant start", "can't start",
)

# CU2 (Session 4B.4) — RECOMMENDATION / ADVICE shape. The founder asked four ways
# "what should I do about lateness" ("would you recommend overtime …", "what
# should i do so those orders are not late", "if i open up hours what machines
# should i run", "how i can avoid late orders") and each got the are-there-late-
# orders STATUS RECITAL — confident, cited, wrong-question, three times. Advice-
# seeking phrasings route to an HONEST SCOPING answer (what the product CAN do
# today + that intervention recommendation is not a supported question yet), never
# a status recital. Checked BEFORE the late/schedule branches (the phrasings
# contain "late" / "machines" / "run"), AFTER triage/remediation/briefing (so
# "what should I fix first" / "what should I worry about" keep their own routes).
_ADVICE_TRIGGERS = (
    "recommend", "would you recommend", "do you recommend", "suggest",
    "what should i do", "what do i do", "what can i do",
    "how can i avoid", "how do i avoid", "how i can avoid", "how i avoid",
    "how can i prevent", "how do i prevent", "how to avoid", "avoid late",
    "prevent late", "reduce late", "less late", "fewer late", "not be late",
    "keep them on time", "make them on time", "get them on time",
    "if i open", "if i add", "if i run", "if i change", "if i turn on",
    "open up hours", "add hours", "add overtime", "run overtime",
    "what machines should i", "which machines should i", "what should i run",
    "how can i improve", "how do i improve", "what would you do",
)

# CU3 (Session 4B.4) — cheap META routes that are pure document/evidence reads,
# plus maintenance/calendar shape-recognition. Checked BEFORE the bare-"schedule"
# listing branch, because "how long did this SCHEDULE take to solve" and "is there
# any maintenance SCHEDULED" both contain a schedule trigger and were misrouting to
# the listing (the category-error insult "I don't see any scheduled operations").
_SOLVE_TIME_TRIGGERS = (
    "how long did", "how long to solve", "solve time", "time to solve",
    "how long did it take", "how long did this take", "how long did the solve",
    "take to solve", "took to solve", "solving take", "how fast did",
    "how long to build", "wall time", "how long did the run",
)
_MACHINE_LIST_TRIGGERS = (
    "how many machines", "how many resources", "how many work center",
    "how many workcenter", "list the machines", "list machines",
    "what machines are there", "which machines are there", "number of machines",
    "how many machine", "list the resources", "what resources", "name the machines",
    "does this schedule use workcenter", "use workcenters", "using workcenters",
    "what work centers", "which work centers",
)
_MAINTENANCE_TRIGGERS = (
    "maintenance", "any maintenance", "is there maintenance", "planned maintenance",
    "shift pattern", "shifts", "off-shift", "off shift", "shift schedule",
    "which shifts", "what shifts", "calendar", "working hours", "operating hours",
)

# CU6 (Session 4A.3-pre / R-AI3(4)) — the sycophancy guard. A CONTEST marker
# signals the user is pushing back on a cited fact; a STATUS word says the fact
# under dispute is on-time/late/early. Together (with an order ref) they route to
# the warm-evidence restatement, which never folds and never hardens.
_CONTEST_MARKERS = (
    "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt", "weren't", "werent",
    "are you sure", "you sure", "you're wrong", "youre wrong", "that's wrong",
    "thats wrong", "you are wrong", "i thought", "thought it was", "thought it wa",
    "supposed to be", "no way", "can't be", "cant be", "cannot be", "surely",
    "shouldn't it be", "shouldnt it be", "but it's", "but its",
)
_STATUS_WORDS = ("on time", "on-time", "late", "early", "not late", "fine",
                 "on schedule", "ahead")


# CU5 (Session 4A.3-pre) — the hypothesis-content guard. An intervention
# STATEMENT — a conditional/hypothetical about changing the plant or the
# submission ("maybe if splitting were allowed fewer orders would be late",
# "overtime would probably help") — is advice CONTENT, not a status question. The
# 4B.4 advice guard covered advice PHRASINGS (interrogatives); this covers advice
# CONTENT (a hypothesis wearing a declarative shape) so it never keyword-matches
# "late" into the status recital. A hypothesis = a conditional/speculative marker
# AND a plant/outcome word (so a plain "the order is late" is not swept in).
# Deliberately NOT bare "would fix/help/reduce/make" — "and what would fix it?" is
# an ellipsis follow-up, not an intervention hypothesis. A hypothesis is a
# CONDITIONAL about changing the plant ("maybe if …", "if we added …") or a hedged
# suggestion ("… would probably help").
_HYPOTHESIS_MARKERS = (
    "maybe if", "what if", "if i ", "if we ", "if you ", "if splitting",
    "if overtime", "if i open", "if we open", "if i add", "if we add",
    "would probably", "probably help", "probably reduce", "probably fix",
    "i bet", "i think it would", "i think that would", "might help",
    "might reduce", "might fix", "if i allow", "if we allow", "if allowed",
    "were allowed", "was allowed",
)
_HYPOTHESIS_OUTCOMES = (
    "late", "on time", "fewer", "less", "reduce", "help", "better", "faster",
    "improve", "avoid", "prevent", "fix", "catch up", "make the due",
)


def _is_hypothesis(q: str) -> bool:
    """True when the question is an intervention HYPOTHESIS (a conditional/
    speculative statement about changing the plant or submission), not a status
    question — so it routes to advice/coaching, never a status recital (CU5)."""
    if not any(m in q for m in _HYPOTHESIS_MARKERS):
        return False
    return any(o in q for o in _HYPOTHESIS_OUTCOMES)


# CU1 (Session 4A.3) — SWAP / MOVE intent (the flagship). "why not just swap X and
# Y", "switch X and Y", "move X earlier / to M". The answer bridges to the board
# gesture — the two-beat sandbox prices the drag — never a status recital.
_SWAP_MARKERS = ("swap", "switch", "trade place", "trade the", "exchange",
                 "flip the order", "put them in the other")
_MOVE_MARKERS = ("move ", "put ", "shift ", "relocate", "reassign", "reschedule ",
                 "give it an earlier", "give it the earlier")


def _swap_move_kind(q: str) -> Optional[str]:
    """'swap' when the question proposes exchanging two jobs' slots, 'move' when it
    proposes relocating one, else None. The caller enforces the order count (swap
    needs two, move one)."""
    if any(m in q for m in _SWAP_MARKERS):
        return "swap"
    if any(m in q for m in _MOVE_MARKERS):
        return "move"
    return None


# CU2 (Session 4A.3) — the absence-explaining pair, promoted from named debt.
#   gap-between  — "why is there a gap / slack between X and Y", "why not run X
#                  right after Y": resolve the gap on the shared machine, name its
#                  CAUSE (occupancy / closure / upstream gate), or report honestly.
#   machine-idle — "why is M unused / idle": eligibility + where the work went.
_GAP_MARKERS = (
    "gap between", "slack between", "space between", "time between", "why not run",
    "right after", "straight after", "just after", "back to back", "back-to-back",
    "immediately after", "why the gap", "why is there a gap", "why is there slack",
    "why the space", "why isn't it right after", "why not right after",
    "why is there space", "gap before", "why is there a delay between",
)
_IDLE_MARKERS = (
    "unused", "not used", "not being used", "sitting idle", "idle",
    "doing nothing", "no jobs on", "nothing on", "no work on", "empty",
    "not doing anything", "why is nothing running on", "carrying no work",
    "why isn't anything on", "why are there no jobs on", "no jobs running on",
)


# The route taxonomy — the closed set of route ids classify()/route() dispatch
# over (docs/07 Phase 4, R-AI1(b)). The interpreter (CU1) maps free-form phrasing
# ONLY onto these ids; it never invents a route. `params` names the external-ref
# slots a route needs (resolved through the identity map, never an id-shape).
# `canonical` is the planner-vocabulary question the interpreter's route+params
# synthesize into — re-parsed by the same assemblers, so identity resolution
# stays inside (the Phase-1 audit lesson).
ROUTE_TAXONOMY: dict[str, dict] = {
    "late-order":            {"params": ["order"],   "canonical": "why is {order} late?"},
    "late-orders":           {"params": [],          "canonical": "which orders are late?"},
    "why-on-machine":        {"params": ["order", "machine"],
                              "canonical": "why is {order} on {machine}?"},
    "machine-schedule":      {"params": ["machine"], "canonical": "what is running on {machine}?"},
    "order-schedule":        {"params": ["order"],   "canonical": "when does {order} start and finish?"},
    "customer-schedule":     {"params": ["customer"],
                              "canonical": "show the schedule for customer {customer}"},
    "downtime":              {"params": ["machine"], "canonical": "how much downtime does {machine} have?"},
    "data-problems":         {"params": [],          "canonical": "what data problems exist?"},
    "version-diff":          {"params": [],          "canonical": "what changed between the two versions?"},
    "remediation":           {"params": [],          "canonical": "how do I fix the submission's problems?"},
    "triage":                {"params": [],          "canonical": "what should I fix first?"},
    "certificate-testimony": {"params": [],          "canonical": "what is wrong with the submission?"},
    "excluded-orders":       {"params": [],          "canonical": "which orders were excluded from the plan?"},
    "edit-summary":          {"params": [],          "canonical": "summarize my changes and what they cost"},
    "edit-cost":             {"params": [],          "canonical": "what did this move cost?"},
    "ledger-refusals":       {"params": [],          "canonical": "what questions couldn't you answer recently?"},
    # Session 4A.2 — the missing route families (CU5), the relevance guard's
    # honest destinations (CU1), drill-down (CU3), and the morning briefing (CU7).
    "order-attributes":      {"params": ["order"],   "canonical": "what are the details of {order}?"},
    "inventory":             {"params": [],          "canonical": "how many orders are in the plan?"},
    "integrity-check":       {"params": ["machine"], "canonical": "is anything double-booked?"},
    "start-reason":          {"params": ["order"],   "canonical": "why does {order} start when it does?"},
    "drill-down":            {"params": [],          "canonical": "tell me more about that"},
    "briefing":              {"params": [],          "canonical": "what should I worry about today?"},
    "unknown-entity":        {"params": ["order"],   "canonical": "is {order} in this schedule?"},
    # Session 4A.3-pre CU6 — the sycophancy guard: the user contests a cited fact.
    "contested-fact":        {"params": ["order"],   "canonical": "is {order} really on time?"},
    # Session 4A.3 CU1 — the swap/move bridge (the flagship): reason over two orders'
    # slack/lateness and bridge to the board gesture the two-beat sandbox prices.
    "swap-move":             {"params": ["order"],
                              "canonical": "why not swap {order} with another order?"},
    # Session 4A.3 CU2 — the absence-explaining pair: the gap between two ops on a
    # shared machine, and why a machine carries no (or little) work.
    "gap-between":           {"params": ["order"],
                              "canonical": "why is there a gap before {order}?"},
    "machine-idle":          {"params": ["machine"],
                              "canonical": "why is {machine} idle?"},
    # Session 4B.4 — the advice/recommendation SCOPING route (CU2) and the cheap
    # meta routes (CU3): solve timing + machine listing are pure document/evidence
    # reads; maintenance is shape-recognized with an honest not-yet.
    "advice":                {"params": [],          "canonical": "what should I do about the late orders?"},
    # Session 4A.3-pre CU4 — the coaching/capability retrieval route: "how do I
    # enable X / does MRE support W". Answered from the authored capability
    # registry (capabilities.py) with a docs/06 § citation.
    "coaching":              {"params": [],          "canonical": "how do I enable that?"},
    "solve-time":            {"params": [],          "canonical": "how long did the solve take?"},
    "machine-count":         {"params": [],          "canonical": "how many machines are there?"},
    "maintenance":           {"params": [],          "canonical": "is any maintenance scheduled?"},
    # Session 4B.3c CU4 — the ROLLING (sliced-world) routes. Live only when the
    # schedule is a rolling document (the /ask path delegates to rolling_questions,
    # which answers from the document's RollingBlock — the connector-era snapshot a
    # rolling run now persists is what unblocks this). A closed set (ROLLING_ROUTES),
    # not an ad-hoc bolt: registered here so the ledger + interpreter recognize them.
    "beyond-horizon":        {"params": [],          "canonical": "what's beyond the horizon?"},
    "why-not-scheduled-yet": {"params": ["order"],   "canonical": "why isn't {order} scheduled yet?"},
    "frozen":                {"params": [],          "canonical": "what's frozen?"},
}


# The three answer registers (honesty armor): testimony (evidence/findings —
# "what is") · remediation (authored fix guidance) · judgment (triage — "what to
# do first"). THE SINGLE SOURCE OF TRUTH: the API metadata (the chip) AND the
# rendered footer (the envelope) both resolve through REGISTER_BY_SUBJECT, so the
# chip can never disagree with the envelope (Session 4A.2 CU6 — the register-tag
# seam). Enumerating findings ("what data problems exist") is TESTIMONY, not
# judgment — it states what is wrong and cites evidence; only triage ("what to
# fix first") is the judgment register. Add, never repurpose: a new subject type
# that belongs to remediation/judgment gets an entry here.
REGISTER_BY_SUBJECT: dict[str, str] = {
    "remediation": "remediation",
    "triage": "judgment",
}


def register_of(bundle: "ExplanationBundle") -> str:
    return REGISTER_BY_SUBJECT.get(getattr(bundle, "subject_type", "") or "",
                                   "testimony")


def canonical_question(route: str, params: Optional[dict] = None) -> str:
    """The planner-vocabulary question a route + resolved external-ref params
    synthesize into. The interpreter feeds this back through the deterministic
    assemblers, so external refs get re-resolved inside (no id-shape regex)."""
    spec = ROUTE_TAXONOMY.get(route)
    if spec is None:
        return (params or {}).get("question", "")
    params = params or {}
    try:
        return spec["canonical"].format(**{k: params.get(k, f"{{{k}}}") for k in
                                            ("order", "machine", "customer")})
    except (KeyError, IndexError):
        return spec["canonical"]


@dataclass
class ExplanationBundle:
    """Structured, renderer-agnostic answer to a question.

    ordered_records  — evidence records in pipeline order (M1 < M7)
    key_facts        — scalar summary used by renderers as the headline
    identity_map     — for resolving UUIDs to external names (WO-XXXX, M-GEAR-01)
    """
    question: str
    subject_id: str
    subject_type: str                        # "demand", "run", "diff", "findings"
    subject_external_name: str
    ordered_records: list[dict]
    key_facts: dict[str, Any]
    snapshot_id: str
    identity_map: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

class Explainer:
    """Read-only answer engine.  No write path."""

    def __init__(
        self,
        snapshot_store: Any,
        index: EvidenceIndex,
        snapshot_id: str = "snap-run",
    ) -> None:
        self._store = snapshot_store
        self._index = index
        self._snap_id = snapshot_id
        # A REJECTED submission never reaches the adapter, so no snapshot (and no
        # identity map) exists — but its gate findings are in the evidence store
        # and certificate questions must still answer. Operate in certificate-
        # only mode when the snapshot cannot be loaded (handoff §4/§7).
        try:
            self._reader = snapshot_store.load_snapshot(snapshot_id)
            self._identity_map = self._reader.read_identity_map()
        except (FileNotFoundError, NotADirectoryError):
            self._reader = None
            self._identity_map = None

        # Vocabulary bridges (Phase-1 exit audit fix): the router used to
        # recognize only sample_data-shaped ids (WO-…, M-…), so "why is
        # ORD-000090 late" misrouted on every IDS submission and the gauntlet.
        # The identity map already knows every external id in the customer's
        # own vocabulary — match against IT, with the legacy regexes kept
        # only as a fallback for snapshots without an identity map.
        self._order_refs: dict[str, str] = {}
        self._machine_refs: dict[str, str] = {}
        if self._identity_map is not None:
            for (sys_, ref_type, value), _cid in self._identity_map._to_canonical.items():
                if ref_type in _ORDER_REF_TYPES:
                    self._order_refs[value.upper()] = value
                elif ref_type in _MACHINE_REF_TYPES:
                    self._machine_refs[value.upper()] = value

        # The relevance guard's evidence (Session 4A.2 CU1). Two dataset-derived
        # vocabularies, both built from EVIDENCE (never an id-shape assumption):
        #   _excluded_labels    — order ids the gate/adapter/validator EXCLUDED,
        #                         from findings; a question naming one of these
        #                         gets the excluded answer, not a global one.
        #   _order_shape_patterns — the SHAPE of this submission's real order ids
        #                         (each known ref with its digit-runs generalized),
        #                         so a token that looks like an order of this
        #                         dataset but resolves to nothing is recognized as
        #                         a named-but-unresolvable entity (→ refuse), never
        #                         silently dropped into a schedule-wide answer.
        self._excluded_labels: set[str] = self._build_excluded_labels()
        self._order_shape_patterns: list[re.Pattern] = self._build_order_shapes()
        # Fuzzy-id tolerance (Session 4A.2b CU6): each real order ref compiled to
        # a pattern that also matches its near-miss spellings — a letter 'o' for a
        # zero (ord-o5), a missing leading zero (ORD-5), a space for the hyphen
        # (ord 05) — so a near-miss resolves (with a visible assumption) instead of
        # falling to the wrong route. Built from the learned refs, never assumed.
        self._order_fuzzy: list[tuple[re.Pattern, str]] = self._build_order_fuzzy()

    def _build_excluded_labels(self) -> set[str]:
        """Order ids excluded/blocked from the plan, from ANY layer's findings —
        the same evidence _explain_excluded_orders enumerates. Upper-cased for
        case-insensitive matching."""
        labels: set[str] = set()
        try:
            findings = self._index.all_findings()
        except Exception:
            return labels
        for f in findings:
            if f.get("disposition") not in ("excluded", "blocked"):
                continue
            ev = f.get("evidence", {}) or {}
            for cand in (ev.get("order_id"), ev.get("wono"), ev.get("demand_id")):
                if cand:
                    labels.add(str(cand).upper())
            for s in f.get("subjects", []) or []:
                sid = s.get("entity_id") if isinstance(s, dict) else ""
                if sid and self._identity_map is not None:
                    erefs = self._identity_map.external_refs(sid)
                    if erefs:
                        labels.add(erefs[0].value.upper())
        return labels

    def _build_order_shapes(self) -> list[re.Pattern]:
        """Generalize each known order ref into a shape pattern by replacing its
        digit runs with ``\\d+`` — so ``ORD-01`` yields ``^ORD-\\d+$``. A token
        matching a shape but resolving to nothing is a named-but-unresolvable
        order of THIS dataset (learned from the data, not an assumed id shape)."""
        shapes: set[str] = set()
        for value in self._order_refs.values():
            pat = re.sub(r"\d+", r"\\d+", re.escape(value).replace(r"\ ", " "))
            if any(ch.isalpha() for ch in value):  # ignore purely-numeric refs
                shapes.add(f"^{pat}$")
        return [re.compile(s, re.IGNORECASE) for s in sorted(shapes)]

    def _build_order_fuzzy(self) -> list[tuple[re.Pattern, str]]:
        """One tolerant pattern per real order ref: its alpha prefix, then an
        optional separator, then the numeric part with leading zeros optional and
        'o'/'0' interchangeable. So ``ORD-05`` also matches ``ORD-5`` / ``ord-o5``
        / ``ord 05``. Refs with no alpha prefix or no trailing number are skipped
        (nothing to disambiguate); a value collision drops both (never guess)."""
        out: list[tuple[re.Pattern, str]] = []
        by_key: dict[tuple[str, int], list[str]] = {}
        for value in self._order_refs.values():
            m = re.match(r"^(.*?)(\d+)$", value)
            if not m:
                continue
            prefix = m.group(1).rstrip(" -_")
            if not prefix or not prefix[-1].isalpha():
                continue
            num = int(m.group(2))
            by_key.setdefault((prefix.upper(), num), []).append(value)
        for (prefix_u, num), values in by_key.items():
            if len(values) != 1:
                continue  # two refs share prefix+value — ambiguous, never guess
            value = values[0]
            prefix = re.match(r"^(.*?)\d+$", value).group(1).rstrip(" -_")
            digits_re = "".join("[0oO]" if ch == "0" else re.escape(ch)
                                for ch in str(num))
            pat = re.compile(
                rf"\b{re.escape(prefix)}[\s\-_]?[0oO]*{digits_re}\b", re.IGNORECASE)
            out.append((pat, value))
        return out

    def rewrite_fuzzy_orders(self, question: str) -> tuple[str, list[tuple[str, str]]]:
        """Rewrite each near-miss order id in the question to its canonical ref,
        returning (new_question, [(matched_text, canonical_ref), …]). A token that
        already resolves EXACTLY is left alone (not a near-miss). The caller
        surfaces the assumption; an id matching nothing here is never rewritten."""
        new_q = question
        notes: list[tuple[str, str]] = []
        for pat, ref in self._order_fuzzy:
            m = pat.search(new_q)
            if not m:
                continue
            matched = m.group(0)
            if self._find_order_ref(matched):
                continue  # exact already — not a near-miss
            new_q = new_q[: m.start()] + ref + new_q[m.end():]
            notes.append((matched.strip(), ref))
        return new_q, notes

    def _order_mention(self, question: str) -> Optional[str]:
        """A token in the question that NAMES an order of this dataset but does
        NOT resolve to a scheduled demand — the signal to refuse/redirect rather
        than answer globally (CU1). Returns the raw token (as typed), or None.

        Evidence-first: an excluded-order label always counts. Otherwise the
        token must match this submission's learned order SHAPE and not be a known
        machine. Used ONLY to choose refuse-vs-global — never to resolve an id."""
        for tok in re.findall(r"[A-Za-z][\w./-]*\d[\w./-]*|[A-Za-z]+-\d[\w-]*", question):
            u = tok.upper().strip(".,?!")
            if u in self._order_refs or u in self._machine_refs:
                continue
            if u in self._excluded_labels:
                return tok.strip(".,?!")
            if any(p.match(u) for p in self._order_shape_patterns):
                return tok.strip(".,?!")
        return None

    def _find_order_ref(self, question: str) -> Optional[str]:
        """Return the external order id mentioned in the question, in the
        customer's own vocabulary, or None."""
        for tok in re.findall(r"[\w][\w./-]*", question):
            hit = self._order_refs.get(tok.upper().strip(".,?!"))
            if hit:
                return hit
        m = re.search(r'WO-[\w-]+', question, re.IGNORECASE)
        return m.group().upper() if m else None

    def _find_order_refs(self, question: str) -> list[str]:
        """Every distinct external order ref named in the question, in order of
        appearance — the swap/move + gap routes reason over TWO orders (CU1/CU2)."""
        out: list[str] = []
        for tok in re.findall(r"[\w][\w./-]*", question):
            hit = self._order_refs.get(tok.upper().strip(".,?!"))
            if hit and hit not in out:
                out.append(hit)
        return out

    def _find_machine_ref(self, question: str) -> Optional[str]:
        for tok in re.findall(r"[\w][\w./-]*", question):
            hit = self._machine_refs.get(tok.upper().strip(".,?!"))
            if hit:
                return hit
        m = re.search(r'M-[A-Z0-9-]+', question, re.IGNORECASE)
        return m.group().upper() if m else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, question: str) -> ExplanationBundle:
        """Route a natural-language question to the right assembler.

        The deterministic router IS the taxonomy (docs/07 Phase 4): classify()
        maps working phrasings onto a route id + params, route() dispatches. This
        split (Session 4A.1) makes the taxonomy callable by the interpreter (CU1)
        without changing any routing — answer() is exactly classify()+route()."""
        route_id, params = self.classify(question)
        return self.route(route_id, params)

    def classify(self, question: str) -> tuple[str, dict]:
        """Deterministic phrasing → (route id, params). No LLM, no cost. Returns
        ("unsupported", …) when nothing matches — the signal the orchestration
        uses to fall through to the interpreter (CU1). Branch order is preserved
        byte-for-byte from the pre-4A.1 router (zero regression)."""
        q = question.lower()
        wo_ref = self._find_order_ref(question)
        machine_ref = self._find_machine_ref(question)
        # The relevance guard's signal (CU1): did the planner NAME an order that
        # does not resolve here? If so, a global answer would be answering the
        # wrong thing — route to unknown-entity instead of the schedule-wide list.
        mention = None if wo_ref else self._order_mention(question)
        base = {"question": question, "order": wo_ref, "machine": machine_ref}

        # The meta-route first — "what couldn't you answer?" must not fall into
        # the schedule/diff handlers (R-AI1(d)).
        if any(t in q for t in _LEDGER_TRIGGERS):
            return "ledger-refusals", base

        # The morning briefing (CU7) — "what should I worry about today?". Before
        # triage so it isn't caught by a bare "what matters".
        if any(t in q for t in _BRIEFING_TRIGGERS):
            return "briefing", base

        # Certificate question domain (handoff §4) — before the schedule routes so
        # "how do I fix …" / "what should I fix first" never fall into schedule/
        # late handling. Judgment (triage) before remediation so "what should I
        # fix first" is not swallowed by the bare "fix" in the remediation
        # triggers.
        if any(t in q for t in _TRIAGE_TRIGGERS):
            return "triage", base
        if any(t in q for t in _REMEDIATION_TRIGGERS):
            limit = 1 if ("worst" in q or "top " in q or "the one" in q) else None
            return "remediation", {**base, "limit": limit}
        if any(t in q for t in _EXCLUDED_ORDERS_TRIGGERS):
            return "excluded-orders", base
        if any(t in q for t in _CERT_TESTIMONY_TRIGGERS):
            return "certificate-testimony", base

        # CU4 (Session 4A.3-pre) — coaching/capability retrieval. "how do I enable
        # X", "does MRE support W", "i want orders to span downtime, how" — a
        # capability question, answered from the authored registry with a § cite.
        # Checked BEFORE advice/downtime because the anchor ("span downtime") both
        # reads as advice-adjacent and contains "downtime" (which would otherwise
        # fall to the calendar route → the "No calendar closures for all" nonsense).
        # An intervention HYPOTHESIS that NAMES a config concept (CU5) — "maybe if
        # splitting were allowed fewer orders would be late" — routes here too: the
        # honest answer is how to enable that knob, not a lateness recital.
        _concept = coaching_concept(q)
        if (is_capability_question(q) or coaching_intent(q, _concept)
                or (_concept and _is_hypothesis(q))):
            return "coaching", {**base, "concept": _concept}

        # CU2 (Session 4B.4) — advice/recommendation SCOPING. Before the edit/late/
        # schedule branches so an advice-seeking phrasing ("would you recommend
        # overtime …", "what should i do so those orders are not late") never lands
        # on the late-orders status recital. After triage/remediation/briefing so
        # "what should I fix first"/"what should I worry about" keep their routes.
        # CU5 (Session 4A.3-pre) — an intervention HYPOTHESIS with no named config
        # concept ("overtime would probably help") is advice CONTENT, not a status
        # question: route it here by SHAPE, never keyword-match "late" into a recital.
        if any(t in q for t in _ADVICE_TRIGGERS) or _is_hypothesis(q):
            return "advice", base

        # The sandbox/edit question domain (3.4 CU2) — before schedule/diff.
        if any(t in q for t in _EDIT_COST_TRIGGERS):
            return "edit-cost", base
        if any(t in q for t in _EDIT_SUMMARY_TRIGGERS):
            return "edit-summary", base

        # Drill-down (CU3) — "tell me more about that/finding N/record X". Before
        # attributes so "tell me more" is not read as a "tell me about" lookup.
        if any(t in q for t in _DRILLDOWN_TRIGGERS):
            return "drill-down", {**base, "target": question}

        # Integrity check (CU5) — "double-booked?", "same machine at the same
        # time?". Before schedule so "running at the same time" is not a listing.
        if any(t in q for t in _INTEGRITY_TRIGGERS) or (
                "same machine" in q and "same time" in q):
            return "integrity-check", base

        # Inventory (CU5) — counts and splits. No order needed.
        if any(t in q for t in _INVENTORY_TRIGGERS):
            return "inventory", base

        # Attribute lookup (CU5, the hover card askable): the audit's
        # answer-the-noun defect — "what product is ORD-01" must reach product,
        # not late-order. Only fires with a RESOLVED order (a differently-shaped
        # question about a real order); a named-but-unresolvable order falls to
        # the relevance guard below.
        if wo_ref and any(t in q for t in _ATTRIBUTE_TRIGGERS):
            return "order-attributes", base
        if mention and any(t in q for t in _ATTRIBUTE_TRIGGERS):
            return "unknown-entity", {**base, "mention": mention}

        # Start-reason (CU5 release/due + CU4 blocked-by) — "why does X start on
        # Friday", "why can't X start earlier". Requires a start/earlier signal so
        # it never swallows "why is X on M" (that stays why-on-machine).
        _start_sig = any(w in q for w in
                         ("start", "begin", "earlier", "sooner", "kick off"))
        if wo_ref and _start_sig and ("why" in q or "cant" in q or "can't" in q
                                      or "cannot" in q):
            return "start-reason", base
        if mention and _start_sig and "why" in q:
            return "unknown-entity", {**base, "mention": mention}

        # CU6 (Session 4A.3-pre / R-AI3(4)) — the sycophancy guard. A user CONTESTS
        # a cited fact ("isn't ORD-05 on time?", "surely ORD-05 isn't late"). Meet
        # it with warm EVIDENCE, never capitulation and never a curt re-assertion.
        # Checked before the late/order-schedule branches so the contradiction is
        # answered as a contest, not a bare schedule listing. Requires an order ref,
        # a contest marker, and a status claim (on-time / late / early).
        if (wo_ref and any(m in q for m in _CONTEST_MARKERS)
                and any(s in q for s in _STATUS_WORDS)):
            return "contested-fact", base

        # CU1 (Session 4A.3) — the swap/move bridge. Before the late/why-on-machine/
        # schedule branches so "why not swap X and Y" / "move X earlier" never fall
        # into a status recital. A swap needs two resolved orders; a move needs one.
        order_refs = self._find_order_refs(question)
        sm_kind = _swap_move_kind(q)
        if sm_kind == "swap" and len(order_refs) >= 2:
            return "swap-move", {**base, "order_a": order_refs[0],
                                 "order_b": order_refs[1], "kind": "swap"}
        if sm_kind == "move" and order_refs:
            return "swap-move", {**base, "order_a": order_refs[0],
                                 "order_b": order_refs[1] if len(order_refs) >= 2 else None,
                                 "kind": "move"}
        # CU2 (Session 4A.3) — the absence pair. gap-between needs an order (or a
        # machine) + a gap marker; machine-idle needs a machine + an idle marker.
        if any(g in q for g in _GAP_MARKERS) and (order_refs or machine_ref):
            return "gap-between", {**base,
                                   "order_a": order_refs[0] if order_refs else None,
                                   "order_b": order_refs[1] if len(order_refs) >= 2 else None}
        if any(w in q for w in _IDLE_MARKERS) and machine_ref:
            return "machine-idle", base

        if ("late" in q or "delay" in q or "tardy" in q) and wo_ref:
            return "late-order", base
        if ("late" in q or "delay" in q or "tardy" in q) and mention:
            return "unknown-entity", {**base, "mention": mention}
        if ("late" in q or "delay" in q or "tardy" in q) and not wo_ref:
            return "late-orders", base
        if ("on" in q or "assign" in q or "why" in q) and wo_ref and machine_ref:
            return "why-on-machine", base
        if "data problem" in q or "finding" in q or "quality" in q:
            return "data-problems", base
        # Word-boundary match (CU6): the pre-4A.2 substring test fired
        # `"diff" in "different"`, sending "move it to a DIFFerent machine" to a
        # nonsense self-diff. Match whole words only.
        if re.search(r"\b(diff|difference|changed|since|updated?)\b", q) or (
                "what changed" in q or "version" in q):
            return "version-diff", base
        if "downtime" in q or "closure" in q or "offline" in q:
            return "downtime", base
        # CU3 (Session 4B.4) — cheap meta reads + maintenance shape, BEFORE the
        # bare-"schedule" listing branch (these phrasings contain "schedule"/
        # "scheduled"/"machines" and were misrouting to the listing → the
        # category-error "I don't see any scheduled operations" insult).
        if any(t in q for t in _SOLVE_TIME_TRIGGERS):
            return "solve-time", base
        if any(t in q for t in _MACHINE_LIST_TRIGGERS):
            return "machine-count", base
        if any(t in q for t in _MAINTENANCE_TRIGGERS):
            return "maintenance", base
        if any(kw in q for kw in _SCHEDULE_TRIGGERS) and not any(
                kw in q for kw in _OPTIMALITY_TRIGGERS):
            return "schedule", base
        # A bare order with no other shape → its own schedule (start/finish),
        # never a lateness verdict it did not ask for (CU1 answer-the-noun).
        if wo_ref:
            return "order-schedule", base
        # A named-but-unresolvable order with no other shape → the honest
        # unknown/excluded answer, never a schedule-wide fallback (CU1).
        if mention:
            return "unknown-entity", {**base, "mention": mention}
        return "unsupported", base

    def route(self, route_id: str, params: dict) -> ExplanationBundle:
        """Dispatch a route id + params to its assembler. The single dispatch
        both the deterministic router and the interpreter (CU1) go through."""
        q = params.get("question", "")
        if route_id == "ledger-refusals":
            return self._explain_recent_refusals(params.get("refusals", []))
        if route_id == "triage":
            return self._explain_fix_first(q)
        if route_id == "remediation":
            return self._explain_how_to_fix(q, params.get("limit"))
        if route_id == "certificate-testimony":
            return self._explain_data_problems(entity_ref=params.get("order"))
        if route_id == "excluded-orders":
            return self._explain_excluded_orders(q)
        if route_id == "briefing":
            return self._explain_briefing(q)
        if route_id == "advice":
            return self._explain_advice(q)
        if route_id == "coaching":
            return self._explain_coaching(q, params.get("concept"))
        if route_id == "solve-time":
            return self._explain_solve_time(q)
        if route_id == "machine-count":
            return self._explain_machine_count(q)
        if route_id == "maintenance":
            return self._explain_maintenance(q)
        if route_id == "inventory":
            return self._explain_inventory(q)
        if route_id == "integrity-check":
            return self._explain_integrity(q, params.get("machine"))
        if route_id == "order-attributes":
            return self._explain_order_attributes(params.get("order"))
        if route_id == "start-reason":
            return self._explain_start_reason(params.get("order"), q)
        if route_id == "contested-fact":
            return self._explain_contested(params.get("order"), q)
        if route_id == "swap-move":
            return self._explain_swap_move(params.get("order_a") or params.get("order"),
                                           params.get("order_b"),
                                           params.get("kind", "swap"), q)
        if route_id == "gap-between":
            return self._explain_gap(params.get("order_a") or params.get("order"),
                                     params.get("order_b"), params.get("machine"), q)
        if route_id == "machine-idle":
            return self._explain_machine_idle(params.get("machine"), q)
        if route_id == "drill-down":
            return self._explain_drill_down(params.get("target", q),
                                            params.get("history"))
        if route_id == "unknown-entity":
            return self._explain_unknown_entity(
                params.get("mention") or params.get("order") or q)
        if route_id == "edit-cost":
            return self._explain_edit_cost(q)
        if route_id == "edit-summary":
            return self._summarize_edits(q)
        if route_id == "late-order":
            return self._explain_why_late(params["order"])
        if route_id == "late-orders":
            return self._list_late_orders()
        if route_id == "why-on-machine":
            return self._explain_why_on_machine(params["order"], params["machine"])
        if route_id == "data-problems":
            return self._explain_data_problems()
        if route_id == "version-diff":
            return self._explain_what_changed(q)
        if route_id == "downtime":
            return self._explain_downtime(q)
        if route_id in ("schedule", "machine-schedule", "order-schedule",
                        "customer-schedule"):
            return self._schedule_query(q, q.lower(), params.get("order"),
                                        params.get("machine"))
        if route_id == "near-miss":
            return self._near_miss(q, params.get("offers", []),
                                   params.get("routes", []))
        if route_id == "clarify":
            return self._clarify(q, params.get("reason", ""))
        return self._unknown_question(q)

    # ------------------------------------------------------------------
    # External-ref param resolution (CU1) — external refs in, canonical
    # resolution inside; never an id-shape regex (Phase-1 audit lesson).
    # ------------------------------------------------------------------

    def resolve_order_value(self, raw: str) -> Optional[str]:
        """Resolve a free-form order phrase to a known external order ref
        (the customer's own vocabulary), or None. Exact-token first, then a
        unique substring match against the identity map's order refs."""
        if not raw:
            return None
        key = raw.upper().strip(" .,?!")
        if key in self._order_refs:
            return self._order_refs[key]
        hits = [v for k, v in self._order_refs.items() if key in k or k in key]
        return hits[0] if len(hits) == 1 else None

    def resolve_machine_value(self, raw: str) -> Optional[str]:
        """Resolve a free-form machine phrase ("the big press") to a known
        external machine ref, or None. Exact-token, then unique substring."""
        if not raw:
            return None
        key = raw.upper().strip(" .,?!")
        if key in self._machine_refs:
            return self._machine_refs[key]
        hits = [v for k, v in self._machine_refs.items() if key in k or k in key]
        return hits[0] if len(hits) == 1 else None

    def summarize_run(self, run_id: Optional[str] = None) -> ExplanationBundle:
        """High-level run summary: notable decisions + findings + late demands."""
        if run_id is None:
            # Most recent M7 run
            m7_runs = [r for r in self._index.runs() if r.get("module") == "M7"]
            if m7_runs:
                run_id = sorted(
                    m7_runs, key=lambda r: r.get("timestamp_close", "")
                )[-1]["run_id"]
            else:
                run_id = "unknown"

        all_ev = self._index._all_evidence
        run_records = [r for r in all_ev if r.get("run_id") == run_id]

        notable_decisions = [
            r for r in run_records
            if r.get("record_type") == "decision"
            and r.get("driver") in ("SETUP_AMORTIZATION", "CALENDAR_WINDOW", "DEMAND_MERGE")
        ]
        affecting_findings = [
            r for r in run_records
            if r.get("record_type") == "finding"
            and r.get("disposition") in ("defaulted", "excluded", "blocked")
        ]
        late_metrics = [
            r for r in run_records
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]

        ordered = sorted(
            notable_decisions + affecting_findings + late_metrics,
            key=lambda r: (
                {"M1": 1, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "M7": 7}.get(
                    r.get("module", ""), 9
                ),
                r.get("seq", 0),
            ),
        )

        return ExplanationBundle(
            question="Run summary",
            subject_id=run_id,
            subject_type="run",
            subject_external_name=run_id[:12] if run_id else "?",
            ordered_records=ordered,
            key_facts={
                "run_id": run_id,
                "notable_decision_count": len(notable_decisions),
                "affecting_finding_count": len(affecting_findings),
                "late_demand_count": len(late_metrics),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def snapshot_diff(self, snap_id_a: str, snap_id_b: str) -> dict:
        """Entity-level diff between two snapshots.

        Returns:
          added_demands    — WO external refs present in b but not a
          removed_demands  — WO external refs present in a but not b
          changed_demands  — [{work_order, field, from, to}, ...]
          costmodel_diff   — {version_a, version_b, rate_changes: {name: {from, to}}}
        """
        reader_a = self._store.load_snapshot(snap_id_a)
        reader_b = self._store.load_snapshot(snap_id_b)
        im_a = reader_a.read_identity_map()
        im_b = reader_b.read_identity_map()

        def _wo_map(reader) -> dict[str, dict]:
            result: dict[str, dict] = {}
            for d in reader.iter_entities("demand"):
                wo = next(
                    (r.get("value") for r in d.get("external_refs", [])
                     if r.get("type") == "work_order"),
                    None,
                )
                if wo:
                    result[wo] = d
            return result

        demands_a = _wo_map(reader_a)
        demands_b = _wo_map(reader_b)

        added = sorted(set(demands_b) - set(demands_a))
        removed = sorted(set(demands_a) - set(demands_b))

        changed: list[dict] = []
        for wo in sorted(set(demands_a) & set(demands_b)):
            d_a = demands_a[wo]
            d_b = demands_b[wo]
            for fld in ("due", "quantity", "commitment_class"):
                v_a = d_a.get(fld)
                v_b = d_b.get(fld)
                if v_a != v_b:
                    changed.append({"work_order": wo, "field": fld, "from": v_a, "to": v_b})

        # CostModel version diff
        costmodel_diff: dict = {}
        cms_a = list(reader_a.iter_entities("costmodel"))
        cms_b = list(reader_b.iter_entities("costmodel"))
        if cms_a and cms_b:
            cm_a = cms_a[0]
            cm_b = cms_b[0]
            rates_a: dict[str, float] = cm_a.get("resource_rates", {})
            rates_b: dict[str, float] = cm_b.get("resource_rates", {})
            rate_changes: dict[str, dict] = {}
            all_ids = set(rates_a) | set(rates_b)
            for rid in all_ids:
                r_a = rates_a.get(rid)
                r_b = rates_b.get(rid)
                if r_a != r_b:
                    # Resolve canonical UUID to machine_id for readability
                    name = rid
                    if im_a:
                        refs = im_a.external_refs(rid)
                        mname = next((r.value for r in refs if r.type == "machine_id"), None)
                        if mname:
                            name = mname
                    rate_changes[name] = {"from": r_a, "to": r_b}
            costmodel_diff = {
                "version_a": cm_a.get("version"),
                "version_b": cm_b.get("version"),
                "rate_changes": rate_changes,
            }

        return {
            "snapshot_a": snap_id_a,
            "snapshot_b": snap_id_b,
            "added_demands": added,
            "removed_demands": removed,
            "changed_demands": changed,
            "costmodel_diff": costmodel_diff,
        }

    # ------------------------------------------------------------------
    # Private assemblers
    # ------------------------------------------------------------------

    def _list_late_orders(self) -> ExplanationBundle:
        """Return all demands with positive lateness_minutes from the evidence index."""
        all_ev = self._index._all_evidence
        late_metrics = [
            r for r in all_ev
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]

        late_items = []
        for m in late_metrics:
            subj_ids = [s.get("entity_id") for s in m.get("subjects", [])]
            for did in subj_ids:
                if did:
                    refs = self._identity_map.external_refs(did) if self._identity_map else []
                    wo_name = refs[0].value if refs else did[:8]
                    late_items.append({
                        "demand_id": did,
                        "wo": wo_name,
                        "lateness_minutes": m.get("value"),
                    })

        worst = max(late_items, key=lambda it: it["lateness_minutes"],
                    default=None) if late_items else None
        return ExplanationBundle(
            question="Are there any late orders?",
            subject_id="all",
            subject_type="late_orders",
            subject_external_name="all demands",
            ordered_records=late_metrics,
            key_facts={
                "late_count": len(late_items),
                "late_orders": [
                    f"{item['wo']} (+{int(item['lateness_minutes'])} min)"
                    for item in late_items
                ],
                "worst_late_order": worst["wo"] if worst else None,
                "excluded_summary": self._excluded_summary(),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_late(self, wo_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} late?", wo_ref, "demand")

        demand = self._reader.get_entity(demand_id) or {}
        due_date = demand.get("due", "unknown")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        lateness = None
        completion_iso = None
        for rec in records:
            if rec.get("record_type") != "metric":
                continue
            name = rec.get("name", "")
            if name == "lateness_minutes":
                if any(s.get("entity_id") == demand_id for s in rec.get("subjects", [])):
                    lateness = rec.get("value")
            elif name == "projected_completion_epoch":
                epoch = rec.get("value")
                if isinstance(epoch, (int, float)):
                    completion_iso = datetime.fromtimestamp(
                        epoch, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M UTC")

        # CU4 — decompress the driver code into the causal story: the assignment
        # decision's driver phrased in plain language, plus the concrete
        # blocked-by fact (what held the machine) from the solved occupancy.
        driver_code = None
        for rec in records:
            if (rec.get("record_type") == "decision"
                    and rec.get("decision_type") == "assignment"):
                driver_code = rec.get("driver")
                break
        blocked = self._blocked_by(wo_ref) if (lateness or 0) > 0 else None

        # R-AI2(c) (Session 4A.2d) — offer a LABELED judgment where the evidence
        # grounds one: a late order blocked by earlier work carries the concrete
        # tradeoff a colleague would voice ("pull the blocker earlier, or accept
        # the N minutes"). Structured here (authored), rendered under "My take:",
        # never blended into the testimony.
        take = None
        if blocked and (lateness or 0) > 0:
            take = (f"pull {blocked['blocker_order']}'s start earlier on "
                    f"{blocked['machine']}, or accept the {int(lateness)} minutes "
                    "late — nothing else frees this slot.")

        return ExplanationBundle(
            question=f"Why is {wo_ref} late?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=records,
            key_facts={
                "lateness_minutes": lateness,
                "lateness_hours": round(lateness / 60, 1) if lateness is not None else None,
                "due_date": due_date,
                "completion_iso": completion_iso,
                "driver_code": driver_code,
                "driver_phrase": driver_phrase(driver_code),
                "blocked_by": blocked,
                "take": take,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_on_machine(self, wo_ref: str, machine_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} on {machine_ref}?", wo_ref, "demand")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        # Filter to assignment decisions only
        assignment_records = [
            r for r in records
            if r.get("record_type") == "decision" and r.get("decision_type") == "assignment"
        ]
        # The assignment's driver in plain language, so the answer leads with a
        # conversational sentence (Session 4A.2d) rather than a bare decision dump.
        # Session 4B.3a CU4b: an EARLINESS_PREFERENCE attribution is by PRICE RANK
        # only (docs/02 §4.2), so append the honest hedge — it cannot distinguish
        # earliness from capacity forcing; a confident single-cause answer would
        # grade wrong on the zero-confident-wrong axis.
        cause = None
        for r in assignment_records:
            cause = driver_phrase(r.get("driver"))
            if cause:
                hedge = driver_hedge(r.get("driver"))
                if hedge:
                    cause = f"{cause} {hedge}"
                break

        return ExplanationBundle(
            question=f"Why is {wo_ref} on {machine_ref}?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=assignment_records or records,
            key_facts={"machine_ref": machine_ref, "cause": cause,
                       "order": wo_ref},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_data_problems(self, entity_ref: Optional[str] = None) -> ExplanationBundle:
        findings = self._index.all_findings()
        if entity_ref:
            findings = self._findings_for_entity(findings, entity_ref)
        findings = sorted(
            findings,
            key=lambda r: (
                {"blocker": 0, "error": 1, "warning": 2, "info": 3}.get(
                    r.get("severity", "info"), 9
                ),
                r.get("seq", 0),
            ),
        )
        codes = sorted({r.get("code", "") for r in findings})
        return ExplanationBundle(
            question=f"What's wrong with {entity_ref}?" if entity_ref
            else "What data problems exist?",
            subject_id=entity_ref or self._snap_id,
            subject_type="findings",
            subject_external_name=entity_ref or self._snap_id,
            ordered_records=findings,
            key_facts={
                "total_findings": len(findings),
                "codes": codes,
                "entity_ref": entity_ref,
                "excluded_summary": None if entity_ref else self._excluded_summary(),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_excluded_orders(self, question: str) -> ExplanationBundle:
        """The excluded-orders story (Session 4.5 CU4): enumerate every order
        dropped from the plan and why — a finding with disposition ``excluded``
        or ``blocked``, from ANY layer (gate rule, adapter, validator). The
        customer's report card may never be blinder than dq_report.md, which
        already lists adapter + validator exclusions; this makes the same data
        enumerable in the certificate conversation. Full conversational polish is
        4A.2 — this surfaces the DATA (each excluded order, in the customer's
        vocabulary, with its reason/code/severity/module)."""
        excluded = [
            f for f in self._index.all_findings()
            if f.get("disposition") in ("excluded", "blocked")
        ]
        excluded = sorted(
            excluded,
            key=lambda r: (
                {"blocker": 0, "error": 1, "warning": 2, "info": 3}.get(
                    r.get("severity", "info"), 9),
                r.get("seq", 0),
            ),
        )
        # Enumerate each excluded order in the customer's vocabulary — the
        # external ref when the subject resolves through the identity map, else
        # the IDS-space order_id the finding already carries (a REJECTED run has
        # only that identity). Never an id-shape regex (Phase-1 audit lesson).
        orders: list[dict] = []
        for f in excluded:
            for s in f.get("subjects", []):
                sid = str(s.get("entity_id", "")) if isinstance(s, dict) else ""
                if not sid:
                    continue
                label = None
                if self._identity_map is not None:
                    erefs = self._identity_map.external_refs(sid)
                    if erefs:
                        label = erefs[0].value
                ev = f.get("evidence", {})
                orders.append({
                    "order": label or ev.get("order_id") or ev.get("demand_id") or sid,
                    "code": f.get("code", ""),
                    "severity": f.get("severity", ""),
                    "module": f.get("module", ""),
                    "reason": f.get("message", "") or ev.get("reason", ""),
                })
        return ExplanationBundle(
            question=question or "which orders were excluded from the plan?",
            subject_id=self._snap_id,
            subject_type="findings",
            subject_external_name="excluded orders",
            ordered_records=excluded,
            key_facts={
                "excluded_orders": orders,
                "excluded_count": len(orders),
                "codes": sorted({o["code"] for o in orders}),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # Session 4A.2 — the missing route families (CU5), the relevance guard's
    # destinations (CU1), drill-down (CU3), the blocked-by chain (CU4), and the
    # morning briefing (CU7). Every one reads only from the snapshot + evidence.
    # ------------------------------------------------------------------

    def _excluded_summary(self) -> Optional[dict]:
        """CU9 — the proactive excluded-orders volunteer. When any order was
        dropped from the plan, relevant answers say so ("14 of 15 scheduled;
        ORD-01 excluded — ask why"), inverting the certificate-silence gap the
        audit found into a trust feature. None when nothing was excluded."""
        orders = sorted(self._excluded_labels)
        if not orders:
            return None
        scheduled = 0
        if self._reader is not None:
            try:
                scheduled = len(list(self._reader.iter_entities("demand")))
            except Exception:
                scheduled = 0
        return {
            "orders": orders,
            "count": len(orders),
            "scheduled": scheduled,
            "total": scheduled + len(orders),
        }

    def _demand_by_order(self, order_ref: str) -> Optional[dict]:
        """The demand entity for an external order ref, via identity + snapshot."""
        if self._reader is None:
            return None
        did = self._resolve_wo(order_ref)
        if did is None:
            return None
        return self._reader.get_entity(did)

    def _priority_label(self, demand: dict) -> tuple[str, float]:
        """Planner-language priority from customer_weight (the canonical priority
        signal: high priority_class → weight > 1). Returns (label, weight)."""
        w = float(demand.get("customer_weight") or 1.0)
        if w >= 3.0:
            return "high priority", w
        if w > 1.0:
            return "elevated priority", w
        return "standard priority", w

    def _product_label(self, demand: dict) -> str:
        """The product's planner name for a demand, via product_ref."""
        pref = demand.get("product_ref")
        if not pref or self._reader is None:
            return "?"
        prod = self._reader.get_entity(pref) or {}
        for r in prod.get("external_refs", []):
            if r.get("type") in ("product_id", "product_no"):
                return r["value"]
        return prod.get("name") or (pref[:8] if pref else "?")

    def _order_rows(self, order_ref: str) -> list[dict]:
        """Scheduled assignment rows for one order, earliest first."""
        target = order_ref.upper()
        rows = [r for r in self._load_enriched_assignments()
                if target in [w.upper() for w in r["work_orders"]]]
        rows.sort(key=lambda r: r["start"] or "")
        return rows

    def _blocked_by(self, order_ref: str) -> Optional[dict]:
        """The CU4 blocked-by fact: for an order's FIRST scheduled operation, the
        job that occupied its machine immediately before it started (the concrete
        cause behind a CAPACITY_BLOCKED driver). Read from the solved occupancy —
        real evidence, never fabricated. None when nothing directly precedes it."""
        rows = self._order_rows(order_ref)
        if not rows or not rows[0].get("start"):
            return None
        first = rows[0]
        machine = first["machine"]
        try:
            my_start = _parse_ts(first["start"])
        except Exception:
            return None
        blocker = None
        best_end = None
        for r in self._load_enriched_assignments():
            if r["machine"] != machine or r is first:
                continue
            if order_ref.upper() in [w.upper() for w in r["work_orders"]]:
                continue
            if not r.get("end"):
                continue
            try:
                r_end = _parse_ts(r["end"])
            except Exception:
                continue
            if r_end <= my_start and (best_end is None or r_end > best_end):
                best_end = r_end
                blocker = r
        if blocker is None:
            return None
        blk_order = "+".join(sorted(blocker["work_orders"])) or "?"
        prio = ""
        for w in blocker["work_orders"]:
            dem = self._demand_by_order(w)
            if dem:
                lbl, wt = self._priority_label(dem)
                if wt > 1.0:
                    prio = lbl
                break
        return {
            "machine": machine,
            "blocker_order": blk_order,
            "blocker_priority": prio,
            "until": _fmt_ts(blocker["end"]),
            "my_start": _fmt_ts(first["start"]),
        }

    def _explain_order_attributes(self, order_ref: Optional[str]) -> ExplanationBundle:
        """The hover card, askable (CU5): product / quantity / customer / due /
        release / priority for one order — never its lateness unless asked."""
        if not order_ref:
            return self._unknown_question("what are the details of that order?")
        demand = self._demand_by_order(order_ref)
        if demand is None:
            return self._explain_unknown_entity(order_ref)
        qty = demand.get("quantity") or {}
        cust = None
        cref = demand.get("customer_ref")
        if cref and self._reader is not None:
            cent = self._reader.get_entity(cref) or {}
            refs = cent.get("external_refs", [])
            cust = refs[0]["value"] if refs else None
        prio_label, _w = self._priority_label(demand)
        facts = {
            "order": order_ref,
            "product": self._product_label(demand),
            "quantity": qty.get("value"),
            "quantity_uom": qty.get("uom", ""),
            "customer": cust,
            "due": _fmt_date(demand.get("due")),
            "release": _fmt_date(demand.get("earliest_start")),
            "priority": prio_label,
        }
        return ExplanationBundle(
            question=f"What are the details of {order_ref}?",
            subject_id=demand.get("id", order_ref),
            subject_type="order_attributes",
            subject_external_name=order_ref,
            ordered_records=[],
            key_facts=facts,
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_inventory(self, question: str) -> ExplanationBundle:
        """Counts + splits (CU5): how many orders are scheduled, how many
        operations, how many split across a pause, how many late."""
        if self._reader is None:
            return self._unknown_question(question)
        demands = list(self._reader.iter_entities("demand"))
        ops = list(self._reader.iter_entities("operation"))
        split_ops = [o for o in ops if o.get("splittable")]
        # a split job actually splits when its assignment has >1 run window
        split_orders: set[str] = set()
        for r in self._load_enriched_assignments():
            if len(r.get("service_outcomes", {})) or True:
                pass
        # count from schedule rows: an order appearing on >1 row for the same op seq
        rows = self._load_enriched_assignments()
        late = self._list_late_orders().key_facts.get("late_count", 0)
        return ExplanationBundle(
            question=question or "How many orders are in the plan?",
            subject_id=self._snap_id,
            subject_type="inventory",
            subject_external_name="the plan",
            ordered_records=[],
            key_facts={
                "order_count": len(demands),
                "operation_count": len(rows),
                "splittable_op_count": len(split_ops),
                "late_count": late,
                "excluded_summary": self._excluded_summary(),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_integrity(self, question: str,
                           machine_ref: Optional[str]) -> ExplanationBundle:
        """Double-booking check (CU5): are two operations scheduled on the same
        resource at the same time? A valid solve is conflict-free — the honest
        answer is usually "no", stated with confidence, and the audit's overlap
        specimen ('ORD-04 and ORD-06 at the same time') is answered directly."""
        rows = self._load_enriched_assignments()
        target_rid = self._resolve_machine(machine_ref) if machine_ref else None
        by_res: dict[str, list[dict]] = {}
        for r in rows:
            if target_rid and r["resource_id"] != target_rid:
                continue
            if r.get("start") and r.get("end"):
                by_res.setdefault(r["resource_id"], []).append(r)
        overlaps: list[dict] = []
        for rid, rs in by_res.items():
            rs.sort(key=lambda r: r["start"])
            for a, b in zip(rs, rs[1:]):
                try:
                    if _parse_ts(b["start"]) < _parse_ts(a["end"]):
                        overlaps.append({
                            "machine": a["machine"],
                            "a": "+".join(sorted(a["work_orders"])) or "?",
                            "b": "+".join(sorted(b["work_orders"])) or "?",
                            "a_end": _fmt_ts(a["end"]),
                            "b_start": _fmt_ts(b["start"]),
                        })
                except Exception:
                    continue
        label = machine_ref if machine_ref else "any machine"
        return ExplanationBundle(
            question=question or "Is anything double-booked?",
            subject_id=machine_ref or self._snap_id,
            subject_type="integrity",
            subject_external_name=label,
            ordered_records=[],
            key_facts={
                "overlaps": overlaps,
                "checked_machine": machine_ref,
                "op_count": sum(len(v) for v in by_res.values()),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_start_reason(self, order_ref: Optional[str],
                              question: str = "") -> ExplanationBundle:
        """Why an order starts when it does (CU5 + CU4 + CU3 polarity).

        POLARITY matters (Session 4A.3-pre CU3). "why can't X start EARLIER / why
        isn't it SOONER / what's blocking it" asks about the LOWER bound — answer
        with the binding cause (release date, or the machine held by earlier work).
        "why is X starting so EARLY / it's not due until {date} / it already
        started" asks the OPPOSITE — why it's early at all — and the honest answer
        is the R-SC3 floor: finishing early is free, so among cost-equal options
        the schedule starts work as soon as it can, banking slack. Answering a
        why-early question with a lower-bound cause is confident-wrong."""
        if not order_ref:
            return self._unknown_question("why does that order start when it does?")
        demand = self._demand_by_order(order_ref)
        if demand is None:
            return self._explain_unknown_entity(order_ref)
        rows = self._order_rows(order_ref)
        start = rows[0]["start"] if rows else None
        release = demand.get("earliest_start")
        blocked = self._blocked_by(order_ref)
        # which bound governs: release if the start sits at/after a release later
        # than the horizon open; else the machine-busy (blocked-by) cause.
        release_binds = False
        if release and start:
            try:
                release_binds = _parse_ts(start).date() <= _parse_ts(release).date() \
                    or abs((_parse_ts(start) - _parse_ts(release)).total_seconds()) < 86400
            except Exception:
                release_binds = False
        # CU3 — is this a why-EARLY question? ("early" as an adjective, never the
        # comparative "earlier"/"sooner" which asks the lower-bound question).
        early = _is_why_early(question)
        # is the placement genuinely ahead of its due date? (grounds the floor).
        due = demand.get("due")
        early_by_days = None
        fdt = _to_dt(rows[-1]["end"]) if rows else None  # completion vs due
        ddt = _to_dt(due)
        if fdt is not None and ddt is not None:
            early_by_days = round((ddt - fdt).total_seconds() / 86400, 1)
        # did a declared earliness_value drive it? (the assignment driver).
        driver = self._first_assignment_driver(order_ref)
        return ExplanationBundle(
            question=f"Why does {order_ref} start when it does?",
            subject_id=demand.get("id", order_ref),
            subject_type="start_reason",
            subject_external_name=order_ref,
            ordered_records=[],
            key_facts={
                "order": order_ref,
                "start": _fmt_ts(start) if start else None,
                "start_weekday": _weekday(start) if start else None,
                "release": _fmt_date(release),
                "release_weekday": _weekday(release) if release else None,
                "release_binds": bool(release and release_binds),
                "blocked_by": blocked,
                "machine": rows[0]["machine"] if rows else None,
                "why_early": early,
                "due": _fmt_date(due),
                "early_by_days": early_by_days,
                "earliness_priced": (str(driver).upper() == "EARLINESS_PREFERENCE"),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _first_assignment_driver(self, order_ref: str) -> Optional[str]:
        """The driver code on the order's first-operation assignment decision, or
        None — read from the lineage, used to detect a declared earliness push."""
        did = self._resolve_wo(order_ref)
        if did is None or self._reader is None:
            return None
        try:
            records = self._index.lineage_walk(did, snapshot_reader=self._reader)
        except Exception:
            return None
        for rec in records:
            if (rec.get("record_type") == "decision"
                    and rec.get("decision_type") == "assignment"):
                return rec.get("driver")
        return None

    def _order_lateness(self, order_ref: str) -> Optional[float]:
        """The order's lateness in minutes (positive = late, negative/zero = early/
        on time), from the lateness_minutes metric, or None when not recorded."""
        did = self._resolve_wo(order_ref)
        if did is None:
            return None
        for r in self._index._all_evidence:
            if (r.get("record_type") == "metric"
                    and r.get("name") == "lateness_minutes"
                    and any(s.get("entity_id") == did for s in r.get("subjects", []))):
                v = r.get("value")
                if isinstance(v, (int, float)):
                    return float(v)
        return None

    def _explain_contested(self, order_ref: Optional[str],
                           question: str) -> ExplanationBundle:
        """CU6 / R-AI3(4) — the user contests a cited fact. Meet it with warm
        EVIDENCE: restate what the record shows and offer to walk the chain. Never
        capitulate ("you're right, my mistake") and never harden (a curt
        re-assertion). The renderer composes the warmth; this assembles the facts.

        contested-wrong: the record contradicts the user's claim → hold, warmly.
        contested-agree: the record agrees with the user → confirm plainly."""
        if not order_ref:
            return self._unknown_question(question)
        demand = self._demand_by_order(order_ref)
        if demand is None:
            return self._explain_unknown_entity(order_ref)
        ql = (question or "").lower()
        # what the user is claiming: not-late (on time / early / fine) vs late.
        claims_not_late = any(s in ql for s in
                              ("on time", "on-time", "not late", "on schedule",
                               "fine", "ahead", "early"))
        lateness = self._order_lateness(order_ref)
        is_late = lateness is not None and lateness > 0
        due = _fmt_date(demand.get("due"))
        return ExplanationBundle(
            question=f"Is {order_ref} really on time?",
            subject_id=demand.get("id", order_ref),
            subject_type="contested_fact",
            subject_external_name=order_ref,
            ordered_records=[],
            key_facts={
                "order": order_ref,
                "lateness_minutes": lateness,
                "is_late": is_late,
                "claims_not_late": claims_not_late,
                "due": due,
                # contested-wrong when the record contradicts the claim either way.
                "contested": (is_late and claims_not_late)
                             or (not is_late and not claims_not_late and lateness is not None),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # Session 4A.3 — the swap/move bridge (CU1) + the absence pair (CU2)
    # ------------------------------------------------------------------

    def _assignment_records(self, order_ref: str) -> list[dict]:
        """The order's assignment Decisions — surfaced as ordered_records so the
        cockpit's cited_refs lights the order's bars (the lit-bars channel; no new
        board machinery). Best-effort, [] on any read failure."""
        did = self._resolve_wo(order_ref)
        if did is None or self._reader is None:
            return []
        try:
            recs = self._index.lineage_walk(did, snapshot_reader=self._reader)
        except Exception:
            return []
        return [r for r in recs if r.get("record_type") == "decision"
                and r.get("decision_type") == "assignment"]

    def _order_slack_facts(self, order_ref: str) -> Optional[dict]:
        """Placement + slack/lateness for one order, read from the persisted
        document (never fabricated): first-op machine + start, lateness minutes, and
        days early (due − completion). None when the order does not resolve."""
        dem = self._demand_by_order(order_ref)
        if dem is None:
            return None
        rows = self._order_rows(order_ref)
        late = self._order_lateness(order_ref)
        placement = None
        if rows and rows[0].get("start"):
            placement = {"machine": rows[0]["machine"],
                         "start": _fmt_ts(rows[0]["start"])}
        slack_days = None
        if rows and rows[-1].get("end"):
            fdt = _to_dt(rows[-1]["end"])
            ddt = _to_dt(dem.get("due"))
            if fdt is not None and ddt is not None:
                slack_days = round((ddt - fdt).total_seconds() / 86400, 1)
        return {"order": order_ref, "placement": placement, "lateness": late,
                "slack_days": slack_days,
                "late": (late is not None and late > 0),
                "records": self._assignment_records(order_ref)}

    def _explain_swap_move(self, order_a: Optional[str], order_b: Optional[str],
                           kind: str, question: str) -> ExplanationBundle:
        """CU1 — the swap/move bridge (the flagship). The R-AI3 ladder: TESTIMONY
        (both orders' placements + slack/lateness), a grounded TAKE (which slot
        changes hands, who can afford it), then the BRIDGE (the concrete board
        gesture the two-beat sandbox prices). The panel proposes; the human drags —
        M10 has no write path."""
        if not order_a:
            return self._unknown_question(question)
        fa = self._order_slack_facts(order_a)
        if fa is None:
            return self._explain_unknown_entity(order_a)
        fb = self._order_slack_facts(order_b) if order_b else None
        if order_b and fb is None:
            return self._explain_unknown_entity(order_b)
        take, bridge = self._swap_take_and_bridge(fa, fb, kind)
        records = list(fa.get("records") or [])
        if fb:
            records += list(fb.get("records") or [])
        a_pub = {k: v for k, v in fa.items() if k != "records"}
        b_pub = {k: v for k, v in fb.items() if k != "records"} if fb else None
        return ExplanationBundle(
            question=question or f"why not swap {order_a}?",
            subject_id=fa["order"], subject_type="swap_move",
            subject_external_name=order_a, ordered_records=records,
            key_facts={"kind": kind, "a": a_pub, "b": b_pub,
                       "take": take, "bridge": bridge},
            snapshot_id=self._snap_id, identity_map=self._identity_map)

    def _swap_take_and_bridge(self, fa: dict, fb: Optional[dict],
                              kind: str) -> tuple[Optional[str], Optional[str]]:
        """The grounded take + the board-gesture bridge for a swap/move. The take
        names who can afford the slot (slack) vs who is hurting (late); the bridge
        names the real drag the two-beat sandbox prices. Never an ungrounded opinion
        (R-AI3(2)): a take only where the evidence supports one."""
        a = fa["order"]
        if not fb:
            slot = fa.get("placement") or {}
            take = None
            if fa["late"]:
                take = (f"{a} is {int(fa['lateness'])} min late — the move worth "
                        "pricing is the one that gives it an earlier opening.")
            bridge = (f"Drag {a}'s first operation to the earlier slot you have in "
                      "mind and the board will run a sandbox and price the move "
                      "exactly.")
            return take, bridge
        b = fb["order"]
        # who's hurting (late) vs who can afford the slot (slack)
        if fa["late"] and not fb["late"]:
            hurting, slack = fa, fb
        elif fb["late"] and not fa["late"]:
            hurting, slack = fb, fa
        elif fa["late"] and fb["late"]:
            hurting = fa if (fa["lateness"] or 0) >= (fb["lateness"] or 0) else fb
            slack = fb if hurting is fa else fa
        else:
            slack = fa if (fa["slack_days"] or 0) >= (fb["slack_days"] or 0) else fb
            hurting = fb if slack is fa else fa
        slot = slack.get("placement") or {}
        if hurting["late"]:
            sd = slack.get("slack_days")
            slack_phrase = (f"~{sd:g} day(s) of slack" if sd and sd > 0
                            else "room to give")
            take = (f"{slack['order']} has {slack_phrase} to spend; {hurting['order']} "
                    f"is the one hurting ({int(hurting['lateness'])} min late) — giving "
                    f"it {slack['order']}'s earlier slot is the move worth pricing.")
            bridge = None
            if slot.get("machine"):
                bridge = (f"Drag {hurting['order']}'s first operation onto "
                          f"{slack['order']}'s slot on {slot['machine']} and the board "
                          "will run a sandbox and price the swap exactly.")
            return take, bridge
        take = (f"Both {a} and {b} already finish on time, so a swap mostly shuffles "
                "free slack — worth pricing only if you want one to finish sooner.")
        bridge = None
        if slot.get("machine"):
            bridge = (f"Drag {a}'s first operation onto {b}'s slot on "
                      f"{slot['machine']} and the sandbox will cost the move.")
        return take, bridge

    def _closure_in_window(self, machine_name: str, start_dt, end_dt) -> Optional[dict]:
        """A calendar closure on a machine overlapping [start_dt, end_dt), or None.
        Naive datetimes throughout (one run's grid), so no tz-mix comparison."""
        if self._reader is None or start_dt is None or end_dt is None:
            return None
        rid = self._resolve_machine(machine_name)
        if rid is None:
            return None
        resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
        calendars = {c["id"]: c for c in self._reader.iter_entities("calendar")}
        res = resources.get(rid)
        cal = calendars.get(res.get("calendar_ref")) if res else None
        if not cal:
            return None
        for exc in cal.get("exceptions", []):
            if exc.get("type") != "closure":
                continue
            w = exc.get("window", {})
            cs, ce = _to_dt(w.get("start")), _to_dt(w.get("end"))
            if cs is None or ce is None:
                continue
            if cs < end_dt and ce > start_dt:
                return {"reason": exc.get("reason", "closure"),
                        "start": _fmt_ts(w.get("start", "")),
                        "end": _fmt_ts(w.get("end", ""))}
        return None

    def _machine_working_windows(self, machine_name: str, from_dt=None,
                                 to_dt=None) -> list[tuple]:
        """Absolute (start_dt, end_dt) working windows for a machine's calendar.
        Prefers the solver's flattened ``horizon_resolved``; falls back to the
        ``base_pattern`` (weekday shift) expanded over [from_dt, to_dt]. [] when
        unavailable — the gap resolver then skips the off-shift check (never a
        false claim)."""
        rid = self._resolve_machine(machine_name)
        if rid is None or self._reader is None:
            return []
        resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
        calendars = {c["id"]: c for c in self._reader.iter_entities("calendar")}
        res = resources.get(rid)
        cal = calendars.get(res.get("calendar_ref")) if res else None
        if not cal:
            return []
        out: list[tuple] = []
        for w in cal.get("horizon_resolved", []) or []:
            s = _to_dt(w.get("start") if isinstance(w, dict) else getattr(w, "start", None))
            e = _to_dt(w.get("end") if isinstance(w, dict) else getattr(w, "end", None))
            if s is not None and e is not None:
                out.append((s, e))
        if out or from_dt is None or to_dt is None:
            return out
        # Fall back to the base pattern (weekday + shift start/end) expanded over
        # the range — the shape glass_box and most authored plants use.
        bp = cal.get("base_pattern") or {}
        weekdays = set(bp.get("weekdays") or [])
        ss, se = bp.get("shift_start"), bp.get("shift_end")
        if not (weekdays and ss and se):
            return []
        try:
            from datetime import date as _date, timedelta as _tdelta
            sh, sm = (int(x) for x in str(ss).split(":")[:2])
            eh, em = (int(x) for x in str(se).split(":")[:2])
        except Exception:
            return []
        d = from_dt.date() - _tdelta(days=1)
        stop = to_dt.date() + _tdelta(days=1)
        while d <= stop:
            if d.weekday() in weekdays:
                out.append((datetime(d.year, d.month, d.day, sh, sm),
                            datetime(d.year, d.month, d.day, eh, em)))
            d += _tdelta(days=1)
        return out

    def _gap_cause(self, order_a: str, order_b: str) -> dict:
        """The cause of the gap between order_a and order_b on their shared machine,
        checked in order: another op occupies it / a closure covers it / the later
        op's release or upstream step gates it / else honestly unexplained. Read from
        the solved occupancy — never a fabricated cause."""
        rows = self._load_enriched_assignments()

        def _order_rows_m(ref):
            return {r["machine"]: r for r in rows
                    if r.get("start") and ref.upper() in
                    [w.upper() for w in r["work_orders"]]}

        a_by_m, b_by_m = _order_rows_m(order_a), _order_rows_m(order_b)
        shared = [m for m in a_by_m if m in b_by_m]
        result: dict[str, Any] = {"machine": None, "gap_min": None, "cause": None}
        if not shared:
            result["cause"] = "no_shared_machine"
            return result
        machine = shared[0]
        ra, rb = a_by_m[machine], b_by_m[machine]
        sa, sb = _to_dt(ra["start"]), _to_dt(rb["start"])
        if sa is None or sb is None:
            result["cause"] = "unexplained"
            return result
        if sa <= sb:
            earlier, later, earlier_ref, later_ref = ra, rb, order_a, order_b
        else:
            earlier, later, earlier_ref, later_ref = rb, ra, order_b, order_a
        e_end, l_start = _to_dt(earlier["end"]), _to_dt(later["start"])
        result.update({
            "machine": machine,
            "earlier_order": "+".join(sorted(earlier["work_orders"])) or earlier_ref,
            "later_order": "+".join(sorted(later["work_orders"])) or later_ref,
            "earlier_end": _fmt_ts(earlier["end"]),
            "later_start": _fmt_ts(later["start"]),
        })
        if e_end is None or l_start is None:
            result["cause"] = "unexplained"
            return result
        gap_min = round((l_start - e_end).total_seconds() / 60.0, 0)
        result["gap_min"] = gap_min
        if gap_min <= 1:
            result["cause"] = "adjacent"
            return result
        # 1. another op occupies the interval
        for r in rows:
            if r["machine"] != machine or r is earlier or r is later or not r.get("start"):
                continue
            s, e = _to_dt(r["start"]), _to_dt(r["end"])
            if s is not None and e is not None and s < l_start and e > e_end:
                result["cause"] = "occupied"
                result["occupier"] = "+".join(sorted(r["work_orders"])) or "?"
                result["occupier_window"] = f"{_fmt_ts(r['start'])} → {_fmt_ts(r['end'])}"
                return result
        # 2. a calendar closure covers part of the window
        closure = self._closure_in_window(machine, e_end, l_start)
        if closure:
            result["cause"] = "closure"
            result["closure"] = closure
            return result
        # 2b. the machine is off-shift for (essentially) the whole gap — no open
        #     capacity between the two ops, so the later one waits for the reopen.
        wins = self._machine_working_windows(machine, e_end, l_start)
        if wins:
            open_min = 0.0
            for (ws, we) in wins:
                lo, hi = max(ws, e_end), min(we, l_start)
                if hi > lo:
                    open_min += (hi - lo).total_seconds() / 60.0
            if open_min <= max(2.0, 0.05 * gap_min):
                result["cause"] = "off_shift"
                result["reopen"] = _fmt_ts(later["start"])
                return result
        # 3. the later op's release or its upstream step gates it
        ldem = self._demand_by_order(later_ref)
        release = ldem.get("earliest_start") if ldem else None
        rdt = _to_dt(release) if release else None
        if rdt is not None and rdt > e_end:
            result["cause"] = "release"
            result["release"] = _fmt_date(release)
            result["later_order"] = later_ref
            return result
        lrows = sorted([r for r in rows if r.get("start") and later_ref.upper() in
                        [w.upper() for w in r["work_orders"]]],
                       key=lambda r: r["start"])
        for i, r in enumerate(lrows):
            if r is later and i > 0:
                prev = lrows[i - 1]
                pend = _to_dt(prev["end"])
                if pend is not None and pend > e_end:
                    result["cause"] = "upstream"
                    result["later_order"] = later_ref
                    result["upstream_machine"] = prev["machine"]
                    result["upstream_until"] = _fmt_ts(prev["end"])
                    return result
                break
        result["cause"] = "unexplained"
        return result

    def _explain_gap(self, order_a: Optional[str], order_b: Optional[str],
                     machine: Optional[str], question: str) -> ExplanationBundle:
        """CU2 — "why is there a gap/slack between X and Y". Resolve the gap on the
        shared machine and name its cause (occupancy / closure / upstream gate), or
        report it honestly when nothing gates it (post-R-SC3, cost-equal slack is
        eliminated — an unexplained gap is worth flagging, not vouching a cause)."""
        if not order_a:
            return self._authored_bundle("gap_between", question, {"no_orders": True})
        if self._demand_by_order(order_a) is None:
            return self._explain_unknown_entity(order_a)
        if order_b and self._demand_by_order(order_b) is None:
            return self._explain_unknown_entity(order_b)
        facts: dict[str, Any] = {"order_a": order_a, "order_b": order_b}
        if order_b:
            facts.update(self._gap_cause(order_a, order_b))
        else:
            facts["no_second"] = True
        return self._authored_bundle("gap_between", question, facts)

    def _manned_idle_hours(self, rid: Optional[str]) -> Optional[float]:
        """The resource's manned-idle time in hours from a manned_idle Metric
        (4B.2d CU5), or None when not recorded. Grounds the machine-idle answer."""
        if not rid:
            return None
        for r in self._index._all_evidence:
            name = r.get("name") or ""
            if (r.get("record_type") == "metric" and "manned_idle" in name
                    and any(s.get("entity_id") == rid for s in r.get("subjects", []))):
                v = r.get("value")
                if isinstance(v, (int, float)):
                    return round(v / 60.0, 1) if "minute" in name else round(v, 1)
        return None

    def _explain_machine_idle(self, machine_ref: Optional[str],
                              question: str) -> ExplanationBundle:
        """CU2 — "why is M unused/idle". A machine that carries work is not idle
        (redirect to its schedule, no order names — avoids answering the wrong
        noun); a genuinely idle machine gets eligibility-honest scoping grounded in
        the manned-idle Metric where present."""
        if not machine_ref:
            return self._unknown_question(question)
        rid = self._resolve_machine(machine_ref)
        rows = [r for r in self._load_enriched_assignments()
                if (rid and r["resource_id"] == rid)
                or r["machine"].upper() == machine_ref.upper()]
        facts: dict[str, Any] = {"machine": machine_ref, "op_count": len(rows)}
        if rows:
            try:
                rows.sort(key=lambda r: r["start"] or "")
                facts["first"] = _fmt_ts(rows[0]["start"])
                facts["last"] = _fmt_ts(rows[-1]["end"])
            except Exception:
                pass
        else:
            facts["idle"] = True
            facts["manned_idle_hours"] = self._manned_idle_hours(rid)
        return self._authored_bundle("machine_idle", question, facts)

    def _explain_unknown_entity(self, mention: str) -> ExplanationBundle:
        """The relevance guard's honest destination (CU1): a named order that is
        not in this schedule. If it was EXCLUDED at a gate/adapter/validator
        layer, say so and cite the finding; otherwise say plainly it isn't here
        (and offer the orders that ARE). Never a global answer wearing a 'Yes'."""
        token = (mention or "").strip().strip(".,?!")
        upper = token.upper()
        excluded_finding = None
        if upper in self._excluded_labels:
            for f in self._index.all_findings():
                if f.get("disposition") not in ("excluded", "blocked"):
                    continue
                ev = f.get("evidence", {}) or {}
                labels = {str(ev.get("order_id", "")).upper(),
                          str(ev.get("demand_id", "")).upper()}
                for s in f.get("subjects", []) or []:
                    sid = s.get("entity_id") if isinstance(s, dict) else ""
                    if sid and self._identity_map is not None:
                        erefs = self._identity_map.external_refs(sid)
                        if erefs:
                            labels.add(erefs[0].value.upper())
                if upper in labels:
                    excluded_finding = f
                    break
        known_orders = sorted(self._order_refs.values())[:6]
        return ExplanationBundle(
            question=f"Is {token} in this schedule?",
            subject_id=token,
            subject_type="unknown_entity",
            subject_external_name=token,
            ordered_records=[excluded_finding] if excluded_finding else [],
            key_facts={
                "mention": token,
                "excluded": excluded_finding is not None,
                "finding": (compose_finding_sentence(
                    excluded_finding, self._identity_map, _load_catalog_safe())
                    if excluded_finding else None),
                "known_orders": known_orders,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_drill_down(self, target: str,
                            history: Optional[list] = None) -> ExplanationBundle:
        """Open the full finding/record behind a citation (CU3): "tell me more
        about finding 2 / that". Resolves an ordinal ('finding 2'), else drills
        into the most severe data-quality finding — so a citation is never a dead
        end. Context-carried when the caller passes the prior turn's records."""
        findings = sorted(
            self._index.all_findings(),
            key=lambda r: ({"blocker": 0, "error": 1, "warning": 2, "info": 3}
                           .get(r.get("severity", "info"), 9), r.get("seq", 0)))
        target = target or ""
        m = re.search(r"(?:finding|item|#|number)\s*#?\s*(\d+)", target.lower())
        pick = None
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(findings):
                pick = findings[idx]
        if pick is None and findings:
            pick = findings[0]
        detail = (compose_finding_sentence(pick, self._identity_map,
                                           _load_catalog_safe()) if pick else None)
        return ExplanationBundle(
            question="Tell me more.",
            subject_id=(pick.get("record_id", "") if pick else ""),
            subject_type="drill_down",
            subject_external_name=(detail["subject"] if detail else "?"),
            ordered_records=[pick] if pick else [],
            key_facts={"detail": detail, "has_target": bool(pick)},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_briefing(self, question: str) -> ExplanationBundle:
        """The morning briefing (CU7): the question a planner asks at 7am. A
        TRIAGE, not a list — the fires ranked by lateness × priority, the common
        cause named if one exists, and the one data-quality item that matters.
        Composed from the existing late/severity/driver machinery, no new solve."""
        # the fires: late orders ranked by lateness × priority weight
        late_metrics = [
            r for r in self._index._all_evidence
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]
        fires: list[dict] = []
        cause_counts: dict[str, int] = {}
        for m in late_metrics:
            for s in m.get("subjects", []):
                did = s.get("entity_id")
                if not did:
                    continue
                refs = self._identity_map.external_refs(did) if self._identity_map else []
                order = refs[0].value if refs else did[:8]
                demand = self._reader.get_entity(did) if self._reader else {}
                _plabel, weight = self._priority_label(demand or {})
                lateness = float(m.get("value") or 0.0)
                blk = self._blocked_by(order)
                driver = None
                if blk:
                    driver = "CAPACITY_BLOCKED"
                    cause_counts[driver] = cause_counts.get(driver, 0) + 1
                fires.append({
                    "order": order,
                    "lateness_minutes": lateness,
                    "priority": _plabel if weight > 1 else "standard",
                    "weight": weight,
                    "score": lateness * weight,
                    "blocked_by": blk,
                })
        fires.sort(key=lambda f: -f["score"])
        common_cause = None
        if cause_counts:
            top, n = max(cause_counts.items(), key=lambda kv: kv[1])
            if n >= 2:
                common_cause = driver_phrase(top)
        # the one data-quality item that matters: the most severe finding
        findings = sorted(
            self._index.all_findings(),
            key=lambda r: ({"blocker": 0, "error": 1, "warning": 2, "info": 3}
                           .get(r.get("severity", "info"), 9), r.get("seq", 0)))
        top_dq = None
        if findings:
            top_dq = compose_finding_sentence(findings[0], self._identity_map,
                                              _load_catalog_safe())
        return ExplanationBundle(
            question=question or "What should I worry about today?",
            subject_id=self._snap_id,
            subject_type="briefing",
            subject_external_name="today",
            ordered_records=[],
            key_facts={
                "fires": fires,
                "fire_count": len(fires),
                "common_cause": common_cause,
                "top_data_quality": top_dq,
                "finding_count": len(findings),
                "excluded_summary": self._excluded_summary(),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # Certificate question domain (handoff §4)
    # ------------------------------------------------------------------

    def _certificate_findings(self) -> list[dict]:
        """Gate (M0) findings from the evidence store — those carrying a
        registry rule_id + outcome. Read from evidence, never by re-running the
        gate (handoff §4)."""
        return [
            f for f in self._index.all_findings()
            if "rule_id" in f.get("evidence", {})
            and "outcome" in f.get("evidence", {})
        ]

    def _findings_for_entity(self, findings: list[dict], entity_ref: str) -> list[dict]:
        """Resolve an entity's findings through identity — the canonical id via
        the identity map when a snapshot exists, else the IDS-space subject the
        gate finding already carries (the only identity a REJECTED run has).
        Never an id-shape regex (Phase-1 exit audit rule)."""
        canonical = self._resolve_wo(entity_ref) if self._identity_map else None
        target = entity_ref.upper()
        hits: list[dict] = []
        for f in findings:
            for s in f.get("subjects", []):
                sid = str(s.get("entity_id", ""))
                if canonical and sid == canonical:
                    hits.append(f)
                    break
                if sid.upper() == target:
                    hits.append(f)
                    break
        return hits

    def _report_findings(self) -> list[dict]:
        """The finding set the certificate registers reason over — the SAME set
        testimony enumerates (Session 4A.2b CU2). remediation/triage previously
        saw only gate-certificate findings (rule_id + outcome), so an ACCEPTED
        submission carrying a validator ADVISORY (a real warning that proceeded)
        made testimony say "1 problem" while remediation/triage said "nothing" —
        the two registers contradicting each other. Reasoning over one source
        makes them coherent by construction; the register bodies split actionable
        from advisory themselves."""
        return self._index.all_findings()

    def _explain_how_to_fix(self, question: str, limit: Optional[int]) -> ExplanationBundle:
        findings = self._report_findings()
        return ExplanationBundle(
            question=question,
            subject_id=self._snap_id,
            subject_type="remediation",
            subject_external_name="submission",
            ordered_records=findings,
            key_facts={"limit": limit, "finding_count": len(findings)},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_fix_first(self, question: str) -> ExplanationBundle:
        findings = self._report_findings()
        return ExplanationBundle(
            question=question,
            subject_id=self._snap_id,
            subject_type="triage",
            subject_external_name="submission",
            ordered_records=findings,
            key_facts={"finding_count": len(findings)},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_what_changed(self, question: str) -> ExplanationBundle:
        snap_match = re.findall(r'snap[\w-]+', question, re.IGNORECASE)
        if len(snap_match) >= 2:
            snap_a, snap_b = snap_match[0], snap_match[1]
        elif len(snap_match) == 1:
            snap_a, snap_b = snap_match[0], self._snap_id
        else:
            snap_a, snap_b = self._snap_id, self._snap_id

        try:
            diff = self.snapshot_diff(snap_a, snap_b)
        except FileNotFoundError as exc:
            diff = {"error": str(exc)}

        return ExplanationBundle(
            question=question,
            subject_id=f"{snap_a}->{snap_b}",
            subject_type="diff",
            subject_external_name=f"{snap_a} -> {snap_b}",
            ordered_records=[],
            key_facts=diff,
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # The sandbox/edit question domain (CU2) — over planner_edit Decisions
    # ------------------------------------------------------------------

    def _planner_edits(self) -> list[dict]:
        """The planner_edit Decisions in this version's run evidence, oldest
        first. An accepted edit records exactly one; a chain of edits leaves one
        per step in each version's run — the explainer, scoped to the current
        version's run, sees this version's edit (docs/02 planner_edit)."""
        edits = [
            r for r in self._index._all_evidence
            if r.get("record_type") == "decision"
            and r.get("decision_type") == "planner_edit"
        ]
        edits.sort(key=lambda r: (r.get("timestamp", ""), r.get("seq", 0)))
        return edits

    def _edit_facts(self, dec: dict) -> dict:
        """Planner-vocabulary facts for one planner_edit Decision: the pinned
        order + machine (via identity), the total + decomposed cost delta, the
        moved-op count, and the authority. Reads only the Decision's own payload
        (self-contained evidence)."""
        chosen = dec.get("chosen") or {}
        pin = chosen.get("pin") or {}
        op_ref = pin.get("operation_ref", "")
        res_ref = pin.get("resource_id", "")
        # resolve to planner vocabulary where the identity map knows it
        machine = res_ref[:8] if res_ref else "?"
        if self._identity_map and res_ref:
            refs = self._identity_map.external_refs(res_ref)
            mref = next((r for r in refs if r.type in _MACHINE_REF_TYPES), None)
            if mref:
                machine = mref.value
        # the pinned op's work order rides the Decision message; fall back to id8
        return {
            "machine": machine,
            "op_ref8": op_ref[:8] if op_ref else "?",
            "start": pin.get("start"),
            "cost_delta": chosen.get("cost_delta") or {},
            "delta_abs": chosen.get("delta_abs"),
            "moved_count": chosen.get("moved_count", 0),
            "authority": dec.get("authority"),
            "moves": chosen.get("moves") or [],
        }

    def _summarize_edits(self, question: str) -> ExplanationBundle:
        """The demo's closing beat: "summarize what I changed and what it cost".
        Over the planner_edit Decisions this version carries — each a pinned op +
        its priced delta — never fabricated, always evidence."""
        edits = self._planner_edits()
        facts = [self._edit_facts(d) for d in edits]
        total_cost_delta = round(
            sum((f["cost_delta"].get("total_delta") or 0.0) for f in facts), 2)
        return ExplanationBundle(
            question=question,
            subject_id=self._snap_id,
            subject_type="edits",
            subject_external_name="this session's edits",
            ordered_records=edits,
            key_facts={
                "edit_count": len(edits),
                "edits": facts,
                "total_cost_delta": total_cost_delta,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_edit_cost(self, question: str) -> ExplanationBundle:
        """"Why does this move cost N?" — decompose the MOST RECENT edit's cost
        delta into production / setup / tardiness (docs/02 §4.4 decomposition)
        plus the per-consequence "why" clauses (3.3 CU3). Refuses honestly when
        no edit has been made yet (the records can't support the question)."""
        edits = self._planner_edits()
        if not edits:
            return self._unknown_question(question)
        facts = self._edit_facts(edits[-1])
        return ExplanationBundle(
            question=question,
            subject_id=self._snap_id,
            subject_type="edit_cost",
            subject_external_name=f"edit on {facts['machine']}",
            ordered_records=[edits[-1]],
            key_facts=facts,
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _near_miss(self, question: str, offers: list[str],
                   routes: list[str]) -> ExplanationBundle:
        """The tiered-fallback bridge (CU4): moderate interpreter confidence or
        params that only partially resolved. Answer honestly with the nearest
        routes offered as concrete follow-ups. All copy is authored upstream
        (ask_fallback_copy) — this assembler only carries it. Never a dead end."""
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type="near_miss",
            subject_external_name="?",
            ordered_records=[],
            key_facts={"parsed": question, "offers": offers, "routes": routes},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _clarify(self, question: str, reason: str) -> ExplanationBundle:
        """An elliptical follow-up (CU2) that cannot be resolved against the
        conversation — ask for the missing referent, never guess."""
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type="clarify",
            subject_external_name="?",
            ordered_records=[],
            key_facts={"parsed": question, "reason": reason},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_recent_refusals(self, refusals: list[dict]) -> ExplanationBundle:
        """The meta-route (R-AI1(d)): the ledger answering about itself. The
        refusal facts are passed in (the orchestration reads the ledger and hands
        them here) so the explainer stays free of the ledger dependency and its
        no-write-path invariant is untouched."""
        return ExplanationBundle(
            question="What questions couldn't you answer recently?",
            subject_id=self._snap_id,
            subject_type="refusals",
            subject_external_name="the question ledger",
            ordered_records=[],
            key_facts={"refusals": refusals, "count": len(refusals)},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _unknown_question(self, question: str) -> ExplanationBundle:
        """Return an explicit 'unsupported' bundle — never silently reroute."""
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type="unsupported",
            subject_external_name="?",
            ordered_records=[],
            key_facts={
                "parsed": question,
                "supported_routes": self._planner_routes(),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _planner_routes(self) -> list[str]:
        """The fallback menu in planner language, led by concrete examples drawn
        from THIS schedule's real external refs where cheap (an actual order /
        machine name), falling back to the generic planner-worded list. Router
        capabilities are unchanged — wording only (CU4)."""
        # Deterministic pick (min of the known refs) so the menu is stable.
        order = min(self._order_refs.values()) if self._order_refs else None
        machine = min(self._machine_refs.values()) if self._machine_refs else None
        examples: list[str] = []
        if order:
            examples.append(f'why is {order} late — the lateness cause chain')
            examples.append(f'when does {order} finish — one order\'s schedule')
        if machine:
            examples.append(f"what's running on {machine} — that machine's schedule")
        return examples + list(_SUPPORTED_ROUTES)

    def _authored_bundle(self, subject_type: str, question: str,
                         key_facts: dict) -> ExplanationBundle:
        """A header-only authored-copy bundle (no evidence chain) — the shape the
        scoping / meta-read answers use. subject_type drives the renderer branch."""
        return ExplanationBundle(
            question=question, subject_id="", subject_type=subject_type,
            subject_external_name="?", ordered_records=[],
            key_facts={"parsed": question, **key_facts},
            snapshot_id=self._snap_id, identity_map=self._identity_map)

    def _late_order_count(self) -> int:
        """Cheap count of demands that finish late, from the service outcomes.
        Defensive — 0 when outcomes cannot be read."""
        n = 0
        try:
            from mre.modules.sandbox import _svc_lateness_min
            for s in self._reader.iter_entities("serviceoutcome"):
                if _svc_lateness_min(s) > 0:
                    n += 1
        except Exception:
            return 0
        return n

    def _explain_advice(self, question: str) -> ExplanationBundle:
        """CU2 — the HONEST SCOPING answer for a recommendation/advice question.

        NEVER a status recital and NEVER an invented intervention. States what the
        product CAN do today (explain why each late order is late; what each is
        waiting on; price a what-if move on the board via the sandbox) and that
        recommending an intervention (open overtime, add a machine) is not yet a
        supported question. Conversational register (R-AI2), no === headers.

        R-AI3(2) — the scoping answer ENDS with a GROUNDED judgment where the
        evidence supports one (the disclaimer covers the action BRIDGE only, not
        the judgment register): the worst late order's slip traced to the concrete
        commitment holding its machine, named as the single biggest lever. Absent
        on a clean plan (nothing to ground a take on)."""
        late = self._late_order_count()
        return self._authored_bundle(
            "advice", question,
            {"late_count": late, "take": self._advice_take()})

    def _advice_take(self) -> Optional[str]:
        """A grounded lever for the advice route (R-AI3(2)): the worst late order,
        the commitment its start waits behind, named as the biggest lever. From the
        SAME solved occupancy the why-late chain reads — never an invented
        intervention. None when nothing is late (no take to ground)."""
        worst = None
        worst_late = 0.0
        for item in self._list_late_orders().key_facts.get("late_orders", []):
            # items read "WO (+N min)"; recover order + minutes without re-solving
            m = re.match(r"^(.*?)\s*\(\+(\d+)\s*min\)$", item)
            if not m:
                continue
            mins = float(m.group(2))
            if mins > worst_late:
                worst_late, worst = mins, m.group(1)
        if not worst:
            return None
        blk = self._blocked_by(worst)
        if blk:
            return (f"{worst}'s {int(worst_late)}-minute slip traces to "
                    f"{blk['blocker_order']} holding {blk['machine']} until "
                    f"{blk['until']} — pulling that earlier is the single biggest "
                    "lever the board gives you today.")
        return (f"{worst} is the worst slip at {int(worst_late)} minutes — start "
                "there; ask \"why is it late?\" and I'll walk the chain.")

    def _explain_coaching(self, question: str,
                          concept: Optional[str]) -> ExplanationBundle:
        """CU4 — the coaching/capability answer. RETRIEVE the authored note for the
        named concept from the capability registry and render its `enables` +
        `how` + § citation (jurisdiction rule: coach the IDS requirement, never ERP
        surgery). A capability question that names no known concept gets an honest
        not-yet that lists what CAN be coached — never an entity-lookup miss."""
        note = note_for_concept(concept) if concept else None
        coachable = [c.concept for c in CAPABILITIES]
        return self._authored_bundle("coaching", question, {
            "concept": concept,
            "enables": note.enables if note else None,
            "how": note.how if note else None,
            "ids_ref": note.ids_ref if note else None,
            "rationale": note.rationale if note else None,
            "coachable": coachable,
        })

    def _explain_solve_time(self, question: str) -> ExplanationBundle:
        """CU3 — how long the solve took. A pure evidence read of the M6 run's
        open→close wall time (the solve stage). Honest not-yet when unavailable."""
        def _iso(x):
            try:
                return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        seconds = None
        try:
            m6 = [r for r in self._index.runs() if r.get("module") == "M6"]
            for r in m6:
                dt_o, dt_c = _iso(r.get("timestamp_open")), _iso(r.get("timestamp_close"))
                if dt_o and dt_c:
                    seconds = max(seconds or 0.0, (dt_c - dt_o).total_seconds())
        except Exception:
            seconds = None
        return self._authored_bundle("solve_time", question,
                                     {"solve_seconds": seconds})

    def _explain_machine_count(self, question: str) -> ExplanationBundle:
        """CU3 — how many machines / list the machines. A pure document read of the
        resource entities, rendered in the planner's external vocabulary."""
        names: list[str] = []
        try:
            for r in self._reader.iter_entities("resource"):
                nm = None
                for ref in (r.get("external_refs") or []):
                    if ref.get("ref_type") in _MACHINE_REF_TYPES or ref.get("value"):
                        nm = ref.get("value")
                        break
                names.append(nm or r.get("id", "?"))
        except Exception:
            names = []
        names = sorted(dict.fromkeys(names))
        return self._authored_bundle("machine_count", question,
                                     {"machine_count": len(names), "machines": names})

    def _explain_maintenance(self, question: str) -> ExplanationBundle:
        """CU3 — maintenance / shift / calendar shape-recognition. Answered with an
        honest not-yet that names the per-machine downtime route that DOES exist
        (the calendar-awareness cluster is named as debt in docs/04, not built)."""
        machine = min(self._machine_refs.values()) if self._machine_refs else None
        return self._authored_bundle("maintenance", question,
                                     {"example_machine": machine})

    def _explain_downtime(self, question: str) -> ExplanationBundle:
        """Sum calendar closure windows for a named resource, pool, or setup family."""
        resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
        calendars = {c["id"]: c for c in self._reader.iter_entities("calendar")}
        pools = list(self._reader.iter_entities("resourcepool"))

        m_match = re.search(r'M-[A-Z0-9-]+', question, re.IGNORECASE)

        if m_match:
            machine_name = m_match.group().upper()
            rid = self._identity_map.resolve("ERP", "machine_id", machine_name) if self._identity_map else None
            target_ids = [rid] if rid else []
            subject_label = machine_name
        else:
            _STOP = {"how", "much", "does", "do", "have", "any", "is", "are", "the",
                     "a", "an", "for", "in", "what", "which", "show", "me",
                     "downtime", "closures", "closure", "offline", "scheduled"}
            words = {w.strip("?.,!") for w in question.lower().split()
                     if w.strip("?.,!") not in _STOP and len(w.strip("?.,!")) > 2}

            target_ids = []
            subject_label = "all resources"
            for pool in pools:
                for ref in pool.get("external_refs", []):
                    pname = ref.get("value", "").lower()
                    if any(word in pname for word in words):
                        target_ids.extend(pool.get("members", []))
                        subject_label = ref.get("value", subject_label)
                        break
                if target_ids:
                    break

            if not target_ids:
                # Fallback: setup_family substring match via assignments in snapshot
                op_ids_by_family: dict[str, list[str]] = {}
                for op in self._reader.iter_entities("operation"):
                    fam = op.get("setup_family", "").lower()
                    if any(word in fam for word in words):
                        op_ids_by_family.setdefault(fam, []).append(op["id"])
                        subject_label = fam
                if op_ids_by_family:
                    matched_ops = {oid for ids in op_ids_by_family.values() for oid in ids}
                    for asgn in self._reader.iter_entities("assignment"):
                        if asgn.get("operation_ref") in matched_ops:
                            for ra in asgn.get("resource_assignments", []):
                                rid = ra.get("resource_ref", "") if isinstance(ra, dict) else getattr(ra, "resource_ref", "")
                                if rid and rid not in target_ids:
                                    target_ids.append(rid)

            if not target_ids:
                target_ids = list(resources.keys())

        # Sum closure exceptions per resource
        closures: list[dict] = []
        for rid in sorted(set(target_ids)):
            resource = resources.get(rid)
            if not resource:
                continue
            cal_ref = resource.get("calendar_ref")
            cal = calendars.get(cal_ref) if cal_ref else None
            if not cal:
                continue
            res_name = rid[:8]
            if self._identity_map:
                refs = self._identity_map.external_refs(rid)
                mref = next((r for r in refs if r.type == "machine_id"), None)
                if mref:
                    res_name = mref.value
            for exc in cal.get("exceptions", []):
                if exc.get("type") != "closure":
                    continue
                window = exc.get("window", {})
                start_str = window.get("start", "")
                end_str = window.get("end", "")
                if not (start_str and end_str):
                    continue
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                hours = round((end_dt - start_dt).total_seconds() / 3600, 1)
                closures.append({
                    "resource": res_name,
                    "duration_hours": hours,
                    "reason": exc.get("reason", "unknown"),
                    "date": start_dt.strftime("%Y-%m-%d"),
                })

        total_hours = round(sum(c["duration_hours"] for c in closures), 1)
        return ExplanationBundle(
            question=question,
            subject_id=subject_label,
            subject_type="downtime",
            subject_external_name=subject_label,
            ordered_records=[],
            key_facts={
                "subject": subject_label,
                "closures": closures,
                "total_hours": total_hours,
                "resource_count": len({c["resource"] for c in closures}),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # Schedule query assembler
    # ------------------------------------------------------------------

    def _schedule_query(
        self, question: str, q: str, wo_ref: Optional[str], machine_ref: Optional[str]
    ) -> ExplanationBundle:
        flt, label = self._build_schedule_filter(q, wo_ref, machine_ref)

        # Resolve target resource IDs (None = no machine filter)
        target_res_ids: Optional[set[str]] = None
        if flt.get("machine"):
            rid = self._resolve_machine(flt["machine"])
            target_res_ids = {rid} if rid else set()
        elif flt.get("pool_words"):
            target_res_ids = self._resolve_pool_resource_ids(flt["pool_words"])

        rows = self._load_enriched_assignments()
        filtered = self._apply_schedule_filter(rows, flt, target_res_ids)
        filtered.sort(key=lambda r: (r["machine"], r["start"]))
        if flt.get("limit"):
            filtered = filtered[: flt["limit"]]

        row_dicts = []
        for r in filtered:
            svc_facts = r.get("service_outcomes", {})
            lateness_min: Optional[float] = None
            if svc_facts:
                mins = [
                    _parse_iso_duration_minutes(s.get("lateness", ""))
                    for s in svc_facts.values()
                    if s.get("lateness")
                ]
                if mins:
                    lateness_min = max(mins)
            row_dicts.append({
                "work_orders": "+".join(sorted(r["work_orders"])) or "?",
                "op_seq": r["op_seq"],
                "setup_family": r["setup_family"],
                "machine": r["machine"],
                "start": _fmt_ts(r["start"]),
                "end": _fmt_ts(r["end"]),
                "lateness_minutes": lateness_min,
            })

        # CU2 (Session 4A.2d) — a scope-placeholder is never a final answer. An
        # empty listing scoped to a real entity is an honest sentence ("Nothing
        # scheduled for CUT-01"); an empty listing scoped to "all" (no filter
        # resolved) must NOT read "Nothing scheduled for all" — say plainly there
        # is nothing to list, naming no placeholder.
        empty_msg = ""
        if not row_dicts:
            empty_msg = ("I don't see any scheduled operations matching that."
                         if label == "all"
                         else f"Nothing scheduled for {label}.")

        # CU3 (Session 4A.2d) — a direct "when does X finish / start" question
        # leads with the asked quantity (the completion), then the table
        # supplements. Computed for a single-order listing when the question is a
        # timing question; the demand's due date grounds the early/late span.
        direct = None
        _timing = any(w in q for w in
                      ("when", "finish", "complete", "done", "ready", "due", "start"))
        if flt.get("work_order") and row_dicts and _timing:
            order = flt["work_order"]
            ends = [r["end"] for r in row_dicts if r["end"]]
            starts = [r["start"] for r in row_dicts if r["start"]]
            finish = max(ends) if ends else ""
            begin = min(starts) if starts else ""
            dem = self._demand_by_order(order)
            due = dem.get("due") if dem else None
            delta_days = None
            fdt = _to_dt(finish)
            ddt = _to_dt(due)
            if fdt is not None and ddt is not None:
                delta_days = round((ddt - fdt).total_seconds() / 86400, 1)
            direct = {
                "order": order,
                "finish": finish,
                "begin": begin,
                "due": _fmt_date(due),
                "delta_days": delta_days,
                "late": (delta_days is not None and delta_days < 0),
            }

        return ExplanationBundle(
            question=question,
            subject_id=label,
            subject_type="schedule",
            subject_external_name=label,
            ordered_records=[],
            key_facts={
                "filter_label": label,
                "rows": row_dicts,
                "total_rows": len(row_dicts),
                "machine_count": len({r["machine"] for r in row_dicts}),
                "direct_answer": direct,
                "empty_message": empty_msg,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _build_schedule_filter(
        self, q: str, wo_ref: Optional[str], machine_ref: Optional[str]
    ) -> tuple[dict, str]:
        """Return (filter_dict, human_label)."""
        flt: dict[str, Any] = {}
        label_parts: list[str] = []

        if wo_ref:
            flt["work_order"] = wo_ref.upper()
            label_parts.append(flt["work_order"])
        if machine_ref:
            flt["machine"] = machine_ref.upper()
            label_parts.append(flt["machine"])

        # Time window
        now = datetime.now(timezone.utc)
        date_m = re.search(r'\d{4}-\d{2}-\d{2}', q)
        if "today" in q:
            d = now.date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append("today")
        elif "tomorrow" in q:
            d = (now + timedelta(days=1)).date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append("tomorrow")
        elif "this week" in q:
            d = now.date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=7)
            label_parts.append("this week")
        elif date_m:
            from datetime import date as _date
            d = _date.fromisoformat(date_m.group())
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append(date_m.group())

        if "next" in q:
            flt["limit"] = 5

        # Customer
        cust_m = re.search(r'customer\s+(\S+)', q)
        if cust_m:
            flt["customer"] = cust_m.group(1).strip("?.,!")
            label_parts.append(f"customer {flt['customer']}")

        # Pool words (for "casting", "gear", etc. when no machine regex matched)
        if not flt.get("machine") and not flt.get("work_order") and not flt.get("customer"):
            _STOP = {"how", "much", "does", "do", "have", "any", "is", "are", "the",
                     "a", "an", "for", "in", "what", "which", "show", "me",
                     "schedule", "scheduled", "running", "on", "next", "full",
                     "when", "start", "finish", "complete", "will", "does"}
            words = {w.strip("?.,!") for w in q.split()
                     if w.strip("?.,!") not in _STOP and len(w.strip("?.,!")) > 2}
            if words:
                flt["pool_words"] = words

        label = " / ".join(label_parts) if label_parts else "all"
        return flt, label

    def _resolve_pool_resource_ids(self, words: set[str]) -> set[str]:
        result: set[str] = set()
        for pool in self._reader.iter_entities("resourcepool"):
            for ref in pool.get("external_refs", []):
                pname = ref.get("value", "").lower()
                if any(w in pname for w in words):
                    result.update(pool.get("members", []))
                    break
        return result

    def _load_enriched_assignments(self) -> list[dict]:
        ops_by_id = {o["id"]: o for o in self._reader.iter_entities("operation")}
        wp_to_fuls: dict[str, list[dict]] = {}
        for f in self._reader.iter_entities("fulfillment"):
            wp_to_fuls.setdefault(f["workpackage_ref"], []).append(f)
        demands_by_id = {d["id"]: d for d in self._reader.iter_entities("demand")}
        outcomes_by_demand: dict[str, dict] = {}
        for svc in self._reader.iter_entities("serviceoutcome"):
            outcomes_by_demand[svc["demand_ref"]] = svc

        rows: list[dict] = []
        for asgn in self._reader.iter_entities("assignment"):
            op_id = asgn.get("operation_ref", "")
            wp_id = asgn.get("workpackage_ref", "")
            op = ops_by_id.get(op_id, {})

            res_id = ""
            for ra in asgn.get("resource_assignments", []):
                ra_dict = ra if isinstance(ra, dict) else vars(ra)
                res_id = ra_dict.get("resource_ref", "")
                break

            machine_name = res_id[:8]
            if self._identity_map and res_id:
                refs = self._identity_map.external_refs(res_id)
                # Any machine-shaped ref type (IDS uses resource_id, sample uses
                # machine_id), else the first external ref — never leave a raw
                # uuid where a planner reads it (Session 4A.2 CU6).
                mref = next((r for r in refs if r.type in _MACHINE_REF_TYPES), None)
                if mref is None and refs:
                    mref = refs[0]
                if mref:
                    machine_name = mref.value

            demand_ids = [f["demand_ref"] for f in wp_to_fuls.get(wp_id, [])]
            wo_names: list[str] = []
            customer_vals: list[str] = []
            for did in demand_ids:
                dem = demands_by_id.get(did, {})
                for ref in dem.get("external_refs", []):
                    if ref.get("type") in _ORDER_REF_TYPES:
                        wo_names.append(ref["value"])
                    elif ref.get("type") == "customer":
                        customer_vals.append(ref["value"])

            run_windows = asgn.get("phase_windows", {}).get("run", [])
            start_str = run_windows[0]["start"] if run_windows else ""
            end_str = run_windows[0]["end"] if run_windows else ""

            svc_facts: dict[str, dict] = {}
            for did in demand_ids:
                svc = outcomes_by_demand.get(did)
                if svc:
                    svc_facts[did] = {
                        "lateness": svc.get("lateness", ""),
                        "projected_completion": svc.get("projected_completion", ""),
                        "tardiness_cost": svc.get("tardiness_cost", 0.0),
                    }

            rows.append({
                "assignment_id": asgn["id"],
                "operation_ref": op_id,
                "workpackage_ref": wp_id,
                "op_seq": op.get("sequence"),
                "setup_family": op.get("setup_family", ""),
                "machine": machine_name,
                "resource_id": res_id,
                "start": start_str,
                "end": end_str,
                "work_orders": wo_names,
                "demand_ids": demand_ids,
                "customer_ids": customer_vals,
                "service_outcomes": svc_facts,
            })
        return rows

    @staticmethod
    def _apply_schedule_filter(
        rows: list[dict], flt: dict, target_res_ids: Optional[set[str]]
    ) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            if flt.get("work_order") and flt["work_order"] not in r["work_orders"]:
                continue
            if target_res_ids is not None and r["resource_id"] not in target_res_ids:
                continue
            if flt.get("customer") and flt["customer"].lower() not in [
                c.lower() for c in r["customer_ids"]
            ]:
                continue
            if flt.get("time_from") or flt.get("time_to"):
                try:
                    s = _parse_ts(r["start"])
                    e = _parse_ts(r["end"])
                except Exception:
                    continue
                if flt.get("time_from") and e < flt["time_from"]:
                    continue
                if flt.get("time_to") and s >= flt["time_to"]:
                    continue
            out.append(r)
        return out

    def _resolve_machine(self, machine_ref: str) -> Optional[str]:
        if self._identity_map is None:
            return None
        cid = self._identity_map.resolve("ERP", "machine_id", machine_ref)
        if cid:
            return cid
        for (sys_, ref_type, value), canon in self._identity_map._to_canonical.items():
            if ref_type in _MACHINE_REF_TYPES and value.upper() == machine_ref.upper():
                return canon
        return None

    def _resolve_wo(self, wo_ref: str) -> Optional[str]:
        if self._identity_map is None:
            return None
        cid = self._identity_map.resolve("ERP", "work_order", wo_ref)
        if cid:
            return cid
        # Any registered order-shaped external ref, any system (IDS order_id
        # etc.) — case-insensitive, in the customer's vocabulary.
        for (sys_, ref_type, value), canon in self._identity_map._to_canonical.items():
            if ref_type in _ORDER_REF_TYPES and value.upper() == wo_ref.upper():
                return canon
        return None

    def _unknown(self, question: str, ref: str, entity_type: str) -> ExplanationBundle:
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type=entity_type,
            subject_external_name=ref,
            ordered_records=[],
            key_facts={"error": f"Unknown {entity_type}: {ref}"},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )


# ---------------------------------------------------------------------------
# Module-level helpers (no snapshot access required)
# ---------------------------------------------------------------------------

def _parse_iso_duration_minutes(s: str) -> float:
    """Parse ISO 8601 duration like 'PT840M' or '-P5DT6H57M' to minutes.

    Pydantic serializes timedeltas ≥ 365 days with a years component
    ('-P3Y34DT10H34M', Y = exactly 365 days) — placeholder-date demands
    (due ~3y out, docs/06 Appendix A) produce these routinely.
    """
    if not s:
        return 0.0
    negative = s.startswith("-")
    s = s.lstrip("-")
    m = re.match(
        r'P(?:(\d+)Y)?(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?',
        s,
    )
    if not m:
        return 0.0
    years = float(m.group(1) or 0)
    days = float(m.group(2) or 0)
    hours = float(m.group(3) or 0)
    minutes = float(m.group(4) or 0)
    seconds = float(m.group(5) or 0)
    total = years * 365 * 1440 + days * 1440 + hours * 60 + minutes + seconds / 60
    return -total if negative else total


_WHY_EARLY_RE = re.compile(
    r"\bso early\b|\btoo early\b|\bvery early\b|\bquite early\b"
    r"|\balready (?:start|runn|goi|beg|under ?way)"
    r"|\bnot due (?:until|for|till)\b|\bbefore (?:it'?s|its) due\b"
    r"|\bahead of (?:its? |the )?(?:due|schedule)\b|\bwell ahead\b"
    r"|\bwhy so soon\b|\bstart(?:s|ed|ing)? (?:so )?early\b"
    r"|\brunning early\b|\bearly\?", re.IGNORECASE)


def _is_why_early(question: str) -> bool:
    """True when the question asks why an order is EARLY (an adjective/soon cue),
    NOT the comparative "why can't it start EARLIER/SOONER" (the lower-bound
    question). The comparative forms are excluded so the two never collide."""
    ql = (question or "").lower()
    if any(w in ql for w in ("earlier", "sooner", "cant start", "can't start",
                             "cannot start", "start earlier", "not sooner")):
        # a comparative "why not earlier" is a LOWER-bound question, unless it ALSO
        # carries a strong why-early cue (a due-date comparison).
        if not ("not due" in ql or "already start" in ql or "so early" in ql):
            return False
    return bool(_WHY_EARLY_RE.search(ql))


def _load_catalog_safe() -> Any:
    """The frozen remediation catalog, or None if it can't load — so a finding
    render degrades to (subject, value, cause) without the fix, never raises."""
    try:
        from mre.catalog import load_catalog
        return load_catalog()
    except Exception:
        return None


def _fmt_date(s: Optional[str]) -> Optional[str]:
    """ISO datetime/date → 'YYYY-MM-DD', or None."""
    if not s:
        return None
    return str(s)[:10]


def _weekday(s: Optional[str]) -> Optional[str]:
    """The weekday name for an ISO timestamp/date ('Friday'), or None."""
    if not s:
        return None
    try:
        return _parse_ts(str(s).replace(" ", "T") if "T" not in str(s) and " " in str(s)
                         else str(s)).strftime("%A")
    except Exception:
        try:
            from datetime import date as _d
            return _d.fromisoformat(str(s)[:10]).strftime("%A")
        except Exception:
            return None


def _parse_ts(s: str) -> datetime:
    """Parse 'Z'-suffixed or offset ISO timestamp to aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _to_dt(s: Optional[str]) -> Optional[datetime]:
    """Best-effort naive datetime from an ISO timestamp, a 'YYYY-MM-DD HH:MM'
    display string, or a bare date. Timezone dropped (both operands come from the
    same run's grid, so a day-count is stable). None when unparseable."""
    if not s:
        return None
    txt = str(s).replace("Z", "").strip()
    txt = re.sub(r"[+-]\d{2}:?\d{2}$", "", txt).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt[:len("2026-01-07T10:40:00")], fmt)
        except ValueError:
            continue
    try:
        from datetime import date as _d
        d = _d.fromisoformat(txt[:10])
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return None


def _fmt_ts(s: str) -> str:
    """Truncate ISO timestamp to 'YYYY-MM-DD HH:MM' for display."""
    if not s:
        return ""
    try:
        dt = _parse_ts(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16]
