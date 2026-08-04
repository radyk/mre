"""Mint the fenced world's ACCEPTED CHILD, so PLANNER_DIRECTIVE has a specimen.

Session 4A teaching-graft (c), Item 1(c). 4B.33 ruled `DriverCode.PLANNER_DIRECTIVE`
and named its own limit (§5a.135): **no pinned world holds a single `planner_edit`
Decision** — 0 of 32 and 0 of 96, measured — because an accept mints a CHILD at
runtime, so the ruling's only live surface was a drill-down on a board a session
had just built by hand. No exam question could reach it.

This mints one, ONCE, as a committed builder over the committed fenced dataset.

WHAT IT IS NOT. It does not write a Decision record. It runs the REAL accept —
`planner_edit.apply_planner_edit`, the same function `POST /schedules/{id}/accept`
calls — against a child run directory, and the Decision is whatever that path
produces. Fabricating the record would give the exam a specimen of our own
authorship, which is the opposite of what an exam is for.

WHAT IT SKIPS, AND WHY THAT IS NAMED RATHER THAN HIDDEN. The API's accept also
mints a Registry run, registers a proposed schedule, composes lineage pins and
assembles a contract document. None of that is here: the fenced world is a
MONOLITHIC run in `_ai_exam_scratch`, outside the registry, exactly like the
`gb_pinned` exam world. So this reproduces the accept's EVIDENCE — which is what
the ask path testifies from and therefore all an exam can grade — and not its
REGISTRY BOOKKEEPING. A session that wants the lineage, the banner and the
schedule picker needs the dev API and a registered board; that is a different
piece of work and it is named in the close-out.

THE GESTURE IS A ZERO-MOVE ACCEPT — pinning a bar at its own placement. R-DP11
made that the sharpest available probe (it is the gesture that was refused on
every rolling board for six sessions), and R-DP12 made it the one where the
driver's honesty is most exposed: nothing moved, the ledger is unchanged, and
the only true thing to say about why the bar is where it is, is that a human
directed it.

    python tools/spikes/teaching_graft_c/mint_edited_world.py
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

BASE = REPO / "_ai_exam_scratch" / "mobility_pinned"
CHILD = REPO / "_ai_exam_scratch" / "mobility_edited"
BASE_SNAP = "snap-mobility"
#: The bar the planner "drops" where it already is. ORD-PACK is the world's
#: `later-open` control: it has room to move, so pinning it is a real decision
#: rather than a restatement of a constraint.
PIN_ORDER = "ORD-PACK"
AUTHORITY = "daryn@mre.local"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--out", default=str(CHILD))
    ap.add_argument("--order", default=PIN_ORDER)
    ap.add_argument("--authority", default=AUTHORITY)
    args = ap.parse_args(argv)

    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.planner_edit import apply_planner_edit
    from mre.modules.sandbox import SANDBOX_DET_TIME_S, SANDBOX_SEED
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore

    base, out = Path(args.base), Path(args.out)
    if not (base / "snapshots" / BASE_SNAP).exists():
        print(f"no base world at {base}. Build it first:\n"
              f"  python -m mre --submission datasets/mobility_box --out {base} "
              f"--snapshot-id {BASE_SNAP} --solver-workers 1 --solver-seed 0 "
              f"--time-limit 600", file=sys.stderr)
        return 2

    index = EvidenceIndex.load(base / "evidence_index.json")
    ex = Explainer(SnapshotStore(base / "snapshots"), index,
                   snapshot_id=BASE_SNAP)
    row = next((r for r in ex._load_enriched_assignments()
                if args.order in (r.get("work_orders") or [])), None)
    if row is None:
        print(f"{args.order} is not placed in {base}", file=sys.stderr)
        return 2

    if out.exists():
        shutil.rmtree(out)
    (out / "snapshots").mkdir(parents=True)
    shutil.copytree(base / "snapshots" / BASE_SNAP, out / "snapshots" / BASE_SNAP)

    ctx = derive_base_context(base / "runs")
    ctx["base_runs_dir"] = str(base / "runs")

    print(f"accepting a ZERO-MOVE pin: {args.order} op{row['op_seq']} on "
          f"{row['machine']} at {row['start']}")
    result = apply_planner_edit(
        out_dir=out, base_snapshot_id=BASE_SNAP,
        pin_op_id=row["operation_ref"], pin_resource_id=row["resource_id"],
        pin_start_iso=str(row["start"]), authority=args.authority,
        base_context=ctx, budget_s=60.0,
        hold_all_placements=True,
        det_time_s=SANDBOX_DET_TIME_S, seed=SANDBOX_SEED,
    )
    print(f"child snapshot : {result.child_snapshot_id}")
    print(f"moved          : {result.moved_count}")
    print(f"cost delta     : {(result.cost_delta or {}).get('total_delta')}")
    print(f"delta_abs      : {result.delta_abs}   (None under a full hold — R-DP12)")

    idx = EvidenceIndex().build(out / "runs")
    idx.save(out / "evidence_index.json")
    decisions = [r for r in idx._all_evidence
                 if getattr(r, "record_type", "") == "decision"
                 or (isinstance(r, dict) and r.get("record_type") == "decision")]
    print(f"evidence index : {len(idx._all_evidence)} record(s), "
          f"{len(decisions)} decision(s)")
    print(f"\nask it with:\n  python tools/spikes/teaching_graft_c/ask_probe.py "
          f"--out-dir {out} --snapshot-id {result.child_snapshot_id} "
          f"\"why is {args.order} where it is\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
