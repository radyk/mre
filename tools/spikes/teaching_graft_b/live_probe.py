"""Live probes against the DEMO BOARD for the close-out's quoted specimens.

Session 4A teaching-graft (b). Three things the sweep grade cannot show and the
acceptance list requires quoted verbatim:

  1. the boss question and its two family siblings in the NEW shape, after the
     lever became the route's own "My take:";
  2. a teaching question at full depth, with labeled general knowledge and the
     invitation;
  3. a short-budget answer with the CLOSER firing on a real cut — which the v2
     sweep did NOT produce (deferred=0 across 8 synthesis answers), so this
     probes for one rather than assuming it.

Usage:  python tools/spikes/teaching_graft_b/live_probe.py [schedule_id]
"""
from __future__ import annotations

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

PROBES = [
    ("G1", "there are a lot of orders late what reason can i give my boss and "
           "what will help lessen the impact"),
    ("G2", "what do i say in the production meeting tomorrow about the late orders"),
    ("G3", "what should i do about all this lateness"),
    ("T1", "in general, what makes a scheduling problem hard to prove optimal"),
    # THE CLOSER HUNT. Short-budget questions whose historical shape drafted five
    # or six claims. If none of these binds the cap, that is the finding.
    ("S1", "what does the overall shape of this schedule look like across the "
           "machines and the weeks"),
    ("S2", "compare how the cutting machines and the press are loaded and what "
           "that means for the late orders"),
    ("S3", "give me a full picture of where the money is going in this plan"),
    ("S4", "walk me through everything that is unusual about this board"),
]


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    explainer = target.build_vocab()._ex
    parser, synth = QuestionParser(), Synthesizer()
    if not (parser.available and synth.available):
        print("PARSER/SYNTHESIZER UNAVAILABLE — nothing measured.")
        return 2
    renderer = TemplateRenderer()

    for tag, q in PROBES:
        forget_deliveries("probe")
        r = run_ask(explainer, q, parser=parser, synthesizer=synth,
                    document=target.document, session_id="probe")
        s = r.synthesis
        print("=" * 78)
        print(f"[{tag}] {q}")
        print(f"  route={r.route}  register={r.register}  "
              f"intent={r.parsed.intent.value if r.parsed else '?'}  "
              f"conf={r.confidence}")
        if s is not None:
            c = s.counts()
            print(f"  claims={c['claims']} verified={c['verified']} "
                  f"interpretive={c['interpretive']} "
                  f"general={c['general_knowledge']} cut={c['failed_and_cut']} "
                  f"DEFERRED={c['deferred']}")
        print("-" * 78)
        print(renderer.render(r.bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
