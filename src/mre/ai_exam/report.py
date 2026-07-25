"""Transcript + sidecar rendering (Session 4A.3b, CU1).

Plain ASCII, matching the founder's paste format — no box-drawing, no emoji. The
transcript is what a human reads and triages; the sidecar is the mechanical
findings JSON that seeds Claude's triage.
"""
from __future__ import annotations

import json
from typing import Any

from .runner import ExamResult, TurnRecord


_RULE = "-" * 72


def _conf(c: Any) -> str:
    return f"{c:.2f}" if isinstance(c, (int, float)) else "-"


def render_transcript(result: ExamResult) -> str:
    lines: list[str] = []
    lines.append("AI EXAM TRANSCRIPT")
    lines.append(f"target      : {result.target_label}")
    lines.append(f"snapshot    : {result.snapshot_id}")
    lines.append(f"started     : {result.started_at}")
    lines.append(f"llm mode    : {result.llm_mode}")
    lines.append(f"questions   : {len(result.turns)}")
    lines.append(f"llm calls   : {result.total_llm_calls}")
    counts = result.finding_counts()
    lines.append("sidecar     : " + (
        ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else "clean"))
    lines.append(_RULE)

    for t in result.turns:
        for c in getattr(t, "_comments", []) or []:
            lines.append(f"# {c}")
        lines.append(f"Q[{t.lineno}]: {t.question}")
        if t.selection:
            lines.append("  selection: " + ", ".join(
                f"{k}={v}" for k, v in t.selection.items()))
        if t.error:
            lines.append(f"  !! ASK-PATH FAILURE: {t.error}")
            lines.append(_RULE)
            continue
        # interpreted-as line WITH the resolution source
        if t.resolved_question and t.resolved_question != t.question:
            note = f"  ({t.resolution_note})" if t.resolution_note else ""
            lines.append(f"  interpreted as: {t.resolved_question}{note}")
        lines.append(
            f"  route={t.route}  source={t.source}  conf={_conf(t.confidence)}  "
            f"register={t.register}  renderer={t.renderer}")
        lines.append(
            f"  lit-bars={t.lit_bars}  records={t.record_count}  "
            f"refs={_refs_str(t.cited_refs)}")
        lines.append("  A:")
        for aln in (t.answer or "").splitlines():
            lines.append(f"    {aln}" if aln else "")
        if t.findings:
            for f in t.findings:
                lines.append(f"  >> sidecar[{f.kind}]: {f.detail}")
        lines.append(_RULE)

    return "\n".join(lines) + "\n"


def _refs_str(refs: dict) -> str:
    if not refs:
        return "0/0/0"
    return "{}/{}/{}".format(
        len(refs.get("operations", [])),
        len(refs.get("resources", [])),
        len(refs.get("demands", [])))


def render_sidecar(result: ExamResult) -> str:
    """The machine-readable findings sidecar (JSON) that seeds triage."""
    payload = {
        "target": result.target_label,
        "snapshot": result.snapshot_id,
        "started_at": result.started_at,
        "llm_mode": result.llm_mode,
        "questions": len(result.turns),
        "llm_calls": result.total_llm_calls,
        "finding_counts": result.finding_counts(),
        "findings": [
            {"kind": f.kind, "lineno": f.lineno, "question": f.question,
             "detail": f.detail}
            for f in result.findings
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
