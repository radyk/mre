"""Tests for M2 SnapshotStore — derived from docs/01 §7 (write contract, sidecar).

The write contract is structural: write_entity accepts (entity, provenance_list)
together. No code path sets a value without its provenance record.
"""
import pytest
from datetime import datetime, timezone

from mre.contracts import (
    Demand, Product, CommitmentClass, DemandStatus, Quantity, ExternalRef,
    ProvenanceSidecar, SynthesizedProvenance, DefaultedProvenance,
    ObservedProvenance, ProvenanceClass,
)
from mre.modules.snapshot_store import SnapshotStore, WriteContractError

UTC = timezone.utc
SNAP = "snap-store-test"
GEN = "test_gen_v1"


def _synth(entity_id: str, attr: str, snapshot_id: str = SNAP) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id,
        attribute_name=attr,
        snapshot_id=snapshot_id,
        provenance_class=ProvenanceClass.SYNTHESIZED,
        payload=SynthesizedProvenance(generator_id=GEN),
    )


def _full_demand_provenance(demand_id: str) -> list[ProvenanceSidecar]:
    attrs = [
        "product_ref", "quantity", "due", "earliest_start",
        "commitment_class", "customer_weight", "customer_ref", "status",
    ]
    return [_synth(demand_id, a) for a in attrs]


def _make_demand(snap_id: str = SNAP) -> Demand:
    return Demand(
        id="demand-001",
        snapshot_id=snap_id,
        product_ref="prod-001",
        quantity=Quantity(value=100.0, uom="EA"),
        due=datetime(2026, 4, 15, tzinfo=UTC),
        commitment_class=CommitmentClass.STANDARD,
        status=DemandStatus.OPEN,
    )


class TestWriteContract:
    def test_write_entity_requires_provenance(self, tmp_path):
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        # Must not raise when full provenance is supplied
        writer.write_entity(demand, _full_demand_provenance(demand.id))

    def test_write_entity_without_provenance_raises(self, tmp_path):
        """No code path may set a value without its provenance record."""
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        with pytest.raises(WriteContractError):
            writer.write_entity(demand, [])  # no provenance at all

    def test_write_entity_missing_one_attr_raises(self, tmp_path):
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        # Omit provenance for 'due'
        provenance = [p for p in _full_demand_provenance(demand.id)
                      if p.attribute_name != "due"]
        with pytest.raises(WriteContractError, match="due"):
            writer.write_entity(demand, provenance)

    def test_universal_fields_exempt_from_provenance(self, tmp_path):
        """id, snapshot_id, external_refs are universal conventions — no provenance required."""
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        # Full provenance covers everything except universals
        writer.write_entity(demand, _full_demand_provenance(demand.id))  # should not raise


class TestReadback:
    def _write_demand(self, tmp_path):
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        writer.write_entity(demand, _full_demand_provenance(demand.id))
        writer.finalize()
        return store, demand

    def test_get_entity_returns_correct_type(self, tmp_path):
        store, demand = self._write_demand(tmp_path)
        reader = store.load_snapshot(SNAP)
        result = reader.get_entity(demand.id)
        assert result is not None

    def test_get_entity_preserves_values(self, tmp_path):
        store, demand = self._write_demand(tmp_path)
        reader = store.load_snapshot(SNAP)
        result = reader.get_entity(demand.id)
        assert result["product_ref"] == "prod-001"
        assert result["status"] == "open"

    def test_iter_entities_by_type(self, tmp_path):
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        d1 = _make_demand()
        d2 = Demand(
            id="demand-002", snapshot_id=SNAP,
            product_ref="prod-002",
            quantity=Quantity(value=50.0, uom="EA"),
            due=datetime(2026, 5, 1, tzinfo=UTC),
            commitment_class=CommitmentClass.RUSH,
            status=DemandStatus.OPEN,
        )
        writer.write_entity(d1, _full_demand_provenance(d1.id))
        writer.write_entity(d2, _full_demand_provenance(d2.id))
        writer.finalize()
        reader = store.load_snapshot(SNAP)
        demands = list(reader.iter_entities("demand"))
        assert len(demands) == 2

    def test_get_provenance_narrow_interface(self, tmp_path):
        """M3/M4 read sidecar through a narrow trust interface (docs/01 §7.4)."""
        store, demand = self._write_demand(tmp_path)
        reader = store.load_snapshot(SNAP)
        prov = reader.get_provenance(demand.id, "quantity")
        assert prov is not None
        assert prov["provenance_class"] == "synthesized"

    def test_iter_provenance_for_entity(self, tmp_path):
        store, demand = self._write_demand(tmp_path)
        reader = store.load_snapshot(SNAP)
        records = list(reader.iter_provenance_for_entity(demand.id))
        attrs = {r["attribute_name"] for r in records}
        assert "quantity" in attrs
        assert "due" in attrs
        assert "commitment_class" in attrs

    def test_solver_builder_gets_no_sidecar(self, tmp_path):
        """Solver Builder uses plain entity view — no provenance access (docs/01 §7.4)."""
        store, demand = self._write_demand(tmp_path)
        reader = store.load_snapshot(SNAP)
        entity = reader.get_entity(demand.id)
        # Plain entity dict has no provenance key
        assert "provenance_class" not in entity
        assert "payload" not in entity


class TestMultipleEntityTypes:
    def test_different_types_stored_separately(self, tmp_path):
        store = SnapshotStore(tmp_path)
        writer = store.begin_snapshot(SNAP)
        demand = _make_demand()
        product = Product(
            id="prod-001", snapshot_id=SNAP,
            name="Widget Alpha", unit_of_measure="EA",
        )
        writer.write_entity(demand, _full_demand_provenance(demand.id))
        writer.write_entity(product, [
            _synth("prod-001", "name"),
            _synth("prod-001", "unit_of_measure"),
            _synth("prod-001", "process_ref"),
            _synth("prod-001", "product_family"),
        ])
        writer.finalize()
        reader = store.load_snapshot(SNAP)
        assert len(list(reader.iter_entities("demand"))) == 1
        assert len(list(reader.iter_entities("product"))) == 1


class TestSnapshotIsolation:
    def test_two_snapshots_are_independent(self, tmp_path):
        store = SnapshotStore(tmp_path)
        for snap in ["snap-001", "snap-002"]:
            writer = store.begin_snapshot(snap)
            d = Demand(
                id=f"demand-{snap}", snapshot_id=snap,
                product_ref="prod-001",
                quantity=Quantity(value=10.0, uom="EA"),
                due=datetime(2026, 4, 1, tzinfo=UTC),
                commitment_class=CommitmentClass.STANDARD,
                status=DemandStatus.OPEN,
            )
            writer.write_entity(d, _full_demand_provenance(d.id))
            writer.finalize()
        snaps = store.list_snapshots()
        assert "snap-001" in snaps
        assert "snap-002" in snaps

    def test_load_nonexistent_snapshot_raises(self, tmp_path):
        store = SnapshotStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_snapshot("does-not-exist")


class TestIdentityMapPersistence:
    """SnapshotWriter.write_identity_map / SnapshotReader.read_identity_map round-trip."""

    def _make_map(self):
        from mre.modules.identity_map import IdentityMap
        im = IdentityMap()
        im.register("canonical-1", "ERP", "work_order", "WO-100")
        im.register("canonical-2", "ERP", "product_no", "PROD-001")
        im.register("canonical-3", "ERP", "machine_id", "CNC-1")
        return im

    def test_write_and_read_round_trip(self, tmp_path):
        store = SnapshotStore(tmp_path / "snapshots")
        writer = store.begin_snapshot("snap-idmap")
        writer.write_identity_map(self._make_map())
        writer.finalize()

        reader = store.load_snapshot("snap-idmap")
        loaded = reader.read_identity_map()
        assert loaded is not None
        assert loaded.resolve("ERP", "work_order", "WO-100") == "canonical-1"
        assert loaded.resolve("ERP", "product_no", "PROD-001") == "canonical-2"

    def test_resolve_unknown_returns_none(self, tmp_path):
        store = SnapshotStore(tmp_path / "snapshots")
        writer = store.begin_snapshot("snap-idmap2")
        writer.write_identity_map(self._make_map())
        writer.finalize()

        reader = store.load_snapshot("snap-idmap2")
        loaded = reader.read_identity_map()
        assert loaded.resolve("ERP", "work_order", "WO-9999") is None

    def test_external_refs_round_trip(self, tmp_path):
        store = SnapshotStore(tmp_path / "snapshots")
        writer = store.begin_snapshot("snap-idmap3")
        writer.write_identity_map(self._make_map())
        writer.finalize()

        reader = store.load_snapshot("snap-idmap3")
        loaded = reader.read_identity_map()
        erefs = loaded.external_refs("canonical-3")
        assert len(erefs) == 1
        assert erefs[0].system == "ERP"
        assert erefs[0].value == "CNC-1"

    def test_read_returns_none_when_not_written(self, tmp_path):
        store = SnapshotStore(tmp_path / "snapshots")
        writer = store.begin_snapshot("snap-no-idmap")
        demand = Demand(
            id="d1", snapshot_id="snap-no-idmap",
            product_ref="p1",
            quantity=Quantity(value=1.0, uom="EA"),
            due=datetime(2026, 6, 1, tzinfo=UTC),
            commitment_class=CommitmentClass.STANDARD,
            status=DemandStatus.OPEN,
        )
        writer.write_entity(demand, _full_demand_provenance(demand.id))
        writer.finalize()

        reader = store.load_snapshot("snap-no-idmap")
        assert reader.read_identity_map() is None
