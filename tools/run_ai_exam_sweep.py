"""Run the FULL exam bank set against a pinned run and write a sweep directory.

Session 4A.5a CU5 — the re-baseline sweep. Fires every committed bank through the
REAL ask path (LLM-first parse + the live renderer when a key is present) against
one pinned world, writes a transcript + sidecar per bank under a dated sweep
directory, and prints the comparison table the close-out states.

    python tools/run_ai_exam_sweep.py \
        --out-dir _ai_exam_scratch/gb_pinned --snapshot-id snap-exam \
        --sweep-dir tests/ai_exam/sweeps/2026-07-26-synthesis

The banks are read from tests/ai_exam/banks/ (every .txt). One parser is shared
across the whole sweep so the parse-specific counts (clarify / retry / malformed
rates, median latency) are the sweep's, not one bank's.

Session 4A.5b: ONE SYNTHESIZER is shared the same way, so the second tier's counts
— claims by verdict, the ungrounded-load-bearing count, the tool-call histogram —
are also the sweep's; and the run reports TOTAL conversational latency split by
tier (parse+route vs parse+synthesis), which is the number the next round needs.

Session 4A.5c: the sweep WRITES A QUESTION LEDGER (``ledger.jsonl``) and emits the
PROVENANCE REPORT from it (``PROVENANCE.txt`` / ``.json``) beside the sidecars —
R-AI5(5)'s standing prioritization, produced automatically rather than on request.
Every ask already logged an entry; what the sweep lacked was a path to write it to,
so the residue that R-AI5(5) exists to rank was being computed and discarded 300
times a run.

The key is read from the gitignored ``.env.local`` at the repo root (the same
source every prior sweep used) when it is not already in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_env_local() -> None:
    """Load the gitignored .env.local into this process's environment, without
    printing anything from it. An already-set variable always wins."""
    path = Path(__file__).resolve().parents[1] / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


load_env_local()

from mre.ai_exam.report import render_sidecar, render_transcript  # noqa: E402
from mre.ai_exam.runner import ExamRunner, RunTarget  # noqa: E402
from mre.ai_exam.script import parse_script  # noqa: E402

BANKS_DIR = Path(__file__).resolve().parents[1] / "tests" / "ai_exam" / "banks"

#: Banks that must run against the PINNED ROLLING RUN rather than the monolithic
#: glass_box world. A rolling question asked of a monolithic world is answered
#: "this isn't a rolling schedule" — honest, and a test of nothing — so these are
#: SKIPPED LOUDLY when the rolling target is absent, never run vacuously.
#:
#: `regression_founder_r5` joins in Session 4B.5: the founder's round-five session
#: ran on a rolling board, and three of its specimens are only askable there (a
#: delta card exists because a gesture was priced against a sliced window).
ROLLING_BANKS = frozenset({"sweep_rolling", "regression_founder_r5"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--snapshot-id", required=True)
    ap.add_argument("--sweep-dir", required=True)
    ap.add_argument("--banks", nargs="*", help="bank file names (default: all)")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rolling-target",
                    default="_ai_exam_scratch/rolling_pinned",
                    help="the pinned ROLLING run (tools/build_rolling_exam_run.py). "
                         "The rolling bank asks THIS world; every other bank asks "
                         "the monolithic one.")
    args = ap.parse_args(argv)

    sweep_dir = Path(args.sweep_dir)
    sweep_dir.mkdir(parents=True, exist_ok=True)
    banks = ([BANKS_DIR / b for b in args.banks] if args.banks
             else sorted(BANKS_DIR.glob("*.txt")))

    target = RunTarget.from_out_dir(args.out_dir, args.snapshot_id,
                                    label=f"out-dir:{Path(args.out_dir).name}")

    # Session 4A.5c CU5 — the ROLLING bank asks a DIFFERENT world. The monolithic
    # glass_box run has no sliced state, so every rolling question there is
    # answered "this isn't a rolling schedule" — honest, and a test of nothing.
    # Built by tools/build_rolling_exam_run.py; SKIPPED loudly (never silently
    # passed against the wrong world) when it has not been built.
    rolling_target = _rolling_target(args.rolling_target)
    # ONE parser and ONE synthesizer for the whole sweep — both tiers' counts are
    # then the sweep's, not one bank's.
    from mre.modules.question_parser import QuestionParser
    from mre.modules.synthesizer import Synthesizer
    parser = QuestionParser()
    synthesizer = Synthesizer()
    print(f"sweep: parser available={parser.available} "
          f"prompt_version={parser.prompt_version}")
    print(f"sweep: synthesizer available={synthesizer.available} "
          f"prompt_version={synthesizer.prompt_version}")

    # A SWEEP DIRECTORY IS ONE RUN. Stale outputs are cleared before anything
    # fires, because a directory holding one bank's transcript from an older run
    # beside the rest is exactly the thing 4A.5b named: a committed sweep that does
    # not match the committed code is not evidence. A re-run that dies halfway must
    # leave an obviously INCOMPLETE sweep, never a plausible mixed one.
    for stale in ("SWEEP.json", "PROVENANCE.txt", "PROVENANCE.json",
                  "ledger.jsonl"):
        (sweep_dir / stale).unlink(missing_ok=True)
    for stale_bank in list(sweep_dir.glob("*.txt")) + \
            list(sweep_dir.glob("*.sidecar.json")):
        stale_bank.unlink(missing_ok=True)

    # ONE ledger for the whole sweep (Session 4A.5c). The provenance report is a
    # read over it, so a per-bank ledger would produce per-bank Paretos — which is
    # exactly the wrong grain: a recurring SHAPE recurs across banks.
    ledger_path = sweep_dir / "ledger.jsonl"

    summary = []
    latencies: dict[str, list[float]] = {"route": [], "synthesis": []}
    skipped: list = []
    for bank in banks:
        bank_target = target
        if bank.stem in ROLLING_BANKS:
            if rolling_target is None:
                print(f"sweep: {bank.stem}: SKIPPED — no pinned rolling run at "
                      f"{args.rolling_target}. Build it with "
                      f"'python tools/build_rolling_exam_run.py'. NOT run against "
                      f"the monolithic world, which would pass vacuously.")
                skipped.append(bank.stem)
                continue
            bank_target = rolling_target
        runner = ExamRunner(bank_target, per_question_timeout=args.timeout,
                            parser=parser, synthesizer=synthesizer,
                            ledger_path=ledger_path,
                            session_id=f"sweep-{bank.stem}")
        result = runner.run(parse_script(bank.read_text(encoding="utf-8")),
                            limit=args.limit)
        (sweep_dir / f"{bank.stem}.txt").write_text(
            render_transcript(result), encoding="utf-8")
        (sweep_dir / f"{bank.stem}.sidecar.json").write_text(
            render_sidecar(result), encoding="utf-8")
        graded, met = result.graded()
        row = {"bank": bank.stem, "questions": len(result.turns),
               "target": bank_target.label,
               "graded": graded, "met": met,
               "findings": result.finding_counts(),
               "llm_calls": result.total_llm_calls,
               "synthesis": result.synthesis_totals(),
               "shadow": result.shadow_totals(),
               "latency": result.latency()}
        summary.append(row)
        for t in result.turns:
            if t.error is None and t.latency_ms is not None:
                latencies["synthesis" if t.synthesis else "route"].append(
                    t.latency_ms)
        print(f"sweep: {bank.stem}: {len(result.turns)} q, graded {met}/{graded}, "
              f"findings {row['findings'] or 'clean'}, "
              f"synthesis answers={row['synthesis']['answers']}")

    totals: dict = {}
    for row in summary:
        for k, v in row["findings"].items():
            totals[k] = totals.get(k, 0) + v
    synth_totals: dict = {}
    histogram: dict = {}
    for row in summary:
        for k, v in row["synthesis"].items():
            if isinstance(v, int):
                synth_totals[k] = synth_totals.get(k, 0) + v
            elif k == "tool_histogram":
                for tool, n in v.items():
                    histogram[tool] = histogram.get(tool, 0) + n
    payload = {
        "target": target.label, "snapshot": args.snapshot_id,
        "banks": summary,
        "totals": {"questions": sum(r["questions"] for r in summary),
                   "graded": sum(r["graded"] for r in summary),
                   "met": sum(r["met"] for r in summary),
                   "findings": totals},
        # Named, never silent: a bank that did not run is not a bank that passed.
        "skipped_banks": skipped,
        "shadow": _merge_shadow(summary),
        "synthesis_totals": {**synth_totals,
                             "tool_histogram": dict(sorted(histogram.items()))},
        "latency": {k: _stats(v) for k, v in latencies.items()},
        "parser_stats": parser.stats.as_dict(),
        "synth_stats": synthesizer.stats.as_dict(),
    }
    (sweep_dir / "SWEEP.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    # R-AI5(5) — the standing report, emitted automatically. Never a separate step
    # someone has to remember: the prioritization is a PRODUCT of the sweep.
    from mre.modules.provenance_report import rows_from_ledger, write_report
    rows = rows_from_ledger(ledger_path)
    if rows:
        txt, _js = write_report(rows, sweep_dir, source=str(ledger_path))
        print(f"sweep: provenance report -> {txt}")
    else:
        print("sweep: NO LEDGER ROWS — provenance report SKIPPED (not clean)")

    print(json.dumps(payload["totals"], indent=2))
    print(json.dumps(payload["shadow"], indent=2))
    print(json.dumps(payload["synthesis_totals"], indent=2))
    print(json.dumps(payload["latency"], indent=2))
    print(json.dumps(payload["parser_stats"], indent=2))
    print(f"sweep: -> {sweep_dir}")
    return 0


def _merge_shadow(summary: list) -> dict:
    """The PROBATION block across the whole sweep (R-AI5(7)). ``diverged`` is the
    number that means something on its own: it is the demotion trigger."""
    out = {"shadowed": 0, "clean": 0, "diverged": 0, "unchecked": 0,
           "provenance_strengthened": 0}
    by_intent: dict = {}
    for row in summary:
        sh = row.get("shadow") or {}
        for k in out:
            out[k] += int(sh.get(k) or 0)
        for intent, counts in (sh.get("by_intent") or {}).items():
            dest = by_intent.setdefault(
                intent, {"shadowed": 0, "diverged": 0, "unchecked": 0})
            for k in dest:
                dest[k] += int(counts.get(k) or 0)
    return {**out, "by_intent": by_intent}


def _rolling_target(path: str):
    """The pinned rolling run as a ``RunTarget``, or None when it has not been
    built. Reads TARGET.json — the builder writes the snapshot id and document
    path there so the sweep never has to guess either."""
    d = Path(path)
    manifest = d / "TARGET.json"
    if not manifest.exists():
        return None
    try:
        spec = json.loads(manifest.read_text(encoding="utf-8"))
        return RunTarget.from_out_dir(
            spec["out_dir"], spec["snapshot_id"],
            document_path=Path(spec["document_path"]),
            label=f"out-dir:{d.name} (rolling)")
    except Exception as exc:  # noqa: BLE001 — a bad manifest is a skip, not a crash
        print(f"sweep: rolling target unreadable ({exc}); the rolling bank will "
              f"be SKIPPED")
        return None


def _stats(xs: list) -> dict:
    """n / median / p90 for one latency bucket (rider c)."""
    xs = sorted(xs)
    if not xs:
        return {"n": 0, "median_ms": None, "p90_ms": None}
    mid = len(xs) // 2
    median = xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2
    return {"n": len(xs), "median_ms": round(median, 1),
            "p90_ms": round(xs[min(len(xs) - 1,
                                   int(round(0.9 * (len(xs) - 1))))], 1)}


if __name__ == "__main__":
    sys.exit(main())
