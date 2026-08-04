"""NEGATIVE CONTROL FOR R-TG5: did rule 14 do it, or did the wind change?

Session 4A teaching-graft (c2). The after-measurement says teaching answers now
read the board. A guard cannot prove that — the guards in
`tests/test_teaching_reads_board.py` prove the rule is IN the artifact and that
nothing gates it, which is a different claim. The only way to find out whether
the RULE moved the measurement is to take it out and look (4B.28 §5a.123, from
the other side).

So: the SAME four transfer-pair teaching questions, twice — once on the shipped
v8 and once with **rule 14 physically excised** and nothing else changed. If the
control arm returns to session (c)'s measured shape (a labelled principle, no
board claim, often no read of this run at all) on at least one pair, the rule is
what moved it.

WHAT THIS CANNOT PROVE, AND THE REPORT SAYS SO. This is a live model on both
arms. Session (c) measured direction (i) firing twice in a hunt and zero times in
two sweep runs of the same probe, so turn-to-turn variance in this tier is
established and is not small. A control arm that reproduces (c)'s shape on some
pairs and not others is the honest outcome to report, not a result to re-roll
until it is clean. The COMMITTED before-sweep stays the baseline of record.

THE PROMPT IS RESTORED IN A `finally` AND THE RESTORE IS ASSERTED BYTE-IDENTICAL
by sha256 — this edits a GOVERNED ARTIFACT, and a spike that left one modified
would be worse than any measurement it produced.

Usage:  python tools/spikes/teaching_graft_c2/rule14_control.py [schedule_id]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from mre.env_local import load_env_local

load_env_local()

from mre.ai_exam.runner import RunTarget  # noqa: E402
from mre.modules.interpreter import forget_deliveries, run_ask  # noqa: E402
from mre.modules.question_parser import QuestionParser  # noqa: E402
from mre.modules.renderers import TemplateRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
PROMPT = ROOT / "src" / "mre" / "modules" / "synthesis_prompt.md"

#: sweep_teaching_v3's four Q1s — the transfer pairs' teaching halves, verbatim.
PROBES = [
    "what generally decides whether an operation can be moved earlier on a "
    "board like this one",
    "in general, why does one order running late tend to make other orders "
    "late as well",
    "how does a scheduler decide which of two orders competing for the same "
    "machine goes first",
    "what does an optimality gap actually mean and how should i read one",
]

DOC_TOOLS = frozenset({"constraint_catalog", "spec_lookup"})


def _excise_rule14(raw: bytes) -> bytes:
    """Rule 14 -> nothing, newline-agnostically.

    The repo mixes line endings PER FILE (4A teaching-graft (a)'s harness
    lesson), so the anchors are matched against a normalised copy and the result
    is re-encoded with the file's own ending.
    """
    text = raw.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    flat = text.replace("\r\n", "\n")
    start = flat.index("\n14. A QUESTION THAT ASKS TO BE TAUGHT") + 1
    cut = flat[:start].rstrip("\n") + "\n"
    assert "14. A QUESTION THAT ASKS" not in cut, "rule 14 survived the excision"
    return cut.replace("\n", eol).encode("utf-8")


def _run_arm(label: str, target, parser, renderer) -> list[dict]:
    from mre.modules.synthesizer import Synthesizer
    explainer = target.build_vocab()._ex
    synth = Synthesizer()                      # re-loads the prompt from disk
    has14 = "14. A QUESTION THAT ASKS" in PROMPT.read_text(encoding="utf-8")
    print(f"\n{'#' * 78}\n# ARM {label} — prompt v{synth.prompt_version}, "
          f"rule 14 present: {has14}\n{'#' * 78}")
    rows = []
    for q in PROBES:
        forget_deliveries("tg5-control")
        r = run_ask(explainer, q, parser=parser, synthesizer=synth,
                    document=target.document, session_id="tg5-control")
        s = r.synthesis
        if s is None:
            print(f"  [{label}] {q[:48]!r} -> {r.route} (no synthesis)")
            rows.append({"arm": label, "q": q, "route": r.route})
            continue
        c = s.counts()
        tools = [call.tool for call in (s.tool_calls or [])]
        reads = [t for t in tools if t not in DOC_TOOLS]
        board = c.get("verified", 0) + c.get("interpretive", 0)
        rows.append({"arm": label, "q": q, "route": r.route, "tools": tools,
                     "board_reads": reads, "board_claims": board,
                     "general_knowledge": c.get("general_knowledge", 0),
                     "cut": c.get("failed_and_cut", 0),
                     "kept": len(s.claims),
                     "text": renderer.render(r.bundle)})
        print(f"  [{label}] reads={reads} board={board} "
              f"gk={c.get('general_knowledge', 0)} cut={c.get('failed_and_cut', 0)} "
              f" {q[:44]!r}")
    return rows


def _tally(rows, arm):
    got = [r for r in rows if r["arm"] == arm and "board_claims" in r]
    return {
        "n": len(got),
        "read_this_run": sum(1 for r in got if r["board_reads"]),
        "carried_board_claim": sum(1 for r in got if r["board_claims"]),
        "board_claims": [r["board_claims"] for r in got],
        "reads": [len(r["board_reads"]) for r in got],
    }


def main() -> int:
    schedule_id = sys.argv[1] if len(sys.argv) > 1 else "rolling-db5395dc-2ae"
    target = RunTarget.from_schedule(ROOT / "_data", schedule_id)
    parser, renderer = QuestionParser(), TemplateRenderer()
    if not parser.available:
        print("PARSER UNAVAILABLE — nothing measured.")
        return 2

    original = PROMPT.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    rows = _run_arm("v8 (shipped)", target, parser, renderer)
    try:
        PROMPT.write_bytes(_excise_rule14(original))
        rows += _run_arm("no rule 14 (control)", target, parser, renderer)
    finally:
        PROMPT.write_bytes(original)
    after = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    assert after == before, f"RESTORE IS NOT BYTE-IDENTICAL ({before} -> {after})"

    shipped, control = _tally(rows, "v8 (shipped)"), _tally(rows, "no rule 14 (control)")
    print(f"\n{'=' * 78}\nSUMMARY (restore byte-identical: {after == before}; "
          f"sha256 {after[:16]}…)")
    for name, t in (("v8 (shipped)", shipped), ("no rule 14", control)):
        print(f"  {name:<20} read this run {t['read_this_run']}/{t['n']}   "
              f"board claim {t['carried_board_claim']}/{t['n']}   "
              f"per-probe board={t['board_claims']}")
    out = ROOT / "tests" / "ai_exam" / "sweeps" / "2026-08-04-teaching-c2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "rule14-control.json").write_text(json.dumps(
        {"schedule": schedule_id, "restore_sha256": after,
         "restore_identical": after == before,
         "shipped": shipped, "control": control, "rows": rows}, indent=2),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
