"""Rep 3 (docs/07 Phase 1): calibrate the STATISTICAL_OUTLIER threshold.

The validator's run-rate outlier check (docs/02 §4.3) grouped OperationSpecs
by product family and flagged anything > 10x the group median — a fixed
constant, never calibrated against a real distribution. On the gauntlet this
fires at a ~20% hit rate (578 warnings), which is not a "these are unusual"
signal, it's "the threshold is wrong for this data."

This tool reads every OperationSpec's run_rate directly from a snapshot
(the full population, not just what a prior validator run already flagged —
calibration needs the whole distribution, not its own output), groups by
product family exactly as the validator does, computes each spec's
ratio-to-group-median, and reports percentiles ON A LOG SCALE.

Why log scale, why pooled, why p99 (the calibration choice, not just the
mechanism):
  - Ratios are inherently multiplicative (a spec running "8x slower" and one
    running "8x faster" are symmetric deviations, but 0.125 and 8.0 are not
    symmetric on a linear scale — log2(ratio) puts them at -3 and +3). Percentiles
    and spread are only meaningful on the scale where the underlying deviations
    are actually symmetric.
  - POOLED across all families, not computed per-family: real family group
    sizes are small and uneven (a median of 2-3 members is common in messy
    real data) — per-family percentiles are statistically meaningless at that
    sample size. Pooling the log-ratios across every family (each family
    already centers itself at 0 by construction, since ratio is relative to
    its OWN median) uses the full sample for a stable tail estimate.
  - p99 (not a fixed log-unit count): the acceptance target is a hit rate
    ("low single-digit %"), not a hand-picked deviation size. Calibrating
    directly against the target percentile is what lets the threshold track
    "what this specific data's distribution actually looks like" rather than
    reintroducing another arbitrary constant.

Usage:
    python tools/calibrate_outliers.py --snapshot-dir mre_output/snapshots/snap-run
    python tools/calibrate_outliers.py --raw-data raw_data --plant-config plant_config.json
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mre.modules.snapshot_store import SnapshotStore  # noqa: E402
from mre.modules.validator import _parse_duration_seconds  # noqa: E402

PERCENTILES = (50, 75, 90, 95, 99, 99.9)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_values[lo]
    frac = rank - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def compute_family_ratios(snapshot_dir: Path) -> dict[str, list[tuple[str, float]]]:
    """Mirror Validator's Check 4 grouping exactly: process -> product ->
    product_family, falling back to setup_family. Returns {family: [(spec_id, rate_seconds)]}."""
    store = SnapshotStore(snapshot_dir.parent)
    reader = store.load_snapshot(snapshot_dir.name)

    op_specs = list(reader.iter_entities("operationspec"))
    products = list(reader.iter_entities("product"))
    processes = list(reader.iter_entities("process"))

    prod_family = {p["id"]: (p.get("product_family") or "") for p in products}
    spec_to_family: dict[str, str] = {}
    for proc in processes:
        pid = proc.get("product_ref", "")
        fam = prod_family.get(pid, "")
        for spec_id in proc.get("operation_specs", []):
            if fam:
                spec_to_family[spec_id] = fam

    family_rates: dict[str, list[tuple[str, float]]] = {}
    for spec in op_specs:
        fam = spec_to_family.get(spec["id"]) or spec.get("setup_family") or "unknown"
        run_rate_raw = spec.get("run_rate")
        if run_rate_raw is None:
            continue
        seconds = _parse_duration_seconds(run_rate_raw)
        if seconds <= 0:
            continue
        family_rates.setdefault(fam, []).append((spec["id"], seconds))
    return family_rates


def calibrate(family_rates: dict[str, list[tuple[str, float]]]) -> dict:
    pooled_log2_ratios: list[float] = []
    per_family_summary: list[dict] = []
    per_spec_ratio: dict[str, float] = {}
    per_spec_family: dict[str, str] = {}
    per_spec_median: dict[str, float] = {}

    for fam, entries in family_rates.items():
        if len(entries) < 2:
            continue
        rates = [r for _, r in entries]
        median = statistics.median(rates)
        if median <= 0:
            continue
        fam_log_ratios = []
        for spec_id, rate in entries:
            ratio = rate / median
            log_ratio = math.log2(ratio)
            pooled_log2_ratios.append(log_ratio)
            fam_log_ratios.append(log_ratio)
            per_spec_ratio[spec_id] = ratio
            per_spec_family[spec_id] = fam
            per_spec_median[spec_id] = median
        per_family_summary.append({
            "family": fam, "n": len(entries), "median_seconds": median,
            "max_log2_ratio": max(fam_log_ratios),
        })

    pooled_sorted = sorted(pooled_log2_ratios)
    percentiles = {p: _percentile(pooled_sorted, p) for p in PERCENTILES}

    return {
        "pooled_log2_ratios": pooled_sorted,
        "percentiles": percentiles,
        "per_family_summary": sorted(per_family_summary, key=lambda s: -s["max_log2_ratio"]),
        "per_spec_ratio": per_spec_ratio,
        "per_spec_family": per_spec_family,
        "per_spec_median": per_spec_median,
    }


def recommend_threshold(calib: dict, target_percentile: float = 99.0) -> float:
    """Recommended multiplier threshold (ratio, not log2) = 2 ** pooled p99."""
    p = calib["percentiles"][target_percentile]
    return 2 ** p


def report(calib: dict, threshold_ratio: float, snapshot_label: str) -> str:
    lines = [
        "# Outlier Threshold Calibration Report (Rep 3)",
        "",
        f"Snapshot: `{snapshot_label}`",
        f"Specs with a computable ratio (family size >= 2): {len(calib['pooled_log2_ratios'])}",
        "",
        "## Pooled log2(ratio) percentiles",
        "",
        "| Percentile | log2(ratio) | equivalent multiplier |",
        "|---|---|---|",
    ]
    for p in PERCENTILES:
        v = calib["percentiles"][p]
        lines.append(f"| p{p} | {v:.3f} | {2**v:.2f}x |")
    lines += [
        "",
        f"**Recommended threshold: {threshold_ratio:.2f}x** (pooled p99, converted back to a plain "
        f"multiplier). Rationale: pooling across families gives a stable tail estimate despite small, "
        f"uneven per-family group sizes; p99 directly targets a ~1% hit rate rather than reintroducing "
        f"an arbitrary fixed log-unit constant.",
        "",
        "## Top 10 families by max deviation",
        "",
        "| Family | n | median (s) | max log2(ratio) |",
        "|---|---|---|---|",
    ]
    for fs in calib["per_family_summary"][:10]:
        lines.append(f"| {fs['family']} | {fs['n']} | {fs['median_seconds']:.2f} | {fs['max_log2_ratio']:.2f} |")

    hit_count = sum(1 for r in calib["per_spec_ratio"].values() if r > threshold_ratio)
    total = len(calib["per_spec_ratio"])
    hit_pct = 100.0 * hit_count / total if total else 0.0
    lines += [
        "",
        f"## Hit rate at the recommended threshold",
        "",
        f"{hit_count} / {total} specs exceed {threshold_ratio:.2f}x their group's median "
        f"(**{hit_pct:.2f}%**).",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the STATISTICAL_OUTLIER threshold (Rep 3)")
    parser.add_argument("--snapshot-dir", help="Path to an existing snapshot directory")
    parser.add_argument("--raw-data", help="Path to raw_data/ (builds a fresh snapshot)")
    parser.add_argument("--plant-config", default="plant_config.json")
    parser.add_argument("--out", default=None, help="Report output path (default: <snapshot>/calibration_report.md)")
    parser.add_argument("--target-percentile", type=float, default=99.0)
    args = parser.parse_args()

    if args.snapshot_dir:
        snap_dir = Path(args.snapshot_dir)
        snapshot_label = str(snap_dir)
    elif args.raw_data:
        import tempfile
        from mre.contracts.vocabularies import ModuleCode, RunStatus
        from mre.modules.raw_adapter import RawAdapter, load_plant_config
        from mre.reporter import Reporter

        tmp = Path(tempfile.mkdtemp(prefix="calibrate_"))
        store = SnapshotStore(tmp / "snapshots")
        snap_id = "snap-calibrate"
        plant_cfg = load_plant_config(Path(args.plant_config))
        rep = Reporter.begin(module=ModuleCode.M1, purpose="calibration adapter", config={},
                             trigger="tools", snapshot_id=snap_id, sink_dir=tmp / "runs")
        RawAdapter(Path(args.raw_data), plant_cfg).run(snap_id, store, rep)
        rep.end(RunStatus.SUCCESS)
        snap_dir = tmp / "snapshots" / snap_id
        snapshot_label = f"{args.raw_data} (freshly adapted)"
    else:
        parser.error("must supply --snapshot-dir or --raw-data")
        return 1

    family_rates = compute_family_ratios(snap_dir)
    calib = calibrate(family_rates)
    threshold = recommend_threshold(calib, args.target_percentile)
    text = report(calib, threshold, snapshot_label)

    out_path = Path(args.out) if args.out else snap_dir / "calibration_report.md"
    out_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[calibrate_outliers] report written to {out_path}")
    print(f"[calibrate_outliers] RECOMMENDED_THRESHOLD_RATIO={threshold:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
