"""R-TG6 — TEACHING SPEAKS WITH THE FLOOR'S VOICE OR NOT AT ALL.

Session 4A teaching-graft (e). The guard for the defect the C9 founder round
found, which is the defect RUBRIC C9/H1 was written to name: a teaching answer
stated a principle that is FALSE of this product, and this product's own
deterministic floor had proven it false on the same board three questions
earlier.

THE FOUNDING PAIR, and it is the regression this file exists to hold. On the
fenced world `datasets/mobility_box`:

  Q7  "why cant this be moved"  [ORD-BOX:BOX-01:20]
      -> the mobility floor computes BOXED_IN. No lock. No pin. The world was
         BUILT so that a bar is boxed in with no lock (R-SW1).

  Q9  "what makes a job impossible to move at all"   (minutes later)
      -> "In this product, a job becomes immovable ONLY through a
          frozen_assignment or pinned constraint declared in locks.csv ...
          nothing else in the catalog removes an operation's mobility
          outright."   [general knowledge]

The founder read Q9 and reported himself satisfied. That is the harm profile
this file guards: not a visible error, a confident reader carrying a wrong rule.

WHAT THESE TESTS CAN AND CANNOT GRADE, stated because the exam bank cannot.
A sweep grades ROUTES and RELATIONS; it has no way to say "this sentence must
not be the same claim as that one". Body truth is gradeable only here, by
construction, which is one more line of Q7 input for the ladder session's format
work (R-EX2).
"""
from __future__ import annotations

import re

import pytest

from mre.contracts.synthesis import ClaimKind, ClaimStatus, DraftClaim
from mre.modules import claim_verifier as cv
from mre.modules import mobility_premise as mp
from mre.modules import renderers as rd


def _claim(text: str, *, kind=ClaimKind.GENERAL_KNOWLEDGE, records=()):
    return DraftClaim(text=text, kind=kind, record_ids=list(records))


# The founding sentence, verbatim from tools/spikes/teaching_graft_c/c9_answers/q9.md
FOUNDING = (
    "In this product, a job becomes immovable only through a frozen_assignment "
    "or pinned constraint declared in locks.csv (lock_type: frozen = immovable, "
    "pinned_resource, or pinned_start) — that is the in-core, proven mechanism "
    "for pinning; nothing else in the catalog removes an operation's mobility "
    "outright.")

# The SAME wrong rule as a CITED board claim — q9.md's first line. It proves why
# (iii) may not be scoped to general-knowledge claims.
FOUNDING_AS_BOARD_CLAIM = (
    "Nothing in this schedule is actually locked: the mechanism that makes a "
    "job immovable is a lock/frozen-assignment constraint (lock_type = frozen, "
    "pinned_resource or pinned_start), and no order here carries one.")

# The paraphrase THIS SESSION'S OWN FIX produced on its first live run, before
# the exclusivity map held the "A, not from B" construction. Kept as a specimen
# because it is the honest measure of what a pattern map is: it holds the shapes
# a model has been SEEN to use, and it was widened by measurement, not by guess.
FOUNDING_PARAPHRASE = (
    "In this run's own data there is no priced move open, and none of the 9 "
    "known orders show any lock or frozen-zone flag — so nothing on this board "
    "is currently showing as immovable; the immovability comes from a lock or "
    "the frozen zone, not from anything intrinsic to a job's lateness or "
    "timing.")


class TestTheFloorVocabularyRefutesTheRule:
    """R-TG6 (iii). The general rule, against the floor's own verdict set."""

    @pytest.mark.parametrize("text", [FOUNDING, FOUNDING_AS_BOARD_CLAIM,
                                      FOUNDING_PARAPHRASE])
    def test_the_wrong_rule_is_refused(self, text):
        assert cv.floor_contradictions(_claim(text)), (
            "a rule this product's own mobility floor falsifies was admitted")

    def test_it_is_refused_whatever_label_it_wears(self):
        """The founding answer said it TWICE — once as general knowledge and
        once as a cited board claim. A check scoped to the GK label would have
        caught one of the two sentences that said it."""
        for kind in (ClaimKind.GENERAL_KNOWLEDGE, ClaimKind.FACT,
                     ClaimKind.CONCLUSION):
            assert cv.floor_contradictions(
                _claim(FOUNDING_AS_BOARD_CLAIM, kind=kind)), kind

    def test_the_premise_the_rule_is_false_against(self):
        """THE PREMISE TEST — the vocabulary really does contain a lockless
        immobility verdict, so the refutation is not a hardcoded opinion.

        `assess` is asked with no hold, no pin and no chunking, an earlier
        direction that is BOUND and no opening later: BOXED_IN. Nothing in that
        call is a lock. If this ever stops being true the rule above stops being
        wrong, and this test is what says so."""
        v = mp.assess(held_kind="", held_at=None, chunk_count=0,
                      later_at=None, earlier_verdict="could_not")
        assert v.verdict == mp.VERDICT_BOXED_IN
        assert v.holds is True
        assert v.held_kind == "", "a boxed-in verdict must carry no lock"

    def test_a_true_general_sentence_about_mobility_survives(self):
        """The map must not swallow correct teaching. This says several things
        decide mobility — which is what the floor actually computes."""
        ok = ("Whether an operation can move earlier depends on precedence, "
              "machine capacity, eligibility and calendars together, not on a "
              "single rule.")
        assert not cv.floor_contradictions(_claim(ok))

    def test_the_reason_names_the_verdict_that_refutes_it(self):
        """A drop whose reason is "it was wrong" teaches nobody anything."""
        reasons = cv.floor_contradictions(_claim(FOUNDING))
        assert "boxed-in" in reasons[0]


class TestTheProductBehaviorClass:
    """R-TG6 (i). A sentence about US is not general knowledge."""

    @pytest.mark.parametrize("text,why", [
        (FOUNDING, "in this product / catalog / locks.csv"),
        ("Freezing is implemented through explicit lock records with a "
         "lock_type such as 'frozen'.", "our declared schema"),
        ("The constraint catalog lists disjunctive capacity as in-core and "
         "proven.", "our catalog's own status words"),
    ])
    def test_it_may_not_wear_the_general_knowledge_label(self, text, why):
        assert cv.product_behavior_disqualifiers(_claim(text)), why

    @pytest.mark.parametrize("text", [
        "Tardiness objectives tend to give weak lower bounds.",
        "Sequence-dependent setups reward grouping similar jobs.",
        "In a job shop, a heavily loaded machine becomes a queueing point once "
        "its utilization climbs.",
        "A solver leaves a machine idle with work waiting when every waiting "
        "operation is blocked by something other than machine availability.",
    ])
    def test_real_general_knowledge_is_untouched(self, text):
        """MEASURED, NOT ASSUMED: these are verbatim general-knowledge claims
        from committed sweeps. The census behind this class ran the predicate
        over all 99 unique GK claims across every committed sweep and it fired
        on 2 — both of them genuine product claims wearing the wrong label."""
        assert not cv.product_behavior_disqualifiers(_claim(text))

    def test_the_bare_word_solver_is_not_a_product_claim(self):
        """THE PATTERN SET'S SHARPEST DELIBERATE OMISSION. Every board claim on
        this surface says "the solver chose"; reading that as a claim about the
        product would drop the plainest true sentences we render."""
        assert not cv.product_behavior_disqualifiers(
            _claim("The solver chose 2026-01-12 rather than being forced into it."))

    def test_a_cited_product_claim_is_left_alone(self):
        """4B.15 §5a.43 built exactly one honest path for a capability claim —
        ground it in the docs/05 catalog. This check must push toward that path,
        never close it, so the DISCRIMINATOR IS THE CITATION."""
        text = ("The constraint catalog lists disjunctive capacity as in-core "
                "and proven.")
        cited = _claim(text, kind=ClaimKind.FACT, records=["abc12345"])
        # The predicate still recognises the sentence for what it is...
        assert cv.product_behavior_disqualifiers(cited)
        # ...and the DROP is gated on `not cited` at the verify seam, which the
        # end-to-end test below proves rather than this unit assertion.


class TestTheMobilityVerdictMeetsTheClaim:
    """R-TG6 (ii). A named order's floor verdict, against what the claim says
    about it. The floor is ASKED, never re-derived."""

    class _Floor:
        """A toolbox whose explainer answers `order_mobility_verdicts` — the
        same shape `Explainer` returns."""

        def __init__(self, verdicts):
            self._ex = self
            self._verdicts = verdicts
            self._order_refs = {"ORD-BOX": 1, "ORD-SPAN": 1}
            self._machine_refs = {"BOX-01": 1}
            self._order_shape_patterns = []
            self.consulted = []

        def order_mobility_verdicts(self, ref, document=None):
            return self._verdicts.get(ref, [])

    def _assertions(self, text, tb):
        return cv.extract_assertions(
            text, order_refs=tb._order_refs, machine_refs=tb._machine_refs,
            order_shapes=[])

    def test_the_founding_example_is_refused(self):
        """"ORD-BOX likewise shows no lock" — offered as an instance of a job
        that is not stuck, about the one bar the floor had computed BOXED_IN."""
        tb = self._Floor({"ORD-BOX": [
            {"verdict": mp.VERDICT_LATER_OPEN, "holds": False, "op_seq": 10},
            {"verdict": mp.VERDICT_BOXED_IN, "holds": True, "op_seq": 20},
        ]})
        text = ("ORD-BOX shows no lock, just two sequential operations, and the "
                "job is still free to move if the planner acts on it.")
        bad = cv.mobility_contradictions(
            _claim(text), self._assertions(text, tb), toolbox=tb)
        assert bad, "an order the floor says is boxed in was called movable"
        assert "boxed-in" in bad[0] and "op20" in bad[0]

    def test_checking_the_first_operation_would_have_missed_it(self):
        """THE REASON `order_mobility_verdicts` EXISTS. ORD-BOX op10 has room
        later; op20 is the boxed-in one. An order is free to move only if its
        operations are, so stopping at the first would clear this order."""
        tb = self._Floor({"ORD-BOX": [
            {"verdict": mp.VERDICT_LATER_OPEN, "holds": False, "op_seq": 10},
        ]})
        text = "ORD-BOX is still free to move if the planner acts on it."
        assert not cv.mobility_contradictions(
            _claim(text), self._assertions(text, tb), toolbox=tb)

    def test_undecidable_contradicts_nothing(self):
        """THE RULED SPECIES, AT A SEVENTH SEAM. The same founding claim also
        named ORD-SPAN, whose operation is chunked and whose verdict is
        UNDECIDABLE — neither `holds` nor `refutes`. Reading it as a
        contradiction would manufacture a claim about the plant out of a limit
        of our own method."""
        tb = self._Floor({"ORD-SPAN": [
            {"verdict": mp.VERDICT_UNDECIDABLE, "holds": False, "chunk_count": 2,
             "op_seq": 10},
        ]})
        text = "ORD-SPAN is still free to move if the planner acts on it."
        assert not cv.mobility_contradictions(
            _claim(text), self._assertions(text, tb), toolbox=tb)

    def test_a_claim_that_asserts_no_mobility_pays_nothing(self):
        """The floor read is expensive and is paid only on a sentence that has
        earned it — one that BOTH asserts free mobility AND names an order."""
        class _Boom(self._Floor):
            def order_mobility_verdicts(self, ref, document=None):
                raise AssertionError("the floor was read for no reason")

        tb = _Boom({})
        text = "ORD-BOX runs two operations, on FEED-01 and BOX-01."
        assert not cv.mobility_contradictions(
            _claim(text), self._assertions(text, tb), toolbox=tb)

    def test_an_unreadable_floor_refutes_nothing(self):
        class _Broken(self._Floor):
            def order_mobility_verdicts(self, ref, document=None):
                raise RuntimeError("no")

        tb = _Broken({})
        text = "ORD-BOX is still free to move."
        assert not cv.mobility_contradictions(
            _claim(text), self._assertions(text, tb), toolbox=tb)


class TestTheCounterfactualAndTheRecordedDriver:
    """W4 — Specimen C, reproduced on the purpose-built bar (q8.md)."""

    def test_a_blocker_driver_contradicts_nothing_prevented_it(self):
        assert rd.counterfactual_contradicts_driver("CAPACITY_BLOCKED")

    @pytest.mark.parametrize("driver", [
        "COST_TRADEOFF", "DUE_DATE_PRESSURE", "SETUP_AMORTIZATION",
        "EARLINESS_PREFERENCE", "POLICY_RULE", "SOLVER_LIMIT",
        "PLANNER_DIRECTIVE",
    ])
    def test_a_preference_driver_does_not(self, driver):
        """These name why the solver PREFERRED the placement, which is what a
        `chose` verdict already says. They are silent here, deliberately."""
        assert not rd.counterfactual_contradicts_driver(driver)

    @pytest.mark.parametrize("driver", [None, "", "WAT", "not_a_code"])
    def test_an_unrecognised_driver_claims_nothing(self, driver):
        """4B.23's fail-safe rule, and the reason this is a NAMED SET rather
        than a "not in the preference list" test: a driver whose meaning we do
        not know must not be read as naming a blocker."""
        assert not rd.counterfactual_contradicts_driver(driver)

    def test_every_member_is_a_real_driver_code(self):
        """A set of strings drifts from the vocabulary it mirrors unless
        something asserts it does not."""
        from mre.contracts.vocabularies import DriverCode
        known = {d.value for d in DriverCode}
        assert rd.CONSTRAINT_NAMING_DRIVERS <= known


class TestTheClosureIsVoiced:
    """W5 — "no opening fits" and "the machine is gone" are different facts."""

    def test_a_shut_calendar_says_so(self):
        out = rd.TemplateRenderer._no_later_clause(
            "BOX-01", {"no_later_kind": "calendar_closed",
                       "closes_at": "2026-01-13 19:00"})
        assert "not open at all after 2026-01-13 19:00" in out
        assert "not a busy machine" in out

    def test_the_bound_is_stated_never_never(self):
        """`_open_windows` resolves the calendar over the solved span padded a
        fortnight, so this can only say the machine does not reopen WITHIN THAT
        SPAN. "Never reopens" would be a claim about a calendar we did not
        read."""
        out = rd.TemplateRenderer._no_later_clause(
            "BOX-01", {"no_later_kind": "calendar_closed",
                       "closes_at": "2026-01-13 19:00"})
        assert "span this plan covers" in out
        assert "never" not in out.lower()

    def test_a_busy_machine_keeps_the_original_wording(self):
        out = rd.TemplateRenderer._no_later_clause(
            "PACK-01", {"no_later_kind": "no_window_fits"})
        assert "No opening on PACK-01 fits the whole operation" in out

    def test_an_unreadable_calendar_falls_to_the_busy_wording(self):
        """THREE STATES, NEVER TWO. A scan we could not run must not read as a
        closure — the honest floor is to say what was scanned and claim nothing
        about why."""
        for mob in ({}, {"no_later_kind": ""},
                    {"no_later_kind": "calendar_closed", "closes_at": None}):
            out = rd.TemplateRenderer._no_later_clause("PACK-01", mob)
            assert "No opening on PACK-01" in out, mob
            assert "not open at all" not in out, mob

    def test_one_definition_two_call_sites(self):
        """`boxed-in` and `earlier-open` both end with nothing later, for the
        same reason. 4A teaching-graft (c) is the session that found out what
        happens when one verdict is rendered from two places."""
        src = rd.TemplateRenderer._render_mobility_later.__code__
        body = src.co_consts
        assert sum(1 for c in body if isinstance(c, str)
                   and "No opening on" in c) == 0, (
            "a later-direction site is authoring its own copy again")


class TestW6TheFramingIsSaidOnce:
    """The founder's felt-bar ruling, 2026-08-05."""

    def test_the_synthesis_preamble_is_gone(self):
        """It opened every synthesis answer by apologising for the route that
        answered it. Asserting its ABSENCE, so a session restoring it has to
        delete a test saying why it went."""
        import inspect
        src = inspect.getsource(rd.TemplateRenderer)
        # The NAME still appears in this class, in the comment explaining why it
        # went — matching the token would make this test pass by deleting the
        # explanation. What must not exist is the RENDER.
        assert "lines.append(SYNTHESIS_LEAD)" not in src, (
            "the synthesis preamble is being rendered again")
        from mre.modules import ask_fallback_copy as afc
        appends = [ln for ln in src.splitlines() if "append" in ln]
        assert afc.SYNTHESIS_LEAD not in " ".join(appends)

    def test_the_outage_lead_is_untouched(self):
        """The reason SYNTHESIS_LEAD was RETIRED rather than deleted: a
        different sentence for a different situation sits beside it."""
        from mre.modules.ask_fallback_copy import OUTAGE_SYNTHESIS_LEAD
        assert OUTAGE_SYNTHESIS_LEAD


def _pb_reasons(text):
    return cv.product_behavior_disqualifiers(_claim(text))


class TestTheCensusBound:
    """What this file does NOT prove, asserted so it cannot be forgotten."""

    def test_the_map_holds_one_floor_and_says_so(self):
        """(iii) is a map from ONE floor's verdict vocabulary to the sentence
        shape it falsifies. Mobility today. The close-out states what adding the
        next floor costs; this asserts nobody has quietly assumed more."""
        assert cv.floor_contradictions(
            _claim("Cost is the only thing that decides which machine an "
                   "operation lands on; nothing else matters.")) == []
