"""Session 4A teaching-graft (d.2) — PART B rung 3, and PART C's clarify-carry.

Two probes, one run, because both are about the same channel.

**L3b — the LAST-ANSWER rung, correctly constructed.** `ladder_probe.py`'s L3
used `when does ORD-000252 finish`, which answers with `subject_type="schedule"`
— NOT one of the five `resolved_subject` carries — so the rung stayed empty and
the follow-up landed on CLARIFY. A code census of `explainer.py` finds all five
carried literals ARE emitted, by six routes: `late-order` and `why-on-machine`
(demand), `order-attributes`, `start-reason`, contested (contested_fact) and
`machine-idle`. L3b drives one of them, so the rung's reachability is settled by
observation rather than by reading.

**PART C — the founder's clarify-carry specimen.** From the freewheel round:

    "why is ORD-000252 on CUT-01 when it is"   -> facts-vs-action CLARIFY
    (a turn naming a typo'd form of the same order)
    "why is it scheduled when it is"           -> asked WHICH ORDER

Hypothesis to TEST, not assume: subjects named in a question that ROUTES TO
CLARIFY never enter carry — the clarify turn eats them. The probe prints what
each turn's carry channels actually hold, so the answer comes from the artifact.

Run: python tools/spikes/teaching_graft_d2/carry_probe.py [--out DIR]
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
ORDER = "ORD-000252"
MACHINE = "CUT-01"


def _dump(label: str, conv: Conversation) -> dict:
    print(f"\n=== {label} " + "=" * max(0, 66 - len(label)))
    for t in conv.turns:
        print(f"  T{t.n}: {t.question!r}")
        print(f"      CARRY IN  selection={t.sent_selection}  "
              f"last_answered={t.sent_last_answered}")
        print("      CARRY IN  history=" + json.dumps(
            [{k: h.get(k) for k in ("question", "route", "order", "machine")}
             for h in t.sent_history], ensure_ascii=False))
        print(f"      route={t.route}  intent={t.intent}  "
              f"subject_type={t.subject_type!r}  subject_name={t.subject_name!r}")
        print(f"      note={t.resolution_note!r}")
        for s in t.subjects:
            print(f"      subject: {s['kind']}={s['ref']}<-{s['source']} "
                  f"(raw={s['raw']!r} pointed={s['pointed']})")
        body = (t.text or "").strip().splitlines()
        print(f"      A: {body[0][:150] if body else '(empty)'}")
    return {"label": label,
            "turns": [{"n": t.n, "question": t.question, "route": t.route,
                       "intent": t.intent, "subject_type": t.subject_type,
                       "subject_name": t.subject_name,
                       "resolution_note": t.resolution_note,
                       "subjects": t.subjects,
                       "sent_selection": t.sent_selection,
                       "sent_last_answered": t.sent_last_answered,
                       "sent_history": t.sent_history,
                       "text": t.text}
                      for t in conv.turns]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).parent / "artifacts"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    target = RunTarget.from_schedule(DATA_ROOT, DEMO)
    parser = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())
    results = []

    # --- L3b: the LAST-ANSWER rung, via a route that DOES carry -----------
    c = Conversation("d2-l3b", target, parser, synth)
    c.reset()
    c.ask(f"why is {ORDER} late")
    c.ask("why cant this be moved earlier")
    results.append(_dump("L3b LAST-ANSWER (late-order -> demand)", c))

    # --- PART C: the founder's clarify-carry sequence ---------------------
    c = Conversation("d2-partc", target, parser, synth)
    c.reset()
    c.ask(f"why is {ORDER} on {MACHINE} when it is")
    c.ask("is ord 252 late")
    c.ask("why is it scheduled when it is")
    results.append(_dump("PART C founder sequence", c))

    # --- PART C control: the SAME third question with NO clarify in front -
    # If the clarify turn is what eats the subject, this arm resolves and the
    # founder's arm does not. If BOTH fail, the clarify is not the cause.
    c = Conversation("d2-partc-control", target, parser, synth)
    c.reset()
    c.ask(f"why is {ORDER} on {MACHINE}")
    c.ask("is ord 252 late")
    c.ask("why is it scheduled when it is")
    results.append(_dump("PART C control (no clarify in front)", c))

    (out / "carry.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nartifact -> {out / 'carry.json'}")

    print("\n--- SUMMARY " + "-" * 60)
    for r in results:
        last = r["turns"][-1]
        srcs = sorted({s["source"] for s in last["subjects"]}) or ["(none)"]
        refs = sorted({str(s["ref"]) for s in last["subjects"]}) or ["(none)"]
        print(f"  {r['label']:42s} final: route={last['route']:12s} "
              f"src={','.join(srcs)} ref={','.join(refs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
