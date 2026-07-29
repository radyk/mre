"""MODEL TIER BENCH — the same question bank against three tiers
(Session 4B.15 Item 6).

    python tools/model_tier_bench.py --run c362baa4-1b03-4f6c-b3a4-d092c341dbdf
    python tools/model_tier_bench.py --tiers haiku,sonnet --out report.json

MEASURE, DO NOT ASSUME. Synthesis runs `claude-haiku-4-5` today — the layer
Daryn calls the differentiator, pinned to the cheapest tier by a default nobody
revisited. This runs one bank through the FULL ask path (parse -> dispatch ->
render) on each tier and reports what actually differs.

WHAT IS SCORED, AND WHY THESE COLUMNS
--------------------------------------
Every question carries a deterministic EXPECTATION — substrings that must
appear, substrings that must NOT, and the route it should reach. Nothing here
is model-graded: an LLM judge would make the measurement circular.

  answers correct      the answer meets every expectation
  reached the fact     the specific figure or verdict the question asks for is
                       present, whatever else the answer says. This is the
                       column that matters most for retrieval: an answer can
                       reach the fact and still be scored incorrect for saying
                       something false beside it.
  multi-hop answered   questions needing two or more joined reads (an order's
                       machine AND that machine's calendar, a field AND its
                       provenance). The single-hop lookups are where a cheap
                       tier looks fine; multi-hop is where a tier decision is
                       actually made.
  latency              wall clock per question, median
  cost per question    measured tokens x the published per-MTok rate

TOKENS ARE COUNTED, NOT ESTIMATED. The client is wrapped so every
`messages.create` records its `usage`. That is why the cost column is a
measurement rather than an approximation from response length.

ALL READS FROM THE PERSISTED RUN (R-AI4). No solve, ever.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_ai_exam_sweep import load_env_local  # noqa: E402

load_env_local()

#: Published rates, $ per million tokens (input, output). Update with the
#: pricing table; the cost column is only as current as this dict.
TIERS: dict[str, tuple[str, float, float]] = {
    "haiku": ("claude-haiku-4-5", 1.00, 5.00),
    "sonnet": ("claude-sonnet-5", 3.00, 15.00),
    "opus": ("claude-opus-5", 5.00, 25.00),
}

DEFAULT_RUN = "c362baa4-1b03-4f6c-b3a4-d092c341dbdf"


@dataclass
class Question:
    """One bank entry and its deterministic expectation."""

    qid: str
    text: str
    #: Substrings, ALL of which must appear (case-insensitive) for "correct".
    expect: tuple[str, ...] = ()
    #: The single fact the question asks for. Present ⇒ "reached the fact".
    fact: str = ""
    #: Substrings that must NOT appear. A confident falsehood.
    forbid: tuple[str, ...] = ()
    #: Routes that count as answering it. Empty = any route.
    routes: tuple[str, ...] = ()
    #: Needs two or more joined reads.
    multihop: bool = False
    selection: dict = field(default_factory=dict)


#: THE BANK. Every expectation is a fact verified against the pinned world's
#: persisted document and snapshot before being written here.
BANK: tuple[Question, ...] = (
    # -- attribute lookups: single-hop, the floor -------------------------
    Question("attr-splittable", "is ORD-000013 op20 splittable",
             expect=("splittable",), fact="no", forbid=("yes, it is splittable",),
             routes=("attribute-lookup",),
             selection={"order": "ORD-000013", "op_seq": 20}),
    Question("attr-duration", "how long does ORD-000013 op20 take",
             expect=("431",), fact="431", routes=("attribute-lookup",),
             selection={"order": "ORD-000013", "op_seq": 20}),
    Question("attr-due", "when is ORD-000013 due",
             expect=("2026-01-15",), fact="2026-01-15",
             routes=("attribute-lookup", "order-attributes")),
    # -- capability: the specimen that started the session ------------------
    Question("cap-operator", "can two machines share one operator",
             expect=("b3", "b5"), fact="not today",
             # The measured falsehood: a confident yes describing ALTERNATES.
             forbid=("alternates", "eligible on more than one machine"),
             routes=("coaching",)),
    Question("cap-oven", "can two orders share an oven cycle",
             expect=("b9",), fact="deliberately",
             routes=("coaching",)),
    # -- causal: the blocker analysis --------------------------------------
    Question("why-here", "why is this operation here and not earlier",
             expect=("paint-01",), fact="431",
             routes=("why-here", "start-reason"),
             selection={"order": "ORD-000013", "machine": "PAINT-01",
                        "op_seq": 20}),
    # -- MULTI-HOP: two or more joined reads --------------------------------
    Question("hop-machine-idle",
             "what else did PAINT-01 run on the day ORD-000013 op20 ran",
             expect=("paint-01",), fact="ord-000022", multihop=True),
    Question("hop-closure",
             "ORD-000013 op20 runs on PAINT-01 — is PAINT-01 closed on any day "
             "between Jan 12 and Jan 16",
             expect=("2026-01-14",), fact="2026-01-14", multihop=True),
    Question("hop-field-source",
             "is ORD-000013 op20 splittable, and where did that value come from",
             expect=("splittable",), fact="routing_lines", multihop=True,
             routes=("attribute-lookup",),
             selection={"order": "ORD-000013", "op_seq": 20}),
    Question("hop-count-late",
             "how many orders are late, and is the schedule proven optimal",
             expect=(), fact="optimal", multihop=True),
    # -- SYNTHESIS-BOUND. No contracted route covers these, so the second tier
    # answers them and the MODEL is doing the work. This is where a tier
    # decision is actually made: with the routes working, the contracted
    # questions above are answered by deterministic assembly and the tier only
    # affects whether the PARSE picked the right one.
    Question("syn-busiest",
             "which machine is carrying the most work in this window",
             expect=("cut-01",), fact="cut-01", multihop=True,
             forbid=("paint-01 is the busiest",)),
    Question("syn-compare",
             "compare how loaded CUT-01 and PAINT-01 are",
             expect=("cut-01", "paint-01"), fact="cut-01", multihop=True),
    Question("syn-spread",
             "is the work spread evenly across the machines or concentrated",
             expect=("cut-01",), fact="cut-01", multihop=True),
    Question("syn-tardiness-zero",
             "is anything running late in this window, and what is it costing",
             expect=(), fact="0", multihop=True,
             forbid=("orders are late", "tardiness cost of $")),
    # -- the honest floor: a question with no answer ------------------------
    Question("floor-unknowable", "what will the weather be on delivery day",
             expect=(), fact="",
             forbid=("the weather will", "forecast is"),),
)


class CountingClient:
    """Wraps an Anthropic client and records every call's token usage.

    Tokens are MEASURED, not estimated from response length — which is what
    makes the cost column a measurement."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.messages = self._Messages(self)

    class _Messages:
        def __init__(self, outer: "CountingClient") -> None:
            self._outer = outer

        def create(self, **kwargs):
            resp = self._outer._inner.messages.create(**kwargs)
            self._outer.calls += 1
            usage = getattr(resp, "usage", None)
            if usage is not None:
                self._outer.input_tokens += getattr(usage, "input_tokens", 0) or 0
                self._outer.output_tokens += getattr(usage, "output_tokens", 0) or 0
            return resp

    def reset(self) -> None:
        self.input_tokens = self.output_tokens = self.calls = 0


def build_world(run_id: str):
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore
    out_dir = REPO / "_data" / "runs" / run_id
    doc = json.loads((out_dir / "schedule_document.json").read_text(encoding="utf-8"))
    index_path = out_dir / "evidence_index.json"
    index = (EvidenceIndex.load(index_path) if index_path.exists()
             else EvidenceIndex().build(out_dir / "runs"))
    return Explainer(SnapshotStore(out_dir / "snapshots"), index,
                     snapshot_id="snap-rolling"), doc


def score(q: Question, text: str, route: str) -> dict:
    low = (text or "").lower()
    hit_expect = all(e.lower() in low for e in q.expect)
    hit_forbid = any(f.lower() in low for f in q.forbid)
    ok_route = (not q.routes) or route in q.routes
    reached = bool(q.fact) and q.fact.lower() in low
    return {"correct": bool(hit_expect and not hit_forbid and ok_route),
            "reached_fact": reached if q.fact else hit_expect,
            "route_ok": ok_route, "said_forbidden": hit_forbid,
            "route": route}


#: SPLIT CONFIGURATIONS. The parse and the synthesis tier are separate model
#: parameters and there is no reason they must match — the parse is a
#: closed-vocabulary classification, synthesis is open reasoning over evidence.
#: Naming the split as a first-class row is what lets the recommendation be
#: MEASURED rather than inferred from two single-model columns.
SPLITS: dict[str, tuple[str, str]] = {
    "split-hs": ("haiku", "sonnet"),
    "split-ho": ("haiku", "opus"),
}


def run_tier(tier: str, run_id: str, bank: tuple[Question, ...],
             verbose: bool) -> dict:
    import anthropic

    from mre.modules.interpreter import dispatch
    from mre.modules.question_parser import QuestionParser
    from mre.modules.renderers import TemplateRenderer
    from mre.modules.rolling_questions import RollingVocabulary
    from mre.modules.synthesizer import Synthesizer

    if tier in SPLITS:
        parse_tier, synth_tier = SPLITS[tier]
    else:
        parse_tier = synth_tier = tier
    parse_model, p_in, p_out = TIERS[parse_tier]
    synth_model, s_in, s_out = TIERS[synth_tier]
    raw = anthropic.Anthropic()
    # Two counters, so a split configuration's cost is the sum of its two real
    # rates rather than one blended guess.
    parse_counter, synth_counter = CountingClient(raw), CountingClient(raw)

    ex, doc = build_world(run_id)
    rolling = RollingVocabulary(doc) or None
    parser = QuestionParser(model=parse_model, _client=parse_counter)
    synth = Synthesizer(model=synth_model, _client=synth_counter)
    model = (parse_model if parse_tier == synth_tier
             else f"{parse_tier}+{synth_tier}")

    rows, latencies = [], []
    for q in bank:
        parse_counter.reset()
        synth_counter.reset()
        ctx = {"selection": q.selection, "history": []}
        t0 = time.perf_counter()
        try:
            parsed = parser.parse(q.text, explainer=ex, context=ctx,
                                  rolling=rolling)
            if parsed is None:
                text, route = "", "PARSE_UNAVAILABLE"
            else:
                d = dispatch(ex, parsed, synthesizer=synth, context=ctx,
                             document=doc, session_id=f"bench-{tier}")
                text, route = TemplateRenderer().render(d.bundle), d.route
        except Exception as exc:  # noqa: BLE001 — a bench never dies on one row
            text, route = f"<error: {type(exc).__name__}: {exc}>", "ERROR"
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        cost = (parse_counter.input_tokens / 1e6 * p_in
                + parse_counter.output_tokens / 1e6 * p_out
                + synth_counter.input_tokens / 1e6 * s_in
                + synth_counter.output_tokens / 1e6 * s_out)
        row = {"qid": q.qid, "question": q.text, "multihop": q.multihop,
               "latency_ms": round(elapsed_ms, 1), "cost_usd": round(cost, 6),
               "calls": parse_counter.calls + synth_counter.calls,
               "in_tokens": parse_counter.input_tokens + synth_counter.input_tokens,
               "out_tokens": parse_counter.output_tokens + synth_counter.output_tokens,
               "answer": text, **score(q, text, route)}
        rows.append(row)
        if verbose:
            mark = "OK " if row["correct"] else "   "
            print(f"  {mark}{q.qid:<20} route={route:<18} "
                  f"{elapsed_ms/1000:5.1f}s  ${cost:.5f}")

    multi = [r for r in rows if r["multihop"]]
    return {
        "tier": tier, "model": model, "rows": rows,
        "n": len(rows),
        "correct": sum(r["correct"] for r in rows),
        "reached_fact": sum(r["reached_fact"] for r in rows),
        "multihop_n": len(multi),
        "multihop_correct": sum(r["correct"] for r in multi),
        "said_forbidden": sum(r["said_forbidden"] for r in rows),
        "median_latency_ms": round(statistics.median(latencies), 1),
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        "cost_per_question_usd": round(
            sum(r["cost_usd"] for r in rows) / max(len(rows), 1), 6),
    }


def render_table(results: list[dict]) -> str:
    head = (f"{'tier':<10}{'model':<22}{'correct':>9}{'fact':>7}"
            f"{'multihop':>10}{'false':>7}{'median s':>10}{'$/question':>12}")
    lines = [head, "-" * len(head)]
    for r in results:
        lines.append(
            f"{r['tier']:<10}{r['model']:<22}"
            f"{r['correct']:>4}/{r['n']:<4}"
            f"{r['reached_fact']:>7}"
            f"{r['multihop_correct']:>6}/{r['multihop_n']:<3}"
            f"{r['said_forbidden']:>7}"
            f"{r['median_latency_ms']/1000:>10.1f}"
            f"{r['cost_per_question_usd']:>12.5f}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", default=DEFAULT_RUN, help="run id under _data/runs")
    ap.add_argument("--tiers", default="haiku,sonnet,opus")
    ap.add_argument("--out", default="", help="write the full JSON report here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    known = set(TIERS) | set(SPLITS)
    unknown = [t for t in tiers if t not in known]
    if unknown:
        print(f"unknown tier(s): {unknown}; known: {sorted(known)}")
        return 2

    results = []
    for tier in tiers:
        if not args.quiet:
            label = (f"parse={TIERS[SPLITS[tier][0]][0]}, "
                     f"synthesis={TIERS[SPLITS[tier][1]][0]}"
                     if tier in SPLITS else TIERS[tier][0])
            print(f"\n=== {tier} ({label}) ===")
        results.append(run_tier(tier, args.run, BANK, not args.quiet))

    print("\n" + render_table(results))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"\nfull report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
