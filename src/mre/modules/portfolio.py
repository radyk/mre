"""R-BK1 — THE PUBLISHED BOARD IS A PORTFOLIO, NOT A DRAW (Session 4B.25).

4B.24 measured the thing this module exists to harvest. Same board, same
incumbent, same one deterministic unit of unpinned search, five seeds:

    seed 42 -> 0%      seed 43 -> 0%      seed 44 -> -16.3%
    seed 45 -> -13.2%  seed 46 -> 0%

The seed decides. Not the budget alone, not the model, not the machine — the
seed. That spread at a fixed budget is the largest quality lever measured in
this project, the published board today is ONE draw from it, and the machine's
other cores sit idle by policy (the determinism rule forbids CP-SAT
``workers > 1``, correctly: a parallel portfolio inside one solve is not
reproducible).

R-BK1's resolution is to run K searches instead of one and publish the best.
The five clauses, and where each lives:

  (1) DETERMINISM. Every member is a full deterministic run — deterministic
      budget, its own pinned seed, ``workers=1``, wall as a SAFETY CEILING only.
      Selection is ``min`` over a FIXED set with a total order (ledger, then
      seed), so the portfolio as a whole is a pure function of its inputs.
      :func:`select` is that function, and it is pure. A member the WALL
      stopped is not reproducible and is therefore NOT SELECTABLE — the same
      refusal 4B.24 clause (1) put on the sandbox baseline, in the same words.

  (2) DECLARED COEFFICIENTS. K and the per-member budget are visible on the
      certificate with their provenance (:meth:`Portfolio.block`), exactly as
      the coarse zone's rho is (``CoarseCoefficients.certificate_block``).
      **K=1 IS EXACTLY TODAY'S BEHAVIOUR**, and at K=1 there is no portfolio: no
      block is emitted, so every existing golden, digest and pinned world is
      byte-identical. The block is ABSENT BY CONSTRUCTION rather than present
      and empty — the discipline 4B.24 put on the delta card's missing
      re-optimization row, and 4B.11's on the tardiness split.

  (3) SELECTION IS BY THE LEDGER. Never the raw objective. 4B.7's lesson: the
      objective is not money on every path, and two members can carry objectives
      that are not comparable to each other at all.

  (4) THE LOSERS ARE NOT DISCARDED SILENTLY. Every member's ledger total is
      published beside the winner's. The cross-seed SPREAD is the stability
      figure 4B.12 named as the honest companion to the gap — and unlike the
      gap it costs nothing extra here, because the searches have already run.
      When five independent searches agree, saying so is a trust statement;
      when they scatter, saying so is the same statement in the other
      direction.

  (5) PARALLELISM BETWEEN RUNS, NEVER INSIDE ONE. :func:`run_members` at
      ``workers > 1`` uses separate PROCESSES. Nothing in this module ever sets
      ``num_search_workers``; that parameter belongs to a solve, and a solve
      here is always single-worker.

This module owns the primitive: the member record, the pure selection, the
authored declaration and spread sentences, and the runner. It knows nothing
about rolling views, baselines or ledgers — its callers
(``rolling_horizon.solve_rolling_portfolio``, ``sandbox.audit_incumbent``) hand
it a member function and read back a :class:`Portfolio`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

# --- declared coefficients (clause 2) --------------------------------------

#: THE DEFAULT IS ONE, AND FLIPPING IT IS DARYN'S CALL. At K=1 not one line of
#: the solve path behaves differently and no portfolio block is emitted, which
#: is what makes clause (2)'s compatibility promise provable by digest rather
#: than argued.
DEFAULT_K = 1

#: The first seed. Members take ``seed0 .. seed0+K-1`` — CONSECUTIVE, so the set
#: is a function of (seed0, K) and nobody can quietly pick the seed that happens
#: to win on the board in front of them (the temptation 4B.24 named and refused).
DEFAULT_SEED0 = 42

#: Members run one at a time by default. The laptop has no cores to spare while
#: a session is measuring; the cloud box is then a config change, not a session.
DEFAULT_WORKERS = 1

#: Below this the members are reported as AGREEING rather than as spread. It is
#: a wording threshold and nothing else — the number itself is always published.
AGREEMENT_PCT = 1.0

#: Two ledger totals within this are the same total. The ledger rounds to the
#: cent; a spread of half a cent is arithmetic noise, not disagreement.
SAME_TOTAL_ABS = 0.005


@dataclass(frozen=True)
class PortfolioMember:
    """One seeded deterministic run, and what it found.

    ``selectable`` is False for a run whose result cannot be published under
    clause (1) — it did not finish, produced no ledger, or was stopped by the
    WALL rather than by its deterministic budget. ``reason`` says which. An
    unselectable member is still REPORTED (clause 4): "this seed did not finish"
    is a fact about the search, and dropping it silently would make the spread
    look tighter than the evidence supports.
    """
    seed: int
    ledger_total: Optional[float] = None
    status: str = ""
    det_consumed: Optional[float] = None
    wall_time_s: Optional[float] = None
    wall_truncated: bool = False
    selectable: bool = True
    reason: str = ""

    def row(self) -> dict:
        return {"seed": self.seed, "ledger_total": self.ledger_total,
                "status": self.status, "det_consumed": self.det_consumed,
                "wall_time_s": self.wall_time_s,
                "selectable": self.selectable, "reason": self.reason}


def unusable(seed: int, reason: str, *, status: str = "",
             wall_truncated: bool = False, **kw) -> PortfolioMember:
    """A member that ran and cannot be published. Never silently dropped."""
    return PortfolioMember(seed=seed, ledger_total=None, status=status,
                           wall_truncated=wall_truncated, selectable=False,
                           reason=reason, **kw)


# The clause-(1) refusal, worded once so every caller says the same thing.
WALL_STOPPED_REASON = ("stopped by the wall, not its deterministic budget, so "
                       "this member is not reproducible")


def select(members: Sequence[PortfolioMember]) -> Optional[PortfolioMember]:
    """THE SELECTION (clauses 1 and 3) — pure, total, and the whole reason the
    portfolio is deterministic.

    Lowest LEDGER total wins; ties break by lowest SEED. Both keys are exact
    (a float and an int over a fixed finite set), so this returns the same
    member for the same inputs on every machine, in every order, forever.
    Returns None when no member is publishable — which is a real outcome and
    never an exception: the caller then falls back to the single-seed path and
    says so.
    """
    usable = [m for m in members if m.selectable and m.ledger_total is not None]
    if not usable:
        return None
    return min(usable, key=lambda m: (m.ledger_total, m.seed))


@dataclass(frozen=True)
class Portfolio:
    """K seeded deterministic runs, the one that won, and the spread."""
    k: int
    seed0: int
    det_time_s: float
    members: tuple = ()
    workers: int = DEFAULT_WORKERS
    wall_time_s: float = 0.0
    #: Provenance, exactly as the coarse coefficients carry it: a defaulted K
    #: must never read as a customer's choice.
    k_declared: bool = False
    det_time_declared: bool = False

    # -- what it found ------------------------------------------------------

    @property
    def usable(self) -> list:
        return [m for m in self.members
                if m.selectable and m.ledger_total is not None]

    @property
    def winner(self) -> Optional[PortfolioMember]:
        return select(self.members)

    @property
    def winner_seed(self) -> Optional[int]:
        w = self.winner
        return None if w is None else w.seed

    @property
    def winner_total(self) -> Optional[float]:
        w = self.winner
        return None if w is None else w.ledger_total

    @property
    def spread_abs(self) -> Optional[float]:
        """max − min over the publishable members. None below two of them: a
        spread of one number is not a spread, and reporting 0.00 there would
        claim an agreement nobody observed."""
        tot = [m.ledger_total for m in self.usable]
        if len(tot) < 2:
            return None
        return round(max(tot) - min(tot), 2)

    @property
    def spread_pct(self) -> Optional[float]:
        """The spread as a percentage OF THE WINNER — the figure a planner is
        actually asking about ("how much better could this have been?"). The
        denominator is named here and in the sentence, per 4B.20's ruling."""
        s = self.spread_abs
        if s is None:
            return None
        best = min(m.ledger_total for m in self.usable)
        if abs(best) < SAME_TOTAL_ABS:
            return None
        return round(100.0 * s / abs(best), 4)

    @property
    def agree(self) -> Optional[bool]:
        s = self.spread_abs
        if s is None:
            return None
        pct = self.spread_pct
        return s <= SAME_TOTAL_ABS or (pct is not None and pct <= AGREEMENT_PCT)

    # -- what it says -------------------------------------------------------

    def declaration(self) -> str:
        """Clause (2): K and the per-member budget, in words, on the
        certificate. A single-member portfolio says so plainly rather than
        dressing one search up as a portfolio of one."""
        if self.k <= 1:
            return (f"one seeded search at {self.det_time_s:g} deterministic "
                    f"units (seed {self.seed0})")
        return (f"best of {self.k} seeded searches at {self.det_time_s:g} "
                f"deterministic units each (seeds {self.seed0}"
                f"–{self.seed0 + self.k - 1})")

    def agreement_sentence(self) -> str:
        """Clause (4) cashing in: the losers' totals, said as one sentence.

        Three registers, because three different things are true. All landing
        on the same total is the strongest trust statement a search can make
        about itself. Landing close is nearly as good. SCATTERING is not a
        failure to report — it is the finding, and it says the board is far from
        settled, which is exactly what a planner should know before treating
        this schedule as the answer."""
        n = len(self.usable)
        if self.k <= 1 or n < 2:
            return ""
        s, pct = self.spread_abs, self.spread_pct
        if s is not None and s <= SAME_TOTAL_ABS:
            return f"all {n} seeded searches landed on the same total"
        if pct is None:
            return f"the {n} seeded searches spread ${s:,.2f} apart"
        if pct <= AGREEMENT_PCT:
            return (f"the {n} seeded searches landed within {pct:.2f}% of each "
                    f"other")
        return (f"the {n} seeded searches spread {pct:.2f}% apart — this window "
                f"is far from settled")

    def unusable_sentence(self) -> str:
        """What was run and could NOT be published. Silence here would let a
        portfolio of five report the agreement of the two that finished."""
        bad = [m for m in self.members if not (m.selectable
                                               and m.ledger_total is not None)]
        if not bad:
            return ""
        seeds = ", ".join(str(m.seed) for m in bad)
        return (f"{len(bad)} of {self.k} member(s) could not be published "
                f"(seed(s) {seeds})")

    # -- the certificate ----------------------------------------------------

    def block(self) -> dict:
        """The certificate's view (clause 2 + clause 4).

        Callers emit this ONLY at K > 1 — see the module docstring. Every member
        appears, publishable or not, with its own seed and its own total."""
        return {
            "k": self.k,
            "k_provenance": "declared" if self.k_declared else "defaulted",
            "det_time_s": self.det_time_s,
            "det_time_s_provenance": ("declared" if self.det_time_declared
                                      else "defaulted"),
            "seed0": self.seed0,
            "workers": self.workers,
            "execution": "processes" if self.workers > 1 else "sequential",
            "declaration": self.declaration(),
            "agreement": self.agreement_sentence(),
            "unpublished": self.unusable_sentence(),
            "winner_seed": self.winner_seed,
            "winner_ledger_total": self.winner_total,
            "spread_abs": self.spread_abs,
            "spread_pct": self.spread_pct,
            "members": [m.row() for m in self.members],
            "wall_time_s": round(self.wall_time_s, 3),
        }


def seeds_for(k: int, seed0: int = DEFAULT_SEED0) -> list:
    """``seed0 .. seed0+k-1``. Consecutive by ruling — see DEFAULT_SEED0."""
    if k < 1:
        raise ValueError(f"a portfolio needs at least one member, got k={k}")
    return [seed0 + i for i in range(k)]


def run_members(member_fn: Callable[[int], PortfolioMember],
                seeds: Sequence[int],
                workers: int = DEFAULT_WORKERS) -> list:
    """Run one member per seed and return them IN SEED ORDER.

    Clause (5): at ``workers > 1`` the members run in separate PROCESSES —
    never as CP-SAT search workers, which is the thing the determinism rule
    forbids and which this whole module exists to route around. Ordering is
    restored by seed regardless of completion order, so the result is
    independent of scheduling and :func:`select` sees the same sequence either
    way.

    ``member_fn`` must be picklable at ``workers > 1`` (a module-level function,
    not a closure). A member that RAISES becomes an unpublishable member naming
    the exception — one seed blowing up must not lose the other four.
    """
    seeds = list(seeds)
    if workers <= 1 or len(seeds) <= 1:
        return [_guarded(member_fn, s) for s in seeds]

    from concurrent.futures import ProcessPoolExecutor

    out: dict = {}
    with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as pool:
        futures = {pool.submit(_guarded, member_fn, s): s for s in seeds}
        for fut, seed in futures.items():
            try:
                out[seed] = fut.result()
            except Exception as exc:  # noqa: BLE001 — a dead worker is a member
                out[seed] = unusable(seed, f"member process failed: "
                                           f"{type(exc).__name__}: {exc}")
    return [out[s] for s in seeds]


def _guarded(member_fn: Callable[[int], PortfolioMember],
             seed: int) -> PortfolioMember:
    """Run one member, converting any failure into an unpublishable member."""
    try:
        return member_fn(seed)
    except Exception as exc:  # noqa: BLE001
        return unusable(seed, f"member failed: {type(exc).__name__}: {exc}")


def build(k: int, seed0: int, det_time_s: float, members: Sequence,
          *, workers: int = DEFAULT_WORKERS, wall_time_s: float = 0.0,
          k_declared: bool = False,
          det_time_declared: bool = False) -> Portfolio:
    """Assemble a :class:`Portfolio` from members already run."""
    return Portfolio(k=k, seed0=seed0, det_time_s=float(det_time_s),
                     members=tuple(members), workers=workers,
                     wall_time_s=wall_time_s, k_declared=k_declared,
                     det_time_declared=det_time_declared)
