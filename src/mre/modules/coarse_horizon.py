"""M-coarse — THE COARSE ZONE (R-SC2 amendment, Session 4B.6).

R-SC2 closed with "far-horizon look-ahead pricing: named, parked". This module
discharges that clause: beyond-horizon demand is **coarsely placed** rather than
merely listed. The seven clauses of the amendment (docs/04, 2026-07-27) govern
every line here; the ones that constrain the CODE are restated where they bite.

CLAUSE (1) — RELAXATION, ALWAYS. The coarse model is a relaxation of the fine
model: every fine-feasible schedule maps to a coarse-feasible allocation. Only
the NEGATIVE is claimed — **coarse-INFEASIBLE implies fine-INFEASIBLE**. The
converse is never asserted in code, certificate, or AI answer. ``tests/
test_coarse_horizon.py`` makes this a theorem rather than a hope (the relaxation
guard, CU4) and its negative control proves the guard can go red.

CLAUSE (2) — THE PROOF RUN AND THE PLANNING RUN ARE DIFFERENT RUNS. The negative
in (1) may be claimed ONLY from ``run_label="proof"`` (rho = 1.0, restricted to
ops that fit within one bucket). ``run_label="planning"`` (rho as declared)
produces planning SIGNAL and is labeled as such; it may never be cited as a
proof of infeasibility. ``CoarseRun.proves_infeasible`` is the only gate through
which the negative is allowed out, and it is False for every planning run.

CLAUSE (3) — rho IS A DECLARED IDS COEFFICIENT (docs/06 §5.9,
``cost_model.refinements.coarse_horizon``), carried on the canonical CostModel,
visible in the certificate, customer-tunable. It is NEVER a constant in solver
code: ``CoarseCoefficients`` reads it from the cost model and records whether it
was DECLARED or DEFAULTED, and the defaulted value is 1.0 — a no-op derate, so
an undeclared plant gets no silent invented margin. (R-SC3's hidden-weight
prohibition, applied here.)

CLAUSE (4) — COARSE NEVER CONSTRAINS FINE, NOR ITS ADMISSION POLICY. Nothing in
this module is read by ``rolling_horizon._admit`` or by the window build. The
window solve re-decides from scratch. Unlock condition, stated so it is a
decision and not a drift: revisit only once the conformance report (CU3) shows
coarse bucket-tardiness is calibrated.

CLAUSE (5) — TWO LEDGERS, NEVER FUSED. Coarse currency and fine currency never
sum into one headline figure. This module reports tardiness in BUCKETS, never in
dollars, precisely so no caller can add it to a fine ledger by accident.

CLAUSE (6) — COARSE NEVER RENDERS AS A BAR. Bars mean placement. The output here
is load: ``CoarseRun.density`` is a per-resource-per-bucket band.

CLAUSE (7) — THE CONFORMANCE REPORT IS OURS TO PUBLISH. Every prediction is
persisted (``coarse_predictions.py``) and compared against its realization.

y[op, res] MACHINE SELECTION IS A FEASIBILITY WITNESS, NOT A PLAN. The
``resource_witness`` on a placement exists because per-resource capacity cannot
be checked honestly without deciding, per op, which resource's bucket budget it
consumes. It is NOT rendered as an assignment, it is NOT an intention, and the
fine solve re-decides it freely. Every field carrying it says "witness".

ORTOOLS SURFACE. CLAUDE.md's working style quarantines ortools to
solver_builder / solve_runner. This module is a SECOND, structurally different
model (a bucketed load relaxation, not the fine time-indexed model), so it
carries its own narrow CP-SAT surface — confined to ``_solve_coarse`` below.
This is a stated deviation, recorded in docs/04's session amendment and docs/07,
not an oversight. Nothing here returns an ortools type: ``CoarseRun`` is plain
values, as ``SolveResult`` is.

DETERMINISM. This is a second CP-SAT model and therefore a second opportunity
for the hash-order leak class (three found and fixed in the 2026-07-26 errand).
EVERY iteration order here is explicitly sorted — demands, operations,
resources, buckets, edges — so variable-creation order cannot move with
PYTHONHASHSEED. ``tests/test_coarse_horizon.py`` tests this CROSS-HASHSEED, not
same-seed-both-sides. ``max_time_in_seconds`` is a SAFETY CEILING, never the
budget: the deterministic budget is what must bind, and a wall-truncated solve
sets ``wall_truncated`` and can never produce ``proves_infeasible``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from mre.modules.calendar_utils import (
    flatten_all_calendars, is_effectively_resumable,
)
from mre.modules.eligibility import capability_eligible
from mre.modules.rolling_horizon import (
    _dt, _merge_intervals, _weight, parse_iso_duration_minutes,
)

# The bucket span is DECLARED (docs/06 §5.9). These are the DEFAULTS, and they
# are labeled as defaults everywhere they surface — clause (3) forbids a hidden
# constant, not a stated default.
DEFAULT_BUCKET_DAYS = 7          # weekly
DEFAULT_CAPACITY_DERATE = 1.0    # no derate; an undeclared plant invents nothing

# A resource with no resolvable calendar is given the bucket's full wall-clock
# minutes. This is deliberately PERMISSIVE: treating a missing calendar as zero
# capacity would TIGHTEN the coarse model and could make it infeasible where the
# fine model is feasible — a direct violation of clause (1). If a future change
# wants real capacity here, it must first prove the fine model also closes that
# resource, or the relaxation guard (CU4) is the thing that should fail.
_WALL_MINUTES_PER_DAY = 1440

# REPORTING threshold for "this resource-week is full" (CU5). Nothing in the
# solve reads it — it selects which cells the answer names, and every named cell
# carries its own load and cap so the reader checks the arithmetic, not the word.
BINDING_UTILIZATION = 0.95


# ---------------------------------------------------------------------------
# declared coefficients (clause 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoarseCoefficients:
    """The declared coarse-zone coefficients and their PROVENANCE.

    ``*_declared`` is False when the submission was silent and the stated
    default stands. The certificate block prints both the value and whether it
    was declared, so a defaulted rho can never read as a customer's choice.
    """
    bucket_days: int = DEFAULT_BUCKET_DAYS
    capacity_derate: float = DEFAULT_CAPACITY_DERATE
    bucket_days_declared: bool = False
    capacity_derate_declared: bool = False

    @classmethod
    def from_cost_model(cls, cost_model: dict) -> "CoarseCoefficients":
        """Read the coefficients off the canonical CostModel (the IDS adapter
        translates ``refinements.coarse_horizon`` onto these fields, docs/06
        §5.9). Absent ⇒ the stated default, marked NOT declared."""
        cm = cost_model or {}
        bd_raw = cm.get("coarse_bucket_days")
        rho_raw = cm.get("coarse_capacity_derate")
        bd_declared = bool(cm.get("coarse_bucket_days_declared", bd_raw is not None))
        rho_declared = bool(cm.get("coarse_capacity_derate_declared",
                                   rho_raw is not None))
        try:
            bd = int(bd_raw) if bd_raw is not None else DEFAULT_BUCKET_DAYS
        except (TypeError, ValueError):
            bd, bd_declared = DEFAULT_BUCKET_DAYS, False
        try:
            rho = float(rho_raw) if rho_raw is not None else DEFAULT_CAPACITY_DERATE
        except (TypeError, ValueError):
            rho, rho_declared = DEFAULT_CAPACITY_DERATE, False
        if bd < 1:
            bd, bd_declared = DEFAULT_BUCKET_DAYS, False
        if not (0.0 < rho <= 1.0):
            rho, rho_declared = DEFAULT_CAPACITY_DERATE, False
        return cls(bucket_days=bd, capacity_derate=rho,
                   bucket_days_declared=bd_declared,
                   capacity_derate_declared=rho_declared)

    def certificate_block(self) -> dict:
        """The certificate's view of the coefficients (acceptance item 6: rho
        appears in the certificate; a hidden default is a failure)."""
        return {
            "coarse_bucket_days": self.bucket_days,
            "coarse_bucket_days_provenance": (
                "declared" if self.bucket_days_declared else "defaulted"),
            "coarse_capacity_derate": self.capacity_derate,
            "coarse_capacity_derate_provenance": (
                "declared" if self.capacity_derate_declared else "defaulted"),
        }


# ---------------------------------------------------------------------------
# result shapes (plain values — no ortools types cross this line)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Bucket:
    index: int
    start: datetime
    end: datetime


@dataclass(frozen=True)
class CoarsePlacement:
    """One coarsely-placed operation. ``resource_witness`` is a FEASIBILITY
    WITNESS, never a plan (see the module docstring)."""
    op_id: str
    demand_id: str
    bucket_index: int
    resource_witness: str
    minutes: int


@dataclass(frozen=True)
class Unmodelable:
    """An op the coarse model cannot represent. FLAGGED AND NAMED, never
    silently dropped: its demand keeps its beyond-horizon disposition and gains
    the ``coarse_unmodelable`` sub-disposition carrying this reason."""
    op_id: str
    demand_id: str
    reason: str
    detail: str = ""


@dataclass
class CoarseRun:
    """One coarse solve. ``label`` is 'proof' or 'planning' (clause 2)."""
    label: str
    rho: float
    status: str                     # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    objective: Optional[float]
    wall_truncated: bool
    placements: list = field(default_factory=list)          # list[CoarsePlacement]
    unmodelable: list = field(default_factory=list)         # list[Unmodelable]
    demand_tardiness_buckets: dict = field(default_factory=dict)
    density: dict = field(default_factory=dict)             # (res, wk) -> minutes
    capacity: dict = field(default_factory=dict)            # (res, wk) -> derated cap
    binding: list = field(default_factory=list)             # [(res, wk, load, cap)]
    n_ops_modeled: int = 0
    solve_wall_s: float = 0.0
    # True when this planning run was NOT a second solve: with rho declared (or
    # defaulted) at 1.0 the planning model is byte-identical to the proof model,
    # so it is copied rather than re-solved. Recorded so the conformance report
    # says "mirrors the proof run" instead of implying an independent result.
    mirrors_proof: bool = False

    @property
    def proves_infeasible(self) -> bool:
        """CLAUSE (1)+(2): the ONLY gate through which the negative is allowed
        out. A planning run never proves anything; a wall-truncated solve never
        proves anything (its INFEASIBLE would be a wall-clock lottery, not a
        completed refutation)."""
        return (self.label == "proof"
                and self.status == "INFEASIBLE"
                and not self.wall_truncated)

    @property
    def placed(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


@dataclass
class CoarseZone:
    """The coarse zone for one rolling view: two runs over the same buckets."""
    coefficients: CoarseCoefficients
    buckets: list                       # list[Bucket]
    proof: CoarseRun
    planning: CoarseRun
    beyond_demand_ids: list = field(default_factory=list)
    due_bucket: dict = field(default_factory=dict)      # demand_id -> int (may be <0)

    def certificate_block(self) -> dict:
        """Coefficients + per-run summary. Coarse tardiness is reported in
        BUCKETS and never in currency — clause (5), enforced by shape."""
        out = dict(self.coefficients.certificate_block())
        out["coarse_bucket_count"] = len(self.buckets)
        for run in (self.proof, self.planning):
            out[f"coarse_{run.label}_status"] = run.status
            out[f"coarse_{run.label}_rho"] = run.rho
            out[f"coarse_{run.label}_ops_modeled"] = run.n_ops_modeled
            out[f"coarse_{run.label}_unmodelable"] = len(run.unmodelable)
            out[f"coarse_{run.label}_wall_truncated"] = run.wall_truncated
            out[f"coarse_{run.label}_tardiness_buckets"] = sum(
                run.demand_tardiness_buckets.values())
        out["coarse_planning_mirrors_proof"] = self.planning.mirrors_proof
        out["coarse_infeasibility_proven"] = self.proof.proves_infeasible
        return out


# ---------------------------------------------------------------------------
# bucket grid + capacity (the calendar as a NUMBER, not blocking intervals)
# ---------------------------------------------------------------------------

def build_buckets(window_end: datetime, last_due: Optional[datetime],
                  bucket_days: int, tail_buckets: int = 0) -> list:
    """Fixed-length buckets spanning from the ACTIVE-WINDOW END to the last
    demand due date, plus a tail.

    The tail exists so that a coarse INFEASIBLE means "capacity/eligibility is
    exhausted", never "the grid ran out of room" — a horizon-truncation
    infeasibility would be a false negative under clause (1). Callers size the
    tail from total beyond-horizon minutes against total capacity.
    """
    span_end = last_due if (last_due and last_due > window_end) else window_end
    n = max(1, math.ceil((span_end - window_end).total_seconds()
                         / (bucket_days * 86400.0)))
    n += max(0, int(tail_buckets))
    return [Bucket(index=k,
                   start=window_end + timedelta(days=k * bucket_days),
                   end=window_end + timedelta(days=(k + 1) * bucket_days))
            for k in range(n)]


def bucket_capacity_minutes(resources: list, calendars: list,
                            buckets: list) -> dict:
    """``available_minutes[(res_id, bucket_index)]`` — REAL working minutes from
    the REAL calendar, per clause-safe rule. The calendar is not dropped; it
    enters as a NUMBER rather than as blocking intervals.

    Resources are iterated in SORTED id order (determinism), and a resource with
    no resolvable calendar gets the bucket's full wall-clock minutes (see
    ``_WALL_MINUTES_PER_DAY`` above — permissive by construction).
    """
    if not buckets:
        return {}
    h_start, h_end = buckets[0].start, buckets[-1].end
    flat = flatten_all_calendars(calendars, h_start, h_end)
    open_by_cal: dict = {}
    for cal in flat:
        wins = []
        for w in cal.get("horizon_resolved", []):
            s = _dt(w["start"])
            e = _dt(w["end"])
            if e > s:
                wins.append((int((s - h_start).total_seconds() // 60),
                             int((e - h_start).total_seconds() // 60)))
        open_by_cal[cal["id"]] = _merge_intervals(wins)

    bucket_span = [(int((b.start - h_start).total_seconds() // 60),
                    int((b.end - h_start).total_seconds() // 60)) for b in buckets]
    full = (buckets[0].end - buckets[0].start).days * _WALL_MINUTES_PER_DAY

    cap: dict = {}
    for res in sorted(resources, key=lambda r: r["id"]):
        rid = res["id"]
        cal_id = res.get("calendar_ref")
        wins = open_by_cal.get(cal_id) if cal_id else None
        for b, (bs, be) in zip(buckets, bucket_span):
            if wins is None:
                cap[(rid, b.index)] = full
                continue
            total = 0
            for (ws, we) in wins:
                lo, hi = max(ws, bs), min(we, be)
                if hi > lo:
                    total += hi - lo
            cap[(rid, b.index)] = total
    return cap


# ---------------------------------------------------------------------------
# the op scope: every operation of every BEYOND-HORIZON demand
# ---------------------------------------------------------------------------

def _op_minutes_by_resource(op: dict, eligible: list) -> dict:
    """Per-resource coarse minutes: setup + run, taking the op's per-resource
    durations where declared (docs/06 §5.3) and the scalar default otherwise —
    the SAME arithmetic the fine builder uses (solver_builder ~line 617), so the
    charge is exact per (op, resource) rather than an approximation."""
    setup = parse_iso_duration_minutes(op.get("setup_duration"))
    run = parse_iso_duration_minutes(op.get("run_duration"))
    res_setup = op.get("resource_setup_durations") or {}
    res_run = op.get("resource_run_durations") or {}
    out = {}
    for rid in eligible:
        s = (parse_iso_duration_minutes(res_setup[rid])
             if rid in res_setup else setup)
        r = (parse_iso_duration_minutes(res_run[rid])
             if rid in res_run else run)
        out[rid] = s + r
    return out


def _coarse_scope(plant, beyond_demand_ids: list) -> list:
    """(demand_id, op) pairs for every op of every beyond-horizon demand, in a
    fully SORTED order (demand id, then op sequence, then op id) — the
    determinism discipline of the module docstring."""
    scope = []
    for did in sorted(beyond_demand_ids):
        wp = plant.wp_of_demand.get(did)
        ops = plant.ops_by_wp.get(wp, [])
        for op in sorted(ops, key=lambda o: (int(o.get("sequence", 0)), o["id"])):
            scope.append((did, op))
    return scope


def _coarse_edges(plant, scope: list) -> list:
    """Coarse precedence pairs (pred_op_id, succ_op_id) resolved from the
    template-level PrecedenceEdges onto the in-scope operation INSTANCES, via
    (workpackage_ref, spec_ref) — the same resolution the fine builder does.
    Sorted for determinism."""
    by_wp_spec = {}
    for (_did, op) in scope:
        by_wp_spec[(op.get("workpackage_ref", ""), op.get("spec_ref", ""))] = op["id"]
    wps = sorted({wp for (wp, _spec) in by_wp_spec})
    pairs = set()
    for edge in sorted(plant.edges, key=lambda e: e.get("id", "")):
        pred_spec, succ_spec = edge.get("predecessor"), edge.get("successor")
        for wp in wps:
            p = by_wp_spec.get((wp, pred_spec))
            s = by_wp_spec.get((wp, succ_spec))
            if p is not None and s is not None:
                pairs.add((p, s))
    return sorted(pairs)


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------

def _classify_unmodelable(did, op, minutes_by_res, eligible, cap, buckets, rho):
    """Return an Unmodelable when this op cannot be represented, else None.

    Two named reasons:
      * ``resumable_out_of_scope`` — a resumable (splittable) op. Cross-bucket
        allocation for resumables is OUT OF SCOPE this session, and unlike the
        other two omissions it does NOT relax permissively: forcing a resumable
        op into a single bucket is a TIGHTENING relative to the fine model,
        which may split it across a bucket boundary. Excluding it outright is
        what keeps clause (1) true. (Recorded as a finding of this session, not
        as an assertion of the ruling — see docs/04.)
      * ``exceeds_bucket_capacity`` — the op's minutes exceed every eligible
        resource-bucket's DERATED capacity, so no single-bucket assignment
        exists at this rho.
    """
    total = max(minutes_by_res.values()) if minutes_by_res else 0
    min_chunk = parse_iso_duration_minutes(op.get("min_chunk"))
    if is_effectively_resumable(bool(op.get("splittable", False)), total, min_chunk):
        return Unmodelable(op["id"], did, "resumable_out_of_scope",
                           "splittable op; cross-bucket allocation is out of "
                           "scope, and single-bucket forcing would TIGHTEN the "
                           "relaxation (clause 1)")
    if not eligible:
        return Unmodelable(op["id"], did, "no_eligible_resource",
                           "capability_eligible returned no resource")
    for rid in eligible:
        need = minutes_by_res.get(rid, 0)
        for b in buckets:
            if need <= math.floor(cap.get((rid, b.index), 0) * rho):
                return None
    return Unmodelable(
        op["id"], did, "exceeds_bucket_capacity",
        f"needs {min(minutes_by_res.values()) if minutes_by_res else 0} min; no "
        f"eligible resource-bucket offers that at rho={rho:g}")


def _solve_coarse(scope, edges, terminal_of, due_bucket, weight_of, eligible_of,
                  minutes_of, cap, buckets, rho, *, label, deterministic, seed,
                  det_time, safety_ceiling_s):
    """Build and solve ONE coarse model. The only ortools surface in the module.

    Model shape (the amendment's Part 2, verbatim in structure):

        x[op, res, wk] in {0,1}          # created ONLY for res in eligible(op)
        add_exactly_one(x[op, res, wk] for res, wk)
        sum(minutes * x) <= floor(available_minutes[res, wk] * rho)
        bidx[op] = sum(wk * x[op, res, wk] for res, wk)
        bidx[succ] >= bidx[pred]
        tard[demand] >= bidx[terminal_op] - due_bucket[demand];  tard >= 0
        minimize sum(weight[demand] * tard[demand])

    ELIGIBILITY IS CARRIED BY VARIABLE EXISTENCE — no variable is created for an
    ineligible (op, res) pair, so an aggregation error that places work on an
    incapable machine is structurally UNREPRESENTABLE rather than constrained
    away.

    NOT MODELED, deliberately (gated on CU3's data): family-presence setup,
    cross-bucket allocation for resumables (excluded instead — see
    ``_classify_unmodelable``), the per-WorkPackage makespan bound. Setup is
    charged per op exactly as the fine builder charges it, so that omission is
    not a discount. The two remaining omissions relax in the PERMISSIVE
    direction, which is what keeps clause (1) true — a future tightening must
    trip over this comment and over the CU4 guard.
    """
    import time as _t
    from ortools.sat.python import cp_model as cp

    model = cp.CpModel()
    x: dict = {}
    bidx: dict = {}
    load_terms: dict = {}

    for (did, op) in scope:                       # scope is pre-sorted
        oid = op["id"]
        cells = []
        for rid in eligible_of[oid]:              # pre-sorted
            for b in buckets:                     # index order
                v = model.new_bool_var(f"x_{oid}_{rid}_{b.index}")
                x[(oid, rid, b.index)] = v
                cells.append(v)
                load_terms.setdefault((rid, b.index), []).append(
                    (minutes_of[oid][rid], v))
        if not cells:
            # unreachable: ops with no eligible resource are filtered upstream
            continue
        model.add_exactly_one(cells)
        bidx[oid] = sum(b.index * x[(oid, rid, b.index)]
                        for rid in eligible_of[oid] for b in buckets)

    # capacity: the calendar as a number, derated
    derated_cap: dict = {}
    for rid_wk in sorted(load_terms):
        rid, wk = rid_wk
        limit = math.floor(cap.get(rid_wk, 0) * rho)
        derated_cap[rid_wk] = limit
        model.add(sum(m * v for (m, v) in load_terms[rid_wk]) <= limit)

    # precedence, coarse but real
    for (p, s) in edges:
        if p in bidx and s in bidx:
            model.add(bidx[s] >= bidx[p])

    # the boundary stops being free
    n = len(buckets)
    obj_terms = []
    tard_of: dict = {}
    for did in sorted(terminal_of):
        term_op = terminal_of[did]
        if term_op not in bidx:
            continue
        db = due_bucket.get(did, 0)
        # upper bound: the worst case is the last bucket against the earliest
        # (possibly negative) due bucket, so the var can always take the value
        # the constraint forces — never a hidden tightening via a tight domain.
        t = model.new_int_var(0, max(0, (n - 1) - db), f"tard_{did}")
        tard_of[did] = t
        model.add(t >= bidx[term_op] - db)
        model.add(t >= 0)
        w = int(round(weight_of.get(did, 1.0) * 100))
        obj_terms.append(w * t)
    if obj_terms:
        model.minimize(sum(obj_terms))

    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1 if deterministic else 8
    solver.parameters.random_seed = int(seed)
    # The DETERMINISTIC budget is what must bind. max_time_in_seconds is a
    # SAFETY CEILING only; if it trips first the run is a wall-clock lottery and
    # ``wall_truncated`` denies it the right to prove anything (clause 2).
    if deterministic:
        solver.parameters.max_deterministic_time = float(det_time)
    solver.parameters.max_time_in_seconds = float(safety_ceiling_s)

    t0 = _t.perf_counter()
    status = solver.solve(model)
    wall = _t.perf_counter() - t0
    status_name = solver.status_name(status)
    # Mirrors SolveRunner's rule exactly: a deterministic-budget solve that hit
    # the WALL ceiling is a lottery wearing a determinism label.
    wall_truncated = bool(deterministic and wall >= safety_ceiling_s - 0.05)

    run = CoarseRun(label=label, rho=rho, status=status_name,
                    objective=(solver.objective_value
                               if status in (cp.OPTIMAL, cp.FEASIBLE) and obj_terms
                               else None),
                    wall_truncated=wall_truncated,
                    capacity=derated_cap, n_ops_modeled=len(bidx),
                    solve_wall_s=round(wall, 3))

    if status in (cp.OPTIMAL, cp.FEASIBLE):
        density: dict = {}
        for (did, op) in scope:
            oid = op["id"]
            for rid in eligible_of[oid]:
                for b in buckets:
                    v = x.get((oid, rid, b.index))
                    if v is not None and solver.value(v):
                        mins = minutes_of[oid][rid]
                        run.placements.append(CoarsePlacement(
                            op_id=oid, demand_id=did, bucket_index=b.index,
                            resource_witness=rid, minutes=mins))
                        density[(rid, b.index)] = density.get((rid, b.index), 0) + mins
        run.density = density
        run.demand_tardiness_buckets = {
            did: int(solver.value(t)) for did, t in sorted(tard_of.items())
            if int(solver.value(t)) > 0}
        # The capacity constraints AT OR NEAR their limit — the raw material for
        # "why is week N full?" (CU5). Each entry carries the LOAD and the CAP,
        # not a verdict word, so the answer states arithmetic rather than an
        # adjective. BINDING_UTILIZATION is the reporting threshold, not a model
        # constant: nothing in the solve reads it.
        run.binding = [
            (rid, wk, density.get((rid, wk), 0), derated_cap[(rid, wk)])
            for (rid, wk) in sorted(derated_cap)
            if derated_cap[(rid, wk)] > 0
            and density.get((rid, wk), 0)
            >= BINDING_UTILIZATION * derated_cap[(rid, wk)]]
    return run


# ---------------------------------------------------------------------------
# THE RELAXATION GUARD (CU4) — what makes clause (1) a theorem, not a hope
# ---------------------------------------------------------------------------

def map_fine_placements_to_coarse(placements: dict, buckets: list) -> dict:
    """Map a FINE schedule to a coarse allocation: ``op_id -> (bucket_index,
    resource)``. An operation is charged to the bucket containing its START.

    Ops starting before the grid map to index -1 ("before the coarse zone"); the
    violation checker excludes those from capacity rather than clamping them
    into bucket 0, because clamping would pile load into the first bucket and
    manufacture a FALSE RED — the guard must fail only on real tightenings."""
    if not buckets:
        return {}
    b0, span = buckets[0].start, (buckets[0].end - buckets[0].start)
    out: dict = {}
    for oid in sorted(placements):
        pl = placements[oid]
        start = _dt(pl["start"])
        if start < b0:
            out[oid] = (-1, pl["resource"])
            continue
        idx = int((start - b0).total_seconds() // span.total_seconds())
        out[oid] = (min(idx, buckets[-1].index), pl["resource"])
    return out


def coarse_allocation_violations(allocation: dict, *, minutes_of: dict,
                                 eligible_of: dict, cap: dict, buckets: list,
                                 rho: float = 1.0, edges=(),
                                 _capacity_scale: float = 1.0) -> list:
    """Check a mapped allocation against the COARSE MODEL's own constraint
    system. Returns a list of violation strings; EMPTY means coarse-feasible.

    This is the strong form of clause (1): every fine-feasible schedule maps to
    a coarse-FEASIBLE allocation. It checks exactly the three things the model
    constrains — eligibility (by variable existence), derated capacity, and
    coarse precedence — so a tightening anywhere in the model must show up here.

    ``_capacity_scale`` is the NEGATIVE CONTROL's lever and nothing else. It
    exists so the guard can be PROVEN falsifiable: a green guard that could
    never have failed is worth what it cost (4B.5 CU4(b) is the precedent for
    saying so out loud). Production callers never pass it.
    """
    viol: list = []
    load: dict = {}
    for oid in sorted(allocation):
        wk, res = allocation[oid]
        elig = eligible_of.get(oid)
        if elig is not None and res not in elig:
            viol.append(f"eligibility: {oid} allocated to {res}, not eligible")
        if wk < 0:
            continue          # before the grid — not the coarse zone's capacity
        mins = (minutes_of.get(oid) or {}).get(res)
        if mins is None:
            viol.append(f"eligibility: {oid} has no duration for {res}")
            continue
        load[(res, wk)] = load.get((res, wk), 0) + mins

    for cell in sorted(load):
        limit = math.floor(cap.get(cell, 0) * rho * _capacity_scale)
        if load[cell] > limit:
            viol.append(f"capacity: {cell[0]} bucket {cell[1]} loaded "
                        f"{load[cell]} > {limit}")

    for (p, s) in edges:
        if p in allocation and s in allocation:
            if allocation[s][0] < allocation[p][0]:
                viol.append(f"precedence: {s} in bucket {allocation[s][0]} "
                            f"before predecessor {p} in {allocation[p][0]}")
    return viol


def coarse_scope_for_guard(plant, demand_ids: list, buckets: list, rho: float):
    """The per-op eligibility/duration maps and coarse edges for a guard run
    over ``demand_ids``, plus the ops the coarse model cannot represent (which
    the guard must exclude, and COUNT, rather than silently skip)."""
    scope = _coarse_scope(plant, demand_ids)
    resources_by_id = {r["id"]: r for r in sorted(plant.resources,
                                                  key=lambda r: r["id"])}
    cap = bucket_capacity_minutes(plant.resources, plant.calendars, buckets)
    eligible_of: dict = {}
    minutes_of: dict = {}
    for (_d, op) in scope:
        elig = sorted(capability_eligible(op.get("resource_requirements"),
                                          resources_by_id))
        eligible_of[op["id"]] = elig
        minutes_of[op["id"]] = _op_minutes_by_resource(op, elig)
    unmodelable = [u for u in (
        _classify_unmodelable(did, op, minutes_of[op["id"]],
                              eligible_of[op["id"]], cap, buckets, rho)
        for (did, op) in scope) if u is not None]
    edges = _coarse_edges(plant, scope)
    return {"scope": scope, "cap": cap, "eligible_of": eligible_of,
            "minutes_of": minutes_of, "edges": edges,
            "unmodelable": unmodelable}


# ---------------------------------------------------------------------------
# the public entry point — TWO RUNS PER SLICE
# ---------------------------------------------------------------------------

def build_coarse_zone(plant, view, *, coefficients: Optional[CoarseCoefficients] = None,
                      deterministic: bool = True, seed: int = 42,
                      det_time: float = 4.0,
                      safety_ceiling_s: float = 60.0) -> CoarseZone:
    """Coarsely place every operation of every BEYOND-HORIZON demand.

    TWO RUNS PER SLICE (clause 2), both persisted by the caller:
      * proof run    — rho = 1.0, restricted to ops that fit within one bucket
      * planning run — rho = declared

    Only the proof run's INFEASIBLE licenses the clause-(1) negative, and only
    via ``CoarseRun.proves_infeasible``.
    """
    coef = coefficients or CoarseCoefficients.from_cost_model(plant.cost_model)
    beyond = sorted(view.beyond_demand_ids)
    demands_by_id = {d["id"]: d for d in plant.demands}

    scope = _coarse_scope(plant, beyond)
    resources_by_id = {r["id"]: r for r in sorted(plant.resources,
                                                  key=lambda r: r["id"])}

    eligible_of: dict = {}
    minutes_of: dict = {}
    for (_did, op) in scope:
        elig = sorted(capability_eligible(op.get("resource_requirements"),
                                          resources_by_id))
        eligible_of[op["id"]] = elig
        minutes_of[op["id"]] = _op_minutes_by_resource(op, elig)

    # bucket grid: window end → last beyond-horizon due, plus a capacity-sized
    # tail so infeasibility can never mean "the grid ran out of room".
    dues = [_dt(demands_by_id[d]["due"]) for d in beyond
            if demands_by_id.get(d, {}).get("due")]
    last_due = max(dues) if dues else None
    probe = build_buckets(view.window_end, last_due, coef.bucket_days)
    cap_probe = bucket_capacity_minutes(plant.resources, plant.calendars, probe)
    total_minutes = sum(min(m.values()) for m in minutes_of.values() if m)
    per_bucket_cap = max(1, sum(cap_probe.get((r, 0), 0) for r in resources_by_id))
    tail = math.ceil(total_minutes / per_bucket_cap) + 1
    buckets = build_buckets(view.window_end, last_due, coef.bucket_days, tail)
    cap = bucket_capacity_minutes(plant.resources, plant.calendars, buckets)

    # due bucket per demand (may be negative: a beyond-horizon demand due before
    # the window end is ALREADY late in coarse terms, and the model says so)
    due_bucket: dict = {}
    for did in beyond:
        due_raw = demands_by_id.get(did, {}).get("due")
        if not due_raw:
            due_bucket[did] = len(buckets) - 1
            continue
        delta_days = (_dt(due_raw) - view.window_end).total_seconds() / 86400.0
        due_bucket[did] = math.floor(delta_days / coef.bucket_days)

    terminal_of: dict = {}
    for (did, op) in scope:
        cur = terminal_of.get(did)
        if cur is None or (int(op.get("sequence", 0)) >=
                           int(cur[1])):
            terminal_of[did] = (op["id"], int(op.get("sequence", 0)))
    terminal_ids = {did: v[0] for did, v in terminal_of.items()}
    weight_of = {did: _weight(plant, demands_by_id[did])
                 for did in beyond if did in demands_by_id}

    edges = _coarse_edges(plant, scope)

    def _run(label: str, rho: float) -> CoarseRun:
        # The ruling restricts the PROOF run to "ops that fit within one
        # bucket". That restriction IS the unmodelable filter evaluated at
        # rho = 1.0 — so it is not a separate flag: each run applies the filter
        # at its OWN rho, and each carries its own unmodelable list.
        unmod: list = []
        kept: list = []
        for (did, op) in scope:
            u = _classify_unmodelable(did, op, minutes_of[op["id"]],
                                      eligible_of[op["id"]], cap, buckets, rho)
            if u is not None:
                unmod.append(u)
                continue
            kept.append((did, op))
        kept_ids = {op["id"] for (_d, op) in kept}
        kept_edges = [(p, s) for (p, s) in edges if p in kept_ids and s in kept_ids]
        kept_terminals = {did: oid for did, oid in terminal_ids.items()
                          if oid in kept_ids}
        run = _solve_coarse(kept, kept_edges, kept_terminals, due_bucket,
                            weight_of, eligible_of, minutes_of, cap, buckets, rho,
                            label=label, deterministic=deterministic, seed=seed,
                            det_time=det_time, safety_ceiling_s=safety_ceiling_s)
        run.unmodelable = unmod
        return run

    proof = _run("proof", 1.0)
    planning = (_run("planning", coef.capacity_derate)
                if coef.capacity_derate != 1.0
                else CoarseRun(label="planning", rho=coef.capacity_derate,
                               status=proof.status, objective=proof.objective,
                               wall_truncated=proof.wall_truncated,
                               placements=list(proof.placements),
                               unmodelable=list(proof.unmodelable),
                               demand_tardiness_buckets=dict(
                                   proof.demand_tardiness_buckets),
                               density=dict(proof.density),
                               capacity=dict(proof.capacity),
                               binding=list(proof.binding),
                               n_ops_modeled=proof.n_ops_modeled,
                               solve_wall_s=proof.solve_wall_s,
                               mirrors_proof=True))

    return CoarseZone(coefficients=coef, buckets=buckets, proof=proof,
                      planning=planning, beyond_demand_ids=beyond,
                      due_bucket=due_bucket)
