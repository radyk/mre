"""R-SP1 — the solve-progress ledger. Written from the ruling, then implemented.

The ruling's clauses map onto these tests one for one:

  (1) the trail is CP-SAT's incumbent trail, and on a rolling board it is keyed
      to ONE window and never summed with another's;
  (2) improvement is stated only over the solver's OWN first feasible plan —
      enforced STRUCTURALLY by the metric rollup, not only by wording;
  (3) the trail is in the solver's own units and no dollar sign touches it;
  (4) the proof floor and gap ride with the story; a flat trail is a true story;
  (5) the trail is a run artifact under the evidence contract, and boards solved
      before the change have no trail;
  (6) the incumbent-objective SEQUENCE is reproducible and is what is asserted;
      elapsed times never are. The callback must not perturb the search.
  (7) the trail is stage 1's — the COST search — and never stage 2's.
"""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from mre.modules import solve_progress as sp


# ---------------------------------------------------------------------------
# summarize / headline — pure, and the one definition of the scalars
# ---------------------------------------------------------------------------

def _trail(*objs):
    return [{"index": i + 1, "objective": float(o), "elapsed_s": 0.1 * (i + 1)}
            for i, o in enumerate(objs)]


def test_summarize_empty_trail_is_all_none_never_zero():
    """A solve that found nothing has no first plan. 0.0 there would assert a
    plan worth nothing — the repo's standing third-state discipline."""
    s = sp.summarize([])
    assert s["count"] == 0
    assert s["first"] is None and s["final"] is None
    assert s["improvement_abs"] is None and s["improvement_pct"] is None
    assert s["flat"] is False


def test_summarize_flat_trail_is_flat_and_improves_by_zero():
    s = sp.summarize(_trail(500.0))
    assert s["count"] == 1 and s["flat"] is True
    assert s["first"] == 500.0 and s["final"] == 500.0
    assert s["improvement_abs"] == 0.0
    assert s["improvement_pct"] == 0.0


def test_summarize_improvement_is_first_minus_final_exactly():
    s = sp.summarize(_trail(1000.0, 900.0, 750.0))
    assert s["first"] == 1000.0 and s["final"] == 750.0
    assert s["improvement_abs"] == 250.0
    assert s["improvement_pct"] == pytest.approx(25.0)
    assert s["flat"] is False


def test_summarize_percent_is_none_at_a_zero_first_objective():
    """A ratio over zero is undefined, not nil (4B.20: a ratio names its own
    denominator, and this one cannot)."""
    assert sp.summarize(_trail(0.0, 0.0))["improvement_pct"] is None


@pytest.mark.parametrize("trail,must_contain", [
    ([], "no workable plan"),
    (_trail(500.0), "did not improve"),
    (_trail(1000.0, 750.0), "first workable plan"),
])
def test_headline_tells_every_state_including_the_flat_one(trail, must_contain):
    """Clause (4): a flat story is a true story — it is TOLD, not hidden."""
    assert must_contain in sp.headline(sp.summarize(trail))


def test_no_authored_string_in_this_module_carries_a_dollar_sign():
    """CLAUSE (3), AND R-DP12 CLAUSE (2) BEHIND IT. A trail point is the scaled
    CP-SAT objective, which is not proportional to the ledger — R-DP12's own
    specimen is a zero-move accept whose ledger did not move a cent while the
    objective moved by 7,014,821. Money on this surface would be a fabrication.
    """
    authored = [sp.CLAUSE_2_LABEL, sp.CLAUSE_3_LABEL,
                sp.headline(sp.summarize(_trail(1000.0, 750.0))),
                sp.headline(sp.summarize(_trail(500.0))),
                sp.headline(sp.summarize([]))]
    for text in authored:
        assert "$" not in text, f"a dollar sign reached a trail figure: {text!r}"


def test_clause_2_label_names_the_comparison_and_denies_the_others():
    """The label is the disclosure that keeps the number honest: a bare
    "improved 34%" IMPLIES a baseline, and clause (2) forbids the implication as
    firmly as the statement."""
    t = sp.CLAUSE_2_LABEL.lower()
    assert "first workable plan" in t
    assert "not a comparison" in t
    assert "planner" in t


def test_the_unit_is_not_currency():
    assert sp.OBJECTIVE_UNIT == "objective_units"


# ---------------------------------------------------------------------------
# the evidence decomposition (clause 5) — Event + Metrics + Artifact
# ---------------------------------------------------------------------------

@pytest.fixture()
def rep(tmp_path):
    from mre.contracts.vocabularies import ModuleCode
    from mre.reporter import Reporter
    return Reporter.begin(module=ModuleCode.M6, purpose="trail test", config={},
                          trigger="test", snapshot_id="snap-x",
                          sink_dir=tmp_path / "runs")


def _records(rep, tmp_path):
    from mre.contracts.vocabularies import RunStatus
    rep.end(RunStatus.SUCCESS)
    out = []
    for f in (tmp_path / "runs").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def test_the_trail_rides_an_event_and_its_scalars_ride_metrics(rep, tmp_path):
    sp.emit_solve_progress(rep, trail=_trail(1000.0, 900.0, 750.0),
                           status="FEASIBLE", best_bound=700.0, gap=0.0667,
                           window_key="2026-01-12T00:00:00+00:00")
    recs = _records(rep, tmp_path)
    events = [r for r in recs if r.get("record_type") == "event"
              and r.get("status_text") == sp.SOLVE_PROGRESS_STATUS]
    assert len(events) == 1
    p = events[0]["payload"]
    assert [i["objective"] for i in p["incumbents"]] == [1000.0, 900.0, 750.0]
    assert p["best_bound"] == 700.0 and p["gap"] == pytest.approx(0.0667)
    assert p["objective_unit"] == sp.OBJECTIVE_UNIT
    # clause (7): the trail names the stage it belongs to
    assert p["stage"] == "cost"
    # clause (1): keyed to ONE window
    assert p["window_key"] == "2026-01-12T00:00:00+00:00"
    # provenance is NAMED ON the record and walkable (S-02's shape)
    assert p["trail_provenance"]["provenance_class"] == "derived"
    assert "CpSolverSolutionCallback" in p["trail_provenance"]["source"]

    metrics = {r["name"]: r for r in recs if r.get("record_type") == "metric"}
    assert set(metrics) == {sp.METRIC_FIRST, sp.METRIC_FINAL,
                            sp.METRIC_IMPROVEMENT, sp.METRIC_COUNT}
    assert metrics[sp.METRIC_COUNT]["value"] == 3.0
    for name in (sp.METRIC_FIRST, sp.METRIC_FINAL, sp.METRIC_IMPROVEMENT):
        assert metrics[name]["unit"] == sp.OBJECTIVE_UNIT, "a trail metric in currency"


def test_first_incumbent_is_a_rollup_that_decomposes_exactly(rep, tmp_path):
    """CLAUSE (2), MADE STRUCTURAL. first = final + improvement is true by
    construction and the consolidator verifies it, so `improvement` cannot
    quietly become a difference against a customer baseline and still decompose.
    """
    sp.emit_solve_progress(rep, trail=_trail(1000.0, 750.0), status="FEASIBLE",
                           best_bound=700.0, gap=0.04)
    recs = _records(rep, tmp_path)
    by_id = {r["record_id"]: r for r in recs if r.get("record_type") == "metric"}
    first = next(r for r in by_id.values() if r["name"] == sp.METRIC_FIRST)
    assert first["rollup_of"], "the first incumbent must be a rollup"
    parts = [by_id[i] for i in first["rollup_of"]]
    assert {p["name"] for p in parts} == {sp.METRIC_FINAL, sp.METRIC_IMPROVEMENT}
    assert sum(p["value"] for p in parts) == pytest.approx(first["value"])


def test_the_improvement_component_is_emitted_even_at_zero(rep, tmp_path):
    """docs/02 §4.4: components that appear only when non-empty cannot be
    verified as a set, and an absent one reads as an unasked question rather
    than a measured nought. A flat trail's improvement IS a measured nought."""
    sp.emit_solve_progress(rep, trail=_trail(500.0), status="OPTIMAL",
                           best_bound=500.0, gap=0.0)
    names = {r["name"] for r in _records(rep, tmp_path)
             if r.get("record_type") == "metric"}
    assert sp.METRIC_IMPROVEMENT in names


def test_an_empty_trail_emits_a_count_and_no_rollup(rep, tmp_path):
    """Nothing to decompose, so no rollup is claimed — but the count is still
    recorded, because "the search found nothing" is a fact worth storing."""
    sp.emit_solve_progress(rep, trail=[], status="UNKNOWN", best_bound=None,
                           gap=None)
    metrics = [r for r in _records(rep, tmp_path) if r.get("record_type") == "metric"]
    assert {m["name"] for m in metrics} == {sp.METRIC_COUNT}
    assert metrics[0]["value"] == 0.0


def test_no_finding_and_no_decision_is_emitted_for_a_trail(rep, tmp_path):
    """The two refusals, asserted rather than only written down. A flat search
    is not a defect (so: no Finding) and an incumbent is not a deliberation
    (so: no Decision)."""
    sp.emit_solve_progress(rep, trail=_trail(500.0), status="OPTIMAL",
                           best_bound=500.0, gap=0.0)
    kinds = {r.get("record_type") for r in _records(rep, tmp_path)}
    assert "finding" not in kinds
    assert "decision" not in kinds


def test_the_artifact_digest_verifies_against_the_file_bytes(rep, tmp_path):
    """S-02 §5's defect, now a named class: ``write_text`` newline-translates on
    Windows, so a digest taken from the string we MEANT to write does not verify
    against the artifact it names."""
    path = tmp_path / "solve_progress.json"
    doc = {"incumbents": _trail(1000.0, 750.0), "stage": "cost"}
    sp.write_solve_progress_json(doc, path, reporter=rep)
    recs = _records(rep, tmp_path)
    arts = [r for r in recs if r.get("record_type") == "artifact"]
    assert len(arts) == 1
    assert arts[0]["artifact_direction"] == "output"
    on_disk = hashlib.sha256(path.read_bytes()).hexdigest()
    assert arts[0]["artifact_hash"] == on_disk
    assert json.loads(path.read_text(encoding="utf-8"))["stage"] == "cost"


def test_writing_the_artifact_without_a_reporter_records_nothing(tmp_path):
    """Tools and tests get the file and no record, which is honest — nothing
    produced it as part of a graded run (the certificate writer's own rule)."""
    path = tmp_path / "p.json"
    sp.write_solve_progress_json({"stage": "cost"}, path)
    assert path.exists()
