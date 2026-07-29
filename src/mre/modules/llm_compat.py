"""MODEL-TIER COMPATIBILITY FOR THE TWO GOVERNED CALL SITES (Session 4B.15 Item 6).

THE MEASURED BLOCKER. The ask path pins ``claude-haiku-4-5`` in both the parse
layer and the synthesis tier, and both send ``temperature=0`` — the right thing
on Haiku, and a **400 on Claude Opus 5 and Claude Sonnet 5**, which removed the
sampling parameters entirely. So the tier question ("should synthesis run on a
bigger model?") could not even be MEASURED without this: every request to the
two candidate tiers failed at the transport, before any answer was produced.

That is worth stating plainly because it is the kind of thing a tier decision
quietly assumes away. The measurement is only meaningful if the call succeeds.

WHAT THIS IS. Two functions and one rule: send a sampling parameter only where
the model accepts one, and never let a model-family list going stale break the
ask path. The declared list is the fast path; :func:`call_text` carries a
retry-once-without-sampling fallback so a model released after this file was
written degrades to a working call rather than a hard failure.

DETERMINISM, HONESTLY STATED. ``temperature=0`` never guaranteed identical
outputs, and on a model that rejects it there is no equivalent knob at all — the
depth control is ``output_config.effort``. Nothing in this repo's determinism
rules is weakened by that: those rules govern the SOLVER (CP-SAT workers, seed,
PYTHONHASHSEED), which is a separate machine entirely. No golden, no schedule
and no cost figure depends on a model call.
"""
from __future__ import annotations

import re
from typing import Any, Optional

#: Model families that REJECT `temperature` / `top_p` / `top_k` outright.
#: Claude Opus 4.7 removed them; Opus 4.8, Opus 5, Sonnet 5 and Fable 5 keep
#: them removed. Matched on a prefix so an alias and a dated snapshot of the
#: same family both resolve.
_NO_SAMPLING = (
    re.compile(r"^claude-opus-(?:5|4-7|4-8)"),
    re.compile(r"^claude-sonnet-5"),
    re.compile(r"^claude-(?:fable|mythos)-5"),
)

#: Families where THINKING IS ON BY DEFAULT. `max_tokens` caps thinking PLUS
#: response text, so a budget sized for text alone truncates mid-answer. The
#: two call sites here want a short structured emission, not reasoning, so they
#: disable thinking — permitted on Opus 5 only at effort `high` or below, which
#: is the default and which neither call site raises.
_THINKS_BY_DEFAULT = (
    re.compile(r"^claude-opus-5"),
    re.compile(r"^claude-sonnet-5"),
    re.compile(r"^claude-(?:fable|mythos)-5"),
)


def _matches(model: str, patterns) -> bool:
    m = (model or "").strip()
    return any(p.match(m) for p in patterns)


def accepts_sampling(model: str) -> bool:
    """False when sending `temperature` to this model returns a 400."""
    return not _matches(model, _NO_SAMPLING)


def thinks_by_default(model: str) -> bool:
    return _matches(model, _THINKS_BY_DEFAULT)


def request_kwargs(model: str) -> dict:
    """The model-dependent request fields for a SHORT, STRUCTURED emission.

    Both governed call sites want one JSON object back, not reasoning: the
    parse emits a closed contract and the synthesis loop emits one tool call or
    one claim list per step. On a thinking-by-default model that means
    disabling thinking, or `max_tokens` is spent on reasoning the caller
    discards and the emission truncates."""
    if accepts_sampling(model):
        return {"temperature": 0}
    if thinks_by_default(model):
        return {"thinking": {"type": "disabled"}}
    return {}


def call_text(client: Any, model: str, max_tokens: int,
              messages: list[dict], system: Optional[str] = None) -> Optional[str]:
    """One model call → its first text block, or None.

    FAIL-CLOSED AND FAIL-FORWARD. A model failure is never a crash (both call
    sites treat None as "unavailable" and fall to an honest floor), and a 400
    naming a request field we chose is retried once with that field dropped —
    so a model family released after this file was written degrades to a
    working call instead of taking the ask path down."""
    kwargs: dict = {"model": model, "max_tokens": max_tokens,
                    "messages": messages, **request_kwargs(model)}
    if system:
        kwargs["system"] = system
    try:
        resp = client.messages.create(**kwargs)
        return resp.content[0].text
    except Exception as exc:  # noqa: BLE001 — a model failure is never a crash
        detail = str(exc).lower()
        retryable = any(f in detail for f in ("temperature", "top_p", "top_k",
                                              "thinking", "effort"))
        if not retryable:
            return None
    # Retry once with only the universally-accepted fields.
    try:
        bare: dict = {"model": model, "max_tokens": max_tokens,
                      "messages": messages}
        if system:
            bare["system"] = system
        resp = client.messages.create(**bare)
        return resp.content[0].text
    except Exception:  # noqa: BLE001
        return None
