"""THE OPENER (Session 4B.16 Item 2) — what on this board should I be looking
at, ranked by consequence, every line carrying its number.

Two halves, tested separately because they fail separately: the pure ranking and
copy module (``board_opener``), and the Explainer's extraction from a document
plus this run's evidence. The pure half is where the RULES live — which band an
item sits in, when a busy machine is a finding rather than an observation, what
is said when there is nothing to say — and it is asserted directly rather than
through a rendered paragraph, so a copy edit cannot quietly change a ruling.
"""
from __future__ import annotations

import pytest

from mre.modules.board_opener import (
    BAND_CLEAN,
    BAND_MONEY,
    BAND_SLIP,
    BAND_STRUCTURE,
    build,
)
from mre.modules.cost_proof import CostProof
from mre.modules.explainer import Explainer
from mre.modules.renderers import TemplateRenderer

from tests.test_why_here_route import _Index as _BareIndex, _Store, _world


class _Index(_BareIndex):
    """The 4B.14 double plus the three readers the opener consults: findings,
    the solve event behind the cost proof, and the M6 run that dates it."""

    def all_findings(self):
        return []

    def runs(self):
        return []

    def events(self):
        return []

PROVED = CostProof(status="OPTIMAL", objective=1000.0)
UNPROVED = CostProof(status="FEASIBLE", gap=0.569, objective=1000.0)
LEDGER = {"total": 42_895.47, "tardiness": 20_701.25}


def _keys(opener) -> list[str]:
    return [i.key for i in opener.items]


def _item(opener, key):
    return next(i for i in opener.items if i.key == key)


# ---------------------------------------------------------------------------
# The ranking rule
# ---------------------------------------------------------------------------

class TestRanking:

    def test_money_leads_and_the_larger_money_leads_it(self):
        """RANK BY CONSEQUENCE, not category. The unproved gap is priced against
        the ledger (42,895.47 x 56.9% = 24,414) and the late orders cost
        20,701 — so the gap leads, and it leads because it is bigger, not
        because proof is a more important kind of thing."""
        o = build(proof=UNPROVED, cost=LEDGER,
                  late=[{"order": "ORD-01", "lateness_min": 100}])
        assert _keys(o)[:2] == ["proof", "late"]
        assert _item(o, "proof").amount > _item(o, "late").amount

    def test_and_it_reverses_when_the_lateness_costs_more(self):
        o = build(proof=CostProof(status="FEASIBLE", gap=0.01),
                  cost=LEDGER, late=[{"order": "ORD-01", "lateness_min": 100}])
        assert _keys(o)[:2] == ["late", "proof"]

    def test_an_unpriced_item_never_outranks_a_priced_one_in_its_band(self):
        """Not because it matters less, but because it is the only one of the
        two whose size is known."""
        o = build(proof=CostProof(status="FEASIBLE", gap=None),
                  cost=LEDGER, late=[{"order": "ORD-01", "lateness_min": 100}])
        assert _keys(o)[:2] == ["late", "proof"]
        assert _item(o, "proof").amount is None

    def test_the_bands_are_money_then_slip_then_structure_then_clean(self):
        o = build(proof=UNPROVED, cost=LEDGER,
                  late=[{"order": "ORD-01", "lateness_min": 100}],
                  at_risk=[{"order": "ORD-02", "slack_min": 40,
                            "longest_op_min": 300}],
                  certificate={"grade": "CONDITIONAL", "count": 2,
                               "proceeded": 2},
                  derate={"value": 1.0, "provenance": "defaulted"})
        assert [i.band for i in o.items] == sorted(i.band for i in o.items)
        assert _item(o, "late").band == BAND_MONEY
        assert _item(o, "at_risk").band == BAND_SLIP
        assert _item(o, "certificate").band == BAND_STRUCTURE

    def test_a_clean_board_gets_a_real_answer_not_a_silence(self):
        """"Three things, and none of them are on fire" MUST be reachable."""
        o = build(proof=PROVED, cost=LEDGER, late=[],
                  certificate={"grade": "ACCEPTED", "count": 0})
        assert o.clean is True
        assert o.worries == ()
        assert {i.key for i in o.items} == {"proof", "late", "certificate"}
        assert all(i.band == BAND_CLEAN for i in o.items)

    def test_what_the_document_does_not_support_is_reported(self):
        o = build(unavailable=[("work beyond the horizon", "monolithic run")])
        assert o.unavailable == (("work beyond the horizon", "monolithic run"),)


# ---------------------------------------------------------------------------
# The items
# ---------------------------------------------------------------------------

class TestProof:

    def test_proved_is_REPORTED_as_reassurance_never_left_silent(self):
        o = build(proof=PROVED, cost=LEDGER)
        item = _item(o, "proof")
        assert item.clean and item.band == BAND_CLEAN
        assert "PROVED" in item.headline

    def test_an_open_gap_is_priced_against_the_ledger_as_an_UPPER_limit(self):
        item = _item(build(proof=UNPROVED, cost=LEDGER), "proof")
        assert item.amount == pytest.approx(42_895.47 * 0.569)
        assert "56.9%" in item.headline
        body = " ".join(item.detail)
        assert "24,407" in body or "24,4" in body
        assert "not a saving anyone has found" in body

    def test_a_run_with_no_solve_claims_neither_proof_nor_failure(self):
        """"Not proved" about a solve that never happened is a false negative."""
        assert "proof" not in _keys(build(proof=CostProof(status="NO_ADMISSION")))


class TestLate:

    def test_the_floor_is_stated_beside_the_controllable_part_never_summed(self):
        """R-PD1 clause (4). Ranking on the fused number would put a board at
        the top of the list for work that was already late when it arrived."""
        o = build(proof=None,
                  cost={"tardiness": 800_000.0, "tardiness_floor": 776_160.0,
                        "tardiness_controllable": 23_840.0},
                  late=[{"order": "ORD-14", "lateness_min": 85_495,
                         "floor_min": 84_240}])
        item = _item(o, "late")
        assert item.amount == 23_840.0                  # ranked on OUR part
        assert "776,160.00 more was already accrued" in item.headline
        assert "already on the clock before this window opened" in \
            " ".join(item.detail)

    def test_an_empty_late_list_is_a_clean_item_not_an_absent_one(self):
        item = _item(build(late=[]), "late")
        assert item.clean and "Nothing in this window is late" in item.headline

    def test_it_names_the_worst_three_and_counts_the_rest(self):
        item = _item(build(late=[{"order": f"ORD-{n}", "lateness_min": n}
                                 for n in range(1, 8)]), "late")
        assert "ORD-7" in item.detail[0]
        assert "…and 4 more." in item.detail


class TestAtRisk:

    def test_on_time_with_less_slack_than_one_of_its_own_steps_is_a_warning(self):
        item = _item(build(at_risk=[{"order": "ORD-02", "slack_min": 40,
                                     "longest_op_min": 300}]), "at_risk")
        assert "40m of slack" in " ".join(item.detail)
        assert "5h of work" in " ".join(item.detail)

    def test_nothing_at_risk_says_nothing(self):
        assert "at_risk" not in _keys(build(at_risk=[]))


class TestConcentration:

    HOT = {"machine": "CUT-01", "utilization": 0.88,
           "alternatives": [{"machine": "CUT-02", "utilization": 0.0},
                            {"machine": "CUT-03", "utilization": 0.02}]}

    def test_a_saturated_machine_beside_ELIGIBLE_idle_ones_is_a_finding(self):
        item = _item(build(concentration=[self.HOT]), "concentration")
        assert "CUT-01 is at 88%" in item.headline
        assert "CUT-02 at 0%" in item.headline

    def test_the_same_picture_with_NO_eligible_alternative_is_not(self):
        """ELIGIBILITY is what makes it a finding and not an observation: a busy
        machine beside an idle one it shares no capability with is what a
        specialised cell looks like."""
        lonely = {**self.HOT, "alternatives": []}
        assert "concentration" not in _keys(build(concentration=[lonely]))

    def test_nor_is_a_busy_machine_whose_alternatives_are_also_busy(self):
        shared = {**self.HOT,
                  "alternatives": [{"machine": "CUT-02", "utilization": 0.7}]}
        assert "concentration" not in _keys(build(concentration=[shared]))


class TestClosuresAndUnplaced:

    def test_a_closure_names_the_day_the_reason_and_what_it_pauses(self):
        item = _item(build(closures=[{
            "date": "Wednesday 2026-01-14", "reason": "planned maintenance",
            "machines": ["CUT-01", "PAINT-01"], "plant_wide": True,
            "spans": 11}]), "closures")
        assert "planned maintenance on Wednesday 2026-01-14" in item.headline
        assert "all 2 of them" in item.headline
        assert "11 operation(s) run across it" in item.detail[0]

    def test_unplaced_work_names_the_count_and_the_first_due_date(self):
        item = _item(build(unplaced={"count": 14,
                                     "earliest_due": "2026-01-20"}), "unplaced")
        assert "14 known order(s) sit beyond the planning horizon" in \
            item.headline
        assert "due 2026-01-20" in item.detail[0]

    def test_coarse_unmodelable_work_says_its_load_was_NOT_counted(self):
        """4B.6a's rule: every load figure names what it did not count."""
        item = _item(build(unplaced={"count": 14, "unmodelable_count": 3}),
                     "unplaced")
        assert "NOT counted in any figure above" in " ".join(item.detail)

    def test_a_coarse_refutation_is_reported_as_the_proof_it_is(self):
        item = _item(build(unplaced={"count": 14,
                                     "infeasibility_proven": True}), "unplaced")
        body = " ".join(item.detail)
        assert "INFEASIBLE" in body
        assert "a coarse placement never is" in body


class TestDeclaredButAbsent:

    def test_a_DEFAULTED_derate_is_named_with_its_consequence(self):
        item = _item(build(derate={"value": 1.0, "provenance": "defaulted"}),
                     "undeclared_derate")
        assert "assumes 100% of open time is usable" in item.headline
        assert "docs/06 §5.9" in item.detail[0]

    def test_a_DECLARED_one_says_nothing(self):
        assert "undeclared_derate" not in _keys(
            build(derate={"value": 0.85, "provenance": "declared"}))


class TestCertificate:

    def test_it_names_the_findings_the_gate_PROCEEDED_PAST(self):
        item = _item(build(certificate={"grade": "CONDITIONAL", "count": 3,
                                        "proceeded": 2, "top": "a thing"}),
                     "certificate")
        assert "3 data-quality finding(s)" in item.headline
        assert "2 of them were PROCEEDED PAST" in item.detail[0]


# ---------------------------------------------------------------------------
# The Explainer's extraction, end to end
# ---------------------------------------------------------------------------

def _document(**over) -> dict:
    """A minimal contract-1.12 document over the why-here world's two orders."""
    doc = {
        "contract_version": "1.12", "schedule_id": "sch", "snapshot_id": "s",
        "run_id": "r", "reference_date": "2026-01-05T00:00:00",
        "horizon": {"start": "2026-01-05T00:00:00", "end": "2026-01-19T00:00:00"},
        "solver": {"status": "OPTIMAL"},
        "cost_summary": {"total": 1000.0, "production_regular": 900.0,
                         "production_overtime": 0.0, "setup": 0.0,
                         "tardiness": 100.0},
        "resources": [{"resource_id": "res-cut"}, {"resource_id": "res-paint"}],
        "assignments": [
            {"assignment_id": "a-13-10", "operation_ref": "op-13-10",
             "workpackage_ref": "wp-13", "work_orders": ["ORD-000013"],
             "resource_id": "res-cut", "op_seq": 10,
             "chunks": [{"chunk_seq": 0, "start": "2026-01-13T07:00:00",
                         "end": "2026-01-13T14:06:00", "working_min": 426}]},
            {"assignment_id": "a-99-10", "operation_ref": "op-99-10",
             "workpackage_ref": "wp-99", "work_orders": ["ORD-000099"],
             "resource_id": "res-cut", "op_seq": 10,
             "chunks": [{"chunk_seq": 0, "start": "2026-01-12T13:37:00",
                         "end": "2026-01-12T15:37:00", "working_min": 120}]},
        ],
        "service_outcomes": [
            {"demand_ref": "dem-13", "work_order": "ORD-000013",
             "projected_completion": "2026-01-25T00:00:00", "lateness_min": 600},
            {"demand_ref": "dem-99", "work_order": "ORD-000099",
             "projected_completion": "2026-01-22T00:00:00", "lateness_min": -30},
        ],
    }
    doc.update(over)
    return doc


@pytest.fixture
def ex():
    return Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")


def _opener(explainer, document=None) -> list[dict]:
    return explainer.route("briefing", {"question": "how does this look?",
                                        "document": document}
                           ).key_facts["opener"]


class TestExtraction:

    def test_the_late_and_at_risk_split_comes_off_the_service_record(self, ex):
        items = {i["key"]: i for i in _opener(ex, _document())}
        assert "ORD-000013" in " ".join(items["late"]["detail"])
        # ORD-000099 is on time by 30 minutes against a 2-hour operation.
        assert "ORD-000099" in " ".join(items["at_risk"]["detail"])

    def test_the_maintenance_day_is_found_on_the_calendar_not_asserted(self, ex):
        item = {i["key"]: i for i in _opener(ex, _document())}["closures"]
        assert "planned maintenance on Wednesday 2026-01-14" in item["headline"]
        assert item["figures"]["count"] == 1

    def test_an_IDLE_machine_is_still_in_the_load_table(self, ex, monkeypatch):
        """The whole point of a concentration finding is the machine with NO
        work on it — so the load table is built over the plant's vocabulary,
        not over the machines that happen to carry rows. Built over rows alone
        it would drop exactly the machines the finding is about.

        The calendar is narrowed to one shift so the demo world's handful of
        operations register as load at all."""
        from datetime import datetime
        monkeypatch.setattr(ex, "_open_windows", lambda m: [
            (datetime(2026, 1, 13, 7, 0), datetime(2026, 1, 13, 19, 0))])
        load = {c["machine"]: c for c in ex._opener_load()[0]}
        assert "CUT-01" in load
        assert "PAINT-01" in [a["machine"]
                              for a in load["CUT-01"]["alternatives"]]

    def test_a_monolithic_document_REPORTS_that_it_has_no_tray(self, ex):
        kf = ex.route("briefing", {"question": "q",
                                   "document": _document()}).key_facts
        gaps = " ".join(g["what"] + g["why"]
                        for g in kf["opener_unavailable"])
        assert "work beyond the planning horizon" in gaps
        assert "monolithic" in gaps

    def test_the_tray_and_a_DEFAULTED_derate_come_off_the_rolling_block(self, ex):
        doc = _document(rolling={
            "reference_origin": "2026-01-05T00:00:00",
            "window_start": "2026-01-05T00:00:00",
            "window_end": "2026-01-19T00:00:00",
            "frozen_until": "2026-01-08T00:00:00",
            "window_days": 14, "frozen_days": 3,
            "beyond_horizon": [{"demand_ref": "d1", "work_order": "ORD-000200",
                                "due": "2026-01-25T00:00:00"}],
            "coarse_zone": {"bucket_days": 7, "bucket_days_provenance":
                            "defaulted", "capacity_derate": 1.0,
                            "capacity_derate_provenance": "defaulted",
                            "proof_status": "OPTIMAL",
                            "planning_status": "OPTIMAL"},
        })
        keys = {i["key"] for i in _opener(ex, doc)}
        assert "unplaced" in keys and "undeclared_derate" in keys

    def test_with_no_document_it_still_answers_and_says_what_it_could_not_read(
            self, ex):
        """The route degrades rather than failing: the evidence store alone
        still knows what is late, and the answer names what it is missing."""
        kf = ex.route("briefing", {"question": "q"}).key_facts
        assert kf["opener"]
        assert any("document" in g["why"] for g in kf["opener_unavailable"])


class TestTheAnswer:

    def test_it_is_ranked_numbered_and_every_item_offers_a_next_question(self, ex):
        text = TemplateRenderer().render(
            ex.route("briefing", {"question": "how does this schedule look?",
                                  "document": _document()}))
        assert "worth your attention, worst first:" in text
        assert "\n1. " in text and "\n2. " in text
        assert "->" in text          # the pointer: where each item opens up

    def test_it_states_the_scope_of_everything_below_it(self, ex):
        text = TemplateRenderer().render(
            ex.route("briefing", {"question": "q", "document": _document()}))
        # Session 4B.21: the word "scheduled" is load-bearing. This figure is
        # the PLACED order count; `inventory` reports the KNOWN one, and a
        # planner reading both had nothing on either surface naming the sets.
        assert ("2 scheduled orders on 2 machines over 2026-01-05 to 2026-01-19"
                in text)

    def test_a_clean_board_is_TOLD_it_is_clean(self):
        """"Three things, and none of them are on fire" — rendered. A silence
        is not an answer; a planner has to interpret it."""
        from mre.modules.explainer import ExplanationBundle
        o = build(proof=PROVED, cost=LEDGER, late=[],
                  certificate={"grade": "ACCEPTED", "count": 0})
        b = ExplanationBundle(
            question="how does this look?", subject_id="s",
            subject_type="briefing", subject_external_name="today",
            ordered_records=[], snapshot_id="snap",
            key_facts={"opener": [{"key": i.key, "band": i.band,
                                   "amount": i.amount, "headline": i.headline,
                                   "detail": list(i.detail),
                                   "pointer": i.pointer, "clean": i.clean,
                                   "figures": i.figures} for i in o.items],
                       "opener_clean": True, "opener_scope": {},
                       "opener_unavailable": []})
        text = TemplateRenderer().render(b)
        assert "Nothing on this board needs your attention" in text
        assert "that is a real answer, not a silence" in text
        assert "The cost optimum is PROVED" in text

    def test_it_is_contracted_testimony_with_no_synthesis_on_the_path(self, ex):
        from mre.modules.explainer import register_of
        from mre.modules.renderers import LLMRenderer
        b = ex.route("briefing", {"question": "q", "document": _document()})
        assert register_of(b) == "testimony"
        # And a reword cannot drop an item — an opener that drops one reads as
        # a clean bill of health for it.
        assert "briefing" in LLMRenderer._AUTHORED_COPY_SUBJECTS
