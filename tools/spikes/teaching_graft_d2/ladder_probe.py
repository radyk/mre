"""Session 4A teaching-graft (d.2), PART B — the resolution ladder, measured.

The (d.0) recon measured all FOUR rungs (card > selection > last-answer >
history) EMPTY on all six turns of a typed conversation, and resolution worked
anyway. It left open (D-03/D-04) whether the ladder is dead code on the live
path or a mis-wired resolver. **The brief says MEASURE FIRST**, and this is the
measurement: for each rung, is there an input class that POPULATES it and a
consumer that READS it when populated?

Four conversations, one per rung, each constructed to make exactly that rung the
top non-empty one:

  L1 CARD        — a priced move is open; nothing else live.
  L2 SELECTION   — a bar is selected; no card.
  L3 LAST-ANSWER — a typed question whose answer's `subject_type` is one of the
                   five `resolved_subject` carries, then a pointed follow-up with
                   NOTHING selected.
  L4 HISTORY     — a bar selected for turn 1 (whose answer's subject_type is NOT
                   one of the five, so the last-answer rung stays empty), the
                   selection CLEARED, then a pointed follow-up.

The observable is `parsed.subjects[].source`: `card` / `selection` /
`last_answer` / `history` are the ladder; `conversation` is R-LD5's
model-recovered binding; `utterance` is the planner's own words.

Run: python tools/spikes/teaching_graft_d2/ladder_probe.py [--out DIR]
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

#: The founder's own specimen bar, and the one Part C uses too.
ORDER = "ORD-000252"
MACHINE = "CUT-01"
SEQ = 10


def _subject_rows(turn) -> list[str]:
    return [f"{s['kind']}={s['ref']}<-{s['source']}"
            f"(raw={s['raw']!r} pointed={s['pointed']})"
            for s in turn.subjects] or ["(no subjects)"]


def _dump(label: str, conv: Conversation) -> dict:
    print(f"\n=== {label} " + "=" * (66 - len(label)))
    for t in conv.turns:
        print(f"  T{t.n}: {t.question!r}")
        print(f"      sent selection={t.sent_selection}  "
              f"last_answered={t.sent_last_answered}  card={bool(conv.card)}")
        print(f"      sent history order/machine="
              f"{[(h.get('order'), h.get('machine')) for h in t.sent_history]}")
        print(f"      route={t.route}  intent={t.intent}  "
              f"subject_type={t.subject_type!r}  subject_name={t.subject_name!r}")
        print(f"      note={t.resolution_note!r}")
        for row in _subject_rows(t):
            print(f"      {row}")
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

    # --- L1: the CARD rung -------------------------------------------------
    c = Conversation("d2-ladder-l1", target, parser, synth)
    c.reset()
    c.card = {"open": True, "order": ORDER, "machine": MACHINE,
              "operation_ref": "probe-op", "outcome": "verdict",
              "feasible": True, "cost_delta_abs": 32.20,
              "move_delta_abs": 32.20, "reopt_delta_abs": 0.0,
              "when": "Jan 8, 08:23", "moves": 1}
    c.ask("why cant this be moved earlier")
    results.append(_dump("L1 CARD", c))

    # --- L2: the SELECTION rung -------------------------------------------
    c = Conversation("d2-ladder-l2", target, parser, synth)
    c.reset()
    c.ask("why cant this be moved earlier",
          select={"order": ORDER, "machine": MACHINE, "op_seq": SEQ})
    results.append(_dump("L2 SELECTION", c))

    # --- L3: the LAST-ANSWER rung -----------------------------------------
    # Turn 1 must produce a subject_type inside `_ORDER_SUBJECT_TYPES`
    # (demand / start_reason / contested_fact / order_attributes).
    c = Conversation("d2-ladder-l3", target, parser, synth)
    c.reset()
    c.ask(f"when does {ORDER} finish")
    c.ask("why cant this be moved earlier")
    results.append(_dump("L3 LAST-ANSWER", c))

    # --- L4: the HISTORY rung ---------------------------------------------
    # Turn 1 selected, answering with a subject_type OUTSIDE the five, so the
    # last-answer rung stays empty; then the selection is cleared.
    c = Conversation("d2-ladder-l4", target, parser, synth)
    c.reset()
    c.ask("why is this here",
          select={"order": ORDER, "machine": MACHINE, "op_seq": SEQ})
    c.selection = {}
    c.ask("why cant this be moved earlier")
    results.append(_dump("L4 HISTORY", c))

    (out / "ladder.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nartifact -> {out / 'ladder.json'}")

    print("\n--- RUNG SUMMARY " + "-" * 55)
    for r in results:
        last = r["turns"][-1]
        srcs = sorted({s["source"] for s in last["subjects"]}) or ["(none)"]
        print(f"  {r['label']:16s} final-turn subject source(s): {', '.join(srcs)}"
              f"   route={last['route']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
