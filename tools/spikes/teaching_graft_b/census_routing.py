"""CENSUS (a) + (c) — where the probe families route at HEAD, and which
deterministic markers separate them.

Session 4A teaching-graft (b). PARSE ONLY: no synthesis runs, so this is cheap
and it measures the thing R-TG2 is about — what the closed vocabulary does with
a question whose goal is "help me understand". Four families:

  T  TEACHING   a question about how scheduling works, naming nothing on the board
  M  MIXED      a board entity AND teaching phrasing in one question
  B  BOARD      an ordinary board question (the control: must not become teaching)
  G  GOAL       a question naming a HUMAN AUDIENCE ("what do I tell my boss")

Part (c) is computed over the same probe texts WITHOUT a model: it applies the
candidate deterministic markers and reports how each family scores, so the
false-positive risk of every marker is a number rather than an intuition.

Usage:  python tools/spikes/teaching_graft_b/census_routing.py [schedule_id]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]

PROBES: dict[str, list[str]] = {
    "T": [
        "in general, what makes a scheduling problem hard to prove optimal",
        "how do schedulers normally decide which job to run first",
        "explain what the optimality gap means",
        "why do setup times matter in scheduling",
        "what does it mean when a schedule is infeasible",
        "how does a rolling horizon normally work",
        "what is a bottleneck machine",
        "why does splitting a job across shifts help sometimes",
        "why do late orders tend to snowball on a board like this one",
        "what is the difference between a tardy order and a late one",
    ],
    "M": [
        "why is ORD-000091 late, and how does lateness normally compound",
        "explain why PRESS-FAST ends up being the bottleneck here",
        "what does the gap on this board mean",
        "is CUT-01 overloaded, and what does overloaded normally mean",
    ],
    "B": [
        "which order carries the largest single tardiness cost line on this board",
        "why is ORD-000128 op20 placed here",
        "what is running on PRESS-FAST",
        "how many orders are late",
        "when does ORD-000091 finish",
        "is ORD-000013 op20 splittable",
    ],
    "G": [
        "there are a lot of orders late what reason can i give my boss and "
        "what will help lessen the impact",
        "what should i tell the customer about ORD-000091",
        "what do i say in the production meeting tomorrow about the late orders",
        "what should i do about all this lateness",
    ],
}

# -- the candidate deterministic markers (part c) ---------------------------
#
# Each is a CANDIDATE only. What this census reports is the hit rate per family,
# which is what makes a false-positive risk arguable rather than asserted.
_MARKERS: dict[str, re.Pattern] = {
    "in_general": re.compile(r"\b(in general|generally|normally|usually|"
                             r"typically|tend to|as a rule)\b", re.I),
    "explain_verb": re.compile(r"\b(explain|what does .* mean|what is meant by|"
                               r"help me understand|walk me through|"
                               r"how does .* work)\b", re.I),
    "what_is_a": re.compile(r"\bwhat (is|are) (a|an|the) \w+", re.I),
    "why_do_plural": re.compile(r"\bwhy (do|does|would) (schedulers|solvers|"
                                r"planners|plants|a solver|a scheduler)\b", re.I),
    # THE SHIPPED PREDICATE ITSELF, imported rather than restated. The first
    # version of this census used a looser local regex and would have reported a
    # sensitivity the product does not have — a census that measures a draft of
    # the thing it is censusing measures nothing.
    "audience": None,      # handled by `markers_for`, see below
    "entity_named": re.compile(r"\b(ORD-\d+|[A-Z]{3,}-\d+)\b"),
    "this_board": re.compile(r"\b(this board|this plan|this schedule|here|"
                             r"on the board)\b", re.I),
}


def markers_for(text: str) -> list[str]:
    from mre.modules.audience_shape import names_an_audience
    out = [name for name, rx in _MARKERS.items()
           if rx is not None and rx.search(text)]
    if names_an_audience(text):
        out.append("audience")
    return sorted(out)


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    vocab = target.build_vocab()
    explainer = vocab._ex
    parser = QuestionParser()
    if not parser.available:
        print("PARSER UNAVAILABLE — no key. Nothing measured.")
        return 2
    rolling = None
    if target.document is not None:
        from mre.modules.rolling_questions import RollingVocabulary
        rolling = RollingVocabulary(target.document) or None

    rows: list[dict] = []
    for family, questions in PROBES.items():
        for q in questions:
            parsed = parser.parse(q, explainer=explainer, context=None,
                                  rolling=rolling)
            rows.append({
                "family": family,
                "question": q,
                "intent": parsed.intent.value if parsed else "PARSE-FAILED",
                "confidence": round(parsed.confidence, 2) if parsed else None,
                "subjects": [f"{s.kind.value}={s.ref or s.raw}"
                             for s in (parsed.subjects if parsed else [])],
                "dropped_qualifier": parsed.dropped_qualifier if parsed else "",
                "markers": markers_for(q),
            })
            print(f"  [{family}] {rows[-1]['intent']:<22} "
                  f"conf={rows[-1]['confidence']}  {q[:62]}")

    print("\n=== (a) ROUTING BY FAMILY ===")
    for family in PROBES:
        fam_rows = [r for r in rows if r["family"] == family]
        counts = Counter(r["intent"] for r in fam_rows)
        print(f"  {family}  n={len(fam_rows)}  " +
              "  ".join(f"{k}={v}" for k, v in counts.most_common()))

    print("\n=== (c) MARKER HIT RATE BY FAMILY (false-positive risk) ===")
    header = f"{'marker':<16}" + "".join(f"{f:>6}" for f in PROBES)
    print(header)
    for name in _MARKERS:
        line = f"{name:<16}"
        for family in PROBES:
            fam_rows = [r for r in rows if r["family"] == family]
            hits = sum(1 for r in fam_rows if name in r["markers"])
            line += f"{hits}/{len(fam_rows):<4}"
        print(line)

    out = Path(__file__).with_name("census_routing.json")
    out.write_text(json.dumps({"schedule": schedule_id, "rows": rows},
                              indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
