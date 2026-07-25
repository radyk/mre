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
  * ``selection`` is a ``{order, machine}`` dict, the only fields the interpreter
    reads from the selection channel.

Nothing is mocked. When ``ANTHROPIC_API_KEY`` is set the interpreter and the LLM
renderer are live (the founder's real path); without a key the deterministic floor
is exercised (still the full router, validator, sidecar, and every structural
property). The runner reports which mode it ran in and a live-call count at close.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .script import Comment, ParsedScript, Question, Reset, Select, parse_script
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

    def build_vocab(self) -> Vocab:
        """A throwaway Explainer over the same snapshot, for the sidecar's shape
        checks (valid entity vocabulary + the real-doors classifier)."""
        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.explainer import Explainer
        from mre.modules.snapshot_store import SnapshotStore
        ip = self.out_dir / "evidence_index.json"
        index = (EvidenceIndex.load(ip) if ip.exists()
                 else EvidenceIndex().build(self.out_dir / self.runs_subdir))
        store = SnapshotStore(self.out_dir / "snapshots")
        return Vocab(Explainer(store, index, snapshot_id=self.snapshot_id))


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
    findings: list[Finding] = field(default_factory=list)


@dataclass
class ExamResult:
    target_label: str
    snapshot_id: str
    llm_mode: str                 # "live" | "deterministic"
    turns: list[TurnRecord] = field(default_factory=list)
    parse_errors: list[Finding] = field(default_factory=list)
    total_llm_calls: int = 0
    started_at: str = ""

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
                 session_id: str = "ai-exam") -> None:
        self.target = target
        key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.use_llm = key if use_llm is None else (use_llm and key)
        self.ledger_path = ledger_path
        self.per_question_timeout = per_question_timeout
        self.session_id = session_id
        self._vocab: Optional[Vocab] = None

    # -- one question -------------------------------------------------------

    def _ask(self, question: str, history: list[dict], selection: dict,
             last_answered: dict) -> tuple[str, dict]:
        from mre.api.app import _answer_question
        return _answer_question(
            self.target.out_dir, self.target.snapshot_id, question,
            use_llm=self.use_llm, runs_subdir=self.target.runs_subdir,
            context={"history": history, "selection": selection,
                     "last_answered_subject": last_answered},
            ledger_path=self.ledger_path, schedule_id=self.target.label,
            session_id=self.session_id, document=self.target.document,
        )

    def _ask_with_timeout(self, question: str, history: list[dict],
                          selection: dict, last_answered: dict
                          ) -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Returns (answer, meta, error). A per-question timeout / exception is
        captured as an error string, never a crash of the run."""
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(self._ask, question, history, selection, last_answered)
            try:
                answer, meta = fut.result(timeout=self.per_question_timeout)
                return answer, meta, None
            except FutureTimeout:
                return None, None, f"timed out after {self.per_question_timeout:g}s"
            except Exception as exc:  # noqa: BLE001 — ask-path failure is a finding
                return None, None, f"{type(exc).__name__}: {exc}"

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

        self._vocab = self.target.build_vocab()
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
        # The resolved subject of the PRIOR answer, carried into the next question
        # exactly as the panel does (Session 4A.3c CU1). Reset by RESET.
        last_answered: dict = {}
        # Comments/selects between questions attach to the NEXT question in the
        # transcript for readability; we buffer them here.
        pending_comments: list[str] = []
        asked = 0

        with _CallCounter() as counter:
            for item in script.items:
                if isinstance(item, Comment):
                    pending_comments.append(item.text)
                    continue
                if isinstance(item, Reset):
                    history = []
                    selection = {}
                    last_answered = {}
                    pending_comments.append("[RESET — conversation cleared]")
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
                        pending_comments.append(
                            "[SELECT " + " ".join(
                                f"{k}={v}" for k, v in selection.items()) + "]")
                    continue

                # A question.
                if limit is not None and asked >= limit:
                    break
                asked += 1
                before = counter.count
                answer, meta, error = self._ask_with_timeout(
                    item.text, history[-4:], selection, last_answered)
                turn = TurnRecord(
                    lineno=item.lineno, question=item.text,
                    selection=dict(selection),
                )
                turn._comments = pending_comments  # type: ignore[attr-defined]
                pending_comments = []
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
        return result
