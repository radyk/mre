"""Session 4B.30 — find real board specimens for each refusal branch.

Item 4's branches are only worth authoring if they are REACHABLE on a real
board, so this reads the demo board and reports, from its own data:

  * chunked operations (branch c)
  * an order whose machine has a DECLARED closure inside the window (branch b)
  * an order with a tight later neighbour on its machine (branch a)
  * the window's own end, so a target that would leave it can be told apart
    from one that stays

No pricing here — it enumerates candidates; the probe measures them live.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

SCHEDULE = sys.argv[1] if len(sys.argv) > 1 else "rolling-c9973708-865"


def main() -> int:
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore

    con = sqlite3.connect(str(ROOT / "_data" / "registry.sqlite"))
    con.row_factory = sqlite3.Row
    row = dict(con.execute("select * from schedules where id=?",
                           (SCHEDULE,)).fetchone())
    run = dict(con.execute("select * from runs where id=?",
                           (row["run_id"],)).fetchone())
    doc = json.loads(Path(row["document_path"]).read_text(encoding="utf-8"))
    out_dir = Path(run["out_dir"])

    index_path = out_dir / "evidence_index.json"
    index = (EvidenceIndex.load(index_path) if index_path.exists()
             else EvidenceIndex().build(out_dir / "runs"))
    ex = Explainer(SnapshotStore(out_dir / "snapshots"), index,
                   snapshot_id=row["snapshot_id"], out_dir=out_dir)

    rb = doc.get("rolling") or {}
    print(f"window {rb.get('window_start')} -> {rb.get('window_end')}  "
          f"frozen_until {rb.get('frozen_until')}")

    rows = [r for r in ex._load_enriched_assignments() if r.get("start")]
    print(f"{len(rows)} placed rows")

    print("\n== CHUNKED OPERATIONS (branch c) ==")
    chunked = [r for r in rows if len(r.get("chunks") or []) > 1]
    for r in chunked[:10]:
        print(f"  {'+'.join(r['work_orders'])} op{r['op_seq']} on {r['machine']} "
              f"{len(r['chunks'])} pieces  {r['start']} -> {r['end']}")
    print(f"  ({len(chunked)} total)")

    print("\n== MACHINES WITH DECLARED CLOSURES (branch b) ==")
    machines = sorted({r["machine"] for r in rows})
    for m in machines:
        cl = ex._closures(m)
        if cl:
            print(f"  {m}: " + "; ".join(
                f"{c['reason']} {c['start']}..{c['end']}" for c in cl[:3]))

    print("\n== TIGHT LATER NEIGHBOURS (branch a) ==")
    # An op whose machine's very next placement starts close behind it: a small
    # push lands inside the neighbour, which is the collision specimen.
    from mre.modules.explainer import _to_dt
    by_m: dict = {}
    for r in rows:
        by_m.setdefault(r["machine"], []).append(r)
    hits = []
    for m, rs in by_m.items():
        rs.sort(key=lambda r: r["start"])
        for a, b in zip(rs, rs[1:]):
            if len(a.get("chunks") or []) > 1:
                continue
            gap = (_to_dt(b["start"]) - _to_dt(a["end"])).total_seconds() / 60.0
            if 0 <= gap <= 600:
                hits.append((gap, m, a, b))
    hits.sort(key=lambda h: h[0])
    for gap, m, a, b in hits[:12]:
        print(f"  {'+'.join(a['work_orders'])} op{a['op_seq']} on {m} ends "
              f"{a['end']}, then {'+'.join(b['work_orders'])} op{b['op_seq']} "
              f"starts {b['start']} (gap {gap:.0f} min)")
    print(f"  ({len(hits)} total)")

    print("\n== EARLY, SHORT, UNCHUNKED ROWS (room to push inside the window) ==")
    cands = [r for r in rows
             if len(r.get("chunks") or []) == 1
             and r["start"] < "2026-01-09"]
    cands.sort(key=lambda r: r["start"])
    for r in cands[:12]:
        print(f"  {'+'.join(r['work_orders'])} op{r['op_seq']} on {r['machine']} "
              f"{r['start']} -> {r['end']}  run {r['run_min']}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
