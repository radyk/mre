"""S-02 / S-03 negative controls — prove each seam of this session CAN go red.

Same harness discipline as (e)'s and (e2)'s, and for the same reasons: it works
in BYTES, it DETECTS the file's line ending rather than assuming it (this repo
mixes them per file — `api/app.py` is LF where every other file touched here is
CRLF), ANCHOR NOT FOUND is a FAILURE and never a skip, every guard is proven
GREEN AT HEAD before its seam is reverted, and every restore is verified
byte-identical by sha256.

    python tools/spikes/certificate_contract/negative_controls.py

EACH CONTROL AIMS AT A SEAM, NOT A CALLER. NC1 and NC6 revert the SAME fix at
its TWO exits independently, so a verdict record that landed on only one of the
gate's paths cannot pass — which is the shape of the gap it closes, and 4B.14
§5a.34's rule (a defect class fixed at one seam is not fixed) applied forward.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONF = ROOT / "src/mre/modules/conformance.py"
EXPL = ROOT / "src/mre/modules/explainer.py"
REND = ROOT / "src/mre/modules/renderers.py"
REP = ROOT / "src/mre/reporter/reporter.py"

CRLF = b"\r\n"
LF = b"\n"

T = "tests/test_certificate_contract.py"

#: (name, file, anchor, replacement, the tests that MUST go red)
CONTROLS: list[tuple] = [
    (
        "NC1 - the verdict emission at the CASCADE exit",
        CONF,
        b"        emit_gate_verdict(\n"
        b"            reporter, subjects=_submission_subject(), grade=grade,\n",
        b"        _skip = emit_gate_verdict\n"
        b"        _noop(\n"
        b"            reporter, subjects=_submission_subject(), grade=grade,\n",
        T + "::test_an_accepted_submission_reports_its_own_grade",
    ),
    (
        "NC6 - the verdict emission at the INTAKE-REFUSAL exit",
        CONF,
        b"        emit_gate_verdict(\n"
        b"            reporter, subjects=[subject], grade=\"REJECTED\", costing_grade=\"C0\",\n",
        b"        _skip = emit_gate_verdict\n"
        b"        _noop(\n"
        b"            reporter, subjects=[subject], grade=\"REJECTED\", costing_grade=\"C0\",\n",
        T + "::test_the_intake_refusal_also_reports_a_verdict",
    ),
    (
        "NC2 - the route's evidence-FIRST order",
        EXPL,
        b"        from_evidence = self._certificate_from_evidence()\n"
        b"        if from_evidence is not None:\n"
        b"            return from_evidence\n",
        b"        from_evidence = None\n",
        T + "::test_the_route_grounds_on_the_evidence_record",
    ),
    (
        "NC3 - the removed signing sentence (the copy as it stood)",
        REND,
        b'                + (\"; the grade is computed from those rule outcomes.\"\n'
        b'                   if derived and checked else \".\"))\n',
        b'                + \", and it is unsigned \\u2014 nobody has countersigned it.\")\n',
        T + "::test_the_certificate_body_says_nothing_about_signing",
    ),
    (
        # THE ANCHOR CARRIES TWO FOLLOWING LINES ON PURPOSE. `subjects=subjects
        # or [],` appears in `record_metric` FIRST, so the obvious one-line
        # anchor reverted the wrong verb and this control STAYED GREEN on its
        # first run — (d.2)'s lesson exactly: a control that reverts something
        # the guard does not depend on proves nothing. `message=message or
        # status_text` is unique to `record_event`.
        "NC4 - Event subjects (the common envelope)",
        REP,
        b"            subjects=subjects or [],\n"
        b"            tier=tier,\n"
        b"            message=message or status_text,\n",
        b"            subjects=[],\n"
        b"            tier=tier,\n"
        b"            message=message or status_text,\n",
        T + "::test_the_verdict_carries_the_common_envelope",
    ),
    (
        "NC5 - the artifact digest taken from the FILE, not the string",
        CONF,
        b"        digest = hashlib.sha256(path.read_bytes()).hexdigest()\n",
        b"        digest = hashlib.sha256(\n"
        b"            json.dumps(certificate, indent=2, default=str).encode(\"utf-8\")\n"
        b"        ).hexdigest()\n",
        T + "::test_the_certificate_artifact_is_registered_with_its_hash",
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
    print("S-02 / S-03 NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 76)
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
    print("=" * 76)
    print(f"{len(CONTROLS) - failures}/{len(CONTROLS)} controls proven red, "
          f"every restore byte-identical")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
