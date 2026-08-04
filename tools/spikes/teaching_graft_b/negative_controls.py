"""R-TG2/R-TG3/R-TG4 negative controls (Session 4A teaching-graft (b)).

A guard that has never been seen to fail proves nothing. Each control here
PHYSICALLY REVERTS one seam of the rulings, runs the tests written for that seam,
and asserts they go red — then restores the file and asserts the restore is
BYTE-IDENTICAL by sha256.

THE HARNESS IS BYTES-ONLY, and the `_match_eol` step is (a)'s lesson carried
forward: this repo mixes line endings PER FILE, so a multi-line anchor written
with `\\n` matches in one file and silently does not in another. It is copied
rather than imported so this file can be read and run on its own.

AND ONE CONTROL IS POINTED AT A REAL POINTER, NOT PAST IT (4B.28 §5a.123): the
closer control reverts the RENDERER's condition, not the seam's, because a
control that called `answer_budget.apply` directly would stay green against a
renderer that had stopped reading `deferred`.

Usage:  python tools/spikes/teaching_graft_b/negative_controls.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUDGET = ROOT / "src" / "mre" / "modules" / "answer_budget.py"
AUDIENCE = ROOT / "src" / "mre" / "modules" / "audience_shape.py"
RENDERERS = ROOT / "src" / "mre" / "modules" / "renderers.py"
INTERP = ROOT / "src" / "mre" / "modules" / "interpreter.py"
PARSE = ROOT / "src" / "mre" / "contracts" / "parse.py"
GUARDS = "tests/test_depth_licence.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _match_eol(anchor: bytes, blob: bytes) -> bytes:
    if b"\r\n" not in blob:
        return anchor.replace(b"\r\n", b"\n")
    return anchor.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def _run(node: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-p", "no:randomly",
         "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, tail[0]


#: (name, file, what it reverts, the old bytes, the new bytes, the test selector)
CONTROLS: list[tuple[str, Path, str, bytes, bytes, str]] = [
    (
        "R-TG3 — the short budget binds at all",
        BUDGET,
        "apply() returns the answer untouched — nothing is ever trimmed",
        b"    claims = list(answer.claims)\n"
        b"    if len(claims) <= licence.max_claims:",
        b"    claims = list(answer.claims)\n"
        b"    return answer  # NEGATIVE CONTROL\n"
        b"    if len(claims) <= licence.max_claims:",
        f"{GUARDS}::TestTheDepthLicence::"
        "test_the_short_budget_trims_and_the_surplus_is_deferred",
    ),
    (
        "R-TG3 — teaching is the ONLY long budget",
        BUDGET,
        "every intent is granted the long budget",
        b"    if intent is Intent.TEACHING:\n        return LONG",
        b"    if True:  # NEGATIVE CONTROL\n        return LONG",
        f"{GUARDS}::TestTheDepthLicence::test_teaching_is_the_only_long_budget",
    ),
    (
        "R-TG3 clause (2) — the conclusion is never trimmed",
        BUDGET,
        "the conclusion rescue is removed; draft order alone decides",
        b"    if not any(_is_conclusion(c) for c in keep):",
        b"    if False:  # NEGATIVE CONTROL",
        f"{GUARDS}::TestTheDepthLicence::test_the_conclusion_is_never_trimmed",
    ),
    (
        "R-TG3 clause (3) — the seam is WIRED to the live dispatch",
        INTERP,
        "the dispatch stops applying the licence — the seam exists and is unreachable",
        b"    licence = answer_budget.licence_for(parsed.intent)\n"
        b"    answer_budget.apply(answer, licence)",
        b"    licence = answer_budget.licence_for(parsed.intent)  # NEGATIVE CONTROL",
        f"{GUARDS}::TestTheCloserDiscloses::"
        "test_the_short_budget_cuts_live_and_the_closer_names_the_count",
    ),
    (
        "R-TG3 — the closer reaches the page",
        RENDERERS,
        "the renderer stops reading `deferred`; the cut happens and is silent",
        b'        deferred = len(kf.get("deferred") or [])\n'
        b"        if deferred:",
        b'        deferred = len(kf.get("deferred") or [])\n'
        b"        if False:  # NEGATIVE CONTROL",
        f"{GUARDS}::TestTheCloserDiscloses::"
        "test_the_short_budget_cuts_live_and_the_closer_names_the_count",
    ),
    (
        "R-TG3 — the closer is ABSENT when nothing was withheld",
        RENDERERS,
        "the closer renders unconditionally — a false disclosure on every "
        "uncut answer",
        b'        deferred = len(kf.get("deferred") or [])\n'
        b"        if deferred:",
        b'        deferred = len(kf.get("deferred") or []) or 2\n'
        b"        if deferred:  # NEGATIVE CONTROL",
        f"{GUARDS}::TestTheCloserDiscloses::"
        "test_the_closer_is_absent_when_nothing_was_withheld",
    ),
    (
        "R-TG2 — teaching reaches the second tier",
        INTERP,
        "the dispatch stops honouring the declared second-tier set",
        b"    if (parsed.intent in SECOND_TIER_INTENTS\n"
        b"            or parsed.confidence < CONF_MATCH):",
        b"    if (parsed.intent is Intent.UNMATCHED  # NEGATIVE CONTROL\n"
        b"            or parsed.confidence < CONF_MATCH):",
        f"{GUARDS}::TestTheTeachingIntent::"
        "test_a_teaching_question_reaches_the_second_tier",
    ),
    (
        "R-TG2 — teaching is not a route",
        PARSE,
        "`teaching` leaves the second-tier set, so the parity test demands a route",
        b"SECOND_TIER_INTENTS: frozenset[Intent] = frozenset(\n"
        b"    {Intent.UNMATCHED, Intent.TEACHING})",
        b"SECOND_TIER_INTENTS: frozenset[Intent] = frozenset(  # NEGATIVE CONTROL\n"
        b"    {Intent.UNMATCHED})",
        "tests/test_parse_contract.py::TestVocabulary::"
        "test_intents_and_routes_name_the_same_set",
    ),
    (
        "R-TG4 — the audience marker fires at all",
        AUDIENCE,
        "names_an_audience always returns \"\" — no question names a person",
        b"    m = _AUDIENCE.search(question or \"\")\n"
        b"    if m is None:\n        return \"\"",
        b"    m = _AUDIENCE.search(question or \"\")\n"
        b"    return \"\"  # NEGATIVE CONTROL\n"
        b"    if m is None:\n        return \"\"",
        f"{GUARDS}::TestTheBossQuestion::"
        "test_it_leads_with_the_account_not_the_inventory",
    ),
    (
        "R-TG4 — the marker is SPECIFIC, not a fire-on-everything",
        AUDIENCE,
        "the marker returns a constant — every question names a person",
        b"    m = _AUDIENCE.search(question or \"\")\n"
        b"    if m is None:\n        return \"\"",
        b"    m = _AUDIENCE.search(question or \"\")\n"
        b"    return \"my boss\"  # NEGATIVE CONTROL\n"
        b"    if m is None:\n        return \"\"",
        f"{GUARDS}::TestTheAudienceMarker::"
        "test_it_stays_silent_on_every_other_family",
    ),
    (
        "R-TG4 — the inventory is OFFERED, never printed",
        RENDERERS,
        "the evidence-chain suppression is removed; the 614-record chain returns",
        b'        if (bundle.key_facts or {}).get("audience_shape") is not None:\n'
        b'            return "\\n".join(lines).rstrip()',
        b"        if False:  # NEGATIVE CONTROL\n"
        b'            return "\\n".join(lines).rstrip()',
        f"{GUARDS}::TestTheBossQuestion::test_the_inventory_is_offered_never_printed",
    ),
    (
        "R-TG4 — the shape is composed and rendered",
        RENDERERS,
        "the audience branch never fires; lateness-cause renders the inventory",
        b"        if self._render_audience_shape(lines, bundle):\n"
        b"            return\n"
        b'        late = int(kf.get("late_count", 0) or 0)',
        b"        if False:  # NEGATIVE CONTROL\n"
        b"            return\n"
        b'        late = int(kf.get("late_count", 0) or 0)',
        f"{GUARDS}::TestTheBossQuestion",
    ),
    (
        "R-TG4 — the evidence SURVIVES the reshaping",
        INTERP,
        "the shape clears ordered_records instead of suppressing the printing — "
        "the bars go dark and the drill-down has nothing to open",
        b'        bundle.key_facts["audience_shape"] = shape',
        b'        bundle.key_facts["audience_shape"] = shape  # NEGATIVE CONTROL\n'
        b"        bundle.ordered_records = []",
        f"{GUARDS}::TestTheBossQuestion::test_the_evidence_survives_the_reshaping",
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
