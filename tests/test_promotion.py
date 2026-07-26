"""The promotion pipeline: propose, gate, shadow, demote (R-AI5(7)).

Session 4A.5c CU2. Written from the ruling text:

    "The promotion loop runs autonomously through analysis, drafting from
     verified-synthesis exemplars, and harness validation; promotion into the
     contracted vocabulary is a reviewed change carrying a machine-produced
     dossier; promoted routes run shadowed for a probation window; demotion to
     synthesis on divergence is automatic. The system proposes its own healing;
     the proven register is entered only by review."

Four asymmetries, each asserted below: proposing is autonomous but entering is
not; promotion is never automatic but demotion always is; probation is measured
rather than waited out; and interpretive residue is never dossier material.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from mre.contracts.parse import Intent, MODEL_SELECTABLE_INTENTS, model_selectable_intents
from mre.contracts.promotion import (
    PROBATION_SWEEPS,
    PROMOTIONS,
    ProbationStatus,
    Promotion,
    ShadowDiff,
    demoted_intents,
    shadowed_intents,
)
from mre.modules.shadow import (
    candidates_for, diff_claims, numeric_facts, shadow_diff,
)


# ---------------------------------------------------------------------------
# The gate: a promotion is PAPERWORK, and the paperwork is checked
# ---------------------------------------------------------------------------

class TestTheGate:

    def test_every_promotion_cites_a_dossier_that_exists(self):
        """R-AI5(7): promotion "carries a machine-produced dossier". A promotion
        whose authority is not on disk is an unsigned one."""
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        assert PROMOTIONS, "this session promotes exactly one shape"
        for intent, promo in PROMOTIONS.items():
            assert promo.intent is intent
            assert promo.dossier, f"{intent.value} cites no dossier"
            assert (repo / promo.dossier).exists(), \
                f"{intent.value} cites a dossier that is not committed"
            assert promo.promoted_from, "a promotion names the cluster it came from"

    def test_a_promoted_intent_is_a_real_route(self):
        """The gate's checklist, asserted: the Intent, its authored meaning, its
        taxonomy entry and its offer all land together or the promotion is half
        wired — reachable by the parse and dead at dispatch."""
        from mre.contracts.parse import INTENT_MEANINGS
        from mre.modules.ask_fallback_copy import ROUTE_OFFERS
        from mre.modules.explainer import ROUTE_TAXONOMY
        for intent in PROMOTIONS:
            assert intent in INTENT_MEANINGS
            assert intent.value in ROUTE_TAXONOMY
            assert intent.value in ROUTE_OFFERS

    def test_the_session_promoted_exactly_one_shape(self):
        """The working thread pre-authorized ONE proof cycle. More than one
        promotion in a session is out of scope by ruling, not by taste."""
        assert len(PROMOTIONS) == 1
        assert Intent.LATENESS_CAUSE in PROMOTIONS

    def test_the_dossier_tool_writes_only_documents(self):
        """The autonomous half PROPOSES. Asserted on WHERE IT WRITES, because
        that is the property that matters and the one a future edit could break:
        every write goes under docs/promotions/, and importing the generator
        changes no vocabulary.

        (Not asserted by grepping for `ROUTE_TAXONOMY` — the dossier's own gate
        checklist NAMES the things a reviewing session must edit, and a test that
        forbade the words would forbid the document explaining itself.)"""
        import re
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        source = (repo / "tools" / "promotion_dossier.py").read_text(encoding="utf-8")

        writes = re.findall(r"^\s*\(?([\w./ ()\[\]\"'*+-]*?)\)?\.write_text\(",
                            source, re.MULTILINE)
        assert writes, "the generator does write files"
        for target in writes:
            assert ("dossier" in target or "draft_rel" in target), \
                f"the generator writes to {target!r}, outside docs/promotions/"

        before = set(model_selectable_intents())
        import tools.promotion_dossier as gen  # noqa: F401
        assert set(model_selectable_intents()) == before
        assert gen.DOSSIER_DIR.name == "promotions"
        assert gen.DRAFT_DIR.parent == gen.DOSSIER_DIR

    def test_the_dossier_tool_refuses_protected_residue(self):
        """R-AI5(6): a dossier for an interpretive shape would be a request to
        contract away a conversation the product is supposed to be able to have.
        The generator refuses rather than drafting it."""
        source = (__import__("pathlib").Path(__file__).resolve().parent.parent
                  / "tools" / "promotion_dossier.py").read_text(encoding="utf-8")
        assert "NOT-PROMOTABLE-BY-DESIGN" in source
        assert "not target.promotable" in source


# ---------------------------------------------------------------------------
# Demotion: the mechanical flag flip
# ---------------------------------------------------------------------------

class TestDemotion:

    def test_demotion_removes_the_intent_from_the_live_vocabulary(self, monkeypatch):
        """R-AI5(7): "demotion to synthesis on divergence is automatic". The whole
        mechanism is one field — the prompt stops offering the id, so the parse
        cannot name it, so the shape returns to the second tier."""
        assert Intent.LATENESS_CAUSE in model_selectable_intents()
        demoted = PROMOTIONS[Intent.LATENESS_CAUSE].demote("a test divergence")
        monkeypatch.setitem(PROMOTIONS, Intent.LATENESS_CAUSE, demoted)

        assert demoted.status is ProbationStatus.DEMOTED
        assert demoted.demotion_reason == "a test divergence"
        assert Intent.LATENESS_CAUSE in demoted_intents()
        assert Intent.LATENESS_CAUSE not in model_selectable_intents()
        # ... and its ENTRY is gone from the prompt the model actually sees.
        # (Matched on the line prefix, not on the bare id: a neighbouring intent's
        # authored meaning names `lateness-cause` to separate itself from it, and
        # that mention is prose about a boundary, not an offer.)
        from mre.modules.question_parser import render_intents
        assert "\n  lateness-cause " not in "\n" + render_intents()

    def test_a_demoted_intent_cannot_be_named_by_a_stale_phrasing(self, monkeypatch):
        """A demotion a model can walk around by remembering the id from an
        earlier turn is not a demotion. The emission coerces to `unmatched`,
        which is the second tier — exactly where the shape belongs again."""
        from mre.modules.question_parser import build_parsed

        emission = {"intent": "lateness-cause", "subjects": [],
                    "confidence": 0.95}
        live = build_parsed("why so many late", emission, None, None)
        assert live is not None and live.intent is Intent.LATENESS_CAUSE

        monkeypatch.setitem(
            PROMOTIONS, Intent.LATENESS_CAUSE,
            PROMOTIONS[Intent.LATENESS_CAUSE].demote("a test divergence"))
        after = build_parsed("why so many late", emission, None, None)
        assert after is not None, "a demoted id is a misfiling, never a crash"
        assert after.intent is Intent.UNMATCHED

    def test_demotion_stops_the_shadow(self, monkeypatch):
        """A demoted route is not on probation — there is nothing left to watch."""
        assert Intent.LATENESS_CAUSE in shadowed_intents()
        monkeypatch.setitem(
            PROMOTIONS, Intent.LATENESS_CAUSE,
            PROMOTIONS[Intent.LATENESS_CAUSE].demote("x"))
        assert Intent.LATENESS_CAUSE not in shadowed_intents()

    def test_promotion_is_never_automatic(self):
        """The asymmetry, asserted as an absence: there is no code path that
        ADDS to PROMOTIONS or moves a status toward PROBATION. `demote` is the
        only transition anything can call."""
        assert hasattr(Promotion, "demote")
        assert not hasattr(Promotion, "promote")
        assert not any(hasattr(Promotion, n) for n in ("settle", "approve"))

    def test_probation_is_measured_not_waited_out(self):
        promo = PROMOTIONS[Intent.LATENESS_CAUSE]
        assert promo.status is ProbationStatus.PROBATION
        assert promo.shadowed
        assert promo.sweeps_observed < PROBATION_SWEEPS
        assert promo.shadow_questions, \
            "a probation asks the shape that was promoted, not whatever comes"


# ---------------------------------------------------------------------------
# The shadow diff — the demotion TRIGGER, so false positives are the hazard
# ---------------------------------------------------------------------------

def _bundle(key_facts: dict, records: int = 1):
    return SimpleNamespace(key_facts=key_facts,
                           ordered_records=[{"id": f"r{i}"} for i in range(records)])


def _claims(*pairs):
    return [{"text": t, "status": s} for s, t in pairs]


class TestShadowDiff:

    def test_agreement_on_a_shared_quantity(self):
        d = diff_claims(_bundle({"late_count": 1.0}),
                        _claims(("verified", "Only one order is late.")))
        assert d.agreed == ["late_count"]
        assert d.contradicted == []
        assert not d.diverged

    def test_contradiction_on_a_shared_quantity_fires(self):
        d = diff_claims(_bundle({"late_count": 3.0}),
                        _claims(("verified", "Only one order is late.")))
        assert d.contradicted == ["late_count"]
        assert d.diverged, "R-AI5(7): this is the demotion trigger"

    def test_a_figure_only_one_side_mentions_is_not_a_disagreement(self):
        """The route answers in its authored shape and the shadow reasons in its
        own. Demanding they say the same words would fire on every turn."""
        d = diff_claims(_bundle({"tardiness_total": 370.83}),
                        _claims(("verified", "ORD-05 runs on CUT-01.")))
        assert d.agreed == [] and d.contradicted == []
        assert not d.diverged

    def test_an_interpretive_claim_never_diverges(self):
        """It is a labeled reading, not a competing fact — and the whole point of
        promoting a shape is that the route proves what synthesis could only
        read."""
        d = diff_claims(_bundle({"late_count": 1.0}),
                        _claims(("interpretive", "About four orders look late.")))
        assert not d.diverged
        assert d.contradicted == []

    def test_a_cut_claim_never_diverges(self):
        d = diff_claims(_bundle({"late_count": 1.0}),
                        _claims(("failed", "Nine orders are late.")))
        assert not d.diverged

    def test_agreement_wins_inside_a_sentence(self):
        """A claim that states the figure correctly somewhere has not
        contradicted it, whatever else the sentence also counts."""
        d = diff_claims(
            _bundle({"late_count": 1.0}),
            _claims(("verified", "Only one order is late, out of 15 late-eligible "
                                 "orders in the book.")))
        assert d.agreed == ["late_count"]
        assert not d.diverged

    def test_a_unit_the_label_does_not_have_is_not_that_labels_figure(self):
        """THE SPECIMEN this rule was written from (the first dossier validation):
        890 MINUTES sits four tokens from the word "late" and is not a count of
        orders. A proximity-only rule reported a perfectly correct claim as
        contradicting late_count = 1."""
        text = ("ORD-05 is the only late order, finishing 890 minutes "
                "(nearly 15 hours) past its due date.")
        assert candidates_for(text, "late_count") == []
        d = diff_claims(_bundle({"late_count": 1.0}),
                        _claims(("verified", text)))
        assert not d.diverged, "this claim AGREES with the route"

    def test_a_clock_time_is_not_a_quantity(self):
        """The second specimen: the 59 of "23:59:59" sat six tokens from the word
        "time" and was reported as contradicting on_time_count = 14."""
        text = ("its due date is 2026-01-05 at 23:59:59 UTC, already past by the "
                "time it runs.")
        assert candidates_for(text, "on_time_count") == []
        d = diff_claims(_bundle({"on_time_count": 14.0}),
                        _claims(("verified", text)))
        assert not d.diverged

    def test_an_entity_ref_is_not_a_quantity(self):
        assert candidates_for("ORD-05 is late.", "late_count") == []

    def test_money_reads_with_or_without_a_currency_symbol(self):
        for text in ("The tardiness cost is $370.83.",
                     "incurring 370.83 in tardiness cost"):
            d = diff_claims(_bundle({"tardiness_total": 370.83}),
                            _claims(("verified", text)))
            assert d.agreed == ["tardiness_total"], text

    def test_rounding_is_not_disagreement(self):
        d = diff_claims(_bundle({"tardiness_total": 370.8333}),
                        _claims(("verified", "a tardiness cost of $370.83")))
        assert d.agreed == ["tardiness_total"]

    def test_a_thousands_separator_is_one_number(self):
        """The 4A.5b verifier calibration learned this cutting true claims:
        "$5,906" is not two numbers."""
        d = diff_claims(_bundle({"tardiness_total": 5906.0}),
                        _claims(("verified", "a tardiness cost of $5,906")))
        assert d.agreed == ["tardiness_total"]

    def test_a_list_is_not_a_stated_fact(self):
        """numeric_facts takes SCALARS only. A synthesized `<label>_count` is a
        fact nobody asserts, and its label collides with the real quantities that
        share its words — which is exactly how the first dossier validation
        reported "a tardiness cost of $370.83" as contradicting
        tardiness_lines_count = 1."""
        facts = numeric_facts({"tardiness_lines": [{"cost": 370.83}],
                               "tardiness_total": 370.83, "premise_holds": False})
        assert "tardiness_lines_count" not in facts
        assert facts == {"tardiness_total": 370.83}

    def test_provenance_strengthening_is_reported_never_a_trigger(self):
        """The promotion's own claim: the route CITES what synthesis could only
        label. A promotion that fails to strengthen provenance is a review
        question, not an automatic demotion."""
        d = diff_claims(
            _bundle({"tardiness_total": 370.83}, records=4),
            _claims(("interpretive", "the plan carries 370.83 in tardiness cost")))
        assert d.provenance_strengthened
        assert not d.diverged

    def test_no_synthesizer_is_UNCHECKED_never_clean(self):
        """The 4A.5a door-check discipline: an instrument that cannot run says
        so, and a probation sweep with no key does not serve the window."""
        d = shadow_diff(_bundle({"late_count": 1.0}), None, question="q",
                        intent="lateness-cause")
        assert d.unchecked
        assert not d.diverged
        assert d.agreed == [] and d.contradicted == []


class TestShadowRunner:

    def test_a_route_not_on_probation_is_never_shadowed(self):
        """The shadow costs a full synthesis. It runs for promotions on probation
        and for nothing else."""
        from mre.modules.shadow import run_shadow
        assert run_shadow(None, "q", _bundle({}), "late-orders") is None
        assert run_shadow(None, "q", _bundle({}), "not-an-intent") is None

    def test_a_probation_route_with_no_synthesizer_reports_unchecked(self):
        from mre.modules.shadow import run_shadow
        d = run_shadow(None, "why so many late orders", _bundle({}),
                       "lateness-cause", synthesizer=None)
        assert d is not None and d.unchecked


class TestTheSidecarSignal:

    def test_a_divergence_is_reported_as_the_demotion_trigger(self):
        from mre.ai_exam.sidecar import check_shadow
        turn = SimpleNamespace(
            lineno=1, question="why so many late orders",
            shadow=ShadowDiff(question="q", intent="lateness-cause",
                              contradicted=["late_count"]).model_dump(mode="json"))
        findings = check_shadow(turn)
        assert [f.kind for f in findings] == ["shadow-divergence"]
        assert "DEMOTE" in findings[0].detail

    def test_a_clean_shadow_is_silent(self):
        from mre.ai_exam.sidecar import check_shadow
        turn = SimpleNamespace(
            lineno=1, question="q",
            shadow=ShadowDiff(intent="lateness-cause",
                              agreed=["late_count"]).model_dump(mode="json"))
        assert check_shadow(turn) == []

    def test_an_unchecked_shadow_is_reported_not_folded_into_clean(self):
        from mre.ai_exam.sidecar import check_shadow
        turn = SimpleNamespace(lineno=1, question="q",
                               shadow={"unchecked": True, "intent": "x"})
        assert [f.kind for f in check_shadow(turn)] == ["shadow-unchecked"]

    def test_no_shadow_at_all_is_silent(self):
        from mre.ai_exam.sidecar import check_shadow
        assert check_shadow(SimpleNamespace(lineno=1, question="q",
                                            shadow={})) == []


class TestTheVocabularyBaseline:

    def test_the_constant_is_the_undemoted_baseline(self):
        """MODEL_SELECTABLE_INTENTS does not know about demotion; the FUNCTION
        does. Anything that reads the constant to build the prompt would leak a
        demoted id back to the model."""
        assert set(model_selectable_intents()) <= set(MODEL_SELECTABLE_INTENTS)
        assert Intent.UNKNOWN_ENTITY not in MODEL_SELECTABLE_INTENTS
