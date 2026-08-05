"""F1 — try a candidate widening of `product_behavior_disqualifiers` against the
whole committed claim corpus BEFORE it is written into the source.

Session 4A teaching-graft (e2). The (e) session's standard is that a widened
predicate re-earns its census; this script is how a candidate is priced first, so
that what lands in `claim_verifier.py` is a measured pattern rather than a
plausible one. Every NEW firing is printed in full for inspection — the number is
worthless without reading the sentences, since the whole question is whether each
is a genuine product claim wearing the general-knowledge label.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from census_precision import claim_lines  # noqa: E402
from mre.modules.claim_verifier import _PRODUCT_BEHAVIOR_RES  # noqa: E402

SWEEPS = ROOT / "tests" / "ai_exam" / "sweeps"
_GK_RE = re.compile(r"^general knowledge")

# --- the candidate -----------------------------------------------------------
#
# THE MEASURED CONSTRUCTION (M1): "...a small number of specific reasons THIS
# PRODUCT ACTUALLY COMPUTES...". The shipped pattern (a) misses it twice over:
# its verb list has no "computes", and it requires the verb to sit immediately
# after the noun, where this sentence has an adverb in between.
#
# So the candidate does two things and no more:
#   1. adds the verbs that assert a COMPUTATION we perform, and
#   2. allows ONE intervening word between the noun and the verb.
CANDIDATE = (
    r"\b(?:in|on|with|for|within)\s+th(?:is|e)\s+product\b"
    r"|\bth(?:is|e)\s+(?:product|system|engine|scheduler)\s+"
    r"(?:\w+\s+)?"
    r"(?:can|cannot|can't|does|doesn't|will|won't|only|never|always|"
    r"treats?|models?|supports?|comput\w+|calculat\w+|determin\w+|"
    r"decid\w+|enforc\w+|recogni[sz]\w+|consider\w+|distinguish\w+)\b"
    r"|\bwe\s+(?:only|never|always)\s+\w+\b"
)

SHIPPED = _PRODUCT_BEHAVIOR_RES[0][1]          # pattern (a), as it stands
CAND_RE = re.compile(CANDIDATE, re.IGNORECASE)

M1_SPECIMEN = (
    "A job becomes impossible to move for one of a small number of specific "
    "reasons this product actually computes, not just a lock: it can be "
    "explicitly frozen or pinned to a resource, it can be excluded from "
    "resources it would need, or it can be boxed in by its own precedence "
    "chain, release date, or calendar with no later opening long enough to "
    "hold it."
)


def main() -> int:
    paths = sorted(SWEEPS.rglob("*.txt"))
    seen: dict[str, str] = {}
    for text, label, _src in claim_lines(paths):
        seen.setdefault(text, label)
    gk = [t for t, lab in seen.items() if _GK_RE.match(lab)]

    print(f"corpus: {len(paths)} transcripts, {len(seen)} unique claim lines, "
          f"{len(gk)} of them general-knowledge\n")

    print("M1 specimen under the candidate: "
          + ("FIRES" if CAND_RE.search(M1_SPECIMEN) else "STILL MISSES")
          + f"   -> {(CAND_RE.search(M1_SPECIMEN) or [None]) and (CAND_RE.search(M1_SPECIMEN).group(0) if CAND_RE.search(M1_SPECIMEN) else '')!r}\n")

    before = [t for t in gk if SHIPPED.search(t)]
    after = [t for t in gk if CAND_RE.search(t)]
    new = [t for t in after if t not in set(before)]

    print(f"pattern (a) firings on GK claims: shipped {len(before)} "
          f"-> candidate {len(after)}   (new: {len(new)})\n")
    for t in new:
        m = CAND_RE.search(t)
        print(f"  NEW  matched {m.group(0)!r}")
        print(f"       {t}\n")

    # The other axis: does the candidate start firing on claims that are NOT
    # general knowledge? Those are not dropped by (i) — the check is gated on
    # `not cited` and on the GK path — but a pattern that fires all over the
    # board claims is a pattern about the wrong thing, and that is worth seeing.
    board = [t for t, lab in seen.items() if not _GK_RE.match(lab)]
    b_before = sum(1 for t in board if SHIPPED.search(t))
    b_after = sum(1 for t in board if CAND_RE.search(t))
    print(f"(context) firings on the {len(board)} NON-GK claim lines: "
          f"shipped {b_before} -> candidate {b_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
