#!/usr/bin/env python3
"""Session 4B.6c item 3 — THE COMPRESSOR (C), measured. SCRATCH ONLY.

C is a post-processor over an already-solved schedule: walk operations in
topological order and pull each as early as precedence, calendar, resource
availability, the frozen boundary and pins allow, WITHOUT changing the
sequence on any machine.

It is measured, not shipped. Nothing imports this from src/.

THE POINT of measuring rather than assuming (item 3c): setup is a function of
the op set alone and cannot move; production is duration-derived and cannot
move; tardiness can only fall. BUT ``production_overtime_cost`` is a separate
ledger line and a shifted op may land in a DEARER hour. So the FULL ledger is
recomputed after every accepted shift and a shift that raises total cost is
REJECTED and counted.

TWO VARIANTS, both reported:
  C_free    every free op movable, floored at the window origin. This is the
            variant comparable to what A2/A2h win INSIDE the solver, because
            the solver's tiebreak also moves ops that land in the frozen front.
  C_frozen  the frozen front is treated as COMMITTED (R-F1): those ops are
            fixed, and no movable op may be pulled to start before
            frozen_end. This is the shippable shape.

BOUNDS ASSERTED (item 3d):
  * no op crosses the frozen boundary into committed territory (C_frozen)
  * fixed ops (committed / resumable-chunked) do not move AT ALL
  * the compressed schedule is re-validated by PINNING every placement into a
    freshly-built window model and asking CP-SAT whether it is feasible — the
    model's own verdict, not the compressor's opinion of itself.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))


def min_lag_map(plant, free_ops):
    """(pred_op_id, succ_op_id) -> min_lag minutes, resolved exactly as
    SolverBuilder does (template edge keyed by spec_ref, per workpackage;
    _td_to_minutes FLOORS AT 1, a quirk the builder preserves deliberately)."""
    from mre.modules.solver_builder import _parse_td, _td_to_minutes
    by_wp_spec = {(o["workpackage_ref"], o["spec_ref"]): o["id"] for o in free_ops}
    wps = {o["workpackage_ref"] for o in free_ops}
    lags, maxlags = {}, 0
    for edge in plant.edges:
        lag = _td_to_minutes(_parse_td(edge.get("min_lag", "PT0S")))
        if edge.get("max_lag") is not None:
            maxlags += 1
        for wp in wps:
            p = by_wp_spec.get((wp, edge["predecessor"]))
            s = by_wp_spec.get((wp, edge["successor"]))
            if p and s:
                lags[(p, s)] = lag
    return lags, maxlags


def transition_matrix(plant):
    """The sequence-dependent setup matrix the builder reads (family -> family
    -> extra minutes, SolverBuilder:486-494). pilot_scale declares one, and it
    is what makes back-to-back placement on a machine ILLEGAL — the first thing
    a naive left-shift gets wrong (measured: a 15-minute family changeover)."""
    mat = {}
    for con in plant.constraints:
        if con.get("constraint_type") != "setup_transition":
            continue
        raw = con.get("parameters", {}).get("transition_minutes", {})
        for key, mins in raw.items():          # "familyA->familyB": minutes
            if "->" in key:
                frm, to = key.split("->")
                mat.setdefault(frm, {})[to] = int(mins)
        break
    return mat


def _earliest_fit(windows, lb, dur):
    """Earliest start >= lb such that [s, s+dur] lies wholly inside ONE working
    window. Mirrors the builder's containment rule for a non-resumable op
    (calendar gaps are blocking intervals under no_overlap)."""
    best = None
    for ws, we in windows:
        if we - ws < dur:
            continue
        s = max(ws, lb)
        if s + dur <= we:
            if best is None or s < best:
                best = s
    return best


def compress(plant, win, var_map, sv, free_ops, *, respect_frozen,
             ledger_of, base_total):
    """Return (new_solve_values, stats). ``ledger_of(sv)`` must return the FULL
    cost ledger for a candidate SolveValues (the real Extractor pass)."""
    fe = win["frozen_end_min"]
    floor = fe if respect_frozen else win["t0_min"]

    placed = [o for o in free_ops if o["id"] in sv.op_start_minutes]
    lags, n_maxlag = min_lag_map(plant, placed)
    if n_maxlag:
        raise RuntimeError(f"max_lag edges present ({n_maxlag}) — C's monotone "
                           "left-shift argument does not hold; refusing to run")

    chunked = {oid for oid, w in (sv.op_chunk_windows or {}).items() if w}
    start = dict(sv.op_start_minutes)
    end = dict(sv.op_end_minutes)
    res_of = dict(sv.op_resource)

    fixed = set(chunked)
    if respect_frozen:
        fixed |= {o["id"] for o in placed if start[o["id"]] < fe}
    frozen_original = {oid: (start[oid], end[oid]) for oid in fixed}

    preds = {}
    for (p, s) in lags:
        preds.setdefault(s, []).append(p)

    # machine sequence, from the ORIGINAL solution — never reordered
    by_res = {}
    for o in placed:
        by_res.setdefault(res_of[o["id"]], []).append(o["id"])
    for rid in by_res:
        by_res[rid].sort(key=lambda oid: (start[oid], oid))
    earlier_on_machine = {}
    for rid, seq in by_res.items():
        for i, oid in enumerate(seq):
            earlier_on_machine[oid] = seq[:i]

    # sequence-dependent setup: the constraint is PAIRWISE over every pair that
    # may share a resource, not just adjacent ones, so the bound is taken over
    # EVERY earlier op on the machine.
    mat = transition_matrix(plant)
    fam = {o["id"]: (o.get("setup_family") or "") for o in placed}
    stats_transition_pairs = sum(len(v) for v in mat.values())

    order = sorted((o["id"] for o in placed), key=lambda oid: (start[oid], oid))

    stats = {"moved": 0, "rejected_overtime": 0, "rejected_magnitude": 0.0,
             "fixed_ops": len(fixed), "chunked_ops": len(chunked),
             "considered": 0, "ledger_recomputes": 0,
             "transition_pairs": stats_transition_pairs,
             "sum_starts_before": sum(start[o["id"]] for o in placed)}

    cur_total = base_total
    for oid in order:
        if oid in fixed:
            continue
        stats["considered"] += 1
        dur = end[oid] - start[oid]
        lb = floor
        try:
            lb = max(lb, int(var_map.op_start[oid].proto.domain[0]))
        except Exception:
            pass
        for p in preds.get(oid, []):
            if p in end:
                lb = max(lb, end[p] + lags[(p, oid)])
        for q in earlier_on_machine.get(oid, ()):
            if q in end:
                lb = max(lb, end[q] + mat.get(fam.get(q, ""), {}).get(fam.get(oid, ""), 0))
        cand = _earliest_fit(var_map.cal_windows.get(res_of[oid], []), lb, dur)
        if cand is None or cand >= start[oid]:
            continue

        old_s, old_e = start[oid], end[oid]
        start[oid], end[oid] = cand, cand + dur
        trial = _rebuild(sv, start, end, res_of, plant, placed)
        led = ledger_of(trial)
        stats["ledger_recomputes"] += 1
        new_total = led.get("total_cost")
        if new_total is None or new_total > cur_total + 1e-9:
            # a shift into a dearer hour — REJECT it (item 3c)
            stats["rejected_overtime"] += 1
            stats["rejected_magnitude"] += (new_total - cur_total) if new_total else 0.0
            start[oid], end[oid] = old_s, old_e
            continue
        cur_total = new_total
        stats["moved"] += 1

    final = _rebuild(sv, start, end, res_of, plant, placed)

    # --- bounds, ASSERTED --------------------------------------------------
    for oid, (s0, e0) in frozen_original.items():
        assert start[oid] == s0 and end[oid] == e0, f"fixed op {oid} moved"
    if respect_frozen:
        for o in placed:
            oid = o["id"]
            if oid not in fixed:
                assert start[oid] >= fe, f"{oid} crossed the frozen boundary"
    for oid in start:
        assert res_of[oid] == sv.op_resource[oid], "C changed a machine"
    for rid, seq in by_res.items():
        srt = sorted(seq, key=lambda oid: (start[oid], oid))
        assert srt == seq, f"C reordered machine {rid}"

    stats["sum_starts_after"] = sum(start[o["id"]] for o in placed)
    stats["start_reduction_min"] = stats["sum_starts_before"] - stats["sum_starts_after"]
    stats["total_before"] = base_total
    stats["total_after"] = cur_total
    return final, stats


def _rebuild(sv, start, end, res_of, plant, placed):
    """A SolveValues carrying the shifted starts/ends, with wp_end_minutes
    recomputed (tardiness is derived from it, so it must move with the ops)."""
    new = copy.copy(sv)
    new.op_start_minutes = dict(start)
    new.op_end_minutes = dict(end)
    new.op_resource = dict(res_of)
    wp_end = dict(sv.wp_end_minutes)
    ends = {}
    for o in placed:
        wp = o["workpackage_ref"]
        ends[wp] = max(ends.get(wp, 0), end[o["id"]])
    wp_end.update(ends)
    new.wp_end_minutes = wp_end
    return new


def validate(plant, win, placements):
    """Pin every placement into a FRESHLY BUILT window model and ask CP-SAT
    whether the compressed schedule is feasible. The model's verdict, not the
    compressor's. Returns the status string."""
    from mre.modules.rolling_horizon import _build_window
    from mre.modules import standing_pins as sp
    from ortools.sat.python import cp_model as cp

    free_ops = win["free_ops"]
    model, var_map = _build_window(plant, free_ops, [], win["ref"],
                                   win["win_horizon_end"])
    for op in free_ops:
        oid = op["id"]
        if oid not in placements:
            continue
        rid, s = placements[oid]
        sp.apply_pin(model, var_map, oid, rid, int(s))
    model.clear_objective()
    solver = cp.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 600.0
    st = solver.Solve(model)
    return {cp.OPTIMAL: "OPTIMAL", cp.FEASIBLE: "FEASIBLE",
            cp.INFEASIBLE: "INFEASIBLE"}.get(st, "UNKNOWN")
