"""Session 4A teaching-graft (e2) — the measurement errand's three fixes.

`tests/test_floor_truth.py` holds R-TG6's founding pair and is untouched. This
file holds what the (e2) errand measured and then built:

  F1  the product-behavior predicate, WIDENED by measurement — and the specimen
      is (e)'s own headline success quote, which shipped uncited under the
      general-knowledge label while enumerating what this product computes.
  F2  R-TG7 — an empty teaching drop has a floor. When the seam cuts every claim
      of a teaching answer, the authored card renders: a draft existed, it was
      refused for contradicting what this product computes, and here is the door
      to the verdict the rule was standing in for.
  F3  W4's lead order — the RECORDED DRIVER leads, our calendar scan follows —
      at all THREE emitting sites, the third of which this session's census
      found still unguarded.

WHAT THE M4 CENSUS CHANGED ABOUT THIS FILE'S SHAPE. (e) fixed two sites and said
so; an AST census of every place rendering the "nothing prevented it" assertion
found three. So the F3 tests below assert the ORDER at each site by name rather
than asserting a property of one, and the census script itself
(`tools/spikes/teaching_graft_e2/m4_w4_site_census.py`) is the standing check
that a fourth has not appeared unguarded.
"""
from __future__ import annotations

import pytest

from mre.contracts.synthesis import ClaimKind, DraftClaim
from mre.modules import claim_verifier as cv
from mre.modules import renderers as rd


def _claim(text: str, *, kind=ClaimKind.GENERAL_KNOWLEDGE, records=()):
    return DraftClaim(text=text, record_ids=list(records), kind=kind)


# ---------------------------------------------------------------------------
# F1 — the predicate, widened by measurement
# ---------------------------------------------------------------------------

#: (e) close-out §4, run 1, first claim — quoted verbatim. It rendered under
#: `[general knowledge]`, and a claim carrying record ids is disqualified from
#: that class by `gk_disqualifiers`' first clause, so the label is proof it was
#: uncited.
E_RUN1_CLAIM = (
    "A job becomes impossible to move for one of a small number of specific "
    "reasons this product actually computes, not just a lock: it can be "
    "explicitly frozen or pinned to a resource, it can be excluded from "
    "resources it would need, or it can be boxed in by its own precedence "
    "chain, release date, or calendar with no later opening long enough to "
    "hold it."
)

#: The second specimen, found by the census rather than by the brief: it names
#: our ledger's own components (tardiness, setup cost, overtime) as what decides
#: the sequence, uncited, under the general-knowledge label.
CENSUS_SPECIMEN = (
    "The scheduler itself does not pick a tiebreak rule from a menu — it is "
    "the solver's objective (tardiness, setup cost, overtime) plus hard "
    "constraints like machine capacity and precedence that determine which "
    "order's operation gets the earlier slot."
)


class TestTheWidenedProductBehaviorPredicate:
    """F1. R-TG6 (i) missed the shape (e)'s own fix produced."""

    def test_the_e_session_success_quote_is_the_species(self):
        """THE FINDING, HELD AS A REGRESSION. (e) §4 quotes this as proof the
        fix worked. It is true — and being true is not the discriminator, since
        both of (e)'s own 2-of-99 specimens were true. It enumerates what WE
        compute while wearing the one label that means "there is nothing here to
        check this against", and there is: the docs/05 catalog and the mobility
        floor's own verdict vocabulary."""
        assert cv.product_behavior_disqualifiers(_claim(E_RUN1_CLAIM)) == [
            "it states what this product does"]

    def test_the_census_found_a_second_specimen(self):
        assert cv.product_behavior_disqualifiers(_claim(CENSUS_SPECIMEN))

    @pytest.mark.parametrize("text", [
        "A job becomes immovable for reasons this product computes.",
        "The scheduler determines which operation goes first.",
        "This system never considers setup families.",
    ])
    def test_the_two_widenings_each_carry_their_weight(self, text):
        """The widening is exactly two things: the verbs that assert a
        COMPUTATION we perform, and ONE intervening word. Each specimen here
        needs at least one of them."""
        assert cv.product_behavior_disqualifiers(_claim(text))

    @pytest.mark.parametrize("text", [
        # Verbatim general-knowledge claims from committed sweeps. The whole
        # census (50 transcripts, 522 unique claim lines, 121 of them general
        # knowledge) fires on THREE, and all three are product claims.
        "Tardiness objectives tend to give weak lower bounds.",
        "Sequence-dependent setups reward grouping similar jobs.",
        "In a job shop, a heavily loaded machine becomes a queueing point once "
        "its utilization climbs.",
        "A solver leaves a machine idle with work waiting when every waiting "
        "operation is blocked by something other than machine availability.",
        # THE SHARPEST CONTROL, and the reason the widened verb list contains no
        # bare "the solver": every board claim on this surface says the solver
        # chose something, and reading that as a claim about the product would
        # drop the plainest true sentences we render.
        "The solver chose 2026-01-12 rather than being forced into it.",
        "The solver determined this placement was cheapest.",
    ])
    def test_real_general_knowledge_is_still_untouched(self, text):
        assert not cv.product_behavior_disqualifiers(_claim(text))

    def test_two_intervening_words_do_not_match(self):
        """The allowance is ONE word, measured from the specimen ("actually").
        Widening it further was not measured and is not taken — a pattern map's
        honesty is its bound, which is (e) §5(a)'s whole lesson."""
        assert not cv.product_behavior_disqualifiers(
            _claim("The system in a general sense computes a start time."))


# ---------------------------------------------------------------------------
# F2 — R-TG7, the empty teaching drop's floor
# ---------------------------------------------------------------------------

def _synth_bundle(**kf):
    from mre.modules.explainer import ExplanationBundle
    base = {"unanswerable": True, "claims": [], "cut": [],
            "consulted_tools": ["placements_for_order"], "offers": [],
            "licence": "long"}
    base.update(kf)
    return ExplanationBundle(
        question="what makes a job impossible to move at all",
        subject_id="synthesis", subject_type="synthesis",
        subject_external_name="?", ordered_records=[], key_facts=base,
        snapshot_id="snap", identity_map=None)


def _refuted_cut(reason_tail="it says a lock is the only thing"):
    return {"text": "a job becomes immovable only through a lock",
            "load_bearing": True,
            "reason": cv.FLOOR_REFUTED_PREFIX + reason_tail}


def _ungrounded_cut():
    return {"text": "PRESS-FAST runs at 85%", "load_bearing": True,
            "reason": "no record states this"}


class TestR_TG7_TheEmptyTeachingDropHasAFloor:
    """F2. Session (e) §8(b) measured the collapse; this is the floor under it."""

    def test_the_card_renders_when_every_claim_was_refused(self):
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_FLOOR_REFUTED_EMPTY, SYNTHESIS_FLOOR_REFUTED_EMPTY_DOOR,
        )
        text = rd.TemplateRenderer().render(
            _synth_bundle(cut=[_refuted_cut()]))
        assert SYNTHESIS_FLOOR_REFUTED_EMPTY in text
        assert SYNTHESIS_FLOOR_REFUTED_EMPTY_DOOR in text

    def test_the_capability_card_does_not_also_render(self):
        """"No capability card" is half the ruling: it says nothing was found,
        which is a DIFFERENT fact from "a rule was drafted and refused", and it
        is the false one here."""
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_UNANSWERABLE, SYNTHESIS_UNANSWERABLE_NO_TOOLS,
        )
        text = rd.TemplateRenderer().render(
            _synth_bundle(cut=[_refuted_cut()]))
        assert SYNTHESIS_UNANSWERABLE not in text
        assert SYNTHESIS_UNANSWERABLE_NO_TOOLS not in text

    def test_it_asserts_nothing_about_the_plant(self):
        """The card is a statement about OUR OWN READ. It may not manufacture a
        claim about the plant out of the fact that we refused one — 4B.23's
        fail-safe, and R-TG1 direction (ii)'s reason for existing."""
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_FLOOR_REFUTED_EMPTY, SYNTHESIS_FLOOR_REFUTED_EMPTY_DOOR,
        )
        both = SYNTHESIS_FLOOR_REFUTED_EMPTY + " " + \
            SYNTHESIS_FLOOR_REFUTED_EMPTY_DOOR
        for forbidden in ("ORD-", "PRESS-", "CUT-0", "$", "%"):
            assert forbidden not in both, (
                f"the empty-drop card names board content ({forbidden!r})")

    def test_a_mixed_cut_set_still_renders_it(self):
        """ANY refuted cut is enough — the same precedence R-TG6 gave the
        mixed-answer line. Two precedence rules for one fact is how the two
        drift apart."""
        from mre.modules.ask_fallback_copy import SYNTHESIS_FLOOR_REFUTED_EMPTY
        text = rd.TemplateRenderer().render(
            _synth_bundle(cut=[_ungrounded_cut(), _refuted_cut()]))
        assert SYNTHESIS_FLOOR_REFUTED_EMPTY in text

    def test_the_wording_is_true_of_a_mixed_set(self):
        """It says "including", not "all of them" and not a count — because the
        gate is ANY, the stronger wording would be false on the set above."""
        from mre.modules.ask_fallback_copy import SYNTHESIS_FLOOR_REFUTED_EMPTY
        assert "including" in SYNTHESIS_FLOOR_REFUTED_EMPTY

    @pytest.mark.parametrize("kf,why", [
        ({"licence": "short", "cut": [_refuted_cut()]},
         "not a teaching question — the long licence is granted to `teaching` "
         "and to nothing else"),
        ({"cut": [_ungrounded_cut()]},
         "nothing was refused, so the card's central sentence would be false"),
        ({"cut": []},
         "no cuts at all"),
    ])
    def test_the_ordinary_floor_still_owns_its_own_cases(self, kf, why):
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_FLOOR_REFUTED_EMPTY, SYNTHESIS_UNANSWERABLE,
        )
        text = rd.TemplateRenderer().render(_synth_bundle(**kf))
        assert SYNTHESIS_FLOOR_REFUTED_EMPTY not in text, why
        assert SYNTHESIS_UNANSWERABLE in text, why

    def test_a_teaching_answer_with_surviving_claims_is_untouched(self):
        """The card is for the EMPTY case. An answer that kept something gets
        R-TG6's own cut disclosure beside its claims, which is unchanged."""
        from mre.modules.ask_fallback_copy import (
            SYNTHESIS_FLOOR_REFUTED, SYNTHESIS_FLOOR_REFUTED_EMPTY,
        )
        text = rd.TemplateRenderer().render(_synth_bundle(
            unanswerable=False,
            claims=[{"text": "PACK-01 has a zero-gap chain.",
                     "status": "verified", "cited_record_ids": ["abc12345"]}],
            cut=[_refuted_cut()]))
        assert SYNTHESIS_FLOOR_REFUTED_EMPTY not in text
        assert SYNTHESIS_FLOOR_REFUTED in text

    def test_the_partial_line_still_travels(self):
        """"Every line was refused" and "the budget ran out" are different
        facts. Dropping the second because the first is more interesting is how
        a floor starts lying by omission."""
        from mre.modules.ask_fallback_copy import SYNTHESIS_PARTIAL
        text = rd.TemplateRenderer().render(
            _synth_bundle(cut=[_refuted_cut()], budget_exhausted=True))
        assert SYNTHESIS_PARTIAL.split("—")[0].strip() in text

    def test_the_doors_survive(self):
        """The Lyon rule twice over: the card's own per-bar door, and the warm
        floor's nearest capabilities. A rejection holds a door handle."""
        from mre.modules.ask_fallback_copy import SYNTHESIS_FLOOR_DOORS
        text = rd.TemplateRenderer().render(
            _synth_bundle(cut=[_refuted_cut()],
                          offers=["why can't ORD-BOX op20 move"]))
        assert SYNTHESIS_FLOOR_DOORS in text
        assert "why can't ORD-BOX op20 move" in text

    def test_the_predicate_appends_nothing_on_the_false_path(self):
        """PREMISE. The caller falls through to the ordinary floor on False, so
        a predicate that had already appended a line would corrupt it."""
        lines: list[str] = []
        assert rd.TemplateRenderer._empty_teaching_floor(
            lines, {"licence": "short", "claims": [],
                    "cut": [_refuted_cut()]}) is False
        assert lines == []


class TestR_TG7_ItDoesNotEnterAnswerMemory:
    """The exclusion is asserted, not assumed — the brief's own instruction.

    There is nothing here for a drill-down to open, and remembering the card
    would erase the last real answer a planner could still point at (R-OF1's
    rider, at the neighbouring floor)."""

    def test_an_all_cut_answer_is_unanswerable(self):
        """The mechanism: `Synthesizer.answer` sets `unanswerable` when no claim
        survives, and the dispatch declines to remember an unanswerable answer.
        Both halves are asserted, because the exclusion is now load-bearing."""
        from mre.contracts.synthesis import SynthesisAnswer
        answer = SynthesisAnswer(question="q", claims=[])
        assert not answer.claims
        # The synthesizer's own rule, quoted from its source so this test fails
        # if the rule moves rather than passing over a stale belief about it.
        import inspect
        from mre.modules import synthesizer as sz
        src = inspect.getsource(sz.Synthesizer)
        assert "if not answer.claims:" in src
        assert "answer.unanswerable = True" in src

    def test_the_dispatch_gates_remember_on_it(self):
        import inspect
        from mre.modules import interpreter as it
        src = inspect.getsource(it)
        assert "if memory is not None and not answer.unanswerable:" in src, (
            "the ANSWER_MEMORY write is no longer gated on `unanswerable`, so "
            "the R-TG7 card can now be remembered as an answer")


# ---------------------------------------------------------------------------
# F3 — the record leads, at all three sites
# ---------------------------------------------------------------------------

_DRIVER_SENTENCE = "records its driver as CAPACITY_BLOCKED"
_SCAN_SENTENCE = "My own scan"


def _order(text: str, first: str, second: str) -> bool:
    """True when `first` appears before `second` and both appear."""
    a, b = text.find(first), text.find(second)
    return a != -1 and b != -1 and a < b


class TestF3TheRecordLeads:
    """(e) §8(e) left the order undecided; arbitrated 2026-08-05.

    THE DISAGREEMENT AND THE REFUSAL TO ADJUDICATE ARE UNCHANGED. Only the order
    moves — the record is something this run WROTE DOWN and a planner can go and
    look at, while the scan is our own derivation computed now. Leading with the
    derivation makes the record read as a caveat on our finding; leading with
    the record makes our finding read as what it is, a second opinion."""

    def test_the_lead_site_puts_the_record_first(self):
        out = rd.TemplateRenderer()._mobility_correction(
            {"order": "ORD-EARLY", "op_seq": 10, "machine": "BOX-01",
             "chosen_driver": "CAPACITY_BLOCKED"},
            {"open_directions": ["earlier"]})
        assert _order(out, _DRIVER_SENTENCE, _SCAN_SENTENCE), out
        assert "do not agree" in out

    def test_the_lead_site_still_refuses_to_adjudicate(self):
        out = rd.TemplateRenderer()._mobility_correction(
            {"order": "ORD-EARLY", "op_seq": 10, "machine": "BOX-01",
             "chosen_driver": "CAPACITY_BLOCKED"},
            {"open_directions": ["earlier"]})
        assert "nothing was holding" not in out, (
            "the assertion the ruling forbids came back")

    @pytest.mark.parametrize("renderer,kf", [
        ("_render_why_here", {
            "verdict": "chose", "order": "ORD-EARLY", "op_seq": 10,
            "machine": "BOX-01", "chosen_driver": "CAPACITY_BLOCKED",
            "binding": {"at": "2026-01-10 07:00", "family": "B1", "facts": {}},
            "actual_start": "2026-01-12 07:00"}),
        ("_render_counterfactual", {
            "verdict": "chose", "op_seq": 10, "machine": "BOX-01",
            "chosen_driver": "CAPACITY_BLOCKED",
            "binding": {"at": "2026-01-10 07:00"}}),
    ])
    def test_both_body_sites_put_the_record_first(self, renderer, kf):
        from mre.modules.explainer import ExplanationBundle
        bundle = ExplanationBundle(
            question="why cant ORD-EARLY op10 start earlier",
            subject_id="o", subject_type="order",
            subject_external_name="ORD-EARLY", ordered_records=[],
            key_facts=kf, snapshot_id="snap", identity_map=None)
        lines: list[str] = []
        getattr(rd.TemplateRenderer(), renderer)(lines, bundle)
        out = "\n".join(lines)
        assert _order(out, _DRIVER_SENTENCE, _SCAN_SENTENCE), out
        assert "disagree" in out

    def test_the_third_site_was_unguarded_before_this_session(self):
        """M4's finding, held as a regression. `_render_counterfactual` — the
        `what-would-change` route — rendered "It was not prevented from going
        earlier" and then printed a blocker-naming driver one line down. (e)
        censused two sites and fixed two; there were three."""
        from mre.modules.explainer import ExplanationBundle
        bundle = ExplanationBundle(
            question="what would let ORD-EARLY op10 start earlier",
            subject_id="o", subject_type="order",
            subject_external_name="ORD-EARLY", ordered_records=[],
            key_facts={"verdict": "chose", "op_seq": 10, "machine": "BOX-01",
                       "chosen_driver": "CAPACITY_BLOCKED",
                       "binding": {"at": "2026-01-10 07:00"}},
            snapshot_id="snap", identity_map=None)
        lines: list[str] = []
        rd.TemplateRenderer()._render_counterfactual(lines, bundle)
        out = "\n".join(lines)
        assert "It was not prevented from going earlier" not in out
        assert "Nothing has to change" not in out

    def test_a_preference_driver_keeps_the_plain_sentence_at_every_site(self):
        """THE TRUE NEGATIVE, and it is what stops the fix eating the answer.
        Where the record names a PREFERENCE, there is no disagreement to
        disclose and the confident sentence is correct."""
        from mre.modules.explainer import ExplanationBundle
        bundle = ExplanationBundle(
            question="what would let ORD-EARLY op10 start earlier",
            subject_id="o", subject_type="order",
            subject_external_name="ORD-EARLY", ordered_records=[],
            key_facts={"verdict": "chose", "op_seq": 10, "machine": "BOX-01",
                       "chosen_driver": "COST_TRADEOFF",
                       "binding": {"at": "2026-01-10 07:00"}},
            snapshot_id="snap", identity_map=None)
        lines: list[str] = []
        rd.TemplateRenderer()._render_counterfactual(lines, bundle)
        out = "\n".join(lines)
        assert "Nothing has to change" in out
        assert "disagree" not in out

    def test_the_fourth_site_is_guarded_by_the_same_one_definition(self):
        """THE TRIPWIRE FIRED AND THIS IS ITS REPLACEMENT.

        (e2) left `mobility_lead_line`'s earlier-open branch asserting "Nothing
        was holding X back" with no driver in hand, and pinned the gap with a
        test that failed the day the payload gained one. Session (d.2)'s rider
        R1 sized it: 0 of 386 on the demo board — a TAUTOLOGY, since
        `earlier-open` needs `later_at` to be None and no plant that keeps
        working produces that — and **1 of 1 on the fenced specimen world**, the
        only board where the branch renders. ORD-EARLY op10, CAPACITY_BLOCKED.

        So the payload carries `chosen_driver` now and this site goes through
        the SAME `counterfactual_contradicts_driver` as the other three, in the
        same arbitrated order: the record leads, the scan is a second opinion,
        and neither is deleted."""
        import ast
        import inspect
        import textwrap
        from mre.modules import explainer as ex
        from mre.modules.explainer import ExplanationBundle

        # THE PAYLOAD'S KEYS, OFF THE AST — not a substring search of the
        # source. A text search passes on the explanatory comment beside the
        # line, which is a guard watching a comment; the negative control for
        # this very assertion caught it doing exactly that.
        tree = ast.parse(textwrap.dedent(
            inspect.getsource(ex.Explainer._mobility_facts)))
        keys = {k.value for node in ast.walk(tree)
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
                for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        assert "chosen_driver" in keys, (
            "the mobility-lead payload must carry the driver, or the fourth W4 "
            f"site has nothing to guard with; keys are {sorted(keys)}")

        def lead(driver):
            bundle = ExplanationBundle(
                question="what would have to change for ORD-EARLY",
                subject_id="d", subject_type="counterfactual",
                subject_external_name="ORD-EARLY", ordered_records=[],
                key_facts={"mobility_lead": {
                    "order": "ORD-EARLY", "op_seq": 10, "machine": "BOX-01",
                    "verdict": "earlier-open", "open_directions": ["earlier"],
                    "chosen_driver": driver}},
                snapshot_id="snap", identity_map=None)
            return rd.mobility_lead_line(bundle) or ""

        blocked = lead("CAPACITY_BLOCKED")
        assert "Nothing was holding" not in blocked
        assert "records its driver as CAPACITY_BLOCKED" in blocked
        # THE RECORD LEADS: the driver is named before our own scan.
        assert blocked.index("records its driver") < blocked.index("My own scan")
        assert "do not agree" in blocked

        # A PREFERENCE DRIVER IS SILENT, and an UNRECOGNISED one claims nothing
        # — the 4B.23 fail-safe, unchanged at this site as at the other three.
        for quiet in ("COST_TRADEOFF", "SOMETHING_WE_DO_NOT_KNOW", None, ""):
            assert "Nothing was holding" in lead(quiet)
