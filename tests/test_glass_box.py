"""Glass Box auditor dataset (datasets/glass_box) — the standing guard.

Session 4B.1 builds hand-authored auditor INSTRUMENTS: a human-readable IDS
submission whose solve tells seven named stories, a one-page sabotage menu, and a
walkthrough. This test is the mechanical floor under those instruments so the
auditor never meets a menu item that is wrong about itself:

  * Part A  — the clean dataset passes the gate ACCEPTED / C2 / no findings.
  * Part B  — every SABOTAGE_MENU.md item, applied as its one-cell edit, trips
              exactly the rule / outcome / grade the menu claims (and the
              false-positive CONTROL trips nothing). Verify each item ONCE, per
              the session's "so Daryn never hits a menu item that's wrong about
              itself" — this is that verification, frozen.
  * Part C  — (slow) the real solve reproduces the seven narrative features the
              README predicts, deterministically. If the solve ever contradicts a
              README prediction, THIS is where it surfaces (a finding, not a
              rewrite).

The sabotage rows here are the executable twin of docs' SABOTAGE_MENU.md — keep
the two in lockstep (same file / cell / rule / outcome).
"""
from __future__ import annotations

import csv
import shutil
from datetime import date
from pathlib import Path

import pytest

from mre.__main__ import main as mre_main
from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import ConformanceGate
from mre.reporter import Reporter

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "glass_box"


# ---------------------------------------------------------------------------
# gate helpers
# ---------------------------------------------------------------------------

def _run_gate(submission_dir: Path, tmp_path: Path):
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="glass_box gate", config={}, trigger="test",
        snapshot_id="pre-adapter", sink_dir=tmp_path / "runs",
    )
    result = ConformanceGate().run(submission_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
    return result


def _copy_dataset(tmp_path: Path) -> Path:
    dst = tmp_path / "sub"
    shutil.copytree(DATASET, dst)
    shutil.rmtree(dst / "gate_output", ignore_errors=True)
    return dst


def _rewrite_csv(path: Path, mutate) -> None:
    rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(mutate(rows)) + "\n", encoding="utf-8")


def _set_cell(order_or_route_id: str, col: int, value: str):
    def _m(rows):
        out = [rows[0]]
        for ln in rows[1:]:
            parts = ln.split(",")
            if parts and parts[0] == order_or_route_id:
                parts[col] = value
            out.append(",".join(parts))
        return out
    return _m


# ---------------------------------------------------------------------------
# Part A — the clean dataset is conformant
# ---------------------------------------------------------------------------

class TestCleanDataset:
    def test_gate_accepts_c2_no_findings(self, tmp_path):
        result = _run_gate(DATASET, tmp_path)
        assert result.grade == "ACCEPTED"
        assert result.go is True
        assert result.costing_grade == "C2"
        assert result.certificate["findings"] == []
        assert result.certificate["deficiencies"] == []


# ---------------------------------------------------------------------------
# Part B — the sabotage menu (each item is right about itself)
# ---------------------------------------------------------------------------
# (label, file, mutate, expected_grade, expected_rule_id_or_None, expected_code_or_None)

def _mutate_bracket_slow_splittable(rows):
    out = [rows[0]]
    for ln in rows[1:]:
        p = ln.split(",")
        if p[:3] == ["RT-BRACKET", "10", "PRESS-SLOW"]:
            p[8] = "true"  # splittable disagrees with the fast row (step attribute)
        out.append(",".join(p))
    return out


def _mutate_bracket_unroutable(rows):
    out = [rows[0]]
    for ln in rows[1:]:
        p = ln.split(",")
        if p[:2] == ["RT-BRACKET", "10"]:
            p[3] = "0"  # deactivate every eligible row -> zero active rows
        out.append(",".join(p))
    return out


def _mutate_duplicate_ord05(rows):
    dup = next(ln for ln in rows[1:] if ln.startswith("ORD-05,"))
    return rows + [dup]


SABOTAGE = [
    # 1 — broken product reference
    ("broken_product_ref", "orders.csv", _set_cell("ORD-01", 1, "PROD-NOPE"),
     "CONDITIONAL", "ids.orders_resolve_to_products", "degraded", "ORPHAN_ENTITY"),
    # 2 — impossible due date (before created)
    ("impossible_due_date", "orders.csv", _set_cell("ORD-01", 4, "2026-01-01"),
     "CONDITIONAL", "ids.order_dates_internally_consistent", "degraded",
     "TEMPORAL_IMPOSSIBILITY"),
    # 3 — alternative-group step attribute mismatch (rule #33)
    ("alt_group_step_mismatch", "routing_lines.csv", _mutate_bracket_slow_splittable,
     "CONDITIONAL", "ids.alternative_step_attributes_agree", "degraded",
     "AMBIGUOUS_SOURCE"),
    # 4 — statistical outlier rate (quality, INFO, still ACCEPTED)
    ("statistical_outlier", "products.csv",
     _set_cell("P-WIDGET", 6, "3000"),
     "ACCEPTED", "ids.durations_within_plausible_range", "flagged",
     "STATISTICAL_OUTLIER"),
    # 5 — duplicate order identity
    ("duplicate_identity", "orders.csv", _mutate_duplicate_ord05,
     "CONDITIONAL", "ids.order_identities_unique", "degraded", "DUPLICATE_IDENTITY"),
    # 6 — malformed field: blank key
    ("malformed_blank_key", "orders.csv", _set_cell("ORD-07", 0, ""),
     "REJECTED", "ids.key_fields_populated", "violated", "MALFORMED_FIELD"),
    # 7 — unroutable step (zero active rows)
    ("unroutable_step", "routing_lines.csv", _mutate_bracket_unroutable,
     "CONDITIONAL", "ids.routes_resolve_to_lines", "degraded", "ORPHAN_ENTITY"),
    # 7b — negative order quantity (rule #34, Session 4.5): invalid demand
    ("negative_quantity", "orders.csv", _set_cell("ORD-09", 3, "-60"),
     "CONDITIONAL", "ids.order_quantities_are_positive", "degraded",
     "VALUE_OUT_OF_RANGE"),
    # 8 — CONTROL: a legal change flags nothing (false-positive guard)
    ("control_legal_change", "orders.csv", _set_cell("ORD-01", 3, "55"),
     "ACCEPTED", None, None, None),
    # 9 — facility mismatch
    ("facility_mismatch", "orders.csv", _set_cell("ORD-02", 7, "F999"),
     "CONDITIONAL", "ids.facility_references_consistent", "degraded", "ORPHAN_ENTITY"),
    # 10 — an inactive route is used by a live order
    ("inactive_route_used", "routings.csv", _set_cell("RT-WIDGET", 3, "inactive"),
     "CONDITIONAL", "ids.orders_use_active_routes", "degraded", "LOW_CONFIDENCE_INPUT"),
]


@pytest.mark.parametrize(
    "label,fname,mutate,grade,rule_id,outcome,code",
    SABOTAGE, ids=[s[0] for s in SABOTAGE],
)
def test_sabotage_menu_item(tmp_path, label, fname, mutate, grade, rule_id, outcome, code):
    sub = _copy_dataset(tmp_path)
    _rewrite_csv(sub / fname, mutate)
    result = _run_gate(sub, tmp_path)
    assert result.grade == grade, f"{label}: grade {result.grade} != {grade}"
    outcomes = result.certificate["rule_outcomes"]
    codes = {f["code"] for f in result.certificate["findings"]}
    if rule_id is None:
        # the false-positive CONTROL: no rule leaves 'satisfied', no finding
        non_sat = {k: v for k, v in outcomes.items() if v != "satisfied"}
        assert non_sat == {}, f"{label}: control tripped {non_sat}"
        assert codes == set(), f"{label}: control emitted findings {codes}"
    else:
        assert outcomes.get(rule_id) == outcome, (
            f"{label}: {rule_id} -> {outcomes.get(rule_id)} != {outcome}")
        assert code in codes, f"{label}: code {code} not in {codes}"


# ---------------------------------------------------------------------------
# Part C — the solve tells the seven stories (slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    out = tmp_path_factory.mktemp("glass_box_out")
    rc = mre_main([
        "--submission", str(DATASET), "--out", str(out),
        "--snapshot-id", "snap-glass-box",
        "--solver-workers", "1", "--solver-seed", "0",
    ])
    assert rc == 0, f"pipeline exit {rc}"
    rows = list(csv.DictReader((out / "schedule.csv").read_text(encoding="utf-8").splitlines()))
    for r in rows:
        r["start_dt"] = r["start"]
        r["end_dt"] = r["end"]
    return rows


def _by_order(rows, oid):
    return [r for r in rows if r["work_orders"] == oid]


def _end_date(iso: str) -> date:
    return date.fromisoformat(iso[:10])


@pytest.mark.slow
class TestUnguardedEdgesDownstream:
    """Session 4.5 CU1/CU2 — the gate finding is only half the guarantee; the
    OFFENDING ORDER must also be gone from the solve, never scheduled early."""

    def _solve_mutated(self, tmp_path, fname, mutate):
        sub = _copy_dataset(tmp_path)
        _rewrite_csv(sub / fname, mutate)
        out = tmp_path / "out"
        rc = mre_main([
            "--submission", str(sub), "--out", str(out),
            "--snapshot-id", "snap-4-5", "--solver-workers", "1", "--solver-seed", "0",
        ])
        assert rc == 0, f"pipeline exit {rc}"
        rows = list(csv.DictReader(
            (out / "schedule.csv").read_text(encoding="utf-8").splitlines()))
        return rows

    def test_negative_quantity_order_excluded_no_floored_op(self, tmp_path):
        # CU2 downstream: ORD-09 quantity -60 is excluded; it produces NO
        # operation. If the -60 had laundered through a duration floor it would
        # appear as a 1-minute op (-60 x 3 min = -180 -> max(1, .) = 1). It
        # must be absent entirely.
        rows = self._solve_mutated(tmp_path, "orders.csv", _set_cell("ORD-09", 3, "-60"))
        assert all(r["work_orders"] != "ORD-09" for r in rows), (
            "ORD-09 (-60 qty) must be excluded, not scheduled")
        # the rest of the plan still solves (a healthy order stays)
        assert any(r["work_orders"] == "ORD-13" for r in rows)

    def test_zero_active_bracket_excluded_not_early(self, tmp_path):
        # CU1 downstream: RT-BRACKET seq10 with zero active rows makes ORD-06/07/08
        # unroutable. They must be EXCLUDED — absent from the solve — never
        # scheduled as a vacuous, operation-less (and therefore EARLY) fulfillment.
        rows = self._solve_mutated(tmp_path, "routing_lines.csv", _mutate_bracket_unroutable)
        for oid in ("ORD-06", "ORD-07", "ORD-08"):
            assert all(r["work_orders"] != oid for r in rows), (
                f"{oid} on the zero-active bracket route must be excluded")
        assert any(r["work_orders"] == "ORD-13" for r in rows)


@pytest.mark.slow
class TestSevenStories:
    def test_exactly_one_late_order_is_ord05(self, solved):
        # due_date is end_of_day; an order is late iff its final op ends on a
        # calendar day after its due date.
        due = {r["order_id"]: date.fromisoformat(r["due_date"])
               for r in csv.DictReader(
                   (DATASET / "orders.csv").read_text(encoding="utf-8").splitlines())}
        last_end = {}
        for r in solved:
            oid = r["work_orders"]
            d = _end_date(r["end_dt"])
            last_end[oid] = max(last_end.get(oid, d), d)
        late = [oid for oid, d in last_end.items() if d > due[oid]]
        assert late == ["ORD-05"], f"expected only ORD-05 late, got {late}"

    def test_f3_contention_ord04_wins_monday(self, solved):
        # F3: the two rush jobs share CUT-01; the higher-priority ORD-04 runs
        # Monday, the standard ORD-05 slips to Tuesday (the traceable cause).
        o4 = _by_order(solved, "ORD-04")[0]
        o5 = _by_order(solved, "ORD-05")[0]
        assert o4["machine"] == o5["machine"] == "CUT-01"
        assert _end_date(o4["end_dt"]) == date(2026, 1, 5)      # Monday, on time
        assert _end_date(o5["end_dt"]) == date(2026, 1, 6)      # Tuesday, late

    def test_f4_overtime_rescues_ord11_on_saturday(self, solved):
        # F4: ORD-11's heat op runs Saturday 2026-01-10; its production_cost
        # carries the 1.5x overtime premium (900 vs the regular 600 of ORD-10).
        o10 = _by_order(solved, "ORD-10")[0]
        o11 = _by_order(solved, "ORD-11")[0]
        assert o11["machine"] == "HEAT-01"
        assert _end_date(o11["end_dt"]) == date(2026, 1, 10)    # Saturday overtime
        assert float(o11["production_cost"]) > float(o10["production_cost"])
        assert float(o11["production_cost"]) == pytest.approx(900.0)

    def test_f2_spacer_splits_at_a_closure(self, solved):
        # F2: the one splittable op pauses at a shift close and resumes.
        chunks = _by_order(solved, "ORD-03")
        assert len(chunks) == 2, f"expected 2 chunks, got {len(chunks)}"
        seqs = sorted(c["chunk_seq"] for c in chunks)
        assert seqs == ["1", "2"]
        # the pause crosses a day boundary (an overnight closure)
        ends = sorted(c["end_dt"] for c in chunks)
        assert _end_date(ends[0]) < _end_date(ends[1])

    def test_f1_one_bracket_on_the_slow_press(self, solved):
        # F1: exactly one BRACKET op runs on PRESS-SLOW at the slow (longer)
        # duration; the other two take the fast press.
        bracket = [r for r in solved if r["work_orders"] in
                   ("ORD-06", "ORD-07", "ORD-08")]
        slow = [r for r in bracket if r["machine"] == "PRESS-SLOW"]
        fast = [r for r in bracket if r["machine"] == "PRESS-FAST"]
        assert len(slow) == 1 and len(fast) == 2
        assert float(slow[0]["duration_min"]) > float(fast[0]["duration_min"])

    def test_f6_changeover_between_the_two_panels(self, solved):
        # F6: the RED and BLUE panels share PAINT-01; a family changeover sits
        # between them as a gap wider than either op's own setup.
        red = _by_order(solved, "ORD-09")[0]
        blue = _by_order(solved, "ORD-12")[0]
        assert red["machine"] == blue["machine"] == "PAINT-01"
        assert red["setup_family"] and blue["setup_family"]
        assert red["setup_family"] != blue["setup_family"]

    def test_f5_precedence_chain_widget(self, solved):
        # F5: a two-machine route — seq20 (PAINT-01) cannot start until seq10
        # (CUT-01) has finished, for each widget order.
        for oid in ("ORD-01", "ORD-02"):
            ops = {r["op_seq"]: r for r in _by_order(solved, oid)}
            assert ops["10"]["machine"] == "CUT-01"
            assert ops["20"]["machine"] == "PAINT-01"
            assert ops["20"]["start"] >= ops["10"]["end"]

    def test_f7_control_order_comfortably_early(self, solved):
        # F7: the control finishes far ahead of its due date.
        o13 = _by_order(solved, "ORD-13")[0]
        assert _end_date(o13["end_dt"]) < date(2026, 1, 16)
