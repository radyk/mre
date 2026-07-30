"""M10 — the read-only evidence tool surface (R-AI5(2), Session 4A.5b CU1).

The CLOSED, typed set of evidence-query tools the synthesis model may call, built as
THIN WRAPPERS over the same readers the contracted routes use — one truth, two
consumers. Nothing here re-derives a fact the routes derive differently; nothing here
executes an arbitrary query; and nothing here writes (M10 has no write path, so a
tool that mutates, re-solves or prices is not "out of scope", it is forbidden).

Three properties every tool has, and the verification pass depends on all three:

  * TYPED RESULTS. One shape (``ToolResult``) with planner-readable rows.
  * ROWS CARRY THEIR RECORD IDS. Each row names the evidence record ids / canonical
    entity ids that back it, so a claim can cite them and the verifier can
    INDEPENDENTLY re-fetch them (R-AI5(8) — the label comes from that re-fetch,
    never from the answering model).
  * A STATED BUDGET. ``MAX_TOOL_CALLS`` per question and a wall-clock ceiling above
    it in the loop; exhaustion yields an honest partial answer naming what was
    consulted, never a stall.

The surface itself is enumerated in ``mre.contracts.synthesis`` (``ToolName``,
``TOOL_MEANINGS``, ``TOOL_ARGS``) and rendered into the GOVERNED prompt artifact
``synthesis_prompt.md``; a parity test asserts the enum, the meanings, the argument
lists and the live implementations name the same closed set.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from mre.contracts.synthesis import (
    MAX_ROWS,
    MAX_TOOL_CALLS,
    ToolCallLog,
    ToolName,
    TOOL_ARGS,
    ToolResult,
)

_ISO_KEYS = ("start", "end")

#: Row fields this toolbox DERIVES by arithmetic over the pinned run rather
#: than copying out of a record — a sum over run windows, a span, a difference,
#: an intersection with a calendar. No single evidence record contains them, so
#: the verifier's re-fetch cannot rebuild them and must be told they are ours
#: (see ``_log``). Adding a field here asserts that WE computed it; a field
#: copied verbatim from a record must NOT be listed, or the re-fetch stops
#: being a check.
_DERIVED_ROW_FIGURES = (
    "working_minutes", "elapsed_span_minutes", "paused_minutes", "pieces",
    "gap_before_minutes", "idle_open_minutes_before",
)


def _fmt(ts: str) -> str:
    from mre.modules.explainer import _fmt_ts
    try:
        return _fmt_ts(ts) if ts else ""
    except Exception:  # noqa: BLE001 — a reader must never raise into the loop
        return ts or ""


def _parse(ts: str):
    from mre.modules.explainer import _to_dt
    try:
        return _to_dt(ts)
    except Exception:  # noqa: BLE001
        return None


class EvidenceToolbox:
    """The budgeted, read-only tool surface over ONE pinned run.

    Construct with the SAME ``Explainer`` the contracted routes would use; every
    tool reads through it. ``call()`` is the only model-facing entry point and it is
    budgeted; ``fetch_source()`` is the VERIFIER's independent re-fetch and is
    deliberately NOT budgeted and NOT model-callable — a verification that had to
    ask the loop's permission would not be independent."""

    def __init__(self, explainer: Any, *, max_calls: int = MAX_TOOL_CALLS,
                 max_rows: int = MAX_ROWS) -> None:
        self._ex = explainer
        self.max_calls = max_calls
        self.max_rows = max_rows
        self.calls: list[ToolCallLog] = []
        #: Every record id any tool call surfaced, in order — the CONSULTED set. An
        #: interpretive claim lists these (CU4); an uncited claim is checked against
        #: them, so a fabricated value still fails even with nothing cited.
        self.consulted: list[str] = []
        #: (tool, record ids, tallies) for each call that enumerated its WHOLE set.
        #: A claim quantifying over a set is VERIFIED only if ONE of these covers
        #: its citations AND its figures are that call's own tallies — the
        #: completeness-honesty rule (CU3).
        self.enumerated: list[tuple[str, set, set]] = []
        #: Every COUNT this surface itself computed — each result's row count and
        #: its summary's numeric values. A count in a claim is checked against this
        #: rather than against a record's fields: the tally is the toolbox's own
        #: deterministic arithmetic over the pinned run, never the model's.
        self.count_profile: set[float] = set()
        #: (tool, record ids, tallies, summary) for EVERY successful call. An
        #: aggregate figure — a machine's busy minutes, a window's first start, a
        #: total — lives in the result's SUMMARY, not in any one record; a claim
        #: citing that call's rows is entitled to it, because WE computed it from
        #: the pinned run.
        self.call_tallies: list[tuple[str, set, set, dict]] = []
        self._rows_cache: Optional[list[dict]] = None
        self._decisions_by_op: Optional[dict[str, list[str]]] = None
        self._metrics_by_demand: Optional[dict[str, dict[str, str]]] = None

    # -- budget -------------------------------------------------------------

    @property
    def calls_made(self) -> int:
        return len(self.calls)

    @property
    def exhausted(self) -> bool:
        return self.calls_made >= self.max_calls

    def remaining(self) -> int:
        return max(0, self.max_calls - self.calls_made)

    # -- the one model-facing entry point -----------------------------------

    def call(self, tool: str, args: Optional[dict] = None) -> ToolResult:
        """Run one tool. A name outside the closed set, a missing required
        argument, or any reader failure returns an honest ``ok=False`` result — the
        loop is told what went wrong and may try something else. It never raises."""
        args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
        try:
            name = ToolName(str(tool))
        except ValueError:
            result = ToolResult(tool=ToolName.ENTITY_VOCABULARY, args=args, ok=False,
                                note=f"no such tool {tool!r}; the tool list is closed")
            self._log(str(tool), args, result)
            return result

        missing = [a.name for a in TOOL_ARGS[name] if a.required and not args.get(a.name)]
        if missing:
            result = ToolResult(tool=name, args=args, ok=False,
                                note=f"missing required argument(s): {', '.join(missing)}")
            self._log(name.value, args, result)
            return result

        if self.exhausted:
            result = ToolResult(tool=name, args=args, ok=False,
                                note=f"tool budget exhausted ({self.max_calls} calls)")
            # A refused call is still logged: the transcript must show the wall.
            self._log(name.value, args, result)
            return result

        try:
            result = self._run(name, args)
        except Exception as exc:  # noqa: BLE001 — a reader failure is a result, not a crash
            result = ToolResult(tool=name, args=args, ok=False,
                                note=f"read failed: {type(exc).__name__}")
        self._log(name.value, args, result)
        return result

    def _log(self, tool: str, args: dict, result: ToolResult) -> None:
        self.calls.append(ToolCallLog(tool=tool, args=dict(args), ok=result.ok,
                                      rows=len(result.rows), note=result.note))
        rids = result.record_ids
        for rid in rids:
            if rid and rid not in self.consulted:
                self.consulted.append(rid)
        tallies: set[float] = set()
        if result.ok:
            tallies.add(float(len(result.rows)))
            for v in result.summary.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    tallies.add(float(v))
            # DERIVED ROW FIGURES ARE OUR ARITHMETIC TOO (Session 4B.20).
            # A summary figure is trusted by the verifier because WE computed
            # it over the pinned run and it lives in no single record. Exactly
            # the same is true of a row's working_minutes: it is a sum over the
            # run windows, and no record contains it. Before 4B.20 this did not
            # bite, because the only row duration was ``end - start`` and the
            # verifier could rebuild it from the two timestamps in the records.
            # Reporting working time made the figure UNREBUILDABLE, and a
            # correct claim quoting it was cut for it — measured on the pinned
            # world: "puts 1501 minutes of actual work on the machine", with
            # four real citations, FAILED. Trading a false VERIFIED answer for
            # a true cut one is an improvement and not the goal.
            #
            # Deliberately a NAMED SET, not every number in every row: a row's
            # verbatim fields still have to be found in a record, which is what
            # keeps the re-fetch honest.
            for row in result.rows:
                for k in _DERIVED_ROW_FIGURES:
                    v = row.get(k)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        tallies.add(float(v))
            self.count_profile |= tallies
            self.call_tallies.append((tool, set(rids), tallies,
                                      dict(result.summary)))
        if result.ok and result.enumerates_set and rids:
            self.enumerated.append((tool, set(rids), tallies))

    # -- dispatch -----------------------------------------------------------

    def _run(self, name: ToolName, args: dict) -> ToolResult:
        if name is ToolName.PLACEMENTS_FOR_ORDER:
            return self._placements_for_order(str(args["order"]))
        if name is ToolName.PLACEMENTS_FOR_MACHINE:
            return self._placements_for_machine(str(args["machine"]))
        if name is ToolName.PLACEMENTS_IN_WINDOW:
            return self._placements_in_window(str(args["start"]), str(args["end"]))
        if name is ToolName.MACHINE_OCCUPANCY:
            return self._machine_occupancy(str(args["machine"]),
                                           args.get("start"), args.get("end"))
        if name is ToolName.LATENESS_SET:
            return self._lateness_set()
        if name is ToolName.COST_LEDGER:
            return self._cost_ledger()
        if name is ToolName.GATE_FINDINGS:
            return self._gate_findings()
        if name is ToolName.CALENDARS:
            return self._calendars(args.get("machine"))
        if name is ToolName.CAPABILITY_REGISTRY:
            return self._capability_registry()
        if name is ToolName.ENTITY_VOCABULARY:
            return self._entity_vocabulary()
        if name is ToolName.CONSTRAINT_CATALOG:
            return self._constraint_catalog(args.get("topic"))
        if name is ToolName.SPEC_LOOKUP:
            return self._spec_lookup(str(args.get("query") or ""))
        return self._fetch_record(str(args["id"]))

    # ------------------------------------------------------------------
    # Shared reads (the SAME readers the routes use)
    # ------------------------------------------------------------------

    def _rows(self) -> list[dict]:
        if self._rows_cache is None:
            try:
                self._rows_cache = self._ex._load_enriched_assignments()
            except Exception:  # noqa: BLE001
                self._rows_cache = []
        return self._rows_cache

    def _decision_ids(self, op_id: str) -> list[str]:
        """The assignment Decision record ids whose subject is this operation. Built
        once from the evidence index (the same records ``_assignment_records_for_ops``
        surfaces for the lit-bars channel)."""
        if self._decisions_by_op is None:
            index: dict[str, list[str]] = {}
            for rec in getattr(self._ex._index, "_all_evidence", []) or []:
                if (rec.get("record_type") != "decision"
                        or rec.get("decision_type") != "assignment"):
                    continue
                rid = str(rec.get("record_id") or "")
                if not rid:
                    continue
                for s in rec.get("subjects", []) or []:
                    eid = s.get("entity_id")
                    if eid:
                        index.setdefault(str(eid), []).append(rid)
            self._decisions_by_op = index
        return list(self._decisions_by_op.get(op_id, []))

    def _demand_metrics(self, demand_id: str) -> dict[str, str]:
        """{metric name: record_id} for one demand's Metric records."""
        if self._metrics_by_demand is None:
            index: dict[str, dict[str, str]] = {}
            for rec in getattr(self._ex._index, "_all_evidence", []) or []:
                if rec.get("record_type") != "metric":
                    continue
                rid = str(rec.get("record_id") or "")
                nm = str(rec.get("name") or "")
                if not rid or not nm:
                    continue
                for s in rec.get("subjects", []) or []:
                    eid = s.get("entity_id")
                    if eid:
                        index.setdefault(str(eid), {})[nm] = rid
            self._metrics_by_demand = index
        return dict(self._metrics_by_demand.get(demand_id, {}))

    def _row_sources(self, r: dict) -> list[str]:
        """Every source that carries a value this placement row reports.

        This list is the row's citation, and it is deliberately complete rather
        than minimal: the assignment DECISION carries the driver and the window,
        the assignment ENTITY carries the phase windows, the DEMAND carries the
        order id and the due date, the RESOURCE carries the machine name. A claim
        quoting the machine name must be able to cite something that actually
        contains it — a citation the verifier can re-fetch and NOT find the value
        in is a false failure, and false failures teach the model to stop citing."""
        ids: list[str] = list(self._decision_ids(r.get("operation_ref", "")))
        for extra in ([r.get("assignment_id", "")] + list(r.get("demand_ids") or [])
                      + [r.get("resource_id", "")]):
            if extra and extra not in ids:
                ids.append(extra)
        return ids

    def _placement_row(self, r: dict) -> dict:
        """One placement, with WORKING TIME and ELAPSED SPAN as separate named
        fields (Session 4B.20, the merged-span ruling).

        Until 4B.20 this row carried a single ``duration_minutes`` computed as
        ``end - start``. On a chunked operation that is the elapsed span, not
        the work: ORD-000011 op10 reported 5821 when it runs 1501 working
        minutes across three pieces, and the second tier quoted the 5821 as
        "a single 5821-minute operation" with a real record id behind it. The
        number was in the evidence; the FIELD NAME was the lie.

        The truer figures were already on this very row — ``_load_enriched_
        assignments`` has carried ``run_min``, ``span_min`` and ``chunks``
        since 4B.14 — and this reader threw them away and recomputed the
        subtraction. Nothing new is measured here; the row stops discarding
        what it was handed. ``duration_minutes`` is GONE rather than kept
        beside them, because a field that does not say which quantity it is
        is the defect the ruling names."""
        working, span, pieces = _work_span_pieces(r)
        row = {
            "order": "+".join(sorted(r["work_orders"])) or "?",
            "op_seq": r.get("op_seq"),
            "machine": r.get("machine"),
            "start": _fmt(r.get("start", "")),
            "end": _fmt(r.get("end", "")),
            "working_minutes": working,
            "elapsed_span_minutes": span,
            "pieces": pieces,
            "setup_family": r.get("setup_family") or None,
            "record_ids": self._row_sources(r),
        }
        if pieces > 1 and working is not None and span is not None:
            # Stated only when it EXISTS. A contiguous operation carrying
            # "paused_minutes: 0" invites the reader to treat the field as
            # noise; an absent field on 54 of 56 rows makes the two that have
            # it legible.
            row["paused_minutes"] = round(span - working, 1)
        return row

    # ------------------------------------------------------------------
    # The tools
    # ------------------------------------------------------------------

    def _placements_for_order(self, order: str) -> ToolResult:
        ref = self._ex.resolve_order_value(order) or order
        rows = [self._placement_row(r) for r in self._ex._order_rows(ref)]
        note = "" if rows else f"{order} has no scheduled operations in this run"
        return ToolResult(tool=ToolName.PLACEMENTS_FOR_ORDER, args={"order": order},
                          rows=rows[: self.max_rows], note=note,
                          truncated=len(rows) > self.max_rows,
                          enumerates_set=len(rows) <= self.max_rows,
                          summary={"order": ref, "operations": len(rows)})

    def _placements_for_machine(self, machine: str) -> ToolResult:
        ref = self._ex.resolve_machine_value(machine) or machine
        rows = [r for r in self._rows() if (r.get("machine") or "").upper() == ref.upper()]
        rows.sort(key=lambda r: r.get("start") or "")
        out = [self._placement_row(r) for r in rows]
        note = "" if out else f"nothing is scheduled on {machine} in this run"
        return ToolResult(tool=ToolName.PLACEMENTS_FOR_MACHINE, args={"machine": machine},
                          rows=out[: self.max_rows], note=note,
                          truncated=len(out) > self.max_rows,
                          enumerates_set=len(out) <= self.max_rows,
                          summary={"machine": ref, "operations": len(out)})

    def _placements_in_window(self, start: str, end: str) -> ToolResult:
        s, e = _parse(start), _parse(end)
        if s is None or e is None:
            return ToolResult(tool=ToolName.PLACEMENTS_IN_WINDOW,
                              args={"start": start, "end": end}, ok=False,
                              note="start/end must be ISO-8601 timestamps")
        hits = []
        for r in self._rows():
            rs, re_ = _parse(r.get("start", "")), _parse(r.get("end", ""))
            if rs is None or re_ is None:
                continue
            if re_ > s and rs < e:
                hits.append(r)
        hits.sort(key=lambda r: (r.get("machine") or "", r.get("start") or ""))
        out = [self._placement_row(r) for r in hits]
        return ToolResult(tool=ToolName.PLACEMENTS_IN_WINDOW,
                          args={"start": start, "end": end},
                          rows=out[: self.max_rows],
                          note="" if out else "nothing is scheduled in that window",
                          truncated=len(out) > self.max_rows,
                          enumerates_set=False,      # a window is a FILTER, never the set
                          summary={"operations": len(out)})

    def _machine_occupancy(self, machine: str, start: Any = None,
                           end: Any = None) -> ToolResult:
        ref = self._ex.resolve_machine_value(machine) or machine
        rows = [r for r in self._rows()
                if (r.get("machine") or "").upper() == ref.upper()]
        rows.sort(key=lambda r: r.get("start") or "")
        s = _parse(str(start)) if start else None
        e = _parse(str(end)) if end else None
        open_windows = self._open_windows_for(ref)
        spans: list[dict] = []
        working_total = 0.0
        prev_end = None
        for r in rows:
            rs, re_ = _parse(r.get("start", "")), _parse(r.get("end", ""))
            if rs is None or re_ is None:
                continue
            if s is not None and re_ <= s:
                continue
            if e is not None and rs >= e:
                continue
            gap = idle_before = None
            if prev_end is not None:
                gap = round((rs - prev_end).total_seconds() / 60.0, 1)
                # THE ACTIONABLE HALF OF A GAP. Wall-clock minutes between two
                # operations are mostly nights: on this plant a 960-minute gap
                # can hold zero open capacity. ``idle_open_minutes_before`` is
                # the machine's OPEN time inside that gap — the only part of it
                # anything could have been scheduled into. None when the
                # calendar could not be read; never silently 0.
                idle_before = _open_minutes_between(open_windows, prev_end, rs)
            working, span, pieces = _work_span_pieces(r)
            working_total += working if working is not None else 0.0
            row = {
                "order": "+".join(sorted(r["work_orders"])) or "?",
                "start": _fmt(r.get("start", "")),
                "end": _fmt(r.get("end", "")),
                "working_minutes": working,
                "elapsed_span_minutes": span,
                "pieces": pieces,
                "gap_before_minutes": gap,
                "idle_open_minutes_before": idle_before,
                "record_ids": self._row_sources(r),
            }
            if pieces > 1 and working is not None and span is not None:
                # WHY A GAP FIELD COULD NEVER HAVE SHOWN THIS (4B.20). 4B.17
                # read ``gap_before_minutes: 0.0`` on the ORD-000011 row as
                # denying the pause the operation contains. The gap field was
                # not lying — the pause is INSIDE this row, not before it, so
                # no before-gap could ever surface it. The row was flat where
                # the work is not. ``paused_minutes`` and ``pieces`` are the
                # fields that can say it, and they exist for that reason.
                row["paused_minutes"] = round(span - working, 1)
            spans.append(row)
            prev_end = re_
        note = "" if spans else f"{ref} carries no work in that window"
        first_start = _parse(rows[0].get("start", "")) if spans else None
        last_end = prev_end
        summary = {
            "machine": ref, "spans": len(spans),
            # BOTH TOTALS, BOTH NAMED. ``busy_minutes`` is gone: on a chunked
            # machine it exceeded the machine's entire open capacity in the
            # same interval by 3.9x, and no reader could tell from the name
            # that it was a span sum rather than a work sum.
            "working_minutes": round(working_total, 1),
            "first_start": spans[0]["start"] if spans else None,
            "last_end": spans[-1]["end"] if spans else None}
        if spans and first_start is not None and last_end is not None:
            summary["elapsed_span_minutes"] = round(
                (last_end - first_start).total_seconds() / 60.0, 1)
            # THE DENOMINATOR, SO A UTILISATION IS COMPUTABLE WITHOUT GUESSING.
            # A reasoner asked "how busy is CUT-01" needs open capacity, and
            # inferring it from the span is exactly the 3.9x error.
            oc = _open_minutes_between(open_windows, first_start, last_end)
            if oc is not None:
                summary["open_capacity_minutes"] = oc
                summary["utilization_pct"] = (round(100.0 * working_total / oc, 1)
                                              if oc > 0 else None)
        return ToolResult(
            tool=ToolName.MACHINE_OCCUPANCY,
            args={k: v for k, v in (("machine", machine), ("start", start),
                                    ("end", end)) if v},
            rows=spans[: self.max_rows], note=note,
            truncated=len(spans) > self.max_rows,
            enumerates_set=(s is None and e is None and len(spans) <= self.max_rows),
            summary=summary)

    def _open_windows_for(self, machine: str) -> Optional[list[tuple]]:
        """The machine's closure-subtracted open windows, or None if the
        calendar cannot be read. None is propagated, never defaulted to []:
        an empty window list means "open nowhere", and reporting that as the
        capacity of a machine we simply could not read is the same class of
        lie this session exists to close."""
        try:
            wins = self._ex._open_windows(machine)
        except Exception:  # noqa: BLE001
            return None
        return wins or None

    def _lateness_set(self) -> ToolResult:
        """EVERY order's lateness — the whole set, deliberately unfiltered, so a
        count over it is enumerable from ONE call (the completeness-honesty rule in
        CU3 turns on exactly that).

        NOT-LATE AND NOT-SCHEDULED ARE DIFFERENT STATES (Session 4B.13 Item 3).
        Until 4B.13 this summary read ``on_time_or_early = len(rows) - late_n``,
        which counted an UNPLACED order as a success: on the pinned exam world it
        returned ``{'orders': 40, 'late': 0, 'on_time_or_early': 40}`` on a board
        where 14 of those 40 are beyond-horizon tray rows with no placement at
        all. Synthesis repeated it faithfully and claim verification PASSED it —
        the count really was what the tool said. The falsehood was in the tool's
        own vocabulary, which is why the fix is here and not in the verifier:
        verification is downstream of tool vocabulary, and a tool that fuses two
        categories makes every claim built on it unfalsifiable-but-verified.

        The three states are disjoint and cover the set:
        ``late`` + ``on_time_or_early`` == ``scheduled``, and
        ``scheduled`` + ``not_scheduled`` == ``orders``.
        """
        reader = getattr(self._ex, "_reader", None)
        imap = getattr(self._ex, "_identity_map", None)
        rows: list[dict] = []
        if reader is not None:
            for dem in reader.iter_entities("demand"):
                did = dem.get("id", "")
                order = ""
                for ref in dem.get("external_refs", []) or []:
                    if ref.get("type") in ("order_id", "work_order"):
                        order = ref["value"]
                        break
                if not order and imap is not None:
                    refs = imap.external_refs(did)
                    order = refs[0].value if refs else did[:8]
                late = self._ex._order_lateness(order)
                metrics = self._demand_metrics(did)
                rids = [r for r in (metrics.get("lateness_minutes"),
                                    metrics.get("projected_completion_epoch")) if r]
                if did and did not in rids:
                    rids.append(did)     # the demand carries the order id + due date
                rows.append({
                    "order": order,
                    "lateness_minutes": None if late is None else round(late, 1),
                    "late": bool(late is not None and late > 0),
                    # The row says its own state, so a model reading rows rather
                    # than the summary cannot make the same fusion by hand.
                    "scheduled": late is not None,
                    "service_state": ("not_scheduled" if late is None
                                      else "late" if late > 0 else "on_time_or_early"),
                    "due": dem.get("due"),
                    "record_ids": rids or [did],
                })
        rows.sort(key=lambda r: -(r["lateness_minutes"] or 0.0))
        late_n = sum(1 for r in rows if r["late"])
        unscheduled_n = sum(1 for r in rows if not r["scheduled"])
        scheduled_n = len(rows) - unscheduled_n
        note = "" if rows else "this run records no lateness metrics"
        if unscheduled_n:
            # Said, not merely counted: the completeness rider a claim about
            # "all orders" has to survive. A tray order is never "on time".
            note = (f"{unscheduled_n} of {len(rows)} order(s) have NO placement in "
                    f"this schedule and therefore no service outcome — they are "
                    f"neither late nor on time. Lateness is stated for the "
                    f"{scheduled_n} scheduled order(s) only.")
        return ToolResult(tool=ToolName.LATENESS_SET, rows=rows[: self.max_rows],
                          truncated=len(rows) > self.max_rows,
                          enumerates_set=len(rows) <= self.max_rows,
                          note=note,
                          summary={"orders": len(rows),
                                   "scheduled": scheduled_n,
                                   "late": late_n,
                                   "on_time_or_early": scheduled_n - late_n,
                                   "not_scheduled": unscheduled_n})

    def _cost_ledger(self) -> ToolResult:
        reader = getattr(self._ex, "_reader", None)
        totals: dict[str, Any] = {}
        schedule_id = ""
        if reader is not None:
            for sched in reader.iter_entities("schedule"):
                totals = dict(sched.get("summary_metrics") or {})
                schedule_id = sched.get("id", "")
                break
        rows: list[dict] = []
        if totals:
            # The TOTALS are a citable row of their own. Without this the ledger's
            # headline figures lived only in the result summary, which carries no
            # ids — and the first live run showed exactly what that costs: the model
            # cited the string "cost_ledger" because there was nothing else to cite,
            # and three true claims about the plan's money were cut for it.
            rows.append({"line": "totals", **{
                k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in totals.items()},
                "record_ids": [schedule_id] if schedule_id else []})
        if reader is not None:
            demands = {d.get("id"): d for d in reader.iter_entities("demand")}
            for svc in reader.iter_entities("serviceoutcome"):
                dem = demands.get(svc.get("demand_ref")) or {}
                order = ""
                for ref in dem.get("external_refs", []) or []:
                    if ref.get("type") in ("order_id", "work_order"):
                        order = ref["value"]
                        break
                cost = svc.get("tardiness_cost") or 0.0
                if not cost:
                    continue
                rows.append({
                    "line": "tardiness",
                    "order": order or (svc.get("demand_ref") or "")[:8],
                    "cost": round(float(cost), 2),
                    "projected_completion": svc.get("projected_completion"),
                    "record_ids": [svc.get("id", "")],
                })
        rows.sort(key=lambda r: (r["line"] != "totals", -r.get("cost", 0.0)))
        return ToolResult(tool=ToolName.COST_LEDGER, rows=rows[: self.max_rows],
                          truncated=len(rows) > self.max_rows,
                          enumerates_set=len(rows) <= self.max_rows,
                          note="" if totals else "no cost ledger is recorded for this run",
                          summary={k: (round(v, 2) if isinstance(v, float) else v)
                                   for k, v in totals.items()})

    def _gate_findings(self) -> ToolResult:
        try:
            findings = self._ex._index.all_findings()
        except Exception:  # noqa: BLE001
            findings = []
        rows = []
        for f in findings:
            rows.append({
                "code": f.get("code"),
                "severity": f.get("severity"),
                "disposition": f.get("disposition"),
                "message": (f.get("message") or "")[:240],
                "record_ids": [str(f.get("record_id") or "")],
            })
        return ToolResult(tool=ToolName.GATE_FINDINGS, rows=rows[: self.max_rows],
                          truncated=len(rows) > self.max_rows,
                          enumerates_set=len(rows) <= self.max_rows,
                          note="" if rows else "this submission raised no findings",
                          summary={"findings": len(rows)})

    def _calendars(self, machine: Any = None) -> ToolResult:
        reader = getattr(self._ex, "_reader", None)
        if reader is None:
            return ToolResult(tool=ToolName.CALENDARS, ok=False,
                              note="no snapshot is loaded for this run")
        want = None
        if machine:
            want = (self._ex.resolve_machine_value(str(machine)) or str(machine)).upper()
        by_cal: dict[str, list[str]] = {}
        for res in reader.iter_entities("resource"):
            name = ""
            for ref in res.get("external_refs", []) or []:
                name = ref.get("value", "")
                break
            cal = res.get("calendar_ref")
            if cal:
                by_cal.setdefault(cal, []).append(name)
        rows = []
        for cal in reader.iter_entities("calendar"):
            users = by_cal.get(cal.get("id", ""), [])
            if want and not any(u.upper() == want for u in users):
                continue
            base = cal.get("base_pattern") or {}
            rows.append({
                "calendar": next((r.get("value") for r in cal.get("external_refs", [])
                                  or []), cal.get("id", "")[:8]),
                "machines": sorted(users),
                "weekdays": base.get("weekdays"),
                "shift_start": base.get("shift_start"),
                "shift_end": base.get("shift_end"),
                "exceptions": cal.get("exceptions") or [],
                "record_ids": [cal.get("id", "")],
            })
        return ToolResult(tool=ToolName.CALENDARS,
                          args={"machine": machine} if machine else {},
                          rows=rows[: self.max_rows],
                          truncated=len(rows) > self.max_rows,
                          enumerates_set=(not want and len(rows) <= self.max_rows),
                          note="" if rows else "no calendar is declared for that machine",
                          summary={"calendars": len(rows)})

    def _capability_registry(self) -> ToolResult:
        from mre.modules.capabilities import CAPABILITIES
        rows = [{"concept": c.concept, "enables": c.enables, "how": c.how,
                 "spec": c.ids_ref, "record_ids": []} for c in CAPABILITIES]
        return ToolResult(tool=ToolName.CAPABILITY_REGISTRY, rows=rows,
                          enumerates_set=True,
                          summary={"capabilities": len(rows)})

    def _constraint_catalog(self, topic: Any = None) -> ToolResult:
        """docs/05's catalog AS RECORDS (Session 4B.15 Item 5).

        The registry above answers "how do I turn X on" and carries no verdict
        and no proof status, so it cannot say "not today". This does: each row
        is the catalog's own verdict, proof status verbatim, and doorway, plus
        the rulings and exclusions that govern it.

        ``record_ids`` is deliberately EMPTY — the same shape
        ``capability_registry`` uses. A catalog row is not an evidence record
        about this run, so a claim resting on it lands INTERPRETIVE rather than
        VERIFIED, which is the honest label: the claim is about the PRODUCT, not
        about this schedule, and the verifier has nothing in the evidence store
        to re-fetch. What stops the claim being invented is that the row is
        quoted; what stops it being overstated is that the verdict and status
        travel with it."""
        from mre.modules.constraint_catalog import ground, load_catalog
        cat = load_catalog()
        if not cat.items:
            return ToolResult(tool=ToolName.CONSTRAINT_CATALOG,
                              args={"topic": topic} if topic else {}, ok=False,
                              note="the constraint catalog is not available in "
                                   "this build")
        g = ground(str(topic)) if topic else None
        items = list(g.items) if g else list(cat.items)
        rows = [{"id": i.item_id, "item": i.name,
                 "verdict": i.verdict.value, "proof_status": i.status_raw,
                 "means": i.register.value,
                 "declarable_today": i.declarable,
                 "submission_doorway": i.doorway,
                 "record_ids": []} for i in items]
        if g:
            for r in g.rulings:
                rows.append({"id": r.ruling_id, "item": f"RULING: {r.title}",
                             "verdict": "locked ruling", "proof_status": "",
                             "means": "", "declarable_today": False,
                             "submission_doorway": r.text[:400],
                             "record_ids": []})
            for e in g.exclusions:
                rows.append({"id": "EXCLUSION", "item": e.name,
                             "verdict": "out", "proof_status": "",
                             "means": "excluded", "declarable_today": False,
                             "submission_doorway": e.text[:400],
                             "record_ids": []})
        note = ("" if rows else
                "the catalog names nothing matching that topic — say so rather "
                "than reasoning out a capability answer")
        return ToolResult(
            tool=ToolName.CONSTRAINT_CATALOG,
            args={"topic": topic} if topic else {},
            rows=rows[: self.max_rows], note=note,
            truncated=len(rows) > self.max_rows,
            # The WHOLE catalog is enumerable; a topic query is a FILTER.
            enumerates_set=(not topic and len(rows) <= self.max_rows),
            summary={"items": len(rows),
                     "topic": g.topic.key if g else "all"})

    def _spec_lookup(self, query: str) -> ToolResult:
        """Prose from the CURRENT specification tier (docs/01, 05, 06).

        The tier boundary is enforced in ``corpus.TIERS_FOR_PURPOSE``, not here
        and not in the prompt: ``Purpose.CAPABILITY`` admits the current specs
        and nothing else, so the roadmap (what we INTEND to build) and the
        design history (which carries superseded rulings as first-class text)
        are unreachable from this tool by construction."""
        from mre.modules.corpus import Purpose, load_corpus, load_error
        corp = load_corpus()
        if corp is None:
            return ToolResult(tool=ToolName.SPEC_LOOKUP, args={"query": query},
                              ok=False,
                              note=f"the specification corpus is not available "
                                   f"in this build ({load_error()})")
        hits = corp.retrieve(query, Purpose.CAPABILITY, limit=4)
        rows = [{"source": p.citation, "text": p.text[:1400], "record_ids": []}
                for p in hits]
        return ToolResult(
            tool=ToolName.SPEC_LOOKUP, args={"query": query}, rows=rows,
            note="" if rows else "the specifications say nothing about that",
            enumerates_set=False,          # a search is never a set
            summary={"passages": len(rows)})

    def _entity_vocabulary(self) -> ToolResult:
        orders = sorted((self._ex._order_refs or {}).values())
        machines = sorted((self._ex._machine_refs or {}).values())
        customers: list[str] = []
        reader = getattr(self._ex, "_reader", None)
        if reader is not None:
            for dem in reader.iter_entities("demand"):
                for ref in dem.get("external_refs", []) or []:
                    if ref.get("type") == "customer" and ref["value"] not in customers:
                        customers.append(ref["value"])
        rows = [{"kind": "order", "names": orders, "record_ids": []},
                {"kind": "machine", "names": machines, "record_ids": []},
                {"kind": "customer", "names": sorted(customers), "record_ids": []}]
        return ToolResult(tool=ToolName.ENTITY_VOCABULARY, rows=rows,
                          enumerates_set=True,
                          summary={"orders": len(orders), "machines": len(machines),
                                   "customers": len(customers)})

    def _fetch_record(self, ident: str) -> ToolResult:
        src = self.fetch_source(ident)
        if src is None:
            return ToolResult(tool=ToolName.FETCH_RECORD, args={"id": ident}, ok=False,
                              note=f"no record or entity with id {ident!r} exists in "
                                   "this run")
        kind, payload = src
        return ToolResult(tool=ToolName.FETCH_RECORD, args={"id": ident},
                          rows=[{"kind": kind, "id": ident,
                                 "payload": _shrink(payload), "record_ids": [ident]}],
                          enumerates_set=True,
                          summary={"kind": kind})

    # ------------------------------------------------------------------
    # The verifier's independent re-fetch (NOT a tool, NOT budgeted)
    # ------------------------------------------------------------------

    def fetch_source(self, ident: str) -> Optional[tuple[str, dict]]:
        """``(kind, payload)`` for an evidence record id or a canonical entity id, or
        None when nothing in this run carries that id.

        This is the verification pass's own reader (R-AI5(8)): it re-assembles the
        cited evidence from the index and the snapshot, independently of whatever the
        loop's tool calls happened to return. A ``None`` here is the fabricated-id
        finding — the ordinal disease's cure."""
        ident = (ident or "").strip()
        if not ident:
            return None
        for rec in getattr(self._ex._index, "_all_evidence", []) or []:
            if str(rec.get("record_id") or "") == ident:
                return "record", rec
        reader = getattr(self._ex, "_reader", None)
        if reader is not None:
            try:
                ent = reader.get_entity(ident)
            except Exception:  # noqa: BLE001
                ent = None
            if ent:
                return "entity", ent
        return None

    def labels_for(self, payload: dict) -> set[str]:
        """Every external name (order / machine / product id) reachable from a
        fetched record or entity — its own external_refs and those of every entity it
        names as a subject or a ref. This is how an ENTITY assertion ("ORD-05") is
        checked against a record whose fields are canonical uuids."""
        imap = getattr(self._ex, "_identity_map", None)
        out: set[str] = set()
        ids = set(_collect_ids(payload))
        for eid in ids:
            if imap is not None:
                try:
                    for ref in imap.external_refs(eid):
                        out.add(str(ref.value).upper())
                except Exception:  # noqa: BLE001
                    pass
        for ref in payload.get("external_refs", []) or []:
            if isinstance(ref, dict) and ref.get("value"):
                out.add(str(ref["value"]).upper())
        return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _open_minutes_between(windows: Optional[list[tuple]], lo, hi) -> Optional[float]:
    """OPEN minutes of a machine's calendar inside [lo, hi]. None when the
    calendar was unreadable — the caller must be able to tell "no open time"
    from "no calendar"."""
    if windows is None or lo is None or hi is None:
        return None if windows is None else 0.0
    # Both sides come from ``_to_dt``, which drops the zone, but the calendar
    # reader and the placement reader are different call paths — normalising
    # here means a future aware/naive mismatch degrades to a wrong-by-offset
    # figure instead of a TypeError swallowed as "read failed".
    lo, hi = _naive(lo), _naive(hi)
    if hi <= lo:
        return 0.0
    total = 0.0
    for ws, we in windows:
        a, b = max(_naive(ws), lo), min(_naive(we), hi)
        if b > a:
            total += (b - a).total_seconds() / 60.0
    return round(total, 1)


def _naive(dt):
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _work_span_pieces(r: dict) -> tuple[Optional[float], Optional[float], int]:
    """WORKING TIME, ELAPSED SPAN and PIECE COUNT for one enriched row.

    Working time is the sum of the run windows and NOTHING ELSE (the ruling).
    It is read from ``run_min``/``chunks``, which the row already carries; the
    span subtraction is only ever the span. When a row predates 4B.14 and has
    neither, working time is reported as None rather than silently backfilled
    from the span — an unknown quantity is not the other quantity."""
    s, e = _parse(r.get("start", "")), _parse(r.get("end", ""))
    span = round((e - s).total_seconds() / 60.0, 1) if (s and e) else None
    chunks = r.get("chunks") or []
    pieces = len(chunks)
    if r.get("run_min") is not None:
        working = round(float(r["run_min"]), 1)
    elif chunks:
        working = round(sum(float(c.get("working_min") or 0.0) for c in chunks), 1)
    else:
        working = None
    return working, span, pieces


def _collect_ids(payload: Any, depth: int = 0) -> list[str]:
    """Every uuid-shaped string reachable in a record/entity payload."""
    out: list[str] = []
    if depth > 6:
        return out
    if isinstance(payload, str):
        if len(payload) >= 32 and payload.count("-") >= 4:
            out.append(payload)
    elif isinstance(payload, dict):
        for v in payload.values():
            out.extend(_collect_ids(v, depth + 1))
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            out.extend(_collect_ids(v, depth + 1))
    return out


def _shrink(payload: dict, limit: int = 2000) -> dict:
    """A fetched payload, bounded — a record dump must not eat the loop's context."""
    import json
    try:
        text = json.dumps(payload, default=str)
    except Exception:  # noqa: BLE001
        return {"note": "record could not be serialized"}
    if len(text) <= limit:
        return payload
    return {"truncated": True, "excerpt": text[:limit]}


class Stopwatch:
    """The synthesis loop's wall-clock ceiling, stated in the contract and checked
    between steps. Kept here so the budget lives in one place."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._t0 = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    @property
    def expired(self) -> bool:
        return (time.perf_counter() - self._t0) >= self.seconds
