"""(d.3) C1 — THE VOCABULARY THE PRODUCT ACTUALLY EMITS.

Session 4A teaching-graft (d.3). R-TE1's first edition is scoped BY THIS COUNT,
not by judgement: a glossary entry for a word this product has never said to a
planner is a documentation feature, and the scope wall says this is not one.

Counted over the committed sweep transcripts — the same corpus
`census_precision.py` reads, for the same reason: it is where rendered ANSWER
text lives. Only the ANSWER BODY is counted (the `  A:` blocks), never the
question lines, never the harness's own header/parse/expect lines — a term the
PLANNER typed is not a term the product emitted, and counting the instrument's
own vocabulary would be the loudest false positive available.

    python tools/spikes/teaching_graft_d3/c1_vocabulary_census.py [--show TERM]

Read-only. No model, no solver, mints nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SWEEPS = ROOT / "tests" / "ai_exam" / "sweeps"

#: The candidate vocabulary, from the brief's expected members plus everything
#: the rulings name as a planner-facing word. Each entry is (term, pattern).
#: PATTERNS ARE WORD-BOUNDED AND INFLECTION-AWARE, because "seeds" and "seeded"
#: are the same word to a planner asking what it means.
CANDIDATES: list[tuple[str, str]] = [
    ("seed",            r"\bseed(?:s|ed|ing)?\b"),
    ("member",          r"\bmember(?:s)?\b"),
    ("gap",             r"\bgap(?:s)?\b"),
    ("calibrated",      r"\b(?:un)?calibrat(?:ed|ion|e)\b"),
    ("frozen",          r"\bfroz(?:en)\b|\bfreeze\b|\bfrozen\s+zone\b"),
    ("pinned",          r"\bpin(?:ned|s|ning)?\b"),
    ("ledger",          r"\bledger(?:s)?\b"),
    ("driver",          r"\bdriver(?:s)?\b"),
    ("setup family",    r"\bsetup\s+famil(?:y|ies)\b|\bsetup\s+matrix\b"),
    ("ghost",           r"\bghost(?:s|ed)?\b"),
    ("rolling",         r"\brolling\b"),
    ("monolithic",      r"\bmonolithic\b"),
    ("register",        r"\bregister(?:s)?\b"),
    ("portfolio",       r"\bportfolio(?:s)?\b"),
    ("spread",          r"\bspread\b"),
    ("horizon",         r"\bhorizon(?:s)?\b"),
    ("beyond-horizon",  r"\bbeyond[\s-]horizon\b"),
    ("tray",            r"\btray\b"),
    ("window",          r"\bwindow(?:s)?\b"),
    ("slack",           r"\bslack\b"),
    ("tardiness",       r"\btardiness\b"),
    ("makespan",        r"\bmakespan\b"),
    ("deterministic",   r"\bdeterministic(?:ally)?\b"),
    ("snapshot",        r"\bsnapshot(?:s)?\b"),
    ("certificate",     r"\bcertificate(?:s)?\b"),
    ("provenance",      r"\bprovenance\b"),
    ("chunk",           r"\bchunk(?:s|ed|ing)?\b"),
    ("splittable",      r"\bsplittable\b"),
    ("boxed-in",        r"\bboxed[\s-]in\b"),
    ("mobility",        r"\bmobilit(?:y|ies)\b"),
    ("counterfactual",  r"\bcounterfactual(?:s)?\b"),
    ("optimal",         r"\boptimal(?:ity)?\b"),
    ("bound",           r"\blower\s+bound\b|\bupper\s+bound\b"),
    ("overtime",        r"\bovertime\b"),
    ("past-due",        r"\bpast[\s-]due\b"),
    ("capability",      r"\bcapabilit(?:y|ies)\b"),
    ("workcenter",      r"\bworkcenter(?:s)?\b"),
    ("coarse",          r"\bcoarse\b"),
    ("derate",          r"\bderat(?:e|ed|ing)\b"),
]

_COMPILED = [(t, re.compile(p, re.IGNORECASE)) for t, p in CANDIDATES]

#: The transcript's own furniture. Everything between `  A:` and the next
#: `Q[` / rule line is answer body; everything else is the instrument talking.
_Q_RE = re.compile(r"^Q\[\d+\]:")
_A_RE = re.compile(r"^\s{2}A:\s*$")
_RULE = "-" * 72


def answer_bodies(path: Path) -> list[str]:
    """Every rendered ANSWER BODY in one transcript, question lines excluded."""
    out, cur, inside = [], [], False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _A_RE.match(raw):
            inside, cur = True, []
            continue
        if inside and (raw.startswith(_RULE) or _Q_RE.match(raw.strip())):
            out.append("\n".join(cur))
            inside, cur = False, []
            continue
        if inside:
            # THE INSTRUMENT IS NOT THE PRODUCT. Three kinds of line sit inside
            # an `A:` block and are not answer text:
            #   * the footer, which names the RENDERER and contains "register";
            #   * the sidecar findings the harness appends after the body —
            #     caught by the first run of this census, where `pinned`'s top
            #     example was `>> sidecar[absent-entity]: interpreted-as names
            #     'ORD-99'`. Counting our own findings as the product's
            #     vocabulary would have put a word in the glossary that no
            #     planner has ever been shown.
            s = raw.strip()
            if (s.startswith("[rendered by:") or s.startswith("[LLM validation")
                    or s.startswith(">> sidecar[")):
                continue
            cur.append(raw)
    if inside and cur:
        out.append("\n".join(cur))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", help="print every answer line containing TERM")
    ap.add_argument("--min", type=int, default=1)
    args = ap.parse_args()

    paths = sorted(SWEEPS.rglob("*.txt"))
    bodies: list[tuple[str, str]] = []
    for p in paths:
        for b in answer_bodies(p):
            bodies.append((p.parent.name + "/" + p.name, b))

    hits: Counter = Counter()
    answers_with: Counter = Counter()
    examples: dict[str, tuple[str, str]] = {}
    for src, body in bodies:
        for term, rx in _COMPILED:
            found = rx.findall(body)
            if not found:
                continue
            hits[term] += len(found)
            answers_with[term] += 1
            if term not in examples:
                line = next((ln.strip() for ln in body.splitlines()
                             if rx.search(ln)), "")
                examples[term] = (src, line)

    print(f"transcripts       : {len(paths)}")
    print(f"rendered answers  : {len(bodies)}")
    print(f"candidate terms   : {len(CANDIDATES)}")
    print(f"terms EMITTED     : {len(hits)}\n")
    print(f"{'term':18s} {'uses':>6s} {'answers':>8s}   first example")
    print("-" * 110)
    for term, n in hits.most_common():
        if n < args.min:
            continue
        src, line = examples[term]
        print(f"{term:18s} {n:6d} {answers_with[term]:8d}   {line[:66]}")

    never = [t for t, _ in CANDIDATES if t not in hits]
    print(f"\nNEVER EMITTED ({len(never)}) — out of the first edition by "
          f"construction:\n    {', '.join(never) or '(none)'}")

    out = Path(__file__).parent / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "c1_vocabulary.json").write_text(json.dumps(
        {"transcripts": len(paths), "answers": len(bodies),
         "uses": dict(hits.most_common()),
         "answers_with": dict(answers_with.most_common()),
         "examples": {k: {"source": v[0], "line": v[1]}
                      for k, v in examples.items()},
         "never_emitted": never}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\nartifact -> {out / 'c1_vocabulary.json'}")

    if args.show:
        rx = dict(_COMPILED)[args.show]
        print(f"\n--- every answer line containing {args.show!r} ---")
        seen = set()
        for src, body in bodies:
            for ln in body.splitlines():
                s = ln.strip()
                if rx.search(s) and s not in seen:
                    seen.add(s)
                    print(f"  [{src}] {s[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
