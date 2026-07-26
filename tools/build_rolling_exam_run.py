"""Build the PINNED ROLLING RUN the ai_exam rolling bank asks against.

Session 4A.5c CU4/CU5. The exam's monolithic world (``_ai_exam_scratch/gb_pinned``)
has no sliced state, so every rolling question there is answered "this isn't a
rolling schedule" — honest, and useless as a test of the sliced world. This builds
its rolling sibling: a pilot_scale plant, window 0 solved deterministically and
PERSISTED as a first-class run (the 4B.3c capability), plus the assembled
contract-1.7 document that carries the committed front, the active window and the
beyond-horizon tray.

    PYTHONHASHSEED=0 python tools/build_rolling_exam_run.py

Deterministic settings are fixed here rather than passed: seed 42 for rolling /
pilot_scale work (the standing convention), ``deterministic=True`` so the window-0
solve is reproducible, and a reference date pinned to the same 2026-01-05 the
cockpit fixture uses. A rolling run whose window moved between two sweeps would
make every comparison meaningless.

Output (gitignored scratch, exactly like ``gb_pinned`` — the BUILDER is the
committed artifact, not its output):

    _ai_exam_scratch/rolling_pinned/
        runs/ snapshots/ evidence_index.json   the persisted window-0 run
        document.json                          the contract-1.7 rolling document
        TARGET.json                            out-dir + snapshot id + doc path

This is a NEW fixture, not a change to an existing golden. Nothing here touches
``tests/cockpit/fixtures/rolling/``.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
OUT = REPO / "_ai_exam_scratch" / "rolling_pinned"
SEED = 42                 # the standing seed for rolling / pilot_scale work
ORDERS = 40
WINDOW_DAYS = 14
FROZEN_DAYS = 3


def main() -> int:
    from generate_erp_dataset import generate
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    tmp = Path(tempfile.mkdtemp(prefix="rollexam"))
    print(f"rolling-exam: generating pilot_scale ({ORDERS} orders, seed 1)…")
    generate(tmp / "sub", scenario="pilot_scale", orders=ORDERS, seed=1)

    plant = prepare_plant(tmp / "sub", tmp / "prep", reference_date=REF)
    print(f"rolling-exam: solving window 0 (window={WINDOW_DAYS}d "
          f"frozen={FROZEN_DAYS}d, deterministic, seed={SEED})…")
    view = build_rolling_view(plant, window_days=WINDOW_DAYS,
                              frozen_days=FROZEN_DAYS, gravity=True,
                              deterministic=True, seed=SEED,
                              member_time_limit_s=10.0, det_time=2.0,
                              persist=True)

    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view,
                                    schedule_id="sched-rolling-exam",
                                    run_id="run-rolling-exam",
                                    identity_map=idmap).model_dump(mode="json")

    OUT.mkdir(parents=True, exist_ok=True)
    # Copy the persisted run beside the document so the exam target is one
    # self-contained directory (the gb_pinned shape).
    import shutil
    for sub in ("runs", "snapshots"):
        src = Path(plant.out_dir) / sub
        if src.exists():
            dst = OUT / sub
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    index = EvidenceIndex().build(OUT / "runs")
    index.save(OUT / "evidence_index.json")

    (OUT / "document.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    target = {
        "out_dir": str(OUT),
        "snapshot_id": plant.snapshot_id,
        "document_path": str(OUT / "document.json"),
        "seed": SEED, "window_days": WINDOW_DAYS, "frozen_days": FROZEN_DAYS,
        "reference_date": REF.isoformat(),
    }
    (OUT / "TARGET.json").write_text(json.dumps(target, indent=2), encoding="utf-8")

    r = doc["rolling"]
    print(f"rolling-exam: {len(doc['assignments'])} bars, "
          f"{r['committed_count']} committed, {r['active_count']} active, "
          f"{len(r['beyond_horizon'])} in the tray")
    print(f"rolling-exam: snapshot {plant.snapshot_id}")
    print(f"rolling-exam: -> {OUT}")
    if not r["beyond_horizon"]:
        print("rolling-exam: !! EMPTY TRAY — the rolling bank's tray questions "
              "would test nothing. Shorten the window and rebuild.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
