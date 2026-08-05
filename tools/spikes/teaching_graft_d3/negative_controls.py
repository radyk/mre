"""(d.3) negative controls — prove R-TE1 and rider R2 CAN go red.

Session 4A teaching-graft (d.3). The harness discipline is (e)'s, (e2)'s and
(d.2)'s, inherited whole: BYTES, per-file line-ending detection, ANCHOR NOT
FOUND is a FAILURE and never a skip, every guard proven GREEN AT HEAD before its
seam is reverted, every restore verified byte-identical by sha256.

    python tools/spikes/teaching_graft_d3/negative_controls.py

EACH CONTROL AIMS AT THE SEAM, AND (d.2) IS WHY THEY ALSO AIM AT CODE. Two of
that session's twelve stayed green on the first attempt and neither was the
seam's fault: one guard searched a whole file and passed on the explanatory
COMMENT beside the line, the other searched a function's source text and did the
same. Where a guard here reads source, it reads the AST or a function body with
comments stripped.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GLOSS = ROOT / "src/mre/modules/glossary.py"
INTERP = ROOT / "src/mre/modules/interpreter.py"
REND = ROOT / "src/mre/modules/renderers.py"
CV = ROOT / "src/mre/modules/claim_verifier.py"
PARSE = ROOT / "src/mre/contracts/parse.py"

G = "tests/test_glossary.py"
CRLF, LF = b"\r\n", b"\n"

#: (name, file, anchor, replacement, the pytest selection that MUST go red)
CONTROLS: list[tuple] = [
    (
        "R-TE1(1) — the trigger is SCHEDULE-scoped (the rebind case)",
        INTERP,
        # THE DEFECT SHAPE, not a cosmetic edit. The first version of this
        # control keyed `seen` on ("session", "") while `remember` still wrote
        # the real schedule, so the lookup missed and the guard stayed GREEN —
        # a control that reverts something the guard does not depend on, which
        # is (d.2)'s lesson caught once more. What R-MT1's key actually forbids
        # is a term from ANOTHER board confirming the intent, so that is what
        # this reverts to: a `seen` that ignores the schedule entirely.
        b"        key = _carry_key(session_id, schedule_id)\n"
        b"        return frozenset(self._by_session.get(key, ()) if key is not None else ())\n",
        b"        return frozenset(t for (s, _sched), v in self._by_session.items()\n"
        b"                         if s == session_id for t in v)\n",
        G + "::TestTermMemory::test_it_is_SCHEDULE_scoped",
    ),
    (
        "R-TE1(1) — the ONE clear clears the fourth store",
        INTERP,
        b"        TERM_MEMORY.forget(session_id)\n",
        b"",
        G + "::TestTermMemory::test_the_ONE_clear_clears_it",
    ),
    (
        "R-TE1(1) — terms are read from the RENDERED answer",
        INTERP,
        b"    found = terms_in(answer or \"\")\n",
        b"    found = frozenset()\n",
        G + "::TestTermMemory::test_remember_terms_reads_the_RENDERED_text",
    ),
    (
        "R-TE1(2) — the glossary answer is AUTHORED, never the model's to reword",
        REND,
        b"        \"term_explanation\",\n        # Session 4B.15 Item 3: an attribute lookup is a VALUE and its SOURCE.\n",
        b"        # Session 4B.15 Item 3: an attribute lookup is a VALUE and its SOURCE.\n",
        G + "::TestTheAnswerIsAuthoredAndCited::"
        "test_the_route_is_authored_copy_and_never_the_models_to_reword",
    ),
    (
        "R-TE1(2) — a citation is PRINTED beside the definition",
        REND,
        b"                    lines.append(f\"  [{target}] {c.get('phrase')}\")\n",
        b"                    pass\n",
        G + "::TestTheAnswerIsAuthoredAndCited::"
        "test_the_rendered_answer_prints_the_definition_and_a_citation",
    ),
    (
        "R-TE1(2) — a MISSING run figure is said, not swallowed",
        REND,
        b"                        lines.append(\n"
        b"                            \"This plan doesn't carry that figure, so the \"\n"
        b"                            \"definition above is all I can show you for it.\")\n",
        b"                        pass\n",
        G + "::TestTheAnswerIsAuthoredAndCited::"
        "test_a_missing_run_figure_is_SAID_not_swallowed",
    ),
    (
        "R-TE1(2) — a PRESENT run figure is voiced",
        REND,
        b"    if kind == \"portfolio\" and isinstance(value, dict):\n",
        b"    if False:\n",
        G + "::TestTheAnswerIsAuthoredAndCited::"
        "test_a_present_run_figure_is_voiced_in_a_sentence",
    ),
    (
        "R-TE1(3) — it is a CONTRACTED route, not a second-tier intent",
        PARSE,
        b"    TERM_EXPLANATION = \"term-explanation\"\n",
        b"    TERM_EXPLANATION = \"term-explanation-unrouted\"\n",
        G + "::TestTheIntentIsWiredLikeARoute",
    ),
    (
        "R-TE1(4) — a moved citation target fails a TEST, not a memory",
        GLOSS,
        b"            (CITE_RULING, \"R-BK1\",\n",
        b"            (CITE_RULING, \"R-NOT-A-RULING\",\n",
        G + "::TestEveryCitationResolves",
    ),
    (
        "R-TE1 — a word we do not define is NOT resolved to a near neighbour",
        GLOSS,
        b"    for entry, rx in _COMPILED:\n        if rx.search(text):\n            return entry\n    return None\n",
        b"    for entry, rx in _COMPILED:\n        if rx.search(text):\n            return entry\n    return GLOSSARY[0]\n",
        G + "::TestTermRecognition::test_a_word_we_do_not_define_resolves_to_nothing",
    ),
    (
        "rider R2 — the POSTPOSED DEICTIC widening",
        CV,
        b"     r\"|\\b(?:product|system|engine|scheduler|solver)s?\\s+like\\s+th(?:is|ese)\\s+\"\n",
        b"     r\"|\\bNOTHINGMATCHESTHIS\\b(?# \"\n",
        "tests/test_floor_truth_e2.py::TestTheWidenedProductBehaviorPredicate",
    ),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _green(node: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-x"],
        cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    print("(d.3) NEGATIVE CONTROLS - each seam reverted, its guard must go RED")
    print("=" * 74)
    failures = 0
    for name, path, anchor, replacement, node in CONTROLS:
        digest = _sha(path)
        before = path.read_bytes()
        a, r = anchor, replacement
        if CRLF in before:
            a, r = a.replace(LF, CRLF), r.replace(LF, CRLF)
        if a not in before:
            print(f"  ANCHOR NOT FOUND   {name}\n"
                  f"                     in {path.relative_to(ROOT)}")
            failures += 1
            continue
        if not _green(node):
            print(f"  NOT GREEN AT HEAD  {name}\n                     {node}")
            failures += 1
            continue
        path.write_bytes(before.replace(a, r, 1))
        try:
            went_red = not _green(node)
        finally:
            path.write_bytes(before)
        restored = _sha(path) == digest
        print(f"  {'RED (good)' if went_red else 'STILL GREEN - FAILED':<22}{name}")
        print(f"  {'restore byte-identical: ' + ('yes' if restored else 'NO'):<22}"
              f"sha256 {digest[:16]}")
        if not went_red or not restored:
            failures += 1
    print("=" * 74)
    print(f"{len(CONTROLS) - failures}/{len(CONTROLS)} controls proven red, "
          "every restore byte-identical")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
