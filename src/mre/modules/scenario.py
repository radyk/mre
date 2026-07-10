"""M_whatif — Scenario definition and execution for what-if analysis.

A Scenario is a base snapshot + a list of typed modifications.
ScenarioRunner derives a child snapshot (copy-on-write), applies the
modifications, re-runs the scheduling spine, and returns a diff.

HARD RULES (docs/01 §4.1, §6.9, §8; docs/02 §4.2):
- Scenario evidence is written to a separate directory so the main
  EvidenceIndex never sees it.
- Scenario schedules carry status="proposed" and is_scenario=True in
  summary_metrics; they must never be confusable with the real schedule.
- Each modification is recorded as a Decision
  (type=scenario_modification, basis=policy_applied, driver=POLICY_RULE).
- ScenarioRunner has no direct write path into canonical model entities
  beyond patching entity JSONL inside the derived snapshot directory.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

UTC = timezone.utc

_M1_ENTITY_TYPES = [
    "demand", "product", "resource", "resourcepool", "calendar",
    "constraint", "costmodel", "process", "operationspec", "precedenceedge",
]


# ---------------------------------------------------------------------------
# Modification types
# ---------------------------------------------------------------------------

class ModificationType(str, Enum):
    SUPPRESS_MERGE = "suppress_merge"
    SET_COST_WEIGHT = "set_cost_weight"
    CALENDAR_EXCEPTION = "calendar_exception"


@dataclass
class SuppressMerge:
    """Force the listed demands to be planned individually (no batching)."""
    demand_refs: list[str]          # external WO names, e.g. ["WO-2001", "WO-2002"]


@dataclass
class SetCostWeight:
    """Override a cost-model field via dot-path."""
    path: str                       # e.g. "tardiness_weights.base_weight"
    value: float


@dataclass
class CalendarException:
    """Add a calendar window exception on a resource's calendar."""
    resource_ref: str               # external machine name, e.g. "M-GEAR-01"
    window: dict                    # {"start": ISO, "end": ISO}
    type: str                       # "closure" | "added"
    reason: str                     # from CalendarExceptionReason


# ---------------------------------------------------------------------------
# Scenario container
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    base_snapshot_id: str
    modifications: list[Any]        # SuppressMerge | SetCostWeight | CalendarException

    def short_hash(self) -> str:
        data = json.dumps({
            "base": self.base_snapshot_id,
            "mods": [(type(m).__name__, vars(m)) for m in self.modifications],
        }, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:8]

    def scenario_snapshot_id(self) -> str:
        return f"{self.base_snapshot_id}--scenario-{self.short_hash()}"

    def description(self) -> str:
        parts: list[str] = []
        for mod in self.modifications:
            if isinstance(mod, SuppressMerge):
                parts.append(f"suppress_merge({', '.join(mod.demand_refs)})")
            elif isinstance(mod, SetCostWeight):
                parts.append(f"set_cost_weight({mod.path}={mod.value})")
            elif isinstance(mod, CalendarException):
                parts.append(f"calendar_exception({mod.resource_ref} {mod.type})")
        return "; ".join(parts) or "no modifications"


@dataclass
class ScenarioResult:
    scenario_snapshot_id: str
    base_snapshot_id: str
    extract_result: Any             # ExtractResult
    diff: dict


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def derive_base_context(runs_dir: Path | str) -> dict:
    """Recover the base pipeline's run configuration from the run_context_open
    records in its runs/ directory (docs/02 RunContext.config_snapshot).

    The scenario runner must re-validate/re-plan/re-solve under the same
    reference date, outlier threshold, planner policy, horizon slice and
    solver settings as the base run — a diff taken under different
    configuration measures drift, not the modification.
    """
    ctx: dict[str, Any] = {}
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return ctx
    for f in sorted(runs_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") != "run_context_open":
                continue
            cfg = rec.get("config_snapshot") or {}
            module = rec.get("module", "")
            purpose = rec.get("purpose") or ""
            if module == "M3":
                rd = cfg.get("reference_date")
                if rd and rd != "now":
                    ctx["reference_date"] = rd
                if cfg.get("outlier_threshold_ratio") is not None:
                    ctx["outlier_threshold_ratio"] = cfg["outlier_threshold_ratio"]
            elif module == "M4" and "horizon-slice" in purpose:
                if cfg.get("horizon_days") is not None:
                    ctx["horizon_days"] = cfg["horizon_days"]
            elif module == "M4":
                if cfg.get("policy"):
                    ctx["policy"] = cfg["policy"]
                if cfg.get("risk_margin") is not None:
                    ctx["risk_margin"] = cfg["risk_margin"]
            elif module == "M6":
                if cfg.get("time_limit") is not None:
                    ctx["time_limit"] = cfg["time_limit"]
                if cfg.get("num_search_workers") is not None:
                    ctx["solver_workers"] = cfg["num_search_workers"]
                if cfg.get("random_seed") is not None:
                    ctx["solver_seed"] = cfg["random_seed"]
    return ctx


class ScenarioRunner:
    """Derives a scenario snapshot, re-runs the scheduling spine, returns a diff.

    Evidence is written to runs_dir (NOT the main mre_output/runs/) so the
    default EvidenceIndex never includes scenario runs.
    """

    def __init__(
        self,
        store: Any,                 # SnapshotStore
        runs_dir: Path,             # separate from main runs/
        time_limit_seconds: float = 30.0,
        base_context: Optional[dict] = None,
    ) -> None:
        self._store = store
        self._runs_dir = Path(runs_dir)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._time_limit = time_limit_seconds
        # Base-pipeline configuration (derive_base_context): the scenario
        # must re-validate/re-plan/re-solve under the SAME policy, demand
        # exclusions, reference date, horizon slice and solver pinning as
        # the base run — otherwise the diff measures configuration drift,
        # not the modification (Phase-1 exit audit: a stale-due demand the
        # base validator excluded reappeared in a scenario 575k min late).
        self._ctx = base_context or {}

    def run(self, scenario: Scenario) -> ScenarioResult:
        """Execute a scenario and return a diff against the base schedule."""
        scen_snap_id = scenario.scenario_snapshot_id()

        # Clean up any stale scenario snapshot (ignore_errors for Windows locks)
        scen_dir = self._store._base / scen_snap_id
        if scen_dir.exists():
            shutil.rmtree(str(scen_dir), ignore_errors=True)

        # 1. Derive snapshot: copy M1 input entities from base
        self._store.derive_scenario_snapshot(
            scenario.base_snapshot_id, scen_snap_id, _M1_ENTITY_TYPES
        )

        # 2. Resolve modifications and apply entity-level changes
        suppressed_demand_ids: set[str] = set()
        base_reader = self._store.load_snapshot(scenario.base_snapshot_id)
        base_identity_map = base_reader.read_identity_map()

        for mod in scenario.modifications:
            if isinstance(mod, SuppressMerge):
                suppressed_demand_ids |= self._resolve_suppress_merge(
                    mod, base_reader, base_identity_map
                )
            elif isinstance(mod, SetCostWeight):
                self._apply_cost_weight(mod, scen_snap_id)
            elif isinstance(mod, CalendarException):
                self._apply_calendar_exception(mod, scen_snap_id, base_identity_map)

        # 3. Emit scenario modification Decisions as evidence
        from mre.contracts.vocabularies import ModuleCode, RunStatus
        from mre.reporter import Reporter

        mod_rep = Reporter.begin(
            module=ModuleCode.M4,
            purpose="scenario modifications",
            config={"scenario_id": scen_snap_id, "description": scenario.description()},
            trigger="whatif",
            snapshot_id=scen_snap_id,
            sink_dir=self._runs_dir,
        )
        for mod in scenario.modifications:
            self._emit_modification_decision(mod_rep, scen_snap_id, mod, base_reader)
        mod_rep.end(RunStatus.SUCCESS)

        # 3b. Re-run M3 (Validator) on the scenario snapshot so the base
        # run's demand exclusions (TEMPORAL_IMPOSSIBILITY, window-fit, ...)
        # are reproduced — the scenario must schedule the same demand
        # population the base did.
        reference_date = None
        ref_raw = self._ctx.get("reference_date")
        if ref_raw and ref_raw != "now":
            reference_date = datetime.fromisoformat(ref_raw)
            if reference_date.tzinfo is None:
                reference_date = reference_date.replace(tzinfo=UTC)

        from mre.modules.validator import Validator
        v_rep = Reporter.begin(
            module=ModuleCode.M3,
            purpose="scenario semantic validation",
            config={"reference_date": ref_raw or "now",
                    "outlier_threshold_ratio": self._ctx.get("outlier_threshold_ratio")},
            trigger="whatif",
            snapshot_id=scen_snap_id,
            sink_dir=self._runs_dir,
        )
        v_result = Validator().run(
            snapshot_id=scen_snap_id, store=self._store, reporter=v_rep,
            reference_date=reference_date,
            outlier_threshold_ratio=self._ctx.get("outlier_threshold_ratio"),
        )
        v_rep.end(RunStatus.SUCCESS)
        excluded_demand_ids: set[str] = set(v_result.excluded_demand_ids)

        # 3c. Reproduce the base run's horizon-slice (--horizon-days), if any.
        horizon_days = self._ctx.get("horizon_days")
        if horizon_days is not None:
            ref_dt = reference_date or datetime.now(UTC)
            cutoff = (ref_dt + timedelta(days=horizon_days)).replace(
                hour=23, minute=59, second=59, microsecond=0,
            )
            slice_reader = self._store.load_snapshot(scen_snap_id)
            for d in slice_reader.iter_entities("demand"):
                if d["id"] in excluded_demand_ids or not d.get("due"):
                    continue
                due_dt = datetime.fromisoformat(d["due"])
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=UTC)
                if due_dt > cutoff:
                    excluded_demand_ids.add(d["id"])

        # 4. Run M4 (Planner) with suppressed merges, under the BASE policy
        policy = self._ctx.get("policy", "merge_by_family_v1")
        risk_margin = self._ctx.get("risk_margin", 1.0)
        p_rep = Reporter.begin(
            module=ModuleCode.M4,
            purpose="scenario demand planning",
            config={"policy": policy, "risk_margin": risk_margin},
            trigger="whatif",
            snapshot_id=scen_snap_id,
            sink_dir=self._runs_dir,
        )
        from mre.modules.planner import Planner
        Planner(policy=policy, risk_margin=risk_margin).run(
            snapshot_id=scen_snap_id,
            store=self._store,
            reporter=p_rep,
            excluded_demand_ids=excluded_demand_ids,
            suppressed_merge_ids=suppressed_demand_ids,
        )
        p_rep.end(RunStatus.SUCCESS)

        # 5. Load entities for solving
        reader = self._store.load_snapshot(scen_snap_id)
        demands    = list(reader.iter_entities("demand"))
        fuls       = list(reader.iter_entities("fulfillment"))
        wps        = list(reader.iter_entities("workpackage"))
        ops        = list(reader.iter_entities("operation"))
        edges      = list(reader.iter_entities("precedenceedge"))
        resources  = list(reader.iter_entities("resource"))
        pools      = list(reader.iter_entities("resourcepool"))
        calendars  = list(reader.iter_entities("calendar"))
        constraints = list(reader.iter_entities("constraint"))
        costmodels  = list(reader.iter_entities("costmodel"))
        cost_model = costmodels[0] if costmodels else {
            "id": "default-cm", "resource_rates": {},
            "setup_cost_basis": {"fixed_per_setup": 50.0, "scrap_cost_per_unit": 0.0},
            "tardiness_weights": {"base_weight": 1.0, "commitment_class_multipliers": {}},
        }

        # 6. Flatten calendars — horizon from the demands actually planned
        # (validator + slice exclusions), clamped to reference_date like the
        # base pipeline.
        from mre.modules.calendar_utils import compute_horizon, flatten_all_calendars
        horizon_start, horizon_end = compute_horizon(demands, excluded_demand_ids)
        if reference_date is not None:
            ref_floor = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
            horizon_start = max(horizon_start, ref_floor)
        flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

        # 7. Run M5 (SolverBuilder)
        b_rep = Reporter.begin(
            module=ModuleCode.M5, purpose="scenario model build",
            config={}, trigger="whatif",
            snapshot_id=scen_snap_id, sink_dir=self._runs_dir,
        )
        from mre.modules.solver_builder import SolverBuilder
        model, var_map = SolverBuilder(reference_date=reference_date).build(
            wps + ops + edges, resources + pools, flattened_cals,
            fuls + demands, constraints, cost_model,
        )
        b_rep.end(RunStatus.SUCCESS)

        # 8. Run M6 (SolveRunner)
        r_rep = Reporter.begin(
            module=ModuleCode.M6, purpose="scenario solve",
            config={"time_limit": self._time_limit}, trigger="whatif",
            snapshot_id=scen_snap_id, sink_dir=self._runs_dir,
        )
        from mre.modules.solve_runner import SolveRunner
        solve_result = SolveRunner(
            time_limit_seconds=self._time_limit,
            num_search_workers=self._ctx.get("solver_workers"),
            random_seed=self._ctx.get("solver_seed"),
        ).solve(
            model, var_map, r_rep
        )
        r_rep.end(
            RunStatus.SUCCESS if solve_result.status in ("OPTIMAL", "FEASIBLE")
            else RunStatus.PARTIAL
        )
        if solve_result.status not in ("OPTIMAL", "FEASIBLE"):
            raise RuntimeError(
                f"Scenario solve failed with status={solve_result.status}"
            )

        # 9. Run M7 (Extractor) — is_scenario=True marks the schedule
        e_rep = Reporter.begin(
            module=ModuleCode.M7, purpose="scenario schedule extraction",
            config={}, trigger="whatif",
            snapshot_id=scen_snap_id, sink_dir=self._runs_dir,
        )
        m7_writer = self._store.extend_snapshot(scen_snap_id)
        from mre.modules.extractor import Extractor
        extract_result = Extractor().extract(
            solve_values=solve_result.solve_values,
            snapshot_id=scen_snap_id,
            operations=ops,
            workpackages=wps,
            resources=resources,
            fulfillments=fuls,
            demands=demands,
            cost_model=cost_model,
            reporter=e_rep,
            cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible,
            snapshot_writer=m7_writer,
            is_scenario=True,
            overtime_windows=var_map.overtime_windows,
        )
        m7_writer.finalize()
        e_rep.end(RunStatus.SUCCESS)

        # 10. Read base schedule data and compute diff
        base_data = self._read_base_data(scenario.base_snapshot_id)
        diff = _compute_schedule_diff(
            base_snap_id=scenario.base_snapshot_id,
            scen_snap_id=scen_snap_id,
            base_data=base_data,
            scen_extract=extract_result,
            store=self._store,
            description=scenario.description(),
        )

        return ScenarioResult(
            scenario_snapshot_id=scen_snap_id,
            base_snapshot_id=scenario.base_snapshot_id,
            extract_result=extract_result,
            diff=diff,
        )

    # ------------------------------------------------------------------
    # Modification helpers
    # ------------------------------------------------------------------

    def _resolve_suppress_merge(
        self,
        mod: SuppressMerge,
        reader: Any,
        identity_map: Any,
    ) -> set[str]:
        ids: set[str] = set()
        for wo_ref in mod.demand_refs:
            if not identity_map:
                continue
            did = identity_map.resolve("ERP", "work_order", wo_ref)
            if did is None:
                # Any order-shaped external ref, any system (IDS order_id
                # etc.) — the customer's vocabulary, not sample_data's.
                did = next(
                    (canon for (s, t, v), canon in identity_map._to_canonical.items()
                     if t in ("work_order", "order_id") and v.upper() == wo_ref.upper()),
                    None,
                )
            if did:
                ids.add(did)
        return ids

    def _apply_cost_weight(self, mod: SetCostWeight, snap_id: str) -> None:
        snap_dir = self._store._base / snap_id
        cm_path = snap_dir / "entities_costmodel.jsonl"
        if not cm_path.exists():
            return
        new_lines: list[str] = []
        for line in cm_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cm = json.loads(line)
            cm = _apply_path_value(cm, mod.path, mod.value)
            new_lines.append(json.dumps(cm))
        cm_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _apply_calendar_exception(
        self,
        mod: CalendarException,
        snap_id: str,
        identity_map: Any,
    ) -> None:
        snap_dir = self._store._base / snap_id
        rid = identity_map.resolve("ERP", "machine_id", mod.resource_ref) if identity_map else None
        if not rid:
            return

        res_path = snap_dir / "entities_resource.jsonl"
        if not res_path.exists():
            return
        cal_ref: Optional[str] = None
        for line in res_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("id") == rid:
                cal_ref = r.get("calendar_ref")
                break
        if not cal_ref:
            return

        cal_path = snap_dir / "entities_calendar.jsonl"
        if not cal_path.exists():
            return
        new_lines: list[str] = []
        for line in cal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cal = json.loads(line)
            if cal.get("id") == cal_ref:
                excs = list(cal.get("exceptions", []))
                excs.append({
                    "window": mod.window,
                    "type": mod.type,
                    "reason": mod.reason,
                })
                cal["exceptions"] = excs
            new_lines.append(json.dumps(cal))
        cal_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _emit_modification_decision(
        self,
        reporter: Any,
        snap_id: str,
        mod: Any,
        base_reader: Any,
    ) -> None:
        from mre.contracts.entities import EntityRef
        from mre.contracts.records import DecisionAlternative
        from mre.contracts.vocabularies import (
            DecisionBasis, DecisionType, DriverCode, RecordTier,
        )

        if isinstance(mod, SuppressMerge):
            chosen = {
                "modification_type": ModificationType.SUPPRESS_MERGE,
                "demand_refs": mod.demand_refs,
            }
            alternatives = [DecisionAlternative(
                option="merge_by_family_v1",
                consequence=(
                    "WOs merged; setup cost amortized but "
                    "earliest-due demand exposed to lateness risk."
                ),
            )]
            msg = f"Scenario: suppress_merge({', '.join(mod.demand_refs)})"
        elif isinstance(mod, SetCostWeight):
            chosen = {
                "modification_type": ModificationType.SET_COST_WEIGHT,
                "path": mod.path,
                "value": mod.value,
            }
            alternatives = []
            msg = f"Scenario: set_cost_weight({mod.path}={mod.value})"
        else:
            chosen = {
                "modification_type": ModificationType.CALENDAR_EXCEPTION,
                "resource_ref": mod.resource_ref,
                "type": mod.type,
                "reason": mod.reason,
            }
            alternatives = []
            msg = f"Scenario: calendar_{mod.type} on {mod.resource_ref}"

        reporter.record_decision(
            decision_type=DecisionType.SCENARIO_MODIFICATION,
            subjects=[],
            chosen=chosen,
            alternatives=alternatives,
            driver=DriverCode.POLICY_RULE,
            basis=DecisionBasis.POLICY_APPLIED,
            tier=RecordTier.HEADLINE,
            message=msg,
        )

    def _read_base_data(self, snap_id: str) -> dict:
        """Reconstruct cost ledger and service outcomes from base snapshot entities.

        Persisted ServiceOutcome entities use 'lateness' (ISO 8601 duration).
        Normalise to 'lateness_minutes' so _compute_schedule_diff sees a consistent key.
        """
        reader = self._store.load_snapshot(snap_id)
        assignments      = list(reader.iter_entities("assignment"))
        raw_svc_outcomes = list(reader.iter_entities("serviceoutcome"))
        schedules        = list(reader.iter_entities("schedule"))

        # Normalise service outcome lateness to minutes
        service_outcomes = []
        for svc in raw_svc_outcomes:
            svc = dict(svc)
            if "lateness_minutes" not in svc:
                svc["lateness_minutes"] = _parse_duration_minutes(svc.get("lateness"))
            service_outcomes.append(svc)

        sm = schedules[0].get("summary_metrics", {}) if schedules else {}

        prod_cost  = sm.get("production_cost",
                            sum(a.get("production_cost", 0.0) for a in assignments))
        tard_cost  = sm.get("tardiness_cost",
                            sum(s.get("tardiness_cost", 0.0) for s in service_outcomes))
        total_cost = sm.get("total_cost", prod_cost + tard_cost)
        setup_cost = sm.get("setup_cost", total_cost - prod_cost - tard_cost)

        # Normalize assignment field names from persisted entity format
        norm_assignments = [_normalize_assignment(a) for a in assignments]

        return {
            "assignments": norm_assignments,
            "service_outcomes": service_outcomes,
            "cost_ledger": {
                "total_cost": total_cost,
                "production_cost": prod_cost,
                "setup_cost": setup_cost,
                "tardiness_cost": tard_cost,
            },
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _normalize_assignment(a: dict) -> dict:
    """Add 'resource_id' and 'run_start' to a persisted Assignment entity dict.

    Persisted entities use resource_assignments[].resource_ref and
    phase_windows.run[].start — different from the in-memory extractor dicts.
    This normaliser adds the flat keys expected by _compute_schedule_diff.
    """
    a = dict(a)
    if "resource_id" not in a:
        ra = a.get("resource_assignments", [])
        a["resource_id"] = ra[0].get("resource_ref") if ra else None
    if "run_start" not in a:
        pw = a.get("phase_windows") or {}
        runs = pw.get("run", [])
        a["run_start"] = runs[0].get("start") if runs else None
    return a


def _parse_duration_minutes(s: Optional[str]) -> Optional[float]:
    """Parse an ISO 8601 duration string (as stored by Pydantic timedelta) to minutes.

    Examples: 'PT14H' -> 840.0; '-P1DT9H59M' -> -1919.0; None -> None.
    """
    if s is None:
        return None
    neg = s.startswith("-")
    s = s.lstrip("-").lstrip("P")
    years = days = hours = minutes = 0.0
    # Pydantic emits a years component for timedeltas ≥ 365 days
    # ('-P3Y34DT10H34M', Y = exactly 365 days) — placeholder-date demands
    # produce these routinely; parsing must not choke on them.
    if "Y" in s:
        y_part, s = s.split("Y", 1)
        years = float(y_part)
    if "D" in s:
        d_part, s = s.split("D", 1)
        days = float(d_part)
    if s.startswith("T"):
        s = s[1:]
    if "H" in s:
        h_part, s = s.split("H", 1)
        hours = float(h_part)
    if "M" in s:
        m_part, _ = s.split("M", 1)
        minutes = float(m_part)
    total = years * 365 * 24 * 60 + days * 24 * 60 + hours * 60 + minutes
    return -total if neg else total


def _apply_path_value(obj: dict, path: str, value: Any) -> dict:
    """Apply a dot-path value override to a nested dict (mutates in place)."""
    parts = path.split(".")
    d = obj
    for part in parts[:-1]:
        if part not in d:
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value
    return obj


def _compute_schedule_diff(
    base_snap_id: str,
    scen_snap_id: str,
    base_data: dict,
    scen_extract: Any,
    store: Any,
    description: str,
) -> dict:
    """Compute per-demand service deltas and cost decomposition delta.

    Returns a dict keyed for the scenario_diff ExplanationBundle.
    """
    base_reader = store.load_snapshot(base_snap_id)
    identity_map = base_reader.read_identity_map()

    def _wo_name(demand_id: str) -> str:
        if identity_map:
            refs = identity_map.external_refs(demand_id)
            wo = next((r.value for r in refs if r.type == "work_order"), None)
            if wo:
                return wo
        return demand_id[:8]

    def _machine_name(resource_id: str) -> str:
        if not resource_id:
            return "?"
        if identity_map:
            refs = identity_map.external_refs(resource_id)
            m = next((r.value for r in refs if r.type == "machine_id"), None)
            if m:
                return m
        return resource_id[:8]

    # Per-demand service deltas
    base_by_demand: dict[str, dict] = {
        s["demand_ref"]: s for s in base_data["service_outcomes"]
    }
    scen_by_demand: dict[str, dict] = {
        s["demand_ref"]: s for s in scen_extract.service_outcomes
    }
    all_demand_ids = sorted(set(base_by_demand) | set(scen_by_demand))

    service_deltas: list[dict] = []
    for did in all_demand_ids:
        b = base_by_demand.get(did, {})
        s = scen_by_demand.get(did, {})
        lb = b.get("lateness_minutes")
        la = s.get("lateness_minutes")
        if lb is None and la is None:
            continue
        service_deltas.append({
            "work_order": _wo_name(did),
            "lateness_before": lb,
            "lateness_after": la,
            "lateness_delta": (
                int(la) - int(lb) if lb is not None and la is not None else None
            ),
        })

    # Cost decomposition deltas — must decompose: total_delta = Σ components
    bl = base_data["cost_ledger"]
    sl = scen_extract.cost_ledger
    prod_d  = sl["production_cost"] - bl["production_cost"]
    setup_d = sl["setup_cost"]      - bl["setup_cost"]
    tard_d  = sl["tardiness_cost"]  - bl["tardiness_cost"]
    total_d = sl["total_cost"]      - bl["total_cost"]
    decomp_check = prod_d + setup_d + tard_d
    cost_delta = {
        "total_before":       bl["total_cost"],
        "total_after":        sl["total_cost"],
        "total_delta":        total_d,
        "production_delta":   prod_d,
        "setup_delta":        setup_d,
        "tardiness_delta":    tard_d,
        "_decomp_ok":         abs(total_d - decomp_check) < 0.01,
    }

    # Assignment moves (operation-level resource or start-time changes)
    base_by_op: dict[str, dict] = {
        a["operation_ref"]: a for a in base_data["assignments"]
    }
    scen_by_op: dict[str, dict] = {
        a["operation_ref"]: a for a in scen_extract.assignments
    }
    moved_op_ids = [
        op_id for op_id in set(base_by_op) & set(scen_by_op)
        if (base_by_op[op_id].get("resource_id") != scen_by_op[op_id].get("resource_id")
            or base_by_op[op_id].get("run_start") != scen_by_op[op_id].get("run_start"))
    ]
    notable_moves: list[str] = []
    for op_id in moved_op_ids[:5]:
        b = base_by_op[op_id]
        s = scen_by_op[op_id]
        bm = _machine_name(b.get("resource_id", ""))
        sm_ = _machine_name(s.get("resource_id", ""))
        bs = (b.get("run_start") or "?")[:16]
        ss = (s.get("run_start") or "?")[:16]
        notable_moves.append(f"op {op_id[:8]}: {bm}@{bs} -> {sm_}@{ss}")

    return {
        "base_snapshot_id":    base_snap_id,
        "scenario_snapshot_id": scen_snap_id,
        "description":         description,
        "service_deltas":      service_deltas,
        "cost_delta":          cost_delta,
        "assignment_moves": {
            "total_changed": len(moved_op_ids),
            "notable":       notable_moves,
        },
    }
