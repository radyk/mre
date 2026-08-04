"""THE AFTER — Session 4A teaching-graft (d.1).

Re-runs the (d.0) recon's own probes against the FIXED tree, using the recon's
own harness (`tools/spikes/multiturn_recon/conv.py`) so the before and the after
are the same instrument pointed at the same boards. Nothing here is a new
measurement design; the design is the recon's and the point is comparability.

    python tools/spikes/teaching_graft_d1/after.py p4 p8 p2b zero deaf

  p4    R-MT1 — the cross-version bleed, BOTH directions, and BOTH halves:
        the SHIPPED gesture (clause 2: the client clears) and the SERVER-ONLY
        arm (clause 1 alone, i.e. what a browser that has not reloaded sends).
  p8    D-01 — the teaching answer, then "can you show me that on my board".
  p2b   R-LD5 — the model-recovered subject and its disclosure line.
  zero  D-06 — a zero-record TESTIMONY answer, drilled, on its own board.
  deaf  D-07 — the deictic follow-up the rider used to scold.

Read-only against the two pinned boards. Mints nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools" / "spikes" / "multiturn_recon"))

from conv import (  # noqa: E402
    Conversation, build, tiers, turns_payload,
)

ARTIFACTS = HERE / "artifacts"
DEMO = "rolling-db5395dc-2ae"
PINNED = "rolling-c362baa4-1b0"


def dump(name: str, payload) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  -> {path.relative_to(ROOT)}")
    return path


def _rebind(conv: Conversation, target, *, clear_client: bool) -> None:
    """`main.js::onVersionChange`, in its two states.

    `clear_client=False` is the gesture the recon measured and is what R-MT1
    clause 1 has to survive ON ITS OWN — a store that is safe only because a
    browser remembered to clear is safe by discipline. `clear_client=True` is
    the shipped gesture after clause 2."""
    conv.rebind(target)                       # the recon's own rebind + selection
    if clear_client:
        conv.history = []
        conv.last_answered = {}


def p4():
    print("P4 — CROSS-VERSION, AFTER (R-MT1)")
    p, s = tiers()
    a, b = build(DEMO), build(PINNED)
    out = {}
    for direction, first, second in (("A-then-B", a, b), ("B-then-A", b, a)):
        for half, clear in (("server-only", False), ("shipped", True)):
            name = f"{direction}/{half}"
            print(f"  {name}  ({first.label} -> {second.label})")
            c = Conversation(f"d1-p4-{direction}-{half}", first, p, s)
            c.reset()
            t = c.ask("how many orders are late and what is the total "
                      "tardiness cost")
            print(f"    {t.brief()}  records={t.record_count}")
            print(f"       {t.text.splitlines()[0][:140]}")
            _rebind(c, second, clear_client=clear)
            for q in ("show me the evidence for that",
                      "can you show me that on my board"):
                t = c.ask(q)
                print(f"    {t.brief()}  records={t.record_count}  "
                      f"(asked against {c.target.label})")
                print(f"       {t.text.splitlines()[0][:200]}")
            out[name] = turns_payload(c)
    dump("p4-after.json", out)
    return out


def p8():
    print("P8 — TEACHING ACROSS TURNS, AFTER (D-01)")
    p, s = tiers()
    c = Conversation("d1-p8", build(DEMO), p, s)
    c.reset()
    for q in ("how does a frozen zone normally work on a board like this",
              "can you show me that on my board",
              "why doesn't that apply to ORD-000128",
              "so what should i do first"):
        t = c.ask(q)
        print(f"    {t.brief()}  records={t.record_count}")
        print(f"       {t.text.splitlines()[0][:200]}")
    dump("p8-after.json", turns_payload(c))
    return c


def p2b():
    print("P2b — THE MODEL-RECOVERED SUBJECT, AFTER (R-LD5)")
    p, s = tiers()
    probe = "why cant this be moved earlier"
    arms = {"cold": [],
            "after-mobility": ["why is ORD-000073 op10 placed where it is"],
            "after-unrelated": ["how many orders are late"]}
    out = {}
    for name, prefix in arms.items():
        print(f"  arm: {name}")
        c = Conversation(f"d1-p2b-{name}", build(DEMO), p, s)
        c.reset()
        for q in prefix:
            c.ask(q)
        t = c.ask(probe)
        print(f"    {t.brief()}  subjects={t.subjects}")
        print(f"       note={t.resolution_note!r}")
        out[name] = turns_payload(c)
    dump("p2b-after.json", out)
    return out


def zero():
    print("ZERO-RECORD CONTROL, AFTER (D-06)")
    p, s = tiers()
    c = Conversation("d1-zerorec", build(PINNED), p, s)
    c.reset()
    t = c.ask("how many orders are late and what is the total tardiness cost")
    print(f"    {t.brief()} records={t.record_count}")
    t = c.ask("show me the evidence for that")
    print(f"    {t.brief()}")
    print(f"       {t.text.splitlines()[0][:300]}")
    dump("zero-record-after.json", turns_payload(c))
    return c


def deaf():
    print("DEAF CONTROL, AFTER (D-07)")
    p, s = tiers()
    c = Conversation("d1-deafctl", build(DEMO), p, s)
    c.reset()
    for q in ("why is ORD-000128 op20 placed where it is", "so why is it there"):
        t = c.ask(q, select={"order": "ORD-000128", "op_seq": 20})
        print(f"    {t.brief()}  followup_of={t.followup_of}  "
              f"key_facts={t.key_facts}")
        print(f"       {t.text.splitlines()[0][:160]}")
    dump("deaf-control-after.json", turns_payload(c))
    return c


PROBES = {"p4": p4, "p8": p8, "p2b": p2b, "zero": zero, "deaf": deaf}

if __name__ == "__main__":
    for n in sys.argv[1:] or ["p4"]:
        if n not in PROBES:
            raise SystemExit(f"unknown probe {n!r}; pick from {sorted(PROBES)}")
        PROBES[n]()
        print()
