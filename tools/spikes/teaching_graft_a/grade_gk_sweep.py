"""Run `sweep_teaching_v1` against the DEMO BOARD and grade R-TG1's four families.

The exam grammar's own EXPECT lines grade ROUTING and nothing else, which is
right — routing is the only thing a bank can grade without re-implementing the
product. R-TG1's claim is about CLAIM CLASSES, so the four expectation families
are graded here, over the same run's rendered answers and per-turn claim counts:

  (a) LABELED    every general-knowledge claim reaches the page wearing the
                 marker, and the marker names BOTH halves. Counted, not
                 spot-checked: N claims must produce N markers, so a class that
                 silently dropped one would fail rather than look tidy.
  (b) CITED      the board claims in those same answers keep their citations. A
                 change that quietly relabeled board claims as general would pass
                 (a) and be a catastrophe; this is the guard against it.
  (c) NO HATCH   no line wearing the general marker carries an order id, a
                 machine id or a timestamp. Checked on the RENDERED TEXT against
                 this run's own vocabulary — deliberately independent of the
                 verifier that enforced it, because a check that shares its
                 subject's code proves only that the code is self-consistent.
  (d) UNTOUCHED  no contracted answer renders a general marker anywhere.

Usage:
  python tools/spikes/teaching_graft_a/grade_gk_sweep.py [schedule_id] [out_dir]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.report import render_sidecar, render_transcript  # noqa: E402
from mre.ai_exam.runner import ExamRunner, RunTarget  # noqa: E402
from mre.ai_exam.script import parse_script  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    SYNTHESIS_GENERAL_NOTE, SYNTHESIS_MARK_GENERAL,
)

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "tests" / "ai_exam" / "banks" / "sweep_teaching_v1.txt"
_TS = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def _general_lines(answer: str) -> list[str]:
    return [ln for ln in (answer or "").splitlines()
            if SYNTHESIS_MARK_GENERAL in ln]


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        ROOT / "tests" / "ai_exam" / "sweeps" / "2026-08-03-teaching-v1")
    out_dir.mkdir(parents=True, exist_ok=True)

    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    vocab = target.build_vocab()
    # The run's OWN vocabulary, as the planner sees it spelled — order and machine
    # external refs. Taken from the same throwaway Explainer the sidecar's shape
    # checks use, so "names an entity" means here what it means everywhere else.
    known = sorted(set(vocab.order_refs) | set(vocab.machine_refs),
                   key=len, reverse=True)

    runner = ExamRunner(target, per_question_timeout=180.0,
                        session_id="sweep-teaching-v1")
    result = runner.run(parse_script(BANK.read_text(encoding="utf-8")))
    (out_dir / "sweep_teaching_v1.txt").write_text(
        render_transcript(result), encoding="utf-8")
    (out_dir / "sweep_teaching_v1.sidecar.json").write_text(
        render_sidecar(result), encoding="utf-8")

    fams = {"a_labeled": [0, 0], "b_cited": [0, 0],
            "c_no_hatch": [0, 0], "d_untouched": [0, 0]}
    problems: list[str] = []

    def _check(fam: str, ok: bool, note: str) -> None:
        fams[fam][1] += 1
        if ok:
            fams[fam][0] += 1
        else:
            problems.append(f"[{fam}] {note}")

    for t in result.turns:
        answer, s = t.answer or "", t.synthesis or {}
        if not s:                                   # a CONTRACTED answer
            _check("d_untouched",
                   SYNTHESIS_MARK_GENERAL not in answer
                   and "general knowledge" not in answer,
                   f"line {t.lineno}: {t.route} rendered a general marker")
            continue

        n_general = int(s.get("general_knowledge") or 0)
        marked = _general_lines(answer)
        _check("a_labeled", len(marked) == n_general,
               f"line {t.lineno}: {n_general} general claim(s), {len(marked)} "
               f"marker(s) on the page")
        if n_general:
            _check("a_labeled", SYNTHESIS_GENERAL_NOTE in answer,
                   f"line {t.lineno}: general lines present, footer note absent")
            _check("a_labeled",
                   "general knowledge" in SYNTHESIS_MARK_GENERAL
                   and "not a fact about this plan" in SYNTHESIS_MARK_GENERAL,
                   "the marker does not name both halves")

        n_verified = int(s.get("verified") or 0)
        _check("b_cited", answer.count("[record:") >= n_verified,
               f"line {t.lineno}: {n_verified} verified claim(s), "
               f"{answer.count('[record:')} citation(s) rendered")

        for line in marked:
            body = line.split(SYNTHESIS_MARK_GENERAL)[0]
            named = [k for k in known
                     if re.search(rf"(?<![A-Z0-9]){re.escape(k)}(?![A-Z0-9])",
                                  body.upper())]
            _check("c_no_hatch", not named and not _TS.search(body),
                   f"line {t.lineno}: a general line names "
                   f"{named or _TS.findall(body)}: {body.strip()[:90]}")

    print(f"\nsweep: {len(result.turns)} turn(s) against {schedule_id}")
    print(f"       synthesis answers={result.synthesis_totals()['answers']} "
          f"general_knowledge={result.synthesis_totals()['general_knowledge']} "
          f"verified={result.synthesis_totals()['verified']} "
          f"interpretive={result.synthesis_totals()['interpretive']} "
          f"cut={result.synthesis_totals()['failed_and_cut']}")
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
         "synthesis": result.synthesis_totals(),
         "problems": problems}, indent=2), encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
