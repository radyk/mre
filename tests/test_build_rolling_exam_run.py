"""Cross-module call signatures must match their callees, across the whole repo.

SESSION 4B.25 ITEM 4b WIDENED THIS FILE, because the species it was written for
turned out to have five more members it could not see. The errand-session guard
below reads ONE file -- ``tools/build_rolling_exam_run.py``. The same 4B.8 CU2
rename (``build_rolling_view``: ``det_time -> det_total``) had also been sitting
un-updated in FOUR test files and one other tool since 4B.8, and nothing was red:
every one of those call sites lives inside a ``--runslow``-gated fixture, so the
default suite collected them, skipped them, and reported green.
``tests/test_rolling_two_beat.py`` was the exception that made it visible -- it
is not slow-gated, so it errored 12 times at HEAD and 4B.24 reported it.

``tools/build_rolling_fixture.py`` carried the EXACT defect this file's original
docstring describes: ``build_coarse_zone(det_total=DET_TOTAL)`` against a callee
whose parameter is ``det_time``. The guard existed, was correct, and was pointed
at one file.

So the sweep below binds every call site in ``tests/`` and ``tools/`` against the
live signature of the callee -- in milliseconds, with no solve, and regardless of
whether the test that contains it would ever run.

--- the original errand-session docstring follows ---

The pinned-exam-world BUILDER's call signatures must match their callees.

Errand session (2026-07-28) CU2. ``tools/build_rolling_exam_run.py`` mints the
world that every rolling exam bank asks against -- a 300-question sweep and the
board the founder selects in the cockpit. It had NO test, and it was BROKEN ON
MASTER: 4B.8 CU2 renamed ``build_rolling_view``'s deterministic-budget parameter
``det_time -> det_total``, the builder's call was updated, and the ADJACENT call
to ``build_coarse_zone`` -- whose parameter is still ``det_time``, because a
coarse run's budget is a different quantity -- was renamed along with it. Every
``--register`` run died with TypeError at the coarse zone, after the window-0
solve had already been paid for.

The guard is deliberately STRUCTURAL rather than a full build: it reads the
builder's own source, finds every call it makes to a module-level function this
repo owns, and binds those call sites against the callee's live signature. A
renamed, dropped or re-typed parameter anywhere in that set fails here in
milliseconds instead of eleven seconds into a mint.

What it CANNOT catch is named in ``test_coarse_budget_is_not_the_rolling_total``:
the two budgets hold the same number today, so passing the wrong ONE would bind
cleanly. That case is pinned by value, not by signature.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "tools" / "build_rolling_exam_run.py"

sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "src"))


def _callees() -> dict:
    """name-as-called -> the real function the builder reaches.

    Keyed by the bare name because the builder imports every one of these with
    ``from ... import name`` (deliberately, so the module-load cost lands inside
    main()). A callee absent from this map is simply not checked -- so adding a
    new cross-module call to the builder without extending this map is a silent
    gap, and the coverage assertion below is what makes that gap visible.
    """
    from generate_erp_dataset import generate
    from mre.modules.coarse_horizon import build_coarse_zone
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    return {
        "generate": generate,
        "prepare_plant": prepare_plant,
        "build_rolling_view": build_rolling_view,
        "build_coarse_zone": build_coarse_zone,
        "assemble_rolling_document": assemble_rolling_document,
    }


def _sweep_callees() -> dict:
    """The callee map for the REPO-WIDE sweep (4B.25 Item 4b).

    Wider than ``_callees()`` above: it adds the other cross-module entry points
    whose signatures a caller can drift away from silently -- the full roll, the
    portfolio wrapper, and the audit. A name absent here is simply not checked,
    which is the same stated gap the builder map carries.
    """
    from mre.modules.rolling_horizon import (
        build_rolling_view, run_rolling_horizon, solve_rolling_portfolio,
    )
    from mre.modules.sandbox import audit_incumbent, baseline_window_solve

    out = dict(_callees())
    out.update({
        "run_rolling_horizon": run_rolling_horizon,
        "solve_rolling_portfolio": solve_rolling_portfolio,
        "build_rolling_view": build_rolling_view,
        "audit_incumbent": audit_incumbent,
        "baseline_window_solve": baseline_window_solve,
    })
    return out


def _swept_files() -> list:
    """Every python file in ``tests/`` and ``tools/``. Nothing is excluded: a
    spike script that no longer binds is drift like any other, and the whole
    point of 4B.25's widening is that ``--runslow``-gated and archival code is
    exactly where this species survives."""
    return sorted(
        [p for p in (REPO / "tests").rglob("*.py")]
        + [p for p in (REPO / "tools").rglob("*.py")]
    )


def _call_sites(path: Path = BUILDER) -> list:
    """Every (name, n_positional, keyword-names, lineno) ``path`` calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (func.id if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute) else None)
        if name is None:
            continue
        # A starred call site cannot be bound structurally; none exist today and
        # one appearing is a deliberate change, so fail loudly rather than skip.
        starred = any(isinstance(a, ast.Starred) for a in node.args)
        kwargs = [k.arg for k in node.keywords]
        sites.append((name, len(node.args), kwargs, node.lineno, starred))
    return sites


class _Any:
    """A stand-in argument. Only ARITY and NAMES are under test here."""


def test_builder_call_signatures_match_their_callees():
    callees = _callees()
    failures = []
    checked = set()
    for (name, n_pos, kwargs, lineno, starred) in _call_sites():
        target = callees.get(name)
        if target is None:
            continue
        if starred or None in kwargs:
            failures.append(f"{BUILDER.name}:{lineno} {name}(): starred/**kwargs "
                            f"call site cannot be checked structurally")
            continue
        checked.add(name)
        sig = inspect.signature(target)
        try:
            sig.bind(*[_Any()] * n_pos, **{k: _Any() for k in kwargs})
        except TypeError as exc:
            failures.append(
                f"{BUILDER.name}:{lineno} {name}({', '.join(kwargs)}) does not "
                f"match {target.__module__}.{target.__qualname__}{sig}: {exc}")

    assert not failures, (
        "the pinned-exam-world builder calls a function it no longer matches:\n  "
        + "\n  ".join(failures))

    # Coverage: every callee this guard knows about must actually BE called, or
    # the map has drifted from the builder and is guarding nothing.
    missing = sorted(set(callees) - checked)
    assert not missing, (
        f"{BUILDER.name} no longer calls {missing} -- either the builder changed "
        f"shape or this guard's callee map is stale; fix the map in the same "
        f"commit, do not delete the entry to make this pass.")


# A call site that forwards ``**kwargs`` cannot be bound structurally -- the
# names are not in the source. Unlike the builder-only guard above (one curated
# file, where such a site is a deliberate change and should fail loudly), a
# repo-wide sweep meets legitimate forwarding in test helpers and measurement
# drivers. They are SKIPPED, and the skip is DECLARED here rather than silent:
# a new unbindable site fails the test until someone writes it down, which keeps
# "what this guard does not cover" a reviewed list instead of a growing hole.
# (No silent caps -- 4B.24's rule, applied to a guard's own coverage.)
UNBINDABLE = {
    "tests/test_audit_portfolio.py": {"audit_incumbent"},
    "tests/test_portfolio.py": {"build_rolling_view"},
    "tools/spikes/portfolio_4b25/measure_main_portfolio.py":
        {"solve_rolling_portfolio"},
}


def test_no_call_site_in_tests_or_tools_has_drifted_from_its_callee():
    """4B.25 Item 4b -- the same binding check, over every file in tests/ and
    tools/. This is the seam the builder-only guard could not see."""
    callees = _sweep_callees()
    failures = []
    skipped: dict = {}
    for path in _swept_files():
        try:
            sites = _call_sites(path)
        except SyntaxError as exc:                       # noqa: PERF203
            failures.append(f"{path.relative_to(REPO)}: unparseable ({exc})")
            continue
        for (name, n_pos, kwargs, lineno, starred) in sites:
            target = callees.get(name)
            if target is None:
                continue
            key = path.relative_to(REPO).as_posix()
            rel = f"{key}:{lineno}"
            if starred or None in kwargs:
                skipped.setdefault(key, set()).add(name)
                continue
            sig = inspect.signature(target)
            try:
                sig.bind(*[_Any()] * n_pos, **{k: _Any() for k in kwargs})
            except TypeError as exc:
                failures.append(
                    f"{rel} {name}({', '.join(kwargs)}) does not match "
                    f"{target.__module__}.{target.__qualname__}{sig}: {exc}")

    assert not failures, (
        "a call site no longer matches the function it calls -- a rename or a "
        "dropped parameter reached only some of its callers:\n  "
        + "\n  ".join(failures))

    assert skipped == {k: set(v) for k, v in UNBINDABLE.items()}, (
        "the set of call sites this guard CANNOT check has changed. It is a "
        "declared list, not a filter: a **kwargs forwarding site is invisible "
        "to a structural bind, so adding one narrows the guard and must be "
        "written down in UNBINDABLE in the same commit.\n"
        f"  found:    {ess(skipped)}\n  declared: {ess(UNBINDABLE)}")


def ess(d: dict) -> str:
    return ", ".join(f"{k}:{sorted(v)}" for k, v in sorted(d.items()))


def test_coarse_budget_is_not_the_rolling_total():
    """The signature check above binds cleanly whichever budget is passed, because
    both are floats and both currently read 4.0. This pins the DISTINCTION.

    ``DET_TOTAL`` is the rolling window-0 solve's budget for BOTH STAGES together
    (4B.8 CU2). ``COARSE_DET_TIME`` is what ONE coarse solve gets, and
    ``build_coarse_zone`` runs two of them. If DET_TOTAL is ever retuned, the
    coarse zone must not silently move with it.
    """
    import build_rolling_exam_run as builder
    from mre.modules.coarse_horizon import build_coarse_zone

    default = inspect.signature(build_coarse_zone).parameters["det_time"].default
    assert builder.COARSE_DET_TIME == default == 4.0, (
        "the coarse zone's intended per-run budget is build_coarse_zone's own "
        f"default of 4.0; the builder now declares {builder.COARSE_DET_TIME} "
        f"against a default of {default}")

    src = BUILDER.read_text(encoding="utf-8")
    assert "det_time=COARSE_DET_TIME" in src, (
        "the coarse zone call must name COARSE_DET_TIME, not DET_TOTAL -- the "
        "two are different quantities that happen to hold the same number")


@pytest.mark.parametrize("const,expected", [
    ("ORDERS", 40), ("WINDOW_DAYS", 14), ("FROZEN_DAYS", 3), ("SEED", 42),
])
def test_pinned_world_constants_are_unchanged(const, expected):
    """The exam world is PINNED: a bank graded against a 14-day window is not
    comparable to one graded against any other. Moving these is a deliberate
    re-baseline of every rolling bank, so it must break a test first."""
    import build_rolling_exam_run as builder
    assert getattr(builder, const) == expected
