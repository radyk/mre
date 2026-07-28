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
    # The shared eligibility narrow waist (Session 4.0b): solver_builder's
    # capability resolution + calendar flatten moved here, so it now consumes
    # calendar base_pattern / horizon_resolved on the solver's behalf.
    "src/mre/modules/eligibility.py",
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

    # Audited end-to-end (docs/04 2026-07-12 rates-audit amendment): the
    # value IS consumed — every adapter folds it into CostModel.resource_rates
    # (docs/06 §5.5 precedence: default < resources.csv cost_rate <
    # refinements), which solver_builder/extractor price from. The fold is
    # adapter-side by design (the builder prices only from CostModel), so no
    # literal read appears in the four pipeline modules and this grep can't
    # see it. The former duplicate-source risk is closed: Resource.cost_rate
    # now carries the same effective $/min value as its CostModel entry
    # (single-source invariant, tests/test_resource_rates.py).
    ("resource", "cost_rate"): "consumed via adapter fold into CostModel.resource_rates (docs/06 §5.5); equality invariant tested in test_resource_rates.py",

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
    # R-SC2 coarse-zone amendment clause 4 (Session 4B.6): these two ARE
    # consumed — by coarse_horizon.CoarseCoefficients.from_cost_model — but by
    # design NOT by any module in _CONSUMER_MODULES. Clause (4) is exactly the
    # rule that COARSE NEVER CONSTRAINS FINE: the far-horizon look-ahead reads
    # them, the window solve re-decides from scratch and must never see them.
    # Their appearance in the fine pipeline would be the defect, not their
    # absence from it.
    ("costmodel", "coarse_bucket_days"): "R-SC2 coarse-zone clause 4 — read by coarse_horizon.CoarseCoefficients.from_cost_model; the fine pipeline must NOT read it",
    ("costmodel", "coarse_capacity_derate"): "R-SC2 coarse-zone clause 4 — rho, read by coarse_horizon.CoarseCoefficients.from_cost_model; the fine pipeline must NOT read it",

    # SESSION 4B.8 CU4(b) — earliness_value is DELIBERATELY dormant to the
    # scheduling pipeline, and this entry is how that was resolved rather than
    # by widening the guard.
    #
    # It was never a "not used yet" field. Until 4B.7 it was a PRICE: R-SC3(2)
    # put it in stage 1's objective, and the extractor read it to attribute a
    # dearer-but-earlier placement to EARLINESS_PREFERENCE. The R-SC3 AMENDMENT
    # (docs/04, 2026-07-27) retired the price — measured at +73.20% of ledger
    # total at 40 orders and +97.61% at 120 — so no solver, objective, cap or
    # cost ledger sees it. 4B.8 CU4 then stopped the extractor's attribution,
    # which named a mechanism that no longer exists. That removed the LAST
    # literal read in _CONSUMER_MODULES.
    #
    # NB the guard was green before this entry existed, but FOR THE WRONG
    # REASON (flagged 4B.7): its one consumer was the dead attribution. A guard
    # kept green by a defect is not a guard, so the honest resolution is to name
    # the dormancy here — not to relax the check.
    #
    # The value IS still consumed, outside the scheduling pipeline: as a
    # REPORTING rate by rolling_horizon._earliness_rate /
    # earliness_tiebreak_report, which values the start-minutes stage 2
    # recovered on its own labelled line (in_ledger: False). It is also
    # gate-checked (conformance rule #35, ids.earliness_value_sane) and offered
    # by capabilities.py. None of those are scheduling modules, which is
    # precisely the point.
    ("costmodel", "earliness_value"): "R-SC3 AMENDMENT (docs/04 2026-07-27) — the price is RETIRED and 4B.8 CU4 made the EARLINESS_PREFERENCE attribution dormant; survives as a REPORTING rate in rolling_horizon.earliness_tiebreak_report (in_ledger: False), never read by the scheduling pipeline. docs/07 §5a.20 owns the vocabulary migration",
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
    # Resolve each module's source via the IMPORTED package, not a hardcoded
    # "src/" path: the installed wheel (the shipped-image layout the CI runs
    # against) has the source under site-packages/mre, not src/. In a source
    # checkout mre.__file__ still points into src/mre, so this reads the same
    # files either way — and it tests the source that actually ships.
    import mre
    pkg = Path(mre.__file__).resolve().parent               # .../mre
    text = ""
    for rel in _CONSUMER_MODULES:
        sub = rel.split("src/mre/", 1)[-1]                  # -> "modules/validator.py"
        text += (pkg / sub).read_text(encoding="utf-8")
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
