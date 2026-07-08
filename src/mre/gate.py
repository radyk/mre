"""Entry point: python -m mre.gate <submission_dir>

Runs the IDS conformance gate (docs/06 §4) standalone against a submission
directory and writes the Submission Certificate (certificate.json +
certificate.md) to --out (default: <submission_dir>/gate_output).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.conformance import (
    ConformanceGate, write_certificate_json, write_certificate_markdown,
)
from mre.reporter import Reporter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IDS conformance gate (docs/06 §4)")
    parser.add_argument("submission_dir", help="Path to an IDS submission directory")
    parser.add_argument("--out", default=None,
                        help="Output directory for the certificate (default: <submission_dir>/gate_output)")
    parser.add_argument("--runs-dir", default=str(Path("runs")),
                        help="Directory for the evidence-run JSONL stream")
    args = parser.parse_args(argv)

    submission_dir = Path(args.submission_dir)
    out_dir = Path(args.out) if args.out else submission_dir / "gate_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="IDS conformance gate",
        config={"submission_dir": str(submission_dir)},
        trigger="cli", snapshot_id="pre-adapter", sink_dir=Path(args.runs_dir),
    )
    result = ConformanceGate().run(submission_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)

    write_certificate_json(result.certificate, out_dir / "certificate.json")
    write_certificate_markdown(result.certificate, out_dir / "certificate.md")

    print(f"[mre.gate] submission   : {submission_dir}")
    print(f"[mre.gate] grade        : {result.grade}")
    print(f"[mre.gate] costing_grade: {result.costing_grade}")
    print(f"[mre.gate] findings     : {len(result.certificate['findings'])}")
    print(f"[mre.gate] certificate  : {out_dir / 'certificate.json'}")

    if result.grade == "REJECTED":
        print("[mre.gate] REJECTED - deficiencies:")
        for d in result.certificate["deficiencies"]:
            print(f"  - {d}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
