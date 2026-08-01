"""Session 4B.6 — THE COARSE ZONE (R-SC2 amendment).

Written from the amendment text (docs/04, 2026-07-27), clause by clause:

  (1) RELAXATION, ALWAYS      — the relaxation guard + its NEGATIVE CONTROL
  (2) TWO DIFFERENT RUNS      — only a complete proof-run INFEASIBLE proves
                                anything; a derated run CAN declare infeasible
                                what the fine model places (necessity, shown
                                rather than asserted)
  (3) rho IS DECLARED         — read from the cost model, provenance recorded,
                                never a constant
  (5) TWO LEDGERS             — coarse tardiness is buckets; no currency exists
                                on the coarse surface at all
  (6) NEVER A BAR             — the document carries density cells, not
                                assignments
  + DETERMINISM, cross-hashseed (not same-seed-both-sides)
  + the 4B.3a COMPLETENESS INVARIANT still passes unchanged
  + (B) a NON-TRIVIAL beyond-horizon set: a coarse zone tested over an empty
    tray is a green suite that could not have failed
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mre.modules.coarse_horizon import (
    BINDING_UTILIZATION, Bucket, CoarseCoefficients, build_buckets,
    build_coarse_zone, bucket_capacity_minutes, coarse_allocation_violations,
    coarse_scope_for_guard, map_fine_placements_to_coarse,
)

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)

# (B) The beyond-horizon set the coarse zone is exercised over must be
# NON-TRIVIAL, and the count is stated in the close-out. Below this floor the
# suite would be green for the wrong reason.
MIN_BEYOND_DEMANDS = 10
MIN_COARSE_OPS = 25


# ---------------------------------------------------------------------------
# fast unit — the declared coefficients (clause 3)
# ---------------------------------------------------------------------------

class TestDeclaredCoefficients:
    """CLAUSE (3): rho is a DECLARED IDS coefficient, never a constant in solver
    code, and a defaulted value can never read as a customer's choice."""

    def test_absent_coefficients_default_and_say_so(self):
        c = CoarseCoefficients.from_cost_model({})
        assert c.capacity_derate == 1.0 and not c.capacity_derate_declared
        assert c.bucket_days == 7 and not c.bucket_days_declared
        block = c.certificate_block()
        assert block["coarse_capacity_derate_provenance"] == "defaulted"
        assert block["coarse_bucket_days_provenance"] == "defaulted"

    def test_declared_coefficients_are_carried_with_declared_provenance(self):
        c = CoarseCoefficients.from_cost_model(
            {"coarse_bucket_days": 14, "coarse_capacity_derate": 0.85})
        assert c.bucket_days == 14 and c.bucket_days_declared
        assert c.capacity_derate == 0.85 and c.capacity_derate_declared
        block = c.certificate_block()
        assert block["coarse_capacity_derate"] == 0.85
        assert block["coarse_capacity_derate_provenance"] == "declared"

    def test_default_is_a_no_op_derate(self):
        """An undeclared plant must get NO invented margin: the defaulted rho is
        1.0, so nothing is silently shaved off its capacity."""
        assert CoarseCoefficients.from_cost_model({}).capacity_derate == 1.0

    def test_out_of_band_values_fall_back_and_lose_declared_status(self):
        for bad in (0.0, -0.5, 1.5, "nonsense"):
            c = CoarseCoefficients.from_cost_model({"coarse_capacity_derate": bad})
            assert c.capacity_derate == 1.0
            assert not c.capacity_derate_declared, (
                f"{bad!r} must not be recorded as a declared coefficient")

    def test_certificate_block_carries_no_currency(self):
        """CLAUSE (5): there is no coarse currency figure anywhere, so nothing
        can be summed into a fine ledger by accident."""
        block = CoarseCoefficients.from_cost_model({}).certificate_block()
        assert not [k for k in block if "cost" in k or "dollar" in k]


# ---------------------------------------------------------------------------
# fast unit — the bucket grid and the calendar-as-a-number
# ---------------------------------------------------------------------------

class TestBucketsAndCapacity:

    def test_buckets_span_window_end_to_last_due(self):
        buckets = build_buckets(REF, REF + timedelta(days=20), 7)
        assert buckets[0].start == REF
        assert len(buckets) == 3                     # ceil(20/7)
        assert all(b.end - b.start == timedelta(days=7) for b in buckets)
        assert [b.index for b in buckets] == [0, 1, 2]

    def test_tail_extends_the_grid(self):
        base = build_buckets(REF, REF + timedelta(days=20), 7)
        tailed = build_buckets(REF, REF + timedelta(days=20), 7, tail_buckets=4)
        assert len(tailed) == len(base) + 4

    def test_capacity_is_real_working_minutes_not_wall_clock(self):
        """The calendar is NOT dropped; it enters as a NUMBER. A 5-day 07:00-19:00
        calendar gives 5x720 = 3600 min/week, not 7x1440."""
        cal = {"id": "cal-1", "base_pattern": {
            "weekdays": [0, 1, 2, 3, 4], "shift_start": "07:00",
            "shift_end": "19:00"}, "exceptions": []}
        res = [{"id": "R1", "calendar_ref": "cal-1"}]
        monday = datetime(2026, 1, 5, tzinfo=UTC)     # a Monday
        buckets = build_buckets(monday, monday + timedelta(days=7), 7)
        cap = bucket_capacity_minutes(res, [cal], buckets)
        assert cap[("R1", 0)] == 5 * 720
        assert cap[("R1", 0)] < 7 * 1440              # never a nominal 7x24

    def test_missing_calendar_is_permissive_not_zero(self):
        """A resource with no resolvable calendar gets FULL wall-clock minutes.
        Zero would TIGHTEN the coarse model and could make it infeasible where
        the fine model is feasible — a direct clause (1) violation."""
        res = [{"id": "R1"}]
        buckets = build_buckets(REF, REF + timedelta(days=7), 7)
        cap = bucket_capacity_minutes(res, [], buckets)
        assert cap[("R1", 0)] == 7 * 1440


# ---------------------------------------------------------------------------
# the plant (shared, module-scoped: every coarse test needs a real tray)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plant(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant
    d = tmp_path_factory.mktemp("coarse")
    generate(d / "sub", scenario="pilot_scale", orders=40, seed=1)
    return prepare_plant(d / "sub", d / "prep", reference_date=REF)


@pytest.fixture(scope="module")
def view(plant):
    from mre.modules.rolling_horizon import build_rolling_view
    return build_rolling_view(plant, window_days=7, frozen_days=2, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=8.0, det_total=3.0)


@pytest.fixture(scope="module")
def zone(plant, view):
    return build_coarse_zone(
        plant, view, coefficients=CoarseCoefficients(7, 1.0, True, True),
        deterministic=True, seed=42, det_time=2.0, safety_ceiling_s=60.0)


# ---------------------------------------------------------------------------
# (B) the coarse zone must have work to do
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_beyond_horizon_set_is_non_trivial(view, zone):
    """(B) A coarse zone tested over an empty or near-empty set is a green suite
    that could not have failed. The counts are asserted here and STATED in the
    close-out."""
    n_demands = len(view.beyond_demand_ids)
    n_ops = zone.proof.n_ops_modeled + len(zone.proof.unmodelable)
    assert n_demands >= MIN_BEYOND_DEMANDS, (
        f"only {n_demands} beyond-horizon demands — the coarse zone has "
        f"nothing to do and this suite proves nothing")
    assert n_ops >= MIN_COARSE_OPS, f"only {n_ops} coarse ops in scope"
    print(f"\n[4B.6 CU4/B] beyond-horizon demands={n_demands} "
          f"coarse ops in scope={n_ops} modeled={zone.proof.n_ops_modeled} "
          f"unmodelable={len(zone.proof.unmodelable)}")


# ---------------------------------------------------------------------------
# CU4 — THE RELAXATION GUARD (clause 1) + its negative control
# ---------------------------------------------------------------------------

def _guard_inputs(plant, demand_ids, bucket_days=7, rho=1.0):
    """Build the coarse grid from the REFERENCE ORIGIN (not the window end) so a
    whole fine schedule maps into it — the theorem is about the coarse model's
    structure, not about where the grid happens to start."""
    ref = plant.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    demands_by_id = {d["id"]: d for d in plant.demands}
    dues = [datetime.fromisoformat(demands_by_id[d]["due"]).replace(tzinfo=UTC)
            if datetime.fromisoformat(demands_by_id[d]["due"]).tzinfo is None
            else datetime.fromisoformat(demands_by_id[d]["due"])
            for d in demand_ids if demands_by_id.get(d, {}).get("due")]
    buckets = build_buckets(ref, max(dues) if dues else None, bucket_days,
                            tail_buckets=26)     # half a year of tail: the guard
    #                                              must never fail for lack of room
    return buckets, coarse_scope_for_guard(plant, demand_ids, buckets, rho)


@pytest.mark.slow
def test_relaxation_guard_fine_feasible_maps_to_coarse_feasible(plant):
    """CLAUSE (1) AS A THEOREM. Take a FINE-FEASIBLE schedule from an existing
    scenario, map it to a coarse allocation, and assert coarse feasibility at
    rho = 1.0. This is what fails loudly the day someone tightens the coarse
    model to make its output look tidier."""
    from mre.modules.rolling_horizon import reference_solve

    _led, _svc, _drv, _tot, placements = reference_solve(
        plant, seed=42, deterministic=True, det_time=3.0)
    assert placements, "reference solve produced no placements"

    demand_ids = [d["id"] for d in plant.schedulable_demands]
    buckets, g = _guard_inputs(plant, demand_ids)

    # exclude what the coarse model cannot represent — COUNTED, never silently
    # skipped (the excluded class is a named finding of this session)
    excluded = {u.op_id for u in g["unmodelable"]}
    fine = {oid: pl for oid, pl in placements.items() if oid not in excluded}
    alloc = map_fine_placements_to_coarse(fine, buckets)
    assert alloc, "nothing mapped — the guard would prove nothing"

    viol = coarse_allocation_violations(
        alloc, minutes_of=g["minutes_of"], eligible_of=g["eligible_of"],
        cap=g["cap"], buckets=buckets, rho=1.0, edges=g["edges"])
    print(f"\n[4B.6 CU4] guard: mapped {len(alloc)} ops, excluded "
          f"{len(excluded)} unmodelable, {len(viol)} violations")
    assert viol == [], (
        "CLAUSE (1) BROKEN — a fine-feasible schedule did not map to a "
        f"coarse-feasible allocation:\n  " + "\n  ".join(viol[:8]))


@pytest.mark.slow
def test_relaxation_guard_negative_control_goes_red(plant):
    """THE PRICE-BOUGHT-SOMETHING RULE, applied to the guard itself. Stub a
    tightening into the coarse model and prove the guard goes RED. A green guard
    that could never have failed is worth what it cost."""
    from mre.modules.rolling_horizon import reference_solve

    _led, _svc, _drv, _tot, placements = reference_solve(
        plant, seed=42, deterministic=True, det_time=3.0)
    demand_ids = [d["id"] for d in plant.schedulable_demands]
    buckets, g = _guard_inputs(plant, demand_ids)
    excluded = {u.op_id for u in g["unmodelable"]}
    alloc = map_fine_placements_to_coarse(
        {o: p for o, p in placements.items() if o not in excluded}, buckets)

    # THE TIGHTENING: a hidden capacity haircut — precisely the "safety margin"
    # someone adds to make coarse output look tidier, and precisely what clause
    # (1) forbids without a declaration.
    viol = coarse_allocation_violations(
        alloc, minutes_of=g["minutes_of"], eligible_of=g["eligible_of"],
        cap=g["cap"], buckets=buckets, rho=1.0, edges=g["edges"],
        _capacity_scale=0.05)
    assert viol, (
        "NEGATIVE CONTROL FAILED — the guard stayed green under a 20x capacity "
        "tightening, so its green verdict means nothing")
    assert any(v.startswith("capacity:") for v in viol)
    print(f"\n[4B.6 CU4 negative control] guard went red with {len(viol)} "
          f"violations under a stubbed tightening — the guard can fail")


@pytest.mark.slow
def test_derated_run_can_declare_a_fine_feasible_instance_infeasible(plant):
    """CLAUSE (2)'s NECESSITY, demonstrated rather than asserted: rho < 1 CAN
    declare infeasible an instance the fine model places. This is exactly why
    the derated run may never be cited as a proof of infeasibility."""
    from mre.modules.rolling_horizon import build_rolling_view

    v = build_rolling_view(plant, window_days=7, frozen_days=2, gravity=True,
                           deterministic=True, seed=42, member_time_limit_s=8.0,
                           det_total=3.0)
    # rho = 0.15 on this plant: measured to leave 80 of 83 ops MODELED (so the
    # verdict is a real aggregate-capacity refutation, not an artifact of ops
    # dropping out as unmodelable) while the proof run at rho = 1.0 places the
    # same book comfortably.
    z = build_coarse_zone(
        plant, v, coefficients=CoarseCoefficients(7, 0.15, True, True),
        deterministic=True, seed=42, det_time=2.0, safety_ceiling_s=60.0)

    assert z.proof.placed, "the proof run must place this book at rho = 1.0"
    assert z.planning.status == "INFEASIBLE", (
        f"expected a derated INFEASIBLE, got {z.planning.status} — clause (2)'s "
        f"necessity is not demonstrated on this instance")
    assert z.planning.n_ops_modeled >= 0.9 * z.proof.n_ops_modeled, (
        "too many ops left the model as unmodelable: the INFEASIBLE would be "
        "about the leftovers, not about aggregate capacity")
    # and whatever it said, it proves NOTHING (clause 2)
    assert not z.planning.proves_infeasible, (
        "a PLANNING run claimed to prove infeasibility — clause (2) violated")
    print(f"\n[4B.6 CU4] rho=0.15 planning run: status={z.planning.status} "
          f"modeled={z.planning.n_ops_modeled} (proof modeled "
          f"{z.proof.n_ops_modeled}) proves_infeasible={z.planning.proves_infeasible}")


@pytest.mark.slow
def test_derate_effect_is_non_monotonic_because_unmodelable_ops_leave(plant, view):
    """A measured property worth pinning, not a bug: LOWERING rho does not
    monotonically tighten the model. Below a threshold, ops stop fitting in ANY
    single derated bucket, become ``exceeds_bucket_capacity`` unmodelable, and
    LEAVE the model — so a smaller rho can be satisfiable where a larger one was
    INFEASIBLE. Measured on this plant: rho 0.20 OPTIMAL, 0.15 INFEASIBLE, 0.10
    OPTIMAL with 19 ops gone.

    This is exactly why the unmodelable set is NAMED and COUNTED rather than
    silently dropped: without the count, the 0.10 result would read as "it
    fits"."""
    seen = {}
    for rho in (0.20, 0.15, 0.10):
        z = build_coarse_zone(
            plant, view, coefficients=CoarseCoefficients(7, rho, True, True),
            deterministic=True, seed=42, det_time=2.0, safety_ceiling_s=60.0)
        seen[rho] = (z.planning.status, z.planning.n_ops_modeled,
                     sum(1 for u in z.planning.unmodelable
                         if u.reason == "exceeds_bucket_capacity"))
    print(f"\n[4B.6] rho ladder (status, modeled, exceeds_bucket): {seen}")
    assert seen[0.15][0] == "INFEASIBLE"
    assert seen[0.10][2] > seen[0.15][2], (
        "the lower rho did not push more ops out as unmodelable — the "
        "non-monotonicity explanation no longer holds and must be re-derived")


# ---------------------------------------------------------------------------
# clause (2) — the proof/planning seal
# ---------------------------------------------------------------------------

class TestProofPlanningSeal:
    """CLAUSE (2): the negative may be claimed ONLY from a complete proof run."""

    def _run(self, **kw):
        from mre.modules.coarse_horizon import CoarseRun
        base = dict(label="proof", rho=1.0, status="INFEASIBLE", objective=None,
                    wall_truncated=False)
        base.update(kw)
        return CoarseRun(**base)

    def test_complete_proof_infeasible_proves(self):
        assert self._run().proves_infeasible

    def test_planning_infeasible_never_proves(self):
        assert not self._run(label="planning", rho=0.8).proves_infeasible

    def test_wall_truncated_proof_never_proves(self):
        """A wall-truncated solve is a lottery wearing a determinism label; its
        INFEASIBLE is not a completed refutation."""
        assert not self._run(wall_truncated=True).proves_infeasible

    def test_feasible_proof_never_proves(self):
        assert not self._run(status="FEASIBLE").proves_infeasible


# ---------------------------------------------------------------------------
# DETERMINISM — cross-hashseed, not same-seed-both-sides
# ---------------------------------------------------------------------------

_DET_SCRIPT = r'''
import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / "tools"))
from generate_erp_dataset import generate
from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
from mre.modules.coarse_horizon import build_coarse_zone, CoarseCoefficients

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
out = Path(sys.argv[1])
if not (out / "sub" / "manifest.json").exists():
    generate(out / "sub", scenario="pilot_scale", orders=40, seed=1)
plant = prepare_plant(out / "sub", out / "prep", reference_date=REF)
view = build_rolling_view(plant, window_days=7, frozen_days=2, gravity=True,
                          deterministic=True, seed=42, member_time_limit_s=8.0,
                          det_time=1.0)
z = build_coarse_zone(plant, view,
                      coefficients=CoarseCoefficients(7, 0.8, True, True),
                      deterministic=True, seed=42, det_time=2.0,
                      safety_ceiling_s=60.0)
digest = {
    "proof": sorted((p.op_id, p.bucket_index, p.resource_witness)
                    for p in z.proof.placements),
    "planning": sorted((p.op_id, p.bucket_index, p.resource_witness)
                       for p in z.planning.placements),
    "cert": z.certificate_block(),
}
print("<<<" + json.dumps(digest, sort_keys=True) + ">>>")
'''


@pytest.mark.slow
def test_coarse_zone_is_deterministic_across_hashseeds(tmp_path):
    """A SECOND CP-SAT model is a SECOND opportunity for the hash-order leak
    class (three found and fixed in the 2026-07-26 errand). Tested CROSS-HASHSEED
    — same-seed-both-sides would pass even with the leak present."""
    script = tmp_path / "det.py"
    script.write_text(_DET_SCRIPT, encoding="utf-8")
    digests = []
    for hashseed in ("0", "1", "2"):
        work = tmp_path / f"hs{hashseed}"
        work.mkdir()
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hashseed
        r = subprocess.run([sys.executable, str(script), str(work), str(REPO)],
                           cwd=REPO, env=env, capture_output=True, text=True,
                           timeout=900)
        assert r.returncode == 0, f"hashseed {hashseed} failed:\n{r.stderr[-3000:]}"
        raw = r.stdout.split("<<<")[1].split(">>>")[0]
        digests.append(json.loads(raw))
    assert digests[0] == digests[1] == digests[2], (
        "the coarse zone moved with PYTHONHASHSEED — an iteration order is "
        "unsorted somewhere in the model build")


# ---------------------------------------------------------------------------
# the document (contract 1.9) — clauses (5) and (6), and 4B.3a unchanged
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestCoarseDocument:

    @pytest.fixture(scope="class")
    def doc(self, plant, view, zone):
        from mre.modules.schedule_assembler import assemble_rolling_document
        identity_map = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        return assemble_rolling_document(
            plant=plant, view=view, schedule_id="sched-coarse", run_id="run-c",
            identity_map=identity_map, coarse_zone=zone)

    def test_contract_is_1_9_and_the_zone_is_present(self, doc):
        assert doc.contract_version == "1.13"
        assert doc.rolling is not None and doc.rolling.coarse_zone is not None

    def test_completeness_invariant_passes_unchanged(self, plant, view, doc):
        """The 4B.3a invariant is the GUARD on unmodelable ops: an op the coarse
        model cannot represent keeps its demand's beyond-horizon disposition, so
        the counting test must pass EXACTLY as before. Not weakened."""
        wp_of_op = {o["id"]: o.get("workpackage_ref", "") for o in plant.operations}
        dem_of_wp: dict = {}
        for f in plant.fulfillments:
            dem_of_wp.setdefault(f.get("workpackage_ref", ""), []).append(
                f.get("demand_ref"))
        placed = set()
        for oid in view.placed:
            placed.update(dem_of_wp.get(wp_of_op.get(oid, ""), []))
        tray = {b.demand_ref for b in doc.rolling.beyond_horizon}
        assert not (placed & tray)
        assert placed | tray == {d["id"] for d in plant.schedulable_demands}

    def test_earliest_window_estimate_is_untouched(self, plant, view, doc):
        """The 4B.6 pre-flight found this field already populated by a due-date
        backoff heuristic. The coarse bucket sits BESIDE it, never on top of it
        (CLAUDE.md: add, never repurpose)."""
        from mre.modules.schedule_assembler import _earliest_window_estimate
        working = plant.demand_working_minutes
        demands = {d["id"]: d for d in plant.demands}
        ref = view.reference_origin
        checked = 0
        for item in doc.rolling.beyond_horizon:
            expected = _earliest_window_estimate(
                demands[item.demand_ref], int(working.get(item.demand_ref, 0)), ref)
            assert item.earliest_window_estimate == expected
            checked += 1
        assert checked > 0

    def test_tray_entries_carry_a_coarse_placement(self, doc):
        placed = [b for b in doc.rolling.beyond_horizon if b.coarse is not None]
        assert placed, "no tray entry got a coarse placement"
        for b in placed:
            assert b.coarse.run_label in ("proof", "planning")
            assert b.coarse.sub_disposition in ("coarsely_placed",
                                                "coarse_unmodelable")
            if b.coarse.sub_disposition == "coarse_unmodelable":
                assert b.coarse.unmodelable_reason, "unmodelable without a reason"

    def test_clause_5_no_coarse_currency_anywhere(self, doc):
        """TWO LEDGERS, NEVER FUSED — enforced by SHAPE: there is no currency
        field on the coarse surface, so no caller can sum coarse into
        cost_summary even by accident."""
        blob = json.dumps(doc.rolling.coarse_zone.model_dump(mode="json"))
        assert "cost" not in blob and "currency" not in blob
        for b in doc.rolling.beyond_horizon:
            if b.coarse:
                assert not [f for f in type(b.coarse).model_fields
                            if "cost" in f]

    def test_clause_6_coarse_renders_as_load_not_bars(self, doc):
        """BARS MEAN PLACEMENT. Coarse output is a density band; no coarse op
        appears in assignments[], and every density cell carries load AND cap so
        the reader checks the arithmetic."""
        cz = doc.rolling.coarse_zone
        assert cz.density, "no density band"
        for cell in cz.density:
            assert cell.capacity_minutes >= 0 and cell.load_minutes >= 0
            if cell.capacity_minutes:
                assert abs(cell.utilization
                           - cell.load_minutes / cell.capacity_minutes) < 1e-9
        tray_ids = {b.demand_ref for b in doc.rolling.beyond_horizon}
        wp_orders = {a.workpackage_ref for a in doc.assignments}
        assert not (tray_ids & wp_orders)     # a tray demand never gets a bar

    def test_binding_cells_are_at_or_near_capacity(self, doc):
        for cell in doc.rolling.coarse_zone.binding_cells:
            assert cell.load_minutes >= BINDING_UTILIZATION * cell.capacity_minutes

    def test_rho_appears_with_its_provenance(self, doc):
        """ACCEPTANCE 6: rho appears in the certificate/document. A hidden
        default is a failure."""
        cz = doc.rolling.coarse_zone
        assert cz.capacity_derate == 1.0
        assert cz.capacity_derate_provenance == "declared"
        assert cz.bucket_days == 7


@pytest.mark.slow
def test_monolithic_document_has_no_coarse_block(plant):
    """HARD ACCEPTANCE: a monolithic solve has no beyond-horizon set, so the
    block is simply ABSENT — the 1.9 addition is invisible on that path."""
    from mre.modules.schedule_assembler import assemble_rolling_document
    # the rolling assembler is the only producer of a RollingBlock; a monolithic
    # document's ``rolling`` is None, so coarse_zone is unreachable by
    # construction. Assert the structural fact rather than re-solving.
    from mre.contracts.schedule_document import ScheduleDocument
    assert "coarse_zone" not in ScheduleDocument.model_fields
    assert ScheduleDocument.model_fields["rolling"].default is None
    del plant, assemble_rolling_document


# ---------------------------------------------------------------------------
# CU3 — the prediction store
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestPredictionStore:

    def test_predictions_round_trip(self, tmp_path, zone):
        from mre.modules.coarse_predictions import (
            CoarsePredictionStore, predictions_from_zone,
        )
        preds = predictions_from_zone(zone, run_id="run-1",
                                      predicted_at=REF)
        assert preds, "no predictions minted"
        store = CoarsePredictionStore(tmp_path / "run")
        assert store.record_predictions(preds) == len(preds)
        back = store.predictions()
        assert len(back) == len(preds)
        assert {p.key() for p in back} == {p.key() for p in preds}

    def test_mirrored_planning_run_is_not_double_counted(self, zone):
        """With rho == 1.0 the planning model is byte-identical to the proof
        model and is COPIED, not re-solved. Recording it as an independent
        prediction would double-count the proof run in every error bar."""
        from mre.modules.coarse_predictions import predictions_from_zone
        assert zone.planning.mirrors_proof
        preds = predictions_from_zone(zone, run_id="run-1", predicted_at=REF)
        assert {p.run_label for p in preds} == {"proof"}

    def test_realizations_capture_both_intake_paths(self, tmp_path, plant, view,
                                                    zone):
        from mre.modules.coarse_predictions import (
            INTAKE_GRAVITY_ADMISSION, INTAKE_NATURAL_ROLL,
            CoarsePredictionStore, predictions_from_zone,
            realizations_from_view,
        )
        preds = predictions_from_zone(zone, run_id="run-1", predicted_at=REF)
        # a later roll: pretend the tray work landed in THIS view's placements
        # for whichever ops overlap, and mark half the demands gravity-admitted
        gravity = set(sorted(view.beyond_demand_ids)[:len(view.beyond_demand_ids) // 2])
        reals = realizations_from_view(preds, view, plant,
                                       realizing_run_id="run-2",
                                       gravity_admitted_demand_ids=gravity,
                                       realized_at=REF)
        store = CoarsePredictionStore(tmp_path / "run2")
        store.record_realizations(reals)
        paths = {r.intake_path for r in store.realizations()}
        assert paths <= {INTAKE_NATURAL_ROLL, INTAKE_GRAVITY_ADMISSION}

    def test_report_names_what_it_cannot_compute(self, zone):
        """The skeleton must SAY when a figure is undefined rather than print a
        confident 0 — the couldn't-answer discipline, applied to a report."""
        from mre.modules.coarse_predictions import build_conformance_report
        rep = build_conformance_report([], [])
        assert rep.realized_fraction is None
        assert any("undefined" in n for n in rep.notes)
        assert rep.cost_error_sign is None
        assert any("clause 5" in n for n in rep.notes)


# ---------------------------------------------------------------------------
# clause (4) — coarse never constrains fine, nor its admission policy
# ---------------------------------------------------------------------------

def test_coarse_output_is_not_read_by_admission_or_the_window_build():
    """CLAUSE (4), enforced as an IMPORT-DIRECTION fact: rolling_horizon must
    not import coarse_horizon. The dependency runs one way only, so coarse
    output cannot reach gravity's criticality read or the window solve."""
    src = (REPO / "src" / "mre" / "modules" / "rolling_horizon.py").read_text(
        encoding="utf-8")
    assert "coarse_horizon" not in src, (
        "rolling_horizon imports coarse_horizon — clause (4) broken: the window "
        "solve must re-decide from scratch and gravity must not consume coarse "
        "output. Unlock condition: revisit only once the conformance report "
        "shows coarse bucket-tardiness is calibrated.")


# ---------------------------------------------------------------------------
# (C) the disposition seam the 4B.6 pre-flight found
# ---------------------------------------------------------------------------

def test_no_rolling_path_site_writes_excluded_demand_ids():
    """PRE-FLIGHT (1), LOCKED WHILE IT IS TRUE. The rolling path READS the
    validator's ``excluded_demand_ids`` and never writes it: exclusion is
    decided in gate/validator territory, and the rolling path only classifies
    what survives into committed / active / beyond-horizon.

    That distinction is load-bearing for the coarse zone (beyond-horizon =
    schedulable − placed) and nothing tested it. This fails loudly the day
    someone files horizon work as exclusion — which is exactly what the
    monolithic ``--horizon-days`` path does (docs/07 carry-forward)."""
    src = (REPO / "src" / "mre" / "modules" / "rolling_horizon.py").read_text(
        encoding="utf-8")
    offenders = []
    for i, line in enumerate(src.splitlines(), 1):
        s = line.strip()
        if s.startswith("#") or "excluded_demand_ids" not in s:
            continue
        # a WRITE is an .add(/.update(/.discard( on the set, or an assignment
        # into it. Reads (comparisons, passing it along, the dataclass field,
        # constructing the plant from the validator's result) are legitimate.
        if (".excluded_demand_ids.add(" in s
                or ".excluded_demand_ids.update(" in s
                or ".excluded_demand_ids.discard(" in s
                or ".excluded_demand_ids.remove(" in s):
            offenders.append(f"{i}: {s}")
    assert offenders == [], (
        "the rolling path now WRITES excluded_demand_ids — horizon work is "
        "being filed as a data-defect exclusion:\n  " + "\n  ".join(offenders))


# ---------------------------------------------------------------------------
# CU5 — REACHABILITY (R-AI1): the three questions the coarse zone must answer
# ---------------------------------------------------------------------------

class TestCoarseAnswers:
    """The answers are authored, ID-free where the planner speaks, and carry the
    clause discipline in their WORDING — a coarse figure is never voiced as a
    placement, and a coarse placement is never voiced as a yes."""

    def _doc(self, **cz):
        base = {
            "bucket_days": 7, "bucket_days_provenance": "declared",
            "capacity_derate": 0.8, "capacity_derate_provenance": "declared",
            "buckets": [{"index": 0, "start": "2026-01-12T00:00:00+00:00",
                         "end": "2026-01-19T00:00:00+00:00"},
                        {"index": 1, "start": "2026-01-19T00:00:00+00:00",
                         "end": "2026-01-26T00:00:00+00:00"}],
            "proof_status": "OPTIMAL", "planning_status": "OPTIMAL",
            "planning_mirrors_proof": False, "infeasibility_proven": False,
            "tardiness_buckets_total": 0, "figures_are_upper_bounds": False,
            "wall_truncated": False, "unmodelable_count": 0,
            "density": [], "binding_cells": [],
        }
        base.update(cz)
        return {"rolling": {"beyond_horizon": [{"work_order": "ORD-9",
                                                "due": "2026-01-30T00:00:00+00:00"}],
                            "coarse_zone": base}}

    def test_will_it_fit_never_converts_a_placement_into_a_yes(self):
        """CLAUSE (1): only the NEGATIVE is claimed. A coarse model that places
        the book proves nothing about the fine model, and the answer must say so
        instead of answering 'yes'."""
        from mre.modules.rolling_questions import answer_coarse_fit
        body = answer_coarse_fit(self._doc())
        assert "NOT a promise" in body
        assert "never that it does" in body
        assert not body.lower().startswith("yes")

    def test_a_proven_negative_names_the_resource_week(self):
        """CLAUSE (2): a COMPLETE proof-run INFEASIBLE is a refutation, and the
        answer names the resource-week that proves it."""
        from mre.modules.rolling_questions import answer_coarse_fit
        body = answer_coarse_fit(self._doc(
            infeasibility_proven=True, proof_status="INFEASIBLE",
            binding_cells=[{"resource_id": "MILL-01", "bucket_index": 1,
                            "load_minutes": 3600, "capacity_minutes": 2880,
                            "utilization": 1.25}]))
        assert body.startswith("No")
        assert "MILL-01" in body and "week of 2026-01-19" in body
        assert "3600" in body and "2880" in body

    def test_a_truncated_check_refuses_to_answer_either_way(self):
        from mre.modules.rolling_questions import answer_coarse_fit
        body = answer_coarse_fit(self._doc(wall_truncated=True))
        assert "didn't finish" in body
        assert "neither a fit nor a proof" in body

    def test_no_coarse_zone_says_so_rather_than_guessing(self):
        from mre.modules.rolling_questions import answer_coarse_fit
        doc = {"rolling": {"beyond_horizon": [], "coarse_zone": None}}
        assert "haven't run the coarse look-ahead" in answer_coarse_fit(doc)

    def test_monolithic_document_is_answered_honestly(self):
        from mre.modules.rolling_questions import (
            answer_bucket_load, answer_coarse_fit,
        )
        assert "isn't a rolling schedule" in answer_coarse_fit({"rolling": None})
        assert "isn't a rolling schedule" in answer_bucket_load({"rolling": None})

    def test_why_is_week_n_full_states_the_binding_arithmetic(self):
        from mre.modules.rolling_questions import answer_bucket_load
        doc = self._doc(density=[
            {"resource_id": "MILL-01", "bucket_index": 1, "load_minutes": 2800,
             "capacity_minutes": 2880, "utilization": 0.972},
            {"resource_id": "CUT-02", "bucket_index": 1, "load_minutes": 400,
             "capacity_minutes": 2880, "utilization": 0.139}])
        body = answer_bucket_load(doc, "week 1")
        assert "MILL-01" in body and "2800" in body and "2880" in body
        assert "genuinely full" in body
        assert "not a schedule" in body            # clause (6)

    def test_an_unfull_week_is_not_called_full(self):
        from mre.modules.rolling_questions import answer_bucket_load
        doc = self._doc(density=[
            {"resource_id": "CUT-02", "bucket_index": 1, "load_minutes": 400,
             "capacity_minutes": 2880, "utilization": 0.139}])
        assert "isn't actually full" in answer_bucket_load(doc, "week 1")

    def test_rho_and_its_provenance_are_always_stated(self):
        """CLAUSE (3): a DEFAULTED derate must never read as the plant's choice."""
        from mre.modules.rolling_questions import answer_bucket_load
        cells = [{"resource_id": "M1", "bucket_index": 0, "load_minutes": 10,
                  "capacity_minutes": 100, "utilization": 0.1}]
        declared = answer_bucket_load(self._doc(density=cells), "week 0")
        assert "declared planning derate of 80%" in declared
        defaulted = answer_bucket_load(
            self._doc(density=cells, capacity_derate=0.8,
                      capacity_derate_provenance="defaulted"), "week 0")
        assert "a default, not something this plant declared" in defaulted

    def test_when_will_it_start_carries_the_bucket_as_an_estimate(self):
        """"When will ORD-X start?" gets NO new route: it is
        why-not-scheduled-yet, whose answer now carries the coarse bucket BESIDE
        the due-date heuristic — two figures, two methods, neither overwriting
        the other."""
        from mre.modules.rolling_questions import answer_why_not_scheduled_yet
        doc = self._doc()
        doc["rolling"]["beyond_horizon"][0].update({
            "earliest_window_estimate": "2026-01-22T00:00:00+00:00",
            "coarse": {"start_bucket_index": 1, "completion_bucket_index": 1,
                       "resource_witness": "MILL-01",
                       "coarse_tardiness_buckets": 2, "run_label": "planning",
                       "sub_disposition": "coarsely_placed",
                       "unmodelable_reason": None}})
        body = answer_why_not_scheduled_yet(doc, "ORD-9")
        assert "2026-01-22" in body                       # the heuristic survives
        assert "week of 2026-01-19" in body               # and the coarse bucket
        assert "not a placement" in body                  # clause (6)
        assert "2 weeks past its due date" in body        # clause (5): buckets
        assert "MILL-01" not in body, "the resource WITNESS must never be voiced"

    def test_an_unmodelable_order_is_named_not_guessed(self):
        from mre.modules.rolling_questions import answer_why_not_scheduled_yet
        doc = self._doc()
        doc["rolling"]["beyond_horizon"][0].update({
            "coarse": {"start_bucket_index": -1, "completion_bucket_index": -1,
                       "resource_witness": "", "coarse_tardiness_buckets": 0,
                       "run_label": "planning",
                       "sub_disposition": "coarse_unmodelable",
                       "unmodelable_reason": "resumable_out_of_scope"}})
        body = answer_why_not_scheduled_yet(doc, "ORD-9")
        assert "can't give a rough week" in body
        assert "rather than guess" in body

    def test_no_coarse_answer_mentions_money(self):
        """CLAUSE (5): coarse tardiness is spoken in weeks. If a currency symbol
        ever appears in a coarse sentence the two ledgers have fused."""
        from mre.modules.rolling_questions import (
            answer_bucket_load, answer_coarse_fit,
        )
        for body in (answer_coarse_fit(self._doc(tardiness_buckets_total=3)),
                     answer_bucket_load(self._doc(binding_cells=[
                         {"resource_id": "M1", "bucket_index": 0,
                          "load_minutes": 99, "capacity_minutes": 100,
                          "utilization": 0.99}]))):
            assert "$" not in body and "cost" not in body.lower()


class TestUncountedPopulation:
    """Session 4B.6a CU2 — VOICE WHAT WAS NOT COUNTED.

    The coarse capacity arithmetic runs over a population missing every
    resumable op and every op exceeding a single bucket's capacity. Excluded ops
    consume ZERO coarse minutes, so load is UNDERSTATED — and resumables are the
    LONG ops, the ones that most stress capacity. The count is on
    ``CoarseZoneBlock.unmodelable_count``; until this CU it was not voiced.

    The precedent is 4B.6's own finding: without the unmodelable COUNT the
    rho = 0.10 result read as "it fits". Same lesson, second exclusion.

    BOTH DIRECTIONS are tested: a caveat when there is something to caveat, and
    NO invented caveat when there is not.
    """

    _CELLS = [{"resource_id": "MILL-01", "bucket_index": 1, "load_minutes": 2800,
               "capacity_minutes": 2880, "utilization": 0.972}]

    def _bodies(self, **cz):
        from mre.modules.rolling_questions import (
            answer_bucket_load, answer_coarse_fit,
        )
        doc = TestCoarseAnswers()._doc(density=self._CELLS,
                                       binding_cells=self._CELLS, **cz)
        return {
            "coarse_fit": answer_coarse_fit(doc),
            "bucket_load_named": answer_bucket_load(doc, "week 1"),
            "bucket_load_fullest": answer_bucket_load(doc),
            "bucket_load_empty_week": answer_bucket_load(doc, "week 0"),
        }

    def test_every_capacity_answer_names_the_uncounted_population(self):
        for name, body in self._bodies(unmodelable_count=7).items():
            assert "7 operations" in body, f"{name} does not name the count"
            assert "not counted" in body or "not in this figure" in body, (
                f"{name} names the count but not that the MINUTES are missing")

    def test_no_caveat_is_invented_when_nothing_is_excluded(self):
        for name, body in self._bodies(unmodelable_count=0).items():
            assert "outside what my coarse model" not in body, (
                f"{name} invented an exclusion caveat with nothing excluded")
            assert "not counted" not in body, name

    def test_a_proven_negative_names_the_exclusion_in_the_honest_direction(self):
        """Leaving work OUT can only make a refutation STRONGER — the excluded
        minutes would add load. The caveat must not read as a hedge on a proof."""
        from mre.modules.rolling_questions import answer_coarse_fit
        body = answer_coarse_fit(TestCoarseAnswers()._doc(
            infeasibility_proven=True, proof_status="INFEASIBLE",
            unmodelable_count=3, binding_cells=self._CELLS))
        assert body.startswith("No")
        assert "3 operations" in body
        assert "stronger, never weaker" in body

    def test_the_caveat_carries_no_currency(self):
        """CLAUSE (5) still holds over the new sentence."""
        for body in self._bodies(unmodelable_count=4).values():
            assert "$" not in body and "cost" not in body.lower()


class TestNoDerateDeclared:
    """Session 4B.6a CU2(d) — THE ABSENCE IS LOUD, AND IS NOT A GATE FINDING.

    At rho = 1.0 the planning run MIRRORS the proof run, so an undeclared plant
    gets NO planning signal and its capacity figures assume every available
    minute is usable — the optimistic direction, the one we do not want to be
    wrong in. No default margin is invented (clause 3 stands); the absence is
    made loud instead.
    """

    def test_the_certificate_carries_a_declaration_note(self):
        c = CoarseCoefficients.from_cost_model({})
        block = c.certificate_block()
        note = block["coarse_capacity_derate_note"]
        assert "NO CAPACITY MARGIN DECLARED" in note
        assert "full utilization" in note
        assert "moves no gate verdict" in note

    def test_a_declared_derate_says_it_was_declared(self):
        c = CoarseCoefficients.from_cost_model({"coarse_capacity_derate": 0.85})
        note = c.certificate_block()["coarse_capacity_derate_note"]
        assert "DECLARED at 0.85" in note
        assert "NO CAPACITY MARGIN DECLARED" not in note

    def test_no_invented_margin(self):
        """The loudness must never become a silent default (clause 3)."""
        assert CoarseCoefficients.from_cost_model({}).capacity_derate == 1.0

    def test_capacity_answers_say_the_figures_assume_full_utilization(self):
        from mre.modules.rolling_questions import answer_bucket_load
        cells = [{"resource_id": "M1", "bucket_index": 0, "load_minutes": 10,
                  "capacity_minutes": 100, "utilization": 0.1}]
        doc = TestCoarseAnswers()._doc(
            density=cells, capacity_derate=1.0,
            capacity_derate_provenance="defaulted")
        body = answer_bucket_load(doc, "week 0")
        assert "no capacity margin is declared" in body
        assert "assume every available minute is usable" in body

    def test_the_rule_count_is_unchanged(self):
        """CU2(d) adds a remediation entry (INFORMATIONAL), never a registry
        rule. The one coarse rule that exists (``coarse_horizon_coefficients_
        sane``, 4B.6) checks a DECLARED value's sanity; loudness about an ABSENT
        one must not become a 37th rule."""
        from mre.contracts.ids_rules import RULE_REGISTRY
        assert len(RULE_REGISTRY) == 36

    def test_an_undeclared_derate_fires_no_rule_and_moves_no_verdict(self,
                                                                     tmp_path):
        """THIS IS NOT A GATE FINDING. rho is an undeclared OPTIONAL coefficient
        (docs/06 §5.9), not a data defect: it must not move a verdict to
        CONDITIONAL or fire a rule violation. Asserted on a real gate run over a
        submission that declares nothing."""
        import json as _json
        from generate_erp_dataset import generate
        from mre.contracts.vocabularies import ModuleCode, RunStatus
        from mre.modules.conformance import ConformanceGate
        from mre.reporter import Reporter

        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=7)
        cm = _json.loads((sub / "cost_model.json").read_text(encoding="utf-8"))
        assert "coarse_horizon" not in (cm.get("refinements") or {}), (
            "this scenario now declares the coefficient — pick one that doesn't")

        rep = Reporter.begin(module=ModuleCode.M0, purpose="CU2(d)", config={},
                             trigger="test", snapshot_id="pre-adapter",
                             sink_dir=tmp_path / "runs")
        result = ConformanceGate().run(sub, rep)
        rep.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)

        assert result.grade == "ACCEPTED", (
            f"an undeclared capacity derate moved the verdict to "
            f"{result.grade} — it is a declaration note, not a defect")
        fired = [f for f in result.certificate.get("rule_outcomes", [])
                 if "coarse_horizon" in str(f)]
        assert fired == [], (
            f"the coarse coefficient rule fired on a submission that never "
            f"declared it: {fired}")


def test_the_two_coarse_intents_are_fully_registered():
    """A vocabulary-class change is only done when EVERY registration site
    carries it: Intent, meaning, taxonomy, offer, rolling dispatch set."""
    from mre.contracts.parse import INTENT_MEANINGS, Intent
    from mre.modules.ask_fallback_copy import ROUTE_OFFERS
    from mre.modules.explainer import ROUTE_TAXONOMY
    from mre.modules.interpreter import ROLLING_INTENTS
    from mre.modules.rolling_questions import ROLLING_ROUTES
    for intent in (Intent.COARSE_FIT, Intent.BUCKET_LOAD):
        assert intent in INTENT_MEANINGS and INTENT_MEANINGS[intent]
        assert intent.value in ROUTE_TAXONOMY
        assert intent.value in ROUTE_OFFERS
        assert intent in ROLLING_INTENTS
        assert intent.value in ROLLING_ROUTES


def test_the_governed_prompt_was_bumped_with_the_vocabulary():
    """R-AI5(8): the parse prompt is a GOVERNED ARTIFACT — a vocabulary change
    without its bump is a review that did not happen."""
    md = (REPO / "src" / "mre" / "modules" / "parse_prompt.md").read_text(
        encoding="utf-8")
    # Session 4B.13: this pinned `prompt_version: 9` exactly, so it broke on the
    # NEXT legitimate bump (v10, `solve-optimality`) — a governance guard that
    # cries wolf at every review is one that gets edited without being read.
    # What it must actually prove is that THIS session's vocabulary landed WITH
    # its review: the v9 changelog entry is permanent, and the live version can
    # only ever move forward from it.
    assert "v9:" in md, "the coarse bump's changelog entry is gone"
    version = int(md.split("prompt_version:")[1].split()[0])
    assert version >= 9, f"prompt_version went backwards: {version}"
    assert "coarse-fit" in md and "bucket-load" in md
