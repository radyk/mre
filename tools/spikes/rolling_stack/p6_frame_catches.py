"""R4.1 W2 — does the frame invariant catch the REAL defect?

The specimen is 4x's own: schedule ``b5daba66-e928-40fb-a0a4-d17e240d6152``
(run dir ``ada15460-…``), the accept-derived child of the gen-2 demo board. It
carries no rolling block and no recoverable reference_date, so the API hands
beat one ``restrict_op_ids=None`` and the builder's origin drags 35 days back
from the evidence horizon.

Before R4.1 the beat-one gesture on that child emitted a confident, FALSE
sentence: "the machine is not open at that time", about a machine that was
open. After R4.1 the same call must raise ``FrameMismatch`` instead — the
gesture fails loudly and no verdict about the plant is rendered.

Runs against a SCRATCH COPY of the child's run dir; _data is never written.

    python tools/spikes/rolling_stack/p6_frame_catches.py --work <scratch dir>
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

CHILD_RUN = Path("_data/runs/ada15460-8fb0-47c4-863b-6d6e6c333162")
# 4x's exact specimen: the op, the machine, and the instant it was refused at.
SPEC_OP = "004733d3-aa3c-58ac-ad63-9f2dfedcf371"
SPEC_RES = "fd34d391-ffa4-5def-a712-05266480c417"
SPEC_AT = "2026-01-08T09:52:00+00:00"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="scratch dir for the copy")
    ap.add_argument("--run", default=str(CHILD_RUN))
    args = ap.parse_args()

    work = Path(args.work)
    copy = work / "b5daba66_copy"
    if copy.exists():
        shutil.rmtree(copy)
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(args.run), copy)
    print(f"scratch copy: {copy}")

    from mre.modules.sandbox import feasibility_ghost
    from mre.modules.standing_pins import FrameMismatch

    snap_id = next(p.name for p in (copy / "snapshots").iterdir() if p.is_dir())
    print(f"snapshot    : {snap_id}")
    print(f"specimen    : op {SPEC_OP[:12]} -> {SPEC_RES[:12]} at {SPEC_AT}")
    print()
    print("Calling beat one EXACTLY as the API does for a document with no")
    print("rolling block: restrict_op_ids=None (the WHOLE PLANT).")
    print("-" * 70)

    try:
        g = feasibility_ghost(
            copy, snap_id,
            pin_op_id=SPEC_OP, pin_resource_id=SPEC_RES, pin_start_iso=SPEC_AT,
            restrict_op_ids=None,          # <- what the API hands a dateless child
        )
    except FrameMismatch as exc:
        print("RAISED FrameMismatch  <- R-SG1 clause (2) holding")
        print(f"  site            : {exc.site}")
        print(f"  evidence origin : {exc.evidence_origin}")
        print(f"  builder origin  : {exc.builder_origin}")
        print(f"  offset (minutes): {exc.offset_minutes}")
        print()
        print("  message:")
        print(f"    {exc}")
        return 0

    print("NO EXCEPTION — the gesture returned a verdict:")
    print(f"  feasible : {g.feasible}")
    print(f"  verdict  : {g.verdict}")
    print(f"  message  : {g.message}")
    print(f"  refusal  : {g.refusal}")
    print()
    print(">> This is the PRE-R4.1 behaviour: a confident sentence about the")
    print("   plant, rendered from a model built 35 days from the frame the")
    print("   pin was expressed in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
