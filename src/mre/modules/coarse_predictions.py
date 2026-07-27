"""Coarse-zone PREDICTION STORE + conformance report skeleton (R-SC2 amendment
clause 7, Session 4B.6 CU3).

CLAUSE (7) — THE CONFORMANCE REPORT IS OURS TO PUBLISH. Every prediction the
coarse zone makes is persisted and compared against its realization when the
bucket enters the fine window, or when gravity admits the demand early. We
publish our own error bars.

WHY THIS IS NOT IN THE DOCUMENT. The schedule document is a WINDOW-0 VIEW by
ruling (4B.3c): it carries no accumulated past. The coarse audit is inherently
CROSS-ROLL — a prediction made at roll N is judged at roll N+k — so it cannot
live in a document that forgets. Hence a separate store, keyed

    (run_id, demand_id, op_id, bucket_index, resource_witness, run_label)

written as JSONL under the run dir (append-only, one file per run) with a
registry-independent reader that sweeps a data root. If this store does not ship
now, six weeks of history is unrecoverable and rho stays folklore.

REALIZATION IS CAPTURED ON TWO INTAKE PATHS:
  (a) NATURAL ROLL     — the predicted bucket entered the active window and the
                         fine solve placed the op.
  (b) GRAVITY ADMISSION — the demand was pulled into a window EARLY by
                         ``rolling_horizon._admit``'s gravity, before its
                         predicted bucket arrived.
Path (b) is the interesting one: it is TWO MECHANISMS ON RECORD DISAGREEING
ABOUT THE SAME JOB — the coarse model said "week 3", gravity said "now". We
capture WHICH path realized it and the GAP in buckets, and the report counts the
disagreements rather than smoothing them.

SCOPE OF THIS UNIT: the store and a report SKELETON that computes the four
figures the amendment names. The full reporting surface (trend, per-resource
error bars, calibration curve) is later work — named in docs/07, not built here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

UTC = timezone.utc

PREDICTIONS_FILENAME = "coarse_predictions.jsonl"
REALIZATIONS_FILENAME = "coarse_realizations.jsonl"

# Realization intake paths (closed vocabulary — add, never repurpose).
INTAKE_NATURAL_ROLL = "natural_roll"
INTAKE_GRAVITY_ADMISSION = "gravity_admission"

# Slippage attribution (closed vocabulary). ``unattributed`` is a first-class
# outcome, not a failure to try: a slip we cannot attribute is reported as
# unattributed rather than assigned to the most plausible cause.
SLIP_CAPACITY = "capacity"
SLIP_PRECEDENCE = "precedence"
SLIP_ELIGIBILITY = "eligibility"
SLIP_UNATTRIBUTED = "unattributed"


@dataclass(frozen=True)
class CoarsePrediction:
    """One coarse prediction, as persisted. The key is the first six fields."""
    run_id: str
    demand_id: str
    op_id: str
    bucket_index: int
    resource_witness: str          # a WITNESS, never a plan (see coarse_horizon)
    run_label: str                 # "proof" | "planning"
    bucket_start: str              # ISO — so a reader needs no bucket grid
    bucket_end: str
    minutes: int
    rho: float
    bucket_days: int
    predicted_at: str              # ISO timestamp of the roll that predicted it

    def key(self) -> tuple:
        return (self.run_id, self.demand_id, self.op_id, self.bucket_index,
                self.resource_witness, self.run_label)


@dataclass(frozen=True)
class CoarseRealization:
    """What actually happened to a predicted op."""
    run_id: str                    # the run that made the PREDICTION
    demand_id: str
    op_id: str
    predicted_bucket: int
    realized_bucket: int           # bucket index the fine placement fell in
    predicted_resource_witness: str
    realized_resource: str
    intake_path: str               # natural_roll | gravity_admission
    gap_buckets: int               # realized - predicted (negative = early)
    realizing_run_id: str          # the run that PLACED it
    realized_at: str               # ISO
    slip_attribution: str = SLIP_UNATTRIBUTED
    note: str = ""


# ---------------------------------------------------------------------------
# the store
# ---------------------------------------------------------------------------

class CoarsePredictionStore:
    """Append-only JSONL store under a run dir.

    Deliberately NOT the SQLite registry: predictions are per-run artifacts that
    must survive independently of the registry's lifecycle, and an append-only
    text file is auditable by hand — the same reasoning that puts evidence in
    JSONL sinks."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # -- write ------------------------------------------------------------
    def record_predictions(self, preds: list) -> int:
        """Append predictions. Returns the count written. Sorted by key so the
        file content is deterministic for a given zone."""
        path = self.run_dir / PREDICTIONS_FILENAME
        rows = sorted(preds, key=lambda p: p.key())
        with path.open("a", encoding="utf-8") as fh:
            for p in rows:
                fh.write(json.dumps(asdict(p), sort_keys=True) + "\n")
        return len(rows)

    def record_realizations(self, reals: list) -> int:
        path = self.run_dir / REALIZATIONS_FILENAME
        rows = sorted(reals, key=lambda r: (r.run_id, r.demand_id, r.op_id))
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")
        return len(rows)

    # -- read -------------------------------------------------------------
    def predictions(self) -> list:
        return [CoarsePrediction(**d)
                for d in _read_jsonl(self.run_dir / PREDICTIONS_FILENAME)]

    def realizations(self) -> list:
        return [CoarseRealization(**d)
                for d in _read_jsonl(self.run_dir / REALIZATIONS_FILENAME)]


def _read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return iter(())
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return iter(out)


def sweep_data_root(data_root: Path | str) -> tuple:
    """Collect every prediction + realization under a data root (the cross-roll
    read the document cannot provide). Returns (predictions, realizations)."""
    root = Path(data_root)
    preds, reals = [], []
    for p in sorted(root.rglob(PREDICTIONS_FILENAME)):
        preds.extend(CoarsePrediction(**d) for d in _read_jsonl(p))
    for p in sorted(root.rglob(REALIZATIONS_FILENAME)):
        reals.extend(CoarseRealization(**d) for d in _read_jsonl(p))
    return preds, reals


# ---------------------------------------------------------------------------
# minting predictions from a CoarseZone
# ---------------------------------------------------------------------------

def predictions_from_zone(zone: Any, run_id: str,
                          predicted_at: Optional[datetime] = None) -> list:
    """Every placement of BOTH runs becomes a prediction row (clause 2: both
    runs are persisted, each carrying its own label, so a later reader can
    separate proof signal from planning signal without re-deriving anything)."""
    stamp = (predicted_at or datetime.now(UTC)).isoformat()
    buckets = {b.index: b for b in zone.buckets}
    out = []
    for run in (zone.proof, zone.planning):
        if getattr(run, "mirrors_proof", False):
            # not a second solve — recording it as an independent prediction
            # would double-count the proof run in every error bar.
            continue
        for p in run.placements:
            b = buckets.get(p.bucket_index)
            if b is None:
                continue
            out.append(CoarsePrediction(
                run_id=run_id, demand_id=p.demand_id, op_id=p.op_id,
                bucket_index=p.bucket_index, resource_witness=p.resource_witness,
                run_label=run.label, bucket_start=b.start.isoformat(),
                bucket_end=b.end.isoformat(), minutes=int(p.minutes),
                rho=float(run.rho), bucket_days=zone.coefficients.bucket_days,
                predicted_at=stamp))
    return out


def realizations_from_view(predictions: list, view: Any, plant: Any,
                           realizing_run_id: str,
                           gravity_admitted_demand_ids: Optional[set] = None,
                           realized_at: Optional[datetime] = None) -> list:
    """Compare a LATER roll's fine placements against earlier predictions.

    An op appears here only when the later roll actually PLACED it (committed or
    active). ``gravity_admitted_demand_ids`` — the set ``rolling_horizon._admit``
    pulled in by gravity rather than by the time window — decides the intake
    path, so path (b) is recorded as a fact from the admission mechanism, not
    inferred from the gap's sign."""
    stamp = (realized_at or datetime.now(UTC)).isoformat()
    gravity = gravity_admitted_demand_ids or set()
    placed = view.placed
    # bucket grid of the PREDICTION, reconstructed from the rows themselves
    out = []
    for pred in sorted(predictions, key=lambda p: (p.demand_id, p.op_id,
                                                   p.run_label)):
        pl = placed.get(pred.op_id)
        if pl is None:
            continue
        start = _parse(pl["start"])
        b_start = _parse(pred.bucket_start)
        realized_bucket = _bucket_of(start, b_start, pred.bucket_index,
                                     pred.bucket_days)
        gap = realized_bucket - pred.bucket_index
        intake = (INTAKE_GRAVITY_ADMISSION if pred.demand_id in gravity
                  else INTAKE_NATURAL_ROLL)
        out.append(CoarseRealization(
            run_id=pred.run_id, demand_id=pred.demand_id, op_id=pred.op_id,
            predicted_bucket=pred.bucket_index, realized_bucket=realized_bucket,
            predicted_resource_witness=pred.resource_witness,
            realized_resource=pl["resource"], intake_path=intake,
            gap_buckets=gap, realizing_run_id=realizing_run_id,
            realized_at=stamp,
            slip_attribution=_attribute_slip(gap, pred, pl, plant)))
    return out


def _parse(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _bucket_of(when: datetime, ref_bucket_start: datetime, ref_index: int,
               bucket_days: int) -> int:
    """Which bucket index ``when`` falls in, given any one bucket's (start,
    index) and the bucket length. Integer floor division on days, so a placement
    before the reference bucket yields a smaller index (possibly negative)."""
    delta_days = (when - ref_bucket_start).total_seconds() / 86400.0
    import math
    return ref_index + math.floor(delta_days / bucket_days)


def _attribute_slip(gap: int, pred: CoarsePrediction, placement: dict,
                    plant: Any) -> str:
    """Attribute a POSITIVE gap (realized later than predicted) to a cause.

    This is deliberately CONSERVATIVE and mostly returns ``unattributed``: a
    confident attribution needs the fine solve's own binding constraints, which
    the coarse store does not have. What it CAN say without guessing:
      * gap <= 0        — nothing to attribute (on time or early);
      * the fine solve chose a DIFFERENT resource than the witness, and the
        witness was the only capability-eligible one ⇒ eligibility;
      * otherwise       — unattributed, and the report says so out loud.
    Sharpening this is named work (docs/07), gated on the store's own data —
    exactly the sequencing clause (7) implies."""
    if gap <= 0:
        return SLIP_UNATTRIBUTED
    if placement.get("resource") != pred.resource_witness:
        return SLIP_ELIGIBILITY
    return SLIP_UNATTRIBUTED


# ---------------------------------------------------------------------------
# the report skeleton
# ---------------------------------------------------------------------------

@dataclass
class ConformanceReport:
    """The four figures the amendment names, per roll.

    Coarse and fine currency NEVER fuse (clause 5): ``cost_error`` is reported
    as a SIGNED PAIR of separately-labeled figures with its own units, never as
    a single blended number, and coarse tardiness stays in buckets."""
    predictions_total: int = 0
    realized_total: int = 0
    realized_in_predicted_bucket: int = 0
    realized_fraction: Optional[float] = None
    slippage: dict = field(default_factory=dict)          # cause -> count
    gravity_disagreements: int = 0
    gravity_gap_buckets: list = field(default_factory=list)
    coarse_tardiness_buckets: Optional[int] = None        # coarse ledger
    fine_tardiness_minutes: Optional[float] = None        # fine ledger, SEPARATE
    cost_error_sign: Optional[str] = None                 # "coarse_over"|"coarse_under"|"exact"
    cost_error_magnitude_buckets: Optional[int] = None    # in BUCKETS, never $
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_conformance_report(predictions: list, realizations: list, *,
                             coarse_tardiness_buckets: Optional[int] = None,
                             fine_tardiness_minutes: Optional[float] = None,
                             fine_tardiness_buckets: Optional[int] = None
                             ) -> ConformanceReport:
    """Compute the per-roll conformance figures. Pure arithmetic over the store."""
    rep = ConformanceReport()
    rep.predictions_total = len(predictions)
    rep.realized_total = len(realizations)
    rep.realized_in_predicted_bucket = sum(1 for r in realizations
                                           if r.gap_buckets == 0)
    if realizations:
        rep.realized_fraction = rep.realized_in_predicted_bucket / len(realizations)
    else:
        rep.notes.append("no realizations yet — the fraction is undefined, not 0")

    slip: dict = {SLIP_CAPACITY: 0, SLIP_PRECEDENCE: 0, SLIP_ELIGIBILITY: 0,
                  SLIP_UNATTRIBUTED: 0}
    for r in realizations:
        if r.gap_buckets > 0:
            slip[r.slip_attribution] = slip.get(r.slip_attribution, 0) + 1
    rep.slippage = slip
    if slip[SLIP_UNATTRIBUTED] and not (slip[SLIP_CAPACITY] or
                                        slip[SLIP_PRECEDENCE] or
                                        slip[SLIP_ELIGIBILITY]):
        rep.notes.append(
            "every slip is UNATTRIBUTED: attribution needs the fine solve's "
            "binding constraints, which this store does not carry (named debt)")

    grav = [r for r in realizations
            if r.intake_path == INTAKE_GRAVITY_ADMISSION and r.gap_buckets != 0]
    rep.gravity_disagreements = len(grav)
    rep.gravity_gap_buckets = sorted(r.gap_buckets for r in grav)

    rep.coarse_tardiness_buckets = coarse_tardiness_buckets
    rep.fine_tardiness_minutes = fine_tardiness_minutes
    if coarse_tardiness_buckets is not None and fine_tardiness_buckets is not None:
        d = coarse_tardiness_buckets - fine_tardiness_buckets
        rep.cost_error_sign = ("exact" if d == 0
                               else "coarse_over" if d > 0 else "coarse_under")
        rep.cost_error_magnitude_buckets = abs(d)
    else:
        rep.notes.append(
            "coarse-vs-fine error not computed: it requires the fine tardiness "
            "expressed in BUCKETS (clause 5 forbids fusing the two ledgers, so "
            "the comparison is made in the coarse unit or not at all)")
    return rep
