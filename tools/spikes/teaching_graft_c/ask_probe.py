"""Ask ONE question of ONE world, with an optional board selection, and print
the answer a planner would read.

Session 4A teaching-graft (c). The founder round (founder_round_c9.md) needs a
command that works on BOTH worlds it uses, and neither existing front door does:
`python -m mre.ask` takes an out-dir but has no selection channel and no
registry lookup, and the cockpit can show a registered board but not the fenced
specimen world, which is a monolithic run in `_ai_exam_scratch`.

This is that command. It is the same ask path the cockpit calls — `run_ask`,
live parse, live renderer — with the board selection supplied on the command
line instead of by clicking a bar. Conversation state is cleared before every
question, so each invocation is a cold turn (the RESET discipline every bank in
this repo uses).

    # a registered board
    python tools/spikes/teaching_graft_c/ask_probe.py \
        --run rolling-db5395dc-2ae "why is ORD-000112 late"

    # the fenced specimen world, with a bar selected
    python tools/spikes/teaching_graft_c/ask_probe.py \
        --out-dir _ai_exam_scratch/mobility_pinned --snapshot-id snap-mobility \
        --select ORD-EARLY:BOX-01:10 "why cant this be moved"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.interpreter import forget_deliveries, run_ask  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402
from mre.modules.synthesizer import Synthesizer  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def _selection(spec: str | None) -> dict:
    """``ORDER[:MACHINE[:SEQ]]`` -> the selection channel the board panel sends."""
    if not spec:
        return {}
    parts = (spec.split(":") + ["", ""])[:3]
    out: dict = {}
    if parts[0]:
        out["order"] = parts[0]
    if parts[1]:
        out["machine"] = parts[1]
    if parts[2]:
        out["op_seq"] = int(parts[2])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("question")
    ap.add_argument("--run", help="a schedule id in the data root")
    ap.add_argument("--data-root", default="_data")
    ap.add_argument("--out-dir", help="a solved out-dir (no registry)")
    ap.add_argument("--snapshot-id", default="snap-exam")
    ap.add_argument("--select", help="ORDER[:MACHINE[:SEQ]] — the board selection")
    args = ap.parse_args(argv)

    if args.run:
        target = RunTarget.from_schedule(ROOT / args.data_root, args.run)
    elif args.out_dir:
        target = RunTarget.from_out_dir(args.out_dir, args.snapshot_id)
    else:
        print("give --run <schedule_id> or --out-dir <path>", file=sys.stderr)
        return 2

    explainer = target.build_vocab()._ex
    parser, synth = QuestionParser(), Synthesizer()
    if not parser.available:
        print("PARSER UNAVAILABLE (no key) — the answer would be the honest "
              "floor, not a measurement.", file=sys.stderr)
        return 2

    forget_deliveries("founder-round")
    r = run_ask(explainer, args.question, parser=parser,
                synthesizer=synth if synth.available else None,
                context={"history": [], "selection": _selection(args.select),
                         "last_answered_subject": {}, "card": {}},
                document=target.document, session_id="founder-round")
    print(f"Q: {args.question}")
    if args.select:
        print(f"   [selected: {args.select}]")
    print(f"   route={r.route} register={r.register} "
          f"intent={r.parsed.intent.value if r.parsed else '?'} "
          f"conf={r.confidence}")
    print("-" * 74)
    print(TemplateRenderer().render(r.bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
