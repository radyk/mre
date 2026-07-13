"""Tests for tools/generate_erp_dataset.py — the IDS's executable twin.

Each scenario preset must emit a structurally valid IDS submission (required
files + manifest) and a truth_manifest.json whose expected_certificate_grade
matches what the gate should compute. clean_large is marked slow (3000 orders).
"""
from __future__ import annotations

import json

import pytest

from tools.generate_erp_dataset import SCENARIOS, generate

REQUIRED_FILES = (
    "manifest.json", "orders.csv", "routings.csv", "routing_lines.csv",
    "products.csv", "resources.csv", "cost_model.json",
)


@pytest.mark.parametrize(
    "scenario",
    [s for s in SCENARIOS if s != "clean_large" and not SCENARIOS[s].get("feel")],
)
def test_scenario_emits_required_files(tmp_path, scenario):
    out = tmp_path / scenario
    generate(out, scenario=scenario, seed=1)
    for fname in REQUIRED_FILES:
        if scenario == "rejected" and fname == "manifest.json":
            continue  # rejected's own anomaly deletes calendars.csv, not manifest
        assert (out / fname).exists(), f"{fname} missing for scenario {scenario}"
    assert (out / "truth_manifest.json").exists()


@pytest.mark.parametrize(
    "scenario",
    [s for s in SCENARIOS if s != "clean_large" and not SCENARIOS[s].get("feel")],
)
def test_truth_manifest_shape(tmp_path, scenario):
    out = tmp_path / scenario
    truth = generate(out, scenario=scenario, seed=2)
    assert truth["scenario"] == scenario
    assert truth["expected_certificate_grade"] in ("REJECTED", "CONDITIONAL", "ACCEPTED")
    assert truth["expected_costing_grade"] in ("C0", "C1", "C2", "C3")
    on_disk = json.loads((out / "truth_manifest.json").read_text(encoding="utf-8"))
    assert on_disk == truth


def test_clean_small_is_deterministic(tmp_path):
    a = generate(tmp_path / "a", scenario="clean_small", seed=42)
    b = generate(tmp_path / "b", scenario="clean_small", seed=42)
    orders_a = (tmp_path / "a" / "orders.csv").read_text(encoding="utf-8")
    orders_b = (tmp_path / "b" / "orders.csv").read_text(encoding="utf-8")
    assert orders_a == orders_b
    assert a["expected_certificate_grade"] == b["expected_certificate_grade"] == "ACCEPTED"


def test_clean_small_has_no_anomalies(tmp_path):
    truth = generate(tmp_path / "clean", scenario="clean_small", seed=1)
    assert truth["anomalies"] == []
    assert truth["expected_certificate_grade"] == "ACCEPTED"


def test_rejected_scenario_omits_calendars(tmp_path):
    out = tmp_path / "rejected"
    truth = generate(out, scenario="rejected", seed=1)
    assert not (out / "calendars.csv").exists()
    assert truth["expected_certificate_grade"] == "REJECTED"


def test_cli_anomaly_override(tmp_path):
    out = tmp_path / "custom"
    truth = generate(
        out, orders=50, resources=6, facilities=1, seed=3,
        scenario="clean_small", anomalies=["duplicate_order_ids:5"],
    )
    assert truth["orders"] == 50
    assert truth["expected_certificate_grade"] == "CONDITIONAL"
    assert truth["anomalies"][0]["anomaly"] == "duplicate_order_ids"


def test_busy_board_is_a_feel_fixture(tmp_path):
    """busy_board is a FEEL fixture: it emits a valid IDS submission plus a
    feel_fixture.json marker, and NEVER a truth_manifest.json — so it is not
    treated as a truth-bearing test scenario. It carries multi-eligible ops
    throughout (the property the gesture surface needs)."""
    import csv as _csv
    from collections import Counter

    out = tmp_path / "busy_board"
    marker = generate(out, scenario="busy_board", seed=1)
    for fname in REQUIRED_FILES:
        assert (out / fname).exists(), f"{fname} missing for busy_board"
    assert (out / "feel_fixture.json").exists()
    assert not (out / "truth_manifest.json").exists()
    assert marker["feel_fixture"] is True

    # Multi-eligible ops throughout: some (route_id, sequence) group names >1
    # resource, and near-equivalent-but-distinct rates give ghosts a price.
    lines = list(_csv.DictReader((out / "routing_lines.csv").open(encoding="utf-8")))
    grp = Counter((r["route_id"], r["sequence"]) for r in lines)
    assert max(grp.values()) > 1, "expected multi-eligible ops (shared route_id+sequence)"
    rates = set(marker["busy_board"]["resource_rates"].values())
    assert len(rates) == marker["resources"], "rates must be distinct per machine"


@pytest.mark.slow
def test_clean_large_generates(tmp_path):
    out = tmp_path / "clean_large"
    truth = generate(out, scenario="clean_large", seed=1)
    assert truth["orders"] == 3000
    assert truth["expected_certificate_grade"] == "ACCEPTED"
