"""(d.3) — R-TE1's TRIGGER CONTRACT, driven live. The scope wall's teeth.

Four arms, and every one of them is a way the route could become a documentation
browser if the contract were not enforced:

  A  CONFIRMED       the word was said on THIS board, and it is one of ours
                     -> term-explanation
  B  NEVER SAID      one of our words, but this conversation has not seen it
                     -> NOT confirmed; the question goes to the second tier
  C  NOT OURS        a word we do not define ("bottleneck"), even though it is
                     a perfectly good scheduling term
                     -> NOT confirmed
  D  AFTER A REBIND  the word was said on the PREVIOUS board. R-MT1's key means
                     the memory does not follow the planner across a version
                     change, and "you said seed" would be citing a conversation
                     about a different plan
                     -> NOT confirmed

Plus the two TRUE NEGATIVES the fix must not have eaten: a genuine entity
ambiguity must still CLARIFY, and a genuine capability question must still
COACH. Those two seams are where the founder's specimens were wrongly caught,
and a fix that empties them has traded one wrong answer for another.

    python tools/spikes/teaching_graft_d3/trigger_contract.py

Read-only against the two pinned boards. Mints nothing.
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
from mre.modules import interpreter as interp  # noqa: E402

DEMO = "rolling-c32a6140-b6b"
EXAM = "rolling-e9ccc879-a4b"
OPENER = "is this the cheapest possible plan"

rows: list[dict] = []


def show(label: str, t, *, want: str) -> None:
    got = t.route
    ok = (got == "term-explanation") if want == "confirm" else (
        got != "term-explanation")
    rows.append({"arm": label, "question": t.question, "route": got,
                 "intent": t.intent, "want": want, "ok": ok,
                 "first_line": (t.text or "").strip().splitlines()[:1]})
    mark = "OK " if ok else "!! "
    print(f"  {mark}{label:34s} route={got:20s} intent={t.intent}")
    body = (t.text or "").strip().splitlines()
    print(f"      A: {(body[0] if body else '')[:120]}")


def main() -> int:
    demo = RunTarget.from_schedule(str(ROOT / "_data"), DEMO)
    exam = RunTarget.from_schedule(str(ROOT / "_data"), EXAM)
    parser = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())

    print("=== R-TE1 TRIGGER CONTRACT " + "=" * 40)

    # A — CONFIRMED
    c = Conversation("d3-tc-a", demo, parser, synth)
    c.reset()
    c.ask(OPENER)
    show("A confirmed (said here)", c.ask("what do you mean seed"),
         want="confirm")

    # B — one of OUR words, never said in this conversation
    c = Conversation("d3-tc-b", demo, parser, synth)
    c.reset()
    show("B never said in this convo", c.ask("what do you mean seed"),
         want="refuse")

    # C — a word we do not define at all
    c = Conversation("d3-tc-c", demo, parser, synth)
    c.reset()
    c.ask(OPENER)
    show("C not one of our words", c.ask("what do you mean bottleneck"),
         want="refuse")

    # D — said on the PREVIOUS board, then a rebind
    c = Conversation("d3-tc-d", demo, parser, synth)
    c.reset()
    c.ask(OPENER)
    seen_before = interp.TERM_MEMORY.seen("d3-tc-d", DEMO)
    c.rebind(exam)                       # main.js::onVersionChange
    seen_after = interp.TERM_MEMORY.seen("d3-tc-d", EXAM)
    print(f"  ... term memory on {DEMO[-3:]}: {sorted(seen_before)}"
          f"   on {EXAM[-3:]} after rebind: {sorted(seen_after)}")
    show("D after a version rebind", c.ask("what do you mean seed"),
         want="refuse")

    print("\n=== THE TWO TRUE NEGATIVES " + "=" * 40)

    # The entity clarify must still clarify.
    c = Conversation("d3-tn-1", demo, parser, synth)
    c.reset()
    t = c.ask("why cant this be moved earlier")
    rows.append({"arm": "TN entity clarify", "question": t.question,
                 "route": t.route, "intent": t.intent, "want": "CLARIFY",
                 "ok": t.route == "CLARIFY",
                 "first_line": (t.text or "").strip().splitlines()[:1]})
    print(f"  {'OK ' if t.route == 'CLARIFY' else '!! '}entity clarify"
          f"{'':21s}route={t.route}")

    # The capability coach must still coach.
    c = Conversation("d3-tn-2", demo, parser, synth)
    c.reset()
    t = c.ask("how do i turn on overtime")
    ok = t.route == "coaching"
    rows.append({"arm": "TN capability coach", "question": t.question,
                 "route": t.route, "intent": t.intent, "want": "coaching",
                 "ok": ok, "first_line": (t.text or "").strip().splitlines()[:1]})
    print(f"  {'OK ' if ok else '!! '}capability coach{'':19s}route={t.route}")
    print(f"      A: {((t.text or '').strip().splitlines() or [''])[0][:120]}")

    d = Path(__file__).parent / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trigger_contract.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [r["arm"] for r in rows if not r["ok"]]
    print(f"\nartifact -> {d / 'trigger_contract.json'}")
    print("VERDICT: " + ("ALL ARMS HOLD" if not bad else f"FAILED: {bad}"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
