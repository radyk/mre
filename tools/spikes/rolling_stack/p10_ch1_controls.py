"""R4.2 — the negative controls for R-CH1, each proven RED against physically
reverted code, with every restore verified byte-for-byte by sha256.

A guard nobody has watched fail is a guard nobody has tested. Three clauses,
three reverts, three named tests that must go red:

  (1) the rolling graft      -> the child renders MONOLITHIC again
  (2) the run-context write  -> the reference date is unrecoverable again
  (3) calibration inheritance-> the child declares nothing again

Each revert is a byte edit to a source file, the tests are run against it, the
ORIGINAL BYTES are written back, and the file's sha256 is compared before and
after. `git checkout --` is not byte-identical under autocrlf in this repo, so
the restore writes the captured bytes (docs/04 2026-08-06).

    python tools/spikes/rolling_stack/p10_ch1_controls.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

ASSEMBLER = REPO / "src/mre/modules/schedule_assembler.py"
PLANNER_EDIT = REPO / "src/mre/modules/planner_edit.py"
TESTS = "tests/test_child_inheritance.py"

CONTROLS = [
    {
        "name": "(1) the rolling graft",
        "file": ASSEMBLER,
        "find": b'    roll_raw = parent.get("rolling")\n',
        "repl": b'    roll_raw = None   # R4.2 NEGATIVE CONTROL\n',
        "tests": [
            f"{TESTS}::TestRollingInheritance::test_a_rolling_parent_mints_a_rolling_child",
            f"{TESTS}::TestAcceptChildOnARealBoard::test_the_child_of_a_rolling_board_is_rolling",
            f"{TESTS}::TestAcceptChildOnARealBoard::test_the_gesture_path_now_scopes_itself_from_the_child",
        ],
    },
    {
        "name": "(2) the run-context write",
        "file": PLANNER_EDIT,
        "find": b'                "reference_date": (reference_date.isoformat()\n'
                b'                                   if reference_date else None),\n',
        "repl": b'',
        "tests": [
            f"{TESTS}::TestAcceptChildOnARealBoard::test_the_reference_date_is_recoverable_from_the_child_s_own_run_dir",
        ],
    },
    {
        "name": "(3) calibration inheritance",
        "file": ASSEMBLER,
        "find": b'    cal_raw = (parent.get("solver") or {}).get("calibration")\n',
        "repl": b'    cal_raw = None   # R4.2 NEGATIVE CONTROL\n',
        "tests": [
            f"{TESTS}::TestCalibrationInheritance::test_the_profile_s_identity_is_inherited",
            f"{TESTS}::TestAcceptChildOnARealBoard::test_the_child_declares_the_plant_s_calibration",
        ],
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def in_file_newlines(blob: bytes, data: bytes) -> bytes:
    """THIS REPO MIXES LINE ENDINGS PER FILE (docs/04, 4A-(a)). `planner_edit.py`
    is CRLF and `schedule_assembler.py` is LF, so an anchor written with `\\n`
    silently fails to match in one of them — and a control whose anchor does not
    match reverts nothing and proves nothing. Check the file's own state."""
    if b"\r\n" in blob:
        return data.replace(b"\n", b"\r\n")
    return data


def run(tests: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--runslow", *tests],
        cwd=REPO, capture_output=True, text=True)
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
    return proc.returncode, tail


def main() -> int:
    ok = True
    for c in CONTROLS:
        path: Path = c["file"]
        original = path.read_bytes()
        before = sha(path)
        print("=" * 74)
        print(f"CONTROL {c['name']}   ({path.name}, sha {before[:12]}…)")
        print("=" * 74)
        find = in_file_newlines(original, c["find"])
        repl = in_file_newlines(original, c["repl"])
        if find not in original:
            print("  !! anchor not found — the control cannot revert anything, "
                  "which proves NOTHING. Fix the anchor.")
            ok = False
            continue
        try:
            path.write_bytes(original.replace(find, repl, 1))
            # EACH TEST SEPARATELY. Run as one invocation, the first failure
            # sets the exit code and a second test that stayed GREEN with the
            # code reverted would be invisible — a control reporting one
            # denominator for a set of claims.
            for t in c["tests"]:
                rc, tail = run([t])
                name = t.rsplit("::", 1)[-1]
                print(f"  {'RED ' if rc else 'GREEN'}  {name}")
                if rc == 0:
                    print("      !! GREEN WITH THE CODE REVERTED — this test "
                          "does not discriminate.")
                    ok = False
        finally:
            path.write_bytes(original)
        after = sha(path)
        print(f"  restored: sha {after[:12]}…  {'IDENTICAL' if after == before else 'MISMATCH'}")
        if after != before:
            ok = False

    print("\n" + "=" * 74)
    print("AT HEAD, restored — the same tests must be GREEN")
    print("=" * 74)
    rc, tail = run([TESTS])
    print(f"  rc={rc}\n    {tail}")
    ok = ok and rc == 0
    print("\nALL CONTROLS DISCRIMINATE" if ok else "\nSOMETHING DID NOT HOLD")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
