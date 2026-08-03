"""Test doubles for the R-AI5 parse layer (Session 4A.5a).

The ask path is LLM-first: without a parser there is no interpretation at all
(R-AI5(2) leaves no keyword fallback to reach for). So a test that exercises
dispatch, assembly, rendering or the exam harness supplies a PARSER, the way it
supplies a fixture snapshot.

Two doubles, deliberately different in what they prove:

  ``FakeClient``     — stands in for the Anthropic client and returns canned JSON
                       text. Everything downstream is REAL: the governed prompt is
                       rendered, the emission is JSON-parsed, validated into the
                       contract, and its subjects are resolved against the run's
                       vocabulary. This is what the parser's own tests use.
  ``ScriptedParser`` — a table of question -> ParsedQuestion for tests whose subject
                       is the DISPATCH, not the parse. It states the parse a live
                       model is expected to produce; the live model's actual
                       agreement with it is the exam sweep's job (R-AI4(2): grading
                       conversation is Claude's and the founder's, not a metric's).

Nothing here is importable by ``src`` — a keyword table living in the product would
be the retired classifier wearing a different name.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from mre.contracts.parse import (
    ClarifyPayload,
    ClarifyReason,
    FollowupKind,
    Intent,
    ParsedQuestion,
    Polarity,
    SubjectKind,
    SubjectRef,
    SubjectSource,
)
from mre.modules.question_parser import QuestionParser, bind_subjects


# ---------------------------------------------------------------------------
# A fake Anthropic client: canned emission text in, real everything else.
# ---------------------------------------------------------------------------

class _Msg:
    def __init__(self, text: str) -> None:
        self.content = [type("B", (), {"text": text})()]


class FakeClient:
    """Returns the next canned response for each ``messages.create`` call."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kw) -> Any:  # noqa: ANN401 — mirrors the SDK's shape
        self.calls.append(kw)
        text = self._responses.pop(0) if self._responses else "{}"
        return _Msg(text)


def emission(intent: str, subjects: Optional[list[dict]] = None, *,
             polarity: Optional[str] = None, followup_of: str = "none",
             confidence: float = 0.9, nearest: Optional[list[str]] = None,
             clarify: Optional[dict] = None,
             move_direction: Optional[str] = None) -> str:
    """One model emission as strict JSON — the shape the governed prompt asks for.

    ``subjects`` entries may carry ``op_seq`` (prompt v17, the listening
    docket): the GRAIN of an order subject, which is where a named operation
    belongs — never as a subject of its own."""
    return json.dumps({
        "intent": intent, "subjects": subjects or [], "polarity": polarity,
        "followup_of": followup_of, "confidence": confidence,
        "nearest": nearest or [], "clarify": clarify,
        "move_direction": move_direction,
    })


def parser_with(responses: list[str]) -> QuestionParser:
    return QuestionParser(_client=FakeClient(responses))


# ---------------------------------------------------------------------------
# A scripted parser: the parse a live model is expected to produce.
# ---------------------------------------------------------------------------

def parsed(question: str, intent: Intent, *,
           orders: tuple = (), machines: tuple = (), customers: tuple = (),
           concepts: tuple = (), pointed: tuple = (), pointed_words: tuple = (),
           polarity: Optional[Polarity] = None,
           followup_of: FollowupKind = FollowupKind.NONE,
           confidence: float = 0.92, nearest: tuple = (),
           clarify: Optional[ClarifyReason] = None,
           clarify_detail: str = "",
           op_seq: Optional[int] = None,
           move_direction: Optional[Any] = None,
           move_target: str = "") -> ParsedQuestion:
    """Build a ParsedQuestion with subjects given as the planner's own words.

    ``pointed`` names the kinds the planner POINTED at rather than named ("this
    order"); those bind from the live context at dispatch time, so they are given
    here with no raw words. Refs are left UNRESOLVED — call ``resolve`` with an
    explainer + context to run the real binding."""
    subjects: list[SubjectRef] = []
    for kind, raws in ((SubjectKind.ORDER, orders), (SubjectKind.MACHINE, machines),
                       (SubjectKind.CUSTOMER, customers),
                       (SubjectKind.CONCEPT, concepts)):
        for raw in raws:
            # The GRAIN rides on the ORDER subject only (the listening docket,
            # Item 1) — an operation is not a subject of any other kind, and a
            # double that let one ride on a machine would be testing a shape
            # the contract forbids.
            subjects.append(SubjectRef(
                kind=kind, raw=raw,
                op_seq=op_seq if kind is SubjectKind.ORDER else None))
    for kind in pointed:
        subjects.append(SubjectRef(
            kind=kind, raw="", pointed=True,
            op_seq=op_seq if kind is SubjectKind.ORDER else None))
    # A pointed subject whose WORDS are in the sentence ("this order", "it") — the
    # dispatch substitutes the bound ref into the planner's own phrasing.
    for kind, raw in pointed_words:
        subjects.append(SubjectRef(kind=kind, raw=raw, pointed=True))
    return ParsedQuestion(
        question=question, intent=intent, subjects=subjects, polarity=polarity,
        followup_of=followup_of, confidence=confidence, nearest=list(nearest),
        clarify=ClarifyPayload(reason=clarify, detail=clarify_detail)
        if clarify else None,
        move_direction=move_direction, move_target=move_target,
        prompt_version="test")


def resolve(p: ParsedQuestion, explainer: Any,
            context: Optional[dict] = None, rolling: Any = None) -> ParsedQuestion:
    """Run the REAL subject binding over a scripted parse — the same code the live
    parser uses, so a scripted test still proves resolution end to end."""
    raw = [{"kind": s.kind.value, "raw": s.raw, "from_context": s.pointed,
            "op_seq": s.op_seq}
           for s in p.subjects]
    return p.model_copy(update={
        "subjects": bind_subjects(explainer, raw, context, rolling=rolling)})


class ScriptedParser:
    """A question -> ParsedQuestion table. Unlisted questions parse as UNMATCHED
    (the honest destination), never as a keyword guess."""

    available = True

    def __init__(self, table: dict[str, ParsedQuestion],
                 *, default_nearest: tuple = ()) -> None:
        self._table = {k.strip().lower(): v for k, v in table.items()}
        self._default_nearest = list(default_nearest)
        self.calls = 0
        self.asked: list[str] = []

    def parse(self, question: str, *, explainer: Any,
              context: Optional[dict] = None,
              rolling: Any = None) -> ParsedQuestion:
        # ``rolling`` (Session 4A.5c CU4) is the sliced world's order vocabulary.
        # The double accepts it and resolves through it, so a test whose subject is
        # the DISPATCH of a tray order gets a real BEYOND-HORIZON disposition
        # rather than a scripted one — the disposition is resolution, and
        # resolution stays real in the doubles by design.
        self.calls += 1
        self.asked.append(question)
        hit = self._table.get((question or "").strip().lower())
        if hit is None:
            return ParsedQuestion(question=question, intent=Intent.UNMATCHED,
                                  confidence=0.1, nearest=self._default_nearest,
                                  prompt_version="test")
        return resolve(hit.model_copy(update={"question": question}),
                       explainer, context, rolling=rolling)


# ---------------------------------------------------------------------------
# Session 4A.5b — the SYNTHESIS doubles (R-AI5(2)).
#
# Same discipline as the parse doubles: the double supplies the model's EMISSIONS,
# and everything downstream is real — the governed prompt is rendered, the tools
# actually read the pinned run, and the verifier actually re-fetches. What a test
# never gets to fake is the verdict.
# ---------------------------------------------------------------------------

def tool_call(tool: str, **args) -> str:
    """One loop step that calls a tool."""
    return json.dumps({"tool": tool, "args": args})


def claims(*items: dict) -> str:
    """One loop step that answers with claims. Each item is
    ``{"text": ..., "record_ids": [...], "kind": "fact"|"conclusion"}``."""
    return json.dumps({"claims": list(items)})


def claim(text: str, record_ids: Optional[list] = None,
          kind: str = "fact") -> dict:
    return {"text": text, "record_ids": list(record_ids or []), "kind": kind}


def cannot_answer(reason: str) -> str:
    return json.dumps({"cannot_answer": reason})


def synthesizer_with(responses: list[str], **kw) -> Any:
    """A ``Synthesizer`` whose model emissions are canned; tools and verification
    are the real ones."""
    from mre.modules.synthesizer import Synthesizer
    return Synthesizer(_client=FakeClient(responses), **kw)


class DeadSynthesizer:
    """A synthesizer that exists but is UNAVAILABLE — proves the honest floor under
    the second tier (part 1's bridge), never a keyword guess."""

    available = False

    def synthesize(self, *a, **kw) -> None:  # pragma: no cover - never called
        raise AssertionError("an unavailable synthesizer must never be called")


def assemble(explainer: Any, route: str, question: str, **params) -> Any:
    """Assemble a bundle by NAMING its route — the assembler tests' entry point.

    ``Explainer.answer(question)`` is gone with the classifier it wrapped (R-AI5(2)).
    These tests were never about routing anyway: they pin what an assembler builds
    and how it renders. Naming the route makes that explicit, and the question text
    is still passed because assemblers legitimately read it for their own details (a
    date filter, a customer name, a swap-vs-move framing). This is not a classifier:
    each call site states its own route; nothing here maps words to routes."""
    return explainer.route(route, {"question": question, **params})


__all__ = [
    "assemble", "cannot_answer", "claim", "claims",
    "ClarifyReason", "DeadSynthesizer", "FakeClient", "FollowupKind", "Intent",
    "ParsedQuestion", "Polarity", "ScriptedParser", "SubjectKind", "SubjectSource",
    "emission", "parsed", "parser_with", "resolve", "synthesizer_with", "tool_call",
]
