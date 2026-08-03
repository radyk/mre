"""The exam runner (Session 4A.3b, CU1).

Drives a question script through the REAL ask path (``_answer_question``) against a
pinned persisted run, holding conversation state exactly as the cockpit does, and
emits a plain-ASCII transcript + a mechanical findings sidecar.

Conversation-state fidelity (the instrument tests what the founder would hear):
  * ``history`` turns are built the way the cockpit builds them — question,
    resolved_question, route, and order/machine drawn from the ACTIVE board
    selection (``askpanel.js`` ``currentSelectionRefs``), not from the answer's
    resolved subject. A conversation carries subject across turns via SELECT, which
    is the channel the panel actually sends. This is the honest choice: enriching
    history beyond what the cockpit transmits would let the harness PASS follow-ups
    the shipped product fails.
  * ``selection`` is a ``{order, machine}`` dict, the only fields the parse layer
    reads from the selection channel.

Nothing is mocked. Session 4A.5a: the ask path is LLM-FIRST (R-AI5), so a run needs
a PARSER as much as it needs a solved world — one is built when ``ANTHROPIC_API_KEY``
is set, or injected (offline tests inject a scripted one). ONE parser serves the
whole run, so the parse-specific counts (retry / malformed / clarify rates, median
latency) are the run's. The runner reports its LLM mode, a live-call count, those
parse counts, and how many graded EXPECT lines were met at close.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .script import (
    Card, Comment, Expect, ParsedScript, Question, Reset, Select, parse_script,
)
from .sidecar import Finding, Vocab, check_turn


# ---------------------------------------------------------------------------
# The pinned world
# ---------------------------------------------------------------------------

@dataclass
class RunTarget:
    """A pinned persisted run to ask against. Either resolved from a schedule id in
    a data root (the API-parity path) or pointed straight at an out-dir + snapshot
    (the CI/test path — no Registry, no HTTP)."""
    out_dir: Path
    snapshot_id: str
    runs_subdir: str = "runs"
    document: Optional[dict] = None
    label: str = ""

    @classmethod
    def from_schedule(cls, data_root: Path | str, schedule_id: str) -> "RunTarget":
        from mre.api.registry import Registry
        reg = Registry(data_root)
        row = reg.get_schedule(schedule_id)
        if not row:
            raise ValueError(f"schedule {schedule_id!r} not found in {data_root}")
        run = reg.get_run(row["run_id"])
        if not run:
            raise ValueError(f"run {row['run_id']!r} for schedule {schedule_id!r} not found")
        document = None
        dp = row.get("document_path")
        if dp:
            try:
                document = json.loads(Path(dp).read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — a missing doc is fine (monolithic)
                document = None
        return cls(
            out_dir=Path(run["out_dir"]),
            snapshot_id=row["snapshot_id"],
            runs_subdir="scenario_runs" if row.get("is_scenario") else "runs",
            document=document,
            label=schedule_id,
        )

    @classmethod
    def from_out_dir(cls, out_dir: Path | str, snapshot_id: str, *,
                     scenario: bool = False, document_path: Optional[Path] = None,
                     label: str = "") -> "RunTarget":
        document = None
        if document_path and Path(document_path).exists():
            document = json.loads(Path(document_path).read_text(encoding="utf-8"))
        return cls(
            out_dir=Path(out_dir), snapshot_id=snapshot_id,
            runs_subdir="scenario_runs" if scenario else "runs",
            document=document, label=label or str(out_dir),
        )

    def build_vocab(self, parser: Any = None) -> Vocab:
        """A throwaway Explainer over the same snapshot, for the sidecar's shape
        checks (valid entity vocabulary + the real-doors door check). The parser is
        the run's own — an offered follow-up is checked by the same parse layer a
        planner clicking it would hit (Session 4A.5a)."""
        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.explainer import Explainer
        from mre.modules.snapshot_store import SnapshotStore
        ip = self.out_dir / "evidence_index.json"
        index = (EvidenceIndex.load(ip) if ip.exists()
                 else EvidenceIndex().build(self.out_dir / self.runs_subdir))
        store = SnapshotStore(self.out_dir / "snapshots")
        return Vocab(Explainer(store, index, snapshot_id=self.snapshot_id),
                     parser=parser)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class TurnRecord:
    lineno: int
    question: str
    selection: dict
    resolved_question: str = ""
    resolution_note: str = ""
    route: str = ""
    source: str = ""
    confidence: Optional[float] = None
    register: str = ""
    renderer: str = ""
    subject_type: str = ""
    subject_external_name: str = ""
    record_count: int = 0
    cited_refs: dict = field(default_factory=dict)
    lit_bars: int = 0
    answer: str = ""
    error: Optional[str] = None
    llm_calls: int = 0
    # TOTAL conversational latency for this turn — parse + dispatch + assembly +
    # render, wall-clock, the number a planner actually waits (Session 4A.5b rider
    # c). Reported split by tier in the sweep, because parse+route and
    # parse+synthesis are different products to wait for.
    latency_ms: Optional[float] = None
    findings: list[Finding] = field(default_factory=list)
    # The parse contract's instrumentation (Session 4A.5a): intent, follow-up
    # linkage, polarity, bound subjects, clarify reason, retries, latency.
    parse: dict = field(default_factory=dict)
    # The SECOND TIER's per-claim provenance (Session 4A.5b): claim counts by
    # verdict, the tools consulted, and whether anything load-bearing was cut.
    # Empty on every contracted answer, which is most of them.
    synthesis: dict = field(default_factory=dict)
    # The graded expectation this turn carried (an EXPECT line), if any.
    expect: dict = field(default_factory=dict)
    # PROBATION SHADOW (Session 4A.5c CU2c, R-AI5(7)): present only when a
    # PROMOTED route on probation answered this turn, in which case the same
    # question was ALSO answered by the synthesis tier and the two were diffed for
    # fact agreement. Empty on every other turn — the shadow is what a probation
    # IS, not a permanent tax on every answer.
    shadow: dict = field(default_factory=dict)


@dataclass
class ExamResult:
    target_label: str
    snapshot_id: str
    llm_mode: str                 # "live" | "deterministic"
    turns: list[TurnRecord] = field(default_factory=list)
    parse_errors: list[Finding] = field(default_factory=list)
    total_llm_calls: int = 0
    started_at: str = ""
    # Parse-layer counts for the sweep close-out (Session 4A.5a CU5).
    parser_stats: dict = field(default_factory=dict)
    # Synthesis-tier counts for the sweep close-out (Session 4A.5b CU5).
    synth_stats: dict = field(default_factory=dict)
    door_check: str = "skipped"          # "live" | "skipped"

    def synthesis_totals(self) -> dict:
        """The sweep sidecar's synthesis block: claims by verdict, the
        ungrounded-load-bearing count, and the tool-call histogram."""
        totals = {"answers": 0, "claims": 0, "verified": 0, "interpretive": 0,
                  "failed_and_cut": 0, "ungrounded_load_bearing": 0,
                  "unanswerable": 0, "budget_exhausted": 0, "tool_calls": 0}
        histogram: dict[str, int] = {}
        per_answer: dict[str, int] = {}
        for t in self.turns:
            s = t.synthesis or {}
            if not s:
                continue
            totals["answers"] += 1
            for key in ("claims", "verified", "interpretive", "failed_and_cut",
                        "ungrounded_load_bearing", "tool_calls"):
                totals[key] += int(s.get(key) or 0)
            totals["unanswerable"] += 1 if s.get("unanswerable") else 0
            totals["budget_exhausted"] += 1 if s.get("budget_exhausted") else 0
            for tool in s.get("tools") or []:
                histogram[tool] = histogram.get(tool, 0) + 1
            n = str(int(s.get("tool_calls") or 0))
            per_answer[n] = per_answer.get(n, 0) + 1
        return {**totals, "tool_histogram": dict(sorted(histogram.items())),
                "calls_per_answer": dict(sorted(per_answer.items()))}

    def shadow_totals(self) -> dict:
        """The probation block (Session 4A.5c CU2c). ``diverged`` is the only
        number here that means anything on its own: R-AI5(7) makes it the demotion
        trigger. ``unchecked`` is reported separately and never folded into
        ``clean`` — a window nobody watched is not a window served."""
        totals = {"shadowed": 0, "clean": 0, "diverged": 0, "unchecked": 0,
                  "provenance_strengthened": 0}
        by_intent: dict[str, dict] = {}
        for t in self.turns:
            s = t.shadow or {}
            if not s:
                continue
            totals["shadowed"] += 1
            intent = s.get("intent") or "?"
            row = by_intent.setdefault(
                intent, {"shadowed": 0, "diverged": 0, "unchecked": 0})
            row["shadowed"] += 1
            if s.get("unchecked"):
                totals["unchecked"] += 1
                row["unchecked"] += 1
            elif s.get("contradicted"):
                totals["diverged"] += 1
                row["diverged"] += 1
            else:
                totals["clean"] += 1
            if s.get("provenance_strengthened"):
                totals["provenance_strengthened"] += 1
        return {**totals, "by_intent": by_intent}

    def latency(self) -> dict:
        """TOTAL conversational latency, split by tier (rider c). ``route`` is
        parse + contracted assembly + render; ``synthesis`` is parse + the agentic
        loop + verification + render. They are different products to wait for and
        the close-out states both."""
        buckets: dict[str, list[float]] = {"route": [], "synthesis": []}
        for t in self.turns:
            if t.error is not None or t.latency_ms is None:
                continue
            key = "synthesis" if t.synthesis else "route"
            buckets[key].append(t.latency_ms)
        out: dict = {}
        for key, xs in buckets.items():
            xs = sorted(xs)
            if not xs:
                out[key] = {"n": 0, "median_ms": None, "p90_ms": None}
                continue
            mid = len(xs) // 2
            median = xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2
            p90 = xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))]
            out[key] = {"n": len(xs), "median_ms": round(median, 1),
                        "p90_ms": round(p90, 1)}
        return out

    def graded(self) -> tuple[int, int]:
        """(graded turns, graded turns that MET their expectation) — the per-bank
        pass/fail the close-out reports. Turns with no EXPECT line are not graded;
        routing is the only machine-graded axis (R-AI4(2))."""
        graded = [t for t in self.turns if t.expect]
        met = [t for t in graded
               if not any(f.kind == "expect-miss" for f in t.findings)]
        return len(graded), len(met)

    @property
    def findings(self) -> list[Finding]:
        out = list(self.parse_errors)
        for t in self.turns:
            out.extend(t.findings)
        return out

    def finding_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

_RENDER_TAG = None  # lazily compiled

# The subject types that unambiguously name an ORDER (their subject_external_name
# is an order ref) vs a MACHINE — the panel's map for carrying the resolved subject
# of the prior answer into the next question's context (Session 4A.3c CU1). Kept in
# lockstep with askpanel.js ORDER_SUBJECTS / MACHINE_SUBJECTS: the runner carries
# EXACTLY what the panel carries, never more — enriching beyond it would let the
# harness pass follow-ups the shipped product fails. Ambiguous types (a bare
# "schedule" label can be an order OR a machine) carry nothing.
_ORDER_SUBJECT_TYPES = frozenset(
    {"demand", "start_reason", "contested_fact", "order_attributes"})
_MACHINE_SUBJECT_TYPES = frozenset({"machine_idle"})


def resolved_subject(subject_type: str, subject_external_name: str) -> dict:
    """The prior answer's subject as an {order|machine} dict, or {} when the type
    is ambiguous or the name is a placeholder. Mirrors askpanel.js exactly."""
    name = (subject_external_name or "").strip()
    if not name or name in ("?", "all"):
        return {}
    if subject_type in _ORDER_SUBJECT_TYPES:
        return {"order": name}
    if subject_type in _MACHINE_SUBJECT_TYPES:
        return {"machine": name}
    return {}


# The SHIPPED card, verbatim. Read off ``tests/cockpit/fixtures/rolling/sandbox.json``
# — the two-beat the fixture builder captured from a real ``sandbox_pin_resolve`` —
# so a card bank feeds the ask path exactly what
# ``drag/controller.js::cardContextFrom`` sends it. Test-realism law: a context
# test feeds ONLY what the shipped surface sends, in the shapes it sends them.
#
# RECALIBRATED SESSION 4B.17 (docs/07 §5a.22, the entry this discharges). The
# figures below are the CURRENT committed fixture's, re-read this session; the
# previous constants were 4B.6b's capture and 4B.7 moved the card under them.
#
#   was (4B.6b): total -11,953.08 = reopt -11,975.83 + move +22.75
#   now (4B.7 ):  total     +32.20 = reopt       0.00 + move  +32.20
#
# AND THE SPECIMEN DEGENERATED, WHICH IS THE THING TO KNOW. The old pair was a
# move that COSTS inside a re-optimization that SAVES, and that sign
# disagreement is what 4B.5 CU1's split exists to express. R-SC3(2)'s retirement
# (4B.7) took the earliness coefficient out of the objective, so the window
# solve and the sandbox baseline now minimize the SAME expression and
# ``reopt_delta_abs`` is **0.00 by construction** (docs/07 §5a.12's discharge).
# The product can no longer produce a card whose halves disagree, so the bank's
# "which half did you quote" question can no longer discriminate: move == total.
# It still grades the SIGN (a cost stated as a cost) and it is reported as
# unexercisable rather than quietly counted as a pass.
#
# CARRIED, NOT FIXED: the fixture predates 4B.8 CU4, which made
# ``EARLINESS_PREFERENCE`` dormant in the extractor (docs/07 §5a.20). The
# ``dominant_driver`` below is therefore a shape the current sandbox would not
# emit. Regenerating the fixture needs a solve, which R-AI4 puts out of this
# session's scope; no bank question grades this field.
_SHIPPED_CARD_COST_DELTA = 32.20
_SHIPPED_CARD_REOPT_DELTA = 0.0
_SHIPPED_CARD_MOVE_DELTA = 32.20
_SHIPPED_CARD_COST_LINES = [
    {"line": "tardiness", "delta": 0.0},
    {"line": "setup", "delta": 0.0},
    {"line": "production (regular)", "delta": 32.20},
    {"line": "production (overtime)", "delta": 0.0},
    {"line": "other placement changes", "delta": 0.0},
]
# EMPTY on the current card, and that is the fixture's own value — the pinned
# world's tardiness is 0.00, so no demand's service outcome moves. A route that
# names orders here is fabricating them.
_SHIPPED_CARD_AFFECTED: list = []
_SHIPPED_CARD_DRIVER = {
    "code": "EARLINESS_PREFERENCE",
    "phrase": "a declared earliness preference paid a little more to start it "
              "sooner on a machine that was free earlier",
    "hedge": "— though I'm attributing this by price alone, so I can't be "
             "certain the earlier start was the real reason rather than the "
             "cheaper machine simply being busy at the time (capacity pressure "
             "can bind here too)",
}


def _exam_card(order: Optional[str], machine: Optional[str]) -> dict:
    """The card payload a ``CARD`` directive stands up (Session 4B.5 CU2).

    A bank states WHICH move is showing; every figure around it is the SHIPPED
    card's, lifted from the committed rolling fixture (see the constants above).
    What a card bank grades is ROUTING — does a question asked with a card open
    reach `open-card` rather than the nearest plan-wide route — but a route that
    READS THE CARD BACK can only be graded against numbers the product actually
    produces, signs included.

    Only the identity fields vary with the directive: the order and machine the
    bank names, and a synthetic ``operation_ref`` (an identifier, never a
    figure — the exam world's own op ids are not the fixture's).

    The shape mirrors what ``askpanel.js`` sends, field for field, so a bank
    exercises the same contract the cockpit does."""
    return {
        "open": True,
        "operation_ref": f"exam-op-{(order or 'x').lower()}",
        "order": order, "machine": machine,
        "when": "Jan 8, 08:23",
        "outcome": "verdict", "feasible": True,
        "message": "optimal delta proven",
        "correlation_id": "corr-53211846731604b5",
        "cost_delta_abs": _SHIPPED_CARD_COST_DELTA,
        "attribution": "split",
        "reopt_delta_abs": _SHIPPED_CARD_REOPT_DELTA,
        "move_delta_abs": _SHIPPED_CARD_MOVE_DELTA,
        "attribution_note": "",
        "cost_lines": [dict(l) for l in _SHIPPED_CARD_COST_LINES],
        "affected_orders": [dict(a) for a in _SHIPPED_CARD_AFFECTED],
        "lateness_delta_min": 0, "moves": 1,
        "no_committed_work_changes": True,
        "dominant_driver": dict(_SHIPPED_CARD_DRIVER),
    }


def _parse_renderer_tag(answer: str) -> str:
    import re
    global _RENDER_TAG
    if _RENDER_TAG is None:
        _RENDER_TAG = re.compile(r"\[rendered by:\s*([^|\]]+)")
    m = None
    for m in _RENDER_TAG.finditer(answer or ""):
        pass  # keep the LAST footer (the delivery seam appends it last)
    return m.group(1).strip() if m else "?"


class _CallCounter:
    """Counts live LLM calls by wrapping the anthropic client's messages.create,
    installed for the duration of a run. Honest instrumentation, never a mock — the
    real client still makes the real call; we only tally it."""

    def __init__(self) -> None:
        self.count = 0
        self._orig = None
        self._cls = None

    def __enter__(self) -> "_CallCounter":
        try:
            import anthropic  # noqa: F401
            from anthropic.resources.messages import Messages
        except Exception:  # noqa: BLE001 — no SDK -> nothing to count (det. mode)
            return self
        self._cls = Messages
        self._orig = Messages.create
        counter = self

        def _counted(self_inner, *a, **kw):  # noqa: ANN001
            counter.count += 1
            return counter._orig(self_inner, *a, **kw)

        Messages.create = _counted  # type: ignore[assignment]
        return self

    def __exit__(self, *exc) -> None:
        if self._cls is not None and self._orig is not None:
            self._cls.create = self._orig  # type: ignore[assignment]


class ExamRunner:
    def __init__(self, target: RunTarget, *, use_llm: Optional[bool] = None,
                 ledger_path: Optional[Path] = None, per_question_timeout: float = 90.0,
                 session_id: str = "ai-exam", parser: Any = None,
                 synthesizer: Any = None) -> None:
        self.target = target
        key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.use_llm = key if use_llm is None else (use_llm and key)
        self.ledger_path = ledger_path
        self.per_question_timeout = per_question_timeout
        self.session_id = session_id
        self._vocab: Optional[Vocab] = None
        # ONE parser for the whole run (Session 4A.5a): the ask path is LLM-first,
        # so a sweep needs a shared parse layer to report clarify / retry /
        # malformed rates and a median parse latency. An injected parser (a test
        # double) is used verbatim; otherwise a live one is built when a key is set.
        if parser is None and key:
            from mre.modules.question_parser import QuestionParser
            parser = QuestionParser()
        self.parser = parser
        # ONE synthesizer for the whole run too (Session 4A.5b): the second tier's
        # counts — claims by verdict, tool-call histogram, median/p90 latency — are
        # then the RUN's, the same way the parse counts are.
        if synthesizer is None and key:
            from mre.modules.synthesizer import Synthesizer
            synthesizer = Synthesizer()
        self.synthesizer = synthesizer

    # -- one question -------------------------------------------------------

    def _ask(self, question: str, history: list[dict], selection: dict,
             last_answered: dict, card: Optional[dict] = None) -> tuple[str, dict]:
        from mre.api.app import _answer_question
        return _answer_question(
            self.target.out_dir, self.target.snapshot_id, question,
            use_llm=self.use_llm, runs_subdir=self.target.runs_subdir,
            context={"history": history, "selection": selection,
                     "last_answered_subject": last_answered,
                     "card": card or {}},
            ledger_path=self.ledger_path, schedule_id=self.target.label,
            session_id=self.session_id, document=self.target.document,
            parser=self.parser, synthesizer=self.synthesizer,
            shadow=self._shadow,
        )

    def _ask_with_timeout(self, question: str, history: list[dict],
                          selection: dict, last_answered: dict,
                          card: Optional[dict] = None
                          ) -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Returns (answer, meta, error). A per-question timeout / exception is
        captured as an error string, never a crash of the run."""
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(self._ask, question, history, selection,
                            last_answered, card)
            try:
                answer, meta = fut.result(timeout=self.per_question_timeout)
                return answer, meta, None
            except FutureTimeout:
                return None, None, f"timed out after {self.per_question_timeout:g}s"
            except Exception as exc:  # noqa: BLE001 — ask-path failure is a finding
                return None, None, f"{type(exc).__name__}: {exc}"

    # -- the probation shadow (R-AI5(7), Session 4A.5c CU2c) ----------------

    def _shadow(self, explainer: Any, question: str, bundle: Any,
                route: str) -> Any:
        """The shadow runner handed to ``run_ask``.

        This is where R-AI5(7)'s "promoted routes run shadowed for a probation
        window" actually happens, and it happens in the SWEEP rather than on the
        planner's turn for an honest reason: a shadow costs a full synthesis
        (roughly ten seconds and a dozen model calls), and making every planner
        pay that so a promotion can be audited would be charging the user for our
        own quality control.

        ``run_shadow`` returns None for any route that is not a promotion on
        probation, so this is bounded by the registry rather than by a list kept
        here. A fired divergence becomes a sidecar finding, and the finding is the
        demotion trigger — the flip itself is a committed edit to ``PROMOTIONS``,
        because a vocabulary that changed itself at runtime would be the router
        rewriting its own routing, which R-AI1 forbids."""
        from mre.modules.shadow import run_shadow
        return run_shadow(explainer, question, bundle, route,
                          synthesizer=self.synthesizer)

    # -- the whole script ---------------------------------------------------

    def run(self, script: ParsedScript, *, limit: Optional[int] = None) -> ExamResult:
        from datetime import datetime, timezone
        result = ExamResult(
            target_label=self.target.label, snapshot_id=self.target.snapshot_id,
            llm_mode="live" if self.use_llm else "deterministic",
            started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for lineno, raw, reason in script.parse_errors:
            result.parse_errors.append(
                Finding("parse-error", lineno, raw.strip(), reason))

        self._vocab = self.target.build_vocab(parser=self.parser)
        result.door_check = "live" if self._vocab.door_check_available else "skipped"
        if not self._vocab.healthy:
            # The pinned run did not load (missing/wiped snapshot or evidence). Do
            # NOT fire questions — every entity answer would silently misroute. Fail
            # loud, like the rest of this codebase (a dead target is a defect, not a
            # transcript to read).
            result.parse_errors.append(Finding(
                "target-unloadable", 0, "",
                f"snapshot {self.target.snapshot_id!r} at {self.target.out_dir} "
                "yielded an empty entity vocabulary — the run did not load; "
                "no questions fired"))
            return result
        history: list[dict] = []
        selection: dict = {}
        # Session 4B.5 CU2 — the OPEN DELTA CARD channel, empty unless a bank
        # opens one (and empty again the moment it closes one).
        card: dict = {}
        # The resolved subject of the PRIOR answer, carried into the next question
        # exactly as the panel does (Session 4A.3c CU1). Reset by RESET.
        last_answered: dict = {}
        # Comments/selects between questions attach to the NEXT question in the
        # transcript for readability; we buffer them here.
        pending_comments: list[str] = []
        pending_expect: dict = {}
        asked = 0

        with _CallCounter() as counter:
            for item in script.items:
                if isinstance(item, Comment):
                    pending_comments.append(item.text)
                    continue
                if isinstance(item, Expect):
                    pending_expect = dict(item.fields)
                    pending_comments.append(
                        "[EXPECT " + " ".join(
                            f"{k}={v}" for k, v in pending_expect.items()) + "]")
                    continue
                if isinstance(item, Reset):
                    history = []
                    selection = {}
                    last_answered = {}
                    card = {}
                    # Errand 4B.16a — RESET cleared four channels and MISSED the
                    # fifth. The deafness signal's memory is server-side and keyed
                    # by session id (a delivered ANSWER cannot be read off the
                    # history channel, which carries only question and route), so
                    # it survived every RESET and the rider scolded across the
                    # boundary, citing a question from a conversation the bank had
                    # already thrown away. A contaminated instrument reads as a
                    # product defect on every bank that starts a second
                    # conversation, which is most of them.
                    from mre.modules.interpreter import forget_deliveries
                    forget_deliveries(self.session_id)
                    pending_comments.append("[RESET — conversation cleared]")
                    continue
                if isinstance(item, Card):
                    # Session 4B.5 CU2 — the open delta card channel. The bank
                    # states WHICH move is showing; the payload around it is
                    # synthesized here, because a card bank grades ROUTING (does
                    # the question reach `open-card`) and the figures are the
                    # card's own in the product.
                    if item.clear:
                        card = {}
                        pending_comments.append("[CARD closed]")
                    else:
                        card = _exam_card(item.order, item.machine)
                        pending_comments.append(
                            "[CARD open — " + " ".join(
                                f"{k}={v}" for k, v in
                                (("order", item.order), ("machine", item.machine))
                                if v) + "]")
                    continue
                if isinstance(item, Select):
                    if item.clear:
                        selection = {}
                        pending_comments.append("[SELECT cleared]")
                    else:
                        selection = {}
                        if item.order:
                            selection["order"] = item.order
                        if item.machine:
                            selection["machine"] = item.machine
                        if item.op_seq is not None:
                            selection["op_seq"] = item.op_seq
                        pending_comments.append(
                            "[SELECT " + " ".join(
                                f"{k}={v}" for k, v in selection.items()) + "]")
                    continue

                # A question.
                if limit is not None and asked >= limit:
                    break
                asked += 1
                before = counter.count
                started = time.perf_counter()
                answer, meta, error = self._ask_with_timeout(
                    item.text, history[-4:], selection, last_answered, card)
                turn = TurnRecord(
                    lineno=item.lineno, question=item.text,
                    selection=dict(selection),
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                )
                turn._comments = pending_comments  # type: ignore[attr-defined]
                pending_comments = []
                turn.expect = pending_expect
                pending_expect = {}
                if error is not None:
                    turn.error = error
                else:
                    turn.answer = answer or ""
                    turn.resolved_question = meta.get("resolved_question", item.text)
                    turn.resolution_note = meta.get("resolution_note", "") or ""
                    turn.route = meta.get("route", "") or ""
                    turn.source = meta.get("source", "") or ""
                    turn.confidence = meta.get("confidence")
                    turn.register = meta.get("register", "") or ""
                    turn.renderer = _parse_renderer_tag(turn.answer)
                    turn.subject_type = meta.get("subject_type", "") or ""
                    turn.subject_external_name = meta.get("subject_external_name", "") or ""
                    turn.record_count = meta.get("record_count", 0) or 0
                    turn.cited_refs = meta.get("cited_refs", {}) or {}
                    turn.lit_bars = sum(
                        len(turn.cited_refs.get(k, []))
                        for k in ("operations", "resources", "demands"))
                    turn.parse = meta.get("parse") or {}
                    turn.synthesis = meta.get("synthesis") or {}
                    turn.shadow = meta.get("shadow") or {}
                    # The PROBATION SHADOW runs inside the ask, so its cost is
                    # inside the wall-clock measured above — and a planner never
                    # pays it (it is our own quality control, and it runs only in
                    # the sweep). Left in, a promoted route would be reported as
                    # ~10x SLOWER than it is, which is the exact opposite of what
                    # the promotion bought. Subtracted, and reported separately.
                    shadow_ms = turn.shadow.get("latency_ms")
                    if shadow_ms and turn.latency_ms is not None:
                        turn.latency_ms = max(0.0, turn.latency_ms - shadow_ms)
                turn.llm_calls = counter.count - before
                turn.findings = check_turn(turn, self._vocab)
                result.turns.append(turn)

                # Extend history exactly as the cockpit does: subject refs from the
                # ACTIVE selection, plus this turn's route/resolved question.
                history.append({
                    "question": item.text,
                    "resolved_question": turn.resolved_question or item.text,
                    "route": turn.route or None,
                    "order": selection.get("order"),
                    "machine": selection.get("machine"),
                })
                # Carry THIS answer's resolved subject into the next question, the
                # way the panel does — the honest fix for a follow-up after a TYPED
                # entity question (CU1). An error turn carries nothing forward.
                if error is None:
                    last_answered = resolved_subject(
                        turn.subject_type, turn.subject_external_name)
            result.total_llm_calls = counter.count
        if self.parser is not None and hasattr(self.parser, "stats"):
            result.parser_stats = self.parser.stats.as_dict()
        if self.synthesizer is not None and hasattr(self.synthesizer, "stats"):
            result.synth_stats = self.synthesizer.stats.as_dict()
        return result
