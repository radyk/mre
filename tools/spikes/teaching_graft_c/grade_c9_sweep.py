"""Run `sweep_teaching_v3` against the DEMO BOARD and grade RUBRIC axis C9's
MECHANICAL HALF — and only its mechanical half.

Session 4A teaching-graft (c), Item 2. C9 asks whether a planner's model of the
system would be better for having read the answer. Most of that is human-graded
and the RUBRIC amendment says which parts and why. This grades the four checks
a script can honestly make, and REPORTS (never asserts) the two hunts.

  M1  PRINCIPLE PRESENT   — a `teaching` answer carries >=1 LABELLED
                            general-knowledge claim. An answer made entirely of
                            board facts is a recital wearing the depth licence.
  M2  PRINCIPLE ATTACHED  — the same answer ALSO carries >=1 verified or
                            interpretive board claim. THIS CHECKS CO-OCCURRENCE
                            AND NOTHING MORE. Whether the general half is ABOUT
                            the specific half is C9b and is not readable from
                            counts; a green M2 is not evidence for C9b and must
                            never be quoted as any.
  M3  THE DOOR IS REAL    — no `dead-door` finding on a teaching turn. Not a new
                            mechanism: the sidecar already fires every offered
                            follow-up through the parse layer a planner clicking
                            it would hit.
  M4  THE PAIR IS VALID   — both halves of a transfer pair were ANSWERED (not a
                            clarify, not the capability card, not an error). An
                            invalid pair cannot grade transfer and is REPORTED
                            as invalid, never counted as a failure.

  M5  THE ATTEMPT        — R-TG5, added by session (c2). A teaching answer made
                            at least one read OF THIS RUN. This is the thing the
                            ruling actually requires: the ATTEMPT, never the
                            grounding, because a board with no instance of the
                            principle is a fact about the board and not a defect
                            in the answer. `constraint_catalog` and `spec_lookup`
                            DO NOT COUNT — they read the product's own
                            documentation and have never seen this plant, and
                            counting them would let an answer satisfy the check
                            by looking up the manual (measured live at v8's first
                            draft, which did exactly that).

  DISCLOSURE vs SILENCE. M2 stays a co-occurrence count and its bound is
  unchanged. What separates "there was no case and the answer said so" from
  "the answer never looked" is M5 plus M2 read together, and it separates them
  BECAUSE OF THE RULING'S OWN SHAPE: a no-case sentence has to cite the read
  that found nothing (uncited, R-TG1(ii) drops it), so a disclosed no-case lands
  as a board claim and shows M5 green / M2 green, while silence shows M5 red or
  M2 red. Every teaching turn carrying no board claim is additionally REPORTED
  verbatim under `no_board_claim_turns`, because whether a sentence reads as a
  disclosure is a human's call and not a script's.

  CONTROLS — a contracted answer renders no teaching invitation, and a
             non-teaching second-tier answer is not required to carry a
             principle (requiring one of every answer would be C8b's failure
             from the other side).

  HUNTS — reported, not graded. Direction (i) refusals are found by the
          product's OWN constant from `claim_verifier`, and closer firings by
          the turn's own deferred count.

Usage:
  python tools/spikes/teaching_graft_c/grade_c9_sweep.py [schedule_id] [out_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.report import render_sidecar, render_transcript  # noqa: E402
from mre.ai_exam.runner import ExamRunner, RunTarget  # noqa: E402
from mre.ai_exam.script import parse_script  # noqa: E402
from mre.modules.ask_fallback_copy import (  # noqa: E402
    SYNTHESIS_DEFERRED, TEACHING_INVITATION,
)

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "tests" / "ai_exam" / "banks" / "sweep_teaching_v3.txt"

_CLOSER_STEM = SYNTHESIS_DEFERRED.split("{")[0]

#: The transfer pairs, by the FIRST WORDS of each half's question text. Keyed on
#: text rather than on line numbers so an edit to the bank's comments cannot
#: silently re-pair the probes.
PAIRS = [
    ("P1", "what generally decides whether an operation",
           "why cant ORD-000128 op20 start earlier"),
    ("P2", "in general, why does one order running late",
           "why is ORD-000112 late"),
    ("P3", "how does a scheduler decide which of two orders",
           "why is ORD-000252 on CUT-01 when it is"),
    ("P4", "what does an optimality gap actually mean",
           "is this schedule the cheapest one you could find"),
]

#: Questions in the two hunt families — reported, never graded.
HUNT_A_STEMS = ("in general, is $", "explain why machines like",
                "generally speaking, is it normal for an order")
HUNT_B_STEMS = ("compare the three cutting machines",
                "give me a machine by machine breakdown",
                "list every distinct problem")

#: The refusal's own words, from `claim_verifier.verify_claim`.
REFUSAL_MARK = "offered as general knowledge and refused the label because"

#: Answers that mean "I did not answer" — an unanswered half invalidates a pair.
_UNANSWERED_ROUTES = ("clarify",)

#: The two tools that read the PRODUCT rather than the PLANT. R-TG5's attempt is
#: a read of this run; these are the manual. Named as a subtraction from the live
#: enum, so a tool added to the surface counts as a board read the day it lands
#: and nobody has to remember to update a list here.
_DOC_TOOLS = frozenset({"constraint_catalog", "spec_lookup"})


def board_reads(tools) -> list[str]:
    """The reads of THIS RUN among ``tools`` — the manual subtracted."""
    return [t for t in (tools or []) if t not in _DOC_TOOLS]


def classify_teaching_turn(s: dict) -> dict:
    """One teaching turn's mechanical reading, as a pure function of its
    synthesis block — so the branch that separates a DISCLOSED no-case from
    SILENCE can be premise-tested with an injected answer instead of being
    believed because it was written down.

    ``verdict`` is the three-way this session cares about:

      ``grounded``        it read this run AND a board claim landed. Under R-TG5
                          that is either the instance or a no-case disclosure
                          carrying the read that found nothing — the ruling makes
                          the disclosure cite, so both shapes arrive here, and
                          telling them apart is a human's read of the sentence.
      ``no-board-claim``  it read this run and nothing survived. Reported
                          verbatim; this is where a silent cut hides.
      ``silent``          it never read this run at all. The manual does not
                          count (see ``_DOC_TOOLS``).
    """
    reads = board_reads(s.get("tools"))
    board = int(s.get("verified") or 0) + int(s.get("interpretive") or 0)
    return {"board_reads": reads, "board_claims": board,
            "m1_principle": int(s.get("general_knowledge") or 0) >= 1,
            "m2_attached": board >= 1,
            "m5_attempt": bool(reads),
            "verdict": ("grounded" if reads and board
                        else "no-board-claim" if reads else "silent")}


def _stem(q: str) -> str:
    return (q or "").strip().lower()


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        ROOT / "tests" / "ai_exam" / "sweeps" / "2026-08-04-teaching-c")
    out_dir.mkdir(parents=True, exist_ok=True)

    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    runner = ExamRunner(target, per_question_timeout=180.0,
                        session_id="sweep-teaching-v3")
    result = runner.run(parse_script(BANK.read_text(encoding="utf-8")))
    (out_dir / "sweep_teaching_v3.txt").write_text(
        render_transcript(result), encoding="utf-8")
    (out_dir / "sweep_teaching_v3.sidecar.json").write_text(
        render_sidecar(result), encoding="utf-8")

    fams = {"m1_principle": [0, 0], "m2_attached": [0, 0], "m3_real_door": [0, 0],
            "m4_pair_valid": [0, 0], "m5_attempt": [0, 0], "controls": [0, 0]}
    problems: list[str] = []
    reported: dict = {"direction_i_refusals": [], "closer_firings": [],
                      "invalid_pairs": [], "no_board_claim_turns": [],
                      "teaching_turns": []}

    def _check(fam: str, ok: bool, note: str) -> None:
        fams[fam][1] += 1
        if ok:
            fams[fam][0] += 1
        else:
            problems.append(f"[{fam}] {note}")

    def _find(prefix: str):
        """Match a pair half by PREFIX. Keyed on the question's opening words
        rather than on a line number, so editing this bank's comments cannot
        silently re-pair the probes — and on a prefix rather than on equality,
        because the pair table would otherwise have to hold every question
        twice, and the copy that drifts is always the one nobody reads."""
        p = _stem(prefix)
        for t in result.turns:
            if _stem(t.question).startswith(p):
                return t
        return None

    for t in result.turns:
        q, answer = _stem(t.question), (t.answer or "")
        s = t.synthesis or {}
        intent = ((t.parse or {}).get("intent") or "")
        deferred = int(s.get("deferred") or 0)

        # -- the hunts: REPORTED, never graded ------------------------------
        if any(q.startswith(x) for x in HUNT_A_STEMS):
            if REFUSAL_MARK in answer:
                reported["direction_i_refusals"].append(
                    {"line": t.lineno, "question": t.question})
            continue
        if any(q.startswith(x) for x in HUNT_B_STEMS):
            if deferred:
                reported["closer_firings"].append(
                    {"line": t.lineno, "question": t.question,
                     "deferred": deferred, "closer_rendered": _CLOSER_STEM in answer})
            continue

        # -- controls --------------------------------------------------------
        if q.startswith("where is ord-000040"):
            _check("controls", TEACHING_INVITATION not in answer and not s,
                   f"line {t.lineno}: a contracted answer carries teaching machinery")
            continue
        if q.startswith("what is the single biggest cause"):
            _check("controls", TEACHING_INVITATION not in answer,
                   f"line {t.lineno}: a non-teaching answer carries the "
                   f"teaching invitation")
            continue

        # -- M1/M2/M3 on the TEACHING half of each pair ----------------------
        if intent == "teaching":
            c = classify_teaching_turn(s)
            _check("m1_principle", c["m1_principle"],
                   f"line {t.lineno}: a teaching answer with no labelled "
                   f"general-knowledge claim — a recital wearing the licence")
            _check("m2_attached", c["m2_attached"],
                   f"line {t.lineno}: a teaching answer with no board claim "
                   f"beside the principle (co-occurrence only — see the RUBRIC)")
            _check("m3_real_door",
                   not any(f.kind == "dead-door" for f in t.findings),
                   f"line {t.lineno}: the invitation offered a door into a wall")
            _check("m5_attempt", c["m5_attempt"],
                   f"line {t.lineno}: a teaching answer that never read this run "
                   f"(tools={s.get('tools') or []}) — R-TG5's attempt")
            reported["teaching_turns"].append(
                {"line": t.lineno, "question": t.question, **c,
                 "tools": list(s.get("tools") or []),
                 "general_knowledge": int(s.get("general_knowledge") or 0),
                 "cut": int(s.get("failed_and_cut") or 0)})
            if not c["m2_attached"]:
                # REPORTED, not judged. A no-case answer that disclosed and a
                # silent one both land here; which is which is read, not counted.
                reported["no_board_claim_turns"].append(
                    {"line": t.lineno, "question": t.question,
                     "verdict": c["verdict"], "board_reads": c["board_reads"],
                     "answer": answer})

    # -- M4: pair validity ---------------------------------------------------
    for tag, q1, q2 in PAIRS:
        t1, t2 = _find(q1), _find(q2)
        missing = [n for n, t in (("Q1", t1), ("Q2", t2)) if t is None]
        if missing:
            _check("m4_pair_valid", False,
                   f"{tag}: {'/'.join(missing)} not found in the transcript")
            continue
        bad = []
        for name, t in (("Q1", t1), ("Q2", t2)):
            if t.error:
                bad.append(f"{name} errored: {t.error}")
            elif t.route in _UNANSWERED_ROUTES:
                bad.append(f"{name} routed to {t.route}")
        _check("m4_pair_valid", not bad, f"{tag}: INVALID PAIR — {'; '.join(bad)}")
        if bad:
            reported["invalid_pairs"].append({"pair": tag, "why": bad})

    tot = result.synthesis_totals()
    graded, met = result.graded()
    print(f"\nsweep: {len(result.turns)} turn(s) against {schedule_id}")
    print(f"       synthesis answers={tot['answers']} "
          f"general_knowledge={tot['general_knowledge']} "
          f"verified={tot['verified']} interpretive={tot['interpretive']} "
          f"cut={tot['failed_and_cut']} deferred={tot.get('deferred', 0)}")
    print(f"       routing expectations: {met}/{graded}")
    for fam, (ok, total) in fams.items():
        print(f"       {fam:16s} {ok}/{total}")
    print(f"\n       HUNT A — direction (i) refusals observed: "
          f"{len(reported['direction_i_refusals'])}")
    print(f"       HUNT B — closer firings observed:         "
          f"{len(reported['closer_firings'])}")
    print(f"       teaching turns with NO board claim (read, not counted): "
          f"{len(reported['no_board_claim_turns'])}")
    for p in problems:
        print("  MISS " + p)
    (out_dir / "GRADE-C9.json").write_text(json.dumps(
        {"schedule": schedule_id, "turns": len(result.turns),
         "routing": {"graded": graded, "met": met},
         "families": {k: {"met": v[0], "of": v[1]} for k, v in fams.items()},
         "synthesis": tot, "reported": reported, "problems": problems},
        indent=2), encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
