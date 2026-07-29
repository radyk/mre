"""THE BLOCKER ANALYSIS AS AN ANSWER (Session 4B.14 Items 2, 3, 5(b), 5(d)).

These exercise the assembled route end to end against a purpose-built world:
the Explainer reads it, the deterministic renderer voices it, and the sentences
a planner reads are asserted verbatim where the session brief set a bar.

The world reproduces the pinned board's shape at three operations rather than
fifty-six, because what is under test is the reasoning, not the solver. Its
figures are the measured ones (docs/closeouts/4B.14.md): a 431-minute
non-splittable operation with 294 minutes of shift left, and a plant-wide
planned-maintenance closure on the day between.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mre.contracts.parse import ContestedClaim, Intent
from mre.modules.explainer import Explainer
from mre.modules.renderers import TemplateRenderer

REF = datetime(2026, 1, 5)


# ---------------------------------------------------------------------------
# A hand-built snapshot: three operations, two machines, one closure
# ---------------------------------------------------------------------------

class _Reader:
    """The narrow slice of the snapshot-reader surface the Explainer uses."""

    def __init__(self, entities: dict) -> None:
        self._e = entities

    def iter_entities(self, kind):
        return list(self._e.get(kind, []))

    def get_entity(self, eid):
        for rows in self._e.values():
            for r in rows:
                if r.get("id") == eid:
                    return r
        return None

    def read_identity_map(self):
        return _IdentityMap()


class _Ref:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


class _IdentityMap:
    """External refs for the two vocabularies the Explainer resolves against."""

    _PAIRS = {
        "dem-13": ("order_id", "ORD-000013"),
        "dem-99": ("order_id", "ORD-000099"),
        "res-cut": ("resource_id", "CUT-01"),
        "res-paint": ("resource_id", "PAINT-01"),
    }

    def __init__(self):
        self._to_canonical = {
            ("IDS", t, v): cid for cid, (t, v) in self._PAIRS.items()}

    def resolve(self, system, ref_type, value):
        return self._to_canonical.get((system, ref_type, value))

    def external_refs(self, cid):
        pair = self._PAIRS.get(cid)
        return [_Ref(*pair)] if pair else []


class _Store:
    def __init__(self, reader):
        self._reader = reader

    def load_snapshot(self, _sid):
        return self._reader


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _world(*, op20_start=datetime(2026, 1, 15, 7, 0),
           op20_splittable=False, op20_min_chunk=None):
    """op10 on CUT-01 Tue 07:00-14:06; op20 on PAINT-01, placed where asked."""
    cal = {
        "id": "cal-1", "base_pattern": {"weekdays": [0, 1, 2, 3, 4],
                                        "shift_start": "07:00",
                                        "shift_end": "19:00"},
        "exceptions": [{"type": "closure",
                        "window": {"start": _iso(datetime(2026, 1, 14, 0, 0)),
                                   "end": _iso(datetime(2026, 1, 14, 23, 59, 59))},
                        "reason": "planned_maintenance"}],
        "horizon_resolved": [],
    }
    ops = [
        {"id": "op-13-10", "workpackage_ref": "wp-13", "sequence": 10,
         "splittable": False, "min_chunk": None, "setup_duration": "PT15M",
         "run_duration": "PT6H51M", "setup_family": ""},
        {"id": "op-13-20", "workpackage_ref": "wp-13", "sequence": 20,
         "splittable": op20_splittable, "min_chunk": op20_min_chunk,
         "setup_duration": "PT20M", "run_duration": "PT6H51M",
         "setup_family": "PAINT_RED"},
        {"id": "op-99-10", "workpackage_ref": "wp-99", "sequence": 10,
         "splittable": False, "min_chunk": None, "setup_duration": "PT10M",
         "run_duration": "PT2H", "setup_family": ""},
    ]

    def _asgn(aid, op, res, start, end):
        return {"id": aid, "operation_ref": op,
                "workpackage_ref": ops[[o["id"] for o in ops].index(op)]
                ["workpackage_ref"],
                "resource_assignments": [{"resource_ref": res}],
                "phase_windows": {"run": [{"start": _iso(start),
                                           "end": _iso(end)}]},
                "decision_ref": ""}

    return _Reader({
        "calendar": [cal],
        "resource": [{"id": "res-cut", "calendar_ref": "cal-1"},
                     {"id": "res-paint", "calendar_ref": "cal-1"}],
        "operation": ops,
        "precedenceedge": [{"predecessor": "op-13-10", "successor": "op-13-20",
                            "min_lag": "PT0S", "max_lag": None}],
        "constraint": [],
        "demand": [
            {"id": "dem-13", "external_refs": [{"type": "order_id",
                                                "value": "ORD-000013"}],
             "due": _iso(datetime(2026, 1, 22)), "customer_weight": 1.0,
             "earliest_start": _iso(REF)},
            {"id": "dem-99", "external_refs": [{"type": "order_id",
                                                "value": "ORD-000099"}],
             "due": _iso(datetime(2026, 1, 22)), "customer_weight": 1.0,
             "earliest_start": _iso(REF)},
        ],
        "fulfillment": [{"workpackage_ref": "wp-13", "demand_ref": "dem-13"},
                        {"workpackage_ref": "wp-99", "demand_ref": "dem-99"}],
        "serviceoutcome": [],
        "assignment": [
            _asgn("a-13-10", "op-13-10", "res-cut",
                  datetime(2026, 1, 13, 7, 0), datetime(2026, 1, 13, 14, 6)),
            _asgn("a-13-20", "op-13-20", "res-paint",
                  op20_start, op20_start + timedelta(minutes=431)),
            # A second order holding CUT-01 through Monday afternoon — the work
            # the original answer named as the whole cause.
            _asgn("a-99-10", "op-99-10", "res-cut",
                  datetime(2026, 1, 12, 13, 37), datetime(2026, 1, 12, 15, 37)),
        ],
    })


class _Index:
    _all_evidence: list = []

    def lineage_walk(self, *_a, **_k):
        return []


@pytest.fixture
def ex():
    return Explainer(_Store(_world()), _Index(), snapshot_id="snap-test")


def _answer(explainer, route, **params):
    params.setdefault("question", "why is this here?")
    return TemplateRenderer().render(explainer.route(route, params))


# ---------------------------------------------------------------------------
# Item 2 — the target sentence
# ---------------------------------------------------------------------------

class TestTargetSentence:
    """The bar the session brief set:

        "op20 couldn't start Tuesday afternoon: it needs 6h and 3h remain
         before PAINT-01 closes, and it can't be split. The next window long
         enough is Thursday, after maintenance."
    """

    def test_it_says_COULDNT_not_that_it_took_the_next_opening(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "couldn't start before" in text
        assert "took the next opening" not in text

    def test_it_states_the_work_and_what_was_left(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "7h11m" in text          # the operation's working minutes
        assert "4h54m" in text          # what remained before PAINT-01 closed

    def test_it_says_the_operation_cannot_be_split(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "can't be split" in text

    def test_it_names_the_maintenance_the_wait_spans(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "planned maintenance" in text
        assert "2026-01-14" in text

    def test_it_cites_the_docs05_family_that_bound(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "docs/05 C3" in text

    def test_it_names_what_it_did_not_weigh(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "Not weighed here" in text
        for family in ("B3/B5", "B7/B8", "C4", "F3"):
            assert family in text


class TestCouldNotVersusChose:

    def test_a_forced_placement_says_it_could_not_go_earlier(self, ex):
        kf = ex.route("why-here", {"order": "ORD-000013",
                                   "machine": "PAINT-01"}).key_facts
        assert kf["verdict"] == "could_not"

    def test_a_free_placement_says_the_solver_CHOSE_it(self):
        """The distinction the product could not draw. Same operation, moved a
        day later into space nothing was using: the honest answer is that
        nothing prevented an earlier start."""
        e = Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                      _Index(), snapshot_id="snap-test")
        text = _answer(e, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "Nothing prevented" in text
        assert "the solver chose" in text
        assert "couldn't" not in text

    def test_the_chose_branch_never_invents_a_cost_reason(self):
        """With no decision record stating a driver, the answer says it cannot
        tell you why — it does not reach for a plausible one (R-AI3(1))."""
        e = Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                      _Index(), snapshot_id="snap-test")
        text = _answer(e, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "can't tell you why" in text

    def test_splitting_the_operation_removes_the_constraint(self):
        """The counterfactual proving the analysis blames the right family: flip
        only the R-C3 class and Tuesday afternoon becomes usable."""
        e = Explainer(
            _Store(_world(op20_start=datetime(2026, 1, 13, 14, 6),
                          op20_splittable=True, op20_min_chunk="PT1H")),
            _Index(), snapshot_id="snap-test")
        kf = e.route("why-here", {"order": "ORD-000013",
                                  "machine": "PAINT-01"}).key_facts
        assert kf["verdict"] == "could_not"
        assert kf["binding"]["family"] == "precedence"


# ---------------------------------------------------------------------------
# Item 5(d) — which operation is being answered about
# ---------------------------------------------------------------------------

class TestOperationScope:

    def test_the_named_machine_selects_the_operation(self, ex):
        for machine, seq in (("CUT-01", 10), ("PAINT-01", 20)):
            kf = ex.route("why-here", {"order": "ORD-000013",
                                       "machine": machine}).key_facts
            assert kf["op_seq"] == seq
            assert kf["machine"] == machine

    def test_an_explicit_op_seq_wins(self, ex):
        kf = ex.route("why-here", {"order": "ORD-000013",
                                   "op_seq": 20}).key_facts
        assert kf["op_seq"] == 20

    def test_an_unscoped_question_SAYS_which_operation_it_answered(self, ex):
        """The bridging sentence. Falling back to the first operation is fine;
        doing it silently is what left a planner reading about CUT-01 with
        PAINT-01 selected."""
        text = _answer(ex, "why-here", order="ORD-000013")
        assert "Answering about ORD-000013 op10 on CUT-01" in text
        assert "the first of its 2 operations" in text

    def test_a_scoped_question_carries_no_bridging_sentence(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "Answering about" not in text

    def test_start_reason_also_honours_the_selected_operation(self, ex):
        kf = ex.route("start-reason", {"order": "ORD-000013",
                                       "machine": "PAINT-01"}).key_facts
        assert kf["machine"] == "PAINT-01"
        assert kf["op_seq"] == 20


# ---------------------------------------------------------------------------
# Item 0 — the chunk-blind row model
# ---------------------------------------------------------------------------

class TestRowModelReadsWholeOperations:

    def test_an_operations_end_is_its_LAST_chunk_not_its_first(self):
        """The root cause of the cited timestamp being four days off: the row
        model read ``phase_windows["run"][0]["end"]``, so a chunked operation
        reported its first PAUSE as its finish."""
        reader = _world()
        for a in reader._e["assignment"]:
            if a["id"] == "a-99-10":
                a["phase_windows"]["run"] = [
                    {"start": _iso(datetime(2026, 1, 8, 14, 36)),
                     "end": _iso(datetime(2026, 1, 8, 19, 0))},
                    {"start": _iso(datetime(2026, 1, 12, 7, 0)),
                     "end": _iso(datetime(2026, 1, 12, 15, 37))},
                ]
        e = Explainer(_Store(reader), _Index(), snapshot_id="snap-test")
        row = next(r for r in e._load_enriched_assignments()
                   if r["assignment_id"] == "a-99-10")
        assert row["end"].startswith("2026-01-12T15:37")
        assert row["start"].startswith("2026-01-08T14:36")

    def test_a_chunked_operation_states_its_pauses_in_the_answer(self):
        """Item 4's distinction, voiced. This is also what makes `why-here` an
        honest answer to "why does it go through downtime" rather than an
        accidental word-match on "closed": every chunk sits inside open calendar
        time by construction, so the pauses ARE non-working time."""
        reader = _world()
        for a in reader._e["assignment"]:
            if a["id"] == "a-13-20":
                a["phase_windows"]["run"] = [
                    {"start": _iso(datetime(2026, 1, 15, 7, 0)),
                     "end": _iso(datetime(2026, 1, 15, 19, 0))},
                    {"start": _iso(datetime(2026, 1, 16, 7, 0)),
                     "end": _iso(datetime(2026, 1, 16, 8, 11))},
                ]
        for o in reader._e["operation"]:
            if o["id"] == "op-13-20":
                o["splittable"], o["min_chunk"] = True, "PT1H"
        e = Explainer(_Store(reader), _Index(), snapshot_id="snap-test")
        text = _answer(e, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "runs in 2 pieces" in text
        assert "of actual work" in text
        assert "pauses when PAINT-01 closes" in text

    def test_an_unbroken_operation_says_nothing_about_pauses(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "pieces" not in text

    def test_run_time_and_elapsed_span_are_separate_facts(self):
        reader = _world()
        for a in reader._e["assignment"]:
            if a["id"] == "a-99-10":
                a["phase_windows"]["run"] = [
                    {"start": _iso(datetime(2026, 1, 8, 14, 36)),
                     "end": _iso(datetime(2026, 1, 8, 19, 0))},
                    {"start": _iso(datetime(2026, 1, 12, 7, 0)),
                     "end": _iso(datetime(2026, 1, 12, 15, 37))},
                ]
        e = Explainer(_Store(reader), _Index(), snapshot_id="snap-test")
        row = next(r for r in e._load_enriched_assignments()
                   if r["assignment_id"] == "a-99-10")
        assert row["run_min"] == pytest.approx(264 + 517)
        assert row["span_min"] > row["run_min"]
        assert len(row["chunks"]) == 2


# ---------------------------------------------------------------------------
# Item 3 — disagreement answered on its own terms
# ---------------------------------------------------------------------------

THE_CHALLENGE = "it seems it should be able to start on tuesday after op10 finishes"


class TestDisagreement:

    def test_a_timing_contest_is_answered_by_the_blocker_analysis(self, ex):
        b = ex.route("contested-fact",
                     {"order": "ORD-000013", "machine": "PAINT-01",
                      "question": THE_CHALLENGE,
                      "contested_claim": ContestedClaim.TIMING.value})
        assert b.subject_type == "why_here"
        assert b.key_facts["contested"] is True

    def test_it_does_NOT_become_a_question_about_lateness(self, ex):
        """DISAGREEMENT LAUNDERING, pinned. The measured answer was "Is
        ORD-000013 really on time? Yes - the record agrees" — an affirmative
        that reads as agreement while addressing nothing that was said."""
        text = _answer(ex, "contested-fact", order="ORD-000013",
                       machine="PAINT-01", question=THE_CHALLENGE,
                       contested_claim=ContestedClaim.TIMING.value)
        assert "really on time" not in text
        assert "the record agrees" not in text
        assert "4h54m" in text          # it engages with the actual hypothesis

    def test_a_lateness_contest_still_reaches_the_lateness_answer(self, ex):
        b = ex.route("contested-fact",
                     {"order": "ORD-000013", "question": "isn't it on time?",
                      "contested_claim": ContestedClaim.LATENESS.value})
        assert b.subject_type == "contested_fact"

    def test_an_absent_claim_behaves_exactly_as_before_the_field_existed(self, ex):
        """No parse emits it yet on an older prompt; the assembler must not
        change behaviour for those."""
        b = ex.route("contested-fact",
                     {"order": "ORD-000013", "question": "isn't it on time?"})
        assert b.subject_type == "contested_fact"

    def test_a_challenge_is_ANSWERED_as_a_challenge_not_merely_answered(self, ex):
        """R-AI3(4). The correct facts delivered with no acknowledgement read as
        though nobody said anything — the same failure in a politer register.
        Here the planner is right about the machine and wrong about the fit, and
        the answer says both."""
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01",
                       question=THE_CHALLENGE,
                       challenge={"kind": "timing", "said": THE_CHALLENGE})
        assert text.startswith("You're right about the machine: PAINT-01 wasn't busy")
        assert "That isn't what held this up." in text
        assert "couldn't start before" in text     # and the correction follows

    def test_where_the_planner_is_RIGHT_the_record_is_corrected_plainly(self):
        """A `chose` verdict under a challenge means the planner was right
        outright. That concession leads — burying it under agreement-shaped
        prose is capitulation's opposite failure and just as dishonest."""
        e = Explainer(_Store(_world(op20_start=datetime(2026, 1, 16, 7, 0))),
                      _Index(), snapshot_id="snap-test")
        text = _answer(e, "why-here", order="ORD-000013", machine="PAINT-01",
                       question=THE_CHALLENGE,
                       challenge={"kind": "timing", "said": THE_CHALLENGE})
        assert text.startswith("You're right, and I'll correct what I said")

    def test_an_unchallenged_question_gets_no_concession(self, ex):
        text = _answer(ex, "why-here", order="ORD-000013", machine="PAINT-01")
        assert "You're right" not in text

    def test_an_unevaluable_contest_SAYS_SO_rather_than_substituting(self, ex):
        b = ex.route("contested-fact",
                     {"order": "ORD-000013", "question": "that's just wrong",
                      "contested_claim": ContestedClaim.OTHER.value})
        assert b.key_facts.get("unevaluable") is True
        assert b.subject_type == "contested_fact"


# ---------------------------------------------------------------------------
# Item 5(b) — the temporal-alternative predicate, and Item 3's coverage floor
# ---------------------------------------------------------------------------

class TestPredicateCoverage:

    def test_an_answer_that_ignores_a_named_day_admits_it(self):
        from mre.modules.predicate_coverage import uncovered_topic
        topic = uncovered_topic(
            "why can't this order start on Monday?", "start-reason",
            "ORD-000013 starts Tuesday 2026-01-13 07:00 because CUT-01 was busy.")
        assert topic is not None
        assert topic.key == "temporal_alternative"

    def test_the_blocker_analysis_covers_it(self):
        from mre.modules.predicate_coverage import uncovered_topic
        assert uncovered_topic("why can't this order start on Monday?",
                               "why-here", "anything at all") is None

    def test_a_challenge_answered_by_an_unrelated_route_admits_it(self):
        from mre.modules.predicate_coverage import uncovered_topic
        topic = uncovered_topic(
            THE_CHALLENGE, "contested-fact-lateness",
            "Is ORD-000013 really on time? Yes - the record agrees.")
        assert topic is not None
        assert topic.key == "disagreement"

    def test_the_route_that_meets_a_challenge_is_not_lectured(self):
        from mre.modules.predicate_coverage import uncovered_topic
        assert uncovered_topic(THE_CHALLENGE, "why-here", "anything") is None
        assert uncovered_topic(THE_CHALLENGE, "contested-fact", "x") is None

    def test_an_honest_floor_never_earns_a_rider(self):
        from mre.modules.predicate_coverage import uncovered_topic
        for route in ("clarify", "synthesis", "unknown-entity", "near-miss"):
            assert uncovered_topic(THE_CHALLENGE, route, "I couldn't tell") is None

    def test_an_ordinary_question_earns_nothing(self):
        from mre.modules.predicate_coverage import uncovered_topic
        assert uncovered_topic("when does ORD-000013 finish?", "order-schedule",
                               "It finishes 2026-01-15 14:11.") is None


# ---------------------------------------------------------------------------
# The vocabulary-class change, paid in full
# ---------------------------------------------------------------------------

class TestVocabularyParity:

    def test_the_new_intents_carry_meanings(self):
        from mre.contracts.parse import INTENT_MEANINGS
        assert Intent.WHY_HERE in INTENT_MEANINGS
        assert INTENT_MEANINGS[Intent.WHY_HERE].strip()

    def test_the_new_intent_is_in_the_taxonomy_and_the_offers(self):
        from mre.modules.ask_fallback_copy import ROUTE_OFFERS
        from mre.modules.explainer import ROUTE_TAXONOMY
        assert Intent.WHY_HERE.value in ROUTE_TAXONOMY
        assert Intent.WHY_HERE.value in ROUTE_OFFERS

    def test_the_new_intent_is_model_selectable(self):
        from mre.contracts.parse import model_selectable_intents
        assert Intent.WHY_HERE in model_selectable_intents()

    def test_the_parse_prompt_was_bumped_and_names_the_field(self):
        from pathlib import Path
        import mre.modules as m
        text = (Path(m.__file__).parent / "parse_prompt.md").read_text(
            encoding="utf-8")
        assert "prompt_version: 11" in text
        assert "why-here" in text
        assert "contested_claim" in text
