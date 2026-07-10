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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_HELP_TEXT = """\
Example questions:
  Why is WO-2001 late?
  Why is WO-2001 on M-GEAR-02?
  What data problems exist?
  What changed since snap-demo-v1 vs snap-demo-v2?
  When does WO-2001 start?
  What is running on M-GEAR-01?
  Show the schedule
  summarize                  (run summary)
  diff snap-demo-v1 snap-demo-v2

What-if questions (trigger scenario re-solve):
  what if we unbatch WO-2001 and WO-2002

Commands:
  reset        clear conversation history
  help / ?     show this message
  quit / exit  exit the REPL

Dialogue mode (--llm only):
  After a routed answer, any unrecognised follow-up is treated as a
  conversational turn. The LLM reasons over prior evidence bundles only
  and labels its reply [register: judgment].
"""

# ---------------------------------------------------------------------------
# Session history (REPL only — one-shot never touches this)
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """One REPL turn: question + optional evidence bundle + rendered text."""
    question: str
    bundle: Any   # ExplanationBundle | None  (None for judgment turns)
    rendered: str


class SessionHistory:
    """Circular buffer of the last max_turns turns."""

    def __init__(self, max_turns: int = 10) -> None:
        self._turns: list[Turn] = []
        self._max = max_turns

    def append(self, turn: Turn) -> None:
        self._turns.append(turn)
        if len(self._turns) > self._max:
            self._turns = self._turns[-self._max:]

    def reset(self) -> None:
        self._turns.clear()

    def is_empty(self) -> bool:
        return not self._turns

    def turns(self) -> list[Turn]:
        return list(self._turns)

    def __len__(self) -> int:
        return len(self._turns)

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
        # A REJECTED submission writes an evidence index but no snapshot; the
        # Explainer runs in certificate-only mode. Only the certificate
        # questions (what's wrong / how do I fix / what first) will answer.
        print(
            f"[mre.ask] No snapshot '{snapshot_id}' — certificate-only mode "
            "(REJECTED submission). Certificate questions only.",
            file=sys.stderr,
        )

    store = SnapshotStore(out_dir / "snapshots")
    index = EvidenceIndex.load(index_path)
    explainer = Explainer(store, index, snapshot_id=snapshot_id)
    return explainer, store


def _assemble_bundle(explainer: Any, question: str) -> Any:
    """Route a question to the right bundle assembler."""
    q = question.strip()
    if q.lower() == "summarize":
        return explainer.summarize_run()
    if q.lower().startswith(_DIFF_PREFIXES):
        rest = q.split(None, 1)[1] if " " in q else ""
        parts = rest.split()
        if len(parts) >= 2:
            return explainer.answer(f"What changed since {parts[0]} vs {parts[1]}?")
        return explainer.answer(q)
    return explainer.answer(q)


def _render(explainer: Any, question: str, use_llm: bool) -> str:
    """One-shot render — no history, no judgment path."""
    from mre.modules.renderers import LLMRenderer, TemplateRenderer

    bundle = _assemble_bundle(explainer, question)
    renderer = LLMRenderer() if use_llm else TemplateRenderer()
    return renderer.render(bundle)


def _parse_whatif_scenario(question: str, snap_id: str, explainer: Any = None) -> Any:
    """Return a Scenario if the question describes a testable what-if, else None."""
    from mre.modules.scenario import Scenario, SuppressMerge

    q = question.lower()
    suppress_triggers = ("unbatch", "separate", "unmerge", "unsplit")
    merge_triggers = ("batch", "merge")

    # "what if we unbatch WO-2001 and WO-2002" or "separate WO-2001 and WO-2002"
    is_suppress = any(kw in q for kw in suppress_triggers)
    is_what_if_merge = (
        "what if" in q
        and any(kw in q for kw in merge_triggers)
        and ("not" in q or "without" in q or "no " in q)
    )
    if is_suppress or is_what_if_merge:
        # Order refs in the customer's own vocabulary (identity-map match,
        # same bridge the explainer routes with); WO-… regex as fallback.
        known = getattr(explainer, "_order_refs", {}) if explainer else {}
        wo_matches = [
            known[tok.upper().strip(".,?!")]
            for tok in re.findall(r"[\w][\w./-]*", question)
            if tok.upper().strip(".,?!") in known
        ]
        if len(wo_matches) < 2:
            wo_matches = [w.upper() for w in re.findall(r'WO-[\w-]+', question, re.IGNORECASE)]
        if len(wo_matches) >= 2:
            return Scenario(
                base_snapshot_id=snap_id,
                modifications=[SuppressMerge(demand_refs=wo_matches)],
            )
    return None


def _make_diff_bundle(result: Any, explainer: Any) -> Any:
    """Wrap a ScenarioResult diff in an ExplanationBundle for rendering."""
    from mre.modules.explainer import ExplanationBundle

    diff = result.diff
    return ExplanationBundle(
        question=f"What if we {diff.get('description', '?')}?",
        subject_id=result.scenario_snapshot_id,
        subject_type="scenario_diff",
        subject_external_name=diff.get("description", "?"),
        ordered_records=[],
        key_facts=diff,
        snapshot_id=result.base_snapshot_id,
        identity_map=explainer._identity_map,
    )


def _render_repl_turn(
    explainer: Any,
    question: str,
    use_llm: bool,
    history: SessionHistory,
    scenario_runner: Optional[Any] = None,
) -> tuple[str, Optional[Any]]:
    """REPL render — may invoke judgment or scenario path.

    Returns (rendered_text, bundle_or_None).
    bundle is None for judgment turns (no evidence was assembled).
    """
    from mre.modules.renderers import LLMRenderer, TemplateRenderer

    # What-if routing: detect and run scenario before normal routing
    if scenario_runner is not None:
        snap_id = getattr(explainer, "_snap_id", "snap-run")
        scenario = _parse_whatif_scenario(question, snap_id, explainer)
        if scenario is not None:
            print("[mre.ask] running scenario — this may take a moment...")
            try:
                result = scenario_runner.run(scenario)
                diff_bundle = _make_diff_bundle(result, explainer)
                renderer = LLMRenderer() if use_llm else TemplateRenderer()
                return renderer.render(diff_bundle), diff_bundle
            except Exception as exc:  # noqa: BLE001
                error_text = f"[scenario error] {exc}"
                return error_text, None

    bundle = _assemble_bundle(explainer, question)

    if bundle.subject_type == "unsupported" and not history.is_empty() and use_llm:
        rendered = LLMRenderer().render_judgment(question, history, bundle)
        return rendered, None

    renderer = LLMRenderer() if use_llm else TemplateRenderer()
    return renderer.render(bundle), bundle


def main(argv: list[str] | None = None) -> int:
    # Windows consoles (and redirected stdout) default to cp1252, which
    # cannot encode characters the renderers legitimately emit (e.g. the
    # '→' in assignment Decision messages) — a REPL turn would die with
    # 'charmap' codec errors. Render lossily rather than crash.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

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
    explainer, store = _load(out_dir, args.snapshot_id)

    # One-shot mode — no scenario runner (requires interactive intent)
    if args.question:
        print(_render(explainer, args.question, args.llm))
        return 0

    # Interactive REPL — wire up scenario runner under the BASE run's
    # configuration (policy, exclusions context, reference date, solver
    # pinning) so what-if diffs measure the modification, not drift.
    from mre.modules.scenario import ScenarioRunner, derive_base_context
    base_ctx = derive_base_context(out_dir / "runs")
    scenario_runner = ScenarioRunner(
        store, out_dir / "scenario_runs",
        time_limit_seconds=base_ctx.get("time_limit", 30.0),
        base_context=base_ctx,
    )

    print(f"[mre.ask] Evidence index loaded ({args.snapshot_id}). Type 'help' for examples, 'quit' to exit.")
    if args.llm:
        print("[mre.ask] LLM renderer active. Unrouted follow-ups will use judgment mode.")
    print('[mre.ask] What-if: try "what if we unbatch WO-2001 and WO-2002"')

    history = SessionHistory()

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

        if raw.lower() == "reset":
            history.reset()
            print("[history cleared]")
            continue

        try:
            print()
            rendered, bundle = _render_repl_turn(
                explainer, raw, args.llm, history, scenario_runner
            )
            print(rendered)
            history.append(Turn(question=raw, bundle=bundle, rendered=rendered))
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
