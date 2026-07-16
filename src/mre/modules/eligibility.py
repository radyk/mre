"""Operation → resource eligibility: ONE derivation, two consumers (docs/04
R-DP6, Session 4.0b — Tier-0 vs solver eligibility unified).

Before this module the eligible set was resolved TWICE, by hand:

  * the Solver Builder decided which resources get an ``op_assign`` literal (and,
    for resumable ops, a chunk-slot) — the set the R-DP1 pin binds against;
  * the schedule-document assembler re-derived ``eligible_resource_ids`` for the
    Tier-0 interaction payload the cockpit dims/greens rows with.

Two hand-maintained copies of the capability resolution, and — worse — the
payload advertised the RAW capability set while the pin binds the COMPILED set,
which for a resumable op is further pruned by calendar feasibility. So Tier-0
could green a row the solver has no literal for: the drop is accepted, the
machine pin is silently un-bindable, and the op relocates (the 4.0-hotfix
symptom, one step upstream). R-DP6 requires green = provably-not-illegal BY THE
SAME RULES the solver compiles; two derivations cannot guarantee that.

This module is the narrow waist. It is ortools-free (the assembler must not
import the solver). The Solver Builder delegates its capability resolution,
calendar flatten, and resumable feasible-window check here; the assembler builds
the payload's eligible set through :func:`pinnable_resources` — the SAME
functions, so the two sets are equal by construction. When the builder prunes a
capability-eligible resource (no in-horizon calendar window that could finish a
resumable op; a WIP-fixed op that is not freely placeable), the payload carries
the SAME prune WITH a reason, so Tier-0 dims it with an honest hover-line
instead of greening it.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

UTC = timezone.utc

# uuid5 namespace for capability ids: uuid5(_CAP_NS, "capability:<code>"). This
# is the standard DNS namespace, shared verbatim with the IDS adapter that mints
# capability_ref values — the single constant both the solver and the payload
# reverse-map through.
_CAP_NS = _uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# Dim reasons carried to Tier-0 for a capability-eligible resource the solver
# still refuses a literal for (so the hover reads the truth, not "capability").
REASON_CAPABILITY = "capability"          # not capability-eligible at all
REASON_NO_CALENDAR = "no_calendar_window"  # resumable op, no window can finish it
REASON_WIP_FIXED = "wip_fixed"            # complete / in-progress: not re-placeable


def _cap_id(name: str) -> str:
    return str(_uuid.uuid5(_CAP_NS, f"capability:{name}"))


def _parse_dt(s: Optional[str]) -> datetime:
    """Identical to the Solver Builder's own parser (naive → UTC), so the
    shared flatten produces byte-identical minute windows."""
    if not s:
        return datetime(2099, 1, 1, tzinfo=UTC)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def capability_eligible(
    resource_requirements: Optional[list[dict]], resources_by_id: dict[str, dict]
) -> list[str]:
    """Resources the op may run on by CAPABILITY, in ``resources_by_id``
    iteration order (the Solver Builder's historical order — callers that need
    determinism sort the result).

    The first ResourceRequirement is consulted (multi-requirement machine-AND-
    tool ops resolve on the first, matching the solver's scope cut). Modes:
      * ``explicit_set`` → the ``resource_refs`` present in the document;
      * ``capability``   → resources bearing a capability whose uuid5 == the ref.
    An empty/absent requirement, or a requirement that matches nothing, opens
    the op to EVERY resource (the solver's "no requirement → all eligible"
    scope cut and its empty-match fallback — never prune to empty here).
    """
    reqs = resource_requirements or []
    if not reqs:
        return list(resources_by_id)
    req = reqs[0]
    mode = req.get("mode", "")
    if mode == "explicit_set":
        refs = [r for r in (req.get("resource_refs") or []) if r in resources_by_id]
        return refs if refs else list(resources_by_id)
    if mode == "capability":
        cap_ref = req.get("capability_ref", "")
        matched = [
            rid for rid, res in resources_by_id.items()
            if any(_cap_id(c) == cap_ref for c in res.get("capabilities", []))
        ]
        return matched if matched else list(resources_by_id)
    return list(resources_by_id)


def feasible_window_range(
    windows: list[tuple[int, int]], working_min: int, wp_earliest_min: int
) -> Optional[tuple[int, int]]:
    """Candidate (lo, hi) calendar-window indices a RESUMABLE op could touch on
    one resource, or ``None`` when the resource has no window at/after
    ``wp_earliest_min`` with enough trailing capacity to ever finish.

    ``None`` ⟺ the resource gets NO ``op_assign`` literal for this resumable op:
    the lo window (``e > wp_earliest_min``) always yields at least one usable
    chunk slot, so a non-None range always produces a literal, and a None range
    never does. This equivalence is what lets the payload re-derive op_assign
    membership exactly. Moved verbatim from ``SolverBuilder._feasible_window_range``
    — the single definition both consumers call.
    """
    lo = next((i for i, (s, e) in enumerate(windows) if e > wp_earliest_min), None)
    if lo is None:
        return None
    n = len(windows)
    suffix_capacity = [0] * (n + 1)
    for i in range(n - 1, lo - 1, -1):
        s, e = windows[i]
        avail_start = max(s, wp_earliest_min)
        suffix_capacity[i] = suffix_capacity[i + 1] + max(0, e - avail_start)
    max_start_idx = lo
    for i in range(lo, n):
        if suffix_capacity[i] >= working_min:
            max_start_idx = i
    min_window_len = min((e - s for s, e in windows[lo:]), default=1) or 1
    chunks_max = max(2, -(-working_min // min_window_len) + 1)
    hi = min(max_start_idx + chunks_max - 1, n - 1)
    return lo, hi


def flatten_resource_windows(
    resources_by_id: dict[str, dict],
    cal_map: dict[str, dict],
    horizon_start: datetime,
    horizon_end: datetime,
) -> dict[str, list[tuple[int, int]]]:
    """Per-resource list of (start_min, end_min) open windows over the horizon.

    The single definition of the solver's calendar flatten (moved verbatim from
    ``SolverBuilder._flatten_all``): uses a calendar's populated
    ``horizon_resolved`` if present, else flattens ``base_pattern`` + exceptions.
    Both the Solver Builder and the assembler flatten through here, so the
    resumable feasible-window prune sees identical windows on both sides.
    """
    result: dict[str, list[tuple[int, int]]] = {}
    for rid, res in resources_by_id.items():
        cal_id = res.get("calendar_ref")
        cal = cal_map.get(cal_id) if cal_id else None
        if cal is None:
            result[rid] = []
            continue
        windows = cal.get("horizon_resolved", [])
        if windows:
            parsed = []
            for w in windows:
                ws = _parse_dt(w["start"] if isinstance(w, dict) else w.start)
                we = _parse_dt(w["end"] if isinstance(w, dict) else w.end)
                s_min = max(0, int((ws - horizon_start).total_seconds() / 60))
                e_min = max(0, int((we - horizon_start).total_seconds() / 60))
                parsed.append((s_min, e_min))
            result[rid] = parsed
        else:
            try:
                from mre.contracts.entities import CalendarException, TimeWindow
                from mre.contracts.vocabularies import (
                    CalendarExceptionReason, CalendarExceptionType,
                )
                from mre.modules.calendar_utils import flatten_calendar
                bp = cal.get("base_pattern", {})
                excs_raw = cal.get("exceptions", [])
                excs: list[CalendarException] = []
                for e in excs_raw:
                    if isinstance(e, dict):
                        tw = TimeWindow(
                            start=_parse_dt(e["window"]["start"]),
                            end=_parse_dt(e["window"]["end"]),
                        )
                        excs.append(CalendarException(
                            window=tw,
                            type=CalendarExceptionType(e.get("type", "closure")),
                            reason=CalendarExceptionReason(e.get("reason", "planned_maintenance")),
                        ))
                    else:
                        excs.append(e)
                flat = flatten_calendar(bp, excs, horizon_start, horizon_end)
                parsed = []
                for w in flat:
                    s_min = max(0, int((w.start - horizon_start).total_seconds() / 60))
                    e_min = max(0, int((w.end - horizon_start).total_seconds() / 60))
                    parsed.append((s_min, e_min))
                result[rid] = parsed
            except Exception:
                result[rid] = []
    return result


def pinnable_resources(
    op: dict,
    resources_by_id: dict[str, dict],
    windows_by_res: dict[str, list[tuple[int, int]]],
    wp_earliest_min: int,
    total_min: int,
) -> tuple[list[str], dict[str, str]]:
    """The resources the Solver Builder would give an ``op_assign`` literal for
    ``op`` — i.e. the set the R-DP1 pin can actually bind — plus, for the
    capability-eligible resources it still refuses, a dim reason.

    Mirrors the builder's op_assign construction:
      * WIP-fixed (``complete`` / ``in_progress``) ops are off the free model or
        pinned to their observed machine — no freely-placeable literal. Every
        capability-eligible resource carries ``wip_fixed``.
      * a NON-resumable op gets a literal on EVERY capability-eligible resource
        (no calendar prune at literal-creation time — an empty calendar only
        makes the choice solve-infeasible, the literal still exists).
      * a RESUMABLE op (``is_effectively_resumable`` over ``total_min`` and
        ``min_chunk``) is pruned to capability ∩ calendar-feasible; a
        capability-eligible resource with no feasible window carries
        ``no_calendar_window``.

    Returns (pinnable_ids, dim_reasons). ``dim_reasons`` keys only the resources
    that are capability-eligible but NOT pinnable (so Tier-0 dims them with a
    truthful hover); capability-INeligible resources are simply absent from
    ``cap`` and Tier-0 already dims those as ``capability``.
    """
    from mre.modules.calendar_utils import is_effectively_resumable

    cap = capability_eligible(op.get("resource_requirements"), resources_by_id)

    wip = op.get("wip_status")
    if wip in ("complete", "in_progress"):
        return [], {rid: REASON_WIP_FIXED for rid in cap}

    def _min_chunk_min() -> int:
        raw = op.get("min_chunk")
        if not raw:
            return 0
        # ISO8601 duration → minutes (PT#S / PT#M / PT#H forms the model emits).
        from mre.modules.scenario import _parse_duration_minutes
        return int(_parse_duration_minutes(raw) or 0)

    resumable = is_effectively_resumable(
        op.get("splittable", False), total_min, _min_chunk_min()
    )
    if not resumable:
        return list(cap), {}

    pinnable: list[str] = []
    reasons: dict[str, str] = {}
    for rid in cap:
        rng = feasible_window_range(windows_by_res.get(rid, []), total_min, wp_earliest_min)
        if rng is None:
            reasons[rid] = REASON_NO_CALENDAR
        else:
            pinnable.append(rid)
    return pinnable, reasons
