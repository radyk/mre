"""Interactive question answerer — python -m mre.ask.

Loads the evidence index and snapshot written by 'python -m mre', then
routes natural-language questions through the M10 Explainer.

Usage:
    python -m mre.ask                           # interactive REPL
    python -m mre.ask "Why is WO-2001 late?"   # one-shot
    python -m mre.ask --llm                     # use LLM renderer (needs ANTHROPIC_API_KEY)
    python -m mre.ask --out DIR --snapshot-id ID  # non-default output directory

Run 'python -m mre' first to generate the evidence index.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HELP_TEXT = """\
Example questions:
  Why is WO-2001 late?
  Why is WO-2001 on M-GEAR-02?
  What data problems exist?
  What changed since snap-demo-v1 vs snap-demo-v2?
  summarize                  (run summary)
  diff snap-demo-v1 snap-demo-v2

Commands:
  help / ?     show this message
  quit / exit  exit the REPL
"""

_DIFF_PREFIXES = ("diff ", "compare ")


def _load(out_dir: Path, snapshot_id: str):
    """Load EvidenceIndex and Explainer from an mre output directory."""
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore

    index_path = out_dir / "evidence_index.json"
    if not index_path.exists():
        print(
            f"[mre.ask] Evidence index not found at {index_path}.\n"
            "Run 'python -m mre' first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    snap_dir = out_dir / "snapshots" / snapshot_id
    if not snap_dir.exists():
        print(
            f"[mre.ask] Snapshot '{snapshot_id}' not found at {snap_dir}.\n"
            f"Run 'python -m mre --snapshot-id {snapshot_id}' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    store = SnapshotStore(out_dir / "snapshots")
    index = EvidenceIndex.load(index_path)
    explainer = Explainer(store, index, snapshot_id=snapshot_id)
    return explainer


def _render(explainer, question: str, use_llm: bool) -> str:
    from mre.modules.renderers import LLMRenderer, TemplateRenderer

    q = question.strip()
    renderer = LLMRenderer() if use_llm else TemplateRenderer()

    if q.lower() == "summarize":
        bundle = explainer.summarize_run()
    elif q.lower().startswith(_DIFF_PREFIXES):
        # e.g. "diff snap-a snap-b" or "compare snap-a snap-b"
        rest = q.split(None, 1)[1] if " " in q else ""
        parts = rest.split()
        if len(parts) >= 2:
            bundle = explainer.answer(f"What changed since {parts[0]} vs {parts[1]}?")
        else:
            bundle = explainer.answer(q)
    else:
        bundle = explainer.answer(q)

    return renderer.render(bundle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask the MRE evidence store a question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_HELP_TEXT,
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Question to answer (omit for interactive REPL)",
    )
    parser.add_argument("--out", default="mre_output", help="Output directory from 'python -m mre'")
    parser.add_argument("--snapshot-id", default="snap-run", help="Snapshot to query against")
    parser.add_argument("--llm", action="store_true", help="Use LLM renderer (needs ANTHROPIC_API_KEY)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    explainer = _load(out_dir, args.snapshot_id)

    # One-shot mode
    if args.question:
        print(_render(explainer, args.question, args.llm))
        return 0

    # Interactive REPL
    print(f"[mre.ask] Evidence index loaded ({args.snapshot_id}). Type 'help' for examples, 'quit' to exit.")
    if args.llm:
        print("[mre.ask] LLM renderer active.")

    while True:
        try:
            raw = input("\nask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        if raw.lower() in ("quit", "exit", "q"):
            break

        if raw.lower() in ("help", "?"):
            print(_HELP_TEXT)
            continue

        try:
            print()
            print(_render(explainer, raw, args.llm))
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
