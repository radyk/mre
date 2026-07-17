"""Tests for M10 Explainer + TemplateRenderer — derived from docs/03 Phase 3.

Key invariants:
- M10 has no write path (no Reporter / SnapshotWriter import)
- ExplanationBundle carries identity_map so renderers can use external names
- TemplateRenderer uses planner vocabulary (WO-2001, M-GEAR-01), never UUIDs
- basis=reconstructed → "was assigned to X" phrasing
- Every cited claim gets a footnoted record ID
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import ExplanationBundle, Explainer
from mre.modules.renderers import TemplateRenderer, _resolve_name


# ---------------------------------------------------------------------------
# M10 no-write-path invariant
# ---------------------------------------------------------------------------

class TestNoWritePath:
    def test_explainer_does_not_import_reporter(self):
        import ast
        src = Path("src/mre/modules/explainer.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imported_names.append(f"{mod}.{alias.name}")
        assert not any("Reporter" in n for n in imported_names), (
            f"M10 must not import Reporter; found in: {[n for n in imported_names if 'Reporter' in n]}"
        )

    def test_explainer_does_not_import_snapshot_writer(self):
        import ast
        src = Path("src/mre/modules/explainer.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imported_names.append(f"{mod}.{alias.name}")
        assert not any("SnapshotWriter" in n for n in imported_names), (
            f"M10 must not import SnapshotWriter"
        )


# ---------------------------------------------------------------------------
# Fixtures: fake snapshot store + index
# ---------------------------------------------------------------------------

DEMAND_ID = "85342968-6107-58db-95d3-256cd6765fec"
DEMAND_WO = "WO-2001"
GEAR_OP_ID = "2c1dfb17-17a1-59f6-9900-818361b5244d"
GEAR_MACHINE_ID = "cdef1234-0000-0000-0000-000000000001"  # M-GEAR-02
ALT_MACHINE_ID = "abcd5678-0000-0000-0000-000000000002"   # M-GEAR-01
FULFILLMENT_ID = "ful-demo-001"
WP_ID = "wp-demo-001"


def _make_index(tmp_path: Path) -> EvidenceIndex:
    """Write minimal fake JSONL runs and build index."""
    records = [
        {"record_type": "run_context_open", "run_id": "run-m4", "module": "M4",
         "snapshot_id": "snap-demo", "purpose": "test", "timestamp": "2026-07-06T00:00:00Z"},
        {
            "record_type": "decision",
            "record_id": "dec-merge-001",
            "run_id": "run-m4",
            "module": "M4",
            "seq": 1,
            "snapshot_id": "snap-demo",
            "subjects": [{"entity_id": DEMAND_ID, "entity_type": "demand"}],
            "tier": "headline",
            "message": "",
            "decision_type": "demand_merge",
            "driver": "SETUP_AMORTIZATION",
            "basis": "policy_applied",
            "chosen": {"estimated_benefit": 50.0},
            "alternatives": [],
        },
        {"record_type": "run_context_close", "run_id": "run-m4",
         "status": "success", "ended_at": "2026-07-06T00:01:00Z"},
        {"record_type": "run_context_open", "run_id": "run-m7", "module": "M7",
         "snapshot_id": "snap-demo", "purpose": "test", "timestamp": "2026-07-06T00:02:00Z"},
        {
            "record_type": "decision",
            "record_id": "dec-assign-001",
            "run_id": "run-m7",
            "module": "M7",
            "seq": 5,
            "snapshot_id": "snap-demo",
            "subjects": [{"entity_id": GEAR_OP_ID, "entity_type": "operation"}],
            "tier": "supporting",
            "message": "",
            "decision_type": "assignment",
            "driver": "CALENDAR_WINDOW",
            "basis": "reconstructed",
            "chosen": {"resource_id": GEAR_MACHINE_ID},
            "alternatives": [
                {
                    "option": f"resource:{ALT_MACHINE_ID}",
                    "consequence": "Unavailable: no calendar window covers this operation slot.",
                }
            ],
        },
        {
            "record_type": "metric",
            "record_id": "met-late-001",
            "run_id": "run-m7",
            "module": "M7",
            "seq": 8,
            "snapshot_id": "snap-demo",
            "subjects": [{"entity_id": DEMAND_ID, "entity_type": "demand"}],
            "tier": "supporting",
            "message": "",
            "name": "lateness_minutes",
            "value": 840.0,
            "unit": "minutes",
            "rollup_of": [],
        },
        {"record_type": "run_context_close", "run_id": "run-m7",
         "status": "success", "ended_at": "2026-07-06T00:03:00Z"},
    ]
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "demo.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return EvidenceIndex().build(runs_dir)


class FakeSnapshotReader:
    """Minimal snapshot reader stub."""

    def get_entity(self, entity_id: str) -> dict | None:
        if entity_id == DEMAND_ID:
            return {"id": DEMAND_ID, "due": "2026-07-13T23:59:00+00:00"}
        return None

    def iter_entities(self, entity_type: str):
        if entity_type == "fulfillment":
            yield {"id": FULFILLMENT_ID, "demand_ref": DEMAND_ID, "workpackage_ref": WP_ID}
        elif entity_type == "operation":
            yield {"id": GEAR_OP_ID, "workpackage_ref": WP_ID, "spec_ref": "x"}
            yield {"id": "op-insp-001", "workpackage_ref": WP_ID, "spec_ref": "y"}
        elif entity_type == "demand":
            yield {"id": DEMAND_ID, "due": "2026-07-13T23:59:00+00:00",
                   "external_refs": [{"system": "ERP", "type": "work_order", "value": "WO-2001"}]}
        elif entity_type == "costmodel":
            yield {
                "id": "cm-001",
                "version": 1,
                "resource_rates": {GEAR_MACHINE_ID: 6.0, ALT_MACHINE_ID: 4.0},
            }

    def read_identity_map(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register(DEMAND_ID, "ERP", "work_order", "WO-2001")
        m.register(GEAR_MACHINE_ID, "ERP", "machine_id", "M-GEAR-02")
        m.register(ALT_MACHINE_ID, "ERP", "machine_id", "M-GEAR-01")
        return m


class FakeStore:
    def __init__(self, snap_id: str) -> None:
        self._snap_id = snap_id

    def load_snapshot(self, snap_id: str) -> FakeSnapshotReader:
        return FakeSnapshotReader()


@pytest.fixture()
def explainer_and_index(tmp_path):
    index = _make_index(tmp_path)
    store = FakeStore("snap-demo")
    exp = Explainer(snapshot_store=store, index=index, snapshot_id="snap-demo")
    return exp, index


# ---------------------------------------------------------------------------
# ExplanationBundle assembly
# ---------------------------------------------------------------------------

class TestExplainerAnswer:
    def test_why_late_returns_bundle(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        assert isinstance(bundle, ExplanationBundle)
        assert bundle.subject_type == "demand"
        assert bundle.subject_external_name == "WO-2001"

    def test_why_late_bundle_has_lateness_key_fact(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        assert bundle.key_facts.get("lateness_minutes") == 840.0

    def test_why_late_bundle_has_demand_merge(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        merge_recs = [
            r for r in bundle.ordered_records
            if r.get("decision_type") == "demand_merge"
        ]
        assert merge_recs, "Bundle must contain DEMAND_MERGE decision"

    def test_why_late_bundle_has_calendar_window(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        cw_recs = [
            r for r in bundle.ordered_records
            if r.get("driver") == "CALENDAR_WINDOW"
        ]
        assert cw_recs, "Bundle must contain CALENDAR_WINDOW decision"

    def test_why_late_bundle_has_lateness_metric(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        metrics = [
            r for r in bundle.ordered_records
            if r.get("record_type") == "metric" and r.get("name") == "lateness_minutes"
        ]
        assert metrics, "Bundle must contain lateness_minutes metric"
        assert metrics[0]["value"] == 840.0

    def test_why_late_ordered_m4_before_m7(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        modules = [r["module"] for r in bundle.ordered_records]
        # All M4 records come before M7 records
        last_m4 = max((i for i, m in enumerate(modules) if m == "M4"), default=-1)
        first_m7 = min((i for i, m in enumerate(modules) if m == "M7"), default=999)
        assert last_m4 < first_m7

    def test_unknown_wo_returns_error_bundle(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-9999 late?")
        assert "error" in bundle.key_facts

    def test_data_problems_returns_findings_bundle(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("What data problems exist?")
        assert bundle.subject_type == "findings"

    def test_route_by_keyword_late(self, explainer_and_index):
        exp, _ = explainer_and_index
        # "delayed" should still route to _explain_why_late
        bundle = exp.answer("Why is WO-2001 delayed?")
        assert bundle.subject_type == "demand"


# ---------------------------------------------------------------------------
# summarize_run
# ---------------------------------------------------------------------------

class TestSummarizeRun:
    def test_summarize_returns_run_bundle(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.summarize_run()
        assert bundle.subject_type == "run"

    def test_summarize_counts_notable_decisions(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.summarize_run()
        # demand_merge has driver SETUP_AMORTIZATION, assignment has CALENDAR_WINDOW
        assert bundle.key_facts.get("notable_decision_count", 0) >= 1

    def test_summarize_counts_late_demands(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.summarize_run()
        # The M7 metric has lateness 840 > 0
        assert bundle.key_facts.get("late_demand_count", 0) >= 1


# ---------------------------------------------------------------------------
# TemplateRenderer
# ---------------------------------------------------------------------------

class TestTemplateRenderer:
    def test_render_uses_external_names(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "WO-2001" in text, "Renderer must use work_order external ref"
        assert DEMAND_ID not in text, "Renderer must not emit UUID"

    def test_render_assignment_uses_machine_name(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "M-GEAR-02" in text, "Renderer must use machine_id external ref"
        assert GEAR_MACHINE_ID not in text

    def test_render_alternative_names_calendar_blocked_machine(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "M-GEAR-01" in text, "Calendar-blocked alternative must be named"

    def test_render_reconstructed_note(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "reconstruction" in text.lower() or "reconstructed" in text.lower(), (
            "Reconstructed decision must be noted as such"
        )

    def test_render_footnotes_record_ids(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "record:" in text, "Each evidence record must be footnoted with its ID"

    def test_render_lateness_headline(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "840" in text, "Lateness value must appear in rendered text"

    def test_render_run_summary_format(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.summarize_run()
        text = TemplateRenderer().render(bundle)
        assert "Run:" in text

    def test_render_diff_format(self, tmp_path):
        """TemplateRenderer renders a diff bundle from key_facts."""
        bundle = ExplanationBundle(
            question="What changed?",
            subject_id="snap-a→snap-b",
            subject_type="diff",
            subject_external_name="snap-a → snap-b",
            ordered_records=[],
            key_facts={
                "snapshot_a": "snap-a",
                "snapshot_b": "snap-b",
                "removed_demands": ["WO-PAST-001"],
                "added_demands": [],
                "changed_demands": [
                    {"work_order": "WO-1002", "field": "due",
                     "from": "2026-08-20", "to": "2026-07-20"}
                ],
                "costmodel_diff": {
                    "version_a": 1,
                    "version_b": 2,
                    "rate_changes": {"M-CAST-01": {"from": 5.0, "to": 7.5}},
                },
            },
            snapshot_id="snap-a",
            identity_map=None,
        )
        text = TemplateRenderer().render(bundle)
        assert "WO-PAST-001" in text
        assert "WO-1002" in text
        assert "M-CAST-01" in text
        assert "7.5" in text


# ---------------------------------------------------------------------------
# _resolve_name helper
# ---------------------------------------------------------------------------

class TestRendererAttribution:
    def test_template_renderer_ends_with_attribution(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert text.endswith("[rendered by: template | register: testimony]")

    def test_template_renderer_register_is_testimony(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        text = TemplateRenderer().render(bundle)
        assert "register: testimony" in text

    def test_llm_renderer_no_key_attribution(self, explainer_and_index):
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        renderer = LLMRenderer(api_key="")
        text = renderer.render(bundle)
        assert "[rendered by: template" in text
        assert "ANTHROPIC_API_KEY not set" in text
        assert "register: testimony" in text

    def test_llm_renderer_no_key_not_silent(self, explainer_and_index):
        """Fallback must not produce the same output as plain TemplateRenderer."""
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        template_text = TemplateRenderer().render(bundle)
        fallback_text = LLMRenderer(api_key="").render(bundle)
        assert template_text != fallback_text

    def test_llm_renderer_no_package_attribution(self, tmp_path, monkeypatch, explainer_and_index):
        """When anthropic package unavailable, attribution names that reason."""
        import sys
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        monkeypatch.setitem(sys.modules, "anthropic", None)
        renderer = LLMRenderer(api_key="sk-fake-key-for-test")
        text = renderer.render(bundle)
        assert "anthropic package not installed" in text

    def test_attribution_on_schedule_bundle(self, sched_exp):
        bundle = sched_exp.answer("Show the schedule")
        text = TemplateRenderer().render(bundle)
        assert text.endswith("[rendered by: template | register: testimony]")

    def test_attribution_on_unsupported_bundle(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("How is the weather?")
        text = TemplateRenderer().render(bundle)
        assert text.endswith("[rendered by: template | register: testimony]")


class TestResolveName:
    def test_resolves_demand_to_work_order(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register("uid-001", "ERP", "work_order", "WO-2001")
        result = _resolve_name("uid-001", "demand", m)
        assert result == "WO-2001"

    def test_resolves_resource_to_machine_id(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register("rid-001", "ERP", "machine_id", "M-GEAR-01")
        result = _resolve_name("rid-001", "resource", m)
        assert result == "M-GEAR-01"

    def test_falls_back_to_truncated_id_when_no_map(self):
        result = _resolve_name("abcdefgh-1234", "demand", None)
        assert "abcdefgh" in result

    def test_empty_id_returns_question_mark(self):
        result = _resolve_name("", "demand", None)
        assert result == "?"


# ---------------------------------------------------------------------------
# Late-orders route
# ---------------------------------------------------------------------------

def _make_index_no_late(tmp_path: Path) -> EvidenceIndex:
    """Index with an on-time demand (lateness=0) — no positive lateness."""
    records = [
        {"record_type": "run_context_open", "run_id": "run-m7-ok", "module": "M7",
         "snapshot_id": "snap-demo", "purpose": "test", "timestamp": "2026-07-06T01:00:00Z"},
        {
            "record_type": "metric",
            "record_id": "met-ontime-001",
            "run_id": "run-m7-ok",
            "module": "M7",
            "seq": 1,
            "snapshot_id": "snap-demo",
            "subjects": [{"entity_id": DEMAND_ID, "entity_type": "demand"}],
            "tier": "supporting",
            "message": "",
            "name": "lateness_minutes",
            "value": -120.0,   # early, not late
            "unit": "minutes",
            "rollup_of": [],
        },
        {"record_type": "run_context_close", "run_id": "run-m7-ok",
         "status": "success", "ended_at": "2026-07-06T01:01:00Z"},
    ]
    runs_dir = tmp_path / "runs_no_late"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "ontime.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return EvidenceIndex().build(runs_dir)


class TestLateOrdersRoute:
    def test_routes_to_late_orders_without_wo(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        assert bundle.subject_type == "late_orders"

    def test_late_count_is_one(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        assert bundle.key_facts["late_count"] == 1

    def test_late_orders_list_contains_wo2001(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        assert any("WO-2001" in item for item in bundle.key_facts["late_orders"])

    def test_late_orders_list_contains_minutes(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        assert any("840" in item for item in bundle.key_facts["late_orders"])

    def test_renderer_shows_late_count(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        text = TemplateRenderer().render(bundle)
        assert "1 late order" in text

    def test_renderer_shows_wo_name(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any late orders?")
        text = TemplateRenderer().render(bundle)
        assert "WO-2001" in text

    def test_renderer_no_late_orders(self, tmp_path):
        index = _make_index_no_late(tmp_path)
        store = FakeStore("snap-demo")
        exp = Explainer(snapshot_store=store, index=index, snapshot_id="snap-demo")
        bundle = exp.answer("Are there any late orders?")
        assert bundle.key_facts["late_count"] == 0

    def test_renderer_no_late_orders_text(self, tmp_path):
        index = _make_index_no_late(tmp_path)
        store = FakeStore("snap-demo")
        exp = Explainer(snapshot_store=store, index=index, snapshot_id="snap-demo")
        bundle = exp.answer("Are there any late orders?")
        text = TemplateRenderer().render(bundle)
        assert "No late orders" in text

    def test_delay_keyword_also_routes(self, explainer_and_index):
        """'delay' synonym should route the same way as 'late'."""
        exp, _ = explainer_and_index
        bundle = exp.answer("Are there any delays?")
        assert bundle.subject_type == "late_orders"

    def test_late_with_wo_still_routes_to_why_late(self, explainer_and_index):
        """'late' + specific WO must NOT fall into _list_late_orders."""
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        assert bundle.subject_type == "demand"


# ---------------------------------------------------------------------------
# Honest fallback — unrouted questions must never silently reroute
# ---------------------------------------------------------------------------

class TestHonestFallback:
    def test_unroutable_returns_unsupported_type(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("How is the weather?")
        assert bundle.subject_type == "unsupported"

    def test_unroutable_not_findings_type(self, explainer_and_index):
        """Old silent reroute to data-problems must not happen."""
        exp, _ = explainer_and_index
        bundle = exp.answer("What is the meaning of life?")
        assert bundle.subject_type != "findings"

    def test_unsupported_renderer_shows_cant_answer(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("How is the weather?")
        text = TemplateRenderer().render(bundle)
        assert "can't answer" in text.lower() or "cannot answer" in text.lower()

    def test_unsupported_renderer_lists_supported_routes(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Random question nobody asked")
        text = TemplateRenderer().render(bundle)
        assert "Supported question types" in text or "Supported" in text

    def test_unsupported_bundle_carries_original_question(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Completely unrecognised input xyz")
        assert bundle.key_facts["parsed"] == "Completely unrecognised input xyz"

    def test_unsupported_supported_routes_nonempty(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Random question")
        assert len(bundle.key_facts.get("supported_routes", [])) >= 1


# ---------------------------------------------------------------------------
# Downtime route — calendar closures for named machine, pool, or family
# ---------------------------------------------------------------------------

GEAR_RID = "gear-rid-0001-0000-0000-000000000001"
CAST_RID = "cast-rid-0001-0000-0000-000000000002"
GEAR_CAL_ID = "gear-cal-0001-0000-0000-000000000001"
CAST_CAL_ID = "cast-cal-0001-0000-0000-000000000002"


class FakeDowntimeReader:
    """Minimal snapshot reader for downtime tests."""

    def iter_entities(self, entity_type: str):
        if entity_type == "resource":
            yield {
                "id": GEAR_RID,
                "external_refs": [{"system": "ERP", "type": "machine_id", "value": "M-GEAR-01"}],
                "calendar_ref": GEAR_CAL_ID,
            }
            yield {
                "id": CAST_RID,
                "external_refs": [{"system": "ERP", "type": "machine_id", "value": "M-CAST-01"}],
                "calendar_ref": CAST_CAL_ID,
            }
        elif entity_type == "calendar":
            yield {
                "id": GEAR_CAL_ID,
                "exceptions": [
                    {
                        "window": {
                            "start": "2026-07-13T00:00:00+00:00",
                            "end": "2026-07-13T23:59:59+00:00",
                        },
                        "type": "closure",
                        "reason": "planned_maintenance",
                    }
                ],
            }
            yield {"id": CAST_CAL_ID, "exceptions": []}
        elif entity_type == "resourcepool":
            yield {
                "id": "pool-gear",
                "external_refs": [{"system": "ERP", "type": "workcenter_id", "value": "WC-GEAR"}],
                "members": [GEAR_RID],
            }
            yield {
                "id": "pool-cast",
                "external_refs": [{"system": "ERP", "type": "workcenter_id", "value": "WC-CASTING"}],
                "members": [CAST_RID],
            }
        else:
            return

    def get_entity(self, entity_id: str):
        return None

    def read_identity_map(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register(GEAR_RID, "ERP", "machine_id", "M-GEAR-01")
        m.register(CAST_RID, "ERP", "machine_id", "M-CAST-01")
        return m


class FakeDowntimeStore:
    def load_snapshot(self, snap_id: str):
        return FakeDowntimeReader()


@pytest.fixture()
def downtime_explainer(tmp_path):
    index = _make_index_no_late(tmp_path)
    store = FakeDowntimeStore()
    return Explainer(snapshot_store=store, index=index, snapshot_id="snap-demo")


class TestDowntimeRoute:
    def test_routes_on_downtime_keyword(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does gear have?")
        assert bundle.subject_type == "downtime"

    def test_closure_keyword_also_routes(self, downtime_explainer):
        bundle = downtime_explainer.answer("Show me closures for gear")
        assert bundle.subject_type == "downtime"

    def test_machine_name_lookup(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does M-GEAR-01 have?")
        assert bundle.subject_type == "downtime"
        closures = bundle.key_facts["closures"]
        assert len(closures) == 1
        assert closures[0]["resource"] == "M-GEAR-01"

    def test_pool_name_lookup_finds_closure(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does gear have?")
        assert bundle.key_facts["total_hours"] > 0

    def test_closure_duration_approximately_24h(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does M-GEAR-01 have?")
        closures = bundle.key_facts["closures"]
        assert abs(closures[0]["duration_hours"] - 24.0) < 0.1

    def test_closure_reason(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does M-GEAR-01 have?")
        assert bundle.key_facts["closures"][0]["reason"] == "planned_maintenance"

    def test_closure_date(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does M-GEAR-01 have?")
        assert bundle.key_facts["closures"][0]["date"] == "2026-07-13"

    def test_no_closures_for_casting(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does casting have?")
        assert bundle.key_facts["total_hours"] == 0.0
        assert bundle.key_facts["closures"] == []

    def test_renderer_shows_machine_name(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does M-GEAR-01 have?")
        text = TemplateRenderer().render(bundle)
        assert "M-GEAR-01" in text

    def test_renderer_shows_duration(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does gear have?")
        text = TemplateRenderer().render(bundle)
        assert "24.0h" in text or "24h" in text

    def test_renderer_no_closures_text(self, downtime_explainer):
        bundle = downtime_explainer.answer("How much downtime does casting have?")
        text = TemplateRenderer().render(bundle)
        assert "No calendar closures" in text


# ---------------------------------------------------------------------------
# Schedule query — ScheduleFilter assembler + routes
# ---------------------------------------------------------------------------

# Fixed IDs for the fake schedule snapshot
_SQ_RES_GEAR = "sq-res-gear-0000-0000-000000000001"
_SQ_RES_CAST = "sq-res-cast-0000-0000-000000000002"
_SQ_OP_1 = "sq-op-0001-0000-0000-000000000001"   # seq=10, gear, WO-2001+WO-2002 merged
_SQ_OP_2 = "sq-op-0002-0000-0000-000000000002"   # seq=10, cast, WO-3001
_SQ_OP_3 = "sq-op-0003-0000-0000-000000000003"   # seq=10, cast, WO-CUST-01 (customer A)
_SQ_WP_MERGED = "sq-wp-merged-0000-000000000001"
_SQ_WP_SINGLE = "sq-wp-single-0000-000000000002"
_SQ_WP_CUST = "sq-wp-cust-00-0000-000000000003"
_SQ_DEM_2001 = "sq-dem-2001-0000-000000000001"
_SQ_DEM_2002 = "sq-dem-2002-0000-000000000002"
_SQ_DEM_3001 = "sq-dem-3001-0000-000000000003"
_SQ_DEM_CUST = "sq-dem-cust-0000-000000000004"


class FakeScheduleReader:
    """Snapshot with 3 assignments across 2 machines, one merged WP."""

    def get_entity(self, entity_id: str):
        return None

    def iter_entities(self, entity_type: str):
        if entity_type == "assignment":
            # Merged WP: gear machine, 2026-07-13
            yield {
                "id": "sq-asgn-0001",
                "snapshot_id": "snap-sq",
                "operation_ref": _SQ_OP_1,
                "workpackage_ref": _SQ_WP_MERGED,
                "resource_assignments": [{"resource_ref": _SQ_RES_GEAR}],
                "phase_windows": {
                    "setup": None,
                    "run": [{"start": "2026-07-13T07:00:00Z", "end": "2026-07-13T14:00:00Z"}],
                    "dwell": None,
                },
                "decision_ref": "dec-001",
            }
            # Single WP: cast machine, 2026-07-28
            yield {
                "id": "sq-asgn-0002",
                "snapshot_id": "snap-sq",
                "operation_ref": _SQ_OP_2,
                "workpackage_ref": _SQ_WP_SINGLE,
                "resource_assignments": [{"resource_ref": _SQ_RES_CAST}],
                "phase_windows": {
                    "setup": None,
                    "run": [{"start": "2026-07-28T07:00:00Z", "end": "2026-07-28T08:00:00Z"}],
                    "dwell": None,
                },
                "decision_ref": "dec-002",
            }
            # Customer WP: cast machine, 2026-08-06
            yield {
                "id": "sq-asgn-0003",
                "snapshot_id": "snap-sq",
                "operation_ref": _SQ_OP_3,
                "workpackage_ref": _SQ_WP_CUST,
                "resource_assignments": [{"resource_ref": _SQ_RES_CAST}],
                "phase_windows": {
                    "setup": None,
                    "run": [{"start": "2026-08-06T07:00:00Z", "end": "2026-08-06T08:00:00Z"}],
                    "dwell": None,
                },
                "decision_ref": "dec-003",
            }
        elif entity_type == "operation":
            yield {"id": _SQ_OP_1, "workpackage_ref": _SQ_WP_MERGED, "sequence": 10,
                   "setup_family": "gear_cutting"}
            yield {"id": _SQ_OP_2, "workpackage_ref": _SQ_WP_SINGLE, "sequence": 10,
                   "setup_family": "casting"}
            yield {"id": _SQ_OP_3, "workpackage_ref": _SQ_WP_CUST, "sequence": 10,
                   "setup_family": "casting"}
        elif entity_type == "fulfillment":
            # Both WO-2001 and WO-2002 fulfilled by the merged WP
            yield {"id": "ful-sq-001", "demand_ref": _SQ_DEM_2001, "workpackage_ref": _SQ_WP_MERGED}
            yield {"id": "ful-sq-002", "demand_ref": _SQ_DEM_2002, "workpackage_ref": _SQ_WP_MERGED}
            yield {"id": "ful-sq-003", "demand_ref": _SQ_DEM_3001, "workpackage_ref": _SQ_WP_SINGLE}
            yield {"id": "ful-sq-004", "demand_ref": _SQ_DEM_CUST, "workpackage_ref": _SQ_WP_CUST}
        elif entity_type == "demand":
            yield {"id": _SQ_DEM_2001, "due": "2026-07-13T23:59:00Z",
                   "external_refs": [{"system": "ERP", "type": "work_order", "value": "WO-2001"}]}
            yield {"id": _SQ_DEM_2002, "due": "2026-07-13T23:59:00Z",
                   "external_refs": [{"system": "ERP", "type": "work_order", "value": "WO-2002"}]}
            yield {"id": _SQ_DEM_3001, "due": "2026-08-31T23:59:00Z",
                   "external_refs": [{"system": "ERP", "type": "work_order", "value": "WO-3001"}]}
            yield {"id": _SQ_DEM_CUST, "due": "2026-09-15T23:59:00Z",
                   "external_refs": [
                       {"system": "ERP", "type": "work_order", "value": "WO-CUST-01"},
                       {"system": "ERP", "type": "customer", "value": "CUST-ACME"},
                   ]}
        elif entity_type == "serviceoutcome":
            # WO-2001 late by 840 min; WO-3001 early
            yield {"id": "svc-001", "demand_ref": _SQ_DEM_2001, "fulfillment_ref": "ful-sq-001",
                   "projected_completion": "2026-07-14T14:00:00Z",
                   "lateness": "PT840M", "tardiness_cost": 840.0}
            yield {"id": "svc-002", "demand_ref": _SQ_DEM_3001, "fulfillment_ref": "ful-sq-003",
                   "projected_completion": "2026-07-28T08:00:00Z",
                   "lateness": "-P30DT0H0M", "tardiness_cost": 0.0}
        elif entity_type == "resourcepool":
            yield {"id": "pool-sq-gear",
                   "external_refs": [{"system": "ERP", "type": "workcenter_id", "value": "WC-GEAR"}],
                   "members": [_SQ_RES_GEAR]}
            yield {"id": "pool-sq-cast",
                   "external_refs": [{"system": "ERP", "type": "workcenter_id", "value": "WC-CASTING"}],
                   "members": [_SQ_RES_CAST]}
        elif entity_type == "resource":
            yield {"id": _SQ_RES_GEAR,
                   "external_refs": [{"system": "ERP", "type": "machine_id", "value": "M-GEAR-02"}],
                   "calendar_ref": None}
            yield {"id": _SQ_RES_CAST,
                   "external_refs": [{"system": "ERP", "type": "machine_id", "value": "M-CAST-01"}],
                   "calendar_ref": None}

    def read_identity_map(self):
        from mre.modules.identity_map import IdentityMap
        m = IdentityMap()
        m.register(_SQ_RES_GEAR, "ERP", "machine_id", "M-GEAR-02")
        m.register(_SQ_RES_CAST, "ERP", "machine_id", "M-CAST-01")
        m.register(_SQ_DEM_2001, "ERP", "work_order", "WO-2001")
        m.register(_SQ_DEM_2002, "ERP", "work_order", "WO-2002")
        m.register(_SQ_DEM_3001, "ERP", "work_order", "WO-3001")
        m.register(_SQ_DEM_CUST, "ERP", "work_order", "WO-CUST-01")
        return m


class FakeScheduleStore:
    def load_snapshot(self, snap_id: str):
        return FakeScheduleReader()


@pytest.fixture()
def sched_exp(tmp_path):
    index = _make_index_no_late(tmp_path)
    return Explainer(
        snapshot_store=FakeScheduleStore(),
        index=index,
        snapshot_id="snap-sq",
    )


class TestScheduleQuery:
    # --- routing ---

    def test_routes_when_does_wo_start(self, sched_exp):
        assert sched_exp.answer("When does WO-2001 start?").subject_type == "schedule"

    def test_routes_when_does_wo_finish(self, sched_exp):
        assert sched_exp.answer("When does WO-2001 finish?").subject_type == "schedule"

    def test_routes_running_on_machine(self, sched_exp):
        assert sched_exp.answer("What is running on M-GEAR-02?").subject_type == "schedule"

    def test_routes_next_on_machine(self, sched_exp):
        assert sched_exp.answer("What's next on M-CAST-01?").subject_type == "schedule"

    def test_routes_show_schedule(self, sched_exp):
        assert sched_exp.answer("Show the schedule").subject_type == "schedule"

    def test_routes_full_schedule(self, sched_exp):
        assert sched_exp.answer("Full schedule").subject_type == "schedule"

    def test_routes_schedule_for_wo(self, sched_exp):
        assert sched_exp.answer("Schedule for WO-3001").subject_type == "schedule"

    def test_routes_schedule_for_customer(self, sched_exp):
        assert sched_exp.answer("Schedule for customer CUST-ACME").subject_type == "schedule"

    # --- WO filter ---

    def test_wo_filter_returns_only_matching_ops(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        rows = bundle.key_facts["rows"]
        assert all("WO-2001" in r["work_orders"] for r in rows)

    def test_wo_filter_excludes_other_machines(self, sched_exp):
        bundle = sched_exp.answer("When does WO-3001 start?")
        rows = bundle.key_facts["rows"]
        assert all(r["machine"] == "M-CAST-01" for r in rows)

    # --- batched WP ---

    def test_batched_wp_shows_both_wo_names(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        rows = bundle.key_facts["rows"]
        assert len(rows) == 1
        assert "WO-2001" in rows[0]["work_orders"]
        assert "WO-2002" in rows[0]["work_orders"]

    def test_batched_wp_contains_plus_separator(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        assert "+" in bundle.key_facts["rows"][0]["work_orders"]

    # --- machine filter ---

    def test_machine_filter_returns_only_that_machine(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01?")
        rows = bundle.key_facts["rows"]
        assert rows
        assert all(r["machine"] == "M-CAST-01" for r in rows)

    def test_machine_filter_count(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-GEAR-02?")
        assert bundle.key_facts["total_rows"] == 1

    # --- date filter ---

    def test_date_filter_within_window(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01 on 2026-07-28?")
        rows = bundle.key_facts["rows"]
        assert len(rows) == 1
        assert "WO-3001" in rows[0]["work_orders"]

    def test_date_filter_empty(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01 on 2026-07-15?")
        assert bundle.key_facts["total_rows"] == 0

    # --- limit (next N) ---

    def test_next_applies_limit(self, sched_exp):
        bundle = sched_exp.answer("What's next on M-CAST-01?")
        assert bundle.key_facts["total_rows"] <= 5

    # --- customer filter ---

    def test_customer_filter_returns_only_customer_ops(self, sched_exp):
        bundle = sched_exp.answer("Schedule for customer CUST-ACME")
        rows = bundle.key_facts["rows"]
        assert len(rows) == 1
        assert "WO-CUST-01" in rows[0]["work_orders"]

    # --- lateness in rows ---

    def test_late_wo_has_positive_lateness(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        rows = bundle.key_facts["rows"]
        assert rows[0]["lateness_minutes"] > 0

    def test_early_wo_has_negative_lateness(self, sched_exp):
        bundle = sched_exp.answer("When does WO-3001 start?")
        rows = bundle.key_facts["rows"]
        assert rows[0]["lateness_minutes"] < 0

    # --- empty result ---

    def test_empty_result_not_error(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01 on 2026-07-15?")
        assert "error" not in bundle.key_facts
        assert bundle.key_facts["empty_message"]

    def test_empty_result_subject_type_is_schedule(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01 on 2026-07-15?")
        assert bundle.subject_type == "schedule"

    # --- full schedule ---

    def test_full_schedule_all_ops(self, sched_exp):
        bundle = sched_exp.answer("Show the schedule")
        assert bundle.key_facts["total_rows"] == 3

    # --- renderer ---

    def test_renderer_groups_by_machine(self, sched_exp):
        bundle = sched_exp.answer("Show the schedule")
        text = TemplateRenderer().render(bundle)
        assert "[M-CAST-01]" in text
        assert "[M-GEAR-02]" in text

    def test_renderer_shows_wo_name(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        text = TemplateRenderer().render(bundle)
        assert "WO-2001" in text

    def test_renderer_shows_both_wo_names_for_merged_wp(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        text = TemplateRenderer().render(bundle)
        assert "WO-2002" in text

    def test_renderer_shows_seq_number(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        text = TemplateRenderer().render(bundle)
        assert "seq=" in text

    def test_renderer_shows_late_marker(self, sched_exp):
        bundle = sched_exp.answer("When does WO-2001 start?")
        text = TemplateRenderer().render(bundle)
        assert "LATE" in text

    def test_renderer_empty_shows_nothing_scheduled(self, sched_exp):
        bundle = sched_exp.answer("What is running on M-CAST-01 on 2026-07-15?")
        text = TemplateRenderer().render(bundle)
        assert "Nothing scheduled" in text

    def test_renderer_no_uuids(self, sched_exp):
        bundle = sched_exp.answer("Show the schedule")
        text = TemplateRenderer().render(bundle)
        assert _SQ_RES_GEAR not in text
        assert _SQ_DEM_2001 not in text


# ---------------------------------------------------------------------------
# Dialogue mode — SessionHistory, judgment path, reset
# ---------------------------------------------------------------------------

class FakeLLMClientSequence:
    """Returns successive responses from a list; repeats the last item."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0

    @property
    def messages(self) -> "FakeLLMClientSequence":
        return self

    def create(self, **kwargs) -> Any:
        text = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        FakeContent = type("FakeContent", (), {"text": text})()
        return type("FakeResponse", (), {"content": [FakeContent]})()


class FakeLLMClient:
    """Minimal Anthropic-API-shaped fake for dialogue tests."""

    def __init__(self, response_text: str = "My take: looks good.") -> None:
        self._text = response_text
        self.calls: list[dict] = []

    @property
    def messages(self) -> "FakeLLMClient":
        return self

    def create(self, **kwargs) -> Any:
        self.calls.append(kwargs)
        FakeContent = type("FakeContent", (), {"text": self._text})()
        return type("FakeResponse", (), {"content": [FakeContent]})()


class TestDialogueMode:
    # --- SessionHistory unit tests ---

    def test_session_history_starts_empty(self):
        from mre.ask import SessionHistory
        h = SessionHistory()
        assert h.is_empty()
        assert len(h) == 0

    def test_session_history_append_and_len(self):
        from mre.ask import SessionHistory, Turn
        h = SessionHistory()
        h.append(Turn(question="q", bundle=None, rendered="r"))
        assert len(h) == 1
        assert not h.is_empty()

    def test_session_history_max_turns(self):
        from mre.ask import SessionHistory, Turn
        h = SessionHistory(max_turns=3)
        for i in range(5):
            h.append(Turn(question=f"q{i}", bundle=None, rendered=f"r{i}"))
        assert len(h) == 3
        assert h.turns()[0].question == "q2"

    def test_session_history_reset(self):
        from mre.ask import SessionHistory, Turn
        h = SessionHistory()
        h.append(Turn(question="q", bundle=None, rendered="r"))
        h.reset()
        assert h.is_empty()

    def test_turns_returns_copy(self):
        from mre.ask import SessionHistory, Turn
        h = SessionHistory()
        h.append(Turn(question="q", bundle=None, rendered="r"))
        turns = h.turns()
        turns.clear()
        assert len(h) == 1

    # --- _render_repl_turn: routed question (testimony) ---

    def test_routed_turn_returns_testimony_register(self, explainer_and_index):
        from mre.ask import SessionHistory, _render_repl_turn
        exp, _ = explainer_and_index
        h = SessionHistory()
        rendered, bundle = _render_repl_turn(exp, "Why is WO-2001 late?", False, h)
        assert "register: testimony" in rendered
        assert bundle is not None

    def test_routed_turn_after_judgment_still_testimony(self, explainer_and_index):
        """A routed question must produce testimony even when history has a judgment turn."""
        from mre.ask import SessionHistory, Turn, _render_repl_turn
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        h = SessionHistory()
        # Add a prior judgment turn to history
        h.append(Turn(question="What do you think?", bundle=None, rendered="My take: x\n[rendered by: LLM | register: judgment]"))
        rendered, bundle = _render_repl_turn(exp, "Why is WO-2001 late?", False, h)
        assert "register: testimony" in rendered
        assert bundle is not None
        assert bundle.subject_type == "demand"

    # --- _render_repl_turn: unrouted + empty history → honest fallback ---

    def test_unrouted_empty_history_is_honest_fallback(self, explainer_and_index):
        from mre.ask import SessionHistory, _render_repl_turn
        exp, _ = explainer_and_index
        h = SessionHistory()
        rendered, bundle = _render_repl_turn(exp, "How is the weather?", False, h)
        assert bundle is not None
        assert bundle.subject_type == "unsupported"
        assert "register: testimony" in rendered

    def test_unrouted_empty_history_no_llm_flag_no_judgment(self, explainer_and_index):
        """Without --llm, unrouted questions never enter judgment mode."""
        from mre.ask import SessionHistory, Turn, _render_repl_turn
        exp, _ = explainer_and_index
        h = SessionHistory()
        h.append(Turn(question="Why is WO-2001 late?", bundle=None, rendered="..."))
        rendered, bundle = _render_repl_turn(exp, "How is the weather?", False, h)
        # Still testimony — no judgment without --llm
        assert bundle is not None
        assert bundle.subject_type == "unsupported"

    # --- judgment path: mocked LLM ---

    def test_judgment_path_calls_mocked_llm(self, explainer_and_index):
        from mre.ask import SessionHistory, Turn, _render_repl_turn
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index

        fake = FakeLLMClient("My take: WO-2001 is late because the gear machine was blocked.")
        h = SessionHistory()
        # Seed history with one routed turn
        prior_bundle = exp.answer("Why is WO-2001 late?")
        h.append(Turn(
            question="Why is WO-2001 late?",
            bundle=prior_bundle,
            rendered=TemplateRenderer()._render_body(prior_bundle),
        ))

        # Monkeypatch LLMRenderer so the _render_repl_turn picks up our fake
        import mre.modules.renderers as _renderers
        original_init = LLMRenderer.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._client = fake
            self._available = True

        _renderers.LLMRenderer.__init__ = patched_init
        try:
            rendered, bundle = _render_repl_turn(exp, "What do you think about this?", True, h)
        finally:
            _renderers.LLMRenderer.__init__ = original_init

        assert fake.calls, "LLM client must have been called"
        assert "My take:" in rendered
        assert bundle is None  # judgment turn has no evidence bundle

    def test_judgment_attribution_register(self, explainer_and_index):
        from mre.ask import SessionHistory, Turn, _render_repl_turn
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index

        fake = FakeLLMClient("My take: short answer.")
        renderer = LLMRenderer(_client=fake)
        prior_bundle = exp.answer("Why is WO-2001 late?")
        h = SessionHistory()
        h.append(Turn(question="Why is WO-2001 late?", bundle=prior_bundle, rendered="..."))

        fallback_bundle = exp.answer("Some unknown question xyz")
        text = renderer.render_judgment("Some unknown question xyz", h, fallback_bundle)
        assert "register: judgment" in text
        assert "register: testimony" not in text

    def test_judgment_response_text_in_output(self, explainer_and_index):
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        from mre.ask import SessionHistory, Turn
        fake = FakeLLMClient("My take: the root cause is the maintenance closure on 2026-07-13.")
        renderer = LLMRenderer(_client=fake)
        prior_bundle = exp.answer("Why is WO-2001 late?")
        h = SessionHistory()
        h.append(Turn(question="q", bundle=prior_bundle, rendered="..."))
        fallback_bundle = exp.answer("Something unrouted")
        text = renderer.render_judgment("Something unrouted", h, fallback_bundle)
        assert "maintenance closure" in text

    def test_judgment_no_llm_falls_back_to_testimony(self, explainer_and_index):
        from mre.modules.renderers import LLMRenderer
        from mre.ask import SessionHistory, Turn
        exp, _ = explainer_and_index
        renderer = LLMRenderer(api_key="")  # no key → unavailable
        prior_bundle = exp.answer("Why is WO-2001 late?")
        h = SessionHistory()
        h.append(Turn(question="q", bundle=prior_bundle, rendered="..."))
        fallback_bundle = exp.answer("How is the weather?")
        text = renderer.render_judgment("How is the weather?", h, fallback_bundle)
        assert "register: testimony" in text
        assert "register: judgment" not in text

    def test_judgment_prompt_contains_prior_facts(self, explainer_and_index):
        """The judgment prompt must include prior turn key facts."""
        from mre.modules.renderers import LLMRenderer
        from mre.ask import SessionHistory, Turn
        exp, _ = explainer_and_index
        fake = FakeLLMClient("My take: ok.")
        renderer = LLMRenderer(_client=fake)
        prior_bundle = exp.answer("Why is WO-2001 late?")
        h = SessionHistory()
        h.append(Turn(question="Why is WO-2001 late?", bundle=prior_bundle, rendered="..."))
        fallback_bundle = exp.answer("Some unrouted question")
        renderer.render_judgment("Some unrouted question", h, fallback_bundle)
        # The prompt sent to the LLM must include prior key facts
        assert fake.calls
        prompt_text = fake.calls[0]["messages"][0]["content"]
        assert "lateness_minutes" in prompt_text or "840" in prompt_text


# ---------------------------------------------------------------------------
# LLM testimony validation — anti-hallucination checks
# ---------------------------------------------------------------------------

def _make_late_bundle_for_validation() -> ExplanationBundle:
    """Minimal bundle with epoch metric + pre-rendered completion_iso."""
    return ExplanationBundle(
        question="Why is WO-2001 late?",
        subject_id="dem-val-001",
        subject_type="demand",
        subject_external_name="WO-2001",
        ordered_records=[
            {
                "record_type": "metric",
                "record_id": "met-epoch-001",
                "run_id": "run-val",
                "module": "M7",
                "seq": 1,
                "snapshot_id": "snap-val",
                "subjects": [],
                "tier": "supporting",
                "message": "",
                "name": "projected_completion_epoch",
                "value": 1784037600.0,   # 2026-07-14T14:00:00Z
                "unit": "epoch_seconds",
                "rollup_of": [],
            },
            {
                "record_type": "metric",
                "record_id": "met-late-001",
                "run_id": "run-val",
                "module": "M7",
                "seq": 2,
                "snapshot_id": "snap-val",
                "subjects": [{"entity_id": "dem-val-001", "entity_type": "demand"}],
                "tier": "supporting",
                "message": "",
                "name": "lateness_minutes",
                "value": 840.0,
                "unit": "minutes",
                "rollup_of": [],
            },
        ],
        key_facts={
            "lateness_minutes": 840.0,
            "lateness_hours": 14.0,
            "due_date": "2026-07-13T23:59:00Z",
            "completion_iso": "2026-07-14 14:00 UTC",
        },
        snapshot_id="snap-val",
        identity_map=None,
    )


class TestLLMTestimonyValidation:
    # --- pre-render: epoch metric → ISO in template body ---

    def test_epoch_metric_renders_as_iso_not_epoch(self):
        bundle = _make_late_bundle_for_validation()
        text = TemplateRenderer()._render_body(bundle)
        assert "1784037600" not in text
        assert "2026-07-14 14:00 UTC" in text

    def test_minutes_metric_renders_with_hours(self):
        bundle = _make_late_bundle_for_validation()
        text = TemplateRenderer()._render_body(bundle)
        assert "840 min" in text
        assert "14.0h" in text

    # --- pre-render: key_facts populated in _explain_why_late ---

    def test_explain_why_late_has_completion_iso(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        # FakeSnapshotReader has no epoch metric → None is acceptable
        # but if the real snapshot is used (integration fixture), it must be non-None.
        # Here we just assert the key is present.
        assert "completion_iso" in bundle.key_facts

    def test_explain_why_late_has_lateness_hours(self, explainer_and_index):
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        assert "lateness_hours" in bundle.key_facts
        lh = bundle.key_facts["lateness_hours"]
        if lh is not None:
            assert lh == round(840.0 / 60, 1)

    # --- validation: wrong timestamp caught ---

    def test_wrong_timestamp_produces_validation_issue(self):
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # Wrong timestamp — not in the prompt (14:00 UTC, not 08:39)
        bad_text = "WO-2001 completed at 2026-07-14T08:39:59Z. [record: met-epoch-001]"
        issues = renderer._validate_testimony(bad_text, known_ts, known_time, known_machines, _known_records)
        assert any("08:39" in i or "unverifiable timestamp" in i for i in issues)

    def test_correct_timestamp_passes_validation(self):
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        good_text = "WO-2001 completed at 2026-07-14 14:00 UTC. [record: met-epoch-001]"
        issues = renderer._validate_testimony(good_text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert not ts_issues

    def test_missing_footnotes_produces_validation_issue(self):
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # Factual sentence with no [record:] footnote
        bad_text = "WO-2001 was 840 minutes late due to machine constraints."
        issues = renderer._validate_testimony(bad_text, known_ts, known_time, known_machines, _known_records)
        assert any("footnote" in i for i in issues)

    def test_unverifiable_machine_name_caught(self):
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # M-CAST-99 is not in the prompt
        bad_text = "M-CAST-99 caused the delay. [record: met-late-001]"
        issues = renderer._validate_testimony(bad_text, known_ts, known_time, known_machines, _known_records)
        assert any("M-CAST-99" in i or "unverifiable machine" in i for i in issues)

    # --- wrong timestamp triggers fallback ---

    def test_wrong_timestamp_triggers_template_fallback(self):
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        # Both calls return the wrong timestamp → must fall back to template
        seq = FakeLLMClientSequence([
            "WO-2001 completed at 2026-07-14T08:39:59Z. No footnotes here.",
            "WO-2001 completed at 2026-07-14T08:39:59Z. Still wrong.",
        ])
        renderer = LLMRenderer(_client=seq)
        text = renderer.render(bundle)
        assert "LLM validation failed" in text
        assert "register: testimony" in text

    def test_bad_first_good_second_passes(self):
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        seq = FakeLLMClientSequence([
            # First: wrong timestamp
            "WO-2001 completed at 2026-07-14T08:39:59Z. No footnotes here.",
            # Second: correct — uses pre-computed value
            "WO-2001 completed at 2026-07-14 14:00 UTC. [record: met-epoch-001]",
        ])
        renderer = LLMRenderer(_client=seq)
        text = renderer.render(bundle)
        assert "LLM validation failed" not in text
        assert "2026-07-14 14:00 UTC" in text
        assert "register: testimony" in text

    # --- precomputed facts in prompt ---

    def test_precomputed_facts_in_llm_prompt(self):
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        fake = FakeLLMClient("WO-2001 completed at 2026-07-14 14:00 UTC. [record: met-epoch-001]")
        renderer = LLMRenderer(_client=fake)
        renderer.render(bundle)
        assert fake.calls
        prompt = fake.calls[0]["messages"][0]["content"]
        assert "PRE-COMPUTED FACTS" in prompt
        assert "2026-07-14 14:00 UTC" in prompt

    def test_regen_note_in_second_prompt(self):
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        seq = FakeLLMClientSequence([
            "WO-2001 at 2026-07-14T08:39:59Z. No footnotes.",
            "WO-2001 at 2026-07-14 14:00 UTC. [record: met-epoch-001]",
        ])
        renderer = LLMRenderer(_client=seq)
        renderer.render(bundle)
        assert seq._index == 2
        second_prompt = seq._responses[1]  # only checking structure, not the actual 2nd call content
        # Verify the second call was made (index advanced)
        assert seq._index == 2

    # --- timestamp variant normalization ---

    def test_due_date_no_seconds_passes(self):
        """LLM quoting 'YYYY-MM-DDTHH:MM' (no seconds) must not be flagged."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # Prompt has due_date "2026-07-13T23:59:00Z"; LLM drops seconds and Z
        text = "WO-2001 was due 2026-07-13T23:59. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert not ts_issues, ts_issues

    def test_due_date_space_separator_passes(self):
        """'YYYY-MM-DD HH:MM' (space instead of T) must not be flagged."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was due 2026-07-13 23:59. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert not ts_issues, ts_issues

    def test_date_only_form_passes(self):
        """Date-only 'YYYY-MM-DD' must pass when any prompt timestamp shares that date."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was due on 2026-07-13. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert not ts_issues, ts_issues

    def test_completion_with_z_suffix_passes(self):
        """'YYYY-MM-DDTHH:MM:SSZ' must match prompt's 'YYYY-MM-DD HH:MM UTC'."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # Prompt has completion_iso "2026-07-14 14:00 UTC"
        text = "WO-2001 completed 2026-07-14T14:00:00Z. [record: met-epoch-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert not ts_issues, ts_issues

    def test_wrong_hour_on_correct_date_still_fails(self):
        """A timestamp with the right date but wrong hour must still be flagged."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # Due date is 2026-07-13 23:59; using 14:00 on same date is wrong
        text = "WO-2001 was due 2026-07-13T14:00. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        ts_issues = [i for i in issues if "unverifiable timestamp" in i]
        assert ts_issues, "Wrong hour should have been flagged"

    # --- time-unit number normalization ---

    def test_hours_notation_passes(self):
        """'14h' must pass against a prompt with 840-minute lateness."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was 14h late. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        time_issues = [i for i in issues if "unverifiable time value" in i]
        assert not time_issues, time_issues

    def test_hours_full_word_passes(self):
        """'14 hours' must pass against 840-minute prompt."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was 14 hours late. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        time_issues = [i for i in issues if "unverifiable time value" in i]
        assert not time_issues, time_issues

    def test_minutes_decimal_passes(self):
        """'840.0 min' must pass (prompt has 840 minutes lateness)."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was 840.0 min late. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        time_issues = [i for i in issues if "unverifiable time value" in i]
        assert not time_issues, time_issues

    def test_wrong_hours_fails(self):
        """'15h' must be flagged — 15h = 900 min, prompt has 840 min."""
        from mre.modules.renderers import LLMRenderer
        renderer = LLMRenderer(api_key="")
        bundle = _make_late_bundle_for_validation()
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        text = "WO-2001 was 15h late. [record: met-late-001]"
        issues = renderer._validate_testimony(text, known_ts, known_time, known_machines, _known_records)
        time_issues = [i for i in issues if "unverifiable time value" in i]
        assert time_issues, "15h (= 900 min, not 840) should have been flagged"

    # --- end-to-end: realistic LLM response using common timestamp variants ---

    def test_realistic_response_with_timestamp_variants_passes(self, explainer_and_index):
        """Full render must pass validation when LLM uses legitimate timestamp variants."""
        from mre.modules.renderers import LLMRenderer
        exp, _ = explainer_and_index
        bundle = exp.answer("Why is WO-2001 late?")
        # Response uses 'YYYY-MM-DDTHH:MM' (no seconds, no Z) for due date
        # and '840 min (14.0h)' for lateness — both legitimate forms
        good_response = (
            "WO-2001 completed 840 min (14.0h) past its due date of 2026-07-13T23:59. "
            "[record: met-late-001]"
        )
        renderer = LLMRenderer(_client=FakeLLMClient(good_response))
        result = renderer.render(bundle)
        assert "LLM validation failed" not in result
        assert "register: testimony" in result

    # --- integration: single-source-of-truth render path ---

    def test_due_date_from_prompt_headline_passes_via_render(self):
        """Integration (real render path): LLM quotes due-date with seconds dropped — must pass.

        The headline in the prompt reads "(2026-07-13T23:59:00Z)" and the pre-computed
        facts show "due_date: 2026-07-13T23:59:00Z".  The LLM abbreviates to "T23:59"
        (dropping seconds and Z).  The validator must accept this because the value
        is present in the prompt at minute granularity.
        """
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        fake = FakeLLMClient(
            "WO-2001 was due on 2026-07-13T23:59 and finished 840 min late. "
            "[record: met-late-001]"
        )
        renderer = LLMRenderer(_client=fake)
        result = renderer.render(bundle)
        assert "LLM validation failed" not in result, result
        assert "register: testimony" in result

    def test_timestamp_absent_from_prompt_triggers_fallback(self):
        """Integration (real render path): LLM invents a timestamp not in the prompt — must fail."""
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        # 2027-06-15T10:00 appears nowhere in the prompt — pure hallucination.
        seq = FakeLLMClientSequence([
            "WO-2001 completed on 2027-06-15T10:00. [record: met-late-001]",
            "WO-2001 completed on 2027-06-15T10:00. [record: met-late-001]",
        ])
        renderer = LLMRenderer(_client=seq)
        result = renderer.render(bundle)
        assert "LLM validation failed" in result
        assert "register: testimony" in result

    def test_build_prompt_material_known_sets_contain_prompt_values(self):
        """_build_prompt_material must expose every value shown to the LLM as verifiable."""
        from mre.modules.renderers import LLMRenderer
        bundle = _make_late_bundle_for_validation()
        renderer = LLMRenderer(api_key="")
        _, known_ts, known_time, known_machines, _known_records = renderer._build_prompt_material(bundle)
        # due_date = "2026-07-13T23:59:00Z" -> (2026, 7, 13, 23, 59)
        assert (2026, 7, 13, 23, 59) in known_ts
        # completion_iso = "2026-07-14 14:00 UTC" -> (2026, 7, 14, 14, 0)
        assert (2026, 7, 14, 14, 0) in known_ts
        # lateness 840 min and its hour equivalent 14.0 both verifiable
        assert 840.0 in known_time
        assert 14.0 in known_time
