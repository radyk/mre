"""THE MOBILITY VERDICT CENSUS — every bar of a world, every verdict.

Session 4A teaching-graft (c), Item 1. The listening docket (4A.x) censused both
pinned worlds and found `boxed-in` and `earlier-open` at ZERO on each: the two
verdicts `mobility_premise.assess` can return were asserted by unit test and had
never been observed against a solved board. This is the measuring instrument for
the world built to hold them.

    python tools/spikes/teaching_graft_c/census_mobility.py \
        _ai_exam_scratch/mobility_pinned snap-mobility

Prints one line per placed operation and a verdict tally. Reads only; mints
nothing; no model, no solver.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))


def census(out_dir: Path, snapshot_id: str) -> list[dict]:
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore

    ip = out_dir / "evidence_index.json"
    index = (EvidenceIndex.load(ip) if ip.exists()
             else EvidenceIndex().build(out_dir / "runs"))
    ex = Explainer(SnapshotStore(out_dir / "snapshots"), index,
                   snapshot_id=snapshot_id)
    seen: list[dict] = []
    for row in ex._load_enriched_assignments():
        orders = row.get("work_orders") or []
        order = orders[0] if orders else None
        if not order:
            continue
        v = ex.mobility_verdict(order, row.get("machine"), row.get("op_seq"))
        seen.append({
            "order": order, "op_seq": row.get("op_seq"),
            "machine": row.get("machine"),
            "start": row.get("start"), "end": row.get("end"),
            "verdict": (v or {}).get("verdict"),
            "later_at": (v or {}).get("later_at"),
            "earlier_verdict": (v or {}).get("earlier_verdict"),
            "chunk_count": (v or {}).get("chunk_count"),
        })
    return seen


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = Path(argv[0]) if argv else REPO / "_ai_exam_scratch" / "mobility_pinned"
    snapshot = argv[1] if len(argv) > 1 else "snap-mobility"
    rows = census(Path(out_dir), snapshot)
    rows.sort(key=lambda r: (r["machine"] or "", str(r["start"])))
    for r in rows:
        print(f'{r["order"]:12} op{r["op_seq"]:<4} {r["machine"]:8} '
              f'{str(r["start"])[:16]} -> {str(r["end"])[:16]}  '
              f'{str(r["verdict"]):14} earlier={r["earlier_verdict"]} '
              f'later_at={r["later_at"]}')
    tally = Counter(r["verdict"] for r in rows)
    print("\nTALLY", json.dumps(dict(tally), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
