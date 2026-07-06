"""Run-document assembly at end() (L3 consolidation).

Pure aggregation from the JSONL stream:
  - decomposability check on rollup metrics (docs/02 §4.4)
  - tier filter: headline + supporting enter the consolidated document;
    detail remains stream-only (docs/02 §7)
"""
from __future__ import annotations

import math

from mre.reporter.sink import JsonlSink


class DecomposabilityError(Exception):
    """A Metric's rollup_of sum does not match its stated value."""


class Consolidator:
    def __init__(self, run_id: str, sink: JsonlSink) -> None:
        self._run_id = run_id
        self._sink = sink

    def consolidate(self) -> dict:
        all_records = self._sink.read_all()

        run_context_open: dict | None = None
        run_context_close: dict | None = None
        evidence_records: list[dict] = []

        for rec in all_records:
            rt = rec.get("record_type")
            if rt == "run_context_open":
                run_context_open = rec
            elif rt == "run_context_close":
                run_context_close = rec
            else:
                evidence_records.append(rec)

        self._check_decomposability(evidence_records)

        filtered = [r for r in evidence_records if r.get("tier") != "detail"]

        run_context: dict = {}
        if run_context_open:
            run_context.update({k: v for k, v in run_context_open.items() if k != "record_type"})
        if run_context_close:
            run_context.update({k: v for k, v in run_context_close.items() if k != "record_type"})

        return {
            "run_id": self._run_id,
            "run_context": run_context,
            "records": filtered,
        }

    @staticmethod
    def _check_decomposability(records: list[dict]) -> None:
        metric_by_id = {
            r["record_id"]: r
            for r in records
            if r.get("record_type") == "metric"
        }

        for rec in records:
            if rec.get("record_type") != "metric":
                continue
            rollup_of = rec.get("rollup_of")
            if not rollup_of:
                continue

            component_sum = 0.0
            for ref_id in rollup_of:
                if ref_id not in metric_by_id:
                    raise DecomposabilityError(
                        f"Metric '{rec['name']}' (id={rec['record_id']}) references "
                        f"unknown component {ref_id}"
                    )
                component_sum += metric_by_id[ref_id]["value"]

            if not math.isclose(rec["value"], component_sum, rel_tol=1e-9, abs_tol=1e-9):
                raise DecomposabilityError(
                    f"Metric '{rec['name']}' (id={rec['record_id']}) claims "
                    f"{rec['value']} but components sum to {component_sum}"
                )
