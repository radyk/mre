"""CLI entry point for what-if scenario analysis — python -m mre.whatif.

Usage:
    python -m mre.whatif --suppress-merge WO-2001,WO-2002
    python -m mre.whatif --suppress-merge WO-2001,WO-2002 --time-limit 60
    python -m mre.whatif --set-cost-weight tardiness_weights.base_weight=2.0

Runs a scenario re-solve against the base schedule and prints a cost/lateness diff.
Evidence is isolated to mre_output/scenario_runs/ — never added to the main index.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    # cp1252-safe output on Windows consoles — see mre.ask.main.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="MRE what-if scenario runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--suppress-merge",
        metavar="WO1,WO2,...",
        help="Comma-separated WO refs to force into individual schedules (unbatch)",
    )
    parser.add_argument(
        "--set-cost-weight",
        metavar="PATH=VALUE",
        help="Override a cost-model field via dot-path, e.g. tardiness_weights.base_weight=2.0",
    )
    parser.add_argument("--out", default="mre_output", help="Output directory from 'python -m mre'")
    parser.add_argument("--snapshot-id", default="snap-run", help="Base snapshot to branch from")
    parser.add_argument("--time-limit", type=float, default=30.0, help="Solver time limit in seconds")
    args = parser.parse_args(argv)

    from mre.modules.scenario import CalendarException, Scenario, ScenarioRunner, SetCostWeight, SuppressMerge
    from mre.modules.snapshot_store import SnapshotStore
    from mre.modules.renderers import TemplateRenderer
    from mre.modules.explainer import ExplanationBundle

    modifications: list = []
    if args.suppress_merge:
        demand_refs = [r.strip() for r in args.suppress_merge.split(",") if r.strip()]
        modifications.append(SuppressMerge(demand_refs=demand_refs))
    if args.set_cost_weight:
        if "=" not in args.set_cost_weight:
            print(
                f"[mre.whatif] --set-cost-weight must be PATH=VALUE, got: {args.set_cost_weight!r}",
                file=sys.stderr,
            )
            return 1
        path, _, raw_value = args.set_cost_weight.partition("=")
        try:
            value = float(raw_value.strip())
        except ValueError:
            print(f"[mre.whatif] Could not parse value as float: {raw_value!r}", file=sys.stderr)
            return 1
        modifications.append(SetCostWeight(path=path.strip(), value=value))

    if not modifications:
        print(
            "[mre.whatif] No modifications specified.\n"
            "  Use --suppress-merge WO-2001,WO-2002\n"
            "   or --set-cost-weight tardiness_weights.base_weight=2.0",
            file=sys.stderr,
        )
        return 1

    out_dir = Path(args.out)
    snap_id = args.snapshot_id

    if not (out_dir / "snapshots" / snap_id).exists():
        print(
            f"[mre.whatif] Snapshot '{snap_id}' not found in {out_dir}/snapshots/.\n"
            "Run 'python -m mre' first.",
            file=sys.stderr,
        )
        return 1

    store = SnapshotStore(out_dir / "snapshots")
    runs_dir = out_dir / "scenario_runs"
    from mre.modules.scenario import derive_base_context
    base_ctx = derive_base_context(Path(args.out) / "runs")
    runner = ScenarioRunner(store, runs_dir, time_limit_seconds=args.time_limit,
                            base_context=base_ctx)

    scenario = Scenario(base_snapshot_id=snap_id, modifications=modifications)
    print(f"[mre.whatif] scenario : {scenario.description()}")
    print(f"[mre.whatif] base     : {snap_id}")

    try:
        result = runner.run(scenario)
    except RuntimeError as exc:
        print(f"[mre.whatif] ERROR: {exc}", file=sys.stderr)
        return 2

    diff = result.diff
    identity_map = store.load_snapshot(snap_id).read_identity_map()

    bundle = ExplanationBundle(
        question=f"What if we {diff.get('description', '?')}?",
        subject_id=result.scenario_snapshot_id,
        subject_type="scenario_diff",
        subject_external_name=diff.get("description", "?"),
        ordered_records=[],
        key_facts=diff,
        snapshot_id=snap_id,
        identity_map=identity_map,
    )
    renderer = TemplateRenderer()
    print()
    print(renderer.render(bundle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
