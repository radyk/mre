"""The Part B probes — Session 4A teaching-graft (d.0), multi-turn recon.

  python tools/spikes/multiturn_recon/probes.py p1     # carry inventory
  python tools/spikes/multiturn_recon/probes.py p2     # history sensitivity
  python tools/spikes/multiturn_recon/probes.py p3     # repetition
  python tools/spikes/multiturn_recon/probes.py p4     # cross-version bleed
  python tools/spikes/multiturn_recon/probes.py p5     # outage turns in history
  python tools/spikes/multiturn_recon/probes.py p6     # decay
  python tools/spikes/multiturn_recon/probes.py p7     # stability (P1 x3)
  python tools/spikes/multiturn_recon/probes.py p8     # teaching across turns

Every probe is read-only against the two pinned boards and mints nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conv import (  # noqa: E402
    Conversation, RecordingParser, RecordingSynthesizer, UnreachableClient,
    build, dump, tiers, turns_payload,
)

DEMO = "rolling-db5395dc-2ae"     # board A — the Khalil/demo board, 386 bars
PINNED = "rolling-c362baa4-1b0"   # board B — the pinned exam world, 56 bars


def _run(conv: Conversation, questions, select=None):
    for i, q in enumerate(questions):
        sel = (select or {}).get(i)
        t = conv.ask(q, select=sel)
        print(f"    {t.brief()}")
        print(f"       q: {q}")
        if t.resolution_note:
            print(f"       note: {t.resolution_note[:160]}")
    return conv


# ---------------------------------------------------------------------------

P1_TURNS = [
    "how many orders are late",                          # 1 plain fact
    "why is that",                                       # 2 ellipsis -> turn 1
    "why is ORD-000128 op20 placed where it is",          # 3 different subject
    "what would have to change",                         # 4 could bind 1 or 3
    "how does a frozen zone normally work on a board",    # 5 teaching
    "why does that matter here",                          # 6 teaching follow-up
]


def p1(tag="p1"):
    print("P1 — CARRY INVENTORY (six turns, one conversation)")
    p, s = tiers()
    c = Conversation(f"recon-{tag}", build(DEMO), p, s)
    c.reset()
    _run(c, P1_TURNS)
    dump(f"{tag}-turns.json", turns_payload(c))
    return c


def p2():
    print("P2 — HISTORY SENSITIVITY (one question, three positions)")
    p, s = tiers()
    probe = "why cant this be moved"
    sel = {"order": "ORD-000128", "op_seq": 20}
    arms = {
        "cold": [],
        "after-mobility": ["why is ORD-000073 op10 placed where it is",
                           "what would have to change for it to start earlier"],
        "after-unrelated": ["how many orders are late",
                            "what does the cost ledger total"],
    }
    out = {}
    for name, prefix in arms.items():
        print(f"  arm: {name}")
        c = Conversation(f"recon-p2-{name}", build(DEMO), p, s)
        c.reset()
        for q in prefix:
            t = c.ask(q, select=None)
            print(f"    (prefix) {t.brief()}")
        t = c.ask(probe, select=sel)
        print(f"    {t.brief()}")
        out[name] = turns_payload(c)
    dump("p2-turns.json", out)
    return out


def p2b():
    """P2's other half: the SAME question with NO board selection, so the
    deterministic ladder has nothing to bind and only the history block can
    carry a subject. P2 measured the selection-bound arm and found it
    position-invariant; this measures where the sensitivity actually lives."""
    print("P2b — HISTORY SENSITIVITY WITH NO SELECTION")
    p, s = tiers()
    probe = "why cant this be moved earlier"
    arms = {
        "cold": [],
        "after-mobility": ["why is ORD-000073 op10 placed where it is"],
        "after-unrelated": ["how many orders are late"],
    }
    out = {}
    for name, prefix in arms.items():
        print(f"  arm: {name}")
        c = Conversation(f"recon-p2b-{name}", build(DEMO), p, s)
        c.reset()
        for q in prefix:
            t = c.ask(q)
            print(f"    (prefix) {t.brief()}")
        t = c.ask(probe)
        print(f"    {t.brief()}  subjects={t.subjects}")
        print(f"       note={t.resolution_note[:140]!r}")
        print(f"       {t.text.splitlines()[0][:150]}")
        out[name] = turns_payload(c)
    dump("p2b-turns.json", out)
    return out


def deaf_control():
    """Was P5's `deaf` firing caused by the OUTAGE turn, or would the same two
    turns adjacent have fired it anyway? One control, no outage."""
    print("DEAF CONTROL — the same two turns, no outage between them")
    p, s = tiers()
    c = Conversation("recon-deafctl", build(DEMO), p, s)
    c.reset()
    for q in ("why is ORD-000128 op20 placed where it is", "so why is it there"):
        t = c.ask(q, select={"order": "ORD-000128", "op_seq": 20})
        print(f"    {t.brief()}  key_facts={t.key_facts}")
    dump("deaf-control.json", turns_payload(c))
    return c


def zero_record_control():
    """Was P4's B-then-A `prove-it` wording ('authored copy') a cross-version
    artefact, or does a ZERO-RECORD testimony answer get that sentence on its
    OWN board too? One control, one board."""
    print("ZERO-RECORD CONTROL — same board, an answer that cites nothing")
    p, s = tiers()
    c = Conversation("recon-zerorec", build(PINNED), p, s)
    c.reset()
    t = c.ask("how many orders are late and what is the total tardiness cost")
    print(f"    {t.brief()} records={t.record_count}")
    t = c.ask("show me the evidence for that")
    print(f"    {t.brief()}")
    print(f"       {t.text.splitlines()[0][:220]}")
    dump("zero-record-control.json", turns_payload(c))
    return c


def p3():
    print("P3 — REPETITION")
    p, s = tiers()
    c = Conversation("recon-p3", build(DEMO), p, s)
    c.reset()
    seq = [
        ("why is ORD-000128 op20 placed where it is", {"order": "ORD-000128", "op_seq": 20}),
        ("why is ORD-000128 op20 placed where it is", {"order": "ORD-000128", "op_seq": 20}),
        ("why is ORD-000073 op10 placed where it is", {"order": "ORD-000073", "op_seq": 10}),
        ("why is ORD-000073 op30 placed where it is", {"order": "ORD-000073", "op_seq": 30}),
    ]
    for q, sel in seq:
        t = c.ask(q, select=sel)
        print(f"    {t.brief()}  key_facts={t.key_facts}")
    dump("p3-turns.json", turns_payload(c))
    return c


def p4():
    print("P4 — CROSS-VERSION BLEED")
    p, s = tiers()
    a, b = build(DEMO), build(PINNED)
    out = {}
    for name, first, second in (("A-then-B", a, b), ("B-then-A", b, a)):
        print(f"  direction: {name}  ({first.label} -> {second.label})")
        c = Conversation(f"recon-p4-{name}", first, p, s)
        c.reset()
        t = c.ask("how many orders are late and what is the total tardiness cost")
        print(f"    {t.brief()}")
        print(f"       {t.text.splitlines()[0][:150]}")
        # main.js::onVersionChange — rebind, drop the selection, clear nothing else
        c.rebind(second)
        for q in ("show me the evidence for that",
                  "is that number still right"):
            t = c.ask(q)
            print(f"    {t.brief()}  (asked against {c.target.label})")
            print(f"       {t.text.splitlines()[0][:150]}")
        out[name] = turns_payload(c)
    dump("p4-turns.json", out)
    return out


def p5():
    print("P5 — OUTAGE TURNS IN HISTORY")
    from mre.modules.question_parser import QuestionParser
    from mre.modules.synthesizer import Synthesizer
    p, s = tiers()
    c = Conversation("recon-p5", build(DEMO), p, s)
    c.reset()
    t = c.ask("why is ORD-000128 op20 placed where it is",
              select={"order": "ORD-000128", "op_seq": 20})
    print(f"    {t.brief()}   (the real answer, before the outage)")

    # The outage turn: a parser whose transport raises. Product code path
    # unchanged; only the CLIENT the parser was constructed with is a double.
    dead_parser = RecordingParser(QuestionParser(_client=UnreachableClient()))
    dead_synth = RecordingSynthesizer(Synthesizer(_client=UnreachableClient()))
    real_p, real_s = c.parser, c.synth
    c.parser, c.synth = dead_parser, dead_synth
    t = c.ask("and what about the one after it")
    print(f"    {t.brief()}   (the OUTAGE turn)")
    print(f"       register={t.register!r}  text[0]={t.text.splitlines()[0][:120]}")
    c.parser, c.synth = real_p, real_s

    for q in ("so why is it there", "show me the evidence for that"):
        t = c.ask(q)
        print(f"    {t.brief()}")
        print(f"       {t.text.splitlines()[0][:150]}")
    print(f"    history the client now holds: "
          f"{[h['route'] for h in c.history]}")
    dump("p5-turns.json", {"turns": turns_payload(c), "history": c.history})
    return c


def p6():
    print("P6 — DECAY (twelve turns; turn 12 can only resolve via turn 1)")
    p, s = tiers()
    c = Conversation("recon-p6", build(DEMO), p, s)
    c.reset()
    c.ask("why is ORD-000128 op20 placed where it is",
          select={"order": "ORD-000128", "op_seq": 20})
    print(f"    {c.turns[-1].brief()}   (the antecedent)")
    c.selection = {}          # the planner clicks away; only history can carry it
    fillers = ["how many orders are late",
               "what is the total cost of this plan",
               "are there any data quality problems",
               "what is beyond the horizon",
               "how busy is CUT-01",
               "what does the certificate say",
               "how many orders are in the tray",
               "what is the frozen zone",
               "what is the biggest driver of lateness",
               "what would you tell me first about this board"]
    for q in fillers:
        t = c.ask(q)
        print(f"    {t.brief()}")
    t = c.ask("and why couldn't that one start earlier")
    print(f"    T{t.n} PROBE: {t.brief()}")
    print(f"       subjects={t.subjects}")
    print(f"       note={t.resolution_note[:200]!r}")
    print(f"       first line: {t.text.splitlines()[0][:180]}")
    dump("p6-turns.json", turns_payload(c))
    return c


def p7():
    print("P7 — STABILITY AT THE SEAMS (P1 three times, identical inputs)")
    runs = []
    for i in range(3):
        print(f"  run {i + 1}")
        c = p1(tag=f"p7-run{i + 1}")
        runs.append(turns_payload(c))
    fields = ["route", "intent", "register", "tier", "followup_of",
              "resolution_note", "subject_type", "subject_name"]
    print("\n  field-by-field across the three runs:")
    stable, varying = [], []
    for f in fields:
        cols = [[r[i].get(f) for r in runs] for i in range(len(P1_TURNS))]
        ok = all(len(set(map(str, col))) == 1 for col in cols)
        (stable if ok else varying).append(f)
        print(f"    {f:20s} {'STABLE' if ok else 'VARIES'}  "
              f"{[list(dict.fromkeys(map(str, col))) for col in cols]}")
    lens = [[len(r[i].get('text') or '') for r in runs] for i in range(len(P1_TURNS))]
    print(f"    text length          {lens}")
    dump("p7-runs.json", {"runs": runs, "stable": stable, "varying": varying})
    return runs


P8_TURNS = [
    "how does a frozen zone normally work on a board like this",
    "can you show me that on my board",
    "why doesn't that apply to ORD-000128",
    "so what should i do first",
]


def p8():
    print("P8 — TEACHING ACROSS TURNS")
    p, s = tiers()
    c = Conversation("recon-p8", build(DEMO), p, s)
    c.reset()
    for q in P8_TURNS:
        t = c.ask(q)
        print(f"    {t.brief()}  licence-tier={t.tier} counts={t.claim_counts} "
              f"deferred={t.deferred}")
        for cl in t.claims:
            print(f"       [{cl['status']}] {cl['text'][:110]}")
    dump("p8-turns.json", turns_payload(c))
    return c


PROBES = {"p1": p1, "p2": p2, "p2b": p2b, "p3": p3, "p4": p4,
          "p5": p5, "p6": p6, "p7": p7, "p8": p8,
          "deaf-control": deaf_control,
          "zero-record-control": zero_record_control}


if __name__ == "__main__":
    names = sys.argv[1:] or ["p1"]
    for n in names:
        if n not in PROBES:
            raise SystemExit(f"unknown probe {n!r}; pick from {sorted(PROBES)}")
        PROBES[n]()
        print()
