"""R-PD1 — PAST-DUE DEMAND DISPOSITION (Session 4B.11).

The ruling is transcribed verbatim in docs/04 (2026-07-28). Six clauses; this
file pins the ones that are behaviour:

  (1) PAST-DUE IS WORK, NOT A DEFECT — admitted, scheduled, priced with
      tardiness from its DECLARED due date.
  (2) EXCLUSION IS A DATA-DEFECT CATEGORY ONLY — never for a true statement
      about the plant's position (late, beyond horizon, over capacity).
  (3) THE GATE'S DISPOSITION BINDS DOWNSTREAM — where M0 grades a finding
      `proceeded_flagged`, no later module may SILENTLY remove the demand. A
      module that must remove one raises its OWN certificate-visible finding
      naming ITSELF as the source.
  (4) TARDINESS DECOMPOSES AND NEVER FUSES — floor + controllable, summing
      exactly.
  (6) EVERY PER-ORDER ROUTE VOICES THE DISPOSITION — "a true answer
      indistinguishable from a false one is not an answer".

THE SPECIMEN is `facility_real_pastdue` (Session 4B.10): 60 orders, 21 of them
already past due at the 2026-01-05 reference date. Before 4B.11 all 21 vanished
before the solver — the live measurement that produced this ruling
(docs/07 §5a.26).

Clause (3)'s guard is the most valuable thing in this file and it is deliberately
GENERAL: it does not know what past-due means. It asserts a property of ANY run —
that a demand the gate passed as `proceeded_flagged` is either still schedulable
or was removed by a module that said so, in a record, by name. That is what
catches the THIRD instance of this defect class, in whatever module invents it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the specimen world, built once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def specimen(tmp_path_factory):
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant

    tmp = tmp_path_factory.mktemp("pastdue")
    sub = tmp / "submission"
    generate(sub, scenario="facility_real_pastdue", orders=60, seed=1)
    plant = prepare_plant(sub, tmp / "run", reference_date=REF)
    records = []
    for path in sorted((plant.out_dir / "runs").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    past_due = [d for d in plant.demands
                if d.get("due") and str(d["due"])[:10] < REF.date().isoformat()]
    return {"plant": plant, "records": records, "past_due": past_due,
            "submission": sub, "out": tmp / "run"}


def _order_ref(plant, demand) -> str:
    for r in demand.get("external_refs") or []:
        if r.get("type") == "order_id":
            return r["value"]
    return demand["id"][:8]


# ---------------------------------------------------------------------------
# clause (1) + (2) — past-due is work
# ---------------------------------------------------------------------------

class TestPastDueIsWork:
    def test_the_specimen_actually_has_past_due_work(self, specimen):
        """Guard the guard: a fixture that stopped producing past-due orders
        would make every assertion below pass vacuously."""
        assert len(specimen["past_due"]) == 21

    def test_none_are_excluded(self, specimen):
        excluded = set(specimen["plant"].excluded_demand_ids)
        offenders = [d["id"] for d in specimen["past_due"] if d["id"] in excluded]
        assert not offenders, (
            f"{len(offenders)} past-due demands excluded — R-PD1 clause (2)")

    def test_all_are_schedulable(self, specimen):
        schedulable = {d["id"] for d in specimen["plant"].schedulable_demands}
        missing = [d["id"] for d in specimen["past_due"]
                   if d["id"] not in schedulable]
        assert not missing, f"{len(missing)} past-due demands not schedulable"

    def test_reported_as_information_not_as_a_defect(self, specimen):
        """It is not silent — 7.83% of the pilot book is already late — but it is
        INFO and proceeded_flagged, so it can neither degrade a grade nor reach a
        fix-first queue for a condition that has no fix."""
        findings = [r for r in specimen["records"]
                    if r.get("record_type") == "finding"
                    and r.get("code") == "PAST_DUE_AT_INTAKE"]
        assert len(findings) == 1
        f = findings[0]
        assert f["severity"] == "info"
        assert f["disposition"] == "proceeded_flagged"
        assert len(f["subjects"]) == 21

    def test_m3_does_not_borrow_the_gates_code(self, specimen):
        """Add, never repurpose. TEMPORAL_IMPOSSIBILITY means "dates that can't
        both be true" (M0's `due < release/created`); it must not also mean
        "late"."""
        offenders = [r for r in specimen["records"]
                     if r.get("record_type") == "finding"
                     and r.get("code") == "TEMPORAL_IMPOSSIBILITY"
                     and r.get("module") == "M3"]
        assert not offenders

    def test_they_reach_the_board(self, specimen):
        """Clause (1) end to end: admitted AND placed, not merely un-excluded."""
        from mre.modules.rolling_horizon import build_rolling_view
        from mre.modules.schedule_assembler import assemble_rolling_document

        plant = specimen["plant"]
        view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                                  deterministic=True, persist=False,
                                  member_time_limit_s=600.0)
        idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        doc = assemble_rolling_document(
            plant=plant, view=view, schedule_id="s", run_id="r",
            identity_map=idmap).model_dump(mode="json")
        placed = {str(w).upper() for a in doc["assignments"]
                  for w in (a.get("work_orders") or [])}
        past = {_order_ref(plant, d).upper() for d in specimen["past_due"]}
        assert past <= placed, (
            f"{len(past - placed)} past-due orders are not on the board")


# ---------------------------------------------------------------------------
# clause (3) — THE GENERAL GUARD
# ---------------------------------------------------------------------------

class TestGateDispositionBindsDownstream:
    """No module may silently remove a demand the gate passed as
    `proceeded_flagged`. Removal is allowed; SILENT removal is not."""

    @staticmethod
    def _gate_flagged_demand_ids(records, plant) -> set[str]:
        """Demands named by a `proceeded_flagged` M0 finding, in CANONICAL ids.

        The gate speaks SUBMISSION space ("ORD-000014") and the rest of the
        pipeline speaks canonical UUIDs, so the two must be joined through the
        identity map or the guard silently compares empty sets — which would
        make it pass for the wrong reason.
        """
        idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        by_order: dict[str, str] = {}
        for d in plant.demands:
            for r in d.get("external_refs") or []:
                if r.get("type") in ("order_id", "work_order"):
                    by_order[str(r["value"]).upper()] = d["id"]
        out: set[str] = set()
        for rec in records:
            if (rec.get("record_type") != "finding"
                    or rec.get("module") != "M0"
                    or rec.get("disposition") != "proceeded_flagged"):
                continue
            for s in rec.get("subjects") or []:
                sid = str(s.get("entity_id") or "")
                if not sid:
                    continue
                if sid in by_order.values():
                    out.add(sid)
                elif sid.upper() in by_order:
                    out.add(by_order[sid.upper()])
                elif idmap is not None and idmap.external_refs(sid):
                    out.add(sid)
        return out

    def test_the_guard_has_something_to_guard(self, specimen):
        """Non-vacuity. The specimen's gate DOES flag demands and proceed: its
        past-due orders carry a due date before their generated created date, so
        `ids.order_dates_internally_consistent` degrades and passes them on. If
        this set were empty the guard below would prove nothing."""
        flagged = self._gate_flagged_demand_ids(specimen["records"],
                                                specimen["plant"])
        assert flagged, "no M0 proceeded_flagged demand subjects in the specimen"

    def test_no_flagged_demand_is_silently_removed(self, specimen):
        """THE GUARD. For every demand M0 passed as proceeded_flagged, either it
        is still schedulable, or SOME module raised its own EXCLUDED/BLOCKED
        finding about it that NAMES THE REMOVING MODULE in its evidence.

        The failure this catches is not "a demand was excluded" — that is legal.
        It is "a demand the gate said to proceed with disappeared, and no record
        says who did it or why". That is exactly what happened to 21 real orders
        between M0 and M3 (docs/07 §5a.26), undetected until a fixture existed
        that could produce one.
        """
        plant = specimen["plant"]
        flagged = self._gate_flagged_demand_ids(specimen["records"], plant)
        schedulable = {d["id"] for d in plant.schedulable_demands}

        attributed: dict[str, str] = {}
        for rec in specimen["records"]:
            if (rec.get("record_type") != "finding"
                    or rec.get("disposition") not in ("excluded", "blocked")):
                continue
            src = (rec.get("evidence") or {}).get("excluded_by_module")
            for s in rec.get("subjects") or []:
                sid = str(s.get("entity_id") or "")
                if sid and src:
                    attributed[sid] = src

        unexplained = [d for d in flagged
                       if d not in schedulable and d not in attributed]
        assert not unexplained, (
            f"{len(unexplained)} demand(s) the M0 gate passed as "
            f"proceeded_flagged were removed downstream with no finding naming "
            f"the module that removed them: {sorted(unexplained)[:5]}")

    def test_every_exclusion_names_its_module(self, specimen):
        """The same rule stated positively, over ALL exclusions rather than just
        the gate-flagged ones. An exclusion that cannot say who made it is not
        traceable, and traceability is the product."""
        offenders = [
            (rec.get("code"), rec.get("module"))
            for rec in specimen["records"]
            if rec.get("record_type") == "finding"
            and rec.get("disposition") in ("excluded", "blocked")
            and not (rec.get("evidence") or {}).get("excluded_by_module")
            and rec.get("module") == "M3"
        ]
        assert not offenders, f"M3 exclusions with no named source: {offenders}"


# ---------------------------------------------------------------------------
# clause (4) — the tardiness split
# ---------------------------------------------------------------------------

class TestTardinessSplit:
    @pytest.fixture(scope="class")
    def document(self, specimen):
        from mre.modules.rolling_horizon import build_rolling_view
        from mre.modules.schedule_assembler import assemble_rolling_document

        plant = specimen["plant"]
        view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                                  deterministic=True, persist=False,
                                  member_time_limit_s=600.0)
        idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        return assemble_rolling_document(
            plant=plant, view=view, schedule_id="s", run_id="r",
            identity_map=idmap).model_dump(mode="json")

    def test_the_split_is_present_on_a_past_due_book(self, document):
        cs = document["cost_summary"]
        assert cs.get("tardiness_floor") is not None
        assert cs.get("tardiness_controllable") is not None

    def test_it_sums_exactly(self, document):
        """On REAL data, not a mock — 4B.5's parts-sum-exactly discipline."""
        cs = document["cost_summary"]
        assert abs(cs["tardiness"]
                   - (cs["tardiness_floor"] + cs["tardiness_controllable"])) < 0.01

    def test_the_total_still_decomposes(self, document):
        """The split DECOMPOSES tardiness; it must not also be added to total."""
        cs = document["cost_summary"]
        parts = (cs["production_regular"] + cs["production_overtime"]
                 + cs["setup"] + cs["tardiness"])
        assert abs(cs["total"] - parts) < 0.01

    def test_the_floor_dominates_and_that_is_the_point(self, document):
        """If the floor were folded into one number, a planner would read the
        plant's whole accumulated lateness as this schedule's doing."""
        cs = document["cost_summary"]
        assert cs["tardiness_floor"] > cs["tardiness_controllable"]

    def test_per_demand_outcomes_carry_it_too(self, document):
        late = [s for s in document["service_outcomes"]
                if s.get("tardiness_floor_min")]
        assert late, "no service outcome carries a floor on a past-due book"
        for s in late:
            assert s["tardiness_floor_min"] <= s["lateness_min"], (
                "the floor is part of the lateness, never more than all of it")

    def test_absent_when_there_is_nothing_to_split(self):
        """Contract 1.11's byte-identity rule: no past-due work, no split — the
        pair is present TOGETHER or not at all."""
        from mre.contracts.schedule_document import CostSummary

        cs = CostSummary(total=10.0, production_regular=4.0,
                         production_overtime=0.0, setup=3.0, tardiness=3.0)
        assert cs.tardiness_floor is None
        assert cs.tardiness_controllable is None

    def test_a_half_present_split_is_rejected(self):
        from mre.contracts.schedule_document import CostSummary

        with pytest.raises(ValueError, match="half-present"):
            CostSummary(total=10.0, production_regular=4.0,
                        production_overtime=0.0, setup=3.0, tardiness=3.0,
                        tardiness_floor=1.0)

    def test_an_inexact_split_is_rejected(self):
        from mre.contracts.schedule_document import CostSummary

        with pytest.raises(ValueError, match="tardiness does not decompose"):
            CostSummary(total=10.0, production_regular=4.0,
                        production_overtime=0.0, setup=3.0, tardiness=3.0,
                        tardiness_floor=1.0, tardiness_controllable=1.0)


# ---------------------------------------------------------------------------
# clause (6) — the three measured answers
# ---------------------------------------------------------------------------

class TestTheThreeAnswers:
    """4B.10 measured three answers on this specimen; two were FALSE and one was
    true-but-useless. Each is pinned here in the words a planner would recognize.
    Driven at the ROUTE level: the dispatch is a model's job (R-AI5(1)) and is
    not what these assertions are about.
    """

    @pytest.fixture(scope="class")
    def asker(self, specimen):
        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.explainer import Explainer
        from mre.modules.renderers import TemplateRenderer
        from mre.modules.rolling_horizon import build_rolling_view
        from mre.modules.schedule_assembler import assemble_rolling_document
        from mre.modules.snapshot_store import SnapshotStore

        plant = specimen["plant"]
        view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                                  deterministic=True, persist=True,
                                  member_time_limit_s=600.0)
        idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        doc = assemble_rolling_document(
            plant=plant, view=view, schedule_id="s", run_id="r",
            identity_map=idmap).model_dump(mode="json")
        out = plant.out_dir
        index = EvidenceIndex().build(out / "runs")
        ex = Explainer(SnapshotStore(out / "snapshots"), index,
                       snapshot_id=plant.snapshot_id)
        specimen_order = _order_ref(
            plant, sorted(specimen["past_due"], key=lambda d: str(d["due"]))[0])

        def ask(route, **params):
            params.setdefault("question", "")
            return TemplateRenderer().render(ex.route(route, params))

        return {"ask": ask, "order": specimen_order, "doc": doc, "ex": ex}

    def test_where_is_it(self, asker):
        """WAS: "Nothing scheduled for ORD-000014." — true, and indistinguishable
        from an order that was simply not placed."""
        answer = asker["ask"]("order-schedule", order=asker["order"],
                              question=f"where is {asker['order']}?")
        assert "Nothing scheduled" not in answer
        assert asker["order"] in answer
        assert "operation(s)" in answer

    def test_why_isnt_it_scheduled_yet(self, asker):
        """WAS: a disjunction NEITHER BRANCH OF WHICH IS TRUE — "it's either
        already in the current window ... or not part of this schedule"."""
        answer = asker["ask"]("why-not-scheduled-yet", order=asker["order"],
                              document=asker["doc"],
                              question=f"why isn't {asker['order']} scheduled yet?")
        assert "either" not in answer.lower()
        assert "IS scheduled" in answer
        # clause (4): the split travels with the per-order answer
        assert "already unavoidable" in answer

    def test_which_orders_are_late(self, asker):
        """WAS: "No late orders found in this schedule." — in a world where 35%
        of the book is already past due. The demo-ending answer."""
        answer = asker["ask"]("late-orders",
                              question="which orders are already late?")
        assert "No late orders found" not in answer
        assert "late order(s)" in answer
        assert "ALREADY PAST DUE" in answer
        assert "unavoidable at the start" in answer

    def test_a_single_order_question_is_not_answered_with_the_aggregate(self, asker):
        """CU4(d): "why was ORD-X excluded?" used to return all 21 exclusions
        with the subject resolved as "excluded orders"."""
        answer = asker["ask"]("excluded-orders", order=asker["order"],
                              question=f"why was {asker['order']} excluded?")
        assert asker["order"] in answer
        assert "21 data-quality" not in answer

    def test_no_raw_uuid_reaches_the_planner(self, asker):
        """CU4(c). A 36-character canonical id in an answer is a defect: the
        planner cannot act on it and is invited to paste it back."""
        import re
        for route, params in (
            ("late-orders", {}),
            ("excluded-orders", {}),
            ("excluded-orders", {"order": asker["order"]}),
        ):
            answer = asker["ask"](route, **params)
            uuids = re.findall(
                r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", answer)
            assert not uuids, f"{route} leaked canonical ids: {uuids[:3]}"


# ---------------------------------------------------------------------------
# CU5 — the exclusion note's arithmetic
# ---------------------------------------------------------------------------

class TestExclusionArithmetic:
    """4B.10 reported, undiagnosed: "60 of 102 orders are scheduled; 42 excluded"
    in a world of 60 demands with 21 exclusions. Two compounding errors, both in
    `Explainer._excluded_summary` — see its docstring. The world here has GENUINE
    data-defect exclusions (quantity <= 0), which clause (2) permits."""

    @pytest.fixture(scope="class")
    def defect_world(self, tmp_path_factory, specimen):
        import csv
        import shutil

        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.explainer import Explainer
        from mre.modules.rolling_horizon import prepare_plant
        from mre.modules.snapshot_store import SnapshotStore

        tmp = tmp_path_factory.mktemp("pastdue_defect")
        sub = tmp / "submission"
        shutil.copytree(specimen["submission"], sub)
        rows = list(csv.DictReader((sub / "orders.csv").open(encoding="utf-8")))
        for r in rows[:3]:
            r["quantity"] = "0"
        with (sub / "orders.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        plant = prepare_plant(sub, tmp / "run", reference_date=REF)
        index = EvidenceIndex().build(plant.out_dir / "runs")
        ex = Explainer(SnapshotStore(plant.out_dir / "snapshots"), index,
                       snapshot_id=plant.snapshot_id)
        return {"plant": plant, "ex": ex}

    def test_the_world_has_exclusions(self, defect_world):
        assert len(defect_world["plant"].excluded_demand_ids) == 3

    def test_the_note_reconciles(self, defect_world):
        summary = defect_world["ex"]._excluded_summary()
        assert summary is not None
        n_demands = len(defect_world["plant"].demands)
        assert summary["count"] == 3
        assert summary["scheduled"] + summary["count"] == summary["total"]
        assert summary["total"] == n_demands

    def test_it_counts_orders_not_id_tokens(self, defect_world):
        """The 42 was 21 orders × 2 id-spaces. The MATCH set may still hold both
        (a planner who pastes a UUID must still be understood); the COUNT may
        not."""
        ex = defect_world["ex"]
        assert len(ex._excluded_labels) > len(ex._excluded_order_labels)
        assert len(ex._excluded_order_labels) == 3

    def test_it_names_orders_not_uuids(self, defect_world):
        for name in defect_world["ex"]._excluded_summary()["orders"]:
            assert not (len(name) == 36 and name.count("-") == 4), name
            assert name.startswith("ORD-")


# ---------------------------------------------------------------------------
# CU1 — the cost proof (docs/07 §5a.23)
# ---------------------------------------------------------------------------

class TestCostProof:
    """4B.10 measured five runs of one instance differing only in the solver's
    random seed splitting 4 OPTIMAL / 1 FEASIBLE, the unproved run's ledger
    13.056% dearer. `solver.status` was the only thing distinguishing them and
    nothing rendered it."""

    def test_a_proved_board_says_so_and_volunteers_nothing(self):
        from mre.modules.cost_proof import CostProof

        p = CostProof(status="OPTIMAL", gap=0.0, tiebreak_status="FEASIBLE")
        assert p.proved and not p.unproved
        assert p.chip()["state"] == "proved"
        # An unproven TIEBREAK never downgrades a proven COST (contract 1.10).
        assert "cost optimum proved" in p.chip()["label"]
        assert p.rider() is None

    def test_an_unproved_board_carries_its_gap(self):
        from mre.modules.cost_proof import CostProof

        p = CostProof(status="FEASIBLE", gap=0.1147)
        assert p.unproved
        assert "11.5%" in p.chip()["label"]
        assert "11.5%" in p.rider()

    def test_an_unreported_gap_is_never_rendered_as_zero(self):
        from mre.modules.cost_proof import CostProof

        p = CostProof(status="FEASIBLE", gap=None)
        assert "0.0%" not in p.chip()["label"]
        assert "unknown" in p.rider()

    def test_a_skipped_tiebreak_is_distinguishable_from_a_lost_one(self):
        from mre.modules.cost_proof import CostProof

        skipped = CostProof(status="OPTIMAL",
                            tiebreak_skipped_reason="budget_exhausted_by_stage1")
        ran = CostProof(status="OPTIMAL", tiebreak_status="FEASIBLE")
        assert "did not run" in skipped.chip()["title"]
        assert "did not prove out" in ran.chip()["title"]

    def test_no_solve_is_not_a_failure_to_prove(self):
        from mre.modules.cost_proof import CostProof

        p = CostProof(status="NO_ADMISSION")
        assert p.no_solve and not p.proved and not p.unproved
        assert p.rider() is None

    def test_the_rider_lands_on_a_money_answer_only(self):
        """The rule is narrow on purpose: an unproved board qualifies its COST
        claims, not every sentence it utters."""
        from mre.modules.cost_proof import CostProof
        from mre.modules.explainer import ExplanationBundle
        from mre.modules.renderers import apply_cost_proof_rider

        unproved = CostProof(status="FEASIBLE", gap=0.1147)
        bundle = ExplanationBundle(
            question="q", subject_id="s", subject_type="late_orders",
            subject_external_name="all", ordered_records=[],
            key_facts={"cost_proof": unproved}, snapshot_id="snap")
        assert apply_cost_proof_rider(bundle, "It costs $1,234.00.") is not None
        assert apply_cost_proof_rider(bundle, "ORD-01 is on M-02.") is None

    def test_a_proved_board_adds_no_rider_to_a_money_answer(self):
        from mre.modules.cost_proof import CostProof
        from mre.modules.explainer import ExplanationBundle
        from mre.modules.renderers import apply_cost_proof_rider

        bundle = ExplanationBundle(
            question="q", subject_id="s", subject_type="late_orders",
            subject_external_name="all", ordered_records=[],
            key_facts={"cost_proof": CostProof(status="OPTIMAL", gap=0.0)},
            snapshot_id="snap")
        assert apply_cost_proof_rider(bundle, "It costs $1,234.00.") is None

    def test_the_proof_reaches_the_answer_surface_from_evidence(self, specimen):
        """The answer and the board must read ONE record — the M6
        `solve_complete` event — not two derivations kept in step."""
        from mre.modules.cost_proof import from_evidence
        from mre.modules.evidence_index import EvidenceIndex
        from mre.modules.rolling_horizon import build_rolling_view

        plant = specimen["plant"]
        build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                           deterministic=True, persist=True,
                           member_time_limit_s=600.0)
        index = EvidenceIndex().build(plant.out_dir / "runs")
        proof = from_evidence(index)
        assert proof.status in ("OPTIMAL", "FEASIBLE")
        assert not proof.no_solve

    def test_the_rolling_document_carries_the_gap(self, specimen):
        """Before 4B.11 the rolling assembler wrote `SolverBlock(gap=None)`
        unconditionally, so an unproved rolling board could say "not proved" and
        never "by how much"."""
        from mre.modules.rolling_horizon import build_rolling_view
        from mre.modules.schedule_assembler import assemble_rolling_document

        plant = specimen["plant"]
        view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                                  deterministic=True, persist=False,
                                  member_time_limit_s=600.0)
        doc = assemble_rolling_document(plant=plant, view=view, schedule_id="s",
                                        run_id="r").model_dump(mode="json")
        solver = doc["solver"]
        if solver["status"] != "OPTIMAL":
            assert solver["gap"] is not None, (
                "an unproved rolling board must state its gap")
        assert solver["objective"] is not None
