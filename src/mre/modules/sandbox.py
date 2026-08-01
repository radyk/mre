"""Tier-2 sandbox re-solve under a hard latency budget (docs/07 Phase 3, R-T1c;
elaborates R-DP2).

When the planner drops a bar (R-DP1: the pin is machine + time exactly as
displayed), the what-if sandbox re-solves the model with that ONE op pinned and
its surroundings free — and it must never spin unboundedly. The re-solve runs
under a hard, VISIBLE budget (a design token, initial 15s) with exactly three
honest outcomes:

  (1) VERDICT within budget            → the delta card as designed. A proven
      (verdict)                          OPTIMAL delta, or a proven-INFEASIBLE
                                         return-home with the binding reason.
  (2) FEASIBLE, bound unproven         → the card ships FLAGGED ("≈ delta,
      (feasible_unproven)                bound not proven" — SOLVER_NONOPTIMAL
                                         surfaced in the UI).
  (3) NOTHING within budget            → R-DP2 return-home ("couldn't verify
      (no_verdict)                       this placement in time").

The board is never blocked during the wait. CI acceptance (a standing latency
regression): a pinned re-solve on the demo fixture must return a VERDICT within
budget — so a heavy fixture fails a test before it fails a demo.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# The budget is a DESIGN TOKEN, not a magic constant — feel-iteration owned,
# surfaced in the UI, and the single knob the latency regression is measured
# against (R-T1c). Override per-call for tests / tuning.
SANDBOX_BUDGET_S = 15.0

# --- R-T2 two-beat interaction contract (Session 4B.3b) --------------------
# BEAT ONE is a first-feasible feasibility check under a SMALL deterministic
# budget — a cheap "can the op go here at all" verdict that NEVER displays a
# monetary quantity (R-T2(1)). It is a RELAXATION of the full budgeted solve
# (beat two): it pins only the dragged op and does NOT hold the lineage's
# committed/standing work, so beat two (which does) may legitimately CONTRADICT
# it (infeasible, or a materially different placement) — R-T2(4). The budget is
# a design token, small so grab→ghost stays snappy; measured shape at demo
# density is first-feasible ~0.3s.
# SESSION 4B.24 ITEM 1(a) RAISED THIS FROM 2.0, AND THE MEASUREMENT INVERTED THE
# EXPLANATION. Beat one on the dense demo board (386 bars), founder's gesture,
# seeds 42-46, reaches its verdict in **0.0426 deterministic units** — the same
# figure to four decimal places at every seed — while spending **2.5 to 3.9
# SECONDS of wall**, and 4.84s on a colliding pin. The deterministic meter barely
# counts PRESOLVE, which is where that wall goes; so the 2.0s ceiling was cutting
# off a check costing four hundredths of a unit, and 4B.23's "beat one's budget
# is marginal" was right about the symptom and wrong about the currency: raising
# the DETERMINISTIC budget alone would have changed nothing.
#
# 12.0s is a SAFETY CEILING at 2.5x the measured worst case, not a spend: a
# proven-impossible pin still returns in 0.06s, and the founder's in ~3s.
FEASIBILITY_BUDGET_S = 12.0
# The deterministic-time budget for beat one, so a first-feasible verdict is
# reproducible run-to-run (workers=1 + fixed seed + max_deterministic_time).
# 2.0 is 47x the measured 0.0426 — deliberately far above it, because what this
# number must guarantee is that the DETERMINISTIC budget is what stops the search
# on any board, never the wall.
FEASIBILITY_DET_TIME_S = 2.0

# --- Session 4B.24: DETERMINISTIC SANDBOX LAW (R-T2 amendment, clause 1) ----
# EVERY SANDBOX SOLVE IS DETERMINISTIC. Before this session beat two and the
# baseline ran with workers=1 and a fixed seed but NO deterministic budget —
# only a wall clock — so where they stopped depended on how fast the machine was
# that second. On a board whose incumbent sits at a 92.4% gap the card was
# reporting the difference between two lottery draws and labelling it "your
# move": the same pin returned feasible_unproven ($2,596.67), no_verdict, and
# -$50,784.33 across three runs of the same gesture.
#
# The seed is pinned here rather than left at 0 so the shipped configuration is
# the one Item 1 measured across seeds 42-46.
SANDBOX_SEED = 42
# The deterministic budget for any WINDOW RE-SOLVE reached from the sandbox — the
# baseline, the opportunity search, the accept re-solve.
#
# ITEM 1(b) SET OUT TO MEASURE A PLATEAU AND FOUND THERE ISN'T ONE. Dense demo
# board, seeds 42-46, one deterministic unit each: the first solution is the
# warm-started incumbent at ~4.7s of wall, and on the seeds that improve at all
# the improvements run right up to the budget edge — seed 45's LAST improvement
# landed at 76.9s of a 77.0s solve. More budget keeps finding money. So this
# number cannot be justified as "past the plateau"; it is justified as "as much
# as a gesture-adjacent solve may spend", and the deliberate audit (clause 5)
# gets more.
#
# THE EXCHANGE RATE IS MEASURED: 40.8 to 77.0 SECONDS PER UNIT on the dense
# board. A caller enabling the opportunity search must give it a wall ceiling
# that actually clears this budget, or clause (1) will (correctly) refuse to
# price from a wall-truncated draw. That is exactly why the opportunity search is
# OFF on the gesture path.
SANDBOX_DET_TIME_S = 2.0

# WALL AS SAFETY CEILING ONLY — and that has to be enforced, not merely intended.
# A caller who asks for 2.0 deterministic units under a 15-second wall has asked
# for two incompatible things, and clause (1) says which one wins: the
# deterministic budget decides where the search stops, and the wall exists to stop
# a pathology. So the wall a re-solve actually gets is the caller's ceiling OR the
# deterministic budget converted at a rate above anything ever measured —
# whichever is LARGER. Measured worst case is 77.0 s/unit (Item 1(b), seed 45);
# 120 is that with half again on top, so only a machine running at half the
# slowest rate we have ever seen can be stopped by the clock.
#
# The consequence is deliberate: `applied_time_limit_s` may exceed the requested
# `budget_s`, and it reports the limit ACTUALLY applied — which is the question
# that field exists to answer.
WALL_PER_DET_UNIT_CEILING_S = 120.0


def wall_ceiling_for(budget_s: float, det_time_s: Optional[float],
                     deterministic: bool = True) -> float:
    """The wall limit a deterministic re-solve actually gets. Pure; see above."""
    if not deterministic or det_time_s is None:
        return budget_s
    return max(float(budget_s), float(det_time_s) * WALL_PER_DET_UNIT_CEILING_S)

# --- Beat one's THREE states (Session 4B.23, Item 5(b)) --------------------
# A CLAIM ABOUT OUR PROCESS MUST NOT BE RENDERED AS A CLAIM ABOUT THE PLANT.
# This is the third instance of a species already ruled twice: ``CostProof``
# gained a fourth state (``unreadable``, 4B.18) so a fact about our STORAGE
# could not be spoken as a fact about the plant, and ``partitions()`` went
# tri-state (4B.21) so an unprovable split could not be reported as a proven
# one. Beat one had the same fusion on a BOOLEAN: ``feasible`` is False both
# when the solver PROVED no placement exists (INFEASIBLE — about the plant) and
# when it ran out of budget before deciding (UNKNOWN — about us). The cockpit
# read the boolean, said "this placement isn't possible here", and snapped the
# bar home — on a board where beat two, called directly, priced the same
# gesture at $2,596.67 (4B.22a §5(e), and Session 4B.23's own measurement).
#
# ``verdict`` names which of the three it is. ``feasible`` keeps its exact
# meaning — PROVEN possible — and is now never sufficient on its own to author
# a sentence about the plant.
FEASIBILITY_POSSIBLE = "possible"          # OPTIMAL/FEASIBLE — a placement exists
FEASIBILITY_IMPOSSIBLE = "impossible"      # INFEASIBLE — proven that none does
FEASIBILITY_UNDETERMINED = "undetermined"  # UNKNOWN — the CHECK did not finish


def classify_feasibility(status: str) -> str:
    """Map a beat-one solver status to one of the three beat-one verdicts.

    Pure and unit-testable without a solve, exactly like
    :func:`classify_sandbox_outcome`. An unrecognised status is UNDETERMINED —
    the fail-safe direction, because "I don't know" is always a true thing to
    say about our own process, while "impossible" is a claim about the plant.
    """
    if status in ("OPTIMAL", "FEASIBLE"):
        return FEASIBILITY_POSSIBLE
    if status == "INFEASIBLE":
        return FEASIBILITY_IMPOSSIBLE
    return FEASIBILITY_UNDETERMINED


def feasibility_message(verdict: str, budget_s: float,
                        wall_truncated: bool = False) -> str:
    """The authored sentence for each beat-one verdict.

    The UNDETERMINED sentence says what ran out — the budget, not the plant's
    room — and it never asserts the placement is either possible or not. Beat
    two is what decides; the caller proceeds to it.

    Session 4B.24: WHICH budget ran out is itself two different facts. A search
    stopped by its DETERMINISTIC budget stopped in the same place on every
    machine — the answer is reproducible, and asking again gets the same
    non-answer. A search stopped by the WALL stopped wherever this machine
    happened to be, and asking again may well answer. A planner deciding whether
    to retry needs to know which, so the sentence says."""
    if verdict == FEASIBILITY_POSSIBLE:
        return "this placement is possible — pricing it now"
    if verdict == FEASIBILITY_IMPOSSIBLE:
        return "this placement isn't possible here"
    if wall_truncated:
        return (f"I ran out of time checking this placement — the {budget_s:g}s "
                "ceiling stopped it, so trying again may well answer. Either "
                "way it is my clock running out, not a verdict about the plant")
    return ("I couldn't finish checking this placement inside my budget — that "
            "is my budget running out, not a verdict about the plant")

# A solve given ``time_limit = budget`` stops AT the budget and reports a hair
# over it (thread teardown). "Within budget" means it honored the budget, so a
# small stop-overhead margin is allowed — it is not a second budget.
_BUDGET_STOP_MARGIN_S = 1.0

# A moved op counts as MAJOR — and so earns a "why" clause on the delta card
# (session 3.3 CU3) — only when it shifted at least this far. A design token:
# it keeps the card from annotating twenty one-minute shuffles with reasons,
# leading instead with the displacements a planner actually feels.
MAJOR_MOVE_THRESHOLD_MIN = 60

# The three honest outcomes (R-T1c). String constants so evidence/JSON carry a
# stable vocabulary.
SANDBOX_VERDICT = "verdict"                    # (1) proven within budget
SANDBOX_FEASIBLE_UNPROVEN = "feasible_unproven"  # (2) feasible, bound unproven
SANDBOX_NO_VERDICT = "no_verdict"              # (3) nothing within budget


@dataclass
class SandboxResult:
    outcome: str                 # one of the three SANDBOX_* constants
    status: str                  # raw solver status (OPTIMAL|FEASIBLE|INFEASIBLE|UNKNOWN)
    within_budget: bool          # wall_time_s <= budget_s
    wall_time_s: float
    budget_s: float
    feasible: bool               # a placement exists with the pin held
    # The time limit actually handed to the solver for this re-solve (= budget_s
    # in normal operation). Echoed explicitly (session 3.3 CU5) so budget-vs-
    # actual is always inspectable straight from the payload — the "was 60s the
    # limit or the wall time?" question answers itself.
    applied_time_limit_s: float = 0.0
    objective: Optional[float] = None
    delta_pct: Optional[float] = None      # vs the incumbent objective (SCALED)
    delta_abs: Optional[float] = None      # objective_after - objective_before (SCALED)
    # The DOLLAR cost delta from the ledger (Phase-3 exit audit fix): the solver
    # objective is a SCALED, tardiness-weighted sum (~100× the dollar ledger), so
    # ``delta_abs`` must NEVER be shown as a dollar amount. These carry the true
    # cost delta — extracted from the re-solve's own ledger vs the base schedule's
    # total — so every number the delta card shows in dollars traces to ledger
    # records (docs/02 §4.4). None when the ledger could not be computed (the card
    # then degrades to a relative-% headline, never a false dollar figure).
    cost_delta_abs: Optional[float] = None   # dollars: total_after - total_before
    cost_delta_pct: Optional[float] = None   # cost_delta_abs / total_before * 100
    message: str = ""
    # The moved-set (R-DP7): every op the pinned re-solve displaced relative to
    # the incumbent, old → new (resource + start). The pinned op itself is
    # flagged (``pinned``) and always present when feasible. Warm-starting keeps
    # this set minimal by construction — the property that makes tracing it
    # tractable (R-DP7 implementation note). The cockpit maps operation_ref →
    # bar to draw the ghost-of-old + motion trace and the delta-card line items.
    moves: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)  # {operation_ref, resource_id, start}
    # --- R-T2 beat-two layered card (Session 4B.3b, CU2) --------------------
    # The deterministic correlation id linking this priced beat two to its beat
    # one (feasibility ghost). Derived from the pin, so the two beats of the same
    # gesture always agree without server state.
    correlation_id: str = ""
    # The ALWAYS-VISIBLE layer (decision-sufficient on its own):
    #   * cost_delta_abs / feasible (above) — the signed total + the verdict
    #   * dominant_driver — the one driver behind the change, in driver_phrase
    #     language, HEDGED where the attribution is by price rank alone (docs/02
    #     §4.2: EARLINESS_PREFERENCE). {code, phrase, hedge|None}.
    dominant_driver: dict = field(default_factory=dict)
    #   * affected_orders — the top-N orders this move touches, each with its own
    #     tardiness ($) and lateness (min) delta (per-Demand truth from the
    #     service outcomes, never per-WorkPackage). [{work_order, demand_ref,
    #     tardiness_delta, lateness_delta_min}], |delta|-ranked, N capped.
    affected_orders: list[dict] = field(default_factory=list)
    #   * lateness_delta_min — net tardiness-minutes introduced (+) or recovered
    #     (−) across every demand, so "made something late / rescued a date" is
    #     one number.
    lateness_delta_min: int = 0
    #   * no_committed_work_changes — the standing invariant, ASSERTED against the
    #     moved-set (a committed/standing-pinned op can never be a consequence).
    #     The card renders it as a line; a test pins it True.
    no_committed_work_changes: bool = True
    # The DETAIL layer (same card): the cost decomposition by ledger line. Each
    # entry {line, delta}; the lines sum EXACTLY to cost_delta_abs (rollup_of
    # discipline — the card may never claim arithmetic the ledger cannot back).
    # An explicit "other" remainder line carries any delta the named lines do not
    # factor (0 when the ledger fully decomposes). None when no ledger (degrade).
    cost_lines: Optional[list[dict]] = None
    # --- CU1 (Session 4B.5): DELTA ATTRIBUTION ------------------------------
    # ``cost_delta_abs`` measures the RE-SOLVE, not the MOVE — and the card read
    # as though it measured the move. The founder's specimen: two different
    # gestures on schedule rolling-279dec02-411 (ORD-38 → MILL-01 at Jan-8 08:30,
    # then at 07:00) produced IDENTICAL cards, −$11,975.83 to the cent, same four
    # affected orders. Both numbers were true and neither was about the gesture:
    # almost all of it was the window re-optimizing under a fresh budget, which
    # the incumbent had never been given.
    #
    # So the verdict SPLITS, always:
    #     window re-optimization  = baseline_total − incumbent_total
    #     your move               = pinned_total   − baseline_total
    # where the BASELINE is the same window, same budget, same standing
    # commitments, WITHOUT the gesture's pin. The planner's move is judged
    # against the baseline, never against the stale incumbent.
    #
    # ``attribution`` is "split" when a baseline was proven, "unavailable" when it
    # was not — in which case the card shows the UNSPLIT total with an explicit
    # "includes window re-optimization" line, and NEVER a silent fused number.
    # The two parts sum EXACTLY to ``cost_delta_abs`` (decomposition-sums
    # discipline, the same rule ``cost_lines`` follows).
    attribution: str = "unavailable"          # "split" | "unavailable"
    reopt_delta_abs: Optional[float] = None   # dollars: baseline − incumbent
    move_delta_abs: Optional[float] = None    # dollars: pinned − baseline
    baseline_total_cost: Optional[float] = None
    attribution_note: str = ""                # why unsplit, when unavailable
    # What the attribution cost in wall time (0.0 on a cache hit) — the honest
    # answer to "what did the split add to my wait", inspectable from the payload.
    baseline_wall_time_s: float = 0.0
    # --- Session 4B.24: the determinism receipt --------------------------------
    # The deterministic budget this solve was given, and what it actually
    # consumed. Together with ``wall_truncated`` they are how a reader tells a
    # reproducible answer from a lottery draw WITHOUT re-running it: a solve that
    # stopped on its deterministic budget returns the same result on any machine;
    # one the WALL stopped does not, and this module refuses to price it.
    det_time_s: Optional[float] = None
    det_consumed: Optional[float] = None
    wall_truncated: bool = False
    # --- Session 4B.24, R-T2 amendment clause (3): THE WINDOW'S OPPORTUNITY ----
    # The deterministic re-solve's improvement over the incumbent, when there is
    # one, is the SEARCH's discovery — never the planner's move. It gets its own
    # labelled section, its own affected list, and its own accept (clause 4).
    # {found, delta_abs, affected_orders, moved_op_count, sentence}; empty {} when
    # no baseline was proven or the search found nothing cheaper.
    opportunity: dict = field(default_factory=dict)
    # HOW the money on this card was computed. ``local`` (clause 2) means every
    # other placement was held and the ledger recomputed — the number is the move
    # and nothing else, and it is exact. ``resolve`` is the legacy whole-window
    # re-solve, still used by the accept path and by callers that need the
    # solver's own placements. A reader must never have to guess which they hold.
    pricing_mode: str = "resolve"
    # A PROVEN refusal from the local pricer, with the docs/05 family named —
    # ``LocalRefusal.summary()``. Distinct from ``message`` alone, because the
    # cockpit needs the ``holds_others`` bit to choose between "no" and "not
    # without moving other work".
    refusal: Optional[dict] = None
    # The model's own verdict on the held world with the pin applied
    # (``local_price.validate_held_world``), when this card was priced locally.
    validation: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return asdict(self)


# The field names beat one is FORBIDDEN to carry — any monetary quantity of any
# kind (R-T2(1), enforced BY CONSTRUCTION with a contract test that inspects the
# dataclass fields). Beat one is feasibility + placement + a correlation id only.
_MONEY_FIELD_TOKENS = ("cost", "delta", "price", "dollar", "objective", "ledger",
                       "tardiness", "spend", "money", "$")


@dataclass(frozen=True)
class FeasibilityGhost:
    """BEAT ONE of the R-T2 two-beat interaction: a first-feasible feasibility
    verdict + placement, NEVER a monetary quantity (R-T2(1)).

    This type CANNOT represent money by construction — it has no cost/delta/price/
    objective field, and ``test_feasibility_no_money`` asserts the field ABSENCE
    (not emptiness). The board renders ``placement`` in the R-M1 ghost class under
    a non-monetary "pricing…" state (R-T2(2)); beat two (the priced
    :class:`SandboxResult`, correlated by ``correlation_id``) supersedes it.

    Beat one mints NO edits and touches NO persistent state (R-T2(5))."""
    correlation_id: str
    feasible: bool               # PROVEN possible. False fuses two states — read
                                 # ``verdict``, never this, to author a sentence.
    within_budget: bool
    wall_time_s: float
    budget_s: float
    status: str                  # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    message: str
    # Session 4B.23: WHICH of the three states this is —
    # ``possible`` | ``impossible`` | ``undetermined``. ``undetermined`` is a
    # statement about the CHECK (it ran out of budget), never about the plant,
    # and the caller proceeds to beat two on it. Defaulted so an older payload
    # deserialises; every path this module returns sets it explicitly.
    verdict: str = FEASIBILITY_UNDETERMINED
    # placement of the pinned op AND any op the first-feasible solve moved —
    # resource + start/end ISO only, NO cost. [{operation_ref, resource_id,
    # start, end, pinned}]. The ghost the board draws.
    placement: list[dict] = field(default_factory=list)
    pin: dict = field(default_factory=dict)
    # Session 4B.24: the determinism receipt (see SandboxResult). Beat one has
    # always carried a deterministic budget; these say what it cost.
    det_time_s: Optional[float] = None
    det_consumed: Optional[float] = None
    wall_truncated: bool = False

    def summary(self) -> dict:
        return asdict(self)


def correlation_id_for(snapshot_id: str, pin_op_id: str,
                       pin_resource_id: Optional[str],
                       pin_start_iso: Optional[str]) -> str:
    """The deterministic id linking beat one to beat two for one gesture. Derived
    purely from the pin (+ snapshot), so both beats compute the SAME id with no
    server state — the client passes beat one's id into beat two and the two are
    provably the same gesture."""
    raw = f"{snapshot_id}|{pin_op_id}|{pin_resource_id}|{pin_start_iso}"
    return "corr-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def classify_sandbox_outcome(status: str, wall_time_s: float,
                             budget_s: float = SANDBOX_BUDGET_S) -> str:
    """Pure classifier — the heart of R-T1c, unit-testable without a solve.

    Maps a solve (status + wall time) to one of the three honest outcomes:

      * OPTIMAL / INFEASIBLE  → VERDICT — the solver PROVED something (an
        optimal delta, or that the pin cannot be honored this horizon). A proof
        that arrives is a verdict even if it landed at the budget edge.
      * FEASIBLE              → FEASIBLE_UNPROVEN when it ran out the budget
        (the common case: a placement exists but optimality is unproven); a
        FEASIBLE that somehow returned INSIDE the budget is still unproven, so
        it is flagged too — only a terminal proof clears the flag.
      * anything else (UNKNOWN / no solution) → NO_VERDICT (return home).

    ``wall_time_s`` / ``budget_s`` decide only ``within_budget`` in the result;
    the OUTCOME is a function of what the solver proved, because a budget-capped
    solve reports UNKNOWN/FEASIBLE precisely when it could not prove more.
    """
    if status in ("OPTIMAL", "INFEASIBLE"):
        return SANDBOX_VERDICT
    if status == "FEASIBLE":
        return SANDBOX_FEASIBLE_UNPROVEN
    return SANDBOX_NO_VERDICT


def _restrict_window(ops, wps, fuls, demands, restrict_op_ids):
    """Restrict the loaded entity sets to a rolling ACTIVE WINDOW (Session 4B.3c
    CU3). ``restrict_op_ids`` is the set of operation ids the window solve placed
    (committed ∪ active — every op with a persisted assignment). Restricting the
    build to exactly that set makes the sandbox re-solve the WINDOW, not the whole
    plant: the SolverBuilder derives the same horizon_start the window-0 solve did
    (it was built over the same ops), so the pin arithmetic aligns with the
    persisted placements, and the beyond-horizon (future) work never re-enters as
    free ops. None ⇒ no restriction (a monolithic schedule)."""
    if restrict_op_ids is None:
        return ops, wps, fuls, demands
    keep = set(restrict_op_ids)
    ops = [o for o in ops if o["id"] in keep]
    wp_ids = {o.get("workpackage_ref", "") for o in ops}
    wps = [w for w in wps if w["id"] in wp_ids]
    fuls = [f for f in fuls if f.get("workpackage_ref", "") in wp_ids]
    dem_ids = {f.get("demand_ref", "") for f in fuls}
    demands = [d for d in demands if d["id"] in dem_ids]
    return ops, wps, fuls, demands


# ---------------------------------------------------------------------------
# CU1 (Session 4B.5) — THE BASELINE: what the window costs with NO gesture at all.
# ---------------------------------------------------------------------------

@dataclass
class BaselineSolve:
    """The same window, same budget, same standing commitments — and NO pin.

    This is the reference the planner's move is judged against. Without it the
    delta card compares a freshly-budgeted re-solve to a STALE INCUMBENT, and the
    difference between those two is dominated by re-optimization the planner did
    not ask for and cannot influence — which is exactly why two different pins
    produced the same card to the cent.

    ``available`` is False when the baseline could not be PROVEN inside the
    budget. That is a first-class outcome, not an error: the card then shows the
    unsplit total and says out loud that it includes window re-optimization."""

    available: bool
    total_cost: Optional[float] = None
    status: str = ""
    outcome: str = ""
    wall_time_s: float = 0.0
    message: str = ""
    cached: bool = False
    # Session 4B.24: the determinism receipt. A baseline the WALL stopped is not
    # reproducible, so it is not `available` — an unsplit card is honest, a card
    # split against a lottery draw is not.
    det_time_s: Optional[float] = None
    det_consumed: Optional[float] = None
    wall_truncated: bool = False
    # Clause (3): the opportunity section's affected list is ITS OWN — the moves
    # and per-order consequences of THIS solve against the incumbent, never the
    # pinned solve's. Computed here because this is the only place the baseline's
    # own solve values exist.
    moves: list[dict] = field(default_factory=list)
    affected_orders: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return asdict(self)


# One baseline serves every card in a session until the INCUMBENT changes. The
# key is everything that defines the baseline solve — the run dir, the snapshot,
# the window restriction, the standing commitments, the budget and the
# determinism flag — so an accepted edit (new snapshot + new pin set) misses by
# construction and a second gesture on the same board hits.
_BASELINE_CACHE: "dict[str, BaselineSolve]" = {}
_BASELINE_CACHE_LIMIT = 8
_BASELINE_LOCK = threading.Lock()


def baseline_cache_key(out_dir: Path | str, snapshot_id: str, budget_s: float,
                       deterministic: bool,
                       standing_pins: Optional[list[dict]],
                       restrict_op_ids: Optional[set],
                       det_time_s: Optional[float] = None,
                       seed: Optional[int] = None) -> str:
    """Everything that defines the baseline solve, including its BUDGET (the
    4B.6b finding: a cached result keyed without the budget it was solved under
    is served to a caller asking for a different one) and, since 4B.24, its
    DETERMINISTIC budget and seed — which are now what decides where it stops."""
    pins = sorted(
        (str(p.get("operation_ref", "")), str(p.get("resource_id", "")),
         str(p.get("start", "")))
        for p in (standing_pins or []))
    payload = json.dumps({
        "out": str(out_dir), "snap": snapshot_id, "budget": round(budget_s, 3),
        "det": bool(deterministic), "pins": pins,
        "det_time": None if det_time_s is None else round(det_time_s, 4),
        "seed": seed,
        "window": sorted(restrict_op_ids) if restrict_op_ids is not None else None,
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def clear_baseline_cache() -> None:
    """Drop every cached baseline. Tests use it; nothing in the product needs to
    (the key changes whenever the incumbent does)."""
    with _BASELINE_LOCK:
        _BASELINE_CACHE.clear()


def baseline_window_solve(
    out_dir: Path | str,
    snapshot_id: str,
    *,
    budget_s: float = SANDBOX_BUDGET_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    standing_pins: Optional[list[dict]] = None,
    restrict_op_ids: Optional[set] = None,
    use_cache: bool = True,
    det_time_s: Optional[float] = SANDBOX_DET_TIME_S,
    seed: int = SANDBOX_SEED,
) -> BaselineSolve:
    """Re-solve the window with NO gesture pin, and return its ledger total.

    Everything else is held identical to the priced beat two: the same entity
    restriction, the same warm start from the incumbent, the same standing
    commitments (held in FULL here — there is no dragged op to exempt), the same
    budget and the same determinism. Only the pin is absent, so the difference
    between this and the pinned solve is attributable to the pin and to nothing
    else.

    Cached per incumbent (:func:`baseline_cache_key`). Fully guarded: any failure
    returns ``available=False`` with a stated reason — a baseline that could not
    be proven must degrade the card honestly, never take it down."""
    key = baseline_cache_key(out_dir, snapshot_id, budget_s, deterministic,
                             standing_pins, restrict_op_ids, det_time_s, seed)
    if use_cache:
        with _BASELINE_LOCK:
            hit = _BASELINE_CACHE.get(key)
        if hit is not None:
            return BaselineSolve(**{**asdict(hit), "cached": True})

    result = _baseline_window_solve_uncached(
        out_dir, snapshot_id, budget_s=budget_s, runs_subdir=runs_subdir,
        deterministic=deterministic, standing_pins=standing_pins,
        restrict_op_ids=restrict_op_ids, det_time_s=det_time_s, seed=seed)
    if use_cache:
        with _BASELINE_LOCK:
            _BASELINE_CACHE.pop(key, None)
            _BASELINE_CACHE[key] = result
            while len(_BASELINE_CACHE) > _BASELINE_CACHE_LIMIT:
                _BASELINE_CACHE.pop(next(iter(_BASELINE_CACHE)))
    return result


def _baseline_window_solve_uncached(
    out_dir: Path | str,
    snapshot_id: str,
    *,
    budget_s: float,
    runs_subdir: str,
    deterministic: bool,
    standing_pins: Optional[list[dict]],
    restrict_op_ids: Optional[set],
    det_time_s: Optional[float] = SANDBOX_DET_TIME_S,
    seed: int = SANDBOX_SEED,
) -> BaselineSolve:
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter

    out_dir = Path(out_dir)
    sandbox_dir = out_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    try:
        reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
        demands = list(reader.iter_entities("demand"))
        fuls = list(reader.iter_entities("fulfillment"))
        wps = list(reader.iter_entities("workpackage"))
        ops = list(reader.iter_entities("operation"))
        edges = list(reader.iter_entities("precedenceedge"))
        resources = list(reader.iter_entities("resource"))
        pools = list(reader.iter_entities("resourcepool"))
        calendars = list(reader.iter_entities("calendar"))
        constraints = list(reader.iter_entities("constraint"))
        costmodels = list(reader.iter_entities("costmodel"))
        incumbent_assignments = list(reader.iter_entities("assignment"))
        cost_model = costmodels[0] if costmodels else {}

        ops, wps, fuls, demands = _restrict_window(
            ops, wps, fuls, demands, restrict_op_ids)

        evidence = _read_evidence(out_dir / runs_subdir)
        ctx = derive_base_context(out_dir / runs_subdir)
        reference_date = _parse_ref_date(ctx.get("reference_date"))
        horizon_start, horizon_end = _m5_horizon(evidence)
        flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

        workers = 1 if deterministic else ctx.get("solver_workers")
        b_rep = Reporter.begin(
            module=ModuleCode.M5, purpose="sandbox baseline model build",
            config={"baseline": True, "pin": None},
            trigger="sandbox_baseline", snapshot_id=snapshot_id,
            sink_dir=sandbox_dir / "runs",
        )
        model, var_map = SolverBuilder(reference_date=reference_date).build(
            wps + ops + edges, resources + pools, flattened_cals,
            fuls + demands, constraints, cost_model,
        )
        b_rep.end(RunStatus.SUCCESS)

        apply_solution_hints(model, var_map, incumbent_assignments)
        # Every standing commitment is held, in full — there is no dragged op to
        # exempt, which is the entire point: this is the plan WITHOUT the gesture.
        try:
            sp.apply_standing_pins(model, var_map, standing_pins, horizon_start)
        except sp.PinUnsatisfiable as exc:
            return BaselineSolve(
                available=False, status="INFEASIBLE",
                outcome=SANDBOX_VERDICT,
                message=f"a standing commitment could not be held: {exc.reason}")

        r_rep = Reporter.begin(
            module=ModuleCode.M6, purpose="sandbox baseline solve",
            config={"time_limit": budget_s, "num_search_workers": workers,
                    "deterministic_time": det_time_s if deterministic else None,
                    "random_seed": seed if deterministic else None,
                    "baseline": True},
            trigger="sandbox_baseline", snapshot_id=snapshot_id,
            sink_dir=sandbox_dir / "runs",
        )
        t0 = time.monotonic()
        wall_limit = wall_ceiling_for(budget_s, det_time_s, deterministic)
        solve_result = SolveRunner(
            time_limit_seconds=wall_limit, num_search_workers=workers,
            random_seed=seed if deterministic else None,
            deterministic_time=det_time_s if deterministic else None,
        ).solve(model, var_map, r_rep)
        wall = round(time.monotonic() - t0, 3)
        feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
        r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)
        outcome = classify_sandbox_outcome(solve_result.status, wall, budget_s)
        receipt = {"det_time_s": det_time_s if deterministic else None,
                   "det_consumed": solve_result.det_consumed,
                   "wall_truncated": bool(solve_result.wall_truncated)}
        if not feasible:
            return BaselineSolve(
                available=False, status=solve_result.status, outcome=outcome,
                wall_time_s=wall, **receipt,
                message="the window could not be re-solved without your move "
                        "inside the budget")
        # CLAUSE (1): a solve the WALL stopped is not reproducible, so it is not a
        # baseline. Refusing to attribute against it is the whole point — the
        # founder's -$50,784.33 was exactly this: a lottery draw in the reference
        # position. The card degrades to the honest unsplit shape.
        if deterministic and det_time_s is not None and solve_result.wall_truncated:
            return BaselineSolve(
                available=False, status=solve_result.status, outcome=outcome,
                wall_time_s=wall, **receipt,
                message="the reference re-solve ran out of wall time before its "
                        "deterministic budget, so its result is not reproducible")

        er = Extractor().extract(
            solve_values=solve_result.solve_values, snapshot_id="sandbox-baseline",
            operations=ops, workpackages=wps, resources=resources,
            fulfillments=fuls, demands=demands, cost_model=cost_model,
            reporter=None, cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible, snapshot_writer=None,
            is_scenario=True, overtime_windows=var_map.overtime_windows,
        )
        ledger = er.cost_ledger or {}
        total = ledger.get("total_cost")
        if total is None:
            return BaselineSolve(
                available=False, status=solve_result.status, outcome=outcome,
                wall_time_s=wall, **receipt,
                message="the baseline re-solve produced no cost ledger")
        # CLAUSE (3): this solve's OWN consequences. It is a search result about
        # the window, not about anybody's gesture, so it carries its own moved-set
        # and its own affected orders and they are never merged with the pin's.
        incumbent_placement = _placements(incumbent_assignments)
        moves = _moved_set(solve_result.solve_values, incumbent_placement,
                           horizon_start, pin_op_id=None)
        affected = _affected_orders(reader, er.service_outcomes)
        return BaselineSolve(
            available=True, total_cost=round(float(total), 2),
            status=solve_result.status, outcome=outcome, wall_time_s=wall,
            moves=moves, affected_orders=affected, **receipt,
            message="baseline proven" if outcome == SANDBOX_VERDICT
                    else "baseline found, bound not proven")
    except Exception as exc:  # noqa: BLE001 — a baseline never takes the card down
        return BaselineSolve(available=False, status="ERROR",
                             message=f"the baseline re-solve failed: {exc}")


# The authored line the card shows when the total could NOT be split. It is not
# an apology — it is the one fact the planner needs to read the number correctly.
UNSPLIT_NOTE = "includes window re-optimization"


def attribute_delta(cost_delta_abs: Optional[float],
                    incumbent_total: Optional[float],
                    baseline: Optional[BaselineSolve]) -> dict:
    """Split a total delta into (window re-optimization, your move) — pure.

    The two parts sum EXACTLY to ``cost_delta_abs``: the re-optimization part is
    measured (baseline − incumbent) and the move part is the REMAINDER, so the
    card can never claim arithmetic that does not close. Any missing input yields
    the honest unsplit shape, never a half-attributed number."""
    # What THIS gesture paid for its attribution: zero on a cache hit, because the
    # baseline was already solved for this incumbent. (The solve's own wall time
    # stays on the BaselineSolve; what the card reports is what the planner waited.)
    wall = 0.0
    if baseline is not None and not baseline.cached:
        wall = round(float(baseline.wall_time_s), 3)
    if cost_delta_abs is None:
        return {"attribution": "unavailable", "reopt_delta_abs": None,
                "move_delta_abs": None, "baseline_total_cost": None,
                "attribution_note": UNSPLIT_NOTE, "baseline_wall_time_s": wall}
    if (baseline is None or not baseline.available
            or baseline.total_cost is None or incumbent_total is None):
        note = (baseline.message if baseline is not None and baseline.message
                else UNSPLIT_NOTE)
        return {"attribution": "unavailable", "reopt_delta_abs": None,
                "move_delta_abs": None,
                "baseline_total_cost": (baseline.total_cost
                                        if baseline is not None else None),
                "attribution_note": note, "baseline_wall_time_s": wall}
    reopt = round(float(baseline.total_cost) - float(incumbent_total), 2)
    move = round(float(cost_delta_abs) - reopt, 2)
    return {"attribution": "split", "reopt_delta_abs": reopt,
            "move_delta_abs": move,
            "baseline_total_cost": round(float(baseline.total_cost), 2),
            "attribution_note": "", "baseline_wall_time_s": wall}


# The dollar threshold below which an "improvement" is rounding, not an offer.
# A search result worth a planner's attention has to be worth more than the cent
# the ledger rounds to.
OPPORTUNITY_MIN_ABS = 0.01


def window_opportunity(baseline: Optional[BaselineSolve],
                       incumbent_total: Optional[float]) -> dict:
    """R-T2 amendment clause (3) — THE WINDOW'S OPPORTUNITY IS ITS OWN THING.

    The baseline re-solve holds no gesture. Whatever it finds that the incumbent
    did not is the SEARCH's discovery about the window, and saying so under the
    heading "your move" is the defect this session exists to end. Pure: it decides
    only whether there is something to say and words it.

    An improvement is a baseline CHEAPER than the incumbent (a negative
    ``reopt``). A baseline DEARER than the incumbent is not an opportunity and is
    not reported as one — it means the search, under its own budget, did not
    re-find the incumbent's quality, which is a fact about the search and says
    nothing a planner can act on."""
    if (baseline is None or not baseline.available
            or baseline.total_cost is None or incumbent_total is None):
        return {}
    delta = round(float(baseline.total_cost) - float(incumbent_total), 2)
    if delta >= -OPPORTUNITY_MIN_ABS:
        return {"found": False, "delta_abs": delta,
                "sentence": "the search found nothing cheaper than the current "
                            "plan for this window"}
    moves = [m for m in (baseline.moves or []) if not m.get("pinned")]
    return {
        "found": True,
        "delta_abs": delta,
        "affected_orders": list(baseline.affected_orders or []),
        "moved_op_count": len(moves),
        "sentence": (f"the search found a schedule ${abs(delta):,.2f} cheaper "
                     f"for this window — {len(moves)} operation(s) would move"),
    }


# --- Session 4B.24, R-T2 amendment clause (5): THE MINIMUM AUDIT -----------
# "Search deeper" is a DELIBERATE act, so it may spend what a gesture may not.
# Measured (Item 1(b), dense demo board): at ONE deterministic unit, seed 42 finds
# nothing better than the incumbent at all; at THREE it finds a schedule 12.4%
# cheaper. The budget is not merely a stopping point for CP-SAT — it schedules its
# own search portfolio around the budget it is given, so a bigger one is a
# different search, not a longer one. 3.0 units is ~100 seconds of real search on
# that board, and it is the smallest budget measured to find anything there.
AUDIT_DET_TIME_S = 3.0
AUDIT_BUDGET_S = 600.0

# --- Session 4B.25, R-BK1: "SEARCH DEEPER" IS A PORTFOLIO -------------------
# This is where the ruling is CHEAPEST to build and most obviously right. The
# audit is already a deliberate act off the gesture path, already deterministic,
# already seeded, and already spends what a drag may not — so running K of them
# and offering the best costs only wall time a planner has already agreed to
# spend, and it harvests the largest quality lever this project has measured
# (4B.24 §7(b): at one deterministic unit on the dense board, three of five
# seeds found nothing and two found 13-16% cheaper schedules).
#
# THE DEFAULT IS 3, NOT 1. Unlike the main solve, the audit has no golden, no
# digest and no pinned world hanging off it: it applies nothing and is invoked
# by a planner asking to look harder. Refusing to look harder in the one place
# whose entire purpose is looking harder would be a strange kind of caution.
AUDIT_K = 3


def audit_incumbent(
    out_dir: Path | str,
    snapshot_id: str,
    *,
    runs_subdir: str = "runs",
    standing_pins: Optional[list[dict]] = None,
    restrict_op_ids: Optional[set] = None,
    det_time_s: Optional[float] = None,
    budget_s: Optional[float] = None,
    seed: Optional[int] = None,
    k: Optional[int] = None,
    portfolio_workers: int = 1,
) -> dict:
    """THE INCUMBENT IS AUDITED, NOT ENSHRINED (clause 5) — the smallest honest
    version of it.

    The incumbent on a dense board is ONE draw from a search that ran out of
    budget, and nothing ever checked whether it was any good. This runs the same
    deterministic, seeded, unpinned window search the baseline uses, at a budget a
    gesture could not afford, and reports what it found.

    It APPLIES NOTHING. An improvement is an OFFER, with its own delta and its own
    affected list, accepted as its own act (clause 4). And when it finds nothing
    it SAYS SO, in units, because "I searched this hard and your plan held" is
    also a thing a planner is owed — silence would leave them unable to tell it
    from a search that never ran.

    SESSION 4B.25 (R-BK1): IT IS A PORTFOLIO. ``k`` members run at consecutive
    seeds ``seed .. seed+k-1``, each a full deterministic search; the best by
    LEDGER is offered and EVERY member's total is published beside it. The
    offer's own sentence carries the spread, because five searches agreeing and
    five scattering are different facts about the board and a planner acting on
    the offer needs both."""
    from mre.modules import portfolio as pf

    det = AUDIT_DET_TIME_S if det_time_s is None else det_time_s
    wall = AUDIT_BUDGET_S if budget_s is None else budget_s
    sd = SANDBOX_SEED if seed is None else seed
    kk = AUDIT_K if k is None else int(k)
    if kk < 1:
        raise ValueError(f"a portfolio needs at least one member, got k={kk}")
    t0 = time.monotonic()
    seeds = pf.seeds_for(kk, sd)

    # Sequential by default (clause 5's worker token is the parallel path, and a
    # laptop running five window solves at once measures its own thermals). The
    # member's own BaselineSolve is retained only on the sequential path — under
    # a process pool it lives and dies in its own process — so the winner is
    # re-run here when it is missing, which determinism makes free of
    # consequence (the same argument `materialize_audit_offer` already rests on).
    runner = _AuditMember({
        "out_dir": str(out_dir), "snapshot_id": snapshot_id,
        "budget_s": wall, "runs_subdir": runs_subdir,
        "standing_pins": standing_pins, "restrict_op_ids": restrict_op_ids,
        "det_time_s": det})
    members = pf.run_members(runner, seeds, workers=portfolio_workers)
    solves = runner.solves
    book = pf.build(kk, sd, det, members, workers=portfolio_workers,
                    wall_time_s=time.monotonic() - t0,
                    k_declared=k is not None,
                    det_time_declared=det_time_s is not None)
    winner = book.winner

    incumbent_total = _incumbent_total(Path(out_dir), snapshot_id)
    out = {
        "searched": True,
        "det_time_s": det,
        "seed": sd,
        "wall_time_s": round(time.monotonic() - t0, 3),
        "incumbent_total": incumbent_total,
        "portfolio": book.block(),
        "opportunity": {},
        "offer": None,
        "sentence": "",
    }
    if winner is None:
        # No member is publishable. NOT an offer and NOT "the incumbent held" —
        # we did not get an answer, and saying "nothing cheaper" here would
        # report our failure as their plan's strength.
        first = next((m for m in members if m.reason), None)
        out["searched"] = False
        out["det_consumed"] = None
        out["status"] = (members[0].status if members else "")
        out["wall_truncated"] = any(m.wall_truncated for m in members)
        out["sentence"] = (
            f"I could not complete a deeper search of this window ({kk} seeded "
            f"attempt(s), none usable), so I have nothing to say about whether "
            f"the plan can be improved"
            + (f" — {first.reason}" if first is not None else ""))
        return out

    base = solves.get(winner.seed)
    if base is None:
        base = baseline_window_solve(
            out_dir, snapshot_id, budget_s=wall, runs_subdir=runs_subdir,
            deterministic=True, standing_pins=standing_pins,
            restrict_op_ids=restrict_op_ids, det_time_s=det, seed=winner.seed,
            use_cache=False)
    opp = window_opportunity(base, incumbent_total)
    out.update({"det_consumed": base.det_consumed, "status": base.status,
                "wall_truncated": base.wall_truncated,
                "winning_seed": winner.seed, "opportunity": opp})
    spread = book.agreement_sentence()
    if opp.get("found"):
        out["offer"] = {
            "delta_abs": opp["delta_abs"],
            "affected_orders": opp.get("affected_orders", []),
            "moved_op_count": opp.get("moved_op_count", 0),
            "moves": list(base.moves or []),
            "seed": winner.seed,
        }
        out["sentence"] = (
            f"the search found a schedule ${abs(opp['delta_abs']):,.2f} cheaper"
            + (f" ({book.declaration()}; {spread})" if spread else "")
            + " — review?")
        return out
    spent = base.det_consumed if base.det_consumed is not None else det
    out["sentence"] = (
        f"searched {spent:.2f} more deterministic units"
        + (f" x {kk} seeds" if kk > 1 else "")
        + "; the incumbent held"
        + (f" — {spread}" if spread else ""))
    return out


class _AuditMember:
    """ONE AUDIT PORTFOLIO MEMBER — a picklable ``seed -> PortfolioMember``.

    Module-level and plain-data-in, so clause (5)'s process pool can carry it
    (a closure cannot survive a pickle, and on Windows the pool spawns). Its
    ``solves`` cache is populated in whichever process runs the member, which is
    the parent on the sequential path and a worker on the parallel one — the
    caller reads it opportunistically and re-solves the winner when it is not
    there.
    """

    __slots__ = ("spec", "solves")

    def __init__(self, spec: dict):
        self.spec = spec
        self.solves: dict = {}

    def __call__(self, seed: int):
        from mre.modules import portfolio as pf

        s = self.spec
        b = baseline_window_solve(
            Path(s["out_dir"]), s["snapshot_id"], budget_s=s["budget_s"],
            runs_subdir=s["runs_subdir"], deterministic=True,
            standing_pins=s["standing_pins"],
            restrict_op_ids=s["restrict_op_ids"], det_time_s=s["det_time_s"],
            seed=seed, use_cache=False)
        self.solves[seed] = b
        if b.wall_truncated:
            # CLAUSE (1). `baseline_window_solve` already refuses to publish a
            # wall-stopped result; this states the same refusal in the
            # portfolio's own vocabulary, so the member is VISIBLE rather than
            # missing and the spread cannot look tighter than the evidence.
            return pf.unusable(seed, pf.WALL_STOPPED_REASON, status=b.status,
                               wall_truncated=True, det_consumed=b.det_consumed,
                               wall_time_s=b.wall_time_s)
        if not b.available or b.total_cost is None:
            return pf.unusable(seed, b.message or "no ledger", status=b.status,
                               det_consumed=b.det_consumed,
                               wall_time_s=b.wall_time_s)
        return pf.PortfolioMember(
            seed=seed, ledger_total=round(float(b.total_cost), 2),
            status=b.status, det_consumed=b.det_consumed,
            wall_time_s=b.wall_time_s)


def materialize_audit_offer(
    out_dir: Path | str,
    base_snapshot_id: str,
    *,
    authority: str,
    runs_subdir: str = "runs",
    base_runs_dir: Optional[Path] = None,
    reference_date_raw: Optional[str] = None,
    standing_pins: Optional[list[dict]] = None,
    restrict_op_ids: Optional[set] = None,
    det_time_s: Optional[float] = None,
    budget_s: Optional[float] = None,
    seed: Optional[int] = None,
    expect_delta_abs: Optional[float] = None,
) -> dict:
    """THE SECOND CEREMONY (clause 4) — accept the WINDOW'S improvement.

    Accepting the planner's move commits the move. This commits something else
    entirely: a schedule the SEARCH found, touching work the planner never
    gestured at. One click must never do both, so this is its own function behind
    its own endpoint, and it records its own Decision naming its own authority.

    It is safe to re-run the search rather than carry the earlier one's placements
    across a request boundary precisely BECAUSE of clause (1): same model, same
    seed, same deterministic budget, same answer. That is what determinism buys
    beyond honesty — a result that can be recomputed instead of cached.

    SESSION 4B.25: the audit is a PORTFOLIO, so ``seed`` must be the WINNING
    member's seed and not the portfolio's ``seed0`` — accepting an offer found
    by seed 44 while re-solving at seed 42 would mint a schedule that is not the
    one on the card. The offer carries its seed; the accept passes it back.

    ``expect_delta_abs`` is that promise made checkable. When given, the minted
    child's own delta must equal it TO THE CENT or nothing is accepted. This is
    the whole point of clause (1) stated as an assertion rather than a hope: if
    determinism holds, the promise on the card and the schedule that lands are
    the same object, and if it does not, the planner must not be handed the
    difference silently (the 4B.24 lesson on ``hold_all_placements``, one
    ceremony over).

    ``out_dir`` must be a fresh run directory whose ``snapshots/`` already holds a
    copy of the base snapshot (the caller mints it, exactly as accept does).
    Returns ``{child_snapshot_id, total_cost, delta_abs, moved_count,
    decision_record_id}``. Raises when the search finds nothing to accept — an
    empty offer is not a version."""
    from mre.contracts.entities import EntityRef
    from mre.contracts.vocabularies import (
        DecisionBasis, DecisionType, DriverCode, ModuleCode, RecordTier, RunStatus,
    )
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.extractor import Extractor
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter

    if not authority:
        raise ValueError("accepting a search result requires an authority")
    det = AUDIT_DET_TIME_S if det_time_s is None else det_time_s
    wall = wall_ceiling_for(AUDIT_BUDGET_S if budget_s is None else budget_s,
                            det, True)
    sd = SANDBOX_SEED if seed is None else seed

    out_dir = Path(out_dir)
    store = SnapshotStore(out_dir / "snapshots")
    runs_dir = out_dir / runs_subdir
    runs_dir.mkdir(parents=True, exist_ok=True)
    child_snap_id = f"{base_snapshot_id}-audit-{sd}-{det:g}".replace(".", "")
    from mre.modules.planner_edit import _EDIT_COPY_TYPES
    store.derive_scenario_snapshot(base_snapshot_id, child_snap_id, _EDIT_COPY_TYPES)

    reader = store.load_snapshot(base_snapshot_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}
    ops, wps, fuls, demands = _restrict_window(
        ops, wps, fuls, demands, restrict_op_ids)

    evidence = _read_evidence(base_runs_dir or (out_dir / runs_subdir))
    horizon_start, horizon_end = _m5_horizon(evidence)
    reference_date = _parse_ref_date(reference_date_raw)
    flattened = flatten_all_calendars(calendars, horizon_start, horizon_end)
    incumbent_placement = _placements(incumbent_assignments)

    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="audit offer model build",
        config={"audit": True, "seed": sd, "deterministic_time": det},
        trigger="audit_accept", snapshot_id=child_snap_id, sink_dir=runs_dir)
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened,
        fuls + demands, constraints, cost_model)
    b_rep.end(RunStatus.SUCCESS)

    apply_solution_hints(model, var_map, incumbent_assignments)
    sp.apply_standing_pins(model, var_map, standing_pins, horizon_start)

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="audit offer re-solve",
        config={"time_limit": wall, "num_search_workers": 1,
                "random_seed": sd, "deterministic_time": det, "audit": True},
        trigger="audit_accept", snapshot_id=child_snap_id, sink_dir=runs_dir)
    solve_result = SolveRunner(
        time_limit_seconds=wall, num_search_workers=1, random_seed=sd,
        deterministic_time=det).solve(model, var_map, r_rep)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)
    if not feasible:
        raise RuntimeError(
            f"the deeper search returned {solve_result.status} — nothing "
            "accepted; the incumbent stands")
    if solve_result.wall_truncated:
        raise RuntimeError(
            "the deeper search was stopped by the wall, not its deterministic "
            "budget, so its result is not reproducible — nothing accepted")

    e_rep = Reporter.begin(
        module=ModuleCode.M7, purpose="audit offer extraction", config={},
        trigger="audit_accept", snapshot_id=child_snap_id, sink_dir=runs_dir)
    writer = store.extend_snapshot(child_snap_id)
    extract = Extractor().extract(
        solve_values=solve_result.solve_values, snapshot_id=child_snap_id,
        operations=ops, workpackages=wps, resources=resources,
        fulfillments=fuls, demands=demands, cost_model=cost_model,
        reporter=e_rep, cal_windows=var_map.cal_windows,
        op_eligible=var_map.op_eligible, snapshot_writer=writer,
        is_scenario=False, overtime_windows=var_map.overtime_windows)
    writer.finalize()
    e_rep.end(RunStatus.SUCCESS)

    total = float((extract.cost_ledger or {}).get("total_cost", 0.0))
    incumbent_total = _incumbent_total_from(reader)
    delta = (None if incumbent_total is None
             else round(total - incumbent_total, 2))
    if delta is not None and delta >= -OPPORTUNITY_MIN_ABS:
        raise RuntimeError(
            "the deeper search did not beat the incumbent on this run — "
            "nothing accepted")
    # THE PROMISE, CHECKED (4B.25 Item 4a). To the cent, because the ledger
    # rounds to the cent and determinism means there is no other tolerance to
    # argue for.
    if expect_delta_abs is not None and delta is not None:
        if abs(delta - float(expect_delta_abs)) > 0.005:
            raise RuntimeError(
                f"the accepted search re-solved to ${delta:,.2f} against an "
                f"offer of ${float(expect_delta_abs):,.2f} — the schedule on "
                "the card is not the schedule this would commit; nothing "
                "accepted")
    moves = _moved_set(solve_result.solve_values, incumbent_placement,
                       horizon_start, pin_op_id=None)

    d_rep = Reporter.begin(
        module=ModuleCode.M4, purpose="audit offer accepted",
        config={"authority": authority, "seed": sd, "deterministic_time": det},
        trigger="audit_accept", snapshot_id=child_snap_id, sink_dir=runs_dir)
    decision = d_rep.record_decision(
        decision_type=DecisionType.PLANNER_EDIT,
        basis=DecisionBasis.OBSERVED,
        # 4B.25 Item 4a: this said `COST_MINIMIZATION`, which is not a member of
        # the vocabulary and never has been — the accept's SUCCESS branch had
        # never executed, so an AttributeError sat behind a button. COST_TRADEOFF
        # is the ruled code for a placement chosen on price (docs/02 §4.2;
        # `add, never repurpose` — no vocabulary change here, a correction to a
        # name that was never in it).
        driver=DriverCode.COST_TRADEOFF,
        chosen={"audit": True, "seed": sd, "deterministic_time": det,
                "total_cost": round(total, 2), "delta_abs": delta,
                "moved_count": len(moves)},
        alternatives=[],
        subjects=[EntityRef(entity_id=child_snap_id, entity_type="schedule")],
        authority=authority,
        message=(f"Accepted a deeper-search schedule ${abs(delta):,.2f} cheaper "
                 f"than the incumbent; {len(moves)} operations move."),
        tier=RecordTier.HEADLINE,
    )
    d_rep.end(RunStatus.SUCCESS)
    return {"child_snapshot_id": child_snap_id, "total_cost": round(total, 2),
            "delta_abs": delta, "moved_count": len(moves),
            "decision_record_id": getattr(decision, "record_id", None)
            or (decision.get("record_id") if isinstance(decision, dict) else None)}


def _incumbent_total_from(reader) -> Optional[float]:
    try:
        schedules = list(reader.iter_entities("schedule"))
        if not schedules:
            return None
        return round(float((schedules[-1].get("summary_metrics") or {})
                           .get("total_cost", 0.0)), 2)
    except Exception:  # noqa: BLE001
        return None


def _incumbent_total(out_dir: Path, snapshot_id: str) -> Optional[float]:
    """The incumbent's own persisted ledger total — the figure any improvement is
    measured against."""
    from mre.modules.snapshot_store import SnapshotStore
    try:
        reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
        schedules = list(reader.iter_entities("schedule"))
        if not schedules:
            return None
        return round(float((schedules[-1].get("summary_metrics") or {})
                           .get("total_cost", 0.0)), 2)
    except Exception:  # noqa: BLE001
        return None


def local_attribution(delta: Optional[float]) -> dict:
    """The attribution shape for a LOCALLY priced move (clause 2).

    There is nothing to split. The re-solve's fused total is what needed
    splitting, and this number was never fused: everything else was held, so the
    window re-optimization component is not "measured as zero" — it is ABSENT BY
    CONSTRUCTION. The fields still sum exactly, so every downstream arithmetic
    check holds, and ``attribution`` says ``local`` so no surface renders a
    "window re-optimization $0.00" line implying we looked."""
    return {"attribution": "local", "reopt_delta_abs": 0.0,
            "move_delta_abs": delta, "baseline_total_cost": None,
            "attribution_note": "", "baseline_wall_time_s": 0.0}


def price_drop(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    *,
    runs_subdir: str = "runs",
    restrict_op_ids: Optional[set] = None,
    standing_pins: Optional[list[dict]] = None,
    budget_s: float = SANDBOX_BUDGET_S,
    deterministic: bool = True,
    det_time_s: Optional[float] = SANDBOX_DET_TIME_S,
    seed: int = SANDBOX_SEED,
    opportunity: bool = False,
    validate: bool = True,
) -> SandboxResult:
    """BEAT TWO, under the R-T2 amendment: price the planner's move LOCALLY.

    This is what ``POST /sandbox`` calls. It replaces the whole-window re-solve
    on the gesture path with :func:`mre.modules.local_price.price_local_move` —
    clause (2). The card's money is now the move's own ledger delta, computed
    with every other placement held exactly where the planner can see it, and
    validated against a fresh model. It is exact, it is deterministic, and it
    takes about a second and a half on a 386-bar board where the re-solve took
    sixty-four.

    ``opportunity`` (clause 3) additionally runs the deterministic UNPINNED
    window search and, where it beats the incumbent, reports that as its own
    labelled section with its own affected list. It is OFF by default on the
    gesture path: the search costs orders of magnitude more than the price, and
    an improvement the planner did not ask for must not be the reason their drag
    took a minute. The "search deeper" action is what turns it on.

    :func:`sandbox_pin_resolve` — the re-solve — is unchanged and still reachable;
    it is now deterministic (clause 1) and is what the accept path and the
    opportunity search are built from."""
    from mre.modules.local_price import price_local_move

    lp = price_local_move(
        out_dir, snapshot_id, pin_op_id=pin_op_id,
        pin_resource_id=pin_resource_id, pin_start_iso=pin_start_iso,
        runs_subdir=runs_subdir, restrict_op_ids=restrict_op_ids,
        standing_pins=standing_pins, validate=validate)
    # The pricer RESOLVES an omitted pin (the latency floor: the first incumbent
    # op at its own placement), so the correlation id is derived from what was
    # actually priced. Deriving it from the request would give beat one and beat
    # two different ids for the same defaulted gesture.
    pin = dict(lp.pin)
    corr = correlation_id_for(snapshot_id, pin.get("operation_ref"),
                              pin.get("resource_id"), pin.get("start"))

    common = dict(
        within_budget=True, wall_time_s=lp.wall_time_s, budget_s=budget_s,
        applied_time_limit_s=budget_s, pin=pin, correlation_id=corr,
        pricing_mode="local", validation=lp.validation,
        det_time_s=None, det_consumed=None, wall_truncated=False)

    if lp.error:
        # OURS, not the plant's. No verdict, and the sentence says whose fault.
        return SandboxResult(
            outcome=SANDBOX_NO_VERDICT, status="UNKNOWN", feasible=False,
            message=lp.error, **common, **attribute_delta(None, None, None))

    if lp.refusal:
        # A PROVEN refusal about the world as it stands. ``holds_others`` decides
        # between "no" and "not without moving other work" — and the second must
        # never be spoken as the first (see LocalRefusal).
        r = lp.refusal
        tail = (" — and this price holds every other job exactly where it is, so "
                "the scheduler might still fit it here by moving other work"
                if r.get("holds_others") else "")
        return SandboxResult(
            outcome=SANDBOX_VERDICT, status="INFEASIBLE", feasible=False,
            message=r.get("sentence", "this placement isn't possible") + tail,
            refusal=r, **common, **attribute_delta(None, None, None))

    opp: dict = {}
    if opportunity:
        base = baseline_window_solve(
            out_dir, snapshot_id, budget_s=budget_s, runs_subdir=runs_subdir,
            deterministic=deterministic, standing_pins=standing_pins,
            restrict_op_ids=restrict_op_ids, det_time_s=det_time_s, seed=seed)
        opp = window_opportunity(base, lp.total_before)

    return SandboxResult(
        outcome=SANDBOX_VERDICT, status=(lp.validation or {}).get("status")
                                        or "OPTIMAL",
        feasible=True, objective=None, delta_pct=None, delta_abs=None,
        cost_delta_abs=lp.cost_delta_abs, cost_delta_pct=lp.cost_delta_pct,
        message="priced exactly — nothing else moved",
        moves=list(lp.moves), dominant_driver={},
        affected_orders=list(lp.affected_orders),
        lateness_delta_min=lp.lateness_delta_min,
        no_committed_work_changes=True, cost_lines=lp.cost_lines,
        opportunity=opp, **common, **local_attribution(lp.cost_delta_abs))


def feasibility_ghost(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    budget_s: float = FEASIBILITY_BUDGET_S,
    det_time_s: float = FEASIBILITY_DET_TIME_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    restrict_op_ids: Optional[set] = None,
    seed: int = SANDBOX_SEED,
) -> FeasibilityGhost:
    """BEAT ONE (R-T2): a first-feasible feasibility verdict + placement for a
    dropped bar, under a SMALL deterministic budget, carrying NO monetary
    quantity (R-T2(1)).

    It is a RELAXATION of the full budgeted solve (:func:`sandbox_pin_resolve`,
    beat two): it pins ONLY the dragged op and does NOT hold the lineage's
    committed/standing work, so the fast "can it go here at all" answer is cheap.
    Beat two, which DOES hold every commitment and runs to a proof, may therefore
    legitimately contradict beat one (R-T2(4)).

    Mints NOTHING and touches NO persistent state (R-T2(5)) — no reporter
    Decisions, no snapshot writes; the evidence Reporter records are read-only
    telemetry under the sandbox run dir, exactly as the priced re-solve's are."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter

    out_dir = Path(out_dir)
    sandbox_dir = out_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    # CU3: on a rolling schedule, restrict the build to the ACTIVE WINDOW's ops so
    # beat one re-solves the window (not the whole plant), aligned with the
    # persisted window-0 incumbent.
    ops, wps, fuls, demands = _restrict_window(ops, wps, fuls, demands, restrict_op_ids)

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    if pin_op_id is None:
        pin_op_id = next(iter(incumbent_placement), None)
        if pin_op_id is None:
            raise ValueError("no incumbent placements to pin")
    inc_res, inc_start = incumbent_placement.get(pin_op_id, (None, None))
    if pin_resource_id is None:
        pin_resource_id = inc_res
    pin_start_dt = (_parse_dt(pin_start_iso) if pin_start_iso else inc_start)
    if pin_start_dt is None or pin_resource_id is None:
        raise ValueError(f"cannot resolve a pin for op {pin_op_id}")
    pin_start_min = int((pin_start_dt - horizon_start).total_seconds() // 60)
    corr = correlation_id_for(snapshot_id, pin_op_id, pin_resource_id,
                              pin_start_dt.isoformat())

    workers = 1 if deterministic else ctx.get("solver_workers")
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="feasibility ghost model build",
        config={"pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min, "beat": "one"},
        trigger="sandbox_feasibility", snapshot_id=snapshot_id,
        sink_dir=sandbox_dir / "runs",
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    apply_solution_hints(model, var_map, incumbent_assignments)
    # RELAXATION: pin ONLY the dragged op — NOT the lineage's standing/committed
    # work. This is exactly what lets beat two (which holds them) contradict beat
    # one (R-T2(4)); it also keeps beat one cheap.
    try:
        sp.apply_pin(model, var_map, pin_op_id, pin_resource_id, pin_start_min)
    except sp.PinUnsatisfiable as exc:
        return FeasibilityGhost(
            correlation_id=corr, feasible=False, within_budget=True,
            wall_time_s=0.0, budget_s=budget_s, status="INFEASIBLE",
            verdict=FEASIBILITY_IMPOSSIBLE,
            message=f"this placement isn't possible: {exc.reason}",
            placement=[],
            pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
                 "start": pin_start_dt.isoformat()},
        )

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="feasibility ghost solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "stop_after_first_solution": True, "beat": "one"},
        trigger="sandbox_feasibility", snapshot_id=snapshot_id,
        sink_dir=sandbox_dir / "runs",
    )
    t0 = time.monotonic()
    solve_result = SolveRunner(
        time_limit_seconds=budget_s, num_search_workers=workers,
        random_seed=seed if deterministic else None,
        deterministic_time=det_time_s if deterministic else None,
        stop_after_first_solution=True,
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    verdict = classify_feasibility(solve_result.status)
    r_rep.end(RunStatus.SUCCESS if feasible else RunStatus.PARTIAL)

    placement: list[dict] = []
    if feasible:
        placement = _placement_list(solve_result.solve_values,
                                    incumbent_placement, horizon_start, pin_op_id)
    return FeasibilityGhost(
        correlation_id=corr, feasible=feasible,
        within_budget=wall <= budget_s + _BUDGET_STOP_MARGIN_S,
        wall_time_s=wall, budget_s=budget_s, status=solve_result.status,
        verdict=verdict,
        message=feasibility_message(verdict, budget_s,
                                    bool(solve_result.wall_truncated)),
        placement=placement,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
        det_time_s=det_time_s if deterministic else None,
        det_consumed=solve_result.det_consumed,
        wall_truncated=bool(solve_result.wall_truncated),
    )


def _placement_list(solve_values, incumbent_placement, horizon_start,
                    pin_op_id) -> list[dict]:
    """The pinned op's placement + any op the (relaxed, first-feasible) solve
    moved, positions ONLY (resource + start/end). Beat one's ghost — NO cost."""
    out: list[dict] = []

    def _pl(op_id):
        rid = solve_values.op_resource.get(op_id)
        smin = solve_values.op_start_minutes.get(op_id)
        emin = solve_values.op_end_minutes.get(op_id)
        if rid is None or smin is None:
            return None
        s = horizon_start + timedelta(minutes=smin)
        e = horizon_start + timedelta(minutes=emin if emin is not None else smin)
        return rid, s, e

    pin_pl = _pl(pin_op_id)
    if pin_pl:
        out.append({"operation_ref": pin_op_id, "resource_id": pin_pl[0],
                    "start": pin_pl[1].isoformat(), "end": pin_pl[2].isoformat(),
                    "pinned": True})
    for op_id, (old_rid, old_start) in incumbent_placement.items():
        if op_id == pin_op_id:
            continue
        pl = _pl(op_id)
        if pl is None:
            continue
        new_rid, new_start, new_end = pl
        moved = new_rid != old_rid or abs(
            round((new_start - old_start).total_seconds() / 60.0)) >= 1
        if not moved:
            continue
        out.append({"operation_ref": op_id, "resource_id": new_rid,
                    "start": new_start.isoformat(), "end": new_end.isoformat(),
                    "pinned": False})
    return out


def sandbox_pin_resolve(
    out_dir: Path | str,
    snapshot_id: str,
    pin_op_id: Optional[str] = None,
    pin_resource_id: Optional[str] = None,
    pin_start_iso: Optional[str] = None,
    budget_s: float = SANDBOX_BUDGET_S,
    runs_subdir: str = "runs",
    deterministic: bool = True,
    standing_pins: Optional[list[dict]] = None,
    restrict_op_ids: Optional[set] = None,
    baseline: bool = True,
    det_time_s: Optional[float] = SANDBOX_DET_TIME_S,
    seed: int = SANDBOX_SEED,
) -> SandboxResult:
    """Re-solve with one op pinned to (machine + time), the rest free, under a
    hard `budget_s`. Returns a classified :class:`SandboxResult`.

    Defaults (no pin args) pin the FIRST incumbent op at its own placement —
    the latency FLOOR (a trivially feasible re-solve the solver must confirm
    within budget); the CI regression uses this. A caller may pin any op at any
    (resource, start) to price a real drag (R-DP1 literalness).

    ``standing_pins`` are the lineage's ACCEPTED commitments (R-DP8): every one is
    compiled as a hard constraint alongside the new drop, so the re-solve can
    never silently relocate a placement the planner already committed. A drop that
    is infeasible against a standing pin returns an honest INFEASIBLE verdict that
    NAMES the blocking commitment — never a quiet sacrifice of the older pin.

    ``baseline`` (CU1, Session 4B.5) buys the card's ATTRIBUTION: the same window
    is also re-solved WITHOUT this pin, and the verdict splits into the window
    re-optimization the planner did not cause and the cost their move actually
    added. The baseline is cached per incumbent, so only the first gesture on a
    board pays for it. Set it False to price a move without attributing it (the
    latency-floor regression, the accept path, a caller that has no use for the
    split) — the result then carries ``attribution="unavailable"``.
    """
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solve_runner import SolveRunner
    from mre.modules.solver_builder import SolverBuilder, apply_solution_hints
    from mre.modules.solution_pool import (
        _incumbent_objective, _m5_horizon, _placements, _read_evidence,
    )
    from mre.modules import standing_pins as sp
    from mre.reporter import Reporter

    out_dir = Path(out_dir)
    sandbox_dir = out_dir / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    reader = SnapshotStore(out_dir / "snapshots").load_snapshot(snapshot_id)
    demands = list(reader.iter_entities("demand"))
    fuls = list(reader.iter_entities("fulfillment"))
    wps = list(reader.iter_entities("workpackage"))
    ops = list(reader.iter_entities("operation"))
    edges = list(reader.iter_entities("precedenceedge"))
    resources = list(reader.iter_entities("resource"))
    pools = list(reader.iter_entities("resourcepool"))
    calendars = list(reader.iter_entities("calendar"))
    constraints = list(reader.iter_entities("constraint"))
    costmodels = list(reader.iter_entities("costmodel"))
    incumbent_assignments = list(reader.iter_entities("assignment"))
    cost_model = costmodels[0] if costmodels else {}

    # CU3: on a rolling schedule, restrict the build to the ACTIVE WINDOW's ops.
    # Beat two ALSO holds the committed frozen front (passed as ``standing_pins``),
    # so it can legitimately contradict beat one (which relaxed them) — the R-T2
    # contradiction, now on a real rolling substrate.
    ops, wps, fuls, demands = _restrict_window(ops, wps, fuls, demands, restrict_op_ids)

    evidence = _read_evidence(out_dir / runs_subdir)
    ctx = derive_base_context(out_dir / runs_subdir)
    reference_date = _parse_ref_date(ctx.get("reference_date"))
    horizon_start, horizon_end = _m5_horizon(evidence)
    incumbent_objective = _incumbent_objective(evidence)
    incumbent_placement = _placements(incumbent_assignments)
    flattened_cals = flatten_all_calendars(calendars, horizon_start, horizon_end)

    # Resolve the pin: default to the first incumbent op at its own placement.
    if pin_op_id is None:
        pin_op_id = next(iter(incumbent_placement), None)
        if pin_op_id is None:
            raise ValueError("no incumbent placements to pin")
    inc_res, inc_start = incumbent_placement.get(pin_op_id, (None, None))
    if pin_resource_id is None:
        pin_resource_id = inc_res
    pin_start_dt = (_parse_dt(pin_start_iso) if pin_start_iso else inc_start)
    if pin_start_dt is None or pin_resource_id is None:
        raise ValueError(f"cannot resolve a pin for op {pin_op_id}")
    pin_start_min = int((pin_start_dt - horizon_start).total_seconds() // 60)
    # R-T2: the correlation id linking this priced beat two to its beat one.
    corr = correlation_id_for(snapshot_id, pin_op_id, pin_resource_id,
                              pin_start_dt.isoformat())

    workers = 1 if deterministic else ctx.get("solver_workers")
    b_rep = Reporter.begin(
        module=ModuleCode.M5, purpose="sandbox pin re-solve model build",
        config={"horizon_start": horizon_start.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "pin_op": pin_op_id, "pin_resource": pin_resource_id,
                "pin_start_min": pin_start_min},
        trigger="sandbox", snapshot_id=snapshot_id, sink_dir=sandbox_dir / "runs",
    )
    model, var_map = SolverBuilder(reference_date=reference_date).build(
        wps + ops + edges, resources + pools, flattened_cals,
        fuls + demands, constraints, cost_model,
    )
    b_rep.end(RunStatus.SUCCESS)

    # warm-start from the incumbent, then pin the target (machine + time), R-DP1.
    apply_solution_hints(model, var_map, incumbent_assignments)
    # R-DP1 (4.0 hotfix): the machine pin binds ONLY when the op is eligible on
    # the target (a literal exists in ``op_assign``). The prior
    # ``if lit is not None: model.add(lit == 1)`` SILENTLY SKIPPED the machine
    # constraint otherwise, so the re-solve kept the op on its cheaper incumbent
    # machine and STILL reported a feasible verdict — a false "OK" for a placement
    # never actually tested (right time, wrong machine). An un-pinnable target is
    # a PROVEN-ILLEGAL placement (R-DP2 return-home), not a happy verdict, so
    # short-circuit to an infeasible verdict before spending the solve budget.
    try:
        sp.apply_pin(model, var_map, pin_op_id, pin_resource_id, pin_start_min)
    except sp.PinUnsatisfiable as exc:
        return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                  pin_start_dt, exc.reason, corr)
    # R-DP8: compile the lineage's ACCEPTED pins as hard constraints too, so the
    # re-solve holds every prior commitment fixed (skip the op being dragged — the
    # new drop re-commits it). A standing pin that cannot bind is a genuine lineage
    # inconsistency → honest infeasible, never a silent skip.
    new_pin = {"operation_ref": pin_op_id, "resource_id": pin_resource_id,
               "start": pin_start_dt.isoformat()}
    try:
        sp.apply_standing_pins(model, var_map, standing_pins, horizon_start,
                               skip_op=pin_op_id)
    except sp.PinUnsatisfiable as exc:
        return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                  pin_start_dt,
                                  f"a standing commitment could not be held: {exc.reason}",
                                  corr)
    standing_ops = sp.standing_pin_ops(standing_pins)

    r_rep = Reporter.begin(
        module=ModuleCode.M6, purpose="sandbox pin re-solve",
        config={"time_limit": budget_s, "num_search_workers": workers,
                "random_seed": seed if deterministic else None,
                "deterministic_time": det_time_s if deterministic else None,
                "pin_op": pin_op_id},
        trigger="sandbox", snapshot_id=snapshot_id, sink_dir=sandbox_dir / "runs",
    )
    t0 = time.monotonic()
    wall_limit = wall_ceiling_for(budget_s, det_time_s, deterministic)
    solve_result = SolveRunner(
        time_limit_seconds=wall_limit, num_search_workers=workers,
        random_seed=seed if deterministic else None,
        deterministic_time=det_time_s if deterministic else None,
    ).solve(model, var_map, r_rep)
    wall = round(time.monotonic() - t0, 3)
    r_rep.end(RunStatus.SUCCESS
              if solve_result.status in ("OPTIMAL", "FEASIBLE")
              else RunStatus.PARTIAL)

    outcome = classify_sandbox_outcome(solve_result.status, wall, budget_s)
    feasible = solve_result.status in ("OPTIMAL", "FEASIBLE")
    receipt = {"det_time_s": det_time_s if deterministic else None,
               "det_consumed": solve_result.det_consumed,
               "wall_truncated": bool(solve_result.wall_truncated)}
    # CLAUSE (1) — A WALL-TRUNCATED SANDBOX SOLVE REFUSES TO PRICE. The wall is a
    # SAFETY CEILING; when it, rather than the deterministic budget, is what
    # stopped the search, the answer is whatever this machine happened to reach in
    # N seconds and the identical gesture would return something else. Pricing
    # from it is what produced -$50,784.33 for a four-hour nudge into empty time.
    # This is a statement about OUR process — the same register as beat one's
    # `undetermined` — so it is a no_verdict, never a claim about the plant.
    if deterministic and det_time_s is not None and solve_result.wall_truncated:
        return SandboxResult(
            outcome=SANDBOX_NO_VERDICT, status=solve_result.status,
            within_budget=False, wall_time_s=wall, budget_s=budget_s,
            applied_time_limit_s=wall_limit, feasible=False,
            message="I ran out of wall time before finishing this price — the "
                    f"{wall_limit:g}s ceiling stopped it, not the plant. Pricing "
                    "from where it happened to stop would not be reproducible.",
            pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
                 "start": pin_start_dt.isoformat()},
            correlation_id=corr, **receipt, **attribute_delta(None, None, None),
        )
    # R-DP8: an INFEASIBLE drop may be blocked by a standing commitment. If a
    # standing pin directly overlaps the drop on its resource, say WHICH decision
    # blocks it (an authored reason), rather than a bare "pin infeasible" — the
    # planner must never be left guessing why their move was refused, nor have an
    # older commitment quietly sacrificed to make room.
    if not feasible and standing_pins:
        conflict = sp.detect_conflict(new_pin, standing_pins, var_map, horizon_start)
        if conflict is not None:
            return _pin_conflict(budget_s, pin_op_id, pin_resource_id,
                                 pin_start_dt, conflict, corr)
    # R-DP1 post-condition (4.0 hotfix): with the machine + time pins now
    # mandatory, a feasible solve MUST place the pinned op exactly where pinned.
    # Belt-and-suspenders against any residual model looseness — if it did not,
    # the verdict would be honest-looking but for the wrong placement, so treat it
    # as unsatisfiable rather than report a delta the drop never earned.
    if feasible:
        solved_res = solve_result.solve_values.op_resource.get(pin_op_id)
        solved_start = solve_result.solve_values.op_start_minutes.get(pin_op_id)
        if solved_res != pin_resource_id or solved_start != pin_start_min:
            return _pin_unsatisfiable(budget_s, pin_op_id, pin_resource_id,
                                      pin_start_dt, "pin did not bind to the target",
                                      corr)
    delta_pct = delta_abs = None
    if feasible and incumbent_objective and solve_result.objective is not None:
        delta_abs = round(solve_result.objective - incumbent_objective, 4)
        if incumbent_objective > 0:
            delta_pct = round(delta_abs / incumbent_objective * 100.0, 4)

    # The moved-set (R-DP7): old → new placement for every displaced op. Read
    # the new placement from the solve values, the old from the incumbent; a
    # move is a resource change or a start shift ≥ 1 min (the differ tolerance).
    moves: list[dict] = []
    if feasible:
        moves = _moved_set(
            solve_result.solve_values, incumbent_placement, horizon_start,
            pin_op_id, exclude_ops=standing_ops,
        )
        _annotate_move_reasons(moves, solve_result.solve_values, horizon_start,
                               pin_op_id)

    # The R-T2 beat-two LAYERED card (CU2). One in-memory extract of the re-solve
    # gives the new ledger + per-order service outcomes + drivers; diffed against
    # the base (its persisted summary + service outcomes) yields the always-visible
    # + detail layers, all ledger-backed. Fully guarded → empty/None on any
    # failure so the card degrades to the relative-% headline, never a false figure.
    cost_delta_abs = cost_delta_pct = None
    cost_lines = None
    affected_orders: list[dict] = []
    lateness_delta_min = 0
    dominant_driver: dict = {}
    incumbent_total = None
    if feasible:
        card = _priced_card_data(
            reader, solve_result.solve_values, ops, wps, resources, fuls,
            demands, cost_model, var_map, pin_op_id)
        cost_delta_abs = card["cost_delta_abs"]
        cost_delta_pct = card["cost_delta_pct"]
        cost_lines = card["cost_lines"]
        affected_orders = card["affected_orders"]
        lateness_delta_min = card["lateness_delta_min"]
        dominant_driver = card["dominant_driver"]
        incumbent_total = card["incumbent_total"]

    # CU1 — ATTRIBUTION. Price the same window with NO pin (cached per incumbent)
    # and split the verdict. Only a feasible, priced result can be attributed;
    # everything else keeps the honest unsplit shape.
    attribution = attribute_delta(None, None, None)
    opportunity: dict = {}
    if feasible and baseline and cost_delta_abs is not None:
        base = baseline_window_solve(
            out_dir, snapshot_id, budget_s=budget_s, runs_subdir=runs_subdir,
            deterministic=deterministic, standing_pins=standing_pins,
            restrict_op_ids=restrict_op_ids, det_time_s=det_time_s, seed=seed)
        attribution = attribute_delta(cost_delta_abs, incumbent_total, base)
        opportunity = window_opportunity(base, incumbent_total)
    # R-T2/R-DP8 standing invariant: a committed/standing-pinned op is structurally
    # excluded from the moved-set (``exclude_ops``), so this is True by
    # construction — but ASSERT it against the actual moves (test pins it).
    no_committed_changes = not any(
        m.get("operation_ref") in standing_ops and not m.get("pinned")
        for m in moves)
    message = {
        SANDBOX_VERDICT: ("optimal delta proven" if feasible
                          else "pin infeasible this horizon"),
        SANDBOX_FEASIBLE_UNPROVEN: "≈ delta, bound not proven",
        SANDBOX_NO_VERDICT: "couldn't verify this placement in time",
    }[outcome]
    return SandboxResult(
        outcome=outcome, status=solve_result.status,
        within_budget=wall <= wall_limit + _BUDGET_STOP_MARGIN_S,
        wall_time_s=wall, budget_s=budget_s,
        applied_time_limit_s=wall_limit,
        feasible=feasible, objective=solve_result.objective,
        delta_pct=delta_pct, delta_abs=delta_abs,
        cost_delta_abs=cost_delta_abs, cost_delta_pct=cost_delta_pct,
        message=message, moves=moves,
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
        correlation_id=corr, dominant_driver=dominant_driver,
        affected_orders=affected_orders, lateness_delta_min=lateness_delta_min,
        no_committed_work_changes=no_committed_changes, cost_lines=cost_lines,
        opportunity=opportunity, **receipt, **attribution,
    )


def _pin_unsatisfiable(budget_s: float, pin_op_id: str, pin_resource_id: str,
                       pin_start_dt: datetime, why: str,
                       corr: str = "") -> SandboxResult:
    """The pin cannot be honoured by construction (the op has no assignment
    literal for the target resource, or no start variable): the placement is
    PROVEN illegal, so the honest verdict is an infeasible return-home — never a
    silently-skipped machine pin that reports a happy delta (4.0 hotfix, R-DP1)."""
    return SandboxResult(
        outcome=SANDBOX_VERDICT, status="INFEASIBLE", within_budget=True,
        wall_time_s=0.0, budget_s=budget_s, applied_time_limit_s=budget_s,
        feasible=False, objective=None, delta_pct=None, delta_abs=None,
        cost_delta_abs=None, cost_delta_pct=None,
        message=f"this placement isn't possible: {why}",
        moves=[],
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat()},
        correlation_id=corr,
    )


def _pin_conflict(budget_s: float, pin_op_id: str, pin_resource_id: str,
                  pin_start_dt: datetime, conflict, corr: str = "") -> SandboxResult:
    """The drop is infeasible because it OVERLAPS a standing commitment on the
    same resource (R-DP8). An honest infeasible verdict that NAMES the blocking
    decision — the planner sees which commitment is in the way, and the older pin
    is never quietly sacrificed to make room. ``conflict.op_id`` is a canonical
    operation id; the cockpit resolves it to planner vocabulary."""
    return SandboxResult(
        outcome=SANDBOX_VERDICT, status="INFEASIBLE", within_budget=True,
        wall_time_s=0.0, budget_s=budget_s, applied_time_limit_s=budget_s,
        feasible=False, objective=None, delta_pct=None, delta_abs=None,
        cost_delta_abs=None, cost_delta_pct=None,
        message="this placement conflicts with a commitment you already made — "
                "it overlaps a placement you accepted earlier",
        moves=[],
        pin={"operation_ref": pin_op_id, "resource_id": pin_resource_id,
             "start": pin_start_dt.isoformat(),
             "conflict_op_ref": conflict.op_id,
             "conflict_resource_id": conflict.resource_id},
        correlation_id=corr,
    )


# The named ledger lines the beat-two decomposition reports, in card order. Each
# maps to an extractor cost_ledger / summary_metrics key. total = the sum of
# these four (the extractor's exact decomposition, docs/02 §4.4), so an explicit
# "other" remainder is 0 whenever the ledger fully decomposes — but the card
# always shows it, so a claim the lines cannot back is impossible.
_LEDGER_LINES = (
    ("tardiness", "tardiness_cost"),
    ("setup", "setup_cost"),
    ("production (regular)", "production_regular_cost"),
    ("production (overtime)", "production_overtime_cost"),
)
# How many affected orders the always-visible layer shows (a design token — small,
# so the card leads with the orders a planner actually feels).
_AFFECTED_ORDERS_TOP_N = 4


def _priced_card_data(reader, solve_values, ops, wps, resources, fuls,
                      demands, cost_model, var_map, pin_op_id) -> dict:
    """The R-T2 beat-two LAYERED card data (CU2). ONE in-memory extract of the
    re-solve gives the new ledger + per-order service outcomes + drivers; diffed
    against the base (its persisted summary + service outcomes) yields:

      * cost_delta_abs / cost_delta_pct — the signed total (always-visible);
      * cost_lines — the ledger-line decomposition (detail layer), summing
        EXACTLY to cost_delta_abs (an explicit ``other`` remainder carries any
        residual — rollup_of discipline);
      * affected_orders — top-N by |tardiness delta|, each with its per-Demand
        tardiness ($) + lateness (min) delta (never per-WorkPackage);
      * lateness_delta_min — net tardiness-minutes introduced (+) / recovered (−);
      * dominant_driver — the pinned op's driver, in driver_phrase language,
        HEDGED where the attribution is by price rank (docs/02 §4.2).

    Fully guarded: any failure returns empty/None so the card degrades to the
    relative-% headline, never a false figure."""
    from mre.modules.planner_language import driver_phrase, driver_hedge
    empty = {"cost_delta_abs": None, "cost_delta_pct": None, "cost_lines": None,
             "affected_orders": [], "lateness_delta_min": 0, "dominant_driver": {},
             "incumbent_total": None}
    try:
        from mre.modules.extractor import Extractor
        schedules = list(reader.iter_entities("schedule"))
        base_sm = schedules[-1].get("summary_metrics", {}) if schedules else {}
        base_total = float(base_sm.get("total_cost", 0.0))
        base_svc = list(reader.iter_entities("serviceoutcome"))
        er = Extractor().extract(
            solve_values=solve_values, snapshot_id="sandbox-cost",
            operations=ops, workpackages=wps, resources=resources,
            fulfillments=fuls, demands=demands, cost_model=cost_model,
            reporter=None, cal_windows=var_map.cal_windows,
            op_eligible=var_map.op_eligible, snapshot_writer=None,
            is_scenario=True, overtime_windows=var_map.overtime_windows,
        )
        new_ledger = er.cost_ledger or {}
        new_total = float(new_ledger.get("total_cost", 0.0))
        if not base_total:
            return empty
        cost_delta_abs = round(new_total - base_total, 2)
        cost_delta_pct = round(cost_delta_abs / base_total * 100.0, 4)

        # cost_lines: named ledger-line deltas + an explicit "other" remainder so
        # the lines sum EXACTLY to cost_delta_abs (rollup_of discipline).
        named_sum = 0.0
        cost_lines: list[dict] = []
        for label, key in _LEDGER_LINES:
            d = round(float(new_ledger.get(key, 0.0)) - float(base_sm.get(key, 0.0)), 2)
            named_sum += d
            cost_lines.append({"line": label, "delta": d})
        other = round(cost_delta_abs - named_sum, 2)
        cost_lines.append({"line": "other placement changes", "delta": other})

        # per-order tardiness/lateness deltas (per-Demand truth from the service
        # outcomes). Resolve work-order names via the identity map.
        affected, lateness_delta = _affected_orders(
            reader, er.service_outcomes, base_svc=base_svc, with_total=True)

        # dominant driver = the pinned op's attribution in the re-solve.
        code = None
        for a in er.assignments:
            if a.get("operation_ref") == pin_op_id:
                code = a.get("driver")
                break
        dominant = {}
        if code:
            dominant = {"code": str(code), "phrase": driver_phrase(code),
                        "hedge": driver_hedge(code)}
        return {"cost_delta_abs": cost_delta_abs, "cost_delta_pct": cost_delta_pct,
                "cost_lines": cost_lines, "affected_orders": affected,
                "lateness_delta_min": lateness_delta, "dominant_driver": dominant,
                # CU1: the incumbent's own total, so the caller can attribute the
                # delta against a baseline without re-reading the schedule.
                "incumbent_total": round(base_total, 2)}
    except Exception:
        return empty


def beat_two_contradicts(ghost: "FeasibilityGhost | dict",
                         result: "SandboxResult | dict",
                         tolerance_min: int = 1) -> dict:
    """Does beat two (the priced re-solve) CONTRADICT beat one (the feasibility
    ghost)? R-T2(4): a contradiction must be SHOWN, never silently reconciled.

    Two contradiction kinds (the frontend mirrors this pure logic to decide
    ghost-relocate vs snap-back):
      * ``infeasible`` — beat one said feasible but beat two proves it isn't
        (e.g. a committed/standing commitment blocks it, which beat one relaxed);
      * ``moved`` — both feasible, but beat two places the SAME op at a
        materially different (resource, start) than the ghost showed.

    Returns ``{"infeasible": bool, "moved": bool, "contradicts": bool}``."""
    g = ghost.summary() if hasattr(ghost, "summary") else dict(ghost)
    r = result.summary() if hasattr(result, "summary") else dict(result)
    g_feasible = bool(g.get("feasible"))
    r_feasible = bool(r.get("feasible"))
    infeasible = g_feasible and not r_feasible
    moved = False
    if g_feasible and r_feasible:
        pin_op = (g.get("pin") or {}).get("operation_ref")
        ghost_pin = next((p for p in (g.get("placement") or [])
                          if p.get("pinned")), None)
        r_pin = (r.get("pin") or {})
        if ghost_pin and pin_op:
            same_res = ghost_pin.get("resource_id") == r_pin.get("resource_id")
            gs, rs = ghost_pin.get("start"), r_pin.get("start")
            shifted = True
            if gs and rs:
                shifted = abs((_parse_dt(rs) - _parse_dt(gs)).total_seconds()
                              / 60.0) >= tolerance_min
            moved = (not same_res) or shifted
    return {"infeasible": infeasible, "moved": moved,
            "contradicts": infeasible or moved}


def _svc_lateness_min(svc: dict) -> int:
    """Lateness in signed minutes from a service outcome, handling BOTH shapes:
    the extractor's fresh dict (``lateness_minutes``: int) and the persisted
    canonical entity (``lateness``: ISO 8601 duration string, e.g. ``-P2DT12H58M``).
    Negative = early."""
    if svc.get("lateness_minutes") is not None:
        return int(svc["lateness_minutes"])
    raw = svc.get("lateness")
    if raw is None:
        return 0
    from mre.modules.scenario import _parse_duration_minutes
    return int(_parse_duration_minutes(raw) or 0)


def _affected_orders(reader, new_svc, base_svc=None, with_total: bool = False):
    """Per-Demand tardiness ($) + lateness (min) deltas of ``new_svc`` against the
    incumbent's persisted service outcomes, top-N by |tardiness delta|.

    Factored out of :func:`_priced_card_data` in Session 4B.24 so the OPPORTUNITY
    section (R-T2 amendment clause 3) can state its OWN affected list from its own
    solve. Two callers, one definition — the two lists must be computed the same
    way to be comparable, and they must never be merged."""
    if base_svc is None:
        base_svc = list(reader.iter_entities("serviceoutcome"))
    wo_of = _order_name_resolver(reader.read_identity_map())
    base_by_dem = {s.get("demand_ref"): s for s in base_svc}
    affected: list[dict] = []
    lateness_delta = 0
    for s in new_svc:
        dem = s.get("demand_ref")
        b = base_by_dem.get(dem, {})
        t_d = round(float(s.get("tardiness_cost", 0.0))
                    - float(b.get("tardiness_cost", 0.0)), 2)
        l_new, l_old = _svc_lateness_min(s), _svc_lateness_min(b)
        lateness_delta += max(0, l_new) - max(0, l_old)
        l_d = l_new - l_old
        if abs(t_d) < 0.005 and l_d == 0:
            continue
        affected.append({"demand_ref": dem, "work_order": wo_of(dem),
                         "tardiness_delta": t_d, "lateness_delta_min": l_d})
    affected.sort(key=lambda a: (-abs(a["tardiness_delta"]),
                                 -abs(a["lateness_delta_min"])))
    affected = affected[:_AFFECTED_ORDERS_TOP_N]
    return (affected, lateness_delta) if with_total else affected


def _order_name_resolver(idmap):
    """A demand_ref → work-order (external) name resolver, via the identity map —
    the same source the schedule assembler uses (never an entity attribute)."""
    from mre.modules.schedule_assembler import _ORDER_REF_TYPES, _external_name

    def _wo(demand_ref):
        try:
            return _external_name(idmap, demand_ref, _ORDER_REF_TYPES)
        except Exception:
            return None
    return _wo


def _moved_set(
    solve_values,
    incumbent_placement: dict[str, tuple],
    horizon_start: datetime,
    pin_op_id: str,
    tolerance_min: int = 1,
    exclude_ops: Optional[set[str]] = None,
) -> list[dict]:
    """Compare the re-solve's placements to the incumbent, op by op, and emit
    the displaced set old → new. The pinned op is always included (flagged) so
    the tentative bar is part of the traced change even when only its neighbours
    truly moved. Sorted: pinned first, then largest start shift, so the delta
    card's line items lead with the biggest displacements (R-DP7c).

    ``exclude_ops`` are ops carrying a STANDING commitment (R-DP8): they are held
    fixed by the standing pins, so a committed op can NEVER be a moved consequence
    — it is structurally excluded here (not filtered downstream), the CU2
    guarantee. The freshly-dropped ``pin_op_id`` is exempt from the exclusion: it
    IS the change being shown."""
    exclude = (exclude_ops or set()) - {pin_op_id}

    def _new_placement(op_id: str):
        rid = solve_values.op_resource.get(op_id)
        smin = solve_values.op_start_minutes.get(op_id)
        if rid is None or smin is None:
            return None
        return rid, horizon_start + timedelta(minutes=smin)

    moves: list[dict] = []
    for op_id, (old_rid, old_start) in incumbent_placement.items():
        if op_id in exclude:
            continue
        new = _new_placement(op_id)
        if new is None:
            continue
        new_rid, new_start = new
        start_delta = round((new_start - old_start).total_seconds() / 60.0)
        changed = (new_rid != old_rid) or (abs(start_delta) >= tolerance_min)
        is_pin = op_id == pin_op_id
        if not changed and not is_pin:
            continue
        moves.append({
            "operation_ref": op_id,
            "from_resource": old_rid, "to_resource": new_rid,
            "from_start": old_start.isoformat(), "to_start": new_start.isoformat(),
            "start_delta_min": start_delta,
            "resource_changed": new_rid != old_rid,
            "pinned": is_pin,
        })
    moves.sort(key=lambda m: (not m["pinned"], -abs(m["start_delta_min"])))
    return moves


def _annotate_move_reasons(
    moves: list[dict],
    solve_values,
    horizon_start: datetime,
    pin_op_id: str,
    threshold_min: int = MAJOR_MOVE_THRESHOLD_MIN,
) -> None:
    """Attach a one-clause ``reason`` to each MAJOR forward-shifted move
    (session 3.3 CU3). A delta card that says "+9818 min" without a WHY is a
    number with no story; this reads the story straight off the re-solve's own
    placements — the same occupancy arithmetic the reconstruction already knows.

    For an op that moved later, the reason is whatever holds its NEW machine
    right up until its new start: if that is the DROPPED op, "displaced by the
    dropped op"; otherwise the machine was simply busy — "blocked on <machine>
    until <time>". The reason is STRUCTURED (resource ids, not names) so the
    cockpit renders it in planner vocabulary via its own identity map. Only
    major shifts are annotated (the threshold token), and only when the machine
    is busy contiguously up to the start — a distant blocker is not the reason,
    so no clause is invented.

    Mutates ``moves`` in place; leaves minor shuffles and the pinned drop
    unannotated (the card's own move text already reads them).
    """
    # New placement of EVERY op in the re-solve (for the per-machine timeline).
    new_all: dict[str, tuple[str, datetime, datetime]] = {}
    for op_id, rid in solve_values.op_resource.items():
        smin = solve_values.op_start_minutes.get(op_id)
        emin = solve_values.op_end_minutes.get(op_id)
        if smin is None or emin is None:
            continue
        new_all[op_id] = (rid, horizon_start + timedelta(minutes=smin),
                          horizon_start + timedelta(minutes=emin))
    by_res: dict[str, list[tuple[datetime, datetime, str]]] = {}
    for op_id, (rid, s, e) in new_all.items():
        by_res.setdefault(rid, []).append((s, e, op_id))
    for v in by_res.values():
        v.sort()

    gap = timedelta(minutes=threshold_min)
    for m in moves:
        if m["pinned"] or m["start_delta_min"] < threshold_min:
            continue
        placed = new_all.get(m["operation_ref"])
        if placed is None:
            continue
        rid, start, _end = placed
        # the op that occupies this machine latest, ending at or before `start`
        blocker_op, blocker_end = None, None
        for bs, be, boid in by_res.get(rid, []):
            if boid == m["operation_ref"]:
                continue
            if be <= start and (blocker_end is None or be > blocker_end):
                blocker_op, blocker_end = boid, be
        if blocker_op is None or (start - blocker_end) > gap:
            continue      # not held contiguously — don't fabricate a why
        if blocker_op == pin_op_id:
            m["reason"] = {"kind": "displaced_by_drop"}
        else:
            m["reason"] = {"kind": "occupancy", "on_resource": rid,
                           "blocker_op": blocker_op,
                           "until": blocker_end.isoformat()}


def _parse_dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_ref_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw == "now":
        return None
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
