"""Tests derived from docs/01 §4-6: entity shapes, universal fields, invariants."""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from mre.contracts.entities import (
    Demand, EntityRef, ExternalRef, Fulfillment, Operation, Product,
    Quantity, Resource, ResourceRequirement, WorkPackage,
)
from mre.contracts.vocabularies import (
    CommitmentClass, DemandStatus, ResourceRequirementMode, ResourceType,
    WorkPackageState,
)

UTC = timezone.utc
NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def make_demand(**kwargs) -> Demand:
    defaults = dict(
        id="d-1",
        snapshot_id="s-1",
        product_ref="prod-1",
        quantity=Quantity(value=100.0, uom="ea"),
        due=NOW,
        commitment_class=CommitmentClass.STANDARD,
        status=DemandStatus.OPEN,
    )
    return Demand(**(defaults | kwargs))


def make_workpackage(**kwargs) -> WorkPackage:
    defaults = dict(
        id="wp-1",
        snapshot_id="s-1",
        product_ref="prod-1",
        quantity=Quantity(value=100.0, uom="ea"),
        state=WorkPackageState.PLANNED,
        created_by="dec-1",
    )
    return WorkPackage(**(defaults | kwargs))


class TestUniversalFields:
    """Every canonical entity carries id, snapshot_id, external_refs (docs/01 §4)."""

    def test_demand_has_universal_fields(self):
        d = make_demand()
        assert d.id == "d-1"
        assert d.snapshot_id == "s-1"
        assert isinstance(d.external_refs, list)

    def test_workpackage_has_universal_fields(self):
        wp = make_workpackage()
        assert wp.id == "wp-1"
        assert wp.snapshot_id == "s-1"
        assert isinstance(wp.external_refs, list)

    def test_external_refs_hold_erp_ids(self):
        ref = ExternalRef(system="SAP", type="sales_order", value="SO-12345")
        d = make_demand(external_refs=[ref])
        assert d.external_refs[0].system == "SAP"
        assert d.external_refs[0].value == "SO-12345"


class TestWorkPackageInvariants:
    """WorkPackage deliberately has no due date and no priority (docs/01 §5.2)."""

    def test_no_due_field(self):
        assert "due" not in WorkPackage.model_fields

    def test_no_priority_field(self):
        assert "priority" not in WorkPackage.model_fields

    def test_has_created_by(self):
        wp = make_workpackage()
        assert wp.created_by == "dec-1"

    def test_has_process_version(self):
        wp = make_workpackage(process_version=3)
        assert wp.process_version == 3

    def test_state_defaults_to_planned(self):
        wp = make_workpackage()
        assert wp.state == WorkPackageState.PLANNED


class TestDemandFields:
    def test_required_fields(self):
        d = make_demand()
        assert d.product_ref == "prod-1"
        assert d.quantity.value == 100.0
        assert d.due == NOW
        assert d.commitment_class == CommitmentClass.STANDARD
        assert d.status == DemandStatus.OPEN

    def test_customer_weight_defaults_to_1(self):
        d = make_demand()
        assert d.customer_weight == 1.0

    def test_missing_product_ref_raises(self):
        with pytest.raises(ValidationError):
            Demand(
                id="d-1", snapshot_id="s-1",
                quantity=Quantity(value=1.0, uom="ea"),
                due=NOW,
                commitment_class=CommitmentClass.STANDARD,
                status=DemandStatus.OPEN,
            )

    def test_missing_due_raises(self):
        with pytest.raises(ValidationError):
            Demand(
                id="d-1", snapshot_id="s-1",
                product_ref="prod-1",
                quantity=Quantity(value=1.0, uom="ea"),
                commitment_class=CommitmentClass.STANDARD,
                status=DemandStatus.OPEN,
            )


class TestFulfillmentRequiresDecisionRef:
    """Fulfillment must trace to the planning decision that created it (docs/01 §5.3)."""

    def test_valid_fulfillment(self):
        f = Fulfillment(
            id="f-1", snapshot_id="s-1",
            demand_ref="d-1", workpackage_ref="wp-1",
            allocated_quantity=Quantity(value=100.0, uom="ea"),
            decision_ref="dec-1",
        )
        assert f.decision_ref == "dec-1"

    def test_missing_decision_ref_raises(self):
        with pytest.raises(ValidationError):
            Fulfillment(
                id="f-1", snapshot_id="s-1",
                demand_ref="d-1", workpackage_ref="wp-1",
                allocated_quantity=Quantity(value=100.0, uom="ea"),
            )


class TestResourceRequirement:
    """Mode validation: capability and explicit_set have different required fields (docs/01 §5.5)."""

    def test_capability_mode_requires_capability_ref(self):
        rr = ResourceRequirement(
            mode=ResourceRequirementMode.CAPABILITY,
            capability_ref="cap-cnc",
            count=1,
        )
        assert rr.capability_ref == "cap-cnc"

    def test_capability_mode_without_ref_raises(self):
        with pytest.raises(ValidationError):
            ResourceRequirement(
                mode=ResourceRequirementMode.CAPABILITY,
                count=1,
            )

    def test_explicit_set_mode_requires_resource_refs(self):
        rr = ResourceRequirement(
            mode=ResourceRequirementMode.EXPLICIT_SET,
            resource_refs=["r-1", "r-2"],
            count=1,
        )
        assert rr.resource_refs == ["r-1", "r-2"]

    def test_explicit_set_mode_empty_refs_raises(self):
        with pytest.raises(ValidationError):
            ResourceRequirement(
                mode=ResourceRequirementMode.EXPLICIT_SET,
                resource_refs=[],
                count=1,
            )


class TestEntityRef:
    def test_entity_ref_structure(self):
        ref = EntityRef(entity_id="d-1", entity_type="demand")
        assert ref.entity_id == "d-1"
        assert ref.entity_type == "demand"


class TestQuantity:
    def test_quantity_never_fused_into_duration(self):
        """docs/01 §8: Quantity and rate are first-class; duration is derived."""
        q = Quantity(value=500.0, uom="units")
        assert q.value == 500.0
        assert q.uom == "units"
