"""R-BK1 at the AUDIT — "search deeper" is a portfolio (Session 4B.25 Item 2).

The audit is where the ruling is cheapest to build and most obviously right: a
deliberate act, off the gesture path, already deterministic and already seeded,
whose entire purpose is to look harder than a drag may afford. 4B.24 measured
what one more seed is worth there (§7(b): three of five seeds found nothing on
the dense board and two found 13-16% cheaper schedules) and left it unharvested.

``audit_incumbent`` had NO tests at all before this file — 4B.24 called its offer
path "verified live" and its accept path "smoke-tested, not proven". These are
written against the SEAM (``baseline_window_solve``), so the selection, the
refusals and the wording are pinned without paying for five window solves; the
end-to-end pair at the bottom pays for them once and is ``--runslow``.

WHAT THIS FILE DELIBERATELY DOES NOT CLAIM: that seeds disagree. On any board
small enough to test here the search closes and every seed lands on the same
optimum. Disagreement is a property of a board the search CANNOT close, and it
is measured in the close-out against the dense demo board, not asserted here.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules import sandbox as sb

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)
INCUMBENT = 10_000.0


def _solve(total, **kw):
    """A BaselineSolve double — the ONE seam the audit reads a member off."""
    return sb.BaselineSolve(
        available=kw.pop("available", True), total_cost=total,
        status=kw.pop("status", "FEASIBLE"), outcome=sb.SANDBOX_VERDICT,
        wall_time_s=1.0, det_consumed=3.0, moves=kw.pop("moves", []),
        affected_orders=kw.pop("affected", []), **kw)


@pytest.fixture
def bench(monkeypatch):
    """Drive the audit off a table of ``seed -> total``, with no solver."""
    def _run(by_seed, **audit_kw):
        seen = []

        def fake(out_dir, snapshot_id, **kw):
            seed = kw["seed"]
            seen.append(seed)
            val = by_seed[seed]
            return val if isinstance(val, sb.BaselineSolve) else _solve(val)

        monkeypatch.setattr(sb, "baseline_window_solve", fake)
        monkeypatch.setattr(sb, "_incumbent_total", lambda *_a, **_k: INCUMBENT)
        res = sb.audit_incumbent(Path("."), "snap", **audit_kw)
        return res, seen
    return _run


# ---------------------------------------------------------------------------
# selection and declaration
# ---------------------------------------------------------------------------

def test_the_audit_runs_k_consecutive_seeds_and_offers_the_best(bench):
    """CLAUSE (1)/(3): K members at ``seed0..seed0+K-1``, best by LEDGER. The
    cheapest total here belongs to the MIDDLE seed, so an audit that simply kept
    the first or the last answer fails."""
    res, seen = bench({42: 9_500.0, 43: 9_000.0, 44: 9_800.0}, k=3)
    assert seen == [42, 43, 44]
    assert res["offer"] is not None
    assert res["offer"]["delta_abs"] == pytest.approx(-1_000.0)
    assert res["offer"]["seed"] == 43
    assert res["winning_seed"] == 43


def test_the_offer_sentence_carries_the_declaration_and_the_spread(bench):
    """CLAUSE (2) + CLAUSE (4) in the one sentence a planner actually reads. The
    money is the offer; the parenthetical is what the OTHER searches found, and
    it is what tells them whether this board is settled."""
    res, _ = bench({42: 9_500.0, 43: 9_000.0, 44: 9_800.0}, k=3)
    s = res["sentence"]
    assert "$1,000.00 cheaper" in s
    assert "best of 3 seeded searches" in s
    assert "spread" in s and "far from settled" in s
    assert s.endswith("review?")


def test_agreeing_searches_say_so_in_the_offer(bench):
    """The other register. Five searches landing on the same number is a TRUST
    statement and the sentence makes it, rather than reporting only the money
    and leaving the planner to guess how solid it is."""
    res, _ = bench({42: 9_000.0, 43: 9_000.0, 44: 9_000.0}, k=3)
    assert "all 3 seeded searches landed on the same total" in res["sentence"]


def test_the_incumbent_holding_still_reports_what_the_losers_found(bench):
    """"I searched this hard and your plan held" is a thing a planner is owed
    (4B.24), and after R-BK1 it is owed with a K on it: held against ONE search
    and held against five are different claims."""
    res, _ = bench({42: 10_000.0, 43: 10_000.0, 44: 10_000.0}, k=3)
    assert res["offer"] is None
    assert "the incumbent held" in res["sentence"]
    assert "x 3 seeds" in res["sentence"]
    assert "landed on the same total" in res["sentence"]


def test_k_of_one_says_nothing_about_a_spread(bench):
    """There is no spread in one number, and the sentence must not manufacture
    one. The K=1 audit reads exactly as it did before this session."""
    res, seen = bench({42: 9_000.0}, k=1)
    assert seen == [42]
    assert "best of" not in res["sentence"]
    assert "seeded searches" not in res["sentence"]
    assert res["portfolio"]["spread_abs"] is None


# ---------------------------------------------------------------------------
# clause (1) — a member that is not reproducible is not a member
# ---------------------------------------------------------------------------

def test_a_wall_stopped_member_cannot_win_and_is_still_reported(bench):
    """CLAUSE (1). The cheapest total on the table belongs to a member the WALL
    stopped — which makes it a lottery draw, not a search result. It must not be
    offered, and it must not vanish either: the published spread has to be the
    spread of what we can actually stand behind."""
    stopped = _solve(1.0, available=False, wall_truncated=True,
                     message="stopped by the wall")
    res, _ = bench({42: stopped, 43: 9_000.0, 44: 9_800.0}, k=3)
    assert res["winning_seed"] == 43
    assert res["offer"]["delta_abs"] == pytest.approx(-1_000.0)
    rows = {m["seed"]: m for m in res["portfolio"]["members"]}
    assert rows[42]["selectable"] is False
    assert rows[42]["ledger_total"] is None
    assert "not reproducible" in rows[42]["reason"]
    assert "1 of 3" in res["portfolio"]["unpublished"]


def test_no_usable_member_is_never_reported_as_the_incumbent_holding(bench):
    """The 4B.24 fusion, one level up. "We found nothing cheaper" is a claim
    about the PLAN; "we could not finish looking" is a claim about US, and
    reporting the second as the first would tell a planner their schedule
    survived a search that never completed."""
    dead = _solve(None, available=False, message="the window could not be re-solved")
    res, _ = bench({42: dead, 43: dead, 44: dead}, k=3)
    assert res["searched"] is False
    assert res["offer"] is None
    assert "could not complete" in res["sentence"]
    assert "3 seeded attempt(s), none usable" in res["sentence"]
    assert "the incumbent held" not in res["sentence"]
    assert "nothing cheaper" not in res["sentence"]


def test_a_dearer_member_is_not_an_opportunity(bench):
    """Unchanged from 4B.24 and re-pinned under K: a search that failed to
    re-find the incumbent's quality is a fact about the search, and a planner
    can act on none of it."""
    res, _ = bench({42: 11_000.0, 43: 12_000.0}, k=2)
    assert res["offer"] is None
    assert "the incumbent held" in res["sentence"]


def test_k_below_one_is_refused():
    with pytest.raises(ValueError):
        sb.audit_incumbent(Path("."), "snap", k=0)


# ---------------------------------------------------------------------------
# the accept — the promise on the card and the schedule that lands
# ---------------------------------------------------------------------------

def test_the_offer_carries_the_seed_that_found_it(bench):
    """The accept must re-solve at the WINNING seed. Accepting an offer found by
    seed 43 while re-solving at the portfolio's seed0 would mint a schedule that
    is not the one on the card — the same class of defect 4B.24 closed with
    ``hold_all_placements``, one ceremony over."""
    res, _ = bench({42: 9_500.0, 43: 9_000.0, 44: 9_800.0}, k=3)
    assert res["offer"]["seed"] == 43


def test_the_accept_path_can_be_held_to_the_offer():
    """ITEM 4a's equality, wired rather than hoped. The promise travels:
    ``expect_delta_abs`` exists on the module function, on the API request, and
    the endpoint passes it through — so a child that re-solved to a different
    number is REFUSED instead of handed over. The live execution of the success
    branch is in the close-out; this pins the wiring that makes it checkable."""
    import inspect
    from mre.api.app import AuditAcceptRequest

    assert "expect_delta_abs" in inspect.signature(
        sb.materialize_audit_offer).parameters
    assert "expect_delta_abs" in AuditAcceptRequest.model_fields
    src = (REPO / "src" / "mre" / "api" / "app.py").read_text("utf-8")
    assert "expect_delta_abs=req.expect_delta_abs" in src
    # and the cockpit hands back BOTH the seed and the promise
    ctl = (REPO / "src" / "cockpit" / "src" / "drag"
           / "controller.js").read_text("utf-8")
    assert "expect_delta_abs: found.delta_abs" in ctl
    assert "seed: found.seed" in ctl


@pytest.mark.slow
def test_the_audit_runs_end_to_end_on_a_real_rolling_run(tmp_path_factory):
    """One real pass, no doubles: a persisted rolling run, a 2-seed audit, and
    a result whose portfolio block names both members and the budget they got."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view

    d = tmp_path_factory.mktemp("auditp")
    generate(d / "sub", scenario="pilot_scale", orders=24, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    build_rolling_view(plant, window_days=7, frozen_days=2, deterministic=True,
                       seed=42, member_time_limit_s=120.0, det_total=2.5,
                       persist=True)

    res = sb.audit_incumbent(plant.out_dir, plant.snapshot_id, k=2,
                             det_time_s=1.0, budget_s=120.0)
    blk = res["portfolio"]
    assert blk["k"] == 2 and blk["seed0"] == 42
    assert [m["seed"] for m in blk["members"]] == [42, 43]
    assert blk["det_time_s"] == 1.0
    assert blk["k_provenance"] == "declared"
    assert res["sentence"], "the audit is never silent"
    # It applies NOTHING, whatever it found.
    assert "offer" in res


@pytest.mark.slow
def test_the_audit_is_deterministic_run_to_run(tmp_path_factory):
    """CLAUSE (1) end to end: the same audit twice gives the IDENTICAL offer —
    the same winning seed, the same member totals, the same sentence. This is
    the property the whole ruling rests on, and it is the one 4B.24's three
    contradictory cards on one gesture proved was missing before it."""
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view

    d = tmp_path_factory.mktemp("auditd")
    generate(d / "sub", scenario="pilot_scale", orders=24, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    build_rolling_view(plant, window_days=7, frozen_days=2, deterministic=True,
                       seed=42, member_time_limit_s=120.0, det_total=2.5,
                       persist=True)

    a = sb.audit_incumbent(plant.out_dir, plant.snapshot_id, k=2,
                           det_time_s=1.0, budget_s=120.0)
    b = sb.audit_incumbent(plant.out_dir, plant.snapshot_id, k=2,
                           det_time_s=1.0, budget_s=120.0)
    assert a["sentence"] == b["sentence"]
    assert a.get("winning_seed") == b.get("winning_seed")
    assert [m["ledger_total"] for m in a["portfolio"]["members"]] == \
           [m["ledger_total"] for m in b["portfolio"]["members"]]
    assert (a["offer"] or {}).get("delta_abs") == (b["offer"] or {}).get("delta_abs")
