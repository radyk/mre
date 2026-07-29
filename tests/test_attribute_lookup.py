"""ATTRIBUTE LOOKUP — any declared field, verbatim, with its source
(Session 4B.15 Item 3).

The specimen is the pinned world's own ORD-000013 op20 (rolling-c362baa4-1b0),
transcribed as plain data — the same discipline ``test_blocker_analysis`` uses —
so these are fast, offline, and independent of whether that run directory still
exists. Every figure is the one measured from its PERSISTED snapshot, never a
re-solve (R-AI4).

THE MEASURED FAILURE: "is ORD-000013 op20 splittable" returned capability
documentation with a scold, and "how long does op20 take" returned the order
card — while the blocker analysis quoted BOTH answers one exchange later off the
same snapshot.
"""
from __future__ import annotations

import pytest

from mre.modules.attribute_lookup import (
    declared_fields, fields_named, human_minutes, iso_minutes, lookup,
    op_seq_in, render, render_value,
)

OP_ID = "op20-id"
SPEC_ID = "spec20-id"
DEMAND_ID = "dem13-id"
RES_ID = "paint01-id"

#: ORD-000013 op20 exactly as the snapshot records it.
OPERATION = {
    "id": OP_ID, "spec_ref": SPEC_ID, "workpackage_ref": "wp13",
    "sequence": 20, "setup_family": "PAINT_RED", "setup_duration": "PT20M",
    "run_duration": "PT6H51M", "splittable": False, "min_chunk": None,
    "wip_status": None, "resource_requirements": [{"mode": "explicit_set"}],
}
SPEC = {
    "id": SPEC_ID, "sequence": 20, "setup_family": "PAINT_RED",
    "base_setup": "PT20M", "run_rate": "PT3M", "splittable": False,
    "min_chunk": None, "yield_factor": 1.0,
    "resource_requirements": [{"mode": "explicit_set"}],
}
DEMAND = {
    "id": DEMAND_ID, "due": "2026-01-15T23:59:59Z",
    "earliest_start": "2026-01-05T00:00:00Z", "quantity": {"value": 137,
                                                            "unit": "each"},
    "commitment_class": "standard", "status": "open",
    "external_refs": [{"type": "order_id", "value": "ORD-000013"}],
}
RESOURCE = {
    "id": RES_ID, "capacity": 1, "resource_type": "machine",
    "cost_rate": 62.5, "capabilities": ["PAINT"], "calendar_ref": "cal-1",
    "external_refs": [{"type": "resource_id", "value": "PAINT-01"}],
}

#: The provenance sidecar. The chain that matters: the OPERATION's `splittable`
#: is `derived` with no source, and the observed value lives on the SPEC citing
#: the submission column.
PROVENANCE = {
    (OP_ID, "splittable"): ("derived", {}),
    (OP_ID, "min_chunk"): ("derived", {}),
    (OP_ID, "setup_family"): ("derived", {}),
    (OP_ID, "run_duration"): ("derived", {}),
    (OP_ID, "setup_duration"): ("derived", {}),
    (OP_ID, "resource_requirements"): ("derived", {}),
    (SPEC_ID, "splittable"): ("observed", {"source_system": "IDS",
                                           "source_field": "splittable"}),
    (SPEC_ID, "min_chunk"): ("observed", {"source_system": "IDS",
                                          "source_field": "min_chunk_minutes"}),
    (SPEC_ID, "setup_family"): ("observed", {"source_system": "IDS",
                                             "source_field": "setup_family"}),
    (SPEC_ID, "run_rate"): ("derived", {}),
    (SPEC_ID, "base_setup"): ("derived", {}),
    (DEMAND_ID, "due"): ("observed", {"source_system": "IDS",
                                      "source_field": "due_date"}),
    (RES_ID, "capacity"): ("observed", {"source_system": "IDS",
                                        "source_field": "parallel_units"}),
}


class FakeReader:
    def get_entity(self, eid):
        return {OP_ID: OPERATION, SPEC_ID: SPEC, DEMAND_ID: DEMAND,
                RES_ID: RESOURCE}.get(eid)

    def iter_entities(self, etype):
        return {"demand": [DEMAND], "resource": [RESOURCE],
                "operation": [OPERATION]}.get(etype, [])

    def get_provenance(self, eid, attr):
        hit = PROVENANCE.get((eid, attr))
        if hit is None:
            return None
        return {"provenance_class": hit[0], "payload": {**hit[1],
                                                        "provenance_class": hit[0]}}


class FakeExplainer:
    _reader = FakeReader()

    def _load_enriched_assignments(self):
        return [{
            "operation_ref": OP_ID, "op_seq": 20, "machine": "PAINT-01",
            "work_orders": ["ORD-000013"], "run_min": 431.0, "span_min": 431.0,
            "setup_duration": "PT20M", "splittable": False, "min_chunk": None,
        }]

    def resolve_machine_value(self, raw):
        return "PAINT-01" if "paint" in (raw or "").lower() else None

    def _eligible_machine_names(self, _op_id):
        return ["PAINT-01"]


@pytest.fixture
def ex():
    return FakeExplainer()


class TestTheAcceptanceSpecimen:
    """Acceptance clause 4: splittable, min_chunk and duration for ORD-000013
    op20, verbatim, with source."""

    def test_splittable(self, ex):
        ans = lookup(ex, "is ORD-000013 op20 splittable", order="ORD-000013")
        assert ans is not None and ans.answered
        f = next(f for f in ans.facts if f.field_name == "splittable")
        assert f.rendered == "no"
        assert f.declared is True
        assert f.provenance_class == "observed"
        assert "splittable" in f.source
        assert f.ids_ref == "§5.3"
        assert "routing template" in f.note

    def test_min_chunk_is_not_declared_and_says_so(self, ex):
        """NOT DECLARED and DECLARED-AS-ZERO are different facts. Rendering an
        absent floor as "none" or "0" would be the same class of lie the
        provenance rules exist to prevent."""
        ans = lookup(ex, "what is the minimum chunk on ORD-000013 op20",
                     order="ORD-000013")
        f = next(f for f in ans.facts if f.field_name == "min_chunk")
        assert f.rendered == "not declared"
        assert f.empty is True
        assert f.declared is False
        text = render(ans)
        assert "not declared" in text
        # and it must NOT claim the value was declared in the submission
        assert "min_chunk: not declared — declared in your submission" not in text

    def test_duration_states_three_labelled_numbers(self, ex):
        """4B.14 made run-time vs elapsed-span a contract field because
        conflating them is a confusion the product used to create."""
        ans = lookup(ex, "how long does op20 take", order="ORD-000013")
        text = render(ans)
        assert "run time" in text
        assert "working time" in text
        assert "elapsed span" in text

    def test_the_working_time_arithmetic_is_431_not_451(self, ex):
        """THE SOLVER MODELS SETUP AND RUN AS ONE CONTIGUOUS BLOCK, so the
        chunk total ALREADY INCLUDES setup. 20m setup + 6h51m run = 431 working
        minutes — which is exactly what the chunks total. Adding setup to the
        chunk total double-counts and yields 451, a number nothing supports."""
        ans = lookup(ex, "how long does op20 take", order="ORD-000013")
        text = render(ans)
        assert "431 minutes" in text
        assert "451" not in text

    def test_the_figures_match_the_blocker_analysis(self, ex):
        """431 is the figure 4B.14's chunk-fit verdict turns on. If these two
        surfaces ever disagree, one of them is lying about the same snapshot."""
        ans = lookup(ex, "how long does op20 take", order="ORD-000013")
        working = next(p for p in ans.placement if p.startswith("working time"))
        assert "7h 11m" in working and "431" in working


class TestBreadthNotEnumeration:
    """The rule is 'ANY declared field on ANY entity', so the vocabulary is
    built by reflection over the canonical models."""

    def test_fields_come_from_the_entity_models(self):
        op = declared_fields("operation")
        assert "splittable" in op and "min_chunk" in op and "run_duration" in op
        assert "id" not in op and "snapshot_id" not in op
        assert "due" in declared_fields("demand")
        assert "capacity" in declared_fields("resource")

    def test_a_bare_field_name_resolves_without_an_alias(self):
        """What keeps the rule broad rather than an enumeration: a field with no
        authored alias is still askable by its own name."""
        hits = fields_named("what is the yield_factor", ("operationspec",))
        assert any(h.field_name == "yield_factor" for h in hits)

    def test_order_level_fields_resolve_on_the_demand(self, ex):
        ans = lookup(ex, "when is ORD-000013 due", order="ORD-000013")
        f = next(f for f in ans.facts if f.field_name == "due")
        assert "2026-01-15" in f.rendered
        assert f.provenance_class == "observed"

    def test_machine_fields_resolve_on_the_resource(self, ex):
        ans = lookup(ex, "what is the capacity of PAINT-01", machine="PAINT-01")
        assert ans is not None
        f = next(f for f in ans.facts if f.field_name == "capacity")
        assert f.rendered == "1"
        assert "parallel_units" in f.source

    def test_the_eligible_set_is_resolved_to_machine_names(self, ex):
        """"1 entry" is not an answer to "which machines can run it"."""
        ans = lookup(ex, "which machines can run ORD-000013 op20",
                     order="ORD-000013")
        f = next(f for f in ans.facts
                 if f.field_name == "resource_requirements")
        assert f.rendered == "PAINT-01"

    def test_setup_family_does_not_also_answer_setup_time(self, ex):
        """A bare "setup" trigger on the duration alias made "what is the setup
        family" answer two questions, one of them unasked."""
        ans = lookup(ex, "what is the setup family on ORD-000013 op20",
                     order="ORD-000013")
        assert {f.field_name for f in ans.facts} == {"setup_family"}
        assert not ans.placement


class TestCorrectionInheritsThePredicate:
    """SPECIMEN: "no, I mean for ORD-000013 specifically" names no field — it
    re-binds the subject and inherits the predicate. Answering it as though
    nothing was asked is how an explicit correction got the same wrong answer a
    second time."""

    def test_the_field_carries_over(self, ex):
        ans = lookup(ex, "no, I mean for ORD-000013 specifically",
                     order="ORD-000013",
                     prior_question="can I make just this one job splittable")
        assert ans is not None and ans.answered
        assert any(f.field_name == "splittable" for f in ans.facts)
        assert ans.inherited_field is True

    def test_the_carry_over_is_said_out_loud(self, ex):
        ans = lookup(ex, "no, I mean for ORD-000013 specifically",
                     order="ORD-000013",
                     prior_question="is that one splittable")
        assert "same field you just asked about" in render(ans)

    def test_a_question_with_its_own_field_ignores_the_prior(self, ex):
        ans = lookup(ex, "when is ORD-000013 due", order="ORD-000013",
                     prior_question="is it splittable")
        assert ans.inherited_field is False
        assert {f.field_name for f in ans.facts} == {"due"}

    def test_no_field_anywhere_returns_none(self, ex):
        assert lookup(ex, "tell me about it", order="ORD-000013") is None


class TestFormatting:
    @pytest.mark.parametrize("iso,mins", [
        ("PT6H51M", 411.0), ("PT20M", 20.0), ("PT1H", 60.0), ("P1D", 1440.0),
        ("not a duration", None), (None, None),
    ])
    def test_iso_minutes(self, iso, mins):
        assert iso_minutes(iso) == mins

    def test_human_minutes(self):
        assert human_minutes(431) == "7h 11m (431 minutes)"
        assert human_minutes(20) == "20 minutes"

    def test_none_renders_as_not_declared(self):
        assert render_value(None) == "not declared"

    def test_booleans_render_as_yes_no(self):
        assert render_value(False) == "no"
        assert render_value(True) == "yes"

    @pytest.mark.parametrize("q,seq", [
        ("is ORD-000013 op20 splittable", 20), ("operation 30", 30),
        ("op_10 duration", 10), ("why is it late", None),
    ])
    def test_op_seq_in(self, q, seq):
        assert op_seq_in(q) == seq
