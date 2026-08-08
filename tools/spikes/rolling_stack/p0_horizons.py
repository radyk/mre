"""R4.0 recon P0 — what horizon does the alternatives builder rebuild against?

READ-ONLY. Reads the gen-3 demo board's committed run dir and reports:
  * every M5 run_context_open horizon recorded by the base rolling run
  * which one ``solution_pool._m5_horizon`` (the alternatives builder's own
    seam) selects
  * the span of the incumbent assignments actually persisted in the snapshot

Usage:  python tools/spikes/rolling_stack/p0_horizons.py [--run <run_dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

DEFAULT_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    args = ap.parse_args()
    run_dir = Path(args.run)

    from mre.modules.solution_pool import _m5_horizon, _placements, _read_evidence
    from mre.modules.snapshot_store import SnapshotStore

    evidence = _read_evidence(run_dir / "runs")
    print(f"run dir      : {run_dir}")
    print(f"evidence recs: {len(evidence)}")

    opens = [r for r in evidence if r.get("record_type") == "run_context_open"]
    print(f"\nrun_context_open records: {len(opens)}")
    for r in sorted(opens, key=lambda x: x.get("started_at", "")):
        cfg = r.get("config_snapshot") or {}
        hs, he = cfg.get("horizon_start"), cfg.get("horizon_end")
        print(f"  {r.get('started_at','')[:19]}  {r.get('module'):3}  "
              f"{(r.get('purpose') or '')[:44]:44}  "
              f"horizon={hs} -> {he}")

    print("\n--- what _m5_horizon() SELECTS (last M5 open, by started_at) ---")
    try:
        hs, he = _m5_horizon(evidence)
        print(f"  horizon_start = {hs}")
        print(f"  horizon_end   = {he}")
        print(f"  span          = {(he - hs).days} days")
    except Exception as exc:  # noqa: BLE001
        print(f"  RAISED: {exc}")
        return 1

    print("\n--- the incumbent assignments actually in the snapshot ---")
    snap_root = run_dir / "snapshots"
    snap_id = next(p.name for p in snap_root.iterdir() if p.is_dir())
    reader = SnapshotStore(snap_root).load_snapshot(snap_id)
    assigns = list(reader.iter_entities("assignment"))
    ops = list(reader.iter_entities("operation"))
    pl = _placements(assigns)
    starts = sorted(p[1] for p in pl.values())
    print(f"  snapshot        : {snap_id}")
    print(f"  operations      : {len(ops)}")
    print(f"  assignments     : {len(assigns)}  (placed ops: {len(pl)})")
    if starts:
        print(f"  earliest start  : {starts[0]}")
        print(f"  latest start    : {starts[-1]}")
        print(f"  placement span  : {(starts[-1] - starts[0]).days} days")

    print("\n--- VERDICT ---")
    if starts:
        outside = [s for s in starts if not (hs <= s <= he)]
        print(f"  placed ops whose incumbent start lies OUTSIDE the rebuilt "
              f"horizon: {len(outside)} / {len(starts)}")
        if outside:
            print(f"    earliest outside: {min(outside)}")
            print(f"    latest outside  : {max(outside)}")
    print(f"  operations in the model the rebuild will build: {len(ops)}")
    print(f"  of which placed by the incumbent               : {len(pl)}")
    print(f"  of which UNPLACED (no assignment)              : {len(ops) - len(pl)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
