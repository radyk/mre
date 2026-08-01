"""Rolling-horizon (sliced) solve runner — Session 4B.2, R-SC2 / R-SC3.

R-SC3 (docs/04, Session 4B.2d, AMENDED 4B.7): earliness is a ZERO-COST TIEBREAK
— and ONLY that. Each window (and the final pricing pass) solves in TWO STAGES:
  * Stage 1 minimizes sum(objective_terms) — COST, and only cost;
  * Stage 2 caps the stage-1 objective at its optimum and re-minimizes Σ free-op
    starts (warm-started from stage 1) — the lexicographic "prefer earlier among
    cost-optimal placements" floor. A small deterministic budget bounds stage 2;
    on exhaustion the stage-1 incumbent stands (never a worse-cost schedule).
    STAGE 2 RUNS UNCONDITIONALLY: R-SC3(1)'s "always and unconditionally" is the
    whole clause, and no declared coefficient gates it.
This replaces the 4B.2 hidden incentive (removed, not re-scoped): no internal
undeclared weight influences placement.

SESSION 4B.7 RETIRED R-SC3(2) — the declared `earliness_value` as a PRICE in the
primary objective. It was measured against a cost-only arm whose seed spread is
exactly zero and cost +73.20% of ledger total at 40 orders / +97.61% at 120,
almost all of it tardiness. `earliness_value` survives as a REPORTING rate only
(`_earliness_rate`, `earliness_tiebreak_report`): it values the start-minutes
stage 2 recovered, on its own labelled line, and never enters a cost figure. The
SCHEDULE is byte-identical across every `earliness_value` setting — asserted, not
assumed (tests/test_objective_units.py).

R-SC2 (docs/04): slicing is a ROLLING HORIZON with a FROZEN ZONE and GRAVITY
admission. Solve a window of declared length; commit only the frozen front;
roll and re-solve (committed work is in the past, so it constrains nothing and
is dropped; warm-start carries the incumbent). Inclusion = the time window PLUS
gravity:
    (a) must-start-by pull   — latest-feasible-start inside the window admits it
    (b) weighted-criticality — a high-weight job is pulled in early
    (c) setup-family affinity — a job sharing a family with in-window work

Window length is chosen by MEASUREMENT (the knee of the cost-vs-window curve,
tools/pilot_measurements.py) and declared per deployment. Far-horizon
look-ahead pricing is named and parked.

Design (v1):
  * The spine (gate → adapter → validator → planner) runs ONCE (prepare_plant),
    persisting the full canonical snapshot. The rolling loop then works at the
    M5/M6/M7 level, choosing per window which demands' operations to solve.
  * FROZEN ZONE: after each window solve, every operation whose solved END falls
    within [window_start, frozen_end) is COMMITTED — its (resource, start) is
    recorded and it is removed from all future windows. Because the next window's
    floor IS frozen_end, committed work always ends before every future window
    starts: it can never conflict with future operations and never needs a pin
    (this is why "committed work enters as fixed" reduces, in a rolling design,
    to "committed work is in the past" — the WIP machinery's guarantee, for free).
  * STANDING PINS (R-DP8): external accepted-edit pins compile into whichever
    window holds them (apply_standing_pins, on the operations still in the model).
  * DETERMINISTIC mode (solver-workers 1 + seed) for every measurement claim.
  * COST: the rolling process yields a committed placement per operation; the
    reported total cost is ONE exact Extractor pass over the fully-pinned union
    (§_final_extract) — the same method across every window setting, so the
    window curve is a fair comparison.

Nothing here imports ortools directly except through SolverBuilder/SolveRunner.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.calendar_utils import flatten_all_calendars
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter

UTC = timezone.utc
_SHIFT_MIN = 720          # nominal working minutes/day (07:00-19:00) for est.
_HORIZON_BUFFER_DAYS = 90  # must match compute_horizon / SolverBuilder (chunk slots)
_WINDOW_TAIL_DAYS = 21     # per-window horizon tail past window_end (near-term only)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

_DUR_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso_duration_minutes(s: Optional[str]) -> int:
    """'PT1H45M' -> 105 (minutes). None/'' -> 0."""
    if not s:
        return 0
    m = _DUR_RE.fullmatch(s.strip())
    if not m:
        return 0
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 60 + mi + (1 if se else 0)


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# SESSION 4B.8 CU2 — THE BUDGET SPLIT, DERIVED.
#
# ``_STAGE2_DET_TIME_S = 2.0`` IS DELETED, not defaulted. It gave stage 2 a
# FIXED slice regardless of what stage 1 spent, and the allocation was backwards
# in both directions at once (docs/07 §5a.19):
#   * 40 orders — stage 1 proves OPTIMAL in 0.101 of its 4.0 while stage 2
#     exhausts its whole 2.0 without closing the tiebreak. 3.9 units unused.
#   * 200 orders / 7d — stage 1 needs 4.542 and 4.962 units on two seeds and
#     gets 4.0, so it truncates: +5.46% and +26.07% ledger against a
#     full-budget cost-only solve.
# A constant that can still be read is a constant that comes back (the 4B.7
# precedent for the earliness coefficient), so it is gone rather than zeroed.
#
# THE REPLACEMENT: the caller declares a TOTAL, stage 1 is capped at the total
# minus a small RESERVE, and stage 2 receives whatever the total has left after
# stage 1 actually ran. Stage 2's limit is therefore never a constant, and
# stage 1 can never starve the tiebreak to nothing.
#
# WHY A RESERVE RATHER THAN A PLAIN REMAINDER (P2 vs P3, measured in CU1):
# R-SC3(1) makes the tiebreak zero-cost, so cost strictly dominates and the
# budget should go to cost FIRST — which argues for a plain remainder. But at
# 120 orders and above stage 1 exhausts everything, so a plain remainder hands
# stage 2 ZERO at exactly the plant sizes where a planner sees the defect
# Session 4B.4 found (an op parked at 14:39 behind a free 11:21 slot). The
# reserve is what keeps R-SC3(1)'s "always and unconditionally" true at scale.
# It is priced in CU1's table, not assumed: stage 1's extra budget beyond the
# cost proof buys nothing (the plateau), so the reserve is free where stage 1
# closes and cheap where it does not.
#
# Expressed as a FRACTION of the total so it scales with the budget the caller
# declared. 1/12 of the shipped 6.0 total is exactly the 0.5 units CU1 measured.
_STAGE2_RESERVE_FRACTION = 1.0 / 12.0

#: The historical TOTAL of the old scheme was ``stage1 + 2.0`` — the caller's
#: ``det_time`` plus the deleted constant. That is 6.0 at the shipped default of
#: 4.0, but it was 4.0 for the exam/fixture builders (det_time 2.0) and 2.5 for
#: the golden driver (det_time 0.5), so there is no single multiplier that
#: preserves every caller's budget. This is why the parameter was RENAMED
#: ``det_time`` -> ``det_total`` rather than reinterpreted: a rename makes every
#: call site fail loudly until someone states the total it means, which is
#: exactly the review this change needed. Each caller now declares its own
#: historical total explicitly and nobody's budget moved silently.
_DET_TOTAL_DEFAULT = 6.0
#: The same number under a public name, for callers outside this module that
#: need to say "the shipped default" rather than restate 6.0 (the API's solve
#: worker, since 4B.25 — a portfolio member's budget is a DECLARED coefficient
#: and a caller declaring nothing must land on exactly this).
DET_TOTAL_DEFAULT = _DET_TOTAL_DEFAULT

#: The MONOLITHIC path's two-stage budget. That path declared no deterministic
#: budget for stage 1 (wall-limited) and a fixed 2.0 for stage 2, so 2.0 IS its
#: historical total — and it is passed with ``cap_stage1=False``, leaving the
#: cost proof exactly as uncapped as it has always been. Only the TIEBREAK's
#: share becomes derived (total minus what stage 1 actually spent).
#:
#: Stage 2 cannot simply be left wall-limited instead: a wall-stopped solve is
#: not reproducible run-to-run, and this is the path the byte-for-byte goldens
#: are captured from (tests/test_defaults_reproduce_baseline.py), so an
#: unbudgeted stage 2 would make the golden a property of the machine and the
#: load. Measured, sample_data, seed 42: stage 1 proves OPTIMAL in 0.043 units,
#: so stage 2 receives 1.957 and the schedule is BYTE-IDENTICAL to the golden.
#:
#: Raising it was measured and REJECTED, not assumed: at 4.0 and 6.0 the tiebreak
#: improves its own objective by 344 and 422 start-minutes out of 3,307,818
#: (-0.01%) while wall time goes 19.6 s -> 37.5 s -> 50.2 s. Paying 2.5x the wall
#: clock for one hundredth of a percent is not a trade this path should make; the
#: instances where stage-2 budget genuinely pays (CU1 measured -19.41% at 15
#: orders) are on the rolling path, which declares its own larger total.
DET_TOTAL_MONOLITHIC = 2.0


def _stage_budgets(det_total: float) -> tuple[float, float]:
    """(stage-1 cap, stage-2 reserve) for a declared total. Stage 2's ACTUAL
    budget is not here — it is the remainder after stage 1 runs, and cannot be
    known before it does."""
    reserve = det_total * _STAGE2_RESERVE_FRACTION
    return max(0.0, det_total - reserve), reserve


def _earliness_rate(cost_model: dict, override: Optional[float]) -> float:
    """The plant's declared earliness rate in DOLLARS PER MINUTE of op start.
    override wins when given (tests / measurement); else the declared
    CostModel.earliness_value; never negative.

    SESSION 4B.7 — this is a REPORTING rate and nothing else. It reaches no
    solver, no objective, no cap and no cost ledger. Its one job is to value the
    start-minutes stage 2 recovered, on its own labelled line. The predecessor
    (``_earliness_coeff_scaled``, which returned CP-SAT objective units) is
    DELETED rather than left callable: a scaled coefficient that still exists is
    a coefficient that can be handed back to ``model.minimize``."""
    val = override if override is not None else float(
        cost_model.get("earliness_value", 0.0) or 0.0)
    return max(0.0, float(val))


def earliness_tiebreak_report(start_minutes_before: Optional[int],
                              start_minutes_after: Optional[int],
                              rate_per_minute: float) -> dict:
    """The R-SC3 tiebreak's own labelled line (Session 4B.7, item 2c).

    Stage 2 recovers ``before - after`` op-start minutes at ZERO ledger cost —
    that is the FLOOR working, and it happens at every ``earliness_value``
    including 0 and undeclared. A plant that has DECLARED what a start-minute is
    worth to it gets that recovery valued at its own rate.

    TWO LEDGERS, NEVER FUSED. ``valued_at`` is not money the plant spent or
    saved on this schedule: no such dollar appears in ``cost_summary.total``, in
    a delta card, or in any ledger line. It is what the plant's own declared rate
    says the recovered minutes are worth to it. ``rate_provenance`` names which
    it is, so a reader is never left to guess whether a zero means "declared
    zero" or "never declared"."""
    if start_minutes_before is None or start_minutes_after is None:
        return {"start_minutes_recovered": None, "declared_rate_per_minute": rate_per_minute,
                "valued_at": None, "in_ledger": False,
                "rate_provenance": "declared" if rate_per_minute > 0 else "undeclared_or_zero"}
    recovered = int(start_minutes_before) - int(start_minutes_after)
    return {
        "start_minutes_recovered": recovered,
        "declared_rate_per_minute": rate_per_minute,
        "valued_at": (round(recovered * rate_per_minute, 2)
                      if rate_per_minute > 0 else None),
        "in_ledger": False,
        "rate_provenance": "declared" if rate_per_minute > 0 else "undeclared_or_zero",
    }


def _hint_from_solve(model, var_map, sv) -> None:
    """Re-seed the model's solution hints from a completed solve (stage-1 →
    stage-2 warm start). Clears prior hints first so no variable is double-hinted
    (CP-SAT rejects duplicate hint entries)."""
    model.clear_hints()
    for oid, smin in sv.op_start_minutes.items():
        v = var_map.op_start.get(oid)
        if v is not None:
            model.add_hint(v, smin)
        ev = var_map.op_end.get(oid)
        emin = sv.op_end_minutes.get(oid)
        if ev is not None and emin is not None:
            model.add_hint(ev, emin)
        res = sv.op_resource.get(oid)
        if res is not None:
            for r2, bv in var_map.op_assign.get(oid, {}).items():
                model.add_hint(bv, 1 if r2 == res else 0)


def _hint_assign_only(model, var_map, sv) -> None:
    """Seed the ASSIGNMENT literals alone — structure, not times (4B.12 CU3
    arm H2).

    A full hint asserts a complete solution; if any part of it conflicts with a
    constraint the objective later tightens, CP-SAT can discard the whole seed.
    A PARTIAL hint asserts only which machine does which operation and leaves
    every start time free, so it survives what an exact-time hint may not. The
    two are measured against each other rather than assumed."""
    model.clear_hints()
    for oid, res in sv.op_resource.items():
        if res is None:
            continue
        for r2, bv in var_map.op_assign.get(oid, {}).items():
            model.add_hint(bv, 1 if r2 == res else 0)


# ---------------------------------------------------------------------------
# SESSION 4B.12 CU3 — THE WARM START, SHIPPED BEHIND A FLAG, DEFAULT OFF.
#
# 4B.8 measured the fact this exists to act on: at 200 orders / 14 days the COST
# solve returned UNKNOWN in 6.0 deterministic units while SATISFIABILITY on the
# SAME model took 0.082 — a factor of 74. The objective does not merely make the
# model hard to OPTIMIZE; it makes it hard to find anything in. So the search can
# be handed a feasible starting point it is demonstrably able to find cheaply.
#
# THE HINT IS NOT FREE, and the flag's contract says so: phase 0 spends out of
# the SAME declared `det_total`, and the cost stages receive what it leaves. An
# arm that bought its speedup with extra budget would not be a speedup.
#
# DEFAULT OFF, and it stays off until a session rules otherwise. 4B.12 measures
# it; the numbers are in docs/07 §5a.31. Turning it on is a ruling, not a
# default change — every golden in the repository is captured with it off.
HINT_OFF = "off"
#: Seed start, end AND assignment vars — the complete solution, via the same
#: `_hint_from_solve` the shipped stage-1 -> stage-2 warm start already uses. Using
#: a different seeder here would measure the seeder rather than the hint.
HINT_FULL = "full"
#: Seed the assignment literals only. See `_hint_assign_only`.
HINT_ASSIGN = "assign"
HINT_MODES = (HINT_OFF, HINT_FULL, HINT_ASSIGN)

#: Phase 0's share of the declared total. 4B.8 measured satisfiability at 0.082
#: units on the largest instance the programme had then, so 1/6 of the shipped
#: 6.0 total is ~12x that — generous enough that a failure to find a solution is
#: a fact about the model, not about the allowance. Unspent budget is NOT lost:
#: the cost stages are sized from `det_total - actually spent`.
_HINT_DET_FRACTION = 1.0 / 6.0


def _warm_start(model, var_map, terms, runner, mode: str):
    """Phase 0: clear the objective, solve for ANY feasible solution, seed it as
    a hint, and restore the cost objective. Returns ``(det_spent, status)``.

    Restoring the objective is done in a ``finally``: a phase-0 solve that raises
    or returns nothing must leave the model exactly as the cost stages expect it,
    or the flag would silently change what stage 1 minimizes."""
    model.clear_hints()
    model.minimize(0)
    try:
        r0 = runner.solve(model, var_map, None)
    finally:
        # `terms` is non-empty by the caller's guard, so this restores the same
        # expression `solver_builder.build` set and nothing else.
        model.minimize(sum(terms))
    spent = r0.det_consumed if r0.det_consumed is not None else 0.0
    if r0.status in ("OPTIMAL", "FEASIBLE") and r0.solve_values is not None:
        if mode == HINT_ASSIGN:
            _hint_assign_only(model, var_map, r0.solve_values)
        else:
            _hint_from_solve(model, var_map, r0.solve_values)
    else:
        # No solution found: no hint to give. The budget it spent is still spent,
        # and the cost stages are sized accordingly — the arm pays for its miss.
        model.clear_hints()
    return spent, r0.status


def _sum_free_starts(solve_values, free_op_ids) -> Optional[int]:
    """Σ start-minutes over the free ops actually placed, or None with no values."""
    if solve_values is None:
        return None
    return sum(solve_values.op_start_minutes[o] for o in free_op_ids
               if o in solve_values.op_start_minutes)


def _two_stage_solve(model, var_map, free_start_vars, *,
                     workers, seed, deterministic, member_time_limit_s,
                     det_total, free_op_ids=None, hint_mode=HINT_OFF):
    """R-SC3 two-stage solve on an already-built model (constraints/pins applied,
    warm-start hints seeded by the caller).

    Returns ``(SolveResult, stage2_ran, recovery)`` where ``recovery`` is
    ``(start_minutes_before, start_minutes_after)`` over ``free_op_ids`` — the
    raw material for the tiebreak's own labelled reporting line — or
    ``(None, None)`` when ``free_op_ids`` is not supplied or stage 2 did not run.

    Stage 1 minimizes COST and only cost — the builder's own
    ``minimize(sum(objective_terms))``, left as set. Stage 2 caps that objective
    at round(best) and re-minimizes Σ free-op starts (the zero-cost tiebreak).
    With no objective terms or no free-op starts, only stage 1 runs. On a stage-2
    non-solution the stage-1 incumbent stands.

    SESSION 4B.7, two changes, both to close measured defects:

    * **The priced-earliness term is GONE from stage 1**, and the parameter that
      carried it is gone from this signature so it cannot leak back. R-SC3(2) is
      retired; R-SC3(1) is not, and stage 2 therefore runs UNCONDITIONALLY at
      every ``earliness_value`` including 0 and undeclared.
    * **The returned result carries stage 1's OBJECTIVE with stage 2's
      PLACEMENTS**, the way ``solver_builder.solve_two_stage`` has always done it
      (``solver_builder.py``, same rebuild). Before this, rolling returned the
      stage-2 result WHOLE, so ``.objective`` was Σ free-op starts — a MINUTE
      COUNT — and ``build_rolling_view`` wrote that into M6 ``solve_complete``
      for every downstream reader (docs/07 §5a.16). It is now the cost objective,
      trivially, because stage 1's objective IS cost.

    SESSION 4B.8, two more:

    * **THE BUDGET IS DERIVED** (CU2). ``det_total`` is the whole two-stage
      deterministic budget. Stage 1 is capped at total minus a small reserve;
      stage 2 gets what the total has LEFT after stage 1 actually ran. Nothing
      here is a constant, and stage 1 cannot starve the tiebreak to nothing.
    * **THE REPORTED STATUS IS STAGE 1's** (CU3). ``status`` is the COST proof;
      ``tiebreak_status`` is stage 2's, and ``tiebreak_skipped_reason`` says why
      when stage 2 did not run. Before this the returned status was stage 2's,
      so a schedule whose cost we could prove OPTIMAL reported FEASIBLE
      (docs/07 §5a.21).

    SESSION 4B.12 CU3 — ``hint_mode``, DEFAULT OFF and shipped off. With a mode
    set, a PHASE 0 runs first: the objective is cleared, the model is solved for
    any feasible solution, and that solution is seeded as a hint for stage 1. Its
    deterministic spend comes out of the SAME ``det_total`` (see
    ``_HINT_DET_FRACTION``), so the arms compare on TOTAL consumption. At
    ``HINT_OFF`` — which is every shipped caller — not one line below behaves
    differently: ``spent0`` is 0.0 and both budget expressions reduce to the ones
    4B.8 derived."""
    from mre.modules.solve_runner import SolveRunner, SolveResult
    from dataclasses import replace

    terms = var_map.objective_terms

    def _runner(det):
        return SolveRunner(time_limit_seconds=member_time_limit_s,
                           num_search_workers=workers, random_seed=seed,
                           deterministic_time=(det if deterministic else None))

    # PHASE 0 — the warm start (off by default). Skipped outright on a model with
    # no objective: stage 1 is already a pure satisfiability solve there, so there
    # would be nothing to warm and nothing to restore.
    spent0 = 0.0
    if hint_mode != HINT_OFF and terms:
        if hint_mode not in HINT_MODES:
            raise ValueError(f"unknown hint_mode {hint_mode!r}; expected one "
                             f"of {HINT_MODES}")
        spent0, _p0_status = _warm_start(
            model, var_map, terms,
            _runner(det_total * _HINT_DET_FRACTION), hint_mode)

    # What the COST stages have left. Identical to `det_total` when no phase 0
    # ran, which is what keeps every existing caller byte-unchanged.
    remaining = max(0.0, det_total - spent0)
    cap1, reserve = _stage_budgets(remaining)

    # STAGE 1 — COST. This function sets no objective of its own.
    s1 = _runner(cap1).solve(model, var_map, None)
    if (not terms or not free_start_vars or s1.objective is None
            or s1.status not in ("OPTIMAL", "FEASIBLE")):
        return replace(
            s1, tiebreak_skipped_reason="stage1_no_solution_or_degenerate_model",
            det_consumed=((s1.det_consumed or 0.0) + spent0
                          if spent0 else s1.det_consumed),
        ), False, (None, None)

    # STAGE 2's budget: the REMAINDER of the declared total. The reserve floor is
    # what makes R-SC3(1)'s "always and unconditionally" survive a stage 1 that
    # spent everything — without it, the tiebreak would silently stop running at
    # exactly the plant sizes where a planner notices its absence.
    #
    # A solve whose deterministic time could not be read (det_consumed is None)
    # is treated as having spent its whole cap: the guard "stage 1 + stage 2 <=
    # total" must hold on the PESSIMISTIC reading, never on an optimistic guess.
    spent1 = s1.det_consumed if s1.det_consumed is not None else cap1
    b2 = max(reserve, remaining - spent1) if reserve > 0 else max(0.0, remaining - spent1)
    if b2 <= 0.0:
        return replace(
            s1, tiebreak_skipped_reason="budget_exhausted_by_stage1",
            det_consumed=((s1.det_consumed or 0.0) + spent0
                          if spent0 else s1.det_consumed),
        ), False, (None, None)

    # STAGE 2 — cap the stage-1 COST objective, re-minimize the raw earliness.
    # Cap source and cap target are the same expression in the same units.
    best = int(round(s1.objective))
    model.add(sum(terms) <= best)
    model.minimize(sum(free_start_vars))
    _hint_from_solve(model, var_map, s1.solve_values)
    s2 = _runner(b2).solve(model, var_map, None)
    if s2.status in ("OPTIMAL", "FEASIBLE"):
        before = _sum_free_starts(s1.solve_values, free_op_ids or ())
        after = _sum_free_starts(s2.solve_values, free_op_ids or ())
        # Stage 1's truncation is carried forward: if the WALL clock (not the
        # deterministic budget) stopped stage 1, the whole two-stage result is a
        # wall-clock lottery, whatever stage 2 then did (Errand session, CU2b).
        return SolveResult(
            status=s1.status, objective=s1.objective, best_bound=s1.best_bound,
            gap=s1.gap, wall_time=s1.wall_time + s2.wall_time,
            solutions_found=s2.solutions_found, solve_values=s2.solve_values,
            wall_truncated=(s1.wall_truncated or s2.wall_truncated),
            tiebreak_status=s2.status,
            # Phase 0 (4B.12 CU3) is INCLUDED: `det_consumed` is what the whole
            # call spent, and a warm start that is not counted is a warm start
            # that looks free. 0.0 at HINT_OFF, so unchanged for every caller.
            det_consumed=(spent0 + spent1
                          + (s2.det_consumed if s2.det_consumed is not None else b2)),
        ), True, (before, after)
    # stage-2 budget exhausted → keep the stage-1 incumbent. The tiebreak RAN and
    # won nothing, which is a different fact from "it never ran" — so its status
    # is recorded and no skip reason is set.
    return replace(
        s1, tiebreak_status=s2.status,
        det_consumed=(spent0 + spent1
                      + (s2.det_consumed if s2.det_consumed is not None else b2)),
    ), False, (None, None)


# ---------------------------------------------------------------------------
# prepared plant (spine run once)
# ---------------------------------------------------------------------------

@dataclass
class PreparedPlant:
    snapshot_id: str
    out_dir: Path
    store: Any
    reference_date: datetime
    cost_model: dict
    resources: list[dict]
    pools: list[dict]
    calendars: list[dict]            # raw (not flattened)
    constraints: list[dict]
    demands: list[dict]
    fulfillments: list[dict]
    workpackages: list[dict]
    operations: list[dict]
    edges: list[dict]
    excluded_demand_ids: set
    # Where this plant was prepared FROM (4B.25, R-BK1 clause 5). A portfolio
    # member running in a separate PROCESS cannot share this object — the
    # snapshot store is not picklable and two processes must not write one
    # out_dir — so it re-prepares the plant from the same submission in its own
    # scratch directory. Optional and unused on every sequential path.
    submission_dir: Optional[Path] = None
    # derived
    ops_by_wp: dict = field(default_factory=dict)
    wp_of_demand: dict = field(default_factory=dict)
    demand_working_minutes: dict = field(default_factory=dict)
    demand_families: dict = field(default_factory=dict)
    priority_multipliers: dict = field(default_factory=dict)

    @property
    def schedulable_demands(self) -> list[dict]:
        return [d for d in self.demands if d["id"] not in self.excluded_demand_ids]


def _report(module, purpose, snap_id, runs_dir, config=None):
    return Reporter.begin(module=module, purpose=purpose, config=config or {},
                          trigger="rolling_horizon", snapshot_id=snap_id,
                          sink_dir=runs_dir)


def prepare_plant(
    submission_dir: Path | str,
    out_dir: Path | str,
    reference_date: Optional[datetime] = None,
    policy: str = "identity_v1",
) -> PreparedPlant:
    """Run the spine (gate → adapter → validator → planner) once and load the
    full canonical snapshot. reference_date defaults to the manifest's."""
    from mre.api.registry import prepare_out_dir
    from mre.modules.conformance import ConformanceGate
    from mre.modules.ids_adapter import IDSAdapter
    from mre.modules.validator import Validator
    from mre.modules.planner import Planner

    submission_dir = Path(submission_dir)
    snap_id = "snap-rolling"
    out_dir, runs_dir = prepare_out_dir(Path(out_dir), snap_id, log=lambda *_: None)
    store = SnapshotStore(out_dir / "snapshots")

    # M0 gate
    g_rep = _report(ModuleCode.M0, "IDS conformance gate", snap_id, runs_dir,
                    {"submission_dir": str(submission_dir)})
    gate = ConformanceGate().run(submission_dir, g_rep)
    g_rep.end(RunStatus.SUCCESS if gate.go else RunStatus.PARTIAL)
    if gate.grade == "REJECTED":
        raise ValueError(f"submission REJECTED by gate: {gate.certificate['deficiencies']}")
    manifest = gate.certificate["manifest"]
    if reference_date is None:
        from datetime import date
        rd = date.fromisoformat(manifest["reference_date"])
        reference_date = datetime(rd.year, rd.month, rd.day, tzinfo=UTC)

    # M1 adapter
    a_rep = _report(ModuleCode.M1, "IDS adapter", snap_id, runs_dir)
    IDSAdapter(submission_dir=submission_dir, manifest=manifest).run(
        snapshot_id=snap_id, store=store, reporter=a_rep)
    a_rep.end(RunStatus.SUCCESS)

    # M3 validator
    v_rep = _report(ModuleCode.M3, "validator", snap_id, runs_dir,
                    {"reference_date": reference_date.isoformat()})
    v_result = Validator().run(snapshot_id=snap_id, store=store, reporter=v_rep,
                               reference_date=reference_date)
    v_rep.end(RunStatus.SUCCESS)

    # M4 planner
    p_rep = _report(ModuleCode.M4, "planner", snap_id, runs_dir, {"policy": policy})
    Planner(policy=policy).run(snapshot_id=snap_id, store=store, reporter=p_rep,
                               excluded_demand_ids=v_result.excluded_demand_ids)
    p_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    cost_model = costmodels[0] if costmodels else {
        "id": "default-cm", "resource_rates": {},
        "setup_cost_basis": {"fixed_per_setup": 50.0, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
    }

    plant = PreparedPlant(
        snapshot_id=snap_id, out_dir=out_dir, store=store,
        reference_date=reference_date, cost_model=cost_model,
        resources=resources, pools=pools, calendars=calendars,
        constraints=constraints, demands=demands, fulfillments=fuls,
        workpackages=wps, operations=ops, edges=edges,
        excluded_demand_ids=set(v_result.excluded_demand_ids),
        submission_dir=submission_dir,
    )
    _derive_maps(plant)
    return plant


def _derive_maps(plant: PreparedPlant) -> None:
    for op in plant.operations:
        plant.ops_by_wp.setdefault(op["workpackage_ref"], []).append(op)
    for ful in plant.fulfillments:
        plant.wp_of_demand[ful["demand_ref"]] = ful["workpackage_ref"]
    # priority multipliers (commitment_class -> weight)
    pm = ((plant.cost_model.get("tardiness_weights") or {})
          .get("commitment_class_multipliers") or {})
    if not pm:
        pm = {"standard": 1.0, "high": 3.0, "critical": 8.0}
    plant.priority_multipliers = pm
    # per-demand working minutes + setup families
    for d in plant.demands:
        wp = plant.wp_of_demand.get(d["id"])
        ops = plant.ops_by_wp.get(wp, [])
        mins = 0
        fams: set[str] = set()
        for op in ops:
            mins += (parse_iso_duration_minutes(op.get("run_duration"))
                     + parse_iso_duration_minutes(op.get("setup_duration")))
            if op.get("setup_family"):
                fams.add(op["setup_family"])
        plant.demand_working_minutes[d["id"]] = mins
        plant.demand_families[d["id"]] = fams


# ---------------------------------------------------------------------------
# rolling result
# ---------------------------------------------------------------------------

@dataclass
class WindowMetric:
    index: int
    window_start: str
    window_end: str
    frozen_end: str
    admitted_demands: int
    free_ops: int
    committed_this_window: int
    gravity_admits: dict
    status: str
    objective: Optional[float]
    solve_wall_s: float
    build_wall_s: float


@dataclass
class RollingResult:
    window_days: int
    frozen_days: int
    gravity: bool
    windows: list[WindowMetric]
    committed_ops: dict           # op_id -> {resource, start(iso), end(iso)}
    n_windows: int
    total_solve_wall_s: float
    total_build_wall_s: float
    total_cost: Optional[float]
    cost_ledger: dict
    service_outcomes: list[dict]
    on_time: int
    late: int
    total_tardiness_minutes: float
    uncommitted_ops: int
    earliness_value: float = 0.0           # R-SC3 coefficient in force ($/min)
    op_drivers: dict = field(default_factory=dict)      # op_id -> DriverCode value
    idle_metrics: list = field(default_factory=list)    # CU5 per-resource idle


# ---------------------------------------------------------------------------
# CU1 (Session 4B.3a) — the CURRENT-WINDOW rolling VIEW (what the cockpit renders).
#
# A full run_rolling_horizon() rolls to completion, committing every op — so its
# final RollingResult has no "active but not frozen" state and nothing beyond the
# horizon. To render THE SLICED WORLD (committed frozen front + an active window +
# admitted-but-unscheduled future work), the document must capture the plant AS OF
# the reference origin: window 0. This is the state a rolling-horizon planner
# actually sees — the current window's schedule plus a tray of known future work.
# build_rolling_view solves exactly that ONE window (the same admission + two-stage
# machinery as the full roll) and classifies every schedulable demand into
# committed / active_window / beyond_horizon — the completeness invariant's states.
# ---------------------------------------------------------------------------

@dataclass
class RollingView:
    """The rolling plant AS OF the reference origin (the current window). Every
    schedulable demand lands in exactly one bucket: an op placed inside the frozen
    front (committed), an op placed in the current window past the frozen boundary
    (active), or a demand with no placed op this window (beyond_horizon)."""
    reference_origin: datetime
    window_start: datetime
    window_end: datetime
    frozen_end: datetime
    window_days: int
    frozen_days: int
    committed: dict            # op_id -> {resource, start(iso), end(iso)}
    active: dict               # op_id -> {resource, start(iso), end(iso)}
    beyond_demand_ids: list    # schedulable demand ids with no placed op this window
    cost_ledger: dict
    service_outcomes: list     # ServiceOutcome dicts for the placed (in-window) demands
    op_drivers: dict           # op_id -> DriverCode value (window solve attribution)
    earliness_value: float
    status: str
    # CU1 (4B.3c): the builder's actual horizon origin for the window solve and the
    # window horizon end — the grid the persisted assignments were written in (so a
    # sandbox re-solve rebuilds against exactly the same clock). ``persisted`` marks
    # a view whose window-0 solve was written to the canonical snapshot as a run.
    win_horizon_start: Optional[datetime] = None
    win_horizon_end: Optional[datetime] = None
    persisted: bool = False
    # True when the window-0 solve ran under a deterministic budget but was
    # actually stopped by the WALL CLOCK (Errand session, CU2b) — i.e. this view
    # is NOT reproducible, whatever ``deterministic`` was passed. Callers that
    # make a reproducibility claim (tools/build_rolling_exam_run.py) must check
    # it; raising the caller's ``member_time_limit_s`` until the deterministic
    # budget binds is the fix.
    wall_truncated: bool = False
    # 4B.7 — the R-SC3 stage-2 tiebreak's OWN labelled line: how many op-start
    # minutes stage 2 recovered at zero ledger cost, and what the plant's DECLARED
    # earliness rate says they are worth. `in_ledger` is False and stays False:
    # this figure never enters cost_ledger, cost_summary.total, or a delta card's
    # money. See earliness_tiebreak_report.
    earliness_tiebreak: dict = field(default_factory=dict)
    # 4B.8 CU3 — THE TIEBREAK PROOF, beside the cost proof and never fused with
    # it. ``status`` above is STAGE 1's: the COST proof, the claim a planner is
    # asking about. This is stage 2's, and it is routinely weaker — the tiebreak
    # exhausts its budget above ~8 orders. A schedule whose cost is proven
    # optimal SAYS SO; an unproven tiebreak does not downgrade that claim.
    # None when stage 2 never ran, in which case tiebreak_skipped_reason says why.
    tiebreak_status: Optional[str] = None
    tiebreak_skipped_reason: Optional[str] = None
    # 4B.11 CU1 — THE COST PROOF'S TWO NUMBERS. `status` above says WHETHER the
    # cost optimum was proved; these say WHAT was proved and, when it was not,
    # BY HOW MUCH the claim falls short. Both are stage 1's (the cost proof), the
    # same source `status` comes from. Before this the rolling assembler wrote
    # `SolverBlock(gap=None)` unconditionally, so a FEASIBLE rolling board could
    # say only "not proved" and never "not proved, and here is the distance" —
    # which is precisely the distinction 4B.10 §5a.27 measured at 13.056% of
    # ledger. None on a solve that reported neither (never a fabricated 0.0).
    objective: Optional[float] = None
    gap: Optional[float] = None
    # 4B.25 — what the two-stage solve ACTUALLY SPENT, in deterministic units.
    # A portfolio member's row is meant to answer "was it the seed or the
    # budget?" (4B.24 §7(b) says both decide), and it could not: the view
    # carried the budget it was GIVEN nowhere and the budget it USED nowhere
    # either. None on a view whose solve did not report one.
    det_consumed: Optional[float] = None

    @property
    def placed(self) -> dict:
        """committed ∪ active — every op with a bar on the board this window."""
        out = dict(self.committed)
        out.update(self.active)
        return out


def build_rolling_view(
    plant: PreparedPlant,
    window_days: int,
    frozen_days: int,
    gravity: bool = True,
    deterministic: bool = True,
    seed: int = 42,
    member_time_limit_s: float = 30.0,
    det_total: float = _DET_TOTAL_DEFAULT,
    crit_threshold: float = 3.0,
    earliness_value: Optional[float] = None,
    persist: bool = False,
    hint_mode: str = HINT_OFF,
) -> RollingView:
    """Solve the CURRENT window (window 0) and classify the sliced world.

    Reuses the full roll's admission (_admit) and two-stage solve (_two_stage_solve)
    on window 0 only — so the committed/active split and the gravity admission are
    the REAL rolling engine, captured at the reference origin rather than rolled to
    completion. Demands not admitted this window (future work) become the
    beyond-horizon tray. Placed demands are priced + given service outcomes from
    the window solve (an honest current-window projection, not a full-roll price).

    ``persist`` (Session 4B.3c CU1): when True, the window-0 solve is written to
    the plant's canonical snapshot as a FIRST-CLASS RUN — Assignment / ServiceOutcome
    / Schedule entities (extractor ``snapshot_writer``, ``is_scenario=False``, so
    solution-extraction assignments carry RECONSTRUCTED basis as everywhere), plus
    M5 horizon + M6 solve_complete evidence under the plant's ``runs/``. This makes
    the sliced run readable by the Tier-2 sandbox and the M10 Explainer exactly as a
    monolithic run — the connector-era prerequisite the 4B.3a/4B.3b debts named.
    Persistence OBSERVES the solve; it never influences it (the solve values and the
    determinism golden are unchanged — persisting is a pure write after the solve)."""
    if frozen_days > window_days:
        raise ValueError("frozen_days must be <= window_days")
    from mre.modules.extractor import Extractor

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    if not sched:
        raise ValueError("no schedulable demands")

    t0 = ref
    window_end = t0 + timedelta(days=window_days)
    frozen_end = t0 + timedelta(days=frozen_days)
    t0_min = int((t0 - ref).total_seconds() / 60.0)
    frozen_end_min = int((frozen_end - ref).total_seconds() / 60.0)
    win_horizon_end = window_end + timedelta(days=_WINDOW_TAIL_DAYS)

    # A REPORTING rate only (4B.7). It reaches no objective and no cap.
    ev_used = _earliness_rate(plant.cost_model, earliness_value)
    tiebreak = earliness_tiebreak_report(None, None, ev_used)

    def _ops_of(did):
        return plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])

    # workpackage -> [demand ids] (a merged WP may fulfil several demands)
    dem_of_wp: dict = {}
    for d in sched:
        wp = plant.wp_of_demand.get(d["id"])
        if wp is not None:
            dem_of_wp.setdefault(wp, []).append(d["id"])

    admitted, _reasons = _admit(plant, sched, t0, window_end, gravity, crit_threshold)
    # SORTED, not raw set order (Errand session, CU2b). ``admitted`` is a set of
    # demand-id STRINGS; iterating it raw hands the ops to _build_window in
    # hash order, so CP-SAT's variable-creation order — and therefore which
    # tied-optimal placement it returns — moves with PYTHONHASHSEED. Measured on
    # the pinned rolling world: an identical submission at seed 42 with
    # deterministic=True split committed/active 43/13, 38/18, 46/10 under hash
    # seeds 1/2/3. Determinism must not depend on an env var the caller might
    # forget; sorting removes the dependency at the source.
    free_ops = [op for did in sorted(admitted) for op in _ops_of(did)]

    workers = 1 if deterministic else None
    committed: dict = {}
    active: dict = {}
    op_drivers: dict = {}
    ledger: dict = {}
    svc: list = []
    status = "NO_ADMISSION"
    # 4B.8 CU3: with nothing admitted there is no solve at all, so there is no
    # tiebreak proof either — and the reason is stated rather than left blank.
    tiebreak_status: Optional[str] = None
    tiebreak_skipped: Optional[str] = "no_admitted_work"
    placed_demand_ids: set = set()
    wall_truncated = False
    # 4B.11 CU1 — stage 1's objective and gap, so a board that could not prove
    # its optimum can state the distance rather than only the fact.
    objective: Optional[float] = None
    gap: Optional[float] = None
    det_consumed: Optional[float] = None

    # CU1 persistence wiring — reporters + snapshot writer are opened only when
    # ``persist`` is set (the API rolling worker). runs_dir mirrors the spine's
    # (plant.out_dir / "runs"), so window-0 evidence sits beside the M0–M4 records.
    runs_dir = plant.out_dir / "runs"
    win_horizon_start = ref

    if free_ops:
        model, var_map = _build_window(plant, free_ops, [], ref, win_horizon_end)
        win_horizon_start = var_map.horizon_start
        # CU1: ONE M5 run recording the builder's ACTUAL horizon_start
        # (max(min earliest, ref)) — the grid the assignments are written in — so
        # _m5_horizon(evidence) aligns the sandbox/Explainer pin arithmetic with
        # the persisted placements. Recorded after the build so it is exact.
        if persist:
            _report(ModuleCode.M5, "rolling window-0 model build",
                    plant.snapshot_id, runs_dir,
                    {"horizon_start": win_horizon_start.isoformat(),
                     "horizon_end": win_horizon_end.isoformat(),
                     "window_days": window_days, "frozen_days": frozen_days}
                    ).end(RunStatus.SUCCESS)
        free_start_vars = []
        for op in free_ops:
            v = var_map.op_start.get(op["id"])
            if v is not None:
                model.add(v >= t0_min)
                free_start_vars.append(v)
        solve, _stage2, _recovery = _two_stage_solve(
            model, var_map, free_start_vars,
            workers=workers, seed=seed, deterministic=deterministic,
            member_time_limit_s=member_time_limit_s,
            det_total=det_total,
            free_op_ids=[op["id"] for op in free_ops],
            hint_mode=hint_mode)
        tiebreak = earliness_tiebreak_report(_recovery[0], _recovery[1], ev_used)
        # 4B.8 CU3: `solve.status` is now STAGE 1's — the COST proof. Stage 2's
        # rides beside it, never over it.
        status = solve.status
        tiebreak_status = solve.tiebreak_status
        tiebreak_skipped = solve.tiebreak_skipped_reason
        wall_truncated = bool(solve.wall_truncated)
        # 4B.11 CU1 — stage 1's own numbers, carried unchanged. `_two_stage_solve`
        # already returns s1.objective / s1.gap even when stage 2 supplied the
        # placements, so these describe the COST proof and nothing else.
        objective = solve.objective
        gap = solve.gap
        det_consumed = solve.det_consumed
        if solve.status in ("OPTIMAL", "FEASIBLE"):
            sv = solve.solve_values
            for op in free_ops:
                oid = op["id"]
                if oid not in sv.op_start_minutes:
                    continue
                res = sv.op_resource.get(oid)
                if res is None:
                    continue
                s_min = sv.op_start_minutes[oid]
                s_dt = ref + timedelta(minutes=s_min)
                e_dt = ref + timedelta(minutes=sv.op_end_minutes[oid])
                placement = {"resource": res, "start": s_dt.isoformat(),
                             "end": e_dt.isoformat()}
                # Session 4B.13 Item 0 — THE PAUSES TRAVEL WITH THE PLACEMENT.
                # `start`/`end` are the op's overall SPAN; for a resumable op
                # (R-C3) that span includes the calendar pauses between chunks,
                # which are NOT working time. Without the chunk windows every
                # downstream reader of this dict can only reconstruct one
                # bar from first-start to last-end — which is exactly what
                # assemble_rolling_document did, drawing ORD-000011 as a single
                # continuous 5821-minute bar across a weekend CUT-01 is shut.
                # The solver placed it correctly in three windows (1501 working
                # minutes); only the view lost them. Absent/empty for a
                # non-resumable op, so a monolithic-shaped placement is
                # byte-identical to its pre-4B.13 self.
                chunk_windows = sv.op_chunk_windows.get(oid)
                if chunk_windows:
                    placement["chunks"] = [
                        {"start": (ref + timedelta(minutes=cs)).isoformat(),
                         "end":   (ref + timedelta(minutes=ce)).isoformat()}
                        for cs, ce in chunk_windows
                    ]
                if s_min < frozen_end_min:
                    committed[oid] = placement
                else:
                    active[oid] = placement
                for did in dem_of_wp.get(op.get("workpackage_ref", ""), []):
                    placed_demand_ids.add(did)

            # price + service outcomes for the placed (in-window) demands, from
            # THIS window solve (an honest current-window projection).
            wp_ids = {op["workpackage_ref"] for op in free_ops}
            wps = [w for w in plant.workpackages if w["id"] in wp_ids]
            fuls = [f for f in plant.fulfillments if f["workpackage_ref"] in wp_ids]
            dem_ids = {f["demand_ref"] for f in fuls}
            demands = [d for d in plant.demands if d["id"] in dem_ids]
            extract_cm = dict(plant.cost_model)
            extract_cm["earliness_value"] = ev_used

            # CU1: persist the window-0 solve as a first-class run. The M6
            # solve_complete event carries the objective (_incumbent_objective
            # reads it); the extractor writes Assignment/ServiceOutcome/Schedule
            # into the plant's snapshot (is_scenario=False → a real schedule).
            e_rep = None
            m7_writer = None
            if persist:
                s_rep = _report(ModuleCode.M6, "rolling window-0 solve",
                                plant.snapshot_id, runs_dir,
                                {"num_search_workers": workers, "random_seed": seed})
                # `objective` is the STAGE-1 (cost) objective since 4B.7 — see
                # _two_stage_solve. `earliness_tiebreak` rides BESIDE it as its
                # own labelled line and is never summed into any cost figure.
                # 4B.8 CU3: `status` is STAGE 1's (the COST proof) and
                # `tiebreak_status` is stage 2's. The assembler reads this
                # payload on the persisted path, so both proofs must reach it —
                # otherwise the board would still show one proof under the
                # other's name.
                s_rep.record_event(
                    status_text="solve_complete",
                    payload={"status": solve.status, "objective": solve.objective,
                             "gap": solve.gap,
                             "earliness_tiebreak": tiebreak,
                             "tiebreak_status": solve.tiebreak_status,
                             "tiebreak_skipped_reason": solve.tiebreak_skipped_reason})
                s_rep.end(RunStatus.SUCCESS)
                e_rep = _report(ModuleCode.M7, "rolling window-0 extraction",
                                plant.snapshot_id, runs_dir)
                m7_writer = plant.store.extend_snapshot(plant.snapshot_id)
            result = Extractor().extract(
                solve_values=sv, snapshot_id=plant.snapshot_id,
                operations=free_ops, workpackages=wps, resources=plant.resources,
                fulfillments=fuls, demands=demands, cost_model=extract_cm,
                reporter=e_rep, cal_windows=var_map.cal_windows,
                op_eligible=var_map.op_eligible, snapshot_writer=m7_writer,
                overtime_windows=var_map.overtime_windows,
                is_scenario=not persist)
            if persist:
                m7_writer.finalize()
                e_rep.end(RunStatus.SUCCESS)
            ledger = result.cost_ledger
            svc = result.service_outcomes
            op_drivers = {a["operation_ref"]: a.get("driver") for a in result.assignments}

    # BEYOND-HORIZON = every schedulable demand with no placed op this window.
    beyond = [d["id"] for d in sched if d["id"] not in placed_demand_ids]

    return RollingView(
        reference_origin=ref, window_start=t0, window_end=window_end,
        frozen_end=frozen_end, window_days=window_days, frozen_days=frozen_days,
        committed=committed, active=active, beyond_demand_ids=beyond,
        cost_ledger=ledger, service_outcomes=svc, op_drivers=op_drivers,
        win_horizon_start=win_horizon_start, win_horizon_end=win_horizon_end,
        persisted=persist, wall_truncated=wall_truncated,
        det_consumed=det_consumed,
        earliness_value=ev_used, status=status, earliness_tiebreak=tiebreak,
        tiebreak_status=tiebreak_status, tiebreak_skipped_reason=tiebreak_skipped,
        objective=objective, gap=gap)


# ---------------------------------------------------------------------------
# R-BK1 — THE PORTFOLIO AT THE MAIN SOLVE (Session 4B.25 Item 3)
# ---------------------------------------------------------------------------
# `build_rolling_view` above is ONE deterministic search. 4B.24 measured what
# that costs: on the dense demo board, one deterministic unit of unpinned search
# found 0% at seeds 42/43/46, 16.3% cheaper at 44 and 13.2% at 45. The published
# board is whichever of those the shipped seed happened to be.
#
# This wrapper runs K of them and publishes the best by LEDGER. At K=1 — the
# default, and the default until Daryn flips it — it calls `build_rolling_view`
# once with the caller's own seed and returns no portfolio at all, so nothing
# about today's path changes and no block reaches the document. That is clause
# (2)'s compatibility promise, and `tests/test_portfolio.py` proves it by
# schedule digest rather than asserting it.
# ---------------------------------------------------------------------------

def _ledger_total(view: "RollingView") -> Optional[float]:
    """A view's LEDGER total — the selection key (clause 3). None when the solve
    produced no ledger, which makes the member unpublishable rather than free."""
    total = (view.cost_ledger or {}).get("total_cost")
    return None if total is None else round(float(total), 2)


def _member_from_view(seed: int, view: "RollingView", wall_s: float):
    """One portfolio member, read off a completed window solve."""
    from mre.modules import portfolio as pf

    if view.wall_truncated:
        # CLAUSE (1): a search the WALL stopped is not reproducible, so it is
        # not a member — the same refusal 4B.24 put on the sandbox baseline, for
        # the same reason. It is still REPORTED (clause 4).
        return pf.unusable(seed, pf.WALL_STOPPED_REASON, status=view.status,
                           wall_truncated=True,
                           det_consumed=getattr(view, "det_consumed", None),
                           wall_time_s=round(wall_s, 3))
    total = _ledger_total(view)
    if total is None or view.status not in ("OPTIMAL", "FEASIBLE"):
        return pf.unusable(
            seed, f"the window solve returned {view.status or 'no result'} with "
                  f"no ledger to compare", status=view.status,
            det_consumed=getattr(view, "det_consumed", None),
            wall_time_s=round(wall_s, 3))
    return pf.PortfolioMember(seed=seed, ledger_total=total, status=view.status,
                              det_consumed=getattr(view, "det_consumed", None),
                              wall_time_s=round(wall_s, 3))


#: The spec a PARALLEL member carries into its own process. Plain data only —
#: everything here must survive a pickle and a spawn (Windows), which is why it
#: is the submission path and the coefficients rather than the PreparedPlant.
_MEMBER_KEYS = ("submission_dir", "reference_date", "policy", "window_days",
                "frozen_days", "gravity", "member_time_limit_s", "det_total",
                "crit_threshold", "earliness_value", "hint_mode")


def _portfolio_member_process(spec_and_seed) -> "object":
    """ONE PORTFOLIO MEMBER, IN ITS OWN PROCESS (clause 5).

    Module-level and plain-data-in so it is picklable under spawn. It re-runs
    the spine into its OWN scratch directory: two processes must never write one
    ``out_dir``, and the spine is deterministic, so a plant prepared twice from
    one submission is the same plant. It returns ONLY a
    :class:`~mre.modules.portfolio.PortfolioMember` — the placements stay in the
    process that found them and the winner is re-solved in the parent, which is
    safe for exactly the reason clause (1) exists.
    """
    import tempfile
    import time as _time
    from mre.modules import portfolio as pf

    spec, seed = spec_and_seed
    t0 = _time.monotonic()
    tmp = tempfile.mkdtemp(prefix=f"mre-portfolio-{seed}-")
    try:
        plant = prepare_plant(spec["submission_dir"], tmp,
                              reference_date=spec["reference_date"],
                              policy=spec["policy"])
        view = build_rolling_view(
            plant, window_days=spec["window_days"],
            frozen_days=spec["frozen_days"], gravity=spec["gravity"],
            deterministic=True, seed=seed,
            member_time_limit_s=spec["member_time_limit_s"],
            det_total=spec["det_total"], crit_threshold=spec["crit_threshold"],
            earliness_value=spec["earliness_value"], persist=False,
            hint_mode=spec["hint_mode"])
        return _member_from_view(seed, view, _time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001 — one dead seed never loses the rest
        return pf.unusable(seed, f"member failed: {type(exc).__name__}: {exc}",
                           wall_time_s=round(_time.monotonic() - t0, 3))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


class PortfolioDrift(RuntimeError):
    """The winner re-solved to a DIFFERENT ledger than the member that won.

    That cannot happen under clause (1), so if it does, the portfolio is not
    deterministic and its selection means nothing. Raising is the only honest
    response: publishing the re-solve would ship a board whose declaration
    ("best of K") is a claim about a search that did not produce it."""


def solve_rolling_portfolio(
    plant: PreparedPlant,
    window_days: int,
    frozen_days: int,
    gravity: bool = True,
    deterministic: bool = True,
    seed: int = 42,
    member_time_limit_s: float = 30.0,
    det_total: float = _DET_TOTAL_DEFAULT,
    crit_threshold: float = 3.0,
    earliness_value: Optional[float] = None,
    persist: bool = False,
    hint_mode: str = HINT_OFF,
    *,
    k: int = 1,
    portfolio_workers: int = 1,
    k_declared: bool = False,
    det_time_declared: bool = False,
) -> tuple:
    """Solve the current window as a DECLARED PORTFOLIO (R-BK1). Returns
    ``(RollingView, Portfolio | None)``.

    ``seed`` is the portfolio's ``seed0``: members take ``seed .. seed+k-1``,
    consecutive by ruling, so nobody can quietly pick the seed that wins on the
    board in front of them.

    **K = 1 IS EXACTLY ``build_rolling_view``**, called once, with no extra
    solve, no scratch directory and no portfolio — the returned Portfolio is
    None and the assembler therefore emits no block.

    At K > 1 the members run with ``persist=False`` (they are probes; only their
    ledger totals matter), the winner is chosen by :func:`portfolio.select`, and
    the winner's seed is then re-solved with the caller's own ``persist`` so the
    artifacts on disk belong to the schedule being published. That re-solve is
    ONE extra solve — K+1 in total — and it is not waste: its ledger is checked
    against the member's, which is the portfolio's determinism asserted rather
    than assumed.

    ``deterministic=False`` cannot be a portfolio at all: without a
    deterministic budget the members are not runs, they are draws, and
    "the best of five draws" is a number with no meaning. K > 1 with
    ``deterministic=False`` raises.
    """
    from mre.modules import portfolio as pf

    if k < 1:
        raise ValueError(f"a portfolio needs at least one member, got k={k}")
    if k == 1:
        return build_rolling_view(
            plant, window_days=window_days, frozen_days=frozen_days,
            gravity=gravity, deterministic=deterministic, seed=seed,
            member_time_limit_s=member_time_limit_s, det_total=det_total,
            crit_threshold=crit_threshold, earliness_value=earliness_value,
            persist=persist, hint_mode=hint_mode), None
    if not deterministic:
        raise ValueError(
            "a portfolio of non-deterministic members is a portfolio of draws — "
            "R-BK1 clause (1) requires every member to be fully deterministic")

    seeds = pf.seeds_for(k, seed)
    t_start = time.monotonic()
    views: dict = {}

    if portfolio_workers > 1:
        if plant.submission_dir is None:
            raise ValueError(
                "a process-parallel portfolio re-prepares the plant in each "
                "worker, so the plant must know the submission it came from; "
                "this one does not (prepare_plant records it)")
        spec = {"submission_dir": str(plant.submission_dir),
                "reference_date": plant.reference_date,
                "policy": "identity_v1",
                "window_days": window_days, "frozen_days": frozen_days,
                "gravity": gravity,
                "member_time_limit_s": member_time_limit_s,
                "det_total": det_total, "crit_threshold": crit_threshold,
                "earliness_value": earliness_value, "hint_mode": hint_mode}
        members = pf.run_members(
            _ProcessMember(spec), seeds, workers=portfolio_workers)
    else:
        members = []
        for s in seeds:
            t0 = time.monotonic()
            try:
                v = build_rolling_view(
                    plant, window_days=window_days, frozen_days=frozen_days,
                    gravity=gravity, deterministic=True, seed=s,
                    member_time_limit_s=member_time_limit_s,
                    det_total=det_total, crit_threshold=crit_threshold,
                    earliness_value=earliness_value, persist=False,
                    hint_mode=hint_mode)
            except Exception as exc:  # noqa: BLE001
                members.append(pf.unusable(
                    s, f"member failed: {type(exc).__name__}: {exc}",
                    wall_time_s=round(time.monotonic() - t0, 3)))
                continue
            views[s] = v
            members.append(_member_from_view(s, v, time.monotonic() - t0))

    book = pf.build(k, seed, det_total, members, workers=portfolio_workers,
                    wall_time_s=time.monotonic() - t_start,
                    k_declared=k_declared, det_time_declared=det_time_declared)
    winner = book.winner
    if winner is None:
        # NOT a failure of the plant and not a schedule we refuse to publish:
        # the portfolio found nothing publishable, so we fall back to the
        # single-seed path with the declared seed0 and the block says so.
        view = build_rolling_view(
            plant, window_days=window_days, frozen_days=frozen_days,
            gravity=gravity, deterministic=True, seed=seed,
            member_time_limit_s=member_time_limit_s, det_total=det_total,
            crit_threshold=crit_threshold, earliness_value=earliness_value,
            persist=persist, hint_mode=hint_mode)
        return view, book

    cached = views.get(winner.seed)
    if cached is not None and not persist:
        return cached, book

    view = build_rolling_view(
        plant, window_days=window_days, frozen_days=frozen_days,
        gravity=gravity, deterministic=True, seed=winner.seed,
        member_time_limit_s=member_time_limit_s, det_total=det_total,
        crit_threshold=crit_threshold, earliness_value=earliness_value,
        persist=persist, hint_mode=hint_mode)
    final = _ledger_total(view)
    if final is None or abs(final - winner.ledger_total) > 0.01:
        raise PortfolioDrift(
            f"seed {winner.seed} won the portfolio at ${winner.ledger_total:,.2f} "
            f"and re-solved to {final if final is None else f'${final:,.2f}'} — "
            "the portfolio is not deterministic and its selection is meaningless")
    return view, book


class _ProcessMember:
    """A picklable ``seed -> PortfolioMember`` closure-substitute (clause 5).

    ``run_members`` calls ``fn(seed)``; under a process pool that callable must
    survive a pickle, which a real closure does not. This is the smallest thing
    that does."""

    __slots__ = ("spec",)

    def __init__(self, spec: dict):
        self.spec = spec

    def __call__(self, seed: int):
        return _portfolio_member_process((self.spec, seed))


# ---------------------------------------------------------------------------
# CU5 (R-SC3) — manned-idle minutes as an EVIDENCE metric (never an objective).
# Total idle is conserved for a fixed book (only its position moves), so it is
# provably inert as an objective and belongs in Metrics — R-SC3(3).
# ---------------------------------------------------------------------------

def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for s, e in sorted(intervals):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _overlap_minutes(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> int:
    """Total minutes where merged interval-lists a and b overlap."""
    total = 0
    for s1, e1 in a:
        for s2, e2 in b:
            lo, hi = max(s1, s2), min(e1, e2)
            if hi > lo:
                total += hi - lo
    return total


def compute_manned_idle_metrics(resources, calendars, committed, ref,
                                horizon_end) -> list[dict]:
    """Per-resource manned-idle minutes within the scheduled horizon:
    calendar-OPEN minutes (from `ref` to the last committed placement) minus
    the minutes a committed placement actually occupies an open window. Pure
    arithmetic over the flattened calendars and the committed placements — no
    solve, no objective. Returns one dict per resource with a machine-scheduled
    op, sorted by resource_id (deterministic)."""
    flat = flatten_all_calendars(calendars, ref, horizon_end)
    windows_by_cal: dict[str, list[tuple[int, int]]] = {}
    for cal in flat:
        wins = []
        for w in cal.get("horizon_resolved", []):
            s = int(round((_dt(w["start"]) - ref).total_seconds() / 60.0))
            e = int(round((_dt(w["end"]) - ref).total_seconds() / 60.0))
            if e > s:
                wins.append((s, e))
        windows_by_cal[cal["id"]] = _merge_intervals(wins)
    cal_of_res = {r["id"]: r.get("calendar_ref") for r in resources}

    busy_by_res: dict[str, list[tuple[int, int]]] = {}
    sched_end = 0
    for oid, c in committed.items():
        s = int(round((_dt(c["start"]) - ref).total_seconds() / 60.0))
        e = int(round((_dt(c["end"]) - ref).total_seconds() / 60.0))
        busy_by_res.setdefault(c["resource"], []).append((s, e))
        sched_end = max(sched_end, e)

    metrics: list[dict] = []
    for rid in sorted(busy_by_res):
        cal_id = cal_of_res.get(rid)
        open_wins = [(s, e) for (s, e) in windows_by_cal.get(cal_id, []) if s < sched_end]
        open_wins = _merge_intervals([(s, min(e, sched_end)) for s, e in open_wins])
        busy = _merge_intervals(busy_by_res[rid])
        open_min = sum(e - s for s, e in open_wins)
        busy_open = _overlap_minutes(open_wins, busy)
        metrics.append({
            "resource_id": rid,
            "calendar_open_minutes": open_min,
            "busy_minutes": busy_open,
            "manned_idle_minutes": max(0, open_min - busy_open),
        })
    return metrics


def record_idle_metrics(reporter, metrics: list[dict], snapshot_id: str) -> None:
    """Emit per-resource manned-idle Metrics plus a plant-level rollup that
    decomposes EXACTLY (rollup_of the per-resource values) — the consolidator's
    decomposition rule. No-op when reporter is None (the measurement harness)."""
    if reporter is None or not metrics:
        return
    from mre.contracts.entities import EntityRef
    from mre.contracts.vocabularies import RecordTier
    for m in metrics:
        reporter.record_metric(
            name="manned_idle_minutes", value=float(m["manned_idle_minutes"]),
            unit="minutes",
            subjects=[EntityRef(entity_id=m["resource_id"], entity_type="resource")],
            tier=RecordTier.SUPPORTING,
            message=f"{m['resource_id']}: {m['manned_idle_minutes']} manned-idle min")


# ---------------------------------------------------------------------------
# admission (the time window + gravity)
# ---------------------------------------------------------------------------

def _weight(plant: PreparedPlant, d: dict) -> float:
    cc = d.get("commitment_class") or "standard"
    return float(plant.priority_multipliers.get(cc, 1.0))


def _latest_feasible_start(plant: PreparedPlant, d: dict) -> datetime:
    due = _dt(d["due"])
    mins = plant.demand_working_minutes.get(d["id"], 0)
    days = max(1, -(-mins // _SHIFT_MIN))     # ceil working days
    return due - timedelta(days=days)


def _admit(plant, candidates, window_start, window_end, gravity, crit_threshold):
    """Return (admitted_ids:set, reasons:dict). candidates = demands with >=1
    uncommitted op. Base = due within window AND released by window_end."""
    admitted: set = set()
    reasons: dict = {"base": 0, "a_must_start": 0, "b_criticality": 0, "c_family": 0}
    for d in candidates:
        es = _dt(d["earliest_start"]) if d.get("earliest_start") else window_start
        if es > window_end:
            continue
        if _dt(d["due"]) <= window_end:
            admitted.add(d["id"])
            reasons["base"] += 1
    if not gravity:
        return admitted, reasons
    window_families: set = set()
    for did in admitted:
        window_families |= plant.demand_families.get(did, set())
    # criticality-sorted single pass so family affinity sees the base + earlier pulls
    for d in sorted(candidates, key=lambda x: -_weight(plant, x)):
        if d["id"] in admitted:
            continue
        es = _dt(d["earliest_start"]) if d.get("earliest_start") else window_start
        if es > window_end:
            continue
        if _latest_feasible_start(plant, d) <= window_end:
            admitted.add(d["id"]); reasons["a_must_start"] += 1
            window_families |= plant.demand_families.get(d["id"], set())
        elif _weight(plant, d) >= crit_threshold:
            admitted.add(d["id"]); reasons["b_criticality"] += 1
            window_families |= plant.demand_families.get(d["id"], set())
        elif plant.demand_families.get(d["id"], set()) & window_families:
            admitted.add(d["id"]); reasons["c_family"] += 1
    return admitted, reasons


def gravity_admitted_demand_ids(plant, candidates, window_start, window_end,
                                crit_threshold: float = 3.0) -> set:
    """The demands this window admitted BY GRAVITY rather than by the time
    window — exactly ``admitted(gravity=True) − admitted(gravity=False)``.

    Session 4B.6 CU3 needs this to label a coarse prediction's realization
    intake path: a demand pulled in early by gravity is TWO MECHANISMS ON RECORD
    DISAGREEING about the same job (the coarse model said "week 3", gravity said
    "now"), and the conformance report counts those rather than smoothing them.

    Pure arithmetic over ``_admit`` — no solve, no state, and NOTHING here feeds
    back into admission (clause 4: coarse never constrains fine, nor its
    admission policy)."""
    with_gravity, _ = _admit(plant, candidates, window_start, window_end,
                             True, crit_threshold)
    base_only, _ = _admit(plant, candidates, window_start, window_end,
                          False, crit_threshold)
    return set(with_gravity) - set(base_only)


# ---------------------------------------------------------------------------
# per-window model build (subset of the canonical entities)
# ---------------------------------------------------------------------------

def _build_window(plant, free_ops, pinned_ops, ref, horizon_end):
    """Build the window model with an ABSOLUTE origin (ref), over the free
    operations (admitted, not yet committed) PLUS the still-overlapping committed
    (pinned) operations. Free ops are floored at t0 and pinned ops fixed by the
    CALLER. The single ref origin lets committed work that began before this
    window pin at a non-negative offset while free work is floored at t0."""
    from mre.modules.solver_builder import SolverBuilder

    ops = free_ops + pinned_ops
    wp_ids = {op["workpackage_ref"] for op in ops}
    wps = [w for w in plant.workpackages if w["id"] in wp_ids]
    fuls = [f for f in plant.fulfillments if f["workpackage_ref"] in wp_ids]
    dem_ids = {f["demand_ref"] for f in fuls}
    demands = [d for d in plant.demands if d["id"] in dem_ids]
    edges = plant.edges   # spec-level; builder resolves per-WP, skips absent (§665)

    cals = flatten_all_calendars(plant.calendars, ref, horizon_end)
    builder = SolverBuilder(reference_date=ref)
    model, var_map = builder.build(
        wps + ops + edges, plant.resources + plant.pools, cals,
        fuls + demands, plant.constraints, plant.cost_model)
    return model, var_map


# ---------------------------------------------------------------------------
# the rolling loop
# ---------------------------------------------------------------------------

def run_rolling_horizon(
    plant: PreparedPlant,
    window_days: int,
    frozen_days: int,
    gravity: bool = True,
    deterministic: bool = True,
    seed: int = 0,
    member_time_limit_s: float = 30.0,
    det_total: float = _DET_TOTAL_DEFAULT,
    crit_threshold: float = 3.0,
    standing_pins: Optional[list[dict]] = None,
    max_windows: Optional[int] = None,
    earliness_value: Optional[float] = None,
    window_observer: Optional[Any] = None,
    hint_mode: str = HINT_OFF,
) -> RollingResult:
    """Roll a window of `window_days`, committing the frozen front of
    `frozen_days`, until every operation is committed.

    R-SC3: `earliness_value` ($/min of op-start earliness) overrides the declared
    CostModel.earliness_value when given (None => read the declared value); 0 =>
    earliness is a pure zero-cost tiebreak (the FLOOR). Every window solves in the
    two-stage shape (_two_stage_solve)."""
    from mre.modules import standing_pins as sp

    if frozen_days > window_days:
        raise ValueError("frozen_days must be <= window_days")

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    sched = plant.schedulable_demands
    if not sched:
        raise ValueError("no schedulable demands")
    last_due = max(_dt(d["due"]) for d in sched if d.get("due"))
    horizon_days = max(1, (last_due - ref).days)
    if max_windows is None:
        # enough windows to cover the horizon AND a generous late tail (an
        # overloaded plant schedules work well past its due dates); a final
        # sweep (below) catches anything the cap leaves uncommitted.
        max_windows = (2 * horizon_days // frozen_days) + 20

    import time as _t
    from mre.modules.solver_builder import apply_solution_hints

    committed: dict = {}                   # op_id -> {resource, start, end}  (placements)
    last_placements: list[dict] = []       # warm-start carry (all solved ops)
    windows: list[WindowMetric] = []
    total_solve = total_build = 0.0
    workers = 1 if deterministic else None
    sp_norm = [sp.normalize_pin(p) for p in (standing_pins or [])]
    earliness_used = _earliness_rate(plant.cost_model, earliness_value)

    # A windowed build only needs to reach far enough to place near-term work
    # (free ops are earliness-pulled and floored at t0), so a MODEST horizon
    # keeps the per-window build cheap — the whole point of slicing. The global
    # horizon end (max due + full buffer) is used only by the final pricing pass.
    global_horizon_end = last_due.replace(hour=23, minute=59, second=59) + \
        timedelta(days=_HORIZON_BUFFER_DAYS)
    all_ops_of_sched = [op for op in plant.operations
                        if op["workpackage_ref"] in
                        {plant.wp_of_demand.get(d["id"]) for d in sched}]
    total_op_count = len(all_ops_of_sched)

    def _ops_of(did):
        return plant.ops_by_wp.get(plant.wp_of_demand.get(did), [])

    for i in range(max_windows):
        t0 = ref + timedelta(days=i * frozen_days)
        window_end = t0 + timedelta(days=window_days)
        frozen_end = t0 + timedelta(days=frozen_days)
        t0_min = int((t0 - ref).total_seconds() / 60.0)
        frozen_end_min = int((frozen_end - ref).total_seconds() / 60.0)

        # candidate demands: any op not yet committed
        remaining = [d for d in sched
                     if any(op["id"] not in committed for op in _ops_of(d["id"]))]
        if not remaining:
            break
        admitted, reasons = _admit(plant, remaining, t0, window_end,
                                   gravity, crit_threshold)
        if not admitted:
            continue

        # sorted() — see build_rolling_view: raw set order makes the window
        # solve PYTHONHASHSEED-dependent (Errand session, CU2b).
        free_ops = [op for did in sorted(admitted) for op in _ops_of(did)
                    if op["id"] not in committed]
        # committed operations still overlapping this window (end > t0) are pinned;
        # those fully in the past cannot conflict with free work floored at t0.
        pinned_ops = [op for op in all_ops_of_sched
                      if op["id"] in committed and _dt(committed[op["id"]]["end"]) > t0]
        committed_at_build = dict(committed)   # pin sources, before this window commits

        win_horizon_end = min(global_horizon_end,
                              window_end + timedelta(days=_WINDOW_TAIL_DAYS))
        t_b = _t.perf_counter()
        model, var_map = _build_window(plant, free_ops, pinned_ops, ref, win_horizon_end)
        build_wall = _t.perf_counter() - t_b
        total_build += build_wall

        free_start_vars = []
        for op in free_ops:
            v = var_map.op_start.get(op["id"])
            if v is not None:
                model.add(v >= t0_min)          # no scheduling in the past
                free_start_vars.append(v)
        for op in pinned_ops:                   # fix carried commitments (absolute)
            c = committed.get(op["id"])
            if not c or op["id"] not in var_map.op_start:
                continue
            smin = int(round((_dt(c["start"]) - ref).total_seconds() / 60.0))
            try:
                sp.apply_pin(model, var_map, op["id"], c["resource"], max(0, smin))
            except Exception:
                pass
        # Warm-start + standing pins seed BEFORE stage 1 (the two-stage solve
        # re-seeds its own hints from the stage-1 incumbent).
        if last_placements:
            apply_solution_hints(model, var_map, last_placements)
        if sp_norm:
            sp.apply_standing_pins(model, var_map, sp_norm, var_map.horizon_start)

        # R-SC3 two-stage: stage 1 minimizes COST; stage 2 caps the stage-1
        # objective and re-minimizes Σ free-op starts (the zero-cost earliest-start
        # tiebreak that makes the frozen front fill). No hidden weight-1 incentive,
        # and since 4B.7 no declared price in the primary objective either.
        t_s = _t.perf_counter()
        solve, _stage2, _recovery = _two_stage_solve(
            model, var_map, free_start_vars,
            workers=workers, seed=seed, deterministic=deterministic,
            member_time_limit_s=member_time_limit_s,
            det_total=det_total, hint_mode=hint_mode)
        solve_wall = _t.perf_counter() - t_s
        total_solve += solve_wall

        committed_this = 0
        win_starts: dict = {}          # op_id -> solved start_min (for the observer)
        win_committed_ids: list = []   # ops committed THIS window (frozen front)
        if solve.status in ("OPTIMAL", "FEASIBLE"):
            sv = solve.solve_values
            placements = []
            for op in free_ops:
                oid = op["id"]
                if oid not in sv.op_start_minutes:
                    continue
                res = sv.op_resource.get(oid)
                if res is None:
                    continue
                s_min = sv.op_start_minutes[oid]
                win_starts[oid] = s_min
                s_dt = ref + timedelta(minutes=s_min)
                e_dt = ref + timedelta(minutes=sv.op_end_minutes[oid])
                placements.append({"operation_ref": oid, "resource_id": res,
                                   "start": s_dt.isoformat(),
                                   "run_windows": [{"start": s_dt.isoformat(),
                                                    "end": e_dt.isoformat()}]})
                # FROZEN ZONE: commit every operation STARTING within the frozen
                # front (op-level, so a long job freezes piecewise as it rolls).
                if s_min < frozen_end_min:
                    committed[oid] = {"resource": res, "start": s_dt.isoformat(),
                                      "end": e_dt.isoformat()}
                    committed_this += 1
                    win_committed_ids.append(oid)
            last_placements = placements

        windows.append(WindowMetric(
            index=i, window_start=t0.isoformat(),
            window_end=window_end.isoformat(), frozen_end=frozen_end.isoformat(),
            admitted_demands=len(admitted), free_ops=len(free_ops),
            committed_this_window=committed_this, gravity_admits=reasons,
            status=solve.status, objective=solve.objective,
            solve_wall_s=round(solve_wall, 3), build_wall_s=round(build_wall, 3)))

        # Observer hook (measurement only, no behavior change): hand the caller
        # the raw inputs needed to REBUILD this exact window's model standalone
        # (for latency timing on a LOADED window — Session 4B.2c CU2).
        if window_observer is not None:
            window_observer({
                "index": i, "free_ops": list(free_ops),
                "pinned_ops": list(pinned_ops),
                "committed": committed_at_build,
                "ref": ref, "win_horizon_end": win_horizon_end,
                "t0_min": t0_min, "frozen_end_min": frozen_end_min,
                "free_op_count": len(free_ops),
                "win_starts": win_starts, "committed_this_ids": win_committed_ids,
                "committed_after": dict(committed),
                "solve_status": solve.status,
                "solve_wall_s": round(solve_wall, 3),
                "build_wall_s": round(build_wall, 3)})

        if len(committed) >= total_op_count:
            break

    # RESOLVE + PRICE: one full solve that PINS the committed operations and
    # places any leftovers (a demand the window cap never reached) FREELY around
    # them, then extracts the exact decomposed cost. Same method for every
    # window setting => a fair curve.
    ledger, svc, tot_cost, uncommitted, op_drivers = _final_extract(
        plant, committed, seed, deterministic, sched, det_total,
        earliness_used)
    on_time = sum(1 for s in svc if s.get("lateness_minutes", 0) <= 0)
    late = sum(1 for s in svc if s.get("lateness_minutes", 0) > 0)
    tard = sum(max(0, s.get("lateness_minutes", 0)) for s in svc)

    # CU5: manned-idle minutes over the committed placements (evidence, not objective).
    idle = compute_manned_idle_metrics(plant.resources, plant.calendars, committed,
                                       ref, global_horizon_end)

    return RollingResult(
        window_days=window_days, frozen_days=frozen_days, gravity=gravity,
        windows=windows, committed_ops=committed, n_windows=len(windows),
        total_solve_wall_s=round(total_solve, 3),
        total_build_wall_s=round(total_build, 3),
        total_cost=tot_cost, cost_ledger=ledger, service_outcomes=svc,
        on_time=on_time, late=late, total_tardiness_minutes=tard,
        uncommitted_ops=uncommitted, earliness_value=earliness_used,
        op_drivers=op_drivers, idle_metrics=idle)


# ---------------------------------------------------------------------------
# final exact cost — one Extractor pass over the fully-pinned committed union
# ---------------------------------------------------------------------------

def reference_solve(plant, *, seed=42, deterministic=True, det_total=_DET_TOTAL_DEFAULT,
                    earliness_value=None, two_stage=True):
    """A NON-rolling reference solve: build the full model over every schedulable
    op (no windowing, no pins), solve it, and extract the exact ledger. Used by
    the R-SC3 counterfactual tests where cost-invariance of the FLOOR is provable
    (a single solve with a cost cap can only reshuffle starts, never change cost).
    `two_stage=False` gives the plain cost-only baseline (stage 1 only).
    Returns (cost_ledger, service_outcomes, op_drivers, total_cost, placements)
    where placements is op_id -> {resource, start(iso), end(iso)}."""
    sched = plant.schedulable_demands
    ev_used = _earliness_rate(plant.cost_model, earliness_value)
    placements: dict = {}
    ledger, svc, tot, _leftover, drivers = _final_extract(
        plant, placements, seed, deterministic, sched, det_total,
        ev_used if two_stage else 0.0, two_stage=two_stage)
    return ledger, svc, drivers, tot, placements


def _final_extract(plant, committed, seed, deterministic, sched, det_total=48.0,
                   earliness_value=0.0, two_stage=True):
    """Build the full model over every scheduled demand's operations, PIN the
    committed operations to their rolling placement, let any leftovers place
    FREELY around the pins (so they cannot conflict), solve in the same R-SC3
    two-stage shape, then extract the exact decomposed ledger + service outcomes.
    `two_stage=False` runs stage 1 only (the plain cost-only baseline).
    Returns (ledger, service_outcomes, total_cost, leftover_count, op_drivers)."""
    from mre.modules.solver_builder import SolverBuilder
    from mre.modules.extractor import Extractor
    from mre.modules import standing_pins as sp

    sched_ids = {d["id"] for d in sched}
    wp_ids = {plant.wp_of_demand.get(did) for did in sched_ids}
    wp_ids.discard(None)
    ops = [op for op in plant.operations if op["workpackage_ref"] in wp_ids]
    wps = [w for w in plant.workpackages if w["id"] in wp_ids]
    fuls = [f for f in plant.fulfillments if f["demand_ref"] in sched_ids]
    demands = [d for d in plant.demands if d["id"] in sched_ids]
    edges = plant.edges   # spec-level; builder resolves per-WP, skips absent (§665)

    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    dues = [_dt(d["due"]) for d in demands if d.get("due")]
    ends = [_dt(c["end"]) for c in committed.values()]
    # Every op is pinned to a known placement (or a small free leftover set), so
    # a modest horizon past the last placement/due suffices — no full buffer.
    horizon_end = (max(dues + ends) if (dues or ends) else ref).replace(
        hour=23, minute=59, second=59) + timedelta(days=_WINDOW_TAIL_DAYS)
    cals = flatten_all_calendars(plant.calendars, ref, horizon_end)

    builder = SolverBuilder(reference_date=ref)
    model, var_map = builder.build(
        wps + ops + edges, plant.resources + plant.pools, cals,
        fuls + demands, plant.constraints, plant.cost_model)

    hstart = var_map.horizon_start
    pinned_oids: set = set()
    for oid, c in committed.items():
        if oid not in var_map.op_start:
            continue
        start_min = int(round((_dt(c["start"]) - hstart).total_seconds() / 60.0))
        try:
            sp.apply_pin(model, var_map, oid, c["resource"], max(0, start_min))
            pinned_oids.add(oid)
        except Exception:
            pass  # a splittable/edge case that resists pinning — priced by solve

    workers = 1 if deterministic else None
    # Free starts for the two-stage tiebreak = the leftover (unpinned) ops; the
    # pinned committed ops are fixed, so earliness only shapes any leftover placement.
    # two_stage=False (the plain cost-only baseline) suppresses stage 2 entirely.
    free_start_vars = ([var_map.op_start[o["id"]] for o in ops
                        if o["id"] not in pinned_oids and o["id"] in var_map.op_start]
                       if two_stage else [])
    solve, _stage2, _recovery = _two_stage_solve(
        model, var_map, free_start_vars,
        workers=workers, seed=seed, deterministic=deterministic,
        member_time_limit_s=120.0,
        # This call site's historical split was stage 1 = 32.0 and a fixed
        # stage 2 = 16.0 — a 48.0 total, which is the default above. Preserved
        # exactly; only the split is now derived.
        det_total=det_total)
    if solve.status not in ("OPTIMAL", "FEASIBLE"):
        return {}, [], None, len([o for o in ops if o["id"] not in committed]), {}

    # record any leftover (uncommitted) operations' placements from this solve
    sv = solve.solve_values
    leftovers = 0
    for op in ops:
        oid = op["id"]
        if oid in committed or oid not in sv.op_start_minutes:
            continue
        res = sv.op_resource.get(oid)
        if res is None:
            continue
        committed[oid] = {
            "resource": res,
            "start": (sv.horizon_start + timedelta(minutes=sv.op_start_minutes[oid])).isoformat(),
            "end": (sv.horizon_start + timedelta(minutes=sv.op_end_minutes[oid])).isoformat()}
        leftovers += 1

    # The extractor's earliness attribution must reflect the RUN's effective
    # coefficient (a coeff-0 override must not attribute EARLINESS_PREFERENCE even
    # when the snapshot declares a positive earliness_value).
    extract_cm = dict(plant.cost_model)
    extract_cm["earliness_value"] = earliness_value
    result = Extractor().extract(
        solve_values=solve.solve_values, snapshot_id=plant.snapshot_id,
        operations=ops, workpackages=wps, resources=plant.resources,
        fulfillments=fuls, demands=demands, cost_model=extract_cm,
        reporter=None, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=None,
        overtime_windows=var_map.overtime_windows, is_scenario=True)
    ledger = result.cost_ledger
    # op -> primary driver (the extractor attributes a dearer-but-earlier eligible
    # placement to EARLINESS_PREFERENCE when earliness_value > 0 — R-SC3 / CU3).
    op_drivers = {a["operation_ref"]: a.get("driver") for a in result.assignments}
    return (ledger, result.service_outcomes, ledger.get("total_cost"),
            leftovers, op_drivers)
