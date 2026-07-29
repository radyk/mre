"""Capability answers ground in docs/05, or are refused (Session 4B.15 Item 5).

Written from the session brief's acceptance clause 6: "can two machines share
one operator" now answers correctly and AGREES WITH THE BLOCKER ANALYSIS'S OWN
not-weighed list. That agreement is the point — both sentences shipped in one
session, on one board, contradicting each other.
"""
from __future__ import annotations

import pytest

from mre.modules.blocker_analysis import UNCOMPUTED_FAMILIES
from mre.modules.capability_answer import LEAD, answer, render
from mre.modules.constraint_catalog import (
    Register,
    Status,
    Verdict,
    load_catalog,
    parse_catalog,
    topics_for,
)


@pytest.fixture(scope="module")
def catalog():
    cat = load_catalog()
    assert cat.items, "the docs/05 catalog must parse into records"
    return cat


class TestCatalogParse:
    """docs/05 §0 says the catalog is 'structured records first; prose is
    rendered from them'. These assert the records really are recovered."""

    def test_every_category_is_represented(self, catalog):
        ids = {i.item_id for i in catalog.items}
        for expected in ("A1", "A4", "B1", "B2", "B3", "B5", "B9", "B10",
                         "C1", "C3", "C4", "D1", "D2", "F1", "F3", "H1"):
            assert expected in ids, f"catalog item {expected} did not parse"

    def test_the_six_locked_rulings_parse(self, catalog):
        got = {r.ruling_id for r in catalog.rulings}
        assert got == {"R-B3", "R-C3", "R-B7/B8", "R-A2/A3", "R-A4", "R-Dwell"}

    def test_global_exclusions_carry_their_limits(self, catalog):
        names = {e.name for e in catalog.exclusions}
        assert "Individual operator rostering" in names
        rost = next(e for e in catalog.exclusions
                    if e.name == "Individual operator rostering")
        assert "pools" in rost.text and "named-person" in rost.text

    def test_verdict_and_status_are_separate_facts(self, catalog):
        """The whole reason a nine-entry authored registry could not answer the
        operator question: B3 is IN-CORE and NOT pipeline-proven at once."""
        b3 = catalog.by_id("B3")
        assert b3.verdict is Verdict.CORE
        assert b3.status is Status.MODEL_PROVEN
        assert b3.register is Register.MODELED_UNPROVEN
        assert not b3.declarable

    def test_a_mixed_status_is_neither_token(self, catalog):
        """B7/B8 reads 'PP (single-attr) / UI (multi-attr)'. Flattening it to PP
        overstates; flattening it to UI would say setup families are unbuilt
        when setup_transitions.csv is pipeline-proven."""
        item = catalog.by_id("B7/B8")
        assert item.mixed_status
        assert item.register is Register.PARTIAL
        assert "single-attr" in item.status_raw and "multi-attr" in item.status_raw

    def test_a_section_8_doorway_is_not_declarable(self, catalog):
        """docs/06 §8 is the process for ADDING a doorway when a plant demands
        one — not a section a planner can go and fill in."""
        assert "§8" in catalog.by_id("B3").doorway
        assert catalog.by_id("B3").real_doorways == []
        assert catalog.by_id("C1").real_doorways  # a real § doorway

    def test_out_items_carry_their_approximation_guidance(self, catalog):
        """An exclusion is a product statement, not a gap — the guidance must
        travel with the No."""
        b9 = catalog.by_id("B9")
        assert b9.verdict is Verdict.OUT
        assert "cumulative resource" in b9.approximation
        assert "bin-packing-in-time" in b9.approximation

    def test_parse_is_pure(self):
        assert parse_catalog("") .items == ()


class TestTheOperatorSpecimen:
    """THE MEASURED FAILURE: a confident YES describing ALTERNATES."""

    @pytest.fixture(scope="class")
    def ans(self):
        a = answer("can two machines share one operator")
        assert a is not None, "the catalog must ground this question"
        return a

    def test_it_grounds_in_B3_and_B5_not_B2(self, ans):
        cited = " ".join(ans.citations)
        assert "B3" in cited and "B5" in cited
        assert "B2" not in cited, (
            "alternates (B2) is one operation eligible on several machines — a "
            "different mechanism, and the one the wrong answer described")

    def test_the_verb_is_the_answer(self, ans):
        assert ans.register is Register.MODELED_UNPROVEN
        assert ans.lead.startswith("Not today")

    def test_it_agrees_with_the_blocker_analysis(self, ans):
        """Both surfaces shipped in ONE session saying opposite things. The
        agreement is asserted, not hoped for."""
        families = dict(UNCOMPUTED_FAMILIES)
        assert "B3/B5" in families
        assert ans.not_weighed, "the answer must say what the scheduler ignores"
        assert families["B3/B5"] in ans.not_weighed[0]

    def test_it_names_the_operators_are_pools_ruling(self, ans):
        assert any("R-B3" in line for line in ans.ruling_lines)

    def test_it_offers_no_how_to(self, ans):
        """Coaching a planner to fill in a column for a capability that is
        model-proven only is exactly how they author data that is silently
        ignored."""
        assert not ans.how

    def test_the_rendering_says_all_of_it(self, ans):
        text = render(ans)
        assert "Not today" in text
        assert "B3" in text and "B5" in text
        assert "operator pools" in text
        assert "docs/05" in text

    def test_the_not_weighed_reason_is_stated_once(self, ans):
        """B3 and B5 are two catalog rows of ONE blocker-analysis family;
        printing its sentence twice reads as two separate gaps."""
        assert len(ans.not_weighed) == 1


class TestOtherRegisters:
    @pytest.mark.parametrize("question,register,item", [
        ("can two orders share an oven cycle", Register.EXCLUDED, "B9"),
        ("can an operation run on more than one machine", Register.PROVEN, "B2"),
        ("can a job span downtime", Register.PROVEN, "C3"),
        ("can it handle sequence dependent changeovers", Register.PARTIAL,
         "B7/B8"),
        ("can I restrict an operation to the day shift only",
         Register.MODELED_UNPROVEN, "C4"),
    ])
    def test_register_and_item(self, question, register, item):
        a = answer(question)
        assert a is not None, f"no grounding for {question!r}"
        assert a.register is register
        assert any(item in c for c in a.citations), (
            f"{question!r} grounded in {a.citations} rather than {item}")

    def test_every_register_has_an_authored_lead(self):
        for reg in Register:
            assert LEAD[reg].strip()

    def test_a_day_shift_question_is_C4_not_the_plant_calendar(self):
        """The ordering of the topic map is load-bearing: with `calendars`
        first this answered 'Yes, proven end to end' about C1/C2 — the wrong
        catalog item, and the optimistic direction to be wrong in."""
        a = answer("can I restrict an operation to the day shift only")
        assert not a.how, "C4 has no doorway; there is nothing to coach"
        assert "C4" in " ".join(a.citations)


class TestRefusal:
    """A capability claim grounds in docs/05 OR IS REFUSED. None is the refusal
    signal, and it is the honest floor rather than a failure."""

    @pytest.mark.parametrize("question", [
        "why is ORD-000013 late",
        "what is running on PAINT-01",
        "how many orders are late",
        "",
    ])
    def test_non_capability_questions_do_not_ground(self, question):
        assert answer(question) is None

    def test_an_unknown_capability_does_not_ground(self):
        assert topics_for("can it predict the weather") == []
        assert answer("can it predict the weather") is None
