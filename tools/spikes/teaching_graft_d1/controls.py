"""THE NEGATIVE CONTROLS — Session 4A teaching-graft (d.1).

    python tools/spikes/teaching_graft_d1/controls.py

Each control PHYSICALLY REVERTS one mechanism under `src/`, runs the tests that
are supposed to notice, restores the file, and asserts the restore is
BYTE-IDENTICAL by sha256. A guard that has never been seen to fail is not a
guard (4A.y's harness lesson; 4B.28 §5a.123 for the other half — a control that
calls past the broken line proves nothing, so every anchor below is on the line
that actually decides).

TWO THINGS THIS HARNESS DOES BECAUSE EARLIER ONES DID NOT:

  * it writes with `newline=""` after reading with `read_text`, because this repo
    mixes line endings PER FILE (`claim_verifier.py` is pure LF, `renderers.py`
    pure CRLF) and `write_text`'s default newline translation silently rewrote a
    whole file the first time a session tried this (4A.y);
  * it asserts the sha256 of the restored bytes against the sha256 taken before
    the edit, so a restore that did not restore is a loud failure rather than a
    clean-looking git status nobody re-read.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Control:
    name: str
    file: str
    anchor: str          # the exact bytes that decide
    broken: str          # what to put there instead
    tests: str           # what must go RED
    green: str = ""      # what must stay GREEN (the "it is a control" half)


CONTROLS = [
    Control(
        name="(a) the store key loses the schedule",
        file="src/mre/modules/interpreter.py",
        anchor='    return (session_id, schedule_id or "")',
        broken='    return (session_id, "")   # NEGATIVE CONTROL: key on the session alone',
        tests="tests/test_carried_answer_state.py::TestStoreKey "
              "tests/test_carried_answer_state.py::TestPreviousVersionSentence",
        green="tests/test_carried_answer_state.py::TestDeafGate",
    ),
    Control(
        name="(b) the drill-down loses its wire",
        file="src/mre/modules/interpreter.py",
        anchor='            params["prior"] = (None if params["claim"] is not None\n'
               '                               else answer_memory.last(session_id, schedule_id))',
        broken='            params["prior"] = None   # NEGATIVE CONTROL: nothing is carried',
        tests="tests/test_carried_answer_state.py::TestDrillDownWired",
        green="tests/test_carried_answer_state.py::TestDrillDownRefusal",
    ),
    Control(
        name="(c) the findings[0] default comes back",
        file="src/mre/modules/explainer.py",
        anchor="        if pick is None:\n"
               "            return self._prove_it_bundle(target or \"Tell me more.\", claim, None,\n"
               "                                         prior, prior_elsewhere=prior_elsewhere)",
        broken="        if pick is None:   # NEGATIVE CONTROL: assert a default\n"
               "            _f = sorted(self._index.all_findings(),\n"
               "                        key=lambda r: r.get('seq', 0))\n"
               "            pick = _f[0] if _f else None\n"
               "        if pick is None:\n"
               "            return self._prove_it_bundle(target or \"Tell me more.\", claim, None,\n"
               "                                         prior, prior_elsewhere=prior_elsewhere)",
        tests="tests/test_carried_answer_state.py::TestDrillDownRefusal",
        green="tests/test_carried_answer_state.py::TestStoreKey",
    ),
    Control(
        name="(d) the prove-it branch is decided by the record count again",
        file="src/mre/modules/explainer.py",
        anchor='        if (prior_dict.get("route") or "") in PRODUCT_META_ROUTES:\n'
               "            return ProveItCase.PRODUCT_META\n"
               "        return ProveItCase.EMPTY_READ",
        broken="        return ProveItCase.PRODUCT_META   # NEGATIVE CONTROL: one sentence for both",
        tests="tests/test_carried_answer_state.py::TestEmptyRead "
              "tests/test_second_question.py::TestDrillDownAfterAnAnswerThatCitesNothing",
        green="tests/test_second_question.py::TestDrillDownAfterCapabilityCopy",
    ),
    Control(
        name="(e) a model-recovered subject reports UTTERANCE again",
        file="src/mre/modules/question_parser.py",
        anchor="                source = SubjectSource.CONVERSATION if ref else source",
        broken="                source = SubjectSource.UTTERANCE if ref else source"
               "   # NEGATIVE CONTROL",
        tests="tests/test_carried_answer_state.py::TestConversationSource",
        green="tests/test_carried_answer_state.py::TestDeafGate",
    ),
    Control(
        name="(f) the deaf rider stops reading followup_of",
        file="src/mre/modules/interpreter.py",
        anchor='             and not (deepening and (row.get("route") or "") == route)]',
        broken="             ]   # NEGATIVE CONTROL: the gate is gone",
        tests="tests/test_carried_answer_state.py::TestDeafGate::"
              "test_a_deepen_follow_up_is_not_told_we_do_not_understand",
        green="tests/test_carried_answer_state.py::TestDeafGate::"
              "test_the_P6_T7_true_positive_STILL_FIRES "
              "tests/test_carried_answer_state.py::TestDeafGate::"
              "test_the_true_positive_fires_even_when_the_parse_calls_it_a_deepen",
    ),
    Control(
        # THE OTHER SIDE OF THE SAME MECHANISM, and the one the sweep caught.
        # A gate that reads `followup_of` alone swallows the true positive; this
        # reverts to exactly that and the true-positive test must go red.
        name="(f2) the deaf gate reads followup_of ALONE (the first draft)",
        file="src/mre/modules/interpreter.py",
        anchor='             and not (deepening and (row.get("route") or "") == route)]',
        broken="             and not deepening]   # NEGATIVE CONTROL: the first draft",
        tests="tests/test_carried_answer_state.py::TestDeafGate::"
              "test_the_true_positive_fires_even_when_the_parse_calls_it_a_deepen",
        green="tests/test_carried_answer_state.py::TestDeafGate::"
              "test_a_deepen_follow_up_is_not_told_we_do_not_understand",
    ),
    Control(
        name="(g) the harness records an errored turn again",
        file="src/mre/ai_exam/runner.py",
        anchor="                if error is None:\n"
               "                    history.append({",
        broken="                if True:   # NEGATIVE CONTROL: unconditional, as before\n"
               "                    history.append({",
        tests="tests/test_carried_answer_state.py::TestHarnessParity",
        green="tests/test_carried_answer_state.py::TestStoreKey",
    ),
]


def _pytest(selection: str) -> int:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", "-x",
         *selection.split()],
        cwd=ROOT, capture_output=True, text=True).returncode


def run(control: Control) -> bool:
    path = ROOT / control.file
    original = path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    # THE MIXED-LINE-ENDING HAZARD, FROM THE OTHER SIDE. 4A teaching-graft (a)
    # met it on the WRITE (`write_text` translated newlines and rewrote a whole
    # file); this harness met it on the MATCH. `explainer.py` is pure CRLF and
    # `interpreter.py` pure LF, so an LF-joined multi-line anchor silently found
    # nothing in half the files — and the first run of these controls reported
    # (c) and (d) as ANCHOR NOT FOUND rather than passing falsely, which is the
    # only reason it was noticed. The anchor is translated to the file's own
    # ending; a file that mixes them internally is left alone and reported.
    eol = "\r\n" if b"\r\n" in original else "\n"
    anchor = control.anchor.replace("\n", eol)
    broken = control.broken.replace("\n", eol)
    control = Control(control.name, control.file, anchor, broken,
                      control.tests, control.green)
    if control.anchor not in text:
        print(f"  !! ANCHOR NOT FOUND in {control.file} — the control proves "
              f"nothing and is reported as a failure, not skipped")
        return False
    try:
        # newline="" : this repo mixes line endings per file and write_text's
        # default translation would rewrite the whole thing.
        path.write_text(text.replace(control.anchor, control.broken, 1),
                        encoding="utf-8", newline="")
        assert path.read_bytes() != original, "the edit did not take"
        red = _pytest(control.tests)
        green = _pytest(control.green) if control.green else 0
    finally:
        path.write_bytes(original)
    restored = hashlib.sha256(path.read_bytes()).hexdigest()
    assert restored == digest, f"RESTORE IS NOT BYTE-IDENTICAL for {control.file}"
    ok = red != 0 and green == 0
    print(f"  target tests: {'RED (good)' if red else 'GREEN — THE GUARD DOES NOT SEE IT'}")
    if control.green:
        print(f"  control tests: {'GREEN (good)' if green == 0 else 'RED — not a control, a smoke test'}")
    print(f"  restore sha256 {restored[:16]} == {digest[:16]}  OK")
    return ok


if __name__ == "__main__":
    results = []
    for c in CONTROLS:
        print(f"\n{c.name}\n  {c.file}")
        results.append((c.name, run(c)))
    print("\n" + "=" * 60)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    sys.exit(0 if all(ok for _, ok in results) else 1)
