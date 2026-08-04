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
    ContestedClaim,
    FollowupKind,
    Intent,
    INTENT_MEANINGS,
    model_selectable_intents,
    MoveDirection,
    ParsedQuestion,
    Polarity,
    SubjectDisposition,
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
    the honest result was a near-miss bridge instead of the machine's schedule.

    Session 4A.5c: the list is ``model_selectable_intents()``, not the constant, so
    a DEMOTED promotion (R-AI5(7)) actually disappears from the prompt. That is the
    whole demotion mechanism — the model can only ever name an id it was shown.
    """
    from mre.modules.explainer import ROUTE_TAXONOMY
    lines = []
    for i in model_selectable_intents():
        needs = ROUTE_TAXONOMY.get(i.value, {}).get("params", [])
        suffix = f"  [needs a named {' + '.join(needs)}]" if needs else ""
        lines.append(f"  {i.value} — {INTENT_MEANINGS[i]}{suffix}")
    return "\n".join(lines)


def describe_card(card: Optional[dict]) -> str:
    """The OPEN DELTA CARD, in one line, for the parse's context block.

    Session 4B.5 CU2. What the model needs is WHETHER a priced move is on screen
    and WHAT it is about — never the figures. Handing it the numbers would invite
    it to answer from them, and the parse never answers (R-AI5(1)); the route
    reads the card itself. So: presence, the order, the machine, and nothing
    else."""
    if not card or not card.get("open"):
        return "none — no priced move is showing."
    order = (card.get("order") or "").strip()
    machine = (card.get("machine") or "").strip()
    where = f" onto {machine}" if machine else ""
    what = f" of {order}" if order else ""
    return (f"a priced move{what}{where} is showing on the board right now "
            f"(the planner can see its cost, the orders it affects, and what "
            f"else moved).")


def render_calendar(document: Optional[dict]) -> str:
    """THE CALENDAR ANCHOR (Session 4B.15 Item 0). Nothing told the model what
    day it was.

    THE MEASURED FAILURE: asked about "Tuesday" on a five-week horizon holding
    several Tuesdays, synthesis described PAINT-01 running 07:00-11:24 — a real,
    contiguous occupancy on Tuesday Jan 6, the FIRST Tuesday in the data — while
    the conversation was about Tuesday Jan 13, on which PAINT-01 carries no work
    at all. A true fact about the wrong day, in the same session whose blocker
    analysis reasoned correctly about Jan 13 because it computes with dates
    rather than reading a weekday off a row.

    Two lines. They do not resolve the ambiguity — the model cannot know which
    Tuesday was meant — but they make it VISIBLE, which is what rule 10 needs to
    be followable."""
    if not document:
        return ""
    ref = (document.get("reference_date") or "")[:10]
    horizon = document.get("horizon") or {}
    start, end = (horizon.get("start") or "")[:10], (horizon.get("end") or "")[:10]
    if not ref and not start:
        return ""
    bits = []
    if ref:
        try:
            from datetime import datetime
            day = datetime.fromisoformat(ref).strftime("%A")
            bits.append(f"  PLAN REFERENCE DATE: {ref} (a {day})")
        except Exception:  # noqa: BLE001 — a bad date simply prints as itself
            bits.append(f"  PLAN REFERENCE DATE: {ref}")
    if start and end:
        bits.append(f"  HORIZON: {start} to {end} — a bare weekday name is "
                    "AMBIGUOUS over this span; resolve it or say which you "
                    "assumed")
    return "\n".join(bits)


def render_context(context: Optional[dict]) -> str:
    """The conversation context the parse reads (R-AI5(1)): the live board
    selection, the last answered subject, and the recent turns — exactly the three
    channels the cockpit panel transmits, never more.

    Since 4B.15 it also carries the CALENDAR ANCHOR when the caller supplies the
    document, for the reason in :func:`render_calendar`."""
    context = context or {}
    selection = context.get("selection") or {}
    last = context.get("last_answered_subject") or {}
    history = context.get("history") or []

    def _pair(d: dict) -> str:
        bits = [f"{k}={v}" for k in ("order", "machine") if (v := d.get(k))]
        return " ".join(bits) if bits else "none"

    lines = [f"  OPEN DELTA CARD: {describe_card(context.get('card'))}",
             f"  BOARD SELECTION (what is highlighted right now): {_pair(selection)}",
             f"  SUBJECT OF THE PREVIOUS ANSWER: {_pair(last)}"]
    calendar = render_calendar(context.get("document"))
    if calendar:
        lines.append(calendar)
    # Session 4A.5c CU3(c) rider — the SCOPE NOTE, present only on a question the
    # ADJACENT-MATCH GUARD diverted. It never appears in a parse's context (the
    # dispatch adds it after the parse), so this line is a synthesis-only channel
    # even though both prompts render this block.
    dropped = (context.get("dropped_qualifier") or "").strip()
    if dropped:
        from mre.modules.ask_fallback_copy import SYNTHESIS_SCOPE_NOTE
        lines.append(SYNTHESIS_SCOPE_NOTE.format(qualifier=dropped[:80]))
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
_DISPOSITION_BY_NAME = {d.value: d for d in SubjectDisposition}


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
    cockpit's channels imply: the OPEN DELTA CARD > live board selection > the
    subject of the previous answer > conversation history. Typed — "that machine"
    never binds to an order (the founder's confident-wrong bug). None when nothing
    of that type is live.

    Session 4B.5 CU2 puts the CARD at the top of the ladder, and the reason is
    that the card is the narrowest channel there is. A selection persists after
    the planner has stopped thinking about it; a card is open because a move is
    being weighed right now, and it closes the moment that stops being true. When
    both are live they usually agree — but where they differ, "this" means the
    thing that is being decided."""
    key = kind.value
    if key not in ("order", "machine"):
        return None, SubjectSource.UTTERANCE
    card = context.get("card") or {}
    if card.get("open") and card.get(key):
        return card[key], SubjectSource.CARD
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
                  context: Optional[dict], rolling: Any = None) -> list[SubjectRef]:
    """The model's typed subject WORDS → resolved ``SubjectRef``s.

    A subject the planner POINTED at (``from_context``) binds from the live
    channels; a subject the planner NAMED resolves against this run's vocabulary.
    An unresolvable subject is returned UNRESOLVED (``ref=None``) — the dispatch
    then answers honestly (absent entity / clarify), never globally.

    Session 4A.5c CU4 — ``rolling`` is the sliced world's ``RollingVocabulary``,
    and it is the prerequisite that let the rolling keyword matcher die. The
    Explainer's snapshot on a rolling run is WINDOW 0 ONLY, so an order in the
    beyond-horizon tray resolved to nothing and was answered as absent. Now: a
    name the window does not carry is tried against the document's three regions,
    and every resolved order gets a DISPOSITION. A tray order is a real subject
    that is BEYOND-HORIZON — never "not in this schedule"."""
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
        # The sliced world, second: the window's vocabulary is authoritative for
        # what it carries, and the document answers for everything else.
        disposition = None
        if kind is SubjectKind.ORDER and rolling:
            if ref is None and raw:
                ref = rolling.resolve(raw)
            disposition = _DISPOSITION_BY_NAME.get(rolling.disposition(ref) or "")
        out.append(SubjectRef(kind=kind, raw=raw, ref=ref, source=source,
                              pointed=pointed, disposition=disposition,
                              op_seq=_coerce_op_seq(raw_subject.get("op_seq"))))
    return out


def _coerce_op_seq(value: Any) -> Optional[int]:
    """The model's operation grain -> an int, or None.

    Fail-closed and silent: a grain we cannot read is a grain the answer will
    disclose it did not have, which is strictly better than a route scoped to
    a number nobody typed. "op30", 30, "30" and 30.0 all read as 30; anything
    else — including a negative, which no `op_seq` ever is — reads as None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        value = digits or None
    try:
        seq = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return seq if seq >= 0 else None


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
    """An emitted id -> a live Intent, or None (not a member of the vocabulary)."""
    try:
        intent = Intent(str(value))
    except ValueError:
        return None
    return None if intent is Intent.UNKNOWN_ENTITY else intent


def _is_demoted(value: Any) -> bool:
    """True when the emission names a REAL intent that is not currently LIVE.

    Session 4A.5c (R-AI5(7)): a DEMOTED intent is dropped from the prompt by
    ``model_selectable_intents()``, so the model should never name it — but a model
    that saw the id earlier in the same conversation might, and a demotion a stale
    phrasing can walk around is not a demotion.

    It is handled as a MISFILING, not as garbage, on exactly the 4A.5b precedent
    (`prove-it` in the intent field): discarding a recognizable emission twice and
    then clarifying is not strictness, it is waste. The intent becomes `unmatched`
    — which is the second tier, which is precisely where a demotion is supposed to
    put the shape."""
    try:
        intent = Intent(str(value))
    except ValueError:
        return False
    return intent not in model_selectable_intents()


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
                 retries: int = 0, latency_ms: Optional[float] = None,
                 rolling: Any = None) -> Optional[ParsedQuestion]:
    """A validated emission dict → ``ParsedQuestion``. None when the emission does
    not name a member of the closed vocabulary (the caller retries, then clarifies).
    """
    raw_intent = emission.get("intent")
    intent = _coerce_intent(raw_intent)
    if intent is not None and _is_demoted(raw_intent):
        # A DEMOTED promotion (R-AI5(7)) is a known id that is no longer live.
        # `unmatched` IS the demotion's destination — the second tier.
        intent = Intent.UNMATCHED
    if intent is None:
        if not _names_a_followup(raw_intent):
            return None
        intent = Intent.UNMATCHED
    subjects = bind_subjects(explainer, emission.get("subjects") or [], context,
                             rolling=rolling)

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
               if i is not None and i is not Intent.UNMATCHED
               and not _is_demoted(i.value)]

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

    # Session 4A.5c CU3(c) — the adjacent-match guard's INPUT. The model reports a
    # qualifier the planner stated that the named intent does not honour; it never
    # decides what to do about it (the dispatch does). Truncated hard: this is a
    # phrase, and a model that starts explaining itself here is emitting prose into
    # a routing contract.
    dropped = str(emission.get("dropped_qualifier") or "").strip()[:80]
    # An `unmatched` parse has no route to drop a qualifier FROM, so the field is
    # meaningless there and is cleared rather than carried into telemetry as noise.
    if intent is Intent.UNMATCHED:
        dropped = ""

    # Session 4B.14 Item 3 — WHICH claim a contest disputes, and whether the turn
    # is a contest at all. Carried on the two intents that can ANSWER one:
    # `contested-fact`, and `why-here` — because a challenge to the system's
    # reasoning usually names the right route by itself ("it seems it should be
    # able to start on tuesday" IS a blocker question) and would otherwise lose
    # the fact that someone pushed back. On every other intent it is meaningless
    # and a stray value would be a routing signal the prompt never promised. An
    # unreadable or absent value stays None, which the assemblers read as the
    # behaviour before this field existed, so no older parse becomes
    # unanswerable by upgrading.
    contested_claim = None
    if intent in (Intent.CONTESTED_FACT, Intent.WHY_HERE):
        raw_cc = emission.get("contested_claim")
        if raw_cc not in (None, "", "null"):
            try:
                contested_claim = ContestedClaim(str(raw_cc))
            except ValueError:
                contested_claim = None

    # Session 4B.30 Item 1/2 — WHICH WAY, and the planner's raw words for WHERE.
    # Carried on the two intents that can ACT on a direction, for the same reason
    # `contested_claim` is carried on two: on every other intent the field is
    # meaningless, and a stray value would be a routing signal the prompt never
    # promised. Absent stays None, which every assembler reads as EARLIER — the
    # behaviour before these fields existed.
    #
    # `move_target` is TRUNCATED and never interpreted here. It is the planner's
    # own words; a model that starts resolving them is authoring a date, and
    # 4B.15 Item 0 is the measured cost of an authored date (a true fact about
    # the wrong Tuesday, in a horizon with five of them).
    move_direction = None
    move_target = ""
    if intent in (Intent.WHAT_WOULD_CHANGE, Intent.SWAP_MOVE):
        raw_md = emission.get("move_direction")
        if raw_md not in (None, "", "null"):
            try:
                move_direction = MoveDirection(str(raw_md))
            except ValueError:
                move_direction = None
        move_target = str(emission.get("move_target") or "").strip()[:80]

    try:
        return ParsedQuestion(
            question=question, intent=intent, subjects=subjects,
            polarity=polarity, followup_of=followup, confidence=confidence,
            nearest=nearest, clarify=clarify, dropped_qualifier=dropped,
            contested_claim=contested_claim,
            move_direction=move_direction, move_target=move_target,
            prompt_version=prompt_version,
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


def parse_unreachable(question: str, *, prompt_version: str = "",
                      retries: int = 0,
                      latency_ms: Optional[float] = None) -> ParsedQuestion:
    """THE OTHER FLOOR (micro-session 4A): the model could not be REACHED, so the
    question was never read.

    Deliberately not `clarify_parse_failed`. That one means a model answered and
    we could not make a parse out of what it said — a fact about the emission.
    This one means nothing was asked of anything, and the only honest thing the
    surface can say is so."""
    return ParsedQuestion(
        question=question, intent=Intent.UNMATCHED, confidence=0.0,
        clarify=ClarifyPayload(reason=ClarifyReason.MODEL_UNREACHABLE),
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
    unreachable: int = 0           # parses whose model call could not be reached
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
                "unavailable": self.unavailable, "unreachable": self.unreachable,
                "median_latency_ms": self.median_latency_ms(),
                "malformed_samples": list(self.malformed_samples)}


class QuestionParser:
    """R-AI5(1) — the parse layer. One call, temperature 0, closed vocabulary.

    Construct with a client (a real Anthropic client or a test double exposing
    ``messages.create``). With no client and no key the parser is simply
    UNAVAILABLE: ``parse`` returns None and the ask path answers honestly that it
    could not interpret the question. There is no keyword fallback (R-AI5(2))."""

    def __init__(self, model: Optional[str] = None,
                 api_key: Optional[str] = None, _client: Any = None,
                 max_tokens: int = 600) -> None:
        # Errand 4B.15a — the DEFAULT lives in `llm_compat`, which is also where
        # the synthesis tier's lives, deliberately as a SEPARATE constant. The
        # parse stays on Haiku: 4B.15's bench moved the SECOND tier, not this
        # one, and a shared constant that moved both would erase the split the
        # measurement actually recommends.
        from mre.modules.llm_compat import parse_model
        self._model = model or parse_model()
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

    def _call(self, prompt: str) -> Any:
        # Session 4B.15 Item 6 — the request fields are MODEL-DEPENDENT.
        # `temperature=0` is right on Haiku and a 400 on Claude Opus 5 and
        # Sonnet 5, which removed the sampling parameters. Hardcoding it made
        # the two candidate tiers untestable: every request failed at the
        # transport, before any answer existed to grade.
        #
        # Micro-session 4A: the OUTCOME, not just the text. A parse that never
        # reached a model must not be answered with a sentence about tools.
        from mre.modules.llm_compat import call_text_outcome
        return call_text_outcome(self._client, self._model, self._max_tokens,
                                 [{"role": "user", "content": prompt}])

    def parse(self, question: str, *, explainer: Any,
              context: Optional[dict] = None,
              rolling: Any = None) -> Optional[ParsedQuestion]:
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
        unreachable = False
        for attempt in range(2):          # one call, one retry on a malformed one
            attempts = attempt + 1
            self.stats.calls += 1
            outcome = self._call(prompt)
            # Micro-session 4A — AN OUTAGE IS NOT RETRIED AND IS NOT MALFORMED.
            # The retry above exists for a model that answered badly; a model
            # that could not be reached will not be reached better by asking
            # twice, and counting it as a malformed emission would file an
            # infrastructure failure as a quality one. Break, and say so.
            if outcome.unreachable:
                unreachable = True
                break
            text = outcome.text
            emission = extract_json(text or "")
            if emission is not None:
                parsed = build_parsed(
                    question, emission, explainer, context,
                    prompt_version=self.prompt_version, retries=attempt,
                    rolling=rolling)
                if parsed is not None:
                    break
            self.stats.note_malformed(text or "")
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.stats.parses += 1
        self.stats.latencies_ms.append(latency_ms)
        if attempts > 1:
            self.stats.retries += 1
        if unreachable:
            self.stats.unreachable += 1
            parsed = parse_unreachable(
                question, prompt_version=self.prompt_version,
                retries=attempts - 1, latency_ms=latency_ms)
        elif parsed is None:
            parsed = clarify_parse_failed(
                question, prompt_version=self.prompt_version,
                retries=attempts - 1, latency_ms=latency_ms)
        else:
            parsed = parsed.model_copy(update={"latency_ms": latency_ms})
        if parsed.clarify is not None:
            self.stats.clarifies += 1
        return parsed
