"""R-CAL1 — the calibration profile, the knee rule, and drift (Session 4B.29).

WHAT THIS GUARD IS FOR, and its stated limit. It proves the RULES: that a grid
audits itself, that an unaccepted profile is inert, that an absence is stated,
that the knee is the number the rule says it is, and that a portfolio which
under-delivers against an accepted calibration says so. It does NOT prove that
any particular plant's knee is any particular number — that is a measurement,
it lives in the profile, and no test can stand in for it.

Every cell here is synthetic and no solver runs: the arithmetic of the knee is
what is under test, and mixing a real solve into it would make a red test
ambiguous between "the rule is wrong" and "the board moved".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mre.contracts.calibration import (
    CalibrationCell, CalibrationProfile, CalibrationStatus,
    DEFAULT_KNEE_TOLERANCE_PCT, MIN_RECOMMENDED_K, build_recommendation,
    find_knee, grid_digest, recommend_k, summarise_arm,
)
from mre.modules import calibration as cal

SEEDS = [42, 43, 44, 45, 46]


def cell(w, det, seed, ledger, *, status=None, frozen=1):
    """One cell. ``ledger=None`` is an EMPTY BOARD — the thing 4B.26 found."""
    pub = ledger is not None
    return CalibrationCell(
        window_days=w, frozen_days=frozen, det_total=det, seed=seed,
        status=status or ("FEASIBLE" if pub else "UNKNOWN"),
        ledger_total=ledger, det_consumed=det, wall_time_s=100.0,
        publishable=pub,
        reason="" if pub else "the window solve returned UNKNOWN with no ledger")


# 4B.26's demo grid, in shape: starved budgets lose seeds 44 and 45, and the
# value switches on at 10 where every seed lands and 44 wins.
DEMO = (
    [cell(10, 3.0, s, v) for s, v in
     zip(SEEDS, [2127482.58, 2164599.48, None, None, 2126904.42])] +
    [cell(10, 6.0, s, v) for s, v in
     zip(SEEDS, [2127482.58, 2164606.83, None, None, 2126183.98])] +
    [cell(10, 10.0, s, v) for s, v in
     zip(SEEDS, [2135369.63, 1801222.70, 1667467.80, 2018597.18, 2087718.57])] +
    [cell(10, 15.0, s, v) for s, v in
     zip(SEEDS, [1790404.72, 1801222.70, 1667467.80, 2013491.08, 2087718.57])]
)

# The 170-order control: reachable at ten days, out of reach at fourteen.
MID = (
    [cell(10, 6.0, s, v) for s, v in
     zip(SEEDS, [1194633.82, 1015335.60, 1442800.07, 1253810.43, 1106191.02])] +
    [cell(14, 6.0, s, None) for s in SEEDS]
)


# ---------------------------------------------------------------------------
# Rule (1) — a profile is measured, never authored
# ---------------------------------------------------------------------------

class TestGridSealsItself:

    def test_a_sealed_profile_matches_its_own_grid(self, tmp_path):
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        assert prof.grid_digest
        assert prof.digest_ok()

    def test_editing_one_ledger_breaks_the_digest(self, tmp_path):
        """THE WHOLE POINT OF RULE (1). A hand-edited grid is a coefficient with
        no measurement behind it, wearing a measurement's clothes."""
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        cells = [c.model_copy() for c in prof.cells]
        cells[0] = cells[0].model_copy(update={"ledger_total": 1.0})
        tampered = prof.model_copy(update={"cells": cells})
        assert not tampered.digest_ok()

    def test_bookkeeping_is_outside_the_digest(self, tmp_path):
        """Re-importing the same measurement under a different label does not
        change what was measured, so it must not change the seal."""
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        moved = [c.model_copy(update={"source": "imported:elsewhere",
                                      "measured_at": datetime(2020, 1, 1,
                                                              tzinfo=timezone.utc)})
                 for c in prof.cells]
        assert grid_digest(moved) == prof.grid_digest

    def test_a_tampered_profile_is_refused_at_accept(self, tmp_path):
        store = cal.ProfileStore(tmp_path)
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        store.save(prof)
        p = store.path_for(prof.plant_key)
        raw = json.loads(p.read_text("utf-8"))
        raw["cells"][0]["ledger_total"] = 1.0
        p.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="digest of its own grid"):
            store.accept(prof.plant_key, by="somebody")


# ---------------------------------------------------------------------------
# Rule (2) — offered, never auto-applied
# ---------------------------------------------------------------------------

class TestOfferIsNotSetting:

    def test_a_saved_profile_is_not_accepted(self, tmp_path):
        store = cal.ProfileStore(tmp_path)
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        store.save(prof)
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=10)
        assert st.state == "unaccepted"
        assert cal.coefficients(st, tmp_path) == {}

    def test_accept_requires_a_name(self, tmp_path):
        store = cal.ProfileStore(tmp_path)
        store.save(cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                     prefer_window=10))
        key, _ = cal.plant_key_for(_sub(tmp_path))
        with pytest.raises(ValueError, match="signature"):
            store.accept(key, by="   ")

    def test_an_accepted_profile_offers_its_coefficients(self, tmp_path):
        store = cal.ProfileStore(tmp_path)
        store.save(cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                     prefer_window=10))
        key, _ = cal.plant_key_for(_sub(tmp_path))
        store.accept(key, by="Daryn Radke")
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=10)
        assert st.state == "accepted"
        assert cal.coefficients(st, tmp_path) == {"det_total": 10.0, "k": 3}

    def test_the_caller_always_wins(self):
        """A profile is a measured recommendation, not an override."""
        st = CalibrationStatus(state="accepted", plant_key="p", sentence="x")
        applied, st2 = cal.apply_to(st, {"det_total": 10.0, "k": 3},
                                    caller_declared={"k"})
        assert applied == {"det_total": 10.0}
        assert "does not override" in st2.sentence

    def test_the_window_is_never_offered(self, tmp_path):
        """A window decides which work is on the board — it is what a planner
        asked to SEE, not a search coefficient."""
        store = cal.ProfileStore(tmp_path)
        store.save(cal.build_profile(_sub(tmp_path), MID, seeds=SEEDS,
                                     prefer_window=14))
        key, _ = cal.plant_key_for(_sub(tmp_path))
        store.accept(key, by="Daryn Radke")
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=14)
        assert "window_days" not in cal.coefficients(st, tmp_path)
        # ...but the difference between the two windows is VISIBLE.
        assert st.window_calibrated == 10 and st.window_solved == 14


# ---------------------------------------------------------------------------
# Rule (3) — an absence is stated, not silent
# ---------------------------------------------------------------------------

class TestAbsenceIsLoud:

    def test_no_profile_still_produces_a_sentence(self, tmp_path):
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=10)
        assert st.state == "absent"
        assert "no calibration profile" in st.sentence
        assert "default" in st.sentence

    def test_a_broken_digest_reads_as_unreadable_not_absent(self, tmp_path):
        """4B.18's discipline: a claim about our calibration is never
        manufactured from a fact about our storage. 'nobody measured this' and
        'somebody edited this' are different facts."""
        store = cal.ProfileStore(tmp_path)
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        store.save(prof.model_copy(update={"accepted": True}))
        p = store.path_for(prof.plant_key)
        raw = json.loads(p.read_text("utf-8"))
        raw["cells"][0]["ledger_total"] = 1.0
        p.write_text(json.dumps(raw), encoding="utf-8")
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=10)
        assert st.state == "unreadable"
        assert "edited after it was measured" in st.sentence
        assert cal.coefficients(st, tmp_path) == {}

    def test_resolve_never_raises_on_a_junk_submission(self, tmp_path):
        st = cal.resolve(tmp_path, tmp_path / "nowhere", window_solved=10)
        assert st.state == "absent" and st.sentence

    def test_a_future_schema_is_refused_whole_not_read_thin(self, tmp_path):
        """4B.18's lesson: pydantic would ignore fields this build has never
        heard of and hand back an object that LOOKS complete. A file that cannot
        be read whole must say so."""
        store = cal.ProfileStore(tmp_path)
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        store.save(prof.model_copy(update={"accepted": True}))
        p = store.path_for(prof.plant_key)
        raw = json.loads(p.read_text("utf-8"))
        raw["schema_version"] = 99
        p.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="schema 99"):
            store.load(prof.plant_key)
        # and the SOLVE path turns that into a sentence rather than a crash
        st = cal.resolve(tmp_path, _sub(tmp_path), window_solved=10)
        assert st.state == "unreadable"
        assert cal.coefficients(st, tmp_path) == {}


# ---------------------------------------------------------------------------
# Rule (4) — the facility is the scope
# ---------------------------------------------------------------------------

class TestFacilityScope:

    def test_a_multi_facility_submission_is_refused_by_name(self, tmp_path):
        sub = _sub(tmp_path, facilities=["F001", "F005"])
        with pytest.raises(cal.MultiFacilitySubmission, match="rule \\(4\\)"):
            cal.plant_key_for(sub)

    def test_the_key_carries_the_facility(self, tmp_path):
        key, facility = cal.plant_key_for(_sub(tmp_path))
        assert facility == "F001" and key.endswith("::F001")

    def test_an_unscoped_submission_is_keyed_and_said_so(self, tmp_path):
        key, facility = cal.plant_key_for(_sub(tmp_path, facilities=[]))
        assert key.endswith("::unscoped")
        assert "no facility declared" in facility


# ---------------------------------------------------------------------------
# THE KNEE RULE — stated, not a vibe
# ---------------------------------------------------------------------------

class TestKnee:

    def test_the_demo_knee_is_ten_not_six(self):
        """Condition (i) fails at 3 and 6 (two seeds publish nothing) and holds
        at 10, where the winner ties the best winner at any larger budget."""
        b, note = find_knee(DEMO, 10)
        assert b == 10.0
        assert "every seeded search" in note

    def test_the_knee_is_not_the_first_all_publishable_budget_by_accident(self):
        """Condition (ii) is load-bearing: make 10 publish everywhere but land
        30% dearer than 15, and the knee must move UP to 15."""
        cells = [c for c in DEMO if c.det_total != 10.0]
        cells += [cell(10, 10.0, s, 2500000.0 + s) for s in SEEDS]
        b, _ = find_knee(cells, 10)
        assert b == 15.0

    def test_an_unreachable_window_has_no_knee_and_says_why(self):
        b, note = find_knee(MID, 14)
        assert b is None
        assert "not reliably reachable at any measured budget" in note
        assert "0 of 5" in note

    def test_tolerance_is_declared_and_changes_the_answer(self):
        """A knee found under a loose tolerance must never read as one found
        under a tight one, which is why the number rides on the profile."""
        cells = [c for c in DEMO if c.det_total != 10.0]
        cells += [cell(10, 10.0, s, v) for s, v in
                  zip(SEEDS, [1800000.0, 1800000.0, 1700000.0, 1800000.0,
                              1800000.0])]
        assert find_knee(cells, 10, 1.0)[0] == 15.0
        assert find_knee(cells, 10, 5.0)[0] == 10.0

    def test_the_largest_measured_budget_satisfies_ii_vacuously(self):
        """The rule's own limit, asserted rather than assumed: a knee is never a
        claim about budgets nobody ran."""
        only = [c for c in DEMO if c.det_total == 15.0]
        b, note = find_knee(only, 10)
        assert b == 15.0
        assert "largest measured budget" in note


class TestRecommendedK:

    def test_demo_recommends_three(self):
        """4B.26 §4 read this off its own table by hand; here it is a rule.
        Seed 42 alone is 28% dearer, 42+43 is 8% dearer, 42+43+44 IS the best."""
        k, k_val, note = recommend_k(DEMO, 10, 10.0, SEEDS)
        assert (k, k_val) == (3, 3)
        assert "smallest prefix" in note

    def test_the_clause_four_floor_is_named_not_hidden(self):
        """Where one seed captures everything, K is still 2 — and the note says
        the second member is buying the SPREAD SENTENCE, not a cheaper board."""
        cells = [cell(10, 6.0, s, 1000.0 + (0 if s == 42 else 10_000))
                 for s in SEEDS]
        k, k_val, note = recommend_k(cells, 10, 6.0, SEEDS)
        assert k_val == 1 and k == MIN_RECOMMENDED_K
        assert "no spread to report" in note

    def test_mid_recommends_two_because_seed_43_wins(self):
        k, k_val, _ = recommend_k(MID, 10, 6.0, SEEDS)
        assert (k, k_val) == (2, 2)


class TestRecommendation:

    def test_demo_recommends_window_ten_ten_units_k_three(self):
        rec = build_recommendation(DEMO, SEEDS, prefer_window=10)
        assert rec.found
        assert (rec.window_days, rec.det_total, rec.k) == (10, 10.0, 3)
        assert rec.publishable_at_knee == 5 and rec.members_at_knee == 5
        assert rec.margin_det_total == 6.0 and rec.margin_publishable == 3

    def test_an_unreachable_declared_window_falls_back_and_says_so(self):
        """mid170's shape. The recommendation must never silently swap the
        planner's horizon for a shorter one."""
        rec = build_recommendation(MID, SEEDS, prefer_window=14)
        assert rec.found and rec.window_days == 10
        assert rec.unreachable_windows == [14]
        assert "declared window (14 days) is not reliably reachable" in rec.knee_note
        assert "14d were not reachable" in rec.sentence()

    def test_nothing_reachable_anywhere_is_a_finding_not_a_gap(self):
        rec = build_recommendation([c for c in MID if c.window_days == 14],
                                   SEEDS, prefer_window=14)
        assert not rec.found
        assert "no recommendation" in rec.sentence()

    def test_the_margin_is_the_budget_below_the_knee(self):
        rec = build_recommendation(DEMO, SEEDS, prefer_window=10)
        assert rec.margin_members == 5 and rec.margin_publishable == 3


class TestArmSummary:

    def test_the_denominator_is_what_ran_not_what_succeeded(self):
        """4B.21: a count names the disposition it counts."""
        arm = summarise_arm(DEMO, 10, 6.0)
        assert arm.k == 5 and arm.publishable == 3

    def test_a_spread_of_one_number_is_not_a_spread(self):
        one = [cell(10, 6.0, 42, 100.0)] + [cell(10, 6.0, s, None)
                                            for s in SEEDS[1:]]
        arm = summarise_arm(one, 10, 6.0)
        assert arm.publishable == 1 and arm.spread_abs is None


# ---------------------------------------------------------------------------
# Item 4 — DRIFT
# ---------------------------------------------------------------------------

class _Book:
    """The smallest thing shaped like a Portfolio for drift's purposes."""

    def __init__(self, k, pub, det=10.0):
        from mre.modules import portfolio as pf
        self.k = k
        self.det_time_s = det
        self.members = tuple(
            [pf.PortfolioMember(seed=42 + i, ledger_total=1000.0 + i,
                                status="FEASIBLE") for i in range(pub)] +
            [pf.unusable(42 + i, "the window solve returned UNKNOWN")
             for i in range(pub, k)])

    @property
    def usable(self):
        return [m for m in self.members
                if m.selectable and m.ledger_total is not None]


def _accepted(det=10.0, k=3):
    return CalibrationStatus(state="accepted", plant_key="p::F001",
                             profile_id="cal-1", sentence="x",
                             applied={"det_total": det, "k": k})


class TestDrift:

    def test_a_short_portfolio_under_an_accepted_profile_drifts(self):
        d = cal.detect_drift(_accepted(), _Book(3, 1))
        assert d is not None
        assert d["missing"] == 2 and d["publishable"] == 1 and d["k"] == 3
        assert d["unpublished_seeds"] == [43, 44]
        assert "recommend re-running calibration" in d["sentence"]

    def test_a_full_portfolio_says_nothing(self):
        assert cal.detect_drift(_accepted(), _Book(3, 3)) is None

    def test_an_uncalibrated_plant_never_drifts(self):
        """A plant on product defaults has no promise to drift FROM, and saying
        it does would turn an uncalibrated plant into a broken one."""
        assert cal.detect_drift(cal.absent_status("p"), _Book(3, 1)) is None

    def test_an_accepted_but_unapplied_profile_never_drifts(self):
        st = CalibrationStatus(state="accepted", plant_key="p", sentence="x",
                               applied={})
        assert cal.detect_drift(st, _Book(3, 1)) is None

    def test_no_portfolio_at_all_never_drifts(self):
        assert cal.detect_drift(_accepted(), None) is None


# ---------------------------------------------------------------------------
# THE PREMISE TEST — the fixtures above are the shape they claim to be
# ---------------------------------------------------------------------------

class TestPremise:

    def test_the_demo_fixture_really_loses_two_seeds_at_the_shipped_budget(self):
        """If this ever goes green while the grid is fully publishable, every
        knee assertion above is testing nothing."""
        arm = summarise_arm(DEMO, 10, 6.0)
        assert arm.k == 5 and arm.publishable == 3
        assert {c.seed for c in DEMO
                if c.det_total == 6.0 and not c.publishable} == {44, 45}

    def test_the_mid_fixture_really_is_empty_at_fourteen_days(self):
        arm = summarise_arm(MID, 14, 6.0)
        assert arm.k == 5 and arm.publishable == 0

    def test_the_demo_fixture_really_has_a_cheaper_winner_at_ten(self):
        assert summarise_arm(DEMO, 10, 10.0).winner_ledger < \
               summarise_arm(DEMO, 10, 6.0).winner_ledger


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — each proven red against a specific reverted behaviour
# ---------------------------------------------------------------------------

class TestNegativeControls:

    def test_a_knee_that_ignored_condition_i_would_recommend_an_empty_board(self):
        """Reverting condition (i) — 'the smallest budget whose winner is within
        tolerance of any larger one', with no requirement that every seed
        published — recommends a budget at which TWO OF FIVE SEEDS PUBLISH
        NOTHING. That is precisely the reliability defect this session exists to
        close, and this control names the grid on which it bites.

        NOTE, because it matters for what this control does NOT prove: on 4B.26's
        real demo grid condition (i) is not what decides the knee — the
        starved budgets' winners are 27% dearer, so condition (ii) rules them out
        on its own. Condition (i) is the clause that protects a plant whose
        starved searches happen to find a GOOD board when they find one at all,
        which is the grid below."""
        # Three seeds publish at 3.0 and find the cheapest board in the sweep;
        # two publish nothing. Every seed publishes at 6.0, a hair dearer.
        grid = (
            [cell(10, 3.0, s, v) for s, v in
             zip(SEEDS, [1_000_000.0, 1_002_000.0, None, None, 1_001_000.0])] +
            [cell(10, 6.0, s, 1_005_000.0 + s) for s in SEEDS]
        )
        budgets = [3.0, 6.0]
        arms = {b: summarise_arm(grid, 10, b) for b in budgets}
        # the rule WITHOUT condition (i)
        naive = next(b for b in budgets
                     if arms[b].winner_ledger is not None
                     and all(arms[b].winner_ledger <= arms[x].winner_ledger * 1.01
                             for x in budgets
                             if x > b and arms[x].winner_ledger is not None))
        assert naive == 3.0
        assert arms[naive].publishable == 3 < arms[naive].k == 5
        # the rule AS RULED
        assert find_knee(grid, 10)[0] == 6.0

    def test_a_digest_over_bookkeeping_would_fire_on_a_reimport(self):
        """Reverting the digest to hash `measured_at`/`source` would make every
        re-import look like tampering. The seal must cover the MEASUREMENT."""
        import hashlib
        naive = lambda cs: hashlib.sha256(  # noqa: E731
            json.dumps(sorted(c.model_dump_json() for c in cs)).encode()
        ).hexdigest()
        moved = [c.model_copy(update={"source": "imported:elsewhere"})
                 for c in DEMO]
        assert naive(moved) != naive(DEMO)
        assert grid_digest(moved) == grid_digest(DEMO)

    def test_drift_without_the_accepted_gate_would_fire_on_every_plant(self):
        """Reverting the state check makes an UNCALIBRATED plant report drift —
        the finding would then be about nothing at all."""
        st = cal.absent_status("p").model_copy(
            update={"state": "accepted", "applied": {"k": 3}})
        assert cal.detect_drift(st, _Book(3, 1)) is not None
        assert cal.detect_drift(cal.absent_status("p"), _Book(3, 1)) is None


# ---------------------------------------------------------------------------
# THE FLIP (Item 1) — the product default, and what it must not have moved
# ---------------------------------------------------------------------------

class TestTheFlip:

    def test_the_product_default_is_three(self):
        from mre.api.app import SolveRequest
        assert SolveRequest().portfolio_k == 3

    def test_the_library_default_is_still_one(self):
        """Every module-level fixture, golden and baseline rides on this — which
        is why no golden moved."""
        from mre.modules import portfolio as pf
        from mre.modules.rolling_horizon import solve_rolling_portfolio
        import inspect
        assert pf.DEFAULT_K == 1
        sig = inspect.signature(solve_rolling_portfolio)
        assert sig.parameters["k"].default == 1

    def test_k_one_remains_requestable(self):
        from mre.api.app import SolveRequest
        assert SolveRequest(portfolio_k=1).portfolio_k == 1

    def test_provenance_reports_who_chose(self):
        """A defaulted K must never read as a customer's choice — and after the
        flip `k != DEFAULT_K` is no longer that test, which is the bug this
        replaces."""
        from mre.api.app import SolveRequest
        assert "portfolio_k" not in SolveRequest().model_fields_set
        assert "portfolio_k" in SolveRequest(portfolio_k=3).model_fields_set

    def test_the_two_minted_worlds_pin_k_one(self):
        """Item 1(b): the pinned exam world and the demo board are REGISTERED
        ARTIFACTS from one seeded search. Their rebuild commands must keep
        reproducing them."""
        for rel in ("tools/build_rolling_exam_run.py",
                    "tools/spikes/demo_board_4b22a/mint_demo_board.py"):
            src = (Path(__file__).parents[1] / rel).read_text("utf-8")
            assert '"portfolio_k": 1' in src, rel

    def test_a_default_cannot_break_a_request_that_worked_before_it(self):
        """`deterministic` defaults to False and a portfolio of draws is
        forbidden (R-BK1 clause 1), so a naive `{"sliced": true}` request would
        have started FAILING at the flip. The DEFAULTED K degrades to 1 and the
        certificate says why; an EXPLICIT portfolio still raises, because asking
        for the best of three draws is asking for a number with no meaning."""
        from mre.modules.rolling_horizon import solve_rolling_portfolio
        with pytest.raises(ValueError, match="portfolio of draws"):
            solve_rolling_portfolio(object(), window_days=10, frozen_days=1,
                                    deterministic=False, k=3)
        # the degradation itself is exercised end to end by
        # TestThroughTheAPI::test_a_non_deterministic_sliced_solve_still_works

    def test_the_search_deeper_scale_names_its_member_count(self):
        """Item 1(d): 'search deeper' says how many searches and roughly how
        long, composed server-side so the JS words no claim about our search."""
        from mre.api.app import _search_deeper_scale
        s = _search_deeper_scale()
        assert s["k"] >= 1 and s["expected_minutes"] > 0
        assert str(s["k"]) in s["sentence"] and "minutes" in s["sentence"]


# ---------------------------------------------------------------------------
# The certificate block (contract 1.14)
# ---------------------------------------------------------------------------

class TestCertificateBlock:

    def test_no_lookup_means_no_block(self):
        """The absent-by-construction half: an assembler handed no store has no
        answer to report, which is why every golden is byte-identical."""
        from mre.modules.schedule_assembler import _calibration_block
        assert _calibration_block(None) is None

    def test_an_absence_produces_a_block_that_says_so(self):
        from mre.modules.schedule_assembler import _calibration_block
        b = _calibration_block(cal.absent_status("p::F001", window_solved=10))
        assert b is not None and b.state == "absent"
        assert "no calibration profile" in b.sentence

    def test_drift_rides_on_the_block(self):
        from mre.modules.schedule_assembler import _calibration_block
        st = _accepted().model_copy(
            update={"drift": cal.detect_drift(_accepted(), _Book(3, 1))})
        b = _calibration_block(st)
        assert b.drift is not None and b.drift.missing == 2

    def test_the_drift_code_is_its_own(self):
        """ADDED, NEVER REPURPOSED. It is not SOLVER_NONOPTIMAL (a claim about
        the proof) and not DENSITY_LIMIT (a claim about the plant)."""
        from mre.contracts.vocabularies import FindingCode
        assert FindingCode.CALIBRATION_DRIFT.value == "CALIBRATION_DRIFT"
        assert FindingCode.CALIBRATION_DRIFT not in (
            FindingCode.SOLVER_NONOPTIMAL, FindingCode.DENSITY_LIMIT)


# ---------------------------------------------------------------------------
# The ceremony's own plumbing
# ---------------------------------------------------------------------------

class TestCeremony:

    def test_the_grid_is_planned_cheapest_budget_first(self):
        """An interrupted ceremony leaves the decision-relevant rows on disk —
        4B.26 §6(e) ran into exactly this."""
        plan = cal.planned_cells([10, 14], [10.0, 3.0], [43, 42], 1)
        assert plan[0][2] == 3.0 and plan[-1][2] == 10.0

    def test_cells_round_trip_append_only_newest_wins(self, tmp_path):
        cal.append_cell(tmp_path, cell(10, 6.0, 42, 100.0))
        cal.append_cell(tmp_path, cell(10, 6.0, 42, 200.0))
        got = cal.load_cells(tmp_path)
        assert len(got) == 1 and got[0].ledger_total == 200.0
        assert len(cal.cells_path(tmp_path).read_text("utf-8").strip()
                   .splitlines()) == 2

    def test_the_projection_is_stated_before_anything_is_spent(self):
        plan = cal.planned_cells([10], [3.0, 6.0], [42], 1)
        assert cal.project_wall_s(plan) == pytest.approx(9.0 * 55.0)

    def test_cost_honesty_compares_the_same_set(self, tmp_path):
        """A forecast for the whole grid printed beside a wall for the five
        cells this run measured is decoration, not cost honesty. Both figures
        cover the cells THIS ceremony measured, and both are derived from the
        grid so a rebuilt profile reports the same pair."""
        mixed = ([c.model_copy(update={"source": "imported:4B.26"})
                  for c in DEMO if c.det_total != 15.0] +
                 [c.model_copy(update={"source": "measured",
                                       "wall_time_s": 200.0})
                  for c in DEMO if c.det_total == 15.0])
        prof = cal.build_profile(_sub(tmp_path), mixed, seeds=SEEDS,
                                 prefer_window=10)
        assert prof.actual_wall_s == pytest.approx(5 * 200.0)
        assert prof.projected_wall_s == pytest.approx(
            5 * 15.0 * cal.SECONDS_PER_DET_UNIT)
        assert "5 cell(s) measured here" in cal.render_profile(prof)

    def test_resume_skips_what_is_already_measured(self, tmp_path):
        cal.append_cell(tmp_path, cell(10, 6.0, 42, 100.0))
        seen = {}
        cal.run_grid(tmp_path / "nowhere", tmp_path, windows=[10],
                     budgets=[6.0], seeds=[42], frozen_days=1, resume=True,
                     on_event=lambda e: seen.setdefault(e["kind"], e))
        assert seen["plan"]["cells_pending"] == 0
        assert seen["plan"]["cells_reused"] == 1
        assert "plant" not in seen          # nothing was prepared, nothing ran

    def test_render_is_plain_and_carries_the_whole_grid(self, tmp_path):
        prof = cal.build_profile(_sub(tmp_path), DEMO, seeds=SEEDS,
                                 prefer_window=10)
        out = cal.render_profile(prof)
        assert "THE GRID" in out and "THE KNEE RULE" in out
        for b in ("3", "6", "10", "15"):
            assert b in out
        assert "NO (rule 2" in out


# ---------------------------------------------------------------------------

PINNED_WORLDS = {
    "rolling-c362baa4-1b0": (
        "07638cecb0b6f54393834110810b877a194eff7390964349a4cf4268aa7def22",
        56, 16481.95, "1.11"),
    "rolling-c9973708-865": (
        "ac86d185e8a977838335bde3a33a08dd01d394ce36f5117c1c6b101ec353fd6a",
        386, 2127482.58, "1.12"),
}


class TestPinnedWorldsUnmoved:
    """ITEM 1(b) — THE FLIP CHANGES FUTURE SOLVES, NOT PAST ARTIFACTS.

    `rolling-c362baa4-1b0` (the pinned exam world) and `rolling-c9973708-865`
    (the demo board) are REGISTERED ARTIFACTS produced by ONE seeded search.
    Nothing in this session re-solves them, and their placement digests are
    pinned here so a future session that accidentally does will find out.

    Skipped where the working data root is not present — `_data/` is gitignored,
    so this is a LOCAL guard and says so rather than pretending to be portable.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def docs():
        import hashlib
        import sqlite3
        root = Path(__file__).parents[1] / "_data"
        if not (root / "registry.sqlite").exists():
            pytest.skip("no working data root — the pinned worlds live in "
                        "gitignored _data/")
        db = sqlite3.connect(root / "registry.sqlite")
        db.row_factory = sqlite3.Row
        out = {}
        for sid in PINNED_WORLDS:
            row = db.execute("SELECT * FROM schedules WHERE id=?",
                             (sid,)).fetchone()
            if row is None:
                continue
            doc = json.loads(Path(row["document_path"]).read_text("utf-8"))
            bars = doc.get("assignments") or []
            payload = sorted(
                (a["operation_ref"], a["resource_id"],
                 (a.get("chunks") or [{}])[0].get("start")) for a in bars)
            out[sid] = (doc, hashlib.sha256(
                json.dumps(payload, default=str).encode()).hexdigest())
        db.close()
        if not out:
            pytest.skip("neither pinned world is registered in this data root")
        return out

    def test_placements_are_byte_identical(self, docs):
        for sid, (doc, dig) in docs.items():
            want_dig, bars, ledger, _cv = PINNED_WORLDS[sid]
            assert dig == want_dig, f"{sid} placements moved"
            assert len(doc["assignments"]) == bars
            assert round(doc["cost_summary"]["total"], 2) == ledger

    def test_they_carry_no_portfolio_and_no_calibration_block(self, docs):
        """They predate both blocks, and the flip did not reach back."""
        for _sid, (doc, _dig) in docs.items():
            assert doc["solver"].get("portfolio") is None
            assert doc["solver"].get("calibration") is None

    def test_an_older_contract_still_parses_under_1_14(self, docs):
        """The bump is MINOR: 1.11 and 1.12 documents still load whole."""
        from mre.contracts.schedule_document import ScheduleDocument
        for sid, (doc, _dig) in docs.items():
            parsed = ScheduleDocument.model_validate(doc)
            assert parsed.contract_version == PINNED_WORLDS[sid][3]
            assert parsed.solver.calibration is None


@pytest.mark.slow
class TestThroughTheAPI:
    """Items 1(c) and 5(a)/(e), end to end: a solve that declares nothing gets
    the PRODUCT default, its certificate carries the K=3 declaration and the
    cross-seed spread, and — with no profile stored — says so out loud."""

    @staticmethod
    @pytest.fixture(scope="class")
    def solved(tmp_path_factory):
        import sys
        sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
        from fastapi.testclient import TestClient
        from generate_erp_dataset import generate
        from mre.api.app import create_app

        root = tmp_path_factory.mktemp("cal_api_root")
        src = tmp_path_factory.mktemp("cal_api_sub") / "pilot"
        generate(src, scenario="pilot_scale", orders=40, seed=1)
        client = TestClient(create_app(data_root=root))
        sub = client.post("/submissions",
                          json={"path": str(src)}).json()["data"]
        assert sub["grade"] != "REJECTED"
        # DECLARES NO K — this is the shipped default under test.
        solve = client.post(
            f"/submissions/{sub['submission_id']}/solve",
            json={"sliced": True, "window_days": 14, "frozen_days": 3,
                  "time_limit": 60, "deterministic": True, "sync": True},
        ).json()["data"]
        run = client.get(f"/runs/{solve['run_id']}").json()["data"]
        assert run["status"] == "succeeded", run.get("error")
        doc = client.get(
            f"/schedules/{run['result']['schedule_id']}").json()["data"]
        return run, doc, root

    def test_an_undeclared_solve_runs_three_seeded_searches(self, solved):
        run, doc, _ = solved
        pf = doc["solver"]["portfolio"]
        assert pf is not None, "K=3 must emit a portfolio block"
        assert pf["k"] == 3 and pf["seed0"] == 42
        assert [m["seed"] for m in pf["members"]] == [42, 43, 44]
        assert run["result"]["portfolio"]["k"] == 3

    def test_the_declaration_is_on_the_certificate_and_names_the_budget(self, solved):
        _run, doc, _ = solved
        pf = doc["solver"]["portfolio"]
        assert "best of 3 seeded searches" in pf["declaration"]
        assert "6 deterministic units each" in pf["declaration"]
        assert "seeds 42" in pf["declaration"]

    def test_a_defaulted_k_does_not_read_as_a_customers_choice(self, solved):
        """The provenance bug the flip would otherwise have introduced: before
        4B.29 `k_declared` was `k != DEFAULT_K`, which after the flip would
        stamp every default solve 'declared'."""
        _run, doc, _ = solved
        assert doc["solver"]["portfolio"]["k_provenance"] == "defaulted"
        assert doc["solver"]["portfolio"]["det_time_s_provenance"] == "defaulted"

    def test_the_spread_is_published_where_two_members_published(self, solved):
        _run, doc, _ = solved
        pf = doc["solver"]["portfolio"]
        pub = [m for m in pf["members"] if m["ledger_total"] is not None]
        if len(pub) >= 2:
            assert pf["spread_abs"] is not None and pf["agreement"]
        else:
            # a spread of one number is not a spread — R-BK1 clause (4)
            assert pf["spread_abs"] is None

    def test_an_uncalibrated_plant_is_told_so_on_its_own_certificate(self, solved):
        run, doc, _ = solved
        block = doc["solver"]["calibration"]
        assert block is not None and block["state"] == "absent"
        assert "no calibration profile" in block["sentence"]
        assert block["window_solved"] == 14
        assert run["result"]["calibration"]["state"] == "absent"

    def test_a_non_deterministic_sliced_solve_still_works(self, solved):
        """The other half of the flip's compatibility promise, end to end: a
        request that omits `deterministic` (its default is False) must still
        produce a board, with the defaulted portfolio degraded to one search and
        the certificate saying why."""
        from fastapi.testclient import TestClient
        from mre.api.app import create_app
        _run, _doc, root = solved
        client = TestClient(create_app(data_root=root))
        subs = sorted((root / "submissions").glob("*"))
        assert subs
        sid = subs[0].name
        solve = client.post(f"/submissions/{sid}/solve",
                            json={"sliced": True, "window_days": 14,
                                  "frozen_days": 3, "time_limit": 60,
                                  "sync": True}).json()["data"]
        run = client.get(f"/runs/{solve['run_id']}").json()["data"]
        assert run["status"] == "succeeded", run.get("error")
        doc = client.get(
            f"/schedules/{run['result']['schedule_id']}").json()["data"]
        assert doc["solver"]["portfolio"] is None
        assert "not deterministic" in doc["solver"]["calibration"]["sentence"]

    def test_search_deeper_names_its_scale_on_meta(self, solved):
        import sys
        from fastapi.testclient import TestClient
        from mre.api.app import create_app
        run, _doc, root = solved
        client = TestClient(create_app(data_root=root))
        meta = client.get(
            f"/schedules/{run['result']['schedule_id']}/meta").json()["data"]
        assert meta["search_deeper"]["k"] >= 1
        assert "minutes" in meta["search_deeper"]["sentence"]


@pytest.mark.slow
class TestDriftPremise:
    """THE PREMISE TEST — a member that GENUINELY fails, on a real solve.

    Everything above is arithmetic over synthetic cells, and arithmetic cannot
    prove that a seeded deterministic search ever comes back empty. This does:
    a real 120-order window at a starved deterministic budget, where the
    searches run out of budget before they place anything. It is the same
    failure mode 4B.26 measured on the demo board at 6.0 units and on mid170 at
    fourteen days — reproduced small enough to live in a test.

    The budget is chosen well BELOW the cliff (0.12 units; 0.2 units publishes
    3 of 3 on this world), so this is not a knife-edge fixture. What it asserts
    is that fewer than K members publish and that drift then fires — not any
    particular count, because the count is a property of the cliff's position.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def starved(tmp_path_factory):
        import sys
        from datetime import datetime, timezone as tz
        sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
        from generate_erp_dataset import generate
        from mre.modules.rolling_horizon import (prepare_plant,
                                                 solve_rolling_portfolio)
        sub = tmp_path_factory.mktemp("drift_sub") / "pilot"
        generate(sub, scenario="pilot_scale", orders=120, seed=1)
        plant = prepare_plant(sub, tmp_path_factory.mktemp("drift_prep"),
                              reference_date=datetime(2026, 1, 5, tzinfo=tz.utc))
        _view, book = solve_rolling_portfolio(
            plant, window_days=14, frozen_days=3, deterministic=True, seed=42,
            member_time_limit_s=300.0, det_total=0.12, persist=False, k=3)
        return book

    def test_a_real_member_really_comes_back_empty(self, starved):
        assert starved.k == 3
        assert len(starved.usable) < starved.k
        assert any(not m.selectable or m.ledger_total is None
                   for m in starved.members)

    def test_drift_fires_on_that_real_portfolio(self, starved):
        d = cal.detect_drift(_accepted(det=0.12, k=3), starved)
        assert d is not None
        assert d["missing"] == starved.k - len(starved.usable) >= 1
        assert "recommend re-running calibration" in d["sentence"]

    def test_and_says_nothing_when_the_same_plant_is_uncalibrated(self, starved):
        assert cal.detect_drift(cal.absent_status("p"), starved) is None


@pytest.mark.slow
class TestDriftThroughTheAPI:
    """ITEMS 5(e) AND 5(f) END TO END — an ACCEPTED profile is declared on the
    certificate, its coefficients are applied, and when the searches do not
    deliver what it promised the certificate says so.

    The profile here declares a budget the plant cannot actually meet (0.12
    deterministic units on a 120-order window), so drift is guaranteed rather
    than hoped for. That is the point of a premise: the fixture must be able to
    fail in the way the feature claims to detect."""

    @staticmethod
    @pytest.fixture(scope="class")
    def drifted(tmp_path_factory):
        import sys
        sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
        from fastapi.testclient import TestClient
        from generate_erp_dataset import generate
        from mre.api.app import create_app

        root = tmp_path_factory.mktemp("drift_api_root")
        src = tmp_path_factory.mktemp("drift_api_sub") / "pilot"
        generate(src, scenario="pilot_scale", orders=120, seed=1)
        client = TestClient(create_app(data_root=root))
        sub = client.post("/submissions",
                          json={"path": str(src)}).json()["data"]
        # the submission the API actually solves is its own copy under the data
        # root, so the profile has to be keyed off THAT manifest
        sub_dir = next((root / "submissions").glob("*")) / "files"
        # Ledgers DESCENDING by seed so the cheapest board is seed 44's: the
        # recommendation is then a genuine K=3 (the smallest prefix whose winner
        # ties the full set's) rather than the clause-(4) floor of 2.
        cells = [cell(14, 0.12, sd, led, frozen=3) for sd, led in
                 ((42, 3000.0), (43, 2000.0), (44, 1000.0))]
        prof = cal.build_profile(sub_dir, cells, seeds=[42, 43, 44],
                                 prefer_window=14)
        store = cal.ProfileStore(root)
        store.save(prof)
        store.accept(prof.plant_key, by="Daryn Radke")

        solve = client.post(
            f"/submissions/{sub['submission_id']}/solve",
            json={"sliced": True, "window_days": 14, "frozen_days": 3,
                  "time_limit": 300, "deterministic": True, "sync": True},
        ).json()["data"]
        run = client.get(f"/runs/{solve['run_id']}").json()["data"]
        assert run["status"] == "succeeded", run.get("error")
        doc = client.get(
            f"/schedules/{run['result']['schedule_id']}").json()["data"]
        return run, doc, prof

    def test_the_accepted_profile_is_declared_on_the_certificate(self, drifted):
        _run, doc, prof = drifted
        block = doc["solver"]["calibration"]
        assert block["state"] == "accepted"
        assert block["profile_id"] == prof.profile_id
        assert "calibrated for" in block["sentence"]
        assert block["instrument_version"] == prof.instrument_version

    def test_its_coefficients_were_actually_applied(self, drifted):
        _run, doc, _prof = drifted
        block = doc["solver"]["calibration"]
        assert block["applied"] == {"det_total": 0.12, "k": 3}
        pf = doc["solver"]["portfolio"]
        assert pf["det_time_s"] == 0.12 and pf["k"] == 3
        # applied FROM a profile is a declaration, not a default
        assert pf["k_provenance"] == "declared"
        assert pf["det_time_s_provenance"] == "declared"

    def test_the_drift_is_on_the_certificate(self, drifted):
        _run, doc, _prof = drifted
        drift = doc["solver"]["calibration"]["drift"]
        assert drift is not None
        assert drift["k"] == 3 and drift["missing"] >= 1
        assert "recommend re-running calibration" in drift["sentence"]

    def test_the_schedule_was_still_registered(self, drifted):
        """INFORMATIONAL, never a gate verdict change: drift must not cost a
        planner their board."""
        run, doc, _prof = drifted
        assert run["status"] == "succeeded"
        assert doc["schedule_id"]

    def test_the_drift_is_a_real_evidence_finding(self, drifted):
        from mre.contracts.vocabularies import FindingCode
        run, _doc, _prof = drifted
        out = Path(run["out_dir"]) if run.get("out_dir") else None
        if out is None or not out.exists():
            pytest.skip("run dir not exposed on the run row")
        hits = [ln for p in out.rglob("*.jsonl")
                for ln in p.read_text("utf-8").splitlines()
                if FindingCode.CALIBRATION_DRIFT.value in ln]
        assert hits, "CALIBRATION_DRIFT was never filed as evidence"


def _sub(tmp_path: Path, facilities=("F001",)) -> Path:
    d = tmp_path / f"sub_{'_'.join(facilities) or 'none'}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "ids_version": "0.2", "source_system": "TestERP",
        "facility_scope": list(facilities), "reference_date": "2026-01-05",
    }), encoding="utf-8")
    return d
