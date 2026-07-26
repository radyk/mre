"""The standing provenance report (R-AI5(5)/(6), Session 4A.5c CU1).

A thin CLI over ``mre.modules.provenance_report``. Runnable against ANY question
ledger; also emitted automatically at the end of every ai_exam sweep, beside the
sidecars.

    # a live ledger (what a sweep or a deployment writes)
    python tools/provenance_report.py --ledger _ai_exam_scratch/ledger.jsonl

    # a COMMITTED sweep whose transcripts predate the ledger (reconstructed rows;
    # no `nearest`, so the report says so per cluster)
    python tools/provenance_report.py --sweep tests/ai_exam/sweeps/2026-07-26-synthesis

    # write PROVENANCE.txt + PROVENANCE.json into a directory
    python tools/provenance_report.py --ledger ... --out-dir tests/ai_exam/sweeps/<date>

This tool READS. It never writes to the ledger, the canonical model or the evidence
store, and it promotes nothing: its output is a ranked list a human reads
(R-AI5(7) — the proven register is entered only by review).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mre.modules.provenance_report import (  # noqa: E402
    render_report, rows_from_ledger, rows_from_sweep, write_report,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ledger", help="a question-ledger JSONL")
    src.add_argument("--sweep", help="a committed sweep directory (transcripts "
                                     "reconstructed; adjacency unavailable)")
    ap.add_argument("--out-dir", help="write PROVENANCE.txt + .json here "
                                      "(default: print to stdout)")
    args = ap.parse_args(argv)

    if args.ledger:
        rows = rows_from_ledger(args.ledger)
        source = str(args.ledger)
    else:
        rows = rows_from_sweep(args.sweep)
        source = f"{args.sweep} (reconstructed from transcripts)"

    if not rows:
        print(f"provenance: no rows read from {source}", file=sys.stderr)
        return 1

    if args.out_dir:
        txt, js = write_report(rows, args.out_dir, source=source)
        print(f"provenance: -> {txt}")
        print(f"provenance: -> {js}")
    else:
        sys.stdout.write(render_report(rows, source=source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
