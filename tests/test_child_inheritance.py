"""R-CH1 (Session R4.2) — what a child inherits at accept.

Both accept ceremonies minted their child through the MONOLITHIC assembler, so a
child of a rolling, calibrated parent came out monolithic, uncalibrated and
dateless BY CONSTRUCTION. That is not a cosmetic metadata loss: the missing
rolling block is what handed the next planner gesture ``restrict_op_ids=None``,
and the missing reference date is what dragged the rebuilt model's origin 35 days
back from the frame the planner's pin is expressed in. R4.0 measured the result
on the live specimen ``b5daba66``: 24 of 24 nudges impossible, 23 of them
carrying a confident FALSE sentence about a machine that was open.

Four clauses, tested here:

  (1) an accept on a rolling parent mints a ROLLING child;
  (2) the child's run context RECORDS what downstream derivation needs, so
      ``derive_base_context`` recovers the reference date from the CHILD's own
      run dir — asserted as a RECOVERY, never as a write;
  (3) calibration is inherited BY DECLARATION, in both directions;
  (4) the portfolio belongs to the solve that ran it, and an accept is not it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from mre.contracts.schedule_document import (
    AssignmentBlock, CalibrationBlock, Chunk, CostSummary, PortfolioBlock,
    RollingBlock, ScheduleDocument, SolverBlock,
)
from mre.modules.schedule_assembler import (
    ChildInheritanceError, inherit_child_metadata,
)

UTC = timezone.utc


def _dt(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


REF = _dt(2026, 1, 5)
FROZEN = _dt(2026, 1, 6)


def _asgn(op_id: str, start: datetime, resource: str = "res-1") -> AssignmentBlock:
    return AssignmentBlock(
        assignment_id=f"a-{op_id}", operation_ref=op_id, workpackage_ref="wp-1",
        resource_id=resource,
        chunks=[Chunk(chunk_seq=1, start=start, end=start + timedelta(hours=1),
                      working_min=60)],
    )


def _child(*assignments: AssignmentBlock, **kw) -> ScheduleDocument:
    """A child exactly as the monolithic assembler hands it over: no rolling
    block, no calibration, no reference_date."""
    return ScheduleDocument(
        schedule_id=kw.pop("schedule_id", "child-1"),
        snapshot_id="snap-edit-abc", run_id="run-child",
        solver=kw.pop("solver", SolverBlock(status="OPTIMAL")),
        cost_summary=CostSummary(total=10.0, production_regular=10.0,
                                 production_overtime=0.0, setup=0.0,
                                 tardiness=0.0),
        assignments=list(assignments),
        **kw,
    )


def _calibration(**over) -> dict:
    base = dict(
        state="accepted",
        sentence="calibrated for F001 on 2026-08-01 by mre.calibrate/1 "
                 "(25 measured cells) — applied: det_total=10, k=3",
        plant_key="F001", profile_id="cal-F001-abc",
        calibrated_at="2026-08-01T00:00:00Z", instrument_version="mre.calibrate/1",
        applied={"det_total": 10.0, "k": 3}, window_calibrated=10,
        window_solved=10,
    )
    base.update(over)
    return base


def _parent(*op_ids: str, rolling: bool = True, calibration: bool = True,
            portfolio: bool = True, tray: int = 2, **roll_over) -> dict:
    """A parent document as it is read off disk — a plain dict."""
    roll = dict(
        reference_origin=REF.isoformat(), window_start=REF.isoformat(),
        window_end=_dt(2026, 1, 15).isoformat(), frozen_until=FROZEN.isoformat(),
        window_days=10, frozen_days=1, committed_count=99, active_count=99,
        beyond_horizon=[{"demand_ref": f"dem-{i}"} for i in range(tray)],
        boundary_moves=[],
    )
    roll.update(roll_over)
    solver: dict = {"status": "OPTIMAL"}
    if calibration:
        solver["calibration"] = _calibration()
    if portfolio:
        solver["portfolio"] = {"k": 3, "winner_seed": 44, "members": []}
    return {
        "schedule_id": "rolling-parent-1",
        "reference_date": REF.isoformat(),
        "solver": solver,
        "assignments": [{"operation_ref": o} for o in op_ids],
        "rolling": roll if rolling else None,
    }


# ---------------------------------------------------------------------------
# clause (1) — the rolling block
# ---------------------------------------------------------------------------

class TestRollingInheritance:

    def test_no_parent_is_the_identity(self):
        """A root solve has no parent. Nothing is inherited and nothing is
        touched — including the portfolio it legitimately owns."""
        doc = _child(_asgn("op-1", _dt(2026, 1, 7)),
                     solver=SolverBlock(status="OPTIMAL",
                                        portfolio=PortfolioBlock(k=3, det_time_s=6.0, seed0=42)))
        assert inherit_child_metadata(doc, None) is doc

    def test_a_monolithic_parent_mints_a_monolithic_child(self):
        """THE TRUE NEGATIVE, and it is load-bearing. This ruling makes a child
        match its parent; it does not make every child rolling."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))),
            _parent("op-1", rolling=False, calibration=False, portfolio=False))
        assert child.rolling is None
        assert child.assignments[0].commitment_state is None

    def test_a_rolling_parent_mints_a_rolling_child(self):
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1"))
        assert child.rolling is not None
        r = child.rolling
        assert r.reference_origin == REF
        assert r.window_start == REF and r.window_end == _dt(2026, 1, 15)
        assert r.frozen_until == FROZEN
        assert r.window_days == 10 and r.frozen_days == 1

    def test_the_tray_comes_across_whole(self):
        """The beyond-horizon tray is invariant under an accept: the accept's
        model is built over exactly the operations the published plan places
        (R-DP11), so it can neither admit nor drop a job."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1", tray=5))
        assert len(child.rolling.beyond_horizon) == 5
        assert [b.demand_ref for b in child.rolling.beyond_horizon] == [
            f"dem-{i}" for i in range(5)]

    def test_the_coarse_zone_comes_across_whole(self):
        """The coarse zone is a RELAXATION over the tray (R-SC2), and the tray
        is unchanged by an accept — so the zone the parent published still
        describes the child. Dropping it would silently retract a published
        statement about the next quarter."""
        zone = {"bucket_days": 7, "bucket_days_provenance": "declared",
                "capacity_derate": 0.85,
                "capacity_derate_provenance": "declared",
                "proof_status": "FEASIBLE", "planning_status": "FEASIBLE"}
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))),
            _parent("op-1", coarse_zone=zone))
        cz = child.rolling.coarse_zone
        assert cz is not None
        assert cz.bucket_days == 7 and cz.capacity_derate == 0.85
        assert cz.capacity_derate_provenance == "declared"

    def test_the_boundary_move_log_comes_across_whole(self):
        """R-F1's log is a LINEAGE fact — the moves this board has had made on
        it — so a child of a board whose boundary was moved still records
        them."""
        move = {"at": REF.isoformat(), "direction": "freeze",
                "from_instant": REF.isoformat(), "to_instant": FROZEN.isoformat(),
                "authority": "dev-planner"}
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))),
            _parent("op-1", boundary_moves=[move]))
        assert len(child.rolling.boundary_moves) == 1
        assert child.rolling.boundary_moves[0].authority == "dev-planner"

    def test_the_commitment_states_are_derived_from_the_child_s_own_placements(self):
        """DERIVED, not copied. ``rolling_horizon`` commits an op whose start
        falls inside the frozen front, so a bar the accept moved carries the
        state its NEW start earns — and the two counts follow from the same
        read rather than from the parent's numbers."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 5, 8)),      # inside the front
                   _asgn("op-2", _dt(2026, 1, 5, 23, 59)),  # inside, just
                   _asgn("op-3", _dt(2026, 1, 6, 0, 1)),    # past it
                   _asgn("op-4", _dt(2026, 1, 9))),
            _parent("op-1", "op-2", "op-3", "op-4"))
        states = {a.operation_ref: a.commitment_state for a in child.assignments}
        assert states == {"op-1": "committed", "op-2": "committed",
                          "op-3": "active_window", "op-4": "active_window"}
        assert child.rolling.committed_count == 2
        assert child.rolling.active_count == 2
        # and NOT the parent's placeholder 99s
        assert child.rolling.committed_count != 99

    def test_a_bar_exactly_on_the_boundary_is_active_not_committed(self):
        """``s_min < frozen_end_min`` in ``rolling_horizon``. One definition,
        read the same way here — an off-by-one at the boundary is a bar that
        renders as locked when a planner may still move it."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", FROZEN)), _parent("op-1"))
        assert child.assignments[0].commitment_state == "active_window"

    def test_the_reference_date_comes_from_the_reference_origin(self):
        """A rolling document's ``reference_date`` IS its reference origin.
        The accept records no M3, so the monolithic path found none."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1"))
        assert child.reference_date == REF

    def test_a_child_that_already_has_a_reference_date_keeps_it(self):
        own = _dt(2026, 2, 1)
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7)), reference_date=own),
            _parent("op-1"))
        assert child.reference_date == own


class TestTheFrameIsAssertedNotAssumed:
    """R-SG1's discipline at the document layer: the inherited window and tray
    describe the parent's PLAN, so inheriting them onto a child that does not
    place that plan would ship a rolling block that is a statement about
    something else."""

    def test_a_child_that_lost_a_bar_refuses(self):
        with pytest.raises(ChildInheritanceError) as exc:
            inherit_child_metadata(
                _child(_asgn("op-1", _dt(2026, 1, 7))),
                _parent("op-1", "op-2"))
        assert "1 lost" in str(exc.value)

    def test_a_child_that_gained_a_bar_refuses(self):
        with pytest.raises(ChildInheritanceError) as exc:
            inherit_child_metadata(
                _child(_asgn("op-1", _dt(2026, 1, 7)),
                       _asgn("op-9", _dt(2026, 1, 8))),
                _parent("op-1"))
        assert "1 gained" in str(exc.value)

    def test_the_refusal_names_both_counts(self):
        """A mismatch a reader cannot diagnose from the message is a mismatch
        reported twice."""
        with pytest.raises(ChildInheritanceError) as exc:
            inherit_child_metadata(_child(_asgn("op-1", _dt(2026, 1, 7))),
                                   _parent("op-2"))
        msg = str(exc.value)
        assert "1 gained" in msg and "1 lost" in msg and "R-CH1" in msg

    def test_a_monolithic_parent_is_not_frame_checked(self):
        """Nothing is inherited, so there is no frame to be wrong about. A
        check that fires where it cannot mean anything is noise."""
        child = inherit_child_metadata(
            _child(_asgn("op-9", _dt(2026, 1, 7))),
            _parent("op-1", rolling=False))
        assert child.rolling is None


# ---------------------------------------------------------------------------
# clause (3) — calibration, inherited by declaration
# ---------------------------------------------------------------------------

class TestCalibrationInheritance:

    def _cal(self, **parent_kw) -> CalibrationBlock | None:
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1", **parent_kw))
        return child.solver.calibration

    def test_the_profile_s_identity_is_inherited(self):
        cal = self._cal()
        assert cal is not None
        assert cal.state == "accepted"
        assert cal.plant_key == "F001"
        assert cal.profile_id == "cal-F001-abc"
        assert cal.instrument_version == "mre.calibrate/1"
        assert cal.window_calibrated == 10

    def test_the_provenance_names_the_parent_it_came_from(self):
        cal = self._cal()
        assert "rolling-parent-1" in cal.sentence
        assert "inherited" in cal.sentence.lower()
        # the parent's own words survive inside it — the child does not
        # re-author what the measurement said
        assert "25 measured cells" in cal.sentence

    def test_applied_is_cleared_because_the_accept_took_no_coefficients(self):
        """R-CAL1 gives ``applied`` ONE meaning: the coefficients this solve
        actually took. An accept re-solve runs at the sandbox's own
        deterministic budget and seed, so copying the block verbatim would
        state that the child ran at the calibrated budget. It did not."""
        cal = self._cal()
        assert cal.applied == {}
        assert cal.window_solved is None
        assert cal.drift is None
        assert "neither re-measured" in cal.sentence

    def test_a_parent_that_declares_nothing_hands_down_nothing(self):
        """The other direction. The child does NOT manufacture
        ``state="absent"`` — that value means "nobody has measured this plant",
        and inferring it from the fact that the parent document carries no
        block would be a claim about the plant made from a fact about our
        storage (the 4B.18 discipline)."""
        assert self._cal(calibration=False) is None

    def test_an_unaccepted_parent_profile_stays_unaccepted(self):
        """The state is the plant's, not the accept's. Inheritance may not
        promote a profile nobody signed."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1"))
        parent = _parent("op-1")
        parent["solver"]["calibration"] = _calibration(
            state="unaccepted", applied={})
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), parent)
        assert child.solver.calibration.state == "unaccepted"

    def test_calibration_is_inherited_from_a_monolithic_parent_too(self):
        """Calibration is a fact about the PLANT, not about the window. A
        monolithic parent that carries one hands it down."""
        parent = _parent("op-1", rolling=False, portfolio=False)
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), parent)
        assert child.rolling is None
        assert child.solver.calibration is not None
        assert "rolling-parent-1" in child.solver.calibration.sentence


# ---------------------------------------------------------------------------
# clause (4) — what is NOT inherited, stated in code
# ---------------------------------------------------------------------------

class TestPortfolioIsNotInherited:

    def test_the_child_carries_no_portfolio(self):
        """K deterministic searches at consecutive seeds and the ledger
        comparison between them (R-BK1). An accept runs ONE pinned re-solve."""
        child = inherit_child_metadata(
            _child(_asgn("op-1", _dt(2026, 1, 7))), _parent("op-1"))
        assert child.solver.portfolio is None

    def test_a_portfolio_on_the_child_is_cleared_rather_than_kept(self):
        """Stated in code, not merely omitted: if a child ever arrives carrying
        one, it is not this solve's and it goes."""
        doc = _child(_asgn("op-1", _dt(2026, 1, 7)),
                     solver=SolverBlock(status="OPTIMAL",
                                        portfolio=PortfolioBlock(k=3, det_time_s=6.0, seed0=42)))
        assert inherit_child_metadata(doc, _parent("op-1")).solver.portfolio is None


# ---------------------------------------------------------------------------
# clause (2) — the run-context write, asserted as a RECOVERY
# ---------------------------------------------------------------------------

class TestReferenceDateRecovery:
    """The C5-fixture pattern (the 2026-08-06 errand): the test asserts what
    ``derive_base_context`` RECOVERS, never that a write happened. A field
    written into a config nobody reads recovers nothing."""

    def _runs(self, tmp_path, *records) -> object:
        d = tmp_path / "runs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "evidence.jsonl").write_text(
            "\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return d

    def _open(self, module, cfg, purpose=""):
        return {"record_type": "run_context_open", "module": module,
                "purpose": purpose, "config_snapshot": cfg}

    def test_an_accept_child_s_own_run_dir_yields_the_reference_date(self, tmp_path):
        """The defect: an accept run records no M3, so this returned the two
        solver-pinning fields and silently not the third."""
        from mre.modules.scenario import derive_base_context

        runs = self._runs(
            tmp_path,
            self._open("M5", {"horizon_start": "2026-01-05T00:00:00+00:00",
                              "horizon_end": "2026-02-05T00:00:00+00:00",
                              "reference_date": "2026-01-05T00:00:00+00:00"},
                       "planner-edit model build"),
            self._open("M6", {"num_search_workers": 1, "random_seed": 42,
                              "time_limit": 120.0}, "planner-edit re-solve"),
        )
        ctx = derive_base_context(runs)
        assert ctx["reference_date"] == "2026-01-05T00:00:00+00:00"
        assert ctx["solver_workers"] == 1 and ctx["solver_seed"] == 42

    def test_m3_still_wins_on_a_root_run(self, tmp_path):
        """NO FIELD DRIFT FOR ORDINARY RUNS. M3 is the root pipeline's own
        statement of the reference date and stays authoritative; the M5 read is
        a fallback for runs that have no M3 at all."""
        from mre.modules.scenario import derive_base_context

        runs = self._runs(
            tmp_path,
            self._open("M3", {"reference_date": "2026-01-05T00:00:00+00:00"},
                       "validator"),
            self._open("M5", {"reference_date": "2025-12-01T00:00:00+00:00"},
                       "rolling window-0 model build"),
        )
        assert derive_base_context(runs)["reference_date"] == \
            "2026-01-05T00:00:00+00:00"

    def test_a_null_reference_date_recovers_nothing(self, tmp_path):
        """The write records ``None`` when the build had no reference date. A
        recovered ``None`` would be worse than an absence — it is the absence
        that the caller's own ``_parse_ref_date`` already handles."""
        from mre.modules.scenario import derive_base_context

        runs = self._runs(tmp_path, self._open("M5", {"reference_date": None}))
        assert "reference_date" not in derive_base_context(runs)

    def test_the_literal_now_is_not_a_date(self, tmp_path):
        from mre.modules.scenario import derive_base_context

        runs = self._runs(tmp_path, self._open("M5", {"reference_date": "now"}))
        assert "reference_date" not in derive_base_context(runs)


# ---------------------------------------------------------------------------
# The same ruling, on a REAL rolling board, through the REAL accept path
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rolling_board(tmp_path_factory):
    """A real sliced solve, so the parent genuinely carries a rolling block and
    a plan of record narrower than its snapshot."""
    from fastapi.testclient import TestClient

    from mre.api.app import create_app
    from tools.generate_erp_dataset import generate

    root = tmp_path_factory.mktemp("ch1_data")
    sub_src = tmp_path_factory.mktemp("ch1_sub") / "pilot"
    generate(sub_src, scenario="pilot_scale", orders=40, seed=1)
    client = TestClient(create_app(data_root=root))
    sub = client.post("/submissions", json={"path": str(sub_src)}).json()["data"]
    assert sub["grade"] == "ACCEPTED"
    solve = client.post(
        f"/submissions/{sub['submission_id']}/solve",
        json={"sliced": True, "window_days": 14, "frozen_days": 3,
              "time_limit": 10, "deterministic": True, "sync": True,
              "portfolio_k": 1},
    ).json()["data"]
    run = client.get(f"/runs/{solve['run_id']}").json()["data"]
    assert run["status"] == "succeeded", run.get("error")
    schedule_id = run["result"]["schedule_id"]
    doc = client.get(f"/schedules/{schedule_id}").json()["data"]
    assert doc.get("rolling"), "the fixture is not rolling — nothing to inherit"
    return SimpleNamespace(client=client, root=root, schedule_id=schedule_id,
                           doc=doc)


@pytest.fixture(scope="module")
def accept_child(rolling_board):
    """ONE real accept through ``POST /schedules/{id}/accept`` — the whole
    ceremony, not the module underneath it."""
    doc = rolling_board.doc
    bar = next(a for a in doc["assignments"]
               if a.get("commitment_state") == "active_window" and a.get("chunks"))
    resp = rolling_board.client.post(
        f"/schedules/{rolling_board.schedule_id}/accept",
        json={"pin_op_id": bar["operation_ref"],
              "pin_resource_id": bar["resource_id"],
              "pin_start_iso": bar["chunks"][0]["start"],
              "authority": "r4.2-test", "budget_s": 120.0})
    assert resp.status_code == 201, resp.text
    child_id = resp.json()["data"]["schedule_id"]
    child = rolling_board.client.get(f"/schedules/{child_id}").json()["data"]
    return SimpleNamespace(id=child_id, doc=child, parent=doc,
                           client=rolling_board.client, root=rolling_board.root)


@pytest.mark.slow
class TestAcceptChildOnARealBoard:

    def test_the_child_of_a_rolling_board_is_rolling(self, accept_child):
        """The regression for the whole arc. Before R-CH1 this was False by
        construction and the next gesture was handed the WHOLE PLANT."""
        assert accept_child.doc.get("rolling") is not None

    def test_the_window_and_the_frozen_front_are_the_parent_s(self, accept_child):
        p, c = accept_child.parent["rolling"], accept_child.doc["rolling"]
        for field in ("reference_origin", "window_start", "window_end",
                      "frozen_until", "window_days", "frozen_days"):
            assert c[field] == p[field], field

    def test_the_tray_comes_across_whole(self, accept_child):
        p, c = accept_child.parent["rolling"], accept_child.doc["rolling"]
        assert ([b["demand_ref"] for b in c["beyond_horizon"]]
                == [b["demand_ref"] for b in p["beyond_horizon"]])

    def test_every_bar_carries_a_commitment_state(self, accept_child):
        states = [a.get("commitment_state") for a in accept_child.doc["assignments"]]
        assert states and all(s in ("committed", "active_window") for s in states)
        roll = accept_child.doc["rolling"]
        assert roll["committed_count"] == states.count("committed")
        assert roll["active_count"] == states.count("active_window")
        assert roll["committed_count"] + roll["active_count"] == len(states)

    def test_the_child_places_exactly_the_parent_s_plan(self, accept_child):
        assert ({a["operation_ref"] for a in accept_child.doc["assignments"]}
                == {a["operation_ref"] for a in accept_child.parent["assignments"]})

    def test_the_child_document_is_contract_valid(self, accept_child):
        """The same validation the parent's kind passes — a rolling document
        assembled a different way is still a rolling document."""
        ScheduleDocument.model_validate(accept_child.doc)

    def test_the_reference_date_is_recoverable_from_the_child_s_own_run_dir(
            self, accept_child):
        """CLAUSE (2), AS A RECOVERY. Nine of ``derive_base_context``'s eleven
        callers do not walk to the root run; all nine were correct on a base run
        and wrong on a child."""
        from mre.modules.scenario import derive_base_context

        runs = accept_child.root / "runs" / accept_child.doc["run_id"] / "runs"
        ctx = derive_base_context(runs)
        assert ctx.get("reference_date"), (
            "the child's own run dir yields no reference date — every "
            "non-walking caller will build a model in the wrong frame")
        assert ctx.get("solver_workers") == 1
        assert ctx.get("solver_seed") is not None

    def test_the_child_declares_the_plant_s_calibration(self, accept_child):
        """The child says exactly what its parent says about this plant, and
        never more.

        The fixture's data root holds no measured profile, so the parent's own
        state is ``absent`` — "nobody has measured this plant", said out loud
        (R-CAL1 rule 3). That is a real declaration and inheriting it is the
        point: before this ruling the child declared NOTHING, which is not the
        same statement.

        **The precondition is asserted rather than assumed.** If the parent ever
        stops carrying a block, the comparison below would pass by comparing two
        absences, which is the empty-denominator shape this repo keeps catching.

        NAMED LIMIT: the parent's ``applied`` is already empty on this fixture
        (nothing was applied because nothing was measured), so the
        clause-(3) CLEARING of applied coefficients is not exercised here. It is
        exercised by ``TestCalibrationInheritance`` above and, at demo density,
        by the gen-3 measurement in the close-out (parent True -> child False)."""
        p = (accept_child.parent.get("solver") or {}).get("calibration")
        c = (accept_child.doc.get("solver") or {}).get("calibration")
        assert p is not None, (
            "the PARENT carries no calibration block, so this test would "
            "compare two absences and prove nothing (R-CAL1 rule 3 says the "
            "solve declares one even when the answer is no)")
        assert c is not None, "the child dropped its parent's declaration"
        assert c["state"] == p["state"]
        assert c["plant_key"] == p["plant_key"]
        assert c["profile_id"] == p["profile_id"]
        assert accept_child.parent["schedule_id"] in c["sentence"]
        assert not c["applied"], "the accept did not run at the coefficients"

    def test_the_child_carries_no_portfolio(self, accept_child):
        assert (accept_child.doc.get("solver") or {}).get("portfolio") is None

    def test_the_gesture_path_now_scopes_itself_from_the_child(self, accept_child):
        """The mechanism the whole ruling exists for: ``_rolling_gesture_context``
        returns ``(None, [])`` on a document with no rolling block, and beat one
        then rebuilt the WHOLE PLANT."""
        from mre.api.app import _rolling_gesture_context

        row = {"document_path": str(_document_path(accept_child))}
        window_op_ids, _pins = _rolling_gesture_context(row)
        assert window_op_ids is not None
        assert window_op_ids == {a["operation_ref"]
                                 for a in accept_child.doc["assignments"]}

    def test_beat_one_on_the_child_renders_a_verdict_without_a_frame_error(
            self, accept_child):
        """b5daba66's founding symptom, on a sound child. R-SG1 turned the
        mis-framed case into a loud typed refusal; this asserts the child is not
        that case — and that the verdict it does render is a real one."""
        bar = next(a for a in accept_child.doc["assignments"]
                   if a.get("commitment_state") == "active_window" and a.get("chunks"))
        at = datetime.fromisoformat(bar["chunks"][0]["start"]) + timedelta(minutes=30)
        resp = accept_child.client.post(
            f"/schedules/{accept_child.id}/sandbox/feasibility",
            json={"pin_op_id": bar["operation_ref"],
                  "pin_resource_id": bar["resource_id"],
                  "pin_start_iso": at.isoformat(), "deterministic": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["verdict"] in ("possible", "impossible")


@pytest.mark.slow
class TestTheAuditCeremonyRecordsItsFrameToo:
    """THE THIRD MEMBER OF THE CLASS, found by censusing it rather than fixing
    the seam the dossier named.

    ``materialize_audit_offer`` recorded neither the reference date NOR the
    horizon on its M5 model build, so an audit-accept child was not merely
    dateless: ``_m5_horizon`` on its own run dir raised "M5 run evidence carries
    no horizon" and every sandbox surface pointed at that child failed outright.

    The ceremony writes its M5 record BEFORE it decides whether the deeper
    search found anything, so this exercises the real write on a board whose
    incumbent holds — which is what this fixture's does. The refusal is the
    positive control that the ceremony genuinely ran."""

    def test_the_audit_offer_records_the_horizon_and_the_reference_date(
            self, rolling_board, tmp_path):
        from mre.modules import longpath
        from mre.modules.sandbox import materialize_audit_offer
        from mre.modules.scenario import derive_base_context
        from mre.modules.solution_pool import _m5_horizon, _read_evidence

        base_run_dir = rolling_board.root / "runs" / rolling_board.doc["run_id"]
        snap = rolling_board.doc["snapshot_id"]
        out = tmp_path / "audit_child"
        longpath.copytree(base_run_dir / "snapshots" / snap,
                          out / "snapshots" / snap)
        window_ops = {a["operation_ref"] for a in rolling_board.doc["assignments"]}
        base_ctx = derive_base_context(base_run_dir / "runs")
        assert base_ctx.get("reference_date"), "the BASE run has no date to pass on"

        with pytest.raises(RuntimeError, match="nothing accepted"):
            materialize_audit_offer(
                out, snap, authority="r4.2-test",
                base_runs_dir=base_run_dir / "runs",
                reference_date_raw=base_ctx["reference_date"],
                standing_pins=[], restrict_op_ids=window_ops)

        evidence = _read_evidence(out / "runs")
        start, end = _m5_horizon(evidence)      # raised before this ruling
        assert start < end
        assert derive_base_context(out / "runs").get("reference_date") ==             base_ctx["reference_date"]


def _document_path(accept_child) -> object:
    return (accept_child.root / "runs" / accept_child.doc["run_id"]
            / "schedule_document.json")


@pytest.fixture(scope="module")
def monolithic_child(tmp_path_factory):
    """A MONOLITHIC parent, accepted onto. Module-scoped so the two assertions
    below share one solve."""
    from fastapi.testclient import TestClient

    from mre.api.app import create_app
    from tools.generate_erp_dataset import generate

    root = tmp_path_factory.mktemp("ch1_mono_data")
    sub_src = tmp_path_factory.mktemp("ch1_mono_sub") / "small"
    generate(sub_src, scenario="clean_small", orders=8, seed=1)
    client = TestClient(create_app(data_root=root))
    sub = client.post("/submissions", json={"path": str(sub_src)}).json()["data"]
    solve = client.post(
        f"/submissions/{sub['submission_id']}/solve",
        json={"sliced": False, "time_limit": 60, "deterministic": True,
              "sync": True},
    ).json()["data"]
    run = client.get(f"/runs/{solve['run_id']}").json()["data"]
    assert run["status"] == "succeeded", run.get("error")
    sid = run["result"]["schedule_id"]
    doc = client.get(f"/schedules/{sid}").json()["data"]
    assert doc.get("rolling") is None, "the fixture is rolling — wrong control"
    bar = next(a for a in doc["assignments"] if a.get("chunks"))
    resp = client.post(f"/schedules/{sid}/accept", json={
        "pin_op_id": bar["operation_ref"],
        "pin_resource_id": bar["resource_id"],
        "pin_start_iso": bar["chunks"][0]["start"],
        "authority": "r4.2-test", "budget_s": 60.0})
    assert resp.status_code == 201, resp.text
    child_id = resp.json()["data"]["schedule_id"]
    return client.get(f"/schedules/{child_id}").json()["data"]


@pytest.mark.slow
class TestMonolithicParentIsUnchanged:
    """THE TRUE NEGATIVE ON A REAL BOARD. A monolithic parent must keep minting
    monolithic children — this ruling is about matching a parent, not about
    making everything rolling."""

    def test_the_child_is_still_monolithic(self, monolithic_child):
        assert monolithic_child.get("rolling") is None

    def test_no_bar_gained_a_commitment_state(self, monolithic_child):
        assert all(a.get("commitment_state") is None
                   for a in monolithic_child["assignments"])
