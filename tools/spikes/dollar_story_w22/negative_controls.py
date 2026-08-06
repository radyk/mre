"""W2.2 (R-SP1 AMENDMENT 1 + the three rollups) negative controls.

Same harness discipline as W2.1's and the certificate session's: BYTES, the
file's own line ending DETECTED not assumed, ANCHOR NOT FOUND is a FAILURE and
never a skip, every guard proven GREEN AT HEAD before its seam is reverted, and
every restore verified byte-identical by sha256.

    python tools/spikes/dollar_story_w22/negative_controls.py

Each control aims at a seam this session added, and the three Part-B rollups are
reverted INDEPENDENTLY — a rollup that stopped being emitted while its two
neighbours kept working is exactly the shape a shared "statistics are emitted"
control would miss.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "src/mre/modules/solve_runner.py"
PRICE = ROOT / "src/mre/modules/plan_pricing.py"
PROG = ROOT / "src/mre/modules/solve_progress.py"
STATS = ROOT / "src/mre/modules/plan_statistics.py"
EXTR = ROOT / "src/mre/modules/extractor.py"

CRLF = b"\r\n"
LF = b"\n"

TP = "tests/test_plan_pricing.py"
TS = "tests/test_plan_statistics.py"
TD = "tests/test_solve_progress_document.py"

#: (name, file, anchor, replacement, the test that MUST go red)
CONTROLS: list[tuple] = [
    (
        "NC1 - the FIRST INCUMBENT's placements are captured (A1)",
        RUNNER,
        b"            try:\n"
        b"                self.first_values = self._var_map.extract(solver)\n",
        b"            try:\n"
        b"                self.first_values = None\n",
        TP + "::test_the_first_incumbents_placements_are_captured",
    ),
    (
        # THE SELF-PROOF's OWN CONTROL. Drop one marshalled argument and the
        # bridge would still return a plausible number — which is the entire
        # reason the final plan is re-priced against a known answer.
        #
        # THE FIRST VERSION OF THIS CONTROL DROPPED ``overtime_windows`` AND
        # STAYED GREEN. That is a fact about the SPECIMEN, not the guard: the
        # pilot_scale window prices no overtime, so that argument is inert on
        # it. The self-proof is only as strong as the features its specimen
        # exercises — carried forward. ``cost_model`` is dropped instead,
        # because every ledger figure on every specimen depends on it.
        "NC2 - the bridge marshals the COST MODEL (A2 self-proof)",
        PRICE,
        b"            cost_model=inputs.cost_model,\n",
        b"            cost_model={},\n",
        TP + "::test_THE_BRIDGE_SELF_PROOF_final_repriced_equals_the_shipped_ledger",
    ),
    (
        "NC3 - the COVERAGE check (both endpoints are the same plan)",
        PRICE,
        b"        placed = set(getattr(solve_values, \"op_resource\", {}) or {})\n"
        b"        if placed != set(require_ops):\n"
        b"            return None\n",
        b"        pass\n",
        TP + "::test_A_PLACEMENT_SET_THAT_IS_NOT_THIS_PLAN_IS_REFUSED_NOT_PRICED",
    ),
    (
        "NC4 - the DOLLAR HEADLINE branch (the amendment's own sentence)",
        PROG,
        b"    if summary.get(\"priced\"):\n",
        b"    if False:\n",
        TD + "::test_THE_ASSEMBLER_puts_the_block_on_a_real_rolling_document",
    ),
    (
        # THIS CONTROL'S FIRST TARGET WAS THE DOCUMENT TEST, AND IT STAYED
        # GREEN — because the only decomposition anyone checked was the BLOCK's
        # own arithmetic (`first - final == improvement`, computed in
        # `price_summary`). The METRIC rollup, which is the thing the
        # consolidator verifies and therefore the thing that makes clause (2)
        # structural, had no test at all. W2.1 gave the objective-space rollup
        # one and W2.2 owed the dollar rollup the same; the control is what
        # collected the debt.
        "NC5 - the DOLLAR ROLLUP that makes the pair decompose",
        PROG,
        b"            rollup_of=[fin.record_id, imp.record_id],\n",
        b"            rollup_of=None,\n",
        "tests/test_solve_progress.py"
        "::test_the_dollar_pair_is_a_rollup_that_decomposes_exactly",
    ),
    (
        "NC6 - B1: the late/on-time emission",
        STATS,
        b"    late = reporter.record_metric(\n",
        b"    late = _noop_metric(\n",
        TS + "::test_demands_counted_is_a_rollup_that_decomposes_exactly",
    ),
    (
        "NC7 - B2: the DENOMINATOR on the utilization record",
        STATS,
        # The source carries a literal em dash (UTF-8 e2 80 94). Spelling it as
        # a \u escape inside a bytes literal produces the six ASCII characters
        # "—" and the anchor never matches — ANCHOR NOT FOUND, which this
        # harness treats as a failure rather than a skip, which is how it was
        # caught.
        "            message=f\"utilization {u['utilization']:.4f} — "
        "{UTILIZATION_DEFINITION}\")\n".encode("utf-8"),
        b"            message=f\"utilization {u['utilization']:.4f}\")\n",
        TS + "::test_every_utilization_record_carries_its_denominator",
    ),
    (
        "NC8 - B3: the WIP filter that keeps minutes and charge on one population",
        EXTR,
        b"        changeover_minutes = 0\n"
        b"        for o in operations:\n"
        b"            if not _is_new_setup(o):\n"
        b"                continue                      # sunk before the reference date\n",
        b"        changeover_minutes = 0\n"
        b"        for o in operations:\n"
        b"            if False:\n"
        b"                continue\n",
        TS + "::test_changeover_minutes_and_the_setup_CHARGE_share_one_population",
    ),
    (
        "NC9 - B2: the utilization NUMERATOR is the billed working minutes",
        EXTR,
        b"            working_minutes_by_resource[chosen_rid] = (\n"
        b"                working_minutes_by_resource.get(chosen_rid, 0) + int(dur_min))\n",
        b"            working_minutes_by_resource[chosen_rid] = (\n"
        b"                working_minutes_by_resource.get(chosen_rid, 0) + int(end_min - start_min))\n",
        # RE-POINTED. The first target used UNCHUNKED ops, where working minutes
        # and elapsed span are the same number, so the control stayed GREEN
        # against a numerator swapped for ``end - start``. Only a RESUMABLE op
        # can see the difference — 4B.20's own lesson, landing on 4B.20's guard.
        TS + "::test_utilization_numerator_EXCLUDES_the_pauses_in_a_resumable_op",
    ),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run(node: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    print("W2.2 NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 78)
    failures = 0
    for name, path, anchor, replacement, node in CONTROLS:
        before = path.read_bytes()
        digest = _sha(path)
        if CRLF in before:
            anchor = anchor.replace(LF, CRLF)
            replacement = replacement.replace(LF, CRLF)
        if anchor not in before:
            print(f"  ANCHOR NOT FOUND  {name}")
            print(f"                    in {path.relative_to(ROOT)}")
            failures += 1
            continue
        if not _run(node):
            print(f"  NOT GREEN AT HEAD {name} - {node}")
            failures += 1
            continue
        path.write_bytes(before.replace(anchor, replacement, 1))
        try:
            went_red = not _run(node)
        finally:
            path.write_bytes(before)
        restored = _sha(path) == digest
        mark = "RED (good)" if went_red else "STILL GREEN - CONTROL FAILED"
        print(f"  {mark:<30} {name}")
        ok = "yes" if restored else "NO"
        print(f"  {'restore byte-identical: ' + ok:<30} sha256 {digest[:16]}")
        if not went_red or not restored:
            failures += 1
    print("=" * 78)
    print(f"{len(CONTROLS) - failures}/{len(CONTROLS)} controls proven red, "
          f"every restore byte-identical")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
