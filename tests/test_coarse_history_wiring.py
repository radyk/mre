"""Session 4B.6a CU1 — THE PREDICTION STORE IS WIRED.

4B.6 shipped ``coarse_predictions.py`` tested and round-tripped, and no roll
ever wrote to it. The mechanism existed; the history did not. Every day unwired
was a day of calibration data that could not be recovered — which was the whole
argument for shipping the unit in the first place.

These tests are written from the session's three named constraints, plus the
accrual proof:

  (a) THE DOCUMENT IS BYTE-IDENTICAL with the store enabled and disabled.
      Persistence is a SIDE-CHANNEL; it must not touch what the planner sees.
  (b) A STORE WRITE FAILURE DOES NOT LOSE A SCHEDULE AND IS NOT SWALLOWED. The
      solve completes, the schedule is registered, and the failure is recorded
      and surfaced on the run. Silent failure here is worse than no store at
      all: it manufactures a false belief that history is accruing.
  (c) REALIZATION CAPTURE FIRES ON BOTH INTAKE PATHS — natural roll and gravity
      admission — END TO END THROUGH THE WORKER, not just at the unit level.
  (d) IT ACCRUES: two consecutive rolls, and the store holds roll 1's
      predictions realized against roll 2. A store that is wired but empty after
      two rolls is not wired.

Every solve here is deterministic (``deterministic=True``, one worker, seed 42)
per the hard rule; the wall ceiling is generous so the deterministic budget is
what binds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from generate_erp_dataset import generate

from mre.api.app import create_app

# window 7 / frozen 2 on the 40-order pilot plant, rolled one window: measured to
# admit 2 demands at roll 0 (so the coarse zone has 38 orders of tray to predict
# over) and 25 at roll 1, of which TEN arrive by GRAVITY rather than by the time
# window — which is what makes constraint (c) testable end to end rather than
# stubbed.
ROLL_0 = "2026-01-05"
ROLL_1 = "2026-01-12"
WINDOW_DAYS, FROZEN_DAYS = 7, 2
TIME_LIMIT = 120.0


def _data(resp, status=200):
    assert resp.status_code == status, resp.text
    return resp.json()["data"]


def _solve(client, sub_id, ref, *, coarse=True):
    solve = _data(client.post(f"/submissions/{sub_id}/solve", json={
        "time_limit": TIME_LIMIT, "deterministic": True, "sliced": True,
        "window_days": WINDOW_DAYS, "frozen_days": FROZEN_DAYS,
        "coarse": coarse, "reference_date": ref}), status=202)
    run = _data(client.get(f"/runs/{solve['run_id']}"))
    assert run["status"] == "succeeded", run.get("error")
    return run


@pytest.fixture(scope="module")
def submission_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("coarse_hist_sub") / "pilot"
    generate(d, scenario="pilot_scale", orders=40, seed=1)
    return d


@pytest.fixture(scope="module")
def two_rolls(tmp_path_factory, submission_dir):
    """TWO CONSECUTIVE ROLLS through the real worker, sharing one data root —
    which is what makes the store cross-roll rather than per-run."""
    root = tmp_path_factory.mktemp("coarse_hist_data")
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(submission_dir)}))
    assert sub["grade"] == "ACCEPTED"
    r0 = _solve(client, sub["submission_id"], ROLL_0)
    r1 = _solve(client, sub["submission_id"], ROLL_1)
    return {"root": root, "client": client, "submission_id": sub["submission_id"],
            "roll0": r0, "roll1": r1}


# ---------------------------------------------------------------------------
# (d) IT ACCRUES
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_two_consecutive_rolls_accrue_history(two_rolls):
    """The proof the whole CU exists for: predictions made at roll 0 are held by
    the store and JUDGED against roll 1's fine placements. The record counts are
    printed and stated in the close-out — a wired-but-empty store is not wired."""
    from mre.modules.coarse_predictions import sweep_data_root

    h0 = two_rolls["roll0"]["result"]["coarse_history"]
    h1 = two_rolls["roll1"]["result"]["coarse_history"]
    assert h0["error"] is None and h1["error"] is None

    assert h0["predictions_written"] > 0, (
        "roll 0 ran a coarse zone and wrote no predictions — the store is wired "
        "to nothing")
    assert h0["realizations_written"] == 0, "roll 0 had no prior roll to judge"
    assert h1["prior_runs_seen"] == 1
    assert h1["realizations_written"] > 0, (
        "roll 1 judged nothing: the cross-roll sweep found no prior predictions, "
        "so history is not accruing")

    preds, reals = sweep_data_root(two_rolls["root"])
    assert len(preds) == h0["predictions_written"] + h1["predictions_written"]
    assert len(reals) == h1["realizations_written"]
    print(f"\n[4B.6a CU1] accrual over two rolls: predictions={len(preds)} "
          f"realizations={len(reals)} "
          f"(roll0 wrote {h0['predictions_written']}, roll1 wrote "
          f"{h1['predictions_written']} and judged {h1['realizations_written']})")


@pytest.mark.slow
def test_a_prediction_is_judged_exactly_once(two_rolls, submission_dir,
                                              tmp_path_factory):
    """A THIRD roll over the same data root must not re-judge what roll 1
    already judged. The store is append-only, so without the dedup on
    ``CoarseRealization.key()`` every later roll would re-realize the same
    prediction and every error bar would drift."""
    from mre.modules.coarse_predictions import sweep_data_root

    before = len(sweep_data_root(two_rolls["root"])[1])
    r2 = _solve(two_rolls["client"], two_rolls["submission_id"], "2026-01-19")
    h2 = r2["result"]["coarse_history"]
    after_preds, after_reals = sweep_data_root(two_rolls["root"])
    already = {r.key() for r in after_reals}
    assert len(already) == len(after_reals), (
        "duplicate realization keys in the store — a prediction was judged twice")
    print(f"\n[4B.6a CU1] roll 2: pending={h2['prior_predictions_pending']} "
          f"judged={h2['realizations_written']} (store held {before} before)")


# ---------------------------------------------------------------------------
# (c) BOTH INTAKE PATHS, END TO END
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_both_intake_paths_are_captured_through_the_worker(two_rolls):
    """Path (b) — GRAVITY ADMISSION — is the interesting one: it is TWO
    MECHANISMS ON RECORD DISAGREEING about the same job (the coarse model said
    "week 3", gravity said "now"). The path is a FACT read from the admission
    mechanism, never inferred from the gap's sign, and it must survive the trip
    through the worker."""
    from mre.modules.coarse_predictions import (
        INTAKE_GRAVITY_ADMISSION, INTAKE_NATURAL_ROLL, sweep_data_root,
    )
    _preds, reals = sweep_data_root(two_rolls["root"])
    paths = {r.intake_path for r in reals}
    assert paths <= {INTAKE_NATURAL_ROLL, INTAKE_GRAVITY_ADMISSION}
    assert INTAKE_GRAVITY_ADMISSION in paths, (
        "no gravity-admitted realization was captured end to end — the intake "
        "label is either not wired or this roll pair no longer exercises "
        "gravity; the unit-level test cannot substitute for it")
    assert INTAKE_NATURAL_ROLL in paths, "no natural-roll realization captured"
    h1 = two_rolls["roll1"]["result"]["coarse_history"]
    assert h1["gravity_admission_realizations"] > 0
    assert h1["natural_roll_realizations"] > 0
    print(f"\n[4B.6a CU1] intake paths through the worker: "
          f"natural={h1['natural_roll_realizations']} "
          f"gravity={h1['gravity_admission_realizations']}")


# ---------------------------------------------------------------------------
# (a) THE DOCUMENT IS UNTOUCHED
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_document_is_byte_identical_with_the_store_on_and_off(
        tmp_path_factory, submission_dir, monkeypatch):
    """Persistence is a SIDE-CHANNEL. Two rolling solves of the same submission
    at the same reference origin — one with the store wired, one with the whole
    history call replaced by a no-op — must produce the SAME DOCUMENT BYTES.

    Exactly two fields are normalized before the comparison, and they are the
    two the registry mints per run and cannot repeat: ``run_id`` and
    ``schedule_id``. Nothing else is normalized, so any figure that moved would
    fail this."""
    import mre.modules.coarse_predictions as cp

    def _run(root_name, store_on):
        root = tmp_path_factory.mktemp(root_name)
        client = TestClient(create_app(data_root=root))
        sub = _data(client.post("/submissions", json={"path": str(submission_dir)}))
        with monkeypatch.context() as m:
            if not store_on:
                m.setattr(cp, "record_roll_history",
                          lambda **kw: cp.RollHistory())
            run = _solve(client, sub["submission_id"], ROLL_0)
        doc = _data(client.get(f"/schedules/{run['result']['schedule_id']}"))
        raw = json.dumps(doc, sort_keys=True)
        raw = raw.replace(run["id"], "<RUN>").replace(
            run["result"]["schedule_id"], "<SCHED>")
        return raw, root

    on, on_root = _run("store_on", True)
    off, off_root = _run("store_off", False)
    assert on == off, (
        "the schedule document MOVED when the prediction store was enabled — "
        "persistence is leaking into what the planner sees")
    # and the two roots really did differ in what was written
    assert list(on_root.rglob("coarse_predictions.jsonl")), "store wrote nothing"
    assert not list(off_root.rglob("coarse_predictions.jsonl")), (
        "the store was supposed to be disabled for the second run")


# ---------------------------------------------------------------------------
# (b) A WRITE FAILURE LOSES NO SCHEDULE AND IS NOT SWALLOWED
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_store_write_failure_keeps_the_schedule_and_is_surfaced(
        tmp_path_factory, submission_dir, monkeypatch):
    """A store fault must cost the history, never the schedule — and it must
    never pass unnoticed. The run stays SUCCEEDED, the schedule is registered
    and readable, and the failure is on the run record where an operator sees
    it."""
    from mre.modules.coarse_predictions import CoarsePredictionStore

    def boom(self, preds):
        raise OSError("disk full (simulated)")

    root = tmp_path_factory.mktemp("store_fail")
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(submission_dir)}))
    monkeypatch.setattr(CoarsePredictionStore, "record_predictions", boom)
    run = _solve(client, sub["submission_id"], ROLL_0)

    assert run["status"] == "succeeded"
    hist = run["result"]["coarse_history"]
    assert hist["error"] and "disk full (simulated)" in hist["error"], (
        "the store failure was SWALLOWED — the run reports nothing wrong while "
        "no history accrued, which is worse than having no store at all")
    assert hist["predictions_written"] == 0
    # the schedule survived the fault, whole
    doc = _data(client.get(f"/schedules/{run['result']['schedule_id']}"))
    assert doc["rolling"]["coarse_zone"] is not None
    assert doc["assignments"], "the schedule lost its assignments to a store fault"


# ---------------------------------------------------------------------------
# clause (2), through the worker
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_a_mirrored_planning_run_mints_nothing(tmp_path_factory, submission_dir,
                                               monkeypatch):
    """With rho = 1.0 the planning model is byte-identical to the proof model
    and is COPIED, not re-solved. Recording it as an independent prediction
    would double-count the proof run in every error bar — so an UNDECLARED plant
    (defaulted rho = 1.0) writes proof rows and nothing else."""
    import mre.modules.coarse_horizon as ch
    from mre.modules.coarse_predictions import sweep_data_root

    real = ch.CoarseCoefficients.from_cost_model

    def undeclared(cost_model):
        c = real(cost_model)
        return ch.CoarseCoefficients(bucket_days=c.bucket_days,
                                     capacity_derate=1.0,
                                     bucket_days_declared=c.bucket_days_declared,
                                     capacity_derate_declared=False)

    monkeypatch.setattr(ch.CoarseCoefficients, "from_cost_model",
                        staticmethod(undeclared))
    root = tmp_path_factory.mktemp("mirror")
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(submission_dir)}))
    run = _solve(client, sub["submission_id"], ROLL_0)
    preds, _reals = sweep_data_root(root)
    assert preds, "no predictions at all"
    assert {p.run_label for p in preds} == {"proof"}, (
        "a mirrored planning run minted predictions — the proof run is being "
        "double-counted")


# ---------------------------------------------------------------------------
# the opt-in is real
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_a_rolling_solve_without_the_coarse_flag_writes_no_predictions(
        tmp_path_factory, submission_dir):
    """The coarse zone is OPT-IN per solve. Without it the document carries no
    coarse block and the store stays untouched — no history is invented for a
    run that never ran a look-ahead."""
    from mre.modules.coarse_predictions import sweep_data_root
    root = tmp_path_factory.mktemp("nocoarse")
    client = TestClient(create_app(data_root=root))
    sub = _data(client.post("/submissions", json={"path": str(submission_dir)}))
    run = _solve(client, sub["submission_id"], ROLL_0, coarse=False)
    assert run["result"]["coarse"] is False
    doc = _data(client.get(f"/schedules/{run['result']['schedule_id']}"))
    assert doc["rolling"]["coarse_zone"] is None
    assert sweep_data_root(root)[0] == []
