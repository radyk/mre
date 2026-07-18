"""Renderers for ExplanationBundle -> text.

TemplateRenderer    - deterministic, footnoted record IDs.  Used in all tests.
LLMRenderer         - Anthropic API.  Falls back to TemplateRenderer if no key.

Rendering rules (from CLAUDE.md / docs/03):
- Use planner vocabulary (WO-2001, M-GEAR-01), never UUIDs.
- basis=reconstructed -> "X was assigned to Y; Z would have cost more / was unavailable"
- Every cited claim gets a footnoted record ID.
- Do not add information not present in the evidence bundle.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from mre.modules.explainer import ExplanationBundle

# Patterns for post-render validation
# Captures full timestamp: date + optional time + optional timezone
_TS_FULL_RE = re.compile(
    r'\b(\d{4}-\d{2}-\d{2}'                         # YYYY-MM-DD
    r'(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?'   # optional T/space HH:MM[:SS[.fff]]
    r'(?:Z|[+-]\d{2}:?\d{2}|\s*UTC)?)',              # optional timezone
    re.IGNORECASE,
)
# Time-unit numbers: "840 min", "14h", "14.0 hours", etc.
_TIME_NUM_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(min(?:utes?)?|h(?:ours?)?)\b', re.IGNORECASE)
_MACHINE_RE = re.compile(r'\bM-[A-Z][A-Z0-9-]*')


def _to_minute_tuple(s: str) -> Optional[tuple]:
    """Parse timestamp string to (year, month, day, hour, minute), or None.

    Strips Z / UTC / ±HH:MM suffixes and converts T-separator to space so
    strptime sees a clean 'YYYY-MM-DD HH:MM[:SS]' or 'YYYY-MM-DD' string.
    Returns hour=minute=-1 for date-only forms.
    """
    clean = s.strip()
    clean = re.sub(r'Z\s*$', '', clean)
    clean = re.sub(r'\s*UTC\s*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[+-]\d{2}:?\d{2}\s*$', '', clean)
    clean = clean.strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            dt = datetime.strptime(clean, fmt)
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        except ValueError:
            pass
    try:
        dt = datetime.strptime(clean, '%Y-%m-%d')
        return (dt.year, dt.month, dt.day, -1, -1)
    except ValueError:
        pass
    return None


def _ts_matches(prose_tup: tuple, bundle_tuples: set) -> bool:
    """True if prose timestamp matches any bundle timestamp at minute granularity.
    Date-only prose (hour=-1) matches any bundle timestamp with the same date.
    """
    if prose_tup[3] == -1:
        return any(bt[:3] == prose_tup[:3] for bt in bundle_tuples)
    return prose_tup in bundle_tuples


def _signed(v: Any) -> str:
    """A signed dollar amount for a cost-delta component (CU2). None → '—'."""
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else '−'}${abs(v):,.0f}"


def _to_minutes(value: float, unit: str) -> float:
    """Convert a time value to minutes based on its unit string."""
    return value * 60.0 if unit.lower().startswith('h') else value




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_name(entity_id: str, entity_type: str, identity_map: Any) -> str:
    """Resolve canonical UUID to human-readable external name."""
    if not entity_id:
        return "?"
    if identity_map is None:
        return entity_id[:12]
    preferred = {
        "demand": "work_order",
        "resource": "machine_id",
        "product": "product_no",
    }
    pref = preferred.get(entity_type, "")
    refs = identity_map.external_refs(entity_id)
    for ref in refs:
        if ref.type == pref:
            return ref.value
    return refs[0].value if refs else entity_id[:12]


# ---------------------------------------------------------------------------
# TemplateRenderer
# ---------------------------------------------------------------------------

# Which answer register each certificate subject_type belongs to (handoff §4).
_REGISTER_BY_SUBJECT = {"remediation": "remediation", "triage": "judgment"}


def _register_for(bundle: ExplanationBundle) -> str:
    return _REGISTER_BY_SUBJECT.get(bundle.subject_type, "testimony")


class TemplateRenderer:
    """Deterministic text renderer.  No external calls."""

    def render(self, bundle: ExplanationBundle) -> str:
        return (self._render_body(bundle)
                + f"\n[rendered by: template | register: {_register_for(bundle)}]")

    def _render_body(self, bundle: ExplanationBundle) -> str:
        lines: list[str] = []
        lines.append(f"=== {bundle.question} ===")
        lines.append("")

        self._render_header(lines, bundle)

        if bundle.subject_type in ("remediation", "triage"):
            # Register bodies are assembled by their own modules from the
            # certificate findings on the bundle (authored catalog text /
            # grade-distance arithmetic), never from the testimony templater.
            return "\n".join(lines) + self._render_register_body(bundle)

        # The edit domain (CU2) renders its whole answer in the header (the
        # planner narrative over planner_edit Decisions); the Decisions ARE the
        # citations, already summarized, so no separate raw evidence chain.
        if bundle.subject_type in ("edits", "edit_cost"):
            return "\n".join(lines)

        if not bundle.ordered_records:
            if bundle.subject_type == "diff":
                self._render_diff(lines, bundle.key_facts)
            elif bundle.subject_type in (
                "downtime", "unsupported", "schedule", "scenario_diff",
                "near_miss", "clarify", "refusals",
            ):
                pass  # header already rendered all content
            elif "error" in bundle.key_facts:
                lines.append(f"  Error: {bundle.key_facts['error']}")
            else:
                lines.append("  (no evidence records found)")
            return "\n".join(lines)

        lines.append(f"Evidence chain ({len(bundle.ordered_records)} record(s)):")
        lines.append("")
        for i, rec in enumerate(bundle.ordered_records, 1):
            self._render_record(lines, i, rec, bundle.identity_map)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_header(self, lines: list[str], bundle: ExplanationBundle) -> None:
        if bundle.subject_type == "demand":
            lateness = bundle.key_facts.get("lateness_minutes")
            due = bundle.key_facts.get("due_date", "unknown")
            if lateness is not None and float(lateness) > 0:
                lines.append(
                    f"{bundle.subject_external_name} completed "
                    f"{int(lateness)} minutes past its due date ({due})."
                )
            elif lateness is not None:
                lines.append(
                    f"{bundle.subject_external_name} completed "
                    f"{abs(int(lateness))} minutes early (due {due})."
                )
            lines.append("")

        elif bundle.subject_type == "run":
            kf = bundle.key_facts
            lines.append(f"Run: {bundle.subject_external_name}")
            lines.append(
                f"  Notable decisions : {kf.get('notable_decision_count', '?')}"
            )
            lines.append(
                f"  Schedule findings : {kf.get('affecting_finding_count', '?')}"
            )
            lines.append(
                f"  Late demands      : {kf.get('late_demand_count', '?')}"
            )
            lines.append("")

        elif bundle.subject_type == "late_orders":
            kf = bundle.key_facts
            count = kf.get("late_count", 0)
            orders = kf.get("late_orders", [])
            if count == 0:
                lines.append("No late orders found in this schedule.")
            else:
                lines.append(f"{count} late order(s):")
                for item in orders:
                    lines.append(f"  - {item}")
            lines.append("")

        elif bundle.subject_type == "downtime":
            kf = bundle.key_facts
            subject = kf.get("subject", "?")
            closures = kf.get("closures", [])
            total = kf.get("total_hours", 0.0)
            if not closures:
                lines.append(f"No calendar closures found for {subject}.")
            else:
                lines.append(f"Downtime for {subject}:")
                for c in closures:
                    lines.append(
                        f"  {c['resource']}: {c['duration_hours']}h"
                        f" — {c['reason']} on {c['date']}"
                    )
                res_count = kf.get("resource_count", len({c["resource"] for c in closures}))
                lines.append(f"  Total: {total}h across {res_count} resource(s)")
            lines.append("")

        elif bundle.subject_type == "edits":
            kf = bundle.key_facts
            edits = kf.get("edits", [])
            n = kf.get("edit_count", len(edits))
            if not n:
                lines.append("No edits have been accepted on this version yet.")
            else:
                total = kf.get("total_cost_delta", 0.0)
                sign = "+" if total >= 0 else "−"
                lines.append(f"You accepted {n} edit(s) on this version "
                             f"({sign}${abs(total):,.0f} total):")
                lines.append("")
                for e in edits:
                    cd = e.get("cost_delta", {})
                    td = cd.get("total_delta")
                    dstr = (f"{'+' if (td or 0) >= 0 else '−'}${abs(td):,.0f}"
                            if td is not None else "cost unknown")
                    lines.append(f"  - pinned op {e.get('op_ref8', '?')} to "
                                 f"{e.get('machine', '?')} · {dstr}"
                                 f" · moved {e.get('moved_count', 0)} op(s)"
                                 f" · by {e.get('authority', '?')}")
            lines.append("")

        elif bundle.subject_type == "edit_cost":
            kf = bundle.key_facts
            cd = kf.get("cost_delta", {})
            total = cd.get("total_delta")
            if total is None:
                lines.append("This edit's cost delta was not recorded.")
            else:
                sign = "+" if total >= 0 else "−"
                lines.append(f"This edit costs {sign}${abs(total):,.0f}, decomposed:")
                lines.append(f"  production  {_signed(cd.get('production_delta'))}")
                lines.append(f"  setup       {_signed(cd.get('setup_delta'))}")
                lines.append(f"  tardiness   {_signed(cd.get('tardiness_delta'))}")
                # per-consequence reasons (3.3 CU3), where the edit annotated them
                reasoned = [m for m in kf.get("moves", []) if m.get("reason")]
                if reasoned:
                    lines.append("")
                    lines.append("Why the surroundings moved:")
                    for m in reasoned[:5]:
                        r = m.get("reason", {})
                        if r.get("kind") == "displaced_by_drop":
                            why = "displaced by the dropped op"
                        else:
                            why = f"blocked on a busy machine until {(r.get('until') or '')[:16]}"
                        lines.append(f"  - op {m.get('operation_ref', '')[:8]} "
                                     f"(+{m.get('start_delta_min', 0)}min): {why}")
            lines.append("")

        elif bundle.subject_type == "unsupported":
            kf = bundle.key_facts
            lines.append(f"I can't answer this question yet: \"{kf.get('parsed', '?')}\"")
            lines.append("")
            lines.append("Supported question types:")
            for route in kf.get("supported_routes", []):
                lines.append(f"  - {route}")
            lines.append("")

        elif bundle.subject_type == "near_miss":
            # The tiered-fallback bridge (CU4): honest miss + the two nearest
            # routes as concrete follow-ups. All copy is authored (never LLM).
            from mre.modules.ask_fallback_copy import NEAR_MISS_LEAD, NEAR_MISS_OFFER
            kf = bundle.key_facts
            lines.append(NEAR_MISS_LEAD.format(q=kf.get("parsed", "?")))
            lines.append("")
            lines.append(NEAR_MISS_OFFER)
            for offer in kf.get("offers", []):
                lines.append(f"  - {offer}")
            lines.append("")

        elif bundle.subject_type == "clarify":
            # Unresolvable ellipsis (CU2): ask for the missing referent, never
            # guess. The reason is authored fallback copy carried on the bundle.
            from mre.modules.ask_fallback_copy import CLARIFY_LEAD
            kf = bundle.key_facts
            lines.append(CLARIFY_LEAD.format(q=kf.get("parsed", "?")))
            reason = kf.get("reason")
            if reason:
                lines.append(reason)
            lines.append("")

        elif bundle.subject_type == "refusals":
            # The meta-route (R-AI1(d)): the ledger answering about itself.
            from mre.modules.ask_fallback_copy import (
                REFUSAL_META_EMPTY, REFUSAL_META_LEAD,
            )
            kf = bundle.key_facts
            refusals = kf.get("refusals", [])
            if not refusals:
                lines.append(REFUSAL_META_EMPTY)
            else:
                lines.append(REFUSAL_META_LEAD.format(n=len(refusals)))
                for r in refusals:
                    q = r.get("verbatim_question", "?")
                    kind = r.get("route", "REFUSED")
                    lines.append(f"  - \"{q}\"  [{kind}]")
            lines.append("")

        elif bundle.subject_type == "schedule":
            kf = bundle.key_facts
            rows = kf.get("rows", [])
            label = kf.get("filter_label", "all")
            if not rows:
                lines.append(kf.get("empty_message") or f"Nothing scheduled for {label}.")
            else:
                lines.append(f"Schedule for {label} ({len(rows)} operation(s)):")
                lines.append("")
                cur_machine = None
                for row in rows:
                    if row["machine"] != cur_machine:
                        cur_machine = row["machine"]
                        lines.append(f"  [{cur_machine}]")
                    lateness = row.get("lateness_minutes")
                    lat_str = ""
                    if lateness is not None:
                        lat_str = (
                            f"  +{int(lateness)}min LATE"
                            if lateness > 0
                            else f"  -{int(abs(lateness))}min early"
                        )
                    lines.append(
                        f"    seq={row['op_seq']:>3}  "
                        f"{row['start']} -> {row['end']}  "
                        f"{row['work_orders']}{lat_str}"
                    )
            lines.append("")

        elif bundle.subject_type == "scenario_diff":
            kf = bundle.key_facts
            lines.append(f"Scenario: {kf.get('description', '?')}")
            lines.append("")
            service_deltas = kf.get("service_deltas", [])
            if service_deltas:
                lines.append("Service changes:")
                for d in service_deltas:
                    wo = d["work_order"]
                    lb = d["lateness_before"]
                    la = d["lateness_after"]
                    delta = d.get("lateness_delta")
                    lb_str = f"{int(lb):+d} min" if lb is not None else "N/A"
                    la_str = f"{int(la):+d} min" if la is not None else "N/A"
                    delta_str = f"  [d{int(delta):+d} min]" if delta is not None else ""
                    lines.append(f"  {wo}: {lb_str} -> {la_str}{delta_str}")
                lines.append("")
            cd = kf.get("cost_delta", {})
            if cd:
                lines.append(
                    f"Cost: {cd.get('total_before', 0):.2f}"
                    f" -> {cd.get('total_after', 0):.2f}"
                    f"  (d {cd.get('total_delta', 0):+.2f})"
                )
                lines.append(f"  production d: {cd.get('production_delta', 0):+.2f}")
                lines.append(f"  setup       d: {cd.get('setup_delta', 0):+.2f}")
                lines.append(f"  tardiness   d: {cd.get('tardiness_delta', 0):+.2f}")
                lines.append("")
            am = kf.get("assignment_moves", {})
            if am.get("total_changed", 0) > 0:
                lines.append(f"Assignment moves: {am['total_changed']}")
                for move in am.get("notable", []):
                    lines.append(f"  {move}")
                lines.append("")

        elif bundle.subject_type == "findings":
            kf = bundle.key_facts
            lines.append(
                f"Total findings: {kf.get('total_findings', '?')} "
                f"| Codes: {', '.join(kf.get('codes', []))}"
            )
            lines.append("")

    def _render_register_body(self, bundle: ExplanationBundle) -> str:
        from mre.modules.remediation import render_remediation_body
        from mre.modules.triage import render_triage_body

        findings = bundle.ordered_records
        if bundle.subject_type == "remediation":
            limit = bundle.key_facts.get("limit")
            return "\n" + render_remediation_body(findings, limit=limit)
        return "\n" + render_triage_body(findings)

    def _render_diff(self, lines: list[str], kf: dict) -> None:
        snap_a = kf.get("snapshot_a", "?")
        snap_b = kf.get("snapshot_b", "?")
        lines.append(f"Comparing {snap_a} -> {snap_b}")
        lines.append("")

        removed = kf.get("removed_demands", [])
        added = kf.get("added_demands", [])
        changed = kf.get("changed_demands", [])
        cm = kf.get("costmodel_diff", {})

        if removed:
            lines.append(f"Removed demands ({len(removed)}):")
            for wo in removed:
                lines.append(f"  - {wo}")
        if added:
            lines.append(f"Added demands ({len(added)}):")
            for wo in added:
                lines.append(f"  + {wo}")
        if changed:
            lines.append(f"Changed demands ({len(changed)}):")
            for c in changed:
                lines.append(
                    f"  ~ {c['work_order']}  | {c['field']}: "
                    f"{c['from']} -> {c['to']}"
                )

        if cm.get("rate_changes"):
            v_a = cm.get("version_a")
            v_b = cm.get("version_b")
            lines.append(
                f"Cost model v{v_a} -> v{v_b} "
                f"({len(cm['rate_changes'])} rate change(s)):"
            )
            for name, chg in sorted(cm["rate_changes"].items()):
                lines.append(f"  ~ {name}: {chg['from']} -> {chg['to']}")

        if not (removed or added or changed or cm.get("rate_changes")):
            lines.append("  (no differences found)")

    def _render_record(
        self,
        lines: list[str],
        idx: int,
        rec: dict,
        identity_map: Any,
    ) -> None:
        rt = rec.get("record_type", "?")
        module = rec.get("module", "?")
        rid_short = (rec.get("record_id") or "?")[:8]

        if rt == "decision":
            self._render_decision(lines, idx, rec, module, rid_short, identity_map)
        elif rt == "metric":
            self._render_metric(lines, idx, rec, module, rid_short, identity_map)
        elif rt == "finding":
            self._render_finding(lines, idx, rec, module, rid_short)
        elif rt == "event":
            lines.append(f"[{idx}] {module} EVENT")
            msg = (rec.get("message") or "")[:120]
            if msg:
                lines.append(f"    {msg}")
            lines.append(f"    [record: {rid_short}...]")
        else:
            lines.append(f"[{idx}] {module} {rt.upper()}")
            lines.append(f"    [record: {rid_short}...]")
        lines.append("")

    def _render_decision(
        self, lines, idx, rec, module, rid_short, identity_map
    ) -> None:
        dt = (rec.get("decision_type") or "?").upper()
        driver = rec.get("driver", "?")
        basis = rec.get("basis", "?")
        lines.append(f"[{idx}] {module} DECISION  | {dt}  | {basis}")

        if dt == "DEMAND_MERGE":
            subjects = rec.get("subjects", [])
            wo_names = [
                _resolve_name(s.get("entity_id", ""), "demand", identity_map)
                for s in subjects
            ]
            if wo_names:
                lines.append(f"    Batched: {', '.join(wo_names)}")
            chosen = rec.get("chosen") or {}
            benefit = chosen.get("estimated_benefit") or chosen.get("estimated_saving")
            if benefit is not None:
                lines.append(f"    Driver: {driver}  - estimated benefit: {float(benefit):.1f}")
            else:
                lines.append(f"    Driver: {driver}")
            for alt in (rec.get("alternatives") or [])[:3]:
                lines.append(
                    f"    Alternative: {alt.get('option','?')}  - {alt.get('consequence','?')}"
                )

        elif dt == "ASSIGNMENT":
            chosen = rec.get("chosen") or {}
            resource_id = chosen.get("resource_id", "")
            resource_name = _resolve_name(resource_id, "resource", identity_map)
            lines.append(f"    Assigned to: {resource_name}")
            lines.append(f"    Driver: {driver}")
            if basis == "reconstructed":
                lines.append(
                    "    Note: This is a reconstruction from the solved schedule."
                )
            for alt in (rec.get("alternatives") or [])[:4]:
                opt = alt.get("option", "")
                alt_id = opt.replace("resource:", "")
                alt_name = _resolve_name(alt_id, "resource", identity_map) if alt_id else opt
                consequence = alt.get("consequence", "")
                lines.append(f"    Alternative: {alt_name}  - {consequence}")

        else:
            lines.append(f"    Driver: {driver}")
            msg = (rec.get("message") or "")[:120]
            if msg:
                lines.append(f"    {msg}")

        lines.append(f"    [record: {rid_short}...]")

    def _render_metric(self, lines, idx, rec, module, rid_short, identity_map) -> None:
        name = rec.get("name", "?")
        value = rec.get("value")
        unit = rec.get("unit", "")

        # Pre-convert epoch metrics → ISO so LLM never sees raw epoch numbers
        display_value: Any = value
        display_unit = unit
        if name.endswith("_epoch") and isinstance(value, (int, float)):
            display_value = datetime.fromtimestamp(value, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            display_unit = ""
        elif unit == "minutes" and isinstance(value, (int, float)) and abs(value) >= 60:
            display_value = f"{value:.0f} min ({value / 60:.1f}h)"
            display_unit = ""

        subjects = rec.get("subjects", [])
        subject_name = ""
        if subjects:
            s = subjects[0]
            subject_name = _resolve_name(
                s.get("entity_id", ""), s.get("entity_type", ""), identity_map
            )
        lines.append(f"[{idx}] {module} METRIC  | {name}")
        subj_part = f" ({subject_name})" if subject_name else ""
        sep = " " if display_unit else ""
        lines.append(f"    Value: {display_value}{sep}{display_unit}{subj_part}")
        lines.append(f"    [record: {rid_short}...]")

    def _render_finding(self, lines, idx, rec, module, rid_short) -> None:
        code = rec.get("code", "?")
        severity = rec.get("severity", "?")
        lines.append(f"[{idx}] {module} FINDING  | {code}  | {severity}")
        detail = rec.get("disposition_detail") or rec.get("message") or ""
        if detail:
            lines.append(f"    {str(detail)[:160]}")
        lines.append(f"    [record: {rid_short}...]")


# ---------------------------------------------------------------------------
# LLMRenderer
# ---------------------------------------------------------------------------

class LLMRenderer:
    """Anthropic API renderer.  Falls back to TemplateRenderer if no key/package."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: Optional[str] = None,
        _client: Any = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        self._available = False
        self._fallback_reason = ""
        if _client is not None:
            self._client = _client
            self._available = True
        elif not self._api_key:
            self._fallback_reason = "ANTHROPIC_API_KEY not set"
        else:
            # Construction is fail-closed: ImportError (no package) OR any other
            # exception the SDK might raise while building a client (a malformed
            # proxy env, an eager-validation change in a future SDK) degrades to
            # the template, never propagates. (4A.1b: the real-key path was never
            # exercised, so an `except ImportError` was mistaken for a full seal.)
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self._available = True
            except ImportError:
                self._fallback_reason = "anthropic package not installed"
            except Exception as exc:  # noqa: BLE001 — construction must never raise
                self._fallback_reason = f"client construction failed: {type(exc).__name__}"

    def _template_fallback(self, bundle: ExplanationBundle, reason: str,
                           register: Optional[str] = None) -> str:
        """The single degradation target: render the deterministic template body
        and mark WHY the LLM path was not used. Every fail-closed exit routes
        here so an operator always sees an honest ``[rendered by: template …]``."""
        body = TemplateRenderer()._render_body(bundle)
        reg = register or _register_for(bundle)
        return f"{body}\n[rendered by: template — {reason} | register: {reg}]"

    # Refusal / fallback bundles are AUTHORED copy — the honest refusal, the
    # near-miss bridge, the clarify prompt, the ledger meta-listing. There is
    # nothing to testify FROM and nothing for the model to improve; the authored
    # header IS the answer. These short-circuit to the template with NO LLM
    # round-trip, regardless of whether the bundle happens to carry records
    # (Session 4B.0 Fix-B extension of the 4A.1c no-evidence guard — defense in
    # depth: an unresolvable question must never reach the LLM renderer).
    _AUTHORED_COPY_SUBJECTS = frozenset({
        "unsupported", "near_miss", "clarify", "refusals",
    })

    def render(self, bundle: ExplanationBundle) -> str:
        if bundle.subject_type in ("remediation", "triage"):
            return self._render_register(bundle)
        if bundle.subject_type in self._AUTHORED_COPY_SUBJECTS:
            return self._template_fallback(
                bundle, "authored copy — rendered verbatim", "testimony")
        if not self._available:
            return self._template_fallback(
                bundle, f"--llm requested but {self._fallback_reason}", "testimony")

        # A bundle with no evidence chain has nothing to testify FROM: an honest
        # refusal / near-miss / clarify (authored copy), or a header-only summary
        # (an empty schedule listing — "Nothing scheduled for all"). Handing such a
        # bundle to the model only invites FABRICATED citations and prose in place
        # of the authored refusal (4A.1c: screenshots showed
        # "[record: Nothing scheduled for all]"). Render the template body verbatim
        # — it IS the answer — and never let an unresolvable question reach the LLM.
        if not bundle.ordered_records:
            return self._template_fallback(
                bundle, "no evidence chain — rendered verbatim", "testimony")

        # The LLM-touching body is wrapped so that ANY runtime failure — network,
        # auth (a bad/expired key), rate-limit, a malformed response, a parsing
        # error — degrades to the deterministic template. This method NEVER raises
        # (4A.1b: fail-closed armor, made real for the unmocked API path).
        try:
            prompt, known_ts, known_time, known_machines, known_records = \
                self._build_prompt_material(bundle)
            text = self._call_llm(prompt)
            issues = self._validate_testimony(
                text, known_ts, known_time, known_machines, known_records)
            if issues:
                regen_prompt, *_ = self._build_prompt_material(bundle, regen_note=issues)
                text = self._call_llm(regen_prompt)
                # Validate against the ORIGINAL known sets — not the regen prompt,
                # which contains the rejected output in its header and must not
                # whitelist itself.
                issues2 = self._validate_testimony(
                    text, known_ts, known_time, known_machines, known_records)
                if issues2:
                    body = TemplateRenderer()._render_body(bundle)
                    warn = "[LLM validation failed: {}; fell back to template]".format(
                        "; ".join(issues2[:2])
                    )
                    return (
                        body + "\n" + warn
                        + "\n[rendered by: template (LLM validated) | register: testimony]"
                    )
            return text + f"\n[rendered by: LLM ({self._model}) | register: testimony]"
        except Exception as exc:  # noqa: BLE001 — render must never raise
            return self._template_fallback(
                bundle, f"LLM error: {type(exc).__name__}", "testimony")

    def _render_register(self, bundle: ExplanationBundle) -> str:
        """Remediation / judgment-triage register (handoff §3): the deterministic
        authored body is the ground truth; the LLM may only reword it for
        fluency. The allowed-number set is derived from exactly that body (the
        single derivation), and any invented number fails closed to the body."""
        from mre.modules.remediation import (
            allowed_numbers, render_remediation_body, unverifiable_numbers,
        )
        from mre.modules.triage import render_triage_body

        register = _register_for(bundle)
        if bundle.subject_type == "remediation":
            body = render_remediation_body(
                bundle.ordered_records, limit=bundle.key_facts.get("limit"))
            intro = ("This is authored remediation guidance from the frozen "
                     "catalog. Reword it for fluency ONLY.")
        else:
            body = render_triage_body(bundle.ordered_records)
            intro = ("This is a grade-distance triage. Reword it for fluency "
                     "ONLY, keeping the fix-first order and the named arithmetic.")

        if not self._available:
            return (body + f"\n[rendered by: template — {self._fallback_reason} "
                    f"| register: {register}]")

        # Same fail-closed seal as render(): the authored body is ground truth, so
        # any LLM failure degrades to it — never a 5xx.
        try:
            allowed = allowed_numbers(body)
            prompt = (
                f"{intro}\n\n"
                "RULES (violating any causes fallback to the source text):\n"
                "1. Do NOT introduce any number, percentage, or § reference not "
                "present below.\n"
                "2. Do NOT invent causes, thresholds, or fixes — only what appears "
                "below.\n"
                "3. Keep every rule_id, catalog note version, and § citation.\n\n"
                f"SOURCE (authored):\n{body}\n"
            )
            text = self._call_llm(prompt)
            if unverifiable_numbers(text, allowed):
                return (body + "\n[LLM validation failed: invented a value; fell "
                        f"back to authored text]\n[rendered by: template (LLM "
                        f"validated) | register: {register}]")
            return text + f"\n[rendered by: LLM ({self._model}) | register: {register}]"
        except Exception as exc:  # noqa: BLE001 — register render must never raise
            return (body + f"\n[LLM error: {type(exc).__name__}; fell back to "
                    f"authored text]\n[rendered by: template (LLM error) "
                    f"| register: {register}]")

    def render_judgment(self, question: str, history: Any, fallback_bundle: ExplanationBundle) -> str:
        """Conversational turn in dialogue mode — reasons over prior evidence bundles."""
        if not self._available:
            body = TemplateRenderer()._render_body(fallback_bundle)
            return (
                body
                + f"\n[rendered by: template — {self._fallback_reason} | register: testimony]"
            )
        try:
            text = self._llm_judgment(question, history)
            return text + f"\n[rendered by: LLM ({self._model}) | register: judgment]"
        except Exception as exc:  # noqa: BLE001 — judgment render must never raise
            body = TemplateRenderer()._render_body(fallback_bundle)
            return (body + f"\n[LLM error: {type(exc).__name__}; fell back to "
                    "template]\n[rendered by: template (LLM error) | register: testimony]")

    def _build_prompt_material(
        self,
        bundle: ExplanationBundle,
        regen_note: Optional[list[str]] = None,
    ) -> tuple:
        """Return (prompt_text, known_ts, known_time, known_machines, known_records).

        The verifiable-value sets are extracted from the base evidence text (prompt
        without the regen_note header) — except known_records, taken straight from
        the bundle's real record ids.  This guarantees:
        - anything shown to the LLM in the evidence section is verifiable,
        - rejected values in a regen_note header cannot whitelist themselves, and
        - every [record: …] citation must name a REAL record in the bundle (4A.1c).
        """
        context = TemplateRenderer()._render_body(bundle)
        facts = self._extract_precomputed_facts(bundle)
        facts_section = "\n".join(f"  {k}: {v}" for k, v in facts.items()) or "  (none)"

        base_evidence = (
            "You are a manufacturing scheduling assistant. "
            "Report on the solved schedule using ONLY the evidence below.\n\n"
            "PRE-COMPUTED FACTS (copy these values exactly — never recompute):\n"
            + facts_section + "\n\n"
            + "EVIDENCE CHAIN:\n" + context + "\n\n"
            + "RULES (violating any rule causes regeneration):\n"
            "1. Quote every timestamp, number, and name EXACTLY as it appears above.\n"
            "   Never perform arithmetic or unit conversions.\n"
            "2. End every factual sentence with [record: XXXX] citing the record_id.\n"
            "3. Do not use causal language ('cascading', 'shifted', 'compressed', 'because of')\n"
            "   unless a record explicitly states it.\n"
            "4. Do not mention any machine, WO, date, or number absent from the evidence.\n"
            "5. Answer in 2-3 sentences.\n\n"
            + "QUESTION: " + bundle.question + "\n"
        )

        header = ""
        if regen_note:
            header = (
                "PREVIOUS ATTEMPT REJECTED — issues found:\n"
                + "\n".join(f"  - {i}" for i in regen_note)
                + "\nFix every issue. Do NOT compute values; quote only from evidence below.\n\n"
            )

        prompt_text = header + base_evidence

        # Extract verifiable sets from base_evidence only — not from the regen header.
        known_ts: set = set()
        for ts_str in _TS_FULL_RE.findall(base_evidence):
            tup = _to_minute_tuple(ts_str)
            if tup is not None:
                known_ts.add(tup)

        known_time: set = set()
        for m in _TIME_NUM_RE.finditer(base_evidence):
            val = float(m.group(1))
            normalized = _to_minutes(val, m.group(2))
            known_time.add(val)
            known_time.add(normalized)

        known_machines: set = set(_MACHINE_RE.findall(base_evidence))

        # The REAL record ids the answer is allowed to cite. The template footnotes
        # an 8-char prefix ("[record: abcd1234...]"); the LLM is told to cite the
        # record_id, so a citation is valid iff it is a prefix of a real id.
        known_records: set = {
            str(rec.get("record_id")) for rec in bundle.ordered_records
            if rec.get("record_id")
        }

        return prompt_text, known_ts, known_time, known_machines, known_records

    def _call_llm(self, prompt_text: str) -> str:
        import anthropic  # type: ignore
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return response.content[0].text

    def _extract_precomputed_facts(self, bundle: ExplanationBundle) -> dict[str, str]:
        """Return string-valued facts for the LLM to quote verbatim."""
        facts: dict[str, str] = {}
        kf = bundle.key_facts
        if kf.get("completion_iso"):
            facts["projected_completion"] = kf["completion_iso"]
        if kf.get("lateness_minutes") is not None:
            mins = kf["lateness_minutes"]
            facts["lateness"] = f"{int(mins)} min"
            if kf.get("lateness_hours") is not None:
                facts["lateness_hours"] = f"{kf['lateness_hours']}h"
        if kf.get("due_date"):
            facts["due_date"] = str(kf["due_date"])
        return facts

    def _validate_testimony(
        self,
        text: str,
        known_ts: set,
        known_time: set,
        known_machines: set,
        known_records: Optional[set] = None,
    ) -> list[str]:
        """Return validation issues; empty list means text is acceptable.

        All known-value sets must come from _build_prompt_material so that only
        values actually shown to the LLM are considered verifiable.
        """
        issues: list[str] = []
        known_records = known_records or set()

        # 1. Timestamps: parse both sides to (year,month,day,hour,minute) and compare.
        #    Tolerates dropped seconds, dropped Z, space-vs-T, UTC suffix, date-only.
        for ts_str in _TS_FULL_RE.findall(text):
            tup = _to_minute_tuple(ts_str)
            if tup is not None and not _ts_matches(tup, known_ts):
                issues.append(f"unverifiable timestamp '{ts_str}'")

        # 2. Time-unit numbers: normalize min/h/hours to minutes before comparing.
        #    "14h", "14.0 hours", "840 min", "840.0 min" all pass against a 840-min prompt.
        for m in _TIME_NUM_RE.finditer(text):
            val = float(m.group(1))
            normalized = _to_minutes(val, m.group(2))
            if val not in known_time and normalized not in known_time:
                issues.append(f"unverifiable time value '{m.group(0).strip()}'")

        # 3. Machine names: every M-XXXX in prose must appear in the prompt.
        for machine in _MACHINE_RE.findall(text):
            if machine not in known_machines:
                issues.append(f"unverifiable machine name '{machine}'")

        # 4. Footnotes: if any factual sentence exists, at least one must be footnoted.
        prose = re.sub(r'\n\[rendered by:.*', '', text, flags=re.DOTALL)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', prose) if s.strip()]
        factual = [s for s in sentences if re.search(r'\d|M-[A-Z]|WO-', s)]
        if factual and not any('[record:' in s for s in factual):
            issues.append("no [record:] footnotes on factual sentences")

        # 5. Record citations: every [record: X] must name a REAL record in the
        #    bundle (4A.1c — the LLM fabricated "[record: Nothing scheduled for
        #    all]" and "[record: evidence_chain_001]"). The template footnotes an
        #    8-char prefix, so a citation is valid iff it prefixes a real id.
        for cite in re.findall(r'\[record:\s*([^\]]*?)\s*\]', text):
            cid = cite.strip().rstrip('.').strip()   # drop the template's trailing "..."
            if cid in ("", "?"):
                continue                             # template placeholder, not a claim
            if not any(rid == cid or rid.startswith(cid) for rid in known_records):
                issues.append(f"fabricated record citation '{cite.strip()}'")

        return issues

    def _llm_judgment(self, question: str, history: Any) -> str:
        prompt = self._build_judgment_prompt(question, history)
        import anthropic  # type: ignore
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _build_judgment_prompt(self, question: str, history: Any) -> str:
        lines = [
            "You are a manufacturing scheduling assistant in dialogue mode.",
            "",
            "PRIOR TURNS (read-only evidence — do not invent facts beyond these):",
        ]
        for i, turn in enumerate(history.turns(), 1):
            lines.append(f"\n[Turn {i}] User: {turn.question}")
            if turn.bundle is not None:
                lines.append(f"  Key facts: {turn.bundle.key_facts}")
                body = TemplateRenderer()._render_body(turn.bundle)
                lines.append(f"  Evidence (excerpt):\n{body[:800]}")
            else:
                lines.append("  (judgment turn — no evidence bundle)")
            lines.append(f"  Answer: {turn.rendered[:400]}")
        lines.extend([
            f"\nNEW MESSAGE: {question}",
            "",
            "INSTRUCTIONS:",
            "- Open your response with 'My take:' or a natural equivalent.",
            "- Reason ONLY over facts from the prior turns above.",
            "  Do not invent schedule facts, assignments, or records.",
            "- When you extrapolate or suggest, name the specific record or metric.",
            "- If the question is testable by re-running the solver with changed parameters,",
            "  say it can be run and name the specific command or phrase, e.g.:",
            "  '\"what if we unbatch WO-2001 and WO-2002\" runs in the REPL,",
            "   or: python -m mre.whatif --suppress-merge WO-2001,WO-2002'.",
            "  Do NOT say 'not wired up yet'.",
            "- Keep your answer to 2-3 paragraphs.",
        ])
        return "\n".join(lines)
