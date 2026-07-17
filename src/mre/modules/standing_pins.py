"""Standing pins — an accepted placement is a commitment (docs/04 R-DP8).

When a planner accepts an edit, the pin (op, resource, start) does not evaporate
after that one re-solve: it becomes a **standing commitment** on the schedule
lineage. Every subsequent sandbox / accept / scenario solve of the same lineage
must compile ALL of the lineage's accepted pins as hard constraints alongside the
new drop — so the optimizer can never silently undo a decision the planner
already made (the live specimen: a cost-neutral published edit that the next
edit's re-solve reverted, then honestly listed as a "consequence").

This module is the SINGLE seam through which pins are applied to a CP-SAT model —
the primary drop AND the standing pins go through the same ``apply_pin`` so the
two can never diverge in how they bind (the 4.0b lesson: give the layers ONE
function to call, don't have each re-implement the invariant). It is intentionally
tiny and imports no ortools at module load; the model/var_map are passed in.

A pin is a plain dict ``{"operation_ref", "resource_id", "start"}`` (``start`` an
ISO-8601 string). ``resource_id`` may also arrive as ``resource_ref`` from older
records; both are read. Release (an explicit ``unpin`` verb) is a named
carry-forward — this module only ever ADDS commitments.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

UTC = timezone.utc


class PinUnsatisfiable(Exception):
    """A pin cannot be honoured on this model: the op has no schedulable start
    variable, or no assignment literal for the target resource. Carries the
    structured reason so callers author the right refusal (hard error on an
    accept, honest infeasible return-home on a sandbox)."""

    def __init__(self, op_id: str, resource_id: str, reason: str) -> None:
        self.op_id = op_id
        self.resource_id = resource_id
        self.reason = reason
        super().__init__(f"pin op {op_id} → {resource_id}: {reason}")


@dataclass
class PinConflict:
    """A new drop is infeasible AGAINST a standing commitment (R-DP8): the two
    pins occupy overlapping time on the same resource. Names the blocking
    commitment so the verdict says which decision blocks the drop, rather than
    quietly sacrificing the older pin."""
    op_id: str                    # the standing-commitment op that blocks
    resource_id: str              # the resource both want
    reason: str = "overlaps a placement you already committed"


def pin_op_id(pin: dict) -> str:
    return pin.get("operation_ref") or pin.get("pin_op_id") or ""


def pin_resource_id(pin: dict) -> Optional[str]:
    return pin.get("resource_id") or pin.get("resource_ref") or pin.get("pin_resource_id")


def pin_start_iso(pin: dict) -> Optional[str]:
    return pin.get("start") or pin.get("pin_start_iso")


def start_minutes(start_iso: str, horizon_start: datetime) -> int:
    """The pin start in the canonical minute grid (int minutes since
    horizon_start) — the same grid the solver's start variables live in, so a pin
    binds without a rounding/tz seam (the 4.0c grid discipline)."""
    dt = _parse_dt(start_iso)
    if dt is None:
        raise ValueError(f"cannot parse pin start {start_iso!r}")
    return int((dt - horizon_start).total_seconds() // 60)


def apply_pin(model, var_map, op_id: str, resource_id: str, start_min: int) -> None:
    """Bind ONE pin on BOTH axes (machine AND time) as HARD constraints (R-DP1).

    Raises :class:`PinUnsatisfiable` when the op has no start variable or no
    assignment literal for ``resource_id`` — the invariant is enforced, never
    skipped-and-vouched (the 4.0 hotfix lesson). Callers translate the exception
    into the register their surface needs.
    """
    if op_id not in var_map.op_start:
        raise PinUnsatisfiable(op_id, resource_id, "op has no schedulable start")
    lit = var_map.op_assign.get(op_id, {}).get(resource_id)
    if lit is None:
        raise PinUnsatisfiable(
            op_id, resource_id,
            f"op is not eligible on the target resource (eligible: "
            f"{sorted(var_map.op_assign.get(op_id, {}))})")
    model.add(var_map.op_start[op_id] == start_min)
    model.add(lit == 1)


def apply_standing_pins(
    model, var_map, standing_pins: Optional[list[dict]],
    horizon_start: datetime, *, skip_op: Optional[str] = None,
) -> list[str]:
    """Apply every standing pin as a hard constraint (R-DP8), skipping the op
    named by ``skip_op`` (the op the caller is pinning fresh — the new drop
    re-commits that op, so its prior commitment is superseded for this solve).

    Returns the list of op ids actually pinned. A standing pin whose op is absent
    from this model (a scenario that re-planned it away) is skipped and its op id
    is NOT in the return — the caller decides whether that is acceptable
    (exploratory scenario: yes; accept: the lineage copies entities verbatim, so
    it never happens). A pin present-but-not-eligible is a genuine inconsistency
    and raises :class:`PinUnsatisfiable`.
    """
    applied: list[str] = []
    for pin in standing_pins or []:
        op = pin_op_id(pin)
        if not op or op == skip_op:
            continue
        rid = pin_resource_id(pin)
        s_iso = pin_start_iso(pin)
        if not rid or not s_iso:
            continue
        if op not in var_map.op_start:
            # The op is not in this model (a scenario re-plan removed/reshaped it).
            # Not a hard error here — the caller reports skipped standing pins.
            continue
        apply_pin(model, var_map, op, rid, start_minutes(s_iso, horizon_start))
        applied.append(op)
    return applied


def normalize_pin(op_id: str, resource_id: str, start_iso: str) -> dict:
    """The canonical standing-pin record shape stored on a version."""
    return {"operation_ref": op_id, "resource_id": resource_id, "start": start_iso}


def compose_lineage_pins(base_pins: Optional[list[dict]], new_pin: dict) -> list[dict]:
    """The cumulative standing pins of a NEW accepted version: the base lineage's
    pins with any prior commitment for the SAME op replaced by ``new_pin`` (the
    drop re-commits that op), plus ``new_pin`` if it names a fresh op (R-DP8).
    Order-stable: existing commitments keep their position, a genuinely new one
    appends. ``new_pin`` is normalized to the canonical record shape."""
    op = pin_op_id(new_pin)
    normalized = normalize_pin(op, pin_resource_id(new_pin) or "",
                               pin_start_iso(new_pin) or "")
    out: list[dict] = []
    replaced = False
    for p in base_pins or []:
        if pin_op_id(p) == op:
            out.append(normalized)
            replaced = True
        else:
            out.append({"operation_ref": pin_op_id(p),
                        "resource_id": pin_resource_id(p) or "",
                        "start": pin_start_iso(p) or ""})
    if not replaced:
        out.append(normalized)
    return out


def standing_pin_ops(standing_pins: Optional[list[dict]]) -> set[str]:
    """The set of op ids carrying a standing commitment — used to STRUCTURALLY
    exclude them from any moved-set (a committed op can never be reported as a
    moved consequence, R-DP8 CU2)."""
    return {pin_op_id(p) for p in (standing_pins or []) if pin_op_id(p)}


def detect_conflict(
    new_pin: dict, standing_pins: Optional[list[dict]],
    var_map, horizon_start: datetime,
) -> Optional[PinConflict]:
    """Find a standing commitment the NEW drop directly conflicts with — an
    exact same-resource time overlap — so an infeasible verdict can NAME which
    decision blocks the drop (R-DP8 CU1). Best-effort and truthful: it returns a
    conflict ONLY on a provable interval overlap (never blames a commitment for an
    infeasibility that is actually precedence/calendar). Durations come from
    ``var_map.op_durations`` (the solver's own minute durations).

    Returns None when no standing pin overlaps the new drop on its resource.
    """
    new_op = pin_op_id(new_pin)
    new_rid = pin_resource_id(new_pin)
    new_iso = pin_start_iso(new_pin)
    if not new_rid or not new_iso:
        return None
    durations = getattr(var_map, "op_durations", {}) or {}
    try:
        new_start = start_minutes(new_iso, horizon_start)
    except ValueError:
        return None
    new_dur = int(durations.get(new_op, 0))
    new_end = new_start + new_dur
    for pin in standing_pins or []:
        op = pin_op_id(pin)
        if not op or op == new_op:
            continue
        rid = pin_resource_id(pin)
        s_iso = pin_start_iso(pin)
        if rid != new_rid or not s_iso:
            continue
        try:
            s_start = start_minutes(s_iso, horizon_start)
        except ValueError:
            continue
        s_end = s_start + int(durations.get(op, 0))
        # half-open interval overlap on the shared resource
        if new_start < s_end and s_start < new_end:
            return PinConflict(op_id=op, resource_id=rid)
    return None


def _parse_dt(raw) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    dt = raw if isinstance(raw, datetime) else datetime.fromisoformat(
        str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
