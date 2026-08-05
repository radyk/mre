"""THE NEXT-SESSION PREDICATE AUDIT — (e2)'s predicates over (e2)'s own sweeps.

Standing law, added by session 4A teaching-graft (d.2) and stated in that
session's brief §0: *a session that has just built a check is the worst-placed
observer of what the check does not catch* ((e2) §9). So every predicate or
pattern map built in session N gets an M1-style check in session N+1: run it
over the BUILDING session's own artifacts and state the result.

This session's instance. (e2) widened `product_behavior_disqualifiers` (R-TG6
(i)) and left `floor_contradictions` (R-TG6 (iii)) as it found it. Both are run
here over the transcripts (e2) itself minted — `2026-08-05-teaching-e2` — which
is the corpus (e2)'s own census included via `--include-new` but never reported
IN ISOLATION. In isolation is the point: a firing rate diluted across sixteen
sweep directories cannot tell you what the predicate did to the answers the
building session was looking at.

    python tools/spikes/teaching_graft_d2/predicate_audit.py [--show]

Reuses (e2)'s own extraction (`census_precision.claim_lines`) rather than
re-implementing it, so the ruler is the committed one and the numbers are
comparable to (e2) §5's table by construction.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "spikes" / "teaching_graft_e2"))

from census_precision import _GK_RE, claim_lines  # noqa: E402

from mre.contracts.synthesis import ClaimKind, DraftClaim  # noqa: E402
from mre.modules.claim_verifier import (  # noqa: E402
    floor_contradictions,
    product_behavior_disqualifiers,
)

E2_DIR = ROOT / "tests" / "ai_exam" / "sweeps" / "2026-08-05-teaching-e2"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", action="store_true",
                    help="print every GK claim, firing or not")
    args = ap.parse_args()

    paths = sorted(E2_DIR.rglob("*.txt"))
    rows = claim_lines(paths)
    seen: dict[str, tuple[str, str]] = {}
    for text, label, src in rows:
        seen.setdefault(text, (label, src))
    gk = {t: v for t, v in seen.items() if _GK_RE.match(v[0])}

    print(f"corpus            : {len(paths)} transcript(s) — (e2)'s OWN sweeps")
    for p in paths:
        print(f"    {p.name}")
    print(f"claim lines       : {len(rows)} rendered, {len(seen)} unique")
    print(f"  of which GK     : {len(gk)} unique\n")

    pb_hits = [(t, why) for t in gk
               if (why := product_behavior_disqualifiers(
                   DraftClaim(text=t, record_ids=[],
                              kind=ClaimKind.GENERAL_KNOWLEDGE)))]
    fc_hits = [t for t in seen
               if floor_contradictions(
                   DraftClaim(text=t, record_ids=[], kind=ClaimKind.FACT))]

    print(f"product_behavior_disqualifiers : {len(pb_hits)} of {len(gk)} GK claims")
    for text, why in pb_hits:
        print(f"    - {text[:170]}")
        print(f"      why: {why}")
    print(f"floor_contradictions           : {len(fc_hits)} of {len(seen)} claim lines")
    for text in fc_hits:
        print(f"    - {text[:170]}")

    if args.show:
        print("\n--- every GK claim in (e2)'s own sweeps ---")
        for i, (text, (label, src)) in enumerate(gk.items(), 1):
            fired = "FIRES" if product_behavior_disqualifiers(
                DraftClaim(text=text, record_ids=[],
                           kind=ClaimKind.GENERAL_KNOWLEDGE)) else "     "
            print(f"{i:3d} [{fired}] ({src}) {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
