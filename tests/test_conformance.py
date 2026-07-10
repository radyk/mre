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


# ---------------------------------------------------------------------------
# wip_status.csv doorway (docs/06 §5.13, §4 Tier 1c/2 WIP coherence)
# ---------------------------------------------------------------------------

_WIP_COLS = ["order_id", "sequence", "status", "actual_start",
             "actual_resource_id", "remaining_minutes", "quantity_complete"]


def _submission_shape(sub_dir):
    """(orders rows, order_id → sorted route sequences, resource ids)."""
    import csv

    with open(sub_dir / "orders.csv", encoding="utf-8-sig", newline="") as f:
        orders = list(csv.DictReader(f))
    with open(sub_dir / "routing_lines.csv", encoding="utf-8-sig", newline="") as f:
        lines = list(csv.DictReader(f))
    seqs_by_route: dict[str, list[int]] = {}
    res_by_route_seq: dict[tuple[str, str], str] = {}
    for rl in lines:
        if rl.get("active") == "1":
            seqs_by_route.setdefault(rl["route_id"], []).append(int(rl["sequence"]))
            res_by_route_seq[(rl["route_id"], rl["sequence"])] = rl["resource_id"]
    order_seqs = {
        o["order_id"]: sorted(seqs_by_route.get(o["route_id"], []))
        for o in orders
    }
    return orders, order_seqs, res_by_route_seq


def _write_wip(sub_dir, rows, basis="remaining_minutes", declare=True):
    import csv
    import json

    with open(sub_dir / "wip_status.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_WIP_COLS)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in _WIP_COLS})
    if declare:
        manifest = json.loads((sub_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["semantics"]["wip_progress_basis"] = basis
        (sub_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")


def _wip_findings(result):
    return [f for f in result.certificate["findings"]
            if str(f.get("evidence", {}).get("check", "")).startswith("wip_")]


class TestWipDoorway:
    """Gate coherence checks are findings, never crashes (docs/06 §4 Tier 2).
    Finding-code review (add-never-repurpose): every WIP check maps onto an
    existing code with its established meaning — ORPHAN_ENTITY (unknown
    refs), MALFORMED_FIELD (in_progress row missing its observed state),
    LOW_CONFIDENCE_INPUT (sequence-order violation: a shop-floor-reporting
    quality signal), VALUE_OUT_OF_RANGE (internally inconsistent or
    post-reference values). No new codes required."""

    def _sub(self, tmp_path):
        out = tmp_path / "sub"
        generate(out, scenario="clean_small", seed=1)
        return out

    def test_wip_without_progress_basis_declaration_rejected(self, tmp_path):
        """§3: wip_progress_basis is REQUIRED iff wip_status.csv is present.
        We do not divine meaning — Tier 1, rejecting."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        _write_wip(sub, [{
            "order_id": o["order_id"], "sequence": str(order_seqs[o["order_id"]][0]),
            "status": "complete", "actual_start": "2026-01-02T08:00:00",
            "actual_resource_id": res_map[(o["route_id"], str(order_seqs[o["order_id"]][0]))],
        }], declare=False)
        result = _run_gate(tmp_path, sub)
        assert result.grade == "REJECTED"
        assert "MALFORMED_FIELD" in _codes(result)
        assert any("wip_progress_basis" in d for d in result.certificate["deficiencies"])

    def test_clean_wip_accepted(self, tmp_path):
        """A coherent WIP file: complete op with actuals, in-flight op with
        observed start/resource/remaining, explicit not_started rows. Grade
        stays ACCEPTED, no WIP findings."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seqs = order_seqs[o["order_id"]]
        rows = [
            {"order_id": o["order_id"], "sequence": str(seqs[0]),
             "status": "complete", "actual_start": "2026-01-02T08:00:00",
             "actual_resource_id": res_map[(o["route_id"], str(seqs[0]))]},
            {"order_id": o["order_id"], "sequence": str(seqs[1]),
             "status": "in_progress", "actual_start": "2026-01-02T14:00:00",
             "actual_resource_id": res_map[(o["route_id"], str(seqs[1]))],
             "remaining_minutes": "240"},
        ]
        if len(seqs) > 2:
            rows.append({"order_id": o["order_id"], "sequence": str(seqs[2]),
                         "status": "not_started"})
        _write_wip(sub, rows)
        result = _run_gate(tmp_path, sub)
        assert result.grade == "ACCEPTED"
        assert _wip_findings(result) == []
        assert result.certificate["counts"]["wip_status"] == len(rows)

    def test_pre_reference_observed_start_is_normal_not_a_finding(self, tmp_path):
        """Recurring-submission reality: an observed start after the PREVIOUS
        run's reference but before this manifest's reference_date is normal
        drift, never a finding (the certificate trend line is where drift
        shows up, not the gate)."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seq = str(order_seqs[o["order_id"]][0])
        # reference_date is 2026-01-05; a start days earlier is history
        _write_wip(sub, [{
            "order_id": o["order_id"], "sequence": seq,
            "status": "in_progress", "actual_start": "2025-12-30T09:15:00",
            "actual_resource_id": res_map[(o["route_id"], seq)],
            "remaining_minutes": "120",
        }])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "ACCEPTED"
        assert _wip_findings(result) == []

    def test_unknown_refs_conditional(self, tmp_path):
        """wip rows referencing unknown orders / sequences / resources —
        ORPHAN_ENTITY, excluded, CONDITIONAL."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seq = str(order_seqs[o["order_id"]][0])
        good_res = res_map[(o["route_id"], seq)]
        _write_wip(sub, [
            {"order_id": "ORD-DOES-NOT-EXIST", "sequence": seq,
             "status": "complete", "actual_start": "2026-01-02T08:00:00",
             "actual_resource_id": good_res},
            {"order_id": o["order_id"], "sequence": "9999",
             "status": "complete", "actual_start": "2026-01-02T08:00:00",
             "actual_resource_id": good_res},
            {"order_id": o["order_id"], "sequence": seq,
             "status": "in_progress", "actual_start": "2026-01-02T08:00:00",
             "actual_resource_id": "RES-DOES-NOT-EXIST",
             "remaining_minutes": "60"},
        ])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "CONDITIONAL"
        wf = _wip_findings(result)
        assert any(f["code"] == "ORPHAN_ENTITY"
                   and f["evidence"]["check"] == "wip_unknown_refs"
                   and f["evidence"]["count"] == 3 for f in wf)

    def test_in_progress_missing_observed_state_conditional(self, tmp_path):
        """in_progress with no observed resource, no observed start, or no
        progress value (per the declared basis) — MALFORMED_FIELD, treated
        as not_started (defaulted), CONDITIONAL."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o1, o2, o3 = orders[0], orders[1], orders[2]

        def _row(o, **kw):
            seq = str(order_seqs[o["order_id"]][0])
            base = {"order_id": o["order_id"], "sequence": seq,
                    "status": "in_progress",
                    "actual_start": "2026-01-02T08:00:00",
                    "actual_resource_id": res_map[(o["route_id"], seq)],
                    "remaining_minutes": "60"}
            base.update(kw)
            return base

        _write_wip(sub, [
            _row(o1, actual_start=""),          # no observed start
            _row(o2, actual_resource_id=""),    # no observed resource
            _row(o3, remaining_minutes=""),     # no progress value (declared basis)
        ])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "CONDITIONAL"
        wf = _wip_findings(result)
        assert any(f["code"] == "MALFORMED_FIELD"
                   and f["evidence"]["check"] == "wip_in_progress_incomplete"
                   and f["evidence"]["count"] == 3 for f in wf)

    def test_sequence_order_violation_flagged(self, tmp_path):
        """An operation in_progress while its predecessor is not_started —
        LOW_CONFIDENCE_INPUT (a data-quality signal about shop-floor
        reporting), proceeded_flagged, CONDITIONAL. IDS routing has no
        overlap-permitting edge source (min_lag ≥ 0, max-lag doorway
        deferred), so no edge can excuse it at the gate."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seqs = order_seqs[o["order_id"]]
        _write_wip(sub, [
            {"order_id": o["order_id"], "sequence": str(seqs[0]),
             "status": "not_started"},
            {"order_id": o["order_id"], "sequence": str(seqs[1]),
             "status": "in_progress", "actual_start": "2026-01-02T08:00:00",
             "actual_resource_id": res_map[(o["route_id"], str(seqs[1]))],
             "remaining_minutes": "60"},
        ])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "CONDITIONAL"
        wf = _wip_findings(result)
        assert any(f["code"] == "LOW_CONFIDENCE_INPUT"
                   and f["evidence"]["check"] == "wip_sequence_order_violation"
                   for f in wf)

    def test_complete_with_remaining_quantity_flagged(self, tmp_path):
        """A completed op still carrying remaining work is internally
        inconsistent — VALUE_OUT_OF_RANGE, proceeded_flagged (completion
        wins), CONDITIONAL."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seq = str(order_seqs[o["order_id"]][0])
        _write_wip(sub, [{
            "order_id": o["order_id"], "sequence": seq,
            "status": "complete", "actual_start": "2026-01-02T08:00:00",
            "actual_resource_id": res_map[(o["route_id"], seq)],
            "remaining_minutes": "120",
        }])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "CONDITIONAL"
        wf = _wip_findings(result)
        assert any(f["code"] == "VALUE_OUT_OF_RANGE"
                   and f["evidence"]["check"] == "wip_complete_with_remaining"
                   for f in wf)

    def test_observed_start_after_reference_flagged(self, tmp_path):
        """An observed start after THIS submission's reference_date means the
        extract is incoherent with its own declared clock — VALUE_OUT_OF_RANGE,
        CONDITIONAL."""
        sub = self._sub(tmp_path)
        orders, order_seqs, res_map = _submission_shape(sub)
        o = orders[0]
        seq = str(order_seqs[o["order_id"]][0])
        _write_wip(sub, [{
            "order_id": o["order_id"], "sequence": seq,
            "status": "in_progress", "actual_start": "2026-01-08T08:00:00",
            "actual_resource_id": res_map[(o["route_id"], seq)],
            "remaining_minutes": "60",
        }])
        result = _run_gate(tmp_path, sub)
        assert result.grade == "CONDITIONAL"
        wf = _wip_findings(result)
        assert any(f["code"] == "VALUE_OUT_OF_RANGE"
                   and f["evidence"]["check"] == "wip_start_after_reference"
                   for f in wf)
