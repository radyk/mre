"""Tests derived from docs/01 §7: provenance sidecar shapes and invariants."""
import pytest
from pydantic import ValidationError

from mre.contracts.provenance import (
    DefaultedProvenance,
    DerivedProvenance,
    InputRef,
    ObservedProvenance,
    ProvenanceSidecar,
    SynthesizedProvenance,
)
from mre.contracts.vocabularies import ProvenanceClass


class TestObservedProvenance:
    def test_valid(self):
        p = ObservedProvenance(
            source_system="SAP",
            source_field="DUEDATE",
            extract_ref="extract-2026-01-01",
        )
        assert p.source_system == "SAP"
        assert p.provenance_class == ProvenanceClass.OBSERVED

    def test_missing_source_system_raises(self):
        with pytest.raises(ValidationError):
            ObservedProvenance(source_field="X", extract_ref="Y")

    def test_missing_source_field_raises(self):
        with pytest.raises(ValidationError):
            ObservedProvenance(source_system="SAP", extract_ref="Y")

    def test_missing_extract_ref_raises(self):
        with pytest.raises(ValidationError):
            ObservedProvenance(source_system="SAP", source_field="X")


class TestDerivedProvenance:
    def test_valid(self):
        p = DerivedProvenance(
            formula_id="run_duration_calc",
            input_refs=[
                InputRef(entity_id="d-1", attribute_name="quantity", snapshot_id="s-1"),
                InputRef(entity_id="prod-1", attribute_name="run_rate", snapshot_id="s-1"),
            ],
        )
        assert p.formula_id == "run_duration_calc"
        assert len(p.input_refs) == 2
        assert p.provenance_class == ProvenanceClass.DERIVED

    def test_missing_formula_id_raises(self):
        with pytest.raises(ValidationError):
            DerivedProvenance(
                input_refs=[InputRef(entity_id="d-1", attribute_name="q", snapshot_id="s-1")]
            )

    def test_missing_input_refs_raises(self):
        with pytest.raises(ValidationError):
            DerivedProvenance(formula_id="calc")

    def test_input_ref_structure(self):
        ref = InputRef(entity_id="d-1", attribute_name="quantity", snapshot_id="s-1")
        assert ref.entity_id == "d-1"
        assert ref.attribute_name == "quantity"
        assert ref.snapshot_id == "s-1"


class TestDefaultedProvenance:
    def test_valid(self):
        p = DefaultedProvenance(policy="default_customer_weight_1.0")
        assert p.policy == "default_customer_weight_1.0"
        assert p.provenance_class == ProvenanceClass.DEFAULTED

    def test_missing_policy_raises(self):
        with pytest.raises(ValidationError):
            DefaultedProvenance()


class TestSynthesizedProvenance:
    def test_not_real_marker_is_always_true(self):
        """Synthesized data must carry a loud not-real marker (docs/01 §7.2)."""
        p = SynthesizedProvenance(generator_id="test_data_gen_v1")
        assert p.not_real is True
        assert p.provenance_class == ProvenanceClass.SYNTHESIZED

    def test_missing_generator_id_raises(self):
        with pytest.raises(ValidationError):
            SynthesizedProvenance()


class TestProvenanceSidecar:
    def test_keyed_by_entity_attribute_snapshot(self):
        """Sidecar key is entity_id + attribute_name + snapshot_id (docs/01 §7.1)."""
        sidecar = ProvenanceSidecar(
            entity_id="demand-1",
            attribute_name="customer_weight",
            snapshot_id="snap-1",
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="default_weight_1.0"),
        )
        assert sidecar.entity_id == "demand-1"
        assert sidecar.attribute_name == "customer_weight"
        assert sidecar.snapshot_id == "snap-1"

    def test_provenance_class_matches_payload(self):
        sidecar = ProvenanceSidecar(
            entity_id="e-1",
            attribute_name="quantity",
            snapshot_id="s-1",
            provenance_class=ProvenanceClass.OBSERVED,
            payload=ObservedProvenance(
                source_system="SAP",
                source_field="QTY",
                extract_ref="ext-1",
            ),
        )
        assert sidecar.provenance_class == ProvenanceClass.OBSERVED

    def test_missing_entity_id_raises(self):
        with pytest.raises(ValidationError):
            ProvenanceSidecar(
                attribute_name="qty",
                snapshot_id="s-1",
                provenance_class=ProvenanceClass.DEFAULTED,
                payload=DefaultedProvenance(policy="p"),
            )

    def test_can_change_across_snapshots(self):
        """Provenance can change across snapshots (defaulted yesterday, observed today)."""
        defaulted = ProvenanceSidecar(
            entity_id="d-1", attribute_name="weight", snapshot_id="snap-1",
            provenance_class=ProvenanceClass.DEFAULTED,
            payload=DefaultedProvenance(policy="default_weight"),
        )
        observed = ProvenanceSidecar(
            entity_id="d-1", attribute_name="weight", snapshot_id="snap-2",
            provenance_class=ProvenanceClass.OBSERVED,
            payload=ObservedProvenance(source_system="SAP", source_field="W", extract_ref="e-2"),
        )
        assert defaulted.snapshot_id != observed.snapshot_id
        assert defaulted.provenance_class != observed.provenance_class
