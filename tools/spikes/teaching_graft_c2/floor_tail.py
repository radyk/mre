"""Ask ONE teaching question N times cold, and report what came back each time.

Session 4A teaching-graft (c2), the after-half of two of session (c)'s
measurements — which are the same probe read two ways:

  THE FLOOR TAIL (c §5). P1's teaching question, asked six times in all, came
  back on the UNANSWERABLE FLOOR once: every board-flavoured claim it drafted was
  cut by R-TG1 direction (ii) for citing nothing, so nothing was left to render
  and a planner was told the product could not answer a question it answers most
  of the time.

  TURN 51's CLAIM COUNT (c §5). The depth licence granted eight claims and the
  answer shipped ONE.

Both are properties of the same six observations, so this takes them together.
Each ask is COLD — conversation state is cleared before every turn, the RESET
discipline every bank in this repo uses — so the six are six samples of one
question and not one conversation with itself.

  python tools/spikes/teaching_graft_c2/floor_tail.py --n 6
  python tools/spikes/teaching_graft_c2/floor_tail.py --n 6 --out before.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    SYNTHESIS_UNANSWERABLE, SYNTHESIS_UNANSWERABLE_NO_TOOLS,
)
from mre.modules.interpreter import forget_deliveries, run_ask  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402
from mre.modules.synthesizer import Synthesizer  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]

#: P1's Q1 — sweep_teaching_v3's first transfer pair, the turn 51 of session (c).
QUESTION = ("what generally decides whether an operation can be moved earlier "
            "on a board like this one")

#: The two tools that read the PRODUCT rather than the PLANT (R-TG5).
DOC_TOOLS = frozenset({"constraint_catalog", "spec_lookup"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default="rolling-db5395dc-2ae")
    ap.add_argument("--data-root", default="_data")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--question", default=QUESTION)
    ap.add_argument("--out", help="write the per-run detail here as JSON")
    args = ap.parse_args(argv)

    target = RunTarget.from_schedule(ROOT / args.data_root, args.run)
    explainer = target.build_vocab()._ex
    parser, synth = QuestionParser(), Synthesizer()
    if not (parser.available and synth.available):
        print("PARSER OR SYNTHESIZER UNAVAILABLE — the answers would be the "
              "honest floor, not a measurement.", file=sys.stderr)
        return 2

    rows = []
    for i in range(args.n):
        forget_deliveries("floor-tail")
        r = run_ask(explainer, args.question, parser=parser, synthesizer=synth,
                    context={"history": [], "selection": {},
                             "last_answered_subject": {}, "card": {}},
                    document=target.document, session_id="floor-tail")
        text = TemplateRenderer().render(r.bundle)
        a = r.synthesis
        counts = a.counts() if a is not None else {}
        tools = [c.tool for c in (getattr(a, "tool_calls", None) or [])]
        row = {
            "i": i + 1,
            "intent": r.parsed.intent.value if r.parsed else "?",
            "route": r.route,
            "floor": (SYNTHESIS_UNANSWERABLE in text
                      or SYNTHESIS_UNANSWERABLE_NO_TOOLS in text),
            "kept": len(getattr(a, "claims", []) or []),
            "verified": counts.get("verified", 0),
            "interpretive": counts.get("interpretive", 0),
            "general_knowledge": counts.get("general_knowledge", 0),
            "cut": counts.get("failed_and_cut", 0),
            "deferred": len(getattr(a, "deferred", []) or []),
            "tools": tools,
            "board_reads": [t for t in tools if t not in DOC_TOOLS],
        }
        row["board_claims"] = row["verified"] + row["interpretive"]
        rows.append(row)
        print(f"  {row['i']}: intent={row['intent']:9s} floor={row['floor']!s:5s} "
              f"kept={row['kept']} board={row['board_claims']} "
              f"gk={row['general_knowledge']} cut={row['cut']} "
              f"reads={row['board_reads']}")

    n = len(rows)
    floors = sum(1 for r in rows if r["floor"])
    reads = sum(1 for r in rows if r["board_reads"])
    boards = sum(1 for r in rows if r["board_claims"])
    print(f"\nQ: {args.question}")
    print(f"  floor hits              {floors}/{n}")
    print(f"  read this run (R-TG5)   {reads}/{n}")
    print(f"  carried a board claim   {boards}/{n}")
    print(f"  kept claims             {[r['kept'] for r in rows]}")
    print(f"  board claims            {[r['board_claims'] for r in rows]}")
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"question": args.question, "run": args.run, "n": n,
             "floor_hits": floors, "read_this_run": reads,
             "carried_board_claim": boards, "rows": rows}, indent=2),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
