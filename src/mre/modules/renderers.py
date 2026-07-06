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
from typing import Any, Optional

from mre.modules.explainer import ExplanationBundle


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
        lines: list[str] = []
        lines.append(f"=== {bundle.question} ===")
        lines.append("")

        self._render_header(lines, bundle)

        if not bundle.ordered_records:
            if bundle.subject_type == "diff":
                self._render_diff(lines, bundle.key_facts)
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
        subjects = rec.get("subjects", [])
        subject_name = ""
        if subjects:
            s = subjects[0]
            subject_name = _resolve_name(
                s.get("entity_id", ""), s.get("entity_type", ""), identity_map
            )
        lines.append(f"[{idx}] {module} METRIC  | {name}")
        subj_part = f" ({subject_name})" if subject_name else ""
        lines.append(f"    Value: {value} {unit}{subj_part}")
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
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        self._available = False
        if self._api_key:
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self._available = True
            except ImportError:
                pass

    def render(self, bundle: ExplanationBundle) -> str:
        if not self._available:
            return TemplateRenderer().render(bundle)
        return self._llm_render(bundle)

    def _llm_render(self, bundle: ExplanationBundle) -> str:
        context = TemplateRenderer().render(bundle)
        prompt = (
            "You are a manufacturing scheduling assistant. "
            "Below is a structured evidence chain from a scheduling system.\n\n"
            f"EVIDENCE:\n{context}\n\n"
            "INSTRUCTIONS:\n"
            "- Answer in 2-3 concise paragraphs for a production planner.\n"
            "- Use external names (WO-2001, M-GEAR-01), never internal IDs.\n"
            "- For reconstructed decisions say 'was assigned to X; Y was unavailable'.\n"
            "- Only cite facts present in the evidence chain above.\n\n"
            f"QUESTION: {bundle.question}\n"
        )
        import anthropic  # type: ignore
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
