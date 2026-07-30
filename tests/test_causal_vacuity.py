"""CU3 (Session 4B.5) — the vacuous-causal tripwire, and the why-on-machine audit.

THE SPECIMEN. "why is ORD-000008 on PAINT-02?" answered "because the machine was
busy with other work [record: bafa03f1…]".

THE AUDIT (CU3a), stated before the fix, because which path is at fault decides
what to change:

  * record ``bafa03f1-1213-4e9b-9989-cb2ab529bec8`` is a REAL ``assignment``
    Decision (module M7, ``driver: CAPACITY_BLOCKED``, ``basis: reconstructed``);
  * the clause is ``DRIVER_PHRASING["CAPACITY_BLOCKED"]`` VERBATIM.

So the verbatim path is INTACT — this was not an LLM rewording authored copy (the
4A.5b CU4 breach class). The defect is in the assembler: it used the driver
phrase as the WHOLE causal clause, and that phrase names no machine, no
alternative and no quantity. On a why-on-MACHINE question it is worse than thin —
the machine that was busy is one the order did NOT get.

The testimony validator passed it, and was right to: every check it makes is
about FABRICATION, and an unfalsifiable sentence fabricates nothing.

TWO FIXES, at two levels, and they are not substitutes:

  (a) the PATH — a CAPACITY_BLOCKED placement now reads its concrete story out of
      the solved occupancy (which eligible machines existed, what held them), or
      says plainly that the occupancy does not attribute it;
  (b) the FLOOR — every causal route gains a vacuity check, and an answer that
      names no driver, no entity beyond the question's own subjects and no
      quantity FAILS CLOSED to the template.
"""
from __future__ import annotations

import pytest

from mre.modules.explainer import ExplanationBundle
from mre.modules.planner_language import DRIVER_PHRASING
from mre.modules.renderers import (
    CAUSAL_SUBJECT_TYPES,
    LLMRenderer,
    TemplateRenderer,
    causal_material,
    causal_vacuity,
)


# ===========================================================================
# (a) THE AUDIT — what the record actually was
# ===========================================================================

class TestTheAudit:
    def test_the_clause_is_authored_copy_carried_verbatim(self):
        """The finding that decides which path to fix: the founder's sentence is
        the authored driver phrase, character for character. Nothing reworded
        it — so the verbatim-render path is not the defect."""
        assert DRIVER_PHRASING["CAPACITY_BLOCKED"] == \
            "the machine was busy with other work"

    def test_the_phrase_names_nothing_a_planner_can_check(self):
        """Why it is vacuous IN THIS FRAME, spelled out: no machine, no order, no
        quantity. As a supporting clause under a concrete story it is fine; as the
        whole answer to "why is X on Y" it is unfalsifiable."""
        phrase = DRIVER_PHRASING["CAPACITY_BLOCKED"]
        assert not any(ch.isdigit() for ch in phrase)
        assert "-" not in phrase                     # no entity ref of any shape

    def test_every_fabrication_check_passes_it(self):
        """The reason it shipped. The validator asks "is anything made up"; an
        unfalsifiable sentence makes nothing up, so a fabrication check can never
        be the thing that catches this class."""
        r = LLMRenderer.__new__(LLMRenderer)
        issues = LLMRenderer._validate_testimony(
            r, "ORD-000008 is on PAINT-02 because the machine was busy with "
               "other work. [record: bafa03f1...]",
            known_ts=set(), known_time=set(),
            known_machines={"PAINT-02"},
            known_records={"bafa03f1-1213-4e9b-9989-cb2ab529bec8"})
        assert issues == []


# ===========================================================================
# (b) THE STRUCTURAL GUARD — hand-built vacuous renders
# ===========================================================================

SUBJECTS = {"ORD-000008", "PAINT-02"}
ENTITIES = {"ORD-000012", "PAINT-01", "ORD-000008", "PAINT-02"}


def _vacuity(text):
    return causal_vacuity(text, subjects=SUBJECTS, entities=ENTITIES,
                          driver_phrases=set())


class TestTheTripwire:
    """Hand-built renders, so the floor is proven against the shapes rather than
    against one specimen. Driver phrases are suppressed here (``driver_phrases=
    set()``) so the OTHER two ways of saying something are exercised on their
    own; the phrase route has its own test below."""

    @pytest.mark.parametrize("text", [
        "It is placed there because of how the schedule worked out.",
        "ORD-000008 is on PAINT-02 because that is where the solver put it.",
        "PAINT-02 was the right choice for ORD-000008.",
        "  \n  ",
        "[record: bafa03f1...] [record: 12ab34cd...]",
        "This placement follows from the constraints. [record: bafa03f1...]",
    ])
    def test_a_vacuous_causal_answer_is_caught(self, text):
        assert _vacuity(text) is not None

    def test_naming_the_questions_own_subjects_back_is_not_an_answer(self):
        # the sharpest case: both nouns present, nothing else. "Why is X on Y"
        # answered "X is on Y" is the shape that reads as an answer and is not.
        assert _vacuity("ORD-000008 is on PAINT-02.") is not None

    @pytest.mark.parametrize("text,why", [
        ("PAINT-01 was running ORD-000012 at the time.", "another entity"),
        ("It could not start before 09:15.", "a quantity"),
        ("It was 3rd in the queue.", "a quantity"),
        ("ORD-000008 is on PAINT-02; PAINT-01 was occupied.", "another entity"),
    ])
    def test_an_answer_that_says_something_passes(self, text, why):
        assert _vacuity(text) is None, why

    def test_a_quantity_in_WORDS_is_not_detected_a_named_limit(self):
        """Stated rather than discovered later: a quantity is a DIGIT. "Two other
        jobs were ahead of it" states a real one and still fails closed to the
        template. That is the safe direction for a floor, and cheaper than
        teaching a tripwire to read numerals in words."""
        assert _vacuity("Two other jobs were ahead of it.") is not None

    def test_the_questions_own_refs_are_not_counted_as_quantities(self):
        """The subtlest way this guard could have been useless: entity refs carry
        digits, so scanning the raw text would let "ORD-000008 is on PAINT-02"
        count as stating a quantity — the exact shape it exists to catch."""
        assert _vacuity("ORD-000008 is on PAINT-02.") is not None

    def test_a_driver_phrase_alone_passes_the_floor_BY_DESIGN(self):
        """The named limit, asserted so it can never be quietly assumed away: the
        founder's own answer PASSES this check, because it reaches for the plant's
        causal vocabulary. That is why CU3 has two halves — the floor catches
        answers that say nothing at all; a vocabulary that says too little is
        fixed in the vocabulary (CU3a), not here."""
        text = "ORD-000008 is on PAINT-02 because the machine was busy with " \
               "other work."
        assert causal_vacuity(text, subjects=SUBJECTS, entities=ENTITIES) is None
        # ... and with the driver vocabulary suppressed, the same sentence is
        # exactly as empty as it reads.
        assert _vacuity(text) is not None

    def test_the_rendered_by_footer_never_rescues_an_empty_answer(self):
        assert _vacuity(
            "It worked out that way.\n[rendered by: LLM (x) | register: testimony]"
        ) is not None

    def test_the_causal_class_is_exactly_the_four_routes_the_ruling_names(self):
        # why-on-machine and why-late both assemble as "demand"
        assert CAUSAL_SUBJECT_TYPES == {"demand", "start_reason", "gap_between"}


# ===========================================================================
# The guard on the real render path — fail closed to the template
# ===========================================================================

def _causal_bundle(cause: str) -> ExplanationBundle:
    return ExplanationBundle(
        question="why is ORD-000008 on PAINT-02?",
        subject_id="dem-8", subject_type="demand",
        subject_external_name="ORD-000008",
        ordered_records=[{
            "record_type": "decision", "record_id": "bafa03f1-1213-4e9b",
            "module": "M7", "decision_type": "assignment",
            "driver": "CAPACITY_BLOCKED", "basis": "reconstructed",
            "subjects": [], "message": "assigned", "alternatives": [],
        }],
        key_facts={"machine_ref": "PAINT-02", "cause": cause,
                   "order": "ORD-000008"},
        snapshot_id="snap-x", identity_map=None,
    )


class _StubLLM(LLMRenderer):
    """A renderer whose model returns one canned answer — the seam the fail-closed
    tests already use, pointed at the vacuity check."""

    def __init__(self, answer: str) -> None:
        self._model = "stub"
        self._client = object()
        self._available = True
        self._fallback_reason = ""
        self._answer = answer

    def _call_llm(self, prompt: str) -> str:  # noqa: D102
        return self._answer


def test_a_vacuous_llm_answer_on_a_causal_route_falls_back_to_the_template():
    r = _StubLLM("It is placed there because of how the schedule worked out.")
    out = r.render(_causal_bundle("the machine was busy with other work"))
    # Session 4B.21 Item 5(a): the tripwire's own verdict left the ANSWER
    # SURFACE — it was developer output on a planner's screen — and the
    # rendered-by tag was renamed, because "template (LLM validated)" read as
    # though the model had validated the answer when it meant the opposite.
    # The verdict is still produced and still checked; it now lives where a
    # dev surface reads it.
    assert "vacuous causal answer" in " ".join(r.last_diagnostics)
    assert "vacuous causal answer" not in out, (
        "the check's internal verdict is back on the planner's surface")
    assert "rendered by: template (model draft rejected)" in out
    # the template body — the thing composed from the evidence — is what ships
    assert "PAINT-02" in out


def test_a_substantive_llm_answer_is_kept():
    out = _StubLLM(
        "ORD-000008 is on PAINT-02 because PAINT-01 was running ORD-000012 "
        "until 09:15. [record: bafa03f1]"
    ).render(_causal_bundle("the machine was busy with other work"))
    assert "rendered by: LLM" in out
    assert "vacuous" not in out


def test_a_NON_causal_route_is_not_subject_to_the_tripwire():
    """The guard is scoped to answers that CLAIM A CAUSE. A schedule listing or a
    count says nothing causal and must not be second-guessed for it."""
    b = _causal_bundle("x")
    b.subject_type = "inventory"
    out = _StubLLM("There are things in the plan. [record: bafa03f1]").render(b)
    assert "vacuous" not in out


def test_causal_material_separates_the_questions_own_nouns_from_the_evidence():
    subjects, _entities = causal_material(_causal_bundle("x"))
    assert subjects == {"ORD-000008", "PAINT-02"}


# ===========================================================================
# (a) THE PATH FIX — the capacity-forced answer names its alternatives
# ===========================================================================

def _capacity_bundle(alternatives, only_option=False) -> ExplanationBundle:
    b = _causal_bundle("the machine was busy with other work")
    b.key_facts.update({"driver_code": "CAPACITY_BLOCKED",
                        "blocked_alternatives": alternatives,
                        "only_option": only_option})
    return b


def test_the_specimen_now_names_the_blocked_alternative():
    out = TemplateRenderer().render(_capacity_bundle([
        {"machine": "PAINT-01", "blocker_order": "ORD-000012",
         "from": "2026-01-08 07:00", "until": "2026-01-08 09:15"},
    ]))
    assert "the machines that could have run it instead were occupied" in out
    assert "PAINT-01 was running ORD-000012 until 2026-01-08 09:15." in out
    # and it is no longer vacuous by the floor's own measure, with the driver
    # vocabulary suppressed — it says something on its own terms
    assert causal_vacuity(out, subjects=SUBJECTS, entities=ENTITIES,
                          driver_phrases=set()) is None


def test_an_unattributable_capacity_block_is_NAMED_as_unattributable():
    """Eligible alternatives exist but the occupancy shows none of them blocked.
    The answer says so — it does not invent a mechanism to fill the gap."""
    out = TemplateRenderer().render(_capacity_bundle([]))
    assert "doesn't show which alternative was blocked" in out
    assert "won't name one" in out


def test_the_only_eligible_machine_is_a_CAPABILITY_fact_and_says_so():
    """Session 4B.13 Item 1 sharpened this. The answer used to LEAD with the
    capacity clause and then contradict it: "the machines that could have run it
    instead were occupied ... In fact it is the only machine that can run this
    step" — two sentences that cannot both be true. With no eligible alternative
    the cause is CAPABILITY, which is what this test has always been named for,
    so the capacity lead is no longer said at all."""
    out = TemplateRenderer().render(_capacity_bundle([], only_option=True))
    assert "the only machine qualified to run this step" in out
    assert "there was no alternative to weigh" in out
    # THE CONTRADICTION, pinned as absent: no occupied-alternatives claim may
    # accompany a no-alternatives fact.
    assert "the machines that could have run it instead were occupied" not in out


def test_a_non_capacity_driver_keeps_its_own_authored_clause():
    b = _causal_bundle("grouping similar jobs together saved changeover time")
    b.key_facts["driver_code"] = "SETUP_AMORTIZATION"
    out = TemplateRenderer().render(b)
    assert "grouping similar jobs together saved changeover time" in out
