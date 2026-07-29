"""Session 4B.13 Items 2-4 — the three remaining measured truth failures.

Each was reproduced against the LIVE registered board (the pinned exam world
rolling-1b170235-64d), and each is reachable by a question a cold stranger asks
in the first minute.

  TF2  lateness_set returned {'orders': 40, 'late': 0, 'on_time_or_early': 40}
       on a board where FOURTEEN rows have no placement at all — exactly the
       beyond-horizon tray. Synthesis repeated it faithfully and claim
       verification PASSED it.
  TF3  "15 machine(s) carry work in this plan" — ten do. Five rows sit at 0%.
  TF4  "is this schedule optimal?" was answered by synthesis improvising its own
       definition from a bar count, while the RENDERED PROOF (solver.status
       OPTIMAL, gap 0.0) sat unread in the document.

THE PRINCIPLE BEHIND TF2, recorded here and in docs/04 because it generalizes:
VERIFICATION IS DOWNSTREAM OF TOOL VOCABULARY. A tool that fuses two categories
makes every claim built on it unfalsifiable-but-verified. Claim-level
verification checks a claim against what the tool SAID; it cannot check whether
the tool's categories are honest. So the fix belongs in the tool, not the
verifier — which is why there is no test here asserting the verifier got
smarter. It did not, and it should not have to.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules import cost_proof as cp
from mre.modules.explainer import ExplanationBundle
from mre.modules.renderers import TemplateRenderer

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# TF4 — the optimality answer. Fast: the copy is a pure function of the proof.
# ---------------------------------------------------------------------------

def _optimality_text(proof: cp.CostProof) -> str:
    unknown = proof.status is None
    kf = {"unknown": unknown, "no_solve": proof.no_solve and not unknown,
          "proved": proof.proved, "unproved": proof.unproved,
          "gap_text": proof.gap_text(), "objective": proof.objective,
          "status": proof.status, "tiebreak_status": proof.tiebreak_status,
          "tiebreak_skipped_reason": proof.tiebreak_skipped_reason,
          "tiebreak_clause": proof._tiebreak_clause()}
    return TemplateRenderer().render(ExplanationBundle(
        question="is this schedule optimal?", subject_id="all",
        subject_type="optimality", subject_external_name="this schedule",
        ordered_records=[], key_facts=kf, snapshot_id="s"))


def test_a_proved_board_says_so_plainly_and_says_what_was_proved():
    text = _optimality_text(cp.CostProof(status="OPTIMAL", gap=0.0,
                                         tiebreak_status="FEASIBLE"))
    assert text.lstrip().startswith("Yes")
    assert "proved" in text
    # 4B.8 CU3's ruling: it is the COST optimum, and the answer must scope
    # itself — a stranger must not read "optimal" as "nothing is late".
    assert "COST optimum" in text
    # and an unproven TIEBREAK never downgrades the cost claim
    assert "does not affect the cost claim" in text


def test_an_unproved_board_states_its_gap_and_is_not_called_bad():
    """4B.12 measured F006 at a 98.8% gap whose ledger spread across seeds was
    0.289%. The gap measures our inability to PROVE, not the answer's quality,
    and the copy has to carry that or it slanders its own schedule."""
    text = _optimality_text(cp.CostProof(status="FEASIBLE", gap=0.988))
    assert "98.8%" in text
    assert "limit of the PROOF" in text
    assert "not a measure of how good the schedule is" in text


def test_an_unproved_board_with_no_gap_never_invents_one():
    text = _optimality_text(cp.CostProof(status="FEASIBLE", gap=None))
    assert "0.0%" not in text and "0%" not in text
    assert "unknown" in text


def test_unreadable_is_distinguished_from_no_solve():
    """CostProof.no_solve covers BOTH "nothing was admitted" and status=None.
    Fusing them in the answer would assert "there was no solve" about a solve
    that happened — the same defect class as the rest of this session."""
    none_text = _optimality_text(cp.CostProof(status=None))
    noadm_text = _optimality_text(cp.CostProof(status="NO_ADMISSION"))
    assert "can't tell you" in none_text
    assert "no solve to prove anything about" in noadm_text
    assert none_text != noadm_text


def test_the_route_is_registered_end_to_end():
    """A vocabulary-class change is only done when every surface carries it."""
    from mre.contracts.parse import Intent, INTENT_MEANINGS, model_selectable_intents
    from mre.modules.explainer import ROUTE_TAXONOMY
    from mre.modules.ask_fallback_copy import ROUTE_OFFERS
    assert Intent.SOLVE_OPTIMALITY in INTENT_MEANINGS
    assert Intent.SOLVE_OPTIMALITY.value in ROUTE_TAXONOMY
    assert Intent.SOLVE_OPTIMALITY.value in ROUTE_OFFERS
    assert Intent.SOLVE_OPTIMALITY in model_selectable_intents()


def test_the_parse_prompt_was_bumped_with_the_vocabulary():
    """The governed artifact and the vocabulary move together or not at all."""
    from mre.modules.question_parser import load_prompt
    _template, version = load_prompt()
    assert version == "10", (
        "the intent vocabulary gained solve-optimality; parse_prompt.md must "
        "carry the matching bump and its changelog entry")


# ---------------------------------------------------------------------------
# TF2 + TF3 — measured against a real solved world with a real tray.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """40 orders in a 7-day window: enough book to guarantee a non-empty
    beyond-horizon tray, which is what makes TF2 non-vacuous."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    d = tmp_path_factory.mktemp("tf4b13")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=7, frozen_days=2, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=120.0, det_total=4.0,
                              persist=True)
    index = EvidenceIndex().build(plant.out_dir / "runs")
    ex = Explainer(plant.store, index, snapshot_id=plant.snapshot_id)
    return plant, view, ex


@pytest.mark.slow
def test_lateness_set_never_counts_an_unplaced_order_as_on_time(world):
    """TF2 at the source. The three states are disjoint and cover the set."""
    from mre.modules.evidence_tools import EvidenceToolbox
    _plant, view, ex = world
    r = EvidenceToolbox(ex).call("lateness_set", {})
    s = r.summary

    assert s["late"] + s["on_time_or_early"] == s["scheduled"]
    assert s["scheduled"] + s["not_scheduled"] == s["orders"]
    # the fixture must actually HAVE unplaced orders or this proves nothing
    assert s["not_scheduled"] > 0, "no tray — this guard would be vacuous"
    assert s["on_time_or_early"] < s["orders"], (
        "on_time_or_early still counts the whole set — the fusion is back")

    # every row says its own state, so a reader of rows cannot re-fuse by hand
    for row in r.rows:
        if row["lateness_minutes"] is None:
            assert row["service_state"] == "not_scheduled"
            assert row["scheduled"] is False
            assert row["late"] is False
        else:
            assert row["scheduled"] is True
            assert row["service_state"] in ("late", "on_time_or_early")

    # and the note SAYS it, because a summary field alone is easy to skip
    assert "no placement" in r.note.lower()


@pytest.mark.slow
def test_the_tool_meaning_teaches_three_states(world):
    """The governed synthesis prompt renders TOOL_MEANINGS. A tool whose
    categories changed but whose authored meaning did not is how the model
    re-learns the fusion."""
    from mre.contracts.synthesis import TOOL_MEANINGS, ToolName
    m = TOOL_MEANINGS[ToolName.LATENESS_SET]
    assert "not_scheduled" in m
    assert "not" in m.lower() and "on time" in m.lower()


@pytest.mark.slow
def test_late_orders_answer_names_the_region_it_speaks_about(world):
    """TF2 in the template channel: "No late orders found in this schedule."
    said alone lets a stranger read the tray as a clean bill of health."""
    from mre.modules.schedule_assembler import assemble_rolling_document
    plant, view, ex = world
    imap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id="s",
                                    run_id="r", identity_map=imap)
    text = TemplateRenderer().render(
        ex._list_late_orders(doc.model_dump(mode="json")))

    assert "beyond the horizon" in text
    assert "neither late nor on time" in text
    # C3: the parenthetical that read as a system failure rather than a clean
    # bill of health is gone.
    assert "(no evidence records found)" not in text


@pytest.mark.slow
def test_late_orders_on_a_monolithic_board_is_unchanged(world):
    """The rider is ABSENT, not zero, where there is no tray to speak of."""
    _plant, _view, ex = world
    text = TemplateRenderer().render(ex._list_late_orders())
    assert "beyond the horizon" not in text


@pytest.mark.slow
def test_machine_count_does_not_call_declared_machines_working(world):
    """TF3. Both facts are worth saying; neither may stand in for the other."""
    _plant, _view, ex = world
    b = ex._explain_machine_count("how many machines are there")
    kf = b.key_facts
    declared, working = kf["machine_count"], kf["working_machine_count"]
    assert working is not None and working <= declared
    assert len(kf["idle_machines"]) == declared - working

    text = TemplateRenderer().render(b)
    # the false sentence, verbatim, must not be reconstructible
    assert f"{declared} machine(s) carry work in this plan." not in text
    if working < declared:
        assert f"{working} of them carry work" in text
        assert "Carrying no work in this window:" in text
        for m in kf["idle_machines"]:
            assert m in text
