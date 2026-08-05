"""(d.2) negative controls — prove R-EX2's forms and R-LD6's fix CAN go red.

Session 4A teaching-graft (d.2). The harness discipline is (e)'s and (e2)'s,
inherited whole and for the same reasons: it works in BYTES, it DETECTS the
file's line ending rather than assuming it (this repo mixes them per file),
ANCHOR NOT FOUND is a FAILURE and never a skip, every guard is proven GREEN AT
HEAD before its seam is reverted, and every restore is verified byte-identical
by sha256.

    python tools/spikes/teaching_graft_d2/negative_controls.py [--no-live]

TWO KINDS OF CONTROL, and the second is the one that matters.

  * ``pytest`` controls revert a seam and prove a named guard goes red. Fast,
    offline, and they aim at the SEAM rather than at a caller — 4B.28 §5a.123's
    lesson: a control that reverts something the guard does not depend on stays
    green and proves nothing.

  * ONE ``bank`` control reverts R-MT1's composite store key — the (d.1) fix for
    the recon's founding cross-version defect — and runs the COMMITTED
    CROSS-VERSION BANK against the live boards, asserting an ``expect-miss``
    appears. That is the whole claim R-EX2 was ruled for: that a bank can now
    watch a defect no bank format could previously express. Asserting the forms
    work on fixtures would not establish it; only pointing the real bank at the
    real defect does. ``--no-live`` skips it and SAYS SO rather than counting it.

  Live cost: two bank runs (~15 model calls) against `_data`, read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INTERP = ROOT / "src/mre/modules/interpreter.py"
SIDECAR = ROOT / "src/mre/ai_exam/sidecar.py"
PANEL = ROOT / "src/cockpit/src/askpanel.js"
EXPL = ROOT / "src/mre/modules/explainer.py"
REND = ROOT / "src/mre/modules/renderers.py"

W4 = ("tests/test_floor_truth_e2.py::TestF3TheRecordLeads::"
      "test_the_fourth_site_is_guarded_by_the_same_one_definition")

GUARD = "tests/test_relational_bank_format.py"
CRLF, LF = b"\r\n", b"\n"

#: (name, file, anchor, replacement, pytest selection that MUST go red)
CONTROLS: list[tuple] = [
    (
        "R-LD6(5) clause TWO — the subject the parse resolved",
        INTERP,
        b"    if parsed is None:\n"
        b"        return {}\n"
        b"    out: dict = {}\n",
        b"    if parsed is None or True:\n"
        b"        return {}\n"
        b"    out: dict = {}\n",
        GUARD + "::TestCarrySubjectClauseTwo",
    ),
    (
        "R-LD6(5) — ambiguity carries NOTHING (never guessed)",
        INTERP,
        b"    return next(iter(refs)) if len(refs) == 1 else None\n",
        b"    return next(iter(refs)) if refs else None\n",
        GUARD + "::TestCarrySubjectClauseTwo::test_two_different_orders_carry_NEITHER",
    ),
    (
        "R-LD6(5) — an UNRESOLVED subject is not a subject",
        INTERP,
        b"            and s.ref}\n",
        b"            }\n",
        GUARD + "::TestCarrySubjectClauseTwo::"
        "test_an_unresolved_sibling_does_not_make_a_resolved_order_ambiguous",
    ),
    (
        "R-EX2 — RECORDS_FROM refuses the empty set (opening nothing)",
        SIDECAR,
        b"            if not mine:\n",
        b"            if False:\n",
        GUARD + "::TestRecordProvenance::test_opening_NOTHING_is_not_grounding_correctly",
    ),
    (
        "R-EX2 — an unresolvable turn reference is a MISS, not a skip",
        SIDECAR,
        b"        if n > len(prior):\n"
        b"            misses.append(\n"
        b"                f\"{key}: refers to turn {n}, but only {len(prior)} turn(s) \"\n"
        b"                \"precede this one in this conversation\")\n"
        b"            return None\n",
        b"        if n > len(prior):\n"
        b"            return None\n",
        GUARD + "::TestAnUnresolvableReferenceIsAMissNotASkip",
    ),
    (
        "R-EX2 — an EMPTY body is unevaluable in both directions",
        SIDECAR,
        b"        if not turn.body_sha or not ref.body_sha:\n",
        b"        if False:\n",
        GUARD + "::TestBodyFingerprint::test_an_empty_body_is_UNEVALUABLE_in_both_directions",
    ),
    (
        "R-EX2 — the fingerprint ignores the rendered-by footer",
        SIDECAR,
        b"    lines = [ln for ln in (answer or \"\").splitlines()\n"
        b"             if not ln.strip().startswith(\"[rendered by:\")\n",
        b"    lines = [ln for ln in (answer or \"\").splitlines()\n"
        b"             if True or not ln.strip().startswith(\"[rendered by:\")\n",
        GUARD + "::TestBodyFingerprint::test_the_fingerprint_ignores_the_rendered_by_footer",
    ),
    (
        "R-EX2 — the per-turn checker leaves the relational keys alone",
        SIDECAR,
        b"        if key in _RELATIONAL_KEYS:\n            continue\n",
        b"        if False:\n            continue\n",
        GUARD + "::TestTheTwoCheckersDoNotOverlap",
    ),
    (
        "R-LD6(5) — the PANEL reads the product's answer",
        PANEL,
        # The WHOLE branch, return included. Blanking only the `if` left the
        # `return { ...meta.carry_subject }` behind, so the guard still saw the
        # identifier and stayed green — a control that reverted something the
        # guard did not depend on, which is 4B.28 §5a.123 caught in the act.
        b"    if (meta && meta.carry_subject && typeof meta.carry_subject === \"object\") {\n"
        b"      return { ...meta.carry_subject };\n"
        b"    }\n",
        b"",
        GUARD + "::TestOneDefinitionThreeSites::test_the_panel_reads_the_products_carry_subject_first",
    ),
    # --- rider R1: W4's fourth site, both halves of it -------------------
    (
        "W4 fourth site — the DRIVER reaches the mobility-lead payload",
        EXPL,
        b'            "chosen_driver": getattr(analysis, "chosen_driver", None),\n',
        b"",
        W4,
    ),
    (
        "W4 fourth site — the lead is GUARDED by the one definition",
        REND,
        b"        driver = mob.get(\"chosen_driver\")\n"
        b"        if counterfactual_contradicts_driver(driver):\n",
        b"        driver = mob.get(\"chosen_driver\")\n"
        b"        if False:\n",
        W4,
    ),
]

#: THE LIVE ONE. Revert R-MT1's composite key to session-only — the state the
#: recon (P4) measured, where board A's 102 record ids were served to a planner
#: looking at board B — and run the committed cross-version bank.
LIVE_CONTROL = (
    "R-MT1's composite store key — the cross-version BANK must go red",
    INTERP,
    b"    return (session_id, schedule_id or \"\")\n",
    b"    return (session_id, \"\")\n",
    "tests/ai_exam/banks/sweep_crossversion_v1.txt",
)

DEMO = "rolling-c32a6140-b6b"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pytest_green(node: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def _bank_green(bank: str) -> tuple[bool, str]:
    """(no expect-miss, a one-line summary). A run that could not happen is NOT
    green — an instrument that did not fire proves nothing either way."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "t.txt"
        r = subprocess.run(
            [sys.executable, "-m", "mre.ai_exam", "--run", DEMO,
             "--data-root", "./_data", "--questions", bank,
             "--transcript", str(out)],
            cwd=ROOT, capture_output=True, text=True)
        side = out.with_suffix(out.suffix + ".sidecar.json")
        if r.returncode != 0 or not side.exists():
            return False, f"RUN FAILED rc={r.returncode}: {r.stderr.strip()[-200:]}"
        data = json.loads(side.read_text(encoding="utf-8"))
        counts = data.get("finding_counts") or {}
        graded = data.get("graded_expectations") or {}
        misses = [f["detail"] for f in data.get("findings") or []
                  if f["kind"] == "expect-miss"]
        summary = (f"graded {graded.get('met')}/{graded.get('graded')}"
                   f"  findings={counts or 'clean'}")
        if misses:
            summary += f"  |  first miss: {misses[0][:110]}"
        return not misses, summary


def _apply(path: Path, anchor: bytes, replacement: bytes) -> tuple[bytes, bool]:
    before = path.read_bytes()
    if CRLF in before:
        anchor = anchor.replace(LF, CRLF)
        replacement = replacement.replace(LF, CRLF)
    if anchor not in before:
        return before, False
    path.write_bytes(before.replace(anchor, replacement, 1))
    return before, True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-live", action="store_true",
                    help="skip the live cross-version bank control (and say so)")
    args = ap.parse_args()

    print("(d.2) NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 74)
    failures = 0
    for name, path, anchor, replacement, node in CONTROLS:
        digest = _sha(path)
        if not _pytest_green(node):
            print(f"  NOT GREEN AT HEAD  {name}\n                     {node}")
            failures += 1
            continue
        before, applied = _apply(path, anchor, replacement)
        if not applied:
            print(f"  ANCHOR NOT FOUND   {name}"
                  f"\n                     in {path.relative_to(ROOT)}")
            failures += 1
            continue
        try:
            went_red = not _pytest_green(node)
        finally:
            path.write_bytes(before)
        restored = _sha(path) == digest
        print(f"  {'RED (good)' if went_red else 'STILL GREEN - FAILED':<22}{name}")
        print(f"  {'restore byte-identical: ' + ('yes' if restored else 'NO'):<22}"
              f"sha256 {digest[:16]}")
        if not went_red or not restored:
            failures += 1

    print("-" * 74)
    if args.no_live:
        print("  LIVE CONTROL SKIPPED (--no-live). It is NOT counted as passing:")
        print("  the cross-version bank's ability to catch R-MT1's defect is "
              "UNPROVEN in this run.")
        total = len(CONTROLS)
    else:
        name, path, anchor, replacement, bank = LIVE_CONTROL
        digest = _sha(path)
        ok, summary = _bank_green(bank)
        print(f"  AT HEAD            {name}\n                     {summary}")
        if not ok:
            print("  NOT GREEN AT HEAD - the bank already misses; control void")
            failures += 1
        else:
            before, applied = _apply(path, anchor, replacement)
            if not applied:
                print(f"  ANCHOR NOT FOUND   in {path.relative_to(ROOT)}")
                failures += 1
            else:
                try:
                    red_ok, red_summary = _bank_green(bank)
                finally:
                    path.write_bytes(before)
                restored = _sha(path) == digest
                went_red = not red_ok
                print(f"  {'RED (good)' if went_red else 'STILL GREEN - FAILED':<22}"
                      f"{name}")
                print(f"                     REVERTED: {red_summary}")
                print(f"  {'restore byte-identical: ' + ('yes' if restored else 'NO'):<22}"
                      f"sha256 {digest[:16]}")
                if not went_red or not restored:
                    failures += 1
        total = len(CONTROLS) + 1

    print("=" * 74)
    print(f"{total - failures}/{total} controls proven red, "
          "every restore byte-identical")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
