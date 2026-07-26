"""M10 — the labeled-synthesis loop (R-AI5(2), Session 4A.5b CU2).

The ask path's SECOND tier. A matched intent dispatches to the contracted routes and
never comes here; an UNMATCHED intent arrives with the planner's question, the
conversation context, and the CU1 read-only tool surface. The model reasons in an
agentic loop under the stated budget and produces a draft answer as STRUCTURED
CLAIMS — each a sentence plus the record ids it believes support it.

Two boundaries, both load-bearing:

  * THE DRAFT NEVER RENDERS. It goes to the verifier (``claim_verifier``), which is
    deterministic code, and only the hardened result reaches the surface. The
    model's beliefs about its own citations are INPUT to verification, never the
    label (R-AI5(8)).
  * NO SILENT PATH BETWEEN THE TIERS. This module is reachable only from
    ``interpreter.dispatch`` on ``Intent.UNMATCHED``; a matched intent cannot fall
    here and an unmatched one never guesses a route.

Without a client the synthesizer is simply UNAVAILABLE and the dispatch falls back to
part 1's honest unsupported answer — never a keyword guess, never a stall.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mre.contracts.synthesis import (
    ClaimKind,
    DraftClaim,
    MAX_TOOL_CALLS,
    SYNTHESIS_TIMEOUT_S,
    SynthesisAnswer,
    TOOL_ARGS,
    TOOL_MEANINGS,
    ToolName,
)
from mre.modules.evidence_tools import EvidenceToolbox, Stopwatch
from mre.modules.question_parser import extract_json

_PROMPT_PATH = Path(__file__).with_name("synthesis_prompt.md")
_PROMPT_MARKER = "## PROMPT"
_VERSION_RE = re.compile(r"prompt_version:\s*(\S+)")

#: A hard iteration ceiling above the tool budget: a model that emits neither a tool
#: call nor claims must still terminate. Never the primary bound.
_MAX_STEPS = MAX_TOOL_CALLS + 4


def load_prompt() -> tuple[str, str]:
    """(template, version) from the governed prompt artifact. Everything above the
    ``## PROMPT`` marker is documentation and is never sent to the model."""
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    m = _VERSION_RE.search(text.split(_PROMPT_MARKER, 1)[0])
    version = m.group(1) if m else "?"
    _, _, body = text.partition(_PROMPT_MARKER)
    return body.strip(), version


def render_tools() -> str:
    """The closed tool surface WITH each tool's meaning and typed arguments — the
    artifact the prompt renders. Authored in ``contracts.synthesis`` so a tool added
    without a meaning fails the parity test rather than becoming uncallable."""
    lines: list[str] = []
    for tool in ToolName:
        args = TOOL_ARGS[tool]
        sig = ", ".join(
            f"{a.name}{'' if a.required else '?'}" for a in args) or "no arguments"
        lines.append(f"  {tool.value}({sig}) — {TOOL_MEANINGS[tool]}")
        for a in args:
            if a.meaning:
                lines.append(f"      {a.name}: {a.meaning}")
    return "\n".join(lines)


def render_context(context: Optional[dict]) -> str:
    """The same three channels the parse layer reads — the live board selection, the
    subject of the previous answer, and the recent turns. Never more."""
    from mre.modules.question_parser import render_context as _rc
    return _rc(context)


@dataclass
class SynthesizerStats:
    """Loop instrumentation for the sweep (CU5). Counts only."""
    syntheses: int = 0
    calls: int = 0                  # model calls (every step)
    tool_calls: int = 0
    malformed: int = 0
    budget_exhausted: int = 0
    timed_out: int = 0
    unanswerable: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def median_latency_ms(self) -> Optional[float]:
        if not self.latencies_ms:
            return None
        xs = sorted(self.latencies_ms)
        mid = len(xs) // 2
        return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2

    def p90_latency_ms(self) -> Optional[float]:
        if not self.latencies_ms:
            return None
        xs = sorted(self.latencies_ms)
        return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))]

    def as_dict(self) -> dict:
        return {"syntheses": self.syntheses, "calls": self.calls,
                "tool_calls": self.tool_calls, "malformed": self.malformed,
                "budget_exhausted": self.budget_exhausted,
                "timed_out": self.timed_out, "unanswerable": self.unanswerable,
                "median_latency_ms": self.median_latency_ms(),
                "p90_latency_ms": self.p90_latency_ms()}


@dataclass
class Draft:
    """What the loop produced, before verification."""
    claims: list[DraftClaim] = field(default_factory=list)
    cannot_answer: str = ""
    budget_exhausted: bool = False
    timed_out: bool = False
    latency_ms: float = 0.0
    steps: int = 0


class Synthesizer:
    """R-AI5(2) — the labeled open synthesis tier.

    Construct with a client (a real Anthropic client or a test double exposing
    ``messages.create``). With no client and no key the synthesizer is UNAVAILABLE:
    ``synthesize`` returns None and the dispatch answers with part 1's honest
    unsupported bridge."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001",
                 api_key: Optional[str] = None, _client: Any = None,
                 max_tokens: int = 1400,
                 timeout_s: float = SYNTHESIS_TIMEOUT_S) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = _client
        self._max_tokens = max_tokens
        self.timeout_s = timeout_s
        self._template, self.prompt_version = load_prompt()
        self.stats = SynthesizerStats()
        self.available = False
        if _client is not None:
            self.available = True
        elif self._api_key:
            # Fail-closed construction, exactly like the parser: no package, a bad
            # key, any client-build failure leaves it UNAVAILABLE, never a raise.
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self.available = True
            except Exception:  # noqa: BLE001 — construction must never raise
                self.available = False

    # -- the prompt ---------------------------------------------------------

    def prompt_for(self, question: str, context: Optional[dict],
                   budget: str) -> str:
        return (self._template
                .replace("{TOOLS}", render_tools())
                .replace("{CONTEXT}", render_context(context))
                .replace("{BUDGET}", budget)
                .replace("{QUESTION}", question or ""))

    # -- one model step -----------------------------------------------------

    def _call(self, messages: list[dict]) -> Optional[str]:
        try:
            resp = self._client.messages.create(
                model=self._model, max_tokens=self._max_tokens, temperature=0,
                messages=messages,
            )
            return resp.content[0].text
        except Exception:  # noqa: BLE001 — a model failure is never a crash
            return None

    # -- the loop -----------------------------------------------------------

    def draft(self, question: str, *, toolbox: EvidenceToolbox,
              context: Optional[dict] = None) -> Draft:
        """Reason to a DRAFT under the CU1 budget. Never renders, never verifies."""
        budget = (f"at most {toolbox.max_calls} tool calls and "
                  f"{self.timeout_s:g} seconds for this question")
        messages: list[dict] = [
            {"role": "user", "content": self.prompt_for(question, context, budget)}]
        watch = Stopwatch(self.timeout_s)
        out = Draft()
        forced = False

        for step in range(_MAX_STEPS):
            out.steps = step + 1
            if not forced and (toolbox.exhausted or watch.expired):
                forced = True
                out.budget_exhausted = toolbox.exhausted
                out.timed_out = watch.expired
                messages.append({"role": "user", "content": _forced_close(toolbox)})
            self.stats.calls += 1
            text = self._call(messages)
            emission = extract_json(text or "")
            if emission is None:
                self.stats.malformed += 1
                if forced or step >= _MAX_STEPS - 1:
                    break
                messages.append({"role": "assistant", "content": text or "(empty)"})
                messages.append({"role": "user", "content": _MALFORMED_NOTE})
                continue

            if isinstance(emission.get("claims"), list):
                out.claims = _coerce_claims(emission["claims"])
                break
            if emission.get("cannot_answer"):
                out.cannot_answer = str(emission["cannot_answer"])[:300]
                break
            if emission.get("tool"):
                result = toolbox.call(str(emission["tool"]), emission.get("args") or {})
                self.stats.tool_calls += 1
                messages.append({"role": "assistant",
                                 "content": json.dumps(emission)})
                messages.append({"role": "user", "content": _tool_message(result)})
                continue

            # Neither a tool call nor an answer — treat as malformed and nudge once.
            self.stats.malformed += 1
            if forced:
                break
            messages.append({"role": "assistant", "content": text or "(empty)"})
            messages.append({"role": "user", "content": _MALFORMED_NOTE})

        out.latency_ms = watch.elapsed_ms
        out.budget_exhausted = out.budget_exhausted or toolbox.exhausted
        out.timed_out = out.timed_out or watch.expired
        return out

    # -- draft -> hardened answer ------------------------------------------

    def synthesize(self, question: str, *, explainer: Any,
                   context: Optional[dict] = None,
                   toolbox: Optional[EvidenceToolbox] = None
                   ) -> Optional[SynthesisAnswer]:
        """The whole second tier for one question: reason, then HARDEN.

        Returns None only when the synthesizer is unavailable (no client) — every
        other outcome is a ``SynthesisAnswer``, honest about what it could not
        ground."""
        if not self.available or self._client is None:
            return None
        from mre.modules.claim_verifier import verify_draft

        started = time.perf_counter()
        box = toolbox if toolbox is not None else EvidenceToolbox(explainer)
        draft = self.draft(question, toolbox=box, context=context)
        answer = verify_draft(question, draft.claims, toolbox=box)
        answer.tool_calls = list(box.calls)
        answer.budget_exhausted = draft.budget_exhausted
        answer.timed_out = draft.timed_out
        answer.model = self._model
        answer.prompt_version = self.prompt_version
        answer.latency_ms = (time.perf_counter() - started) * 1000.0
        if draft.cannot_answer and not answer.claims:
            answer.unanswerable = True
        if not answer.claims:
            answer.unanswerable = True

        self.stats.syntheses += 1
        self.stats.latencies_ms.append(answer.latency_ms)
        if answer.budget_exhausted:
            self.stats.budget_exhausted += 1
        if answer.timed_out:
            self.stats.timed_out += 1
        if answer.unanswerable:
            self.stats.unanswerable += 1
        return answer


# ---------------------------------------------------------------------------
# The loop's own messages (authored — the model is never asked to grade itself)
# ---------------------------------------------------------------------------

_MALFORMED_NOTE = (
    "That was not a single strict JSON object. Reply with exactly one of: "
    '{"tool": ..., "args": {...}}, {"claims": [...]}, or {"cannot_answer": "..."}. '
    "No prose, no code fence."
)


def _forced_close(toolbox: EvidenceToolbox) -> str:
    consulted = ", ".join(sorted({c.tool for c in toolbox.calls})) or "nothing"
    return (
        "BUDGET REACHED — no more tool calls. Answer now with claims built from what "
        f"you already read (you consulted: {consulted}). Say plainly in one claim "
        "what you did not get to look at. Reply with a single "
        '{"claims": [...]} object.'
    )


def _tool_message(result: Any) -> str:
    """The tool result handed back to the loop: the rows verbatim (with their record
    ids), the summary, and the honest note on an empty or failed read."""
    payload = {
        "tool": result.tool.value,
        "ok": result.ok,
        "note": result.note,
        "summary": result.summary,
        "rows": result.rows,
        "truncated": result.truncated,
        "enumerates_whole_set": result.enumerates_set,
    }
    try:
        return json.dumps(payload, default=str)
    except Exception:  # noqa: BLE001
        return json.dumps({"tool": result.tool.value, "ok": False,
                           "note": "result could not be serialized"})


def _coerce_claims(raw: list) -> list[DraftClaim]:
    """The emission's claims → the contract. A malformed claim is DROPPED, never
    repaired into something the model did not say."""
    out: list[DraftClaim] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        ids = [str(r).strip() for r in (item.get("record_ids") or [])
               if str(r).strip()]
        try:
            kind = ClaimKind(str(item.get("kind") or "fact"))
        except ValueError:
            kind = ClaimKind.FACT
        out.append(DraftClaim(text=text[:600], record_ids=ids[:12], kind=kind))
    return out
