"""(d.2) — the P2b live probe, re-run after Parts B and C.

R-LD5 must survive whatever the ladder session decides. P2b is the recon's
sharpest resolution specimen and the reason R-LD5 exists: *"why cant this be
moved earlier"* with NOTHING selected, in three positions.

  cold                                          -> CLARIFY, nothing bound
  after "why is ORD-000073 op10 placed where it is" -> a subject the PARSE
        recovered from the RECENT TURNS block, which used to report `utterance`
        and disclose NOTHING (D-02). R-LD5 made it `conversation` and disclosed.
  after "how many orders are late"              -> CLARIFY, nothing to bind

(d.2) TOUCHED THIS SEAM. R-LD6 clause (5) widened what enters the LAST-ANSWER
rung, so the middle arm may now resolve off the LADDER instead of off the model.
Either is correct and BOTH must disclose; what would be a regression is a
resolution with an EMPTY note, which is the defect R-LD5 closed.

Run: python tools/spikes/teaching_graft_d2/p2b_after.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "spikes" / "multiturn_recon"))

from mre.env_local import load_env_local  # noqa: E402

load_env_local()

from conv import Conversation, RecordingParser, RecordingSynthesizer  # noqa: E402

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.synthesizer import Synthesizer  # noqa: E402

DEMO = "rolling-c32a6140-b6b"
PROBE = "why cant this be moved earlier"
ARMS = {
    "cold": [],
    "after-mobility": ["why is ORD-000073 op10 placed where it is"],
    "after-unrelated": ["how many orders are late"],
}


def main() -> int:
    target = RunTarget.from_schedule(str(ROOT / "_data"), DEMO)
    parser = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())
    rows = []

    for arm, openers in ARMS.items():
        c = Conversation(f"d2-p2b-{arm}", target, parser, synth)
        c.reset()
        for q in openers:
            c.ask(q)
        t = c.ask(PROBE)
        row = {"arm": arm, "route": t.route, "note": t.resolution_note,
               "subjects": t.subjects,
               "carry_in": t.sent_last_answered}
        rows.append(row)
        print(f"\n[{arm}]  route={t.route}")
        print(f"  carry in : {t.sent_last_answered}")
        print(f"  note     : {t.resolution_note!r}")
        for s in t.subjects:
            print(f"  subject  : {s['kind']}={s['ref']}<-{s['source']} "
                  f"(raw={s['raw']!r} pointed={s['pointed']})")

    out = Path(__file__).parent / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "p2b_after.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n--- R-LD5's RULE: every resolution MADE is disclosed " + "-" * 20)
    bad = []
    for r in rows:
        bound = [s for s in r["subjects"] if s["ref"]]
        if bound and not (r["note"] or "").strip():
            bad.append(r["arm"])
        state = ("bound " + ",".join(str(s["ref"]) for s in bound)
                 if bound else "bound nothing")
        disc = "DISCLOSED" if (r["note"] or "").strip() else "no note"
        print(f"  {r['arm']:16s} {state:22s} {disc}")
    print("\nVERDICT: " + ("R-LD5 HOLDS" if not bad else
                           f"REGRESSION — undisclosed resolution in {bad}"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
