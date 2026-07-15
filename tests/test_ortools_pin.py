"""Environment-drift guard: the installed ortools MUST match the pyproject pin.

CP-SAT's search is not reproducible across ortools versions when a model has
tied-cost alternatives. Every golden regression baseline in this repo was
captured under a specific ortools build (see docs/04 2026-07-15). If the
installed solver silently drifts from that build, "identical schedule" claims
become unfalsifiable and reproduce-baseline gates can pass or fail for reasons
no one chose. This test turns that drift into a named, immediate failure instead
of a mystery discovered days later.

The pin is read from pyproject.toml (single source of truth) so this guard and
the dependency spec can never disagree.
"""
from __future__ import annotations

import re
from pathlib import Path

import ortools

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _pinned_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    # Match:  "ortools==9.15.6755"  (exact pin only; a range is itself a defect here)
    m = re.search(r'["\']ortools==([0-9]+\.[0-9]+\.[0-9]+)["\']', text)
    assert m, (
        "pyproject.toml must pin ortools to an EXACT version (ortools==X.Y.Z). "
        "An unpinned solver is an unpinned product (docs/04 2026-07-15)."
    )
    return m.group(1)


def test_installed_ortools_matches_pin():
    pinned = _pinned_version()
    installed = ortools.__version__
    assert installed == pinned, (
        f"ortools environment drift: installed {installed!r} != pinned {pinned!r} "
        f"(pyproject.toml). CP-SAT is not reproducible across versions, so the golden "
        f"baselines are only valid under the pin. Either install the pinned build "
        f"(pip install 'ortools=={pinned}') or, if adopting a new build deliberately, "
        f"re-verify/regenerate every golden baseline under it and move the pin in the "
        f"same commit with a docs/04 baseline-epoch ruling."
    )
