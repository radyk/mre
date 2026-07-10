#!/usr/bin/env python3
"""Deploy smoke test - the docs/07 Phase 2 exit demo, over the API (CU3).

Drives a generated ~3,000-order IDS submission through ANY deployed instance
by base URL: gate -> solve -> retrieve schedule -> one what-if, with wall-clock
timings recorded as scale-ladder regression baselines. Provider-agnostic: it
speaks only the HTTP contract, so the SAME script validates the local compose
stack and a cloud deployment.

    python deploy/smoke.py --base-url https://mre.example.com
    python deploy/smoke.py --base-url http://localhost:8000          # local compose
    python deploy/smoke.py --base-url https://localhost --insecure   # local TLS stack

Deterministic solve by default (the baseline-claim rule): the server must also
run PYTHONHASHSEED=0 for a byte-identical schedule (2026-07-09 amendment); the
timings here are the durable regression signal regardless.

Requires the repo (to generate the submission) and httpx.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# Repo import for the generator (client-side submission synthesis).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.generate_erp_dataset import generate  # noqa: E402


def _envelope(resp: httpx.Response) -> dict:
    resp.raise_for_status()
    body = resp.json()
    assert body.get("api_version") == "1", f"unexpected envelope: {body}"
    if "error" in body:
        raise RuntimeError(f"API error: {body['error']}")
    return body["data"]


def _poll_run(client: httpx.Client, run_id: str, *, timeout_s: float) -> dict:
    """Poll GET /runs/{id} until it leaves 'running' (background task done)."""
    deadline = time.monotonic() + timeout_s
    while True:
        run = _envelope(client.get(f"/runs/{run_id}"))
        if run["status"] != "running":
            return run
        if time.monotonic() > deadline:
            raise TimeoutError(f"run {run_id} still running after {timeout_s}s")
        time.sleep(1.0)


def _phase(label: str, timings: dict, fn):
    t0 = time.monotonic()
    result = fn()
    dt = round(time.monotonic() - t0, 2)
    timings[label] = dt
    print(f"  [{dt:7.2f}s] {label}")
    return result


def run_smoke(base_url: str, *, scenario: str, seed: int, time_limit: float,
              poll_timeout: float, insecure: bool, keep: bool) -> dict:
    print(f"MRE deploy smoke -> {base_url}  (scenario={scenario}, seed={seed})")
    timings: dict[str, float] = {}
    counts: dict[str, object] = {"scenario": scenario, "seed": seed}

    # --- generate the submission client-side -------------------------------
    sub_dir = Path(__file__).resolve().parent / f".smoke_{scenario}_{seed}"
    if not sub_dir.exists():
        _phase("generate submission", timings,
               lambda: generate(sub_dir, scenario=scenario, seed=seed))
    files = [p for p in sorted(sub_dir.iterdir()) if p.is_file()]
    counts["submission_files"] = len(files)

    verify = not insecure
    with httpx.Client(base_url=base_url, timeout=300.0, verify=verify) as client:
        # health first - fail fast with a clear message if the instance is down
        health = _envelope(client.get("/health"))
        assert health["status"] == "ok", health

        # --- gate ----------------------------------------------------------
        def _submit():
            uploads = [("files", (p.name, p.read_bytes(), "text/csv")) for p in files]
            return _envelope(client.post("/submissions", files=uploads))
        sub = _phase("submit + gate (M0 certificate)", timings, _submit)
        counts["grade"] = sub["grade"]
        counts["costing_grade"] = sub.get("costing_grade")
        print(f"      grade={sub['grade']} costing={sub.get('costing_grade')} "
              f"deficiencies={len(sub.get('deficiencies', []))}")
        if sub["grade"] == "REJECTED":
            raise SystemExit("smoke FAILED: submission REJECTED by the gate "
                             f"({sub.get('deficiencies')})")

        # --- solve (async -> poll) -----------------------------------------
        def _solve():
            acc = _envelope(client.post(
                f"/submissions/{sub['submission_id']}/solve",
                json={"time_limit": time_limit, "deterministic": True}))
            return _poll_run(client, acc["run_id"], timeout_s=poll_timeout)
        run = _phase("solve (poll to done)", timings, _solve)
        if run["status"] != "succeeded":
            raise SystemExit(f"smoke FAILED: solve run {run['status']}: "
                             f"{run.get('error')}")
        schedule_id = run["result"]["schedule_id"]

        # --- retrieve schedule --------------------------------------------
        doc = _phase("retrieve schedule document", timings,
                     lambda: _envelope(client.get(f"/schedules/{schedule_id}")))
        summ = doc.get("summary", {}) or doc.get("annotations", {})
        counts["schedule_id"] = schedule_id
        counts["assignments"] = len(doc.get("assignments", []))

        # --- one what-if (always-valid, dataset-independent modification) --
        def _whatif():
            acc = _envelope(client.post(
                f"/schedules/{schedule_id}/whatif",
                json={"modifications": [
                    {"type": "set_cost_weight",
                     "path": "tardiness_weights.base_weight", "value": 2.0}],
                      "time_limit": time_limit}))
            return _poll_run(client, acc["run_id"], timeout_s=poll_timeout)
        wrun = _phase("what-if (poll to done)", timings, _whatif)
        if wrun["status"] != "succeeded":
            raise SystemExit(f"smoke FAILED: what-if run {wrun['status']}: "
                             f"{wrun.get('error')}")
        counts["whatif_cost_delta"] = (
            wrun["result"].get("diff", {}).get("cost_delta", {}).get("total_delta"))

    if not keep:
        import shutil
        shutil.rmtree(sub_dir, ignore_errors=True)

    timings["total"] = round(sum(v for k, v in timings.items()), 2)
    return {"base_url": base_url, "timings_seconds": timings, "counts": counts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:8000",
                    help="deployed instance base URL (local compose default)")
    ap.add_argument("--scenario", default="clean_large",
                    help="generator scenario (clean_large ~= 3,000 orders)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--time-limit", type=float, default=60.0,
                    help="solver time limit per solve/what-if (seconds)")
    ap.add_argument("--poll-timeout", type=float, default=1800.0,
                    help="max seconds to wait for a background run")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (local self-signed CA)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the generated submission dir")
    ap.add_argument("--out", type=Path, default=None,
                    help="write the baseline JSON here (append to the ladder)")
    args = ap.parse_args(argv)

    result = run_smoke(
        args.base_url, scenario=args.scenario, seed=args.seed,
        time_limit=args.time_limit, poll_timeout=args.poll_timeout,
        insecure=args.insecure, keep=args.keep,
    )

    print("\n=== smoke PASSED ===")
    print(json.dumps(result, indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nbaseline written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
