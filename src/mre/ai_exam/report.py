"""Transcript + sidecar rendering (Session 4A.3b, CU1).

Plain ASCII, matching the founder's paste format — no box-drawing, no emoji. The
transcript is what a human reads and triages; the sidecar is the mechanical
findings JSON that seeds Claude's triage.
"""
from __future__ import annotations

import json
from typing import Any

from .runner import ExamResult, TurnRecord
from .sidecar import _RELATIONAL_KEYS


_RULE = "-" * 72


def _conf(c: Any) -> str:
    return f"{c:.2f}" if isinstance(c, (int, float)) else "-"


def _ms(v: Any) -> str:
    return "-" if v is None else f"{v:.0f}ms"


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
    if result.synth_stats:
        ss = result.synth_stats
        med, p90 = ss.get("median_latency_ms"), ss.get("p90_latency_ms")
        lines.append(
            "synthesis   : answers={syntheses} calls={calls} tools={tool_calls} "
            "malformed={malformed} budget-out={budget_exhausted} "
            "unanswerable={unanswerable} median={med} p90={p90}".format(
                med="-" if med is None else f"{med:.0f}ms",
                p90="-" if p90 is None else f"{p90:.0f}ms",
                **{k: ss.get(k) for k in
                   ("syntheses", "calls", "tool_calls", "malformed",
                    "budget_exhausted", "unanswerable")}))
        tot = result.synthesis_totals()
        lines.append(
            "claims      : {claims} total  verified={verified} "
            "interpretive={interpretive} general-knowledge={general_knowledge} "
            "failed-and-cut={failed_and_cut} deferred={deferred}  "
            "ungrounded-load-bearing={ungrounded_load_bearing}".format(**tot))
    sh = result.shadow_totals()
    if sh["shadowed"]:
        lines.append(
            "probation   : shadowed={shadowed} clean={clean} "
            "DIVERGED={diverged} unchecked={unchecked} "
            "provenance-strengthened={provenance_strengthened}".format(**sh))
    lat = result.latency()
    lines.append(
        "latency     : route n={r[n]} median={rm} p90={rp} | "
        "synthesis n={s[n]} median={sm} p90={sp}".format(
            r=lat["route"], s=lat["synthesis"],
            rm=_ms(lat["route"]["median_ms"]), rp=_ms(lat["route"]["p90_ms"]),
            sm=_ms(lat["synthesis"]["median_ms"]),
            sp=_ms(lat["synthesis"]["p90_ms"])))
    graded, met = result.graded()
    if graded:
        lines.append(f"graded      : {met}/{graded} expectations met")
    counts = result.finding_counts()
    lines.append("sidecar     : " + (
        ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else "clean"))
    lines.append(_RULE)

    # R-EX2: a bank can now cross a version boundary mid-conversation, so the
    # transcript names the board per turn the moment more than one appears. On
    # every bank that does not REBIND this prints nothing and reads as before.
    boards = {t.schedule for t in result.turns if t.schedule}
    show_board = len(boards) > 1

    for t in result.turns:
        for c in getattr(t, "_comments", []) or []:
            lines.append(f"# {c}")
        lines.append(f"Q[{t.lineno}]: {t.question}")
        if show_board:
            lines.append(f"  board: {t.schedule}  (turn {t.conv_index} of this "
                         "conversation)")
        if t.selection:
            lines.append("  selection: " + ", ".join(
                f"{k}={v}" for k, v in t.selection.items()))
        if t.error:
            lines.append(f"  !! ASK-PATH FAILURE: {t.error}")
            lines.append(_RULE)
            continue
        # interpreted-as line WITH the resolution source
        # Session 4A.y Item 3 — UNGATED FROM THE REWRITE, the same fix as
        # askpanel.js's and for the same reason: since the listening docket the
        # note carries the GRAIN and the DIRECTION, and a question that needed no
        # rewrite ("when does ORD-000126 op30 finish") carries a note saying it
        # was answered at ORDER level. Gating the disclosure on the rewrite hid
        # exactly the disclosures the docket added.
        if t.resolved_question and t.resolved_question != t.question:
            note = f"  ({t.resolution_note})" if t.resolution_note else ""
            lines.append(f"  interpreted as: {t.resolved_question}{note}")
        elif t.resolution_note:
            lines.append(f"  interpreted as: ({t.resolution_note})")
        lines.append(
            f"  route={t.route}  source={t.source}  conf={_conf(t.confidence)}  "
            f"register={t.register}  renderer={t.renderer}")
        lines.append(
            f"  lit-bars={t.lit_bars}  records={t.record_count}  "
            f"refs={_refs_str(t.cited_refs)}")
        if t.parse:
            lines.append("  parse: " + _parse_str(t.parse))
        if t.synthesis:
            lines.append("  synthesis: " + _synth_str(t.synthesis))
        if t.shadow:
            lines.append("  shadow: " + _shadow_str(t.shadow))
        if t.expect:
            ok = not any(f.kind == "expect-miss" for f in t.findings)
            lines.append("  expect: " + " ".join(
                f"{k}={v}" for k, v in t.expect.items()) +
                ("  -> MET" if ok else "  -> MISSED"))
            # THE VALUES A RELATIONAL EXPECTATION ACTUALLY COMPARED.
            #
            # Found by (d.3)'s standing predicate audit, pointed at (d.2)'s own
            # sweeps: the committed transcripts said `records_from=1 -> MET` and
            # nothing else, so **a real comparison and a degenerate one look
            # identical in the artifact**. (d.2)'s close-out claim that "every
            # relational form carried real values" was true, and it was
            # established by cross-referencing OTHER lines of the transcript by
            # eye — which the next auditor has to redo from scratch, and which
            # is precisely the position this law exists to prevent.
            #
            # A relational PASS is now self-evidencing: the fingerprint, the
            # record count and the referenced turn are on the line.
            if any(k in _RELATIONAL_KEYS for k in t.expect):
                lines.append(f"    compared: body={t.body_sha[:12] or '(empty)'}"
                             f"  records={len(t.record_ids)}"
                             f"  turn={t.conv_index} of this conversation")
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


def _synth_str(s: dict) -> str:
    """The second tier's per-claim provenance on one line (Session 4A.5b): what it
    proved, what stayed interpretive, what it cut, and what it read to get there."""
    bits = [f"claims={s.get('claims', 0)}",
            f"verified={s.get('verified', 0)}",
            f"interpretive={s.get('interpretive', 0)}",
            # R-TG1: printed BESIDE interpretive, never folded into it. Without
            # this line the per-turn counts silently did not sum to `claims`,
            # which is how a reader first notices a class they were not told
            # about.
            f"general-knowledge={s.get('general_knowledge', 0)}",
            f"cut={s.get('failed_and_cut', 0)}"]
    # R-TG3, and it is R-TG1's reason one class later: printed only when it is
    # NON-ZERO, but printed BESIDE `cut` and never folded into it. Without this
    # the per-turn counts silently stop summing to `claims` the moment the depth
    # licence binds — which is exactly how a reader first fails to notice a
    # class they were not told about. Gated on non-zero because a `deferred=0`
    # on every line of every sweep is noise that trains a reader to skip it.
    if s.get("deferred"):
        bits.append(f"deferred={s['deferred']}")
    if s.get("ungrounded_load_bearing"):
        bits.append(f"ungrounded-load-bearing={s['ungrounded_load_bearing']}")
    tools = s.get("tools") or []
    bits.append(f"tools={len(tools)}" + (f"({','.join(tools)})" if tools else ""))
    if s.get("budget_exhausted"):
        bits.append("budget-exhausted")
    if s.get("unanswerable"):
        bits.append("unanswerable")
    if s.get("latency_ms") is not None:
        bits.append(f"{s['latency_ms']:.0f}ms")
    return "  ".join(bits)


def _shadow_str(s: dict) -> str:
    """The probation comparison on one line (Session 4A.5c): what the promoted
    route and its synthesis shadow agreed on, and what — if anything — they
    contradicted each other about, which is the demotion trigger."""
    if s.get("unchecked"):
        return "UNCHECKED (no synthesizer) — this sweep does not serve the window"
    bits = [f"agreed={','.join(s.get('agreed') or []) or '-'}"]
    contradicted = s.get("contradicted") or []
    bits.append(f"contradicted={','.join(contradicted) or '-'}")
    if contradicted:
        bits.append("** DIVERGED — R-AI5(7): DEMOTE **")
    bits.append("provenance-strengthened="
                + ("yes" if s.get("provenance_strengthened") else "no"))
    if s.get("shadow_only"):
        bits.append(f"shadow-only={len(s['shadow_only'])}")
    if s.get("latency_ms") is not None:
        # Reported, and SUBTRACTED from the turn's latency above: the planner
        # never waits for the probation.
        bits.append(f"cost {s['latency_ms']:.0f}ms (not the planner's)")
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
        "synth_stats": result.synth_stats,
        "synthesis": result.synthesis_totals(),
        "shadow": result.shadow_totals(),
        "latency": result.latency(),
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
