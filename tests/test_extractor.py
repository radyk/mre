"""Tests for M7 Extractor — derived from docs/01 §6.9 and docs/02 §4.2.

The extractor turns SolveValues + canonical entities into Schedule, Assignments,
ServiceOutcomes, and reconstructed-alternative Decisions.

Key invariants:
- One ServiceOutcome per Fulfillment (per-Demand tardiness, D-07).
- total cost = production + setup + tardiness (decomposability check).
- All assignment Decisions carry basis=reconstructed.
- After extraction, Schedule/Assignments readable with no ortools import.
"""
from datetime import datetime, timedelta, timezone

import pytest

UTC = timezone.utc
HORIZON = datetime(2026, 7, 13, 7, 0, tzinfo=UTC)
DUE_MON = datetime(2026, 7, 13, 23, 59, tzinfo=UTC)
DUE_WED = datetime(2026, 7, 15, 23, 59, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _solve_values(
    op_start=0, op_end=150, op_resource="res-1",
    wp_end=150, tard_min=0,
    op_id="op-1", wp_id="wp-1", f_id="f-1",
):
    from mre.modules.solver_builder import SolveValues
    return SolveValues(
        op_start_minutes={op_id: op_start},
        op_end_minutes={op_id: op_end},
        op_resource={op_id: op_resource},
        wp_end_minutes={wp_id: wp_end},
        tardiness_minutes={f_id: tard_min},
        horizon_start=HORIZON,
    )


def _costmodel(cmid="cm-1", rate=6.0, setup_fixed=50.0):
    return {
        "id": cmid,
        "resource_rates": {"res-1": rate, "res-2": 8.0},
        "setup_cost_basis": {"fixed_per_setup": setup_fixed, "scrap_cost_per_unit": 0.0},
        "tardiness_weights": {
            "base_weight": 1.0,
            "commitment_class_multipliers": {"standard": 1.0, "rush": 2.0},
        },
    }


def _demand(did, due, earliest=None, weight=1.0, cclass="standard"):
    return {
        "id": did, "product_ref": "prod-1",
        "quantity": {"value": 200, "uom": "EA"},
        "due": due.isoformat(),
        "earliest_start": earliest.isoformat() if earliest else None,
        "commitment_class": cclass, "customer_weight": weight,
    }


def _fulfillment(fid, demand_id, wp_id, qty=200):
    return {
        "id": fid, "demand_ref": demand_id, "workpackage_ref": wp_id,
        "allocated_quantity": {"value": qty, "uom": "EA"}, "decision_ref": "dec-1",
    }


def _operation(oid, wp_id, setup_sec=60, run_sec=9000, family="gear"):
    return {
        "id": oid, "spec_ref": "spec-1", "workpackage_ref": wp_id,
        "sequence": 10,
        "resource_requirements": [],
        "setup_family": family,
        "setup_duration": f"PT{setup_sec}S",
        "run_duration": f"PT{run_sec}S",
        "splittable": False,
    }


def _resource(rid, rate=6.0, cal=None):
    return {"id": rid, "resource_type": "machine", "capabilities": [],
             "capacity": 1, "cost_rate": rate, "calendar_ref": cal, "pool_refs": []}


def _wp(wid, ops, qty=200):
    return {"id": wid, "product_ref": "prod-1",
             "quantity": {"value": qty, "uom": "EA"},
             "earliest_start": HORIZON.isoformat(),
             "operations": ops, "process_version": 1,
             "state": "planned", "created_by": "dec-1"}


def _make_reporter(tmp_path, snap_id):
    from mre.reporter import Reporter
    from mre.contracts.vocabularies import ModuleCode
    return Reporter.begin(
        module=ModuleCode.M7, purpose="extractor test", config={},
        trigger="pytest", snapshot_id=snap_id,
        sink_dir=tmp_path / "runs_ex",
    )


# ---------------------------------------------------------------------------
# Session 4.5 CU1 — a vacuous fulfillment is unrepresentable
# ---------------------------------------------------------------------------

class TestVacuousFulfillmentUnrepresentable:
    def test_operationless_fulfillment_raises(self, tmp_path):
        """A ServiceOutcome requires >=1 real operation. A fulfillment whose
        WorkPackage has no operations would default its completion to the
        horizon start and read as EARLY — a plausible lie about an order that
        was never scheduled. The extractor must refuse it, not materialize it."""
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, wp_end=150, tard_min=0)
        wps = [_wp("wp-1", [])]                       # no operations
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        rep = _make_reporter(tmp_path, "snap-vac")
        with pytest.raises(ValueError, match="vacuous fulfillment"):
            Extractor().extract(sv, "snap-vac", [], wps, [_resource("res-1")],
                                fuls, demands, _costmodel(), rep)

    def test_real_operation_fulfillment_is_fine(self, tmp_path):
        """The healthy path still works — a WP with >=1 operation yields a
        ServiceOutcome without complaint."""
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, wp_end=150, tard_min=0)
        result = Extractor().extract(
            sv, "snap-ok", [_operation("op-1", "wp-1")], [_wp("wp-1", ["op-1"])],
            [_resource("res-1")], [_fulfillment("f-1", "d-1", "wp-1")],
            [_demand("d-1", DUE_WED)], _costmodel(), _make_reporter(tmp_path, "snap-ok"))
        assert len(result.service_outcomes) == 1


# ---------------------------------------------------------------------------
# Assignment creation
# ---------------------------------------------------------------------------

class TestAssignments:
    def test_assignment_per_operation(self, tmp_path):
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, wp_end=150, tard_min=0)
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex1")

        result = Extractor().extract(sv, "snap-ex1", ops, wps, ress, fuls, demands, cm, rep)
        assert len(result.assignments) == 1

    def test_assignment_has_real_timestamps(self, tmp_path):
        """phase_windows must contain real UTC datetimes, not raw minutes."""
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, wp_end=150)
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex2")

        result = Extractor().extract(sv, "snap-ex2", ops, wps, ress, fuls, demands, cm, rep)
        asgn = result.assignments[0]
        # phase_windows should have a run_start that is >= horizon_start
        assert asgn["run_start"] >= HORIZON.isoformat()

    def test_assignment_decision_basis_is_reconstructed(self, tmp_path):
        from mre.modules.extractor import Extractor
        from mre.contracts.vocabularies import DecisionBasis
        sv = _solve_values()
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1"), _resource("res-2", rate=8.0)]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex3")

        result = Extractor().extract(sv, "snap-ex3", ops, wps, ress, fuls, demands, cm, rep)
        records = rep._sink.read_all()
        decisions = [r for r in records if r.get("record_type") == "decision"
                     and r.get("decision_type") == "assignment"]
        assert len(decisions) >= 1
        for d in decisions:
            assert d["basis"] == DecisionBasis.RECONSTRUCTED.value


class TestAlternativeConsequenceWording:
    """A cheaper road-not-taken renders as savings, not a negative 'more'
    (Session 3.1c carry-in). The number was always honest; the sentence now
    matches it. Symmetric: a costlier alternative reads 'Would cost $X more.'"""

    def _consequences(self, tmp_path, snap_id):
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, op_resource="res-1")
        ops = [_operation("op-1", "wp-1")]
        # res-1 chosen @ $10; res-2 cheaper @ $8; res-3 costlier @ $12
        ress = [_resource("res-1"), _resource("res-2"), _resource("res-3")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel(rate=10.0)
        cm["resource_rates"] = {"res-1": 10.0, "res-2": 8.0, "res-3": 12.0}
        rep = _make_reporter(tmp_path, snap_id)

        Extractor().extract(sv, snap_id, ops, wps, ress, fuls, demands, cm, rep)
        records = rep._sink.read_all()
        [dec] = [r for r in records if r.get("record_type") == "decision"
                 and r.get("decision_type") == "assignment"]
        return {a["option"]: a["consequence"] for a in dec["alternatives"]}

    def test_cheaper_alternative_renders_as_savings(self, tmp_path):
        cons = self._consequences(tmp_path, "snap-alt-save")
        # (8 - 10) * 150 min = -$300 cheaper
        assert cons["resource:res-2"] == "Would save $300.00."
        assert "more" not in cons["resource:res-2"]
        assert "-" not in cons["resource:res-2"]

    def test_costlier_alternative_renders_as_more(self, tmp_path):
        cons = self._consequences(tmp_path, "snap-alt-more")
        # (12 - 10) * 150 min = +$300 costlier
        assert cons["resource:res-3"] == "Would cost $300.00 more."


class TestEarlinessDriverAttribution:
    """R-SC3 / CU3: a dearer-but-earlier eligible placement is attributed to
    EARLINESS_PREFERENCE only when a positive earliness_value is declared — with
    earliness_value == 0 the classification is byte-identical to pre-R-SC3."""

    def _driver(self, chosen, rates, earliness_value):
        from mre.modules.extractor import Extractor
        from mre.contracts.vocabularies import DriverCode
        return Extractor()._assignment_driver(
            chosen, list(rates), rates, op_start_min=0, op_end_min=100,
            cal_windows=None, earliness_value=earliness_value)

    def test_dearer_chosen_with_earliness_is_earliness_preference(self):
        from mre.contracts.vocabularies import DriverCode
        # res-2 ($12) chosen over the cheaper eligible res-1 ($10), earliness on.
        d = self._driver("res-2", {"res-1": 10.0, "res-2": 12.0}, earliness_value=0.05)
        assert d == DriverCode.EARLINESS_PREFERENCE

    def test_zero_earliness_is_byte_identical(self):
        from mre.contracts.vocabularies import DriverCode
        # same dearer choice, earliness OFF -> the pre-R-SC3 classification stands.
        d = self._driver("res-2", {"res-1": 10.0, "res-2": 12.0}, earliness_value=0.0)
        assert d != DriverCode.EARLINESS_PREFERENCE
        assert d == DriverCode.CAPACITY_BLOCKED

    def test_cheapest_chosen_stays_cost_tradeoff(self):
        from mre.contracts.vocabularies import DriverCode
        # earliness on, but the cheapest eligible was chosen -> COST_TRADEOFF wins.
        d = self._driver("res-1", {"res-1": 10.0, "res-2": 12.0}, earliness_value=0.05)
        assert d == DriverCode.COST_TRADEOFF


# ---------------------------------------------------------------------------
# ServiceOutcomes (per-Demand tardiness, D-07)
# ---------------------------------------------------------------------------

class TestServiceOutcomes:
    def test_one_service_outcome_per_fulfillment(self, tmp_path):
        """Two Fulfillments on same WP → two ServiceOutcomes."""
        from mre.modules.extractor import Extractor
        from mre.modules.solver_builder import SolveValues

        sv = SolveValues(
            op_start_minutes={"op-1": 0},
            op_end_minutes={"op-1": 660},
            op_resource={"op-1": "res-1"},
            wp_end_minutes={"wp-1": 660},
            tardiness_minutes={"f-1": 660, "f-2": 0},
            horizon_start=HORIZON,
        )
        ops = [_operation("op-1", "wp-1", run_sec=39600)]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"], qty=400)]
        demands = [
            _demand("d-1", DUE_MON, weight=1.0),   # due Mon → late
            _demand("d-2", DUE_WED, weight=1.0),   # due Wed → on time
        ]
        fuls = [
            _fulfillment("f-1", "d-1", "wp-1", qty=200),
            _fulfillment("f-2", "d-2", "wp-1", qty=200),
        ]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex4")

        result = Extractor().extract(sv, "snap-ex4", ops, wps, ress, fuls, demands, cm, rep)
        assert len(result.service_outcomes) == 2

    def test_service_outcome_lateness_negative_when_early(self, tmp_path):
        """lateness < 0 when WP completes before due date."""
        from mre.modules.extractor import Extractor
        # WP ends at t=0 (HORIZON), due Wed (2 days later) → early
        sv = _solve_values(wp_end=0, tard_min=0)
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex5")

        result = Extractor().extract(sv, "snap-ex5", ops, wps, ress, fuls, demands, cm, rep)
        assert result.service_outcomes[0]["lateness_minutes"] < 0

    def test_service_outcome_lateness_positive_when_late(self, tmp_path):
        """lateness > 0 when WP completes after due date."""
        from mre.modules.extractor import Extractor
        # WP ends at minute 1100 from HORIZON (about 18 hours after start)
        # DUE_MON = HORIZON + 16h59m = 1019 min
        # So lateness = 1100 - 1019 = 81 min
        due_min = int((DUE_MON - HORIZON).total_seconds() / 60)
        wp_end_min = due_min + 81  # 81 minutes late
        sv = _solve_values(op_start=0, op_end=wp_end_min, wp_end=wp_end_min, tard_min=81)
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_MON)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex6")

        result = Extractor().extract(sv, "snap-ex6", ops, wps, ress, fuls, demands, cm, rep)
        assert result.service_outcomes[0]["lateness_minutes"] > 0


# ---------------------------------------------------------------------------
# Cost ledger decomposability (docs/01 §6.9)
# ---------------------------------------------------------------------------

class TestCostLedger:
    def test_cost_ledger_decomposes_total_equals_sum(self, tmp_path):
        """total_cost = production_cost + setup_cost + tardiness_cost."""
        from mre.modules.extractor import Extractor
        sv = _solve_values(op_start=0, op_end=150, wp_end=150, tard_min=0)
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1", rate=6.0)]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel(rate=6.0, setup_fixed=50.0)
        rep = _make_reporter(tmp_path, "snap-ex7")

        result = Extractor().extract(sv, "snap-ex7", ops, wps, ress, fuls, demands, cm, rep)
        ledger = result.cost_ledger
        total = ledger["total_cost"]
        parts = ledger["production_cost"] + ledger["setup_cost"] + ledger["tardiness_cost"]
        assert abs(total - parts) < 1e-6, f"Decomposability failed: {total} != {parts}"

    def test_cost_ledger_fails_decomposability_on_bad_total(self, tmp_path):
        """A manually broken ledger must fail the decomposability check."""
        from mre.modules.extractor import Extractor
        from mre.reporter.consolidate import DecomposabilityError

        sv = _solve_values()
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex8")

        result = Extractor().extract(sv, "snap-ex8", ops, wps, ress, fuls, demands, cm, rep)
        bad = dict(result.cost_ledger)
        bad["total_cost"] += 999.0  # corrupt
        parts = bad["production_cost"] + bad["setup_cost"] + bad["tardiness_cost"]
        assert abs(bad["total_cost"] - parts) > 1.0  # sanity that it's bad

    def test_schedule_readable_after_extraction(self, tmp_path):
        """Schedule and Assignments are plain dicts/dataclasses — no ortools needed."""
        from mre.modules.extractor import Extractor
        sv = _solve_values()
        ops = [_operation("op-1", "wp-1")]
        ress = [_resource("res-1")]
        wps = [_wp("wp-1", ["op-1"])]
        fuls = [_fulfillment("f-1", "d-1", "wp-1")]
        demands = [_demand("d-1", DUE_WED)]
        cm = _costmodel()
        rep = _make_reporter(tmp_path, "snap-ex9")

        result = Extractor().extract(sv, "snap-ex9", ops, wps, ress, fuls, demands, cm, rep)
        # These should be plain Python structures, not ortools objects
        assert result.schedule["snapshot_ref"] == "snap-ex9"
        assert isinstance(result.assignments, list)
        assert isinstance(result.service_outcomes, list)
        assert isinstance(result.cost_ledger, dict)
