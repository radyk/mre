"""The mechanical pre-triage sidecar (Session 4A.3b, CU3).

Everything checkable about an answer WITHOUT judgment. The sidecar seeds Claude's
triage (RUBRIC.md); it never grades conversation (R-AI4(2)). Each check is a pure
function over a finished ``TurnRecord`` plus a ``Vocab`` view of the pinned world,
and returns zero or more ``Finding``s.

The six mechanical signals (verbatim from the session brief):
  1. the ask path itself raised / timed out               (kind ``exception``)
  2. an empty answer body                                   (kind ``empty``)
  3. an LLM testimony that failed validation                (kind ``validator``)
  4. an interpreted-as entity absent from the document      (kind ``absent-entity``)
  5. a route citing zero records where its shape needs them (kind ``dark-evidence``)
  6. an invitation proposing a route that does not exist    (kind ``dead-door``)

Signals 1-3 are truth-floor tripwires (R-AI4(1)); 4-6 are shape checks that a human
still reads. None of them is a verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Finding:
    kind: str
    lineno: int
    question: str
    detail: str


# Routes whose ANSWER shape is testimony over evidence — it should light at least
# one bar/lane (a non-empty ``cited_refs``). A dark evidence channel here is the
# regression the founder would see as "the answer doesn't point at anything". This
# is a heuristic SEED for triage, not a grade: header-only routes (findings,
# briefing, swap_move, gap_between, machine_idle, coaching, …) compose their whole
# answer in prose and are deliberately excluded.
EVIDENCE_ROUTES = frozenset({
    "late-order", "why-on-machine", "order-schedule", "machine-schedule",
    "start-reason",
})


class Vocab:
    """A read-only view of the pinned world for the sidecar's shape checks — the
    valid entity vocabulary + a classifier for the real-doors reverse-guard.

    Built from a throwaway Explainer over the same snapshot the answers run
    against, so 'present in the document' means exactly what the ask path means."""

    def __init__(self, explainer: Any) -> None:
        self._ex = explainer
        self.order_refs = set((explainer._order_refs or {}).values())
        self.machine_refs = set((explainer._machine_refs or {}).values())
        self.excluded = set(getattr(explainer, "_excluded_labels", set()) or set())
        self._order_shapes = list(getattr(explainer, "_order_shape_patterns", []) or [])
        # A loaded snapshot yields a non-empty entity vocabulary. An EMPTY one means
        # the snapshot did not load (a wiped/missing run dir), and the Explainer has
        # fallen to certificate-only mode — every entity question then silently
        # misroutes. The runner reads this to refuse to run against a dead target
        # rather than emit a transcript full of garbage.
        self.healthy = bool(self.order_refs or self.machine_refs)

    def classify_route(self, question: str) -> str:
        try:
            rid, _ = self._ex.classify(question)
            return rid
        except Exception:  # noqa: BLE001 — a classifier raise is itself a finding
            return "unsupported"

    def absent_order_tokens(self, text: str) -> list[str]:
        """Order-SHAPED tokens in ``text`` that resolve to no scheduled demand and
        are not a known excluded label — a resolution to an order that isn't here.

        An excluded order (a real order the gate dropped) is NOT flagged: answering
        about it is legitimate (the excluded-orders route). We flag only tokens that
        look like this dataset's orders yet name nothing in it."""
        out: list[str] = []
        for tok in re.findall(r"[A-Za-z][\w./-]*\d[\w./-]*|[A-Za-z]+-\d[\w-]*", text or ""):
            u = tok.upper().strip(".,?!")
            if u in self.order_refs or u in self.machine_refs or u in self.excluded:
                continue
            if any(p.match(u) for p in self._order_shapes) and u not in out:
                out.append(u)
        return out


# An offered follow-up in an invitation / near-miss is phrased  Ask "<question>".
_OFFERED_QUESTION = re.compile(r'Ask\s+"([^"]+)"')


def offered_questions(answer: str) -> list[str]:
    """Every follow-up question an answer offers the planner (the invitation /
    near-miss surface). The real-doors guard classifies each one."""
    return [m.group(1).strip() for m in _OFFERED_QUESTION.finditer(answer or "")]


def _answer_body(answer: str) -> str:
    """The answer with its ``[rendered by: … | register: …]`` footer stripped, for
    the empty-body check."""
    lines = [ln for ln in (answer or "").splitlines()
             if not ln.strip().startswith("[rendered by:")
             and not ln.strip().startswith("[LLM validation failed")]
    return "\n".join(lines).strip()


def check_turn(turn: Any, vocab: Vocab) -> list[Finding]:
    """All mechanical findings for one finished turn."""
    findings: list[Finding] = []
    q = turn.question

    # 1 — the ask path itself failed.
    if turn.error:
        findings.append(Finding("exception", turn.lineno, q, turn.error))
        return findings  # nothing else is meaningful on a crashed turn

    # 2 — an empty answer body (the footer alone is not an answer).
    if not _answer_body(turn.answer):
        findings.append(Finding("empty", turn.lineno, q, "answer body is empty"))

    # 3 — an LLM testimony that failed validation and fell back / warned.
    if "LLM validation failed" in (turn.answer or "") or turn.renderer.startswith(
            "template (LLM validated)"):
        findings.append(Finding(
            "validator", turn.lineno, q,
            "LLM testimony failed validation; fell back to template"))

    # 4 — an interpreted-as entity absent from the pinned document.
    for tok in vocab.absent_order_tokens(turn.resolved_question):
        findings.append(Finding(
            "absent-entity", turn.lineno, q,
            f"interpreted-as names '{tok}', absent from the pinned document"))

    # 5 — an evidence-shaped route that cited nothing (a dark lit-bars channel).
    if turn.route in EVIDENCE_ROUTES and turn.lit_bars == 0 and turn.record_count == 0:
        findings.append(Finding(
            "dark-evidence", turn.lineno, q,
            f"route '{turn.route}' cited 0 records and lit 0 bars"))

    # 6 — an invitation offering a door into a wall.
    for offered in offered_questions(turn.answer):
        if vocab.classify_route(offered) == "unsupported":
            findings.append(Finding(
                "dead-door", turn.lineno, q,
                f'offered follow-up "{offered}" classifies to no route'))

    return findings
