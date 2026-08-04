"""R-TG1 negative controls — prove each guard can go RED (Session 4A teaching-graft a).

A guard that has never been seen to fail proves nothing. Each control here
PHYSICALLY REVERTS one seam of the ruling, runs the tests written for that seam,
and asserts they go red — then restores the file and asserts the restore is
BYTE-IDENTICAL by sha256.

THE HARNESS IS BYTES-ONLY, and that is 4A.y's lesson paid forward: its first
version used ``Path.write_text``, which translates newlines on Windows, and
corrupted a file's line endings on its first run. It was caught by the restore
assertion, which is the whole reason the restore assertion exists. Nothing here
touches text mode.

Usage:  python tools/spikes/teaching_graft_a/negative_controls.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "src" / "mre" / "modules" / "claim_verifier.py"
RENDERERS = ROOT / "src" / "mre" / "modules" / "renderers.py"
INTERP = ROOT / "src" / "mre" / "modules" / "interpreter.py"
GUARDS = "tests/test_general_knowledge_claims.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _match_eol(anchor: bytes, blob: bytes) -> bytes:
    """Rewrite an anchor's newlines to the file's own.

    THIS REPO MIXES CONVENTIONS PER FILE — measured: `claim_verifier.py` is pure
    LF, `renderers.py` and `interpreter.py` are pure CRLF, and no file is mixed.
    A multi-line anchor written with `\\n` therefore matched in one file and
    silently did not in another, which the harness reported as SETUP FAIL rather
    than as a passing control. That report is the only reason this was not read
    as "the guard cannot fire" — 4A.y's newline lesson from the other side, where
    the translation happens on the READ rather than the write."""
    if b"\r\n" not in blob:
        return anchor.replace(b"\r\n", b"\n")
    return anchor.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def _run(node: str) -> tuple[bool, str]:
    """Run one test selector. Returns (passed, tail)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-p", "no:randomly",
         "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, tail[0]


#: (name, file, what it reverts, the old bytes, the new bytes, the test selector)
CONTROLS: list[tuple[str, Path, str, bytes, bytes, str]] = [
    (
        "direction (i) — the label is refused to a board sentence",
        VERIFIER,
        "gk_disqualifiers always returns [] — every proposal is honoured",
        b"    reasons: list[str] = []\n    if [r for r in claim.record_ids if r]:",
        b"    reasons: list[str] = []\n    return reasons  # NEGATIVE CONTROL\n"
        b"    if [r for r in claim.record_ids if r]:",
        f"{GUARDS}::TestDirectionOne",
    ),
    (
        "direction (ii) — the third state is closed",
        VERIFIER,
        "the drop branch is removed; an uncited ungrounded claim ships again",
        b"    if (claim.kind is not ClaimKind.GENERAL_KNOWLEDGE and not cited\n"
        b"            and _GROUNDED not in results\n"
        b"            and not _has_board_content(claim, assertions, scope, wide)):",
        b"    if False:  # NEGATIVE CONTROL\n"
        b"            pass\n"
        b"    if (False and claim.kind is not ClaimKind.GENERAL_KNOWLEDGE and not cited\n"
        b"            and _GROUNDED not in results\n"
        b"            and not _has_board_content(claim, assertions, scope, wide)):",
        f"{GUARDS}::TestDirectionTwo",
    ),
    (
        "the general line carries no provenance",
        VERIFIER,
        "the GK return carries `base` again — the whole consulted set and every tool",
        b"            return VerifiedClaim(\n"
        b"                text=claim.text, kind=claim.kind,\n"
        b"                status=ClaimStatus.GENERAL_KNOWLEDGE, assertions=assertions,",
        b"            return VerifiedClaim(  # NEGATIVE CONTROL\n"
        b"                status=ClaimStatus.GENERAL_KNOWLEDGE, assertions=assertions,\n"
        b"                **base,",
        f"{GUARDS}::TestTheClass::test_it_carries_no_provenance_at_all",
    ),
    (
        "the rendered label names both halves",
        RENDERERS,
        "the general line falls back to the ordinary synthesis marker",
        b'            if claim.get("status") == "general_knowledge":',
        b'            if False:  # NEGATIVE CONTROL',
        f"{GUARDS}::TestRendering",
    ),
    (
        "the drill-down honours the class",
        RENDERERS,
        "prove-it treats a general line as a reading of the plan again",
        # Anchored on the line ABOVE, because the same test appears in the claim
        # loop at a different indent. ASCII only: a bytes literal cannot carry the
        # em-dash the real comment uses.
        b'        rows = kf.get("lines") or []\n'
        b'        if claim.get("status") == "general_knowledge":',
        b'        rows = kf.get("lines") or []\n'
        b"        if False:  # NEGATIVE CONTROL",
        f"{GUARDS}::TestRendering::"
        "test_a_drill_down_onto_it_does_not_call_it_a_reading_of_the_plan",
    ),
    (
        "a cut says which kind of cut it was",
        RENDERERS,
        "every load-bearing cut reports as a failed grounding again",
        b"                SYNTHESIS_UNPLACEABLE\n"
        b'                if all((c.get("reason") or "") == UNPLACEABLE_REASON',
        b"                SYNTHESIS_UNGROUNDED  # NEGATIVE CONTROL\n"
        b'                if all((c.get("reason") or "") == UNPLACEABLE_REASON',
        f"{GUARDS}::TestDirectionTwo::test_the_cut_says_which_kind_of_cut_it_was",
    ),
    (
        "R-OF1 rider — an outage card never enters ANSWER_MEMORY",
        INTERP,
        "the register test is removed; the card is remembered as an answer",
        b'            and register != "system"):',
        b"            and True):  # NEGATIVE CONTROL",
        f"{GUARDS}::TestOutageIsNotAnAnswer",
    ),
]


def main() -> int:
    failures: list[str] = []
    for name, path, what, old, new, node in CONTROLS:
        original = path.read_bytes()
        before = hashlib.sha256(original).hexdigest()
        old, new = _match_eol(old, original), _match_eol(new, original)
        if old not in original:
            print(f"[SETUP FAIL] {name}: anchor not found in {path.name} — the "
                  f"control is pointed at code that has moved")
            failures.append(name)
            continue
        # PHYSICALLY revert, in bytes.
        path.write_bytes(original.replace(old, new, 1))
        try:
            passed, tail = _run(node)
        finally:
            path.write_bytes(original)
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        assert after == before, (
            f"RESTORE IS NOT BYTE-IDENTICAL for {path} ({before} -> {after})")
        verdict = "GREEN (control did NOT fire)" if passed else "RED"
        print(f"[{verdict}] {name}\n    reverted: {what}\n    {node}\n    {tail}")
        if passed:
            failures.append(name)

    print()
    if failures:
        print(f"{len(failures)} control(s) DID NOT FIRE: " + "; ".join(failures))
        return 1
    print(f"all {len(CONTROLS)} controls proven RED; every restore byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
