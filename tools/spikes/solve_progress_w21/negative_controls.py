"""W2.1 (R-SP1) negative controls — prove each seam of this session CAN go red.

Same harness discipline as the certificate session's, and for the same reasons:
it works in BYTES, it DETECTS the file's line ending rather than assuming it
(this repo mixes them per file), ANCHOR NOT FOUND is a FAILURE and never a skip,
every guard is proven GREEN AT HEAD before its seam is reverted, and every
restore is verified byte-identical by sha256.

    python tools/spikes/solve_progress_w21/negative_controls.py

EACH CONTROL AIMS AT A SEAM, NOT A CALLER. NC1 and NC6 revert the SAME rule at
its TWO paths independently — the monolithic runner's emission and the rolling
window's — because a trail recorded on only one of them would be a gap shaped
exactly like the one this session closed (4B.14 §5a.34).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "src/mre/modules/solve_runner.py"
PROG = ROOT / "src/mre/modules/solve_progress.py"
ROLL = ROOT / "src/mre/modules/rolling_horizon.py"
ASM = ROOT / "src/mre/modules/schedule_assembler.py"

CRLF = b"\r\n"
LF = b"\n"

T = "tests/test_solve_progress.py"
TD = "tests/test_solve_progress_determinism.py"
TX = "tests/test_solve_progress_document.py"

#: (name, file, anchor, replacement, the tests that MUST go red)
CONTROLS: list[tuple] = [
    (
        "NC1 - the callback COLLECTS the incumbent (the trail itself)",
        RUNNER,
        b'        self.trail.append({"index": self._count, "objective": float(obj),\n'
        b'                           "elapsed_s": elapsed})\n',
        b"        pass\n",
        TD + "::test_a_the_incumbent_objective_sequence_is_reproducible",
    ),
    (
        "NC2 - the clause (2) disclosure (the label that keeps the % honest)",
        PROG,
        b"CLAUSE_2_LABEL = (\n"
        b'    "This compares the solver\'s own first workable plan with the plan it "\n',
        b"CLAUSE_2_LABEL = (\n"
        b'    "The solver improved this plan. "  # the bare claim, no comparison named\n'
        b'    "" if False else "" or "improved. " or (\n',
        T + "::test_clause_2_label_names_the_comparison_and_denies_the_others",
    ),
    (
        "NC3 - the METRIC ROLLUP that makes clause (2) structural",
        PROG,
        b"            subjects=subjects or [], rollup_of=metric_ids,\n",
        b"            subjects=subjects or [], rollup_of=None,\n",
        T + "::test_first_incumbent_is_a_rollup_that_decomposes_exactly",
    ),
    (
        # CLAUSE (7). The rolling two-stage's fused return is the ONE place a
        # tiebreak trail could be substituted for the cost trail, and the guard
        # catches it because the trail's last point must equal stage 1's
        # objective — a stage-2 trail's last point is a MINUTE COUNT.
        "NC4 - clause (7): the fused return carries STAGE 1's trail",
        ROLL,
        b"            incumbent_trail=s1.incumbent_trail,\n",
        b"            incumbent_trail=s2.incumbent_trail,\n",
        TX + "::test_the_rolling_trail_is_stage_ones_not_the_tiebreaks",
    ),
    (
        "NC5 - the artifact digest taken from the FILE, not the string",
        PROG,
        b"        digest = hashlib.sha256(path.read_bytes()).hexdigest()\n",
        b"        digest = hashlib.sha256(\n"
        b'            json.dumps(doc, indent=2, default=str).encode("utf-8")\n'
        b"        ).hexdigest()\n",
        T + "::test_the_artifact_digest_verifies_against_the_file_bytes",
    ),
    (
        # The MONOLITHIC path's emission, reverted independently of NC1's
        # collection: the trail can be collected correctly and still never reach
        # evidence, and that is a different defect with a different fix.
        "NC6 - the trail's EMISSION at the monolithic seam",
        RUNNER,
        b"            emit_solve_progress(\n"
        b"                reporter, trail=trail, status=status_str, best_bound=bound,\n",
        b"            _unused = emit_solve_progress\n"
        b"            _noop(\n"
        b"                reporter, trail=trail, status=status_str, best_bound=bound,\n",
        TX + "::test_the_monolithic_path_writes_the_trail_and_the_assembler_reads_it",
    ),
    (
        "NC7 - the assembler's READ of the trail (contract 1.16 wiring)",
        ASM,
        b"    p = max(recs, key=lambda r: r.get(\"timestamp\", \"\")).get(\"payload\", {})\n",
        b"    p = {}\n",
        TX + "::test_the_monolithic_path_writes_the_trail_and_the_assembler_reads_it",
    ),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run(node: str) -> bool:
    """True when the selection is GREEN."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    print("W2.1 / R-SP1 NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
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
