"""FastAPI surface over the existing pipeline (docs/07 Phase 2, session 2.1).

Thin by design: endpoints validate, mint run-scoped directories via the
Registry, invoke the EXISTING machinery (``mre.__main__.main``, the M0 gate,
ScenarioRunner, Explainer), and serve the versioned schedule JSON contract.
No scheduling/business logic lives in this module.

All responses are versioned envelopes: ``{"api_version": "1", "data": ...}``
or ``{"api_version": "1", "error": {"code": ..., "message": ...}}``.

Guardrails:
- REJECTED submissions never reach the pipeline (409 on solve).
- What-if scenario schedules never appear in the default GET /schedules
  listing (evidence isolation extended to the API).
- ask/whatif validate the schedule exists and is not superseded.
- ``deterministic: true`` pins ``--solver-workers 1 --solver-seed 0``.
  (A full identical-schedule claim additionally needs PYTHONHASHSEED=0 in
  the server environment — see the 2026-07-09 amendment.)

Run it: ``uvicorn mre.api.app:create_app --factory`` with MRE_DATA_ROOT set,
or embed ``create_app(data_root=...)``.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from mre.api.registry import Registry
from mre.modules import longpath

API_VERSION = "1"

# On-demand forced-alternative pricing (session 3.3 CU1) guards the solve bill
# — a burst of grabs must not fan out into an unbounded fleet of re-solves. A
# process-wide semaphore caps CONCURRENT on-demand pricings; a dedup set drops a
# second grab of an op already being priced. Both are design tokens.
MAX_CONCURRENT_ONDEMAND = 2
ONDEMAND_TIME_LIMIT_S = 6.0
_ONDEMAND_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_ONDEMAND)
_ONDEMAND_INFLIGHT: set[tuple[str, str]] = set()
_ONDEMAND_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SolveRequest(BaseModel):
    policy: str = "identity_v1"
    horizon_days: Optional[int] = None
    time_limit: float = 30.0
    deterministic: bool = False
    sync: bool = False              # small runs may opt into the sync path
    # Warm the solution pool right after the solve (same background task,
    # so it runs strictly after the schedule is registered). Opt-in until
    # the publish workflow (Phase 3) makes warming-on-publish the default.
    pool: bool = False
    # SLICED (rolling-horizon) solve (Session 4B.3a CU1, R-SC2): instead of a
    # monolithic solve, render the plant AS OF the reference origin — the current
    # window (committed frozen front + active window) plus a beyond-horizon tray.
    # Registers a contract-1.7 rolling document like any other run.
    sliced: bool = False
    window_days: int = 7            # the rolling window length (the knee is ~7d)
    frozen_days: int = 2            # the frozen-front length (<= window_days)


class PoolRequest(BaseModel):
    k: int = 5
    tolerance_pct: float = 10.0
    member_time_limit: float = 10.0
    seed: int = 1234
    sync: bool = False


class AlternativesRequest(BaseModel):
    """Forced-alternative build (R-T1a): the priced roads not taken. When
    ``target_op_ids`` is omitted the selection heuristic v1 picks the at-risk
    demands' multi-eligible ops (docs/04 R-T1b)."""
    target_op_ids: Optional[list[str]] = None
    budget: int = 4
    member_time_limit: float = 10.0
    seed: int = 1234
    sync: bool = False


class OpAlternativesRequest(BaseModel):
    """On-demand pricing for ONE grabbed op (session 3.3 CU1, R-T1a K'): price
    every eligible machine for it, right now. Fired when a planner grabs an op
    the precomputed batch missed. ``max_machines`` + ``member_time_limit`` cap
    the solve bill (the API also enforces a concurrency cap across grabs)."""
    max_machines: int = 4
    member_time_limit: Optional[float] = None   # defaults to ONDEMAND_TIME_LIMIT_S
    seed: int = 1234
    sync: bool = False


class SandboxRequest(BaseModel):
    """Tier-2 sandbox re-solve for a dropped bar (R-DP1/R-T1c). Pin one op at
    (machine + time exactly as displayed) and re-solve its surroundings under a
    hard, visible budget. Omitting the pin fields pins the first incumbent op at
    its own placement — the latency-floor case the CI regression uses."""
    pin_op_id: Optional[str] = None
    pin_resource_id: Optional[str] = None
    pin_start_iso: Optional[str] = None
    budget_s: Optional[float] = None    # override the SANDBOX_BUDGET_S token
    deterministic: bool = True


class AcceptRequest(BaseModel):
    """Accept a dropped bar's Tier-2 verdict (docs/07 Phase 3 CU1, R-DP7). Pin
    the op at (machine + time as displayed), re-solve, and MINT A NEW proposed
    schedule version — the base is never mutated. Records one ``planner_edit``
    Decision (authority MANDATORY: a dev identity token now, real auth
    post-pilot)."""
    pin_op_id: str
    pin_resource_id: str
    pin_start_iso: str
    authority: str = "dev-planner"      # who accepted (identity token)
    budget_s: Optional[float] = None    # override the SANDBOX_BUDGET_S token


class AskRequest(BaseModel):
    question: str
    llm: bool = False               # honored only if ANTHROPIC_API_KEY is set
    # Conversational context (Session 4A.1 CU2): recent turns + the current board
    # selection, so an elliptical follow-up resolves before routing. The server is
    # stateless — the client carries the short history. Each history turn is
    # {question, resolved_question, route, order, machine}; selection is
    # {order, machine}. Omitted → a fresh, self-contained question.
    history: list[dict[str, Any]] = []
    selection: dict[str, Any] = {}
    session_id: Optional[str] = None    # links a refusal to its later rephrase


class WhatIfRequest(BaseModel):
    modifications: list[dict[str, Any]]
    time_limit: Optional[float] = None
    sync: bool = False


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def _ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse({"api_version": API_VERSION, "data": data},
                        status_code=status_code)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(data_root: Path | str | None = None) -> FastAPI:
    if data_root is None:
        data_root = os.environ.get("MRE_DATA_ROOT", "mre_api_data")
    registry = Registry(data_root)

    # Boot-time path-budget tripwire (4.0d fix 3): a path-length problem must never
    # again be discovered only at accept time. If the worst-case snapshot path could
    # exceed the classic limit AND the long-path seam is somehow not mitigating it,
    # warn LOUDLY at startup; otherwise record the numbers so /health can surface
    # them. In normal operation the seam always mitigates on Windows, so this is a
    # standing guard, not an expected warning.
    _budget = longpath.path_budget(registry.data_root)
    _log = logging.getLogger("mre.api")
    if _budget["status"] == "at_risk":
        _log.warning(
            "PATH BUDGET AT RISK: worst-case snapshot path is %d chars under data "
            "root %r, over the classic Windows limit of %d. The run store's "
            "long-path seam is mitigating this (active=%s) so accepts still work, "
            "but the data root is dangerously deep — shorten it to remove the "
            "dependency and never risk a FileNotFoundError at accept time.",
            _budget["worst_case_path_len"], str(registry.data_root),
            _budget["classic_max_path"], _budget["long_path_mitigation"],
        )
    else:
        _log.info("path budget ok: worst-case %d chars, mitigation=%s",
                  _budget["worst_case_path_len"], _budget["long_path_mitigation"])

    app = FastAPI(title="Manufacturing Reasoning Engine API", version=API_VERSION)
    app.state.registry = registry

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            {"api_version": API_VERSION,
             "error": {"code": exc.status_code, "message": str(exc.detail)}},
            status_code=exc.status_code,
        )

    # ------------------------------------------------------------------
    # Liveness / readiness (container healthcheck, docs/07 W4 CU1)
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        """Cheap readiness probe for the container HEALTHCHECK and any
        reverse proxy / platform liveness check. Confirms the process is up
        and its data root is present and writable (the run registry, snapshot
        and evidence stores all live under it) without touching the solver."""
        root = Path(registry.data_root)
        writable = False
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".health_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            writable = True
        except OSError:
            writable = False
        if not writable:
            return JSONResponse(
                {"api_version": API_VERSION,
                 "error": {"code": 503, "message": "data root not writable"}},
                status_code=503,
            )
        # Surface the path-length budget (4.0d) so a thin margin is visible on a
        # liveness probe, never a surprise at accept time.
        return _ok({"status": "ok", "api_version": API_VERSION,
                    "data_root_writable": True,
                    "path_budget": longpath.path_budget(registry.data_root)})

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    @app.post("/submissions")
    async def create_submission(request: Request):
        """Intake an IDS submission (multipart files or {"path": dir}), run
        the M0 conformance gate, and return the certificate verdict.
        REJECTED submissions get their deficiency list and never solve."""
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/"):
            form = await request.form()
            uploads = [v for v in form.multi_items() if hasattr(v[1], "filename")]
            if not uploads:
                raise HTTPException(400, "multipart request contains no files")
            sub = registry.create_submission(source="multipart")
            for _, up in uploads:
                name = Path(up.filename or "unnamed").name
                (sub["files_dir"] / name).write_bytes(await up.read())
        else:
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(400, "expected multipart files or JSON {'path': ...}")
            src = Path(str(body.get("path", "")))
            if not src.is_dir():
                raise HTTPException(400, f"submission path is not a directory: {src}")
            sub = registry.create_submission(source=str(src))
            shutil.copytree(src, sub["files_dir"], dirs_exist_ok=True)

        cert = _run_gate(registry, sub["id"], sub["dir"], sub["files_dir"])
        return _ok({
            "submission_id": sub["id"],
            "grade": cert["grade"],
            "costing_grade": cert.get("costing_completeness_grade"),
            "deficiencies": cert.get("deficiencies", []),
            "certificate_ref": f"/submissions/{sub['id']}/certificate",
        })

    @app.get("/submissions/{submission_id}/certificate")
    def get_certificate(submission_id: str):
        cert_row = registry.get_certificate(submission_id)
        if cert_row is None:
            raise HTTPException(404, f"no certificate for submission {submission_id}")
        certificate = json.loads(Path(cert_row["json_path"]).read_text(encoding="utf-8"))
        return _ok({
            "submission_id": submission_id,
            "certificate": certificate,
            "markdown_ref": cert_row["md_path"],
        })

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------

    @app.post("/submissions/{submission_id}/solve", status_code=202)
    def solve(submission_id: str, req: SolveRequest, background: BackgroundTasks):
        sub = registry.get_submission(submission_id)
        if sub is None:
            raise HTTPException(404, f"unknown submission {submission_id}")
        cert = registry.get_certificate(submission_id)
        if cert is None:
            raise HTTPException(409, "submission has no certificate — gate did not run")
        if cert["grade"] == "REJECTED":
            raise HTTPException(
                409, "submission was REJECTED by the conformance gate; "
                     "fix the deficiencies and resubmit — nothing is solved")
        run = registry.create_run(
            kind="solve", submission_id=submission_id,
            params=req.model_dump(),
        )
        files_dir = Path(sub["dir"]) / "files"
        worker = _execute_rolling_solve if req.sliced else _execute_solve
        if req.sync:
            worker(registry, run, files_dir, req, submission_id)
        else:
            background.add_task(worker, registry, run, files_dir, req,
                                submission_id)
        return _ok({"run_id": run["id"], "status": registry.get_run(run["id"])["status"]},
                   status_code=202)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        run = registry.get_run(run_id)
        if run is None:
            raise HTTPException(404, f"unknown run {run_id}")
        return _ok(run)

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    @app.get("/schedules")
    def list_schedules(include_scenarios: bool = False):
        rows = registry.list_schedules(include_scenarios=include_scenarios)
        return _ok({"schedules": rows})

    @app.get("/schedules/{schedule_id}")
    def get_schedule(schedule_id: str):
        row = registry.get_schedule(schedule_id)
        if row is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        document = json.loads(Path(row["document_path"]).read_text(encoding="utf-8"))
        return _ok(document)

    @app.get("/schedules/{schedule_id}/meta")
    def get_schedule_meta(schedule_id: str):
        """Registry-level metadata for a schedule joined to its certificate
        grade — the cockpit top strip's version + grade, kept out of the
        derived-not-invented schedule document (the grade is a submission
        property)."""
        meta = registry.get_schedule_meta(schedule_id)
        if meta is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        # A superseded version carries a pointer to the live successor so the
        # cockpit can offer "view current" on a deep link (session 3.8 CU3),
        # never a raw error and never an editable zombie.
        if meta.get("status") == "superseded":
            meta["successor_id"] = registry.live_successor(schedule_id)
        return _ok(meta)

    @app.get("/schedules/{schedule_id}/interaction")
    def get_schedule_interaction(schedule_id: str):
        """The Tier-0 legality-arithmetic payload (contract 1.3, docs/04 R-T1d),
        served SEPARATELY from the main render document so the +35.7% payload
        never sits inside first-paint. The cockpit fetches this in the
        background after first paint; the board renders read-only immediately
        and enables drag affordances when this arrives (interim-B). Pool
        members and pre-1.3 schedules carry no payload (404 — degrade to
        Tier-0-green-only, R-T1b/R-DP6)."""
        row = registry.get_schedule(schedule_id)
        if row is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        ipath = Path(row["document_path"]).parent / "interaction.json"
        if not ipath.exists():
            raise HTTPException(
                404, f"schedule {schedule_id} has no interaction payload "
                     "(pool member or pre-1.3 document)")
        return _ok(json.loads(ipath.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------
    # Solution pool (docs/07 Phase 2)
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/pool", status_code=202)
    def warm_pool(schedule_id: str, req: PoolRequest, background: BackgroundTasks):
        row = _live_schedule(registry, schedule_id)
        if row["is_scenario"]:
            raise HTTPException(409, "pools are built for base schedules; "
                                     "a what-if scenario has no pool")
        import uuid as _uuid
        pool_id = f"pool-{_uuid.uuid4().hex[:12]}"
        registry.create_pool(pool_id, schedule_id, params=req.model_dump())
        if req.sync:
            _execute_pool(registry, pool_id, row, req.model_dump())
        else:
            background.add_task(_execute_pool, registry, pool_id, row,
                                req.model_dump())
        return _ok({"pool_id": pool_id, "status": "warming"}, status_code=202)

    @app.get("/schedules/{schedule_id}/pool")
    def get_pool(schedule_id: str):
        if registry.get_schedule(schedule_id) is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        pool = registry.get_pool_for_schedule(schedule_id)
        if pool is None:
            raise HTTPException(404, f"schedule {schedule_id} has no pool — "
                                     "POST /schedules/{id}/pool to warm one")
        return _ok(pool)

    @app.get("/schedules/{schedule_id}/pool/{member_index}")
    def get_pool_member(schedule_id: str, member_index: int):
        pool = registry.get_pool_for_schedule(schedule_id)
        if pool is None:
            raise HTTPException(404, f"schedule {schedule_id} has no pool")
        member = next((m for m in pool["members"]
                       if m["member_index"] == member_index), None)
        if member is None:
            raise HTTPException(404, f"pool {pool['id']} has no member "
                                     f"{member_index}")
        document = json.loads(
            Path(member["document_path"]).read_text(encoding="utf-8"))
        return _ok(document)

    # ------------------------------------------------------------------
    # Forced alternatives (docs/07 Phase 3, R-T1a) — the priced roads not
    # taken. Surfaced through the pool endpoint family (additive), stored in
    # the same pool tables (structural isolation + supersede invalidation),
    # distinguishable by the members' ``source`` label.
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/alternatives", status_code=202)
    def build_alternatives(schedule_id: str, req: AlternativesRequest,
                           background: BackgroundTasks):
        row = _live_schedule(registry, schedule_id)
        if row["is_scenario"]:
            raise HTTPException(409, "forced alternatives are built for base "
                                     "schedules; a what-if scenario has none")
        import uuid as _uuid
        pool_id = f"alt-{_uuid.uuid4().hex[:12]}"
        registry.create_pool(pool_id, schedule_id, params=req.model_dump(),
                             kind="alternatives")
        if req.sync:
            _execute_forced_alternatives(registry, pool_id, row, req.model_dump())
        else:
            background.add_task(_execute_forced_alternatives, registry, pool_id,
                                row, req.model_dump())
        return _ok({"pool_id": pool_id, "status": "building"}, status_code=202)

    @app.get("/schedules/{schedule_id}/alternatives")
    def get_alternatives(schedule_id: str):
        if registry.get_schedule(schedule_id) is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        pool = registry.get_pool_for_schedule(schedule_id, kind="alternatives")
        if pool is None:
            raise HTTPException(
                404, f"schedule {schedule_id} has no forced alternatives — "
                     "POST /schedules/{id}/alternatives to build them")
        return _ok(pool)

    @app.get("/schedules/{schedule_id}/alternatives/{member_index}")
    def get_alternative_member(schedule_id: str, member_index: int):
        pool = registry.get_pool_for_schedule(schedule_id, kind="alternatives")
        if pool is None:
            raise HTTPException(404, f"schedule {schedule_id} has no alternatives")
        member = next((m for m in pool["members"]
                       if m["member_index"] == member_index), None)
        if member is None:
            raise HTTPException(404, f"no alternative member {member_index}")
        if not member.get("document_path"):
            # infeasible verdict — first-class, but no placement document
            raise HTTPException(
                409, f"alternative {member_index} is a "
                     f"'{member.get('verdict')}' verdict — no placement document")
        document = json.loads(
            Path(member["document_path"]).read_text(encoding="utf-8"))
        return _ok(document)

    @app.post("/schedules/{schedule_id}/alternatives/op/{op_id}", status_code=202)
    def price_op_alternatives(schedule_id: str, op_id: str,
                              req: OpAlternativesRequest,
                              background: BackgroundTasks):
        """ON-DEMAND (session 3.3 CU1, R-T1a K'): price every eligible machine
        for ONE grabbed op the precomputed batch missed. Results persist to the
        SAME alternatives pool (appended, not replaced), so the next grab of the
        same op is instant. Idempotent under a burst of grabs: a repeat while
        pricing is in flight returns 'pricing' without re-firing the solves."""
        row = _live_schedule(registry, schedule_id)
        if row["is_scenario"]:
            raise HTTPException(409, "forced alternatives are built for base "
                                     "schedules; a what-if scenario has none")
        # ensure an alternatives pool exists to append into
        pool = registry.get_pool_for_schedule(schedule_id, kind="alternatives")
        if pool is None:
            import uuid as _uuid
            pool_id = f"alt-{_uuid.uuid4().hex[:12]}"
            registry.create_pool(pool_id, schedule_id,
                                 params={"selection": "on_demand"},
                                 kind="alternatives")
            registry.finish_pool(pool_id, "ready", summary={}, members=[])
        else:
            pool_id = pool["id"]
        key = (schedule_id, op_id)
        with _ONDEMAND_LOCK:
            if key in _ONDEMAND_INFLIGHT:
                return _ok({"op_id": op_id, "pool_id": pool_id,
                            "status": "pricing"}, status_code=202)
            _ONDEMAND_INFLIGHT.add(key)
        args = (registry, pool_id, row, op_id, req.model_dump())
        if req.sync:
            _execute_op_alternatives(*args)
        else:
            background.add_task(_execute_op_alternatives, *args)
        return _ok({"op_id": op_id, "pool_id": pool_id, "status": "pricing"},
                   status_code=202)

    # ------------------------------------------------------------------
    # Sandbox (Tier-2 pinned re-solve, docs/07 Phase 3, R-DP1/R-T1c) — the
    # authority behind a dropped bar. Pin one op (machine + time as displayed)
    # and re-solve its surroundings under a hard, visible budget; return the
    # classified outcome + the moved-set (R-DP7 traces). Synchronous: the call
    # holds for at most the budget (the cockpit shows a countdown and never
    # blocks its own board during the wait).
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/sandbox")
    def sandbox(schedule_id: str, req: SandboxRequest):
        from mre.modules.sandbox import SANDBOX_BUDGET_S, sandbox_pin_resolve
        row = _live_schedule(registry, schedule_id)
        if row["is_scenario"]:
            raise HTTPException(409, "sandbox re-solves run against a base "
                                     "schedule; a what-if scenario is itself one")
        run = registry.get_run(row["run_id"])
        result = sandbox_pin_resolve(
            out_dir=Path(run["out_dir"]), snapshot_id=row["snapshot_id"],
            pin_op_id=req.pin_op_id, pin_resource_id=req.pin_resource_id,
            pin_start_iso=req.pin_start_iso,
            budget_s=req.budget_s if req.budget_s is not None else SANDBOX_BUDGET_S,
            deterministic=req.deterministic,
            # R-DP8: hold the lineage's accepted commitments during the re-solve.
            standing_pins=registry.schedule_pins(schedule_id),
        )
        return _ok(result.summary())

    # ------------------------------------------------------------------
    # Accept + publish (docs/07 Phase 3 CU1, R-DP7) — the edit becomes real.
    # Accept mints a NEW proposed version (the base is never mutated) and records
    # a planner_edit Decision. Publish is a second, explicit act: proposed →
    # published, superseding the prior version and invalidating its pools.
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/accept", status_code=201)
    def accept_edit(schedule_id: str, req: AcceptRequest):
        from mre.modules.sandbox import SANDBOX_BUDGET_S
        base = _live_schedule(registry, schedule_id)
        if base["is_scenario"]:
            raise HTTPException(409, "cannot accept an edit onto a what-if "
                                     "scenario; edit its base schedule")
        new_schedule_id, decision = _execute_accept(
            registry, base, req,
            budget_s=req.budget_s if req.budget_s is not None else SANDBOX_BUDGET_S,
        )
        return _ok({
            "schedule_id": new_schedule_id,
            "parent_schedule_id": schedule_id,
            "status": "proposed",
            "decision": decision,
        }, status_code=201)

    @app.post("/schedules/{schedule_id}/publish")
    def publish_schedule(schedule_id: str):
        row = registry.get_schedule(schedule_id)
        if row is None:
            raise HTTPException(404, f"unknown schedule {schedule_id}")
        if row["status"] == "published":
            raise HTTPException(409, f"schedule {schedule_id} is already published")
        if row["status"] == "superseded":
            raise HTTPException(409, f"schedule {schedule_id} is superseded — "
                                     "cannot publish a stale version")
        if row["is_scenario"]:
            raise HTTPException(409, "a what-if scenario is not publishable")
        superseded = registry.publish_schedule(schedule_id)
        return _ok({"schedule_id": schedule_id, "status": "published",
                    "superseded": superseded})

    # ------------------------------------------------------------------
    # Ask (M10 explainer)
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/ask")
    def ask(schedule_id: str, req: AskRequest):
        row = _live_schedule(registry, schedule_id)
        run = registry.get_run(row["run_id"])
        answer, bundle_meta = _answer_question(
            Path(run["out_dir"]), row["snapshot_id"], req.question,
            use_llm=req.llm and bool(os.environ.get("ANTHROPIC_API_KEY")),
            runs_subdir="scenario_runs" if row["is_scenario"] else "runs",
            context={"history": req.history, "selection": req.selection},
            ledger_path=_ledger_path(registry),
            schedule_id=schedule_id,
            session_id=req.session_id,
        )
        return _ok({"question": req.question, "answer": answer,
                    "bundle": bundle_meta})

    @app.get("/ledger/refusals")
    def ledger_refusals(limit: int = 20):
        """The question ledger's refusal clusters (R-AI1(d)) — the DEV-panel
        view. DEV-gated (like the tuning panel): 404 unless MRE_DEV is set, so a
        production deployment never exposes it. Reads the ledger; never writes."""
        if not os.environ.get("MRE_DEV"):
            raise HTTPException(404, "not found")
        from mre.modules.question_ledger import QuestionLedger
        led = QuestionLedger(_ledger_path(registry))
        return _ok({"clusters": led.refusal_clusters(limit=limit),
                    "recent": [e.model_dump(mode="json")
                               for e in led.recent(limit=limit)]})

    # ------------------------------------------------------------------
    # What-if
    # ------------------------------------------------------------------

    @app.post("/schedules/{schedule_id}/whatif", status_code=202)
    def whatif(schedule_id: str, req: WhatIfRequest, background: BackgroundTasks):
        row = _live_schedule(registry, schedule_id)
        if row["is_scenario"]:
            raise HTTPException(409, "cannot branch a what-if from a scenario "
                                     "schedule; use its base schedule")
        mods = _parse_modifications(req.modifications)  # 400s on bad input
        run = registry.create_run(
            kind="whatif", submission_id=row["submission_id"],
            base_run_id=row["run_id"],
            params={"modifications": req.modifications, "time_limit": req.time_limit},
        )
        if req.sync:
            _execute_whatif(registry, run, row, mods, req.time_limit)
        else:
            background.add_task(_execute_whatif, registry, run, row, mods,
                                req.time_limit)
        return _ok({"run_id": run["id"], "status": registry.get_run(run["id"])["status"]},
                   status_code=202)

    return app


# ---------------------------------------------------------------------------
# Workers (module-level so background tasks are picklable/testable)
# ---------------------------------------------------------------------------

def _persist_document(document: Any, out_dir: Path) -> Path:
    """Persist a schedule document under the split-endpoint discipline
    (contract 1.3, docs/04 R-T1d): the main render document (interaction
    stripped → ~1.1 size) to ``schedule_document.json``, and the Tier-0
    interaction payload — when present — to a sibling ``interaction.json``
    the split endpoint serves. Pool members / edge-less callers have no
    interaction and write no sibling file. Returns the main document path."""
    doc_path = out_dir / "schedule_document.json"
    main_doc = document.model_copy(update={"interaction": None})
    longpath.write_text(doc_path, main_doc.model_dump_json(indent=2))
    if document.interaction is not None:
        longpath.write_text(
            out_dir / "interaction.json",
            json.dumps({
                "schedule_id": document.schedule_id,
                "contract_version": document.contract_version,
                "interaction": document.interaction.model_dump(mode="json"),
            }, indent=2),
        )
    return doc_path


def _run_gate(registry: Registry, submission_id: str, sub_dir: Path | str,
              files_dir: Path) -> dict:
    """Run the M0 conformance gate; persist + register the certificate."""
    from mre.contracts.vocabularies import ModuleCode, RunStatus
    from mre.modules.conformance import (
        ConformanceGate, write_certificate_json, write_certificate_markdown,
    )
    from mre.reporter import Reporter

    sub_dir = Path(sub_dir)
    reporter = Reporter.begin(
        module=ModuleCode.M0, purpose="IDS conformance gate",
        config={"submission_dir": str(files_dir)},
        trigger="api", snapshot_id="pre-adapter", sink_dir=sub_dir / "gate_runs",
    )
    result = ConformanceGate().run(files_dir, reporter)
    reporter.end(RunStatus.SUCCESS if result.go else RunStatus.PARTIAL)

    json_path = sub_dir / "certificate.json"
    md_path = sub_dir / "certificate.md"
    write_certificate_json(result.certificate, json_path)
    write_certificate_markdown(result.certificate, md_path)
    registry.record_certificate(
        submission_id, result.grade, result.costing_grade, json_path, md_path,
    )
    return result.certificate


def _execute_solve(registry: Registry, run: dict, files_dir: Path,
                   req: SolveRequest, submission_id: str) -> None:
    """Run the existing pipeline into the minted run dir, then assemble and
    register the schedule document."""
    from mre.__main__ import main as mre_main
    from mre.contracts.schedule_document import CONTRACT_VERSION
    from mre.modules.schedule_assembler import build_document_from_run

    run_id, out_dir, snapshot_id = run["id"], Path(run["out_dir"]), run["snapshot_id"]
    argv = [
        "--submission", str(files_dir),
        "--out", str(out_dir),
        "--snapshot-id", snapshot_id,
        "--policy", req.policy,
        "--time-limit", str(req.time_limit),
    ]
    if req.horizon_days is not None:
        argv += ["--horizon-days", str(req.horizon_days)]
    if req.deterministic:
        argv += ["--solver-workers", "1", "--solver-seed", "0"]

    try:
        exit_code = mre_main(argv)
    except Exception as exc:  # noqa: BLE001 — background task must not raise
        registry.finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
        return

    if exit_code == 1:
        registry.finish_run(run_id, "failed",
                            error="gate or validator NO-GO — see run evidence")
        return
    if exit_code != 0:
        registry.finish_run(run_id, "failed",
                            error=f"solver produced no schedule (exit {exit_code})")
        return

    try:
        document = build_document_from_run(out_dir, snapshot_id, run_id)
        doc_path = _persist_document(document, out_dir)
        registry.register_schedule(
            schedule_id=document.schedule_id, run_id=run_id,
            snapshot_id=snapshot_id, status=document.status.value,
            contract_version=CONTRACT_VERSION, document_path=doc_path,
            submission_id=submission_id,
        )
        registry.finish_run(run_id, "succeeded", result={
            "schedule_id": document.schedule_id,
            "solver": document.solver.model_dump(mode="json"),
            "cost_total": document.cost_summary.total,
        })
    except Exception as exc:  # noqa: BLE001
        registry.finish_run(run_id, "failed",
                            error=f"document assembly: {type(exc).__name__}: {exc}")
        return

    if req.pool:
        # Warm the solution pool strictly after the schedule is registered —
        # same background task, so "warmed by a background task after solve
        # completes" holds without a second scheduling mechanism.
        import uuid as _uuid
        pool_id = f"pool-{_uuid.uuid4().hex[:12]}"
        registry.create_pool(pool_id, document.schedule_id)
        _execute_pool(registry, pool_id,
                      registry.get_schedule(document.schedule_id), {})


def _execute_rolling_solve(registry: Registry, run: dict, files_dir: Path,
                           req: SolveRequest, submission_id: str) -> None:
    """Rolling-horizon (sliced) solve worker (Session 4B.3a CU1): run the spine
    once (prepare_plant), solve the CURRENT window (build_rolling_view), assemble
    the contract-1.7 rolling document, and register it like any other schedule.
    The document renders the plant AS OF the reference origin — a committed frozen
    front + an active window + a beyond-horizon tray (the sliced world)."""
    from mre.contracts.schedule_document import CONTRACT_VERSION
    from mre.modules.rolling_horizon import prepare_plant, build_rolling_view
    from mre.modules.schedule_assembler import assemble_rolling_document

    run_id, out_dir = run["id"], Path(run["out_dir"])
    try:
        plant = prepare_plant(files_dir, out_dir, policy=req.policy)
        view = build_rolling_view(
            plant, window_days=req.window_days, frozen_days=req.frozen_days,
            deterministic=req.deterministic, member_time_limit_s=req.time_limit)
        idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
        schedule_id = f"rolling-{run_id[:12]}"
        document = assemble_rolling_document(
            plant=plant, view=view, schedule_id=schedule_id,
            run_id=run_id, identity_map=idmap)
        doc_path = _persist_document(document, out_dir)
        registry.register_schedule(
            schedule_id=document.schedule_id, run_id=run_id,
            snapshot_id=plant.snapshot_id, status=document.status.value,
            contract_version=CONTRACT_VERSION, document_path=doc_path,
            submission_id=submission_id,
        )
        registry.finish_run(run_id, "succeeded", result={
            "schedule_id": document.schedule_id, "sliced": True,
            "committed": view.committed and len(view.committed) or 0,
            "beyond_horizon": len(view.beyond_demand_ids),
        })
    except Exception as exc:  # noqa: BLE001 — background task must not raise
        registry.finish_run(run_id, "failed",
                            error=f"rolling solve: {type(exc).__name__}: {exc}")


def _execute_pool(registry: Registry, pool_id: str, schedule_row: dict,
                  params: dict) -> None:
    """Warm the solution pool for a registered schedule. The pool module is
    registry-free; this worker owns the indexing and status transitions."""
    from mre.modules.solution_pool import warm_solution_pool

    run = registry.get_run(schedule_row["run_id"])
    try:
        result = warm_solution_pool(
            out_dir=Path(run["out_dir"]),
            snapshot_id=schedule_row["snapshot_id"],
            base_schedule_id=schedule_row["id"],
            run_id=schedule_row["run_id"],
            k=int(params.get("k", 5)),
            tolerance_pct=float(params.get("tolerance_pct", 10.0)),
            member_time_limit_s=float(params.get("member_time_limit", 10.0)),
            seed=int(params.get("seed", 1234)),
            pool_id=pool_id,
        )
        summary = result.summary()
        registry.finish_pool(
            pool_id, result.status,
            summary=summary,
            members=[
                {"member_index": m.member_index, "objective": m.objective,
                 "objective_delta_pct": m.objective_delta_pct,
                 "hamming_from_incumbent": m.hamming_from_incumbent,
                 "document_path": m.document_path}
                for m in result.members if m.document_path
            ],
        )
    except Exception as exc:  # noqa: BLE001 — background task must not raise
        registry.finish_pool(pool_id, "failed",
                             error=f"{type(exc).__name__}: {exc}")


def _execute_forced_alternatives(registry: Registry, pool_id: str,
                                 schedule_row: dict, params: dict) -> None:
    """Build the forced-alternative ghosts (R-T1a) for a registered schedule
    and index them into the pool tables with a ``forced_alternative`` source
    label. Registry-free module; this worker owns the indexing."""
    from mre.modules.forced_alternatives import build_forced_alternatives

    run = registry.get_run(schedule_row["run_id"])
    try:
        result = build_forced_alternatives(
            out_dir=Path(run["out_dir"]),
            snapshot_id=schedule_row["snapshot_id"],
            base_schedule_id=schedule_row["id"],
            run_id=schedule_row["run_id"],
            target_op_ids=params.get("target_op_ids"),
            budget=int(params.get("budget", 4)),
            member_time_limit_s=float(params.get("member_time_limit", 10.0)),
            seed=int(params.get("seed", 1234)),
            pool_id=pool_id,
        )
        registry.finish_pool(
            pool_id, result.status,
            summary=result.summary(),
            members=[
                {"member_index": m.member_index, "objective": m.objective,
                 "objective_delta_pct": m.objective_delta_pct,
                 "hamming_from_incumbent": None,
                 "document_path": m.document_path,
                 "source": "forced_alternative", "verdict": m.verdict,
                 "label": {
                     "target_operation_ref": m.target_operation_ref,
                     "forbidden_resource_ref": m.forbidden_resource_ref,
                     "alternative_resource_ref": m.alternative_resource_ref,
                     "status": m.status,
                     # compact ghost placement — the bar the cockpit draws (CU2)
                     "placement": m.alternative_placement,
                 }}
                for m in result.members
            ],
        )
    except Exception as exc:  # noqa: BLE001 — background task must not raise
        registry.finish_pool(pool_id, "failed",
                             error=f"{type(exc).__name__}: {exc}")


def _execute_op_alternatives(registry: Registry, pool_id: str,
                             schedule_row: dict, op_id: str, params: dict) -> None:
    """On-demand pricing worker (session 3.3 CU1): price every eligible machine
    for one grabbed op and APPEND the members to the schedule's alternatives
    pool. Bounded by the process-wide concurrency semaphore; the in-flight dedup
    key is cleared on exit so a later grab of the same op can re-price if it
    ever needs to. Registry-free module; this worker owns the indexing."""
    from mre.modules.forced_alternatives import build_op_alternatives

    key = (schedule_row["id"], op_id)
    run = registry.get_run(schedule_row["run_id"])
    time_limit = params.get("member_time_limit")
    if time_limit is None:
        time_limit = ONDEMAND_TIME_LIMIT_S
    acquired = _ONDEMAND_SEMAPHORE.acquire(timeout=120)
    try:
        result = build_op_alternatives(
            out_dir=Path(run["out_dir"]),
            snapshot_id=schedule_row["snapshot_id"],
            base_schedule_id=schedule_row["id"],
            run_id=schedule_row["run_id"],
            op_id=op_id,
            max_machines=int(params.get("max_machines", 4)),
            member_time_limit_s=float(time_limit),
            seed=int(params.get("seed", 1234)),
            pool_id=pool_id,
        )
        registry.append_pool_members(
            pool_id,
            members=[
                {"member_index": m.member_index, "objective": m.objective,
                 "objective_delta_pct": m.objective_delta_pct,
                 "hamming_from_incumbent": None,
                 "document_path": m.document_path,
                 "source": "forced_alternative", "verdict": m.verdict,
                 "label": {
                     "target_operation_ref": m.target_operation_ref,
                     "forbidden_resource_ref": m.forbidden_resource_ref,
                     "alternative_resource_ref": m.alternative_resource_ref,
                     "status": m.status, "on_demand": True,
                     "placement": m.alternative_placement,
                 }}
                for m in result.members
            ],
        )
    except Exception:  # noqa: BLE001 — background task must not raise
        pass
    finally:
        if acquired:
            _ONDEMAND_SEMAPHORE.release()
        with _ONDEMAND_LOCK:
            _ONDEMAND_INFLIGHT.discard(key)


def _execute_whatif(registry: Registry, run: dict, base_schedule: dict,
                    modifications: list, time_limit: Optional[float]) -> None:
    """Run a scenario re-solve, fully run-scoped: the base snapshot is copied
    into the minted run dir, so scenario artifacts never touch the base run."""
    from mre.modules.scenario import Scenario, ScenarioRunner, derive_base_context
    from mre.modules.schedule_assembler import build_document_from_run
    from mre.modules.snapshot_store import SnapshotStore
    from mre.contracts.schedule_document import CONTRACT_VERSION

    run_id, out_dir = run["id"], Path(run["out_dir"])
    base_run = registry.get_run(base_schedule["run_id"])
    base_out = Path(base_run["out_dir"])
    base_snap = base_run["snapshot_id"]

    try:
        longpath.copytree(base_out / "snapshots" / base_snap,
                          out_dir / "snapshots" / base_snap)
        base_ctx = derive_base_context(base_out / "runs")
        # R-DP8: a scenario of a lineage that carries accepted commitments must
        # respect them — the standing pins are held during the scenario solve too.
        base_pins = registry.schedule_pins(base_schedule["id"])
        runner = ScenarioRunner(
            SnapshotStore(out_dir / "snapshots"),
            out_dir / "scenario_runs",
            time_limit_seconds=time_limit or base_ctx.get("time_limit", 30.0),
            base_context=base_ctx,
            standing_pins=base_pins,
        )
        scenario = Scenario(base_snapshot_id=base_snap, modifications=modifications)
        result = runner.run(scenario)

        from mre.modules import standing_pins as sp
        document = build_document_from_run(
            out_dir, result.scenario_snapshot_id, run_id,
            runs_subdir="scenario_runs",
            parent_schedule_id=base_schedule["id"],
            standing_pin_ops=sp.standing_pin_ops(base_pins),
        )
        doc_path = _persist_document(document, out_dir)
        (out_dir / "diff.json").write_text(
            json.dumps(result.diff, indent=2, default=str), encoding="utf-8")

        registry.register_schedule(
            schedule_id=document.schedule_id, run_id=run_id,
            snapshot_id=result.scenario_snapshot_id, status=document.status.value,
            contract_version=CONTRACT_VERSION, document_path=doc_path,
            submission_id=base_schedule["submission_id"],
            is_scenario=True, parent_schedule_id=base_schedule["id"],
        )
        registry.finish_run(run_id, "succeeded", result={
            "schedule_id": document.schedule_id,
            "diff": result.diff,
        })
    except Exception as exc:  # noqa: BLE001
        registry.finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")


def _execute_accept(registry: Registry, base_schedule: dict, req: "AcceptRequest",
                    budget_s: float) -> tuple[str, dict]:
    """Materialize an accepted edit (CU1): mint a run, copy the base snapshot
    into it, pin + re-solve into a child snapshot (never mutating the base),
    assemble the document, and register it as a NEW proposed schedule whose
    parent is the base. Returns (new_schedule_id, decision_summary).

    Synchronous by design — accept is a deliberate act; the planner waits behind
    the sandbox budget (the cockpit already showed the verdict) rather than
    polling a background run."""
    from mre.contracts.schedule_document import CONTRACT_VERSION
    from mre.modules.planner_edit import apply_planner_edit
    from mre.modules.scenario import derive_base_context
    from mre.modules.schedule_assembler import build_document_from_run
    from mre.modules import standing_pins as sp

    base_run = registry.get_run(base_schedule["run_id"])
    base_out = Path(base_run["out_dir"])
    # The schedule's OWN snapshot — for an accept-derived version this is an
    # accept-derived child snapshot (opaque snap-edit-<sha12>, 4.0d), NOT the run's
    # minted snapshot id (so chained edits copy the right ground truth).
    base_snap = base_schedule["snapshot_id"]

    # Config (reference_date, policy, outlier threshold) must come from the ROOT
    # solve run — an accept run records no M3/M4 pipeline, so re-deriving from a
    # chained parent would lose the reference date (the 3.3b wall-clock trap). The
    # M5 horizon + incumbent objective, however, come from the IMMEDIATE parent's
    # evidence (its own accept re-solve), which is where the version we edit sits.
    root_run = base_run
    while root_run.get("base_run_id"):
        nxt = registry.get_run(root_run["base_run_id"])
        if nxt is None:
            break
        root_run = nxt

    run = registry.create_run(
        kind="accept", submission_id=base_schedule["submission_id"],
        base_run_id=base_schedule["run_id"],
        params={"pin_op_id": req.pin_op_id, "pin_resource_id": req.pin_resource_id,
                "pin_start_iso": req.pin_start_iso, "authority": req.authority},
    )
    run_id, out_dir = run["id"], Path(run["out_dir"])
    try:
        # Route through the long-path seam: the base snapshot dir can be nested
        # deep under a chained-edit run, past Windows MAX_PATH (4.0d).
        longpath.copytree(base_out / "snapshots" / base_snap,
                          out_dir / "snapshots" / base_snap)
        base_ctx = derive_base_context(Path(root_run["out_dir"]) / "runs")
        base_ctx["base_runs_dir"] = str(base_out / "runs")
        # R-DP8: the lineage's standing commitments are held during the accept
        # re-solve; the NEW version's cumulative pins = the base's, with this
        # drop's op re-committed (or appended if fresh).
        base_pins = registry.schedule_pins(base_schedule["id"])
        result = apply_planner_edit(
            out_dir=out_dir, base_snapshot_id=base_snap,
            pin_op_id=req.pin_op_id, pin_resource_id=req.pin_resource_id,
            pin_start_iso=req.pin_start_iso, authority=req.authority,
            base_context=base_ctx, budget_s=budget_s,
            standing_pins=base_pins,
        )
        new_pins = sp.compose_lineage_pins(base_pins, result.pin)
        document = build_document_from_run(
            out_dir, result.child_snapshot_id, run_id,
            runs_subdir="runs", parent_schedule_id=base_schedule["id"],
            standing_pin_ops=sp.standing_pin_ops(new_pins),
        )
        doc_path = _persist_document(document, out_dir)
        registry.register_schedule(
            schedule_id=document.schedule_id, run_id=run_id,
            snapshot_id=result.child_snapshot_id, status="proposed",
            contract_version=CONTRACT_VERSION, document_path=doc_path,
            submission_id=base_schedule["submission_id"],
            is_scenario=False, parent_schedule_id=base_schedule["id"],
            pins=new_pins,
        )
        registry.finish_run(run_id, "succeeded", result={
            "schedule_id": document.schedule_id,
            "delta_abs": result.delta_abs, "moved_count": result.moved_count,
        })
    except Exception as exc:  # noqa: BLE001
        registry.finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
        raise HTTPException(409, f"accept failed: {type(exc).__name__}: {exc}")

    decision = {
        "record_id": result.decision_record_id,
        "authority": req.authority,
        # delta_abs/delta_pct are the SCALED solver objective (never dollars);
        # cost_delta carries the LEDGER dollars the card shows (exit-audit fix).
        "delta_abs": result.delta_abs, "delta_pct": result.delta_pct,
        "cost_delta": result.cost_delta,
        "moved_count": result.moved_count, "pin": result.pin,
    }
    return document.schedule_id, decision


def _live_schedule(registry: Registry, schedule_id: str) -> dict:
    """Shared ask/whatif validation: the schedule exists and is not superseded."""
    row = registry.get_schedule(schedule_id)
    if row is None:
        raise HTTPException(404, f"unknown schedule {schedule_id}")
    if row["status"] == "superseded":
        raise HTTPException(409, f"schedule {schedule_id} is superseded")
    return row


def _parse_modifications(raw: list[dict]) -> list:
    from mre.modules.scenario import CalendarException, SetCostWeight, SuppressMerge

    out: list = []
    for i, m in enumerate(raw):
        kind = m.get("type")
        try:
            if kind == "suppress_merge":
                out.append(SuppressMerge(demand_refs=list(m["demand_refs"])))
            elif kind == "set_cost_weight":
                out.append(SetCostWeight(path=str(m["path"]), value=float(m["value"])))
            elif kind == "calendar_exception":
                out.append(CalendarException(
                    resource_ref=str(m["resource_ref"]),
                    window=dict(m["window"]),
                    type=str(m.get("exception_type", "closure")),
                    reason=str(m.get("reason", "planned_maintenance")),
                ))
            else:
                raise HTTPException(
                    400, f"modifications[{i}]: unknown type {kind!r} (expected "
                         "suppress_merge | set_cost_weight | calendar_exception)")
        except KeyError as missing:
            raise HTTPException(400, f"modifications[{i}]: missing field {missing}")
    if not out:
        raise HTTPException(400, "modifications must be a non-empty list")
    return out


def _ledger_path(registry: Registry) -> Path:
    """The question ledger's own stream (R-AI1(d), CU3): under the data root,
    NEVER inside a run's evidence dir — a ledger entry is a fact about the AI
    layer, not about the schedule, and must never pollute schedule evidence."""
    return Path(registry.data_root) / "ledger" / "questions.jsonl"


def _render_fail_closed(bundle: Any, use_llm: bool, log: Any) -> str:
    """Render a bundle, guaranteeing a string and never a raise (4A.1b).

    The LLMRenderer is itself internally sealed (never raises), so this is the
    outer belt: on the DEV/LLM path a construction/network/auth/parsing/validation
    failure degrades to the deterministic TEMPLATE render and logs one Event. A
    taxonomy-shaped question therefore always renders, whatever the AI stack does.
    """
    from mre.modules.renderers import LLMRenderer, TemplateRenderer

    if use_llm:
        try:
            return LLMRenderer().render(bundle)
        except Exception as exc:  # noqa: BLE001 — render must never surface as 5xx
            log.warning(
                "EVENT ask.llm_degraded: LLM render raised %s: %s — "
                "degraded to template render", type(exc).__name__, exc,
            )
    return TemplateRenderer().render(bundle)


def _answer_question(out_dir: Path, snapshot_id: str, question: str,
                     use_llm: bool, runs_subdir: str = "runs",
                     context: Optional[dict] = None,
                     ledger_path: Optional[Path] = None,
                     schedule_id: Optional[str] = None,
                     session_id: Optional[str] = None) -> tuple[str, dict]:
    """Route a question through the M10 explainer for a persisted run.

    Session 4A.1: the deterministic router is now wrapped by the interpreter +
    conversational context + question ledger (``run_ask``). Deterministic
    phrasings route exactly as before (zero regression / zero LLM); only a
    miss falls through to the interpreter, and every ask is logged."""
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.interpreter import Interpreter, run_ask
    from mre.modules.question_ledger import QuestionLedger
    from mre.modules.snapshot_store import SnapshotStore

    index_path = out_dir / "evidence_index.json"
    if index_path.exists():
        index = EvidenceIndex.load(index_path)
    else:
        # Scenario runs keep their evidence isolated in scenario_runs/ and
        # have no persisted index; build one on the fly (read-only).
        index = EvidenceIndex().build(out_dir / runs_subdir)

    store = SnapshotStore(out_dir / "snapshots")
    explainer = Explainer(store, index, snapshot_id=snapshot_id)
    _log = logging.getLogger("mre.api")
    ledger = QuestionLedger(ledger_path) if ledger_path is not None else None

    # --- routing (deterministic; the LLM interpreter only on a miss) ----------
    # The interpreter is available only when a key is set; without one it is
    # simply off (deterministic-only, zero regression). It never authors an
    # answer — it maps phrasing onto the closed route taxonomy, and it is
    # fail-closed at the source (construction + interpret cannot raise). This
    # guard is the belt to that suspenders: should anything in the routing
    # surface still throw, the question re-routes DETERMINISTICALLY (interpreter
    # off, ledger already handled) so the answer is never lost to a 5xx.
    if question.strip().lower() == "summarize":
        bundle = explainer.summarize_run()
        ask_meta = {"resolved_question": question, "route": "summarize",
                    "source": "deterministic", "confidence": None}
    else:
        try:
            interpreter = Interpreter() if os.environ.get("ANTHROPIC_API_KEY") else None
            result = run_ask(explainer, question, context=context,
                             interpreter=interpreter, ledger=ledger,
                             schedule_id=schedule_id, session_id=session_id)
        except Exception as exc:  # noqa: BLE001 — the ask surface must never 5xx
            _log.warning(
                "EVENT ask.llm_degraded: routing surface raised %s: %s — "
                "re-routed deterministically (interpreter off)",
                type(exc).__name__, exc,
            )
            result = run_ask(explainer, question, context=context,
                             interpreter=None, ledger=None,
                             schedule_id=schedule_id, session_id=session_id)
        bundle = result.bundle
        ask_meta = {"resolved_question": result.resolved_question,
                    "route": result.route, "source": result.source,
                    "confidence": result.confidence,
                    "resolution_note": result.resolution_note}

    # --- render (the LLM renderer is the real hazard; it is internally sealed
    #     and this boundary is the outer belt: ANY failure — construction,
    #     network, auth, parsing, validation — degrades to the deterministic
    #     TEMPLATE + a logged Event, never a 5xx) --------------------------------
    answer = _render_fail_closed(bundle, use_llm, _log)
    return answer, {
        "subject_id": bundle.subject_id,
        "subject_type": bundle.subject_type,
        "subject_external_name": bundle.subject_external_name,
        "snapshot_id": bundle.snapshot_id,
        "record_count": len(bundle.ordered_records),
        "register": _register_of(bundle),
        # The entity refs this answer already cites — surfaced (not synthesized)
        # so the cockpit can highlight the corresponding bars/lanes in sync with
        # the text. Reads only bundle.ordered_records; adds no answer path.
        "cited_refs": _cited_refs_from_bundle(bundle),
        **ask_meta,
    }


def _register_of(bundle: Any) -> str:
    """testimony (evidence/decisions) vs judgment (findings/triage). Delegates to
    the single-source classifier in explainer.py so no register ever blends."""
    from mre.modules.explainer import register_of
    return register_of(bundle)


def _cited_refs_from_bundle(bundle: Any) -> dict:
    """Collect the canonical entity refs the answer cites, WITHOUT re-deriving
    anything: walk ``bundle.ordered_records`` (the exact records the renderer
    footnoted) and pull the operation/resource/demand UUIDs already there.

    - ``operations`` — every record subject of type operation, plus the subject
      demand: the board highlights bars whose operation_ref is in this set.
    - ``resources`` — the CHOSEN resource of each assignment decision AND its
      priced alternatives (``resource:<uuid>`` options): the cockpit glows the
      chosen lane and the alternative lanes the answer prices.
    - ``demands`` — the subject demand ref, if the subject is a demand.
    This is the evidence architecture made spatial (docs/07 Phase 3): the refs
    are the citations, not a new computation over them."""
    operations: list[str] = []
    resources: list[str] = []
    demands: list[str] = []

    if getattr(bundle, "subject_type", "") == "demand" and bundle.subject_id:
        demands.append(bundle.subject_id)

    for rec in getattr(bundle, "ordered_records", []) or []:
        for subj in rec.get("subjects", []) or []:
            eid, etype = subj.get("entity_id"), subj.get("entity_type")
            if not eid:
                continue
            if etype == "operation":
                operations.append(eid)
            elif etype == "resource":
                resources.append(eid)
            elif etype == "demand":
                demands.append(eid)
        chosen = rec.get("chosen") or {}
        if isinstance(chosen, dict) and chosen.get("resource_id"):
            resources.append(chosen["resource_id"])
        for alt in rec.get("alternatives", []) or []:
            opt = str(alt.get("option", ""))
            if opt.startswith("resource:"):
                resources.append(opt.split(":", 1)[1])

    # de-dup, preserve first-seen order
    def _uniq(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        return [x for x in xs if not (x in seen or seen.add(x))]

    return {
        "operations": _uniq(operations),
        "resources": _uniq(resources),
        "demands": _uniq(demands),
    }
