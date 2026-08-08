"""R4.1 W5(b) — Q6: does C5's finding touch R-T2's hold-everything-else contract?

R4.0 §4.3 question 6, NAMED but NOT MEASURED. The maintenance errand's C5 item
measured that single-worker CP-SAT does not follow warm-start HINTS tightly (43
untouched operations moved at workers=1 vs 4 at workers=8). R-T2's local price
claims "nothing else moved". The inference from a code read was that the two
cannot collide, because a beat-two accept PINS every other placement
(``hold_all_placements``, 4B.24) rather than hinting it — a pin is a hard
constraint, a hint is a suggestion.

That is an inference, and R4.0 twice found inferences of exactly this kind
wrong. So it is measured here, in TWO cells on the same board and the same
gesture, both at workers=1:

  A. hold_all_placements=True  — what the product actually does after a
     beat-two card. R-T2's claim lives here. Expected 0 movers.
  B. hold_all_placements=False — only the lineage's standing pins are held and
     the rest of the window is free to re-optimize. This is where warm-start
     hints, and therefore C5's finding, actually live.

Cell B is the contrast that makes cell A mean something: a 0 in A is only
informative if the same board and gesture can produce a nonzero somewhere.

Always runs on a SCRATCH COPY; refuses to touch the live data root.

    python tools/spikes/rolling_stack/p8_q6_hold_contract.py --work <dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

GEN3_RUN = Path("_data/runs/9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc")


def placements_of(assignments):
    """op -> (resource, run start). Uses the SHARED reader, which handles both
    the persisted-entity shape (``resource_assignments[0].resource_ref``) and
    the extractor's flat ``resource_id``.

    A hand-rolled reader here returned 0 placements for all 386 bars on the
    first run of this probe — it only looked at ``resource_id`` — and the
    movers count it produced was therefore 0 out of an EMPTY SET. That is the
    (d.2) blind-instrument failure, on the probe written to avoid inferring.
    Hence: refuse an empty read rather than report a clean zero from it."""
    from mre.modules.solution_pool import _placements
    out = _placements(assignments)
    if not out:
        raise RuntimeError(
            "read 0 placements from a plan that has them — the reader is "
            "blind; a movers count from this set would be meaningless")
    return out


def run_cell(label, run_dir, work, hold_all, pin):
    from mre.modules import longpath
    from mre.modules.planner_edit import apply_planner_edit
    from mre.modules.sandbox import SANDBOX_DET_TIME_S, SANDBOX_SEED
    from mre.modules.scenario import derive_base_context
    from mre.modules.snapshot_store import SnapshotStore

    op, res, start = pin
    base_snap = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())
    child_out = work / f"q6_child_{label}"
    if child_out.exists():
        shutil.rmtree(child_out)
    child_out.mkdir(parents=True, exist_ok=True)
    longpath.copytree(run_dir / "snapshots" / base_snap,
                      child_out / "snapshots" / base_snap)

    base_ctx = derive_base_context(run_dir / "runs")
    base_ctx["base_runs_dir"] = str(run_dir / "runs")

    before = placements_of(
        list(SnapshotStore(run_dir / "snapshots").load_snapshot(base_snap)
             .iter_entities("assignment")))

    result = apply_planner_edit(
        out_dir=child_out, base_snapshot_id=base_snap,
        pin_op_id=op, pin_resource_id=res, pin_start_iso=start,
        authority="r4.1-q6", base_context=base_ctx, budget_s=180.0,
        standing_pins=[], hold_all_placements=hold_all,
        deterministic=True,                      # -> workers = 1
        det_time_s=SANDBOX_DET_TIME_S, seed=SANDBOX_SEED,
    )
    after = placements_of(
        list(SnapshotStore(child_out / "snapshots")
             .load_snapshot(result.child_snapshot_id)
             .iter_entities("assignment")))

    movers = []
    for oid, (rid, st) in before.items():
        if oid == op:
            continue                              # the gesture itself
        nxt = after.get(oid)
        if nxt is None:
            movers.append((oid, "DROPPED", None))
        elif nxt != (rid, st):
            movers.append((oid, f"{rid[:8]}@{st:%m-%d %H:%M}",
                           f"{nxt[0][:8]}@{nxt[1]:%m-%d %H:%M}"))
    return result, before, after, movers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--run", default=str(GEN3_RUN))
    ap.add_argument("--shift", type=int, default=60,
                    help="minutes for the positive-control real move")
    args = ap.parse_args()

    work = Path(args.work)
    if "_data" in work.resolve().parts:
        print("REFUSING: that path is inside the live data root.")
        return 2
    copy = work / "q6_copy"
    if copy.exists():
        shutil.rmtree(copy)
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(args.run), copy)
    print(f"scratch copy : {copy}")

    doc = json.loads((copy / "schedule_document.json").read_text(encoding="utf-8"))
    # A real move: the first ACTIVE single-chunk bar, pinned at its own place.
    # (Zero-move keeps the pin trivially satisfiable, which is the cleanest way
    # to ask whether anything ELSE moves.)
    bar = None
    for a in doc.get("assignments") or []:
        ch = a.get("chunks") or []
        if a.get("commitment_state") != "committed" and len(ch) == 1 and ch[0].get("start"):
            bar = (a["operation_ref"], a["resource_id"], ch[0]["start"])
            break
    if bar is None:
        print("no editable bar")
        return 1
    print(f"gesture      : op {bar[0][:12]} on {bar[1][:12]} @ {bar[2]} "
          f"(zero-move)")
    print()

    from datetime import timedelta
    from mre.modules.sandbox import _parse_dt
    # The positive control must actually BIND. A pin that collides with another
    # placement is a correct refusal, not a measurement, so try successively
    # larger shifts on successively later bars until one is accepted.
    candidates = []
    for a in doc.get("assignments") or []:
        ch = a.get("chunks") or []
        if a.get("commitment_state") != "committed" and len(ch) == 1 and ch[0].get("start"):
            candidates.append((a["operation_ref"], a["resource_id"], ch[0]["start"]))
    shifted = None
    for cand in candidates[:12]:
        for mins in (args.shift, 120, 240, 480):
            trial = (cand[0], cand[1],
                     (_parse_dt(cand[2]) + timedelta(minutes=mins)).isoformat())
            try:
                run_cell("probe", copy, work, True, trial)
            except Exception:                              # noqa: BLE001
                continue
            shifted = trial
            print(f"positive-control gesture : op {trial[0][:12]} "
                  f"+{mins} min -> {trial[2]}")
            break
        if shifted:
            break
    if shifted is None:
        print("positive-control gesture : NONE FOUND — cells C/D cannot run, "
              "so cell A's zero is UNCONTROLLED")
    print()

    # Cells C/D are the POSITIVE CONTROL. A "0 movers" in cell A only means
    # something if this instrument can produce a nonzero on the same board with
    # the same reader — otherwise it is a clean bill from a blind detector,
    # which is the failure this probe already hit once (see placements_of).
    cells = [("A_pinned_zeromove", True, bar),
             ("B_unpinned_zeromove", False, bar)]
    if shifted is not None:
        cells += [("C_pinned_realmove", True, shifted),
                  ("D_unpinned_realmove", False, shifted)]
    for label, hold_all, gesture in cells:
        print("=" * 70)
        print(f"CELL {label}   hold_all_placements={hold_all}   workers=1")
        print("=" * 70)
        try:
            result, before, after, movers = run_cell(
                label, copy, work, hold_all, gesture)
        except Exception as exc:                       # noqa: BLE001
            print(f"  RAISED {type(exc).__name__}: {exc}")
            print()
            continue
        print(f"  incumbent placements       : {len(before)}")
        print(f"  child placements           : {len(after)}")
        print(f"  result.moved_count         : {result.moved_count}")
        print(f"  UNTOUCHED placements MOVED : {len(movers)}")
        for oid, was, now in movers[:10]:
            print(f"      {oid[:12]}  {was}  ->  {now}")
        if len(movers) > 10:
            print(f"      ... and {len(movers) - 10} more")
        print()

    print("R-T2 claims 'nothing else moved'. Cell A is where that claim lives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
