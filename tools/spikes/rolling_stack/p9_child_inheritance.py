"""R4.2 W5 — ONE REAL ACCEPT, THROUGH THE API, AND THE GESTURE THAT STARTED IT.

The arc's founding symptom (4x, then R4.0 §3.4): a planner accepted an edit on a
rolling board, and every nudge on the resulting child came back "this placement
isn't possible here — the machine is not open at that time", about machines that
were open. 24 of 24 impossible, 23 of them a false sentence, because the accept
minted a MONOLITHIC, DATELESS child of a rolling, calibrated parent.

This probe drives ONE real accept through the real API path — `POST
/schedules/{id}/accept`, `_execute_accept`, `apply_planner_edit`,
`build_document_from_run` — on a SCRATCH COPY of the gen-3 demo world, and then
fires the same beat-one ladder at the CHILD and at the PARENT through the real
`POST /schedules/{id}/sandbox/feasibility` endpoint.

Three parts:

  A. the accept, and the child's INHERITANCE TABLE (R-CH1 clauses 1-4);
  B. beat one on the child vs beat one on the parent, same ops, same offsets;
  C. the 2x2 against an INDEPENDENT calendar ground truth — false refusals AND
     false permissions, which is R4.1's audit of R4.0's one-directional check.

THE DENOMINATOR HABIT. Part C reports its own visibility before its verdict: the
ground-truth reader RAISES rather than returning [] (R4.0's `p2_frame` reported
"0 false sentences" from a calendar key that does not exist), and the summary
states whether the instrument saw a nonzero in BOTH the refusal and the pass
column. A 2x2 with an empty row proves nothing about the other.

NEVER touches the live data root: it copies what it needs into a scratch tree and
runs with the process cwd there, because registry paths are cwd-relative.

    python tools/spikes/rolling_stack/p9_child_inheritance.py --work <scratch dir>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

GEN3_SCHEDULE = "rolling-9fdee7aa-ec5"
GEN3_RUN = "9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc"
NUDGES = (30, 60, 120, 240)


# ---------------------------------------------------------------------------
# scratch data root
# ---------------------------------------------------------------------------

def build_scratch_root(work: Path, run_id: str) -> Path:
    """A data root holding exactly the registry + the one run we accept onto.

    Registry rows store cwd-RELATIVE paths (`_data\\runs\\<id>\\...`), so the
    copy is faithful only if the process then runs with `work` as its cwd. That
    is what keeps this probe off `_data` entirely."""
    src = REPO / "_data"
    dst = work / "_data"
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "runs").mkdir(parents=True)
    shutil.copy2(src / "registry.sqlite", dst / "registry.sqlite")
    if (src / "calibration").exists():
        shutil.copytree(src / "calibration", dst / "calibration")
    from mre.modules import longpath
    longpath.copytree(src / "runs" / run_id, dst / "runs" / run_id)
    return dst


# ---------------------------------------------------------------------------
# ground truth (independent of var_map, and it RAISES on a blind read)
# ---------------------------------------------------------------------------

class CalendarTruth:
    """Open windows per resource, from the canonical calendar entities.

    Refuses to answer from an empty read. R4.0's own probe reported a clean bill
    out of an empty denominator by reading a calendar key that does not exist;
    the cheap defence is to make the blind case raise, not return []."""

    def __init__(self, run_dir: Path, snapshot_id: str):
        from mre.modules.calendar_utils import flatten_all_calendars
        from mre.modules.snapshot_store import SnapshotStore
        from mre.modules.solution_pool import _m5_horizon, _read_evidence

        reader = SnapshotStore(run_dir / "snapshots").load_snapshot(snapshot_id)
        hs, he = _m5_horizon(_read_evidence(run_dir / "runs"))
        cals = flatten_all_calendars(list(reader.iter_entities("calendar")), hs, he)
        self._res = {r["id"]: r for r in reader.iter_entities("resource")}
        self._cal = {c.get("id"): c for c in cals}
        self.horizon_start, self.horizon_end = hs, he

    def windows(self, rid: str) -> list[tuple[datetime, datetime]]:
        r = self._res.get(rid) or {}
        cal = self._cal.get(r.get("calendar_ref"))
        if cal is None:
            raise RuntimeError(f"no calendar for resource {rid}")
        hr = cal.get("horizon_resolved")
        if not hr:
            raise RuntimeError(f"calendar for {rid} has no horizon_resolved windows")
        return [(datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"]))
                for w in hr]

    def fits(self, rid: str, at: datetime, dur_min: int) -> tuple[bool, bool]:
        ws = self.windows(rid)
        open_now = any(s <= at < e for s, e in ws)
        fits = any(s <= at and at + timedelta(minutes=dur_min) <= e for s, e in ws)
        return open_now, fits


# ---------------------------------------------------------------------------

def beat_one_ladder(client, schedule_id, targets, truth, label):
    """Fire the ladder at ONE board through the real endpoint. Returns rows and
    the typed-frame-error count — a FrameMismatch is R-SG1's refusal and must be
    ZERO on a sound child, so it is counted, never swallowed."""
    from mre.modules.standing_pins import FrameMismatch

    rows, frame_errors = [], 0
    for op_id, rid, inc_start, dur in targets:
        for nudge in NUDGES:
            at = inc_start + timedelta(minutes=nudge)
            try:
                resp = client.post(
                    f"/schedules/{schedule_id}/sandbox/feasibility",
                    json={"pin_op_id": op_id, "pin_resource_id": rid,
                          "pin_start_iso": at.isoformat(), "deterministic": True},
                )
            except FrameMismatch as exc:
                frame_errors += 1
                rows.append({"op": op_id, "nudge": nudge, "at": at,
                             "res": rid, "dur": dur, "feasible": None,
                             "verdict": "FRAME-MISMATCH", "message": str(exc)})
                continue
            if resp.status_code != 200:
                rows.append({"op": op_id, "nudge": nudge, "at": at, "res": rid,
                             "dur": dur, "feasible": None,
                             "verdict": f"HTTP {resp.status_code}",
                             "message": resp.text[:200]})
                continue
            d = resp.json()["data"]
            rows.append({"op": op_id, "nudge": nudge, "at": at, "res": rid,
                         "dur": dur, "feasible": bool(d.get("feasible")),
                         "verdict": d.get("verdict"),
                         "message": d.get("message") or ""})
    # the 2x2 against ground truth
    for r in rows:
        if r["feasible"] is None:
            r["open"] = r["truth_fits"] = None
            continue
        r["open"], r["truth_fits"] = truth.fits(r["res"], r["at"], r["dur"])
    print(f"\n  --- {label}: {schedule_id}")
    for r in rows:
        mark = ""
        if r["feasible"] is False and r["truth_fits"]:
            mark = "  <<< FALSE REFUSAL"
        if r["feasible"] is True and r["truth_fits"] is False:
            mark = "  <<< FALSE PERMISSION"
        print(f"    op {r['op'][:11]} +{r['nudge']:4}min {str(r['at'])[:16]} "
              f"truth[open={str(r['open']):5} fits={str(r['truth_fits']):5}] "
              f"-> {str(r['verdict']):14}{mark}")
    return rows, frame_errors


def tally(rows):
    ok_refuse = sum(1 for r in rows if r["feasible"] is False and r["truth_fits"] is False)
    ok_pass = sum(1 for r in rows if r["feasible"] is True and r["truth_fits"] is True)
    false_refuse = sum(1 for r in rows if r["feasible"] is False and r["truth_fits"] is True)
    false_permit = sum(1 for r in rows if r["feasible"] is True and r["truth_fits"] is False)
    impossible = sum(1 for r in rows if r["verdict"] == "impossible")
    possible = sum(1 for r in rows if r["feasible"] is True)
    not_open = sum(1 for r in rows
                   if "not open at that time" in (r["message"] or "") and r["open"])
    return dict(total=len(rows), ok_refuse=ok_refuse, ok_pass=ok_pass,
                false_refuse=false_refuse, false_permit=false_permit,
                impossible=impossible, possible=possible,
                false_sentences=not_open)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--schedule", default=GEN3_SCHEDULE)
    ap.add_argument("--run", default=GEN3_RUN)
    ap.add_argument("--targets", type=int, default=8)
    ap.add_argument("--budget", type=float, default=300.0)
    args = ap.parse_args()

    work = Path(args.work).resolve()
    if (REPO / "_data").resolve() in work.parents or work == (REPO / "_data").resolve():
        print("REFUSING: that path is inside the live data root.")
        return 2
    work.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("R4.2 W5 — one real accept through the API, on a scratch copy")
    print("=" * 78)
    root = build_scratch_root(work, args.run)
    print(f"  scratch data root : {root}")
    os.chdir(work)                       # registry paths are cwd-relative
    os.environ["MRE_DATA_ROOT"] = "_data"

    from fastapi.testclient import TestClient
    from mre.api.app import create_app
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.solution_pool import _placements
    from mre.modules.sandbox import _incumbent_duration_min

    app = create_app("_data")
    client = TestClient(app)

    parent_doc = client.get(f"/schedules/{args.schedule}").json()["data"]
    run_dir = Path("_data/runs") / args.run
    snap_id = parent_doc["snapshot_id"]
    assigns = list(SnapshotStore(run_dir / "snapshots")
                   .load_snapshot(snap_id).iter_entities("assignment"))
    placements = _placements(assigns)
    if not placements:
        raise RuntimeError("read 0 placements from a plan that has them")

    # ---- the targets: ACTIVE-WINDOW bars, in document order ------------------
    by_op = {a["operation_ref"]: a for a in assigns}
    active = [a["operation_ref"] for a in parent_doc["assignments"]
              if a.get("commitment_state") == "active_window"]
    # STRIDED, not the first N. The document is sorted by start, so the first
    # eight active bars all sit in the same open morning and the whole ladder
    # comes back `possible` — a 2x2 with an empty refusal row, which is exactly
    # the empty-denominator shape this repo keeps catching. Striding across the
    # window puts probes against shift ends, where a refusal is EARNED.
    stride = max(1, len(active) // max(1, args.targets))
    targets = []
    for oid in active[::stride]:
        if len(targets) >= args.targets:
            break
        rid, start = placements[oid]
        dur = _incumbent_duration_min(by_op.get(oid))
        if dur:
            targets.append((oid, rid, start, dur))

    # ---- A. THE ACCEPT -------------------------------------------------------
    pin_op, pin_res, pin_start, _ = targets[0]
    print(f"\n  accept gesture   : op {pin_op[:11]} -> {pin_res[:11]} "
          f"@ {pin_start.isoformat()}  (zero-move: its own placement)")
    resp = client.post(f"/schedules/{args.schedule}/accept", json={
        "pin_op_id": pin_op, "pin_resource_id": pin_res,
        "pin_start_iso": pin_start.isoformat(),
        "authority": "r4.2-w5", "budget_s": args.budget,
    })
    if resp.status_code != 201:
        print(f"  ACCEPT FAILED {resp.status_code}: {resp.text[:400]}")
        return 1
    child_id = resp.json()["data"]["schedule_id"]
    child_doc = client.get(f"/schedules/{child_id}").json()["data"]
    print(f"  child            : {child_id}")

    # ---- B. THE INHERITANCE TABLE -------------------------------------------
    from mre.modules.scenario import derive_base_context
    child_run = client.get(f"/schedules/{child_id}/meta").json()["data"]
    child_run_dir = Path("_data/runs") / child_doc["run_id"]
    ctx = derive_base_context(child_run_dir / "runs")

    def cal(doc):
        return ((doc.get("solver") or {}).get("calibration") or {})

    p_roll, c_roll = parent_doc.get("rolling") or {}, child_doc.get("rolling") or {}
    print("\n" + "=" * 78)
    print("A. THE INHERITANCE TABLE (R-CH1)")
    print("=" * 78)
    rowfmt = "  {:34} {:>20} {:>20}"
    print(rowfmt.format("", "PARENT", "CHILD"))
    print(rowfmt.format("contract", parent_doc["contract_version"],
                        child_doc["contract_version"]))
    print(rowfmt.format("rolling block", str(bool(p_roll)), str(bool(c_roll))))
    print(rowfmt.format("  reference_origin", str(p_roll.get("reference_origin"))[:19],
                        str(c_roll.get("reference_origin"))[:19]))
    print(rowfmt.format("  window_start", str(p_roll.get("window_start"))[:19],
                        str(c_roll.get("window_start"))[:19]))
    print(rowfmt.format("  window_end", str(p_roll.get("window_end"))[:19],
                        str(c_roll.get("window_end"))[:19]))
    print(rowfmt.format("  frozen_until", str(p_roll.get("frozen_until"))[:19],
                        str(c_roll.get("frozen_until"))[:19]))
    print(rowfmt.format("  window/frozen days",
                        f"{p_roll.get('window_days')}/{p_roll.get('frozen_days')}",
                        f"{c_roll.get('window_days')}/{c_roll.get('frozen_days')}"))
    print(rowfmt.format("  committed_count", str(p_roll.get("committed_count")),
                        str(c_roll.get("committed_count"))))
    print(rowfmt.format("  active_count", str(p_roll.get("active_count")),
                        str(c_roll.get("active_count"))))
    print(rowfmt.format("  beyond_horizon (tray)",
                        str(len(p_roll.get("beyond_horizon") or [])),
                        str(len(c_roll.get("beyond_horizon") or []))))
    print(rowfmt.format("  coarse_zone", str(bool(p_roll.get("coarse_zone"))),
                        str(bool(c_roll.get("coarse_zone")))))
    print(rowfmt.format("assignments", str(len(parent_doc["assignments"])),
                        str(len(child_doc["assignments"]))))
    print(rowfmt.format("solver.calibration state",
                        str(cal(parent_doc).get("state")),
                        str(cal(child_doc).get("state"))))
    print(rowfmt.format("  profile_id", str(cal(parent_doc).get("profile_id"))[:20],
                        str(cal(child_doc).get("profile_id"))[:20]))
    print(rowfmt.format("  applied (coefficients)",
                        str(bool(cal(parent_doc).get("applied"))),
                        str(bool(cal(child_doc).get("applied")))))
    print(rowfmt.format("solver.portfolio present",
                        str(bool((parent_doc.get("solver") or {}).get("portfolio"))),
                        str(bool((child_doc.get("solver") or {}).get("portfolio")))))
    print(rowfmt.format("document reference_date",
                        str(parent_doc.get("reference_date"))[:19],
                        str(child_doc.get("reference_date"))[:19]))
    print(rowfmt.format("reference_date RECOVERABLE",
                        "n/a", str(ctx.get("reference_date"))))
    print(rowfmt.format("  solver_workers / seed", "n/a",
                        f"{ctx.get('solver_workers')} / {ctx.get('solver_seed')}"))
    print(f"\n  child calibration sentence:\n    {cal(child_doc).get('sentence')}")
    print(f"\n  child meta status: {child_run.get('status')}")

    # placements identical to the accepted plan?
    child_run_snap = child_doc["snapshot_id"]
    child_assigns = list(
        SnapshotStore(child_run_dir / "snapshots")
        .load_snapshot(child_run_snap).iter_entities("assignment"))
    cp = _placements(child_assigns)
    doc_pl = {a["operation_ref"]: (a["resource_id"], a["chunks"][0]["start"])
              for a in child_doc["assignments"] if a.get("chunks")}
    same = sum(1 for oid, (r, s) in cp.items()
               if doc_pl.get(oid, (None, None))[0] == r
               and doc_pl.get(oid, (None, ""))[1][:19] == s.isoformat()[:19])
    print(f"  document placements == accepted plan : {same} of {len(cp)}")

    moved = sum(1 for oid, (r, s) in cp.items()
                if placements.get(oid) and placements[oid] != (r, s))
    print(f"  bars that moved vs the parent        : {moved} of {len(cp)}")

    # ---- C. THE GESTURE THAT STARTED THIS ARC -------------------------------
    print("\n" + "=" * 78)
    print("B. BEAT ONE — the child, and the correctly-scoped parent")
    print("=" * 78)
    truth_parent = CalendarTruth(run_dir, snap_id)
    truth_child = CalendarTruth(child_run_dir, child_run_snap)
    print(f"  ground-truth visibility: parent {len(truth_parent.windows(targets[0][1]))} "
          f"windows on the first target's machine; child "
          f"{len(truth_child.windows(targets[0][1]))} "
          f"(the reader RAISES on an empty read rather than returning [])")

    c_rows, c_frame = beat_one_ladder(client, child_id, targets, truth_child,
                                      "CHILD")
    p_rows, p_frame = beat_one_ladder(client, args.schedule, targets, truth_parent,
                                      "PARENT (correctly scoped)")

    ct, pt = tally(c_rows), tally(p_rows)
    print("\n" + "=" * 78)
    print("C. THE 2x2, BOTH BOARDS")
    print("=" * 78)
    f = "  {:36} {:>12} {:>12}"
    print(f.format("", "CHILD", "PARENT"))
    for k, lbl in (("total", "probes"), ("possible", "possible"),
                   ("impossible", "impossible"),
                   ("ok_refuse", "correct refusal (refused, no fit)"),
                   ("ok_pass", "correct pass    (passed,  fits)"),
                   ("false_refuse", "FALSE REFUSAL   (refused, fits)"),
                   ("false_permit", "FALSE PERMISSION(passed, no fit)"),
                   ("false_sentences", "FALSE 'not open' sentences")):
        print(f.format(lbl, ct[k], pt[k]))
    print(f.format("typed frame errors (FrameMismatch)", c_frame, p_frame))

    blind = []
    if ct["ok_refuse"] == 0 and ct["false_refuse"] == 0:
        blind.append("the CHILD produced no refusal at all — the refusal column "
                     "is empty and proves nothing")
    if ct["ok_pass"] == 0:
        blind.append("the CHILD produced no pass at all — the pass column is "
                     "empty and proves nothing")
    print("\n  DENOMINATOR CHECK:")
    if blind:
        for b in blind:
            print(f"    !! {b}")
    else:
        print(f"    both columns non-empty on the child "
              f"({ct['ok_pass']} passes, {ct['ok_refuse'] + ct['false_refuse']} "
              f"refusals) — the 2x2 can discriminate.")

    (work / "p9_result.json").write_text(json.dumps({
        "child_schedule_id": child_id, "parent": args.schedule,
        "child_rolling": bool(c_roll), "child_tally": ct, "parent_tally": pt,
        "child_frame_errors": c_frame, "parent_frame_errors": p_frame,
        "reference_date_recoverable": ctx.get("reference_date"),
        "calibration_state": cal(child_doc).get("state"),
        "calibration_sentence": cal(child_doc).get("sentence"),
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
