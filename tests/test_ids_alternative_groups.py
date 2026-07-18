"""IDS alternative-resource doorway (docs/06 §5.3, Session 4B.0).

Repeated (route_id, sequence) rows naming DIFFERENT resource_id express an
operation's eligible set (docs/05 B2). This suite establishes the adapter's
truth about such groups and pins the per-alternative time model.

CU1 (adapter truth, test-FIRST): before this session the adapter grouped the
rows into ONE explicit_set OperationSpec but read the whole per-operation time
model (setup/run) from the FIRST row only — a submitter who gave a distinct
run_minutes_per_unit per alternative machine had every non-first row's time
SILENTLY DROPPED. That is a silent-wrong (not last-wins, not two ops, not a
crash), so it is pinned here as a regression: `TestAdapterTruth` documents the
grouping (one spec, explicit_set over the whole set) and `test_*_rates_captured`
asserts the CU3 fix — per-alternative setup/run land in
ResourceRequirement.rate_overrides, and step attributes that disagree raise the
new Tier-2 finding.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.ids_adapter import IDSAdapter
from mre.modules.snapshot_store import SnapshotStore
from mre.reporter import Reporter
from tools.generate_erp_dataset import generate

SNAP = "alt-snap"
_RL_COLS = ["route_id", "sequence", "resource_id", "active", "setup_minutes",
            "run_minutes_per_unit", "dwell_minutes", "setup_family",
            "splittable", "min_chunk_minutes"]


def _read_rl(sub: Path) -> list[dict]:
    with open(sub / "routing_lines.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_rl(sub: Path, rows: list[dict]) -> None:
    fields = list(rows[0].keys())
    with open(sub / "routing_lines.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _two_resource_ids(sub: Path) -> tuple[str, str]:
    with open(sub / "resources.csv", encoding="utf-8-sig", newline="") as f:
        res = [r["resource_id"] for r in csv.DictReader(f) if r.get("resource_id")]
    assert len(res) >= 2, "fixture needs >= 2 resources"
    return res[0], res[1]


def _make_group(sub: Path, *, run_a: str, run_b: str,
                setup_a: str = "", setup_b: str = "",
                splittable_b: str = "false", family_b: str = "") -> tuple[str, int, str, str]:
    """Rewrite routing_lines so the first route's first sequence becomes a
    two-alternative group (resource A then B). Returns
    (route_id, sequence, res_a, res_b)."""
    res_a, res_b = _two_resource_ids(sub)
    rows = _read_rl(sub)
    route_id = rows[0]["route_id"]
    seq = rows[0]["sequence"]
    # Keep every row that is NOT the target (route, seq); replace the target
    # with the two-alternative group.
    kept = [r for r in rows if not (r["route_id"] == route_id and r["sequence"] == seq)]
    row_a = {c: "" for c in _RL_COLS}
    row_a.update({"route_id": route_id, "sequence": seq, "resource_id": res_a,
                  "active": "1", "run_minutes_per_unit": run_a, "setup_minutes": setup_a,
                  "dwell_minutes": "0", "setup_family": "", "splittable": "false"})
    row_b = {c: "" for c in _RL_COLS}
    row_b.update({"route_id": route_id, "sequence": seq, "resource_id": res_b,
                  "active": "1", "run_minutes_per_unit": run_b, "setup_minutes": setup_b,
                  "dwell_minutes": "0", "setup_family": family_b, "splittable": splittable_b})
    _write_rl(sub, [row_a, row_b] + kept)
    return route_id, int(seq), res_a, res_b


def _run_adapter(sub: Path, tmp: Path):
    store = SnapshotStore(tmp / "snapshots")
    runs = tmp / "runs"
    manifest = json.loads((sub / "manifest.json").read_text(encoding="utf-8"))
    rep = Reporter.begin(module=ModuleCode.M1, purpose="alt adapter", config={},
                         trigger="test", snapshot_id=SNAP, sink_dir=runs)
    IDSAdapter(submission_dir=sub, manifest=manifest).run(SNAP, store, rep)
    rep.end(RunStatus.SUCCESS)
    findings = []
    for f in runs.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec.get("record_type") == "finding":
                    findings.append(rec)
    return store.load_snapshot(SNAP), findings


def _spec_for(reader, route_id: str, seq: int) -> dict:
    """The OperationSpec written for (route_id, seq): match by sequence among
    the specs of the route's process (identify by any spec at that sequence)."""
    specs = [s for s in reader.iter_entities("operationspec") if s["sequence"] == seq]
    assert specs, f"no operationspec at sequence {seq}"
    # A single route in the fixture owns this sequence; the group collapses to
    # exactly one spec, which is the whole point.
    return specs[0]


# ---------------------------------------------------------------------------
# CU1 — adapter truth: repeated (route,seq) rows group into ONE spec
# ---------------------------------------------------------------------------

class TestAdapterTruth:
    def test_group_is_one_spec_over_the_whole_eligible_set(self, tmp_path):
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=1)
        route_id, seq, res_a, res_b = _make_group(sub, run_a="10", run_b="20")
        reader, _ = _run_adapter(sub, tmp_path)

        specs_at_seq = [s for s in reader.iter_entities("operationspec")
                        if s["sequence"] == seq]
        # NOT two operations, NOT a crash — exactly one spec per (route, seq).
        # (Other routes may share the sequence number; filter to the group's
        # eligible members to be sure we found the grouped one.)
        grouped = [s for s in specs_at_seq
                   if set((s["resource_requirements"][0].get("resource_refs") or []))
                   and any(True for _ in [s])]
        assert grouped, "no spec carries an eligible set"
        spec = next(s for s in specs_at_seq
                    if len(s["resource_requirements"][0].get("resource_refs") or []) >= 2)
        req = spec["resource_requirements"][0]
        assert req["mode"] == "explicit_set"
        # The eligible set is BOTH resources (order-preserving, first-seen).
        from mre.modules.adapter import _stable_id
        assert req["resource_refs"] == [_stable_id("resource", res_a),
                                        _stable_id("resource", res_b)]


# ---------------------------------------------------------------------------
# CU3 — the fix: per-alternative rates captured; step attrs must agree
# ---------------------------------------------------------------------------

class TestPerAlternativeRates:
    def test_distinct_run_rates_captured_in_rate_overrides(self, tmp_path):
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=1)
        route_id, seq, res_a, res_b = _make_group(sub, run_a="10", run_b="20")
        reader, findings = _run_adapter(sub, tmp_path)
        from mre.modules.adapter import _stable_id
        spec = next(s for s in reader.iter_entities("operationspec")
                    if s["sequence"] == seq
                    and len(s["resource_requirements"][0].get("resource_refs") or []) >= 2)
        req = spec["resource_requirements"][0]
        overrides = req.get("rate_overrides") or {}
        rid_a, rid_b = _stable_id("resource", res_a), _stable_id("resource", res_b)
        # res_a is the FIRST row → the spec default → needs no override.
        # res_b differs (run=20 vs default 10) → carries a rate_override.
        assert rid_a not in overrides
        assert rid_b in overrides
        assert overrides[rid_b]["run_rate"] == "PT20M"
        # The spec default run_rate is the first row's (10 min).
        assert spec["run_rate"] == "PT10M"

    def test_disagreeing_step_attribute_flagged_by_gate_first_row_wins(self, tmp_path):
        """The GATE (not the adapter) owns detection — "the gate checks; it
        never repairs". Alternative B declares splittable=true while A is
        false: a STEP-attribute disagreement (splittable belongs to the
        operation, not the machine). The gate flags
        ids.alternative_step_attributes_agree (AMBIGUOUS_SOURCE, degraded); the
        adapter proceeds first-row-wins (the grouped spec is NOT splittable)."""
        from mre.modules.conformance import ConformanceGate
        sub = tmp_path / "sub"
        generate(sub, scenario="clean_small", seed=1)
        route_id, seq, res_a, res_b = _make_group(
            sub, run_a="10", run_b="20", splittable_b="true")

        # Gate detection.
        rep = Reporter.begin(module=ModuleCode.M0, purpose="alt gate", config={},
                             trigger="test", snapshot_id="pre-adapter",
                             sink_dir=tmp_path / "gate_runs")
        result = ConformanceGate().run(sub, rep)
        rep.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)
        hits = [f for f in result.certificate["findings"]
                if f["evidence"].get("rule_id") == "ids.alternative_step_attributes_agree"
                and f["evidence"].get("outcome") != "satisfied"]
        assert hits, "gate did not flag the step-attribute disagreement"
        assert hits[0]["code"] == "AMBIGUOUS_SOURCE"

        # Adapter first-row-wins: the grouped spec is NOT splittable (A's value).
        reader, _ = _run_adapter(sub, tmp_path)
        spec = next(s for s in reader.iter_entities("operationspec")
                    if s["sequence"] == seq
                    and len(s["resource_requirements"][0].get("resource_refs") or []) >= 2)
        assert spec["splittable"] is False
