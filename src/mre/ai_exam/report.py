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
    lines.append(f"door check  : {result.door_check}")
    if result.parser_stats:
        ps = result.parser_stats
        med = ps.get("median_latency_ms")
        lines.append(
            "parse       : parses={parses} calls={calls} retries={retries} "
            "malformed={malformed} clarifies={clarifies} unavailable={unavailable} "
            "median={med}".format(
                med="-" if med is None else f"{med:.0f}ms", **ps))
    graded, met = result.graded()
    if graded:
        lines.append(f"graded      : {met}/{graded} expectations met")
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
        if t.parse:
            lines.append("  parse: " + _parse_str(t.parse))
        if t.expect:
            ok = not any(f.kind == "expect-miss" for f in t.findings)
            lines.append("  expect: " + " ".join(
                f"{k}={v}" for k, v in t.expect.items()) +
                ("  -> MET" if ok else "  -> MISSED"))
        lines.append("  A:")
        for aln in (t.answer or "").splitlines():
            lines.append(f"    {aln}" if aln else "")
        if t.findings:
            for f in t.findings:
                lines.append(f"  >> sidecar[{f.kind}]: {f.detail}")
        lines.append(_RULE)

    return "\n".join(lines) + "\n"


def _parse_str(p: dict) -> str:
    """The parse contract on one line (Session 4A.5a): the intent it named, the
    subjects it bound and from where, and the follow-up linkage it read."""
    bits = [f"intent={p.get('intent')}", f"conf={_conf(p.get('confidence'))}"]
    if p.get("followup_of") and p["followup_of"] != "none":
        bits.append(f"followup={p['followup_of']}")
    if p.get("polarity"):
        bits.append(f"polarity={p['polarity']}")
    for s in p.get("subjects", []) or []:
        ref = s.get("ref") or "UNRESOLVED"
        bits.append(f"{s.get('kind')}={ref}<-{s.get('source')}(\"{s.get('raw')}\")")
    if p.get("clarify"):
        bits.append(f"clarify={p['clarify']}")
    if p.get("retries"):
        bits.append(f"retries={p['retries']}")
    if p.get("latency_ms") is not None:
        bits.append(f"{p['latency_ms']:.0f}ms")
    return "  ".join(bits)


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
        "parser_stats": result.parser_stats,
        "graded_expectations": {"graded": result.graded()[0],
                                "met": result.graded()[1]},
        "door_check": result.door_check,
        "finding_counts": result.finding_counts(),
        "findings": [
            {"kind": f.kind, "lineno": f.lineno, "question": f.question,
             "detail": f.detail}
            for f in result.findings
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
