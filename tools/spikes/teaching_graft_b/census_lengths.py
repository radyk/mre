"""CENSUS (b) — the answer-length distribution, per register and per route.

Session 4A teaching-graft (b). R-TG3's short budget is a CAP, and a cap chosen
by taste is a style preference wearing a ruling's clothes. This measures what
the product actually ships today, over every committed exam sweep in
``tests/ai_exam/sweeps/``, so the number in the ruling is chosen FROM THE DATA.

WHAT IT COUNTS. The rendered answer block of every turn — the ``  A:`` block of
the transcript, dedented — minus the two lines that are never content:

  * the ``[rendered by: ...]`` footer, which every answer carries; and
  * blank lines.

The unit is the CONTENT LINE, not the word and not the character. That is
deliberate: what a planner sees as "all that" is a wall of lines, the cap has to
be enforceable at a seam that counts something the renderer can count before it
writes, and a claim is a line. Characters are reported beside it so a session
that later wants a byte cap has the distribution rather than an anecdote.

Usage:  python tools/spikes/teaching_graft_b/census_lengths.py [out.json]
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SWEEPS = ROOT / "tests" / "ai_exam" / "sweeps"

_Q = re.compile(r"^Q\[(\d+)\]:\s*(.*)$")
_META = re.compile(r"^  route=(\S+)\s+source=(\S+)\s+conf=(\S+)\s+register=(\S+)")
_RULE = "-" * 72


class Turn:
    def __init__(self, question: str) -> None:
        self.question = question
        self.route = ""
        self.register = ""
        self.answer: list[str] = []

    @property
    def content_lines(self) -> list[str]:
        out = []
        for ln in self.answer:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("[rendered by:"):
                continue
            out.append(s)
        return out


def parse_transcript(path: Path) -> list[Turn]:
    turns: list[Turn] = []
    cur: Turn | None = None
    in_answer = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _Q.match(raw)
        if m:
            cur = Turn(m.group(2))
            turns.append(cur)
            in_answer = False
            continue
        if cur is None:
            continue
        if raw.startswith(_RULE):
            in_answer = False
            cur = None
            continue
        mm = _META.match(raw)
        if mm:
            cur.route, cur.register = mm.group(1), mm.group(4)
            continue
        if raw == "  A:":
            in_answer = True
            continue
        if in_answer:
            if raw.startswith("  >> sidecar["):
                in_answer = False
                continue
            cur.answer.append(raw[4:] if raw.startswith("    ") else raw)
    return turns


def _stats(xs: list[int]) -> dict:
    if not xs:
        return {"n": 0}
    xs = sorted(xs)
    return {
        "n": len(xs),
        "min": xs[0],
        "p25": xs[max(0, int(round(0.25 * (len(xs) - 1))))],
        "median": statistics.median(xs),
        "p75": xs[max(0, int(round(0.75 * (len(xs) - 1))))],
        "p90": xs[max(0, int(round(0.90 * (len(xs) - 1))))],
        "max": xs[-1],
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).with_name("census_lengths.json"))

    by_register: dict[str, list[int]] = defaultdict(list)
    by_route: dict[str, list[int]] = defaultdict(list)
    chars_by_register: dict[str, list[int]] = defaultdict(list)
    rows: list[dict] = []

    for tpath in sorted(SWEEPS.rglob("*.txt")):
        if not tpath.read_text(encoding="utf-8", errors="replace").startswith(
                "AI EXAM TRANSCRIPT"):
            continue
        for t in parse_transcript(tpath):
            if not t.register:
                continue
            lines = t.content_lines
            n = len(lines)
            chars = sum(len(x) for x in lines)
            by_register[t.register].append(n)
            by_route[t.route].append(n)
            chars_by_register[t.register].append(chars)
            rows.append({"sweep": tpath.parent.name, "question": t.question,
                         "route": t.route, "register": t.register,
                         "lines": n, "chars": chars})

    report = {
        "turns": len(rows),
        "sweeps": sorted({r["sweep"] for r in rows}),
        "by_register": {k: _stats(v) for k, v in sorted(by_register.items())},
        "by_register_chars": {k: _stats(v)
                              for k, v in sorted(chars_by_register.items())},
        "by_route": {k: _stats(v) for k, v in sorted(by_route.items())
                     if len(v) >= 3},
        "longest": sorted(rows, key=lambda r: -r["lines"])[:15],
    }
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"turns: {report['turns']}  sweeps: {len(report['sweeps'])}")
    print("\nBY REGISTER (content lines)")
    print(f"{'register':<16}{'n':>5}{'min':>6}{'p25':>6}{'med':>7}{'p75':>6}"
          f"{'p90':>6}{'max':>6}")
    for reg, s in report["by_register"].items():
        print(f"{reg:<16}{s['n']:>5}{s['min']:>6}{s['p25']:>6}"
              f"{s['median']:>7}{s['p75']:>6}{s['p90']:>6}{s['max']:>6}")
    print("\nBY REGISTER (characters)")
    for reg, s in report["by_register_chars"].items():
        print(f"{reg:<16}{s['n']:>5}{s['min']:>7}{s['p25']:>7}"
              f"{s['median']:>8}{s['p75']:>7}{s['p90']:>7}{s['max']:>7}")
    print("\nBY ROUTE (n>=3, content lines)")
    for route, s in sorted(report["by_route"].items(),
                           key=lambda kv: -kv[1]["median"]):
        print(f"{route:<24}{s['n']:>4}  med={s['median']:>5}  "
              f"p90={s['p90']:>4}  max={s['max']:>4}")
    print("\nLONGEST 15")
    for r in report["longest"]:
        print(f"  {r['lines']:>4} lines  {r['route']:<18} {r['question'][:60]}")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
