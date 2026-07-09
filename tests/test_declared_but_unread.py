"""Standing guard against the "declared-but-unread" bug species (docs/04
2026-07-12 amendment, item 4).

Third occurrence of this exact bug shape: an attribute is populated by the
adapter, carries a real ProvenanceSidecar, looks load-bearing — and no
downstream pipeline module ever reads it. Found twice before by accident
(Product.process_ref in IDSAdapter's write ordering; Operation.min_chunk /
OperationSpec.min_chunk in ids_adapter.py/planner.py). This test makes the
next occurrence a red test instead of a silent gap.

Method: run the Adapter against sample_data/, collect every (entity_type,
attribute) pair that receives a ProvenanceSidecar, and grep the four
scheduling-pipeline modules (validator, planner, solver_builder, extractor)
for a literal reference to the attribute name. A hit in any of the four is
a real consumer. A miss must be justified in _DORMANT_REGISTER, citing
where the field IS meaningful (a docs/05 catalog id, another module outside
the pipeline's scope, or a named future-work item) — never a bare skip.

This is a static, name-based check (grep, not AST/type analysis) — the same
method that found both prior bugs. False negatives are possible if an
attribute is read through an indirection this test can't see; the register
is where such cases get named and reasoned about, not silently passed.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mre.modules.adapter import Adapter
from mre.modules.snapshot_store import SnapshotStore
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.reporter import Reporter

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"

_UNIVERSAL = frozenset({"id", "snapshot_id", "external_refs"})

# The M1-adapter-written entity types (docs/01's canonical model inputs) —
# NOT the planner/solver-derived types (WorkPackage, Operation, Fulfillment,
# Schedule, Assignment, ServiceOutcome), which are produced downstream and
# are naturally consumed by construction.
_ADAPTER_ENTITY_TYPES = (
    "calendar", "capability", "constraint", "costmodel", "demand",
    "operationspec", "precedenceedge", "process", "product", "resource",
    "resourcepool",
)

# The scheduling pipeline proper (docs/03 M3-M7). Deliberately excludes
# explainer.py, conformance.py, config_loader.py, demo.py — a field consumed
# only by those is still "unread" by the pipeline that actually schedules.
_CONSUMER_MODULES = (
    "src/mre/modules/validator.py",
    "src/mre/modules/planner.py",
    "src/mre/modules/solver_builder.py",
    "src/mre/modules/extractor.py",
)

# (entity_type, attribute) -> justification, each citing where the field IS
# meaningful (a docs/05 catalog id, a named future-work item, or a module
# outside the four above) so "why is this here" never requires re-deriving
# the investigation. New entries MUST cite something concrete — never a
# bare "not used yet".
_DORMANT_REGISTER: dict[tuple[str, str], str] = {
    # Display/label metadata: rendered by explainer.py / dq_report.py for
    # human messages, not consulted by scheduling logic.
    ("capability", "name"): "display metadata — explainer.py/dq_report.py, not scheduling logic",
    ("capability", "description"): "display metadata — explainer.py/dq_report.py, not scheduling logic",
    ("product", "name"): "display metadata — explainer.py/dq_report.py, not scheduling logic",
    ("product", "unit_of_measure"): "display metadata — explainer.py/dq_report.py, not scheduling logic",

    # docs/05 B5 (MP, not yet PP): cumulative/pool secondary-resource
    # capacity is modeled and validated but not wired into solver_builder's
    # constraint construction (verified: solver_builder detects a pool only
    # via the presence of "concurrent_capacity", never reads "members";
    # single Resources are always treated as capacity=1, "capacity" unread).
    ("resource", "capacity"): "docs/05 B5 (MP not PP) — secondary-resource capacity not yet in solver_builder",
    ("resource", "pool_refs"): "docs/05 B5 (MP not PP) — pool membership (inverse of ResourcePool.members) not yet consumed by solver_builder",
    ("resourcepool", "members"): "docs/05 B5 (MP not PP) — pool membership not yet consumed by solver_builder",
    ("resourcepool", "limit_reason"): "docs/05 B5 (MP not PP) — informational only until pool capacity is wired",

    # Verified: solver_builder.py and extractor.py both price production
    # cost from CostModel.resource_rates (cost_model.get("resource_rates")),
    # never from Resource.cost_rate. The ERP-sourced cost_rate is currently
    # read only by conformance.py's certificate grading — a real duplicate-
    # source risk (the two could silently disagree), flagged in the
    # 2026-07-12 docs/04 amendment as a follow-up decision, not fixed here.
    ("resource", "cost_rate"): "docs/04 2026-07-12 amendment — duplicate cost source; CostModel.resource_rates is authoritative, flagged not fixed",

    # docs/05 D3 (MP not PP): yield_factor's validation half exists (bad-
    # yield finding per the doorway) but the "quantity model upstream-
    # inflates" half is not yet in planner.py's quantity computation.
    ("operationspec", "yield_factor"): "docs/05 D3 (MP not PP) — yield inflation not yet wired into planner's quantity model",

    # Soft-constraint penalty pricing is not yet built — docs/05 Category F
    # preamble ("anything expressing preference or price lives in CostModel;
    # Constraint is reserved for restrictions") + docs/01's hardness field.
    # Only hard frozen_assignment/pinned_window constraints are enforced
    # today (docs/05 A7, F1); lock targeting is read out of `parameters`
    # (demand_ref/sequence/resource_ref/start), not the canonical `subjects`
    # field, and `authority`/`expiry` are gate-checked at write time but not
    # read by solver_builder.
    ("constraint", "hardness"): "docs/05 Category F preamble — soft-constraint penalty pricing not yet built",
    ("constraint", "penalty_weight"): "docs/05 Category F preamble — soft-constraint penalty pricing not yet built",
    ("constraint", "subjects"): "docs/05 A7/F1 — lock targeting is read from parameters, not subjects, today",
    ("constraint", "authority"): "docs/05 A7 — mandatory at write time (gate-checked), not read by solver_builder",
    ("constraint", "expiry"): "docs/05 A7/F1 — constraint expiration not yet enforced by solver_builder",

    # Reserved for future customer- and version-specific features.
    ("demand", "customer_ref"): "reserved for customer-specific business rules (docs/07 post-pilot ATP/CTP)",
    ("process", "effective_from"): "reserved for multi-version/temporal process tracking; single-snapshot solves don't need it yet",
    ("costmodel", "effective_from"): "reserved for multi-version/temporal cost-model tracking; single-snapshot solves don't need it yet",
    ("costmodel", "inventory_carrying"): "reserved cost-model term, not yet priced into any objective",

    # CLAUDE.md next-work item (docs/04 2026-07-12 amendment, item 5):
    # overtime premium pricing. Expected to be removed from this register
    # once that work lands.
    ("costmodel", "overtime_premium"): "CLAUDE.md next-work item (overtime premium pricing) — not yet wired into solver_builder/extractor",
}


@pytest.fixture(scope="module")
def adapter_provenance():
    """Run the Adapter against sample_data; return {(entity_type, attr), ...}
    for every attribute that receives a ProvenanceSidecar."""
    tmp = Path(tempfile.mkdtemp())
    store = SnapshotStore(tmp / "snapshots")
    snap_id = "snap-declared-unread"
    a_rep = Reporter.begin(
        module=ModuleCode.M1, purpose="declared-but-unread guard",
        config={}, trigger="pytest", snapshot_id=snap_id, sink_dir=tmp / "runs",
    )
    Adapter(extract_dir=SAMPLE_DATA).run(snap_id, store, a_rep)
    a_rep.end(RunStatus.SUCCESS)

    reader = store.load_snapshot(snap_id)
    pairs: set[tuple[str, str]] = set()
    for entity_type in _ADAPTER_ENTITY_TYPES:
        for entity in reader.iter_entities(entity_type):
            for prov in reader.iter_provenance_for_entity(entity["id"]):
                attr = prov["attribute_name"]
                if attr in _UNIVERSAL:
                    continue
                pairs.add((entity_type, attr))
    return pairs


@pytest.fixture(scope="module")
def consumer_source():
    text = ""
    root = Path(__file__).parent.parent
    for rel in _CONSUMER_MODULES:
        text += (root / rel).read_text(encoding="utf-8")
    return text


def _has_consumer(attr: str, source: str) -> bool:
    return f'"{attr}"' in source or f"'{attr}'" in source


class TestDeclaredButUnreadGuard:
    def test_every_adapter_attribute_has_a_consumer_or_dormant_entry(
        self, adapter_provenance, consumer_source,
    ):
        unaccounted = []
        for entity_type, attr in sorted(adapter_provenance):
            if (entity_type, attr) in _DORMANT_REGISTER:
                continue
            if _has_consumer(attr, consumer_source):
                continue
            unaccounted.append((entity_type, attr))

        assert not unaccounted, (
            "declared-but-unread attribute(s) found — add a real consumer in "
            "validator/planner/solver_builder/extractor, or add a dormant-"
            "register entry citing why (see _DORMANT_REGISTER in this file): "
            f"{unaccounted}"
        )

    def test_dormant_register_entries_are_still_actually_dormant(
        self, adapter_provenance, consumer_source,
    ):
        """If a dormant-registered attribute gains a real consumer, the
        register entry is stale and should be removed — catches drift in
        the other direction."""
        stale = [
            (etype, attr) for (etype, attr) in _DORMANT_REGISTER
            if (etype, attr) in adapter_provenance and _has_consumer(attr, consumer_source)
        ]
        assert not stale, (
            f"dormant-register entries now have a real consumer — remove them: {stale}"
        )

    def test_dormant_register_only_covers_real_attributes(self, adapter_provenance):
        """Guards against a stale register entry citing an attribute that no
        longer exists (renamed/removed field)."""
        ghost = [
            pair for pair in _DORMANT_REGISTER
            if pair not in adapter_provenance
        ]
        assert not ghost, f"dormant-register entries for attributes that no longer exist: {ghost}"
