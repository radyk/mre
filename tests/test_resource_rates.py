"""Resource-rates audit tests (docs/06 §5.5, docs/04 rates-audit amendment).

The consumption path under guard: resources.csv cost_rate → CostModel.
resource_rates (precedence: cost-model default < resources.csv override <
refinements.resource_rates) → solver_builder/extractor pricing. Plus the
single-source invariant that closed the dormant-register finding:
Resource.cost_rate carries the SAME effective $/minute value as the
resource's CostModel.resource_rates entry — the two sources can no longer
silently disagree.
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter
from tools.generate_erp_dataset import generate

from tests.test_solver_builder import (
    _calendar, _costmodel, _demand, _fulfillment, _operation, _resource, _wp,
)

UTC = timezone.utc
REPO = Path(__file__).parent.parent
MON = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
DUE = datetime(2026, 7, 14, 23, 59, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Per-resource rates differentiate machine choices (builder level)
# ---------------------------------------------------------------------------


class TestRatesDifferentiateMachineChoice:
    def _solve_choice(self, rates: dict) -> str:
        """One op eligible on two resources; return the chosen resource."""
        from ortools.sat.python import cp_model as cp
        from mre.modules.solver_builder import SolverBuilder

        op = _operation("op-1", "wp-1", "spec-1", run_sec=600 * 60)
        op["resource_requirements"] = [
            {"mode": "explicit_set", "resource_refs": ["r-cheap", "r-dear"], "count": 1}
        ]
        model, var_map = SolverBuilder().build(
            [_wp("wp-1", "p", 1, ["op-1"], earliest=MON), op],
            [_resource("r-cheap", cal_ref="cal"), _resource("r-dear", cal_ref="cal")],
            [_calendar("cal")],
            [_fulfillment("f1", "d1", "wp-1", 1), _demand("d1", "p", 1, DUE, earliest=MON)],
            [],
            _costmodel("cm", rates=rates, setup_fixed=0.0),
        )
        solver = cp.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 42
        assert solver.Solve(model) == cp.OPTIMAL
        return var_map.extract(solver).op_resource["op-1"]

    def test_cheaper_rate_wins_and_flipping_rates_flips_the_choice(self):
        assert self._solve_choice({"r-cheap": 1.0, "r-dear": 5.0}) == "r-cheap"
        assert self._solve_choice({"r-cheap": 5.0, "r-dear": 1.0}) == "r-dear"


# ---------------------------------------------------------------------------
# IDS path: resources.csv cost_rate → CostModel, single-source invariant
# ---------------------------------------------------------------------------


def _run_ids_adapter(sub_dir: Path, tmp: Path):
    from mre.modules.ids_adapter import IDSAdapter
    store = SnapshotStore(tmp / "snapshots")
    rep = Reporter.begin(
        module=ModuleCode.M1, purpose="rates audit test", config={},
        trigger="pytest", snapshot_id="snap-rates", sink_dir=tmp / "runs",
    )
    IDSAdapter(submission_dir=sub_dir).run("snap-rates", store, rep)
    rep.end(RunStatus.SUCCESS)
    return store.load_snapshot("snap-rates")


class TestIDSCostRateConsumption:
    @pytest.fixture()
    def snapshot_reader(self, tmp_path):
        sub_dir = tmp_path / "submission"
        generate(sub_dir, scenario="clean_small", seed=5)

        # Give the LAST resource (never covered by clean_small's refinements,
        # which span only the first half) a resources.csv cost_rate override.
        res_path = sub_dir / "resources.csv"
        with open(res_path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.override_ext_id = rows[-1]["resource_id"]
        rows[-1]["cost_rate"] = "120.0"
        with open(res_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

        self.cost_model_raw = json.loads((sub_dir / "cost_model.json").read_text(encoding="utf-8"))
        self.refinements = self.cost_model_raw["refinements"]["resource_rates"]
        assert self.override_ext_id not in self.refinements
        return _run_ids_adapter(sub_dir, tmp_path)

    def test_csv_override_refinement_and_default_all_land_in_costmodel(self, snapshot_reader):
        reader = snapshot_reader
        cm = next(iter(reader.iter_entities("costmodel")))
        resources = {r["id"]: r for r in reader.iter_entities("resource")}
        ext_of = {
            r["id"]: next(e["value"] for e in r["external_refs"] if e["type"] == "resource_id")
            for r in resources.values()
        }

        default_per_min = self.cost_model_raw["core"]["default_resource_rate_per_hour"] / 60.0
        seen = {"observed": 0, "refined": 0, "defaulted": 0}
        for rid, ext in ext_of.items():
            got = cm["resource_rates"][rid]
            if ext in self.refinements:
                assert got == pytest.approx(self.refinements[ext] / 60.0)
                seen["refined"] += 1
            elif ext == self.override_ext_id:
                assert got == pytest.approx(120.0 / 60.0)
                seen["observed"] += 1
            else:
                assert got == pytest.approx(default_per_min)
                seen["defaulted"] += 1
        # All three precedence layers must actually occur in this fixture.
        assert all(v > 0 for v in seen.values()), seen

    def test_resource_cost_rate_equals_costmodel_entry_for_every_resource(self, snapshot_reader):
        """The single-source invariant that closes the dormant-register
        finding: the entity field and the CostModel entry are the same
        effective $/minute value — no silent disagreement possible."""
        reader = snapshot_reader
        cm = next(iter(reader.iter_entities("costmodel")))
        for r in reader.iter_entities("resource"):
            assert r["cost_rate"] == pytest.approx(cm["resource_rates"][r["id"]]), (
                f"Resource.cost_rate diverged from CostModel.resource_rates "
                f"for {r['id']}"
            )
            assert r["cost_rate"] > 0

    def test_cost_rate_provenance_matches_actual_source(self, snapshot_reader):
        """The pre-fix bug: a hardcoded 0.0 written under an *observed*
        sidecar citing the cost_rate column. Now the provenance class must
        name where the value really came from."""
        reader = snapshot_reader
        for r in reader.iter_entities("resource"):
            ext = next(e["value"] for e in r["external_refs"] if e["type"] == "resource_id")
            prov = next(
                p for p in reader.iter_provenance_for_entity(r["id"])
                if p["attribute_name"] == "cost_rate"
            )
            if ext in self.refinements:
                assert prov["provenance_class"] == "derived"
            elif ext == self.override_ext_id:
                assert prov["provenance_class"] == "observed"
            else:
                assert prov["provenance_class"] == "defaulted"


class TestGeneratedC1CostDecomposition:
    def test_production_cost_is_priced_from_per_resource_rates(self, tmp_path):
        """Full --submission pipeline on a C1 scenario: recompute production
        cost from the persisted assignments × per-resource rates and match
        the schedule's ledger — and show the per-resource rates matter (the
        all-default figure differs)."""
        sub_dir = tmp_path / "submission"
        out_dir = tmp_path / "out"
        generate(sub_dir, scenario="clean_small", seed=5)
        exit_code = mre_main([
            "--submission", str(sub_dir), "--out", str(out_dir),
            "--time-limit", "30", "--solver-workers", "1", "--solver-seed", "42",
        ])
        assert exit_code == 0

        reader = SnapshotStore(out_dir / "snapshots").load_snapshot("snap-run")
        cm = next(iter(reader.iter_entities("costmodel")))
        rates = cm["resource_rates"]
        schedule = next(iter(reader.iter_entities("schedule")))
        ledger_production = schedule["summary_metrics"]["production_cost"]

        recomputed = 0.0
        default_priced = 0.0
        used_rates = set()
        default_per_min = 60.0 / 60.0  # clean_small core default
        for asgn in reader.iter_entities("assignment"):
            rid = asgn["resource_assignments"][0]["resource_ref"]
            minutes = sum(
                (datetime.fromisoformat(w["end"]) - datetime.fromisoformat(w["start"])
                 ).total_seconds() / 60
                for w in asgn["phase_windows"]["run"]
            )
            recomputed += minutes * rates[rid]
            default_priced += minutes * default_per_min
            used_rates.add(round(rates[rid], 6))

        assert recomputed == pytest.approx(ledger_production)
        # C1 refinements give half the plant non-default rates: the schedule
        # must actually exercise more than one rate, and pricing everything
        # at the default must give a different answer.
        assert len(used_rates) >= 2
        assert default_priced != pytest.approx(ledger_production)


# ---------------------------------------------------------------------------
# Sample path: machines.csv CostRate fills costmodel.json gaps
# ---------------------------------------------------------------------------


class TestSampleAdapterFold:
    def test_machine_missing_from_costmodel_json_falls_back_to_csv_rate(self, tmp_path):
        from mre.modules.adapter import Adapter, _stable_id

        data_dir = tmp_path / "sample_data"
        shutil.copytree(REPO / "sample_data", data_dir)

        # Remove one machine from costmodel.json and give another a CSV rate
        # that differs from its json entry (json must win where present).
        cm_path = data_dir / "costmodel.json"
        cm_raw = json.loads(cm_path.read_text(encoding="utf-8"))
        del cm_raw["resource_rates"]["M-CAST-01"]
        cm_path.write_text(json.dumps(cm_raw, indent=2), encoding="utf-8")

        m_path = data_dir / "machines.csv"
        with open(m_path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["MachineID"] == "M-CAST-02":
                row["CostRate"] = "9.9"
        with open(m_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

        store = SnapshotStore(tmp_path / "snapshots")
        rep = Reporter.begin(
            module=ModuleCode.M1, purpose="fold test", config={},
            trigger="pytest", snapshot_id="snap-fold", sink_dir=tmp_path / "runs",
        )
        Adapter(extract_dir=data_dir).run("snap-fold", store, rep)
        rep.end(RunStatus.SUCCESS)

        reader = store.load_snapshot("snap-fold")
        cm = next(iter(reader.iter_entities("costmodel")))
        # Gap filled from machines.csv (CostRate 5.0, $/min).
        assert cm["resource_rates"][_stable_id("resource", "M-CAST-01")] == pytest.approx(5.0)
        # json wins where present: M-CAST-02 keeps 5.0 despite CSV 9.9.
        assert cm["resource_rates"][_stable_id("resource", "M-CAST-02")] == pytest.approx(5.0)
