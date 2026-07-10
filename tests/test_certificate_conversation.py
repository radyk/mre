"""Conversational Certificate: triage ordering, the three registers, and the
expected-remediation assertions on the generator scenarios (handoff §4, §5, §7).

Every CONDITIONAL/REJECTED scenario gains expected-remediation assertions: the
fix-first ordering obeys the grade-distance rule, and each finding's rendered
remediation cites its registry rule's IDS ref and invents no number. The two
canonical scenarios (messy_realistic, rejected) also pin an exact fix-first
rule_id list as a regression bar.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.ids_rules import RULE_REGISTRY, RuleId
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import ConformanceGate
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer
from mre.modules.remediation import build_remediation_items
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.renderers import TemplateRenderer
from mre.modules.triage import escape_distance, triage_findings
from mre.reporter import Reporter
from mre.catalog import load_catalog
from tools.generate_erp_dataset import SCENARIOS, generate

_OUTCOME_TIER = {"violated": 0, "degraded": 1, "flagged": 2}
NON_SLOW = [s for s in SCENARIOS if not SCENARIOS[s].get("slow")]
CATALOG = load_catalog()


def _gate(sub_dir: Path, runs_dir: Path):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="cert conversation test", config={},
        trigger="test", snapshot_id="pre-adapter", sink_dir=runs_dir,
    )
    result = ConformanceGate().run(sub_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


def _cert_findings(result) -> list[dict]:
    return [f for f in result.certificate["findings"]
            if "rule_id" in f.get("evidence", {}) and "outcome" in f["evidence"]]


# --------------------------------------------------------------------------
# §5 — expected-remediation over every non-ACCEPTED generator scenario
# --------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", NON_SLOW)
class TestExpectedRemediation:
    def test_triage_order_and_citations(self, tmp_path, scenario):
        sub = tmp_path / "sub"
        truth = generate(sub, scenario=scenario, seed=11)
        result = _gate(sub, tmp_path / "runs")
        if truth["expected_certificate_grade"] == "ACCEPTED":
            pytest.skip(f"{scenario} is ACCEPTED — no remediation to order")

        findings = _cert_findings(result)
        ordered = triage_findings(findings, CATALOG)
        assert ordered, f"{scenario}: non-ACCEPTED but no actionable findings"

        # Outcome tiers are monotonic (violated → degraded → flagged).
        tiers = [_OUTCOME_TIER[f["evidence"]["outcome"]] for f in ordered]
        assert tiers == sorted(tiers), f"{scenario}: tiers not monotonic: {tiers}"

        # Within the degraded band, escape distances are non-decreasing where
        # a rate distance exists (closest escape first).
        dists = [escape_distance(f, CATALOG) for f in ordered
                 if f["evidence"]["outcome"] == "degraded"]
        rate_dists = [d for d in dists if d is not None]
        assert rate_dists == sorted(rate_dists), f"{scenario}: degrade order wrong"

        # Every finding's rendered remediation cites its registry rule's IDS ref
        # and invents no number.
        for item in build_remediation_items(findings, CATALOG):
            spec = RULE_REGISTRY[RuleId(item.rule_id)]
            assert spec.ids_ref in item.text, (
                f"{scenario}: {item.rule_id} remediation omits IDS ref {spec.ids_ref}")
            assert not item.validate(), (
                f"{scenario}: {item.rule_id} remediation invented {item.validate()}")


class TestCanonicalFixFirstOrdering:
    """Regression pins: the exact fix-first rule_id list for the two canonical
    scenarios (deterministic by seed)."""

    def test_messy_realistic_conditional(self, tmp_path):
        sub = tmp_path / "sub"
        generate(sub, scenario="messy_realistic", seed=11)
        result = _gate(sub, tmp_path / "runs")
        order = [f["evidence"]["rule_id"] for f in triage_findings(_cert_findings(result))]
        assert order == [
            "ids.orders_resolve_to_products",
            "ids.order_identities_unique",
            "ids.orders_use_active_routes",
            "ids.backlog_is_current",
            "ids.due_dates_within_planning_horizon",
        ]

    def test_rejected_orders_violated_first(self, tmp_path):
        sub = tmp_path / "sub"
        generate(sub, scenario="rejected", seed=1)
        result = _gate(sub, tmp_path / "runs")
        assert result.grade == "REJECTED"
        order = [f["evidence"]["rule_id"] for f in triage_findings(_cert_findings(result))]
        assert order == [
            "ids.calendar_patterns_exist",
            "ids.submission_files_present",
        ]


# --------------------------------------------------------------------------
# §4/§7 — the three registers route and answer through the explainer
# --------------------------------------------------------------------------

class TestThreeRegistersRoute:
    def _explainer(self, tmp_path, scenario, seed=11, snap="snap-cert"):
        sub = tmp_path / "sub"
        out = tmp_path / "out"
        generate(sub, scenario=scenario, seed=seed)
        code = mre_main(["--submission", str(sub), "--out", str(out),
                         "--snapshot-id", snap, "--time-limit", "20"])
        idx = EvidenceIndex.load(out / "evidence_index.json")
        store = SnapshotStore(out / "snapshots")
        return Explainer(store, idx, snapshot_id=snap), code

    def test_conditional_three_questions(self, tmp_path):
        ex, code = self._explainer(tmp_path, "messy_realistic")
        assert code == 0
        r = TemplateRenderer()

        testimony = r.render(ex.answer("what's wrong?"))
        assert "register: testimony" in testimony

        remediation = r.render(ex.answer("how do I fix the worst one?"))
        assert "register: remediation" in remediation
        assert "catalog note v1" in remediation
        assert "§" in remediation  # cites an IDS section

        judgment = r.render(ex.answer("what should I fix first?"))
        assert "register: judgment" in judgment
        assert "Fix-first order" in judgment
        # names the arithmetic
        assert "needs 97%" in judgment or "count-based degrade" in judgment

    def test_rejected_certificate_only_mode(self, tmp_path):
        """A REJECTED submission has no snapshot; the three certificate
        questions still answer off the gate findings with IDS-space identity."""
        sub = tmp_path / "sub"
        out = tmp_path / "out"
        generate(sub, scenario="rejected", seed=1)
        code = mre_main(["--submission", str(sub), "--out", str(out),
                         "--snapshot-id", "snap-rej"])
        assert code == 1
        assert not (out / "snapshots" / "snap-rej").exists()
        assert (out / "evidence_index.json").exists()

        idx = EvidenceIndex.load(out / "evidence_index.json")
        store = SnapshotStore(out / "snapshots")
        ex = Explainer(store, idx, snapshot_id="snap-rej")  # certificate-only
        assert ex._identity_map is None
        r = TemplateRenderer()

        assert "register: remediation" in r.render(ex.answer("how do I fix this?"))
        judgment = r.render(ex.answer("what should I fix first?"))
        assert "register: judgment" in judgment
        assert "violated" in judgment
        assert "register: testimony" in r.render(ex.answer("why was it rejected?"))
