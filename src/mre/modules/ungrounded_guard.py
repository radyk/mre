"""THE ZERO-TOOL-CALL GUARD (Errand 4B.15a, rider).

THE SPECIMEN. 4B.15's model-tier bench asked each tier "which machine is carrying
the most work in this window". Opus answered with three machine names that do not
exist in this plant, having made ZERO tool calls. Claim verification did its job —
every sentence was labelled unsupported — and the answer SHIPPED, because the
synthesis tier's contract is to LABEL what it grounds, not to withhold what it
cannot. On a capability claim, labelling is not sufficient; on a fabricated
machine roster it is not sufficient either. A planner reads three names and goes
looking for them.

THE RULE, and it is narrow on purpose:

  * the answer came from the SYNTHESIS tier (a contracted route reads evidence by
    construction; the honest floors state no facts),
  * the tier made ZERO tool calls AND cited no record that RESOLVES — it read
    nothing through either channel, and
  * a delivered CLAIM names something specific to THIS WORLD that the planner did
    not put there themselves.

The resolved-record clause is what makes the second one dodge-resistant. A model
that invents record ids alongside its invented machines gains nothing: the bundle
carries only the ids that resolved against the real evidence index (the assembler
drops the rest), so a fabricated citation is an empty list, not a free pass.

The third clause is what makes the guard safe. A token the planner supplied is
not a claim about the world — an answer echoing "ORD-000013" back at the person
who typed it invented nothing. Only tokens the tier INTRODUCED count, which is
exactly what fabrication looks like and exactly what a legitimate no-tools answer
("I can't forecast the weather") does not do.

NO MODEL JUDGMENT ANYWHERE. Two regexes, a set difference and a count. The tier's
own beliefs about its citations are input to verification, never the label
(R-AI5(8)); this holds the same line one step further out — the tier's belief
that it did not need to read anything is not the test either.

FAILS OPEN, like every other guard at this seam: a missing field or an odd shape
yields "nothing applies" and the answer is delivered untouched. A guard that can
break an answer path is worse than the defect it guards.
"""
from __future__ import annotations

import re
from typing import Any, Optional

#: An identifier shaped like this plant's entities: ORD-000013, CUT-01, PAINT-01,
#: M-02, WP-1174. Upper-case stem, hyphen, digits.
_ENTITY = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")

#: Figures that are only meaningful AS FACTS ABOUT THIS PLAN: a currency amount,
#: an ISO date, a clock time. A bare integer is deliberately NOT here — "one of
#: two ways" is not a claim about the schedule, and the guard must not fire on
#: prose that happens to count something.
_FIGURE = re.compile(r"\$\s?\d|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b")

_FOOTER = "\n[rendered by:"


def _tokens(text: str) -> set[str]:
    """The world-specific tokens a piece of text asserts."""
    out = {m.group(0).upper() for m in _ENTITY.finditer(text or "")}
    out |= {m.group(0) for m in _FIGURE.finditer(text or "")}
    return out


def _claim_texts(kf: dict) -> list[str]:
    """Only the claims that actually REACH the planner. A cut claim was already
    removed by the verifier and never rendered, so it cannot mislead anyone."""
    out: list[str] = []
    for claim in kf.get("claims") or []:
        if isinstance(claim, dict):
            text = str(claim.get("text") or "")
            if text.strip():
                out.append(text)
    return out


def unread_claims(bundle: Any) -> list[str]:
    """The world-specific tokens this answer INTRODUCED without reading anything.

    Empty for every answer that is not a zero-tool-call synthesis answer, and for
    a zero-tool-call answer whose specifics all came from the planner's own
    question. Non-empty means the answer must not ship."""
    if getattr(bundle, "subject_type", "") != "synthesis":
        return []
    kf = getattr(bundle, "key_facts", None)
    if not isinstance(kf, dict):
        return []
    # `tool_call_count` is the length of the tier's own recorded call list, set by
    # the assembler from the SynthesisAnswer. Absent ⇒ an older bundle shape ⇒
    # fail open.
    count = kf.get("tool_call_count")
    if not isinstance(count, int) or count > 0:
        return []
    # The other read channel: a citation that RESOLVED to a real evidence record.
    # Anything here means something was genuinely read, whatever the call count
    # says. Fabricated ids never land here — they resolve to nothing.
    if getattr(bundle, "ordered_records", None):
        return []
    claims = _claim_texts(kf)
    if not claims:
        # The honest floor states nothing. Nothing to withhold.
        return []
    asked = str(kf.get("asked_question") or getattr(bundle, "question", "") or "")
    supplied = _tokens(asked)
    introduced: list[str] = []
    for token in sorted(_tokens(" \n".join(claims))):
        if token not in supplied and token.upper() not in supplied:
            introduced.append(token)
    return introduced


def apply_unread_guard(bundle: Any, text: str) -> Optional[str]:
    """The delivered text → the withholding floor, or None when nothing applies.

    The rendered-by footer is PRESERVED verbatim: it already reads
    "0 tool call(s)", which is the evidence for the guard's own verdict, and the
    register stays `synthesis` because that is still which tier answered."""
    if not unread_claims(bundle):
        return None
    from mre.modules.ask_fallback_copy import SYNTHESIS_UNREAD
    footer = ""
    if _FOOTER in (text or ""):
        footer = text[text.index(_FOOTER):]
    return SYNTHESIS_UNREAD + footer
