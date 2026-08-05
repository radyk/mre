"""The multi-turn recon harness — Session 4A teaching-graft (d.0).

ONE job: drive `run_ask` the way `src/cockpit/src/askpanel.js` drives it, turn
after turn, and CAPTURE what each tier actually received. Nothing here changes
product behaviour and nothing here is a fix. It is an instrument.

Three things it does that the exam runner does not:

  * it records the VERBATIM PROMPT each tier was handed, by wrapping the parser
    and the synthesizer in recording proxies. `prompt_for` is a pure function on
    both, so the capture is the real string, not a reconstruction. The
    synthesizer proxy additionally records the CONTEXT DICT `synthesize` was
    called with — which is not the dict the dispatch was given (the dispatch
    adds `document`, and on a diverted match `dropped_qualifier`), so a
    reconstruction here would be a guess;
  * it mirrors `askpanel.js`'s history construction EXACTLY — see `Conversation.
    ask` — because a harness that carries more than the panel carries measures a
    product nobody ships (the exam runner's own law, `runner.py` module
    docstring);
  * it can be pointed at a DIFFERENT SCHEDULE mid-conversation without clearing
    anything, which is what `main.js::onVersionChange` does after an accept and
    is the whole subject of probe P4.

Read-only against existing artifacts. Mints nothing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget, resolved_subject  # noqa: E402
from mre.modules.interpreter import (  # noqa: E402
    carry_subject, forget_deliveries, remember_terms, run_ask,
)
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402
from mre.modules.synthesizer import Synthesizer  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

#: The two tools that read OUR DOCUMENTATION rather than the plant (R-TG5's own
#: subtraction, copied from `teaching_graft_c2/floor_tail.py` so the two
#: sessions' "did it read the board" numbers mean the same thing).
DOC_TOOLS = frozenset({"constraint_catalog", "spec_lookup"})


# ---------------------------------------------------------------------------
# Recording proxies — the capture, without a product source change
# ---------------------------------------------------------------------------

class RecordingParser:
    """A `QuestionParser` that keeps the prompt it built for each parse."""

    def __init__(self, inner: QuestionParser) -> None:
        self._inner = inner
        self.prompts: list[str] = []

    @property
    def available(self) -> bool:
        return self._inner.available

    @property
    def stats(self) -> Any:
        return self._inner.stats

    def parse(self, question: str, **kw: Any) -> Any:
        self.prompts.append(self._inner.prompt_for(question, kw.get("context")))
        return self._inner.parse(question, **kw)


class RecordingSynthesizer:
    """A `Synthesizer` that keeps the CONTEXT and the PROMPT of each synthesis.

    The context is captured at `synthesize`, i.e. AFTER `_synthesis_dispatch`
    has added the document and any dropped qualifier — the dict the tier really
    sees. The prompt is then rebuilt from that captured context with the
    inner synthesizer's own `prompt_for`, which is the same pure call the loop
    makes on its first step.
    """

    def __init__(self, inner: Synthesizer) -> None:
        self._inner = inner
        self.contexts: list[dict] = []
        self.prompts: list[str] = []

    @property
    def available(self) -> bool:
        return self._inner.available

    @property
    def stats(self) -> Any:
        return self._inner.stats

    def synthesize(self, question: str, **kw: Any) -> Any:
        ctx = kw.get("context") or {}
        self.contexts.append(ctx)
        budget = (f"at most {kw['toolbox'].max_calls} tool calls and "
                  f"{self._inner.timeout_s:g} seconds for this question")
        self.prompts.append(self._inner.prompt_for(question, ctx, budget))
        return self._inner.synthesize(question, **kw)


class UnreachableClient:
    """A client whose every call raises — the outage seam probe P5 needs.

    `llm_compat.call_text_outcome` classifies a raising `messages.create` as
    UNREACHABLE, which is exactly the state R-OF1's floors were built for. This
    is a TRANSPORT double, not a source change: the product code path is the
    shipped one.
    """

    def __init__(self) -> None:
        self.messages = self

    def create(self, **_kw: Any) -> Any:  # noqa: D102
        raise ConnectionError("multiturn_recon: simulated transport failure")


# ---------------------------------------------------------------------------
# One turn, as observed
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    n: int
    question: str
    schedule: str
    route: str = ""
    intent: str = ""
    confidence: Optional[float] = None
    register: str = ""
    tier: str = ""
    resolved_question: str = ""
    resolution_note: str = ""
    subject_type: str = ""
    subject_name: str = ""
    record_count: int = 0
    text: str = ""
    # what the parse said about the subjects it bound
    subjects: list[dict] = field(default_factory=list)
    followup_of: str = ""
    # synthesis detail, when the second tier answered
    claims: list[dict] = field(default_factory=list)
    claim_counts: dict = field(default_factory=dict)
    deferred: int = 0
    tools: list[str] = field(default_factory=list)
    board_reads: list[str] = field(default_factory=list)
    licence: str = ""
    # the two captured payloads
    parse_prompt: str = ""
    synthesis_prompt: str = ""
    synthesis_context_keys: list[str] = field(default_factory=list)
    # what the CLIENT was holding when this turn was sent
    sent_history: list[dict] = field(default_factory=list)
    sent_last_answered: dict = field(default_factory=dict)
    sent_selection: dict = field(default_factory=dict)
    # signals stamped on the bundle
    key_facts: dict = field(default_factory=dict)

    def brief(self) -> str:
        bits = [f"T{self.n} [{self.schedule[-3:]}]", f"route={self.route}",
                f"reg={self.register}"]
        if self.claims:
            bits.append(f"claims={len(self.claims)}")
        if self.tools:
            bits.append(f"reads={self.board_reads}")
        for k in ("repeat", "deaf"):
            if k in self.key_facts:
                bits.append(f"{k}={self.key_facts[k]}")
        return "  ".join(bits)


# ---------------------------------------------------------------------------
# The conversation — askpanel.js, in Python
# ---------------------------------------------------------------------------

class Conversation:
    """A cockpit ask panel: one session id, a rolling history, a last-answered
    subject, a board selection, and a MUTABLE schedule binding."""

    def __init__(self, session_id: str, target: RunTarget,
                 parser: RecordingParser, synth: RecordingSynthesizer) -> None:
        self.session_id = session_id
        self.target = target
        self._explainer = target.build_vocab()._ex
        self.parser = parser
        self.synth = synth
        # askpanel.js: `const askHistory = []` / `let lastAnswered = {}`
        self.history: list[dict] = []
        self.last_answered: dict = {}
        self.selection: dict = {}
        self.card: dict = {}
        self.turns: list[Turn] = []

    # -- the mutable schedule binding (main.js::onVersionChange) -------------

    def rebind(self, target: RunTarget, *, clear_selection: bool = True) -> None:
        """What `onVersionChange` does: point at a new schedule, drop the board
        selection, and TOUCH NOTHING ELSE. No history clear, no session change,
        no server-side forget. This is the shipped gesture, reproduced."""
        self.target = target
        self._explainer = target.build_vocab()._ex
        if clear_selection:
            self.selection = {}

    # -- the RESET discipline ----------------------------------------------

    def reset(self) -> None:
        """The bank's RESET: every channel the runner clears, plus the server's
        own (`forget_deliveries`, which also clears ANSWER_MEMORY)."""
        self.history = []
        self.last_answered = {}
        self.selection = {}
        self.card = {}
        forget_deliveries(self.session_id)

    # -- one turn -----------------------------------------------------------

    def ask(self, question: str, *, select: Optional[dict] = None) -> Turn:
        if select is not None:
            self.selection = dict(select)
        sent_history = self.history[-4:]
        context = {"history": sent_history, "selection": self.selection,
                   "last_answered_subject": self.last_answered,
                   "card": self.card}
        p_before, s_before = len(self.parser.prompts), len(self.synth.prompts)

        r = run_ask(self._explainer, question, parser=self.parser,
                    synthesizer=self.synth, context=context,
                    document=self.target.document, session_id=self.session_id,
                    schedule_id=self.target.label)

        text = TemplateRenderer().render(r.bundle)
        # R-TE1 clause (1) (session (d.3)): the API records which of OUR WORDS
        # the planner was shown, from the RENDERED text, right after the render.
        # This harness renders for itself, so it makes the same call at the same
        # point rather than holding its own copy of the rule.
        remember_terms(self.session_id, self.target.label, text)
        t = Turn(n=len(self.turns) + 1, question=question,
                 schedule=self.target.label,
                 route=r.route, register=r.register,
                 confidence=r.confidence,
                 resolved_question=r.resolved_question,
                 resolution_note=r.resolution_note, text=text,
                 sent_history=[dict(h) for h in sent_history],
                 sent_last_answered=dict(self.last_answered),
                 sent_selection=dict(self.selection))
        if r.parsed is not None:
            t.intent = r.parsed.intent.value
            t.followup_of = r.parsed.followup_of.value
            t.subjects = [{"kind": s.kind.value, "raw": s.raw, "ref": s.ref,
                           "source": s.source.value, "pointed": s.pointed,
                           "op_seq": s.op_seq} for s in r.parsed.subjects]
        t.subject_type = getattr(r.bundle, "subject_type", "") or ""
        t.subject_name = getattr(r.bundle, "subject_external_name", "") or ""
        t.record_count = len(getattr(r.bundle, "ordered_records", None) or [])
        kf = getattr(r.bundle, "key_facts", None)
        if isinstance(kf, dict):
            t.key_facts = {k: kf[k] for k in ("repeat", "deaf", "deaf_prior")
                           if k in kf}
        a = r.synthesis
        if a is not None:
            # `VerifiedClaim.cited_record_ids` is the verifier's list and the one
            # `_synthesis_bundle` builds `ordered_records` from; `record_ids` is
            # the DRAFT's field and does not exist here. Reading the draft field
            # off a verified claim silently yields [] — which this harness did on
            # its first run, and is why both are recorded by name.
            t.claims = [{"text": c.text,
                         "status": getattr(c.status, "value", str(c.status)),
                         "kind": getattr(c.kind, "value", str(c.kind)),
                         "cited": list(getattr(c, "cited_record_ids", []) or []),
                         "consulted": list(getattr(c, "consulted_record_ids", []) or []),
                         "read_from": list(getattr(c, "read_from", []) or []),
                         "load_bearing": bool(getattr(c, "load_bearing", False))}
                        for c in (a.claims or [])]
            t.claim_counts = a.counts()
            t.deferred = len(getattr(a, "deferred", None) or [])
            t.tools = [c.tool for c in (getattr(a, "tool_calls", None) or [])]
            t.board_reads = [x for x in t.tools if x not in DOC_TOOLS]
        if len(self.parser.prompts) > p_before:
            t.parse_prompt = self.parser.prompts[-1]
        if len(self.synth.prompts) > s_before:
            t.synthesis_prompt = self.synth.prompts[-1]
            t.synthesis_context_keys = sorted(self.synth.contexts[-1].keys())
        t.tier = "synthesis" if t.synthesis_prompt else "route"

        # --- askpanel.js::run, verbatim in behaviour -----------------------
        self.history.append({
            "question": question,
            "resolved_question": r.resolved_question or question,
            "route": r.route or None,
            "order": self.selection.get("order"),
            "machine": self.selection.get("machine"),
            "op_seq": self.selection.get("op_seq"),
        })
        # R-LD6 clause (5) (session (d.2)): the panel reads the ask meta's
        # `carry_subject`, which the API computes with `interpreter.carry_subject`.
        # This harness drives `run_ask` directly, so it calls the SAME function on
        # the same two inputs rather than re-implementing the rule — a harness
        # holding its own copy of a rule is what made the rule drift in the first
        # place. `resolved_subject` stays imported as clause (1)'s definition.
        self.last_answered = carry_subject(r.bundle, r.parsed)
        self.turns.append(t)
        return t


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def build(schedule: str = "rolling-db5395dc-2ae",
          data_root: str = "_data") -> RunTarget:
    return RunTarget.from_schedule(ROOT / data_root, schedule)


def tiers() -> tuple[RecordingParser, RecordingSynthesizer]:
    p, s = QuestionParser(), Synthesizer()
    if not (p.available and s.available):
        raise SystemExit("PARSER OR SYNTHESIZER UNAVAILABLE — every answer would "
                         "be the honest floor, which is not a measurement.")
    return RecordingParser(p), RecordingSynthesizer(s)


def dump(name: str, payload: Any) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  -> {path.relative_to(ROOT)}")
    return path


def turns_payload(conv: Conversation) -> list[dict]:
    from dataclasses import asdict
    return [asdict(t) for t in conv.turns]
