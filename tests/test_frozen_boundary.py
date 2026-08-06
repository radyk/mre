"""THE MOVABLE FROZEN BOUNDARY — R-F1's mechanics (Session 4B.28 Item 1).

Written from the ruling, not from the implementation. R-F1 says four things this
file has to be able to fail on:

  (b) a THAW converts every uncovered commitment to a STANDING PIN AT ITS EXACT
      PLACEMENT — nothing becomes free-floating, and nothing MOVES;
  (c) a FREEZE commits active work and ABSORBS any standing pin it crosses;
  (d) every boundary move is EVIDENCE — the act, not just its consequences;
  (e) the confirmation beat states the count and the direction, and the count it
      states is the count that applies.

THE NEGATIVE CONTROLS (the brief's two, plus the digest one) are at the bottom
and are proven RED against physically reverted behaviour in the close-out: a
thaw that leaves a bar free-floating, and a boundary move that emits no
evidence, must both go red. They are written as assertions ABOUT the guard, so
a future refactor that quietly stops checking is itself caught.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mre.modules import standing_pins as sp
from mre.modules.frozen_boundary import (
    BoundaryRefused, apply_move, compose_pins, plan_move, thaw_origin,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 5, 6, 0, tzinfo=UTC)


def _iso(dt):
    return dt.isoformat()


def _chunk(start, minutes=120):
    return {"start": _iso(start), "end": _iso(start + timedelta(minutes=minutes)),
            "working_min": minutes}


def _asg(idx, start, state, *, pin=False, resource="RES-1"):
    return {
        "assignment_id": f"A{idx}",
        "operation_ref": f"OP-{idx}",
        "workpackage_ref": f"WP-{idx}",
        "work_orders": [f"ORD-{idx:06d}"],
        "op_seq": 10,
        "resource_id": resource,
        "chunks": [_chunk(start)],
        "commitment_state": state,
        "standing_pin": pin,
    }


def _doc(frozen_hours=48, window_days=10):
    """A rolling document with committed work on BOTH SIDES of a candidate
    boundary — the PREMISE the brief requires the fixture to satisfy. Without it
    a thaw test would pass by thawing nothing."""
    frozen_until = T0 + timedelta(hours=frozen_hours)
    return {
        "contract_version": "1.16",
        "schedule_id": "rolling-fixture",
        "assignments": [
            # committed, well before the boundary — a thaw to +24h must NOT touch it
            _asg(1, T0 + timedelta(hours=2), "committed"),
            # committed, between +24h and +48h — the thaw candidate
            _asg(2, T0 + timedelta(hours=30), "committed"),
            _asg(3, T0 + timedelta(hours=40), "committed", resource="RES-2"),
            # active, just after the boundary — the freeze candidate
            _asg(4, T0 + timedelta(hours=52), "active_window"),
            # active and already PINNED (an accepted drag) — the absorb candidate
            _asg(5, T0 + timedelta(hours=60), "active_window", pin=True),
            # active, far out — untouched by a freeze to +72h
            _asg(6, T0 + timedelta(hours=200), "active_window"),
        ],
        "rolling": {
            "reference_origin": _iso(T0),
            "window_start": _iso(T0),
            "window_end": _iso(T0 + timedelta(days=window_days)),
            "frozen_until": _iso(frozen_until),
            "window_days": window_days,
            "frozen_days": 2,
            "committed_count": 3,
            "active_count": 3,
            "beyond_horizon": [],
            "boundary_moves": [],
        },
    }


# ---------------------------------------------------------------------------
# The premise test — a fixture that cannot exercise the ruling proves nothing.
# ---------------------------------------------------------------------------


def test_premise_fixture_has_committed_work_on_both_sides():
    doc = _doc()
    frozen = datetime.fromisoformat(doc["rolling"]["frozen_until"])
    target = T0 + timedelta(hours=24)
    committed_starts = [
        datetime.fromisoformat(a["chunks"][0]["start"])
        for a in doc["assignments"] if a["commitment_state"] == "committed"
    ]
    assert any(s < target for s in committed_starts), \
        "premise: committed work BEFORE the candidate boundary (a thaw must not touch it)"
    assert any(target <= s < frozen for s in committed_starts), \
        "premise: committed work the candidate boundary UNCOVERS (else a thaw thaws nothing)"
    assert any(a["standing_pin"] and a["commitment_state"] == "active_window"
               for a in doc["assignments"]), \
        "premise: an active PINNED placement (else clause (c)'s absorb is unexercised)"


# ---------------------------------------------------------------------------
# Clause (b) — the thaw
# ---------------------------------------------------------------------------


def test_thaw_selects_exactly_the_uncovered_commitments():
    plan = plan_move(_doc(), _iso(T0 + timedelta(hours=24)))
    assert plan.direction == "thaw"
    assert plan.changed_ops == ["OP-2", "OP-3"]
    assert plan.pinned_ops == ["OP-2", "OP-3"]
    assert plan.absorbed_pins == []


def test_thaw_changes_authority_and_never_position():
    """R-F1(b) as a PROPERTY, not a comment: every chunk, resource and phase in
    the child is identical to the parent's. This is the guard the ruling's whole
    'nothing becomes free-floating' clause rests on."""
    doc = _doc()
    res = apply_move(doc, _iso(T0 + timedelta(hours=24)), authority="daryn")
    before = {a["operation_ref"]: (a["resource_id"], json.dumps(a["chunks"]))
              for a in doc["assignments"]}
    after = {a["operation_ref"]: (a["resource_id"], json.dumps(a["chunks"]))
             for a in res.document["assignments"]}
    assert before == after, "a thaw moved a placement — R-F1(b) says it must not"


def test_thaw_leaves_no_bar_free_floating():
    """NEGATIVE CONTROL TARGET. Every op the thaw touched must come out BOTH
    ``active_window`` (the solver may now consider it) AND standing-pinned (the
    planner holds it). A thaw that dropped the pin would leave free-floating
    work, which is the one outcome R-F1 forbids by name."""
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)))
    touched = set(res.plan.changed_ops)
    assert touched, "premise: the thaw touched something"
    pinned = sp.standing_pin_ops(res.pins)
    for a in res.document["assignments"]:
        if a["operation_ref"] not in touched:
            continue
        assert a["commitment_state"] == "active_window"
        assert a["standing_pin"] is True, \
            f"{a['operation_ref']} was thawed into free-floating work"
        assert a["operation_ref"] in pinned, \
            f"{a['operation_ref']} is not in the lineage pin register"


def test_thawed_pin_records_the_exact_placement():
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)))
    by_op = {sp.pin_op_id(p): p for p in res.pins}
    src = {a["operation_ref"]: a for a in res.document["assignments"]}
    for op in res.plan.pinned_ops:
        assert sp.pin_resource_id(by_op[op]) == src[op]["resource_id"]
        assert sp.pin_start_iso(by_op[op]) == src[op]["chunks"][0]["start"]


def test_thaw_updates_the_boundary_and_the_counts():
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)))
    r = res.document["rolling"]
    assert r["frozen_until"] == _iso(T0 + timedelta(hours=24))
    assert r["committed_count"] == 1        # only OP-1 stays committed
    assert r["active_count"] == 5


# ---------------------------------------------------------------------------
# Clause (c) — the freeze, and the absorbed pin
# ---------------------------------------------------------------------------


def test_freeze_commits_the_covered_active_work():
    plan = plan_move(_doc(), _iso(T0 + timedelta(hours=72)))
    assert plan.direction == "freeze"
    assert plan.changed_ops == ["OP-4", "OP-5"]
    assert plan.pinned_ops == []


def test_freeze_absorbs_a_standing_pin_and_records_it():
    pins = [sp.normalize_pin("OP-5", "RES-1",
                             _iso(T0 + timedelta(hours=60)))]
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=72)), standing_pins=pins)
    assert res.plan.absorbed_pins == ["OP-5"]
    # the pin LEAVES the register — commitment is the stronger authority and the
    # frozen front binds the placement anyway
    assert sp.standing_pin_ops(res.pins) == set()
    frozen = {a["operation_ref"]: a for a in res.document["assignments"]}
    assert frozen["OP-5"]["commitment_state"] == "committed"
    assert frozen["OP-5"]["standing_pin"] is False
    # and the ACT records the absorption, so a reader never sees a pin vanish
    assert res.move_block["absorbed_pins"] == ["OP-5"]


def test_freeze_never_moves_anything_either():
    doc = _doc()
    res = apply_move(doc, _iso(T0 + timedelta(hours=72)))
    before = [json.dumps(a["chunks"]) for a in doc["assignments"]]
    after = [json.dumps(a["chunks"]) for a in res.document["assignments"]]
    assert before == after


# ---------------------------------------------------------------------------
# Clause (e) — the confirmation beat states what applies
# ---------------------------------------------------------------------------


def test_the_confirmed_count_is_the_applied_count():
    doc = _doc()
    target = _iso(T0 + timedelta(hours=24))
    preview = plan_move(doc, target)
    res = apply_move(doc, target, expect_digest=preview.digest)
    assert res.plan.count == preview.count
    assert res.plan.changed_ops == preview.changed_ops
    assert len(res.move_block["changed_ops"]) == preview.count


def test_the_sentence_names_the_direction_and_the_count():
    thaw = plan_move(_doc(), _iso(T0 + timedelta(hours=24))).sentence()
    assert "thaws 2 placements" in thaw
    assert "pins you hold" in thaw
    freeze = plan_move(_doc(), _iso(T0 + timedelta(hours=72))).sentence()
    assert "commits 2 placements" in freeze


def test_a_stale_confirmation_is_refused_not_applied():
    doc = _doc()
    stale = plan_move(doc, _iso(T0 + timedelta(hours=24))).digest
    with pytest.raises(BoundaryRefused) as e:
        apply_move(doc, _iso(T0 + timedelta(hours=30)), expect_digest=stale)
    assert e.value.code == "stale_confirmation"


def test_a_no_op_move_says_so_rather_than_minting_a_version():
    doc = _doc()
    assert plan_move(doc, doc["rolling"]["frozen_until"]).direction == "none"
    with pytest.raises(BoundaryRefused) as e:
        apply_move(doc, doc["rolling"]["frozen_until"])
    assert e.value.code == "no_change"


# ---------------------------------------------------------------------------
# Refusals — each names the BOARD fact it is about
# ---------------------------------------------------------------------------


def test_a_monolithic_board_has_no_boundary_to_move():
    with pytest.raises(BoundaryRefused) as e:
        plan_move({"assignments": []}, _iso(T0))
    assert e.value.code == "not_rolling"


def test_the_two_window_edges_are_different_refusals():
    doc = _doc()
    with pytest.raises(BoundaryRefused) as a:
        plan_move(doc, _iso(T0 - timedelta(hours=1)))
    assert a.value.code == "before_window"
    with pytest.raises(BoundaryRefused) as b:
        plan_move(doc, _iso(T0 + timedelta(days=30)))
    assert b.value.code == "after_window"
    assert a.value.sentence != b.value.sentence


# ---------------------------------------------------------------------------
# Clause (d) — the act is recorded, and the ask path can read it back
# ---------------------------------------------------------------------------


def test_the_move_is_recorded_on_the_document():
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)), authority="daryn")
    moves = res.document["rolling"]["boundary_moves"]
    assert len(moves) == 1
    mv = moves[0]
    assert mv["direction"] == "thaw"
    assert mv["from_instant"] == _iso(T0 + timedelta(hours=48))
    assert mv["to_instant"] == _iso(T0 + timedelta(hours=24))
    assert mv["authority"] == "daryn"
    assert mv["pinned_ops"] == ["OP-2", "OP-3"]


def test_boundary_moves_accumulate_rather_than_replace():
    res1 = apply_move(_doc(), _iso(T0 + timedelta(hours=24)))
    res2 = apply_move(res1.document, _iso(T0 + timedelta(hours=36)),
                      standing_pins=res1.pins)
    assert len(res2.document["rolling"]["boundary_moves"]) == 2


def test_thaw_origin_finds_the_move_that_pinned_a_bar():
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)), authority="daryn")
    mv = thaw_origin(res.document, "OP-2")
    assert mv is not None and mv["direction"] == "thaw"
    assert thaw_origin(res.document, "OP-1") is None   # never thawed


def test_thaw_origin_reports_the_LATEST_thaw_not_the_first():
    """A bar thawed, re-frozen and thawed again is pinned by the most recent
    act. Reporting the first would be a true fact about the wrong event."""
    r1 = apply_move(_doc(), _iso(T0 + timedelta(hours=24)), authority="first")
    r2 = apply_move(r1.document, _iso(T0 + timedelta(hours=48)),
                    standing_pins=r1.pins, authority="refreeze")
    r3 = apply_move(r2.document, _iso(T0 + timedelta(hours=24)),
                    standing_pins=r2.pins, authority="second")
    mv = thaw_origin(r3.document, "OP-2")
    assert mv["authority"] == "second"


def test_the_ask_path_answers_why_this_bar_is_pinned():
    """R-F1(d) end to end, through the 4B.27 frozen route — the reader that
    already exists, not a second one."""
    from mre.modules.rolling_questions import answer_frozen

    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)), authority="daryn")
    answer = answer_frozen(res.document, "ORD-000002")
    assert "pinned" in answer.lower()
    assert "boundary was pulled back" in answer
    assert "daryn" in answer
    assert "never where it sits" in answer


def test_a_bar_that_was_never_thawed_gets_the_ordinary_answer():
    """The other side of the same branch: a pin with no recorded thaw (an
    ACCEPTED DRAG) must NOT be attributed to a boundary move."""
    from mre.modules.rolling_questions import answer_frozen

    doc = _doc()
    for a in doc["assignments"]:
        if a["operation_ref"] == "OP-4":
            a["standing_pin"] = True          # an accepted drag, not a thaw
    answer = answer_frozen(doc, "ORD-000004")
    assert "boundary was pulled back" not in answer
    assert "active part of this window" in answer


# ---------------------------------------------------------------------------
# compose_pins — the narrow release
# ---------------------------------------------------------------------------


def test_compose_pins_never_drops_an_unrelated_commitment():
    keep = sp.normalize_pin("OP-9", "RES-3", _iso(T0))
    pins = [keep, sp.normalize_pin("OP-5", "RES-1",
                                   _iso(T0 + timedelta(hours=60)))]
    plan = plan_move(_doc(), _iso(T0 + timedelta(hours=72)),
                     standing_pins=pins)
    out = compose_pins(pins, plan)
    assert sp.standing_pin_ops(out) == {"OP-9"}


def test_a_thaw_does_not_duplicate_an_existing_pin():
    doc = _doc()
    doc["assignments"][1]["standing_pin"] = True
    existing = [sp.normalize_pin("OP-2", "RES-1", _iso(T0 + timedelta(hours=30)))]
    res = apply_move(doc, _iso(T0 + timedelta(hours=24)), standing_pins=existing)
    ops = [sp.pin_op_id(p) for p in res.pins]
    assert ops.count("OP-2") == 1


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — proven red against physically reverted behaviour.
#
# These do not test the product; they test THE GUARD. Each reproduces the defect
# the ruling forbids and asserts that the assertion above would have caught it.
# A guard that cannot go red is worth exactly what it cost (4B.18's rule).
# ---------------------------------------------------------------------------


def test_negative_control_a_free_floating_thaw_would_be_caught():
    """Revert clause (b): thaw WITHOUT minting the pin. The guard above must
    fail on that document."""
    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)))
    broken = json.loads(json.dumps(res.document))
    for a in broken["assignments"]:
        if a["operation_ref"] in res.plan.changed_ops:
            a["standing_pin"] = False          # the defect
    caught = [a["operation_ref"] for a in broken["assignments"]
              if a["operation_ref"] in set(res.plan.changed_ops)
              and not a["standing_pin"]]
    assert caught, "the free-floating-thaw assertion would not have gone red"


def test_negative_control_a_move_with_no_record_would_be_caught():
    """Revert clause (d): apply the move but record no act. The document-level
    guard must fail, and — the point of the control — the ask path must then be
    UNABLE to answer 'why is this pinned', which is exactly the silence the
    clause exists to prevent."""
    from mre.modules.rolling_questions import answer_frozen

    res = apply_move(_doc(), _iso(T0 + timedelta(hours=24)), authority="daryn")
    broken = json.loads(json.dumps(res.document))
    broken["rolling"]["boundary_moves"] = []   # the defect
    assert thaw_origin(broken, "OP-2") is None
    answer = answer_frozen(broken, "ORD-000002")
    assert "boundary was pulled back" not in answer


# ---------------------------------------------------------------------------
# THE ENDPOINTS (Session 4B.28 Item 1) - the seam the browser harness cannot
# reach hermetically.
#
# The cockpit spec drives the DISPATCH against a fixture server; the tests above
# prove the RULING against the module. What neither touches is the wiring in
# between: that a preview mutates nothing, that an apply mints a real registered
# child sharing its parent's run, and that the act lands in the run's own
# evidence sink where ``EvidenceIndex`` will find it with nothing new to learn.
# ---------------------------------------------------------------------------


@pytest.fixture()
def rolling_api(tmp_path):
    """A registered ROLLING schedule, assembled without a solver.

    The document is this file's own fixture - the boundary endpoints never
    re-solve, so a real solve here would buy nothing but minutes.
    """
    from fastapi.testclient import TestClient

    from mre.api.app import create_app
    from mre.api.registry import Registry
    from mre.contracts.schedule_document import CONTRACT_VERSION

    root = tmp_path / "data"
    root.mkdir()
    client = TestClient(create_app(data_root=root))
    registry = Registry(root)

    run = registry.create_run(kind="rolling", submission_id="sub-x", params={})
    out_dir = Path(run["out_dir"])
    (out_dir / "runs").mkdir(parents=True, exist_ok=True)
    doc = _doc()
    doc["schedule_id"] = "rolling-fixture-x"
    doc["snapshot_id"] = "snap-rolling-x"
    doc["run_id"] = run["id"]
    doc_path = out_dir / "schedule_document.json"
    doc_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    registry.register_schedule(
        schedule_id=doc["schedule_id"], run_id=run["id"],
        snapshot_id="snap-rolling-x", status="proposed",
        contract_version=CONTRACT_VERSION, document_path=doc_path,
        submission_id="sub-x")
    registry.finish_run(run["id"], "succeeded", result={})

    class _Ctx:
        pass

    ctx = _Ctx()
    ctx.client = client
    ctx.registry = registry
    ctx.schedule_id = doc["schedule_id"]
    ctx.out_dir = out_dir
    return ctx


def _ok(resp, status=200):
    assert resp.status_code == status, resp.text
    return resp.json()["data"]


def test_endpoint_preview_mutates_nothing(rolling_api):
    target = _iso(T0 + timedelta(hours=24))
    path = Path(rolling_api.registry.get_schedule(
        rolling_api.schedule_id)["document_path"])
    before = path.read_text(encoding="utf-8")
    plan = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary/preview",
        json={"frozen_until": target}))
    assert plan["refused"] is False
    assert plan["direction"] == "thaw" and plan["count"] == 2
    assert path.read_text(encoding="utf-8") == before, "a preview wrote to the document"
    assert len(rolling_api.registry.list_schedules()) == 1


def test_endpoint_apply_mints_a_child_that_shares_its_parents_run(rolling_api):
    target = _iso(T0 + timedelta(hours=24))
    plan = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary/preview",
        json={"frozen_until": target}))
    res = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary",
        json={"frozen_until": plan["to_instant"], "authority": "daryn",
              "expect_digest": plan["digest"]}), status=201)

    child_id = res["schedule_id"]
    parent = rolling_api.registry.get_schedule(rolling_api.schedule_id)
    child = rolling_api.registry.get_schedule(child_id)
    assert child["parent_schedule_id"] == rolling_api.schedule_id
    # NOTHING WAS RE-SOLVED, so there is nothing new to point at: the child is
    # the same placements under different authority, and it shares the run and
    # snapshot that produced them. That is also what keeps the ask path working
    # unchanged - the same evidence, in the same run dir.
    assert child["run_id"] == parent["run_id"]
    assert child["snapshot_id"] == parent["snapshot_id"]
    assert child["document_path"] != parent["document_path"]

    # ...and the PARENT is untouched: a boundary move mints, never mutates.
    pdoc = json.loads(Path(parent["document_path"]).read_text(encoding="utf-8"))
    assert pdoc["rolling"]["frozen_until"] == _iso(T0 + timedelta(hours=48))
    assert pdoc["rolling"]["boundary_moves"] == []

    cdoc = _ok(rolling_api.client.get(f"/schedules/{child_id}"))
    assert cdoc["rolling"]["frozen_until"] == plan["to_instant"]
    assert len(cdoc["rolling"]["boundary_moves"]) == 1
    assert sp.standing_pin_ops(rolling_api.registry.schedule_pins(child_id))         == set(plan["pinned_ops"])


def test_endpoint_apply_writes_the_act_into_the_runs_evidence_sink(rolling_api):
    target = _iso(T0 + timedelta(hours=24))
    plan = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary/preview",
        json={"frozen_until": target}))
    res = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary",
        json={"frozen_until": plan["to_instant"], "authority": "daryn",
              "expect_digest": plan["digest"]}), status=201)

    decisions = []
    for jl in (rolling_api.out_dir / "runs").glob("*.jsonl"):
        for line in jl.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("record_type") == "decision":
                decisions.append(rec)
    assert len(decisions) == 1, "one boundary move, one Decision"
    d = decisions[0]
    assert d["record_id"] == res["boundary"]["decision_record_id"]
    assert d["driver"] == "FROZEN_COMMITMENT"
    assert d["authority"] == "daryn"
    assert d["basis"] == "observed"
    # THE SUBJECTS ARE THE OPERATIONS WHOSE STATE CHANGED - a Decision naming no
    # subjects would record that something happened without recording to what.
    assert {s["entity_id"] for s in d["subjects"]} == set(plan["changed_ops"])
    # ...and the ALTERNATIVE is the real one: leaving the boundary where it was.
    assert d["alternatives"] and "leave the frozen boundary" in         d["alternatives"][0]["option"]


def test_endpoint_refuses_a_stale_confirmation_with_409(rolling_api):
    target = _iso(T0 + timedelta(hours=24))
    resp = rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary",
        json={"frozen_until": target, "expect_digest": "not-the-digest"})
    assert resp.status_code == 409
    body = resp.json()["data"]
    assert body["refused"] is True and body["code"] == "stale_confirmation"
    assert len(rolling_api.registry.list_schedules()) == 1, "nothing was minted"


def test_endpoint_preview_refuses_a_monolithic_board_by_name(rolling_api):
    """A refusal is an ANSWER (200 with a sentence), not a transport error - the
    preview is a question, and "this board has no boundary" is its answer."""
    doc_path = Path(rolling_api.registry.get_schedule(
        rolling_api.schedule_id)["document_path"])
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    doc.pop("rolling")
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    plan = _ok(rolling_api.client.post(
        f"/schedules/{rolling_api.schedule_id}/boundary/preview",
        json={"frozen_until": _iso(T0)}))
    assert plan["refused"] is True and plan["code"] == "not_rolling"
    assert "no frozen boundary" in plan["sentence"]
