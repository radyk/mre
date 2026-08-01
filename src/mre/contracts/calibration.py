"""R-CAL1 — CALIBRATION IS MEASURED, OFFERED, AND DECLARED (Session 4B.29).

4B.26 measured the demo board's knee: the cold main-solve portfolio is worth
$578 at 6.0 deterministic units per member and $460,014.78 at 10.0, the
empty-board hazard clears somewhere between the two, and K=3 takes the whole of
K=5's gain wherever the gain is material. The temptation is to ship 10.0 as the
product default. That is the seed-44 mistake one level up: **10.0 is ONE BOARD's
calibration, not a law.** The 170-order control board in the same sweep needs a
different window entirely, and nothing in the sweep licenses a number for a
plant nobody has measured.

What generalizes is not the number — it is the PROCEDURE. 4B.26, run as a
ceremony per plant, its output declared on the certificate. This module is that
output's shape.

THE FOUR RULES (verbatim in docs/04, 2026-08-01):

  (1) A PROFILE IS MEASURED, NEVER AUTHORED. Every cell in its grid is solver
      output. Hand-editing one is the hidden-weight defect wearing a config
      file: a coefficient with no measurement behind it, presented as though it
      had one. The file carries a DIGEST OF ITS OWN GRID (:func:`grid_digest`),
      recomputed on load, and a profile whose digest does not match is REFUSED
      rather than used — the same discipline the provenance sidecar puts on an
      `observed` attribute.

  (2) A PROFILE IS OFFERED, NEVER AUTO-APPLIED. The ceremony emits it; a human
      accepts it. This is the promotion-pipeline precedent (4A.5c): a clean
      dossier still crosses a human signature, because the dossier is the
      application and the review is the decision. Until accepted, solves run the
      product defaults and the certificate says an unaccepted profile exists.

  (3) AN ACCEPTED PROFILE IS DECLARED. The certificate names the calibrated
      coefficients, the calibration date and the instrument that measured them,
      on every solve that used them. An ABSENT or EXPIRED profile is STATED, not
      silent — the no-derate-declared precedent (4B.6a CU2(d)): a plant running
      on product defaults is told so, rather than being left to assume its
      numbers were measured.

  (4) THE PROFILE'S SCOPE IS THE FACILITY. The facility is the planning unit
      (the 4B.10 partition ruling); a coefficient calibrated across two
      facilities is calibrated for neither. One submission spanning facilities
      gets one profile per facility — and until the solve itself partitions,
      a multi-facility submission is REFUSED calibration by name rather than
      given one profile wearing two plants' evidence.

WHAT IS **NOT** IN HERE, AND WHY. The calibrated coefficients are PRODUCT-SIDE,
not IDS. K, the per-member deterministic budget and the window are facts about
OUR SEARCH — how long our solver looks and how many times — and a plant cannot
declare them because a plant does not have them. Contrast the coarse zone's rho
(docs/06 §5.9): a capacity derate is a fact about the PLANT, so it is a declared
IDS coefficient and pays the §8 pipeline-proof chain. Nothing here reaches the
model, the objective or the ledger; a profile changes only how hard we look and
how many times, never what we are looking for. **No docs/06 doorway is owed,
and this paragraph is the record of that decision.**
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

#: Bumped when the on-disk shape changes. A profile written by a newer schema is
#: REFUSED by older code rather than partially read — the 4B.18 lesson: a file
#: that cannot be read completely must say so loudly, not yield a thin object.
CALIBRATION_SCHEMA_VERSION = 1

#: The instrument. A profile records which version of the ceremony measured it,
#: because a grid measured by a changed instrument is not comparable to one that
#: was not, and "the numbers moved" must be separable from "the meter moved".
INSTRUMENT_VERSION = "mre.calibrate/1"

#: THE KNEE TOLERANCE (see :func:`find_knee`). A budget counts as "as good as"
#: a larger one when its winner is within this percentage. Declared, and carried
#: on the profile, so a knee found under a loose tolerance can never be read as
#: one found under a tight one.
DEFAULT_KNEE_TOLERANCE_PCT = 1.0

#: R-BK1 clause (4) needs two publishable members to say anything at all: a
#: spread of one number is not a spread. So a RECOMMENDED K is never 1 even
#: where one seed captures all the value — the second member is not buying a
#: cheaper board, it is buying the sentence that says how settled this one is.
MIN_RECOMMENDED_K = 2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalibrationCell(BaseModel):
    """ONE MEASURED CELL: one seed, at one budget, in one window. Solver output.

    ``publishable`` is the R-BK1 clause (1) test, not a paraphrase of ``status``:
    a run that produced no ledger, or that the WALL stopped rather than its
    deterministic budget, is not reproducible and is therefore not selectable.
    ``reason`` says which, and an unpublishable cell is still CARRIED — the
    empty cells are the finding (4B.26 §1), and a grid that dropped them would
    report a reliability nobody measured.
    """
    window_days: int
    frozen_days: int
    det_total: float
    seed: int
    status: str = ""
    ledger_total: Optional[float] = None
    det_consumed: Optional[float] = None
    wall_time_s: Optional[float] = None
    publishable: bool = False
    reason: str = ""
    measured_at: datetime = Field(default_factory=_utcnow)
    #: Where this cell came from. ``"measured"`` is this ceremony's own run;
    #: anything else names the run it was IMPORTED from. Rule (1) allows import
    #: — a re-used row is still solver output — but never anonymously.
    source: str = "measured"

    @property
    def arm(self) -> tuple:
        return (self.window_days, self.frozen_days, self.det_total)


class ArmSummary(BaseModel):
    """One (window, budget) column of the grid, summarised over its seeds."""
    window_days: int
    frozen_days: int
    det_total: float
    seeds: list[int] = []
    publishable: int = 0
    k: int = 0
    winner_seed: Optional[int] = None
    winner_ledger: Optional[float] = None
    spread_abs: Optional[float] = None
    spread_pct: Optional[float] = None
    wall_total_s: float = 0.0

    @property
    def all_publishable(self) -> bool:
        return self.k > 0 and self.publishable == self.k


class CalibrationRecommendation(BaseModel):
    """WHAT THE GRID RECOMMENDS, and how it got there.

    ``found`` is False when NO measured budget put every seed on the board for
    the requested window. That is a finding, not a gap: "this window is not
    reliably reachable at any measured budget" is what mid170-w14 says, and the
    profile then recommends the DEEPEST window that IS reachable and names the
    one it gave up on.
    """
    found: bool = False
    window_days: Optional[int] = None
    frozen_days: Optional[int] = None
    det_total: Optional[float] = None
    k: Optional[int] = None
    #: The smallest K that captures the value at the knee, BEFORE the clause-(4)
    #: floor is applied. Reported separately so the floor is never mistaken for
    #: a measurement.
    k_for_value: Optional[int] = None
    knee_rule: str = ""
    knee_note: str = ""
    tolerance_pct: float = DEFAULT_KNEE_TOLERANCE_PCT
    #: Reliability AT the recommendation, and at one measured budget below it —
    #: the margin. A knee sitting one step above a cliff is a different
    #: recommendation from one sitting three steps above it, and the number that
    #: distinguishes them is free here.
    publishable_at_knee: Optional[int] = None
    #: The DENOMINATOR of the line above — how many searches ran, not how many
    #: succeeded. 4B.21's rule: a count names the disposition it counts, and
    #: adjacent counts share a denominator or state their own.
    members_at_knee: Optional[int] = None
    margin_det_total: Optional[float] = None
    margin_publishable: Optional[int] = None
    margin_members: Optional[int] = None
    #: Windows the grid measured and could not reach at any budget.
    unreachable_windows: list[int] = []

    def sentence(self) -> str:
        if not self.found:
            return ("no measured budget put every seeded search on the board in "
                    "any measured window — this plant has no recommendation")
        parts = [f"window {self.window_days} days, "
                 f"{self.det_total:g} deterministic units per search, "
                 f"K={self.k}"]
        if self.publishable_at_knee is not None and self.members_at_knee:
            parts.append(f"{self.publishable_at_knee} of "
                         f"{self.members_at_knee} seeded searches published at "
                         f"this budget")
        if self.margin_det_total is not None and self.margin_members:
            parts.append(f"at {self.margin_det_total:g} units "
                         f"{self.margin_publishable} of {self.margin_members} "
                         f"did")
        if self.unreachable_windows:
            ws = ", ".join(f"{w}d" for w in self.unreachable_windows)
            parts.append(f"window(s) {ws} were not reachable at any measured "
                         f"budget")
        return "; ".join(parts)


class CalibrationProfile(BaseModel):
    """A PLANT'S MEASURED SEARCH CALIBRATION (R-CAL1).

    The evidence is carried WHOLE — ``cells`` is the grid, not a summary of it.
    A recommendation a reader cannot check against its own measurements is an
    assertion, and this project's whole discipline is that a figure the product
    derives must be quotable by the surface that derives it (4B.20).
    """
    schema_version: int = CALIBRATION_SCHEMA_VERSION
    profile_id: str
    #: Facility-scoped by rule (4). A submission whose manifest declares more
    #: than one facility never reaches here — the ceremony refuses it.
    plant_key: str
    facility: str
    submission_dir: str = ""
    reference_date: Optional[str] = None
    calibrated_at: datetime = Field(default_factory=_utcnow)
    instrument_version: str = INSTRUMENT_VERSION
    seeds: list[int] = []
    cells: list[CalibrationCell] = []
    #: Rule (1). sha256 over the canonical measurement content of every cell.
    grid_digest: str = ""
    recommendation: CalibrationRecommendation = CalibrationRecommendation()
    #: COST HONESTY. What the ceremony said it would cost before it started, and
    #: what it actually cost. An onboarding ceremony that surprises nobody.
    projected_wall_s: Optional[float] = None
    actual_wall_s: Optional[float] = None
    #: Rule (2). A profile is inert until a human accepts it.
    accepted: bool = False
    accepted_at: Optional[datetime] = None
    accepted_by: str = ""
    notes: str = ""

    # -- rule (1): the grid audits itself ------------------------------------

    def compute_digest(self) -> str:
        return grid_digest(self.cells)

    def digest_ok(self) -> bool:
        return bool(self.grid_digest) and self.grid_digest == self.compute_digest()

    def sealed(self) -> "CalibrationProfile":
        """Return a copy carrying a digest of its own grid."""
        return self.model_copy(update={"grid_digest": self.compute_digest()})

    # -- reading the grid ----------------------------------------------------

    def windows(self) -> list[int]:
        return sorted({c.window_days for c in self.cells})

    def budgets(self, window_days: Optional[int] = None) -> list[float]:
        return sorted({c.det_total for c in self.cells
                       if window_days is None or c.window_days == window_days})

    def arm(self, window_days: int, det_total: float) -> Optional[ArmSummary]:
        return summarise_arm(self.cells, window_days, det_total)

    def arms(self) -> list[ArmSummary]:
        out = []
        for w in self.windows():
            for b in self.budgets(w):
                a = summarise_arm(self.cells, w, b)
                if a is not None:
                    out.append(a)
        return out

    def declaration(self) -> str:
        """Rule (3): what the certificate says when this profile was applied."""
        when = self.calibrated_at.date().isoformat()
        return (f"calibrated for {self.facility} on {when} by "
                f"{self.instrument_version} ({len(self.cells)} measured cells)")


def grid_digest(cells) -> str:
    """sha256 over the MEASUREMENT content of the grid, in a canonical order.

    Deliberately excludes ``measured_at`` and ``source``: they are bookkeeping,
    and a re-import that changes neither the coefficients nor what the solver
    found has not changed the grid. Everything a recommendation is derived FROM
    is inside the hash, which is what makes rule (1) enforceable.
    """
    rows = sorted(
        (c.window_days, c.frozen_days, round(float(c.det_total), 6), c.seed,
         c.status,
         None if c.ledger_total is None else round(float(c.ledger_total), 2),
         None if c.det_consumed is None else round(float(c.det_consumed), 6),
         bool(c.publishable))
        for c in cells
    )
    blob = json.dumps(rows, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def summarise_arm(cells, window_days: int,
                  det_total: float) -> Optional[ArmSummary]:
    """Collapse one (window, budget) column. Never drops an unpublishable cell
    from ``k`` — the denominator is what was RUN, not what succeeded."""
    got = [c for c in cells
           if c.window_days == window_days
           and abs(c.det_total - det_total) < 1e-9]
    if not got:
        return None
    got = sorted(got, key=lambda c: c.seed)
    pub = [c for c in got if c.publishable and c.ledger_total is not None]
    tot = [c.ledger_total for c in pub]
    win = min(pub, key=lambda c: (c.ledger_total, c.seed)) if pub else None
    spread = round(max(tot) - min(tot), 2) if len(tot) >= 2 else None
    pct = None
    if spread is not None and abs(min(tot)) > 0.005:
        pct = round(100.0 * spread / abs(min(tot)), 4)
    return ArmSummary(
        window_days=window_days, frozen_days=got[0].frozen_days,
        det_total=det_total, seeds=[c.seed for c in got],
        publishable=len(pub), k=len(got),
        winner_seed=None if win is None else win.seed,
        winner_ledger=None if win is None else win.ledger_total,
        spread_abs=spread, spread_pct=pct,
        wall_total_s=round(sum(c.wall_time_s or 0.0 for c in got), 3),
    )


KNEE_RULE = (
    "the smallest measured budget at which (i) every seeded search published a "
    "board and (ii) its winning ledger is within {tol:g}% of the best winner at "
    "any LARGER measured budget"
)


def find_knee(cells, window_days: int,
              tolerance_pct: float = DEFAULT_KNEE_TOLERANCE_PCT
              ) -> tuple[Optional[float], str]:
    """THE KNEE, AS A STATED RULE RATHER THAN A VIBE.

    Returns ``(budget, note)``; ``budget`` is None when no measured budget put
    every seed on the board, and the note then says so in the words the profile
    prints. Condition (ii) is vacuously true at the largest measured budget,
    which is honest and is the rule's own limit: a knee is the smallest budget
    that is as good as anything MEASURED above it, never a claim about budgets
    nobody ran.
    """
    budgets = sorted({c.det_total for c in cells
                      if c.window_days == window_days})
    if not budgets:
        return None, f"no cells measured at window {window_days}"
    arms = {b: summarise_arm(cells, window_days, b) for b in budgets}
    full = [b for b in budgets
            if arms[b] is not None and arms[b].all_publishable]
    if not full:
        worst = max((arms[b].publishable for b in budgets
                     if arms[b] is not None), default=0)
        k = next((arms[b].k for b in budgets if arms[b] is not None), 0)
        return None, (f"window {window_days} is not reliably reachable at any "
                      f"measured budget — the best any of "
                      f"{', '.join(f'{b:g}' for b in budgets)} units managed is "
                      f"{worst} of {k} seeded searches on the board")
    for b in full:
        larger = [arms[x].winner_ledger for x in budgets
                  if x > b and arms[x] is not None
                  and arms[x].winner_ledger is not None]
        here = arms[b].winner_ledger
        if here is None:
            continue
        if not larger:
            return b, (f"{b:g} units is the largest measured budget at this "
                       f"window and every seeded search published there")
        best = min(larger)
        if best <= 0:
            within = abs(here - best) <= 0.005
        else:
            within = here <= best * (1.0 + tolerance_pct / 100.0)
        if within:
            return b, (f"{b:g} units puts every seeded search on the board and "
                       f"its winner (${here:,.2f}) is within {tolerance_pct:g}% "
                       f"of the best winner at any larger measured budget "
                       f"(${best:,.2f})")
    biggest = full[-1]
    return biggest, (f"no smaller budget reached within {tolerance_pct:g}% of a "
                     f"larger one, so the knee is the largest budget at which "
                     f"every seeded search published: {biggest:g} units")


def recommend_k(cells, window_days: int, det_total: float, seeds,
                tolerance_pct: float = DEFAULT_KNEE_TOLERANCE_PCT
                ) -> tuple[Optional[int], Optional[int], str]:
    """THE SMALLEST K THAT CAPTURES THE VALUE, and the K we recommend.

    Members are CONSECUTIVE seeds (R-BK1 clause 1), so the K-member portfolio of
    a measured arm is literally the first K of its seeds — no re-solve is needed
    to read K=1, K=2, K=3 off a K=5 measurement, and 4B.26 §4 read exactly this
    way. The rule: the smallest prefix whose winner is within tolerance of the
    full seed set's winner.

    Returns ``(k_recommended, k_for_value, note)``. They differ only where the
    clause-(4) floor bites, and the note says so — the floor is an argument, not
    a measurement, and must never wear a measurement's clothes.
    """
    seeds = sorted(seeds)
    arm = summarise_arm(cells, window_days, det_total)
    if arm is None or arm.winner_ledger is None:
        return None, None, "no publishable member at the recommended budget"
    by_seed = {c.seed: c for c in cells
               if c.window_days == window_days
               and abs(c.det_total - det_total) < 1e-9}
    best = arm.winner_ledger
    k_val = None
    for k in range(1, len(seeds) + 1):
        pub = [by_seed[s].ledger_total for s in seeds[:k]
               if s in by_seed and by_seed[s].publishable
               and by_seed[s].ledger_total is not None]
        if not pub:
            continue
        here = min(pub)
        if best <= 0:
            ok = abs(here - best) <= 0.005
        else:
            ok = here <= best * (1.0 + tolerance_pct / 100.0)
        if ok:
            k_val = k
            break
    if k_val is None:
        k_val = len(seeds)
    k_rec = max(MIN_RECOMMENDED_K, k_val)
    if k_rec == k_val:
        note = (f"K={k_val} is the smallest prefix of seeds "
                f"{seeds[0]}..{seeds[-1]} whose winner is within "
                f"{tolerance_pct:g}% of the full set's")
    else:
        note = (f"K={k_val} captures the value, but a portfolio of one has no "
                f"spread to report (R-BK1 clause 4), so the recommendation is "
                f"K={k_rec}")
    return k_rec, k_val, note


def build_recommendation(cells, seeds, *, prefer_window: Optional[int] = None,
                         tolerance_pct: float = DEFAULT_KNEE_TOLERANCE_PCT
                         ) -> CalibrationRecommendation:
    """Apply the knee rule to every measured window and pick one.

    ``prefer_window`` is the submission's own declared window — what the plant
    asked for. If it is reachable we recommend it; if it is NOT, we recommend
    the DEEPEST window that is and name the one we gave up on, because a
    recommendation that silently swapped the planner's horizon for a shorter one
    would be answering a question nobody asked.
    """
    windows = sorted({c.window_days for c in cells})
    if not windows:
        return CalibrationRecommendation(tolerance_pct=tolerance_pct)
    knees: dict = {}
    notes: dict = {}
    for w in windows:
        b, note = find_knee(cells, w, tolerance_pct)
        knees[w], notes[w] = b, note
    reachable = [w for w in windows if knees[w] is not None]
    unreachable = [w for w in windows if knees[w] is None]
    if not reachable:
        return CalibrationRecommendation(
            found=False, tolerance_pct=tolerance_pct,
            knee_rule=KNEE_RULE.format(tol=tolerance_pct),
            knee_note="; ".join(notes[w] for w in windows),
            unreachable_windows=unreachable)
    if prefer_window in reachable:
        pick = prefer_window
    else:
        pick = max(reachable)
    budget = knees[pick]
    arm = summarise_arm(cells, pick, budget)
    k_rec, k_val, k_note = recommend_k(cells, pick, budget, seeds,
                                       tolerance_pct)
    below = [b for b in sorted({c.det_total for c in cells
                                if c.window_days == pick}) if b < budget]
    margin_b = below[-1] if below else None
    margin_arm = (summarise_arm(cells, pick, margin_b)
                  if margin_b is not None else None)
    note = notes[pick]
    if prefer_window is not None and prefer_window != pick:
        note = (f"the declared window ({prefer_window} days) is not reliably "
                f"reachable — {notes[prefer_window]} — so the recommendation is "
                f"the deepest window that is: {note}")
    return CalibrationRecommendation(
        found=True, window_days=pick,
        frozen_days=arm.frozen_days if arm is not None else None,
        det_total=budget, k=k_rec, k_for_value=k_val,
        knee_rule=KNEE_RULE.format(tol=tolerance_pct),
        knee_note=f"{note}. {k_note}",
        tolerance_pct=tolerance_pct,
        publishable_at_knee=arm.publishable if arm is not None else None,
        members_at_knee=arm.k if arm is not None else None,
        margin_det_total=margin_b,
        margin_publishable=(margin_arm.publishable
                            if margin_arm is not None else None),
        margin_members=(margin_arm.k if margin_arm is not None else None),
        unreachable_windows=unreachable,
    )


# ---------------------------------------------------------------------------
# What the certificate says (rule 3). Its shape lives here; the block that
# reaches the document is `schedule_document.CalibrationBlock`, built from this.
# ---------------------------------------------------------------------------

CalibrationState = Literal["accepted", "unaccepted", "absent", "unreadable"]


class CalibrationStatus(BaseModel):
    """WHAT A SOLVE FOUND WHEN IT LOOKED FOR A PROFILE — never silence.

    ``absent`` is a first-class outcome and carries its own sentence: a plant
    running on product defaults is TOLD it is running on product defaults. That
    is the no-derate-declared precedent, and it is the difference between "we
    measured this" and "nobody has measured this yet", which a planner cannot
    otherwise tell apart.

    ``unreadable`` is the 4B.18 state: a profile exists and its grid digest does
    not match, so it is refused. A claim about our calibration must never be
    manufactured from a fact about our storage.
    """
    state: CalibrationState = "absent"
    plant_key: str = ""
    profile_id: str = ""
    calibrated_at: Optional[datetime] = None
    instrument_version: str = ""
    sentence: str = ""
    #: The coefficients the solve ACTUALLY used from the profile. Empty when the
    #: profile was not applied — an accepted profile that could not be applied
    #: (the caller declared its own) says so rather than implying it was.
    applied: dict = {}
    #: The profile's window against the window this solve actually ran. A
    #: calibration measured at 10 days says nothing about a 14-day solve, and
    #: mid170 is the specimen: same world, same budget, 5 of 5 at w10 and 0 of 5
    #: at w14.
    window_calibrated: Optional[int] = None
    window_solved: Optional[int] = None
    #: Item 4 — drift, when the members disagreed with the calibration.
    drift: Optional[dict] = None


def absent_status(plant_key: str = "", window_solved: Optional[int] = None
                  ) -> CalibrationStatus:
    return CalibrationStatus(
        state="absent", plant_key=plant_key, window_solved=window_solved,
        sentence=("no calibration profile for this plant — this solve ran the "
                  "product's default search coefficients, which are not "
                  "measured for this plant"))
