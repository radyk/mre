"""Rule Registry coverage + evidence-shape regression (docs/06 §4, handoff §D).

These tests parametrize over RULE_REGISTRY *itself*, so a future rule added
without an anomaly generator, or an emit site that drops its rule_id, fails CI
by construction — the registry can never again silently claim a check the gate
does not have.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.ids_rules import (
    RULE_REGISTRY, RuleId, RuleOutcome, RuleStatus, grade_from_outcomes,
)
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import ConformanceGate
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter
from tools.generate_erp_dataset import RULE_TO_ANOMALY, generate

IMPLEMENTED = sorted(
    rid.value for rid, spec in RULE_REGISTRY.items()
    if spec.status == RuleStatus.IMPLEMENTED
)


def _run_gate(sub_dir: Path, runs_dir: Path):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="registry test", config={}, trigger="test",
        snapshot_id="pre-adapter", sink_dir=runs_dir,
    )
    result = ConformanceGate().run(sub_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


class TestRegistryShape:
    def test_thirty_four_rules(self):
        assert len(RULE_REGISTRY) == 34

    def test_every_implemented_rule_has_an_anomaly(self):
        """Completeness by construction: the coverage map must name a trigger
        for every implemented rule — no more, no fewer."""
        assert set(RULE_TO_ANOMALY) == set(IMPLEMENTED)

    def test_rule_ids_follow_naming_convention(self):
        """Present-tense conditions in IDS vocabulary: no digits, no
        threshold/severity/implementation words (docs/06 §4 lint-bound)."""
        banned = {"check", "validate", "parse", "band", "threshold", "severity",
                  "warning", "error"}
        for rid in RuleId:
            local = rid.value.split(".", 1)[1]
            assert not any(ch.isdigit() for ch in local), rid.value
            assert local == local.lower()
            # 'parse' is grandfathered in required_columns_parse (registry note);
            # everything else stays clean.
            tokens = set(local.split("_"))
            assert not (tokens & banned) or rid == RuleId.REQUIRED_COLUMNS_PARSE, rid.value


@pytest.mark.parametrize("rule_id", IMPLEMENTED)
class TestCoverageMatrix:
    """Every implemented rule has a scenario that produces its finding, with a
    non-satisfied outcome the rule's category permits."""

    def test_rule_produces_its_finding(self, tmp_path, rule_id):
        spec_str = RULE_TO_ANOMALY[rule_id]
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=7, anomalies=[spec_str])
        result = _run_gate(sub, tmp_path / "runs")
        hits = [
            f for f in result.certificate["findings"]
            if f["evidence"].get("rule_id") == rule_id
            and f["evidence"].get("outcome") != "satisfied"
        ]
        assert hits, (
            f"{rule_id} (anomaly '{spec_str}') produced no finding; "
            f"got {sorted({f['evidence'].get('rule_id') for f in result.certificate['findings']})}"
        )
        outcome = RuleOutcome(hits[0]["evidence"]["outcome"])
        assert RULE_REGISTRY[RuleId(rule_id)].allows(outcome)
        assert hits[0]["evidence"]["rule_id"] == RULE_REGISTRY[RuleId(rule_id)].rule_id.value
        # the finding code is exactly the registry's code for this rule
        assert hits[0]["code"] == RULE_REGISTRY[RuleId(rule_id)].finding_code.value


class TestReverseGuard:
    """Every M0 finding carries a registry rule_id in typed evidence — no
    orphan (anonymous) checks can reappear (the audit's reverse guard)."""

    def test_no_orphan_checks(self, tmp_path):
        registry_values = {r.value for r in RuleId}
        # a submission that trips a broad spread of rules at once
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=3, anomalies=[
            "duplicate_order_ids:2", "inactive_route_refs:2", "stale_due_dates:2",
            "placeholder_dates:1", "foreign_facility:2", "inverted_dates:2",
            "sparse_optionals:1", "defaulted_attributes:2",
        ])
        result = _run_gate(sub, tmp_path / "runs")
        assert result.certificate["findings"]
        for f in result.certificate["findings"]:
            assert "rule_id" in f["evidence"], f
            assert f["evidence"]["rule_id"] in registry_values, f["evidence"]["rule_id"]
            assert "outcome" in f["evidence"]


class TestGradeIsPureFunction:
    """The certificate grade equals grade_from_outcomes over the recorded rule
    outcomes (docs/06 §4) — grade is not an ad-hoc accumulation."""

    @pytest.mark.parametrize("scenario", [
        "clean_small", "messy_realistic", "priority_pressure", "transition_heavy",
        "locked_plant", "mid_replan",
    ])
    def test_grade_matches_outcomes(self, tmp_path, scenario):
        sub = tmp_path / "sub"
        generate(sub, scenario=scenario, seed=1)
        result = _run_gate(sub, tmp_path / "runs")
        outcomes = [RuleOutcome(v) for v in result.certificate["rule_outcomes"].values()]
        assert grade_from_outcomes(outcomes) == result.grade

    def test_clean_submission_has_no_warning_or_error_findings(self, tmp_path):
        """A clean submission carries zero WARNING/ERROR findings — the two
        spurious '100% resolved' warnings are gone (handoff §B3)."""
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=1)
        result = _run_gate(sub, tmp_path / "runs")
        sevs = {f["severity"] for f in result.certificate["findings"]}
        assert "warning" not in sevs and "error" not in sevs and "blocker" not in sevs


class TestSubmissionSpaceRefsReachable:
    """Handoff §B1: a gate finding names typed submission-space subjects
    (system='IDS'); the M1 adapter registers those refs, making the finding
    reachable by canonical key after a full run — and the IDS ref is a stable
    permanent identity for REJECTED submissions that never reach M1."""

    def test_reachable_by_canonical_key_after_full_run(self, tmp_path):
        sub = tmp_path / "sub"
        out = tmp_path / "out"
        # stale order stays canonical; its gate finding (backlog_is_current)
        # subjects the order_id.
        truth = generate(sub, scenario="clean_small", seed=5, anomalies=["stale_due_dates:2"])
        code = mre_main(["--submission", str(sub), "--out", str(out),
                         "--snapshot-id", "snap-reach", "--time-limit", "20"])
        assert code == 0

        idx = EvidenceIndex().build(out / "runs")
        stale_finding = next(
            f for f in idx.all_findings()
            if f.get("evidence", {}).get("rule_id") == "ids.backlog_is_current"
        )
        subj = stale_finding["subjects"][0]
        assert subj["system"] == "IDS"
        assert subj["entity_type"] == "order_id"
        ids_value = subj["entity_id"]

        # the gate finding is indexed under the submission-space id ...
        assert any(f["record_id"] == stale_finding["record_id"]
                   for f in idx.entity_records(ids_value))

        # ... and that id resolves to a real canonical demand via the identity
        # map the M1 adapter wrote (retroactive canonical reachability).
        store = SnapshotStore(out / "snapshots")
        reader = store.load_snapshot("snap-reach")
        identity_map = reader.read_identity_map()
        demand_id = identity_map.resolve("IDS", "order_id", ids_value)
        assert demand_id is not None
        assert reader.get_entity(demand_id) is not None

    def test_ids_ref_is_permanent_identity_for_rejected(self, tmp_path):
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=5, anomalies=["orphan_product_refs:80"])
        result = _run_gate(sub, tmp_path / "runs")
        assert result.grade == "REJECTED"
        # every finding's subjects are typed IDS-space refs (stable per source)
        for f in result.certificate["findings"]:
            for s in f["subjects"]:
                assert s["system"] == "IDS"
