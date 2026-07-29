"""Session 4B.13 Item 1 — THE RELEVANCE GUARD, both clauses, as FLOORS.

Two measured failures, one root cause: relevance was never validated.

  TF1, PREMISE ECHO. "why is ORD-000023 on MILL-01" returned an answer asserting
  it IS on MILL-01 — contradicted by its own evidence block one line below, which
  named PRESS-FAST. "why did ORD-000009 end up on CUT-01" was false twice: the
  order runs MILL-02 -> ASM-01 -> FINISH-01, and the answer added that CUT-01 "is
  the only machine that can run it" about a machine the order never touches.

  PREDICATE SWAP. "why does this order go through downtime" (ORD-000011, from the
  board selection) explained why it STARTS when it starts — true, cited, right
  register, and not about downtime at all.

A stranger who MISTYPES A MACHINE NAME OFF THE BOARD got a fluent falsehood with
an evidence chain attached. That is the worst failure mode this product has,
because the evidence block makes it look audited.

Both specimens are pinned here VERBATIM, including the mistyped-machine case.
Deliberately NOT done in the same session: recalibrating the r5 bank. The
ordering is load-bearing — the premise-echo defect is VISIBLE only because stale
bank questions carry false premises, so fixing the bank first would have hidden
it with no guard behind it. The guard ships first; the bank waits.
"""
from __future__ import annotations

import pytest

from mre.modules.predicate_coverage import TOPICS, uncovered_topic


# ---------------------------------------------------------------------------
# clause (ii) — predicate coverage. Pure, so it needs no world.
# ---------------------------------------------------------------------------

def test_the_measured_predicate_swap_is_caught():
    """The specimen, verbatim: a downtime question answered by start-time
    causation, on a route that does not cover downtime."""
    q = "why does this order go through downtime"
    answer = ("ORD-000011 starts Thursday (2026-01-08 14:36) because CUT-01 was "
              "busy: it was held by ORD-000019, high priority until "
              "2026-01-08 14:36, so ORD-000011 took the next opening.")
    topic = uncovered_topic(q, "start-reason", answer)
    assert topic is not None and topic.key == "downtime_traversal"


def test_a_route_that_covers_the_topic_is_never_riddered():
    q = "how much downtime does CUT-01 have"
    assert uncovered_topic(q, "downtime", "CUT-01 is closed on 2026-01-14.") is None


def test_an_answer_that_addresses_the_topic_anyway_is_never_contradicted():
    """Condition 3: the ANSWER gets the benefit of the doubt over the coverage
    declaration. A route not declared to cover downtime, which nonetheless spoke
    about closures, must not be told it didn't."""
    q = "why does this order go through downtime"
    answer = "It spans a closure on CUT-01 over the weekend of Jan 10-11."
    assert uncovered_topic(q, "start-reason", answer) is None


def test_a_question_naming_no_topic_never_fires():
    for q in ("why is ORD-000011 late",
              "what does this move cost",
              "when does ORD-000011 start",
              "which orders are late"):
        assert uncovered_topic(q, "start-reason", "an answer") is None, q


def test_topic_matching_is_word_bounded():
    """A term must appear as a WHOLE WORD. This is what keeps the rider rare:
    the cost of a false fire is an answer telling the planner it failed to
    address something they never asked about."""
    # exact members of the vocabulary fire
    assert uncovered_topic("does it run through a closure", "start-reason",
                           "x") is not None
    assert uncovered_topic("is it working over the weekend", "start-reason",
                           "x") is not None
    # a word merely CONTAINING a term does not
    assert uncovered_topic("why is ORD-1 unclosedish", "start-reason", "x") is None
    assert uncovered_topic("the shutdowns list is empty", "start-reason",
                           "x") is None, (
        "'shutdowns' is not a vocabulary member; inflections are added "
        "deliberately or not at all, never by loose matching")


def test_honest_floors_are_not_treated_as_dodges():
    """A clarify or an unknown-entity answer did not evade the predicate — it
    declined to answer at all, and saying "I also didn't cover downtime" on top
    of "I don't know what you mean" is noise, not honesty."""
    q = "why does this order go through downtime"
    for route in ("clarify", "CLARIFY", "unknown-entity", "near-miss", "synthesis"):
        assert uncovered_topic(q, route, "I need one more detail.") is None, route


def test_both_renderers_apply_the_floor_or_neither_does():
    """The seam is written TWICE — `TemplateRenderer.render` and
    `LLMRenderer.render` — and the first pass of this session wired only one, so
    every answer that went through the LLM path (start-reason among them) skipped
    the floor silently. A floor one path can skip is not a floor. Read the source
    rather than the behaviour: the behavioural test would need a live model."""
    import inspect
    from mre.modules.renderers import LLMRenderer, TemplateRenderer
    for cls in (TemplateRenderer, LLMRenderer):
        src = inspect.getsource(cls.render)
        assert "apply_coverage_rider" in src, (
            f"{cls.__name__}.render does not apply the predicate-coverage floor")
        assert "apply_cost_proof_rider" in src, (
            f"{cls.__name__}.render does not apply the cost-proof rider")
        # Session 4B.14 Item 1 — the causal-sufficiency floor, same rule. The
        # LLM path is the one that matters here: a reword is exactly how "so it
        # took the next opening" comes back after the assembler removed it.
        assert "apply_sufficiency_rider" in src, (
            f"{cls.__name__}.render does not apply the causal-sufficiency floor")


def test_the_vocabulary_is_deliberately_minimal_and_stays_declared():
    """The vocabulary grows only with a MEASURED specimen (module docstring).
    This pins the intent: if a topic is added, this test is the place the
    reviewer is forced to look, and it went red for both of Session 4B.14's
    additions before they were reviewed in.

    The three, each with the live exchange that earned it:

      downtime_traversal   (4B.13) "why does this order go through downtime"
                           answered with why it STARTS when it starts.
      disagreement         (4B.14) "it seems it should be able to start on
                           tuesday after op10 finishes" answered "is ORD-000013
                           really on time? Yes - the record agrees."
      temporal_alternative (4B.14) "why can't this order start on Monday"
                           answered with when it DOES start; Monday never
                           addressed.
    """
    assert [t.key for t in TOPICS] == [
        "downtime_traversal", "disagreement", "temporal_alternative"]


def test_every_topic_declares_the_routes_that_cover_it():
    """A topic with no COVERED_BY entry fires its rider on the very route built
    to answer it — a false admission, which is its own species of lying."""
    from mre.modules.predicate_coverage import COVERED_BY
    for topic in TOPICS:
        assert COVERED_BY.get(topic.key), f"{topic.key} declares no covering route"
        assert topic.route in COVERED_BY[topic.key], (
            f"{topic.key} points at {topic.route}, which is not declared to "
            "cover it — the pointer would send a planner to a route that then "
            "admits it did not answer")


def test_every_topic_has_surface_forms_and_an_authored_pointer():
    for topic in TOPICS:
        assert topic.terms or topic.phrases, f"{topic.key} matches nothing"
        assert topic.admission.strip()
        # The first topic composes its pointer from `label`; the later two are
        # authored, because the honest next step is not always a question of the
        # "how much X does <machine> have?" shape.
        assert topic.pointer.strip() or topic.label.strip()


# ---------------------------------------------------------------------------
# clause (i) — premise verification, against a real solved world.
# ---------------------------------------------------------------------------

REF = "2026-01-05"


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    """A small monolithic run is enough: the guard is about the relation between
    an order and a machine, not about slicing."""
    import sys
    from pathlib import Path
    REPO = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(REPO / "tools"))
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
    from mre.modules.schedule_assembler import assemble_rolling_document  # noqa: F401
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from datetime import datetime, timezone

    d = tmp_path_factory.mktemp("relguard")
    generate(d / "sub", scenario="pilot_scale", orders=12, seed=1)
    plant = prepare_plant(d / "sub", d / "prep",
                          reference_date=datetime(2026, 1, 5, tzinfo=timezone.utc))
    build_rolling_view(plant, window_days=14, frozen_days=3, gravity=True,
                       deterministic=True, seed=42, member_time_limit_s=60.0,
                       det_total=4.0, persist=True)
    index = EvidenceIndex().build(plant.out_dir / "runs")
    return Explainer(plant.store, index, snapshot_id=plant.snapshot_id)


def _placed(ex):
    """(order, machine) for some order that IS placed, from the world itself."""
    for a in ex._load_enriched_assignments():
        if a.get("work_orders") and a.get("machine"):
            return a["work_orders"][0], a["machine"]
    raise AssertionError("no placement in the fixture world")


@pytest.mark.slow
def test_a_true_premise_is_answered_not_corrected(ex):
    order, machine = _placed(ex)
    b = ex._explain_why_on_machine(order, machine)
    assert b.subject_type == "demand", (
        "a TRUE premise must reach the real route — the guard is a floor, not a "
        "gate that fires on everything")


@pytest.mark.slow
def test_a_false_premise_is_corrected_with_the_real_machines(ex):
    """TF1's shape: the order is real, the machine is real, the RELATION is not."""
    order, machine = _placed(ex)
    others = sorted({a["machine"] for a in ex._load_enriched_assignments()
                     if a.get("machine")}
                    - {m for m in [machine]})
    wrong = next((m for m in others
                  if m not in {r["machine"] for r in ex._order_rows(order)}), None)
    assert wrong, "fixture has no second machine to be wrong about"

    b = ex._explain_why_on_machine(order, wrong)
    assert b.subject_type == "premise_correction"
    kf = b.key_facts
    assert kf["claimed_machine"] == wrong
    assert kf["claimed_machine_exists"] is True
    assert machine in kf["actual_machines"]
    assert wrong not in kf["actual_machines"]

    from mre.modules.renderers import TemplateRenderer
    text = TemplateRenderer().render(b)
    # The correction states the negative EXPLICITLY — the defect was an answer
    # that asserted the placement, so "isn't on" must be said, not implied.
    assert f"{order} isn't on {wrong}" in text
    assert machine in text
    # and it must NOT assert the false placement anywhere
    assert f"{order} is on {wrong}" not in text


@pytest.mark.slow
def test_a_mistyped_machine_is_named_as_nonexistent(ex):
    """THE COLD-STRANGER CASE, pinned verbatim per the brief. A name that is not
    in the plant at all gets a DIFFERENT correction from one that is — a
    stranger mistyping needs to be told which mistake they made."""
    order, machine = _placed(ex)
    b = ex._explain_why_on_machine(order, "MILL-99")
    assert b.subject_type == "premise_correction"
    assert b.key_facts["claimed_machine_exists"] is False

    from mre.modules.renderers import TemplateRenderer
    text = TemplateRenderer().render(b)
    assert "no machine called MILL-99" in text
    assert machine in text, "the correction must still say where the order IS"


@pytest.mark.slow
def test_the_uniqueness_claim_cannot_be_made_about_a_machine_the_order_avoids(ex):
    """The second half of TF1: the old answer added "it is the only machine that
    can run this step" about a machine the order never touches. A corrected
    premise never reaches the clause that says it."""
    order, _ = _placed(ex)
    from mre.modules.renderers import TemplateRenderer
    text = TemplateRenderer().render(ex._explain_why_on_machine(order, "MILL-99"))
    assert "only machine" not in text


@pytest.mark.slow
def test_an_unplaced_order_is_not_refuted(ex):
    """The guard refutes only a relation it can SEE is false. An order with no
    placements has no contradicting evidence, and other routes own that
    disposition — inventing a refutation here would be the same overreach in the
    other direction."""
    assert ex._verify_placement_premise("ORD-DOES-NOT-EXIST", "CUT-01") is None
