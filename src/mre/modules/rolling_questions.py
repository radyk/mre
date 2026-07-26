"""Rolling-horizon (sliced world) question answers (Session 4B.3a CU3, R-AI1).

The M10 Explainer answers over a persisted canonical snapshot + evidence index; a
rolling-horizon run's sliced state (committed frozen front / active window /
beyond-horizon tray) lives in the contract-1.7 RollingBlock of the schedule
document, NOT in a snapshot the Explainer reads. So the three rolling questions are
answered HERE — deterministically, from the document, planner-voiced. The answers
are authored, ID-free, and honest (the beyond-horizon estimate is hedged because it
is an estimate, never a placement).

**Session 4A.5c CU4 — THE LAST DETERMINISTIC CLASSIFIER IS GONE.**

``classify_rolling`` — a keyword matcher over three trigger tuples — was the final
surviving piece of the router R-AI5 retired in 4A.5a. It lived on because retiring
it was NOT a small seam, and 4A.5b ruled it 4A.5c scope with the reason stated:

    the parse resolves SUBJECTS against the Explainer's snapshot, which on a
    rolling run is WINDOW 0 ONLY. An order sitting in the beyond-horizon tray
    would resolve to nothing and be answered as ABSENT — a confident-wrong
    answer replacing a correct one.

So the prerequisite came first. ``RollingVocabulary`` below reads the document's
THREE regions — the committed frozen front, the active window, and the tray — and
subject resolution consults it, giving every resolved subject a DISPOSITION
(``SubjectDisposition``). A tray order is now a real subject that is
BEYOND-HORIZON; it is never "not in this schedule". Only then did the matcher die:
the three rolling intents were already in the closed vocabulary
(``Intent.BEYOND_HORIZON`` / ``WHY_NOT_SCHEDULED_YET`` / ``FROZEN``) with authored
meanings, so the parse names them and the dispatch reaches these answerers. The
keyword tables are DELETED, not bypassed.

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


class RollingVocabulary:
    """The sliced world's ORDER VOCABULARY, read from the schedule document.

    THE PREREQUISITE (4A.5b rider d). Subject resolution against the Explainer's
    snapshot sees window 0 and nothing else. This class supplies the rest — every
    work order the document knows and WHICH REGION it is in:

      * ``committed``      — placed and frozen; it will not move as the plan rolls
      * ``in_window``      — placed in the active window
      * ``beyond_horizon`` — in the tray: admitted, due-dated, not yet windowed

    Read-only, built per ask from the document the API already loads. It resolves
    names the customer's own vocabulary uses (work orders), never an id shape —
    the relevance guard's rule holds here exactly as it does in the Explainer: only
    names the document actually carries can match.
    """

    def __init__(self, doc: Any) -> None:
        self._by_order: dict[str, str] = {}
        rolling = _rolling(doc) or {}
        self.is_rolling = bool(rolling)
        if not self.is_rolling or doc is None:
            return
        d = doc if isinstance(doc, dict) else (
            doc.model_dump(mode="json") if hasattr(doc, "model_dump") else {})
        # The tray first, then the placed bars: a bar's region wins over the tray
        # if a name somehow appears in both (a placed order is placed).
        for item in rolling.get("beyond_horizon") or []:
            wo = item.get("work_order")
            if wo:
                self._by_order[str(wo).upper()] = "beyond-horizon"
        for a in d.get("assignments") or []:
            region = ("committed" if a.get("commitment_state") == "committed"
                      else "in-window")
            for wo in a.get("work_orders") or []:
                if wo:
                    self._by_order[str(wo).upper()] = region

    def __bool__(self) -> bool:
        return self.is_rolling

    def resolve(self, raw: str) -> Optional[str]:
        """A planner's words → the work order this document carries, or None.

        Exact match first, then a UNIQUE substring — the same discipline
        ``Explainer.resolve_order_value`` uses, and for the same reason: two
        candidates leave it unresolved rather than guessed."""
        if not raw or not self._by_order:
            return None
        key = raw.upper().strip(" .,?!")
        if key in self._by_order:
            return key
        hits = [k for k in self._by_order if key in k or k in key]
        return hits[0] if len(hits) == 1 else None

    def disposition(self, order: Optional[str]) -> Optional[str]:
        """The region a resolved order sits in, or None if the document does not
        carry it."""
        if not order:
            return None
        return self._by_order.get(str(order).upper())

    def beyond_horizon(self, order: Optional[str]) -> bool:
        return self.disposition(order) == "beyond-horizon"


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
