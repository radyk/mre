"""Commit the two measured profiles as artifacts (Session 4B.29 Item 3).

The ceremony writes into a scratch out-dir; this rebuilds each profile FROM ITS
OWN CELLS (so the grid digest, the recommendation and the cost-honesty pair are
all derived rather than carried) and writes the sealed JSON plus its rendered
report under `docs/calibration/`.

R-CAL1 rule (2): neither is accepted. A committed artifact is the OFFER.

    python tools/spikes/calibration_4b29/export_profiles.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "src"))

REF = datetime(2026, 1, 5, tzinfo=timezone.utc)
OUT = REPO / "docs" / "calibration"

ARMS = [
    ("demo_board",
     REPO / "_4b29_scratch" / "demo",
     REPO / "_4b22a_scratch" / "demo_board" / "submission",
     10,
     "demo_board, 280 orders, seed 1, ref 2026-01-05 -- the world "
     "rolling-c9973708-865 was minted from (4B.22a). Budgets 3/6/8/10/15 at "
     "window 10; the 8.0 column is 4B.26 section 6(b)'s residual arm."),
    ("mid170",
     REPO / "_4b29_scratch" / "mid170",
     REPO / "_4b26_scratch" / "mid170" / "submission",
     14,
     "170 orders, 4B.22a's c3-w14-170 generator settings (seed 1, pd_share "
     "0.12, lead_p50 10, splittable_weight 1) -- the CONTROL board. Budgets "
     "3/6/10 at windows 10 and 14; the w14 arm is 4B.26 section 6(d)'s "
     "residual arm."),
]


def main() -> int:
    from mre.modules.calibration import build_profile, load_cells, render_profile

    OUT.mkdir(parents=True, exist_ok=True)
    for name, cells_dir, submission, prefer, notes in ARMS:
        cells = load_cells(cells_dir)
        if not cells:
            print(f"{name}: NO CELLS at {cells_dir} — skipped")
            continue
        prof = build_profile(submission, cells, seeds=[42, 43, 44, 45, 46],
                             prefer_window=prefer, reference_date=REF,
                             notes=notes)
        assert prof.digest_ok(), f"{name} did not seal"
        assert not prof.accepted, "rule (2): a committed profile is an OFFER"
        (OUT / f"{name}.json").write_text(prof.model_dump_json(indent=2),
                                          encoding="utf-8")
        (OUT / f"{name}.txt").write_text(render_profile(prof) + "\n",
                                         encoding="utf-8")
        print(f"{name}: {len(cells)} cells, digest {prof.grid_digest[:16]}...")
        print(f"  {prof.recommendation.sentence()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
