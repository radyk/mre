"""R-BK1 — THE PUBLISHED BOARD IS A PORTFOLIO, NOT A DRAW (Session 4B.25).

Written from the ruling. Five clauses, and the two that carry the weight are the
two easiest to lose:

  * **CLAUSE (1) — the portfolio is DETERMINISTIC.** Not because the members are
    fast, but because selection is ``min`` over a FIXED set under a TOTAL order
    (ledger, then seed). ``test_selection_*`` pin that order, including the
    tie-break, which is the only part of it that can quietly become
    order-dependent. A member the WALL stopped is not reproducible and is
    therefore not selectable — the same refusal 4B.24 clause (1) put on the
    sandbox baseline.

  * **CLAUSE (2) — K=1 IS EXACTLY TODAY'S BEHAVIOUR.** Proven by SCHEDULE
    DIGEST against a direct ``build_rolling_view`` call on the same plant, and
    by the assembled document carrying NO portfolio block. Asserting
    "compatible" without a digest would be exactly the hope this project
    replaced with measurement.

THE PREMISE TEST comes first: a fixture whose window solve produced no ledger
would make every selection test below pass while proving nothing.

THE LIMIT, STATED: the plant here is 24 pilot_scale orders and proves OPTIMAL,
so its seeds cannot disagree — a proved optimum is a proved optimum at every
seed. The SPREAD this ruling exists to harvest only appears on a board the
search cannot close, which is why Item 3's measurement runs against the dense
demo board and lives in the close-out, not here. What this file guards is the
MACHINERY: the selection, the refusals, the wording, the compatibility.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.contracts.schedule_document import CONTRACT_VERSION
from mre.modules import portfolio as pf

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)
ORDERS = 24
WINDOW_DAYS, FROZEN_DAYS = 7, 2
DET_TOTAL = 2.5
WALL_CEILING_S = 120.0          # a CEILING, never the budget


# ---------------------------------------------------------------------------
# the pure core — no solve, no fixture, no clock
# ---------------------------------------------------------------------------

def _m(seed, total, **kw):
    return pf.PortfolioMember(seed=seed, ledger_total=total,
                              status=kw.pop("status", "FEASIBLE"), **kw)


def test_selection_takes_the_lowest_ledger():
    """CLAUSE (3): by the LEDGER, never the raw objective. The members are given
    in an order that does NOT match the answer, so a selection reading position
    instead of value fails here."""
    won = pf.select([_m(42, 100.0), _m(43, 90.0), _m(44, 110.0)])
    assert won.seed == 43 and won.ledger_total == 90.0


def test_selection_breaks_ties_by_the_lowest_seed():
    """The tie-break is the whole of clause (1)'s determinism claim on a board
    where several seeds find the same money — which is the COMMON case on a
    board that proves. Without it, ``min`` returns whichever member the list
    happened to hold first, and the portfolio's answer becomes a function of
    completion order."""
    won = pf.select([_m(45, 90.0), _m(43, 90.0), _m(44, 90.0)])
    assert won.seed == 43
    # and the reverse listing gives the same answer, which is the property
    assert pf.select([_m(43, 90.0), _m(44, 90.0), _m(45, 90.0)]).seed == 43


def test_an_unpublishable_member_is_never_selected_but_is_always_reported():
    """CLAUSE (1) + CLAUSE (4). A member stopped by the WALL is not reproducible
    so it cannot win; it still APPEARS, with its reason, because dropping it
    would make the spread look tighter than the evidence supports."""
    members = [pf.unusable(42, pf.WALL_STOPPED_REASON, wall_truncated=True),
               _m(43, 90.0)]
    book = pf.build(2, 42, 3.0, members)
    assert book.winner_seed == 43
    assert [m.seed for m in book.members] == [42, 43]
    assert "42" in book.unusable_sentence()
    assert book.block()["members"][0]["reason"] == pf.WALL_STOPPED_REASON


def test_a_wall_stopped_window_solve_is_not_a_member():
    """CLAUSE (1) at the MAIN SOLVE, on a fabricated view rather than a real
    one — because a fixture small enough to run here will never wall-truncate,
    and a refusal that only fires on a board no test owns is a refusal nobody
    guards. (Written after the negative control for this branch came back GREEN:
    the live-path tests could not see it at all.)"""
    from mre.modules.rolling_horizon import _member_from_view

    class _V:
        wall_truncated = True
        status = "FEASIBLE"
        cost_ledger = {"total_cost": 1.0}       # a total it must NOT publish

    m = _member_from_view(42, _V(), 1.0)
    assert m.selectable is False and m.ledger_total is None
    assert m.reason == pf.WALL_STOPPED_REASON
    assert pf.select([m]) is None


def test_a_window_solve_with_no_ledger_is_not_a_member():
    """CLAUSE (3): selection is by the LEDGER, so a member without one is not a
    member — it is reported, with what the solver actually returned."""
    from mre.modules.rolling_horizon import _member_from_view

    class _V:
        wall_truncated = False
        status = "UNKNOWN"
        cost_ledger = {}

    m = _member_from_view(42, _V(), 1.0)
    assert m.selectable is False and "UNKNOWN" in m.reason


def test_no_publishable_member_is_a_real_outcome_not_an_exception():
    book = pf.build(2, 42, 3.0, [pf.unusable(42, "a"), pf.unusable(43, "b")])
    assert book.winner is None and book.spread_abs is None
    assert book.agreement_sentence() == ""
    assert "2 of 2" in book.unusable_sentence()


def test_a_spread_of_one_number_is_not_a_spread():
    """4B.21's tri-state discipline: below two publishable members the spread is
    None, never 0.00. Printing zero there would claim an agreement nobody
    observed."""
    book = pf.build(3, 42, 3.0, [_m(42, 90.0), pf.unusable(43, "x"),
                                 pf.unusable(44, "y")])
    assert book.spread_abs is None and book.spread_pct is None
    assert book.agreement_sentence() == ""


def test_the_spread_names_its_denominator():
    """4B.20's ruling: a percentage names what it is a percentage OF. Here it is
    of the WINNER, which is the figure a planner is asking about."""
    book = pf.build(2, 42, 3.0, [_m(42, 100.0), _m(43, 110.0)])
    assert book.spread_abs == 10.0
    assert book.spread_pct == pytest.approx(10.0)       # of 100, not of 110


@pytest.mark.parametrize("totals,expect", [
    ([90.0, 90.0, 90.0], "landed on the same total"),
    ([100.0, 100.5, 100.2], "within 0.50% of each other"),
    ([100.0, 130.0, 110.0], "spread 30.00% apart"),
])
def test_the_three_agreement_registers(totals, expect):
    """CLAUSE (4) cashing in. Agreement is a trust statement; SCATTER is the
    same statement in the other direction and is never softened — the sentence
    says the window is far from settled, because it is."""
    book = pf.build(len(totals), 42, 3.0,
                    [_m(42 + i, t) for i, t in enumerate(totals)])
    assert expect in book.agreement_sentence()


def test_scatter_says_the_window_is_far_from_settled():
    book = pf.build(2, 42, 3.0, [_m(42, 100.0), _m(43, 130.0)])
    assert "far from settled" in book.agreement_sentence()


def test_a_single_member_declares_one_search_not_a_portfolio_of_one():
    """CLAUSE (2): K=1 is what every board has always been. Dressing it up as a
    portfolio would make the declaration a claim about a search nobody ran."""
    book = pf.build(1, 42, 6.0, [_m(42, 90.0)])
    assert "one seeded search" in book.declaration()
    assert "best of" not in book.declaration()
    assert book.agreement_sentence() == ""


def test_the_declaration_states_k_and_the_budget():
    """CLAUSE (2): K and the per-member budget are DECLARED — visible, never
    hidden. Both must be readable off the sentence itself, not only the JSON."""
    book = pf.build(5, 42, 3.0, [_m(42 + i, 90.0) for i in range(5)])
    d = book.declaration()
    assert "best of 5 seeded searches" in d and "3 deterministic units" in d
    assert "42" in d and "46" in d


def test_provenance_distinguishes_a_declared_k_from_a_defaulted_one():
    """The coarse zone's rho discipline, on K: a defaulted coefficient must
    never read as a customer's choice."""
    a = pf.build(3, 42, 3.0, [_m(42, 1.0)], k_declared=True,
                 det_time_declared=False).block()
    assert a["k_provenance"] == "declared"
    assert a["det_time_s_provenance"] == "defaulted"


def test_seeds_are_consecutive_from_seed0():
    """Consecutive by ruling, so the SET is a function of (seed0, K) and nobody
    can quietly pick the seed that wins on the board in front of them — the
    temptation 4B.24 named and refused."""
    assert pf.seeds_for(5, 42) == [42, 43, 44, 45, 46]
    with pytest.raises(ValueError):
        pf.seeds_for(0)


# ---------------------------------------------------------------------------
# clause (5) — parallelism BETWEEN runs, never inside one
# ---------------------------------------------------------------------------

def _square_member(seed: int):
    """A picklable member function. Module-level on purpose: a closure cannot
    survive the pickle a process pool performs, and on Windows the pool spawns."""
    return pf.PortfolioMember(seed=seed, ledger_total=float(seed * seed),
                              status="OPTIMAL")


def _exploding_member(seed: int):
    if seed == 43:
        raise RuntimeError("boom")
    return _square_member(seed)


def test_members_run_sequentially_by_default():
    got = pf.run_members(_square_member, [42, 43, 44])
    assert [m.ledger_total for m in got] == [42 * 42, 43 * 43, 44 * 44]


def test_a_member_that_raises_never_loses_the_others():
    got = pf.run_members(_exploding_member, [42, 43, 44])
    assert got[1].selectable is False and "boom" in got[1].reason
    assert pf.select(got).seed == 42


@pytest.mark.slow
def test_members_run_in_separate_processes_and_come_back_in_seed_order():
    """CLAUSE (5): separate PROCESSES, never CP-SAT ``workers > 1``. Ordering is
    restored by SEED regardless of completion order, so :func:`select` sees the
    same sequence either way and the portfolio stays deterministic under
    parallelism."""
    got = pf.run_members(_square_member, [44, 42, 43], workers=3)
    assert [m.seed for m in got] == [44, 42, 43]
    assert [m.ledger_total for m in got] == [44 * 44, 42 * 42, 43 * 43]


def test_nothing_in_the_portfolio_ever_names_a_cp_sat_worker_count():
    """The structural half of clause (5). CP-SAT parallelism inside one solve is
    exactly what the determinism rule forbids; this module routes around it, so
    it must never reach for it."""
    src = (REPO / "src" / "mre" / "modules" / "portfolio.py").read_text("utf-8")
    # The docstring NAMES the parameter, to say it is never reached for; what
    # must not appear is a USE of it.
    assert "num_search_workers=" not in src


# ---------------------------------------------------------------------------
# the live path — a real plant, a real window solve
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plant(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant
    d = tmp_path_factory.mktemp("portfolio")
    generate(d / "sub", scenario="pilot_scale", orders=ORDERS, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


def _digest(view) -> str:
    """The rolling golden's own canonical placement hash (tools/rolling_golden.py)
    — the digest clause (2)'s compatibility promise is made against."""
    rows = sorted([oid, c["resource"], c["start"], c["end"]]
                  for oid, c in view.placed.items())
    return hashlib.sha256(json.dumps(rows, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _view(plant, **kw):
    from mre.modules.rolling_horizon import build_rolling_view
    return build_rolling_view(
        plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        deterministic=True, seed=kw.pop("seed", 42),
        member_time_limit_s=WALL_CEILING_S, det_total=DET_TOTAL, **kw)


@pytest.fixture(scope="module")
def direct(plant):
    return _view(plant)


@pytest.mark.slow
def test_premise_the_fixture_actually_solves_and_prices(direct):
    """PREMISE. Every test below reads a LEDGER TOTAL off a window solve. A
    fixture that placed nothing, or placed work and produced no ledger, would
    make all of them pass while proving nothing about selection."""
    assert direct.status in ("OPTIMAL", "FEASIBLE")
    assert direct.placed, "the window solve placed no operations"
    total = (direct.cost_ledger or {}).get("total_cost")
    assert total is not None and total > 0
    assert not direct.wall_truncated, (
        "the window solve hit the WALL ceiling — every member below would be "
        "correctly refused and this file would be measuring its own timeout")


@pytest.mark.slow
def test_k_of_one_is_byte_for_byte_the_same_schedule(plant, direct):
    """CLAUSE (2), PROVEN BY DIGEST rather than asserted. K=1 must be exactly
    ``build_rolling_view`` — same placements, same ledger, and no portfolio at
    all to declare."""
    from mre.modules.rolling_horizon import solve_rolling_portfolio
    view, book = solve_rolling_portfolio(
        plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        deterministic=True, seed=42, member_time_limit_s=WALL_CEILING_S,
        det_total=DET_TOTAL, k=1)
    assert book is None, "K=1 declares no portfolio; there is nothing to declare"
    assert _digest(view) == _digest(direct)
    assert view.cost_ledger["total_cost"] == direct.cost_ledger["total_cost"]
    assert view.status == direct.status


@pytest.mark.slow
def test_k_of_one_puts_no_portfolio_block_in_the_document(plant, direct):
    """The other half of clause (2): a K=1 document is its pre-1.13 self apart
    from the version string. A block saying "best of 1" would be a claim about a
    portfolio nobody ran — 4B.24's absent-by-construction discipline."""
    from mre.modules.schedule_assembler import assemble_rolling_document
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=direct, schedule_id="s",
                                    run_id="r", identity_map=idmap,
                                    portfolio=None)
    assert doc.solver.portfolio is None
    assert doc.contract_version == CONTRACT_VERSION

    # AND the assembler's own guard, independently: handed a K=1 Portfolio
    # OBJECT it still emits nothing. Two things must both hold for clause (2) —
    # the solver returns None at K=1, and the assembler would refuse anyway —
    # and the first was hiding the second (its negative control ran green).
    one = pf.build(1, 42, DET_TOTAL, [_m(42, 1.0)])
    doc2 = assemble_rolling_document(plant=plant, view=direct, schedule_id="s",
                                     run_id="r", identity_map=idmap,
                                     portfolio=one)
    assert doc2.solver.portfolio is None


@pytest.fixture(scope="module")
def book3(plant):
    from mre.modules.rolling_horizon import solve_rolling_portfolio
    return solve_rolling_portfolio(
        plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        deterministic=True, seed=42, member_time_limit_s=WALL_CEILING_S,
        det_total=DET_TOTAL, k=3)


@pytest.mark.slow
def test_a_real_portfolio_publishes_every_member(book3):
    view, book = book3
    assert book is not None and book.k == 3
    assert [m.seed for m in book.members] == [42, 43, 44]
    assert all(m.ledger_total is not None for m in book.members), (
        "every member of this portfolio should have solved and priced")
    assert book.winner_total == min(m.ledger_total for m in book.members)


@pytest.mark.slow
def test_the_published_view_is_the_winning_member(book3):
    """The point of the whole wrapper: the board on disk is the member that won,
    not the seed the caller happened to pass. ``solve_rolling_portfolio`` proves
    this on the way through — a re-solve that priced differently raises
    PortfolioDrift — and this asserts the result."""
    view, book = book3
    assert view.cost_ledger["total_cost"] == pytest.approx(book.winner_total,
                                                           abs=0.01)


@pytest.mark.slow
def test_a_real_portfolio_reaches_the_document_as_a_declaration(plant, book3):
    view, book = book3
    from mre.modules.schedule_assembler import assemble_rolling_document
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id="s",
                                    run_id="r", identity_map=idmap,
                                    portfolio=book)
    blk = doc.solver.portfolio
    assert blk is not None
    assert blk.k == 3 and blk.seed0 == 42
    assert blk.winner_seed == book.winner_seed
    assert len(blk.members) == 3
    assert "best of 3 seeded searches" in blk.declaration
    # clause (4): the LOSERS' totals are in the document, not just the winner's
    assert [m.ledger_total for m in blk.members] == \
           [m.ledger_total for m in book.members]
    assert blk.agreement, "a 3-member portfolio must say something about spread"


@pytest.mark.slow
def test_the_portfolio_is_deterministic_run_to_run(plant, book3):
    """CLAUSE (1) as a property, not a promise: the same portfolio run twice
    gives the same winner, the same member totals and the same spread."""
    from mre.modules.rolling_horizon import solve_rolling_portfolio
    _view2, again = solve_rolling_portfolio(
        plant, window_days=WINDOW_DAYS, frozen_days=FROZEN_DAYS,
        deterministic=True, seed=42, member_time_limit_s=WALL_CEILING_S,
        det_total=DET_TOTAL, k=3)
    _v, first = book3
    assert again.winner_seed == first.winner_seed
    assert [m.ledger_total for m in again.members] == \
           [m.ledger_total for m in first.members]
    assert again.spread_abs == first.spread_abs


def test_a_portfolio_of_draws_is_refused():
    """CLAUSE (1) at the door. Without a deterministic budget the members are
    not runs, they are draws, and "the best of five draws" is a number with no
    meaning — so it is refused rather than computed. The refusal happens before
    the plant is touched, which is why this needs no fixture."""
    from mre.modules.rolling_horizon import solve_rolling_portfolio
    with pytest.raises(ValueError, match="portfolio of draws"):
        solve_rolling_portfolio(None, window_days=WINDOW_DAYS,
                                frozen_days=FROZEN_DAYS, deterministic=False,
                                k=3)
