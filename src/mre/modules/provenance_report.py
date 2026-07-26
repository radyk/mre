"""Provenance telemetry and the frequency-weighted Pareto (R-AI5(5)/(6)).

Session 4A.5c CU1. R-AI5(5), verbatim: *"Per-claim provenance is recorded in the
question ledger. The frequency-weighted Pareto of synthesis residue is the standing
prioritization for promoting recurring shapes to contracted intents."*

This module turns a question ledger into that prioritization. It reads; it never
writes to the ledger, the canonical model or the evidence store.

WHAT THE REPORT ANSWERS, in order:

  1. **Questions by tier** — contracted / synthesis / honest floor. The denominator
     for everything else, and the number that says whether the second tier is a
     trickle or the product.
  2. **Recurring shapes** — the synthesis residue clustered (see below).
  3. **Per cluster** — frequency, the verified/interpretive ratio, exemplars, the
     tools it consulted.
  4. **The Pareto** — promotable clusters ordered by frequency x verified share,
     with the cumulative share of promotable volume.

R-AI5(6) IS PRINTED IN THE HEADER, not implied. *"The target is synthesis rare
where a proof exists and honest where it does not — never zero. Interpretive
residue (takes, aggregate reads) is first-class conversation, protected, not
minimized."* A report that ranks every cluster by frequency alone would put the
plan's most interesting conversations at the top of an "improvement backlog" and
quietly instruct the next session to contract them away. So clusters whose residue
is takes and aggregate reads are marked NOT-PROMOTABLE-BY-DESIGN, excluded from the
Pareto, and counted nowhere near the backlog.

THE CLUSTERING METHOD, STATED HONESTLY (crude-but-stated beats clever-but-opaque).
Two synthesis answers are the same SHAPE when all three of these match:

  * **Intent adjacency** — the (up to two) contracted intents the parse judged
    closest, sorted. Every second-tier answer takes the same ROUTE (`synthesis`),
    so the route says nothing; the adjacency is the parse's own statement of what
    neighbourhood the question sat in, and it is the strongest signal available
    without reading prose.
  * **Subject kinds** — which KINDS the planner named (order / machine / customer
    / concept), sorted and de-duplicated. Not the refs: "why is ORD-05 late" and
    "why is ORD-13 late" are one shape, and a cluster keyed on refs would be a
    list of questions rather than a shape.
  * **Dominant tool** — the tool the loop called MOST while answering (ties broken
    by which was called first). Two questions answered out of the same evidence
    family are answerable by the same contracted assembly, which is precisely what
    a promotion would build.

    Why the dominant tool and not the whole call SET, which was the first thing
    tried: the set fragments shapes badly. On the 4A.5b residue it split "why so
    many late orders" (cost_ledger + lateness_set + placements_for_order) from
    "cant you just make it cheaper" (cost_ledger + lateness_set) into two clusters
    of one, because the loop made one extra exploratory call on one of them. The
    long tail of supporting calls is the model's exploration; the tool it leaned on
    is the shape. The whole distinct set is still REPORTED per cluster — it is just
    not part of the key.

What this is NOT: semantic clustering. Two questions that mean the same thing but
whose parses disagreed about adjacency, or that leaned on different tools, land in
different clusters. That splits shapes and therefore UNDER-states frequency — it
never invents one. Under-counting is the safe error for a prioritization whose
output is "build a route", and the failure mode is visible: two clusters with the
same exemplar shape sitting next to each other in the report is the tell, and a
reader merges them by naming the shape in a dossier.

Nothing here is authored by a model, and nothing here promotes anything: the
report's output is a ranked list a human reads (R-AI5(7)).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# The promotability rule (R-AI5(6)) — stated as constants, not buried in a branch
# ---------------------------------------------------------------------------

#: A cluster whose claims ground less often than this is PREDOMINANTLY INTERPRETIVE:
#: the evidence does not carry what the question asks, so the honest answer is a
#: labeled reading. A contracted route for such a shape could only refuse or
#: pretend. One in three is deliberately generous — the bar is "could a route prove
#: a meaningful part of this", not "is it mostly proven".
VERIFIED_SHARE_FLOOR = 1.0 / 3.0

#: A cluster more than half of whose claims are the draft's own CONCLUSION is a
#: TAKE. Protected by R-AI5(6) as first-class conversation.
CONCLUSION_SHARE_CEILING = 0.5

#: How many exemplar questions a cluster carries into the report and the dossier.
EXEMPLARS = 3

#: How many adjacency ids take part in the cluster key. Two: the parse is asked for
#: its nearest, and past the second the ordering is noise.
ADJACENCY_DEPTH = 2


class NotPromotable(str):
    """The stated reason a cluster is protected. A string subclass so it prints
    itself, with the constants below as the closed set."""


PROTECTED_INTERPRETIVE = NotPromotable(
    "predominantly interpretive -- an aggregate read; no route could prove it")
PROTECTED_TAKE = NotPromotable(
    "predominantly conclusions -- a take; R-AI5(6) protects it")
PROTECTED_CONVERSATIONAL = NotPromotable(
    "consulted no evidence -- conversational, not a question about the plan")


# ---------------------------------------------------------------------------
# Reading a ledger
# ---------------------------------------------------------------------------

@dataclass
class LedgerRow:
    """One ledger entry, flattened to exactly what the report reads.

    A dataclass rather than the pydantic entry because this module also reads
    RECONSTRUCTED rows (from a committed sweep transcript, where no ledger was
    written), and both sources must land in one shape or the clustering would
    quietly mean different things for different inputs."""

    question: str
    route: str
    intent: str = ""
    nearest: list = field(default_factory=list)
    subject_kinds: list = field(default_factory=list)
    #: The tool calls IN CALL ORDER, repeats included — the dominant tool is a
    #: count, so a de-duplicated list would silently make every tool equally
    #: dominant and the key would collapse to "the alphabetically first tool".
    tools: list = field(default_factory=list)
    verified: int = 0
    interpretive: int = 0
    failed: int = 0
    conclusions: int = 0
    load_bearing_cut: int = 0
    unanswerable: bool = False
    #: True when this row's adjacency was NOT available (a reconstructed row).
    #: Reported, because clustering without it is a weaker method and a reader is
    #: owed that fact rather than a footnote.
    adjacency_unknown: bool = False

    @property
    def dominant_tool(self) -> str:
        """The tool this answer leaned on: most calls, ties to the earliest."""
        if not self.tools:
            return ""
        best, best_n = "", 0
        for i, t in enumerate(self.tools):
            n = self.tools.count(t)
            if n > best_n:
                best, best_n = t, n
        return best

    @property
    def is_synthesis(self) -> bool:
        return self.route == "synthesis"

    @property
    def is_floor(self) -> bool:
        """The honest floor: the shape was recognized and NOT answered."""
        return self.route in ("REFUSED", "NEAR_MISS", "CLARIFY")


def rows_from_ledger(path: Path | str) -> list[LedgerRow]:
    """Read a question-ledger JSONL into report rows. Malformed lines are skipped
    exactly as ``QuestionLedger.all_entries`` skips them — the ledger is advisory,
    and a telemetry read must never be the thing that breaks."""
    from mre.contracts.question_ledger import QuestionLedgerEntry

    out: list[LedgerRow] = []
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = QuestionLedgerEntry.model_validate_json(line)
        except Exception:  # noqa: BLE001 — advisory stream
            continue
        out.append(_row_of(e))
    return out


def _row_of(entry: Any) -> LedgerRow:
    parse = getattr(entry, "parse", None)
    syn = getattr(entry, "synthesis", None)
    claims = list(getattr(syn, "claims", []) or []) if syn is not None else []
    return LedgerRow(
        question=entry.verbatim_question,
        route=entry.route,
        intent=getattr(parse, "intent", "") or "",
        nearest=list(getattr(parse, "nearest", []) or []),
        subject_kinds=list(getattr(parse, "subject_kinds", []) or []),
        tools=[t.tool for t in (getattr(syn, "tool_calls", []) or [])],
        verified=sum(1 for c in claims if c.get("status") == "verified"),
        interpretive=sum(1 for c in claims if c.get("status") == "interpretive"),
        failed=sum(1 for c in claims if c.get("status") == "failed"),
        conclusions=sum(1 for c in claims if c.get("kind") == "conclusion"),
        load_bearing_cut=sum(1 for c in claims if c.get("load_bearing")),
        unanswerable=bool(getattr(syn, "unanswerable", False)),
        adjacency_unknown=parse is None,
    )


# ---------------------------------------------------------------------------
# Reconstructing rows from a committed sweep transcript
# ---------------------------------------------------------------------------

_Q_RE = re.compile(r"^Q\[\d+\]:\s*(.*)$")
_ROUTE_RE = re.compile(r"^\s+route=(\S+)")
_PARSE_RE = re.compile(r"^\s+parse:\s+intent=(\S+)")
_SUBJ_RE = re.compile(r"\b(order|machine|customer|concept)=(\S+?)<-")
_SYNTH_RE = re.compile(r"^\s+synthesis:\s+(.*)$")
_TOOLS_RE = re.compile(r"tools=\d+\(([^)]*)\)")
_COUNT_RE = re.compile(r"\b(claims|verified|interpretive|cut)=(\d+)")


def rows_from_sweep(sweep_dir: Path | str) -> list[LedgerRow]:
    """Reconstruct report rows from a COMMITTED sweep's transcripts.

    Why this exists: the 4A.5b sweep — the baseline this session's promotion proof
    is drawn from — ran before the runner wrote a ledger, so its residue exists
    only as transcripts. Reconstruction is honest about what it loses: a transcript
    carries the intent, the bound subject KINDS and the tool pattern, but NOT the
    parse's ``nearest`` list, so every reconstructed row is flagged
    ``adjacency_unknown`` and the clustering falls back to subject-kinds +
    tool-pattern for it. The report prints that fact rather than presenting a
    weaker method as the same one.

    Live sweeps from this session forward write a real ledger and never come
    through here."""
    rows: list[LedgerRow] = []
    d = Path(sweep_dir)
    for txt in sorted(d.glob("*.txt")):
        rows.extend(_rows_from_transcript(txt.read_text(encoding="utf-8")))
    return rows


def _rows_from_transcript(text: str) -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    cur: Optional[LedgerRow] = None
    for line in text.splitlines():
        m = _Q_RE.match(line)
        if m:
            if cur is not None:
                rows.append(cur)
            cur = LedgerRow(question=m.group(1).strip(), route="",
                            adjacency_unknown=True)
            continue
        if cur is None:
            continue
        m = _ROUTE_RE.match(line)
        if m:
            cur.route = m.group(1)
            continue
        m = _PARSE_RE.match(line)
        if m:
            cur.intent = m.group(1)
            cur.subject_kinds = sorted({k for k, _ in _SUBJ_RE.findall(line)})
            continue
        m = _SYNTH_RE.match(line)
        if m:
            body = m.group(1)
            counts = {k: int(v) for k, v in _COUNT_RE.findall(body)}
            cur.verified = counts.get("verified", 0)
            cur.interpretive = counts.get("interpretive", 0)
            cur.failed = counts.get("cut", 0)
            tm = _TOOLS_RE.search(body)
            cur.tools = tm.group(1).split(",") if tm and tm.group(1) else []
            cur.unanswerable = "unanswerable" in body
    if cur is not None:
        rows.append(cur)
    return rows


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

@dataclass
class ShapeCluster:
    """One recurring shape of synthesis residue."""

    cluster_id: str
    adjacency: list           # the contracted intents the parse judged closest
    subject_kinds: list
    dominant_tool: str        # the key's third component
    tools: list = field(default_factory=list)   # every distinct tool, reported
    questions: list = field(default_factory=list)
    verified: int = 0
    interpretive: int = 0
    failed: int = 0
    conclusions: int = 0
    unanswerable: int = 0
    adjacency_unknown: bool = False

    @property
    def frequency(self) -> int:
        return len(self.questions)

    @property
    def claims(self) -> int:
        return self.verified + self.interpretive + self.failed

    @property
    def verified_share(self) -> float:
        """Of the claims that RENDERED (verified + interpretive), the share that
        grounded. Cut claims are excluded on purpose: they never reached a planner,
        and counting them would rate a shape by the draft's mistakes rather than by
        what the evidence can carry."""
        denom = self.verified + self.interpretive
        return (self.verified / denom) if denom else 0.0

    @property
    def conclusion_share(self) -> float:
        return (self.conclusions / self.claims) if self.claims else 0.0

    @property
    def exemplars(self) -> list:
        return self.questions[:EXEMPLARS]

    @property
    def protected(self) -> Optional[NotPromotable]:
        """The stated reason this cluster is NOT-PROMOTABLE-BY-DESIGN, or None.

        R-AI5(6) lives here. Three ways a shape is protected, and each is a
        statement about the EVIDENCE, never about the question's worth."""
        if not self.dominant_tool:
            return PROTECTED_CONVERSATIONAL
        if self.conclusion_share >= CONCLUSION_SHARE_CEILING:
            return PROTECTED_TAKE
        if self.verified_share < VERIFIED_SHARE_FLOOR:
            return PROTECTED_INTERPRETIVE
        return None

    @property
    def promotable(self) -> bool:
        return self.protected is None

    @property
    def weight(self) -> float:
        """The Pareto weight: **frequency x verified share**.

        Frequency alone would rank a shape nobody can prove above one asked half as
        often that a route could answer outright. The product asks the promotion
        question directly: how much PROVEN answering would contracting this shape
        buy? A cluster asked 10 times whose claims ground 20% of the time scores
        2.0; one asked 4 times that grounds 75% scores 3.0, and it should be built
        first."""
        return self.frequency * self.verified_share


def cluster_key(row: LedgerRow) -> tuple:
    adjacency = tuple(sorted(row.nearest[:ADJACENCY_DEPTH]))
    return (adjacency, tuple(row.subject_kinds), row.dominant_tool)


def cluster_id_of(adjacency: Iterable, kinds: Iterable, dominant: str) -> str:
    """A stable, readable cluster id. Long on purpose: it is the PRIMARY KEY a
    dossier cites, so it must say what it is without a lookup table."""
    a = "+".join(adjacency) or "unanchored"
    k = "+".join(kinds) or "no-subject"
    t = dominant or "no-tools"
    return f"{a}|{k}|{t}"


def cluster(rows: Iterable[LedgerRow]) -> list[ShapeCluster]:
    """Group synthesis rows into shapes, most frequent first.

    Only ``route == synthesis`` rows take part: the residue is what the second tier
    ANSWERED. Floor rows (REFUSED / NEAR_MISS / CLARIFY) are counted in the tier
    table but never clustered — a question nothing read has no tool pattern, and
    clustering it would fabricate a shape out of two empty tuples."""
    buckets: dict[tuple, ShapeCluster] = {}
    for row in rows:
        if not row.is_synthesis:
            continue
        key = cluster_key(row)
        c = buckets.get(key)
        if c is None:
            c = ShapeCluster(
                cluster_id=cluster_id_of(key[0], key[1], key[2]),
                adjacency=list(key[0]), subject_kinds=list(key[1]),
                dominant_tool=key[2])
            buckets[key] = c
        c.questions.append(row.question)
        for t in row.tools:
            if t not in c.tools:
                c.tools.append(t)
        c.verified += row.verified
        c.interpretive += row.interpretive
        c.failed += row.failed
        c.conclusions += row.conclusions
        c.unanswerable += 1 if row.unanswerable else 0
        c.adjacency_unknown = c.adjacency_unknown or row.adjacency_unknown
    return sorted(buckets.values(),
                  key=lambda c: (-c.frequency, -c.weight, c.cluster_id))


def pareto(clusters: Iterable[ShapeCluster]) -> list[tuple]:
    """The frequency-weighted Pareto: ``[(cluster, cumulative_share), ...]``.

    PROMOTABLE clusters only (R-AI5(6)). ``cumulative_share`` runs over the
    promotable weight, so "the top two clusters are 70% of the backlog" is a claim
    about what CAN be contracted — never about the conversation as a whole."""
    promotable = [c for c in clusters if c.promotable and c.weight > 0]
    promotable.sort(key=lambda c: (-c.weight, -c.frequency, c.cluster_id))
    total = sum(c.weight for c in promotable)
    out: list[tuple] = []
    running = 0.0
    for c in promotable:
        running += c.weight
        out.append((c, (running / total) if total else 0.0))
    return out


# ---------------------------------------------------------------------------
# Tier counts
# ---------------------------------------------------------------------------

def tier_counts(rows: Iterable[LedgerRow]) -> dict:
    rows = list(rows)
    synth = [r for r in rows if r.is_synthesis]
    floor = [r for r in rows if r.is_floor]
    contracted = [r for r in rows if not r.is_synthesis and not r.is_floor]
    return {
        "questions": len(rows),
        "contracted": len(contracted),
        "synthesis": len(synth),
        "floor": len(floor),
        "synthesis_unanswerable": sum(1 for r in synth if r.unanswerable),
        "claims_verified": sum(r.verified for r in synth),
        "claims_interpretive": sum(r.interpretive for r in synth),
        "claims_cut": sum(r.failed for r in synth),
        "load_bearing_cut": sum(r.load_bearing_cut for r in synth),
    }


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

_RULE = "-" * 72


def render_report(rows: list[LedgerRow], *, source: str = "") -> str:
    """The standing report. Plain ASCII, no box-drawing, no emoji."""
    clusters = cluster(rows)
    tiers = tier_counts(rows)
    ranked = pareto(clusters)
    protected = [c for c in clusters if not c.promotable]
    reconstructed = any(c.adjacency_unknown for c in clusters)

    L: list[str] = []
    L.append("PROVENANCE REPORT -- synthesis residue, clustered and ranked")
    L.append(f"source      : {source or '(unnamed ledger)'}")
    L.append(f"questions   : {tiers['questions']}")
    L.append(_RULE)
    L.append("R-AI5(6) -- READ THIS BEFORE READING THE PARETO.")
    L.append("")
    L.append("  \"The target is synthesis rare where a proof exists and honest")
    L.append("   where it does not -- NEVER ZERO. Interpretive residue (takes,")
    L.append("   aggregate reads) is first-class conversation, protected, not")
    L.append("   minimized.\"")
    L.append("")
    L.append("Clusters marked NOT-PROMOTABLE-BY-DESIGN below are exactly that")
    L.append("residue. They are excluded from the Pareto and are NOT improvement")
    L.append("backlog. A shape whose sentences the evidence cannot ground is not a")
    L.append("gap in the route table -- it is a conversation the product is")
    L.append("supposed to be able to have. Contracting it could only produce a")
    L.append("route that refuses or one that pretends.")
    L.append(_RULE)

    L.append("TIERS")
    L.append(f"  contracted routes      : {tiers['contracted']}")
    L.append(f"  synthesis (second tier): {tiers['synthesis']}"
             f"  (unanswerable {tiers['synthesis_unanswerable']})")
    L.append(f"  honest floor           : {tiers['floor']}"
             "   (REFUSED / NEAR_MISS / CLARIFY)")
    L.append(f"  claims                 : verified {tiers['claims_verified']}  "
             f"interpretive {tiers['claims_interpretive']}  "
             f"cut {tiers['claims_cut']}"
             f"  (load-bearing cut {tiers['load_bearing_cut']})")
    L.append(_RULE)

    L.append("CLUSTERING METHOD (stated, not implied)")
    L.append("  Two synthesis answers are the same SHAPE when all three match:")
    L.append("    1. intent adjacency  -- the <=2 contracted intents the parse")
    L.append("                            judged closest, sorted")
    L.append("    2. subject kinds     -- order / machine / customer / concept,")
    L.append("                            sorted; NOT the refs")
    L.append("    3. dominant tool     -- the tool the loop called MOST (ties to")
    L.append("                            the earliest). The whole call set is")
    L.append("                            reported but is NOT part of the key:")
    L.append("                            one extra exploratory call would else")
    L.append("                            split a shape into two clusters of one.")
    L.append("  This is not semantic clustering. It SPLITS shapes whose parses")
    L.append("  disagreed, so it UNDER-states frequency; it never invents one.")
    L.append("  Two clusters with the same exemplar shape side by side is the")
    L.append("  tell, and a human merges them by naming the shape in a dossier.")
    if reconstructed:
        L.append("")
        L.append("  !! Some rows were RECONSTRUCTED from a committed sweep")
        L.append("     transcript, which carries no `nearest` list. Their")
        L.append("     adjacency is empty and they cluster on subject-kinds +")
        L.append("     tool-pattern alone -- a weaker method, flagged per cluster")
        L.append("     as [adjacency-unknown] rather than presented as the same.")
    L.append(_RULE)

    L.append(f"RECURRING SHAPES ({len(clusters)} clusters)")
    L.append("")
    for i, c in enumerate(clusters, 1):
        flag = "" if c.promotable else "   [NOT-PROMOTABLE-BY-DESIGN]"
        unknown = "  [adjacency-unknown]" if c.adjacency_unknown else ""
        L.append(f"  {i}. {c.cluster_id}{flag}{unknown}")
        L.append(f"     frequency  : {c.frequency}")
        L.append(f"     claims     : verified {c.verified}  "
                 f"interpretive {c.interpretive}  cut {c.failed}   "
                 f"(verified share {c.verified_share:.0%})")
        L.append(f"     leaned on  : {c.dominant_tool or '(nothing consulted)'}")
        L.append(f"     also read  : "
                 f"{', '.join(t for t in c.tools if t != c.dominant_tool) or '-'}")
        if not c.promotable:
            L.append(f"     protected  : {c.protected}")
        L.append(f"     weight     : {c.weight:.2f}  (frequency x verified share)")
        L.append("     exemplars  :")
        for q in c.exemplars:
            L.append(f"       - \"{q}\"")
        L.append("")
    L.append(_RULE)

    L.append("THE FREQUENCY-WEIGHTED PARETO (promotable clusters only)")
    L.append("  ordering: frequency x verified share, descending.")
    L.append("  cumulative runs over PROMOTABLE weight -- never over the whole")
    L.append("  conversation (R-AI5(6)).")
    L.append("")
    if not ranked:
        L.append("  (nothing promotable -- every cluster is protected residue, or")
        L.append("   no synthesis answer grounded a claim. This is a legitimate")
        L.append("   outcome, not an empty result.)")
    else:
        L.append("  rank  weight  cum%   frequency  cluster")
        for rank, (c, cum) in enumerate(ranked, 1):
            L.append(f"  {rank:<5} {c.weight:<7.2f} {cum:<6.0%} {c.frequency:<10} "
                     f"{c.cluster_id}")
        L.append("")
        top = ranked[0][0]
        L.append(f"  NEXT PROMOTION CANDIDATE: {top.cluster_id}")
        L.append(f"    asked {top.frequency}x, {top.verified_share:.0%} of its")
        L.append("    rendered claims grounded. Generate its dossier with:")
        L.append("      python tools/promotion_dossier.py --cluster "
                 f"\"{top.cluster_id}\" ...")
        L.append("    The dossier is an APPLICATION. Promotion is a reviewed")
        L.append("    change (R-AI5(7)); this tool never wires anything into")
        L.append("    dispatch.")
    L.append(_RULE)

    if protected:
        L.append(f"PROTECTED RESIDUE ({len(protected)} clusters) -- R-AI5(6)")
        L.append("  Not backlog. Not a defect. Not counted above.")
        for c in protected:
            L.append(f"  - {c.cluster_id}  (x{c.frequency})")
            L.append(f"      {c.protected}")
            if c.exemplars:
                L.append(f"      e.g. \"{c.exemplars[0]}\"")
        L.append(_RULE)

    return "\n".join(L) + "\n"


def report_payload(rows: list[LedgerRow], *, source: str = "") -> dict:
    """The machine-readable twin of ``render_report`` (committed beside it, the way
    every transcript in this repo is committed beside its sidecar)."""
    clusters = cluster(rows)
    ranked = pareto(clusters)
    order = {c.cluster_id: (i + 1, cum) for i, (c, cum) in enumerate(ranked)}
    return {
        "source": source,
        "tiers": tier_counts(rows),
        "method": {
            "keys": ["intent_adjacency", "subject_kinds", "tool_pattern"],
            "adjacency_depth": ADJACENCY_DEPTH,
            "weight": "frequency * verified_share",
            "verified_share_floor": VERIFIED_SHARE_FLOOR,
            "conclusion_share_ceiling": CONCLUSION_SHARE_CEILING,
            "semantic": False,
            "under_states_frequency": True,
        },
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "adjacency": c.adjacency,
                "subject_kinds": c.subject_kinds,
                "tools": c.tools,
                "frequency": c.frequency,
                "verified": c.verified,
                "interpretive": c.interpretive,
                "cut": c.failed,
                "verified_share": round(c.verified_share, 4),
                "conclusion_share": round(c.conclusion_share, 4),
                "weight": round(c.weight, 4),
                "promotable": c.promotable,
                "protected_reason": str(c.protected) if c.protected else None,
                "adjacency_unknown": c.adjacency_unknown,
                "exemplars": c.exemplars,
                "pareto_rank": order.get(c.cluster_id, (None, None))[0],
                "pareto_cumulative": (
                    round(order[c.cluster_id][1], 4)
                    if c.cluster_id in order else None),
            }
            for c in clusters
        ],
    }


def write_report(rows: list[LedgerRow], out_dir: Path | str, *,
                 source: str = "") -> tuple[Path, Path]:
    """Write ``PROVENANCE.txt`` + ``PROVENANCE.json`` into ``out_dir``."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    txt = d / "PROVENANCE.txt"
    js = d / "PROVENANCE.json"
    txt.write_text(render_report(rows, source=source), encoding="utf-8")
    js.write_text(
        json.dumps(report_payload(rows, source=source), indent=2,
                   ensure_ascii=True) + "\n", encoding="utf-8")
    return txt, js
