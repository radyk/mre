"""R-SP1 AMENDMENT 1 — PRICING A PLACEMENT SET THROUGH THE REAL LEDGER.

The bridge that lets the solve-progress story render in DOLLARS. It is the whole
mechanism, and it is deliberately tiny, because the amendment's admissibility
rule is a statement about WHICH extractor priced the number:

    dollars are admissible exactly when both endpoints are LEDGER-PRICED
    PLACEMENTS — priced by the same extractor that prices the finished plan.

So this module runs :class:`~mre.modules.extractor.Extractor`, unmodified, on a
captured ``SolveValues``. It does not reimplement a cost model, it does not
approximate, and it has no arithmetic of its own. If it ever grows any, the
amendment's premise stops being true and R-DP12 is back in play.

WHY THE CAPTURE IS FREE OF APPROXIMATION. ``VariableMap.extract`` reads its
values through ``solver.Value(v)`` and nothing else, and a
``CpSolverSolutionCallback`` provides exactly that accessor. A mid-search
snapshot is therefore taken by the SAME function that reads the final solution —
there is no second reader that could disagree with the first, and no field the
snapshot has to invent. (This was the axis the brief said to stop on if it did
not hold. It holds.)

WHAT IS DELIBERATELY NOT WRITTEN. The pricing call passes ``reporter=None`` and
``snapshot_writer=None``: pricing a hypothetical plan must not emit assignment
Decisions, must not write entities into the canonical snapshot, and must not
mint a Schedule. It is a MEASUREMENT of a placement set the solver passed
through on its way somewhere else — the plan of record is the final one, and
only the final one is extracted for real. ``is_scenario=True`` says so in the
one field that carries it.

COST. One extraction, once, post-solve. Not per incumbent — the amendment's
one-snapshot bound is the wall, and a per-incumbent extractor loop is exactly
what it forbids.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PricingInputs:
    """Everything the ledger extractor needs BESIDES the placements.

    Captured once by the caller that owns the plant tables, then reused to price
    any number of placement sets from the same solve. Frozen because two prices
    compared against each other must have been computed against the same tables
    — a first plan priced on one op set and a final plan priced on another would
    be a difference of two different questions.
    """
    snapshot_id: str
    operations: list
    workpackages: list
    resources: list
    fulfillments: list
    demands: list
    cost_model: dict
    cal_windows: Optional[dict] = None
    op_eligible: Optional[dict] = None
    overtime_windows: Optional[dict] = None


def price_placements(
    solve_values: Any,
    inputs: PricingInputs,
    *,
    require_ops: Optional[set] = None,
) -> Optional[float]:
    """The LEDGER TOTAL for one placement set, or None if it cannot be priced.

    ONE definition. Both endpoints of the money story go through this function,
    and so does the guard that proves it against the known answer — re-pricing
    the FINAL plan here must reproduce the shipped ledger total to the cent, or
    the bridge is marshalling something wrong and its novel answer (the first
    plan's price) is not to be trusted.

    Returns None rather than raising on a placement set the extractor cannot
    price: a missing price is a state the surfaces already render (the
    objective-space story), and a crashed solve would be a far worse trade for a
    figure that is decoration on top of a schedule that is already correct.
    """
    if solve_values is None:
        return None

    # THE COVERAGE CHECK, AND WHY IT IS NOT OPTIONAL.
    #
    # The extractor does not fail on a placement set that places nothing — it
    # prices it, as a plan where every demand is late. On a 40-order window that
    # returns a confident $1,520.00. So a capture that silently came back empty
    # or partial would not raise; it would produce a plausible first-plan price
    # that is not a price of this plan at all, and the money story would be a
    # comparison between the solver's plan and a fiction.
    #
    # Found by a guard written to assert the opposite (that a degenerate set
    # raises). It does not, and the amendment's premise — BOTH endpoints are
    # placements of the same plan — needs this to be checked rather than
    # assumed. The caller passes the operation set the FINAL plan placed; a
    # capture that does not place the same ones is REFUSED, and the surfaces
    # fall back to the objective-space story, which is honest.
    if require_ops is not None:
        placed = set(getattr(solve_values, "op_resource", {}) or {})
        if placed != set(require_ops):
            return None

    from mre.modules.extractor import Extractor

    try:
        result = Extractor().extract(
            solve_values=solve_values,
            snapshot_id=inputs.snapshot_id,
            operations=inputs.operations,
            workpackages=inputs.workpackages,
            resources=inputs.resources,
            fulfillments=inputs.fulfillments,
            demands=inputs.demands,
            cost_model=inputs.cost_model,
            reporter=None,             # a hypothetical plan mints no evidence
            cal_windows=inputs.cal_windows,
            op_eligible=inputs.op_eligible,
            snapshot_writer=None,      # …and writes no entities
            overtime_windows=inputs.overtime_windows,
            is_scenario=True,          # …and says which it is
        )
    except Exception:  # noqa: BLE001 — a price is never worth a failed solve
        return None
    total = (result.cost_ledger or {}).get("total_cost")
    return None if total is None else round(float(total), 2)
