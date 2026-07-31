"""Errand 4B.22a -- run the OPENER against a candidate's persisted run, offline.

The candidate table's utilisation column uses its own denominator (the board
extent -- see `measure_candidates.py`), and the OPENER uses a different one:
`Explainer._opener_load` divides run minutes by the machine's OWN open windows
over the whole resolved calendar. Two figures, two denominators, and neither may
be used to predict the other -- which matters here because the errand's Item 5
expects the concentration band to fire for the first time, and whether it does is
a fact about the opener's number, not about the table's.

Concentration ALSO requires an eligible IDLE alternative (`board_opener.py`:
`utilization >= SATURATED` AND some alternative `<= IDLE`). On the pilot family
only CUT and PRESS steps carry alternates, so a saturated PAINT or MILL lane can
never produce the finding however hot it runs. This probe reports both halves so
a "did not fire" is attributable.

    python tools/spikes/demo_board_4b22a/opener_probe.py \
        --run _4b22a_scratch/candidates/c7-w7-280/run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True,
                    help="a candidate's out_dir (contains runs/ and snapshots/)")
    ap.add_argument("--snapshot", default="snap-rolling")
    ap.add_argument("--document", default=None,
                    help="optional schedule document json; without it the "
                         "opener sees no rolling regions")
    args = ap.parse_args(argv)

    from mre.modules.board_opener import IDLE, SATURATED
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore

    out = Path(args.run)
    index = EvidenceIndex().build(out / "runs")
    store = SnapshotStore(out / "snapshots")
    ex = Explainer(store, index, snapshot_id=args.snapshot)
    doc = json.loads(Path(args.document).read_text(encoding="utf-8")) \
        if args.document else None

    print(f"thresholds: SATURATED={SATURATED}  IDLE={IDLE}")

    # THE RAW NUMBERS `_opener_load` FILTERS AT 50%. Recomputed here from the
    # SAME two calls the method uses (`_load_enriched_assignments` for run
    # minutes, `_open_windows` for the denominator), so a machine that never
    # reaches the filter is still visible and its denominator is checkable.
    rows = [r for r in ex._load_enriched_assignments() if r.get("start")]
    busy: dict[str, float] = {}
    for r in rows:
        m = r.get("machine")
        if m:
            busy[m] = busy.get(m, 0.0) + float(r.get("run_min") or 0.0)
    print("\n--- every machine, at the OPENER's denominator ---")
    print(f"{'machine':14s}{'run_min':>10s}{'open_min':>12s}{'util%':>9s}")
    for m in sorted(set(ex._machine_refs.values()) | set(busy)):
        open_min = sum((e - s).total_seconds() / 60.0
                       for s, e in ex._open_windows(m))
        u = (busy.get(m, 0.0) / open_min * 100.0) if open_min else 0.0
        print(f"{m:14s}{busy.get(m, 0.0):10.0f}{open_min:12.0f}{u:9.1f}")

    load, notes = ex._opener_load()
    print(f"\n--- _opener_load (utilisation over the machine's OWN open "
          f"windows) ---")
    if not load:
        print("  (none: no busy lane at or above 50%, or no placements)")
    for c in sorted(load or [], key=lambda c: -(c["utilization"] or 0)):
        alts = ", ".join(f"{a['machine']} {a['utilization']*100:.1f}%"
                         for a in c["alternatives"]) or "(no eligible alternative)"
        fires = ((c["utilization"] or 0) >= SATURATED
                 and any((a["utilization"] or 0) <= IDLE
                         for a in c["alternatives"]))
        print(f"  {c['machine']:12s} {c['utilization']*100:6.1f}%   "
              f"alternatives: {alts}   -> concentration fires: {fires}")
    for n in notes:
        print(f"  note: {n}")

    # The FULL opener is assembled by the live route on the ask path; the load
    # table above is the whole of what decides the concentration band, so this
    # probe stops here rather than half-reconstructing the route.
    return 0


if __name__ == "__main__":
    sys.exit(main())
