"""API layer (docs/07 Phase 2): FastAPI surface over the existing pipeline.

No business logic lives here — the API wraps `python -m mre`'s spine, the
ScenarioRunner, and the Explainer, adds the SQLite run/schedule registry,
and serves the versioned schedule JSON contract
(mre.contracts.schedule_document).
"""
