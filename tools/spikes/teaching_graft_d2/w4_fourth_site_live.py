"""(d.2) RIDER R1 — the fourth W4 site, BEFORE and AFTER, on the fenced world.

The site is `mobility_lead_line`'s earlier-open branch, which renders on a
FAMILY route (`what-would-change` / `frozen`) that did not compute its own
verdict. `_ai_exam_scratch/mobility_pinned` is the only world that produces the
verdict at all, and `ORD-EARLY op10 on BOX-01` is its one specimen — driver
CAPACITY_BLOCKED, measured by `w4_fourth_site_count.py`.

This renders the lead through the real `mobility_verdict` -> `mobility_lead_line`
path, so what it prints is what a planner would read.

    python tools/spikes/teaching_graft_d2/w4_fourth_site_live.py

Read-only. No model, no solver.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "_ai_exam_scratch" / "mobility_pinned"


def main() -> int:
    from mre.ai_exam.runner import RunTarget
    from mre.modules.explainer import ExplanationBundle
    from mre.modules.renderers import mobility_lead_line

    ex = RunTarget.from_out_dir(OUT, "snap-mobility").build_vocab()._ex
    mob = ex.mobility_verdict("ORD-EARLY", "BOX-01", 10)
    if mob is None:
        print("the fenced world did not load; nothing measured")
        return 1

    print("mobility_lead payload keys:")
    for k in sorted(mob):
        print(f"    {k:18s} {mob[k]!r}")
    print()

    bundle = ExplanationBundle(
        question="what would have to change for ORD-EARLY op10 to start earlier",
        subject_id="d", subject_type="counterfactual",
        subject_external_name="ORD-EARLY", ordered_records=[],
        key_facts={"mobility_lead": mob}, snapshot_id="snap-mobility",
        identity_map=None)
    print("THE LEAD, as a planner reads it:")
    print("   ", mobility_lead_line(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
