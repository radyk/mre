"""(e2) negative controls — prove each of this errand's three fixes CAN go red.

Session 4A teaching-graft (e2). Same harness discipline as (e)'s, and for the
same reasons: it works in BYTES, it DETECTS the file's line ending rather than
assuming it (this repo mixes them per file, and a `git stash` round-trip
renormalized one of them mid-session in (e)), ANCHOR NOT FOUND is a FAILURE and
never a skip, every guard is proven GREEN AT HEAD before its seam is reverted,
and every restore is verified byte-identical by sha256.

    python tools/spikes/teaching_graft_e2/negative_controls.py

(e)'s five controls are NOT re-run here — `tools/spikes/teaching_graft_e/
negative_controls.py` still owns those seams and is unchanged.
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

F3 = "tests/test_floor_truth_e2.py::TestF3TheRecordLeads"

#: (name, file, anchor, replacement, the tests that MUST go red)
#:
#: EACH CONTROL AIMS AT THE SEAM, NOT AT A CALLER. (e)'s §5(c) and 4B.28
#: §5a.123 are the same lesson from two sides: a control that reverts something
#: the guard does not actually depend on stays green and proves nothing.
CONTROLS: list[tuple] = [
    (
        "F1 - the widened product-behavior verbs",
        CV,
        b"     r\"(?:\\w+\\s+)?\"\n"
        b"     r\"(?:can|cannot|can't|does|doesn't|will|won't|only|never|always|\"\n"
        b"     r\"treats?|models?|supports?|comput\\w+|calculat\\w+|determin\\w+|\"\n"
        b"     r\"decid\\w+|enforc\\w+|recogni[sz]\\w+|consider\\w+|distinguish\\w+)\\b\"\n",
        b"     r\"(?:can|cannot|can't|does|doesn't|will|won't|only|never|always|\"\n"
        b"     r\"treats?|models?|supports?)\\b\"\n",
        "tests/test_floor_truth_e2.py::TestTheWidenedProductBehaviorPredicate",
    ),
    (
        "F2 - R-TG7's empty-drop floor",
        RD,
        b"        if self._empty_teaching_floor(lines, kf):\n",
        b"        if False:\n",
        "tests/test_floor_truth_e2.py::TestR_TG7_TheEmptyTeachingDropHasAFloor",
    ),
    (
        "F2 - the floor-refuted gate (the card must not render on any empty answer)",
        RD,
        b"        if not any((c.get(\"reason\") or \"\").startswith(FLOOR_REFUTED_PREFIX)\n"
        b"                   for c in cuts):\n"
        b"            return False\n",
        b"        if False:\n"
        b"            return False\n",
        "tests/test_floor_truth_e2.py::TestR_TG7_TheEmptyTeachingDropHasAFloor"
        "::test_the_ordinary_floor_still_owns_its_own_cases",
    ),
    (
        "F3 - the record leads at the LEAD site (_mobility_correction)",
        RD,
        b'            return (f"The assignment decision for {name} records its driver as "\n',
        b'            return (f"It may be movable \\u2014 {machine} had open time. "\n'
        b'                    f"But the record says {driver}. "\n',
        F3 + "::test_the_lead_site_puts_the_record_first",
    ),
    (
        "F3 - the record leads at the BODY site (_render_why_here)",
        RD,
        b'                lines.append(\n'
        b'                    f"The assignment decision records its driver as {driver}, "\n'
        b'                    f"which names a constraint rather than a preference.")\n'
        b'                lines.append(\n'
        b'                    f"My own scan reads it the other way: holding every other "\n',
        b'                lines.append(\n'
        b'                    f"My own scan first: holding every other "\n',
        F3 + "::test_both_body_sites_put_the_record_first",
    ),
    (
        "F3 - the THIRD site's guard (_render_counterfactual, found by M4)",
        RD,
        b"            if counterfactual_contradicts_driver(driver):\n"
        b"                lines.append(\n"
        b'                    f"The assignment decision records its driver as {driver}, "\n'
        b'                    f"which names a constraint rather than a preference.")\n'
        b'                lines.append(\n'
        b'                    f"My own scan reads it the other way: {room}. Those two "\n',
        b"            if False:\n"
        b"                lines.append(\n"
        b'                    f"The assignment decision records its driver as {driver}, "\n'
        b'                    f"which names a constraint rather than a preference.")\n'
        b'                lines.append(\n'
        b'                    f"My own scan reads it the other way: {room}. Those two "\n',
        F3 + "::test_the_third_site_was_unguarded_before_this_session",
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
    print("(e2) NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 74)
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
