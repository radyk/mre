"""Session 4.5 — the unguarded-edge family + severity semantics.

The Glass Box audit found three architectural misses and one disease:

  * CU3 (the disease) — severity meant nothing: a finding could claim ``error``
    while its disposition said the run proceeded. The Finding contract now
    enforces that an error/blocker severity carries an acting disposition, and
    the gate derives finding severity from the disposition, so a proceeded flag
    is honestly a WARNING (the grade still degrades via the outcome).
  * CU5 — a duration floor laundered garbage: a negative computed duration
    (from a negative quantity) floored to a plausible 1-minute op. The seam
    now raises instead of laundering.
  * CU1/CU2/CU4 have their integration coverage in test_glass_box.py and their
    unit coverage in test_extractor.py (the vacuous-fulfillment guard) and here
    (the excluded-orders enumeration).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from mre.contracts.entities import EntityRef
from mre.contracts.records import Finding
from mre.contracts.vocabularies import (
    FindingCode, FindingDisposition, FindingSeverity, ModuleCode, RecordTier,
)

UTC = timezone.utc


def _finding(severity: FindingSeverity, disposition: FindingDisposition) -> Finding:
    return Finding(
        record_id="rec-1", run_id="run-1", seq=1, module=ModuleCode.M3,
        timestamp=datetime(2026, 1, 5, tzinfo=UTC), snapshot_id="snap-1",
        subjects=[EntityRef(entity_id="d-1", entity_type="demand")],
        tier=RecordTier.SUPPORTING, message="test",
        code=FindingCode.VALUE_OUT_OF_RANGE, severity=severity,
        evidence={"reason": "test"}, disposition=disposition,
    )


# ---------------------------------------------------------------------------
# CU3 — severity carries a consequence (the Finding contract invariant)
# ---------------------------------------------------------------------------

class TestSeverityCarriesConsequence:
    def test_error_with_proceeded_flagged_is_illegal(self):
        """The named specimen: VALUE_OUT_OF_RANGE at ERROR + proceeded_flagged.
        The label claims a consequence the disposition did not deliver."""
        with pytest.raises(ValidationError, match="error"):
            _finding(FindingSeverity.ERROR, FindingDisposition.PROCEEDED_FLAGGED)

    def test_error_with_defaulted_is_illegal(self):
        with pytest.raises(ValidationError):
            _finding(FindingSeverity.ERROR, FindingDisposition.DEFAULTED)

    def test_error_with_excluded_is_legal(self):
        f = _finding(FindingSeverity.ERROR, FindingDisposition.EXCLUDED)
        assert f.severity == FindingSeverity.ERROR

    def test_blocker_must_block(self):
        with pytest.raises(ValidationError, match="blocker"):
            _finding(FindingSeverity.BLOCKER, FindingDisposition.EXCLUDED)

    def test_blocker_with_blocked_is_legal(self):
        f = _finding(FindingSeverity.BLOCKER, FindingDisposition.BLOCKED)
        assert f.severity == FindingSeverity.BLOCKER

    def test_warning_proceeded_flagged_is_legal(self):
        """A proceeded flag is exactly a WARNING — the honest demotion."""
        f = _finding(FindingSeverity.WARNING, FindingDisposition.PROCEEDED_FLAGGED)
        assert f.severity == FindingSeverity.WARNING


class TestGateSeverityFromDisposition:
    """The systemic cure: a DEGRADED gate rule that proceeds flagged now emits a
    WARNING finding (the run proceeded) while still degrading the grade via its
    outcome — the two axes no longer contradict each other."""

    def test_degraded_proceeded_rule_is_warning_not_error(self, tmp_path):
        from mre.contracts.vocabularies import RunStatus
        from mre.modules.conformance import ConformanceGate
        from mre.reporter import Reporter
        from tools.generate_erp_dataset import generate

        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=7, anomalies=["duplicate_order_ids:2"])
        reporter = Reporter.begin(
            module=ModuleCode.M0, purpose="t", config={}, trigger="test",
            snapshot_id="pre-adapter", sink_dir=tmp_path / "runs",
        )
        result = ConformanceGate().run(sub, reporter)
        reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)

        assert result.grade == "CONDITIONAL"          # grade still degrades
        dup = [f for f in result.certificate["findings"]
               if f["evidence"].get("rule_id") == "ids.order_identities_unique"]
        assert dup, "expected a duplicate-identity finding"
        # proceeded_flagged -> WARNING, never a lying ERROR
        assert dup[0]["severity"] == "warning"
        assert dup[0]["disposition"] == "proceeded_flagged"


# ---------------------------------------------------------------------------
# CU5 — a duration floor never launders garbage
# ---------------------------------------------------------------------------

class TestDurationFloorSeam:
    def test_negative_duration_raises(self):
        from mre.modules.solver_builder import _td_to_minutes
        # -60 units x 3 min/unit = -180 min — the exact glass_box -60 path.
        with pytest.raises(ValueError, match="negative"):
            _td_to_minutes(timedelta(minutes=-180))

    def test_sub_minute_positive_still_floors_to_one(self):
        from mre.modules.solver_builder import _td_to_minutes
        assert _td_to_minutes(timedelta(seconds=30)) == 1
        assert _td_to_minutes(timedelta(0)) == 1

    def test_normal_duration_unchanged(self):
        from mre.modules.solver_builder import _td_to_minutes
        assert _td_to_minutes(timedelta(minutes=470)) == 470


# ---------------------------------------------------------------------------
# CU4 — validator exclusions reach the certificate conversation (enumerable)
# ---------------------------------------------------------------------------

class TestExcludedOrdersEnumerable:
    def test_excluded_orders_route_enumerates_from_all_layers(self, tmp_path):
        """A negative-quantity order is excluded downstream; the certificate
        conversation must enumerate it (the report card may never be blinder
        than dq_report.md)."""
        from mre.__main__ import main as mre_main
        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.explainer import Explainer
        from mre.modules.snapshot_store import SnapshotStore
        from tools.generate_erp_dataset import generate

        sub = tmp_path / "sub"
        out = tmp_path / "out"
        generate(sub, scenario="clean_small", seed=5, anomalies=["negative_quantity:1"])
        code = mre_main(["--submission", str(sub), "--out", str(out),
                         "--snapshot-id", "snap-excl", "--time-limit", "20"])
        assert code == 0

        idx = EvidenceIndex.load(out / "evidence_index.json")
        store = SnapshotStore(out / "snapshots")
        ex = Explainer(store, idx, snapshot_id="snap-excl")

        route, _ = ex.classify("which orders were excluded from the plan?")
        assert route == "excluded-orders"

        bundle = ex.answer("which orders were excluded from the plan?")
        enumerated = bundle.key_facts["excluded_orders"]
        assert bundle.key_facts["excluded_count"] >= 1
        # a VALUE_OUT_OF_RANGE exclusion (the negative quantity) is enumerated
        assert any(o["code"] == "VALUE_OUT_OF_RANGE" for o in enumerated), enumerated
        # and the report card is not blinder than dq_report: every excluded /
        # blocked finding in the store is enumerated
        store_excluded = [
            f for f in idx.all_findings()
            if f.get("disposition") in ("excluded", "blocked")
        ]
        assert len(bundle.ordered_records) == len(store_excluded)
