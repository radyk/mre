"""Run the FULL exam bank set against a pinned run and write a sweep directory.

Session 4A.5a CU5 — the re-baseline sweep. Fires every committed bank through the
REAL ask path (LLM-first parse + the live renderer when a key is present) against
one pinned world, writes a transcript + sidecar per bank under a dated sweep
directory, and prints the comparison table the close-out states.

    python tools/run_ai_exam_sweep.py \
        --out-dir _ai_exam_scratch/gb_pinned --snapshot-id snap-exam \
        --sweep-dir tests/ai_exam/sweeps/2026-07-25-llm-parse

The banks are read from tests/ai_exam/banks/ (every .txt). One parser is shared
across the whole sweep so the parse-specific counts (clarify / retry / malformed
rates, median latency) are the sweep's, not one bank's.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mre.ai_exam.report import render_sidecar, render_transcript  # noqa: E402
from mre.ai_exam.runner import ExamRunner, RunTarget  # noqa: E402
from mre.ai_exam.script import parse_script  # noqa: E402

BANKS_DIR = Path(__file__).resolve().parents[1] / "tests" / "ai_exam" / "banks"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--snapshot-id", required=True)
    ap.add_argument("--sweep-dir", required=True)
    ap.add_argument("--banks", nargs="*", help="bank file names (default: all)")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args(argv)

    sweep_dir = Path(args.sweep_dir)
    sweep_dir.mkdir(parents=True, exist_ok=True)
    banks = ([BANKS_DIR / b for b in args.banks] if args.banks
             else sorted(BANKS_DIR.glob("*.txt")))

    target = RunTarget.from_out_dir(args.out_dir, args.snapshot_id,
                                    label=f"out-dir:{Path(args.out_dir).name}")
    # ONE parser for the whole sweep — the parse counts are the sweep's.
    from mre.modules.question_parser import QuestionParser
    parser = QuestionParser()
    print(f"sweep: parser available={parser.available} "
          f"prompt_version={parser.prompt_version}")

    summary = []
    for bank in banks:
        runner = ExamRunner(target, per_question_timeout=args.timeout,
                            parser=parser, session_id=f"sweep-{bank.stem}")
        result = runner.run(parse_script(bank.read_text(encoding="utf-8")),
                            limit=args.limit)
        (sweep_dir / f"{bank.stem}.txt").write_text(
            render_transcript(result), encoding="utf-8")
        (sweep_dir / f"{bank.stem}.sidecar.json").write_text(
            render_sidecar(result), encoding="utf-8")
        graded, met = result.graded()
        row = {"bank": bank.stem, "questions": len(result.turns),
               "graded": graded, "met": met,
               "findings": result.finding_counts(),
               "llm_calls": result.total_llm_calls}
        summary.append(row)
        print(f"sweep: {bank.stem}: {len(result.turns)} q, graded {met}/{graded}, "
              f"findings {row['findings'] or 'clean'}")

    totals: dict = {}
    for row in summary:
        for k, v in row["findings"].items():
            totals[k] = totals.get(k, 0) + v
    payload = {
        "target": target.label, "snapshot": args.snapshot_id,
        "banks": summary,
        "totals": {"questions": sum(r["questions"] for r in summary),
                   "graded": sum(r["graded"] for r in summary),
                   "met": sum(r["met"] for r in summary),
                   "findings": totals},
        "parser_stats": parser.stats.as_dict(),
    }
    (sweep_dir / "SWEEP.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["totals"], indent=2))
    print(json.dumps(payload["parser_stats"], indent=2))
    print(f"sweep: -> {sweep_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
