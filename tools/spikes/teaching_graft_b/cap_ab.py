"""DID THE PROMPT DO IT, OR DID THE SEAM? A controlled A/B (R-TG3).

Session 4A teaching-graft (b). The v2 sweep and the live probe set produced
`deferred=0` across every short-budget answer — the cap never bound. Two
explanations, and they are not the same fact:

  (A) synthesis prompt v7's "four claims is the budget, write the four that
      matter first" is being FOLLOWED, so the seam has nothing to trim; or
  (B) the seam is not wired, or the tier never drafted five claims anyway.

(B) is refuted by guard and by negative control. (A) is a claim about a model's
behaviour and can only be settled by measurement, so this measures it: the SAME
probes, twice, with rule 6 SWAPPED BACK to its v6 text ("between three and six
claims is usually right") and nothing else changed.

WHAT IT PROVES EITHER WAY. If the v6 arm defers and the v7 arm does not, the
prompt is doing the work and the seam is the FLOOR UNDER IT — which is the
architecture R-TG3 asks for, and the v6 arm is the live closer specimen. If
NEITHER arm defers, the honest report is that the cap has no live specimen at
all, and the report says so.

THE PROMPT IS RESTORED IN A `finally` AND THE RESTORE IS ASSERTED BYTE-IDENTICAL
by sha256 — this edits a GOVERNED ARTIFACT, and a spike that left one modified
would be worse than any measurement it produced.

Usage:  python tools/spikes/teaching_graft_b/cap_ab.py [schedule_id]
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    SYNTHESIS_DEFERRED, SYNTHESIS_DEFERRED_ONE,
)
from mre.modules.interpreter import forget_deliveries, run_ask  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
PROMPT = ROOT / "src" / "mre" / "modules" / "synthesis_prompt.md"

_V6_RULE6 = (
    "6. THE PLANNER'S LANGUAGE. Order and machine ids as this run spells them, "
    "minutes\n   and hours and dates, no uuids in the prose, no module names, no "
    "record ids in\n   the sentence itself (they go in `record_ids`). Short "
    "sentences. Between three\n   and six claims is usually right; one is thin "
    "and ten is a report.\n")

PROBES = [
    "compare how the cutting machines and the press are loaded and what that "
    "means for the late orders",
    "give me a full picture of where the money is going in this plan",
    "why might tardiness cluster on bottleneck machines",
    "what would you say is going wrong with this plan and why",
]


def _swap_rule6(raw: bytes) -> bytes:
    """Rule 6 -> its v6 text, newline-agnostically.

    The file is CRLF and the anchors here are LF; normalising first and
    re-encoding with the file's own ending is the same discipline the negative
    controls' `_match_eol` keeps, and for the same measured reason."""
    text = raw.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    flat = text.replace("\r\n", "\n")
    start = flat.index("\n6. THE PLANNER'S LANGUAGE") + 1
    end = flat.index("\n7. YOU DO NOT CHANGE THE PLAN", start) + 1
    swapped = flat[:start] + _V6_RULE6 + "\n" + flat[end:]
    return swapped.replace("\n", eol).encode("utf-8")


def _run_arm(label: str, target, parser, renderer) -> list[dict]:
    from mre.modules.synthesizer import Synthesizer
    explainer = target.build_vocab()._ex
    synth = Synthesizer()                      # re-loads the prompt from disk
    print(f"\n{'#' * 78}\n# ARM {label} — synthesis prompt v{synth.prompt_version}"
          f"\n{'#' * 78}")
    rows = []
    for q in PROBES:
        forget_deliveries("ab")
        r = run_ask(explainer, q, parser=parser, synthesizer=synth,
                    document=target.document, session_id="ab")
        s = r.synthesis
        if s is None:
            print(f"  [{label}] {q[:55]!r} -> {r.route} (no synthesis)")
            continue
        c = s.counts()
        text = renderer.render(r.bundle)
        closer = (SYNTHESIS_DEFERRED_ONE in text
                  or SYNTHESIS_DEFERRED.split("{")[0] in text)
        rows.append({"arm": label, "q": q, **c, "closer": closer, "text": text})
        print(f"  [{label}] kept={len(s.claims)} cut={c['failed_and_cut']} "
              f"DEFERRED={c['deferred']} closer={closer}  {q[:48]!r}")
        if c["deferred"]:
            print("    " + "\n    ".join(
                ln for ln in text.splitlines()
                if SYNTHESIS_DEFERRED.split("{")[0] in ln))
    return rows


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    parser, renderer = QuestionParser(), TemplateRenderer()
    if not parser.available:
        print("PARSER UNAVAILABLE — nothing measured.")
        return 2

    original = PROMPT.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    rows = _run_arm("v7 (shipped)", target, parser, renderer)

    try:
        PROMPT.write_bytes(_swap_rule6(original))
        rows += _run_arm("v6 (control)", target, parser, renderer)
    finally:
        PROMPT.write_bytes(original)
    after = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    assert after == before, f"RESTORE IS NOT BYTE-IDENTICAL ({before} -> {after})"

    print(f"\n{'=' * 78}\nSUMMARY (restore byte-identical: {after == before})")
    for arm in ("v7 (shipped)", "v6 (control)"):
        got = [r for r in rows if r["arm"] == arm]
        if not got:
            continue
        print(f"  {arm:<14} n={len(got)}  "
              f"kept={[r['claims'] - r['failed_and_cut'] - r['deferred'] for r in got]}  "
              f"deferred={[r['deferred'] for r in got]}  "
              f"closers={sum(1 for r in got if r['closer'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
