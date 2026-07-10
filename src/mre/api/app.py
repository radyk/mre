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
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from mre.api.registry import Registry

API_VERSION = "1"


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


class PoolRequest(BaseModel):
    k: int = 5
    tolerance_pct: float = 10.0
    member_time_limit: float = 10.0
    seed: int = 1234
    sync: bool = False


class AskRequest(BaseModel):
    question: str
    llm: bool = False               # honored only if ANTHROPIC_API_KEY is set


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
        if req.sync:
            _execute_solve(registry, run, files_dir, req, submission_id)
        else:
            background.add_task(_execute_solve, registry, run, files_dir, req,
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
        )
        return _ok({"question": req.question, "answer": answer,
                    "bundle": bundle_meta})

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
        doc_path = out_dir / "schedule_document.json"
        doc_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
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
        shutil.copytree(base_out / "snapshots" / base_snap,
                        out_dir / "snapshots" / base_snap)
        base_ctx = derive_base_context(base_out / "runs")
        runner = ScenarioRunner(
            SnapshotStore(out_dir / "snapshots"),
            out_dir / "scenario_runs",
            time_limit_seconds=time_limit or base_ctx.get("time_limit", 30.0),
            base_context=base_ctx,
        )
        scenario = Scenario(base_snapshot_id=base_snap, modifications=modifications)
        result = runner.run(scenario)

        document = build_document_from_run(
            out_dir, result.scenario_snapshot_id, run_id,
            runs_subdir="scenario_runs",
            parent_schedule_id=base_schedule["id"],
        )
        doc_path = out_dir / "schedule_document.json"
        doc_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
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


def _answer_question(out_dir: Path, snapshot_id: str, question: str,
                     use_llm: bool, runs_subdir: str = "runs") -> tuple[str, dict]:
    """Route a question through the M10 explainer for a persisted run."""
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.renderers import LLMRenderer, TemplateRenderer
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
    bundle = (explainer.summarize_run() if question.strip().lower() == "summarize"
              else explainer.answer(question))
    renderer = LLMRenderer() if use_llm else TemplateRenderer()
    answer = renderer.render(bundle)
    return answer, {
        "subject_id": bundle.subject_id,
        "subject_type": bundle.subject_type,
        "subject_external_name": bundle.subject_external_name,
        "snapshot_id": bundle.snapshot_id,
        "record_count": len(bundle.ordered_records),
    }
