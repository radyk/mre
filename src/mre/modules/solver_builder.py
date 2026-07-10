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
    # op_id → [(chunk_start_min, chunk_end_min), ...] in time order, for
    # resumable (chunked) operations only — absent/empty for non-resumable
    # ops. Each tuple is one calendar-window chunk; gaps between consecutive
    # chunks are the pauses (R-C3), always exactly a calendar closure by
    # construction (see solver_builder._build_resumable_operation).
    op_chunk_windows: dict[str, list[tuple[int, int]]] = field(default_factory=dict)


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
    # op_id → [{"used": BoolVar, "start": IntVar, "end": IntVar,
    # "resource": str}, ...] one entry per candidate (resource, window)
    # chunk slot — resumable ops only.
    op_chunks: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # resource_id → [(start_min, end_min), ...] PREMIUM minute windows:
    # overtime 'added' capacity minus regular availability (docs/06 §5.6).
    # Minutes scheduled inside these windows price at rate × overtime_premium.
    overtime_windows: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    # The objective's terms (ortools linear expressions), captured so pool /
    # scenario tooling can post additional constraints over the SAME
    # objective expression (e.g. an incumbent-relative upper bound) without
    # rebuilding it. Purely additive; the model itself is unchanged.
    objective_terms: list[Any] = field(default_factory=list)

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

        op_chunk_windows: dict[str, list[tuple[int, int]]] = {}
        for oid, slots in self.op_chunks.items():
            used_slots = [
                (solver.Value(slot["start"]), solver.Value(slot["end"]))
                for slot in slots if solver.Value(slot["used"])
            ]
            if used_slots:
                op_chunk_windows[oid] = sorted(used_slots)

        return SolveValues(
            op_start_minutes=op_start_min,
            op_end_minutes=op_end_min,
            op_resource=op_resource,
            wp_end_minutes=wp_end_min,
            tardiness_minutes=tard_min,
            horizon_start=self.horizon_start,
            op_chunk_windows=op_chunk_windows,
        )


# ---------------------------------------------------------------------------
# Warm-start hints from a previously solved schedule
# ---------------------------------------------------------------------------

def apply_solution_hints(
    model,
    var_map: "VariableMap",
    assignments: list[dict],
    invalidated_resource_ids: "frozenset[str] | set[str]" = frozenset(),
) -> dict[str, int]:
    """Seed `model` with a prior schedule's solution as CP-SAT hints.

    `assignments` are Assignment dicts in either the persisted-entity shape
    (``resource_assignments`` + ``phase_windows.run``) or the extractor
    shape (``resource_id`` + ``run_windows``). Correspondence is by
    operation id — the Planner mints deterministic uuid5 ids, so an
    operation whose WorkPackage composition is unchanged between the two
    snapshots has the same id, and a structurally modified portion (e.g. an
    unbatched merge) simply finds no matching variable and stays unhinted.

    Operations on `invalidated_resource_ids` (e.g. a scenario added a
    calendar exception there) are deliberately left unhinted: their base
    placement may no longer be legal, and CP-SAT treats a partially wrong
    hint worse than no hint.

    Hints are per (var, value) — ``add_hint`` does not batch (docs/04
    2026-07-10 amendment). Chunked (R-C3) operations get their overall
    start/end and resource literal hinted; chunk-slot variables stay free.

    Returns telemetry counts for the warm_start_hints evidence Event.
    """
    stats = {
        "hinted_operations": 0,
        "skipped_structure_changed": 0,
        "skipped_invalidated_resource": 0,
        "skipped_out_of_horizon": 0,
    }
    horizon_start = var_map.horizon_start
    for a in assignments:
        oid = a.get("operation_ref")
        rid = a.get("resource_id")
        if not rid:
            ras = a.get("resource_assignments") or []
            rid = ras[0].get("resource_ref") if ras else None
        windows = (a.get("phase_windows") or {}).get("run") or a.get("run_windows") or []
        if not (oid and rid and windows):
            stats["skipped_structure_changed"] += 1
            continue
        if oid not in var_map.op_start or rid not in var_map.op_assign.get(oid, {}):
            stats["skipped_structure_changed"] += 1
            continue
        if rid in invalidated_resource_ids:
            stats["skipped_invalidated_resource"] += 1
            continue
        start_min = int((_parse_dt(windows[0]["start"]) - horizon_start).total_seconds() // 60)
        end_min = int((_parse_dt(windows[-1]["end"]) - horizon_start).total_seconds() // 60)
        if start_min < 0:
            stats["skipped_out_of_horizon"] += 1
            continue
        model.add_hint(var_map.op_start[oid], start_min)
        model.add_hint(var_map.op_end[oid], end_min)
        for r2, bv in var_map.op_assign[oid].items():
            model.add_hint(bv, 1 if r2 == rid else 0)
        stats["hinted_operations"] += 1
    return stats


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
        edges        = [d for d in work_items if "predecessor" in d]
        resources    = {d["id"]: d for d in capacity_items if "resource_type" in d}
        pools        = [d for d in capacity_items if "concurrent_capacity" in d]
        demands      = {d["id"]: d for d in demand_items if "due" in d}
        fulfillments = [d for d in demand_items if "demand_ref" in d]
        cal_map      = {c["id"]: c for c in calendars}

        # Resource rates from cost_model
        rates: dict[str, float] = cost_model.get("resource_rates", {})

        # Overtime premium multiplier (docs/06 §5.9 refinements.
        # overtime_premium_multiplier → CostModel.overtime_premium).
        # ≤ 1.0 (including the 0.0 "unset" default) means no premium is
        # priced and NO overtime variables are created — models without
        # overtime build byte-identically to pre-overtime code (the
        # defaults-reproduce-baseline gate depends on this).
        ot_mult = float(cost_model.get("overtime_premium", 0.0) or 0.0)

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

        # Premium windows per resource: overtime 'added' exception windows
        # minus regular availability. Computed even when ot_mult is unset so
        # the extractor can report zero overtime consistently.
        overtime_windows = self._premium_windows(
            resources, cal_map, cal_windows, horizon_start, horizon_minutes
        )
        var_map.overtime_windows = overtime_windows

        # ------------------------------------------------------------------
        # Build interval variables for each operation × eligible resource
        # ------------------------------------------------------------------
        wp_op_map: dict[str, list[str]] = {}  # wp_id → [op_ids]
        op_durations: dict[str, int] = {}     # op_id → total minutes (setup + run)
        op_families: dict[str, str] = {}      # op_id → setup_family
        res_op_intervals: dict[str, list[Any]] = {rid: [] for rid in resources}
        # Ops that get the R-C3 chunk encoding this build. splittable=true
        # alone is not enough: the degenerate-split rule (working < 2 ×
        # min_chunk ⇒ cannot split ⇒ non-resumable) must hold or the chunk
        # encoding is structurally infeasible. Shared with the validator via
        # calendar_utils.is_effectively_resumable.
        from mre.modules.calendar_utils import is_effectively_resumable
        resumable_op_ids: set[str] = set()

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

            # Determine eligible resources (all for now — scope cut: single tool type)
            eligible = list(resources.keys())  # all resources are eligible if no requirements
            # Scope cut: if op has resource_requirements, filter by those
            op_reqs = op.get("resource_requirements", [])
            if op_reqs:
                eligible = self._eligible_resources(op_reqs, resources)
            var_map.op_eligible[oid] = eligible
            var_map.op_assign[oid] = {}

            min_chunk_raw = op.get("min_chunk")
            min_chunk_min = _td_to_minutes(_parse_td(min_chunk_raw)) if min_chunk_raw else 0
            if is_effectively_resumable(op.get("splittable", False), total_min, min_chunk_min):
                # R-C3 resumable operation — chunk-boundary-interval encoding
                # (docs/05 R-C3, spike 2 productionized: tools/chunking_spike2_report.md).
                resumable_op_ids.add(oid)
                self._build_resumable_operation(
                    model, var_map, oid, eligible, total_min, min_chunk_min,
                    cal_windows, horizon_minutes, wp_earliest_min, res_op_intervals,
                )
                continue

            # Start and end variables for this operation
            s_var = model.new_int_var(wp_earliest_min, horizon_minutes - total_min, f"s_{oid}")
            e_var = model.new_int_var(wp_earliest_min + total_min, horizon_minutes, f"e_{oid}")
            model.add(e_var == s_var + total_min)

            var_map.op_start[oid] = s_var
            var_map.op_end[oid]   = e_var

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
        # Frozen / pinned assignment constraints (locks doorway, docs/06 §5.12)
        # ------------------------------------------------------------------
        self._apply_lock_constraints(model, constraints, fulfillments, operations, var_map)

        # ------------------------------------------------------------------
        # No-overlap per resource + calendar blocking
        # ------------------------------------------------------------------
        # Resumable operations' chunk intervals were already appended to
        # res_op_intervals above (bounded within their own calendar window by
        # construction, so they can never overlap a blocking interval — no
        # separate no_overlap group needed, unlike the falsified spike-1
        # encoding). Only non-resumable ops need their intervals (re)built here.
        for op in operations:
            oid = op["id"]
            if oid in resumable_op_ids:
                continue
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
        # Precedence within WorkPackage — read from PrecedenceEdge records
        # (docs/05 R-A2/A3, §4 surgery). Edges are template-level (keyed by
        # OperationSpec id, one linear chain per Process); resolved here to
        # the concrete Operation instances of each WorkPackage via spec_ref.
        # min_lag carries dwell per R-Dwell (phases occupy resources; lags
        # don't). max_lag is plumbed through but unconstrained (None) until
        # a real source exists (docs/06 §8 doorway, R-A3 default = infinity).
        #
        # Quirk preserved from the pre-surgery implicit-sequence model
        # (defaults-reproduce-baseline, docs/05 §3 item 2): _td_to_minutes
        # floors at 1 minute, so a min_lag of exactly 0 still yields a
        # 1-minute gap — this was already true of dwell_duration=0 before
        # edges existed, and changing it would move every downstream
        # operation's start time by a minute.
        # ------------------------------------------------------------------
        ops_by_wp_and_spec: dict[tuple[str, str], str] = {
            (op["workpackage_ref"], op["spec_ref"]): op["id"] for op in operations
        }

        for edge in edges:
            pred_spec = edge["predecessor"]
            succ_spec = edge["successor"]
            min_lag_min = _td_to_minutes(_parse_td(edge.get("min_lag", "PT0S")))
            max_lag_raw = edge.get("max_lag")

            for wp_id in wp_op_map:
                pred_id = ops_by_wp_and_spec.get((wp_id, pred_spec))
                succ_id = ops_by_wp_and_spec.get((wp_id, succ_spec))
                if pred_id is None or succ_id is None:
                    continue
                model.add(
                    var_map.op_start[succ_id] >= var_map.op_end[pred_id] + min_lag_min
                )
                if max_lag_raw is not None:
                    max_lag_min = _td_to_minutes(_parse_td(max_lag_raw))
                    model.add(
                        var_map.op_start[succ_id] <= var_map.op_end[pred_id] + max_lag_min
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

        # Overtime premium (docs/06 §5.6/§5.9): minutes scheduled inside a
        # premium window cost rate × ot_mult. Base production above already
        # charges rate × duration for every minute, so the objective adds
        # only the DELTA — rate × (ot_mult − 1) — per overtime minute.
        # Guarded so that no variables are created when the multiplier is
        # unset or no calendar declares overtime: datasets without overtime
        # must build byte-identical models (defaults-reproduce-baseline).
        if ot_mult > 1.0:
            for op in operations:
                oid = op["id"]
                if oid in resumable_op_ids:
                    # Resumable: one overlap var per (chunk slot, premium
                    # window), gated by the slot's own `used` literal (which
                    # already implies the resource assignment).
                    for ci, slot in enumerate(var_map.op_chunks.get(oid, [])):
                        rid = slot["resource"]
                        delta_int = int(rates.get(rid, 0.0) * (ot_mult - 1.0) * _COST_SCALE)
                        if delta_int <= 0:
                            continue
                        for k, (ws, we) in enumerate(overtime_windows.get(rid, [])):
                            ov = self._overlap_var(
                                model, slot["start"], slot["end"], ws, we,
                                slot["used"], horizon_minutes, f"cot_{oid}_{ci}_{k}",
                            )
                            obj_terms.append(ov * delta_int)
                    continue
                for rid, bv in var_map.op_assign.get(oid, {}).items():
                    delta_int = int(rates.get(rid, 0.0) * (ot_mult - 1.0) * _COST_SCALE)
                    if delta_int <= 0:
                        continue
                    for k, (ws, we) in enumerate(overtime_windows.get(rid, [])):
                        ov = self._overlap_var(
                            model, var_map.op_start[oid], var_map.op_end[oid],
                            ws, we, bv, horizon_minutes, f"ot_{oid}_{rid}_{k}",
                        )
                        obj_terms.append(ov * delta_int)

        # Tardiness cost: Σ tard_var[f] × weight[f]
        for fid, tard_var in var_map.tardiness.items():
            w = tard_weights.get(fid, 1)
            obj_terms.append(tard_var * w)

        var_map.objective_terms = obj_terms
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
    # Overtime premium windows (docs/06 §5.6/§5.9)
    # ------------------------------------------------------------------

    @staticmethod
    def _overlap_var(model, s_var, e_var, ws: int, we: int, lit,
                     horizon_minutes: int, name: str):
        """IntVar equal (under minimization) to the overlap in minutes of
        [s_var, e_var) with the fixed window [ws, we), when `lit` holds;
        0 otherwise. Only lower-bounded — the positive objective coefficient
        pins it to max(0, min(e, we) − max(s, ws)) exactly."""
        lo = model.new_int_var(0, horizon_minutes, f"lo_{name}")
        hi = model.new_int_var(0, horizon_minutes, f"hi_{name}")
        model.add_max_equality(lo, [s_var, ws])
        model.add_min_equality(hi, [e_var, we])
        ov = model.new_int_var(0, we - ws, name)
        model.add(ov >= hi - lo).only_enforce_if(lit)
        model.add(ov == 0).only_enforce_if(lit.negated())
        return ov

    def _premium_windows(
        self,
        resources: dict[str, dict],
        cal_map: dict[str, dict],
        cal_windows: dict[str, list[tuple[int, int]]],
        horizon_start: datetime,
        horizon_minutes: int,
    ) -> dict[str, list[tuple[int, int]]]:
        """Per-resource PREMIUM minute windows: the resource calendar's
        `added` exceptions with reason=overtime, minus its regular
        availability. Minutes here exist only because of overtime, so they
        (and only they) price at rate × overtime_premium — an overtime
        window that merely overlaps a regular shift is premium only for the
        portion outside the shift."""
        result: dict[str, list[tuple[int, int]]] = {}
        for rid, res in resources.items():
            cal_id = res.get("calendar_ref")
            cal = cal_map.get(cal_id) if cal_id else None
            if cal is None:
                result[rid] = []
                continue

            ot_raw: list[tuple[int, int]] = []
            for e in cal.get("exceptions", []):
                if isinstance(e, dict):
                    etype = e.get("type", "closure")
                    reason = e.get("reason", "")
                    w = e.get("window", {})
                    ws_dt = _parse_dt(w.get("start"))
                    we_dt = _parse_dt(w.get("end"))
                else:
                    etype = getattr(e.type, "value", e.type)
                    reason = getattr(e.reason, "value", e.reason)
                    ws_dt, we_dt = e.window.start, e.window.end
                if etype != "added" or reason != "overtime":
                    continue
                s_min = max(0, int((ws_dt - horizon_start).total_seconds() / 60))
                e_min = min(horizon_minutes,
                            max(0, int((we_dt - horizon_start).total_seconds() / 60)))
                if e_min > s_min:
                    ot_raw.append((s_min, e_min))

            if not ot_raw:
                result[rid] = []
                continue

            # Regular availability = the flattened windows minus the ones
            # that ARE the overtime additions (flatten appends exception
            # windows verbatim, so they match exactly).
            ot_set = set(ot_raw)
            regular = [w for w in cal_windows.get(rid, []) if w not in ot_set]
            result[rid] = _subtract_intervals(sorted(ot_raw), sorted(regular))
        return result

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
    # Resumable operations — chunk-boundary-interval encoding (docs/05 R-C3)
    #
    # Productionizes tools/chunking_spike2.py, verdicted YELLOW (build for
    # the deployment-relevant density; per-resource decomposition is the
    # validated mitigation at high resumable density — see
    # tools/chunking_spike2_report.md and the 2026-07-10 docs/04 amendment).
    #
    # One optional interval per (eligible resource, candidate calendar
    # window) "chunk slot". Exactly one resource is chosen (op_assign, same
    # boolean interface non-resumable ops use — transitions/locks/objective
    # code need no special-casing). On the chosen resource: chunk working-
    # durations sum to the op's total working minutes; gluing forces a
    # chunk followed by another chunk of the same op to run to its window's
    # end, with the next starting at the next window's open (R-C3: pauses
    # only at calendar boundaries); contiguity requires exactly one "start
    # transition" and one "end transition" among used chunks — the same
    # transition literals pin the operation's overall start/end (needed for
    # WorkPackage-end/tardiness/objective) at no extra cost.
    #
    # Chunk intervals are bounded within their own calendar window by
    # construction, so they can never overlap a closure-blocking interval —
    # unlike the falsified spike-1 (AddElement) encoding, one add_no_overlap
    # group per resource suffices; chunk intervals are appended directly to
    # res_op_intervals by the caller's loop.
    # ------------------------------------------------------------------

    def _feasible_window_range(
        self, windows: list[tuple[int, int]], working_min: int, wp_earliest_min: int,
    ) -> Optional[tuple[int, int]]:
        """Return (lo, hi) candidate window indices this op could touch on
        one resource, or None if the resource has no windows at or after
        wp_earliest_min. hi trims windows with insufficient trailing
        capacity to ever finish the op if started there (tail pruning);
        lo trims windows entirely before the WorkPackage's earliest_start."""
        lo = next((i for i, (s, e) in enumerate(windows) if e > wp_earliest_min), None)
        if lo is None:
            return None
        n = len(windows)
        suffix_capacity = [0] * (n + 1)
        for i in range(n - 1, lo - 1, -1):
            s, e = windows[i]
            avail_start = max(s, wp_earliest_min)
            suffix_capacity[i] = suffix_capacity[i + 1] + max(0, e - avail_start)
        max_start_idx = lo
        for i in range(lo, n):
            if suffix_capacity[i] >= working_min:
                max_start_idx = i

        # Worst-case chunk count bound (not hardcoded to spike 2's synthetic
        # "1-3x window" assumption — real durations vary): ceil(working_min /
        # shortest window) + 1 buffer for a partial first/last chunk.
        min_window_len = min((e - s for s, e in windows[lo:]), default=1) or 1
        chunks_max = max(2, -(-working_min // min_window_len) + 1)

        hi = min(max_start_idx + chunks_max - 1, n - 1)
        return lo, hi

    def _build_resumable_operation(
        self,
        model,
        var_map: "VariableMap",
        oid: str,
        eligible: list[str],
        working_min: int,
        min_chunk_min: int,
        cal_windows: dict[str, list[tuple[int, int]]],
        horizon_minutes: int,
        wp_earliest_min: int,
        res_op_intervals: dict[str, list[Any]],
    ) -> None:
        op_start = model.new_int_var(0, horizon_minutes, f"opstart_{oid}")
        op_end = model.new_int_var(0, horizon_minutes, f"opend_{oid}")
        var_map.op_start[oid] = op_start
        var_map.op_end[oid] = op_end
        var_map.op_chunks[oid] = []

        assign_or: dict[str, Any] = {}
        any_slot_created = False

        for rid in eligible:
            windows = cal_windows.get(rid, [])
            rng = self._feasible_window_range(windows, working_min, wp_earliest_min)
            if rng is None:
                continue
            lo, hi = rng
            idxs = list(range(lo, hi + 1))

            used, durv, starts, ends = {}, {}, {}, {}
            for w in idxs:
                w_start, w_end = windows[w]
                eff_start = max(w_start, wp_earliest_min)
                if eff_start >= w_end:
                    continue
                u = model.new_bool_var(f"u_{oid}_{rid}_{w}")
                s_var = model.new_int_var(eff_start, w_end, f"cs_{oid}_{rid}_{w}")
                e_var = model.new_int_var(eff_start, w_end, f"ce_{oid}_{rid}_{w}")
                d_var = model.new_int_var(0, w_end - eff_start, f"cd_{oid}_{rid}_{w}")
                iv = model.new_optional_interval_var(s_var, d_var, e_var, u, f"civ_{oid}_{rid}_{w}")
                model.add(d_var == 0).only_enforce_if(u.Not())
                if min_chunk_min:
                    model.add(d_var >= min_chunk_min).only_enforce_if(u)
                used[w], durv[w], starts[w], ends[w] = u, d_var, s_var, e_var
                res_op_intervals.setdefault(rid, []).append(iv)
                var_map.op_chunks[oid].append(
                    {"used": u, "start": s_var, "end": e_var, "resource": rid}
                )
                any_slot_created = True

            idxs = [w for w in idxs if w in used]
            if not idxs:
                continue

            bv = model.new_bool_var(f"assign_{oid}_{rid}")
            assign_or[rid] = bv

            # Chunk usage only permitted on the chosen resource.
            for w in idxs:
                model.add(used[w] == 0).only_enforce_if(bv.Not())

            # (1) chunk working-durations sum to the op's total working duration
            model.add(sum(durv[w] for w in idxs) == working_min).only_enforce_if(bv)

            # (3) contiguity — single start-transition, single end-transition
            start_trans, end_trans = {}, {}
            for pos, w in enumerate(idxs):
                if pos == 0:
                    start_trans[w] = used[w]
                else:
                    prev_w = idxs[pos - 1]
                    t = model.new_bool_var(f"st_{oid}_{rid}_{w}")
                    model.add_bool_and([used[w], used[prev_w].Not()]).only_enforce_if(t)
                    model.add_bool_or([used[w].Not(), used[prev_w]]).only_enforce_if(t.Not())
                    start_trans[w] = t
                if pos == len(idxs) - 1:
                    end_trans[w] = used[w]
                else:
                    next_w = idxs[pos + 1]
                    t2 = model.new_bool_var(f"et_{oid}_{rid}_{w}")
                    model.add_bool_and([used[w], used[next_w].Not()]).only_enforce_if(t2)
                    model.add_bool_or([used[w].Not(), used[next_w]]).only_enforce_if(t2.Not())
                    end_trans[w] = t2
            model.add(sum(start_trans.values()) == 1).only_enforce_if(bv)
            model.add(sum(end_trans.values()) == 1).only_enforce_if(bv)

            # (2) gluing — a chunk followed by another chunk of the same op
            # must run to its window's end; the next chunk starts at its
            # window's open (R-C3: pauses only at calendar boundaries)
            for pos in range(len(idxs) - 1):
                w, w_next = idxs[pos], idxs[pos + 1]
                w_end = windows[w][1]
                w_next_start = windows[w_next][0]
                model.add(ends[w] == w_end).only_enforce_if([used[w], used[w_next]])
                model.add(starts[w_next] == w_next_start).only_enforce_if([used[w], used[w_next]])

            for w in idxs:
                model.add(op_start == starts[w]).only_enforce_if([bv, start_trans[w]])
                model.add(op_end == ends[w]).only_enforce_if([bv, end_trans[w]])

        var_map.op_assign[oid] = assign_or
        if assign_or:
            model.add_exactly_one(assign_or.values())
        elif not any_slot_created:
            # No eligible resource has any feasible chunk placement at all —
            # constrain to never start (infeasible signal, matching the
            # non-resumable no-eligible-resource case).
            model.add(op_start == horizon_minutes)

    # ------------------------------------------------------------------
    # Lock constraints (frozen_assignment / pinned_window)
    # ------------------------------------------------------------------

    def _apply_lock_constraints(
        self,
        model,
        constraints: list[dict],
        fulfillments: list[dict],
        operations: list[dict],
        var_map: VariableMap,
    ) -> None:
        """Honor locks.csv-derived Constraint entities (docs/06 §5.12).

        Each lock's Constraint.parameters carries demand_ref/resource_ref/
        sequence/start. Resolved via Fulfillment (demand -> workpackage) to
        the target Operation(s); a blank sequence means "the whole order"
        (all operations in that WorkPackage). No-op for constraint types
        other than frozen_assignment/pinned_window and for submissions with
        no locks — existing sample_data/raw_data runs are unaffected.
        """
        lock_constraints = [
            c for c in constraints
            if c.get("constraint_type") in ("frozen_assignment", "pinned_window")
        ]
        if not lock_constraints:
            return

        fulfillment_by_demand = {f["demand_ref"]: f for f in fulfillments}
        ops_by_wp: dict[str, list[dict]] = {}
        for op in operations:
            ops_by_wp.setdefault(op["workpackage_ref"], []).append(op)

        for con in lock_constraints:
            params = con.get("parameters", {})
            demand_id = params.get("demand_ref")
            ful = fulfillment_by_demand.get(demand_id)
            if ful is None:
                continue
            wp_id = ful["workpackage_ref"]
            seq = params.get("sequence")
            target_ops = [
                op for op in ops_by_wp.get(wp_id, [])
                if seq is None or op.get("sequence") == seq
            ]
            resource_ref = params.get("resource_ref")
            start_iso = params.get("start")

            for op in target_ops:
                oid = op["id"]
                assigns = var_map.op_assign.get(oid, {})
                if resource_ref and resource_ref in assigns:
                    for rid, bv in assigns.items():
                        model.add(bv == 1 if rid == resource_ref else bv == 0)
                if start_iso and oid in var_map.op_start:
                    start_dt = _parse_dt(start_iso)
                    start_min = max(0, int((start_dt - var_map.horizon_start).total_seconds() / 60))
                    model.add(var_map.op_start[oid] == start_min)

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


def _subtract_intervals(
    base: list[tuple[int, int]], cuts: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Return the portions of `base` intervals not covered by any `cuts`."""
    out: list[tuple[int, int]] = []
    for s, e in base:
        segs = [(s, e)]
        for cs, ce in cuts:
            nxt: list[tuple[int, int]] = []
            for a, b in segs:
                if ce <= a or cs >= b:
                    nxt.append((a, b))
                    continue
                if a < cs:
                    nxt.append((a, cs))
                if ce < b:
                    nxt.append((ce, b))
            segs = nxt
            if not segs:
                break
        out.extend(segs)
    return sorted(out)


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime(2099, 1, 1, tzinfo=UTC)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
