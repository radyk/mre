"""Tests for M4 Planner — derived from docs/01 §§5.2–5.4 and docs/03 Phase 2.

Tests run against a minimal in-memory snapshot, not against sample_data.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers to build a minimal snapshot
# ---------------------------------------------------------------------------

def _make_reporter(snap_id: str, tmp_path: Path, suffix: str = ""):
    from mre.reporter import Reporter
    from mre.contracts.vocabularies import ModuleCode
    return Reporter.begin(
        module=ModuleCode.M4,
        purpose="planner test",
        config={},
        trigger="pytest",
        snapshot_id=snap_id,
        sink_dir=tmp_path / f"runs{suffix}",
    )


def _make_store(tmp_path: Path):
    from mre.modules.snapshot_store import SnapshotStore
    return SnapshotStore(tmp_path / "snapshots")


def _build_minimal_snapshot(
    store,
    snap_id: str,
    demands: list,
    op_specs: list,
    products: list,
    processes: list,
):
    """Write a ready-to-read snapshot without running the adapter."""
    from mre.contracts.provenance import ProvenanceSidecar, ProvenanceClass, DefaultedProvenance
    from mre.contracts.entities import WorkPackageState

    writer = store.begin_snapshot(snap_id)

    def _dp(eid: str, attr: str) -> ProvenanceSidecar:
        return ProvenanceSidecar(
            entity_id=eid, attribute_name=attr, snapshot_id=snap_id,
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="test"),
        )

    for entity, attrs in list(demands) + list(op_specs) + list(products) + list(processes):
        writer.write_entity(entity, [_dp(entity.id, a) for a in attrs])

    writer.finalize()


def _make_product(snap_id: str, prod_id: str, family: str = "casting"):
    from mre.contracts.entities import Product
    return (
        Product(id=prod_id, snapshot_id=snap_id, name="P", unit_of_measure="EA",
                process_ref=None, product_family=family),
        ["name", "unit_of_measure", "process_ref", "product_family"],
    )


def _make_op_spec(snap_id: str, spec_id: str, seq: int = 10,
                  setup_sec: int = 60, rate_sec: int = 45,
                  family: str = "casting"):
    from mre.contracts.entities import OperationSpec
    return (
        OperationSpec(
            id=spec_id, snapshot_id=snap_id, sequence=seq,
            setup_family=family,
            base_setup=timedelta(seconds=setup_sec),
            run_rate=timedelta(seconds=rate_sec),
        ),
        ["sequence", "resource_requirements", "setup_family",
         "base_setup", "run_rate", "dwell_rule", "splittable",
         "min_chunk", "yield_factor"],
    )


def _make_process(snap_id: str, proc_id: str, prod_id: str, spec_ids: list[str]):
    from mre.contracts.entities import Process
    from mre.contracts.vocabularies import ProcessStatus
    return (
        Process(id=proc_id, snapshot_id=snap_id, product_ref=prod_id,
                operation_specs=spec_ids, version=1, status=ProcessStatus.ACTIVE),
        ["product_ref", "operation_specs", "version", "effective_from", "status"],
    )


def _make_demand(snap_id: str, demand_id: str, prod_id: str, qty: float,
                 due: datetime, earliest: datetime | None = None):
    from mre.contracts.entities import Demand, Quantity
    from mre.contracts.vocabularies import CommitmentClass, DemandStatus
    return (
        Demand(id=demand_id, snapshot_id=snap_id, product_ref=prod_id,
               quantity=Quantity(value=qty, uom="EA"),
               due=due, earliest_start=earliest,
               commitment_class=CommitmentClass.STANDARD,
               customer_weight=1.0, status=DemandStatus.OPEN),
        ["product_ref", "quantity", "due", "earliest_start",
         "commitment_class", "customer_weight", "customer_ref", "status"],
    )


@pytest.fixture
def snap_env(tmp_path):
    """Return (store, snap_id, reporter) with a minimal one-demand snapshot."""
    snap_id = "test-snap-001"
    store = _make_store(tmp_path)
    prod_id = "prod-1"
    spec_id = "spec-1"
    proc_id = "proc-1"
    demand_id = "d-1"

    _build_minimal_snapshot(
        store, snap_id,
        demands=[_make_demand(snap_id, demand_id, prod_id, 200.0,
                              datetime(2026, 8, 1, 23, 59, tzinfo=UTC))],
        op_specs=[_make_op_spec(snap_id, spec_id)],
        products=[_make_product(snap_id, prod_id)],
        processes=[_make_process(snap_id, proc_id, prod_id, [spec_id])],
    )
    reporter = _make_reporter(snap_id, tmp_path)
    return store, snap_id, reporter, demand_id, prod_id, spec_id


# ---------------------------------------------------------------------------
# WorkPackage invariants (docs/01 §5.2)
# ---------------------------------------------------------------------------

class TestWorkPackageInvariants:
    def test_workpackage_has_no_due_field(self):
        """WorkPackage must not have a due_date field — lives on Demands (D-07)."""
        from mre.contracts.entities import WorkPackage
        assert "due" not in WorkPackage.model_fields
        assert "due_date" not in WorkPackage.model_fields

    def test_workpackage_has_no_priority_field(self):
        """Priority is derived from Demands at solve time, never stored on WP."""
        from mre.contracts.entities import WorkPackage
        assert "priority" not in WorkPackage.model_fields

    def test_workpackage_requires_created_by(self):
        """created_by references the Decision that authorised creation."""
        from mre.contracts.entities import WorkPackage
        assert "created_by" in WorkPackage.model_fields
        # Not Optional — required
        field = WorkPackage.model_fields["created_by"]
        assert field.is_required()


# ---------------------------------------------------------------------------
# identity_v1 policy
# ---------------------------------------------------------------------------

class TestIdentityPolicy:
    def test_identity_creates_one_wp_per_demand(self, snap_env, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, demand_id, prod_id, spec_id = snap_env
        result = Planner(policy="identity_v1").run(snap_id, store, reporter)
        assert result.workpackage_count == 1
        assert result.fulfillment_count == 1
        assert result.merge_count == 0

    def test_identity_wp_written_to_snapshot(self, snap_env, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, *_ = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        wps = list(reader.iter_entities("workpackage"))
        assert len(wps) == 1

    def test_identity_fulfillment_links_demand_to_wp(self, snap_env):
        from mre.modules.planner import Planner
        store, snap_id, reporter, demand_id, *_ = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        fuls = list(reader.iter_entities("fulfillment"))
        assert len(fuls) == 1
        assert fuls[0]["demand_ref"] == demand_id

    def test_identity_operation_count_matches_specs(self, snap_env):
        from mre.modules.planner import Planner
        store, snap_id, reporter, *_ = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        ops = list(reader.iter_entities("operation"))
        assert len(ops) == 1  # 1 demand × 1 spec = 1 operation

    def test_run_duration_is_derived_quantity_times_rate(self, snap_env):
        """run_duration = quantity × spec.run_rate (DERIVED provenance, docs/01 §5.3)."""
        from mre.modules.planner import Planner
        store, snap_id, reporter, demand_id, prod_id, spec_id = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        ops = list(reader.iter_entities("operation"))
        op = ops[0]
        # quantity=200, run_rate=45 sec/unit → 200×45=9000 sec = 150 min
        # Stored as ISO 8601 duration string
        run_td = _parse_td(op["run_duration"])
        assert run_td == timedelta(seconds=200 * 45), f"Expected 9000s, got {run_td}"

    def test_run_duration_has_derived_provenance(self, snap_env):
        from mre.modules.planner import Planner
        from mre.contracts.vocabularies import ProvenanceClass
        store, snap_id, reporter, *_ = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        ops = list(reader.iter_entities("operation"))
        op_id = ops[0]["id"]
        prov = reader.get_provenance(op_id, "run_duration")
        assert prov is not None
        assert prov["provenance_class"] == ProvenanceClass.DERIVED.value

    def test_wp_created_by_references_a_decision(self, snap_env):
        from mre.modules.planner import Planner
        store, snap_id, reporter, *_ = snap_env
        Planner(policy="identity_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        wp = next(reader.iter_entities("workpackage"))
        assert wp.get("created_by")


# ---------------------------------------------------------------------------
# merge_by_family_v1 policy
# ---------------------------------------------------------------------------

def _make_two_demand_snapshot(tmp_path: Path, qty1=200, qty2=200,
                               due1_offset_days=0, due2_offset_days=2,
                               family="gear"):
    """Return (store, snap_id, reporter, d1_id, d2_id) with two demands of the
    same product+family whose due dates are due2_offset_days apart."""
    snap_id = "merge-snap-001"
    store = _make_store(tmp_path)
    prod_id = "prod-gear"
    spec_id = "spec-gear"
    proc_id = "proc-gear"
    d1_id = "d-gear-1"
    d2_id = "d-gear-2"
    base = datetime(2026, 7, 13, 23, 59, tzinfo=UTC)

    _build_minimal_snapshot(
        store, snap_id,
        demands=[
            _make_demand(snap_id, d1_id, prod_id, qty1, base),
            _make_demand(snap_id, d2_id, prod_id, qty2,
                         datetime(2026, 7, 13 + due2_offset_days, 23, 59, tzinfo=UTC)),
        ],
        op_specs=[_make_op_spec(snap_id, spec_id, family=family)],
        products=[_make_product(snap_id, prod_id, family=family)],
        processes=[_make_process(snap_id, proc_id, prod_id, [spec_id])],
    )
    from mre.reporter import Reporter
    from mre.contracts.vocabularies import ModuleCode
    reporter = Reporter.begin(
        module=ModuleCode.M4, purpose="merge test", config={},
        trigger="pytest", snapshot_id=snap_id,
        sink_dir=tmp_path / "runs_merge",
    )
    return store, snap_id, reporter, d1_id, d2_id


class TestMergePolicy:
    def test_merge_within_window_creates_one_wp(self, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, d1_id, d2_id = _make_two_demand_snapshot(
            tmp_path, due2_offset_days=2  # 2 days ≤ 3-day window → merge
        )
        result = Planner(policy="merge_by_family_v1", merge_window_days=3).run(
            snap_id, store, reporter
        )
        assert result.workpackage_count == 1
        assert result.fulfillment_count == 2
        assert result.merge_count == 1

    def test_merge_beyond_window_creates_two_wps(self, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, d1_id, d2_id = _make_two_demand_snapshot(
            tmp_path, due2_offset_days=5  # 5 days > 3-day window → no merge
        )
        result = Planner(policy="merge_by_family_v1", merge_window_days=3).run(
            snap_id, store, reporter
        )
        assert result.workpackage_count == 2
        assert result.merge_count == 0

    def test_merged_wp_has_no_due_field(self, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, *_ = _make_two_demand_snapshot(tmp_path)
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        wp = next(reader.iter_entities("workpackage"))
        assert "due" not in wp

    def test_merge_decision_has_setup_amortization_driver(self, tmp_path):
        from mre.modules.planner import Planner
        from mre.reporter import Reporter, JsonlSink
        from mre.contracts.vocabularies import DriverCode, ModuleCode, DecisionType
        store, snap_id, reporter, *_ = _make_two_demand_snapshot(tmp_path)
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        # Read evidence records
        from mre.contracts.records import Decision
        records = reporter._sink.read_all()
        decisions = [r for r in records if r.get("record_type") == "decision"
                     and r.get("decision_type") == DecisionType.DEMAND_MERGE.value]
        assert len(decisions) == 1
        assert decisions[0]["driver"] == DriverCode.SETUP_AMORTIZATION.value

    def test_merge_decision_basis_is_policy_applied(self, tmp_path):
        from mre.modules.planner import Planner
        from mre.contracts.vocabularies import DecisionBasis, DecisionType
        store, snap_id, reporter, *_ = _make_two_demand_snapshot(tmp_path)
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        records = reporter._sink.read_all()
        decisions = [r for r in records if r.get("record_type") == "decision"
                     and r.get("decision_type") == DecisionType.DEMAND_MERGE.value]
        assert decisions[0]["basis"] == DecisionBasis.POLICY_APPLIED.value

    def test_merge_decision_has_estimated_benefit(self, tmp_path):
        from mre.modules.planner import Planner
        from mre.contracts.vocabularies import DecisionType
        store, snap_id, reporter, *_ = _make_two_demand_snapshot(tmp_path)
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        records = reporter._sink.read_all()
        decisions = [r for r in records if r.get("record_type") == "decision"
                     and r.get("decision_type") == DecisionType.DEMAND_MERGE.value]
        chosen = decisions[0].get("chosen", {})
        # chosen payload should carry estimated_benefit
        assert "estimated_benefit" in str(chosen) or "setups_avoided" in str(chosen)

    def test_merge_two_fulfillments_link_both_demands_to_same_wp(self, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, d1_id, d2_id = _make_two_demand_snapshot(tmp_path)
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        fuls = list(reader.iter_entities("fulfillment"))
        assert len(fuls) == 2
        wp_refs = {f["workpackage_ref"] for f in fuls}
        demand_refs = {f["demand_ref"] for f in fuls}
        assert len(wp_refs) == 1   # both point to same WP
        assert d1_id in demand_refs
        assert d2_id in demand_refs

    def test_merged_quantity_is_sum_of_constituents(self, tmp_path):
        from mre.modules.planner import Planner
        store, snap_id, reporter, *_ = _make_two_demand_snapshot(
            tmp_path, qty1=200, qty2=300
        )
        Planner(policy="merge_by_family_v1").run(snap_id, store, reporter)
        reader = store.load_snapshot(snap_id)
        wp = next(reader.iter_entities("workpackage"))
        assert wp["quantity"]["value"] == pytest.approx(500.0)

    def test_different_families_not_merged(self, tmp_path):
        """Demands of different product_families must stay separate (different products)."""
        snap_id = "diff-fam-snap"
        store = _make_store(tmp_path)

        # Two products with different families
        prod_a = "prod-cast"
        prod_b = "prod-gear"
        spec_a = "spec-cast"
        spec_b = "spec-gear"

        _build_minimal_snapshot(
            store, snap_id,
            demands=[
                _make_demand(snap_id, "d-a", prod_a, 100.0,
                              datetime(2026, 7, 13, 23, 59, tzinfo=UTC)),
                _make_demand(snap_id, "d-b", prod_b, 100.0,
                              datetime(2026, 7, 14, 23, 59, tzinfo=UTC)),
            ],
            op_specs=[
                _make_op_spec(snap_id, spec_a, family="casting"),
                _make_op_spec(snap_id, spec_b, family="gear"),
            ],
            products=[
                _make_product(snap_id, prod_a, family="casting"),
                _make_product(snap_id, prod_b, family="gear"),
            ],
            processes=[
                _make_process(snap_id, "proc-a", prod_a, [spec_a]),
                _make_process(snap_id, "proc-b", prod_b, [spec_b]),
            ],
        )
        from mre.reporter import Reporter
        from mre.contracts.vocabularies import ModuleCode
        rep = Reporter.begin(
            module=ModuleCode.M4, purpose="diff fam test", config={},
            trigger="pytest", snapshot_id=snap_id,
            sink_dir=tmp_path / "runs_difffam",
        )

        from mre.modules.planner import Planner
        result = Planner(policy="merge_by_family_v1").run(snap_id, store, rep)
        assert result.workpackage_count == 2  # different products → no merge
        assert result.merge_count == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_td(s: str) -> timedelta:
    """Parse ISO 8601 duration string (PT...S / PT...M...S / etc.)."""
    import re
    m = re.fullmatch(r"PT?(\d+(?:\.\d+)?H)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?S)?", s)
    if not m:
        raise ValueError(f"Unparseable duration: {s}")
    h = float(m.group(1).rstrip("H")) if m.group(1) else 0.0
    mn = float(m.group(2).rstrip("M")) if m.group(2) else 0.0
    sec = float(m.group(3).rstrip("S")) if m.group(3) else 0.0
    return timedelta(hours=h, minutes=mn, seconds=sec)
