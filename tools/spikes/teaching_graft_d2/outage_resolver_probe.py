"""Session 4A teaching-graft (d.2) PART B — what resolves a follow-up when the
parse tier is DOWN.

The brief's decision frame keeps a ladder rung if it "does something the parse's
resolution does not — determinism where the parse varies, OR resolution when the
parse tier is down". The second half is the claim this probe settles, because it
is the only one that would make the ladder a FALLBACK rather than a first
resolver, and a wrong answer here would be written into a ruling.

Driven with the (d.0) dossier's transport double (`UnreachableClient` through
`QuestionParser(_client=…)`, a constructor parameter the shipped code already
exposes) — a TRANSPORT failure, not a source change. Two turns: one that
establishes a subject with the model reachable, then a pointed follow-up with
the model unreachable and the LAST-ANSWER rung FULL.

Run: python tools/spikes/teaching_graft_d2/outage_resolver_probe.py
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

from conv import (  # noqa: E402
    Conversation, RecordingParser, RecordingSynthesizer, UnreachableClient,
)

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.synthesizer import Synthesizer  # noqa: E402

DEMO = "rolling-c32a6140-b6b"
ORDER = "ORD-000252"


def main() -> int:
    target = RunTarget.from_schedule(str(ROOT / "_data"), DEMO)
    live = RecordingParser(QuestionParser())
    synth = RecordingSynthesizer(Synthesizer())

    c = Conversation("d2-outage", target, live, synth)
    c.reset()
    t1 = c.ask(f"why is {ORDER} late")
    print(f"T1 (model reachable) {t1.question!r}")
    print(f"   route={t1.route}  subject_type={t1.subject_type!r}")
    print(f"   carry now: last_answered={c.last_answered}")
    assert c.last_answered, "precondition: the LAST-ANSWER rung must be FULL"

    # The parse tier goes down between turns. Everything else is held.
    c.parser = RecordingParser(QuestionParser(_client=UnreachableClient()))
    t2 = c.ask("why cant this be moved earlier")
    print(f"\nT2 (model UNREACHABLE) {t2.question!r}")
    print(f"   route={t2.route}  intent={t2.intent!r}  register={t2.register}")
    print(f"   subject_type={t2.subject_type!r}  subject_name={t2.subject_name!r}")
    print(f"   subjects bound: {t2.subjects or '(none)'}")
    print(f"   note={t2.resolution_note!r}")
    print("   A:")
    for line in (t2.text or "").strip().splitlines()[:8]:
        print(f"     {line}")

    out = Path(__file__).parent / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "outage_resolver.json").write_text(json.dumps(
        {"carry_at_outage": c.turns[-1].sent_last_answered,
         "t2_route": t2.route, "t2_subjects": t2.subjects,
         "t2_subject_name": t2.subject_name, "t2_text": t2.text},
        indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nVERDICT: the ladder resolved a subject during the outage: "
          + ("YES" if t2.subjects else "NO — nothing was resolved; "
             "R-OF1's outage floor answered first"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
