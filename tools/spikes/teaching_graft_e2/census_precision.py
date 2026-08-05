"""The two precision censuses of session (e), re-run — and re-runnable.

Session 4A teaching-graft (e2), F1's standard: **a widened predicate re-earns its
census, it does not inherit one.** Session (e) measured

  * `product_behavior_disqualifiers` firing on **2 of 99** unique
    general-knowledge claims, and
  * `floor_contradictions` firing on **0 of 485** unique claim lines,

and the scripts that produced those numbers were scratch. This is the standing
version. It reads the committed sweep TRANSCRIPTS, which is where a claim's text
and its LABEL live together (the sidecar carries only counts), and it reports the
same two numbers so that a change to either predicate can be priced.

    python tools/spikes/teaching_graft_e2/census_precision.py [--include-new]

`--include-new` adds this session's own sweep directory, which is what F1's
re-census must use: extending the corpus with the transcripts that motivated the
widening is the only way the number means anything.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from mre.contracts.synthesis import ClaimKind, DraftClaim  # noqa: E402
from mre.modules.claim_verifier import (  # noqa: E402
    floor_contradictions,
    product_behavior_disqualifiers,
)

SWEEPS = ROOT / "tests" / "ai_exam" / "sweeps"
#: This session's own directory — excluded by default so the BASELINE number is
#: reproducible against the committed corpus alone.
NEW_DIR = "2026-08-05-teaching-e2"

#: A rendered claim carries its class in a trailing bracket. These are the three
#: the synthesis surface emits (R-TG1 gave the first its own marker).
_LABEL_RE = re.compile(
    r"\s*\[(general knowledge[^\]]*|synthesis\s+—[^\]]*|record:[^\]]*)\]\s*$")
_GK_RE = re.compile(r"^general knowledge")
#: The once-per-answer FOOTER note explaining the label is not itself a claim.
_FOOTER = "Where a line is marked general knowledge it draws on"


def claim_lines(paths: list[Path]) -> list[tuple[str, str, str]]:
    """(text, label, source) for every labelled claim line in these transcripts."""
    out: list[tuple[str, str, str]] = []
    for p in paths:
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in body.splitlines():
            line = raw.strip()
            m = _LABEL_RE.search(line)
            if not m or _FOOTER in line:
                continue
            text = _LABEL_RE.sub("", line).strip()
            if text:
                out.append((text, m.group(1), p.name))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--include-new", action="store_true",
                    help=f"also read {NEW_DIR} (F1's re-census)")
    ap.add_argument("--show", action="store_true", help="print every firing")
    args = ap.parse_args()

    paths = sorted(p for p in SWEEPS.rglob("*.txt")
                   if args.include_new or p.parent.name != NEW_DIR)
    rows = claim_lines(paths)

    # UNIQUE BY TEXT. The same sentence rendered in two sweep runs is one claim
    # for precision purposes; counting it twice would let a repeated true
    # negative flatter the number.
    seen: dict[str, tuple[str, str]] = {}
    for text, label, src in rows:
        seen.setdefault(text, (label, src))

    gk = {t: v for t, v in seen.items() if _GK_RE.match(v[0])}

    print(f"corpus            : {len(paths)} transcript(s)"
          + ("  [including this session's]" if args.include_new else ""))
    print(f"claim lines       : {len(rows)} rendered, {len(seen)} unique")
    print(f"  of which GK     : {len(gk)} unique\n")

    pb_hits = []
    for text in gk:
        claim = DraftClaim(text=text, record_ids=[],
                           kind=ClaimKind.GENERAL_KNOWLEDGE)
        why = product_behavior_disqualifiers(claim)
        if why:
            pb_hits.append((text, why))

    fc_hits = []
    for text in seen:
        claim = DraftClaim(text=text, record_ids=[], kind=ClaimKind.FACT)
        if floor_contradictions(claim):
            fc_hits.append(text)

    print(f"product_behavior_disqualifiers : {len(pb_hits)} of {len(gk)} GK claims")
    for text, why in pb_hits:
        print(f"    - {text[:150]}")
        print(f"      why: {why}")
    print(f"\nfloor_contradictions           : {len(fc_hits)} of {len(seen)} "
          f"claim lines")
    for text in fc_hits:
        print(f"    - {text[:150]}")
    if args.show and not (pb_hits or fc_hits):
        print("    (no firings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
