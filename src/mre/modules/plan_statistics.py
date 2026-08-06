"""THE THREE ROLLUPS THE SUMMARY SCREEN NAMED AS GAPS (Session W2.2, W2.1 §7(b)).

W2.1 refused to compute three statistics client-side and rendered them as named
gaps instead, each saying where it should come from. This module is where they
come from. Nothing here is new arithmetic over new inputs: each rollup walks the
SAME source the extractor already walks for the figure beside it, which is the
property that keeps the pair from drifting.

  * **late / on-time counts** walk the service outcomes the extractor has just
    built — the same list `lateness_minutes` is emitted per demand from. They
    are COUNTS and they are kept distinct from R-PD1's tardiness split, which
    decomposes a COST: "how many orders are late" and "how much of the lateness
    charge was unavoidable" are two statements, and W2.1's screen already keeps
    them apart.
  * **utilization by machine** divides the WORKING minutes the ledger bills
    (`dur_min`, the sum of a resumable op's own chunk spans — never the elapsed
    span, 4B.20) by the OPEN CALENDAR minutes the builder flattened for that
    resource. **THE DENOMINATOR IS CARRIED IN THE RECORD**, not implied by the
    surface: 4B.20's defect was one denominator per surface, and the fix is that
    the number arrives with its own definition and both of its components, so no
    reader has to guess and no surface can re-imply its own.
  * **total changeover minutes** sums each RUNNING operation's setup duration
    over exactly the op set the setup COST is charged on. That set is
    WIP-filtered (`wip_status not in (complete, in_progress)` — a setup that
    already happened before the reference date is sunk, docs/06 §5.13), and the
    minutes must be filtered identically or the plant's changeover time and its
    changeover bill would describe different plans.

EVERY ROLLUP DECOMPOSES OR CARRIES ITS COMPONENTS. `service.demands_counted`
rolls up late + on-time and the consolidator verifies it (docs/02 §4.4).
Utilization is a RATIO, which is not a sum and therefore not a rollup — so its
two components are emitted as their own metrics beside it and the reader checks
the arithmetic instead of trusting the adjective (the `CoarseDensityCell`
precedent). Components are emitted EVEN AT ZERO.
"""
from __future__ import annotations

from typing import Any, Optional

#: Metric names. Additive to the vocabulary, never repurposed.
METRIC_LATE = "service.late_demands"
METRIC_ON_TIME = "service.on_time_demands"
METRIC_DEMANDS = "service.demands_counted"
METRIC_CHANGEOVER = "setup.changeover_minutes"
METRIC_WORKING = "resource.working_minutes"
METRIC_OPEN_CAPACITY = "resource.open_capacity_minutes"
METRIC_UTILIZATION = "resource.utilization"

#: THE DENOMINATOR, WRITTEN DOWN ONCE AND CARRIED ON THE RECORD. This string is
#: the whole of 4B.20's fix: a utilization figure that travels without its
#: denominator invites every surface to supply a different one, and two correct
#: numbers then read as a contradiction. The cockpit's own per-visible-window
#: utilization is a DIFFERENT and equally correct number for a different
#: question; it is left alone, and this definition is what lets a reader see
#: that the two are not in conflict.
UTILIZATION_DEFINITION = (
    "working minutes billed on this resource (the sum of each operation's own "
    "run windows, excluding calendar pauses) divided by the open calendar "
    "minutes flattened for this resource across the solver's planning horizon"
)

#: The counting rule for lateness, named for the same reason.
LATENESS_DEFINITION = (
    "a demand is LATE when its projected completion is after its declared due "
    "date (lateness_minutes > 0); every demand with a service outcome is "
    "counted exactly once"
)

#: And for changeover.
CHANGEOVER_DEFINITION = (
    "the sum of each RUNNING operation's setup duration on the resource it was "
    "assigned to — the same operation set the setup charge is billed on, so "
    "operations whose setup was already sunk before the reference date "
    "(wip_status complete or in_progress) are excluded from both"
)


def late_counts(service_outcomes: list[dict]) -> dict:
    """Late / on-time / total, over the outcomes the extractor just built.

    Every outcome is counted exactly once and the two components sum to the
    total by construction — which is what makes the rollup verifiable rather
    than merely asserted.
    """
    late = sum(1 for s in service_outcomes if (s.get("lateness_minutes") or 0) > 0)
    return {"late": late, "on_time": len(service_outcomes) - late,
            "counted": len(service_outcomes)}


def utilization_by_resource(
    working_minutes: dict[str, int],
    cal_windows: Optional[dict],
) -> dict[str, dict]:
    """Per-resource working minutes, open capacity, and the ratio.

    ``utilization`` is None where the denominator is unknown or zero — a ratio
    over no capacity is undefined, not nought, and the third-state discipline
    says an instrument that cannot see the value does not report one. The
    components are still returned in that case: "this resource was worked for N
    minutes and we cannot say against what" is a true and useful statement.

    Resources with NO work are included with zero working minutes: an idle
    machine at 0% is a fact a planner wants, and a rollup whose members appear
    only when non-empty cannot be read as a set (docs/02 §4.4's rule, applied to
    a map rather than to a sum).
    """
    out: dict[str, dict] = {}
    rids = set(working_minutes) | set(cal_windows or {})
    for rid in sorted(rids):
        worked = int(working_minutes.get(rid, 0))
        windows = (cal_windows or {}).get(rid)
        if windows is None:
            capacity = None
        else:
            capacity = int(sum(max(0, e - s) for s, e in windows))
        util = (round(worked / capacity, 6)
                if capacity is not None and capacity > 0 else None)
        out[rid] = {"working_minutes": worked,
                    "open_capacity_minutes": capacity,
                    "utilization": util}
    return out


def build(
    *,
    service_outcomes: list[dict],
    working_minutes: dict[str, int],
    changeover_minutes: int,
    cal_windows: Optional[dict] = None,
) -> dict:
    """The statistics payload, composed ONCE.

    Two assemblers read it from two different places — the rolling one off the
    view, the monolithic one out of the Schedule's ``summary_metrics`` — so the
    CONTENT is built here and only the SOURCE differs. W2.1's pattern, same
    reason: a payload composed twice is a payload that can say two things.
    """
    counts = late_counts(service_outcomes)
    return {
        "late_demands": counts["late"],
        "on_time_demands": counts["on_time"],
        "demands_counted": counts["counted"],
        "lateness_definition": LATENESS_DEFINITION,
        "changeover_minutes": int(changeover_minutes),
        "changeover_definition": CHANGEOVER_DEFINITION,
        "utilization_definition": UTILIZATION_DEFINITION,
        "utilization_by_resource": utilization_by_resource(
            working_minutes, cal_windows),
    }


def emit(reporter, stats: dict, *, subjects=None) -> None:
    """Write the rollups into the evidence store (docs/02 §4.4).

    ``service.demands_counted`` is the ROLLUP of late + on-time, verified by the
    consolidator rather than asserted here. Utilization is a ratio and therefore
    NOT a rollup: its two components ride beside it as their own metrics, and
    every one of the three carries its definition in the message so the number
    can never travel without its denominator.
    """
    from mre.contracts.entities import EntityRef
    from mre.contracts.vocabularies import RecordTier

    subj = subjects or []
    late = reporter.record_metric(
        name=METRIC_LATE, value=float(stats["late_demands"]), unit="demands",
        subjects=subj, tier=RecordTier.SUPPORTING,
        message=f"{stats['late_demands']} demand(s) late — {LATENESS_DEFINITION}")
    on_time = reporter.record_metric(
        name=METRIC_ON_TIME, value=float(stats["on_time_demands"]),
        unit="demands", subjects=subj, tier=RecordTier.SUPPORTING,
        message=f"{stats['on_time_demands']} demand(s) on time or early")
    reporter.record_metric(
        name=METRIC_DEMANDS, value=float(stats["demands_counted"]),
        unit="demands", subjects=subj,
        rollup_of=[late.record_id, on_time.record_id],
        tier=RecordTier.SUPPORTING,
        message=f"{stats['demands_counted']} demand(s) counted")

    reporter.record_metric(
        name=METRIC_CHANGEOVER, value=float(stats["changeover_minutes"]),
        unit="minutes", subjects=subj, tier=RecordTier.SUPPORTING,
        message=(f"{stats['changeover_minutes']} changeover minute(s) — "
                 f"{CHANGEOVER_DEFINITION}"))

    for rid, u in (stats.get("utilization_by_resource") or {}).items():
        rsub = [EntityRef(entity_id=rid, entity_type="resource")]
        reporter.record_metric(
            name=METRIC_WORKING, value=float(u["working_minutes"]),
            unit="minutes", subjects=rsub, tier=RecordTier.SUPPORTING,
            message="working minutes billed on this resource")
        if u["open_capacity_minutes"] is None:
            # No calendar was supplied, so there is no denominator and there is
            # no ratio. Saying nothing here is the honest move; a 0.0 would be a
            # claim about the plant made from a fact about our inputs.
            continue
        reporter.record_metric(
            name=METRIC_OPEN_CAPACITY,
            value=float(u["open_capacity_minutes"]), unit="minutes",
            subjects=rsub, tier=RecordTier.SUPPORTING,
            message="open calendar minutes for this resource over the horizon")
        if u["utilization"] is None:
            continue
        reporter.record_metric(
            name=METRIC_UTILIZATION, value=float(u["utilization"]),
            unit="ratio", subjects=rsub, tier=RecordTier.SUPPORTING,
            message=f"utilization {u['utilization']:.4f} — {UTILIZATION_DEFINITION}")
