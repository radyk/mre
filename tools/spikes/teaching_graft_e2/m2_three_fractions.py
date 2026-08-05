"""M2 — the three counts the brief asks for, over a sweep's own artifacts.

Session 4A teaching-graft (e2). Beside the family scores, M2 must state three
things as fractions of the TEACHING answers swept:

  (i)   empty-collapse — a teaching-intent question whose every claim was cut,
        so the answer fell to the unanswerable floor. This is (e) §8(b)'s
        failure mode, and F2 is the floor built under it.
  (ii)  product-naming sentences shipped under the general-knowledge label —
        M1's species, at sweep scale.
  (iii) `SYNTHESIS_FLOOR_REFUTED` cut-line occurrences — R-TG6's own cut kind,
        rendered.

A teaching answer is identified from the PARSE INTENT the transcript records,
never from the question's wording: what makes a turn a teaching turn is what the
parse decided, and re-deciding it here would be a second classifier disagreeing
with the first. (The sidecar carries aggregate counts only, which is why the
transcript is the source.)
"""
from __future__ import annotations

import argparse

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from census_precision import claim_lines  # noqa: E402
from mre.contracts.synthesis import ClaimKind, DraftClaim  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    SYNTHESIS_FLOOR_REFUTED, SYNTHESIS_UNANSWERABLE,
    SYNTHESIS_UNANSWERABLE_NO_TOOLS,
)
from mre.modules.claim_verifier import product_behavior_disqualifiers  # noqa: E402

_GK_RE = re.compile(r"^general knowledge")
#: The first sentence of each floor card, which is what a transcript shows.
_FLOOR_HEAD = SYNTHESIS_FLOOR_REFUTED.split("—")[0].strip()[:60]
_EMPTY_HEADS = tuple(
    s.split(".")[0].strip()[:50]
    for s in (SYNTHESIS_UNANSWERABLE, SYNTHESIS_UNANSWERABLE_NO_TOOLS))


_Q_RE = re.compile(r"(?m)^Q\[\d+\]:")
_INTENT_RE = re.compile(r"^\s*parse:\s*intent=(\S+)", re.MULTILINE)


def _turn_blocks(transcript: str) -> list[str]:
    """Split a transcript into per-question blocks. The runner writes one
    `Q[<n>]:` header per turn; splitting on it keeps every rendered line with
    the question that produced it, which is what makes a per-turn count
    possible at all."""
    idx = [m.start() for m in _Q_RE.finditer(transcript)]
    return [transcript[a:b] for a, b in zip(idx, idx[1:] + [len(transcript)])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sweep_dir", help="a sweep output directory")
    args = ap.parse_args()
    d = Path(args.sweep_dir)

    transcripts = sorted(d.glob("*.txt"))

    # --- teaching turns, from the PARSE the transcript records ---------------
    # The sidecar carries aggregate counts only, so the per-turn intent is read
    # off the transcript's own `parse: intent=` line. That is the parse model's
    # decision, quoted — not a second classifier re-deciding it here.
    blocks: list[tuple[str, str]] = []
    for p in transcripts:
        body = p.read_text(encoding="utf-8", errors="replace")
        for b in _turn_blocks(body):
            m = _INTENT_RE.search(b)
            blocks.append((m.group(1) if m else "", b))
    teaching_blocks = [b for intent, b in blocks if intent == "teaching"]
    teaching = len(teaching_blocks)

    # --- (ii) product-naming GK sentences -----------------------------------
    rows = claim_lines(transcripts)
    gk = [(t, s) for t, lab, s in rows if _GK_RE.match(lab)]
    pb = [(t, product_behavior_disqualifiers(
        DraftClaim(text=t, record_ids=[], kind=ClaimKind.GENERAL_KNOWLEDGE)))
        for t, _s in gk]
    pb_hits = [(t, why) for t, why in pb if why]

    # --- (i) and (iii), read off the rendered TEACHING turns ----------------
    # Both are counted on teaching turns only, because both fractions are
    # stated per teaching answer and an empty collapse on some other route is a
    # different fact with a different owner.
    empty = sum(1 for b in teaching_blocks
                if any(h and h in b for h in _EMPTY_HEADS))
    refuted = sum(1 for b in teaching_blocks if _FLOOR_HEAD and _FLOOR_HEAD in b)

    print(f"sweep dir        : {d}")
    print(f"transcripts      : {[p.name for p in transcripts]}")
    print(f"TEACHING answers : {teaching}  (parse intent, not wording)")
    print(f"GK claim lines   : {len(gk)}\n")
    print(f"(i)   empty-collapse turns              : {empty} / {teaching} teaching")
    print(f"(ii)  product-naming GK sentences       : {len(pb_hits)} / {len(gk)} GK "
          f"claims  ({len(pb_hits)} / {teaching} teaching)")
    for t, why in pb_hits:
        print(f"        - {t[:160]}")
        print(f"          why: {why}")
    print(f"(iii) SYNTHESIS_FLOOR_REFUTED rendered  : {refuted} / {teaching} teaching")
    return 0


if __name__ == "__main__":
    sys.exit(main())
