"""L2 + L3 — Reporter, JSONL sink, and consolidator.

Primary export: Reporter (eight verbs, ambient capture, context manager).
Also exports: JsonlSink, Consolidator, DecomposabilityError.
"""
from mre.reporter.reporter import Reporter
from mre.reporter.sink import JsonlSink
from mre.reporter.consolidate import Consolidator, DecomposabilityError

__all__ = ["Reporter", "JsonlSink", "Consolidator", "DecomposabilityError"]
