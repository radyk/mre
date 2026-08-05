"""(d.2) RIDER R1 — THE FOURTH W4 SITE, SIZED.

(e2) §8(a) named `mobility_lead_line`'s `earlier-open` branch as the fourth site
of the W4 defect class and did not fix it: the branch asserts *"Nothing was
holding {name} back"* and **has no driver in hand** — `_mobility_facts` returns
fifteen keys and none of them is one. Plumbing a driver into the mobility-lead
payload changes what the floor COMPUTES rather than how a renderer orders two
paragraphs, so it was left, pinned by a tripwire test.

THE RIDER'S RULE, and this script is the number it turns on: count, on the demo
board, how many `earlier-open` placements carry a driver in
`CONSTRAINT_NAMING_DRIVERS`. **Zero means the sentence is currently true
everywhere it renders** — file the count, leave the tripwire standing, done.
**Nonzero means plumb the driver** and put the site under the same one-definition
guard as the other three.

Counted at the same grain the renderer renders at — one (order, machine, op_seq)
placement — and the DRIVER is read off the same assignment decision
`_render_why_here` reads, never re-derived.

    python tools/spikes/teaching_graft_d2/w4_fourth_site_count.py [--run <id>]

Read-only. No model, no solver, mints nothing.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

DEMO = "rolling-c32a6140-b6b"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default=DEMO)
    ap.add_argument("--data-root", default=str(ROOT / "_data"))
    ap.add_argument("--out-dir", help="a solved out-dir instead of a schedule id "
                                      "(the FENCED specimen world)")
    ap.add_argument("--snapshot-id", default="snap-mobility")
    args = ap.parse_args()

    from mre.ai_exam.runner import RunTarget
    from mre.modules import mobility_premise as mp
    from mre.modules.renderers import (
        CONSTRAINT_NAMING_DRIVERS, counterfactual_contradicts_driver,
    )

    # THE DEMO BOARD'S ZERO IS NEARLY A TAUTOLOGY and saying so is the point:
    # `earlier-open` needs `later_at` to be None, which no plant that keeps
    # working can produce, so a count of "earlier-open placements carrying a
    # driver" on the demo board is 0 because the numerator's SET is empty. The
    # fenced specimen world (R-SW1) is the only place the branch renders, and
    # `--out-dir _ai_exam_scratch/mobility_pinned` is where the number means
    # something.
    if args.out_dir:
        target = RunTarget.from_out_dir(args.out_dir, args.snapshot_id,
                                        label=f"out-dir:{args.out_dir}")
    else:
        target = RunTarget.from_schedule(args.data_root, args.run)
    ex = target.build_vocab()._ex

    tally: Counter = Counter()
    drivers_on_earlier_open: Counter = Counter()
    hits: list[tuple] = []
    placements = 0

    for row in ex._load_enriched_assignments():
        orders = row.get("work_orders") or []
        if not orders:
            continue
        placements += 1
        order, machine, seq = orders[0], row.get("machine"), row.get("op_seq")
        verdict = (ex.mobility_verdict(order, machine, seq) or {}).get("verdict")
        tally[verdict] += 1
        if verdict != mp.VERDICT_EARLIER_OPEN:
            continue
        # THE RECORD'S OWN ATTRIBUTION, read from the SAME PLACE the three
        # guarded W4 sites read it: `key_facts["chosen_driver"]`, which is
        # `_first_assignment_driver`. The first version of this script read
        # `row["driver"]` off the enriched assignment and got `(none)` for the
        # fenced world's ORD-EARLY op10 — a bar (e2) §5 quotes as recording
        # CAPACITY_BLOCKED. A zero produced by an instrument that cannot see the
        # value is not a zero, and this is that class caught on this session's
        # own rider.
        driver = str(ex._first_assignment_driver(order) or "").strip().upper()
        driver = driver or "(none)"
        drivers_on_earlier_open[driver] += 1
        if counterfactual_contradicts_driver(driver):
            hits.append((order, seq, machine, driver))

    print(f"board            : {target.label}")
    print(f"placements       : {placements}")
    print("verdict tally    :")
    for v, n in tally.most_common():
        print(f"    {str(v):16s} {n}")
    n_eo = tally.get(mp.VERDICT_EARLIER_OPEN, 0)
    print(f"\nEARLIER_OPEN placements                : {n_eo}")
    if drivers_on_earlier_open:
        print("  their drivers:")
        for d, n in drivers_on_earlier_open.most_common():
            print(f"    {d:24s} {n}")
    print(f"...carrying a CONSTRAINT_NAMING driver : {len(hits)}")
    for h in hits:
        print(f"    {h[0]} op{h[1]} on {h[2]} -> {h[3]}")
    print(f"\n(CONSTRAINT_NAMING_DRIVERS = {sorted(CONSTRAINT_NAMING_DRIVERS)})")
    print("\nVERDICT: " + (
        "ZERO — `mobility_lead_line`'s sentence is true everywhere it renders on "
        "this board. File the count, leave the tripwire standing."
        if not hits else
        f"{len(hits)} SITE(S) — plumb the driver into `_mobility_facts` and guard "
        "the site."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
