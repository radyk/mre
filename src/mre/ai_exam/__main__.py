"""``python -m mre.ai_exam`` — fire a question script through the ask path.

Usage (API-parity, resolves a schedule id in a data root):
    python -m mre.ai_exam --run <schedule_id> --data-root <path> \
        --questions bank.txt --transcript out.txt

Usage (CI/test, straight at a solved out-dir; no Registry):
    python -m mre.ai_exam --out-dir <run_out> --snapshot-id snap-exam \
        --questions bank.txt --transcript out.txt

The sidecar JSON is written next to the transcript (``out.sidecar.json``) unless
``--sidecar`` names another path. ``--limit`` caps the number of questions; the
per-question timeout defaults to 90s. The runner prints its LLM mode and a live-call
count at close (a sweep is hundreds of live calls when a key is present).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .report import render_sidecar, render_transcript
from .runner import ExamRunner, RunTarget
from .script import parse_script


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mre.ai_exam", description=__doc__)
    src = p.add_argument_group("pinned run (choose one)")
    src.add_argument("--run", help="schedule id to resolve via the Registry")
    src.add_argument("--data-root", help="data root for --run (default $MRE_DATA_ROOT)")
    src.add_argument("--out-dir", help="a solved run out-dir (bypasses the Registry)")
    src.add_argument("--snapshot-id", help="snapshot id for --out-dir")
    src.add_argument("--scenario", action="store_true",
                     help="--out-dir is a scenario run (scenario_runs subdir)")
    src.add_argument("--document", help="optional schedule document json (rolling)")

    p.add_argument("--questions", required=True, help="the question script")
    p.add_argument("--transcript", required=True, help="transcript output path")
    p.add_argument("--sidecar", help="sidecar json path (default <transcript>.sidecar.json)")
    p.add_argument("--limit", type=int, help="cap the number of questions fired")
    p.add_argument("--timeout", type=float, default=90.0,
                   help="per-question timeout seconds (default 90)")
    p.add_argument("--llm", choices=["auto", "on", "off"], default="auto",
                   help="LLM mode: auto (on iff a key is set), on, off")
    p.add_argument("--ledger", help="optional question-ledger path to write asks to")
    p.add_argument("--session-id", default="ai-exam")
    return p


def _resolve_target(args: argparse.Namespace) -> RunTarget:
    if args.run:
        data_root = args.data_root or _env("MRE_DATA_ROOT")
        if not data_root:
            raise SystemExit("--run requires --data-root or $MRE_DATA_ROOT")
        return RunTarget.from_schedule(data_root, args.run)
    if args.out_dir:
        if not args.snapshot_id:
            raise SystemExit("--out-dir requires --snapshot-id")
        return RunTarget.from_out_dir(
            args.out_dir, args.snapshot_id, scenario=args.scenario,
            document_path=Path(args.document) if args.document else None,
            label=f"out-dir:{Path(args.out_dir).name}")
    raise SystemExit("provide --run (with --data-root) or --out-dir (with --snapshot-id)")


def _env(name: str) -> str:
    import os
    return os.environ.get(name, "")


def main(argv: list[str] | None = None) -> int:
    # Errand 4B.16a — this front door had NO loader, so from a bare shell it built
    # an unavailable parser and every answer landed on the honest
    # could-not-interpret floor: indistinguishable from a key that is missing, and
    # one of the readings behind docs/07 §5a.7's three-session-old rumour. An
    # already-set variable still wins; a missing file is a no-op.
    from mre.env_local import load_env_local
    load_env_local()

    args = build_parser().parse_args(argv)
    target = _resolve_target(args)

    use_llm = {"auto": None, "on": True, "off": False}[args.llm]
    # R-EX2: a bank may REBIND to another schedule mid-sequence, which needs a
    # data root to resolve against. `--out-dir` runs have none, and a REBIND
    # there is a loud finding rather than a silent continuation.
    runner = ExamRunner(
        target, use_llm=use_llm,
        ledger_path=Path(args.ledger) if args.ledger else None,
        per_question_timeout=args.timeout, session_id=args.session_id,
        data_root=args.data_root or _env("MRE_DATA_ROOT") or None)

    script = parse_script(Path(args.questions).read_text(encoding="utf-8"))
    result = runner.run(script, limit=args.limit)

    transcript_path = Path(args.transcript)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(render_transcript(result), encoding="utf-8")

    sidecar_path = Path(args.sidecar) if args.sidecar else transcript_path.with_suffix(
        transcript_path.suffix + ".sidecar.json")
    sidecar_path.write_text(render_sidecar(result), encoding="utf-8")

    counts = result.finding_counts()
    print(f"ai-exam: {len(result.turns)} question(s), llm mode {result.llm_mode}, "
          f"{result.total_llm_calls} live call(s)")
    if result.parser_stats:
        ps = result.parser_stats
        med = ps.get("median_latency_ms")
        print(f"ai-exam: parse: {ps['parses']} parse(s), {ps['calls']} call(s), "
              f"{ps['retries']} retry, {ps['malformed']} malformed, "
              f"{ps['clarifies']} clarify, median "
              f"{'-' if med is None else f'{med:.0f}ms'}")
    graded, met = result.graded()
    if graded:
        print(f"ai-exam: graded expectations: {met}/{graded} met")
    print(f"ai-exam: door check: {result.door_check}")
    print(f"ai-exam: sidecar findings: "
          f"{', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'clean'}")
    print(f"ai-exam: transcript -> {transcript_path}")
    print(f"ai-exam: sidecar    -> {sidecar_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
