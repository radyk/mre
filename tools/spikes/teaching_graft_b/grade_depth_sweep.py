"""Run `sweep_teaching_v2` against the DEMO BOARD and grade R-TG2/R-TG3/R-TG4.

The exam grammar's EXPECT lines grade ROUTING and nothing else, which is right —
routing is the only thing a bank can grade without re-implementing the product.
The three rulings here are about ANSWER SHAPE, so the five expectation families
are graded here, over the same run's rendered answers and per-turn claim counts:

  (e) LONG        a `teaching` question is not capped and its answer carries the
                  invitation to push back. Asserted on the RENDERED text and on
                  the turn's own deferred count, so a class that granted the
                  budget and lost the invitation fails.
  (f) SHORT       every other second-tier answer is inside SHORT_CLAIM_BUDGET,
                  and where the budget BOUND the closer names the count.
  (g) NO FALSE    the closer is absent wherever nothing was withheld. This is the
                  guard that matters most and is the easiest to lose: a closer
                  that always rendered would pass (f) and be a false disclosure
                  on every uncut answer.
  (h) AUDIENCE    a question naming a person leads with the account, then the
                  lever, then OFFERS the inventory — and prints no evidence
                  chain and no hold list. Checked on the RENDERED TEXT, which is
                  what a planner reads.
  (i) UNTOUCHED   no contracted testimony answer renders cap machinery or the
                  teaching invitation.

Usage:
  python tools/spikes/teaching_graft_b/grade_depth_sweep.py [schedule_id] [out_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.report import render_sidecar, render_transcript  # noqa: E402
from mre.ai_exam.runner import ExamRunner, RunTarget  # noqa: E402
from mre.ai_exam.script import parse_script  # noqa: E402
from mre.contracts.synthesis import SHORT_CLAIM_BUDGET  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    AUDIENCE_LEVER_HEADER, SYNTHESIS_DEFERRED, SYNTHESIS_DEFERRED_ONE,
    TEACHING_INVITATION,
)

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "tests" / "ai_exam" / "banks" / "sweep_teaching_v2.txt"

_CLOSER_STEM = SYNTHESIS_DEFERRED.split("{")[0]        # "I've kept this short — "
_LEAD_STEM = "You asked what to say to"
_AUDIENCE_QUESTIONS = ("my boss", "the customer", "the production meeting")


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        ROOT / "tests" / "ai_exam" / "sweeps" / "2026-08-04-teaching-v2")
    out_dir.mkdir(parents=True, exist_ok=True)

    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    runner = ExamRunner(target, per_question_timeout=180.0,
                        session_id="sweep-teaching-v2")
    result = runner.run(parse_script(BANK.read_text(encoding="utf-8")))
    (out_dir / "sweep_teaching_v2.txt").write_text(
        render_transcript(result), encoding="utf-8")
    (out_dir / "sweep_teaching_v2.sidecar.json").write_text(
        render_sidecar(result), encoding="utf-8")

    fams = {"e_long": [0, 0], "f_short": [0, 0], "g_no_false": [0, 0],
            "h_audience": [0, 0], "i_untouched": [0, 0]}
    problems: list[str] = []

    def _check(fam: str, ok: bool, note: str) -> None:
        fams[fam][1] += 1
        if ok:
            fams[fam][0] += 1
        else:
            problems.append(f"[{fam}] {note}")

    for t in result.turns:
        answer, s = t.answer or "", t.synthesis or {}
        q = (t.question or "").lower()
        intent = ((t.parse or {}).get("intent") or "")
        closer = _CLOSER_STEM in answer
        deferred = int(s.get("deferred") or 0)

        # (h) — a question naming a person, whatever route answered it.
        if any(a in q for a in _AUDIENCE_QUESTIONS):
            _check("h_audience", _LEAD_STEM in answer,
                   f"line {t.lineno}: no audience lead — {t.route}")
            _check("h_audience", "Evidence chain" not in answer,
                   f"line {t.lineno}: the evidence chain was PRINTED")
            _check("h_audience", "Where the hold is concrete" not in answer,
                   f"line {t.lineno}: the hold inventory was PRINTED")
            if _LEAD_STEM in answer and AUDIENCE_LEVER_HEADER in answer:
                _check("h_audience",
                       answer.index(_LEAD_STEM) < answer.index(
                           AUDIENCE_LEVER_HEADER),
                       f"line {t.lineno}: the lever precedes the account")
            continue

        if not s:                                   # a CONTRACTED answer
            _check("i_untouched",
                   not closer and TEACHING_INVITATION not in answer,
                   f"line {t.lineno}: {t.route} rendered cap machinery")
            continue

        if intent == "teaching":
            _check("e_long", deferred == 0,
                   f"line {t.lineno}: a teaching answer deferred {deferred}")
            _check("e_long", TEACHING_INVITATION in answer,
                   f"line {t.lineno}: a teaching answer lost its invitation")
        else:
            kept = int(s.get("claims") or 0) - int(s.get("failed_and_cut") or 0) \
                - deferred
            _check("f_short", kept <= SHORT_CLAIM_BUDGET,
                   f"line {t.lineno}: {kept} claims past a "
                   f"{SHORT_CLAIM_BUDGET}-claim budget")
            if deferred:
                expect = (SYNTHESIS_DEFERRED_ONE if deferred == 1
                          else SYNTHESIS_DEFERRED.format(n=deferred))
                _check("f_short", expect in answer,
                       f"line {t.lineno}: {deferred} withheld, closer absent "
                       f"or miscounted")
            _check("i_untouched", TEACHING_INVITATION not in answer,
                   f"line {t.lineno}: a short answer carries the teaching "
                   f"invitation")

        # (g) applies to EVERY second-tier answer, teaching included.
        _check("g_no_false", closer == bool(deferred),
               f"line {t.lineno}: closer={closer} but deferred={deferred}")

    tot = result.synthesis_totals()
    print(f"\nsweep: {len(result.turns)} turn(s) against {schedule_id}")
    print(f"       synthesis answers={tot['answers']} "
          f"general_knowledge={tot['general_knowledge']} "
          f"verified={tot['verified']} interpretive={tot['interpretive']} "
          f"cut={tot['failed_and_cut']} deferred={tot.get('deferred', 0)}")
    graded, met = result.graded()
    print(f"       routing expectations: {met}/{graded}")
    for fam, (ok, total) in fams.items():
        print(f"       {fam:14s} {ok}/{total}")
    for p in problems:
        print("  MISS " + p)
    (out_dir / "GRADE.json").write_text(json.dumps(
        {"schedule": schedule_id, "turns": len(result.turns),
         "routing": {"graded": graded, "met": met},
         "families": {k: {"met": v[0], "of": v[1]} for k, v in fams.items()},
         "synthesis": tot, "problems": problems}, indent=2), encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
