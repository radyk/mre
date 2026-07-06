"""Provenance sidecar structures for the canonical manufacturing model.

Architecture: clean entity + sidecar (docs/01 §7).
Keyed by entity_id + attribute_name + snapshot_id.
Four provenance classes with class-specific payloads.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel

from mre.contracts.vocabularies import ProvenanceClass


class InputRef(BaseModel):
    """One input in a derivation chain: which attribute on which entity."""
    entity_id: str
    attribute_name: str
    snapshot_id: str


class ObservedProvenance(BaseModel):
    """Read from the source system."""
    provenance_class: Literal[ProvenanceClass.OBSERVED] = ProvenanceClass.OBSERVED
    source_system: str
    source_field: str
    extract_ref: str


class DerivedProvenance(BaseModel):
    """Computed by a formula. Carries a walkable derivation chain."""
    provenance_class: Literal[ProvenanceClass.DERIVED] = ProvenanceClass.DERIVED
    formula_id: str
    input_refs: list[InputRef]


class DefaultedProvenance(BaseModel):
    """Supplied by a policy in the absence of data."""
    provenance_class: Literal[ProvenanceClass.DEFAULTED] = ProvenanceClass.DEFAULTED
    policy: str


class SynthesizedProvenance(BaseModel):
    """Generated (test data, simulation). Loud NOT-REAL marker — must never
    masquerade as observed truth."""
    provenance_class: Literal[ProvenanceClass.SYNTHESIZED] = ProvenanceClass.SYNTHESIZED
    generator_id: str
    not_real: Literal[True] = True


ProvenancePayload = Annotated[
    Union[ObservedProvenance, DerivedProvenance, DefaultedProvenance, SynthesizedProvenance],
    "provenance_payload",
]


class ProvenanceSidecar(BaseModel):
    """One sidecar record per (entity_id, attribute_name, snapshot_id) triple.

    The provenance_class in the top-level matches the payload's own class field
    for fast filtering without deserialising the payload.
    """
    entity_id: str
    attribute_name: str
    snapshot_id: str
    provenance_class: ProvenanceClass
    payload: ProvenancePayload
