"""(d.3) C2 — THE TWO WRONG DOORS, located.

The founding specimen (founder freewheel round, 2026-08-04, demo board): the
cost-optimum answer — a CONTRACTED route — said "seed" nine times, and then

  T1  "what do you mean seed"
      -> entity CLARIFY  ("Name it — an order, a machine, or a capability...")
  T2  "you mentioned seed 44 is the cheapest seed but what does it mean to
       change seeds"
      -> capability coach ("I don't recognize which capability you mean...")

Two refusals, each holding a door handle that opens on the wrong room.

This reproduces both, in a conversation whose FIRST turn actually emits the word
(that matters — the planner was asking about a term the product's own last
answer introduced), and prints for each turn: the parse's proposed intent, its
subjects, the clarify reason if any, and the route the dispatch chose. That is
"which route matched, on what, and what the parse proposed."

`--sweep` additionally fires a BATTERY of term questions across phrasings and
terms, which is the no-third-seam evidence: every phrasing must land on one of
the seams this session fixes, or there is a door nobody has looked at.

    python tools/spikes/teaching_graft_d3/c2_wrong_doors.py [--sweep]

Read-only against the pinned demo board. Mints nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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

#: The turn that makes the word the PRODUCT's. Measured in C1: the R-BK1
#: portfolio answer is where "seed" reaches a planner at all (30 uses, 5
#: answers, and this is the question that produces them).
OPENER = "is this the cheapest possible plan"

T1 = "what do you mean seed"
T2 = ("you mentioned seed 44 is the cheapest seed but what does it mean to "
      "change seeds")

#: The no-third-seam battery. Phrasings x terms the C1 census proved emitted.
PHRASINGS = [
    "what do you mean {t}",
    "what is a {t}",
    "what does {t} mean",
    "i don't know what {t} means",
    "explain {t}",
]
TERMS = ["seed", "gap", "ledger", "frozen", "the driver"]


def _row(t) -> dict:
    return {
        "question": t.question,
        "route": t.route,
        "intent": t.intent,
        "register": t.register,
        "subject_type": t.subject_type,
        "subject_name": t.subject_name,
        "subjects": t.subjects,
        "note": t.resolution_note,
        "first_line": (t.text or "").strip().splitlines()[:1],
    }


def _print(t) -> None:
    print(f"  Q: {t.question!r}")
    print(f"     PARSE proposed intent={t.intent!r}  "
          f"subjects={[(s['kind'], s['ref'], s['raw']) for s in t.subjects]}")
    print(f"     DISPATCH route={t.route!r}  register={t.register!r}  "
          f"subject_type={t.subject_type!r}")
    body = (t.text or "").strip().splitlines()
    print(f"     A: {(body[0] if body else '')[:150]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sweep", action="store_true",
                    help="fire the no-third-seam battery too")
    args = ap.parse_args()

    target = RunTarget.from_schedule(str(ROOT / "_data"), DEMO)
    parser = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())
    out: dict = {}

    print("=== THE FOUNDING SPECIMEN, reproduced " + "=" * 30)
    c = Conversation("d3-c2-founder", target, parser, synth)
    c.reset()
    t0 = c.ask(OPENER)
    emitted = "seed" in (t0.text or "").lower()
    print(f"  T0 {OPENER!r}  route={t0.route}  "
          f"EMITS 'seed': {emitted}")
    for line in (t0.text or "").strip().splitlines()[:4]:
        print(f"     {line[:150]}")
    for q in (T1, T2):
        _print(c.ask(q))
    out["founder"] = {"opener_emits_seed": emitted,
                      "turns": [_row(t) for t in c.turns]}

    if args.sweep:
        print("\n=== THE NO-THIRD-SEAM BATTERY " + "=" * 37)
        rows = []
        seams: Counter = Counter()
        for term in TERMS:
            for pat in PHRASINGS:
                q = pat.format(t=term)
                c = Conversation(f"d3-c2-{abs(hash(q)) % 9999}", target,
                                 parser, synth)
                c.reset()
                c.ask(OPENER)          # the term is now the PRODUCT's
                t = c.ask(q)
                rows.append({"term": term, **_row(t)})
                seams[f"{t.route} / {t.intent}"] += 1
                print(f"  {term:12s} {pat.format(t='<t>'):28s} -> "
                      f"route={t.route:22s} intent={t.intent}")
        out["battery"] = rows
        print("\n  SEAMS REACHED:")
        for k, n in seams.most_common():
            print(f"    {n:3d}  {k}")

    d = Path(__file__).parent / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "c2_wrong_doors.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nartifact -> {d / 'c2_wrong_doors.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
