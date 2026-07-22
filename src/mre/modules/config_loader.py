"""Config loader — reads CostModel and setup Constraint from JSON config files.

These are policy documents (not ERP extracts), so all provenance is DEFAULTED
with a policy payload naming the file and version.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mre.contracts.entities import Constraint, CostModel, SetupCostBasis, TardinessWeights
from mre.contracts.provenance import DefaultedProvenance, ProvenanceSidecar, ProvenanceClass
from mre.contracts.vocabularies import ConstraintHardness, ConstraintProvenance, ConstraintType

UTC = timezone.utc


def _defaulted(entity_id: str, attr: str, snapshot_id: str, policy: str) -> ProvenanceSidecar:
    return ProvenanceSidecar(
        entity_id=entity_id,
        attribute_name=attr,
        snapshot_id=snapshot_id,
        provenance_class=ProvenanceClass.DEFAULTED,
        payload=DefaultedProvenance(policy=policy),
    )


def load_cost_model(
    path: Path,
    snapshot_id: str,
    identity_map=None,
) -> tuple[CostModel, list[ProvenanceSidecar], list[str]]:
    """Read costmodel.json and return (CostModel, provenance, unresolved_keys).

    If identity_map is provided, resource_rates keys are translated from external
    machine IDs to canonical UUIDs. unresolved_keys lists any key that couldn't
    be mapped — the caller must emit findings for these (silent zero-defaults are
    forbidden per the no-silent-defaults rule).
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    version = raw.get("version", 1)
    eff_str = raw.get("effective_from")
    effective_from = (
        datetime.fromisoformat(eff_str).replace(tzinfo=UTC) if eff_str else None
    )

    setup_raw = raw.get("setup_cost_basis", {})
    tard_raw  = raw.get("tardiness_weights", {})

    cm_id = str(uuid.uuid5(
        uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        f"costmodel:{Path(path).name}:v{version}",
    ))
    policy_label = f"costmodel.json v{version}"

    # Translate external machine IDs → canonical UUIDs so the solver and
    # extractor (which only know canonical IDs) can look up rates correctly.
    raw_rates: dict = raw.get("resource_rates", {})
    unresolved_keys: list[str] = []
    if identity_map is not None:
        resolved_rates: dict[str, float] = {}
        for ext_key, rate in raw_rates.items():
            canonical = identity_map.resolve("ERP", "machine_id", ext_key)
            if canonical is None:
                unresolved_keys.append(ext_key)
            else:
                resolved_rates[canonical] = float(rate)
        resource_rates = resolved_rates
    else:
        resource_rates = {k: float(v) for k, v in raw_rates.items()}

    cm = CostModel(
        id=cm_id,
        snapshot_id=snapshot_id,
        version=version,
        effective_from=effective_from,
        resource_rates=resource_rates,
        setup_cost_basis=SetupCostBasis(
            fixed_per_setup=setup_raw.get("fixed_per_setup", 0.0),
            scrap_cost_per_unit=setup_raw.get("scrap_cost_per_unit", 0.0),
        ),
        tardiness_weights=TardinessWeights(
            base_weight=tard_raw.get("base_weight", 1.0),
            commitment_class_multipliers=tard_raw.get("commitment_class_multipliers", {}),
        ),
        overtime_premium=raw.get("overtime_premium", 0.0),
        inventory_carrying=raw.get("inventory_carrying", 0.0),
        earliness_value=raw.get("earliness_value", 0.0),   # R-SC3
    )

    attrs = [
        "version", "effective_from", "resource_rates",
        "setup_cost_basis", "tardiness_weights",
        "overtime_premium", "inventory_carrying", "earliness_value",
    ]
    provenance = [_defaulted(cm_id, a, snapshot_id, policy_label) for a in attrs]
    return cm, provenance, unresolved_keys


def load_setup_constraint(
    path: Path,
    snapshot_id: str,
    costmodel_id: str,
) -> tuple[Constraint, list[ProvenanceSidecar], dict[str, dict[str, int]]]:
    """Read setup_transitions.json and return (Constraint, provenance, matrix dict).

    Returns the raw transition matrix as a nested dict for use by the Solver Builder.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    version = raw.get("version", "1.0")
    policy_label = f"setup_transitions.json v{version}"

    # Parse flat "A->B: minutes" into nested dict
    matrix: dict[str, dict[str, int]] = {}
    for key, minutes in raw.get("transition_minutes", {}).items():
        from_fam, to_fam = key.split("->")
        matrix.setdefault(from_fam, {})[to_fam] = int(minutes)

    con_id = str(uuid.uuid5(
        uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
        f"constraint:setup_transition:{Path(path).name}:v{version}",
    ))

    con = Constraint(
        id=con_id,
        snapshot_id=snapshot_id,
        constraint_type=ConstraintType.SETUP_TRANSITION,
        subjects=[costmodel_id],
        parameters={
            "version": version,
            "families": raw.get("families", []),
            "transition_minutes": raw.get("transition_minutes", {}),
        },
        provenance_class=ConstraintProvenance.POLICY,
        authority="setup_transitions.json",
        hardness=ConstraintHardness.SOFT,
        penalty_weight=1.0,
    )

    attrs = [
        "constraint_type", "subjects", "parameters",
        "provenance_class", "authority", "hardness",
        "penalty_weight", "expiry",
    ]
    provenance = [_defaulted(con_id, a, snapshot_id, policy_label) for a in attrs]
    return con, provenance, matrix
