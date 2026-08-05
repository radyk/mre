"""R-TG6 negative controls — prove each new check CAN go red.

Session 4A teaching-graft (e). A premise test that cannot fail is a decoration,
and this repo has been caught twice by controls that stayed green against
physically reverted code (4B.28 §5a.123 — a control that drove the API past the
broken line; 4A.y — a control whose own harness corrupted line endings).

SO THIS WORKS IN BYTES, NEVER TEXT, AND DETECTS THE LINE ENDING RATHER THAN
ASSUMING IT. `Path.write_text` translates newlines, and this repo mixes line
endings per file. HARDCODING THEM IS NOT ENOUGH EITHER, which this harness
learned the hard way inside its own session: `claim_verifier.py` was LF when
these controls first ran 5/5, and a `git stash` round-trip — taken to measure the
HEAD baseline in this same checkout — renormalized it to CRLF, after which three
anchors silently stopped matching. **They reported ANCHOR NOT FOUND rather than
passing falsely, which is the one thing that saved it**, and it is why that state
is a FAILURE here and never a skip.

So every anchor below is authored with a bare newline and TRANSLATED to whatever
the file actually uses at match time. Every restore is verified by sha256 against
the digest taken before the edit.

    python tools/spikes/teaching_graft_e/negative_controls.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CV = ROOT / "src/mre/modules/claim_verifier.py"
RD = ROOT / "src/mre/modules/renderers.py"

CRLF = b"\r\n"
LF = b"\n"

#: (name, file, anchor, replacement, the tests that MUST go red)
CONTROLS: list[tuple] = [
    (
        "iii - the floor contradiction map",
        CV,
        b"    if (_IMMOBILITY_RE.search(text) and _EXCLUSIVITY_RE.search(text)\n"
        b"            and _LOCK_TERM_RE.search(text)):\n"
        b"        return [FLOOR_CONTRADICTION_REASON]\n",
        b"    if False:\n"
        b"        return [FLOOR_CONTRADICTION_REASON]\n",
        "tests/test_floor_truth.py::TestTheFloorVocabularyRefutesTheRule",
    ),
    (
        "i - the product-behavior class",
        CV,
        b"    return [why for why, rx in _PRODUCT_BEHAVIOR_RES "
        b"if rx.search(claim.text or \"\")]\n",
        b"    return []\n",
        "tests/test_floor_truth.py::TestTheProductBehaviorClass",
    ),
    (
        "ii - the mobility verdict meets the claim",
        CV,
        b"    if not _FREE_TO_MOVE_RE.search(claim.text or \"\"):\n"
        b"        return []\n",
        b"    if True:\n"
        b"        return []\n",
        "tests/test_floor_truth.py::TestTheMobilityVerdictMeetsTheClaim"
        "::test_the_founding_example_is_refused",
    ),
    (
        "W4 - the counterfactual vs the recorded driver",
        RD,
        b'CONSTRAINT_NAMING_DRIVERS = frozenset({\n'
        b'    "CAPACITY_BLOCKED", "CAPABILITY_LIMITED", "CALENDAR_WINDOW",\n'
        b'    "FROZEN_COMMITMENT", "SEQUENCE_DEPENDENCY", "NO_ALTERNATIVE",\n'
        b'})\n',
        b'CONSTRAINT_NAMING_DRIVERS = frozenset()\n',
        "tests/test_floor_truth.py::TestTheCounterfactualAndTheRecordedDriver"
        "::test_a_blocker_driver_contradicts_nothing_prevented_it",
    ),
    (
        "W5 - the closure is voiced",
        RD,
        b'        if kind == "calendar_closed" and closes_at:\n',
        b'        if False:\n',
        "tests/test_floor_truth.py::TestTheClosureIsVoiced",
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
    print("R-TG6 NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 74)
    failures = 0
    for name, path, anchor, replacement, node in CONTROLS:
        before = path.read_bytes()
        digest = _sha(path)
        # DETECT, DO NOT ASSUME - see the module note. A stash round-trip
        # renormalized one of these files mid-session and three hardcoded
        # anchors stopped matching.
        if CRLF in before:
            anchor = anchor.replace(LF, CRLF)
            replacement = replacement.replace(LF, CRLF)
        if anchor not in before:
            print(f"  ANCHOR NOT FOUND  {name}")
            print(f"                    in {path.relative_to(ROOT)}")
            failures += 1
            continue
        # GREEN FIRST. A control that never saw the guard pass proves nothing
        # about the guard; it might be red for an unrelated reason.
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
        print(f"  {mark:<28} {name}")
        ok = "yes" if restored else "NO"
        print(f"  {'restore byte-identical: ' + ok:<28} sha256 {digest[:16]}")
        if not went_red or not restored:
            failures += 1
    print("=" * 74)
    print(f"{len(CONTROLS) - failures}/{len(CONTROLS)} controls proven red, "
          f"every restore byte-identical")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
