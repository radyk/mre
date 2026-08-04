"""THE TWO LIVE-SPECIMEN HUNTS — R-TG1 direction (i), and R-TG3's closer.

Session 4A teaching-graft (c), Item 3. Two clauses shipped in (a) and (b) that
have never fired against a real board, only against injected guards:

  HUNT A — R-TG1 ENFORCEMENT DIRECTION (i). A claim OFFERED as general knowledge
           that names an order, a machine, a time, money, or a figure this run
           computed is REFUSED the label and checked as an ordinary board claim.
           Session (a) reported: "under v6 the model keeps figures out of general
           sentences, so no proposal was refused in the wild." The probes below
           are written to TEMPT the refusal — they mix idiom with named entities
           and invite a general-sounding sentence about a specific number.

  HUNT B — R-TG3's CLOSER. When the depth cap (SHORT = 4) actually BINDS, the
           answer names how many claims it withheld. Session (b)'s A/B measured
           the shipped arm at deferred [0,0,0] — the prompt compresses below the
           cap on its own — so the shipped arm has no live closer specimen. The
           probes below ask for comparisons with many legitimately distinct
           claims, which is the shape that should overflow four if anything does.

NEITHER PROMPT IS TOUCHED. A specimen manufactured by weakening the governed
artifact would measure the weakening, not the clause. If a hunt comes back
empty, the empty result IS the finding and is reported as one.

    python tools/spikes/teaching_graft_c/hunt_specimens.py [schedule_id]
    python tools/spikes/teaching_graft_c/hunt_specimens.py --hunt a
"""
from __future__ import annotations

import argparse
import json
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

#: The refusal's own words, from `claim_verifier.verify_claim`. Matching the
#: PRODUCT's constant rather than a paraphrase is the point: a hunt that greps
#: for wording it invented would report on itself.
REFUSAL_MARK = "offered as general knowledge and refused the label because"

# ---------------------------------------------------------------------------
# HUNT A — tempt direction (i)
# ---------------------------------------------------------------------------
# Each probe pairs a GENERAL-KNOWLEDGE invitation ("in general", "usually",
# "typically", "as a rule") with something only this board can supply: a ledger
# figure, a named machine, a named order, a date. A model that answers the
# question at all has to put the two in one sentence to be responsive.
HUNT_A = [
    ("A1", "in general, is $1,667,467.80 of tardiness a lot for a plant like this"),
    ("A2", "explain why machines like CUT-01 usually end up being the bottleneck"),
    ("A3", "as a rule of thumb, how bad is a gap of 89.6% — is that normal for "
           "a schedule this size"),
    ("A4", "generally speaking, is it normal for an order like ORD-000112 to slip "
           "this far, and why does that happen in job shops"),
    ("A5", "typically, what does it mean when a plant has 122 orders sitting "
           "beyond the horizon — is that a lot"),
    ("A6", "in most factories, is running a machine at the load CUT-01 is "
           "carrying sustainable"),
]

# ---------------------------------------------------------------------------
# HUNT B — overflow SHORT = 4
# ---------------------------------------------------------------------------
# Comparisons across several named subjects on several named axes. Every claim
# such a question invites is legitimately distinct, so compression below four
# means dropping content rather than merging it.
HUNT_B = [
    ("B1", "compare the three cutting machines on utilization, lateness "
           "contribution, and idle time"),
    ("B2", "for each of CUT-01, MILL-01 and PRESS-FAST tell me how loaded it is, "
           "how much lateness it is responsible for, and how much idle time it has"),
    ("B3", "give me a machine by machine breakdown of this board: load, late "
           "orders, idle time and setup burden for every lane that carries work"),
    ("B4", "list every distinct problem on this board, one line each, and do not "
           "merge them"),
    ("B5", "what are the five separate things going wrong on this schedule"),
]


def _run(tag: str, q: str, explainer, parser, synth, renderer, document,
         verbose: bool) -> dict:
    forget_deliveries("hunt")
    r = run_ask(explainer, q, parser=parser, synthesizer=synth,
                document=document, session_id="hunt")
    s = r.synthesis
    rec: dict = {
        "tag": tag, "question": q, "route": r.route, "register": r.register,
        "intent": r.parsed.intent.value if r.parsed else None,
        "confidence": r.confidence,
    }
    if s is not None:
        c = s.counts()
        rec["counts"] = c
        refused = []
        for cl in list(s.claims) + list(s.cut) + list(s.deferred):
            if REFUSAL_MARK in (cl.reason or ""):
                refused.append({"text": cl.text, "status": cl.status.value,
                                "reason": cl.reason})
        rec["refused_gk"] = refused
        rec["deferred_texts"] = [c2.text for c2 in s.deferred]
    text = renderer.render(r.bundle)
    rec["answer"] = text
    print("=" * 78)
    print(f"[{tag}] {q}")
    print(f"  route={rec['route']} register={rec['register']} "
          f"intent={rec['intent']} conf={rec['confidence']}")
    if s is not None:
        c = rec["counts"]
        print(f"  claims={c['claims']} verified={c['verified']} "
              f"interpretive={c['interpretive']} general={c['general_knowledge']} "
              f"cut={c['failed_and_cut']} DEFERRED={c['deferred']}")
        print(f"  REFUSED-GK={len(rec['refused_gk'])}")
        for rf in rec["refused_gk"]:
            print(f"    ! {rf['text'][:150]}")
            print(f"      -> {rf['reason'][:300]}")
    if verbose:
        print("-" * 78)
        print(text)
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("schedule_id", nargs="?", default="rolling-db5395dc-2ae")
    ap.add_argument("--hunt", choices=["a", "b", "both"], default="both")
    ap.add_argument("--out", help="write the records as json here")
    ap.add_argument("--quiet", action="store_true",
                    help="omit the rendered answers (counts only)")
    args = ap.parse_args(argv)

    target = RunTarget.from_schedule(ROOT / "_data", args.schedule_id)
    explainer = target.build_vocab()._ex
    parser, synth = QuestionParser(), Synthesizer()
    if not (parser.available and synth.available):
        print("PARSER/SYNTHESIZER UNAVAILABLE — nothing measured.")
        return 2
    renderer = TemplateRenderer()

    probes = []
    if args.hunt in ("a", "both"):
        probes += HUNT_A
    if args.hunt in ("b", "both"):
        probes += HUNT_B

    records = []
    for tag, q in probes:
        try:
            records.append(_run(tag, q, explainer, parser, synth, renderer,
                                target.document, not args.quiet))
        except Exception as exc:  # noqa: BLE001 — a dead probe is data, not a stop
            print(f"[{tag}] RAISED {type(exc).__name__}: {exc}")
            records.append({"tag": tag, "question": q,
                            "error": f"{type(exc).__name__}: {exc}"})

    a_hits = sum(len(r.get("refused_gk") or []) for r in records
                 if r["tag"].startswith("A"))
    b_hits = sum(1 for r in records if r["tag"].startswith("B")
                 and (r.get("counts") or {}).get("deferred", 0) > 0)
    print("=" * 78)
    print(f"HUNT A — direction (i) refusals observed: {a_hits}")
    print(f"HUNT B — answers whose closer fired:      {b_hits}")
    if args.out:
        Path(args.out).write_text(json.dumps(records, indent=1), encoding="utf-8")
        print(f"records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
