"""M4 — the W4 surface inventory.

Session 4A teaching-graft (e2), measurement M4. The (e) close-out §2(d) says the
counterfactual-vs-driver defect has **two** emitting sites, both in
`renderers.py`, both fixed. This script does not take that on trust: it walks the
renderer with the AST and reports EVERY place that renders a "nothing prevented
it / it was not prevented / nothing was holding it" assertion, together with
whether that place is inside a branch guarded by
`counterfactual_contradicts_driver`.

The census is a PROPERTY, not a hand-written list, because a hand list of sites
is exactly the thing that goes stale — and the reason M4 exists is that F3 must
provably land at every site, not at the sites somebody remembered.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "src" / "mre" / "modules" / "renderers.py"

#: The ASSERTION this ruling forbids beside a constraint-naming driver: a
#: sentence saying the placement was free / unforced. Matched on the rendered
#: STRING, so a site is found by what a planner would read, not by its name.
_ASSERTION_RE = re.compile(
    r"nothing\s+prevented|not\s+prevented|nothing\s+was\s+holding"
    r"|was\s+not\s+forced|nothing\s+has\s+to\s+change", re.IGNORECASE)

#: The neighbouring fact that makes it a contradiction rather than a sentence.
_DRIVER_RE = re.compile(r"records\s+its\s+driver", re.IGNORECASE)

_GUARD = "counterfactual_contradicts_driver"


def _strings(node: ast.AST) -> list[tuple[int, str]]:
    """Every string constant under `node`, with its line — including the pieces
    of an f-string, which is how all of this copy is written."""
    out: list[tuple[int, str]] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append((getattr(n, "lineno", 0), n.value))
    return out


def main() -> int:
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    print(f"M4 — W4 emitting-site census over {TARGET.relative_to(ROOT)}")
    print(f"    assertion shapes : {_ASSERTION_RE.pattern}")
    print(f"    guard            : {_GUARD}()\n")

    sites: list[dict] = []
    for fn in funcs:
        strs = _strings(fn)
        assertion = [(ln, s) for ln, s in strs if _ASSERTION_RE.search(s)]
        if not assertion:
            continue
        driver = [(ln, s) for ln, s in strs if _DRIVER_RE.search(s)]
        guarded = any(
            isinstance(n, ast.Name) and n.id == _GUARD
            for n in ast.walk(fn)) or any(
            isinstance(n, ast.Attribute) and n.attr == _GUARD
            for n in ast.walk(fn))
        sites.append({
            "func": fn.name, "line": fn.lineno, "guarded": guarded,
            "assertion_lines": [ln for ln, _ in assertion],
            "driver_lines": [ln for ln, _ in driver],
            "sample": assertion[0][1].strip()[:90],
        })

    for s in sites:
        flag = "GUARDED    " if s["guarded"] else "UNGUARDED <-"
        print(f"  {flag} {s['func']}  (def line {s['line']})")
        print(f"      assertion at {s['assertion_lines']}"
              f"   driver sentence at {s['driver_lines'] or 'none'}")
        print(f"      {s['sample']!r}")

    unguarded_with_driver = [
        s for s in sites if not s["guarded"] and s["driver_lines"]]
    print(f"\n  sites rendering the assertion            : {len(sites)}")
    print(f"  guarded by {_GUARD}: "
          f"{sum(1 for s in sites if s['guarded'])}")
    print(f"  UNGUARDED *and* rendering a driver line  : "
          f"{len(unguarded_with_driver)}"
          + (f"  -> {[s['func'] for s in unguarded_with_driver]}"
             if unguarded_with_driver else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
