"""Tests for M0 — the IDS conformance gate (src/mre/modules/conformance.py).

Builds fixtures via tools/generate_erp_dataset.py (the gate's executable
twin) rather than hand-rolled CSVs, so the gate and the generator keep each
other honest — the same pairing exercised at scale by test_ids_end_to_end.py.
"""
from __future__ import annotations

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import ConformanceGate
from mre.reporter import Reporter
from tools.generate_erp_dataset import generate


def _run_gate(tmp_path, submission_dir, runs_dir=None):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="test gate run", config={}, trigger="test",
        snapshot_id="pre-adapter", sink_dir=runs_dir or (tmp_path / "runs"),
    )
    result = ConformanceGate().run(submission_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


def _codes(result):
    return {f["code"] for f in result.certificate["findings"]}


class TestCleanSmall:
    def test_accepted(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        result = _run_gate(tmp_path, out)
        assert result.grade == "ACCEPTED"
        assert result.go is True
        assert result.costing_grade == "C1"

    def test_no_deficiencies(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        result = _run_gate(tmp_path, out)
        assert result.certificate["deficiencies"] == []


class TestMissingRequiredFile:
    def test_rejected(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["missing_required_file:products.csv"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "REJECTED"
        assert result.go is False
        assert "MISSING_REFERENCE" in _codes(result)
        assert any("products.csv" in d for d in result.certificate["deficiencies"])

    def test_missing_manifest_is_rejected(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        (out / "manifest.json").unlink()
        result = _run_gate(tmp_path, out)
        assert result.grade == "REJECTED"
        assert any("manifest" in d for d in result.certificate["deficiencies"])


class TestCostModelCore:
    def test_missing_core_field_rejected(self, tmp_path):
        import json
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        cm_path = out / "cost_model.json"
        cm = json.loads(cm_path.read_text(encoding="utf-8"))
        del cm["core"]["tardiness_cost_per_hour"]
        cm_path.write_text(json.dumps(cm), encoding="utf-8")
        result = _run_gate(tmp_path, out)
        assert result.grade == "REJECTED"
        assert any("cost_model core" in d for d in result.certificate["deficiencies"])


class TestOrphanRefs:
    def test_low_pct_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, orders=100,
                 anomalies=["orphan_product_refs:5"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "ORPHAN_ENTITY" in _codes(result)

    def test_high_pct_rejected(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, orders=100,
                 anomalies=["orphan_product_refs:70"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "REJECTED"


class TestZeroLotSize:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["zero_lot_size:2"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "VALUE_OUT_OF_RANGE" in _codes(result)


class TestDuplicateOrderIds:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["duplicate_order_ids:3"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "DUPLICATE_IDENTITY" in _codes(result)
        dup_finding = next(f for f in result.certificate["findings"] if f["code"] == "DUPLICATE_IDENTITY")
        assert dup_finding["evidence"]["duplicate_count"] == 3


class TestInactiveRouteRefs:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["inactive_route_refs:3"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "LOW_CONFIDENCE_INPUT" in _codes(result)


class TestStaleAndPlaceholderDates:
    def test_stays_accepted_but_flagged(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1,
                 anomalies=["stale_due_dates:2", "placeholder_dates:1"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "ACCEPTED"  # Tier 3: informational only
        codes = _codes(result)
        assert "VALUE_OUT_OF_RANGE" in codes
        infos = [f for f in result.certificate["findings"] if f["severity"] == "info"]
        assert any(f["evidence"].get("check") == "stale_backlog" for f in infos)
        assert any(f["evidence"].get("check") == "placeholder_date" for f in infos)


class TestSetupFamilyWithoutMatrix:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["setup_family_without_matrix"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "AMBIGUOUS_SOURCE" in _codes(result)


class TestUncoveredPriorityClass:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["uncovered_priority_class"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "UNMAPPABLE_VALUE" in _codes(result)


class TestLockOnUnknownOrder:
    def test_conditional(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1, anomalies=["lock_on_unknown_order:2"])
        result = _run_gate(tmp_path, out)
        assert result.grade == "CONDITIONAL"
        assert "ORPHAN_ENTITY" in _codes(result)


class TestCostingCompletenessGrade:
    def test_c1_c2_ladder(self, tmp_path):
        for scenario, expected in (("clean_small", "C1"), ("transition_heavy", "C2")):
            out = tmp_path / scenario
            generate(out, scenario=scenario, seed=1)
            result = _run_gate(tmp_path, out, runs_dir=tmp_path / f"runs_{scenario}")
            assert result.costing_grade == expected


class TestPermittedNormalizations:
    def test_bom_stripped_recorded(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        orders_path = out / "orders.csv"
        orders_path.write_bytes(b"\xef\xbb\xbf" + orders_path.read_bytes())
        result = _run_gate(tmp_path, out)
        assert any("BOM stripped" in n for n in result.certificate["normalizations"])
        assert result.grade == "ACCEPTED"
