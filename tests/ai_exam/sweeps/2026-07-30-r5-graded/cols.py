"""Item 4's quality columns: did the answer reach the ASKED QUANTITY, and did
the multi-hop questions get answered. Both sets are declared here from the
bank's own written expectation plus the pinned world's facts.
"""
from __future__ import annotations
import json
import re
import sys

# The single fact each question asks for. Present => "reached the fact".
# Derived from the bank's substantive expectation, never from an answer.
FACT = {
    105: r"no order|nothing'?s lateness|no committed work",   # affected set empty
    128: r"32\.20",                                           # the move's cost
    137: r"32\.20",
    139: r"no order|nothing'?s lateness|no committed work",
    141: r"32\.20",
    161: r"no priced move|nothing to read back|no (?:card|move) open",
    174: r"no late orders|none .{0,30}late",
    176: r"CUT-01",
    193: r"not late|on time",
    221: r"PRESS-FAST",
    231: r"MILL-02",
    242: r"no machine called MILL-99|MILL-99 .{0,20}(?:isn't|is not|does not)",
    256: r"only machine|no alternative",
    262: r"PAINT-01|only machine|no alternative",   # the chain it was asked to deepen
    280: r"can'?t recommend|don'?t answer today|no late orders|none .{0,30}late",
    282: r"calendars\.csv|overtime_premium_multiplier",
    286: r"which order|name",
    288: r"resumable|chunk|split",
    301: r"worth your attention|things",
    303: r"worth your attention|things",
    314: r"no late orders|none .{0,30}late",
    316: r"no late orders|none .{0,30}late",
    325: r"15 machine",
    327: r"15 machine",
    336: r"no late orders|none .{0,30}late",
    338: r"can'?t recommend|don'?t answer today",
    340: r"15 machine",
    342: r"no late orders|none .{0,30}late",
    367: r"3 pieces|pauses|resumes",           # the downtime predicate
    385: r"7h11m|431",                          # the arithmetic that decides it
    401: r"215|min(?:imum)? piece|op10 finish",  # a lever with its threshold
    418: r"worth your attention",
    439: r"CUT-01",
}

# MULTI-HOP: the answer needs two or more independent evidence reads joined.
# Declared, with the hops named.
MULTI_HOP = {
    139: "card channel -> affected set (ellipsis resolved against the card)",
    193: "card outranks selection -> that order's demand -> its lateness",
    242: "utterance machine -> plant vocabulary -> absence",
    256: "order -> the op on the NAMED machine -> that op's eligibility",
    262: "prior turn's subject -> the chain it established -> deepen",
    288: "capability catalog -> the board's lateness set -> a joined read",
    367: "placement -> its chunks -> the calendar the pauses sit in",
    385: "planner's claim -> precedence finish -> window remainder -> chunk fit",
    401: "selection -> the op -> its binding family -> the lever's threshold",
    418: "slack vs longest step + calendar + tray + derate + proof, ranked",
}


def main(argv):
    for path in argv:
        runs = json.load(open(path, encoding="utf-8"))
        label = runs[0]["label"]
        per_run_fact = []
        per_run_hop = []
        for r in runs:
            f = h = 0
            missed_f, missed_h = [], []
            for row in r["rows"]:
                ln = row["lineno"]
                pat = FACT.get(ln)
                hit = bool(pat and re.search(pat, row["answer"] or "",
                                             re.IGNORECASE))
                if hit:
                    f += 1
                else:
                    missed_f.append(ln)
                if ln in MULTI_HOP:
                    if hit:
                        h += 1
                    else:
                        missed_h.append(ln)
            per_run_fact.append((f, missed_f))
            per_run_hop.append((h, missed_h))
        n = len(runs[0]["rows"])
        print(f"{label}:")
        for i, ((f, mf), (h, mh)) in enumerate(zip(per_run_fact, per_run_hop), 1):
            print(f"  run{i}  fact {f}/{n}  (missed {mf})   "
                  f"multi-hop {h}/{len(MULTI_HOP)}  (missed {mh})")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
