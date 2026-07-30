"""THE COUNTERFACTUAL — what would have to be DIFFERENT? (Session 4B.16 Item 1.)

4B.14 built the blocker analysis: an earliest-feasible-start per docs/05 family,
the one that BINDS named, and COULDN'T distinguished from CHOSE-NOT-TO. This is
its INVERSE, over the SAME computed bounds and with NO NEW ONES: take the family
that binds and report the change that would move that bound, with its threshold
and the arithmetic.

The worked specimen the copy is written against (op20, binding family C3
chunk-fit: 431 working minutes needed in one piece, 294 left on PAINT-01 after
op10 finished at 14:06):

    op20 needs 431 minutes in one piece and Tuesday had 294 left after op10.

    To fit Tuesday, one of these has to change:
      min_chunk_minutes <= 215 on this operation      [C3, docs/06 §5.3]
      op10 finishes by 11:49 instead of 14:06         [A1/A2]
      431 contiguous minutes free on an eligible machine  [B1]
      PAINT-01's Tuesday window extended by 137 minutes   [C1/C2]

    If min_chunk changed, the next bound would be an earlier step (A1/A2) at
    2026-01-13 14:06 — so this removes the barrier, it does not place the
    operation there.

THE HARD RULE — A NECESSARY CONDITION, NEVER A SUFFICIENT ONE
-------------------------------------------------------------
Each lever is computed to REMOVE THE BINDING BOUND, and removing a bound is not
placing an operation. Whether the solver would then put it there is a question
only a re-solve can answer, and R-AI4 forbids one. So every counterfactual NAMES
THE NEXT BOUND that would apply once the barrier is gone, and the authored copy
says "removes the barrier" — never "then it can go there".

The disjunction as a WHOLE is the necessary condition: without one of these
changing, the operation cannot start earlier. That claim is only as complete as
the family census behind it, which is why ``uncomputed`` (docs/05 B3/B5, B7/B8,
C4, F3 — carried verbatim from the blocker analysis) travels with every answer.
A counterfactual that ignores them is exactly as partial as the explanation was.

WHERE A RELAXATION CANNOT BE COMPUTED, IT SAYS SO
-------------------------------------------------
``unpriceable`` follows the precedent 4B.14 set on changeover: the setup this
operation would need at an EARLIER position depends on what would then precede
it there, which is a different schedule. Pricing that is a re-solve wearing an
estimate's clothes, so it is named and not attempted. The same applies to the
`chose` verdict's only real lever — the objective — which is why a chosen
placement gets a counterfactual that honestly has no threshold in it.

EVERY THRESHOLD IS VERIFIED AGAINST THE SAME SCAN THAT PRODUCED THE BOUND.
``blocker_analysis.earliest_fit`` is re-run under each hypothetical, and a lever
whose threshold does not actually move the fit is DROPPED rather than stated.
That is what stops this module from being arithmetic about arithmetic: a number
here is a number the same function agrees with.

PURE: plain data in, a dataclass out. No I/O, no snapshot reader, no model. The
Explainer assembles the inputs (it already does, for the blocker analysis) and
the renderer voices the output.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from mre.modules.blocker_analysis import (
    FAMILY_LADDER,
    BlockerAnalysis,
    _dur,
    _first_moment_inside,
    _first_moment_outside,
    _fmt,
    _minutes,
    _subtract,
    earliest_fit,
)

#: docs/06 sections where each family's INPUT is declared — the submission column
#: a planner would actually have to change. A lever that names a docs/05 family
#: without naming where the field lives is advice nobody can act on.
#:
#: THESE ARE AUTHORED CONSTANTS ON PURPOSE, NOT A MISSED REFACTOR (Errand 4B.16a
#: A3). docs/07 §5a.48 is the standing prescription: until a CITATION KIND for
#: spec passages exists — a contract change, therefore a reviewed vocabulary-class
#: change — "an answer whose strongest evidence is a spec passage should route that
#: reference through authored copy rather than let synthesis carry it under the
#: interpretive label." Measured there: four claims quoting docs/05 correctly all
#: landed `[synthesis — my reading, no record states this]`, because the corpus and
#: catalog tools return SPEC TEXT and `claim_verifier` has nothing to re-fetch. So
#: a verbatim quote of the constitution reads WEAKER than an inference over
#: placements, which inverts the evidence hierarchy §5a.43 rules on.
#:
#: Reading these out of the 4B.15 corpus index instead would look like an
#: improvement and would re-open §5a.48 for this route: the reference would become
#: a corpus-grounded claim and take the weakest label the surface has. Do not do it
#: before the citation kind lands.
SPEC_OF: dict[str, str] = {
    "release": "docs/06 §5.1 orders.csv release_date",
    "precedence": "docs/06 §5.3 routing_lines.csv sequence",
    "pin": "docs/06 §5.12 locks.csv",
    "resource": "docs/06 §5.3 routing_lines.csv alternative rows",
    "calendar": "docs/06 §5.6 calendars.csv exception rows",
    "chunkfit": "docs/06 §5.3 routing_lines.csv splittable / min_chunk_minutes",
}

#: Relaxations this module will NOT compute, and why. Same discipline as
#: ``blocker_analysis.UNCOMPUTED_FAMILIES``: named on every answer rather than
#: silently absent.
UNPRICEABLE: tuple[tuple[str, str], ...] = (
    ("B7/B8", "sequence-dependent changeover — the setup this operation would "
              "need at an earlier position depends on what would precede it "
              "there, which is a different schedule (R-AI4)"),
)

#: The objective's own relaxation, named on a `chose` verdict for the same
#: reason: "what would make the solver prefer an earlier slot" is a re-solve.
UNPRICEABLE_OBJECTIVE: tuple[str, str] = (
    "the objective —",
    "why the solver PREFERRED a later slot — a different optimization, and "
    "pricing the change means re-solving (R-AI4)",
)


@dataclass(frozen=True)
class Lever:
    """One change that would move the binding bound, with its threshold."""

    key: str
    #: The docs/05 family this change acts on (the analysis's own citation).
    citation: str
    #: Where the input is declared in a submission (``SPEC_OF``), or "".
    spec: str
    #: The change itself, in planner language, carrying its threshold.
    statement: str
    #: What it buys, with the arithmetic that makes it true.
    effect: str
    threshold_min: Optional[float] = None
    #: True when re-running the same scan under this hypothetical actually moved
    #: the fit. An unverified lever is never stated (see ``build``).
    verified: bool = True


@dataclass(frozen=True)
class Counterfactual:
    """The answer to 'what would have to change?' for ONE operation."""

    order: str
    op_seq: Optional[int]
    machine: str
    #: Mirrors the blocker analysis: could_not | chose | undetermined.
    verdict: str
    needed_min: float
    splittable: bool
    min_chunk_min: Optional[float]
    binding_family: Optional[str] = None
    binding_citation: str = ""
    binding_label: str = ""
    binding_at: Optional[datetime] = None
    #: The near-miss window the arithmetic lives in (chunk-fit bindings):
    #: {start, end, available_min, needed_min}. None for the other families.
    window: Optional[dict] = None
    levers: tuple[Lever, ...] = ()
    #: What would bind once the barrier is removed — the reason a lever is a
    #: necessary condition and never a promise. {family, citation, label, at}.
    next_bound: Optional[dict] = None
    #: Eligible machines other than this one, and what the scan found on them.
    alternatives: tuple[dict, ...] = ()
    #: True when capability resolution says this is the ONLY machine that can
    #: run the operation — a fact worth stating outright, not an empty list.
    only_eligible: bool = False
    #: None when eligibility could not be resolved at all (never an empty list
    #: masquerading as "no alternatives").
    eligibility_known: bool = True
    #: A DECLARED closure standing between the near-miss window and where the
    #: operation sits, when the analysis found one. Reported, never offered as
    #: a lever — see ``build``.
    closure: Optional[dict] = None
    slack_min: Optional[float] = None
    chosen_driver: Optional[str] = None
    unpriceable: tuple[tuple[str, str], ...] = UNPRICEABLE
    uncomputed: tuple[tuple[str, str], ...] = ()
    #: Levers computed and DROPPED because re-running the scan did not confirm
    #: them. Counted, never silently discarded.
    dropped: int = 0

    @property
    def has_levers(self) -> bool:
        return bool(self.levers)


def _label_of(family: str) -> tuple[str, str]:
    for key, citation, label in FAMILY_LADDER:
        if key == family:
            return citation, label
    return "", family


def _span(minutes: Optional[float]) -> str:
    """An ELAPSED amount — how much earlier something would have to happen.
    Days past 48h, because "195h06m earlier" is a number nobody can picture.
    Working amounts keep ``_dur``'s hours-only rule (a day of work is a day of
    what?); this is wall-clock, where a day is unambiguous."""
    if minutes is None:
        return "?"
    m = int(round(float(minutes)))
    if m < 2880:
        return _dur(m)
    d, rem = divmod(m, 1440)
    h = rem // 60
    return f"{d}d" if not h else f"{d}d {h}h"


def _when(dt: Optional[datetime]) -> str:
    """A timestamp that says WHICH DAY it is (4B.15 Item 0: a five-Tuesday
    horizon is why a weekday alone is not an anchor)."""
    return dt.strftime("%a %Y-%m-%d %H:%M") if dt is not None else "?"


def resumable_fit(free: list[tuple[datetime, datetime]], at: datetime,
                  working_min: float, min_chunk_min: Optional[float]):
    """``earliest_fit`` for a SPLITTABLE operation, with R-C3's degenerate-split
    rule applied exactly as the SolverBuilder, the Validator and the blocker
    analysis apply it.

    This is the whole reason the min_chunk lever's ceiling is a real number.
    ``earliest_fit`` itself does not know about R-C3 — its caller applies it —
    so verifying a proposed min_chunk without it would happily confirm a value
    at which the solver treats the operation as atomic again, and the answer
    would state a change that does not work."""
    from mre.modules.calendar_utils import is_effectively_resumable
    return earliest_fit(
        free, at, working_min,
        splittable=is_effectively_resumable(True, working_min,
                                            float(min_chunk_min or 0.0)),
        min_chunk_min=min_chunk_min)


def _fits_at(free: list[tuple[datetime, datetime]], at: datetime,
             working_min: float, *, splittable: bool,
             min_chunk_min: Optional[float], tolerance_min: float) -> bool:
    """Does the WHOLE operation open at ``at`` under this hypothetical? The same
    scan the bound came from, re-run — never a second opinion about it."""
    if splittable:
        start, _facts = resumable_fit(free, at, working_min, min_chunk_min)
    else:
        start, _facts = earliest_fit(free, at, working_min, splittable=False,
                                     min_chunk_min=min_chunk_min)
    return start is not None and _minutes(at, start) <= tolerance_min


def _extend_window(open_windows: list[tuple[datetime, datetime]],
                   end: datetime,
                   minutes: float) -> list[tuple[datetime, datetime]]:
    """The machine's calendar with the window ending at ``end`` running longer —
    the C1/C2 hypothetical, expressed as data rather than as a sentence."""
    out: list[tuple[datetime, datetime]] = []
    for s, e in open_windows:
        out.append((s, e + timedelta(minutes=minutes)) if e == end else (s, e))
    return out


def _tail_ladder(floor: datetime, *,
                 open_windows: list[tuple[datetime, datetime]],
                 occupied: list[tuple[datetime, datetime]],
                 free: list[tuple[datetime, datetime]],
                 working_min: float, splittable: bool,
                 min_chunk_min: Optional[float],
                 tolerance_min: float) -> Optional[dict]:
    """What binds at ``floor`` once an EARLIER family has been relaxed.

    The same three primitives the analysis uses, in the same order — resource,
    then calendar, then chunk-fit — so the next bound is COMPUTED rather than
    assumed to be the runner-up. It matters: relaxing precedence can expose a
    chunk-fit the runner-up never mentioned, and promising the runner-up would
    be a claim about a placement nobody checked.
    """
    res = _first_moment_outside(occupied, floor)
    if res > floor + timedelta(minutes=tolerance_min):
        return _bound("resource", res)
    cal = _first_moment_inside(open_windows, res)
    if cal is None:
        return None
    if cal > res + timedelta(minutes=tolerance_min):
        return _bound("calendar", cal)
    fit, _facts = earliest_fit(free, cal, working_min, splittable=splittable,
                               min_chunk_min=min_chunk_min)
    if fit is not None and fit > cal + timedelta(minutes=tolerance_min):
        return _bound("chunkfit", fit)
    return None


def _bound(family: str, at: Optional[datetime]) -> dict:
    citation, label = _label_of(family)
    return {"family": family, "citation": citation, "label": label, "at": at}


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------

def build(analysis: BlockerAnalysis, *,
          open_windows: list[tuple[datetime, datetime]],
          occupied: list[tuple[datetime, datetime]],
          alternatives: Optional[list[dict]] = None,
          eligibility_known: bool = True,
          tolerance_min: float = 1.0) -> Counterfactual:
    """The counterfactual for one analyzed operation.

    ``alternatives`` is one entry per OTHER capability-eligible machine:
    ``{"machine": name, "free": [(start, end), …]}`` — its open calendar minus
    everything already placed on it. The caller resolves eligibility (it is the
    layer that knows the snapshot); this module only does the arithmetic.

    ``eligibility_known`` is False when capability resolution failed, so the
    answer can say it does not know rather than report "no alternatives".
    """
    free = _subtract(open_windows, occupied)
    W = analysis.working_min
    binding = analysis.binding
    common = dict(
        order=analysis.order, op_seq=analysis.op_seq, machine=analysis.machine,
        needed_min=W, splittable=analysis.splittable,
        min_chunk_min=analysis.min_chunk_min,
        chosen_driver=analysis.chosen_driver,
        uncomputed=analysis.uncomputed,
        eligibility_known=eligibility_known,
    )

    # -- the two verdicts with no binding bound to relax --------------------
    if analysis.verdict == "chose" or binding is None or analysis.verdict == "undetermined":
        return Counterfactual(
            verdict=analysis.verdict,
            binding_family=binding.family if binding else None,
            binding_citation=binding.citation if binding else "",
            binding_label=binding.label if binding else "",
            binding_at=binding.est if binding else None,
            slack_min=analysis.slack_min,
            unpriceable=(UNPRICEABLE + (UNPRICEABLE_OBJECTIVE,)
                         if analysis.verdict == "chose" else UNPRICEABLE),
            **common)

    alts = _scan_alternatives(alternatives or [], analysis, tolerance_min,
                              floor=_upstream_floor(analysis))
    levers: list[Lever] = []
    dropped = 0
    window: Optional[dict] = None

    fam = binding.family
    if fam == "chunkfit":
        window, levers, dropped = _chunkfit_levers(
            analysis, binding, free, open_windows, occupied, alts,
            tolerance_min)
        next_bound = (_bound(analysis.runner_up.family, analysis.runner_up.est)
                      if analysis.runner_up is not None else None)
    else:
        # THE NEXT BOUND IS COMPUTED FIRST, and the levers' thresholds are
        # measured against IT rather than against the runner-up. Otherwise a
        # lever could say "up to 6h earlier, where precedence takes over" in
        # the same answer whose closing line says chunk-fit binds two hours
        # before that — two figures from one paragraph, disagreeing.
        floor = analysis.runner_up.est if analysis.runner_up is not None else None
        next_bound = None
        if floor is not None:
            next_bound = _tail_ladder(
                floor, open_windows=open_windows, occupied=occupied, free=free,
                working_min=W, splittable=analysis.splittable,
                min_chunk_min=analysis.min_chunk_min,
                tolerance_min=tolerance_min) or _bound(
                    analysis.runner_up.family, analysis.runner_up.est)
        levers, dropped = _upstream_levers(analysis, binding, alts,
                                           next_at=(next_bound or {}).get("at"))

    # A DECLARED CLOSURE IS REPORTED AND NOT PRICED. Lifting a maintenance day
    # would plainly move this operation, so leaving it unmentioned would be a
    # hole in the disjunction — but pricing it means asserting what the
    # machine's open hours WOULD be on a day the calendar says it is shut, and
    # that is an invention, not a reading. Named, with the reason.
    closure = (binding.facts or {}).get("closure")

    return Counterfactual(
        verdict=analysis.verdict,
        binding_family=fam, binding_citation=binding.citation,
        binding_label=binding.label, binding_at=binding.est,
        closure=closure,
        window=window, levers=tuple(levers), next_bound=next_bound,
        alternatives=tuple(alts),
        only_eligible=bool(eligibility_known and not alts),
        dropped=dropped, **common)


def _upstream_floor(analysis: BlockerAnalysis) -> Optional[datetime]:
    """The bound a DIFFERENT MACHINE would still be subject to: release,
    precedence, the frozen boundary, the pin.

    Moving an operation to another lane changes B1 and C1/C2 and nothing else.
    Scanning an alternative from the beginning of its calendar instead would
    report open time before the order was even released — a true statement about
    the machine and a false one about the operation."""
    ests = [e.est for e in analysis.estimates
            if e.computed and e.family in ("release", "precedence", "frozen",
                                           "pin")]
    return max(ests) if ests else None


def _scan_alternatives(alternatives: list[dict], analysis: BlockerAnalysis,
                       tolerance_min: float,
                       floor: Optional[datetime] = None) -> list[dict]:
    """The B1 lever, COMPUTED: for each other eligible machine, the earliest it
    could carry the WHOLE operation, and whether that is earlier than where the
    operation actually sits.

    Stated as a fact about open, unheld time — never as "it could go there".
    Which machine the solver would choose is an objective question, and this
    module does not answer objective questions."""
    out: list[dict] = []
    for alt in alternatives:
        machine = alt.get("machine")
        free = alt.get("free") or []
        if not machine:
            continue
        starts = [s for s, _e in free]
        origin = max(floor, min(starts)) if (floor and starts) else (
            floor or min(starts, default=None))
        fit = None
        if origin is not None:
            fit, _facts = earliest_fit(
                free, origin, analysis.working_min,
                splittable=analysis.splittable,
                min_chunk_min=analysis.min_chunk_min)
        earlier = (fit is not None and analysis.actual_start is not None
                   and _minutes(fit, analysis.actual_start) > tolerance_min)
        out.append({"machine": machine, "earliest": fit, "earlier": earlier})
    return out


def _chunkfit_levers(analysis: BlockerAnalysis, binding, free, open_windows,
                     occupied, alts: list[dict],
                     tolerance_min: float) -> tuple[Optional[dict], list[Lever],
                                                    int]:
    """The four levers of the worked specimen — the shape of a C3 counterfactual.

    Every one of them is a way of making the same inequality true: the operation
    needs ``W`` minutes and the near-miss window has ``A``. Shrink the piece it
    must place at once, arrive earlier, find room elsewhere, or make the window
    longer. Each is verified by re-running the fit, and dropped if it does not."""
    sw = (binding.facts or {}).get("short_window") or {}
    win_start, win_end = sw.get("start"), sw.get("end")
    avail = sw.get("available_min")
    W = analysis.working_min
    levers: list[Lever] = []
    dropped = 0
    window = ({"start": win_start, "end": win_end, "available_min": avail,
               "needed_min": W} if win_start and win_end and avail is not None
              else None)

    def _keep(lever: Lever, ok: bool) -> None:
        nonlocal dropped
        if ok:
            levers.append(lever)
        else:
            dropped += 1

    # -- (1) C3: the piece it must place at once ---------------------------
    # R-C3's degenerate-split rule is the ceiling: an operation splits only if
    # its duration is at least TWICE the minimum piece, so no min_chunk above
    # W/2 makes it resumable at all. The window is the other ceiling — the first
    # piece has to fit in what is left.
    if window is not None:
        ceiling = min(math.floor(W / 2.0), math.floor(float(avail)))
        current = analysis.min_chunk_min
        proposes = ceiling >= 1 and (not analysis.splittable
                                     or (current or 0) > ceiling)
        if proposes:
            ok = _fits_at(free, win_start, W, splittable=True,
                          min_chunk_min=float(ceiling),
                          tolerance_min=tolerance_min)
            statement = (
                f"op{analysis.op_seq} declared splittable with a minimum "
                f"piece of {ceiling:g} minutes or less"
                if not analysis.splittable else
                f"op{analysis.op_seq}'s min_chunk_minutes lowered from "
                f"{current:g} to {ceiling:g} or less")
            effect = (
                f"the run phase becomes resumable, so the {_dur(avail)} still "
                f"open is enough to START it — R-C3 caps the piece at half the "
                f"{_dur(W)} it needs ({W:g}/2 = {math.floor(W / 2.0):g})"
                if not analysis.splittable else
                f"a piece that small fits the {_dur(avail)} still open, so it "
                f"can OPEN there and finish in a later window; at "
                f"{current:g} it cannot start at all")
            _keep(Lever(
                key="min_chunk", citation="C3", spec=SPEC_OF["chunkfit"],
                statement=statement, effect=effect,
                threshold_min=float(ceiling), verified=ok), ok)

    # -- (2) A1/A2: arrive earlier -----------------------------------------
    pred = analysis.est_of("precedence")
    if window is not None and pred is not None and pred.computed:
        need_by = win_end - timedelta(minutes=W)
        shift = _minutes(need_by, pred.est)
        if shift > tolerance_min:
            ok = _fits_at(free, need_by, W, splittable=analysis.splittable,
                          min_chunk_min=analysis.min_chunk_min,
                          tolerance_min=tolerance_min)
            step = (f"op{pred.facts.get('op_seq')}"
                    if pred.facts.get("op_seq") is not None else "the step before it")
            _keep(Lever(
                key="predecessor", citation="A1/A2",
                spec=SPEC_OF["precedence"],
                statement=f"{step} finishes by {_fmt(need_by)} instead of "
                          f"{_fmt(pred.est)} ({_span(shift)} earlier)",
                effect=(f"that leaves the whole {_dur(W)} before "
                        f"{analysis.machine} closes at "
                        f"{win_end.strftime('%H:%M')}"),
                threshold_min=shift, verified=ok), ok)

    # -- (3) B1: room somewhere else ---------------------------------------
    lever = _alternatives_lever(analysis, alts)
    if lever is not None:
        levers.append(lever)

    # -- (4) C1/C2: a longer window ----------------------------------------
    if window is not None:
        deficit = W - float(avail)
        if deficit > tolerance_min:
            extended = _extend_window(open_windows, win_end, deficit)
            ok = _fits_at(_subtract(extended, occupied), win_start, W,
                          splittable=analysis.splittable,
                          min_chunk_min=analysis.min_chunk_min,
                          tolerance_min=tolerance_min)
            _keep(Lever(
                key="calendar", citation="C1/C2", spec=SPEC_OF["calendar"],
                statement=f"{analysis.machine}'s "
                          f"{win_start.strftime('%A')} window extended by "
                          f"{_dur(deficit)} (past "
                          f"{win_end.strftime('%H:%M')})",
                effect=(f"declared overtime or a longer shift — "
                        f"{_dur(avail)} open plus {_dur(deficit)} is the "
                        f"{_dur(W)} it needs"),
                threshold_min=deficit, verified=ok), ok)
    return window, levers, dropped


def _upstream_levers(analysis: BlockerAnalysis, binding,
                     alts: list[dict],
                     next_at: Optional[datetime] = None) -> tuple[list[Lever],
                                                                  int]:
    """The levers for a bound that is not the fit: a date, a predecessor, a
    holder, a calendar, a pin, the frozen boundary.

    These share one shape. The bound stands at T, the next bound stands at T0,
    and the change is worth exactly T − T0 — beyond that it buys nothing,
    because the next bound is already waiting. Naming that ceiling is the honest
    form of "how much earlier can this go", and the ceiling is measured against
    the COMPUTED next bound so the lever and the closing sentence cannot state
    different instants."""
    ceiling = (_minutes(next_at, binding.est)
               if next_at is not None and binding.est is not None else None)
    if ceiling is not None and ceiling <= 0:
        ceiling = None
    gain = f"moves it up to {_span(ceiling)} earlier" if ceiling else \
        "moves it earlier by however much it moves; nothing else I compute " \
        "binds below it"
    fam = binding.family
    levers: list[Lever] = []

    if fam == "release":
        levers.append(Lever(
            key="release", citation="A4", spec=SPEC_OF["release"],
            statement=f"the order's release date moves earlier than "
                      f"{_fmt(binding.est)}",
            effect=gain, threshold_min=ceiling))
    elif fam == "precedence":
        step = (f"op{binding.facts.get('op_seq')}"
                if binding.facts.get("op_seq") is not None else "the step before it")
        levers.append(Lever(
            key="predecessor", citation="A1/A2", spec=SPEC_OF["precedence"],
            statement=f"{step} finishes earlier than {_fmt(binding.est)}",
            effect=gain, threshold_min=ceiling))
        lag = float(binding.facts.get("min_lag_min") or 0.0)
        if lag > 0:
            levers.append(Lever(
                key="min_lag", citation="A1/A2", spec=SPEC_OF["precedence"],
                statement=f"the declared {lag:g}-minute minimum lag after "
                          f"{step} is reduced",
                effect=f"each minute removed is a minute earlier this "
                       f"operation may open, up to {_span(lag)}",
                threshold_min=lag))
    elif fam == "resource":
        held = binding.facts.get("order")
        who = f"{held} " if held else ""
        levers.append(Lever(
            key="holder", citation="B1", spec=SPEC_OF["resource"],
            statement=f"the work holding {analysis.machine} ({who}"
                      f"finishing {_fmt(binding.est)}) releases it earlier",
            effect=gain, threshold_min=ceiling))
    elif fam == "calendar":
        levers.append(Lever(
            key="calendar", citation="C1/C2", spec=SPEC_OF["calendar"],
            statement=f"{analysis.machine} is open before "
                      f"{_fmt(binding.est)} — a declared addition on that day",
            effect=gain, threshold_min=ceiling))
    elif fam == "pin":
        levers.append(Lever(
            key="pin", citation="A7/F1", spec=SPEC_OF["pin"],
            statement=f"the pin holding this operation at {_fmt(binding.est)} "
                      f"is lifted or moved",
            effect=gain, threshold_min=ceiling))
    elif fam == "frozen":
        levers.append(Lever(
            key="frozen", citation="R-F1", spec="",
            statement=f"the frozen boundary at {_fmt(binding.est)} is moved "
                      f"back (R-F1: a thaw makes standing pins, not free work)",
            effect=gain, threshold_min=ceiling))

    lever = _alternatives_lever(analysis, alts)
    if lever is not None:
        levers.append(lever)
    return levers, 0


def _alternatives_lever(analysis: BlockerAnalysis,
                        alts: list[dict]) -> Optional[Lever]:
    """The B1 lever as a computed fact about the other eligible machines.

    Three different sentences, because they are three different facts: one
    machine could take the whole operation earlier, none could, or the operation
    has nowhere else to go at all. The last one is the strongest and the easiest
    to leave unsaid."""
    earlier = [a for a in alts if a.get("earlier")]
    if not earlier:
        # NOT a lever. "No other machine could take it earlier either" is a
        # finding about the plant, and listing it among the things that could
        # change would be offering a door that is already shut. The renderer
        # states it from ``alternatives``/``only_eligible`` instead.
        return None
    first = min(earlier, key=lambda a: a["earliest"])
    names = ", ".join(a["machine"] for a in earlier)
    return Lever(
        key="alternate", citation="B1", spec=SPEC_OF["resource"],
        statement=f"the operation runs on {names} instead",
        effect=(f"{first['machine']} has {_dur(analysis.working_min)} of "
                f"open, unheld time from {_when(first['earliest'])} — whether "
                f"the solver would prefer it is a cost question I cannot "
                f"answer without re-solving"),
        threshold_min=None)
