"""Rolling-horizon (sliced world) question answers (Session 4B.3a CU3, R-AI1).

The M10 Explainer answers over a persisted canonical snapshot + evidence index; a
rolling-horizon run's sliced state (committed frozen front / active window /
beyond-horizon tray) lives in the contract-1.7 RollingBlock of the schedule
document, NOT in a snapshot the Explainer reads today. So the three rolling
questions are answered HERE — deterministically, from the document, planner-voiced
— the AI-reachable capability. This is the reviewable artifact R-AI1 requires: the
answers are authored, ID-free, and honest (the beyond-horizon estimate is hedged
because it is an estimate, never a placement).

NAMED R-AI1 DEBT (docs/04, Session 4B.3a): these answers are NOT yet wired into the
free-phrasing Interpreter, the question ledger, or the deterministic route
taxonomy. Doing so cleanly requires a rolling run to persist a canonical snapshot
the Explainer reads (the connector-era work) — until then this module is the
deterministic surface a caller (the cockpit ask panel, a future explainer route)
delegates the three shapes to. It does not bolt an ad-hoc route onto the router.

Three shapes answered:
  * "what's beyond the horizon?"        → the tray contents
  * "why isn't {order} scheduled yet?"  → admitted-not-yet-windowed, with due +
                                          (if present) the earliest-window estimate
  * "what's frozen?"                    → committed-state facts
"""
from __future__ import annotations

from typing import Any, Optional


# The three rolling question shapes (a closed set — never an ad-hoc route).
ROLLING_ROUTES = ("beyond-horizon", "why-not-scheduled-yet", "frozen")

_BEYOND_TRIGGERS = ("beyond the horizon", "beyond horizon", "not yet scheduled",
                    "unscheduled", "future work", "what's coming", "whats coming",
                    "what is coming", "not in the window", "outside the window")
_FROZEN_TRIGGERS = ("what's frozen", "whats frozen", "what is frozen", "frozen",
                    "committed", "locked in", "what's locked", "whats locked")
_WHYNOT_TRIGGERS = ("why isn't", "why isnt", "why is not", "why not",
                    "not scheduled yet", "not yet scheduled", "when will")


def _rolling(doc: Any) -> Optional[dict]:
    """The rolling block as a dict, or None if the document is monolithic."""
    if doc is None:
        return None
    if isinstance(doc, dict):
        return doc.get("rolling")
    r = getattr(doc, "rolling", None)
    if r is None:
        return None
    return r.model_dump(mode="json") if hasattr(r, "model_dump") else r


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "an unstated date"
    return str(iso)[:10]


def classify_rolling(question: str, doc: Any) -> Optional[str]:
    """Return the rolling route a question matches, or None. Returns None on a
    monolithic document (there is no sliced world to ask about) so a caller only
    delegates here when it is a rolling document."""
    if _rolling(doc) is None:
        return None
    q = (question or "").lower().strip()
    # why-not is checked first: it is the most specific (an order + a "why not").
    if any(t in q for t in _WHYNOT_TRIGGERS):
        return "why-not-scheduled-yet"
    if any(t in q for t in _BEYOND_TRIGGERS):
        return "beyond-horizon"
    if any(t in q for t in _FROZEN_TRIGGERS):
        return "frozen"
    return None


def answer_beyond_horizon(doc: Any) -> str:
    """The tray contents: how many orders are known but not yet scheduled, and the
    nearest few by due date. Empty tray answers honestly (nothing is beyond)."""
    r = _rolling(doc)
    if r is None:
        return "This isn't a rolling schedule, so there's no horizon to look past."
    tray = r.get("beyond_horizon") or []
    if not tray:
        return ("Nothing is beyond the horizon — every known order is already in "
                "the current window.")
    n = len(tray)
    # tray is due-sorted by the assembler; name the nearest few.
    names = []
    for it in tray[:5]:
        wo = it.get("work_order") or (it.get("demand_ref") or "")[:8]
        names.append(f"{wo} (due {_fmt_date(it.get('due'))})")
    lead = (f"{n} order{'s' if n != 1 else ''} {'are' if n != 1 else 'is'} known but "
            f"not yet scheduled — they sit beyond the current window and will enter a "
            f"later one as the schedule rolls forward.")
    tail = " Nearest by due date: " + "; ".join(names) + ("." if n <= 5 else
           f"; and {n - 5} more.")
    return lead + tail


def answer_frozen(doc: Any) -> str:
    """The committed-state facts: how much is frozen and through when."""
    r = _rolling(doc)
    if r is None:
        return "This isn't a rolling schedule, so nothing is frozen."
    committed = int(r.get("committed_count", 0))
    active = int(r.get("active_count", 0))
    frozen_until = _fmt_date(r.get("frozen_until"))
    if committed == 0:
        return (f"Nothing is frozen yet in this window — {active} operation"
                f"{'s' if active != 1 else ''} are being solved but none has crossed "
                f"the frozen boundary ({frozen_until}) to be committed.")
    return (f"{committed} operation{'s' if committed != 1 else ''} "
            f"{'are' if committed != 1 else 'is'} frozen and committed — locked in "
            f"the frozen zone through {frozen_until}; they will not move as the "
            f"schedule rolls. Another {active} operation"
            f"{'s' if active != 1 else ''} are active in the current window, solved "
            f"but not yet frozen.")


def answer_why_not_scheduled_yet(doc: Any, order_ref: Optional[str]) -> str:
    """Why a specific order isn't scheduled yet — admitted-but-beyond-the-window,
    with its due date and (if derivable) the earliest-window estimate, HEDGED
    honestly (the estimate is not a placement). If the order is in the current
    window (committed/active), say so; if unknown, say so."""
    r = _rolling(doc)
    if r is None:
        return "This isn't a rolling schedule, so there is no horizon to be beyond."
    if not order_ref:
        return ("Which order? Name one and I'll say whether it's in the current "
                "window, frozen, or still beyond the horizon.")
    tray = r.get("beyond_horizon") or []
    match = None
    for it in tray:
        if (it.get("work_order") == order_ref
                or it.get("demand_ref") == order_ref):
            match = it
            break
    if match is not None:
        due = _fmt_date(match.get("due"))
        est = match.get("earliest_window_estimate")
        if est:
            return (f"{order_ref} isn't scheduled yet because it sits beyond the "
                    f"current window — its work hasn't been pulled into a scheduling "
                    f"window. It's due {due}, and I estimate it needs to enter a "
                    f"window around {_fmt_date(est)} (based on its due date and work "
                    f"content — that's an estimate, not a committed placement). It "
                    f"will be scheduled as the horizon rolls forward.")
        return (f"{order_ref} isn't scheduled yet because it sits beyond the current "
                f"window. It's due {due}; I can't cheaply estimate its window (no due "
                f"date to work back from), but it will be scheduled as the horizon "
                f"rolls forward.")
    # not in the tray: it's either in the current window or not in this schedule.
    return (f"{order_ref} isn't in the beyond-horizon list — it's either already in "
            f"the current window (committed or active) or not part of this schedule. "
            f"Ask about its placement directly to see which.")
