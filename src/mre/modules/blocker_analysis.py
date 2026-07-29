"""THE BLOCKER ANALYSIS — what is the binding constraint on this operation
starting earlier? (Session 4B.14 Item 2.)

THE MEASURED FAILURE THIS EXISTS FOR. On the pinned board the explainer said:

    ORD-000013 starts Tue 2026-01-13 07:00 because CUT-01 was busy: held by
    ORD-000011 until 2026-01-08 19:00, so ORD-000013 took the next opening.

CUT-01's next opening after Jan 8 19:00 is Jan 9 07:00 — four days earlier than
the start being explained — and CUT-01 carries three other placements in
between. The route named the FIRST blocker in a chain and presented it as the
whole cause.

The deeper shortage is not that number. The explainer knew ONE causal story,
resource contention, and the plant has at least six. When the true cause is one
of the other five it reached for the only story it had and rendered it fluently,
with citations. Here the true cause was the sixth: an indivisible operation that
did not fit what was left of the shift.

THE METHOD — an independent earliest-feasible-start per constraint FAMILY
------------------------------------------------------------------------
Each family answers one question — "ignoring everything else, how early could
this operation begin?" — and the ladder is monotone by construction, because
each family is computed at or after the previous one's answer:

    release     (docs/05 A4)      the demand's release date
    precedence  (docs/05 A1/A2)   max(end + min_lag) over placed predecessors
    frozen      (R-F1)            the frozen boundary, where it applies
    pin         (docs/05 A7/F1)   an exact pinned window, where one exists
    resource    (docs/05 B1)      first moment the machine is not otherwise held
    calendar    (docs/05 C1/C2)   first OPEN moment on that machine's calendar
    chunkfit    (docs/05 C3)      first placement with room for the WHOLE op —
                                  one contiguous piece when it cannot be split,
                                  else pieces no smaller than min_chunk

BINDING is the EARLIEST family in ladder order attaining the maximum est. Ties
matter: when precedence and chunkfit both land on the same instant, precedence
is what pushed it there and chunkfit merely failed to push further. RUNNER-UP is
the largest est strictly below the maximum, with the family that produced it —
the thing that would bind next if the binding cause were removed.

THE DISTINCTION THAT MATTERS MOST, and the product could not draw it before:

    actual_start == max(est)   IT COULD NOT START EARLIER.
    actual_start >  max(est)   NOTHING PREVENTED IT — the solver CHOSE this.

"Couldn't" and "chose not to" are different facts to a planner, and the
explainer asserted the first for both. That is the deepest form of the causal
defect this module answers, and it is why the verdict is a first-class field
rather than a footnote.

WHAT THE ESTIMATES MEAN, STATED SO IT CANNOT BE OVERREAD. Every figure is read
from the PERSISTED document with every OTHER placement held exactly where it is
(R-AI4: no re-solve). So `could_not_start_earlier` means "not without moving
something else", and `nothing_prevented_it` means "this operation alone could
have gone earlier into space that is genuinely free". Neither is a claim about
what a re-solve would produce, and the authored copy never makes one.

FAMILIES IN docs/05 THAT THIS CANNOT COMPUTE — named, not silently omitted
--------------------------------------------------------------------------
Listed in ``UNCOMPUTED_FAMILIES`` and reported on every analysis, so an answer
can say what it did not weigh:

  * B3/B5 — secondary and cumulative resources (tools, operator pools). The
    document carries occupancy for the PRIMARY lane only; there is no surface
    for a secondary draw, so a tool or an operator pool holding this operation
    back is invisible here. A document-shape change, not a computation.
  * B7/B8 — sequence-dependent changeover. The matrix IS readable (the pinned
    world carries a `setup_transition` Constraint with a PAINT_RED/PAINT_BLUE
    transition table), so this is not a data gap — it is a METHOD gap. The setup
    an operation would need at an EARLIER position depends on what would then
    precede it, which is a different schedule, and asserting it would be a
    re-solve wearing an estimate's clothes (R-AI4). The analysis therefore prices
    the setup this operation actually has, and says so rather than pretending the
    term is absent. This is exactly the placement-dependent term docs/07 §5a.27's
    caveat says a plant that prices changeovers would carry.
  * C4 — time-window operation restrictions ("only day shift"). Catalog status
    MP with an §8 doorway; no adapter populates it, so there is nothing to read.
  * A3 / A6 — max lag and hard deadline. These are UPPER bounds. They can make a
    LATER start infeasible; they can never be why an operation could not start
    EARLIER, so they are out of scope for this question rather than missing
    from it. Named here so the omission is a decision, not an oversight.
  * F3 — SameResource. Catalog status UI; no records exist.

This module is PURE: plain data in, a dataclass out, no I/O and no snapshot
reader. The Explainer assembles its input from the persisted document; the
renderer voices its output. Both of those are the places that already know how.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

#: The ladder, in the order the estimates are computed and ties are broken.
#: Each entry is (key, docs/05 citation, planner-facing label).
FAMILY_LADDER: tuple[tuple[str, str, str], ...] = (
    ("release", "A4", "release date"),
    ("precedence", "A1/A2", "an earlier step"),
    ("frozen", "R-F1", "the frozen boundary"),
    ("pin", "A7/F1", "a pin"),
    ("resource", "B1", "the machine being held"),
    ("calendar", "C1/C2", "the machine's calendar"),
    ("chunkfit", "C3", "no window long enough"),
)

FAMILY_KEYS: tuple[str, ...] = tuple(k for k, _, _ in FAMILY_LADDER)

#: docs/05 families this analysis does NOT weigh, and why (see the module
#: docstring). Reported on every analysis so an answer can name its own limits.
UNCOMPUTED_FAMILIES: tuple[tuple[str, str], ...] = (
    ("B3/B5", "secondary and cumulative resources (tools, operator pools) — the "
              "document carries primary-lane occupancy only"),
    ("B7/B8", "sequence-dependent changeover — the ChangeoverRule matrix is not "
              "in the document, so setup at another position cannot be priced"),
    ("C4", "time-window operation restrictions — no adapter populates the "
           "doorway, so there is nothing to read"),
    ("F3", "SameResource linkage — unimplemented in the catalog"),
)


@dataclass(frozen=True)
class Estimate:
    """One family's earliest-feasible-start, with the evidence behind it."""

    family: str
    citation: str
    label: str
    est: Optional[datetime]
    #: Short, planner-facing statement of WHY this family lands where it does.
    #: Composed here (never by a model) so a figure and its reason cannot drift.
    because: str = ""
    #: Family-specific evidence the renderer may quote — the holder's order id,
    #: the minutes that were left, the closure's reason.
    facts: dict = field(default_factory=dict)

    @property
    def computed(self) -> bool:
        return self.est is not None


@dataclass(frozen=True)
class BlockerAnalysis:
    """The answer to 'why is it here?' for ONE operation."""

    order: str
    op_seq: Optional[int]
    machine: str
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    working_min: float
    splittable: bool
    min_chunk_min: Optional[float]
    estimates: tuple[Estimate, ...]
    binding: Optional[Estimate]
    runner_up: Optional[Estimate]
    #: "could_not" | "chose" | "undetermined" — see the module docstring.
    verdict: str
    #: When the verdict is "chose": how much earlier it could have gone.
    slack_min: Optional[float] = None
    #: The driver code on this operation's assignment Decision, when one exists —
    #: the cost reason behind a CHOSEN placement (R-AI3(1): cited, never guessed).
    chosen_driver: Optional[str] = None
    uncomputed: tuple[tuple[str, str], ...] = UNCOMPUTED_FAMILIES
    #: Every family that strictly pushed the estimate later, in ladder order.
    #: The chain of causes, of which ``binding`` is the last link.
    pushers: tuple[Estimate, ...] = ()

    @property
    def could_not_start_earlier(self) -> bool:
        return self.verdict == "could_not"

    def est_of(self, family: str) -> Optional[Estimate]:
        for e in self.estimates:
            if e.family == family:
                return e
        return None


# ---------------------------------------------------------------------------
# Interval arithmetic — the whole module's only mathematics, kept in one place
# ---------------------------------------------------------------------------

def _merge(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Sorted, non-overlapping union of half-open spans."""
    out: list[tuple[datetime, datetime]] = []
    for s, e in sorted(x for x in spans if x[0] is not None and x[1] is not None):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _subtract(base: list[tuple[datetime, datetime]],
              cut: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """``base`` minus ``cut`` — the free-and-open time an operation may occupy."""
    out: list[tuple[datetime, datetime]] = []
    cuts = _merge(cut)
    for s, e in _merge(base):
        cur = s
        for cs, ce in cuts:
            if ce <= cur or cs >= e:
                continue
            if cs > cur:
                out.append((cur, min(cs, e)))
            cur = max(cur, ce)
            if cur >= e:
                break
        if cur < e:
            out.append((cur, e))
    return [(s, e) for s, e in out if e > s]


def _first_moment_outside(spans: list[tuple[datetime, datetime]],
                          after: datetime) -> datetime:
    """The earliest instant at or after ``after`` that lies in no span."""
    t = after
    for s, e in _merge(spans):
        if e <= t:
            continue
        if s > t:
            return t
        t = e
    return t


def _first_moment_inside(spans: list[tuple[datetime, datetime]],
                         after: datetime) -> Optional[datetime]:
    """The earliest instant at or after ``after`` that lies in some span."""
    for s, e in _merge(spans):
        if e <= after:
            continue
        return max(s, after)
    return None


def _minutes(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60.0


def earliest_fit(free: list[tuple[datetime, datetime]], after: datetime,
                 working_min: float, *, splittable: bool,
                 min_chunk_min: Optional[float]) -> tuple[Optional[datetime], dict]:
    """The earliest start at or after ``after`` from which the WHOLE operation
    can be placed in ``free`` (open calendar time not held by other work).

    Non-splittable: one contiguous piece of ``working_min``.

    Splittable: pieces that are each at least ``min_chunk_min``, summing to
    ``working_min``. The degenerate-split rule (docs/05 R-C3, and
    ``calendar_utils.is_effectively_resumable``) is the caller's to apply — an
    operation whose duration is under 2 x min_chunk cannot split at all and is
    passed here as non-splittable, exactly as the SolverBuilder treats it. The
    two MUST agree or this analysis would claim a fit the solver cannot place.

    Returns (start, facts). ``facts["short_window"]`` is the LAST window that was
    too short before the fit succeeded — the near miss, not the first miss. That
    distinction is the whole usefulness of the fact: for ORD-000013's op10 the
    FIRST too-short window is a six-minute sliver at the end of Jan 5, which
    explains nothing, while the LAST one is Monday 15:37-19:00, which is exactly
    why it waited for Tuesday. It is the difference between "no window was long
    enough" and the target sentence, "it needs 6h and 3h remain".

    STATED LIMIT (splittable operations). Setup is a separate phase with its own
    interruptibility class (docs/05 R-C3), and this scan treats the operation's
    working minutes as one divisible quantity. So for a splittable operation the
    fit is a LOWER bound on where the solver could have opened it, not a
    placement the solver is guaranteed to be able to produce. The copy that
    voices a `chose` verdict is worded against what this actually computes —
    open, unheld time on the machine — and never against what a re-solve would do.
    """
    spans = [(s, e) for s, e in _merge(free) if e > after]
    if not spans:
        return None, {}
    spans = [(max(s, after), e) for s, e in spans]
    facts: dict = {}
    floor = float(min_chunk_min or 0.0)

    for i, (s0, e0) in enumerate(spans):
        if not splittable:
            if _minutes(s0, e0) + 1e-9 >= working_min:
                return s0, facts
            facts["short_window"] = {
                "start": s0, "end": e0,
                "available_min": round(_minutes(s0, e0), 3),
                "needed_min": working_min,
            }
            continue
        # Splittable: walk forward from this window accumulating usable pieces.
        remaining = working_min
        first_piece = _minutes(s0, e0)
        if floor > 0 and first_piece + 1e-9 < min(floor, remaining):
            # Cannot even open here — the first piece would be below the floor.
            facts["short_window"] = {
                "start": s0, "end": e0,
                "available_min": round(first_piece, 3),
                "needed_min": min(floor, remaining),
                "reason": "below min_chunk",
            }
            continue
        for s, e in spans[i:]:
            usable = _minutes(s, e)
            if usable + 1e-9 >= remaining:
                remaining = 0.0
                break
            if floor > 0 and usable + 1e-9 < floor:
                continue          # too short to be a legal piece; skip it
            if floor > 0 and (remaining - usable) + 1e-9 < floor:
                # Taking all of this window would strand a final piece below the
                # floor; take only what leaves a legal remainder.
                usable = remaining - floor
                if usable <= 0:
                    continue
            remaining -= usable
        if remaining <= 1e-9:
            return s0, facts
        facts["short_window"] = {
            "start": s0, "end": e0,
            "available_min": round(first_piece, 3),
            "needed_min": working_min,
        }
    return None, facts


# ---------------------------------------------------------------------------
# The analysis
# ---------------------------------------------------------------------------

def analyze(*, order: str, op_seq: Optional[int], machine: str,
            actual_start: Optional[datetime], actual_end: Optional[datetime],
            working_min: float, splittable: bool,
            min_chunk_min: Optional[float],
            open_windows: list[tuple[datetime, datetime]],
            occupied: list[tuple[datetime, datetime]],
            predecessors: Optional[list[dict]] = None,
            release: Optional[datetime] = None,
            frozen_until: Optional[datetime] = None,
            frozen_applies: bool = False,
            pin_start: Optional[datetime] = None,
            chosen_driver: Optional[str] = None,
            holder: Optional[dict] = None,
            closures: Optional[list[dict]] = None,
            tolerance_min: float = 1.0) -> BlockerAnalysis:
    """Compute the ladder for one placed operation. Pure; see the module docstring.

    ``occupied`` is every OTHER operation's span on this machine (the caller
    removes this operation's own). ``open_windows`` is the machine's resolved
    calendar — regular windows plus declared additions, minus closures — which
    the persisted document already carries per resource.

    ``tolerance_min`` is the equality band for "the estimate EQUALS the actual
    start". One minute: the document's grid is whole minutes, and a verdict that
    flipped on a rounding artefact would be worse than no verdict at all.
    """
    preds = list(predecessors or [])
    estimates: list[Estimate] = []

    def _add(family: str, est: Optional[datetime], because: str,
             facts: Optional[dict] = None) -> None:
        cit = next(c for k, c, _ in FAMILY_LADDER if k == family)
        lbl = next(l for k, _, l in FAMILY_LADDER if k == family)
        estimates.append(Estimate(family=family, citation=cit, label=lbl,
                                  est=est, because=because, facts=facts or {}))

    # --- release (A4) ------------------------------------------------------
    _add("release", release,
         f"its release date is {_fmt(release)}" if release else
         "no release date is recorded for this order",
         {"release": release})

    # --- precedence (A1/A2) ------------------------------------------------
    pred_est: Optional[datetime] = None
    pred_facts: dict = {}
    for p in preds:
        end = p.get("end")
        if end is None:
            continue
        cand = end + timedelta(minutes=float(p.get("min_lag_min") or 0.0))
        if pred_est is None or cand > pred_est:
            pred_est = cand
            pred_facts = {"op_seq": p.get("op_seq"), "machine": p.get("machine"),
                          "end": end, "min_lag_min": p.get("min_lag_min") or 0.0}
    if pred_est is not None:
        step = (f"op{pred_facts['op_seq']}" if pred_facts.get("op_seq") is not None
                else "its previous step")
        lag = float(pred_facts.get("min_lag_min") or 0.0)
        lag_txt = f" plus a {lag:g}-minute lag" if lag else ""
        _add("precedence", pred_est,
             f"{step} finishes at {_fmt(pred_facts['end'])}{lag_txt}", pred_facts)
    else:
        _add("precedence", None,
             "this is the order's first step, so no earlier step gates it")

    # --- frozen (R-F1) -----------------------------------------------------
    if frozen_applies and frozen_until is not None:
        _add("frozen", frozen_until,
             f"the frozen boundary stands at {_fmt(frozen_until)}",
             {"frozen_until": frozen_until})
    else:
        _add("frozen", None, "no frozen boundary applies to this operation")

    # --- pin (A7/F1) -------------------------------------------------------
    if pin_start is not None:
        _add("pin", pin_start, f"it is pinned to start at {_fmt(pin_start)}",
             {"pin_start": pin_start})
    else:
        _add("pin", None, "no pin constrains this operation")

    floor_candidates = [e.est for e in estimates if e.est is not None]
    floor = max(floor_candidates) if floor_candidates else (
        actual_start or (open_windows[0][0] if open_windows else None))
    if floor is None:
        return BlockerAnalysis(
            order=order, op_seq=op_seq, machine=machine,
            actual_start=actual_start, actual_end=actual_end,
            working_min=working_min, splittable=splittable,
            min_chunk_min=min_chunk_min, estimates=tuple(estimates),
            binding=None, runner_up=None, verdict="undetermined",
            chosen_driver=chosen_driver)

    # --- resource (B1) -----------------------------------------------------
    res_est = _first_moment_outside(occupied, floor)
    if res_est > floor:
        held = holder or {}
        # The holder is the work occupying the machine at the moment `res_est`
        # frees it — the caller resolves it from the same rows it built
        # `occupied` from, because only the caller knows the order ids. Naming
        # "other work" is the honest fallback; inventing a name is not an option.
        because = (f"{machine} is held by {held['order']} until {_fmt(res_est)}"
                   if held.get("order") else
                   f"{machine} is held by other work until {_fmt(res_est)}")
        _add("resource", res_est, because, {"free_at": res_est, **held})
    else:
        _add("resource", res_est, f"{machine} is free from {_fmt(floor)}",
             {"free_at": res_est})

    # --- calendar (C1/C2) --------------------------------------------------
    cal_est = _first_moment_inside(open_windows, res_est)
    if cal_est is None:
        _add("calendar", None,
             f"{machine}'s calendar has no open time on or after {_fmt(res_est)}")
    elif cal_est > res_est:
        _add("calendar", cal_est,
             f"{machine} is closed until {_fmt(cal_est)}", {"opens_at": cal_est})
    else:
        _add("calendar", cal_est, f"{machine} is open at {_fmt(res_est)}",
             {"opens_at": cal_est})

    # --- chunkfit (C3) -----------------------------------------------------
    scan_from = cal_est if cal_est is not None else res_est
    free = _subtract(open_windows, occupied)
    fit, fit_facts = earliest_fit(free, scan_from, working_min,
                                  splittable=splittable,
                                  min_chunk_min=min_chunk_min)
    if fit is None:
        _add("chunkfit", None,
             "no run of open, unheld time long enough for this operation was "
             f"found on {machine}", fit_facts)
    elif fit > scan_from:
        # THREE different reasons an operation waits for a later window, and they
        # are three different sentences to a planner. Saying "only 6m remained"
        # about a 25-hour resumable operation would be arithmetic dressed as a
        # cause; the reason it could not open in that sliver is the min_chunk
        # floor, not the total.
        sw = fit_facts.get("short_window") or {}
        avail = sw.get("available_min")
        if sw.get("reason") == "below min_chunk":
            because = (f"the open stretches before {_fmt(fit)} were shorter than "
                       f"its {_dur(min_chunk_min)} minimum piece")
        elif sw and not splittable:
            # NAME THE WINDOW, not just its length. "only 3h23m remained" without
            # saying when is arithmetic a planner cannot check against the board;
            # with the instant, it is the exact fact that refutes the original
            # answer's "so it took the next opening".
            because = (f"it needs {_dur(working_min)} in one piece and {machine} "
                       f"had only {_dur(avail)} left when it came free at "
                       f"{_fmt(sw.get('start'))}")
        elif sw:
            because = (f"there was not enough open, unheld time on {machine} to "
                       f"carry its {_dur(working_min)} until {_fmt(fit)}")
        else:
            because = f"the first stretch long enough begins {_fmt(fit)}"
        # "...after maintenance" — the target sentence's closing clause. Stated
        # only when a DECLARED closure actually stands between the near miss and
        # the placement: a maintenance day that delayed nothing is not part of
        # the cause, and saying it would be the same over-claim in a new place.
        gap_from = (sw.get("end") if sw else scan_from)
        for cl in closures or []:
            cs, ce = cl.get("start"), cl.get("end")
            if cs is None or ce is None or gap_from is None:
                continue
            if cs < fit and ce > gap_from:
                fit_facts["closure"] = {"start": cs, "end": ce,
                                        "reason": cl.get("reason") or "closure"}
                break
        _add("chunkfit", fit, because, fit_facts)
    else:
        _add("chunkfit", fit, f"it fits from {_fmt(scan_from)}", fit_facts)

    # --- binding, runner-up, verdict ---------------------------------------
    #
    # A family PUSHED if its estimate strictly exceeds every estimate before it
    # in ladder order. The last pusher carries the maximum and is, by
    # construction, the EARLIEST family attaining it — which is exactly the tie
    # rule the docstring states, arrived at without a separate scan. The
    # second-to-last pusher is the runner-up: the largest estimate strictly
    # below the maximum, and therefore what would bind next if the binding
    # cause were lifted.
    pushers: list[Estimate] = []
    running: Optional[datetime] = None
    for e in estimates:
        if not e.computed:
            continue
        if running is None or e.est > running:      # type: ignore[operator]
            pushers.append(e)
            running = e.est
    binding: Optional[Estimate] = pushers[-1] if pushers else None
    runner_up: Optional[Estimate] = pushers[-2] if len(pushers) >= 2 else None
    verdict = "undetermined"
    slack: Optional[float] = None
    if binding is not None and actual_start is not None:
        delta = _minutes(binding.est, actual_start)   # type: ignore[arg-type]
        if abs(delta) <= tolerance_min:
            verdict = "could_not"
        elif delta > tolerance_min:
            verdict = "chose"
            slack = round(delta, 3)
        else:
            # The actual start precedes every computed lower bound. That is not a
            # planner-facing verdict, it is a contradiction in our own reading —
            # say nothing rather than assert either branch (R-AI3(1)).
            verdict = "undetermined"
    return BlockerAnalysis(
        order=order, op_seq=op_seq, machine=machine,
        actual_start=actual_start, actual_end=actual_end,
        working_min=working_min, splittable=splittable,
        min_chunk_min=min_chunk_min, estimates=tuple(estimates),
        binding=binding, runner_up=runner_up, verdict=verdict,
        slack_min=slack, chosen_driver=chosen_driver,
        pushers=tuple(pushers))


def _fmt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt is not None else "?"


def _dur(minutes: Optional[float]) -> str:
    """Planner-facing duration: '6h51m', '3h', '45m'. The target sentence's
    register — a planner reads hours, never 411 minutes."""
    if minutes is None:
        return "?"
    m = int(round(float(minutes)))
    if m < 60:
        return f"{m}m"
    h, r = divmod(m, 60)
    return f"{h}h" if r == 0 else f"{h}h{r:02d}m"
