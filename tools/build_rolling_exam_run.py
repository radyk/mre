"""Build the pinned rolling run, and with --register put it in the cockpit.

The world the ai_exam rolling bank asks against -- and, with ``--register``, the
same world in front of the founder, selectable, in one command.

Session 4A.5c CU4/CU5. The exam's monolithic world (``_ai_exam_scratch/gb_pinned``)
has no sliced state, so every rolling question there is answered "this isn't a
rolling schedule" — honest, and useless as a test of the sliced world. This builds
its rolling sibling: a pilot_scale plant, window 0 solved deterministically and
PERSISTED as a first-class run (the 4B.3c capability), plus the assembled
contract-1.7 document that carries the committed front, the active window and the
beyond-horizon tray.

    python tools/build_rolling_exam_run.py                 # harness fixture only
    python tools/build_rolling_exam_run.py --register      # ... and into the cockpit

Deterministic settings are fixed here rather than passed: seed 42 for rolling /
pilot_scale work (the standing convention), ``deterministic=True`` so the window-0
solve is reproducible, and a reference date pinned to the same 2026-01-05 the
cockpit fixture uses (which is also the generator's default, so the API — reading
the manifest — lands on the same origin). A rolling run whose window moved between
two sweeps would make every comparison meaningless.

PYTHONHASHSEED no longer matters (Errand session, CU2b): the two hash-order leaks
that made the committed/active split move between processes were fixed at the
source (``ids_adapter`` entity write order, ``rolling_horizon`` admitted-set
iteration), and the wall-clock ceiling was raised so the DETERMINISTIC budget is
what stops the solve. §DETERMINISM below re-proves this on every build.

Output (gitignored scratch, exactly like ``gb_pinned`` — the BUILDER is the
committed artifact, not its output):

    _ai_exam_scratch/rolling_pinned/
        submission/                            the generated IDS submission (reused)
        runs/ snapshots/ evidence_index.json   the persisted window-0 run
        document.json                          the contract-1.7 rolling document
        TARGET.json                            out-dir + snapshot id + doc path

This is a NEW fixture, not a change to an existing golden. Nothing here touches
``tests/cockpit/fixtures/rolling/``.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
OUT = REPO / "_ai_exam_scratch" / "rolling_pinned"
SUBMISSION = OUT / "submission"
SEED = 42                 # the standing seed for rolling / pilot_scale work
ORDERS = 40
WINDOW_DAYS = 14
FROZEN_DAYS = 3
DET_TIME = 2.0            # the window-0 solve's DETERMINISTIC budget (what binds)

# The wall-clock limit is a SAFETY CEILING, never the budget (Errand session,
# CU2b). CP-SAT always gets a max_time_in_seconds as well as a
# max_deterministic_time; at the old 10.0s the WALL clock stopped the solve every
# time (measured: wall=10.01s against a deterministic budget of 2.0 that was
# never reached), so "deterministic mode" returned whatever the machine happened
# to reach in ten seconds. The deterministic budget costs ~11-12s of wall here;
# this ceiling is far above it, and _verify_determinism fails the build if the
# wall clock ever binds again.
WALL_CEILING_S = 900.0

DEFAULT_API = "http://localhost:8000"
DEV_API_SCRIPT = r".\src\cockpit\dev_api.ps1"


# ---------------------------------------------------------------------------
# the world
# ---------------------------------------------------------------------------

def build_submission(fresh: bool = False) -> Path:
    """Generate the pinned world's IDS submission under OUT, or reuse the one
    already there. Reuse is the default and is the point: the generator stamps a
    fresh ``extract_timestamp`` into every manifest, so regenerating gives a
    byte-different submission for the same world — fine for the solve, noise for
    anything that fingerprints the submission."""
    from generate_erp_dataset import generate

    if SUBMISSION.exists() and not fresh:
        if (SUBMISSION / "manifest.json").exists():
            print(f"rolling-exam: reusing submission at {SUBMISSION}")
            return SUBMISSION
        shutil.rmtree(SUBMISSION)
    if SUBMISSION.exists():
        shutil.rmtree(SUBMISSION)
    print(f"rolling-exam: generating pilot_scale ({ORDERS} orders, seed 1)...")
    SUBMISSION.parent.mkdir(parents=True, exist_ok=True)
    generate(SUBMISSION, scenario="pilot_scale", orders=ORDERS, seed=1)
    return SUBMISSION


def solve_window0(submission: Path, out_dir: Path, persist: bool):
    """prepare_plant + build_rolling_view at the pinned settings. Returns
    (plant, view)."""
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant

    plant = prepare_plant(submission, out_dir, reference_date=REF)
    view = build_rolling_view(plant, window_days=WINDOW_DAYS,
                              frozen_days=FROZEN_DAYS, gravity=True,
                              deterministic=True, seed=SEED,
                              member_time_limit_s=WALL_CEILING_S,
                              det_time=DET_TIME, persist=persist)
    return plant, view


# ---------------------------------------------------------------------------
# §DETERMINISM — the assertion (Errand session, CU2b)
# ---------------------------------------------------------------------------

def _placement_fingerprint(view) -> dict:
    """Everything a second run must reproduce exactly: which ops are committed,
    which are active, which demands are in the tray, and every placement."""
    return {
        "committed": sorted(view.committed),
        "active": sorted(view.active),
        "beyond": sorted(view.beyond_demand_ids),
        "placements": {oid: (p["resource"], p["start"], p["end"])
                       for oid, p in sorted(view.placed.items())},
    }


def verify_determinism(submission: Path, first_view) -> list[str]:
    """Re-run the ENTIRE pinned path (spine + window-0 solve) from the same
    submission and require an identical result. Returns a list of failures
    (empty = the build is reproducible).

    A second pass through prepare_plant, not a second solve of the same plant:
    the leak this catches most recently lived in the M1 adapter's entity WRITE
    ORDER, which a plant-reusing check would have sailed straight past."""
    failures: list[str] = []
    if first_view.wall_truncated:
        failures.append(
            "the window-0 solve was stopped by the WALL CLOCK, not by its "
            f"deterministic budget of {DET_TIME}s - the result is not "
            f"reproducible. Raise WALL_CEILING_S (currently {WALL_CEILING_S}s).")

    tmp = Path(tempfile.mkdtemp(prefix="rollexam-verify"))
    _plant2, view2 = solve_window0(submission, tmp, persist=False)
    if view2.wall_truncated:
        failures.append("the verification solve was wall-clock truncated")

    a, b = _placement_fingerprint(first_view), _placement_fingerprint(view2)
    for key in ("committed", "active", "beyond"):
        if a[key] != b[key]:
            failures.append(
                f"{key}: run 1 has {len(a[key])}, run 2 has {len(b[key])} "
                f"({len(set(a[key]) ^ set(b[key]))} differ)")
    if a["placements"] != b["placements"]:
        moved = [oid for oid in a["placements"]
                 if b["placements"].get(oid) != a["placements"][oid]]
        failures.append(f"{len(moved)} operation(s) placed differently, "
                        f"e.g. {moved[:3]}")
    if not failures:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        failures.append(f"verification run left at {tmp}")
    return failures


# ---------------------------------------------------------------------------
# §REGISTER — the live dev API (CU1)
# ---------------------------------------------------------------------------

class ApiError(RuntimeError):
    pass


def _api(base: str, path: str, body: dict | None = None, timeout: float = 30.0):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:          # the API's own error envelope
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:                        # noqa: BLE001
            payload = {"error": {"message": str(e)}}
        raise ApiError(f"{path} -> HTTP {e.code}: "
                       f"{payload.get('error', {}).get('message', payload)}") from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ApiError(f"{path} -> unreachable: {e}") from e


def check_api(base: str) -> bool:
    """Probe /health BEFORE anything is built. 'Never half-register' means the
    unreachable case costs the founder nothing but the message."""
    try:
        health = _api(base, "/health", timeout=5.0)
    except ApiError:
        print(f"\nrolling-exam: no API at {base}.\n"
              f"  Start it in another terminal, from the repo root:\n"
              f"      {DEV_API_SCRIPT}\n"
              f"  (it serves on {DEFAULT_API} with MRE_DATA_ROOT=./_data; leave it\n"
              f"   running, then re-run this command). Nothing was built or "
              f"registered.", file=sys.stderr)
        return False
    print(f"rolling-exam: API at {base} is "
          f"{health.get('data', {}).get('status', '?')}")
    return True


def register(base: str, submission: Path, poll_timeout_s: float) -> int:
    """The two-step the API actually exposes: POST /submissions (M0 gate ->
    certificate), then POST /submissions/{id}/solve with the SLICED request.
    Prints the certificate grade, the schedule id, and how to select it."""
    print(f"rolling-exam: submitting {submission} ...")
    sub = _api(base, "/submissions", {"path": str(submission)}, timeout=120.0)["data"]
    sub_id, grade = sub["submission_id"], sub["grade"]
    print(f"rolling-exam: certificate grade {grade} "
          f"(costing {sub.get('costing_grade')}), submission {sub_id}")
    if grade == "REJECTED":
        for d in sub.get("deficiencies", []):
            print(f"  - {d}", file=sys.stderr)
        print("rolling-exam: REJECTED submissions never solve - nothing registered.",
              file=sys.stderr)
        return 1

    solve_req = {
        "policy": "identity_v1",
        "deterministic": True,
        "sliced": True,
        "window_days": WINDOW_DAYS,
        "frozen_days": FROZEN_DAYS,
        # SolveRequest.time_limit becomes build_rolling_view's member_time_limit_s
        # — the WALL ceiling, not the budget. The API's own det_time (4.0) is what
        # stops this solve, so it is the same world and window as the harness
        # fixture above but not a bit-identical solve (a larger budget, its own
        # run dir). That is deliberate: the cockpit run is the API's, end to end.
        "time_limit": WALL_CEILING_S,
    }
    print(f"rolling-exam: solving sliced (window={WINDOW_DAYS}d "
          f"frozen={FROZEN_DAYS}d, deterministic) ...")
    run = _api(base, f"/submissions/{sub_id}/solve", solve_req, timeout=60.0)["data"]
    run_id = run["run_id"]

    t0 = time.perf_counter()
    while True:
        row = _api(base, f"/runs/{run_id}")["data"]
        status = row["status"]
        if status in ("succeeded", "failed"):
            break
        if time.perf_counter() - t0 > poll_timeout_s:
            print(f"rolling-exam: run {run_id} still '{status}' after "
                  f"{poll_timeout_s:.0f}s - giving up on the wait. The solve may "
                  f"still finish; check GET {base}/runs/{run_id}.", file=sys.stderr)
            return 1
        time.sleep(2.0)

    elapsed = time.perf_counter() - t0
    if status == "failed":
        print(f"rolling-exam: run {run_id} FAILED after {elapsed:.0f}s: "
              f"{row.get('error')}", file=sys.stderr)
        return 1

    result = row.get("result") or {}
    schedule_id = result.get("schedule_id")
    if not schedule_id:
        print(f"rolling-exam: run {run_id} succeeded but registered no schedule "
              f"id: {result}", file=sys.stderr)
        return 1

    print(f"rolling-exam: run {run_id} succeeded in {elapsed:.0f}s "
          f"({result.get('committed')} committed, "
          f"{result.get('beyond_horizon')} in the tray)")
    print("")
    print(f"  certificate grade : {grade}")
    print(f"  schedule id       : {schedule_id}")
    print(f"  select {schedule_id} in the cockpit")
    print("")
    return 0


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--register", action="store_true",
                    help="also submit the world through the LIVE dev API and "
                         "print the schedule id to select in the cockpit")
    ap.add_argument("--api-base", default=DEFAULT_API,
                    help=f"dev API base URL (default {DEFAULT_API})")
    ap.add_argument("--fresh", action="store_true",
                    help="regenerate the submission instead of reusing it")
    ap.add_argument("--poll-timeout", type=float, default=600.0,
                    help="seconds to wait for the async solve (default 600)")
    args = ap.parse_args(argv)

    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.schedule_assembler import assemble_rolling_document

    # Reachability FIRST: an unreachable API must cost nothing but the message.
    if args.register and not check_api(args.api_base):
        return 2

    submission = build_submission(fresh=args.fresh)

    tmp = Path(tempfile.mkdtemp(prefix="rollexam"))
    print(f"rolling-exam: solving window 0 (window={WINDOW_DAYS}d "
          f"frozen={FROZEN_DAYS}d, deterministic, seed={SEED}, "
          f"det budget={DET_TIME}s) ...")
    plant, view = solve_window0(submission, tmp, persist=True)

    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-rolling-exam",
                                    run_id="run-rolling-exam",
                                    identity_map=idmap).model_dump(mode="json")

    OUT.mkdir(parents=True, exist_ok=True)
    # Copy the persisted run beside the document so the exam target is one
    # self-contained directory (the gb_pinned shape).
    for sub in ("runs", "snapshots"):
        src = Path(plant.out_dir) / sub
        if src.exists():
            dst = OUT / sub
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    index = EvidenceIndex().build(OUT / "runs")
    index.save(OUT / "evidence_index.json")

    (OUT / "document.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    target = {
        "out_dir": str(OUT),
        "snapshot_id": plant.snapshot_id,
        "document_path": str(OUT / "document.json"),
        "submission_path": str(submission),
        "seed": SEED, "window_days": WINDOW_DAYS, "frozen_days": FROZEN_DAYS,
        "reference_date": REF.isoformat(),
    }
    (OUT / "TARGET.json").write_text(json.dumps(target, indent=2), encoding="utf-8")

    r = doc["rolling"]
    print(f"rolling-exam: {len(doc['assignments'])} bars, "
          f"{r['committed_count']} committed, {r['active_count']} active, "
          f"{len(r['beyond_horizon'])} in the tray")
    print(f"rolling-exam: snapshot {plant.snapshot_id}")
    print(f"rolling-exam: -> {OUT}")
    if not r["beyond_horizon"]:
        print("rolling-exam: !! EMPTY TRAY - the rolling bank's tray questions "
              "would test nothing. Shorten the window and rebuild.",
              file=sys.stderr)
        return 1

    # §DETERMINISM — prove the fixture is reproducible, every build.
    print("rolling-exam: verifying determinism (a second spine + window-0 solve)...")
    failures = verify_determinism(submission, view)
    if failures:
        print("rolling-exam: !! NOT DETERMINISTIC - the pinned world moved "
              "between two identical runs:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("rolling-exam: determinism verified (identical split and placements)")

    if args.register:
        return register(args.api_base, submission, args.poll_timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
