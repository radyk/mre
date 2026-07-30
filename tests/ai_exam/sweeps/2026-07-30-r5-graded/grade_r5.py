"""Session 4B.17 grader: deterministic tripwires over the r5 answers.

These are NOT the grade. The grade is a read (R-AI4(2)); this layer only finds
what a read must look at, and every check below is derived from the pinned
world's PERSISTED document or from the bank's own written expectation -- never
from an observed answer.

    python grade_r5.py <runs-*.json> [<runs-*.json> ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORLD_ORDERS = {
    "ORD-000001", "ORD-000002", "ORD-000003", "ORD-000004", "ORD-000005",
    "ORD-000006", "ORD-000007", "ORD-000008", "ORD-000009", "ORD-000010",
    "ORD-000011", "ORD-000012", "ORD-000013", "ORD-000014", "ORD-000015",
    "ORD-000016", "ORD-000017", "ORD-000018", "ORD-000019", "ORD-000020",
    "ORD-000021", "ORD-000022", "ORD-000023", "ORD-000024", "ORD-000025",
    "ORD-000026", "ORD-000027", "ORD-000028", "ORD-000029", "ORD-000030",
    "ORD-000031", "ORD-000032", "ORD-000033", "ORD-000034", "ORD-000035",
    "ORD-000036", "ORD-000037", "ORD-000038", "ORD-000039", "ORD-000040",
}
WORLD_MACHINES = {
    "ASM-01", "CUT-01", "CUT-02", "CUT-03", "FINISH-01", "FINISH-02",
    "FINISH-03", "HEAT-01", "HEAT-02", "MILL-01", "MILL-02", "PAINT-01",
    "PAINT-02", "PRESS-FAST", "PRESS-SLOW",
}
IDLE = {"CUT-02", "CUT-03", "FINISH-03", "HEAT-02", "PRESS-SLOW"}
# Every currency figure the board can truthfully state, to the cent. Anything
# else in a $ position is flagged for a read (not automatically a failure -- a
# per-order production share or a card figure is legitimate).
KNOWN_MONEY = {"16481.95", "16,481.95", "14241.95", "14,241.95", "2240.00",
               "2,240.00", "0.00", "32.20", "24414.97"}

ORD_RE = re.compile(r"\bORD-\d{6}\b")
MACH_RE = re.compile(r"\b[A-Z]{3,7}-(?:\d{2}|FAST|SLOW)\b")
MONEY_RE = re.compile(r"\$\s?([\d,]+\.\d{2})")
# An ASSERTION that something is late: an order NAMED and called late, or a
# QUANTIFIED lateness. Deliberately narrow -- "explain why any order is late" is
# an OFFER and "nothing in this window is late" is the truth, and an over-broad
# pattern flags both. Tuned against the pinned world's facts, never against an
# answer's wording.
LATE_CLAIM_RE = re.compile(
    r"(?:ORD-\d{6}[^.\n]{0,70}?\b(?:is|are|was|will be|finishes?|finishing|ends?)"
    r"\s+(?:[^.\n]{0,25}?\s)?late\b"
    r"|\b\d[\d.,]*\s*(?:d|days?|h|hours?|min(?:utes?)?)\s+late\b"
    r"|\blate by\s+\d"
    r"|\b\d+\s+(?:order|orders)\s+(?:finish|are|is|will be)\s+late\b"
    r"|\btardiness (?:of|costs?)\s*\$?\s*[1-9])", re.IGNORECASE)


def _machines_in(text: str) -> set:
    return {m for m in MACH_RE.findall(text)}


def check(lineno: int, question: str, answer: str) -> list:
    """Tripwires for one turn. Each entry is (severity, code, detail).

    severity: 'truth'  -> a candidate TRUTH FAILURE, must be read
              'read'   -> something a read must look at, not itself a verdict
    """
    out = []
    a = answer or ""
    low = a.lower()

    # --- world-vocabulary fabrication (applies to every turn) --------------
    for o in sorted(set(ORD_RE.findall(a)) - WORLD_ORDERS):
        out.append(("truth", "fabricated-order", o))
    q_machines = _machines_in(question)
    for m in sorted(_machines_in(a) - WORLD_MACHINES - q_machines):
        out.append(("truth", "fabricated-machine", m))
    for amt in sorted({x for x in MONEY_RE.findall(a)} - KNOWN_MONEY):
        out.append(("read", "unlisted-money", "$" + amt))

    # --- the board has ZERO tardiness -------------------------------------
    m = LATE_CLAIM_RE.search(a)
    if m:
        out.append(("truth", "asserts-lateness", m.group(0)[:70]))
    # UNPLACED IS NOT LATE (4B.13 Item 3). Fusing the tray into a lateness
    # statement is the defect lateness_set was split to end.
    if re.search(r"lateness (?:problem|issue)|late (?:because|due to)[^.]{0,40}"
                 r"(?:unscheduled|not scheduled|no placement)", low):
        out.append(("truth", "unplaced-called-late", ""))

    # --- per-specimen, from the bank's written expectation -----------------
    if lineno == 105:            # affected set is EMPTY on the card
        named = set(ORD_RE.findall(a)) - {"ORD-000023"}
        if named:
            out.append(("truth", "invented-affected-orders",
                        ",".join(sorted(named))))
    if lineno in (128, 137, 141):  # the move COST $32.20
        if "32.20" not in a:
            out.append(("read", "no-card-figure", "32.20 absent"))
        if re.search(r"sav(?:e|es|ing|ings)[^.]{0,40}32\.20", low) or \
           re.search(r"32\.20[^.]{0,30}sav", low):
            out.append(("truth", "cost-reported-as-saving", "32.20"))
    if lineno == 128:            # "not the re-solve" must be honoured
        if not re.search(r"re-?optimi|re-?solve|0\.00|no(?:thing)?\b",
                         low):
            out.append(("read", "exclusion-unaddressed", ""))
    if lineno == 161:            # no card open -- no stale card may leak
        if "32.20" in a:
            out.append(("truth", "stale-card-figure", "32.20"))
    if lineno == 193:            # ORD-000023 is NOT late
        if "ORD-000023" not in a:
            out.append(("read", "card-order-unbound", ""))
    if lineno == 221:            # premise correction, machine exists
        if "PRESS-FAST" not in a:
            out.append(("truth", "premise-not-corrected", "PRESS-FAST absent"))
        if not re.search(r"(?:isn'?t|is not|not) on mill-01", low):
            out.append(("read", "correction-not-explicit", ""))
    if lineno == 231:
        missing = [m for m in ("MILL-02", "ASM-01", "FINISH-01") if m not in a]
        if missing:
            out.append(("truth", "premise-not-corrected",
                        "missing " + ",".join(missing)))
        if not re.search(r"(?:isn'?t|is not|not) on cut-01", low):
            out.append(("read", "correction-not-explicit", ""))
    if lineno == 242:            # MILL-99 does not exist
        if not re.search(r"no machine called mill-99|mill-99 (?:isn'?t|is not|"
                         r"does not|doesn'?t)|no such machine", low):
            out.append(("truth", "nonexistent-machine-not-named", ""))
        if "PRESS-FAST" in a and "MILL-99" not in a:
            out.append(("truth", "silent-substitution", "PRESS-FAST"))
    if lineno == 256:            # only-eligible lead
        if not re.search(r"only machine|only .{0,20}qualified|no alternative|"
                         r"only eligible|only lane", low):
            out.append(("read", "only-eligible-lead-absent", ""))
    if lineno in (325, 327, 340):   # machine count: both facts, idle named
        if "15" not in a:
            out.append(("truth", "declared-count-absent", "15"))
        if "10" not in a:
            out.append(("truth", "working-count-absent", "10"))
        if lineno != 327 and len(IDLE & set(MACH_RE.findall(a))) < 3:
            out.append(("read", "idle-machines-unnamed", ""))
    if lineno in (174, 314, 316, 336, 342):   # nothing is late
        if not re.search(r"\bno\b[^.\n]{0,25}late|\bnone\b[^.\n]{0,40}late"
                         r"|nothing[^.\n]{0,30}late|\bzero\b[^.\n]{0,20}late"
                         r"|not late|on time", low):
            out.append(("truth", "empty-late-set-not-stated", ""))
        # 4B.13 Item 3's region note: 26 in this window, 14 beyond the horizon.
        if not re.search(r"\b14\b", a) or not re.search(r"\b26\b|\b40\b", a):
            out.append(("read", "region-not-named", ""))
    if lineno == 385:            # the disagreement
        if re.search(r"really on time|the record agrees", low):
            out.append(("truth", "disagreement-laundered", ""))
        if not re.search(r"431|7h11|7 h 11|4h54|294", a):
            out.append(("read", "arithmetic-absent", ""))
    if lineno == 401:            # what-would-change thresholds
        if re.search(r"\b240\b", a) and "215" not in a:
            out.append(("truth", "unverified-threshold", "240"))
    if lineno == 418:            # the opener
        if re.search(r"\bACCEPTED\b|\bCONDITIONAL\b|\bREJECTED\b", a):
            out.append(("truth", "certificate-grade-stated", ""))
    if lineno == 439:            # overtime on CUT-01
        if "CUT-01" not in a:
            out.append(("read", "named-machine-unaddressed", "CUT-01"))
        if not re.search(r"help|difference|change|no\b", low):
            out.append(("read", "help-unaddressed", ""))
    return out


def main(argv) -> int:
    runs = []
    for p in argv:
        runs.extend(json.loads(Path(p).read_text(encoding="utf-8")))
    per_q: dict = {}
    for r in runs:
        key = (r["label"], r["run"])
        for row in r["rows"]:
            trips = check(row["lineno"], row["question"], row["answer"])
            per_q.setdefault(row["lineno"], {})[key] = {
                "q": row["question"], "intent": row["intent"],
                "route": row["route"], "register": row["register"],
                "met": row["expect_met"], "expect": row["expect"],
                "trips": trips, "err": row["error"],
                "latency": row["latency_ms"],
                "answer": row["answer"],
            }

    labels = sorted({(r["label"], r["run"]) for r in runs})
    print("=" * 78)
    print("PER-QUESTION x RUN  (intent / route / expect-met / tripwires)")
    print("=" * 78)
    for ln in sorted(per_q):
        cells = per_q[ln]
        q = next(iter(cells.values()))["q"]
        print(f"\nL{ln} :: {q}")
        for key in labels:
            c = cells.get(key)
            if c is None:
                continue
            tr = ";".join(f"{s}:{code}:{d}" for s, code, d in c["trips"])
            print(f"   {key[0]}-{key[1]}  {str(c['intent']):<18} "
                  f"{str(c['route']):<16} met={str(c['met']):<5} "
                  f"{c['latency']:>7.0f}ms  {tr}")
        verdicts = {key: (cells[key]["route"], cells[key]["met"],
                          tuple(sorted((s, c2) for s, c2, _ in cells[key]["trips"])))
                    for key in labels if key in cells}
        by_label: dict = {}
        for (lab, n), v in verdicts.items():
            by_label.setdefault(lab, set()).add(v)
        for lab, vs in sorted(by_label.items()):
            print(f"   -> {lab}: {'STABLE' if len(vs) == 1 else 'FLIPPED'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
