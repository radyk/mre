"""The AI exam harness (Session 4A.3b, R-AI4).

Evaluation of the conversational layer at machine speed. The exam FIRES question
scripts through the real ask path — interpreter, explainer, renderer, validator,
LLM when a key is present — against a pinned persisted run, and emits a plain-ASCII
transcript (the founder's paste format) plus a mechanical findings sidecar.

The harness discovers; it does not grade conversation. Per R-AI4(2), grading is
Claude's (against ``tests/ai_exam/RUBRIC.md``) and the founder's — never a metric's.
The sidecar carries only what is checkable WITHOUT judgment (validator failures,
empty/exception answers, an interpreted-as entity absent from the pinned document, a
route citing nothing where its shape requires evidence, an invitation proposing a
route that does not exist).
"""
from __future__ import annotations

from .script import ScriptItem, Question, Select, Reset, parse_script
from .runner import ExamRunner, RunTarget, TurnRecord, Finding, ExamResult

__all__ = [
    "ScriptItem", "Question", "Select", "Reset", "parse_script",
    "ExamRunner", "RunTarget", "TurnRecord", "Finding", "ExamResult",
]
