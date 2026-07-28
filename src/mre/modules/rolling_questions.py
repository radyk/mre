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

**Session 4B.6 — THE COARSE ZONE REACHES THE ASK PATH (R-AI1).**

Beyond-horizon work is now coarsely PLACED, not merely listed (R-SC2 amendment),
so two shapes became answerable that previously had no route. They are added to
the CLOSED vocabulary the same way the first three were — `Intent.COARSE_FIT` /
`Intent.BUCKET_LOAD` with authored meanings, taxonomy entries and offers — never
as an ad-hoc route. "When will ORD-X start?" deliberately gets no new intent: it
is already `why-not-scheduled-yet`, whose answer now carries the coarse bucket
BESIDE the due-date heuristic (two figures, two methods, never fused).

Five shapes answered:
  * "what's beyond the horizon?"        → the tray contents
  * "why isn't {order} scheduled yet?"  → admitted-not-yet-windowed, with due,
                                          the earliest-window estimate, and (1.9)
                                          the coarse bucket, each labeled
  * "what's frozen?"                    → committed-state facts
  * "will it fit?"                      → the PROOF run only; a proven negative
                                          names the resource-week, and a
                                          placement is never converted to a yes
  * "why is week N full?"               → the binding capacity constraint, stated
                                          as load against DERATED capacity
"""
from __future__ import annotations

from typing import Any, Optional


# The rolling question shapes (a closed set — never an ad-hoc route). The last
# two arrived in Session 4B.6 with the coarse zone (R-SC2 amendment).
ROLLING_ROUTES = ("beyond-horizon", "why-not-scheduled-yet", "frozen",
                  "coarse-fit", "bucket-load")


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
    window (committed/active), say so; if unknown, say so.

    R-PD1 clause (6), Session 4B.11 CU4(a). The fall-through used to answer a
    non-tray order with a DISJUNCTION — "it's either already in the current
    window (committed or active) or not part of this schedule" — and on the
    past-due specimen NEITHER BRANCH WAS TRUE (4B.10 §5a.26(d)). The document
    already knows which: ``RollingVocabulary`` reads the three regions off it.
    The disjunction is replaced by the answer, and it now RESOLVES rather than
    redirecting: an order in the window gets its placement region and, when it is
    late, the floor/controllable split (clause (4) — never one fused number).
    """
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
        coarse = _coarse_sentence(match, r)
        if est:
            return (f"{order_ref} isn't scheduled yet because it sits beyond the "
                    f"current window — its work hasn't been pulled into a scheduling "
                    f"window. It's due {due}, and I estimate it needs to enter a "
                    f"window around {_fmt_date(est)} (based on its due date and work "
                    f"content — that's an estimate, not a committed placement)."
                    f"{coarse} It will be scheduled as the horizon rolls forward.")
        if coarse:
            return (f"{order_ref} isn't scheduled yet because it sits beyond the "
                    f"current window. It's due {due}.{coarse} It will be scheduled "
                    f"as the horizon rolls forward.")
        return (f"{order_ref} isn't scheduled yet because it sits beyond the current "
                f"window. It's due {due}; I can't cheaply estimate its window (no due "
                f"date to work back from), but it will be scheduled as the horizon "
                f"rolls forward.")
    # NOT IN THE TRAY. The document says which of the remaining cases this is —
    # so say it, rather than offering the planner a disjunction to resolve.
    region = RollingVocabulary(doc).disposition(order_ref)
    if region in ("committed", "in-window"):
        placed = "committed in the frozen zone" if region == "committed" else \
                 "placed in the current window"
        late = _lateness_clause(doc, order_ref)
        return (f"{order_ref} IS scheduled — it's {placed}, not waiting beyond the "
                f"horizon.{late} Ask \"where is {order_ref}?\" for the operation "
                f"timeline.")
    return (f"{order_ref} isn't in this schedule at all: it is neither placed in "
            f"the current window nor sitting beyond the horizon. That is a data "
            f"question rather than a scheduling one — ask \"why was {order_ref} "
            f"excluded?\" and I'll cite the record that removed it, and which "
            f"module did.")


def _lateness_clause(doc: Any, order_ref: str) -> str:
    """" It finishes N minutes late …" for a placed order, with the R-PD1
    clause (4) SPLIT when part of that lateness was unavoidable.

    Two figures, never fused: a planner told an order is 85,495 minutes late
    needs to know that 84,240 of those minutes were already on the clock before
    this schedule existed. Empty string when the order is on time or the document
    carries no outcome for it — silence rather than a guess."""
    d = doc if isinstance(doc, dict) else (
        doc.model_dump(mode="json") if hasattr(doc, "model_dump") else {})
    for s in d.get("service_outcomes") or []:
        if str(s.get("work_order") or "").upper() != str(order_ref).upper():
            continue
        late = int(s.get("lateness_min") or 0)
        if late <= 0:
            return " It finishes on time."
        floor = s.get("tardiness_floor_min")
        if floor:
            floor = int(floor)
            return (f" It finishes {late} minutes past its due date — but "
                    f"{floor} of those were already unavoidable when this window "
                    f"opened (it was ALREADY PAST DUE), so this schedule adds "
                    f"{late - floor}.")
        return f" It finishes {late} minutes past its due date."
    return ""


# ---------------------------------------------------------------------------
# THE COARSE ZONE (Session 4B.6, R-SC2 amendment) — two answers and a fragment.
#
# Every sentence below obeys the same three clauses:
#   (1)/(2) only a COMPLETE PROOF-RUN INFEASIBLE licenses "it won't fit"; a
#           proof run that PLACES the book proves nothing about the fine model,
#           and the answer says so rather than converting it into a yes.
#   (5)     coarse tardiness is spoken in WEEKS/BUCKETS, never in money, so it
#           can never be heard as part of the schedule's cost.
#   (6)     a coarse figure is an ESTIMATE FROM A LOAD MODEL, never a placement,
#           and the wording never says "scheduled on" or names a start time.
# The resource WITNESS is never voiced as an assignment: the fine solve
# re-decides it freely, so naming it would be a promise we do not hold.
# ---------------------------------------------------------------------------

def _coarse(r: Optional[dict]) -> Optional[dict]:
    """The coarse-zone block of a rolling block, or None when it did not run."""
    if not r:
        return None
    return r.get("coarse_zone")


def _bucket_label(cz: dict, index: int) -> str:
    """A planner-voiced name for a bucket: 'the week of 12 Jan' (or the
    period, when the declared bucket length is not a week)."""
    for b in cz.get("buckets") or []:
        if int(b.get("index", -1)) == index:
            days = int(cz.get("bucket_days", 7))
            noun = "week" if days == 7 else f"{days}-day period"
            return f"the {noun} of {_fmt_date(b.get('start'))}"
    return f"bucket {index}"


def _rho_clause(cz: dict) -> str:
    """State rho and its PROVENANCE. A defaulted derate must never read as the
    plant's own choice (clause 3).

    4B.6a CU2(d) — THE ABSENCE IS MADE LOUD. At rho = 1.0 the planning run
    MIRRORS the proof run, so an undeclared plant gets no planning signal at all
    and every figure here assumes each available minute is usable. That is the
    OPTIMISTIC direction, which is the one we do not want to be wrong in. We do
    not invent a margin to cover it (clause 3 stands) — we say out loud that
    there isn't one.
    """
    rho = float(cz.get("capacity_derate", 1.0))
    declared = cz.get("capacity_derate_provenance") == "declared"
    if rho >= 1.0:
        if declared:
            return (" That's against full calendar capacity (a derate of 1.0 is "
                    "declared), so these figures assume every available minute "
                    "is usable.")
        return (" That's against full calendar capacity — no capacity margin is "
                "declared for this plant, so I've shaved nothing off and these "
                "figures assume every available minute is usable. Declare a "
                "planning derate and I'll hold time back for the unknown.")
    pct = f"{rho:.0%}"
    if declared:
        return (f" Capacity here is your declared planning derate of {pct} of "
                f"calendar time, not the full calendar.")
    return (f" Capacity here is {pct} of calendar time — a default, not something "
            f"this plant declared.")


def _plural(n: int) -> str:
    return "s" if n != 1 else ""


def _uncounted_clause(cz: dict) -> str:
    """4B.6a CU2(a) — VOICE WHAT WAS NOT COUNTED.

    The coarse capacity arithmetic runs over a population missing every
    resumable op and every op that exceeds a single bucket's capacity. An
    excluded op consumes ZERO coarse minutes, so every load and every
    utilization here is UNDERSTATED — and resumables are the LONG ops, the ones
    that most stress capacity. A cell reading 60% over a partial population is
    not 60%.

    The precedent is 4B.6's own finding: without the unmodelable COUNT, the
    rho = 0.10 result read as "it fits". Same lesson, second exclusion.

    Empty when nothing is excluded — an answer must not invent a caveat it does
    not have.
    """
    n = int(cz.get("unmodelable_count", 0) or 0)
    if n <= 0:
        return ""
    return (f" One caveat on those numbers: {n} operation{_plural(n)} "
            f"{'are' if n != 1 else 'is'} outside what my coarse model can "
            f"represent, and {'their' if n != 1 else 'its'} minutes are not "
            f"counted in any load or percentage above — so the real load is "
            f"higher than what I've shown.")


def _coarse_sentence(tray_item: dict, r: dict) -> str:
    """The coarse fragment appended to a why-not-scheduled-yet answer. Empty
    when the coarse zone did not run or could not represent the order."""
    cz = _coarse(r)
    c = (tray_item or {}).get("coarse")
    if not cz or not c:
        return ""
    if c.get("sub_disposition") == "coarse_unmodelable":
        reason = {
            "resumable_out_of_scope":
                "it can be split across shifts, and my coarse look-ahead can't "
                "model split work yet",
            "exceeds_bucket_capacity":
                "no single machine-week has enough open time for one of its "
                "operations at the planning capacity in force",
            "no_eligible_resource":
                "I can't find a machine qualified for one of its operations",
        }.get(c.get("unmodelable_reason", ""),
              "my coarse look-ahead can't model it")
        return (f" I can't give a rough week for it either — {reason}, so I've "
                f"left it out of the look-ahead rather than guess.")
    label = _bucket_label(cz, int(c.get("start_bucket_index", 0)))
    late = int(c.get("coarse_tardiness_buckets", 0) or 0)
    bound = (" That's an upper bound — the look-ahead ran out of budget before "
             "proving it couldn't do better."
             if cz.get("figures_are_upper_bounds") else "")
    tail = ""
    if late > 0:
        noun = "week" if int(cz.get("bucket_days", 7)) == 7 else "period"
        tail = (f" On that rough plan it finishes about {late} {noun}"
                f"{_plural(late)} past its due date.")
    return (f" Looking further out, my coarse capacity model puts its first work "
            f"in {label} — that's a load estimate over whole weeks, not a "
            f"placement, and the real schedule will re-decide it.{tail}{bound}")


def answer_coarse_fit(doc: Any) -> str:
    """"Will it fit?" — answered from the PROOF RUN ONLY (clause 2).

    The asymmetry is the whole point and it is spoken out loud: a proof-run
    INFEASIBLE is a REFUTATION (and names the resource-week that proves it),
    while a proof run that places the book is NOT a promise that the real
    schedule will. The converse of clause (1) is never asserted."""
    r = _rolling(doc)
    if r is None:
        return ("This isn't a rolling schedule, so there's no look-ahead beyond "
                "the horizon to check capacity against.")
    cz = _coarse(r)
    if cz is None:
        return ("I haven't run the coarse look-ahead for this schedule, so I "
                "can't say whether the work beyond the horizon fits. What I can "
                "show you is what's out there and when each order is due.")

    tray = r.get("beyond_horizon") or []
    n = len(tray)

    if cz.get("infeasibility_proven"):
        cells = cz.get("binding_cells") or []
        where = ""
        if cells:
            c0 = max(cells, key=lambda c: c.get("utilization", 0))
            where = (f" The binding constraint is {c0.get('resource_id')} in "
                     f"{_bucket_label(cz, int(c0.get('bucket_index', 0)))}: "
                     f"{int(c0.get('load_minutes', 0))} minutes of work against "
                     f"{int(c0.get('capacity_minutes', 0))} minutes of capacity.")
        # The exclusion is named here too (CU2(a)) — and named in the direction
        # that is true: leaving work OUT can only make the refutation stronger,
        # never weaker, because the excluded minutes would add load. Saying so
        # keeps the caveat from reading as a hedge on a proof.
        left_out = ""
        unmod = int(cz.get("unmodelable_count", 0) or 0)
        if unmod:
            left_out = (f" That count leaves out {unmod} operation"
                        f"{_plural(unmod)} my coarse model can't represent — "
                        f"{'their' if unmod != 1 else 'its'} minutes aren't in "
                        f"these figures at all, which only makes the case "
                        f"stronger, never weaker.")
        return (f"No — and this one I can prove. Running the {n} order{_plural(n)} "
                f"beyond the horizon against full calendar capacity, there is no "
                f"way to fit them: the coarse model is infeasible at full "
                f"capacity, and because it is a simplification of the real "
                f"schedule, the real schedule can't fit them either.{where} "
                f"Something has to give — a due date, overtime, or work moving "
                f"out.{left_out}")

    if cz.get("proof_status") == "UNKNOWN" or cz.get("wall_truncated"):
        return (f"I can't answer that one honestly. The capacity check over the "
                f"{n} order{_plural(n)} beyond the horizon didn't finish, so I "
                f"have neither a fit nor a proof that it doesn't fit — and I "
                f"won't report a half-finished search as either.")

    # It PLACED the book. This is NOT a yes, and the sentence must not imply one.
    parts = [
        f"My coarse capacity model can place all {n} order{_plural(n)} beyond "
        f"the horizon into the coming weeks. That is NOT a promise it fits — the "
        f"coarse model is a simplification, so it can only ever prove that "
        f"something DOESN'T fit, never that it does. The real schedule decides."]
    late = int(cz.get("tardiness_buckets_total", 0) or 0)
    if late:
        noun = "week" if int(cz.get("bucket_days", 7)) == 7 else "period"
        parts.append(f"Even in that rough plan, work runs about {late} {noun}"
                     f"{_plural(late)} past due in total.")
    tight = list(cz.get("binding_cells") or [])
    if tight:
        c0 = max(tight, key=lambda c: c.get("utilization", 0))
        parts.append(f"The tightest spot is {c0.get('resource_id')} in "
                     f"{_bucket_label(cz, int(c0.get('bucket_index', 0)))}, "
                     f"running at {c0.get('utilization', 0):.0%} of capacity.")
    return (" ".join(parts) + _rho_clause(cz)).rstrip() + _uncounted_clause(cz)


def answer_bucket_load(doc: Any, bucket: Any = None) -> str:
    """"Why is week N full?" — the BINDING CAPACITY CONSTRAINT, stated as
    arithmetic (load against derated capacity) rather than as an adjective."""
    r = _rolling(doc)
    if r is None:
        return ("This isn't a rolling schedule, so there are no look-ahead weeks "
                "to be full.")
    cz = _coarse(r)
    if cz is None:
        return ("I haven't run the coarse look-ahead for this schedule, so I "
                "don't have per-week loads beyond the horizon to explain.")

    density = cz.get("density") or []
    idx = _bucket_index_from(bucket, cz)

    if idx is not None:
        here = [c for c in density if int(c.get("bucket_index", -1)) == idx]
        if not here:
            # A ZERO is a load claim too, and the most misleading one to make
            # over a partial population.
            return (f"I don't have any load in {_bucket_label(cz, idx)} — nothing "
                    f"beyond the horizon lands there in my coarse "
                    f"model.{_uncounted_clause(cz)}")
        top = sorted(here, key=lambda c: -c.get("utilization", 0))[:3]
        lines = "; ".join(
            f"{c.get('resource_id')} at {c.get('utilization', 0):.0%} "
            f"({int(c.get('load_minutes', 0))} of "
            f"{int(c.get('capacity_minutes', 0))} minutes)" for c in top)
        verdict = ("It's genuinely full" if top[0].get("utilization", 0) >= 0.95
                   else "It isn't actually full")
        return (f"{verdict} in {_bucket_label(cz, idx)}. The busiest machines "
                f"there: {lines}.{_rho_clause(cz)} These are whole-week loads "
                f"from my coarse look-ahead, not a schedule — no operation has a "
                f"start time yet.{_uncounted_clause(cz)}")

    cells = cz.get("binding_cells") or []
    if not cells:
        return ("Nothing beyond the horizon is running at capacity in my coarse "
                "look-ahead — no machine-week is full. Name a week and I'll show "
                "you what's in it." + _uncounted_clause(cz))
    c0 = max(cells, key=lambda c: c.get("utilization", 0))
    return (f"The fullest spot beyond the horizon is {c0.get('resource_id')} in "
            f"{_bucket_label(cz, int(c0.get('bucket_index', 0)))}: "
            f"{int(c0.get('load_minutes', 0))} minutes of work against "
            f"{int(c0.get('capacity_minutes', 0))} minutes of capacity "
            f"({c0.get('utilization', 0):.0%}).{_rho_clause(cz)} That's a "
            f"whole-week load from my coarse look-ahead, not a "
            f"schedule.{_uncounted_clause(cz)}")


def _bucket_index_from(bucket: Any, cz: dict) -> Optional[int]:
    """Resolve what the planner meant by a week. Accepts a bucket index, a
    'week N' phrase, or a date inside a bucket. Returns None when nothing
    resolves — the answer then names the fullest cell rather than guessing."""
    if bucket is None or bucket == "":
        return None
    if isinstance(bucket, int):
        return bucket
    import re as _re
    s = str(bucket).strip().lower()
    m = _re.search(r"(\d+)", s)
    if m and ("week" in s or "bucket" in s or "period" in s or s == m.group(1)):
        n = int(m.group(1))
        idx = {int(b.get("index", -1)) for b in (cz.get("buckets") or [])}
        # a planner counting "week 1" means the first bucket; accept both
        if n in idx:
            return n
        if (n - 1) in idx:
            return n - 1
        return None
    for b in cz.get("buckets") or []:
        start, end = str(b.get("start", "")), str(b.get("end", ""))
        if start[:10] <= s[:10] < end[:10]:
            return int(b.get("index", 0))
    return None
