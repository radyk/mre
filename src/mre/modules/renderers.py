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


def _to_minutes(value: float, unit: str) -> float:
    """Convert a time value to minutes based on its unit string."""
    return value * 60.0 if unit.lower().startswith('h') else value


def _collect_known_time_values(bundle: "ExplanationBundle") -> set:
    """Return all acceptable numeric time values from the bundle.

    For each minutes metric, also includes the hours equivalent so that
    prose using '14h' or '14.0 hours' passes when the bundle records 840 min.
    """
    values: set[float] = set()
    for rec in bundle.ordered_records:
        if rec.get("record_type") == "metric":
            v = rec.get("value")
            if not isinstance(v, (int, float)):
                continue
            v = float(v)
            unit = rec.get("unit", "").lower()
            values.add(v)
            values.add(round(v, 1))
            if "minute" in unit:
                h = v / 60.0
                values.add(h)
                values.add(round(h, 1))
                values.add(float(int(h)))
    for kv in bundle.key_facts.values():
        if isinstance(kv, (int, float)):
            kv = float(kv)
            values.add(kv)
            values.add(round(kv, 1))
    return values


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

class TemplateRenderer:
    """Deterministic text renderer.  No external calls."""

    def render(self, bundle: ExplanationBundle) -> str:
        return self._render_body(bundle) + "\n[rendered by: template | register: testimony]"

    def _render_body(self, bundle: ExplanationBundle) -> str:
        lines: list[str] = []
        lines.append(f"=== {bundle.question} ===")
        lines.append("")

        self._render_header(lines, bundle)

        if not bundle.ordered_records:
            if bundle.subject_type == "diff":
                self._render_diff(lines, bundle.key_facts)
            elif bundle.subject_type in (
                "downtime", "unsupported", "schedule", "scenario_diff",
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

        elif bundle.subject_type == "unsupported":
            kf = bundle.key_facts
            lines.append(f"I can't answer this question yet: \"{kf.get('parsed', '?')}\"")
            lines.append("")
            lines.append("Supported question types:")
            for route in kf.get("supported_routes", []):
                lines.append(f"  - {route}")
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
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self._available = True
            except ImportError:
                self._fallback_reason = "anthropic package not installed"

    def render(self, bundle: ExplanationBundle) -> str:
        if not self._available:
            body = TemplateRenderer()._render_body(bundle)
            return (
                body
                + f"\n[rendered by: template — --llm requested but {self._fallback_reason}"
                + " | register: testimony]"
            )

        text = self._llm_render(bundle)
        issues = self._validate_testimony(text, bundle)
        if issues:
            text = self._llm_render(bundle, validation_issues=issues)
            issues2 = self._validate_testimony(text, bundle)
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

    def render_judgment(self, question: str, history: Any, fallback_bundle: ExplanationBundle) -> str:
        """Conversational turn in dialogue mode — reasons over prior evidence bundles."""
        if not self._available:
            body = TemplateRenderer()._render_body(fallback_bundle)
            return (
                body
                + f"\n[rendered by: template — {self._fallback_reason} | register: testimony]"
            )
        text = self._llm_judgment(question, history)
        return text + f"\n[rendered by: LLM ({self._model}) | register: judgment]"

    def _llm_render(
        self, bundle: ExplanationBundle, validation_issues: Optional[list[str]] = None
    ) -> str:
        context = TemplateRenderer()._render_body(bundle)
        facts = self._extract_precomputed_facts(bundle)
        facts_section = "\n".join(f"  {k}: {v}" for k, v in facts.items()) or "  (none)"

        regen_note = ""
        if validation_issues:
            regen_note = (
                "PREVIOUS ATTEMPT REJECTED — issues found:\n"
                + "\n".join(f"  - {i}" for i in validation_issues)
                + "\nFix every issue. Do NOT compute values; quote only from evidence below.\n\n"
            )

        prompt = (
            regen_note
            + "You are a manufacturing scheduling assistant. "
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
        import anthropic  # type: ignore
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
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
        self, text: str, bundle: ExplanationBundle
    ) -> list[str]:
        """Return a list of validation issues; empty list means text is acceptable."""
        issues: list[str] = []

        bundle_body = TemplateRenderer()._render_body(bundle)
        kf_text = " ".join(str(v) for v in bundle.key_facts.values() if v is not None)
        all_bundle_text = bundle_body + " " + kf_text

        # 1. Timestamps: parse both sides to (year,month,day,hour,minute) and compare.
        #    Tolerates dropped seconds, dropped Z, space-vs-T, UTC suffix, date-only.
        known_ts: set[tuple] = set()
        for ts_str in _TS_FULL_RE.findall(all_bundle_text):
            tup = _to_minute_tuple(ts_str)
            if tup is not None:
                known_ts.add(tup)
        for ts_str in _TS_FULL_RE.findall(text):
            tup = _to_minute_tuple(ts_str)
            if tup is not None and not _ts_matches(tup, known_ts):
                issues.append(f"unverifiable timestamp '{ts_str}'")

        # 2. Time-unit numbers: normalize min/h/hours to minutes before comparing.
        #    "14h", "14.0 hours", "840 min", "840.0 min" all pass against a 840-min metric.
        known_time = _collect_known_time_values(bundle)
        for m in _TIME_NUM_RE.finditer(text):
            val = float(m.group(1))
            normalized = _to_minutes(val, m.group(2))
            if val not in known_time and normalized not in known_time:
                issues.append(f"unverifiable time value '{m.group(0).strip()}'")

        # 3. Machine names: every M-XXXX in prose must appear in bundle
        known_machines = set(_MACHINE_RE.findall(all_bundle_text))
        for machine in _MACHINE_RE.findall(text):
            if machine not in known_machines:
                issues.append(f"unverifiable machine name '{machine}'")

        # 4. Footnotes: if any factual sentence exists, at least one must be footnoted
        prose = re.sub(r'\n\[rendered by:.*', '', text, flags=re.DOTALL)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', prose) if s.strip()]
        factual = [s for s in sentences if re.search(r'\d|M-[A-Z]|WO-', s)]
        if factual and not any('[record:' in s for s in factual):
            issues.append("no [record:] footnotes on factual sentences")

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
