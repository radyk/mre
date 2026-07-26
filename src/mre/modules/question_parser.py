"""The LLM-first question parser (R-AI5(1), Session 4A.5a CU1).

ONE language-model call, temperature 0, against the CLOSED intent vocabulary
(``mre.contracts.parse``), with the conversation history, the live board selection,
and the last-answered subject as context. It emits a ``ParsedQuestion`` — intent,
typed subjects, polarity, follow-up linkage, confidence, and a clarify payload when
it cannot commit — and NEVER an answer.

What this module replaces: the deterministic keyword/precedence classifier
(``Explainer.classify``) and the deictic/correction/menu/list-expand rewrite rules
(``interpreter.resolve_followup``), both retired by R-AI5. Four founder exam rounds
proved the class those rules belonged to: understanding INTENT is a natural-language
problem, and string matching kept answering the wrong question with perfect
citations. There is NO deterministic-classifier fallback (R-AI5(2)) — without a
parser the ask path answers honestly that it could not interpret the question.

What stays deterministic, deliberately:

  * The PROMPT is a governed artifact (``parse_prompt.md``), versioned and reviewed
    like a vocabulary change.
  * SUBJECT RESOLUTION is deterministic and local: the model says which words name
    a subject and whether the planner pointed instead of naming; this module
    resolves those words against THIS run's vocabulary (the identity map, the
    fuzzy/near-miss forms, the "order N" number index) and binds a pointed subject
    from selection > last answered subject > history. The model never invents a ref
    and never picks between two candidates — an unresolvable subject stays
    unresolved and the dispatch answers honestly.
  * The output is validated at construction (pydantic). A malformed emission is
    retried ONCE and then becomes the clarify path — never a guess, never a crash.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mre.contracts.parse import (
    ClarifyPayload,
    ClarifyReason,
    FollowupKind,
    Intent,
    INTENT_MEANINGS,
    MODEL_SELECTABLE_INTENTS,
    ParsedQuestion,
    Polarity,
    SubjectKind,
    SubjectRef,
    SubjectSource,
)

_PROMPT_PATH = Path(__file__).with_name("parse_prompt.md")
_PROMPT_MARKER = "## PROMPT"
_VERSION_RE = re.compile(r"prompt_version:\s*(\S+)")


def load_prompt() -> tuple[str, str]:
    """(template, version) from the governed prompt artifact. Everything above the
    ``## PROMPT`` marker is documentation and is never sent to the model."""
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    m = _VERSION_RE.search(text.split(_PROMPT_MARKER, 1)[0])
    version = m.group(1) if m else "?"
    _, _, body = text.partition(_PROMPT_MARKER)
    return body.strip(), version


def render_intents() -> str:
    """The closed vocabulary WITH each intent's one-line meaning AND the subject it
    needs — the artifact the prompt renders.

    The meanings are authored in ``contracts.parse.INTENT_MEANINGS`` (so a route
    added without a meaning fails the parity test); the required subject is DERIVED
    from the route taxonomy, never re-authored, so the two cannot drift. Naming the
    requirement matters: the first sweep had "whats holding CUT-01" parsed as
    `start-reason` — an intent that needs an ORDER — with only a machine named, and
    the honest result was a near-miss bridge instead of the machine's schedule."""
    from mre.modules.explainer import ROUTE_TAXONOMY
    lines = []
    for i in MODEL_SELECTABLE_INTENTS:
        needs = ROUTE_TAXONOMY.get(i.value, {}).get("params", [])
        suffix = f"  [needs a named {' + '.join(needs)}]" if needs else ""
        lines.append(f"  {i.value} — {INTENT_MEANINGS[i]}{suffix}")
    return "\n".join(lines)


def render_context(context: Optional[dict]) -> str:
    """The conversation context the parse reads (R-AI5(1)): the live board
    selection, the last answered subject, and the recent turns — exactly the three
    channels the cockpit panel transmits, never more."""
    context = context or {}
    selection = context.get("selection") or {}
    last = context.get("last_answered_subject") or {}
    history = context.get("history") or []

    def _pair(d: dict) -> str:
        bits = [f"{k}={v}" for k in ("order", "machine") if (v := d.get(k))]
        return " ".join(bits) if bits else "none"

    lines = [f"  BOARD SELECTION (what is highlighted right now): {_pair(selection)}",
             f"  SUBJECT OF THE PREVIOUS ANSWER: {_pair(last)}"]
    if not history:
        lines.append("  RECENT TURNS: none — this is the first question.")
        return "\n".join(lines)
    lines.append("  RECENT TURNS (oldest first):")
    for turn in history[-4:]:
        q = (turn.get("question") or "").strip()
        route = turn.get("route") or "?"
        lines.append(f'    planner asked: "{q}"  -> answered with intent: {route}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic subject resolution (local, never the model's)
# ---------------------------------------------------------------------------

_KIND_BY_NAME = {k.value: k for k in SubjectKind}


def _resolve_order(explainer: Any, raw: str) -> Optional[str]:
    """A planner's words for an order → this run's external ref, or None.

    Exact / unique-substring against the identity map first, then the near-miss
    forms the fuzzy layer learned from the world's REAL ids (ord-o5, ORD-5, ord 05),
    then the "order N" number index. Never string synthesis; an ambiguous number was
    already dropped from the index, so it stays unresolved rather than guessed."""
    if not raw:
        return None
    hit = explainer.resolve_order_value(raw)
    if hit:
        return hit
    for probe in (raw, f"order {raw}" if raw.strip().isdigit() else None):
        if not probe:
            continue
        try:
            _new, notes = explainer.rewrite_fuzzy_orders(probe)
        except Exception:  # noqa: BLE001 — resolution must never raise
            notes = []
        if notes:
            return notes[0][1]
    return None


# Words a planner wraps a machine's name in ("the paint LINE", "the big PRESS").
# Stripped before the token-wise fallback so the distinguishing word is what
# matches. Not a route decision — a resolution one.
_MACHINE_FILLER = frozenset({
    "the", "a", "an", "my", "our", "that", "this", "big", "small", "old", "new",
    "machine", "line", "cell", "station", "resource", "workcenter", "work",
    "center", "centre", "unit", "one",
})


def _resolve_machine(explainer: Any, raw: str) -> Optional[str]:
    """A planner's words for a machine → this run's external ref, or None.

    Exact / unique-substring first; then TOKEN-WISE, because planners say "the
    paint line" and "the big press" where the world says PAINT-01 and PRESS-FAST
    (the first sweep's finding). A token resolves only when it picks out exactly
    one machine — two candidates leave it unresolved, never guessed."""
    if not raw:
        return None
    hit = explainer.resolve_machine_value(raw)
    if hit:
        return hit
    known = getattr(explainer, "_machine_refs", {}) or {}
    for tok in re.findall(r"[A-Za-z0-9]+", raw):
        if len(tok) < 3 or tok.lower() in _MACHINE_FILLER:
            continue
        matches = {v for k, v in known.items() if tok.upper() in k}
        if len(matches) == 1:
            return next(iter(matches))
    return None


def _resolve_concept(raw: str) -> Optional[str]:
    from mre.modules.capabilities import coaching_concept
    return coaching_concept((raw or "").lower())


def _bind_from_context(kind: SubjectKind, context: dict
                       ) -> tuple[Optional[str], SubjectSource]:
    """A POINTED subject ("this order", "it") bound at the fixed priority the
    cockpit's channels imply: live board selection > the subject of the previous
    answer > conversation history. Typed — "that machine" never binds to an order
    (the founder's confident-wrong bug). None when nothing of that type is live."""
    key = kind.value
    if key not in ("order", "machine"):
        return None, SubjectSource.UTTERANCE
    selection = context.get("selection") or {}
    if selection.get(key):
        return selection[key], SubjectSource.SELECTION
    last = context.get("last_answered_subject") or {}
    if last.get(key):
        return last[key], SubjectSource.LAST_ANSWER
    for turn in reversed(context.get("history") or []):
        if turn.get(key):
            return turn[key], SubjectSource.HISTORY
    return None, SubjectSource.UTTERANCE


def bind_subjects(explainer: Any, raw_subjects: list[dict],
                  context: Optional[dict]) -> list[SubjectRef]:
    """The model's typed subject WORDS → resolved ``SubjectRef``s.

    A subject the planner POINTED at (``from_context``) binds from the live
    channels; a subject the planner NAMED resolves against this run's vocabulary.
    An unresolvable subject is returned UNRESOLVED (``ref=None``) — the dispatch
    then answers honestly (absent entity / clarify), never globally."""
    context = context or {}
    out: list[SubjectRef] = []
    for raw_subject in raw_subjects or []:
        if not isinstance(raw_subject, dict):
            continue
        kind = _KIND_BY_NAME.get(str(raw_subject.get("kind", "")).lower())
        if kind is None:
            continue
        raw = str(raw_subject.get("raw", "") or "").strip()
        pointed = bool(raw_subject.get("from_context"))
        ref: Optional[str] = None
        source = SubjectSource.UTTERANCE
        if pointed:
            ref, source = _bind_from_context(kind, context)
            if ref is None and raw and explainer is not None:
                # The model flagged it as pointed but also gave usable words —
                # try them before giving up (a named subject is never worse).
                ref = _resolve_named(explainer, kind, raw)
                source = SubjectSource.UTTERANCE if ref else source
        elif explainer is not None:
            ref = _resolve_named(explainer, kind, raw)
        out.append(SubjectRef(kind=kind, raw=raw, ref=ref, source=source,
                              pointed=pointed))
    return out


def _resolve_named(explainer: Any, kind: SubjectKind, raw: str) -> Optional[str]:
    if kind is SubjectKind.ORDER:
        return _resolve_order(explainer, raw)
    if kind is SubjectKind.MACHINE:
        return _resolve_machine(explainer, raw)
    if kind is SubjectKind.CONCEPT:
        return _resolve_concept(raw)
    # customer — the schedule filter substring-matches the planner's own words
    return raw or None


# ---------------------------------------------------------------------------
# The emission → contract
# ---------------------------------------------------------------------------

def _coerce_intent(value: Any) -> Optional[Intent]:
    try:
        intent = Intent(str(value))
    except ValueError:
        return None
    return None if intent is Intent.UNKNOWN_ENTITY else intent


def _names_a_followup(value: Any) -> bool:
    """True when the emission put a FOLLOW-UP KIND in the intent field.

    Session 4A.5b, from the sweep's malformed-emission samples: the model twice
    named the GESTURE correctly and put it in the wrong field —
    ``{"intent": "prove-it", "followup_of": "prove-it"}`` and
    ``{"intent": "list-expand", "followup_of": "list-expand"}`` — and the whole
    parse was discarded as malformed, retried, discarded again, and answered with
    "I couldn't make out what that one was asking". Throwing away a correct reading
    over a misfiled field is not strictness, it is waste: the intent becomes
    ``unmatched`` (the honest destination, which now answers) and the follow-up
    linkage — which the model got right — is kept."""
    try:
        FollowupKind(str(value))
    except ValueError:
        return False
    return True


def build_parsed(question: str, emission: dict, explainer: Any,
                 context: Optional[dict], *, prompt_version: str = "",
                 retries: int = 0, latency_ms: Optional[float] = None
                 ) -> Optional[ParsedQuestion]:
    """A validated emission dict → ``ParsedQuestion``. None when the emission does
    not name a member of the closed vocabulary (the caller retries, then clarifies).
    """
    intent = _coerce_intent(emission.get("intent"))
    if intent is None:
        if not _names_a_followup(emission.get("intent")):
            return None
        intent = Intent.UNMATCHED
    subjects = bind_subjects(explainer, emission.get("subjects") or [], context)

    polarity = None
    raw_pol = emission.get("polarity")
    if raw_pol not in (None, "", "null"):
        try:
            polarity = Polarity(str(raw_pol))
        except ValueError:
            polarity = None

    try:
        followup = FollowupKind(str(emission.get("followup_of") or "none"))
    except ValueError:
        followup = FollowupKind.NONE

    try:
        confidence = max(0.0, min(1.0, float(emission.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    nearest = [i for i in (_coerce_intent(n) for n in emission.get("nearest") or [])
               if i is not None and i is not Intent.UNMATCHED]

    clarify = None
    raw_clarify = emission.get("clarify")
    # An UNMATCHED question is already answered honestly (shape recognized, nearest
    # capabilities offered). Asking the planner to disambiguate something we have no
    # route for is a dead end, so a clarify on an unmatched parse is dropped here as
    # well as forbidden in the prompt — belt and suspenders on a dead end.
    if intent is Intent.UNMATCHED:
        raw_clarify = None
    if isinstance(raw_clarify, dict) and raw_clarify.get("reason"):
        try:
            clarify = ClarifyPayload(
                reason=ClarifyReason(str(raw_clarify["reason"])),
                detail=str(raw_clarify.get("detail", ""))[:400])
        except ValueError:
            clarify = None

    try:
        return ParsedQuestion(
            question=question, intent=intent, subjects=subjects,
            polarity=polarity, followup_of=followup, confidence=confidence,
            nearest=nearest, clarify=clarify, prompt_version=prompt_version,
            retries=retries, latency_ms=latency_ms)
    except Exception:  # noqa: BLE001 — validation failure is a malformed emission
        return None


def extract_json(text: str) -> Optional[dict]:
    """The first JSON object in the model's text (tolerant of a code fence or
    surrounding prose; strict about it being an object)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def clarify_parse_failed(question: str, *, prompt_version: str = "",
                         retries: int = 0,
                         latency_ms: Optional[float] = None) -> ParsedQuestion:
    """The floor: the parse could not commit. Never a guess, never a crash."""
    return ParsedQuestion(
        question=question, intent=Intent.UNMATCHED, confidence=0.0,
        clarify=ClarifyPayload(reason=ClarifyReason.PARSE_FAILED),
        prompt_version=prompt_version, retries=retries, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# The parser
# ---------------------------------------------------------------------------

@dataclass
class ParserStats:
    """Parse-specific instrumentation for the exam sweep (CU5). Counts only —
    nothing here is read by a route."""
    calls: int = 0                 # model calls made (retries included)
    parses: int = 0                # questions parsed
    retries: int = 0               # questions that needed a second call
    malformed: int = 0             # emissions that did not validate (each attempt)
    clarifies: int = 0             # parses that emitted a clarify payload
    unavailable: int = 0           # parses attempted with no parser available
    latencies_ms: list[float] = field(default_factory=list)
    #: The first few malformed emissions, verbatim and truncated (Session 4A.5b).
    #: A `parse-failed` clarify says only THAT the parse could not commit; the
    #: sweep needs to see WHAT the model emitted before anyone can fix it. The 4A.5b
    #: sweep produced one such miss and could not diagnose it — instrument first,
    #: change the coercion rule only on evidence.
    malformed_samples: list[str] = field(default_factory=list)

    def median_latency_ms(self) -> Optional[float]:
        if not self.latencies_ms:
            return None
        xs = sorted(self.latencies_ms)
        mid = len(xs) // 2
        return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2

    def note_malformed(self, text: str, limit: int = 8) -> None:
        self.malformed += 1
        if len(self.malformed_samples) < limit:
            self.malformed_samples.append((text or "(empty)")[:400])

    def as_dict(self) -> dict:
        return {"calls": self.calls, "parses": self.parses, "retries": self.retries,
                "malformed": self.malformed, "clarifies": self.clarifies,
                "unavailable": self.unavailable,
                "median_latency_ms": self.median_latency_ms(),
                "malformed_samples": list(self.malformed_samples)}


class QuestionParser:
    """R-AI5(1) — the parse layer. One call, temperature 0, closed vocabulary.

    Construct with a client (a real Anthropic client or a test double exposing
    ``messages.create``). With no client and no key the parser is simply
    UNAVAILABLE: ``parse`` returns None and the ask path answers honestly that it
    could not interpret the question. There is no keyword fallback (R-AI5(2))."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001",
                 api_key: Optional[str] = None, _client: Any = None,
                 max_tokens: int = 600) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = _client
        self._max_tokens = max_tokens
        self._template, self.prompt_version = load_prompt()
        self.stats = ParserStats()
        self.available = False
        if _client is not None:
            self.available = True
        elif self._api_key:
            # Fail-closed construction: no package, bad key, any client-build
            # failure leaves the parser UNAVAILABLE, never a raise.
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self.available = True
            except Exception:  # noqa: BLE001 — construction must never raise
                self.available = False

    # -- the prompt ---------------------------------------------------------

    def prompt_for(self, question: str, context: Optional[dict]) -> str:
        return (self._template
                .replace("{INTENTS}", render_intents())
                .replace("{CONTEXT}", render_context(context))
                .replace("{QUESTION}", question or ""))

    # -- one parse ----------------------------------------------------------

    def _call(self, prompt: str) -> Optional[str]:
        try:
            resp = self._client.messages.create(
                model=self._model, max_tokens=self._max_tokens, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception:  # noqa: BLE001 — a model failure is never a crash
            return None

    def parse(self, question: str, *, explainer: Any,
              context: Optional[dict] = None) -> Optional[ParsedQuestion]:
        """Parse one question. Returns None ONLY when the parser is unavailable
        (no client) — every other failure yields a ParsedQuestion, clarifying
        rather than guessing."""
        if not self.available or self._client is None:
            self.stats.unavailable += 1
            return None
        prompt = self.prompt_for(question, context)
        started = time.perf_counter()
        parsed: Optional[ParsedQuestion] = None
        attempts = 0
        for attempt in range(2):          # one call, one retry on a malformed one
            attempts = attempt + 1
            self.stats.calls += 1
            text = self._call(prompt)
            emission = extract_json(text or "")
            if emission is not None:
                parsed = build_parsed(
                    question, emission, explainer, context,
                    prompt_version=self.prompt_version, retries=attempt)
                if parsed is not None:
                    break
            self.stats.note_malformed(text or "")
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.stats.parses += 1
        self.stats.latencies_ms.append(latency_ms)
        if attempts > 1:
            self.stats.retries += 1
        if parsed is None:
            parsed = clarify_parse_failed(
                question, prompt_version=self.prompt_version,
                retries=attempts - 1, latency_ms=latency_ms)
        else:
            parsed = parsed.model_copy(update={"latency_ms": latency_ms})
        if parsed.clarify is not None:
            self.stats.clarifies += 1
        return parsed
