"""R4.0 recon P2 — reproduce an S2-class beat-one refusal, in-process.

Calls the REAL ``sandbox.feasibility_ghost`` (the same function the API's
``POST /sandbox/feasibility`` calls, with the same ``restrict_op_ids`` the API
derives) on a SCRATCH COPY of a run dir. Beat one writes evidence under
``<run>/sandbox/``, so it is never pointed at a pinned world.

Selection and ladder are 4x's own (``tools/worlds/replay_demo_lineage.py``):
ACTIVE, single-chunk bars in sorted order; offsets +60/+120/+30/+240 minutes.

For every refusal it records BOTH halves of the question the 4x close-out left
open — is the CHECK wrong, or is the SENTENCE wrong:

  * CP-SAT's own verdict (the check), and
  * what ``relaxed_refusal`` attributed it to (the sentence), beside the
    calendar's INDEPENDENTLY computed ground truth for that instant.

Usage:
  python tools/spikes/rolling_stack/p2_nudge_replay.py --run <SCRATCH run dir>
                                                       [--ops 10]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

OFFSET_MINUTES = (60, 120, 30, 240)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="a SCRATCH run dir (copied)")
    ap.add_argument("--ops", type=int, default=10)
    ap.add_argument("--no-restrict", action="store_true",
                    help="pass restrict_op_ids=None — what the API does for a "
                         "document with no rolling block (a MONOLITHIC child)")
    ap.add_argument("--force-ref", default=None,
                    help="ISO date forced as reference_date, by monkeypatching "
                         "the run-context read — isolates the LOST-reference_"
                         "date defect (the SENTENCE) from the LOST-scope one "
                         "(the CHECK)")
    args = ap.parse_args()

    if args.force_ref:
        # the one field `derive_base_context` could not recover from the child's
        # run dir, put back — nothing else changed.
        from mre.modules import scenario as _scen
        _orig = _scen.derive_base_context

        def _patched(runs_dir):
            ctx = _orig(runs_dir)
            ctx["reference_date"] = args.force_ref
            return ctx
        _scen.derive_base_context = _patched
    run_dir = Path(args.run)

    if "_data" in run_dir.resolve().parts:
        print("REFUSING: that path is inside the live data root. Copy it first.")
        return 2

    from mre.modules.calendar_utils import flatten_all_calendars
    from mre.modules.sandbox import feasibility_ghost
    from mre.modules.snapshot_store import SnapshotStore

    doc = json.loads((run_dir / "schedule_document.json").read_text(encoding="utf-8"))
    snap_id = next(p.name for p in (run_dir / "snapshots").iterdir() if p.is_dir())

    # 4x's own selection: ACTIVE, single-chunk bars, sorted.
    bars = []
    for a in doc.get("assignments") or []:
        chunks = a.get("chunks") or []
        if a.get("commitment_state") == "committed" or len(chunks) != 1:
            continue
        if not chunks[0].get("start"):
            continue
        bars.append((a["operation_ref"], a["resource_id"], chunks[0]["start"]))
    bars.sort()
    print(f"run           : {run_dir}")
    print(f"active bars   : {len(bars)}  (walking {min(args.ops, len(bars))})")

    # the API's restrict set
    reader = SnapshotStore(run_dir / "snapshots").load_snapshot(snap_id)
    assigns = list(reader.iter_entities("assignment"))
    resources = list(reader.iter_entities("resource"))
    calendars = list(reader.iter_entities("calendar"))
    ops_total = len(list(reader.iter_entities("operation")))
    restrict = (None if args.no_restrict
                else {a["operation_ref"] for a in assigns
                      if a.get("operation_ref")})
    print(f"rolling block : {bool(doc.get('rolling'))}")
    print(f"restrict set  : "
          f"{'None (WHOLE PLANT: %d ops)' % ops_total if restrict is None else '%d ops' % len(restrict)}")

    # independent calendar ground truth
    from mre.modules.solution_pool import _m5_horizon, _read_evidence
    hs, he = _m5_horizon(_read_evidence(run_dir / "runs"))
    flat = flatten_all_calendars(calendars, hs, he)
    cal_by_id = {c.get("id"): c for c in flat}
    res_by_id = {r["id"]: r for r in resources}

    def truth(rid, at, dur_min):
        cal = cal_by_id.get((res_by_id.get(rid) or {}).get("calendar_ref"))
        hr = (cal or {}).get("horizon_resolved")
        if not hr:
            raise RuntimeError(f"no resolved calendar for {rid}")
        ws = [(datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"]))
              for w in hr]
        op = any(s <= at < e for s, e in ws)
        ft = any(s <= at and at + timedelta(minutes=dur_min) <= e for s, e in ws)
        return op, ft

    dur_by_op = {}
    for a in assigns:
        w = (a.get("phase_windows") or {}).get("run") or []
        if w:
            s = datetime.fromisoformat(w[0]["start"])
            e = datetime.fromisoformat(w[-1]["end"])
            dur_by_op[a["operation_ref"]] = int((e - s).total_seconds() // 60)

    tally = {}
    false_sentences = []
    unattributed = 0
    probes = 0
    for op, rid, start_iso in bars[: args.ops]:
        base = datetime.fromisoformat(start_iso)
        for off in OFFSET_MINUTES:
            at = base + timedelta(minutes=off)
            probes += 1
            g = feasibility_ghost(
                out_dir=run_dir, snapshot_id=snap_id, pin_op_id=op,
                pin_resource_id=rid, pin_start_iso=at.isoformat(),
                restrict_op_ids=restrict, deterministic=True)
            ref = g.refusal or {}
            sent = ref.get("sentence") if isinstance(ref, dict) else None
            fam = (ref.get("family") if isinstance(ref, dict) else None) or "(none)"
            o, f = truth(rid, at, dur_by_op.get(op, 0))
            key = (g.verdict, fam, sent or "(unattributed)")
            tally[key] = tally.get(key, 0) + 1
            bad = ""
            if g.verdict == "impossible":
                if sent is None:
                    unattributed += 1
                elif "not open at that time" in sent and o:
                    bad = "  <<< FALSE SENTENCE"
                    false_sentences.append((op, rid, at.isoformat(), sent))
                elif "closes before this would finish" in sent and f:
                    bad = "  <<< FALSE SENTENCE"
                    false_sentences.append((op, rid, at.isoformat(), sent))
            print(f"  {op[:12]} {rid[:12]} +{off:4}m {str(at)[:19]} "
                  f"{g.verdict:11} status={g.status:11} "
                  f"truth[open={o!s:5} fits={f!s:5}] {sent or '(unattributed)'}{bad}")

    print("\n" + "=" * 74)
    print(f"probes                     : {probes}")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4}  verdict={k[0]:11} family={k[1]:8} {k[2]}")
    print(f"refusals with NO attribution : {unattributed}")
    print(f"FALSE sentences              : {len(false_sentences)}")
    for f in false_sentences[:10]:
        print(f"    {f[0][:12]} on {f[1][:12]} at {f[2]} -> {f[3]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
