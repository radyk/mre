"""M10 — Explainer.

Strictly read-only: this module has no import of Reporter or SnapshotWriter.
It assembles ExplanationBundles from the evidence index and snapshot store,
then renders them via TemplateRenderer (all tests) or LLMRenderer (--llm flag).

Entry points:
  explainer.route("late-order", {"order": "WO-2001", "question": ...})
                                                    -> ExplanationBundle
  explainer.summarize_run()                         -> ExplanationBundle
  explainer.snapshot_diff("snap-v1", "snap-v2")     -> dict

Routing (R-AI5, Session 4A.5a): there is NONE here. The keyword router that used
to turn a question into a route id is retired -- intent arrives on the parse
contract (mre.contracts.parse) and route() is the only way in. What this module
owns is the ASSEMBLY: given a route id and resolved external refs, build the
evidence bundle. Assemblers still read the question text for their own
route-internal details (a date filter, a customer name, a swap-vs-move framing);
none of them decides WHAT was asked.
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

# External-ref types that name an order / a machine across the three adapter
# vocabularies (sample ERP, raw_data, IDS). Subjects are resolved against the
# identity map — never by assuming an id shape.
_ORDER_REF_TYPES = frozenset({"work_order", "order_id"})
_MACHINE_REF_TYPES = frozenset({"machine_id", "resource_id", "workcenter", "workcenter_id"})

# Session 4A.5a (R-AI5) — THE KEYWORD/PRECEDENCE ROUTER IS RETIRED. Every trigger
# table that used to live here (schedule / optimality / certificate / triage /
# remediation / excluded / edit / ledger / briefing / inventory / integrity /
# attribute / drill-down / start-reason / advice / solve-time / machine-list /
# maintenance / contest / hypothesis / gap / idle markers) was the deterministic
# classifier's precedence cascade, and four founder exam rounds proved the class it
# belonged to: understanding INTENT is a natural-language problem, and string
# matching kept answering the wrong question with perfect citations. Intent now
# arrives on the parse contract (mre.contracts.parse) and `route()` below is the
# only dispatch. The two marker sets that survive are ROUTE-INTERNAL parameter
# reads inside one assembler, never intent selection.

# Swap vs move — a PARAMETER of the swap/move bridge, read inside its own assembler
# (the intent that gets there is `swap-move` either way).
_SWAP_MARKERS = ("swap", "switch", "trade place", "trade the", "exchange",
                 "flip the order", "put them in the other")
_MOVE_MARKERS = ("move ", "put ", "shift ", "relocate", "reassign", "reschedule ",
                 "give it an earlier", "give it the earlier")


def _swap_move_kind(q: str) -> str:
    """'swap' when the question proposes exchanging two jobs' slots, 'move' when it
    proposes relocating one. A route-internal parameter read: by the time this runs
    the intent is already `swap-move`; this only picks which framing the bridge
    uses. Defaults to 'swap' when the wording names neither."""
    ql = (q or "").lower()
    if any(m in ql for m in _MOVE_MARKERS) and not any(m in ql for m in _SWAP_MARKERS):
        return "move"
    return "swap"


# The remediation route's "just the worst one" qualifier — a route-internal
# parameter read (the intent is `remediation` either way).
def _remediation_limit(q: str) -> "Optional[int]":
    ql = (q or "").lower()
    return 1 if ("worst" in ql or "top " in ql or "the one" in ql) else None


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
    # Session 4A.5c (R-AI5(7)) — THE ONE PROMOTED SHAPE, and the only route in this
    # table that no designer chose. It is the `aggregate-lateness` cluster of the
    # 4A.5b synthesis residue, promoted through the pipeline the ruling specifies:
    # the provenance report ranked it, tools/promotion_dossier.py drafted the
    # application, the working thread reviewed it, and THIS LINE is the signature.
    # Authority: docs/promotions/aggregate-lateness-2026-07-26.md.
    # It answers the CAUSE MIX across the late set — not the list (`late-orders`)
    # and not one order's chain (`late-order`). On PROBATION: every sweep asks its
    # shape under both paths and a contradiction demotes it automatically.
    "lateness-cause":        {"params": [],
                              "canonical": "why are so many orders late?"},
    "why-on-machine":        {"params": ["order", "machine"],
                              "canonical": "why is {order} on {machine}?"},
    "machine-schedule":      {"params": ["machine"], "canonical": "what is running on {machine}?"},
    "order-schedule":        {"params": ["order"],   "canonical": "when does {order} start and finish?"},
    # Session 4A.5a: the whole-plan listing was a route() destination the taxonomy
    # never named, so no parse could reach it. Named now (add, never repurpose).
    "schedule":              {"params": [],          "canonical": "show the full schedule"},
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
    # Session 4B.5 CU2 — the OPEN DELTA CARD route. It takes no subject slot: the
    # card IS the subject, and it arrives on the context channel, not as a param
    # the parse resolves. Reachable only when a card is open (dispatch-enforced).
    "open-card":             {"params": [],
                              "canonical": "what does this move do?"},
    "ledger-refusals":       {"params": [],          "canonical": "what questions couldn't you answer recently?"},
    # Session 4A.2 — the missing route families (CU5), the relevance guard's
    # honest destinations (CU1), drill-down (CU3), and the morning briefing (CU7).
    "order-attributes":      {"params": ["order"],   "canonical": "what are the details of {order}?"},
    "inventory":             {"params": [],          "canonical": "how many orders are in the plan?"},
    "integrity-check":       {"params": ["machine"], "canonical": "is anything double-booked?"},
    "start-reason":          {"params": ["order"],   "canonical": "why does {order} start when it does?"},
    # Session 4B.14 Item 2 — THE BLOCKER ANALYSIS. The "Why is this here?"
    # button's answer, and the route a temporal-alternative question ("why can't
    # it start Monday") must reach: the BINDING CONSTRAINT on this operation
    # starting earlier, computed per docs/05 family from the persisted document,
    # with COULDN'T distinguished from CHOSE-NOT-TO. Takes the machine too,
    # because an order-level question asked with one bar selected is about THAT
    # operation (Item 5(d)).
    "why-here":              {"params": ["order"],
                              "canonical": "why is {order} placed where it is?"},
    # Session 4B.16 Item 1 — THE COUNTERFACTUAL. The INVERSE of `why-here` over
    # the same computed bounds: not "what is holding this here" but "what would
    # have to be DIFFERENT for it to go earlier", with the threshold and the
    # arithmetic. Same subject, different predicate — which is why it is its own
    # intent rather than a paragraph appended to the blocker analysis.
    "what-would-change":     {"params": ["order"],
                              "canonical": "what would have to change for "
                                           "{order} to start earlier?"},
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
    # Session 4B.15 Item 3 — ATTRIBUTE LOOKUP. "is ORD-000013 op20 splittable"
    # and "how long does op20 take" are fully specified, zero-ambiguity reads of
    # a declared field, and both were answered with documentation because no
    # route read a field off an entity and stated it. Requires an ORDER (or a
    # machine, for a resource field); the operation is narrowed by op_seq.
    "attribute-lookup":      {"params": ["order"],
                              "canonical": "what does the record say about that?"},
    "solve-time":            {"params": [],          "canonical": "how long did the solve take?"},
    "machine-count":         {"params": [],          "canonical": "how many machines are there?"},
    # Session 4B.13 Item 2 — the cost proof becomes ASKABLE (docs/07 §5a.29).
    "solve-optimality":      {"params": [],          "canonical": "is this schedule optimal?"},
    "maintenance":           {"params": [],          "canonical": "is any maintenance scheduled?"},
    # Session 4B.3c CU4 — the ROLLING (sliced-world) routes. Live only when the
    # schedule is a rolling document (the /ask path delegates to rolling_questions,
    # which answers from the document's RollingBlock — the connector-era snapshot a
    # rolling run now persists is what unblocks this). A closed set (ROLLING_ROUTES),
    # not an ad-hoc bolt: registered here so the ledger + interpreter recognize them.
    # Session 4A.5a (R-AI5 part 1) — the confirmation-of-take bridge. The planner
    # repeats OUR OWN prior suggestion back as a question ("so move the first
    # operation to an earlier start time?"). That is a confirmation, not a new
    # instruction and not a near-miss: name the gesture, name the sandbox that
    # prices it, and hand the board back. Reached via the parse contract's
    # followup_of=confirm-take.
    "confirm-take":          {"params": [],
                              "canonical": "should I make that move on the board?"},
    # Session 4A.5b (R-AI5(4)) — "prove it": the grounding pass re-run on ONE claim
    # the assistant just made. A route id because it is a destination the dispatch
    # names and the ledger records; reached via followup_of=prove-it OR the intent
    # of the same name (the pair `confirm-take` already set the precedent for).
    "prove-it":              {"params": [],
                              "canonical": "how do you know that?"},
    "beyond-horizon":        {"params": [],          "canonical": "what's beyond the horizon?"},
    "why-not-scheduled-yet": {"params": ["order"],   "canonical": "why isn't {order} scheduled yet?"},
    "frozen":                {"params": [],          "canonical": "what's frozen?"},
    # Session 4B.6 — the coarse zone (R-SC2 amendment). `coarse-fit` takes no
    # subject: it is about the whole beyond-horizon book against capacity.
    # `bucket-load` takes an optional `bucket` (a week number or a period the
    # planner names); with none, the answer names the fullest cell it has.
    "coarse-fit":            {"params": [],          "canonical": "will the coming work fit?"},
    "bucket-load":           {"params": ["bucket"],  "canonical": "why is that week full?"},
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
    # Session 4A.5b (R-AI5(4)) — the SYNTHESIS register. The second tier's answers
    # are neither testimony (they are not assembled by a contracted route) nor
    # judgment (they are not authored advice): they are labeled open synthesis over
    # read-only evidence, hardened claim by claim. A distinct tag is the whole
    # point — a planner must be able to see which tier answered them, and the
    # per-claim markers inside the body say which SENTENCES are proven.
    "synthesis": "synthesis",
    "prove_it": "synthesis",
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
        self._cost_proof = None                  # 4B.11 CU1, lazily read once
        self._excluded_labels: set[str] = self._build_excluded_labels()
        self._order_shape_patterns: list[re.Pattern] = self._build_order_shapes()
        # Fuzzy-id tolerance (Session 4A.2b CU6): each real order ref compiled to
        # a pattern that also matches its near-miss spellings — a letter 'o' for a
        # zero (ord-o5), a missing leading zero (ORD-5), a space for the hyphen
        # (ord 05) — so a near-miss resolves (with a visible assumption) instead of
        # falling to the wrong route. Built from the learned refs, never assumed.
        self._order_fuzzy: list[tuple[re.Pattern, str]] = self._build_order_fuzzy()
        self._order_number_index: dict[int, str] = self._build_order_number_index()

    def _build_excluded_labels(self) -> set[str]:
        """Every TOKEN that names an excluded/blocked demand — the MATCH set.

        Deliberately wide: it holds both the customer's order id and the
        canonical UUID, so a planner who pastes either gets the excluded answer
        instead of a global one. It is used ONLY to decide refuse-vs-answer
        (``_order_mention``, ``_explain_unknown_entity``).

        SESSION 4B.11 CU5 — IT IS NO LONGER USED FOR DISPLAY OR FOR COUNTING,
        and that was the whole of the "60 of 102 orders are scheduled; 42
        excluded" defect (4B.10, undiagnosed). Each of 21 excluded demands
        contributed TWO members here (its UUID and its ORD- id), so the "count"
        was 2× the truth and the names shown were half raw UUIDs. See
        ``_excluded_demand_ids`` / ``_excluded_order_labels`` for the two sets
        that actually mean something.
        """
        labels: set[str] = set()
        for _did, order, tokens in self._excluded_records():
            labels |= tokens
            if order:
                labels.add(order.upper())
        return labels

    def _excluded_records(self) -> list[tuple[str, Optional[str], set[str]]]:
        """One entry per EXCLUDED/BLOCKED **order**: ``(key, order_ref, tokens)``.

        THE KEY IS THE ORDER, NOT THE FINDING AND NOT THE ID-SPACE (Session
        4B.11 CU5). The same order is excluded in two id-spaces by two layers —
        the M0 gate's subjects are SUBMISSION-space order ids (``ORD-000001``),
        the validator's are CANONICAL demand UUIDs — so keying on the raw subject
        id counts one order twice and labels one of the two copies with a
        truncated id nobody recognizes. Resolving to the planner's order ref
        first, and keying on that, collapses them into the one order they both
        describe. A finding that resolves to no order at all keeps its own key,
        because merging unnamed things would under-count.
        """
        by_order: dict[str, tuple[Optional[str], set[str]]] = {}
        try:
            findings = self._index.all_findings()
        except Exception:
            return []
        for f in findings:
            if f.get("disposition") not in ("excluded", "blocked"):
                continue
            ev = f.get("evidence", {}) or {}
            tokens = {str(c).upper() for c in
                      (ev.get("order_id"), ev.get("wono"), ev.get("demand_id"))
                      if c}
            subject_ids = [s.get("entity_id") for s in (f.get("subjects") or [])
                           if isinstance(s, dict) and s.get("entity_id")]
            # THE ORDER, in the planner's vocabulary, from whichever id-space
            # this layer speaks: the identity map for a canonical subject, the
            # learned order refs for a submission-space one, the evidence's own
            # order_id as the last resort (a REJECTED run's only identity).
            order = None
            for sid in subject_ids:
                if self._identity_map is not None:
                    erefs = self._identity_map.external_refs(sid)
                    if erefs:
                        order = erefs[0].value
                        break
                if str(sid).upper() in self._order_refs:
                    order = self._order_refs[str(sid).upper()]
                    break
            if not order and ev.get("order_id"):
                order = str(ev["order_id"])
            key = (order.upper() if order
                   else (subject_ids[0] if subject_ids
                         else (ev.get("demand_id") or "")))
            if not key:
                continue
            tokens |= {str(s).upper() for s in subject_ids}
            prev_order, prev_tokens = by_order.get(key, (None, set()))
            by_order[key] = (order or prev_order, prev_tokens | tokens)
        return [(key, order, tokens)
                for key, (order, tokens) in sorted(by_order.items())]

    @property
    def _excluded_order_labels(self) -> list[str]:
        """The excluded demands' names IN THE PLANNER'S VOCABULARY, for DISPLAY.

        Session 4B.11 CU4(c): an answer that names an order as
        ``01D65946-E8F2-5832-829B-B7D797104857`` has told the planner nothing they
        can act on and invited them to paste a UUID back. A demand whose external
        ref does not resolve falls back to a SHORT canonical id, marked as such,
        rather than a 36-character one — an honest "we have no order number for
        this" instead of a wall of hex.
        """
        out: list[str] = []
        for did, order, _tokens in self._excluded_records():
            out.append(order if order else f"(unnamed demand {str(did)[:8]})")
        return sorted(out)

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

    def _build_order_number_index(self) -> dict[int, str]:
        """Map each order's trailing NUMBER to its canonical ref, keeping only the
        numbers a single ref claims (Session 4A.3c CU4). Lets "order 5" / "ord 5"
        resolve to ORD-05 by numeric inference against the PINNED world's actual ids
        (never string synthesis; zero-padding is inferred from the real ref). A
        number two refs share is dropped — ambiguous, so it clarifies, never guesses."""
        by_num: dict[int, set[str]] = {}
        for value in self._order_refs.values():
            m = re.search(r"(\d+)\s*$", value)
            if not m:
                continue
            by_num.setdefault(int(m.group(1)), set()).add(value)
        return {n: next(iter(vs)) for n, vs in by_num.items() if len(vs) == 1}

    # "order 5" / "ord 5" / "order number 5" / "order #5" — the noun 'order'/'ord'
    # IMMEDIATELY followed by a number (optionally via number/no./#). The order/ord
    # must PRECEDE the digit, so "show 5 late orders" (a count) is never swallowed.
    _ORDER_N_RE = re.compile(
        r"\b(?:orders?|ord)\s+(?:number\s+|no\.?\s+|#\s*)?(\d+)\b", re.IGNORECASE)

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

        # CU4 (Session 4A.3c) — the founder's live register: "swap order 5 and order
        # 4" / "order 15". Resolve the bare "order N" / "ord N" form to its canonical
        # ref by numeric inference against the world's real ids. A number no ref
        # claims is left untouched (→ the honest unresolved/absent path); an
        # ambiguous number was dropped from the index (never guessed).
        def _sub_number(m: re.Match) -> str:
            ref = self._order_number_index.get(int(m.group(1)))
            if not ref:
                return m.group(0)
            notes.append((m.group(0).strip(), ref))
            return ref
        new_q = self._ORDER_N_RE.sub(_sub_number, new_q)
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
    # Public API — ONE dispatch (R-AI5(2), Session 4A.5a)
    # ------------------------------------------------------------------
    #
    # `classify()` and `answer()` are GONE. They were the deterministic
    # keyword/precedence router: a question in, a route id out, decided by a
    # cascade of trigger tables whose order encoded every patch four founder exam
    # rounds produced. R-AI5 retires that layer whole — intent now arrives on the
    # parse contract and `route()` is the only way in. There is deliberately no
    # question-to-route shim here: a fallback classifier is exactly what R-AI5(2)
    # forbids, and a private one would be the same router wearing a different name.

    def cost_proof(self):
        """This run's COST proof, read from the M6 ``solve_complete`` evidence —
        the same record the schedule document's ``solver`` block is built from
        (Session 4B.11 CU1, docs/07 §5a.23). Cached per Explainer; never raises.
        """
        if self._cost_proof is None:
            from mre.modules.cost_proof import from_evidence
            self._cost_proof = from_evidence(self._index)
        return self._cost_proof

    def route(self, route_id: str, params: dict) -> ExplanationBundle:
        """Dispatch a route id + params to its assembler — the ONE way in.

        Params carry resolved external refs (order / machine / customer / concept)
        and the question text the assemblers still read for their own route-internal
        details (a date filter, a swap-vs-move framing, a "just the worst one"
        qualifier). Nothing here decides WHAT was asked; that arrived on the parse
        contract (R-AI5(1)).

        Session 4B.11 CU1: every bundle leaves here carrying this run's COST
        PROOF. Stamping it at the ONE dispatch rather than in ~40 assemblers is
        what makes the guarantee total — a route added tomorrow inherits it, and
        no assembler can forget. The renderer decides whether it bears on the
        answer (it does when the answer states money); this only supplies it."""
        bundle = self._route_inner(route_id, params)
        try:
            if bundle is not None and isinstance(bundle.key_facts, dict):
                bundle.key_facts.setdefault("cost_proof", self.cost_proof())
                # Session 4B.13 Item 1, clause (ii): the ROUTE THAT ANSWERED,
                # stamped at the same one dispatch and for the same reason. The
                # predicate-coverage floor at the delivery seam needs to know
                # which route spoke in order to know what it was expected to
                # cover; a bundle alone carries a subject type, not a route.
                bundle.key_facts.setdefault("route_id", route_id)
                # The planner's ORIGINAL words, when the dispatch carried them.
                # Assemblers overwrite bundle.question with canonical phrasing,
                # so this is the only surviving record of what was asked.
                asked = params.get("asked_question") or params.get("question")
                if asked:
                    bundle.key_facts.setdefault("asked_question", asked)
        except Exception:  # noqa: BLE001 — a missing proof never breaks an answer
            pass
        return bundle

    def _route_inner(self, route_id: str, params: dict) -> ExplanationBundle:
        q = params.get("question", "")
        if route_id == "ledger-refusals":
            return self._explain_recent_refusals(params.get("refusals", []))
        if route_id == "triage":
            return self._explain_fix_first(q)
        if route_id == "remediation":
            limit = params.get("limit")
            return self._explain_how_to_fix(
                q, limit if limit is not None else _remediation_limit(q))
        if route_id == "certificate-testimony":
            return self._explain_data_problems(entity_ref=params.get("order"))
        if route_id == "excluded-orders":
            return self._explain_excluded_orders(q, params.get("order"))
        if route_id == "briefing":
            return self._explain_briefing(q, params.get("document"))
        if route_id == "advice":
            return self._explain_advice(q, params.get("order"))
        if route_id == "confirm-take":
            return self._explain_confirm_take(q, params.get("order"),
                                              params.get("machine"))
        if route_id == "coaching":
            concept = params.get("concept") or coaching_concept(q.lower())
            return self._explain_coaching(q, concept)
        if route_id == "attribute-lookup":
            # THE PLANNER'S OWN WORDS, not the canonical question. `q` is the
            # ROUTED question, which a subject rewrite replaces with the route's
            # canonical phrasing ("what does the record say about that?") — and
            # that phrasing names no field, so the lookup found nothing to look
            # up. `asked_question` is threaded by the dispatch for exactly this
            # class of reader (4B.13 added it for predicate coverage).
            asked = params.get("asked_question") or q
            return self._explain_attribute_lookup(
                asked, params.get("order"), params.get("op_seq"),
                params.get("machine"), params.get("prior_question") or "")
        if route_id == "solve-time":
            return self._explain_solve_time(q)
        if route_id == "machine-count":
            return self._explain_machine_count(q)
        if route_id == "solve-optimality":
            return self._explain_optimality(q)
        if route_id == "maintenance":
            return self._explain_maintenance(q)
        if route_id == "inventory":
            return self._explain_inventory(q)
        if route_id == "integrity-check":
            return self._explain_integrity(q, params.get("machine"))
        if route_id == "order-attributes":
            return self._explain_order_attributes(params.get("order"))
        if route_id == "start-reason":
            return self._explain_start_reason(params.get("order"), q,
                                              polarity=params.get("polarity"),
                                              machine_ref=params.get("machine"),
                                              op_seq=params.get("op_seq"))
        if route_id == "why-here":
            return self._explain_why_here(params.get("order"),
                                          params.get("machine"), q,
                                          op_seq=params.get("op_seq"),
                                          document=params.get("document"),
                                          challenge=params.get("challenge"))
        if route_id == "what-would-change":
            return self._explain_counterfactual(params.get("order"),
                                                params.get("machine"), q,
                                                op_seq=params.get("op_seq"),
                                                document=params.get("document"))
        if route_id == "contested-fact":
            return self._explain_contested(params.get("order"), q,
                                           claim=params.get("contested_claim"),
                                           machine_ref=params.get("machine"),
                                           op_seq=params.get("op_seq"),
                                           document=params.get("document"))
        if route_id == "swap-move":
            return self._explain_swap_move(params.get("order_a") or params.get("order"),
                                           params.get("order_b"),
                                           params.get("kind") or _swap_move_kind(q), q)
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
                params.get("mention") or params.get("order") or q,
                params.get("mention_kind") or "")
        if route_id == "open-card":
            return self._explain_open_card(q, params.get("card") or {})
        if route_id == "edit-cost":
            return self._explain_edit_cost(q)
        if route_id == "edit-summary":
            return self._summarize_edits(q)
        if route_id == "late-order":
            return self._explain_why_late(params["order"])
        if route_id == "late-orders":
            return self._list_late_orders(params.get("document"))
        if route_id == "lateness-cause":
            return self._explain_lateness_cause(q)
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
        if route_id == "synthesis":
            return self._synthesis_bundle(q, params["answer"],
                                          params.get("diverted_qualifier", ""),
                                          params.get("offers"))
        if route_id == "prove-it":
            return self._prove_it_bundle(q, params.get("claim"),
                                         params.get("answer"))
        if route_id in ("beyond-horizon", "why-not-scheduled-yet", "frozen",
                        "coarse-fit", "bucket-load"):
            return self._rolling_bundle(route_id, q, params.get("document"),
                                        params.get("order"),
                                        params.get("bucket"))
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

    def _list_late_orders(self, document: Any = None) -> ExplanationBundle:
        """Return all demands with positive lateness_minutes from the evidence index.

        ``document`` (Session 4B.13 Item 3) is the rolling schedule document when
        one is in play. NOT-LATE AND NOT-SCHEDULED ARE DIFFERENT STATES: on the
        pinned exam world 26 orders are in the window and on time while 14 sit in
        the beyond-horizon tray with no placement at all, and "No late orders
        found in this schedule." said alone lets a stranger read the tray as a
        clean bill of health. The count of late orders is unchanged and still
        comes from the evidence index — the tray count rides BESIDE it as its own
        labelled figure, never summed into it and never used to soften it.

        R-PD1 clause (4)/(6), Session 4B.11 CU4(b). Once past-due work is
        SCHEDULED rather than excluded, this route is the one a planner asks in
        the first minute of a demo — and a single fused minute-count is the wrong
        answer to it. On the specimen ORD-000014 reads "+85,495 min late", of
        which 84,240 were already on the clock before this window opened: the
        schedule added 1,255. The route therefore reports the FLOOR and the
        CONTROLLABLE part separately, and never sums them into one figure a
        planner could read as this schedule's doing.
        """
        all_ev = self._index._all_evidence
        late_metrics = [
            r for r in all_ev
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]
        # demand_id → minutes already past due at t0 (absent = nothing unavoidable)
        floors: dict[str, float] = {}
        for r in all_ev:
            if (r.get("record_type") == "metric"
                    and r.get("name") == "tardiness_floor_minutes"):
                for s in r.get("subjects", []) or []:
                    if s.get("entity_id"):
                        floors[s["entity_id"]] = float(r.get("value") or 0.0)

        late_items = []
        for m in late_metrics:
            subj_ids = [s.get("entity_id") for s in m.get("subjects", [])]
            for did in subj_ids:
                if did:
                    refs = self._identity_map.external_refs(did) if self._identity_map else []
                    wo_name = refs[0].value if refs else did[:8]
                    total = float(m.get("value") or 0.0)
                    floor = min(floors.get(did, 0.0), total)
                    late_items.append({
                        "demand_id": did,
                        "wo": wo_name,
                        "lateness_minutes": m.get("value"),
                        "floor_minutes": floor,
                        "controllable_minutes": total - floor,
                    })

        worst = max(late_items, key=lambda it: it["lateness_minutes"],
                    default=None) if late_items else None
        past_due = [it for it in late_items if it["floor_minutes"] > 0]
        # The rolling regions, when there is a rolling document. On a monolithic
        # document (or none) both stay None and the rendered answer is
        # byte-identical to its pre-4B.13 self.
        placed_n = tray_n = None
        if document is not None:
            d = document if isinstance(document, dict) else (
                document.model_dump(mode="json")
                if hasattr(document, "model_dump") else {})
            rolling = d.get("rolling") or {}
            if rolling:
                placed = set()
                for a in d.get("assignments") or []:
                    for wo in a.get("work_orders") or []:
                        if wo:
                            placed.add(str(wo))
                tray = {str(i.get("work_order")) for i in
                        (rolling.get("beyond_horizon") or []) if i.get("work_order")}
                tray -= placed          # a placed order is placed
                placed_n, tray_n = len(placed), len(tray)
        return ExplanationBundle(
            question="Are there any late orders?",
            subject_id="all",
            subject_type="late_orders",
            subject_external_name="all demands",
            ordered_records=late_metrics,
            key_facts={
                "late_count": len(late_items),
                "late_orders": [
                    # The split is IN the line, not a footnote: whoever reads only
                    # the list still cannot mistake unavoidable lateness for ours.
                    (f"{item['wo']} (+{int(item['lateness_minutes'])} min"
                     + (f"; {int(item['floor_minutes'])} already past due at the "
                        f"start, {int(item['controllable_minutes'])} added here)"
                        if item["floor_minutes"] > 0 else ")"))
                    for item in late_items
                ],
                "worst_late_order": worst["wo"] if worst else None,
                # Clause (4): two totals, stated separately, never fused.
                "past_due_at_intake_count": len(past_due),
                "tardiness_floor_minutes": sum(it["floor_minutes"] for it in late_items),
                "tardiness_controllable_minutes": sum(
                    it["controllable_minutes"] for it in late_items),
                "excluded_summary": self._excluded_summary(),
                # Item 3: the two regions, separately counted. None on a
                # monolithic board — absent, not zero.
                "scheduled_order_count": placed_n,
                "not_scheduled_order_count": tray_n,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_lateness_cause(self, question: str) -> ExplanationBundle:
        """THE PROMOTED ROUTE (R-AI5(7), Session 4A.5c) — the cause mix across the
        late set. Authority: docs/promotions/aggregate-lateness-2026-07-26.md.

        The dossier's evidence-assembly pattern, implemented deterministically:
        the whole lateness set (enumerable in one read, which is what lets a COUNT
        be stated rather than sampled), each late order's assignment driver and its
        concrete blocked-by fact, and the tardiness lines from the cost ledger. All
        three are the SAME readers the synthesis tier called through the tool
        surface — a promotion is not a reimplementation, it is this evidence
        assembled deterministically instead of agentically.

        TWO HONESTY RULES the dossier carried over from R-AI5(6), and they are the
        reason this route is safe to contract at all:

          * **The premise is checked, not assumed.** "Why are so many orders late"
            asked of a plan with one late order is answered by saying so. The
            synthesis tier did exactly this ("the premise ... does not match the
            data") and it is the single most useful thing this shape says; a route
            that skipped straight to causes would be a worse answer than the one it
            replaced.
          * **A cause the evidence does not carry stays out.** Each late order
            contributes a driver phrase and, where the solved occupancy shows one, a
            named blocker. Where it shows nothing, the answer says the cause is not
            attributable rather than reaching for one. An interpretive claim does
            not become true by being assembled deterministically — promoting a take
            into testimony would be worse than not promoting at all.
        """
        late_bundle = self._list_late_orders()
        kf = late_bundle.key_facts
        late_count = int(kf.get("late_count", 0) or 0)
        records = list(late_bundle.ordered_records)

        # The whole book, so "N of M" is enumerable rather than sampled.
        total_orders = 0
        if self._reader is not None:
            try:
                total_orders = sum(1 for _ in self._reader.iter_entities("demand"))
            except Exception:  # noqa: BLE001 — a count is never worth a raise
                total_orders = 0

        # Per late order: the driver the assignment recorded and the concrete
        # blocked-by fact from the solved occupancy.
        causes: list[dict] = []
        for item in kf.get("late_orders", []) or []:
            order = str(item).split(" ")[0]
            detail = self._explain_why_late(order)
            dkf = detail.key_facts
            causes.append({
                "order": order,
                "lateness_minutes": dkf.get("lateness_minutes"),
                "driver_code": dkf.get("driver_code"),
                "driver_phrase": dkf.get("driver_phrase"),
                "blocked_by": dkf.get("blocked_by"),
            })
            records.extend(r for r in detail.ordered_records if r not in records)

        # The cause MIX: driver phrase -> the orders it accounts for. This is the
        # whole point of the shape — one order's chain is `late-order`; what the
        # planner asked is which chains repeat.
        mix: dict[str, list] = {}
        for c in causes:
            phrase = c["driver_phrase"] or "no recorded driver"
            mix.setdefault(phrase, []).append(c["order"])
        unattributed = [c["order"] for c in causes if not c["driver_phrase"]]

        # The money, from the ledger's tardiness lines.
        tardiness_total = 0.0
        tardiness_lines: list[dict] = []
        if self._reader is not None:
            try:
                demands = {d.get("id"): d for d in self._reader.iter_entities("demand")}
                for svc in self._reader.iter_entities("serviceoutcome"):
                    cost = float(svc.get("tardiness_cost") or 0.0)
                    if not cost:
                        continue
                    dem = demands.get(svc.get("demand_ref")) or {}
                    order = ""
                    for ref in dem.get("external_refs", []) or []:
                        if ref.get("type") in ("order_id", "work_order"):
                            order = ref["value"]
                            break
                    tardiness_total += cost
                    tardiness_lines.append({"order": order or "?",
                                            "cost": round(cost, 2)})
            except Exception:  # noqa: BLE001
                tardiness_lines = []
        tardiness_lines.sort(key=lambda r: -r["cost"])

        return ExplanationBundle(
            question=question or "Why are so many orders late?",
            subject_id="all",
            subject_type="lateness_cause",
            subject_external_name="all demands",
            ordered_records=records,
            key_facts={
                "late_count": late_count,
                "total_orders": total_orders,
                "on_time_count": max(0, total_orders - late_count) if total_orders else None,
                # The premise check. A route that answers "why are so many late" on
                # a plan with 0 or 1 late orders must lead with that fact.
                "premise_holds": late_count > 1,
                "causes": causes,
                "cause_mix": [{"cause": phrase, "orders": orders}
                              for phrase, orders in sorted(
                                  mix.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
                "unattributed": unattributed,
                "worst_late_order": kf.get("worst_late_order"),
                "tardiness_total": round(tardiness_total, 2),
                "tardiness_lines": tardiness_lines,
                "excluded_summary": kf.get("excluded_summary"),
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

    def _machine_exists(self, machine_ref: str) -> bool:
        """Does the plant declare a machine by this external name?"""
        if not machine_ref:
            return False
        target = machine_ref.strip().upper()
        try:
            for r in self._reader.iter_entities("resource"):
                for ref in (r.get("external_refs") or []):
                    if str(ref.get("value") or "").upper() == target:
                        return True
        except Exception:  # noqa: BLE001
            return False
        return False

    def _verify_placement_premise(self, wo_ref: str,
                                  machine_ref: str) -> Optional[dict]:
        """CLAUSE (i) OF THE RELEVANCE GUARD (Session 4B.13 Item 1).

        A question of the form "why is X on Y" ASSERTS a fact about the world.
        Verify it before adopting it. Returns None when the premise HOLDS (or
        cannot be checked, which is never treated as a failure); otherwise a dict
        describing how it fails, for the correction bundle.

        THE SPECIMENS, both reproduced against the live registered board:

          "why is ORD-000023 on MILL-01"  -> ORD-000023 has exactly one operation
              and it is on PRESS-FAST. The answer asserted the false placement in
              its first sentence and printed the true one in the evidence block
              directly below it.
          "why did ORD-000009 end up on CUT-01" -> it runs MILL-02, ASM-01,
              FINISH-01. False twice: the placement, and an added claim that
              CUT-01 "is the only machine that can run it" about a machine the
              order never touches.

        Both routes ACCEPTED the machine from the utterance and never checked it
        against the placement they were about to explain. A stranger who mistypes
        or guesses a machine name off the board got a fluent falsehood with an
        evidence chain attached — the worst failure mode this product has,
        because the evidence block makes it look audited.

        A false premise is CORRECTED, with evidence, not answered around. That is
        R-AI3's register ladder doing its job — testimony first, disagreement met
        with warm evidence — and it is a BETTER answer than the one it replaces,
        not a refusal.
        """
        if not machine_ref:
            return None
        try:
            rows = self._order_rows(wo_ref)
        except Exception:  # noqa: BLE001 — unreadable is not refuted
            return None
        if not rows:
            # No placements to contradict: the order may be beyond-horizon or
            # unscheduled. Other routes own that disposition; this guard only
            # refutes a relation it can see is false.
            return None
        actual = []
        for r in rows:
            m = r.get("machine")
            if m and m not in actual:
                actual.append(m)
        if machine_ref.strip().upper() in {m.upper() for m in actual}:
            return None                      # the premise HOLDS
        return {
            "order": wo_ref,
            "claimed_machine": machine_ref,
            "actual_machines": actual,
            # A machine that does not exist in the plant at all is a DIFFERENT
            # correction from one that exists but carries none of this order's
            # work — a stranger mistyping a name needs to be told which.
            "claimed_machine_exists": self._machine_exists(machine_ref),
            "rows": rows,
        }

    def _premise_correction(self, question: str, bad: dict) -> ExplanationBundle:
        """The bundle a refuted premise produces (Item 1, clause (i)). Carries the
        REAL placements as its evidence chain, so the correction is cited exactly
        as an answer would be."""
        return ExplanationBundle(
            question=question,
            subject_id=self._resolve_wo(bad["order"]) or bad["order"],
            subject_type="premise_correction",
            subject_external_name=bad["order"],
            ordered_records=[],
            key_facts={
                "order": bad["order"],
                "claimed_machine": bad["claimed_machine"],
                "claimed_machine_exists": bad["claimed_machine_exists"],
                "actual_machines": bad["actual_machines"],
                "placements": [
                    {"machine": r.get("machine"), "seq": r.get("op_seq"),
                     "start": r.get("start"), "end": r.get("end")}
                    for r in bad["rows"]
                ],
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_on_machine(self, wo_ref: str, machine_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} on {machine_ref}?", wo_ref, "demand")

        # THE FLOOR, before any cause is assembled: this route's whole question
        # presupposes the placement. If the placement is false the cause is
        # unanswerable, and every sentence built on it inherits the falsehood.
        bad = self._verify_placement_premise(wo_ref, machine_ref)
        if bad is not None:
            return self._premise_correction(
                f"Why is {wo_ref} on {machine_ref}?", bad)

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
        # THE CAUSE MUST BE THE CAUSE OF *THIS* PLACEMENT (Session 4B.13 Item 1,
        # the predicate-coverage discipline applied within a matched route).
        #
        # A multi-operation order carries one assignment Decision PER OPERATION,
        # and this loop used to take the first one with a driver — whichever
        # `lineage_walk` returned first. Asked "why is ORD-000012 on PAINT-01"
        # (a TRUE premise, seq 30) it answered from the decision about the same
        # order's CUT-01 operation (seq 10) and reported that cause — "the
        # cheaper option once every cost was weighed" — as the reason for the
        # PAINT-01 placement. Same family as the false-premise defect above: the
        # route never checked what it was explaining against what was asked.
        # Prefer the decision whose chosen resource IS the named machine; fall
        # back to the old order-wide behaviour only when none can be matched, so
        # a single-operation order is unaffected.
        target_machine = (machine_ref or "").strip().upper()

        def _decision_machine(rec: dict) -> str:
            rid = (rec.get("chosen") or {}).get("resource_id", "")
            if not rid or self._identity_map is None:
                return ""
            refs = self._identity_map.external_refs(rid)
            return (refs[0].value if refs else "").upper()

        ranked = assignment_records
        if target_machine:
            on_machine = [r for r in assignment_records
                          if _decision_machine(r) == target_machine]
            if on_machine:
                ranked = on_machine + [r for r in assignment_records
                                       if r not in on_machine]

        cause = None
        driver_code = None
        for r in ranked:
            cause = driver_phrase(r.get("driver"))
            if cause:
                driver_code = r.get("driver")
                hedge = driver_hedge(r.get("driver"))
                if hedge:
                    cause = f"{cause} {hedge}"
                break

        # Session 4B.5 CU3(a) — THE VACUOUS-CAUSAL SPECIMEN, fixed at its path.
        #
        # The founder asked "why is ORD-000008 on PAINT-02?" and got "because the
        # machine was busy with other work [record: bafa03f1…]". The audit: the
        # record is a REAL assignment Decision (driver CAPACITY_BLOCKED, basis
        # reconstructed) and the clause is `DRIVER_PHRASING["CAPACITY_BLOCKED"]`
        # VERBATIM. So the verbatim path is intact — this was NOT an LLM reword of
        # authored copy (the 4A.5b CU4 breach class). The defect is here: the
        # driver phrase was used as the WHOLE causal clause, and for
        # CAPACITY_BLOCKED that phrase says nothing a planner can check. It names
        # no machine, no alternative, no quantity — and on a why-on-MACHINE
        # question it is not merely thin, it is pointing at a DIFFERENT machine
        # (the busy one is the one the order did NOT get). The testimony validator
        # passed it because every check it makes is about FABRICATION, and an
        # unfalsifiable sentence fabricates nothing.
        #
        # A capacity-forced placement has a concrete story in the solved
        # occupancy: which eligible alternatives existed, and what was running on
        # them at the time. Read it. When it cannot be read, the answer says the
        # placement was capacity-forced AND that the occupancy does not show which
        # alternative was blocked — an unattributable cause named as
        # unattributable, never given an invented mechanism (the RUBRIC's own
        # rule, carried over from the promoted lateness-cause route).
        blocked_alternatives = only_option = None
        if driver_code == "CAPACITY_BLOCKED":
            forced = self._capacity_forced_alternatives(wo_ref, machine_ref)
            if forced is not None:
                blocked_alternatives = forced["alternatives"]
                only_option = forced["only_option"]

        return ExplanationBundle(
            question=f"Why is {wo_ref} on {machine_ref}?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=ranked or records,
            key_facts={"machine_ref": machine_ref, "cause": cause,
                       "order": wo_ref, "driver_code": driver_code,
                       "blocked_alternatives": blocked_alternatives,
                       "only_option": only_option},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _capacity_forced_alternatives(self, order_ref: str,
                                      machine_ref: str) -> Optional[dict]:
        """Session 4B.5 CU3(a) — what a CAPACITY_BLOCKED placement actually means,
        read from the solved occupancy: the ELIGIBLE machines this order's step
        could have run on instead, and what was occupying each of them while it
        ran. Real evidence, never fabricated.

        Returns ``{"alternatives": [...], "only_option": bool}`` — each entry
        ``{machine, blocker_order, from, until}`` — or None when the eligibility or
        the placement cannot be read at all. THREE different facts, which the
        answer states differently and never collapses:

          * alternatives, occupied   -> name them and what held them;
          * no alternatives at all   -> this machine was the only one that can
                                        run the step (a capability fact, not a
                                        capacity one);
          * alternatives, none shown -> say the occupancy does not attribute it,
            occupied                    rather than invent a mechanism.

        Collapsing those three into one sentence is exactly how "the machine was
        busy with other work" came to be the answer to "why is it on PAINT-02"."""
        try:
            rows = self._order_rows(order_ref)
        except Exception:  # noqa: BLE001
            return None
        chosen = next((r for r in rows
                       if r["machine"].upper() == (machine_ref or "").upper()),
                      rows[0] if rows else None)
        if not chosen or not chosen.get("start") or not chosen.get("end"):
            return None
        try:
            my_start, my_end = _parse_ts(chosen["start"]), _parse_ts(chosen["end"])
        except Exception:  # noqa: BLE001
            return None

        eligible = self._eligible_machine_names(chosen.get("operation_ref"))
        if eligible is None:
            return None
        others = [m for m in eligible
                  if m.upper() != chosen["machine"].upper()]
        if not others:
            # a CAPABILITY fact, not a capacity one — and worth saying, because it
            # means no rearrangement of the plan would have changed this placement.
            return {"alternatives": [], "only_option": True}

        out: list[dict] = []
        for row in self._load_enriched_assignments():
            if row["machine"] not in others or not row.get("start") \
                    or not row.get("end"):
                continue
            if order_ref.upper() in [w.upper() for w in row["work_orders"]]:
                continue
            try:
                r_start, r_end = _parse_ts(row["start"]), _parse_ts(row["end"])
            except Exception:  # noqa: BLE001
                continue
            if r_end <= my_start or r_start >= my_end:
                continue                   # not occupied while our step ran
            out.append({
                "machine": row["machine"],
                "blocker_order": "+".join(sorted(row["work_orders"])) or "?",
                "from": _fmt_ts(row["start"]),
                "until": _fmt_ts(row["end"]),
            })
        # one entry per alternative machine, the earliest overlap kept
        seen: dict[str, dict] = {}
        for entry in out:
            seen.setdefault(entry["machine"], entry)
        return {"alternatives": sorted(seen.values(), key=lambda e: e["machine"]),
                "only_option": False}

    def _machine_name(self, res_id: str) -> Optional[str]:
        """A resource id → the planner's own name for it, via the identity map —
        the same bridge ``_load_enriched_assignments`` uses, so the two agree. None
        when the map carries no external ref (never a raw uuid in an answer)."""
        if not res_id or not self._identity_map:
            return None
        try:
            refs = self._identity_map.external_refs(res_id)
        except Exception:  # noqa: BLE001
            return None
        mref = next((r for r in refs if r.type in _MACHINE_REF_TYPES), None)
        if mref is None and refs:
            mref = refs[0]
        return mref.value if mref else None

    def _eligible_machine_names(self, op_id: Optional[str]) -> Optional[list[str]]:
        """The machines an operation may run on by CAPABILITY, in planner
        vocabulary. None when the operation or its requirements cannot be read —
        the honest "I don't know what the alternatives were", which the answer
        states rather than papering over."""
        if not op_id:
            return None
        try:
            from mre.modules.eligibility import capability_eligible
            op = next((o for o in self._reader.iter_entities("operation")
                       if o["id"] == op_id), None)
            if op is None:
                return None
            resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
            ids = capability_eligible(op.get("resource_requirements"), resources)
            names = [nm for nm in (self._machine_name(rid) for rid in ids) if nm]
            return names or None
        except Exception:  # noqa: BLE001 — an unreadable eligibility is "unknown"
            return None

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

    def _explain_excluded_orders(self, question: str,
                                 order: Optional[str] = None) -> ExplanationBundle:
        """The excluded-orders story (Session 4.5 CU4): enumerate every order
        dropped from the plan and why — a finding with disposition ``excluded``
        or ``blocked``, from ANY layer (gate rule, adapter, validator). The
        customer's report card may never be blinder than dq_report.md, which
        already lists adapter + validator exclusions; this makes the same data
        enumerable in the certificate conversation. Full conversational polish is
        4A.2 — this surfaces the DATA (each excluded order, in the customer's
        vocabulary, with its reason/code/severity/module).

        SESSION 4B.11 CU4(d) — IT ANSWERS THE QUESTION THAT WAS ASKED. "Why was
        ORD-000014 excluded?" used to return ALL TWENTY-ONE exclusions with the
        subject resolved as "excluded orders" (4B.10 §5a.26(e)): a one-order
        question answered with an aggregate, which is the same category error as
        answering "where is my order" with a plant summary. When an order is
        named, the answer is about THAT order — including the case where it was
        not excluded at all, which is now said plainly instead of being buried in
        a list of twenty others.
        """
        excluded = [
            f for f in self._index.all_findings()
            if f.get("disposition") in ("excluded", "blocked")
        ]
        subject_of_interest = None
        if order:
            subject_of_interest = self.resolve_order_value(order) or order
            target = subject_of_interest.upper()
            canon = self._resolve_wo(subject_of_interest)

            def _about_target(f: dict) -> bool:
                ev = f.get("evidence", {}) or {}
                if str(ev.get("order_id", "")).upper() == target:
                    return True
                for s in f.get("subjects", []) or []:
                    sid = s.get("entity_id") if isinstance(s, dict) else ""
                    if not sid:
                        continue
                    if canon and sid == canon:
                        return True
                    if str(sid).upper() == target:
                        return True
                    if self._identity_map is not None:
                        erefs = self._identity_map.external_refs(sid)
                        if erefs and erefs[0].value.upper() == target:
                            return True
                return False

            excluded = [f for f in excluded if _about_target(f)]
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
                    # CU4(c): the planner's own vocabulary first; the raw
                    # canonical id is the LAST resort, not a co-equal label.
                    "order": label or ev.get("order_id") or sid,
                    "code": f.get("code", ""),
                    "severity": f.get("severity", ""),
                    "module": f.get("module", ""),
                    # R-PD1 clause (3): the module that actually removed it, as
                    # the finding itself states. A demand removed downstream of a
                    # gate that said "proceed" must be traceable to the module
                    # that overrode that, by name.
                    "excluded_by": ev.get("excluded_by_module") or f.get("module", ""),
                    "reason": f.get("message", "") or ev.get("reason", ""),
                })
        return ExplanationBundle(
            question=question or "which orders were excluded from the plan?",
            subject_id=subject_of_interest or self._snap_id,
            subject_type="findings",
            subject_external_name=subject_of_interest or "excluded orders",
            ordered_records=excluded,
            key_facts={
                "excluded_orders": orders,
                "excluded_count": len(orders),
                "codes": sorted({o["code"] for o in orders}),
                # CU4(d): the named order, so the renderer can say "ORD-14 was
                # NOT excluded" rather than falling through to the clean-submission
                # line, which would be true of the SUBMISSION and silent about the
                # order actually asked about.
                "entity_ref": subject_of_interest,
                # …and whether it is actually on the board, so the not-excluded
                # answer can say WHERE it is instead of only where it isn't.
                "subject_is_scheduled": (
                    bool(self._order_rows(subject_of_interest))
                    if subject_of_interest else None),
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
        audit found into a trust feature. None when nothing was excluded.

        SESSION 4B.11 CU5 — THE ARITHMETIC, RECONCILED. This note read
        "60 of 102 orders are scheduled; 42 excluded" in a world of 60 demands
        with 21 exclusions (4B.10, reported undiagnosed). TWO independent errors,
        both here, and they compounded:

          (1) the COUNT came from ``_excluded_labels``, a TOKEN set holding both
              the UUID and the ORD- id of every excluded demand — so 21 became
              42, and the names shown were whichever half sorted first (the
              UUIDs). It now counts DEMANDS, via ``_excluded_records``.
          (2) ``scheduled`` counted EVERY demand entity in the snapshot —
              including the excluded ones — and ``total`` was then that number
              PLUS the exclusions, double-counting them: 60 + 42 = 102 in a
              60-order world.

        The invariant this note must satisfy, and now does:
        ``scheduled + count == total`` AND ``total == demands in the snapshot``.
        """
        orders = self._excluded_order_labels
        if not orders:
            return None
        total = 0
        if self._reader is not None:
            try:
                total = len(list(self._reader.iter_entities("demand")))
            except Exception:
                total = 0
        count = len(orders)
        # A snapshot read that failed (or a demand excluded before it was ever
        # written) must never produce a NEGATIVE scheduled count.
        scheduled = max(0, total - count)
        return {
            "orders": orders,
            "count": count,
            "scheduled": scheduled,
            "total": max(total, count),
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

    def _blocked_by(self, order_ref: str,
                    row: Optional[dict] = None) -> Optional[dict]:
        """The CU4 blocked-by fact: the job that occupied this operation's machine
        immediately before it started (the concrete cause behind a
        CAPACITY_BLOCKED driver). Read from the solved occupancy — real evidence,
        never fabricated. None when nothing directly precedes it.

        Session 4B.14 Item 1: the fact now carries its own SUFFICIENCY. The
        blocker is the LAST thing on the machine before this operation, which is
        a true statement and was never the whole cause — the answer built on it
        went on to claim "so it took the next opening", an arithmetic identity
        nobody checked. ``accounts_for_start`` is that check, and
        ``causal_sufficiency`` carries the blockers in between when it fails.

        Session 4B.14 Item 5(d): ``row`` selects WHICH operation is being
        explained. It defaulted to the order's first, so a question asked with
        ORD-000013 selected on PAINT-01 was answered about CUT-01."""
        rows = self._order_rows(order_ref)
        if not rows or not rows[0].get("start"):
            return None
        first = row if (row is not None and row.get("start")) else rows[0]
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
        suff = self._sufficiency_of(machine, blocker.get("end"),
                                    first.get("start"), order_ref)
        return {
            "machine": machine,
            "blocker_order": blk_order,
            "blocker_priority": prio,
            "until": _fmt_ts(blocker["end"]),
            "my_start": _fmt_ts(first["start"]),
            "op_seq": first.get("op_seq"),
            # Item 1's floor, computed here so the sentence that cites this fact
            # can be true when it is composed, not corrected after the fact.
            "accounts_for_start": bool(suff.get("accounts")),
            "causal_sufficiency": suff,
        }

    def _sufficiency_of(self, machine: str, cited_end: Optional[str],
                        explained_start: Optional[str],
                        exclude_order: str = "") -> dict:
        """Session 4B.14 Item 1 — does "held until T, so it took the next opening"
        actually account for the start it explains?

        Arithmetic against the persisted document: the first OPEN window on the
        machine at or after T, and the placements standing between that opening
        and the start. Returns the ``causal_sufficiency`` key_fact shape, with
        display-formatted timestamps because it is quoted verbatim in copy."""
        from mre.modules.causal_sufficiency import check_next_opening

        cited = _to_dt(cited_end)
        start = _to_dt(explained_start)
        windows = self._open_windows(machine)
        occupancy = []
        for r in self._load_enriched_assignments():
            if r["machine"] != machine or not r.get("start"):
                continue
            if exclude_order and exclude_order.upper() in [
                    w.upper() for w in r["work_orders"]]:
                continue
            occupancy.append({"order": "+".join(sorted(r["work_orders"])) or "?",
                              "start": _to_dt(r["start"]),
                              "end": _to_dt(r["end"])})
        s = check_next_opening(cited_until=cited, explained_start=start,
                               open_windows=windows, occupancy=occupancy)
        return {
            "accounts": s.accounts,
            "first_opening": (s.first_opening.strftime("%Y-%m-%d %H:%M")
                              if s.first_opening else None),
            "unexplained_min": s.unexplained_min,
            "remaining": [{"order": r["order"],
                           "start": r["start"].strftime("%Y-%m-%d %H:%M"),
                           "end": r["end"].strftime("%Y-%m-%d %H:%M")}
                          for r in s.remaining],
            "undetermined": s.undetermined,
        }

    # ------------------------------------------------------------------
    # Session 4B.14 Item 2 — THE BLOCKER ANALYSIS ("why is it here?")
    # ------------------------------------------------------------------

    def _pick_op_row(self, order_ref: str, machine_ref: Optional[str] = None,
                     op_seq: Optional[int] = None) -> Optional[dict]:
        """WHICH operation an order-level question is about (Item 5(d)).

        The board selection carries the machine (and, since this session, the
        operation) the planner is pointing at; ignoring it and answering about
        ``rows[0]`` is how a question asked with ORD-000013 selected on PAINT-01
        came back about CUT-01. Resolution order: an explicit op sequence, then
        the named/selected machine, then the order's first operation — and the
        caller is expected to SAY which one it chose when it fell back."""
        rows = [r for r in self._order_rows(order_ref) if r.get("start")]
        if not rows:
            return None
        if op_seq is not None:
            for r in rows:
                if r.get("op_seq") == op_seq:
                    return r
        if machine_ref:
            name = self._machine_refs.get(str(machine_ref).upper(), machine_ref)
            for r in rows:
                if str(r.get("machine", "")).upper() == str(name).upper():
                    return r
        return rows[0]

    def _min_lag_minutes(self, pred_op: str, succ_op: str) -> float:
        """The declared min lag on the precedence edge between two operations
        (docs/05 A2), 0.0 when no edge carries one."""
        if self._reader is None:
            return 0.0
        try:
            for e in self._reader.iter_entities("precedenceedge"):
                if e.get("predecessor") == pred_op and e.get("successor") == succ_op:
                    return _parse_iso_duration_minutes(str(e.get("min_lag") or ""))
        except Exception:  # noqa: BLE001
            return 0.0
        return 0.0

    def _pin_start_for(self, op_id: str) -> Optional[datetime]:
        """An exact pinned window's start for one operation (docs/05 A7/F1), or
        None. Read from Constraint records — the only place a pin may live."""
        if self._reader is None or not op_id:
            return None
        try:
            for c in self._reader.iter_entities("constraint"):
                if c.get("constraint_type") not in ("pinned_window",
                                                    "frozen_assignment"):
                    continue
                if op_id not in (c.get("subjects") or []):
                    continue
                w = (c.get("parameters") or {}).get("window") or {}
                dt = _to_dt(w.get("start"))
                if dt is not None:
                    return dt
        except Exception:  # noqa: BLE001
            return None
        return None

    def _blocker_analysis(self, order_ref: str, machine_ref: Optional[str] = None,
                          op_seq: Optional[int] = None,
                          document: Any = None):
        """Assemble the blocker analysis for ONE placed operation, entirely from
        the persisted document (R-AI4 — never a re-solve).

        Returns ``(analysis, row)`` or ``(None, None)``."""
        got = self._blocker_inputs(order_ref, machine_ref, op_seq, document)
        if got is None:
            return None, None
        analysis, row, _inputs = got
        return analysis, row

    def _blocker_inputs(self, order_ref: str, machine_ref: Optional[str] = None,
                        op_seq: Optional[int] = None,
                        document: Any = None):
        """The blocker analysis AND the raw ladder inputs it was computed from.

        Session 4B.16 Item 1: the counterfactual re-runs the SAME scan under a
        hypothetical, so it needs the same open windows and occupancy the
        analysis used — not a second reading of them, which could differ. One
        reader, two consumers.

        Returns ``(analysis, row, inputs)`` or None. Everything the pure modules
        need is read here, because this is the layer that knows how to resolve an
        order to its rows, a machine to its calendar and an operation to its
        spec."""
        from mre.modules.blocker_analysis import analyze
        from mre.modules.calendar_utils import is_effectively_resumable

        row = self._pick_op_row(order_ref, machine_ref, op_seq)
        if row is None:
            return None
        machine = row["machine"]
        my_start, my_end = _to_dt(row["start"]), _to_dt(row["end"])

        occupied: list[tuple] = []
        holder: dict = {}
        for r in self._load_enriched_assignments():
            if r["machine"] != machine or r["assignment_id"] == row["assignment_id"]:
                continue
            for c in r.get("chunks") or []:
                cs, ce = _to_dt(c.get("start")), _to_dt(c.get("end"))
                if cs is not None and ce is not None:
                    occupied.append((cs, ce))
            rend = _to_dt(r["end"])
            if my_start is not None and rend is not None and rend <= my_start:
                if not holder or rend > holder["_end"]:
                    holder = {"order": "+".join(sorted(r["work_orders"])) or "?",
                              "_end": rend}
        holder.pop("_end", None)

        predecessors = []
        for r in self._order_rows(order_ref):
            if (r.get("workpackage_ref") != row.get("workpackage_ref")
                    or not r.get("end")):
                continue
            if (r.get("op_seq") or 0) >= (row.get("op_seq") or 0):
                continue
            predecessors.append({
                "op_seq": r.get("op_seq"), "machine": r.get("machine"),
                "end": _to_dt(r["end"]),
                "min_lag_min": self._min_lag_minutes(r["operation_ref"],
                                                     row["operation_ref"]),
            })

        demand = self._demand_by_order(order_ref) or {}
        working_min = float(row.get("run_min") or 0.0)
        min_chunk = _parse_iso_duration_minutes(str(row.get("min_chunk") or "")) \
            or None
        # R-C3's degenerate-split rule, applied exactly as the SolverBuilder and
        # the Validator apply it. The three MUST agree: an analysis that split an
        # operation the solver treats as atomic would report a fit the solver
        # cannot place, and would then call a real constraint a free choice.
        splittable = is_effectively_resumable(bool(row.get("splittable")),
                                              working_min, float(min_chunk or 0.0))

        frozen_until = None
        frozen_applies = False
        try:
            rb = (document or {}).get("rolling") if isinstance(document, dict) \
                else getattr(document, "rolling", None)
            if rb is not None:
                fu = rb.get("frozen_until") if isinstance(rb, dict) \
                    else getattr(rb, "frozen_until", None)
                frozen_until = _to_dt(fu if isinstance(fu, str) else
                                      (fu.isoformat() if fu else None))
                frozen_applies = (frozen_until is not None and my_start is not None
                                  and my_start < frozen_until)
        except Exception:  # noqa: BLE001 — a monolithic run has no rolling block
            frozen_until, frozen_applies = None, False

        open_windows = self._open_windows(machine)
        analysis = analyze(
            order=order_ref, op_seq=row.get("op_seq"), machine=machine,
            actual_start=my_start, actual_end=my_end,
            working_min=working_min, splittable=splittable,
            min_chunk_min=min_chunk,
            open_windows=open_windows,
            occupied=occupied, predecessors=predecessors,
            release=_to_dt(demand.get("earliest_start")),
            frozen_until=frozen_until, frozen_applies=frozen_applies,
            pin_start=self._pin_start_for(row["operation_ref"]),
            chosen_driver=self._first_assignment_driver(order_ref),
            holder=holder, closures=self._closures(machine))
        return analysis, row, {"open_windows": open_windows,
                               "occupied": occupied}

    def _explain_why_here(self, order_ref: Optional[str],
                          machine_ref: Optional[str] = None,
                          question: str = "", op_seq: Optional[int] = None,
                          document: Any = None,
                          challenge: Optional[dict] = None) -> ExplanationBundle:
        """"Why is this here?" — the binding constraint on this operation
        starting earlier (Item 2), and whether there was one at all.

        This is the answer the board's own button asks for. It draws the
        distinction the product could not draw before: COULDN'T (name the
        binding family, with its numbers) versus CHOSE-NOT-TO (nothing prevented
        it — the solver placed it here). ``challenge`` carries a planner's
        hypothesis when this route is answering a disagreement (Item 3), so the
        copy can address what they actually said."""
        if not order_ref:
            return self._unknown_question("why is that operation where it is?")
        if self._demand_by_order(order_ref) is None:
            return self._explain_unknown_entity(order_ref)
        analysis, row = self._blocker_analysis(order_ref, machine_ref, op_seq,
                                               document=document)
        if analysis is None or row is None:
            return self._explain_why_not_placed(order_ref)

        def _e(est) -> Optional[dict]:
            if est is None:
                return None
            return {"family": est.family, "citation": est.citation,
                    "label": est.label,
                    "at": est.est.strftime("%Y-%m-%d %H:%M") if est.est else None,
                    "because": est.because,
                    "facts": _display_facts(est.facts)}

        # Item 5(d): when the operation was chosen by fallback rather than named,
        # the answer SAYS which one it is about. A bridging sentence is cheap; a
        # planner silently answered about a different bar is not.
        rows = [r for r in self._order_rows(order_ref) if r.get("start")]
        return ExplanationBundle(
            question=f"Why is {order_ref} op{row.get('op_seq')} where it is?",
            subject_id=(self._demand_by_order(order_ref) or {}).get("id", order_ref),
            subject_type="why_here",
            subject_external_name=order_ref,
            ordered_records=self._assignment_records_for_ops(
                {row["operation_ref"]}, set(row.get("demand_ids") or [])),
            key_facts={
                "order": order_ref,
                "op_seq": row.get("op_seq"),
                "machine": analysis.machine,
                "start": _fmt_ts(row["start"]),
                "start_weekday": _weekday(row["start"]),
                "end": _fmt_ts(row["end"]),
                "run_min": row.get("run_min"),
                "span_min": row.get("span_min"),
                "chunk_count": len(row.get("chunks") or []),
                "splittable": analysis.splittable,
                "min_chunk_min": analysis.min_chunk_min,
                "verdict": analysis.verdict,
                "binding": _e(analysis.binding),
                "runner_up": _e(analysis.runner_up),
                "chain": [_e(e) for e in analysis.pushers],
                "estimates": [_e(e) for e in analysis.estimates if e.computed],
                "slack_min": analysis.slack_min,
                "chosen_driver": analysis.chosen_driver,
                "uncomputed": [{"catalog": c, "why": w}
                               for c, w in analysis.uncomputed],
                "op_count": len(rows),
                "op_named": bool(op_seq is not None or machine_ref),
                "challenge": challenge or None,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _eligible_lanes(self, op_ref: Optional[str],
                        exclude: str) -> tuple[Optional[list[dict]], bool]:
        """Every OTHER capability-eligible machine, with its free time.

        Returns ``(lanes, known)``. ``known`` is False when capability
        resolution could not be read at all — the difference between "there is
        nowhere else" and "I could not tell", which the answer must not blur.

        Free time is the machine's resolved open calendar minus everything
        already placed on it, computed through the SAME two helpers the blocker
        analysis uses, so an alternative lane is measured the way the incumbent
        lane is."""
        from mre.modules.blocker_analysis import _subtract
        names = self._eligible_machine_names(op_ref)
        if names is None:
            return None, False
        rows = self._load_enriched_assignments()
        lanes: list[dict] = []
        for name in names:
            if name == exclude:
                continue
            busy: list[tuple] = []
            for r in rows:
                if r.get("machine") != name:
                    continue
                for c in r.get("chunks") or []:
                    cs, ce = _to_dt(c.get("start")), _to_dt(c.get("end"))
                    if cs is not None and ce is not None:
                        busy.append((cs, ce))
            lanes.append({"machine": name,
                          "free": _subtract(self._open_windows(name), busy)})
        return lanes, True

    def _explain_counterfactual(self, order_ref: Optional[str],
                                machine_ref: Optional[str] = None,
                                question: str = "",
                                op_seq: Optional[int] = None,
                                document: Any = None) -> ExplanationBundle:
        """"What would have to change?" — the INVERSE of the blocker analysis
        over the same computed bounds (Session 4B.16 Item 1).

        No new bounds are computed here and none are needed: `why-here` already
        knows which docs/05 family binds, and this route reports what would move
        that bound, with its threshold and the arithmetic. Every threshold is
        verified by re-running the same scan under the hypothetical.

        THE HARD RULE, enforced by the shape of what is returned: a lever
        removes a barrier, and ``next_bound`` names what applies once it is
        gone. Nothing here claims the solver would then place the operation
        there — that needs a re-solve, which R-AI4 forbids."""
        from mre.modules.counterfactual import build

        if not order_ref:
            return self._unknown_question("what would have to change for that "
                                          "operation to start earlier?")
        if self._demand_by_order(order_ref) is None:
            return self._explain_unknown_entity(order_ref)
        got = self._blocker_inputs(order_ref, machine_ref, op_seq,
                                   document=document)
        if got is None:
            # Its OWN floor, not `why-here`'s. "There is no 'here' to explain"
            # answers a question about a placement; this one was asked about a
            # change, and the honest answer is that there is nothing placed to
            # move — which is a different sentence and a different next step.
            return ExplanationBundle(
                question=(f"What would have to change for {order_ref} to start "
                          "earlier?"),
                subject_id=(self._demand_by_order(order_ref) or {}).get(
                    "id", order_ref),
                subject_type="counterfactual",
                subject_external_name=order_ref,
                ordered_records=[],
                key_facts={"order": order_ref, "verdict": "unplaced"},
                snapshot_id=self._snap_id,
                identity_map=self._identity_map,
            )
        analysis, row, inputs = got
        lanes, known = self._eligible_lanes(row.get("operation_ref"),
                                            analysis.machine)
        cf = build(analysis,
                   open_windows=inputs["open_windows"],
                   occupied=inputs["occupied"],
                   alternatives=lanes or [],
                   eligibility_known=known)

        rows = [r for r in self._order_rows(order_ref) if r.get("start")]
        return ExplanationBundle(
            question=(f"What would have to change for {order_ref} "
                      f"op{row.get('op_seq')} to start earlier?"),
            subject_id=(self._demand_by_order(order_ref) or {}).get("id", order_ref),
            subject_type="counterfactual",
            subject_external_name=order_ref,
            ordered_records=self._assignment_records_for_ops(
                {row["operation_ref"]}, set(row.get("demand_ids") or [])),
            key_facts={
                "order": order_ref,
                "op_seq": row.get("op_seq"),
                "machine": analysis.machine,
                "start": _fmt_ts(row["start"]),
                "start_weekday": _weekday(row["start"]),
                "verdict": cf.verdict,
                "needed_min": cf.needed_min,
                "splittable": cf.splittable,
                "min_chunk_min": cf.min_chunk_min,
                "binding": ({"family": cf.binding_family,
                             "citation": cf.binding_citation,
                             "label": cf.binding_label,
                             "at": _fmt_dt(cf.binding_at)}
                            if cf.binding_family else None),
                "window": ({"start": _fmt_dt(cf.window["start"]),
                            "end": _fmt_dt(cf.window["end"]),
                            "weekday": cf.window["start"].strftime("%A"),
                            "available_min": cf.window["available_min"],
                            "needed_min": cf.window["needed_min"]}
                           if cf.window else None),
                "levers": [{"key": l.key, "citation": l.citation,
                            "spec": l.spec, "statement": l.statement,
                            "effect": l.effect,
                            "threshold_min": l.threshold_min}
                           for l in cf.levers],
                "next_bound": ({**cf.next_bound,
                                "at": _fmt_dt(cf.next_bound.get("at")),
                                "at_weekday": (
                                    cf.next_bound["at"].strftime("%A")
                                    if cf.next_bound.get("at") else None)}
                               if cf.next_bound else None),
                "closure": (_display_facts(cf.closure) if cf.closure else None),
                "alternatives": [{"machine": a["machine"],
                                  "earliest": _fmt_dt(a.get("earliest")),
                                  "earlier": a.get("earlier")}
                                 for a in cf.alternatives],
                "only_eligible": cf.only_eligible,
                "eligibility_known": cf.eligibility_known,
                "slack_min": cf.slack_min,
                "chosen_driver": cf.chosen_driver,
                "dropped": cf.dropped,
                "unpriceable": [{"catalog": c, "why": w}
                                for c, w in cf.unpriceable],
                "uncomputed": [{"catalog": c, "why": w}
                               for c, w in cf.uncomputed],
                "op_count": len(rows),
                "op_named": bool(op_seq is not None or machine_ref),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_not_placed(self, order_ref: str) -> ExplanationBundle:
        """The honest floor for a blocker question about an order with no
        placement in this window — it has no 'here' to explain."""
        return ExplanationBundle(
            question=f"Why is {order_ref} where it is?",
            subject_id=(self._demand_by_order(order_ref) or {}).get("id", order_ref),
            subject_type="why_here",
            subject_external_name=order_ref,
            ordered_records=[],
            key_facts={"order": order_ref, "verdict": "unplaced"},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

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
                              question: str = "",
                              polarity: Optional[str] = None,
                              machine_ref: Optional[str] = None,
                              op_seq: Optional[int] = None) -> ExplanationBundle:
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
        # Item 5(d): the SELECTED operation, not reflexively the order's first.
        row = self._pick_op_row(order_ref, machine_ref, op_seq) or (
            rows[0] if rows else None)
        start = row["start"] if row else None
        release = demand.get("earliest_start")
        blocked = self._blocked_by(order_ref, row=row)
        # which bound governs: release if the start sits at/after a release later
        # than the horizon open; else the machine-busy (blocked-by) cause.
        release_binds = False
        if release and start:
            try:
                release_binds = _parse_ts(start).date() <= _parse_ts(release).date() \
                    or abs((_parse_ts(start) - _parse_ts(release)).total_seconds()) < 86400
            except Exception:
                release_binds = False
        # CU3 — is this a why-EARLY question ("why is it running so early") or the
        # comparative lower-bound one ("why can't it start earlier")? Session 4A.5a:
        # the PARSE decides — polarity=positive is the placement as it stands (the
        # why-early floor), polarity=negative is the lower bound. The regex survives
        # only as the fallback for a call that carries no parsed polarity (the CLI,
        # a direct route() in a test), never as a second opinion over the parse.
        # a NEGATIVE parse ("why can't it start sooner") is the lower-bound question
        # by construction, so the early framing is ruled out whatever the wording
        # looks like. A positive parse still asks the assembler's own read whether
        # the planner said "early" or just "when it does" — the two are both
        # positive, and that distinction is route-internal (named residue).
        early = False if polarity == "negative" else _is_why_early(question)
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
            # CU2 (Session 4A.3c) — the answer narrates the order's placement, so it
            # lights the order's bars through the existing cited_refs channel. The
            # prose stays deterministic (start_reason is authored copy — see
            # LLMRenderer._AUTHORED_COPY_SUBJECTS); these records only feed lit-bars.
            ordered_records=self._assignment_records(order_ref),
            key_facts={
                "order": order_ref,
                "start": _fmt_ts(start) if start else None,
                "start_weekday": _weekday(start) if start else None,
                "release": _fmt_date(release),
                "release_weekday": _weekday(release) if release else None,
                "release_binds": bool(release and release_binds),
                "blocked_by": blocked,
                "machine": row["machine"] if row else None,
                "op_seq": row.get("op_seq") if row else None,
                "why_early": early,
                # Item 1 — the floor travels with the fact that needs it, so a
                # reworded answer that reasserts "took the next opening" is
                # still checked against the arithmetic.
                "causal_sufficiency": (blocked or {}).get("causal_sufficiency"),
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
                           question: str, claim: Optional[str] = None,
                           machine_ref: Optional[str] = None,
                           op_seq: Optional[int] = None,
                           document: Any = None) -> ExplanationBundle:
        """CU6 / R-AI3(4) — the user contests a cited fact. Meet it with warm
        EVIDENCE: restate what the record shows and offer to walk the chain. Never
        capitulate ("you're right, my mistake") and never harden (a curt
        re-assertion). The renderer composes the warmth; this assembles the facts.

        contested-wrong: the record contradicts the user's claim → hold, warmly.
        contested-agree: the record agrees with the user → confirm plainly.

        SESSION 4B.14 ITEM 3 — DISAGREEMENT IS NOT RE-PARSED. This assembler knew
        exactly ONE proposition, lateness, and its canonical question said so:
        "is {order} really on time?". So a challenge to the system's REASONING —
        "it seems it should be able to start on tuesday after op10 finishes" —
        was answered "Yes, the record agrees", an affirmative that reads as
        agreement while addressing nothing that was said. The parse now reports
        WHICH claim is disputed (``ContestedClaim``) and a TIMING challenge is
        answered by the blocker analysis, on the planner's own terms: whether
        they are right, and if not, the arithmetic that decides it. Where the
        challenge cannot be evaluated the answer says THAT, and never
        substitutes an adjacent question it can answer."""
        from mre.contracts.parse import ContestedClaim

        kind = str(claim or ContestedClaim.LATENESS.value)
        if kind == ContestedClaim.TIMING.value and order_ref:
            # Answered by the blocker analysis, carrying the challenge so the
            # copy can address the hypothesis rather than recite a placement.
            bundle = self._explain_why_here(
                order_ref, machine_ref, question, op_seq=op_seq,
                document=document,
                challenge={"kind": kind, "said": question})
            if isinstance(bundle.key_facts, dict):
                bundle.key_facts["contested"] = True
            return bundle
        if kind == ContestedClaim.OTHER.value:
            return ExplanationBundle(
                question=question or "what are you disputing?",
                subject_id=order_ref or "",
                subject_type="contested_fact",
                subject_external_name=order_ref or "",
                ordered_records=[],
                key_facts={"order": order_ref, "unevaluable": True,
                           "said": question},
                snapshot_id=self._snap_id,
                identity_map=self._identity_map,
            )
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

    def _assignment_records_for_ops(self, op_ids: set[str],
                                    demand_ids: set[str]) -> list[dict]:
        """Assignment Decisions for a SPECIFIC set of operations (the placements a
        machine/schedule listing narrates), gathered by walking each demand's
        lineage and keeping the assignment decisions whose operation subject is in
        ``op_ids`` (Session 4A.3c CU2). The lit bars are then exactly the rows the
        answer lists — capped to the shown ops, never a lane's whole history. Real
        Decision records (real record_ids), so the lit-bars channel and the
        testimony validator both stay honest. Best-effort, [] on any read failure."""
        if self._reader is None or not op_ids:
            return []
        out: list[dict] = []
        seen: set[str] = set()
        for did in demand_ids:
            try:
                recs = self._index.lineage_walk(did, snapshot_reader=self._reader)
            except Exception:
                continue
            for r in recs:
                if (r.get("record_type") != "decision"
                        or r.get("decision_type") != "assignment"):
                    continue
                if not any(s.get("entity_id") in op_ids
                           for s in r.get("subjects", []) or []):
                    continue
                rid = str(r.get("record_id") or id(r))
                if rid in seen:
                    continue
                seen.add(rid)
                out.append(r)
        return out

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

    def _machine_calendar(self, machine_name: str) -> Optional[dict]:
        """The Calendar entity behind a machine, or None."""
        rid = self._resolve_machine(machine_name)
        if rid is None or self._reader is None:
            return None
        resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
        calendars = {c["id"]: c for c in self._reader.iter_entities("calendar")}
        res = resources.get(rid)
        return calendars.get(res.get("calendar_ref")) if res else None

    def _closures(self, machine_name: str) -> list[dict]:
        """A machine's DECLARED closures (docs/05 C2) with their reasons — the
        evidence behind "after maintenance". Never inferred from a calendar gap:
        a night and a shutdown look identical in a window list, and only one of
        them is a thing the plant decided."""
        out: list[dict] = []
        for exc in (self._machine_calendar(machine_name) or {}).get(
                "exceptions", []) or []:
            if exc.get("type") != "closure":
                continue
            w = exc.get("window", {}) or {}
            s, e = _to_dt(w.get("start")), _to_dt(w.get("end"))
            if s is not None and e is not None:
                out.append({"start": s, "end": e,
                            "reason": exc.get("reason") or "closure"})
        return out

    def _open_windows(self, machine_name: str) -> list[tuple]:
        """A machine's RESOLVED open calendar over the solved span: regular
        windows plus declared additions (overtime), MINUS closures.

        Session 4B.14. ``_machine_working_windows`` expands the base pattern and
        stops there — it has never subtracted a closure, which is harmless for
        the gap resolver (it asks a separate closure question) and fatal for the
        blocker analysis, which would place work inside a maintenance day. The
        span is taken from the solved placements themselves, padded a fortnight
        each way, so no horizon plumbing is needed and a machine carrying no work
        still resolves against the same grid as one that does."""
        rows = [r for r in self._load_enriched_assignments() if r.get("start")]
        starts = [_to_dt(r["start"]) for r in rows]
        ends = [_to_dt(r["end"]) for r in rows]
        pts = [p for p in starts + ends if p is not None]
        if not pts:
            return []
        lo, hi = min(pts) - timedelta(days=14), max(pts) + timedelta(days=14)
        base = self._machine_working_windows(machine_name, lo, hi)
        if not base:
            return []
        cal = self._machine_calendar(machine_name)
        closures: list[tuple] = []
        for exc in (cal or {}).get("exceptions", []) or []:
            w = exc.get("window", {}) or {}
            s, e = _to_dt(w.get("start")), _to_dt(w.get("end"))
            if s is None or e is None:
                continue
            if exc.get("type") == "closure":
                closures.append((s, e))
            else:
                base.append((s, e))          # declared addition (overtime)
        from mre.modules.blocker_analysis import _subtract
        return _subtract(base, closures)

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

    def _explain_unknown_entity(self, mention: str,
                                kind: str = "") -> ExplanationBundle:
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
        # Session 4B.13 — a MACHINE that is not here is not an unknown ORDER.
        # A mistyped machine name off the board ("MILL-99") was answered "I don't
        # see it among the planned orders", offering orders back, which names the
        # wrong vocabulary at the one moment the planner needs the right one. The
        # kind comes from the parse; this route never infers it from the string.
        known_machines: list[str] = []
        if kind == "machine":
            try:
                names = set()
                for r in self._reader.iter_entities("resource"):
                    for ref in (r.get("external_refs") or []):
                        if ref.get("value"):
                            names.add(ref["value"])
                            break
                known_machines = sorted(names)[:8]
            except Exception:  # noqa: BLE001
                known_machines = []
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
                "mention_kind": kind,
                "known_machines": known_machines,
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

    # ------------------------------------------------------------------
    # THE OPENER (Session 4B.16 Item 2) — extraction. The board_opener module
    # decides what is worth saying and in what order; these read the facts.
    # ------------------------------------------------------------------

    @staticmethod
    def _doc(document: Any) -> dict:
        """A schedule document as a plain dict, whatever arrived. The ask path
        hands over JSON; a test or the assembler may hand over the model."""
        if document is None:
            return {}
        if isinstance(document, dict):
            return document
        if hasattr(document, "model_dump"):
            try:
                return document.model_dump(mode="json")
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _opener_late(self, doc: dict) -> tuple[list[dict], list[tuple[str, str]]]:
        """Late orders from the document's per-demand service truth (R-PD1:
        the floor beside the controllable part, never fused).

        Without a document this falls back to the evidence metrics the briefing
        has always read — the same facts, one field poorer (no due date), which
        is why at-risk is reported as unavailable in that case rather than
        guessed at."""
        outcomes = doc.get("service_outcomes") or []
        if outcomes:
            return ([{"order": o.get("work_order"),
                      "lateness_min": o.get("lateness_min"),
                      "floor_min": o.get("tardiness_floor_min"),
                      "cost": o.get("tardiness_cost")}
                     for o in outcomes if (o.get("lateness_min") or 0) > 0], [])
        floors: dict[str, float] = {}
        for r in self._index._all_evidence:
            if (r.get("record_type") == "metric"
                    and r.get("name") == "tardiness_floor_minutes"):
                for s in r.get("subjects", []) or []:
                    if s.get("entity_id"):
                        floors[s["entity_id"]] = float(r.get("value") or 0.0)
        late: list[dict] = []
        for r in self._index._all_evidence:
            if (r.get("record_type") != "metric"
                    or r.get("name") != "lateness_minutes"
                    or (r.get("value") or 0.0) <= 0):
                continue
            for s in r.get("subjects", []) or []:
                did = s.get("entity_id")
                if not did:
                    continue
                refs = (self._identity_map.external_refs(did)
                        if self._identity_map else [])
                total = float(r.get("value") or 0.0)
                late.append({"order": refs[0].value if refs else did[:8],
                             "lateness_min": total,
                             "floor_min": min(floors.get(did, 0.0), total)})
        return late, [("what those late orders cost and how much slack the "
                       "on-time ones have",
                       "the per-demand service record reaches this answer on "
                       "the schedule document, which this run did not supply")]

    def _opener_at_risk(self, doc: dict) -> list[dict]:
        """On time, with less slack than one of its own operations takes.

        The threshold is the order's OWN longest operation, read from the
        assignments' chunk minutes — so the sentence is "one hiccup on the
        longest step and this is late" rather than an arbitrary hours figure."""
        longest: dict[str, float] = {}
        for a in doc.get("assignments") or []:
            mins = sum(float(c.get("working_min") or 0)
                       for c in a.get("chunks") or [])
            for wo in a.get("work_orders") or []:
                longest[str(wo)] = max(longest.get(str(wo), 0.0), mins)
        out: list[dict] = []
        for o in doc.get("service_outcomes") or []:
            lateness = o.get("lateness_min")
            wo = str(o.get("work_order") or "")
            if lateness is None or lateness > 0 or not wo:
                continue
            slack = -float(lateness)
            op = longest.get(wo)
            if op and slack < op:
                out.append({"order": wo, "slack_min": slack,
                            "longest_op_min": op})
        return out

    def _opener_load(self) -> tuple[Optional[list[dict]], list[tuple[str, str]]]:
        """Per-machine utilization over its OWN open hours, and — for a machine
        near saturation — the eligible alternatives and their utilization.

        ELIGIBILITY IS WHAT MAKES IT A FINDING. A busy machine beside an idle
        one it shares no capability with is what a specialised cell looks like,
        not a concentration, and calling it one would be an observation dressed
        as a problem."""
        rows = [r for r in self._load_enriched_assignments() if r.get("start")]
        if not rows:
            return None, [("machine load", "this run has no placements")]
        busy: dict[str, float] = {}
        ops_on: dict[str, list[str]] = {}
        for r in rows:
            m = r.get("machine")
            if not m:
                continue
            busy[m] = busy.get(m, 0.0) + float(r.get("run_min") or 0.0)
            ops_on.setdefault(m, []).append(r.get("operation_ref"))
        # EVERY machine in the plant's vocabulary, not just the ones carrying
        # work: an IDLE eligible alternative has no rows at all, so building
        # this over `busy` alone would drop exactly the machines a
        # concentration finding is about.
        util: dict[str, float] = {}
        for m in sorted(set(self._machine_refs.values()) | set(busy)):
            open_min = sum((e - s).total_seconds() / 60.0
                           for s, e in self._open_windows(m))
            util[m] = (busy.get(m, 0.0) / open_min) if open_min > 0 else 0.0

        unknown = 0
        out: list[dict] = []
        for m, u in util.items():
            if u < 0.5:                       # only a busy lane can concentrate
                continue
            alts: dict[str, float] = {}
            for op_ref in ops_on.get(m, []):
                names = self._eligible_machine_names(op_ref)
                if names is None:
                    unknown += 1
                    continue
                for nm in names:
                    if nm != m and nm in util:
                        alts[nm] = util[nm]
            out.append({"machine": m, "utilization": u,
                        "alternatives": [{"machine": k, "utilization": v}
                                         for k, v in sorted(alts.items())]})
        notes = ([("whether the busiest machine's work could have gone "
                   "elsewhere", "capability requirements could not be read for "
                   f"{unknown} of its operations")] if unknown else [])
        return out, notes

    def _opener_closures(self, doc: dict) -> list[dict]:
        """Declared closures inside the window, grouped by (date, reason), with
        the count of operations that pause across each — "what it displaces",
        computed rather than asserted."""
        rows = [r for r in self._load_enriched_assignments() if r.get("start")]
        machines = sorted({r["machine"] for r in rows if r.get("machine")})
        if not machines:
            return []
        lo = _to_dt(doc.get("reference_date")) or min(
            (_to_dt(r["start"]) for r in rows), default=None)
        hi = max((_to_dt(r["end"]) for r in rows if r.get("end")), default=None)
        grouped: dict[tuple, dict] = {}
        for m in machines:
            for c in self._closures(m):
                s, e = c.get("start"), c.get("end")
                if s is None or e is None:
                    continue
                if (lo is not None and e < lo) or (hi is not None and s > hi):
                    continue
                key = (s.date(), c.get("reason") or "closure")
                g = grouped.setdefault(key, {
                    "date": s.strftime("%A %Y-%m-%d"),
                    "reason": (c.get("reason") or "closure").replace("_", " "),
                    "start": s, "end": e, "machines": [], "spans": 0})
                g["machines"].append(m)
                for r in rows:
                    if r.get("machine") != m or len(r.get("chunks") or []) < 2:
                        continue
                    rs, re_ = _to_dt(r["start"]), _to_dt(r.get("end"))
                    if rs is not None and re_ is not None and rs < s and re_ > e:
                        g["spans"] += 1
        for g in grouped.values():
            g["plant_wide"] = len(g["machines"]) == len(machines)
        return sorted(grouped.values(),
                      key=lambda g: (-len(g["machines"]), str(g["start"])))

    def _opener_certificate(self) -> dict:
        """The grade is not in the document (it is a SUBMISSION fact, joined on
        /meta), so the opener reports what the evidence carries: how many
        findings stand and how many the gate PROCEEDED PAST."""
        findings = sorted(
            self._index.all_findings(),
            key=lambda r: ({"blocker": 0, "error": 1, "warning": 2, "info": 3}
                           .get(r.get("severity", "info"), 9), r.get("seq", 0)))
        top = None
        if findings:
            composed = compose_finding_sentence(findings[0], self._identity_map,
                                                _load_catalog_safe())
            top = (composed or {}).get("cause")
        return {"grade": None, "count": len(findings),
                "proceeded": sum(1 for f in findings
                                 if f.get("disposition") == "proceeded_flagged"),
                "top": top}

    def _build_opener(self, document: Any):
        """Assemble the opener from the document and this run's evidence."""
        from mre.modules.board_opener import build

        doc = self._doc(document)
        unavailable: list[tuple[str, str]] = []
        if not doc:
            unavailable.append(
                ("the money at stake, slack, and everything beyond the horizon",
                 "no schedule document reached this answer, so I am reading the "
                 "evidence store alone"))
        late, notes = self._opener_late(doc)
        unavailable += notes
        at_risk = self._opener_at_risk(doc) if doc else []
        load, notes = self._opener_load()
        unavailable += notes
        rolling = doc.get("rolling") or {}
        tray = rolling.get("beyond_horizon") or []
        coarse = rolling.get("coarse_zone") or {}
        unplaced = None
        if rolling:
            dues = sorted(str(i.get("due"))[:10] for i in tray if i.get("due"))
            unplaced = {
                "count": len(tray),
                "earliest_due": dues[0] if dues else None,
                "unmodelable_count": coarse.get("unmodelable_count"),
                "infeasibility_proven": coarse.get("infeasibility_proven"),
            }
        elif doc:
            unavailable.append(
                ("work beyond the planning horizon",
                 "this is a monolithic run — it has one window and no tray"))
        derate = ({"value": coarse.get("capacity_derate"),
                   "provenance": coarse.get("capacity_derate_provenance")}
                  if coarse else None)
        if doc and not coarse:
            unavailable.append(
                ("whether the coming weeks fit",
                 "the coarse zone did not run on this solve (it is opt-in)"))
        horizon = doc.get("horizon") or {}
        return build(
            proof=self.cost_proof(),
            cost=doc.get("cost_summary") or {},
            late=late, at_risk=at_risk, concentration=load,
            closures=self._opener_closures(doc), unplaced=unplaced,
            derate=derate, certificate=self._opener_certificate(),
            scope={"reference_date": _fmt_date(doc.get("reference_date")),
                   "window_start": _fmt_date(horizon.get("start")
                                             or rolling.get("window_start")),
                   "window_end": _fmt_date(horizon.get("end")
                                           or rolling.get("window_end")),
                   "orders": len({wo for a in doc.get("assignments") or []
                                  for wo in a.get("work_orders") or []}) or None,
                   "machines": len(doc.get("resources") or []) or None},
            unavailable=unavailable)

    def _explain_briefing(self, question: str,
                          document: Any = None) -> ExplanationBundle:
        """THE OPENER (Session 4B.16 Item 2) — what on this board should I be
        looking at, ranked by consequence, every line carrying its number.

        It began (4A.2 CU7) as the morning briefing: the fires ranked by
        lateness × priority, the common cause, one data-quality line. That is
        still in here — it is the `late` item — but it was a fraction of what
        the persisted document knows. A board can be provably optimal, hold a
        maintenance day that pauses eleven operations, run one machine at 88%
        beside two eligible empty ones and carry fourteen orders beyond the
        horizon, and none of it reached the answer.

        ENTIRELY CONTRACTED TESTIMONY: no synthesis on this path. Each item
        carries a POINTER — the question that opens it up — which is where the
        second tier or another route elaborates on one line.

        The pre-4B.16 fire list is still computed and still on ``key_facts``:
        it is what the older renderers and the exam bank read, and the opener
        is additive over it rather than a replacement that breaks them."""
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
        opener = self._build_opener(document)
        return ExplanationBundle(
            question=question or "What should I be looking at?",
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
                # Session 4B.16 Item 2 — the ranked board read.
                "opener": [{"key": i.key, "band": i.band, "amount": i.amount,
                            "headline": i.headline, "detail": list(i.detail),
                            "pointer": i.pointer, "clean": i.clean,
                            "figures": i.figures}
                           for i in opener.items],
                "opener_clean": opener.clean,
                "opener_scope": opener.scope,
                "opener_unavailable": [{"what": w, "why": y}
                                       for w, y in opener.unavailable],
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

    # ------------------------------------------------------------------
    # Session 4A.5b (R-AI5(2)/(4)) — the labeled-synthesis surface.
    #
    # The claims arrive ALREADY HARDENED (claim_verifier ran; every status is the
    # verifier's). These two assemblers only carry them into a bundle, resolve the
    # cited ids to real evidence records so the lit-bars channel and the citation
    # floor stay honest, and hand the whole thing to the renderer. No assembler
    # here decides what is proven — that decision was made before it got here.
    # ------------------------------------------------------------------

    def _records_by_id(self, ids: list[str]) -> list[dict]:
        """The real evidence records for a list of cited ids, in the order cited.
        Entity ids (an assignment, a service outcome) resolve to no RECORD and are
        skipped here — they are still verifiable, they just do not light a bar."""
        wanted = [i for i in ids if i]
        if not wanted:
            return []
        by_id = {str(r.get("record_id") or ""): r
                 for r in getattr(self._index, "_all_evidence", []) or []}
        out: list[dict] = []
        seen: set[str] = set()
        for i in wanted:
            rec = by_id.get(i)
            if rec is not None and i not in seen:
                seen.add(i)
                out.append(rec)
        return out

    def _synthesis_bundle(self, question: str, answer: Any,
                          diverted_qualifier: str = "",
                          offers: Optional[list] = None) -> ExplanationBundle:
        """A verified ``SynthesisAnswer`` → the bundle the surface renders (CU4).

        ``diverted_qualifier`` is set when the ADJACENT-MATCH GUARD (Session 4A.5c
        CU3(c)) sent a MATCHED intent here because the route could not honour a
        qualifier the planner stated. It reaches only the rendered-by line: a
        planner who asked about next month and got a reasoned answer instead of a
        proven one is owed the reason."""
        cited: list[str] = []
        for c in answer.claims:
            for rid in c.cited_record_ids:
                if rid not in cited:
                    cited.append(rid)
        return ExplanationBundle(
            question=question,
            subject_id="synthesis",
            subject_type="synthesis",
            subject_external_name="?",
            ordered_records=self._records_by_id(cited),
            key_facts={
                "claims": [c.model_dump(mode="json") for c in answer.claims],
                "cut": [c.model_dump(mode="json") for c in answer.cut],
                "tool_calls": [t.model_dump(mode="json") for t in answer.tool_calls],
                "tool_call_count": len(answer.tool_calls),
                "consulted_tools": sorted({t.tool for t in answer.tool_calls}),
                "budget_exhausted": answer.budget_exhausted,
                "timed_out": answer.timed_out,
                "unanswerable": answer.unanswerable,
                "counts": answer.counts(),
                "model": answer.model,
                "diverted_qualifier": diverted_qualifier,
                # CU3(b) — the warm floor's doors. Carried on every synthesis
                # bundle, rendered ONLY on the couldn't-answer: an answer that
                # grounded something needs no consolation prize.
                "offers": list(offers or []),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _rolling_bundle(self, route_id: str, question: str, document: Any,
                        order: Optional[str] = None,
                        bucket: Any = None) -> ExplanationBundle:
        """THE ROLLING (sliced-world) ROUTES (Session 4A.5c CU4; the two coarse
        routes added in Session 4B.6).

        The three answers still come from ``rolling_questions``, unchanged in
        authority and still authored, ID-free and hedged. What changed is how they
        are REACHED: a keyword pre-route in the API used to answer them before the
        parse ran, and that matcher — the last deterministic classifier in the
        codebase — is deleted. The parse names the intent; this is where the intent
        lands.

        The document rides in as a param because a rolling run's sliced state lives
        in the contract-1.7 RollingBlock, not in the window-0 snapshot the
        Explainer reads. Asked of a MONOLITHIC document the answerers say so
        honestly ("this isn't a rolling schedule"), which is the right answer to a
        sliced-world question about a plan that has no slices."""
        from mre.modules import rolling_questions as rq
        if route_id == "beyond-horizon":
            body = rq.answer_beyond_horizon(document)
        elif route_id == "frozen":
            body = rq.answer_frozen(document)
        elif route_id == "coarse-fit":
            body = rq.answer_coarse_fit(document)
        elif route_id == "bucket-load":
            body = rq.answer_bucket_load(document, bucket)
        else:
            body = rq.answer_why_not_scheduled_yet(document, order)
        return ExplanationBundle(
            question=question,
            subject_id=order or "rolling",
            subject_type="rolling",
            subject_external_name=order or "?",
            ordered_records=[],
            key_facts={"route": route_id, "body": body, "order": order,
                       "bucket": bucket},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _prove_it_bundle(self, question: str, claim: Any,
                         answer: Any = None) -> ExplanationBundle:
        """"Prove it" (R-AI5(4)): the grounding pass re-run on ONE claim,
        conversationally. Either the record, or the honest "that part is my
        inference from A and B — here's each"."""
        claim_dict = claim if isinstance(claim, dict) else (
            claim.model_dump(mode="json") if claim is not None else None)
        rids = list((claim_dict or {}).get("cited_record_ids") or [])
        if not rids:
            rids = list((claim_dict or {}).get("consulted_record_ids") or [])
        records = self._records_by_id(rids)
        lines = []
        for rec in records:
            lines.append({"rid": str(rec.get("record_id") or "")[:8],
                          "summary": self._record_summary(rec)})
        return ExplanationBundle(
            question=question,
            subject_id="prove-it",
            subject_type="prove_it",
            subject_external_name="?",
            ordered_records=records,
            key_facts={"claim": claim_dict, "lines": lines,
                       "have_claim": claim_dict is not None},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _record_summary(self, rec: dict) -> str:
        """One planner-readable line for a record, for the prove-it listing. Reads
        only what the record carries; resolves subjects through the identity map so
        no uuid reaches the planner."""
        rt = (rec.get("record_type") or "?").lower()
        names = []
        for s in rec.get("subjects", []) or []:
            eid = s.get("entity_id")
            if not eid or self._identity_map is None:
                continue
            refs = self._identity_map.external_refs(eid)
            if refs and refs[0].value not in names:
                names.append(refs[0].value)
        who = ", ".join(names[:3])
        if rt == "metric":
            val = rec.get("value")
            unit = " min" if "minutes" in (rec.get("name") or "") else ""
            return f"{rec.get('name')} = {val}{unit}" + (f" for {who}" if who else "")
        if rt == "decision":
            dt = (rec.get("decision_type") or "?").replace("_", " ")
            drv = rec.get("driver") or ""
            phrase = driver_phrase(drv) or drv.lower().replace("_", " ")
            return (f"the {dt} decision" + (f" for {who}" if who else "")
                    + (f" — {phrase}" if phrase else ""))
        if rt == "finding":
            return f"finding {rec.get('code')}" + (f" on {who}" if who else "")
        return f"{rt} record" + (f" for {who}" if who else "")

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

    def _explain_confirm_take(self, question: str, order: Optional[str],
                              machine: Optional[str]) -> ExplanationBundle:
        """Session 4A.5a CU2 — the confirmation-of-take bridge.

        The planner has repeated OUR OWN prior suggestion back as a question ("so
        move the first operation to an earlier start time?"). The old router had
        nowhere for that: it read a move phrasing with no second order and fell to a
        near-miss, which reads as the assistant forgetting what it just said. The
        honest answer names the gesture, says plainly that the move is the planner's
        to make (M10 has no write path), and points at the sandbox that prices it
        before acceptance. Authored copy — carried, never composed here."""
        facts = self._order_slack_facts(order) if order else None
        placement = (facts or {}).get("placement") or {}
        return self._authored_bundle("confirm_take", question, {
            "order": order,
            "machine": machine or placement.get("machine"),
            "placement": placement or None,
        })

    def _explain_open_card(self, question: str, card: dict) -> ExplanationBundle:
        """Session 4B.5 CU2 — VOICE the delta card that is open on the board.

        The founder's failing exchange was "what orders are affected in this
        move", asked with a priced card on screen showing exactly that. It parsed
        as `swap-move` — a route that reasons about two orders' slack and has
        never heard of the card — and answered a question nobody asked. The
        affected set, the decomposition and the placements were already computed;
        what was missing was a way to READ THEM BACK.

        So this route re-derives NOTHING. Every figure it states came off the
        sandbox result the card is already showing, and the answer is that card in
        sentences. Which part of the card the planner asked about is deliberately
        NOT classified — sub-classifying "the delta" vs "these orders" vs "this
        move" would be a keyword router wearing a new name (R-AI5), and the card
        is small enough to say whole. The composition order is the card's own:
        where it landed, what it costs split into re-optimization and the move,
        who it touches, and what else shifted.

        The card payload rides on the CONTEXT channel (like the board selection),
        so nothing here reads the canonical model — this bundle carries no
        evidence chain by construction, and the register is testimony about our
        own sandbox result, hedged exactly as the card hedges."""
        return self._authored_bundle("open_card", question, {"card": card or {}})

    def _expedite_early_facts(self, order: Optional[str]) -> Optional[dict]:
        """For an EXPEDITE question about an order that is already early: how early
        it finishes and the release date that is its only earlier bound.

        The founder's round-four thread is the specimen — asked four ways how to get
        an order done faster, on an order finishing 11.3 days ahead of its due date.
        A status recital ("N orders are late") answers a question nobody asked; the
        truthful answer is that there is nothing to expedite, and why. None when the
        order does not resolve or is not early."""
        if not order:
            return None
        facts = self._order_slack_facts(order)
        if not facts or facts.get("late"):
            return None
        slack = facts.get("slack_days")
        if slack is None or slack <= 0:
            return None
        dem = self._demand_by_order(order) or {}
        return {"order": order, "days_early": slack,
                "release": _fmt_date(dem.get("earliest_start")),
                "placement": facts.get("placement")}

    def _explain_advice(self, question: str,
                        order: Optional[str] = None) -> ExplanationBundle:
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
        on a clean plan (nothing to ground a take on).

        Session 4A.5a CU2 — the EXPEDITE-AN-EARLY-ORDER branch. When the advice is
        sought for one named order that already finishes ahead of its due date, the
        answer leads with that fact and with the release date that is its only
        earlier bound, instead of a plan-wide lateness scope that answers a question
        the planner did not ask."""
        late = self._late_order_count()
        return self._authored_bundle(
            "advice", question,
            {"late_count": late, "take": self._advice_take(),
             "order": order, "expedite_early": self._expedite_early_facts(order)})

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
        # Session 4B.15 Item 5 — GROUND THE CLAIM IN docs/05, OR REFUSE IT.
        #
        # The nine-entry registry above answers "how do I turn X on" and it
        # answers it well. What it cannot do is say whether the product HAS X,
        # because it carries no verdict and no proof status — so a question it
        # did not recognize reached the second tier, which had no constraint
        # catalog either, and "can two machines share one operator" came back a
        # confident YES describing alternates. The catalog answers exactly that
        # question and this is where it is read.
        cap = None
        try:
            from mre.modules.capability_answer import answer as _cap_answer
            cap = _cap_answer(question, concept)
        except Exception:  # noqa: BLE001 — an unreadable catalog is "no ground"
            cap = None
        return self._authored_bundle("coaching", question, {
            "concept": concept,
            "enables": note.enables if note else None,
            "how": note.how if note else None,
            "ids_ref": note.ids_ref if note else None,
            "rationale": note.rationale if note else None,
            "coachable": coachable,
            "capability": cap,
        })

    def _explain_attribute_lookup(self, question: str, order: Optional[str],
                                  op_seq: Optional[int],
                                  machine: Optional[str],
                                  prior_question: str = "") -> ExplanationBundle:
        """Session 4B.15 Item 3 — ANY DECLARED FIELD, VERBATIM, WITH ITS SOURCE.

        Reads the canonical entity and its provenance sidecar off the persisted
        snapshot (R-AI4: no re-solve). The facts were always loaded — the
        blocker analysis quoted `splittable=False` and 431 working minutes one
        exchange after both questions were answered with documentation — there
        was simply no route that reads a field and states it."""
        from mre.modules.attribute_lookup import lookup
        ans = lookup(self, question, order=order, op_seq=op_seq,
                     machine=machine, prior_question=prior_question)
        return self._authored_bundle("attribute_lookup", question, {
            "attribute_answer": ans,
            "subject": ans.subject if ans else (order or machine or ""),
            "unresolved": ans is None,
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

    def _explain_optimality(self, question: str) -> ExplanationBundle:
        """"Is this schedule optimal?" — ANSWERED FROM THE SOLVER'S OWN PROOF
        (Session 4B.13 Item 2; discharges docs/07 §5a.29).

        Read, never re-derived: ``cost_proof.from_evidence`` takes the M6
        ``solve_complete`` event — the same record the document's ``SolverBlock``
        and the strip chip are built from — so the answer and the board agree
        because they read ONE record, not because they were kept in step.

        Before this route existed the question fell to synthesis, which cannot
        see ``solver.status``. On the pinned exam world it therefore invented its
        own definition ("optimal on the dimensions that matter most") from a
        lateness count that was itself false, and reached the right verdict by
        the wrong road. The proof was rendered, correct, and unaskable.

        BOTH DIRECTIONS ARE FIRST-CLASS. A proved board says so plainly and says
        WHAT was proved — the COST optimum (4B.8 CU3's ruling), never the
        tiebreak, which rides beside it and never downgrades it. An unproved
        board says so WITH ITS GAP and is not thereby called bad: 4B.12 measured
        F006 at a 98.8% gap whose ledger spread across seeds was 0.289%, so the
        gap measures our inability to PROVE, not the answer's quality. That
        distinction is authored into the copy rather than left to the reader.
        """
        from mre.modules import cost_proof as cp
        proof = cp.from_evidence(self._index)
        # UNREADABLE IS NOT THE SAME AS NO-SOLVE. CostProof.no_solve covers both
        # "nothing was admitted" (a real fact about the run) and status=None,
        # which is what an index with no solve_complete event yields — including
        # one this Explainer simply could not read. Fusing them would make the
        # answer assert "there was no solve" about a solve that happened, which
        # is the same class of defect as the rest of this session. Separated
        # here rather than in CostProof, whose chip/rider callers want the
        # existing three-way split.
        unknown = proof.status is None
        return self._authored_bundle("optimality", question, {
            "unknown": unknown,
            "no_solve": proof.no_solve and not unknown,
            "proved": proof.proved,
            "unproved": proof.unproved,
            "gap_text": proof.gap_text(),
            "objective": proof.objective,
            "status": proof.status,
            "tiebreak_status": proof.tiebreak_status,
            "tiebreak_skipped_reason": proof.tiebreak_skipped_reason,
            # The tiebreak clause is composed by the SINGLE definition, so the
            # answer, the strip chip and the money rider cannot word it
            # differently.
            "tiebreak_clause": proof._tiebreak_clause(),
        })

    def _explain_machine_count(self, question: str) -> ExplanationBundle:
        """CU3 — how many machines / list the machines. A pure document read of the
        resource entities, rendered in the planner's external vocabulary.

        TWO NUMBERS, SEPARATELY LABELLED (Session 4B.13 Item 4). This route
        counted DECLARED resources and the renderer called them "machine(s) carry
        work in this plan" — on the pinned exam world, "15 machine(s) carry work"
        on a board where five rows (CUT-02, CUT-03, FINISH-03, HEAT-02,
        PRESS-SLOW) sit at 0%, which a stranger falsifies by counting bars. The
        count a stranger wants (15 machines exist) was right; the sentence was
        false. Both facts are now carried and both are labelled, so neither has
        to stand in for the other.
        """
        names: list[str] = []
        by_id: dict[str, str] = {}
        try:
            for r in self._reader.iter_entities("resource"):
                nm = None
                for ref in (r.get("external_refs") or []):
                    if ref.get("ref_type") in _MACHINE_REF_TYPES or ref.get("value"):
                        nm = ref.get("value")
                        break
                label = nm or r.get("id", "?")
                names.append(label)
                if r.get("id"):
                    by_id[r["id"]] = label
        except Exception:
            names = []
            by_id = {}
        names = sorted(dict.fromkeys(names))

        # Which of them actually carry an assignment in this plan.
        working: list[str] = []
        try:
            seen: set[str] = set()
            for asgn in self._reader.iter_entities("assignment"):
                for ra in asgn.get("resource_assignments", []) or []:
                    rid = (ra.get("resource_ref", "") if isinstance(ra, dict)
                           else getattr(ra, "resource_ref", ""))
                    if rid:
                        seen.add(rid)
            working = sorted({by_id.get(rid, rid) for rid in seen})
        except Exception:
            working = []

        return self._authored_bundle("machine_count", question, {
            "machine_count": len(names), "machines": names,
            # None (not 0) when the assignments could not be read at all — an
            # unknown is never rendered as "nothing is working".
            "working_machine_count": len(working) if working else None,
            "working_machines": working,
            "idle_machines": [n for n in names if n not in set(working)] if working else [],
        })

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

        # CU2 (Session 4A.3c) — an order-schedule / machine-schedule answer narrates
        # specific placements, so it lights their bars through the existing
        # cited_refs channel. The lit set is exactly the rows shown (capped when the
        # listing truncates), never a lane's whole history. Real assignment Decisions
        # (real record_ids), so lit-bars and the testimony validator stay honest;
        # the prose stays deterministic ("schedule" is authored copy).
        narrated_ops = {r["operation_ref"] for r in filtered if r.get("operation_ref")}
        narrated_demands = {d for r in filtered for d in r.get("demand_ids", [])}
        schedule_records = self._assignment_records_for_ops(narrated_ops, narrated_demands)

        return ExplanationBundle(
            question=question,
            subject_id=label,
            subject_type="schedule",
            subject_external_name=label,
            ordered_records=schedule_records,
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
        """The solved placements as planner-vocabulary rows, memoized per
        Explainer.

        Session 4B.14 added the memo, for a cost this session introduced: the
        blocker analysis reads these rows four or five times per answer (the
        order's own rows, the machine's occupancy, the sufficiency check, the
        open-window span), and each call re-walked every operation, fulfillment,
        demand and service outcome in the snapshot. A snapshot is immutable for
        the life of an Explainer, so the derived view is too — and no caller
        mutates a row (``_order_rows`` sorts a fresh comprehension,
        ``_apply_schedule_filter`` returns a filtered list)."""
        cached = getattr(self, "_enriched_cache", None)
        if cached is not None:
            return cached
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

            # Session 4B.14 Item 0 — THE EXPLAINER'S ROW MODEL WAS CHUNK-BLIND.
            # ``end`` read ``run[0]["end"]``: the first CHUNK's end, not the
            # operation's. On the pinned board ORD-000011 runs three chunks and
            # this reported its end as 2026-01-08 19:00, its first PAUSE, when it
            # completes 2026-01-12 15:37 — and that wrong figure is exactly what
            # "held by ORD-000011 until 2026-01-08 19:00" cited. 4B.13 fixed this
            # class in the document assembler and on the board; the explainer's
            # own read was still first-chunk-only, so every consumer of ``end``
            # (the blocked-by cause, order completion, slack, the gap resolver)
            # was reading a pause as a finish. ``end`` is now the LAST run
            # window's end, and the chunks travel with the row so an answer can
            # distinguish RUN TIME from ELAPSED SPAN rather than conflating them.
            run_windows = asgn.get("phase_windows", {}).get("run", [])
            start_str = run_windows[0]["start"] if run_windows else ""
            end_str = run_windows[-1]["end"] if run_windows else ""
            chunks: list[dict] = []
            run_min = 0.0
            for i, w in enumerate(run_windows, start=1):
                cs, ce = _to_dt(w.get("start")), _to_dt(w.get("end"))
                mins = (ce - cs).total_seconds() / 60.0 if (cs and ce) else 0.0
                run_min += mins
                chunks.append({"chunk_seq": i, "start": w.get("start"),
                               "end": w.get("end"), "working_min": round(mins, 3)})
            sdt, edt = _to_dt(start_str), _to_dt(end_str)
            span_min = ((edt - sdt).total_seconds() / 60.0
                        if (sdt and edt) else 0.0)

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
                # 4B.14 Item 0 / Item 4: run time and elapsed span, SEPARATELY.
                # After 4B.13's chunk fix these genuinely differ (ORD-000011 is
                # 1,501 working minutes across a 5,821-minute span) and that
                # difference IS the answer to half the "why is there a gap"
                # questions. Conflating them is the confusion the merged bar
                # used to create.
                "chunks": chunks,
                "run_min": round(run_min, 3),
                "span_min": round(span_min, 3),
                "splittable": bool(op.get("splittable")),
                "min_chunk": op.get("min_chunk"),
                "setup_duration": op.get("setup_duration"),
                "work_orders": wo_names,
                "demand_ids": demand_ids,
                "customer_ids": customer_vals,
                "service_outcomes": svc_facts,
            })
        self._enriched_cache = rows
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


def _display_facts(facts: Optional[dict]) -> dict:
    """A family's evidence with datetimes formatted for copy (Session 4B.14).
    key_facts are quoted verbatim by the renderers and serialized onto the ask
    response, so a raw datetime here would leak an ISO string into planner text."""
    out: dict = {}
    for k, v in (facts or {}).items():
        if isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M")
        elif isinstance(v, dict):
            out[k] = _display_facts(v)
        else:
            out[k] = v
    return out


def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    """A real datetime → 'YYYY-MM-DD HH:MM' for copy (Session 4B.16). key_facts
    are quoted verbatim by the renderers and serialized onto the ask response, so
    a datetime object here would leak an ISO string into planner text."""
    return dt.strftime("%Y-%m-%d %H:%M") if isinstance(dt, datetime) else None


def _fmt_ts(s: str) -> str:
    """Truncate ISO timestamp to 'YYYY-MM-DD HH:MM' for display."""
    if not s:
        return ""
    try:
        dt = _parse_ts(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16]
