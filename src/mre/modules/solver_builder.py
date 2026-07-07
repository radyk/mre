"""M5 — Solver Builder.

Converts canonical entities into a CP-SAT CpModel and VariableMap.

Six inputs (docs/01 §8.6):
  1. work_items     list[dict]  WorkPackage + Operation entities (mixed)
  2. capacity_items list[dict]  Resource + ResourcePool entities (mixed)
  3. calendars      list[dict]  Calendar entities (horizon_resolved populated)
  4. demand_items   list[dict]  Fulfillment + Demand entities (mixed)
  5. constraints    list[dict]  Constraint entities
  6. cost_model     dict        CostModel entity

Hard rules:
- Never reads the provenance sidecar.
- Scope cuts: splittable=false, no straddling rewards, simple dwell, single tool type.
- Time unit: integer minutes from horizon_start.
- VariableMap carries IntVar/BoolVar objects for extraction; SolveValues is plain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

UTC = timezone.utc


# ---------------------------------------------------------------------------
# SolveValues — plain-value record after extraction; no ortools import needed
# ---------------------------------------------------------------------------

@dataclass
class SolveValues:
    """Plain-value extract of a CP-SAT solve result. No ortools types."""
    op_start_minutes: dict[str, int]
    op_end_minutes: dict[str, int]
    op_resource: dict[str, str]           # operation_id → chosen resource_id
    wp_end_minutes: dict[str, int]        # workpackage_id → completion minute
    tardiness_minutes: dict[str, int]     # fulfillment_id → tardiness (minutes, ≥0)
    horizon_start: datetime


# ---------------------------------------------------------------------------
# VariableMap — maps entity IDs ↔ solver variables
# ---------------------------------------------------------------------------

@dataclass
class VariableMap:
    """Mapping from canonical entity IDs to CP-SAT variables.

    Holds ortools IntVar/BoolVar objects; call extract(solver) after solving
    to obtain a plain SolveValues struct with no ortools dependency.
    """
    horizon_start: datetime
    # op_id → IntVar (start in minutes)
    op_start: dict[str, Any] = field(default_factory=dict)
    # op_id → IntVar (end in minutes)
    op_end: dict[str, Any] = field(default_factory=dict)
    # op_id → {resource_id: BoolVar} (assignment literals)
    op_assign: dict[str, dict[str, Any]] = field(default_factory=dict)
    # workpackage_id → IntVar (completion = max end of all ops in WP)
    wp_end: dict[str, Any] = field(default_factory=dict)
    # fulfillment_id → IntVar (tardiness, ≥0)
    tardiness: dict[str, Any] = field(default_factory=dict)
    # op_id → [resource_id, ...] eligible resources (plain strings, no ortools)
    op_eligible: dict[str, list[str]] = field(default_factory=dict)
    # resource_id → [(start_min, end_min), ...] available calendar windows
    cal_windows: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    @property
    def op_ids(self) -> dict[str, Any]:
        """Mapping of operation_id → start_var (convenience alias)."""
        return self.op_start

    @property
    def fulfillment_ids(self) -> dict[str, Any]:
        """Mapping of fulfillment_id → tardiness_var."""
        return self.tardiness

    def extract(self, solver) -> SolveValues:
        """Extract plain integer values from a solved CpSolver.

        Call this after solver.Solve(); the result has no ortools types.
        """
        op_start_min = {oid: solver.Value(v) for oid, v in self.op_start.items()}
        op_end_min   = {oid: solver.Value(v) for oid, v in self.op_end.items()}

        op_resource: dict[str, str] = {}
        for oid, assigns in self.op_assign.items():
            for rid, bv in assigns.items():
                if solver.Value(bv):
                    op_resource[oid] = rid
                    break

        wp_end_min = {wid: solver.Value(v) for wid, v in self.wp_end.items()}
        tard_min   = {fid: solver.Value(v) for fid, v in self.tardiness.items()}

        return SolveValues(
            op_start_minutes=op_start_min,
            op_end_minutes=op_end_min,
            op_resource=op_resource,
            wp_end_minutes=wp_end_min,
            tardiness_minutes=tard_min,
            horizon_start=self.horizon_start,
        )


# ---------------------------------------------------------------------------
# SolverBuilder
# ---------------------------------------------------------------------------

_COST_SCALE = 100   # multiply floats by this to get CP-SAT integers
_MINUTES_PER_DAY = 24 * 60
_HORIZON_DAYS = 60  # planning horizon length if not derivable from data


class SolverBuilder:
    """Build a CP-SAT scheduling model from six canonical inputs.

    Constructor parameters:
        reference_date  Planning floor (optional): no operation may start
                        before this date.  Pass for real-data runs to prevent
                        the solver from scheduling in the past.  This is solver
                        configuration, not a canonical model input, so it lives
                        on the constructor rather than build().
    """

    def __init__(self, reference_date: Optional[datetime] = None) -> None:
        self._reference_date = reference_date

    def build(
        self,
        work_items: list[dict],
        capacity_items: list[dict],
        calendars: list[dict],
        demand_items: list[dict],
        constraints: list[dict],
        cost_model: dict,
    ):
        """Return (CpModel, VariableMap).

        Parameters (exactly six, non-self):
            work_items      WorkPackage + Operation dicts (mixed list)
            capacity_items  Resource + ResourcePool dicts (mixed list)
            calendars       Calendar entities with horizon_resolved populated
            demand_items    Fulfillment + Demand dicts (mixed list)
            constraints     list of Constraint dicts
            cost_model      CostModel dict
        """
        from ortools.sat.python import cp_model as cp

        # Separate mixed inputs
        workpackages = {d["id"]: d for d in work_items if "operations" in d}
        operations   = [d for d in work_items if "spec_ref" in d]
        resources    = {d["id"]: d for d in capacity_items if "resource_type" in d}
        pools        = [d for d in capacity_items if "concurrent_capacity" in d]
        demands      = {d["id"]: d for d in demand_items if "due" in d}
        fulfillments = [d for d in demand_items if "demand_ref" in d]
        cal_map      = {c["id"]: c for c in calendars}

        # Resource rates from cost_model
        rates: dict[str, float] = cost_model.get("resource_rates", {})

        # Transition matrix from first setup_transition constraint
        transition_matrix: dict[str, dict[str, int]] = {}
        for con in constraints:
            if con.get("constraint_type") == "setup_transition":
                raw = con.get("parameters", {}).get("transition_minutes", {})
                for key, mins in raw.items():
                    if "->" in key:
                        frm, to = key.split("->")
                        transition_matrix.setdefault(frm, {})[to] = int(mins)
                break

        # Planning horizon
        horizon_start, horizon_end = self._compute_horizon(
            workpackages, demands
        )
        horizon_minutes = int((horizon_end - horizon_start).total_seconds() / 60)

        model    = cp.CpModel()
        var_map  = VariableMap(horizon_start=horizon_start)

        # Flattened calendar windows per resource
        cal_windows = self._flatten_all(
            resources, cal_map, horizon_start, horizon_end
        )
        var_map.cal_windows = cal_windows

        # ------------------------------------------------------------------
        # Build interval variables for each operation × eligible resource
        # ------------------------------------------------------------------
        wp_op_map: dict[str, list[str]] = {}  # wp_id → [op_ids]
        op_durations: dict[str, int] = {}     # op_id → total minutes (setup + run)
        op_families: dict[str, str] = {}      # op_id → setup_family

        for op in operations:
            oid = op["id"]
            wp_id = op["workpackage_ref"]
            wp_op_map.setdefault(wp_id, []).append(oid)

            setup_min = _td_to_minutes(_parse_td(op.get("setup_duration", "PT0S")))
            run_min   = _td_to_minutes(_parse_td(op.get("run_duration", "PT0S")))
            total_min = setup_min + run_min
            op_durations[oid] = total_min
            op_families[oid] = op.get("setup_family", "")

            # Determine earliest_start for the WP
            wp_earliest_min = 0
            wp = workpackages.get(wp_id, {})
            if wp.get("earliest_start"):
                es_dt = _parse_dt(wp["earliest_start"])
                wp_earliest_min = max(0, int((es_dt - horizon_start).total_seconds() / 60))

            # Start and end variables for this operation
            s_var = model.new_int_var(wp_earliest_min, horizon_minutes - total_min, f"s_{oid}")
            e_var = model.new_int_var(wp_earliest_min + total_min, horizon_minutes, f"e_{oid}")
            model.add(e_var == s_var + total_min)

            var_map.op_start[oid] = s_var
            var_map.op_end[oid]   = e_var
            var_map.op_assign[oid] = {}

            # Determine eligible resources (all for now — scope cut: single tool type)
            eligible = list(resources.keys())  # all resources are eligible if no requirements
            # Scope cut: if op has resource_requirements, filter by those
            op_reqs = op.get("resource_requirements", [])
            if op_reqs:
                eligible = self._eligible_resources(op_reqs, resources)
            var_map.op_eligible[oid] = eligible

            # Create optional interval per eligible resource
            all_intervals: list[Any] = []
            for rid in eligible:
                bv = model.new_bool_var(f"assign_{oid}_{rid}")
                dur = total_min
                iv = model.new_optional_interval_var(s_var, dur, e_var, bv, f"iv_{oid}_{rid}")
                var_map.op_assign[oid][rid] = bv
                all_intervals.append((rid, iv, bv))

            # Exactly one resource must be assigned
            if var_map.op_assign[oid]:
                model.add_exactly_one(var_map.op_assign[oid].values())
            else:
                # No eligible resource — constrain to never start (infeasible signal)
                model.add(s_var == horizon_minutes)

        # ------------------------------------------------------------------
        # No-overlap per resource + calendar blocking
        # ------------------------------------------------------------------
        resource_intervals: dict[str, list[Any]] = {rid: [] for rid in resources}

        for op in operations:
            oid = op["id"]
            for rid, iv, bv in [
                (rid, None, bv)
                for rid, bv in var_map.op_assign.get(oid, {}).items()
            ]:
                pass  # rebuild below with correct iv reference

        # Rebuild resource_intervals with the actual interval variables
        # We need to re-create them since we didn't store them in var_map directly
        # Instead, use the approach of storing (start, duration, end, bool) per op×resource
        # and building no-overlap constraints from those.

        # Collect intervals per resource for no-overlap
        res_op_intervals: dict[str, list[Any]] = {rid: [] for rid in resources}

        for op in operations:
            oid = op["id"]
            s_var = var_map.op_start[oid]
            e_var = var_map.op_end[oid]
            dur   = op_durations[oid]

            for rid, bv in var_map.op_assign.get(oid, {}).items():
                iv = model.new_optional_interval_var(s_var, dur, e_var, bv, f"iv2_{oid}_{rid}")
                res_op_intervals.setdefault(rid, []).append(iv)

        for rid, intervals in res_op_intervals.items():
            # Add calendar blocking intervals
            blocking = self._blocking_intervals(
                rid, cal_windows.get(rid, []), horizon_minutes, model
            )
            model.add_no_overlap(intervals + blocking)

        # ------------------------------------------------------------------
        # Precedence within WorkPackage (sequenced operations)
        # ------------------------------------------------------------------
        for wp_id, op_ids in wp_op_map.items():
            op_seqs = sorted(
                [(operations_by_id[oid]["sequence"], oid) for oid in op_ids
                 if oid in (operations_by_id := {o["id"]: o for o in operations})],
                key=lambda x: x[0],
            )
            for i in range(len(op_seqs) - 1):
                pred_id = op_seqs[i][1]
                succ_id = op_seqs[i+1][1]
                dwell_op = next(
                    (o for o in operations if o["id"] == pred_id), {}
                )
                dwell_sec = _td_to_minutes(_parse_td(dwell_op.get("dwell_duration", "PT0S")))
                model.add(
                    var_map.op_start[succ_id] >= var_map.op_end[pred_id] + dwell_sec
                )

        # ------------------------------------------------------------------
        # WorkPackage end = max of its operations' ends
        # ------------------------------------------------------------------
        for wp_id, op_ids in wp_op_map.items():
            if not op_ids:
                continue
            wp_end_var = model.new_int_var(0, horizon_minutes, f"wp_end_{wp_id}")
            model.add_max_equality(wp_end_var, [var_map.op_end[oid] for oid in op_ids])
            var_map.wp_end[wp_id] = wp_end_var

        # ------------------------------------------------------------------
        # Tardiness variables per Fulfillment (D-07)
        # ------------------------------------------------------------------
        tard_weights: dict[str, int] = {}  # fulfillment_id → scaled weight
        base_w = cost_model.get("tardiness_weights", {}).get("base_weight", 1.0)
        cc_mult = cost_model.get("tardiness_weights", {}).get(
            "commitment_class_multipliers", {}
        )

        for ful in fulfillments:
            fid = ful["id"]
            d_id = ful["demand_ref"]
            wp_id = ful["workpackage_ref"]

            demand = demands.get(d_id, {})
            due_dt = _parse_dt(demand.get("due", ""))
            due_min = max(0, int((due_dt - horizon_start).total_seconds() / 60))

            cclass = demand.get("commitment_class", "standard")
            mult = cc_mult.get(cclass, 1.0)
            cust_w = float(demand.get("customer_weight", 1.0))
            weight_scaled = max(1, int(base_w * mult * cust_w * _COST_SCALE))
            tard_weights[fid] = weight_scaled

            tard_var = model.new_int_var(0, horizon_minutes, f"tard_{fid}")
            var_map.tardiness[fid] = tard_var

            if wp_id in var_map.wp_end:
                excess = model.new_int_var(-horizon_minutes, horizon_minutes, f"excess_{fid}")
                model.add(excess == var_map.wp_end[wp_id] - due_min)
                model.add(tard_var >= excess)

        # ------------------------------------------------------------------
        # Sequence-dependent setup transitions (soft, pairwise)
        # ------------------------------------------------------------------
        self._add_transition_constraints(
            model, operations, var_map, resources, op_families, transition_matrix,
            op_durations, horizon_minutes
        )

        # ------------------------------------------------------------------
        # Objective: production cost + setup costs + weighted tardiness
        # ------------------------------------------------------------------
        obj_terms = []

        # Production cost: Σ assign[op][r] × duration[op] × rate[r]
        for op in operations:
            oid = op["id"]
            dur = op_durations[oid]
            for rid, bv in var_map.op_assign.get(oid, {}).items():
                rate_int = int(rates.get(rid, 0.0) * _COST_SCALE)
                if rate_int > 0:
                    obj_terms.append(bv * dur * rate_int)

        # Setup cost: fixed_per_setup × (number of operations that run)
        fixed_setup = int(
            cost_model.get("setup_cost_basis", {}).get("fixed_per_setup", 0.0)
            * _COST_SCALE
        )
        if fixed_setup > 0:
            for op in operations:
                oid = op["id"]
                assign_vars = list(var_map.op_assign.get(oid, {}).values())
                if assign_vars:
                    runs = model.new_bool_var(f"runs_{oid}")
                    model.add_bool_or(assign_vars).only_enforce_if(runs)
                    model.add_bool_and([v.negated() for v in assign_vars]).only_enforce_if(runs.negated())
                    obj_terms.append(runs * fixed_setup)

        # Tardiness cost: Σ tard_var[f] × weight[f]
        for fid, tard_var in var_map.tardiness.items():
            w = tard_weights.get(fid, 1)
            obj_terms.append(tard_var * w)

        if obj_terms:
            model.minimize(sum(obj_terms))

        return model, var_map

    # ------------------------------------------------------------------
    # Horizon computation
    # ------------------------------------------------------------------

    def _compute_horizon(
        self,
        workpackages: dict[str, dict],
        demands: dict[str, dict],
    ) -> tuple[datetime, datetime]:
        """Compute planning horizon from demand data.

        self._reference_date, when set, acts as a hard floor: the horizon
        start is max(min(earliest_starts), reference_date).  This prevents
        the solver from placing operations before the planning reference date
        (i.e., in the past relative to the snapshot).
        """
        starts: list[datetime] = []
        ends: list[datetime] = []

        for wp in workpackages.values():
            if wp.get("earliest_start"):
                starts.append(_parse_dt(wp["earliest_start"]))

        for d in demands.values():
            if d.get("earliest_start"):
                starts.append(_parse_dt(d["earliest_start"]))
            if d.get("due"):
                ends.append(_parse_dt(d["due"]))

        if starts:
            hs = min(starts)
            hs = hs.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            hs = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        # Clamp to reference_date: operations must not start before the planning date.
        if self._reference_date is not None:
            ref_floor = self._reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if ref_floor.tzinfo is None:
                ref_floor = ref_floor.replace(tzinfo=UTC)
            hs = max(hs, ref_floor)

        if ends:
            he = max(ends) + timedelta(days=90)
        else:
            he = hs + timedelta(days=_HORIZON_DAYS)

        return hs, he

    # ------------------------------------------------------------------
    # Calendar flattening
    # ------------------------------------------------------------------

    def _flatten_all(
        self,
        resources: dict[str, dict],
        cal_map: dict[str, dict],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> dict[str, list[tuple[int, int]]]:
        """Return per-resource list of (start_min, end_min) available windows."""
        result: dict[str, list[tuple[int, int]]] = {}
        for rid, res in resources.items():
            cal_id = res.get("calendar_ref")
            cal = cal_map.get(cal_id) if cal_id else None
            if cal is None:
                result[rid] = []
                continue

            # Use horizon_resolved if populated
            windows = cal.get("horizon_resolved", [])
            if windows:
                parsed = []
                for w in windows:
                    ws = _parse_dt(w["start"] if isinstance(w, dict) else w.start)
                    we = _parse_dt(w["end"]   if isinstance(w, dict) else w.end)
                    s_min = max(0, int((ws - horizon_start).total_seconds() / 60))
                    e_min = max(0, int((we - horizon_start).total_seconds() / 60))
                    parsed.append((s_min, e_min))
                result[rid] = parsed
            else:
                # horizon_resolved empty → use base_pattern via calendar_utils
                try:
                    from mre.modules.calendar_utils import flatten_calendar
                    from mre.contracts.entities import CalendarException, TimeWindow
                    from mre.contracts.vocabularies import CalendarExceptionType, CalendarExceptionReason
                    bp = cal.get("base_pattern", {})
                    excs_raw = cal.get("exceptions", [])
                    excs: list[CalendarException] = []
                    for e in excs_raw:
                        if isinstance(e, dict):
                            tw = TimeWindow(
                                start=_parse_dt(e["window"]["start"]),
                                end=_parse_dt(e["window"]["end"]),
                            )
                            excs.append(CalendarException(
                                window=tw,
                                type=CalendarExceptionType(e.get("type", "closure")),
                                reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                            ))
                        else:
                            excs.append(e)
                    flat = flatten_calendar(bp, excs, horizon_start, horizon_end)
                    parsed = []
                    for w in flat:
                        s_min = max(0, int((w.start - horizon_start).total_seconds() / 60))
                        e_min = max(0, int((w.end   - horizon_start).total_seconds() / 60))
                        parsed.append((s_min, e_min))
                    result[rid] = parsed
                except Exception:
                    result[rid] = []
        return result

    # ------------------------------------------------------------------
    # Calendar blocking intervals
    # ------------------------------------------------------------------

    def _blocking_intervals(
        self,
        rid: str,
        available: list[tuple[int, int]],
        horizon_minutes: int,
        model,
    ) -> list[Any]:
        """Return fixed interval variables covering unavailable periods."""
        if not available:
            return []

        blocking = []
        prev_end = 0
        for s_min, e_min in sorted(available):
            if s_min > prev_end:
                # Gap [prev_end, s_min) is unavailable
                dur = s_min - prev_end
                iv = model.new_fixed_size_interval_var(
                    prev_end, dur, f"block_{rid}_{prev_end}"
                )
                blocking.append(iv)
            prev_end = max(prev_end, e_min)

        # Gap from last available to horizon
        if prev_end < horizon_minutes:
            dur = horizon_minutes - prev_end
            iv = model.new_fixed_size_interval_var(
                prev_end, dur, f"block_{rid}_{prev_end}"
            )
            blocking.append(iv)

        return blocking

    # ------------------------------------------------------------------
    # Eligible resource resolution
    # ------------------------------------------------------------------

    def _eligible_resources(
        self, requirements: list[dict], resources: dict[str, dict]
    ) -> list[str]:
        """Return resource IDs matching the first ResourceRequirement.

        capability_ref is a UUID5 computed as uuid5(ns, "capability:<code>").
        We reverse-map by computing uuid5 for each resource's capability codes.
        """
        import uuid as _uuid
        _NS = _uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

        def _cap_id(name: str) -> str:
            return str(_uuid.uuid5(_NS, f"capability:{name}"))

        if not requirements:
            return list(resources.keys())
        req = requirements[0]
        mode = req.get("mode", "")
        if mode == "explicit_set":
            refs = req.get("resource_refs") or []
            matched = [r for r in refs if r in resources]
            return matched if matched else list(resources.keys())
        elif mode == "capability":
            cap_ref = req.get("capability_ref", "")
            matched = [
                rid for rid, res in resources.items()
                if any(_cap_id(c) == cap_ref for c in res.get("capabilities", []))
            ]
            return matched if matched else list(resources.keys())
        return list(resources.keys())

    # ------------------------------------------------------------------
    # Setup transition constraints
    # ------------------------------------------------------------------

    def _add_transition_constraints(
        self,
        model,
        operations: list[dict],
        var_map: VariableMap,
        resources: dict[str, dict],
        op_families: dict[str, str],
        transition_matrix: dict[str, dict[str, int]],
        op_durations: dict[str, int],
        horizon_minutes: int,
    ) -> None:
        """Add pairwise sequence-dependent setup constraints (soft, big-M style).

        For each pair (op_i, op_j) that may run on the same resource:
        if both assigned to r, then either:
          start[j] >= end[i] + extra_ij  (i before j)
          start[i] >= end[j] + extra_ji  (j before i)
        """
        if not transition_matrix:
            return

        op_list = operations
        for i in range(len(op_list)):
            for j in range(i + 1, len(op_list)):
                oi = op_list[i]["id"]
                oj = op_list[j]["id"]
                fi = op_families.get(oi, "")
                fj = op_families.get(oj, "")

                extra_ij = transition_matrix.get(fi, {}).get(fj, 0)
                extra_ji = transition_matrix.get(fj, {}).get(fi, 0)

                if extra_ij == 0 and extra_ji == 0:
                    continue

                # Check which resources they share
                ri_assigns = var_map.op_assign.get(oi, {})
                rj_assigns = var_map.op_assign.get(oj, {})
                shared = set(ri_assigns.keys()) & set(rj_assigns.keys())
                if not shared:
                    continue

                for rid in shared:
                    bv_i = ri_assigns[rid]
                    bv_j = rj_assigns[rid]
                    both = model.new_bool_var(f"both_{oi}_{oj}_{rid}")
                    model.add_bool_and([bv_i, bv_j]).only_enforce_if(both)
                    model.add_bool_or([bv_i.negated(), bv_j.negated()]).only_enforce_if(
                        both.negated()
                    )

                    order_ij = model.new_bool_var(f"order_{oi}_{oj}_{rid}")
                    # i before j: start[j] >= end[i] + extra_ij
                    model.add(
                        var_map.op_start[oj] >= var_map.op_end[oi] + extra_ij
                    ).only_enforce_if([both, order_ij])
                    # j before i: start[i] >= end[j] + extra_ji
                    model.add(
                        var_map.op_start[oi] >= var_map.op_end[oj] + extra_ji
                    ).only_enforce_if([both, order_ij.negated()])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_td(s: str | None) -> timedelta:
    if not s:
        return timedelta(0)
    if isinstance(s, (int, float)):
        return timedelta(seconds=float(s))
    import re
    m = re.fullmatch(
        r"P(?:(\d+(?:\.\d+)?)D)?T?(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?",
        s,
    )
    if not m:
        return timedelta(0)
    days  = float(m.group(1) or 0)
    hours = float(m.group(2) or 0)
    mins  = float(m.group(3) or 0)
    secs  = float(m.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=mins, seconds=secs)


def _td_to_minutes(td: timedelta) -> int:
    return max(1, int(td.total_seconds() / 60))


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime(2099, 1, 1, tzinfo=UTC)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
