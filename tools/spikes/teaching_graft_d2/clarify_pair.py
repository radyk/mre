"""Session 4A teaching-graft (d.2) PART C — the MINIMAL clarify-carry pair.

`carry_probe.py`'s three-turn reproduction of the founder's specimen did NOT
reproduce: turn 2 (`is ord 252 late`) named the order again and answered on
`late-order`, whose `subject_type` is `demand` — one of the five the carry
channel accepts — so turn 3 resolved cleanly off the LAST-ANSWER rung. The
intervening turn re-supplied what turn 1 had dropped, which is why the founder's
specimen needed a turn 2 that does NOT carry.

So the question is isolated to TWO turns, and asked as a PAIR with one variable:

  ARM A  T1 "why is ORD-000252 on CUT-01 WHEN IT IS"  -> facts-vs-action CLARIFY
  ARM B  T1 "why is ORD-000252 on CUT-01"             -> why-on-machine (carries)
  both   T2 "why is it scheduled when it is"

Everything else is held: same order, same machine, same board, no selection, no
card, conversation cleared between arms. If A loses the subject and B keeps it,
the clarify route is what ate it.

`--repeat N` runs the pair N times — the parse tier varies run to run (the (d.0)
dossier's §6.2), so a single arm is a specimen and not a rate.

Run: python tools/spikes/teaching_graft_d2/clarify_pair.py [--repeat 3]
"""
from __future__ import annotations

import argparse
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
DATA_ROOT = str(ROOT / "_data")
ORDER, MACHINE = "ORD-000252", "CUT-01"
FOLLOWUP = "why is it scheduled when it is"

ARMS = {
    "A_clarify": f"why is {ORDER} on {MACHINE} when it is",
    "B_control": f"why is {ORDER} on {MACHINE}",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default=str(Path(__file__).parent / "artifacts"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    target = RunTarget.from_schedule(DATA_ROOT, DEMO)
    parser = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())
    rows = []

    for run in range(1, args.repeat + 1):
        for arm, opener in ARMS.items():
            c = Conversation(f"d2-pair-{arm}-{run}", target, parser, synth)
            c.reset()
            t1 = c.ask(opener)
            t2 = c.ask(FOLLOWUP)
            row = {
                "run": run, "arm": arm,
                "t1_question": opener, "t1_route": t1.route,
                "t1_parse_bound": [s["ref"] for s in t1.subjects
                                   if s["kind"] == "order"],
                "t1_subject_type": t1.subject_type,
                "t1_subject_name": t1.subject_name,
                "carry_into_t2": dict(t2.sent_last_answered),
                "t2_route": t2.route, "t2_intent": t2.intent,
                "t2_subjects": t2.subjects,
                "t2_note": t2.resolution_note,
                "t2_first_line": (t2.text or "").strip().splitlines()[:1],
            }
            rows.append(row)
            print(f"\n[run {run}] {arm}")
            print(f"  T1 {opener!r}")
            print(f"     route={t1.route}  subject_type={t1.subject_type!r}  "
                  f"subject_name={t1.subject_name!r}")
            print(f"     PARSE BOUND order(s): {row['t1_parse_bound']}")
            print(f"  carry into T2: last_answered={row['carry_into_t2']}")
            print(f"  T2 {FOLLOWUP!r}")
            print(f"     route={t2.route}  note={t2.resolution_note!r}")
            for s in t2.subjects:
                print(f"     subject: {s['kind']}={s['ref']}<-{s['source']} "
                      f"(raw={s['raw']!r} pointed={s['pointed']})")
            print(f"     A: {(row['t2_first_line'] or [''])[0][:140]}")

    (out / "clarify_pair.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nartifact -> {out / 'clarify_pair.json'}")

    print("\n--- PAIR SUMMARY " + "-" * 55)
    for r in rows:
        srcs = ",".join(sorted({s["source"] for s in r["t2_subjects"]})) or "-"
        refs = ",".join(sorted({str(s["ref"]) for s in r["t2_subjects"]})) or "-"
        print(f"  run{r['run']} {r['arm']:10s} T1 bound={r['t1_parse_bound']} "
              f"carry={r['carry_into_t2'] or '{}'}  ->  T2 route={r['t2_route']:14s}"
              f" src={srcs} ref={refs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
