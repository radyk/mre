"""DQ Report generator.

Reads ONLY from consolidated evidence documents — never from raw ERP extracts.
Renders affected entities in planner vocabulary via external refs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from mre.modules.identity_map import IdentityMap


def generate_dq_report(
    adapter_doc: dict,
    validator_doc: dict,
    identity_map: Optional[IdentityMap],
    output_path: Path,
) -> None:
    """Write a Markdown DQ report to output_path.

    Parameters sourced only from consolidated docs + identity map.
    No CSV paths or raw extract data.
    """
    output_path = Path(output_path)

    adapter_findings = [
        r for r in adapter_doc.get("records", [])
        if r.get("record_type") == "finding"
    ]
    validator_findings = [
        r for r in validator_doc.get("records", [])
        if r.get("record_type") == "finding"
    ]
    all_findings = adapter_findings + validator_findings

    # Provenance stats from adapter run_context (via records)
    all_prov_records = [
        r for r in adapter_doc.get("records", [])
        if r.get("record_type") == "artifact"
    ]
    prov_counts = _count_provenance_classes(adapter_doc, validator_doc)

    # Go/no-go from validator run context
    val_ctx = validator_doc.get("run_context", {})
    # We infer go/no-go from absence of blocker findings
    has_blocker = any(f.get("severity") == "blocker" for f in all_findings)
    go_nogo = "NO-GO" if has_blocker else "GO"

    # Group findings by code
    by_code: dict[str, list[dict]] = defaultdict(list)
    for f in all_findings:
        by_code[f["code"]].append(f)

    lines: list[str] = []
    lines.append("# Data Quality Report")
    lines.append("")

    # Run context summary
    adapter_ctx = adapter_doc.get("run_context", {})
    snap_id = adapter_ctx.get("snapshot_id", "unknown")
    lines.append(f"**Snapshot:** `{snap_id}`  ")
    lines.append(f"**Adapter run:** `{adapter_ctx.get('run_id', 'unknown')}`  ")
    lines.append(f"**Validator run:** `{val_ctx.get('run_id', 'unknown')}`  ")
    lines.append(f"**Go/No-Go Gate:** **{go_nogo}**")
    lines.append("")

    # Summary counts
    sev_counts: Counter = Counter(f.get("severity", "unknown") for f in all_findings)
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ("blocker", "error", "warning", "info"):
        count = sev_counts.get(sev, 0)
        if count > 0:
            lines.append(f"| {sev} | {count} |")
    if not any(sev_counts.get(s, 0) > 0 for s in ("blocker", "error", "warning", "info")):
        lines.append("| (none) | 0 |")
    lines.append("")

    # Findings by code
    lines.append("## Findings by Code")
    lines.append("")

    for code in sorted(by_code.keys()):
        findings = by_code[code]
        lines.append(f"### {code}")
        lines.append("")
        lines.append(f"**Count:** {len(findings)}")
        lines.append("")

        for f in findings:
            severity = f.get("severity", "?")
            disposition = f.get("disposition", "?")
            message = f.get("message", "") or f.get("evidence", {}).get("reason", "")
            subjects = f.get("subjects", [])

            # Render subject as ERP identifier if available via identity map
            subject_labels = []
            for s in subjects:
                eid = s.get("entity_id") if isinstance(s, dict) else getattr(s, "entity_id", "")
                label = _resolve_label(eid, identity_map) or eid[:12]
                subject_labels.append(label)

            # Also try to get ERP label from evidence
            evidence = f.get("evidence", {})
            erp_label = (
                evidence.get("wono")
                or evidence.get("product_no")
                or evidence.get("machine_id")
                or ""
            )
            if erp_label and erp_label not in subject_labels:
                subject_labels.append(erp_label)

            subject_str = ", ".join(subject_labels) if subject_labels else "(no subjects)"
            lines.append(
                f"- **{severity}** / {disposition}: {message or '(see evidence)'}"
                f"  — entities: {subject_str}"
            )

        lines.append("")

    # Provenance composition stats
    lines.append("## Provenance Composition")
    lines.append("")
    if prov_counts:
        lines.append("| Class | Count |")
        lines.append("|-------|-------|")
        for cls, count in sorted(prov_counts.items()):
            lines.append(f"| {cls} | {count} |")
    else:
        lines.append("*No provenance statistics available.*")
    lines.append("")

    # Entities in planner vocabulary (via external refs from identity map)
    if identity_map:
        lines.append("## Entities Referenced in Findings")
        lines.append("")
        referenced_ids = set()
        for f in all_findings:
            for s in f.get("subjects", []):
                eid = s.get("entity_id") if isinstance(s, dict) else getattr(s, "entity_id", "")
                if eid:
                    referenced_ids.add(eid)

        if referenced_ids:
            lines.append("| Canonical ID | ERP Reference |")
            lines.append("|-------------|---------------|")
            for cid in sorted(referenced_ids):
                erefs = identity_map.external_refs(cid)
                erp_str = ", ".join(f"{e.system}/{e.type}={e.value}" for e in erefs) if erefs else "(unregistered)"
                lines.append(f"| `{cid[:16]}…` | {erp_str} |")
        else:
            lines.append("*(no entities referenced)*")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _resolve_label(entity_id: str, identity_map: Optional[IdentityMap]) -> Optional[str]:
    if not identity_map or not entity_id:
        return None
    erefs = identity_map.external_refs(entity_id)
    if not erefs:
        return None
    return f"{erefs[0].value}"


def _count_provenance_classes(
    adapter_doc: dict, validator_doc: dict
) -> dict[str, int]:
    """Count provenance class mentions from run context and event payloads."""
    counts: Counter = Counter()
    for doc in (adapter_doc, validator_doc):
        ctx = doc.get("run_context", {})
        cfg = ctx.get("config_snapshot") or {}
        # Metrics and events sometimes carry provenance info; for Phase 1 use a heuristic
        for rec in doc.get("records", []):
            if rec.get("record_type") == "finding":
                ev = rec.get("evidence", {})
                for pclass in ("synthesized", "observed", "derived", "defaulted"):
                    if pclass in str(ev).lower():
                        counts[pclass] += 1
    # If we have no signal from findings, note that all data was synthesized
    if not counts:
        counts["synthesized"] = 1
    return dict(counts)
