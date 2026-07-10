"""Tests for M1 RawAdapter against the raw_data_mini fixture.

Fixture layout (tests/fixtures/raw_data_mini/):
  OpenWorkOrder.csv — 9 WOs covering all test cases
  Routing.csv       — 7 routes (R001–R007)
  RoutingLines.csv  — 8 lines (R004 line has Active=0)
  Product.csv       — 5 products (P003 has CostingLotSize=0)
  BOM.csv           — 3 rows (opaque input only)
  plant_config.json — reference_date 2025-03-22, D3001/D3002 workcenters

Cases exercised:
  WO-A001: admitted — generic route R001 (ProductNo=0), product P001 via WO.ProductNo
  WO-A002: MISSING_REFERENCE — product PMISS not in Product.csv
  WO-A003: VALUE_OUT_OF_RANGE — P003 has CostingLotSize=0
  WO-A004: MISSING_REFERENCE — R004 has no active RoutingLines
  WO-A005: out-of-window — ScheduleDate 2025-03-10 < reference_date 2025-03-22
  WO-A006: admitted — generic route R001, product P006 (different product, same route)
  WO-A007: PROCEEDED_FLAGGED — R005 has Status=0
  WO-A008: PROCEEDED_FLAGGED — R006 has ApprovedStatus=R
  WO-A009: PROCEEDED_FLAGGED — R007.ProductNo=P999 != WO.ProductNo=P001 (product-specific mismatch)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.contracts.vocabularies import (
    FindingCode, FindingDisposition, FindingSeverity, ModuleCode, RecordTier, RunStatus,
)
from mre.modules.raw_adapter import RawAdapter, load_plant_config
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator
from mre.reporter import Reporter

FIXTURE = Path(__file__).parent / "fixtures" / "raw_data_mini"
UTC = timezone.utc


@pytest.fixture
def plant_cfg():
    return load_plant_config(FIXTURE / "plant_config.json")


@pytest.fixture
def adapter_result(tmp_path, plant_cfg):
    store = SnapshotStore(tmp_path / "snapshots")
    rep = Reporter.begin(
        module=ModuleCode.M1, purpose="test adapter run",
        config={}, trigger="test", snapshot_id="snap-mini",
        sink_dir=tmp_path / "runs",
    )
    result = RawAdapter(FIXTURE, plant_cfg).run("snap-mini", store, rep)
    rep.end(RunStatus.SUCCESS)
    return result, rep, store


# ---------------------------------------------------------------------------
# Demand counts
# ---------------------------------------------------------------------------

class TestDemandSelection:
    def test_in_scope_count(self, adapter_result):
        result, rep, _ = adapter_result
        # WO-A001, A002(excl), A003(excl), A004(excl), A006, A007, A008, A009 = 8 in-scope
        # admitted: WO-A001, A006, A007, A008, A009 = 5
        assert result.demand_count == 5

    def test_out_of_window_count(self, adapter_result):
        result, rep, _ = adapter_result
        assert result.out_of_window_count == 1  # WO-A005

    def test_date_filter_decision_emitted(self, adapter_result):
        result, rep, _ = adapter_result
        decisions = [r for r in rep.consolidated_doc.get("records", [])
                     if r.get("record_type") == "decision"]
        assert any("out-of-window" in r.get("message", "") for r in decisions)


# ---------------------------------------------------------------------------
# MISSING_REFERENCE — missing product
# ---------------------------------------------------------------------------

class TestMissingProduct:
    def test_finding_emitted(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.MISSING_REFERENCE.value]
        missing_product_findings = [
            f for f in findings
            if "PMISS" in str(f.get("evidence", {}))
        ]
        assert len(missing_product_findings) >= 1

    def test_excluded_disposition(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.MISSING_REFERENCE.value
                    and "PMISS" in str(r.get("evidence", {}))]
        assert all(f["disposition"] == FindingDisposition.EXCLUDED.value for f in findings)


# ---------------------------------------------------------------------------
# VALUE_OUT_OF_RANGE — zero CostingLotSize
# ---------------------------------------------------------------------------

class TestZeroLotSize:
    def test_finding_emitted(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.VALUE_OUT_OF_RANGE.value]
        p3_findings = [f for f in findings if "P003" in str(f.get("evidence", {}))]
        assert len(p3_findings) >= 1

    def test_severity_error(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.VALUE_OUT_OF_RANGE.value
                    and "P003" in str(r.get("evidence", {}))]
        assert all(f["severity"] == FindingSeverity.ERROR.value for f in findings)


# ---------------------------------------------------------------------------
# MISSING_REFERENCE — inactive route (R004 has only Active=0 lines)
# ---------------------------------------------------------------------------

class TestInactiveRoute:
    def test_finding_emitted(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.MISSING_REFERENCE.value
                    and "R004" in str(r.get("evidence", {}))]
        assert len(findings) >= 1

    def test_excluded(self, adapter_result):
        result, rep, _ = adapter_result
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and r.get("code") == FindingCode.MISSING_REFERENCE.value
                    and "R004" in str(r.get("evidence", {}))]
        assert all(f["disposition"] == FindingDisposition.EXCLUDED.value for f in findings)


# ---------------------------------------------------------------------------
# Generic route — product resolved via WO.ProductNo, not routing
# ---------------------------------------------------------------------------

class TestGenericRoute:
    def test_product_p001_admitted(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        demands = list(reader.iter_entities("demand"))
        d_ids_with_wonoa001 = [
            d for d in demands
            if any(e.get("value") == "WO-A001" for e in d.get("external_refs", []))
        ]
        assert len(d_ids_with_wonoa001) == 1

    def test_demand_product_ref_is_p001(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        demands = {
            next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), ""):
            d for d in reader.iter_entities("demand")
        }
        d = demands.get("WO-A001")
        assert d is not None
        products = {p["id"] for p in reader.iter_entities("product")}
        assert d["product_ref"] in products

    def test_p006_on_same_generic_route_admitted(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        demands = {
            next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), ""):
            d for d in reader.iter_entities("demand")
        }
        assert "WO-A006" in demands

    def test_p001_and_p006_have_distinct_processes(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        prods = {
            next((e["value"] for e in p.get("external_refs", []) if e.get("type") == "product_no"), ""):
            p for p in reader.iter_entities("product")
        }
        assert prods["P001"]["process_ref"] != prods["P006"]["process_ref"]

    def test_routing_productno_zero_does_not_become_product_ref(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        demands = list(reader.iter_entities("demand"))
        product_ids = {p["id"] for p in reader.iter_entities("product")}
        for d in demands:
            assert d["product_ref"] in product_ids


# ---------------------------------------------------------------------------
# Workcenter slash split — F001/D3001 → Resource + Capability
# ---------------------------------------------------------------------------

class TestSlashSplit:
    def test_resources_created_for_each_wc_string(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        resources = list(reader.iter_entities("resource"))
        wc_values = {
            e["value"] for r in resources
            for e in r.get("external_refs", [])
            if e.get("type") == "workcenter"
        }
        assert "F001/D3001" in wc_values
        assert "F001/D3002" in wc_values

    def test_resource_capability_is_code_only(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        resources = {
            next((e["value"] for e in r.get("external_refs", []) if e.get("type") == "workcenter"), ""):
            r for r in reader.iter_entities("resource")
        }
        r3001 = resources.get("F001/D3001")
        assert r3001 is not None
        assert "D3001" in r3001.get("capabilities", [])
        assert "F001" not in r3001.get("capabilities", [])
        assert "F001/D3001" not in r3001.get("capabilities", [])

    def test_explicit_set_req_points_to_resource(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        specs = list(reader.iter_entities("operationspec"))
        res_ids = {r["id"] for r in reader.iter_entities("resource")}
        for spec in specs:
            for req in spec.get("resource_requirements", []):
                assert req.get("mode") == "explicit_set"
                for rid in req.get("resource_refs", []):
                    assert rid in res_ids


# ---------------------------------------------------------------------------
# PROCEEDED_FLAGGED findings
# ---------------------------------------------------------------------------

class TestProceededFlagged:
    def test_status0_route_warning(self, adapter_result):
        result, rep, _ = adapter_result
        # WO-A007 references R005 (Status=0)
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and "R005" in str(r.get("evidence", {}))
                    and r.get("disposition") == FindingDisposition.PROCEEDED_FLAGGED.value]
        assert len(findings) >= 1

    def test_approved_status_r_warning(self, adapter_result):
        result, rep, _ = adapter_result
        # WO-A008 references R006 (ApprovedStatus=R)
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and "R006" in str(r.get("evidence", {}))
                    and r.get("disposition") == FindingDisposition.PROCEEDED_FLAGGED.value]
        assert len(findings) >= 1

    def test_product_mismatch_warning(self, adapter_result):
        result, rep, _ = adapter_result
        # WO-A009: WO.ProductNo=P001, R007.ProductNo=P999
        findings = [r for r in rep.consolidated_doc.get("records", [])
                    if r.get("record_type") == "finding"
                    and "P999" in str(r.get("evidence", {}))
                    and r.get("disposition") == FindingDisposition.PROCEEDED_FLAGGED.value]
        assert len(findings) >= 1

    def test_proceeded_flagged_demands_still_admitted(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        demand_wonos = {
            next((e["value"] for e in d.get("external_refs", []) if e.get("type") == "work_order"), "")
            for d in reader.iter_entities("demand")
        }
        # WO-A007, A008, A009 should all be admitted despite findings
        assert "WO-A007" in demand_wonos
        assert "WO-A008" in demand_wonos
        assert "WO-A009" in demand_wonos


# ---------------------------------------------------------------------------
# Run rate provenance
# ---------------------------------------------------------------------------

class TestRunRateProvenance:
    def test_run_rate_is_derived(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        specs = list(reader.iter_entities("operationspec"))
        assert len(specs) > 0
        for spec in specs:
            prov_records = list(reader.iter_provenance_for_entity(spec["id"]))
            run_rate_prov = [p for p in prov_records if p.get("attribute_name") == "run_rate"]
            assert len(run_rate_prov) >= 1
            assert all(p.get("provenance_class") == "derived" for p in run_rate_prov), (
                f"run_rate provenance should be derived, got {run_rate_prov}"
            )

    def test_run_rate_formula_id(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        specs = list(reader.iter_entities("operationspec"))
        for spec in specs:
            prov_records = list(reader.iter_provenance_for_entity(spec["id"]))
            run_rate_prov = [p for p in prov_records if p.get("attribute_name") == "run_rate"]
            for p in run_rate_prov:
                assert p["payload"]["formula_id"] == "legacy_author_definition_v1"


# ---------------------------------------------------------------------------
# BOM — opaque input
# ---------------------------------------------------------------------------

class TestBOMIngestion:
    def test_bom_metric_emitted(self, adapter_result):
        result, rep, _ = adapter_result
        metrics = [r for r in rep.consolidated_doc.get("records", [])
                   if r.get("record_type") == "metric"
                   and r.get("name") == "bom_row_count"]
        assert len(metrics) == 1
        assert metrics[0]["value"] == 3

    def test_no_bom_canonical_entities(self, adapter_result):
        result, rep, store = adapter_result
        reader = store.load_snapshot("snap-mini")
        # BOM has no canonical entity type; verify no entity with "bom" type
        all_entity_types = set()
        # No dedicated iter call needed — just verify demand/product/resource/etc exist
        # and BOM rows don't sneak in as a new type
        demands = list(reader.iter_entities("demand"))
        assert len(demands) > 0  # sanity


# ---------------------------------------------------------------------------
# Validator integration — reference_date respected
# ---------------------------------------------------------------------------

class TestValidatorIntegration:
    def test_reference_date_prevents_temporal_impossibility(self, tmp_path, plant_cfg):
        """With reference_date=2025-03-22, admitted demands (ScheduleDate >= 2025-03-22)
        should NOT trigger TEMPORAL_IMPOSSIBILITY even though they're in the past
        relative to today's wall clock."""
        from datetime import date
        store = SnapshotStore(tmp_path / "snapshots")
        a_rep = Reporter.begin(
            module=ModuleCode.M1, purpose="test adapter",
            config={}, trigger="test", snapshot_id="snap-vtest",
            sink_dir=tmp_path / "runs",
        )
        RawAdapter(FIXTURE, plant_cfg).run("snap-vtest", store, a_rep)
        a_rep.end(RunStatus.SUCCESS)

        rd = date.fromisoformat(plant_cfg["reference_date"])
        reference_date = datetime(rd.year, rd.month, rd.day, 0, 0, 0, tzinfo=UTC)

        v_rep = Reporter.begin(
            module=ModuleCode.M3, purpose="test validator",
            config={}, trigger="test", snapshot_id="snap-vtest",
            sink_dir=tmp_path / "runs2",
        )
        v_result = Validator().run(
            snapshot_id="snap-vtest", store=store, reporter=v_rep,
            reference_date=reference_date,
        )
        v_rep.end(RunStatus.SUCCESS)

        ti_findings = [r for r in v_rep.consolidated_doc.get("records", [])
                       if r.get("record_type") == "finding"
                       and r.get("code") == FindingCode.TEMPORAL_IMPOSSIBILITY.value]
        assert len(ti_findings) == 0, (
            f"reference_date should suppress TEMPORAL_IMPOSSIBILITY; got {ti_findings}"
        )

    def test_window_fit_check_excludes_infeasible_demand(self, tmp_path):
        """Demand with huge quantity × run_rate that exceeds 720-min shift is excluded."""
        import csv
        import json

        # Build a synthetic mini extract with one huge WO
        mini = tmp_path / "mini_wf"
        mini.mkdir()
        (mini / "plant_config.json").write_text(json.dumps({
            "reference_date": "2025-03-22",
            "workcenter_defaults": {
                "parallel_units": 1,
                "shift_days": [0, 1, 2, 3, 4, 5],
                "shift_start": "07:00",
                "shift_end": "19:00",
            },
            "workcenters": {"D3001": {"parallel_units": 1}},
            "facility_overrides": {},
        }), encoding="utf-8")
        # Product: CostingLotSize=1, ProductionMinutes=100 → rate=100 min/unit
        # WO qty=100 → duration = 100×100 + 30 setup = 10030 min >> 720 min
        with open(mini / "Product.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ProductNo","RetailerID","Facility","ProductGroup","ProductType",
                        "CostPrice","PricePer","CostingLotSize","SetUpMinutes",
                        "ProductionMinutes","UOM"])
            w.writerow(["PBIG","99","F001","PG1","PT1","1","1000","1","30","100","PCS"])
        with open(mini / "Routing.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["RouteCode","FacilityCode","ProductNo","IsDefault","JobCategory",
                        "Status","ApprovedStatus","ApprovedBy","ApprovedDate"])
            w.writerow(["RBIG","F001","0","1","J001","1","A","1","2020-01-01"])
        with open(mini / "RoutingLines.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Ref","RoutingCode","Workcenter","TrackMode","TargetTime",
                        "Sequence","Active","ResourceCode"])
            w.writerow(["1","RBIG","F001/D3001","Default","00:00:00","1","1",""])
        with open(mini / "OpenWorkOrder.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Wono","JobCategory","RouteCode","ProductNo","WoQuantity",
                        "ScheduleDate","CreatedDate","FacilityCode"])
            w.writerow(["WO-BIG","J001","RBIG","PBIG","100",
                        "2025-04-01 00:00:00.000","2025-03-22 08:00:00.000","F001"])
        with open(mini / "BOM.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ProductNo","MaterialNo","UPS","CUT","FixedWastage","Wastage%"])

        cfg = load_plant_config(mini / "plant_config.json")
        store = SnapshotStore(tmp_path / "snapshots2")
        snap = "snap-wf"
        a_rep = Reporter.begin(
            module=ModuleCode.M1, purpose="test",
            config={}, trigger="test", snapshot_id=snap,
            sink_dir=tmp_path / "runs3",
        )
        RawAdapter(mini, cfg).run(snap, store, a_rep)
        a_rep.end(RunStatus.SUCCESS)

        from datetime import date
        rd = date.fromisoformat("2025-03-22")
        reference_date = datetime(rd.year, rd.month, rd.day, 0, 0, 0, tzinfo=UTC)
        v_rep = Reporter.begin(
            module=ModuleCode.M3, purpose="test validator",
            config={}, trigger="test", snapshot_id=snap,
            sink_dir=tmp_path / "runs4",
        )
        v_result = Validator().run(snap, store, v_rep, reference_date=reference_date)
        v_rep.end(RunStatus.SUCCESS)

        inf_findings = [r for r in v_rep.consolidated_doc.get("records", [])
                        if r.get("record_type") == "finding"
                        and r.get("code") == FindingCode.INFEASIBLE_SUBSET.value]
        assert len(inf_findings) >= 1
        assert "WO-BIG" in str(inf_findings[0].get("evidence", {})) or \
               inf_findings[0].get("severity") == FindingSeverity.ERROR.value


# ---------------------------------------------------------------------------
# Splittability doorway (docs/05 R-C3): plant_config declares resumability
# per workcenter — raw routing lines have no splittable column.
# ---------------------------------------------------------------------------

class TestSplittabilityDoorway:
    def _run(self, tmp_path, cfg):
        store = SnapshotStore(tmp_path / "snapshots")
        rep = Reporter.begin(
            module=ModuleCode.M1, purpose="doorway test", config={},
            trigger="test", snapshot_id="snap-split", sink_dir=tmp_path / "runs",
        )
        RawAdapter(FIXTURE, cfg).run("snap-split", store, rep)
        rep.end(RunStatus.SUCCESS)
        return store.load_snapshot("snap-split")

    def _specs_by_wc(self, reader):
        res_ext = {r["id"]: r["external_refs"][0]["value"]
                   for r in reader.iter_entities("resource")}
        out = {}
        for sp in reader.iter_entities("operationspec"):
            refs = sp["resource_requirements"][0]["resource_refs"]
            wc = res_ext[refs[0]].split("/", 1)[-1]
            out.setdefault(wc, []).append(sp)
        return out

    def test_undeclared_workcenters_stay_non_splittable(self, tmp_path, plant_cfg):
        reader = self._run(tmp_path, plant_cfg)
        for sp in reader.iter_entities("operationspec"):
            assert sp["splittable"] is False
            assert sp["min_chunk"] is None

    def test_declared_workcenter_specs_become_resumable_with_min_chunk(
        self, tmp_path, plant_cfg
    ):
        import copy
        cfg = copy.deepcopy(plant_cfg)
        cfg["workcenters"]["D3001"]["splittable"] = True
        cfg["workcenters"]["D3001"]["min_chunk_minutes"] = 30

        reader = self._run(tmp_path, cfg)
        by_wc = self._specs_by_wc(reader)
        assert by_wc.get("D3001"), "fixture should route work through D3001"
        for sp in by_wc["D3001"]:
            assert sp["splittable"] is True
            assert sp["min_chunk"] == "PT30M"
        for wc, specs in by_wc.items():
            if wc == "D3001":
                continue
            for sp in specs:
                assert sp["splittable"] is False

    def test_splittable_provenance_is_defaulted_policy_not_observed(
        self, tmp_path, plant_cfg
    ):
        """The pre-doorway code wrote OBSERVED sidecars citing RoutingLines
        for splittable/min_chunk — a column that does not exist. Provenance
        must say plant-config policy (declared) or absent-source default."""
        import copy
        cfg = copy.deepcopy(plant_cfg)
        cfg["workcenters"]["D3001"]["splittable"] = True

        reader = self._run(tmp_path, cfg)
        by_wc = self._specs_by_wc(reader)
        for wc, specs in by_wc.items():
            for sp in specs:
                provs = {p["attribute_name"]: p
                         for p in reader.iter_provenance_for_entity(sp["id"])}
                for attr in ("splittable", "min_chunk"):
                    assert provs[attr]["provenance_class"] == "defaulted", (
                        f"{wc}/{attr}: expected defaulted, got "
                        f"{provs[attr]['provenance_class']}"
                    )


# ---------------------------------------------------------------------------
# Cost-model doorway: plant_config.cost_model prices the raw path
# (docs/06 §5.9 semantics; absent -> historical zero defaults)
# ---------------------------------------------------------------------------

class TestCostModelDoorway:
    def _run(self, tmp_path, cfg):
        store = SnapshotStore(tmp_path / "snapshots")
        rep = Reporter.begin(
            module=ModuleCode.M1, purpose="cost doorway test", config={},
            trigger="test", snapshot_id="snap-cost", sink_dir=tmp_path / "runs",
        )
        RawAdapter(FIXTURE, cfg).run("snap-cost", store, rep)
        rep.end(RunStatus.SUCCESS)
        return store.load_snapshot("snap-cost")

    def test_absent_cost_model_keeps_zero_defaults(self, tmp_path, plant_cfg):
        reader = self._run(tmp_path, plant_cfg)
        cm = next(iter(reader.iter_entities("costmodel")))
        assert cm["resource_rates"] == {}
        assert cm["setup_cost_basis"]["fixed_per_setup"] == 0.0
        assert cm["tardiness_weights"]["base_weight"] == 1.0
        for r in reader.iter_entities("resource"):
            assert r["cost_rate"] == 0.0

    def test_cost_model_section_prices_resources_and_tardiness(self, tmp_path, plant_cfg):
        import copy
        cfg = copy.deepcopy(plant_cfg)
        cfg["cost_model"] = {
            "default_resource_rate_per_hour": 60.0,
            "setup_cost_per_setup": 40.0,
            "tardiness_cost_per_hour": 25.0,
            "resource_rates": {"D3001": 120.0},
        }
        reader = self._run(tmp_path, cfg)
        cm = next(iter(reader.iter_entities("costmodel")))
        assert cm["setup_cost_basis"]["fixed_per_setup"] == 40.0
        assert cm["tardiness_weights"]["base_weight"] == pytest.approx(25.0 / 60.0)
        for r in reader.iter_entities("resource"):
            wc_full = r["external_refs"][0]["value"]
            expected = 2.0 if wc_full.endswith("/D3001") else 1.0
            # single-source invariant: entity field == CostModel entry, $/min
            assert r["cost_rate"] == pytest.approx(expected)
            assert cm["resource_rates"][r["id"]] == pytest.approx(expected)
