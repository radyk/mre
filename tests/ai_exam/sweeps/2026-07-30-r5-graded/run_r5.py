"""Session 4B.17 driver: run regression_founder_r5 N times against the pinned
rolling world and emit a per-question row set plus measured token usage BY MODEL.

Nothing is mocked. The only instrumentation is a wrapper on the anthropic SDK's
messages.create that tallies each call's reported `usage` and the model it named
-- the same MEASURED-not-estimated discipline tools/model_tier_bench.py uses, so
the cost column is a measurement.

    python run_r5.py --label shipped --runs 3 --out <dir>
    MRE_SYNTHESIS_MODEL=claude-haiku-4-5-20251001 python run_r5.py --label haiku ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(r"C:\dev\mre")
sys.path.insert(0, str(REPO / "src"))

from mre.env_local import load_env_local  # noqa: E402

load_env_local()

BANK = REPO / "tests" / "ai_exam" / "banks" / "regression_founder_r5.txt"
TARGET_MANIFEST = REPO / "_ai_exam_scratch" / "rolling_pinned" / "TARGET.json"

#: Published rates, $ per million tokens (input, output) -- the same table
#: tools/model_tier_bench.py carries. The cost column is only as current as this.
RATES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
}


class Usage:
    """Per-model token tally, measured off each response's own `usage`."""

    def __init__(self) -> None:
        self.by_model: dict[str, dict[str, int]] = {}
        self._orig = None
        self._cls = None

    def __enter__(self) -> "Usage":
        from anthropic.resources.messages import Messages
        self._cls = Messages
        self._orig = Messages.create
        outer = self

        def _counted(self_inner, *a, **kw):
            resp = outer._orig(self_inner, *a, **kw)
            model = str(kw.get("model") or "?")
            row = outer.by_model.setdefault(
                model, {"calls": 0, "in": 0, "out": 0})
            row["calls"] += 1
            u = getattr(resp, "usage", None)
            if u is not None:
                row["in"] += getattr(u, "input_tokens", 0) or 0
                row["out"] += getattr(u, "output_tokens", 0) or 0
            return resp

        Messages.create = _counted
        return self

    def __exit__(self, *exc) -> None:
        if self._cls is not None:
            self._cls.create = self._orig

    def snapshot(self) -> dict:
        return {m: dict(v) for m, v in self.by_model.items()}

    @staticmethod
    def cost(snap: dict) -> float:
        total = 0.0
        for model, row in snap.items():
            rin, rout = RATES.get(model, (0.0, 0.0))
            total += row["in"] / 1e6 * rin + row["out"] / 1e6 * rout
        return total

    @staticmethod
    def delta(a: dict, b: dict) -> dict:
        out: dict = {}
        for model in set(a) | set(b):
            x = a.get(model, {"calls": 0, "in": 0, "out": 0})
            y = b.get(model, {"calls": 0, "in": 0, "out": 0})
            d = {k: y.get(k, 0) - x.get(k, 0) for k in ("calls", "in", "out")}
            if any(d.values()):
                out[model] = d
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from mre.ai_exam.report import render_sidecar, render_transcript
    from mre.ai_exam.runner import ExamRunner, RunTarget
    from mre.ai_exam.script import parse_script
    from mre.modules import llm_compat
    from mre.modules.question_parser import QuestionParser
    from mre.modules.synthesizer import Synthesizer

    spec = json.loads(TARGET_MANIFEST.read_text(encoding="utf-8"))
    target = RunTarget.from_out_dir(
        spec["out_dir"], spec["snapshot_id"],
        document_path=Path(spec["document_path"]),
        label="rolling-c362baa4-1b0")

    config = {"parse_model": llm_compat.parse_model(),
              "synthesis_model": llm_compat.synthesis_model(),
              "voice_model": llm_compat.voice_model()}
    print(f"[{args.label}] config {config}", flush=True)

    script = parse_script(BANK.read_text(encoding="utf-8"))
    all_runs = []

    with Usage() as usage:
        for n in range(1, args.runs + 1):
            # A FRESH parser and synthesizer per run: run-to-run variance is what
            # this measures, and a shared stats object would fuse the three.
            parser = QuestionParser()
            synth = Synthesizer()
            assert parser.available, "parser unavailable -- no key?"
            assert synth.available, "synthesizer unavailable -- no key?"
            before = usage.snapshot()
            t0 = time.perf_counter()
            runner = ExamRunner(target, per_question_timeout=args.timeout,
                                parser=parser, synthesizer=synth,
                                ledger_path=out / f"ledger-{args.label}-{n}.jsonl",
                                session_id=f"4b17-{args.label}-{n}")
            result = runner.run(script)
            wall = time.perf_counter() - t0
            after = usage.snapshot()
            tok = Usage.delta(before, after)
            (out / f"transcript-{args.label}-{n}.txt").write_text(
                render_transcript(result), encoding="utf-8")
            (out / f"sidecar-{args.label}-{n}.json").write_text(
                render_sidecar(result), encoding="utf-8")

            rows = []
            for t in result.turns:
                rows.append({
                    "lineno": t.lineno,
                    "question": t.question,
                    "selection": t.selection,
                    "intent": (t.parse or {}).get("intent"),
                    "confidence": t.confidence,
                    "route": t.route,
                    "source": t.source,
                    "register": t.register,
                    "renderer": t.renderer,
                    "subject_type": t.subject_type,
                    "subject": t.subject_external_name,
                    "records": t.record_count,
                    "lit_bars": t.lit_bars,
                    "latency_ms": round(t.latency_ms or 0.0, 1),
                    "llm_calls": t.llm_calls,
                    "parse": t.parse,
                    "synthesis": t.synthesis,
                    "shadow": {k: v for k, v in (t.shadow or {}).items()
                               if k != "answer"},
                    "expect": t.expect,
                    "expect_met": (bool(t.expect) and
                                   not any(f.kind == "expect-miss"
                                           for f in t.findings)),
                    "findings": [{"kind": f.kind, "detail": f.detail}
                                 for f in t.findings],
                    "error": t.error,
                    "answer": t.answer,
                })
            graded, met = result.graded()
            run_rec = {
                "label": args.label, "run": n, "config": config,
                "target": result.target_label, "snapshot": result.snapshot_id,
                "llm_mode": result.llm_mode,
                "wall_s": round(wall, 1),
                "questions": len(result.turns),
                "graded": graded, "met": met,
                "findings": result.finding_counts(),
                "latency": result.latency(),
                "synthesis_totals": result.synthesis_totals(),
                "shadow": result.shadow_totals(),
                "parser_stats": result.parser_stats,
                "synth_stats": result.synth_stats,
                "tokens": tok,
                "cost_usd": round(Usage.cost(tok), 4),
                "rows": rows,
            }
            all_runs.append(run_rec)
            print(f"[{args.label}] run {n}: {len(result.turns)} q, "
                  f"graded {met}/{graded}, {wall:.0f}s, "
                  f"findings {result.finding_counts() or 'clean'}, "
                  f"${run_rec['cost_usd']}", flush=True)
            (out / f"runs-{args.label}.json").write_text(
                json.dumps(all_runs, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8")
    print(f"[{args.label}] -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
