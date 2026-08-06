"""R-SP1 — THE SOLVE-PROGRESS LEDGER.

CP-SAT's incumbent trail, told against itself and against nothing else.

WHY THIS EXISTS. The optimizer's contribution was invisible. A board published
one number — the ledger — and nothing anywhere said what the search had done to
reach it. The solver had in fact been streaming its improving solutions into the
evidence stream since ``solve_runner`` was written (one ``improving_solution``
Event per incumbent, carrying a counter and an objective), but with **no elapsed
time, no collection, no terminal bound beside them and no reader** — a per-record
ping nobody could assemble into a story. This module is the collection, the
story, and the refusals that bound it.

WHICH RECORD KIND, AND WHAT WAS REFUSED. docs/02 §4 offers six, and the trail
decomposes into three parts that each already have a home — the same
decomposition S-02 made for the gate's verdict, for the same reasons:

  * the TRAIL ITSELF is an ordered sequence of (objective, elapsed) pairs. It is
    free structure, not a scalar, so it rides a §4.5 Event whose ``status_text``
    is a status string and whose payload carries the substance (§5: "codes are
    for routing, payloads are for substance"). §4.5 anticipated exactly this
    record — "long solves stream improving solutions and telemetry here" — and
    the in-repo precedent is the M6 ``solve_complete`` Event this one sits
    beside;
  * the SCALARS the trail summarises are numbers with a unit and an exact
    decomposition, so they are §4.4 Metrics. ``solve.first_incumbent`` is
    recorded as the ROLLUP of ``solve.final_incumbent`` and
    ``solve.incumbent_improvement``, which is true by construction and is
    verified by the consolidator rather than asserted here. That rollup is also
    what makes R-SP1 clause (2) STRUCTURAL rather than a matter of wording:
    improvement is *defined* as first minus final, so no other subtrahend — no
    customer baseline, no planner's plan — can enter it and still decompose;
  * the FILE (``solve_progress.json``) is an output with a reference and a hash —
    §4.6 Artifact, registered through verb 7 by :func:`write_solve_progress_json`,
    and hashed FROM THE FILE. (S-02 §5's defect, now a named class: ``write_text``
    newline-translates on Windows, so a digest taken from the string we meant to
    write does not verify against the artifact it names.)

REFUSED, and each for its own reason:
  * a **Finding** — every code in the vocabulary names a defect. A search that
    found one plan and could not improve it is not one; clause (4) says a flat
    story is a true story, and wearing a finding code would turn a fact into a
    complaint. (The already-shipped ``SOLVER_NONOPTIMAL`` Finding stays exactly
    where it is: an unclosed gap IS a defect-shaped fact about the plan, and it
    is a different statement from the trail.);
  * a **Decision** — an incumbent is not a deliberation. There are no
    alternatives to enumerate, and ``driver`` is mandatory-exactly-one over codes
    that every one of them name SCHEDULING causes; "CP-SAT's search improved" is
    not one, and inventing a code for it would claim the solver chose between
    options it can name. Recording a search step as a Decision claims
    deliberation that did not happen — S-02's phrasing, and the same fusion;
  * a **Metric for the trail itself** — ``value`` is a float. A trail is a
    sequence;
  * a **new record type** — nothing here needs one.

NO EVIDENCE-SIDE ``CONTRACT_VERSION`` BUMP IS OWED: docs/02 §4.2 says that
constant versions the SCHEDULE DOCUMENT. The document does gain a block for this
(1.16, ``solver.progress``), and that bump is owed by the block, not by these
records.

R-DP12 IS THE REASON THERE IS NO DOLLAR SIGN IN THIS FILE. A trail point is a
CP-SAT objective value — the scaled integer objective, which R-DP12 clause (3)
admits only as *labelled solver telemetry* and clause (2) forbids from reaching a
planner surface as money. It is not proportional to the ledger: R-DP12's own
specimen is a zero-move accept whose ledger did not change by a cent while the
scaled objective moved by 7,014,821. So the improvement renders as a PERCENTAGE
of the first incumbent — the same objective-space ratio the shipped gap rider
already puts in front of a planner — and the ledger, the one comparable number,
belongs to the FINAL plan alone and is never differenced against an earlier
incumbent. See R-SP1 clause (3).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from mre.contracts.entities import EntityRef
from mre.contracts.vocabularies import RecordTier

#: ``status_text`` for the trail Event. ONE constant, read by the two paths that
#: write it and by the assembler that reads it — a second spelling of this string
#: is a second definition of the record (S-02's discipline, same shape).
SOLVE_PROGRESS_STATUS = "solve_progress"

#: The stage this trail belongs to. An R-SC3 solve runs two, and only stage 1
#: minimizes COST; stage 2 minimizes a sum of START MINUTES. A trail that
#: concatenated them would show a cost search collapsing into a minute count and
#: call the difference improvement. R-SP1 clause (7).
TRAIL_STAGE = "cost"

#: Metric names. ``solve.first_incumbent`` is the rollup; the two below are its
#: components and are emitted EVEN AT ZERO (docs/02 §4.4 — a component that
#: appears only when non-empty cannot be verified as a set, and an absent
#: component reads as an unasked question rather than a measured nought). A flat
#: trail therefore emits ``solve.incumbent_improvement`` at 0.0 and says so.
METRIC_FIRST = "solve.first_incumbent"
METRIC_FINAL = "solve.final_incumbent"
METRIC_IMPROVEMENT = "solve.incumbent_improvement"
METRIC_COUNT = "solve.incumbents_found"

#: The unit every trail figure carries. NOT dollars, and named so at the record
#: level rather than only in prose — a reader who takes one of these numbers
#: without reading this module still sees that it is not currency.
OBJECTIVE_UNIT = "objective_units"

#: R-SP1 clause (2), VERBATIM, in the one place both the answer surfaces and the
#: cockpit read it from. The clause forbids stating or IMPLYING savings against
#: the customer's current process, a human planner, or any baseline the solver
#: did not itself produce — and a bare "improved 34%" implies exactly that to a
#: reader who has not been told what the comparison is. So the comparison is
#: named every time the figure is shown.
CLAUSE_2_LABEL = (
    "This compares the solver's own first workable plan with the plan it "
    "finished on. It is not a comparison with your current schedule, your "
    "planners, or any other baseline — the solver's first plan is not what a "
    "planner would have made."
)

#: R-SP1 clause (3): the trail is in the solver's own units, so the reader is
#: told what they are and where the money went instead.
CLAUSE_3_LABEL = (
    "The figures in this trail are the solver's own internal cost measure, not "
    "dollars. The dollar figure for this plan is the ledger above; it belongs "
    "to the finished plan and is not differenced against an earlier one."
)

#: R-SP1 AMENDMENT 1 — the SAME clause, on a trail whose endpoints are priced.
#:
#: A separate string rather than a conditional clause, because the two say
#: genuinely different things and a reader must be able to tell which regime
#: they are in. Here the two dollar figures ARE real ledger costs — that is what
#: the amendment admits — while the per-incumbent table below is still the
#: scaled objective and still may not wear a dollar sign. The sentence names
#: that boundary explicitly, because it is the one thing a reader could
#: reasonably get wrong when both measures are on one screen.
CLAUSE_3_LABEL_PRICED = (
    "Both dollar figures above are real ledger costs: the solver's first "
    "workable plan was priced by the same extractor that priced the finished "
    "plan, so their difference is ledger arithmetic end to end. The trail below "
    "is a different measure — the solver's own internal cost score, not "
    "dollars — and the two are never mixed."
)

#: The amendment's wall-cost disclosure, used only where it applies.
CAPTURE_NOTE_WALL = (
    "Capturing the first plan costs a moment of real time, and this solve was "
    "stopped by the wall clock rather than by its search budget — so the plan "
    "it finished on may differ slightly from an uncaptured run of the same "
    "search. Under a search budget there is no such effect."
)


def summarize(trail: list[dict]) -> dict:
    """The scalars a trail implies. Pure, and the ONE definition of them.

    Returns first/final/improvement (absolute and percent) and the flat flag.
    Every value is None on an empty trail — a solve that found nothing has no
    first plan, and 0.0 there would assert a plan worth nothing.
    """
    if not trail:
        return {"count": 0, "first": None, "final": None,
                "improvement_abs": None, "improvement_pct": None, "flat": False}
    first = float(trail[0]["objective"])
    final = float(trail[-1]["objective"])
    abs_imp = first - final
    # A percentage OF THE FIRST INCUMBENT — the denominator is named because
    # 4B.20's lesson is that a ratio names its own. None rather than 0.0 at a
    # zero first objective: the ratio is undefined there, not nil.
    pct = (abs_imp / abs(first) * 100.0) if abs(first) > 1e-9 else None
    return {"count": len(trail), "first": first, "final": final,
            "improvement_abs": abs_imp, "improvement_pct": pct,
            "flat": len(trail) == 1}


#: Metric names for the DOLLAR story (R-SP1 AMENDMENT 1). Deliberately distinct
#: from the objective-space set above, which STAYS as labelled solver telemetry:
#: two measures, two names, and no reader has to guess which one a number is.
METRIC_FIRST_COST = "solve.first_plan_cost"
METRIC_FINAL_COST = "solve.final_plan_cost"
METRIC_COST_IMPROVEMENT = "solve.plan_cost_improvement"
#: The unit that IS currency, named as plainly as `objective_units` is.
COST_UNIT = "currency"


def price_summary(first_cost, final_cost) -> dict:
    """The DOLLAR scalars, or an unpriced verdict. Pure, one definition.

    ``priced`` is the amendment's admissibility test rendered as a boolean: BOTH
    endpoints must be ledger-priced placements. One of the two missing is not a
    partial story, it is no story — a difference needs two real numbers, and
    inventing the other end is exactly what the amendment forbids.
    """
    if first_cost is None or final_cost is None:
        return {"priced": False, "first_plan_cost": None, "final_plan_cost": None,
                "dollar_improvement_abs": None, "dollar_improvement_pct": None}
    first, final = round(float(first_cost), 2), round(float(final_cost), 2)
    abs_imp = round(first - final, 2)
    pct = (abs_imp / abs(first) * 100.0) if abs(first) > 1e-9 else None
    return {"priced": True, "first_plan_cost": first, "final_plan_cost": final,
            "dollar_improvement_abs": abs_imp, "dollar_improvement_pct": pct}


def headline(summary: dict) -> str:
    """The authored story sentence for a trail, in ONE place.

    R-SP1 clause (2) fixes the FORM ("first plan found at X, improved to Z") and
    clause (4) fixes the flat case ("first plan found was not improved within
    budget") — a flat story is a true story, and it is told rather than hidden.
    The figures are the solver's own units per clause (3), so this sentence
    carries no currency symbol and says whose measure it is.

    Authored server-side for the same reason ``CostProof.chip`` is: two surfaces
    composing their own wording is two surfaces that can state different things.
    """
    n = summary.get("count") or 0
    if not n:
        return ("The solver found no workable plan for this window, so there is "
                "no search history to show.")
    # R-SP1 AMENDMENT 1 — DOLLARS WHEN BOTH ENDPOINTS ARE LEDGER-PRICED, and
    # only then. This branch states two real costs and their real difference;
    # every other branch below states the objective-space percentage exactly as
    # clause (3) has always required. Three generations of trail, each honest,
    # and the sentence never straddles them.
    if summary.get("priced"):
        fc = summary["first_plan_cost"]
        lc = summary["final_plan_cost"]
        if summary.get("flat"):
            return (f"The solver found one workable plan, costing ${lc:,.2f}, "
                    f"and did not improve on it within its budget.")
        d = summary["dollar_improvement_abs"]
        dp = summary.get("dollar_improvement_pct")
        if d <= 0:
            # Priced, more than one incumbent, and no cheaper ledger: the search
            # improved its own score without improving the bill. Said plainly
            # rather than rounded into a $0 saving nobody can act on.
            return (f"The solver's first workable plan would have cost "
                    f"${fc:,.2f}, and the plan it finished on costs ${lc:,.2f} "
                    f"— its later plans scored better on its own measure "
                    f"without costing less.")
        tail = f" — {dp:.1f}% less" if dp is not None else ""
        return (f"The solver's first workable plan would have cost ${fc:,.2f}; "
                f"the plan it finished on costs ${lc:,.2f}{tail}.")
    first, final = summary.get("first"), summary.get("final")
    if summary.get("flat"):
        return (f"The solver found one workable plan, scoring {first:,.0f} on "
                f"its own cost measure, and did not improve on it within its "
                f"budget.")
    pct = summary.get("improvement_pct")
    tail = (f" — {pct:.1f}% better by its own cost measure"
            if pct is not None else "")
    return (f"The solver's first workable plan scored {first:,.0f}; it finished "
            f"on a plan scoring {final:,.0f}{tail}.")


def progress_block_fields(
    trail: list[dict],
    *,
    best_bound: Optional[float],
    gap: Optional[float],
    window_key: Optional[str] = None,
    first_plan_cost: Optional[float] = None,
    final_plan_cost: Optional[float] = None,
    wall_truncated: bool = False,
) -> dict:
    """The ``SolveProgressBlock``'s content, composed ONCE.

    Two assemblers build the block from two different sources — the monolithic
    one reads the ``solve_progress`` Event out of evidence, the rolling one reads
    the trail off the completed ``RollingView`` — and a block composed twice is a
    block that can say two things. Only the SOURCE differs; the content comes
    from here.
    """
    s = dict(summarize(trail))
    s.update(price_summary(first_plan_cost, final_plan_cost))
    return {
        "stage": TRAIL_STAGE,
        "window_key": window_key,
        "incumbents": [
            {"index": int(i["index"]), "objective": float(i["objective"]),
             "elapsed_s": float(i["elapsed_s"])}
            for i in trail
        ],
        "count": s["count"],
        "first": s["first"],
        "final": s["final"],
        "improvement_abs": s["improvement_abs"],
        "improvement_pct": s["improvement_pct"],
        "flat": s["flat"],
        "best_bound": best_bound,
        "gap": gap,
        "objective_unit": OBJECTIVE_UNIT,
        "headline": headline(s),
        "clause_2_label": CLAUSE_2_LABEL,
        # The priced regime says something different and says so — see
        # CLAUSE_3_LABEL_PRICED for why this is a second string, not a branch.
        "clause_3_label": (CLAUSE_3_LABEL_PRICED if s["priced"]
                           else CLAUSE_3_LABEL),
        "priced": s["priced"],
        "first_plan_cost": s["first_plan_cost"],
        "final_plan_cost": s["final_plan_cost"],
        "dollar_improvement_abs": s["dollar_improvement_abs"],
        "dollar_improvement_pct": s["dollar_improvement_pct"],
        # The amendment's wall-cost disclosure, present ONLY where it applies:
        # capture costs wall time, and only a wall-stopped solve can have had
        # its outcome touched by that. Empty under a deterministic budget.
        "capture_note": (CAPTURE_NOTE_WALL
                         if (s["priced"] and wall_truncated) else ""),
    }


def emit_solve_progress(
    reporter,
    *,
    trail: list[dict],
    status: str,
    best_bound: Optional[float],
    gap: Optional[float],
    det_consumed: Optional[float] = None,
    det_budget: Optional[float] = None,
    window_key: Optional[str] = None,
    first_plan_cost: Optional[float] = None,
    final_plan_cost: Optional[float] = None,
    subjects: Optional[list[EntityRef]] = None,
) -> dict[str, Any]:
    """Write the solve-progress trail into the evidence store.

    ONE definition, called from both paths that solve for cost — the monolithic
    ``SolveRunner`` (which emits its own ``solve_complete``) and the rolling
    window solve in ``build_rolling_view`` (which emits its own, with the runner's
    reporter deliberately None). A record written on only one path would be a gap
    shaped exactly like the one it was built to close, which is the mistake S-02
    named at the gate's two exits.

    ``window_key`` is R-SP1 clause (1): on a rolling board the trail belongs to
    ONE window and is keyed to it, so no reader can sum two of them. None on a
    monolithic solve, which has no window to name.

    Returns the emitted records' ids so a caller can cite them.
    """
    s = summarize(trail)
    metric_ids: list[str] = []

    if s["count"]:
        # Components FIRST, then the rollup that references them — the
        # consolidator resolves `rollup_of` by record id, so the ids must exist.
        final_rec = reporter.record_metric(
            name=METRIC_FINAL, value=s["final"], unit=OBJECTIVE_UNIT,
            subjects=subjects or [], tier=RecordTier.SUPPORTING,
            message=("the objective of the plan this solve finished on "
                     "(solver units, not dollars)"),
        )
        imp_rec = reporter.record_metric(
            name=METRIC_IMPROVEMENT, value=s["improvement_abs"],
            unit=OBJECTIVE_UNIT, subjects=subjects or [],
            tier=RecordTier.SUPPORTING,
            message=("what the search took off its OWN first workable plan "
                     "(solver units, not dollars); 0.0 means it found one plan "
                     "and could not improve it"),
        )
        metric_ids = [final_rec.record_id, imp_rec.record_id]
        # THE ROLLUP IS WHAT MAKES CLAUSE (2) STRUCTURAL. first = final +
        # improvement decomposes exactly and the consolidator checks it, so
        # `improvement` cannot quietly become a difference against anything else.
        reporter.record_metric(
            name=METRIC_FIRST, value=s["first"], unit=OBJECTIVE_UNIT,
            subjects=subjects or [], rollup_of=metric_ids,
            tier=RecordTier.SUPPORTING,
            message="the objective of the FIRST workable plan the solver found",
        )
    reporter.record_metric(
        name=METRIC_COUNT, value=float(s["count"]), unit="incumbents",
        subjects=subjects or [], tier=RecordTier.SUPPORTING,
        message=f"{s['count']} improving solution(s) found",
    )

    # R-SP1 AMENDMENT 1 — THE DOLLAR ROLLUP, beside the objective-space one and
    # never instead of it. Same mechanism as W2.1's (docs/02 §4.4): the first
    # plan's COST decomposes into the final plan's cost plus what the search took
    # off it, exactly, and the consolidator verifies it — so "improvement" cannot
    # become a difference against anything the solver did not itself produce and
    # still decompose. Emitted at zero: a one-plan search has a true $0.00 story.
    price = price_summary(first_plan_cost, final_plan_cost)
    if price["priced"]:
        fin = reporter.record_metric(
            name=METRIC_FINAL_COST, value=price["final_plan_cost"],
            unit=COST_UNIT, subjects=subjects or [], tier=RecordTier.SUPPORTING,
            message="ledger cost of the plan this solve finished on")
        imp = reporter.record_metric(
            name=METRIC_COST_IMPROVEMENT, value=price["dollar_improvement_abs"],
            unit=COST_UNIT, subjects=subjects or [], tier=RecordTier.SUPPORTING,
            message=("what the search took off the ledger cost of its OWN first "
                     "workable plan; 0.00 means it found no cheaper plan"))
        reporter.record_metric(
            name=METRIC_FIRST_COST, value=price["first_plan_cost"],
            unit=COST_UNIT, subjects=subjects or [],
            rollup_of=[fin.record_id, imp.record_id],
            tier=RecordTier.SUPPORTING,
            message=("ledger cost of the FIRST workable plan the solver found, "
                     "priced by the same extractor that priced the final plan"))

    payload = {
        "stage": TRAIL_STAGE,
        "window_key": window_key,
        "status": status,
        "incumbents": trail,
        "best_bound": best_bound,
        "gap": gap,
        "det_consumed": det_consumed,
        "det_budget": det_budget,
        "objective_unit": OBJECTIVE_UNIT,
        "cost_unit": COST_UNIT,
        **price,
        # The provenance CLASS and the source, named ON the record so it is
        # walkable rather than asserted (S-02's `grade_provenance`, same shape).
        # `derived` and not `observed`: these are CP-SAT's own readings of its
        # own search, read back through the callback — the plant was never
        # measured for them.
        "trail_provenance": {
            "provenance_class": "derived",
            "source": "ortools.sat.python.cp_model.CpSolverSolutionCallback",
        },
        **s,
    }
    ev = reporter.record_event(
        status_text=SOLVE_PROGRESS_STATUS,
        payload=payload,
        tier=RecordTier.SUPPORTING,
        subjects=subjects or [],
        message=(f"solve progress: {s['count']} incumbent(s), "
                 f"stage={TRAIL_STAGE}"),
    )
    return {"event_id": ev.record_id, "metric_ids": metric_ids}


def write_solve_progress_json(doc: dict, path: Path, reporter=None) -> None:
    """Write the trail artifact, and — when a still-open reporter is given —
    REGISTER it as this run's output (docs/02 §4.6, verb 7).

    Mirrors ``conformance.write_certificate_json`` deliberately, including the
    reason it hashes ``path.read_bytes()`` rather than the string it serialized:
    ``write_text`` newline-translates on Windows, so a digest of the JSON we
    MEANT to write does not verify against the file it names. That was caught by
    a guard rather than by reading the code, and it is now a named class.

    Registration must happen BEFORE ``reporter.end()``: the output manifest is
    sealed into the close record.
    """
    path = Path(path)
    path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    if reporter is not None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reporter.register_output(str(path), artifact_hash=digest)
