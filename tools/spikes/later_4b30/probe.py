"""Session 4B.30 — drive the LIVE ask path against a registered board.

Mirrors what ``POST /schedules/{id}/ask`` does (document + snapshot + out_dir +
one continuous conversation with history), so a measured turn here is the turn a
planner gets. No fixtures: the point is the live dispatch.

    python tools/spikes/later_4b30/probe.py --schedule rolling-c9973708-865 \
        --q "can i move ORD-000057 later, maintenance wants the machine for the day"
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))


def load_board(data_root: Path, schedule_id: str):
    con = sqlite3.connect(str(data_root / "registry.sqlite"))
    con.row_factory = sqlite3.Row
    row = dict(con.execute("select * from schedules where id=?",
                           (schedule_id,)).fetchone())
    run = dict(con.execute("select * from runs where id=?",
                           (row["run_id"],)).fetchone())
    doc = None
    try:
        doc = json.loads(Path(row["document_path"]).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        doc = None
    return row, run, doc


def build_explainer(out_dir: Path, snapshot_id: str, runs_subdir: str):
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore

    index_path = out_dir / "evidence_index.json"
    index = (EvidenceIndex.load(index_path) if index_path.exists()
             else EvidenceIndex().build(out_dir / runs_subdir))
    try:
        return Explainer(SnapshotStore(out_dir / "snapshots"), index,
                         snapshot_id=snapshot_id, out_dir=out_dir,
                         runs_subdir=runs_subdir)
    except TypeError:
        # The CENSUS runs against the pre-change Explainer, which has no pricing
        # plumbing. Measuring the defect needs the code that has it.
        return Explainer(SnapshotStore(out_dir / "snapshots"), index,
                         snapshot_id=snapshot_id)


def main() -> int:
    from mre.env_local import load_env_local
    load_env_local()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=str(ROOT / "_data"))
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--q", action="append", default=[],
                    help="one turn; repeat for a continuous conversation")
    ap.add_argument("--questions-file", default=None,
                    help="a file of one question per line (# comments skipped)")
    ap.add_argument("--fresh", action="store_true",
                    help="drop history between turns (independent probes)")
    ap.add_argument("--selection", default=None, help="JSON board selection")
    args = ap.parse_args()

    from mre.modules.interpreter import run_ask
    from mre.modules.question_parser import QuestionParser
    from mre.modules.renderers import TemplateRenderer
    from mre.modules.synthesizer import Synthesizer

    questions = list(args.q)
    if args.questions_file:
        for line in Path(args.questions_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                questions.append(line)

    data_root = Path(args.data_root)
    row, run, doc = load_board(data_root, args.schedule)
    runs_subdir = "scenario_runs" if row["is_scenario"] else "runs"
    explainer = build_explainer(Path(run["out_dir"]), row["snapshot_id"],
                                runs_subdir)
    parser = QuestionParser()
    synth = Synthesizer()
    renderer = TemplateRenderer()
    selection = json.loads(args.selection) if args.selection else None

    history: list[dict] = []
    last_subject = None
    print(f"### BOARD {args.schedule}  ({row['contract_version']})")
    for i, q in enumerate(questions, start=1):
        t0 = time.monotonic()
        res = run_ask(explainer, q,
                      context={"history": history, "selection": selection,
                               "last_answered_subject": last_subject,
                               "card": None},
                      parser=parser, synthesizer=synth, document=doc,
                      session_id="probe-4b30")
        text = renderer.render(res.bundle)
        wall = round(time.monotonic() - t0, 2)
        p = res.parsed
        print(f"\n{'=' * 72}\nTURN {i}: {q}\n{'-' * 72}")
        print(f"[intent={p.intent.value if p else '?'} "
              f"route={res.route} conf={res.confidence} "
              f"register={res.register} "
              f"move_direction={getattr(p, 'move_direction', None)} "
              f"move_target={getattr(p, 'move_target', None)!r} "
              f"wall={wall}s]")
        print(text)
        if not args.fresh:
            history.append({"question": q, "answer": text})
            if res.bundle is not None:
                name = getattr(res.bundle, "subject_external_name", None)
                last_subject = {"order": name} if name else None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
