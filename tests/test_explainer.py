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
