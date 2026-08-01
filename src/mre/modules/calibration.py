"""R-CAL1 — THE CALIBRATION CEREMONY'S ENGINE (Session 4B.29).

The shape lives in ``mre.contracts.calibration``; this is what fills it, stores
it, and reads it back at solve time. Four jobs:

  * :func:`run_grid` — the measurement. 4B.26's sweep, productized: resumable,
    append-only, deterministic per cell, one cell at a time.
  * :class:`ProfileStore` — rules (1) and (2): a profile is written sealed with
    a digest of its own grid, refused if the digest does not match, and inert
    until :meth:`ProfileStore.accept` records a human's signature.
  * :func:`resolve` — rule (3): what a solve found when it looked. It never
    returns None; ``absent`` is a first-class answer with its own sentence.
  * :func:`detect_drift` — Item 4: an accepted profile promised K publishable
    searches at this budget; if fewer arrived, the solve completes and SAYS SO.

NOTHING HERE AUTO-APPLIES ANYTHING. :func:`resolve` reports; the caller decides,
and the caller's own declared coefficients always win. That is rule (2) at the
seam where it can actually be violated.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from mre.contracts.calibration import (
    CALIBRATION_SCHEMA_VERSION, CalibrationCell, CalibrationProfile,
    CalibrationStatus, DEFAULT_KNEE_TOLERANCE_PCT, INSTRUMENT_VERSION,
    absent_status, build_recommendation, summarise_arm,
)

#: The ceremony's default grid (4B.26's own axes, plus the 8.0 bisection the
#: errand's residual arm asked for). Every one of these is OVERRIDABLE and
#: whatever actually ran is recorded in the profile — a default that silently
#: became the record would be rule (1) with extra steps.
DEFAULT_BUDGETS = (3.0, 6.0, 10.0, 15.0)
DEFAULT_SEEDS = (42, 43, 44, 45, 46)

#: A CEILING, never a budget (the standing rule). A member the wall stops is not
#: reproducible and its cell is unpublishable by R-BK1 clause (1), so this is set
#: high enough that it decides nothing.
DEFAULT_WALL_CEILING_S = 1800.0

#: Seconds per deterministic unit, for the projected-wall estimate ONLY. 4B.24
#: measured 33.9-77.0 s/unit on this laptop; the midpoint is a forecast, and the
#: profile records what it actually cost beside what it predicted.
SECONDS_PER_DET_UNIT = 55.0


# ---------------------------------------------------------------------------
# Rule (4) — the facility is the scope
# ---------------------------------------------------------------------------

class MultiFacilitySubmission(Exception):
    """Rule (4), enforced rather than assumed.

    A submission declaring more than one facility cannot be calibrated today:
    the solve does not partition by facility (the 4B.10 partition ruling's
    corollary is still an open follow-up), so one grid over two plants would
    produce coefficients calibrated for neither and a profile that LOOKED
    measured. Refusing by name is the honest outcome; inventing a joint profile
    is the hidden-weight defect.
    """


def plant_key_for(submission_dir: Path | str) -> tuple[str, str]:
    """``(plant_key, facility)`` from the submission manifest's facility scope.

    Raises :class:`MultiFacilitySubmission` where the scope names more than one.
    A submission declaring NO facility scope is keyed on its source system and
    said so — an unnamed plant is still one plant, and refusing it would lock
    out every synthetic world we measure with.
    """
    manifest = Path(submission_dir) / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"no manifest.json under {submission_dir}")
    data = json.loads(manifest.read_text("utf-8"))
    scope = data.get("facility_scope") or []
    if isinstance(scope, str):
        scope = [scope]
    scope = [str(s) for s in scope if str(s).strip()]
    if len(scope) > 1:
        raise MultiFacilitySubmission(
            f"this submission declares {len(scope)} facilities "
            f"({', '.join(sorted(scope))}) and the solve does not partition by "
            f"facility yet, so one profile would be calibrated for neither — "
            f"R-CAL1 rule (4). Split the submission, or calibrate per facility "
            f"once partitioning lands")
    src = str(data.get("source_system") or "unknown").strip()
    if scope:
        facility = scope[0]
        return f"{src}::{facility}", facility
    return f"{src}::unscoped", "(no facility declared)"


# ---------------------------------------------------------------------------
# The store — rules (1) and (2)
# ---------------------------------------------------------------------------

def _safe(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in name)


class ProfileStore:
    """``<data_root>/calibration/<plant_key>.json``, one profile per plant.

    Writes are always SEALED (rule 1); reads always verify the seal and a
    mismatch is returned as ``unreadable`` rather than raising, because a solve
    must not die because someone edited a config file — it must say so.
    """

    def __init__(self, data_root: Path | str) -> None:
        self.root = Path(data_root) / "calibration"

    def path_for(self, plant_key: str) -> Path:
        return self.root / f"{_safe(plant_key)}.json"

    def save(self, profile: CalibrationProfile) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        sealed = profile.sealed()
        p = self.path_for(sealed.plant_key)
        p.write_text(sealed.model_dump_json(indent=2), encoding="utf-8")
        return p

    def load(self, plant_key: str) -> Optional[CalibrationProfile]:
        """The profile as written. None when there is none; raises nothing for a
        bad digest — :func:`resolve` is where that becomes a sentence.

        A profile written by a NEWER schema raises rather than parsing: pydantic
        would happily ignore fields this code has never heard of and hand back a
        thin object that looks complete, which is 4B.18's defect exactly. A file
        that cannot be read WHOLE must say so.
        """
        p = self.path_for(plant_key)
        if not p.exists():
            return None
        raw = p.read_text("utf-8")
        try:
            version = int(json.loads(raw).get("schema_version", 0))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"the calibration profile for {plant_key} is not "
                             f"readable JSON: {type(exc).__name__}") from exc
        if version > CALIBRATION_SCHEMA_VERSION:
            raise ValueError(
                f"the calibration profile for {plant_key} was written by schema "
                f"{version} and this build reads {CALIBRATION_SCHEMA_VERSION} — "
                f"refusing to read it partially")
        return CalibrationProfile.model_validate_json(raw)

    def accept(self, plant_key: str, *, by: str) -> CalibrationProfile:
        """RULE (2) — the human signature, and the only way a profile goes live.

        Refuses a profile whose grid digest does not match: accepting an edited
        grid is exactly the thing rule (1) exists to prevent, and this is the
        one place a human's authority could otherwise launder it.
        """
        prof = self.load(plant_key)
        if prof is None:
            raise FileNotFoundError(f"no calibration profile for {plant_key}")
        if not prof.digest_ok():
            raise ValueError(
                f"the profile for {plant_key} does not match the digest of its "
                f"own grid — it has been edited since it was measured, and "
                f"R-CAL1 rule (1) refuses it. Re-run the calibration")
        if not by.strip():
            raise ValueError("accepting a calibration profile requires a name — "
                             "rule (2) is a signature, not a flag")
        live = prof.model_copy(update={
            "accepted": True, "accepted_by": by,
            "accepted_at": datetime.now(timezone.utc)})
        self.save(live)
        return live


# ---------------------------------------------------------------------------
# Rule (3) — what a solve found when it looked
# ---------------------------------------------------------------------------

def resolve(data_root: Path | str | None, submission_dir: Path | str | None, *,
            window_solved: Optional[int] = None) -> CalibrationStatus:
    """Look for this plant's profile and REPORT, in every branch.

    Never raises and never returns None. A solve that could not even work out
    which plant it is running against is ``absent`` with that reason on it —
    silence here would let a plant on product defaults look calibrated.
    """
    if data_root is None or submission_dir is None:
        return absent_status(window_solved=window_solved)
    try:
        key, _facility = plant_key_for(submission_dir)
    except Exception as exc:  # noqa: BLE001 — a refusal is a sentence
        return CalibrationStatus(
            state="absent", window_solved=window_solved,
            sentence=(f"this plant could not be identified for calibration "
                      f"({type(exc).__name__}: {exc}), so this solve ran the "
                      f"product's default search coefficients"))
    store = ProfileStore(data_root)
    try:
        prof = store.load(key)
    except Exception as exc:  # noqa: BLE001
        return CalibrationStatus(
            state="unreadable", plant_key=key, window_solved=window_solved,
            sentence=(f"a calibration profile for this plant exists and could "
                      f"not be read ({type(exc).__name__}) — this solve ran the "
                      f"product's default search coefficients"))
    if prof is None:
        return absent_status(plant_key=key, window_solved=window_solved)
    if not prof.digest_ok():
        return CalibrationStatus(
            state="unreadable", plant_key=key, profile_id=prof.profile_id,
            calibrated_at=prof.calibrated_at,
            instrument_version=prof.instrument_version,
            window_solved=window_solved,
            window_calibrated=prof.recommendation.window_days,
            sentence=("this plant's calibration profile does not match the "
                      "digest of its own grid — it was edited after it was "
                      "measured, so it is refused (R-CAL1 rule 1) and this "
                      "solve ran the product's default search coefficients"))
    rec = prof.recommendation
    if not prof.accepted:
        return CalibrationStatus(
            state="unaccepted", plant_key=key, profile_id=prof.profile_id,
            calibrated_at=prof.calibrated_at,
            instrument_version=prof.instrument_version,
            window_solved=window_solved, window_calibrated=rec.window_days,
            sentence=(f"a calibration profile for this plant was measured on "
                      f"{prof.calibrated_at.date().isoformat()} and has not "
                      f"been accepted, so this solve ran the product's default "
                      f"search coefficients (R-CAL1 rule 2)"))
    return CalibrationStatus(
        state="accepted", plant_key=key, profile_id=prof.profile_id,
        calibrated_at=prof.calibrated_at,
        instrument_version=prof.instrument_version,
        window_solved=window_solved, window_calibrated=rec.window_days,
        sentence=prof.declaration())


def coefficients(status: CalibrationStatus, data_root: Path | str | None
                 ) -> dict:
    """The (det_total, k) an ACCEPTED profile offers. Empty otherwise.

    The window is deliberately NOT offered. A window is what a planner asked to
    SEE — it decides which work is on the board — where K and the budget decide
    only how hard we look for a way to place it. Silently re-cutting the horizon
    to the calibrated one would answer a question nobody asked; instead
    :func:`apply_to` records both windows and the certificate states when they
    differ. mid170 is why that difference must be visible: same world, same
    budget, 5 of 5 at ten days and 0 of 5 at fourteen.
    """
    if status.state != "accepted" or not status.plant_key:
        return {}
    try:
        prof = ProfileStore(data_root).load(status.plant_key)
    except Exception:  # noqa: BLE001 — a profile that became unreadable between
        return {}      # resolve and here offers nothing; resolve owns the words

    if prof is None or not prof.recommendation.found:
        return {}
    rec = prof.recommendation
    out = {}
    if rec.det_total is not None:
        out["det_total"] = float(rec.det_total)
    if rec.k is not None:
        out["k"] = int(rec.k)
    return out


def apply_to(status: CalibrationStatus, offered: dict, *,
             caller_declared: Iterable[str] = ()) -> tuple[dict, CalibrationStatus]:
    """Merge an accepted profile's coefficients under the caller's own.

    THE CALLER ALWAYS WINS. A profile is a measured recommendation, not an
    override: a request that declared ``portfolio_k`` gets the K it asked for,
    and the status then says the profile was not applied to that field rather
    than implying it was.
    """
    declared = set(caller_declared)
    applied = {k: v for k, v in offered.items() if k not in declared}
    note = ""
    withheld = sorted(set(offered) - set(applied))
    if withheld:
        note = (f" (the request declared its own {', '.join(withheld)}, which "
                f"the profile does not override)")
    if status.state == "accepted":
        status = status.model_copy(update={
            "applied": applied,
            "sentence": status.sentence + (
                f" — applied: " + ", ".join(f"{k}={v:g}" if isinstance(v, float)
                                            else f"{k}={v}"
                                            for k, v in sorted(applied.items()))
                if applied else " — no coefficient applied") + note,
        })
    return applied, status


# ---------------------------------------------------------------------------
# Item 4 — drift
# ---------------------------------------------------------------------------

DRIFT_SENTENCE = (
    "calibration drift — {missing} of {k} searches returned no board at the "
    "calibrated budget of {det:g} deterministic units; recommend re-running "
    "calibration for this plant")


def detect_drift(status: CalibrationStatus, book) -> Optional[dict]:
    """Did the portfolio deliver what the calibration promised?

    Fires ONLY under an accepted, APPLIED profile: a solve running product
    defaults has no promise to drift from, and reporting drift there would turn
    an uncalibrated plant into a broken one. Informational — the solve completes
    on the best available member (R-BK1), because a schedule the planner can use
    is worth more than a clean certificate, and the no-derate precedent already
    settled that absence is loud but not a gate verdict.

    Returns None when there is nothing to say. A drift dict is never empty and
    never partial.
    """
    if status is None or status.state != "accepted":
        return None
    if book is None or getattr(book, "k", 1) <= 0:
        return None
    applied = status.applied or {}
    if "det_total" not in applied and "k" not in applied:
        return None
    k = int(getattr(book, "k", 0) or 0)
    pub = len(getattr(book, "usable", []) or [])
    if k <= 0 or pub >= k:
        return None
    det = float(getattr(book, "det_time_s", 0.0) or 0.0)
    seeds = [m.seed for m in getattr(book, "members", ())
             if not (m.selectable and m.ledger_total is not None)]
    return {
        "kind": "calibration_drift",
        "k": k,
        "publishable": pub,
        "missing": k - pub,
        "det_total": det,
        "unpublished_seeds": seeds,
        "profile_id": status.profile_id,
        "calibrated_at": (status.calibrated_at.isoformat()
                          if status.calibrated_at else None),
        "sentence": DRIFT_SENTENCE.format(missing=k - pub, k=k, det=det),
    }


def record_drift(drift: Optional[dict], *, snapshot_id: str, runs_dir,
                 plant_key: str = "") -> None:
    """File the drift as a real evidence Finding, not only a document field.

    ``CALIBRATION_DRIFT`` at INFO / ``proceeded_flagged``: the schedule stands
    and nothing is excluded. Never raises — a reporting fault must not take away
    a board that is already solved, which is the discipline the coarse
    prediction store already runs under (4B.6a).
    """
    if not drift:
        return
    try:
        from mre.contracts.entities import EntityRef
        from mre.contracts.vocabularies import (
            FindingCode, FindingDisposition, FindingSeverity,
        )
        from mre.reporter import Reporter

        rep = Reporter.begin(
            module="M6", purpose="calibration_drift",
            config={"plant_key": plant_key, "k": drift["k"],
                    "det_total": drift["det_total"]},
            trigger="calibration", snapshot_id=snapshot_id, sink_dir=runs_dir)
        rep.record_finding(
            code=FindingCode.CALIBRATION_DRIFT,
            severity=FindingSeverity.INFO,
            # The subject is the PLANT, which is not a canonical entity — so it
            # is named as a typed non-canonical ref (docs/02 boundary rule 1)
            # rather than dressed up as a Resource it is not.
            subjects=[EntityRef(entity_id=plant_key, entity_type="plant",
                                system="calibration")] if plant_key else [],
            evidence={k: v for k, v in drift.items() if k != "sentence"},
            disposition=FindingDisposition.PROCEEDED_FLAGGED,
            disposition_detail="the solve published the best available member",
            message=drift["sentence"])
        rep.end()
    except Exception as exc:  # noqa: BLE001 — caught, and named in the log
        import logging
        logging.getLogger("mre.calibration").warning(
            "calibration drift finding could not be recorded: %s: %s",
            type(exc).__name__, exc)


# ---------------------------------------------------------------------------
# The measurement (Item 3's engine)
# ---------------------------------------------------------------------------

def cells_path(out_dir: Path | str) -> Path:
    return Path(out_dir) / "cells.jsonl"


def load_cells(out_dir: Path | str) -> list[CalibrationCell]:
    """Every cell already on disk, append-only, newest wins on a repeat.

    A re-measured cell is not an error: the ceremony is resumable and a cell may
    legitimately be re-run. The LAST row for a coordinate is the one that counts,
    and both rows stay in the file — the jsonl is the audit trail, the list is
    the grid.
    """
    p = cells_path(out_dir)
    if not p.exists():
        return []
    by_key: dict = {}
    for line in p.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            c = CalibrationCell.model_validate_json(line)
        except Exception:  # noqa: BLE001 — a malformed row is skipped, loudly
            continue
        by_key[(c.window_days, c.frozen_days, round(c.det_total, 6), c.seed)] = c
    return [by_key[k] for k in sorted(by_key)]


def append_cell(out_dir: Path | str, cell: CalibrationCell) -> None:
    p = cells_path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(cell.model_dump_json() + "\n")


def planned_cells(windows, budgets, seeds, frozen_days: int) -> list[tuple]:
    """The grid's coordinates, cheapest-budget-first so an interrupted ceremony
    still leaves the decision-relevant rows on disk (4B.26 ran into exactly
    this, and its ORDER comment is the reason this is not alphabetical)."""
    out = []
    for b in sorted(budgets):
        for w in sorted(windows):
            for s in sorted(seeds):
                out.append((w, frozen_days, float(b), int(s)))
    return out


def project_wall_s(pending: Iterable[tuple],
                   seconds_per_unit: float = SECONDS_PER_DET_UNIT) -> float:
    """COST HONESTY: what this ceremony is about to spend, before it spends it.

    A forecast from 4B.24's measured exchange rate, not a promise — the profile
    records the actual beside it, and 4B.26 §6(f) already found members at the
    wide end of that rate. An onboarding ceremony that surprises nobody says the
    number BEFORE it starts.
    """
    return round(sum(float(det) for (_w, _f, det, _s) in pending)
                 * seconds_per_unit, 1)


def measure_cell(plant, window_days: int, frozen_days: int, det_total: float,
                 seed: int, *, wall_ceiling_s: float = DEFAULT_WALL_CEILING_S,
                 gravity: bool = True) -> CalibrationCell:
    """ONE CELL — one deterministic search, nothing persisted.

    ``persist=False``: a calibration cell is a probe. It measures how a search
    behaves at these coefficients and must never mint a schedule, register a
    board, or write to the working data root.
    """
    from mre.modules.rolling_horizon import _member_from_view, build_rolling_view

    t0 = time.monotonic()
    try:
        view = build_rolling_view(
            plant, window_days=window_days, frozen_days=frozen_days,
            gravity=gravity, deterministic=True, seed=seed,
            member_time_limit_s=wall_ceiling_s, det_total=det_total,
            persist=False)
    except Exception as exc:  # noqa: BLE001 — a cell that dies is a cell
        return CalibrationCell(
            window_days=window_days, frozen_days=frozen_days,
            det_total=det_total, seed=seed, status="ERROR",
            publishable=False,
            reason=f"the search failed: {type(exc).__name__}: {exc}",
            wall_time_s=round(time.monotonic() - t0, 3))
    member = _member_from_view(seed, view, time.monotonic() - t0)
    return CalibrationCell(
        window_days=window_days, frozen_days=frozen_days, det_total=det_total,
        seed=seed, status=member.status or view.status or "",
        ledger_total=member.ledger_total, det_consumed=member.det_consumed,
        wall_time_s=member.wall_time_s,
        publishable=bool(member.selectable and member.ledger_total is not None),
        reason=member.reason)


def run_grid(submission_dir: Path | str, out_dir: Path | str, *,
             windows: Iterable[int], budgets: Iterable[float],
             seeds: Iterable[int], frozen_days: int = 1,
             reference_date=None, resume: bool = True,
             wall_ceiling_s: float = DEFAULT_WALL_CEILING_S,
             on_event: Optional[Callable[[dict], Any]] = None
             ) -> list[CalibrationCell]:
    """MEASURE THE GRID. Resumable, append-only, one cell at a time.

    STRICTLY SEQUENTIAL by construction, and that is not laziness: 4B.25
    measured a member running ~1.8x slower with four siblings on this laptop, so
    a wall taken beside a competing process is not a wall — and the wall column
    is half of what this ceremony is for.
    """
    from mre.modules.rolling_horizon import prepare_plant

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    say = on_event or (lambda _e: None)

    have = {(c.window_days, c.frozen_days, round(c.det_total, 6), c.seed)
            for c in load_cells(out_dir)} if resume else set()
    plan = planned_cells(windows, budgets, seeds, frozen_days)
    pending = [c for c in plan
               if (c[0], c[1], round(c[2], 6), c[3]) not in have]
    say({"kind": "plan", "cells_total": len(plan), "cells_pending": len(pending),
         "cells_reused": len(plan) - len(pending),
         "projected_wall_s": project_wall_s(pending)})
    if not pending:
        return load_cells(out_dir)

    t0 = time.monotonic()
    plant = prepare_plant(submission_dir, out_dir / "prep",
                          reference_date=reference_date)
    say({"kind": "plant", "prepare_s": round(time.monotonic() - t0, 3),
         "demands": len(plant.demands), "operations": len(plant.operations),
         "resources": len(plant.resources)})

    for i, (w, fz, det, seed) in enumerate(pending, start=1):
        say({"kind": "cell_start", "i": i, "n": len(pending), "window_days": w,
             "det_total": det, "seed": seed})
        cell = measure_cell(plant, w, fz, det, seed,
                            wall_ceiling_s=wall_ceiling_s)
        append_cell(out_dir, cell)
        say({"kind": "cell", "i": i, "n": len(pending),
             "window_days": w, "det_total": det, "seed": seed,
             "status": cell.status, "ledger_total": cell.ledger_total,
             "publishable": cell.publishable,
             "wall_s": cell.wall_time_s})
    return load_cells(out_dir)


def build_profile(submission_dir: Path | str, cells, *, seeds,
                  prefer_window: Optional[int] = None,
                  reference_date=None,
                  tolerance_pct: float = DEFAULT_KNEE_TOLERANCE_PCT,
                  projected_wall_s: Optional[float] = None,
                  actual_wall_s: Optional[float] = None,
                  notes: str = "") -> CalibrationProfile:
    """Assemble and SEAL a profile from measured cells. Never accepted here —
    rule (2) is a separate ceremony with a name attached."""
    key, facility = plant_key_for(submission_dir)
    rec = build_recommendation(cells, seeds, prefer_window=prefer_window,
                               tolerance_pct=tolerance_pct)
    # COST HONESTY, over the SAME SET. Both figures describe the cells THIS
    # ceremony measured — never the whole grid against one run's wall, which
    # would be a forecast for twenty-five cells printed beside a wall for five.
    # Derived from the grid so a profile rebuilt from its own cells reports the
    # same pair rather than zeros.
    mine = [c for c in cells if c.source == "measured"]
    if projected_wall_s is None:
        projected_wall_s = round(sum(float(c.det_total) for c in mine)
                                 * SECONDS_PER_DET_UNIT, 1)
    if actual_wall_s is None:
        actual_wall_s = round(sum(c.wall_time_s or 0.0 for c in mine), 1)
    prof = CalibrationProfile(
        schema_version=CALIBRATION_SCHEMA_VERSION,
        profile_id=f"cal-{_safe(key)}-{int(time.time())}",
        plant_key=key, facility=facility,
        submission_dir=str(submission_dir),
        reference_date=(reference_date.date().isoformat()
                        if hasattr(reference_date, "date") else
                        (str(reference_date) if reference_date else None)),
        instrument_version=INSTRUMENT_VERSION,
        seeds=sorted(int(s) for s in seeds),
        cells=list(cells), recommendation=rec,
        projected_wall_s=projected_wall_s, actual_wall_s=actual_wall_s,
        notes=notes)
    return prof.sealed()


def render_profile(profile: CalibrationProfile) -> str:
    """The ceremony's own report — plain ASCII, the grid whole."""
    L = []
    L.append(f"CALIBRATION PROFILE  {profile.profile_id}")
    L.append(f"  plant      {profile.plant_key}  (facility {profile.facility})")
    L.append(f"  measured   {profile.calibrated_at.isoformat()} "
             f"by {profile.instrument_version}")
    L.append(f"  seeds      {profile.seeds}")
    L.append(f"  grid       {len(profile.cells)} cells, digest "
             f"{profile.grid_digest[:16]}...")
    if profile.projected_wall_s is not None:
        # The pair is over the SAME SET — the cells this run actually had to
        # measure. A forecast for the whole grid beside a wall for five cells
        # would be decoration, not cost honesty.
        mine = sum(1 for c in profile.cells if c.source == "measured")
        L.append(f"  wall       {mine} cell(s) measured here: projected "
                 f"{profile.projected_wall_s:.0f}s, actual "
                 f"{(profile.actual_wall_s or 0.0):.0f}s")
    L.append(f"  accepted   {'yes, by ' + profile.accepted_by if profile.accepted else 'NO (rule 2 — offer only)'}")
    L.append("")
    L.append("THE GRID")
    seeds = profile.seeds
    head = "  window  budget " + "".join(f"{s:>14}" for s in seeds) + "   pub"
    L.append(head)
    L.append("  " + "-" * (len(head) - 2))
    for w in profile.windows():
        for b in profile.budgets(w):
            arm = summarise_arm(profile.cells, w, b)
            by = {c.seed: c for c in profile.cells
                  if c.window_days == w and abs(c.det_total - b) < 1e-9}
            row = f"  {w:>6}  {b:>6g} "
            for s in seeds:
                c = by.get(s)
                if c is None:
                    row += f"{'--':>14}"
                elif c.publishable and c.ledger_total is not None:
                    row += f"{c.ledger_total:>14,.0f}"
                else:
                    row += f"{(c.status or 'EMPTY'):>14}"
            row += f"   {arm.publishable}/{arm.k}" if arm else ""
            L.append(row)
    L.append("")
    L.append("THE KNEE RULE")
    L.append(f"  {profile.recommendation.knee_rule}")
    L.append("")
    L.append("RECOMMENDATION")
    L.append(f"  {profile.recommendation.sentence()}")
    L.append(f"  {profile.recommendation.knee_note}")
    return "\n".join(L)
