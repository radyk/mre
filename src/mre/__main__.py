"""Entry point: python -m mre

Runs the full data-quality pipeline:
    M1 Adapter → M3 Validator → DQ Report

Usage:
    python -m mre [--sample-data PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mre.contracts.vocabularies import ModuleCode, RunStatus
from mre.modules.adapter import Adapter
from mre.modules.dq_report import generate_dq_report
from mre.modules.snapshot_store import SnapshotStore
from mre.modules.validator import Validator
from mre.reporter import Reporter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manufacturing Reasoning Engine — data quality pipeline"
    )
    parser.add_argument(
        "--sample-data",
        default=str(Path(__file__).parent.parent.parent / "sample_data"),
        help="Path to ERP extract directory (default: sample_data/)",
    )
    parser.add_argument(
        "--out",
        default=str(Path("mre_output")),
        help="Output directory for snapshots, run logs, and report",
    )
    parser.add_argument(
        "--snapshot-id",
        default="snap-dq-run",
        help="Snapshot identifier",
    )
    args = parser.parse_args(argv)

    extract_dir = Path(args.sample_data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_id = args.snapshot_id
    runs_dir = out_dir / "runs"
    store = SnapshotStore(out_dir / "snapshots")

    print(f"[mre] extract_dir : {extract_dir}")
    print(f"[mre] output_dir  : {out_dir}")
    print(f"[mre] snapshot_id : {snap_id}")

    # --- M1: Adapter ---
    adapter_reporter = Reporter.begin(
        module=ModuleCode.M1,
        purpose="ERP adapter run",
        config={"extract_dir": str(extract_dir)},
        trigger="cli",
        snapshot_id=snap_id,
        sink_dir=runs_dir,
    )
    adapter = Adapter(
        extract_dir=extract_dir,
        synthesized_generator="sample_data_gen_v1",
    )
    adapter_result = adapter.run(
        snapshot_id=snap_id,
        store=store,
        reporter=adapter_reporter,
    )
    adapter_reporter.end(RunStatus.SUCCESS)
    adapter_doc = adapter_reporter.consolidated_doc
    print(
        f"[mre] adapter     : {adapter_result.demand_count} demands, "
        f"{adapter_result.product_count} products, "
        f"{adapter_result.resource_count} resources"
    )

    # --- M3: Validator ---
    val_reporter = Reporter.begin(
        module=ModuleCode.M3,
        purpose="semantic validator run",
        config={},
        trigger="cli",
        snapshot_id=snap_id,
        sink_dir=runs_dir,
    )
    validator = Validator()
    val_result = validator.run(
        snapshot_id=snap_id,
        store=store,
        reporter=val_reporter,
    )
    val_reporter.end(RunStatus.SUCCESS)
    val_doc = val_reporter.consolidated_doc
    gate = "GO" if val_result.go else "NO-GO"
    print(
        f"[mre] validator   : {val_result.blocker_count} blockers, "
        f"{val_result.error_count} errors, "
        f"{val_result.warning_count} warnings — gate={gate}"
    )

    # --- DQ Report ---
    report_path = out_dir / "dq_report.md"
    generate_dq_report(
        adapter_doc=adapter_doc,
        validator_doc=val_doc,
        identity_map=adapter_result.identity_map,
        output_path=report_path,
    )
    print(f"[mre] dq_report   : {report_path}")

    adapter_jsonl = runs_dir / f"{adapter_reporter.run_id}.jsonl"
    val_jsonl = runs_dir / f"{val_reporter.run_id}.jsonl"
    print(f"[mre] adapter run : {adapter_jsonl}")
    print(f"[mre] validator run: {val_jsonl}")

    return 0 if val_result.go else 1


if __name__ == "__main__":
    sys.exit(main())
