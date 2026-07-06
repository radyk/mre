"""M10 — Explainer.

Strictly read-only: this module has no import of Reporter or SnapshotWriter.
It assembles ExplanationBundles from the evidence index and snapshot store,
then renders them via TemplateRenderer (all tests) or LLMRenderer (--llm flag).

Entry points:
  explainer.answer("Why is WO-2001 late?")         -> ExplanationBundle
  explainer.summarize_run()                          -> ExplanationBundle
  explainer.snapshot_diff("snap-v1", "snap-v2")     -> dict

Keyword routing (no NLU, no embeddings):
  "late"           + WO ref  -> _explain_why_late
  "on" / "assign"  + WO+M    -> _explain_why_on_machine
  "data problem" / "finding" -> _explain_data_problems
  "changed" / "diff"         -> _explain_what_changed (snapshot diff)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mre.modules.evidence_index import EvidenceIndex

_SUPPORTED_ROUTES = [
    '"Why is WO-XXXX late?" — lateness cause chain',
    '"Are there any late orders?" — all late demands',
    '"Why is WO-XXXX on M-YYYY?" — machine assignment reason',
    '"What data problems exist?" — findings and quality issues',
    '"What changed since snap-a vs snap-b?" — snapshot diff',
    '"summarize" — run summary',
    '"How much downtime does [machine/pool] have?" — calendar closures',
    '"When does WO-XXXX start/finish?" — schedule for a work order',
    '"What is running on M-YYYY [date]?" — machine schedule',
    '"What\'s next on M-YYYY?" — upcoming jobs on a machine',
    '"Schedule for customer X" — all jobs for a customer',
    '"Show the schedule" / "full schedule" — complete schedule',
]

_SCHEDULE_TRIGGERS = frozenset({
    "schedule", "scheduled", "running on", "next on",
    "when does", "when will", "when is",
    "when start", "when finish", "when complete",
    "start on", "finish on",
})


@dataclass
class ExplanationBundle:
    """Structured, renderer-agnostic answer to a question.

    ordered_records  — evidence records in pipeline order (M1 < M7)
    key_facts        — scalar summary used by renderers as the headline
    identity_map     — for resolving UUIDs to external names (WO-XXXX, M-GEAR-01)
    """
    question: str
    subject_id: str
    subject_type: str                        # "demand", "run", "diff", "findings"
    subject_external_name: str
    ordered_records: list[dict]
    key_facts: dict[str, Any]
    snapshot_id: str
    identity_map: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

class Explainer:
    """Read-only answer engine.  No write path."""

    def __init__(
        self,
        snapshot_store: Any,
        index: EvidenceIndex,
        snapshot_id: str = "snap-run",
    ) -> None:
        self._store = snapshot_store
        self._index = index
        self._snap_id = snapshot_id
        self._reader = snapshot_store.load_snapshot(snapshot_id)
        self._identity_map = self._reader.read_identity_map()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, question: str) -> ExplanationBundle:
        """Route a natural-language question to the right assembler."""
        q = question.lower()
        wo_match = re.search(r'WO-[\w-]+', question, re.IGNORECASE)
        m_match = re.search(r'M-[A-Z0-9-]+', question, re.IGNORECASE)

        if ("late" in q or "delay" in q or "tardy" in q) and wo_match:
            return self._explain_why_late(wo_match.group().upper())
        if ("late" in q or "delay" in q or "tardy" in q) and not wo_match:
            return self._list_late_orders()
        if ("on" in q or "assign" in q or "why" in q) and wo_match and m_match:
            return self._explain_why_on_machine(
                wo_match.group().upper(), m_match.group().upper()
            )
        if "data problem" in q or "finding" in q or "quality" in q:
            return self._explain_data_problems()
        if ("change" in q or "diff" in q or "since" in q or "update" in q):
            return self._explain_what_changed(question)
        if "downtime" in q or "closure" in q or "offline" in q:
            return self._explain_downtime(question)
        if any(kw in q for kw in _SCHEDULE_TRIGGERS):
            return self._schedule_query(question, q, wo_match, m_match)
        if wo_match:
            return self._explain_why_late(wo_match.group().upper())
        return self._unknown_question(question)

    def summarize_run(self, run_id: Optional[str] = None) -> ExplanationBundle:
        """High-level run summary: notable decisions + findings + late demands."""
        if run_id is None:
            # Most recent M7 run
            m7_runs = [r for r in self._index.runs() if r.get("module") == "M7"]
            if m7_runs:
                run_id = sorted(
                    m7_runs, key=lambda r: r.get("timestamp_close", "")
                )[-1]["run_id"]
            else:
                run_id = "unknown"

        all_ev = self._index._all_evidence
        run_records = [r for r in all_ev if r.get("run_id") == run_id]

        notable_decisions = [
            r for r in run_records
            if r.get("record_type") == "decision"
            and r.get("driver") in ("SETUP_AMORTIZATION", "CALENDAR_WINDOW", "DEMAND_MERGE")
        ]
        affecting_findings = [
            r for r in run_records
            if r.get("record_type") == "finding"
            and r.get("disposition") in ("defaulted", "excluded", "blocked")
        ]
        late_metrics = [
            r for r in run_records
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]

        ordered = sorted(
            notable_decisions + affecting_findings + late_metrics,
            key=lambda r: (
                {"M1": 1, "M3": 3, "M4": 4, "M5": 5, "M6": 6, "M7": 7}.get(
                    r.get("module", ""), 9
                ),
                r.get("seq", 0),
            ),
        )

        return ExplanationBundle(
            question="Run summary",
            subject_id=run_id,
            subject_type="run",
            subject_external_name=run_id[:12] if run_id else "?",
            ordered_records=ordered,
            key_facts={
                "run_id": run_id,
                "notable_decision_count": len(notable_decisions),
                "affecting_finding_count": len(affecting_findings),
                "late_demand_count": len(late_metrics),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def snapshot_diff(self, snap_id_a: str, snap_id_b: str) -> dict:
        """Entity-level diff between two snapshots.

        Returns:
          added_demands    — WO external refs present in b but not a
          removed_demands  — WO external refs present in a but not b
          changed_demands  — [{work_order, field, from, to}, ...]
          costmodel_diff   — {version_a, version_b, rate_changes: {name: {from, to}}}
        """
        reader_a = self._store.load_snapshot(snap_id_a)
        reader_b = self._store.load_snapshot(snap_id_b)
        im_a = reader_a.read_identity_map()
        im_b = reader_b.read_identity_map()

        def _wo_map(reader) -> dict[str, dict]:
            result: dict[str, dict] = {}
            for d in reader.iter_entities("demand"):
                wo = next(
                    (r.get("value") for r in d.get("external_refs", [])
                     if r.get("type") == "work_order"),
                    None,
                )
                if wo:
                    result[wo] = d
            return result

        demands_a = _wo_map(reader_a)
        demands_b = _wo_map(reader_b)

        added = sorted(set(demands_b) - set(demands_a))
        removed = sorted(set(demands_a) - set(demands_b))

        changed: list[dict] = []
        for wo in sorted(set(demands_a) & set(demands_b)):
            d_a = demands_a[wo]
            d_b = demands_b[wo]
            for fld in ("due", "quantity", "commitment_class"):
                v_a = d_a.get(fld)
                v_b = d_b.get(fld)
                if v_a != v_b:
                    changed.append({"work_order": wo, "field": fld, "from": v_a, "to": v_b})

        # CostModel version diff
        costmodel_diff: dict = {}
        cms_a = list(reader_a.iter_entities("costmodel"))
        cms_b = list(reader_b.iter_entities("costmodel"))
        if cms_a and cms_b:
            cm_a = cms_a[0]
            cm_b = cms_b[0]
            rates_a: dict[str, float] = cm_a.get("resource_rates", {})
            rates_b: dict[str, float] = cm_b.get("resource_rates", {})
            rate_changes: dict[str, dict] = {}
            all_ids = set(rates_a) | set(rates_b)
            for rid in all_ids:
                r_a = rates_a.get(rid)
                r_b = rates_b.get(rid)
                if r_a != r_b:
                    # Resolve canonical UUID to machine_id for readability
                    name = rid
                    if im_a:
                        refs = im_a.external_refs(rid)
                        mname = next((r.value for r in refs if r.type == "machine_id"), None)
                        if mname:
                            name = mname
                    rate_changes[name] = {"from": r_a, "to": r_b}
            costmodel_diff = {
                "version_a": cm_a.get("version"),
                "version_b": cm_b.get("version"),
                "rate_changes": rate_changes,
            }

        return {
            "snapshot_a": snap_id_a,
            "snapshot_b": snap_id_b,
            "added_demands": added,
            "removed_demands": removed,
            "changed_demands": changed,
            "costmodel_diff": costmodel_diff,
        }

    # ------------------------------------------------------------------
    # Private assemblers
    # ------------------------------------------------------------------

    def _list_late_orders(self) -> ExplanationBundle:
        """Return all demands with positive lateness_minutes from the evidence index."""
        all_ev = self._index._all_evidence
        late_metrics = [
            r for r in all_ev
            if r.get("record_type") == "metric"
            and r.get("name") == "lateness_minutes"
            and (r.get("value") or 0.0) > 0
        ]

        late_items = []
        for m in late_metrics:
            subj_ids = [s.get("entity_id") for s in m.get("subjects", [])]
            for did in subj_ids:
                if did:
                    refs = self._identity_map.external_refs(did) if self._identity_map else []
                    wo_name = refs[0].value if refs else did[:8]
                    late_items.append({
                        "demand_id": did,
                        "wo": wo_name,
                        "lateness_minutes": m.get("value"),
                    })

        return ExplanationBundle(
            question="Are there any late orders?",
            subject_id="all",
            subject_type="late_orders",
            subject_external_name="all demands",
            ordered_records=late_metrics,
            key_facts={
                "late_count": len(late_items),
                "late_orders": [
                    f"{item['wo']} (+{int(item['lateness_minutes'])} min)"
                    for item in late_items
                ],
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_late(self, wo_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} late?", wo_ref, "demand")

        demand = self._reader.get_entity(demand_id) or {}
        due_date = demand.get("due", "unknown")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        lateness = None
        completion_iso = None
        for rec in records:
            if rec.get("record_type") != "metric":
                continue
            name = rec.get("name", "")
            if name == "lateness_minutes":
                if any(s.get("entity_id") == demand_id for s in rec.get("subjects", [])):
                    lateness = rec.get("value")
            elif name == "projected_completion_epoch":
                epoch = rec.get("value")
                if isinstance(epoch, (int, float)):
                    completion_iso = datetime.fromtimestamp(
                        epoch, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M UTC")

        return ExplanationBundle(
            question=f"Why is {wo_ref} late?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=records,
            key_facts={
                "lateness_minutes": lateness,
                "lateness_hours": round(lateness / 60, 1) if lateness is not None else None,
                "due_date": due_date,
                "completion_iso": completion_iso,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_why_on_machine(self, wo_ref: str, machine_ref: str) -> ExplanationBundle:
        demand_id = self._resolve_wo(wo_ref)
        if demand_id is None:
            return self._unknown(f"Why is {wo_ref} on {machine_ref}?", wo_ref, "demand")

        records = self._index.lineage_walk(demand_id, snapshot_reader=self._reader)

        # Filter to assignment decisions only
        assignment_records = [
            r for r in records
            if r.get("record_type") == "decision" and r.get("decision_type") == "assignment"
        ]

        return ExplanationBundle(
            question=f"Why is {wo_ref} on {machine_ref}?",
            subject_id=demand_id,
            subject_type="demand",
            subject_external_name=wo_ref,
            ordered_records=assignment_records or records,
            key_facts={"machine_ref": machine_ref},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_data_problems(self) -> ExplanationBundle:
        findings = sorted(
            self._index.all_findings(),
            key=lambda r: (
                {"blocker": 0, "error": 1, "warning": 2, "info": 3}.get(
                    r.get("severity", "info"), 9
                ),
                r.get("seq", 0),
            ),
        )
        codes = sorted({r.get("code", "") for r in findings})
        return ExplanationBundle(
            question="What data problems exist?",
            subject_id=self._snap_id,
            subject_type="findings",
            subject_external_name=self._snap_id,
            ordered_records=findings,
            key_facts={
                "total_findings": len(findings),
                "codes": codes,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_what_changed(self, question: str) -> ExplanationBundle:
        snap_match = re.findall(r'snap[\w-]+', question, re.IGNORECASE)
        if len(snap_match) >= 2:
            snap_a, snap_b = snap_match[0], snap_match[1]
        elif len(snap_match) == 1:
            snap_a, snap_b = snap_match[0], self._snap_id
        else:
            snap_a, snap_b = self._snap_id, self._snap_id

        try:
            diff = self.snapshot_diff(snap_a, snap_b)
        except FileNotFoundError as exc:
            diff = {"error": str(exc)}

        return ExplanationBundle(
            question=question,
            subject_id=f"{snap_a}->{snap_b}",
            subject_type="diff",
            subject_external_name=f"{snap_a} -> {snap_b}",
            ordered_records=[],
            key_facts=diff,
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _unknown_question(self, question: str) -> ExplanationBundle:
        """Return an explicit 'unsupported' bundle — never silently reroute."""
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type="unsupported",
            subject_external_name="?",
            ordered_records=[],
            key_facts={
                "parsed": question,
                "supported_routes": _SUPPORTED_ROUTES,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _explain_downtime(self, question: str) -> ExplanationBundle:
        """Sum calendar closure windows for a named resource, pool, or setup family."""
        resources = {r["id"]: r for r in self._reader.iter_entities("resource")}
        calendars = {c["id"]: c for c in self._reader.iter_entities("calendar")}
        pools = list(self._reader.iter_entities("resourcepool"))

        m_match = re.search(r'M-[A-Z0-9-]+', question, re.IGNORECASE)

        if m_match:
            machine_name = m_match.group().upper()
            rid = self._identity_map.resolve("ERP", "machine_id", machine_name) if self._identity_map else None
            target_ids = [rid] if rid else []
            subject_label = machine_name
        else:
            _STOP = {"how", "much", "does", "do", "have", "any", "is", "are", "the",
                     "a", "an", "for", "in", "what", "which", "show", "me",
                     "downtime", "closures", "closure", "offline", "scheduled"}
            words = {w.strip("?.,!") for w in question.lower().split()
                     if w.strip("?.,!") not in _STOP and len(w.strip("?.,!")) > 2}

            target_ids = []
            subject_label = "all resources"
            for pool in pools:
                for ref in pool.get("external_refs", []):
                    pname = ref.get("value", "").lower()
                    if any(word in pname for word in words):
                        target_ids.extend(pool.get("members", []))
                        subject_label = ref.get("value", subject_label)
                        break
                if target_ids:
                    break

            if not target_ids:
                # Fallback: setup_family substring match via assignments in snapshot
                op_ids_by_family: dict[str, list[str]] = {}
                for op in self._reader.iter_entities("operation"):
                    fam = op.get("setup_family", "").lower()
                    if any(word in fam for word in words):
                        op_ids_by_family.setdefault(fam, []).append(op["id"])
                        subject_label = fam
                if op_ids_by_family:
                    matched_ops = {oid for ids in op_ids_by_family.values() for oid in ids}
                    for asgn in self._reader.iter_entities("assignment"):
                        if asgn.get("operation_ref") in matched_ops:
                            for ra in asgn.get("resource_assignments", []):
                                rid = ra.get("resource_ref", "") if isinstance(ra, dict) else getattr(ra, "resource_ref", "")
                                if rid and rid not in target_ids:
                                    target_ids.append(rid)

            if not target_ids:
                target_ids = list(resources.keys())

        # Sum closure exceptions per resource
        closures: list[dict] = []
        for rid in sorted(set(target_ids)):
            resource = resources.get(rid)
            if not resource:
                continue
            cal_ref = resource.get("calendar_ref")
            cal = calendars.get(cal_ref) if cal_ref else None
            if not cal:
                continue
            res_name = rid[:8]
            if self._identity_map:
                refs = self._identity_map.external_refs(rid)
                mref = next((r for r in refs if r.type == "machine_id"), None)
                if mref:
                    res_name = mref.value
            for exc in cal.get("exceptions", []):
                if exc.get("type") != "closure":
                    continue
                window = exc.get("window", {})
                start_str = window.get("start", "")
                end_str = window.get("end", "")
                if not (start_str and end_str):
                    continue
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                hours = round((end_dt - start_dt).total_seconds() / 3600, 1)
                closures.append({
                    "resource": res_name,
                    "duration_hours": hours,
                    "reason": exc.get("reason", "unknown"),
                    "date": start_dt.strftime("%Y-%m-%d"),
                })

        total_hours = round(sum(c["duration_hours"] for c in closures), 1)
        return ExplanationBundle(
            question=question,
            subject_id=subject_label,
            subject_type="downtime",
            subject_external_name=subject_label,
            ordered_records=[],
            key_facts={
                "subject": subject_label,
                "closures": closures,
                "total_hours": total_hours,
                "resource_count": len({c["resource"] for c in closures}),
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    # ------------------------------------------------------------------
    # Schedule query assembler
    # ------------------------------------------------------------------

    def _schedule_query(
        self, question: str, q: str, wo_match, m_match
    ) -> ExplanationBundle:
        flt, label = self._build_schedule_filter(q, wo_match, m_match)

        # Resolve target resource IDs (None = no machine filter)
        target_res_ids: Optional[set[str]] = None
        if flt.get("machine"):
            rid = (
                self._identity_map.resolve("ERP", "machine_id", flt["machine"])
                if self._identity_map else None
            )
            target_res_ids = {rid} if rid else set()
        elif flt.get("pool_words"):
            target_res_ids = self._resolve_pool_resource_ids(flt["pool_words"])

        rows = self._load_enriched_assignments()
        filtered = self._apply_schedule_filter(rows, flt, target_res_ids)
        filtered.sort(key=lambda r: (r["machine"], r["start"]))
        if flt.get("limit"):
            filtered = filtered[: flt["limit"]]

        row_dicts = []
        for r in filtered:
            svc_facts = r.get("service_outcomes", {})
            lateness_min: Optional[float] = None
            if svc_facts:
                mins = [
                    _parse_iso_duration_minutes(s.get("lateness", ""))
                    for s in svc_facts.values()
                    if s.get("lateness")
                ]
                if mins:
                    lateness_min = max(mins)
            row_dicts.append({
                "work_orders": "+".join(sorted(r["work_orders"])) or "?",
                "op_seq": r["op_seq"],
                "setup_family": r["setup_family"],
                "machine": r["machine"],
                "start": _fmt_ts(r["start"]),
                "end": _fmt_ts(r["end"]),
                "lateness_minutes": lateness_min,
            })

        empty_msg = ""
        if not row_dicts:
            parts = [p for p in [
                flt.get("machine") or (
                    "pool" if flt.get("pool_words") else None
                ),
                flt.get("work_order"),
                f"on {flt['time_from'].date()}" if flt.get("time_from") else None,
            ] if p]
            empty_msg = f"Nothing scheduled for {label}."

        return ExplanationBundle(
            question=question,
            subject_id=label,
            subject_type="schedule",
            subject_external_name=label,
            ordered_records=[],
            key_facts={
                "filter_label": label,
                "rows": row_dicts,
                "total_rows": len(row_dicts),
                "empty_message": empty_msg,
            },
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )

    def _build_schedule_filter(self, q: str, wo_match, m_match) -> tuple[dict, str]:
        """Return (filter_dict, human_label)."""
        flt: dict[str, Any] = {}
        label_parts: list[str] = []

        if wo_match:
            flt["work_order"] = wo_match.group().upper()
            label_parts.append(flt["work_order"])
        if m_match:
            flt["machine"] = m_match.group().upper()
            label_parts.append(flt["machine"])

        # Time window
        now = datetime.now(timezone.utc)
        date_m = re.search(r'\d{4}-\d{2}-\d{2}', q)
        if "today" in q:
            d = now.date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append("today")
        elif "tomorrow" in q:
            d = (now + timedelta(days=1)).date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append("tomorrow")
        elif "this week" in q:
            d = now.date()
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=7)
            label_parts.append("this week")
        elif date_m:
            from datetime import date as _date
            d = _date.fromisoformat(date_m.group())
            flt["time_from"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            flt["time_to"] = flt["time_from"] + timedelta(days=1)
            label_parts.append(date_m.group())

        if "next" in q:
            flt["limit"] = 5

        # Customer
        cust_m = re.search(r'customer\s+(\S+)', q)
        if cust_m:
            flt["customer"] = cust_m.group(1).strip("?.,!")
            label_parts.append(f"customer {flt['customer']}")

        # Pool words (for "casting", "gear", etc. when no machine regex matched)
        if not flt.get("machine") and not flt.get("work_order") and not flt.get("customer"):
            _STOP = {"how", "much", "does", "do", "have", "any", "is", "are", "the",
                     "a", "an", "for", "in", "what", "which", "show", "me",
                     "schedule", "scheduled", "running", "on", "next", "full",
                     "when", "start", "finish", "complete", "will", "does"}
            words = {w.strip("?.,!") for w in q.split()
                     if w.strip("?.,!") not in _STOP and len(w.strip("?.,!")) > 2}
            if words:
                flt["pool_words"] = words

        label = " / ".join(label_parts) if label_parts else "all"
        return flt, label

    def _resolve_pool_resource_ids(self, words: set[str]) -> set[str]:
        result: set[str] = set()
        for pool in self._reader.iter_entities("resourcepool"):
            for ref in pool.get("external_refs", []):
                pname = ref.get("value", "").lower()
                if any(w in pname for w in words):
                    result.update(pool.get("members", []))
                    break
        return result

    def _load_enriched_assignments(self) -> list[dict]:
        ops_by_id = {o["id"]: o for o in self._reader.iter_entities("operation")}
        wp_to_fuls: dict[str, list[dict]] = {}
        for f in self._reader.iter_entities("fulfillment"):
            wp_to_fuls.setdefault(f["workpackage_ref"], []).append(f)
        demands_by_id = {d["id"]: d for d in self._reader.iter_entities("demand")}
        outcomes_by_demand: dict[str, dict] = {}
        for svc in self._reader.iter_entities("serviceoutcome"):
            outcomes_by_demand[svc["demand_ref"]] = svc

        rows: list[dict] = []
        for asgn in self._reader.iter_entities("assignment"):
            op_id = asgn.get("operation_ref", "")
            wp_id = asgn.get("workpackage_ref", "")
            op = ops_by_id.get(op_id, {})

            res_id = ""
            for ra in asgn.get("resource_assignments", []):
                ra_dict = ra if isinstance(ra, dict) else vars(ra)
                res_id = ra_dict.get("resource_ref", "")
                break

            machine_name = res_id[:8]
            if self._identity_map and res_id:
                refs = self._identity_map.external_refs(res_id)
                mref = next((r for r in refs if r.type == "machine_id"), None)
                if mref:
                    machine_name = mref.value

            demand_ids = [f["demand_ref"] for f in wp_to_fuls.get(wp_id, [])]
            wo_names: list[str] = []
            customer_vals: list[str] = []
            for did in demand_ids:
                dem = demands_by_id.get(did, {})
                for ref in dem.get("external_refs", []):
                    if ref.get("type") == "work_order":
                        wo_names.append(ref["value"])
                    elif ref.get("type") == "customer":
                        customer_vals.append(ref["value"])

            run_windows = asgn.get("phase_windows", {}).get("run", [])
            start_str = run_windows[0]["start"] if run_windows else ""
            end_str = run_windows[0]["end"] if run_windows else ""

            svc_facts: dict[str, dict] = {}
            for did in demand_ids:
                svc = outcomes_by_demand.get(did)
                if svc:
                    svc_facts[did] = {
                        "lateness": svc.get("lateness", ""),
                        "projected_completion": svc.get("projected_completion", ""),
                        "tardiness_cost": svc.get("tardiness_cost", 0.0),
                    }

            rows.append({
                "assignment_id": asgn["id"],
                "operation_ref": op_id,
                "workpackage_ref": wp_id,
                "op_seq": op.get("sequence"),
                "setup_family": op.get("setup_family", ""),
                "machine": machine_name,
                "resource_id": res_id,
                "start": start_str,
                "end": end_str,
                "work_orders": wo_names,
                "demand_ids": demand_ids,
                "customer_ids": customer_vals,
                "service_outcomes": svc_facts,
            })
        return rows

    @staticmethod
    def _apply_schedule_filter(
        rows: list[dict], flt: dict, target_res_ids: Optional[set[str]]
    ) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            if flt.get("work_order") and flt["work_order"] not in r["work_orders"]:
                continue
            if target_res_ids is not None and r["resource_id"] not in target_res_ids:
                continue
            if flt.get("customer") and flt["customer"].lower() not in [
                c.lower() for c in r["customer_ids"]
            ]:
                continue
            if flt.get("time_from") or flt.get("time_to"):
                try:
                    s = _parse_ts(r["start"])
                    e = _parse_ts(r["end"])
                except Exception:
                    continue
                if flt.get("time_from") and e < flt["time_from"]:
                    continue
                if flt.get("time_to") and s >= flt["time_to"]:
                    continue
            out.append(r)
        return out

    def _resolve_wo(self, wo_ref: str) -> Optional[str]:
        if self._identity_map is None:
            return None
        return self._identity_map.resolve("ERP", "work_order", wo_ref)

    def _unknown(self, question: str, ref: str, entity_type: str) -> ExplanationBundle:
        return ExplanationBundle(
            question=question,
            subject_id="",
            subject_type=entity_type,
            subject_external_name=ref,
            ordered_records=[],
            key_facts={"error": f"Unknown {entity_type}: {ref}"},
            snapshot_id=self._snap_id,
            identity_map=self._identity_map,
        )


# ---------------------------------------------------------------------------
# Module-level helpers (no snapshot access required)
# ---------------------------------------------------------------------------

def _parse_iso_duration_minutes(s: str) -> float:
    """Parse ISO 8601 duration like 'PT840M' or '-P5DT6H57M' to minutes."""
    if not s:
        return 0.0
    negative = s.startswith("-")
    s = s.lstrip("-")
    m = re.match(
        r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?',
        s,
    )
    if not m:
        return 0.0
    days = float(m.group(1) or 0)
    hours = float(m.group(2) or 0)
    minutes = float(m.group(3) or 0)
    seconds = float(m.group(4) or 0)
    total = days * 1440 + hours * 60 + minutes + seconds / 60
    return -total if negative else total


def _parse_ts(s: str) -> datetime:
    """Parse 'Z'-suffixed or offset ISO timestamp to aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt_ts(s: str) -> str:
    """Truncate ISO timestamp to 'YYYY-MM-DD HH:MM' for display."""
    if not s:
        return ""
    try:
        dt = _parse_ts(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16]
