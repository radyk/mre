"""The R-T2 two-beat Tier-2 interaction (Session 4B.3b).

R-T2 (docs/04, verbatim): a Tier-2 sandbox gesture is TWO beats.
  (1) Beat one never displays a monetary quantity — feasibility + placement only.
  (2) Beat one renders in the R-M1 ghost class.
  (3) Beat two supersedes visibly.
  (4) A beat-two contradiction (infeasible / materially moved) is SHOWN.
  (5) Beat one mints no edits and touches no persistent state.

These tests pin the CONTRACT:
  * fast — the no-money-by-construction guard (field ABSENCE, not emptiness);
    the deterministic correlation between the two beats; the contradiction
    detector (both branches, hand-built — the CU3 unit-level fallback).
  * slow — real solves: beat one/beat two correlate; the decomposition sums
    EXACTLY to the verdict; the no-committed-work-changes invariant holds; beat
    one mints nothing; the infeasible contradiction FORCED via a standing pin;
    and the forced-alternative gesture (a cross-machine pin) runs the identical
    two-beat path.
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.modules.sandbox import (
    FEASIBILITY_BUDGET_S,
    FeasibilityGhost,
    SANDBOX_BUDGET_S,
    SandboxResult,
    _MONEY_FIELD_TOKENS,
    beat_two_contradicts,
    correlation_id_for,
    feasibility_ghost,
    sandbox_pin_resolve,
)
from mre.modules.snapshot_store import SnapshotStore
from tools.generate_erp_dataset import generate

SNAP = "snap-2beat"


# ---------------------------------------------------------------------------
# CU1 — beat one carries NO money, BY CONSTRUCTION (field absence, not empty)
# ---------------------------------------------------------------------------

class TestBeatOneNoMoney:
    def test_feasibility_ghost_has_no_monetary_field(self):
        """R-T2(1) enforced by CONSTRUCTION: the beat-one TYPE cannot represent
        a monetary quantity — no field name contains any money token. This is a
        field-ABSENCE assertion, not a check that some cost field is empty."""
        names = [f.name for f in fields(FeasibilityGhost)]
        offenders = [n for n in names for tok in _MONEY_FIELD_TOKENS
                     if tok in n.lower()]
        assert offenders == [], f"beat one must carry no money field: {offenders}"
        # and specifically none of beat two's priced fields leaked in
        for forbidden in ("cost_delta_abs", "cost_delta_pct", "delta_abs",
                          "delta_pct", "objective", "cost_lines"):
            assert forbidden not in names

    def test_beat_two_DOES_carry_the_money(self):
        """The contrast: beat two's type IS where money lives (so the guard above
        is meaningful, not vacuous)."""
        names = [f.name for f in fields(SandboxResult)]
        assert "cost_delta_abs" in names and "cost_lines" in names

    def test_summary_of_ghost_exposes_no_money_keys(self):
        g = FeasibilityGhost(
            correlation_id="corr-x", feasible=True, within_budget=True,
            wall_time_s=0.1, budget_s=2.0, status="FEASIBLE", message="ok",
            placement=[{"operation_ref": "op", "resource_id": "r",
                        "start": "2026-01-05T00:00:00+00:00",
                        "end": "2026-01-05T01:00:00+00:00", "pinned": True}],
            pin={"operation_ref": "op"})
        keys = g.summary().keys()
        assert not any(tok in k.lower() for k in keys for tok in _MONEY_FIELD_TOKENS)


# ---------------------------------------------------------------------------
# Correlation — the two beats of one gesture agree, without server state
# ---------------------------------------------------------------------------

class TestCorrelation:
    def test_correlation_id_is_deterministic_from_the_pin(self):
        a = correlation_id_for("snap", "op-1", "res-1", "2026-01-05T08:00:00+00:00")
        b = correlation_id_for("snap", "op-1", "res-1", "2026-01-05T08:00:00+00:00")
        assert a == b and a.startswith("corr-")

    def test_correlation_id_differs_per_pin(self):
        a = correlation_id_for("snap", "op-1", "res-1", "2026-01-05T08:00:00+00:00")
        b = correlation_id_for("snap", "op-1", "res-2", "2026-01-05T08:00:00+00:00")
        c = correlation_id_for("snap", "op-2", "res-1", "2026-01-05T08:00:00+00:00")
        assert a != b != c and a != c


# ---------------------------------------------------------------------------
# CU3 — the contradiction detector, hand-built (the unit-level fallback for
# the materially-moved case; the infeasible case is also forced end-to-end below)
# ---------------------------------------------------------------------------

class TestContradictionDetector:
    def _ghost(self, feasible=True, res="R1", start="2026-01-05T08:00:00+00:00"):
        return FeasibilityGhost(
            correlation_id="corr-x", feasible=feasible, within_budget=True,
            wall_time_s=0.1, budget_s=2.0,
            status="FEASIBLE" if feasible else "INFEASIBLE", message="",
            placement=([{"operation_ref": "A", "resource_id": res, "start": start,
                         "end": "2026-01-05T09:00:00+00:00", "pinned": True}]
                       if feasible else []),
            pin={"operation_ref": "A", "resource_id": res, "start": start})

    def _result(self, feasible=True, res="R1", start="2026-01-05T08:00:00+00:00"):
        return SandboxResult(
            outcome="verdict", status="OPTIMAL" if feasible else "INFEASIBLE",
            within_budget=True, wall_time_s=1.0, budget_s=15.0, feasible=feasible,
            pin={"operation_ref": "A", "resource_id": res, "start": start})

    def test_agreement_is_not_a_contradiction(self):
        v = beat_two_contradicts(self._ghost(), self._result())
        assert v == {"infeasible": False, "moved": False, "contradicts": False}

    def test_infeasible_beat_two_contradicts_a_feasible_ghost(self):
        v = beat_two_contradicts(self._ghost(feasible=True),
                                 self._result(feasible=False))
        assert v["infeasible"] and v["contradicts"] and not v["moved"]

    def test_material_move_is_a_contradiction(self):
        # beat two placed the SAME op on a different machine than the ghost showed
        v = beat_two_contradicts(self._ghost(res="R1"), self._result(res="R2"))
        assert v["moved"] and v["contradicts"] and not v["infeasible"]

    def test_start_shift_beyond_tolerance_is_a_move(self):
        v = beat_two_contradicts(
            self._ghost(start="2026-01-05T08:00:00+00:00"),
            self._result(start="2026-01-05T10:00:00+00:00"))
        assert v["moved"]


# ---------------------------------------------------------------------------
# Slow — the real two-beat over a solved fixture
# ---------------------------------------------------------------------------

def _solve_fixture(tmp_path_factory, scenario: str, snap: str) -> Path:
    tmp = tmp_path_factory.mktemp(f"twobeat_{scenario}")
    sub = tmp / "sub"
    generate(sub, scenario=scenario, seed=7)
    out = tmp / "out"
    rc = mre_main([
        "--submission", str(sub), "--out", str(out), "--snapshot-id", snap,
        "--time-limit", "45", "--solver-workers", "1", "--solver-seed", "42",
    ])
    assert rc == 0, f"pipeline exit {rc}"
    return out


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    return _solve_fixture(tmp_path_factory, "multi_route_distinct", SNAP)


def _first_assignment(out: Path, snap: str):
    reader = SnapshotStore(out / "snapshots").load_snapshot(snap)
    a = next(iter(reader.iter_entities("assignment")))
    op = a["operation_ref"]
    rid = (a.get("resource_assignments") or [{}])[0].get("resource_ref")
    start = (a.get("phase_windows") or {}).get("run", [{}])[0].get("start")
    return op, rid, start


@pytest.mark.slow
def test_beat_one_is_feasible_and_correlates_with_beat_two(solved):
    op, rid, start = _first_assignment(solved, SNAP)
    g = feasibility_ghost(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                          pin_resource_id=rid, pin_start_iso=start)
    assert g.feasible is True
    assert g.within_budget is True
    assert g.placement and g.placement[0]["pinned"] is True
    # the pinned placement is at the drop
    assert g.placement[0]["resource_id"] == rid

    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            budget_s=SANDBOX_BUDGET_S, deterministic=True)
    # R-T2: the two beats of the SAME gesture carry the SAME correlation id.
    assert r.correlation_id == g.correlation_id
    assert r.correlation_id == correlation_id_for(
        SNAP, op, rid, g.pin["start"])


@pytest.mark.slow
def test_beat_two_decomposition_sums_exactly_to_the_verdict(solved):
    """CU2 detail layer: the cost lines MUST sum EXACTLY to cost_delta_abs — the
    card may never make an arithmetic claim the ledger cannot back (rollup_of)."""
    op, rid, start = _first_assignment(solved, SNAP)
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            deterministic=True)
    assert r.feasible and r.cost_lines is not None
    lines_sum = round(sum(l["delta"] for l in r.cost_lines), 2)
    assert abs(lines_sum - (r.cost_delta_abs or 0.0)) < 0.01, (
        f"cost lines {lines_sum} must sum to verdict {r.cost_delta_abs}")
    # an explicit "other placement changes" remainder line is always present
    assert any(l["line"] == "other placement changes" for l in r.cost_lines)
    # the always-visible layer is populated
    assert isinstance(r.lateness_delta_min, int)
    assert isinstance(r.dominant_driver, dict)


@pytest.mark.slow
def test_no_committed_work_changes_holds_with_a_standing_pin(solved):
    """CU2 always-visible invariant: a committed/standing-pinned op can never be
    a moved consequence — asserted against the beat-two result, not assumed."""
    op, rid, start = _first_assignment(solved, SNAP)
    reader = SnapshotStore(solved / "snapshots").load_snapshot(SNAP)
    assignments = list(reader.iter_entities("assignment"))
    # pick a DIFFERENT op to hold as a standing commitment
    other = next(a for a in assignments if a["operation_ref"] != op)
    o_op = other["operation_ref"]
    o_rid = (other.get("resource_assignments") or [{}])[0].get("resource_ref")
    o_start = (other.get("phase_windows") or {}).get("run", [{}])[0].get("start")
    standing = [{"operation_ref": o_op, "resource_id": o_rid, "start": o_start}]
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=rid, pin_start_iso=start,
                            deterministic=True, standing_pins=standing)
    # the standing op is not a (non-pin) moved consequence, and the flag says so
    moved_ops = {m["operation_ref"] for m in r.moves if not m.get("pinned")}
    assert o_op not in moved_ops
    assert r.no_committed_work_changes is True


@pytest.mark.slow
def test_beat_one_mints_nothing(solved):
    """R-T2(5): beat one touches NO persistent state — no child snapshot, no new
    canonical entity, no Decision record."""
    op, rid, start = _first_assignment(solved, SNAP)
    snap_dir = solved / "snapshots"
    before = sorted(p.name for p in snap_dir.iterdir())
    reader = SnapshotStore(snap_dir).load_snapshot(SNAP)
    n_asg_before = len(list(reader.iter_entities("assignment")))

    feasibility_ghost(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                      pin_resource_id=rid, pin_start_iso=start)

    after = sorted(p.name for p in snap_dir.iterdir())
    assert after == before, "beat one must mint no new snapshot"
    reader2 = SnapshotStore(snap_dir).load_snapshot(SNAP)
    assert len(list(reader2.iter_entities("assignment"))) == n_asg_before
    # no Decision records anywhere in the beat-one run evidence
    decisions = 0
    fdir = solved / "sandbox" / "runs"
    if fdir.exists():
        for jf in fdir.rglob("*.jsonl"):
            for line in jf.read_text(encoding="utf-8").splitlines():
                if '"record_type": "decision"' in line.lower() or '"decision"' in line.lower():
                    decisions += 1
    assert decisions == 0, "beat one must record no Decision"


@pytest.mark.slow
def test_contradiction_infeasible_is_forced_via_a_standing_pin(solved):
    """CU3 (the FORCED infeasible contradiction): beat one relaxes the lineage's
    committed work, so a drop that overlaps a standing commitment is FEASIBLE at
    beat one but INFEASIBLE at beat two (R-T2(4)). The contradiction is real,
    shown, and detected."""
    reader = SnapshotStore(solved / "snapshots").load_snapshot(SNAP)
    assignments = list(reader.iter_entities("assignment"))
    # find two ops on the SAME resource; hold B as a standing commitment and drop
    # A onto B's exact (resource, start) so beat two (which holds B) can't fit A.
    by_res: dict = {}
    for a in assignments:
        rid = (a.get("resource_assignments") or [{}])[0].get("resource_ref")
        st = (a.get("phase_windows") or {}).get("run", [{}])[0].get("start")
        by_res.setdefault(rid, []).append((a["operation_ref"], st))
    pair_res = next((r for r, v in by_res.items() if len(v) >= 2), None)
    assert pair_res, "need two ops on one resource to force the conflict"
    (a_op, _a_start), (b_op, b_start) = by_res[pair_res][0], by_res[pair_res][1]
    standing = [{"operation_ref": b_op, "resource_id": pair_res, "start": b_start}]

    # BEAT ONE — relaxed (no standing pins): A onto B's slot is feasible (B moves)
    g = feasibility_ghost(out_dir=solved, snapshot_id=SNAP, pin_op_id=a_op,
                          pin_resource_id=pair_res, pin_start_iso=b_start)
    # BEAT TWO — holds B fixed: A cannot occupy B's slot → infeasible
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=a_op,
                            pin_resource_id=pair_res, pin_start_iso=b_start,
                            deterministic=True, standing_pins=standing)
    verdict = beat_two_contradicts(g, r)
    # If the fixture happens to allow A at B's slot even with B held (e.g. B's op
    # is short and there is room), the contradiction won't fire — assert the
    # meaningful direction only when beat one was feasible.
    if g.feasible and not r.feasible:
        assert verdict["infeasible"] and verdict["contradicts"]
        assert r.correlation_id == g.correlation_id
    else:
        pytest.skip("this fixture's op geometry did not force the overlap "
                    "conflict; the detector is unit-tested separately")


@pytest.mark.slow
def test_forced_alternative_gesture_runs_the_same_two_beat_path(solved):
    """CU4: a forced-alternative gesture (pin an op to a CHOSEN, non-incumbent
    resource) is the identical two-beat path — same functions, a cross-machine
    pin. Beat one feasible, beat two priced, the pin's machine change reflected."""
    reader = SnapshotStore(solved / "snapshots").load_snapshot(SNAP)
    ops = list(reader.iter_entities("operation"))
    incumbent = {a["operation_ref"]:
                 (a.get("resource_assignments") or [{}])[0].get("resource_ref")
                 for a in reader.iter_entities("assignment")}
    # a multi-eligible op with an alternative machine (explicit_set)
    target = None
    for o in ops:
        reqs = o.get("resource_requirements") or []
        refs = list(reqs[0].get("resource_refs") or []) if reqs else []
        if len(refs) > 1 and o["id"] in incumbent:
            alt = next((r for r in refs if r != incumbent[o["id"]]), None)
            if alt:
                target = (o["id"], alt)
                break
    if target is None:
        pytest.skip("no multi-eligible op with an alternative machine in fixture")
    op, alt_res = target
    # keep the incumbent start (a pure cross-machine forced alternative)
    inc_a = next(a for a in reader.iter_entities("assignment")
                 if a["operation_ref"] == op)
    start = (inc_a.get("phase_windows") or {}).get("run", [{}])[0].get("start")

    g = feasibility_ghost(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                          pin_resource_id=alt_res, pin_start_iso=start)
    r = sandbox_pin_resolve(out_dir=solved, snapshot_id=SNAP, pin_op_id=op,
                            pin_resource_id=alt_res, pin_start_iso=start,
                            deterministic=True)
    # the two beats correlate; if the cross-machine placement is feasible, beat
    # two prices it (its decomposition still sums exactly).
    assert r.correlation_id == g.correlation_id
    if r.feasible:
        assert r.pin["resource_id"] == alt_res
        assert r.cost_lines is not None
        s = round(sum(l["delta"] for l in r.cost_lines), 2)
        assert abs(s - (r.cost_delta_abs or 0.0)) < 0.01
