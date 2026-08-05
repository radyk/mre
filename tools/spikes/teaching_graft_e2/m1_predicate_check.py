"""M1 — did `product_behavior_disqualifiers` evaluate the (e) run-1 first claim,
and why did it not fire?

Session 4A teaching-graft (e2), measurement M1. Deterministic; reads no board and
calls no model. The claim TEXT is quoted verbatim from
`docs/closeouts/4a-teaching-e-floor-truth.md` §4 (the run-1 block), which is the
surviving record of that run — the live JSON artifact was scratch and did not
outlive the session.

The verdict this script produces is one of the brief's two:
  (a) cited, the quote merely omitted the citation  -> no defect
  (b) uncited AND the predicate does not match this construction -> defect
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from mre.contracts.synthesis import ClaimKind, DraftClaim  # noqa: E402
from mre.modules.claim_verifier import (  # noqa: E402
    _PRODUCT_BEHAVIOR_RES,
    floor_contradictions,
    product_behavior_disqualifiers,
)

# The (e) close-out §4, run 1, FIRST claim. It rendered under `[general
# knowledge]`; the second claim of the same answer rendered under
# `[record: 6af3d3e4...]`, so the label is not an artifact of the quotation.
RUN1_CLAIM_1 = (
    "A job becomes impossible to move for one of a small number of specific "
    "reasons this product actually computes, not just a lock: it can be "
    "explicitly frozen or pinned to a resource, it can be excluded from "
    "resources it would need, or it can be boxed in by its own precedence "
    "chain, release date, or calendar with no later opening long enough to "
    "hold it."
)

# The same answer's SECOND claim, for the contrast: it is a board claim, cited.
RUN1_CLAIM_2 = (
    "ORD-BOX shows the boxed-in shape directly: its FEED-01 operation ends at "
    "2026-01-13 09:52 and its BOX-01 operation starts the same minute, with "
    "zero gap between them - a chain like this has no slack to move into even "
    "though neither operation carries a lock."
)

# The founding DEFECT sentence, as the positive control: the predicate must
# still fire on it after any widening.
FOUNDING_SPECIMEN = (
    "In this product, a job becomes immovable only through a "
    "frozen_assignment or pinned constraint declared in locks.csv, and "
    "nothing else in the catalog removes an operation's mobility outright."
)


def _report(label: str, text: str, record_ids: list[str]) -> None:
    claim = DraftClaim(text=text, record_ids=record_ids,
                       kind=ClaimKind.GENERAL_KNOWLEDGE)
    fired = product_behavior_disqualifiers(claim)
    print(f"\n=== {label} ===")
    print(f"  cited            : {bool([r for r in record_ids if r])}")
    print(f"  product_behavior : {fired or 'DID NOT FIRE'}")
    print(f"  floor_contradict : {floor_contradictions(claim) or '[]'}")
    print("  per-pattern:")
    for why, rx in _PRODUCT_BEHAVIOR_RES:
        m = rx.search(text)
        print(f"    {'HIT ' if m else 'miss'}  {why}"
              + (f"   -> {m.group(0)!r}" if m else ""))


def main() -> int:
    print(__doc__.splitlines()[0])
    # The label the claim rendered under is the citation evidence: a claim
    # carrying record_ids is disqualified from the general-knowledge class by
    # `gk_disqualifiers`' FIRST clause ("it cites this run's records"), so a
    # sentence that shipped as `[general knowledge]` cannot have been cited.
    _report("run 1, claim 1 -- shipped as [general knowledge], so UNCITED",
            RUN1_CLAIM_1, [])
    _report("run 1, claim 2 -- shipped as [record: 6af3d3e4...], CITED",
            RUN1_CLAIM_2, ["6af3d3e4"])
    _report("founding specimen (positive control)", FOUNDING_SPECIMEN, [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
