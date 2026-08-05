"""R-CM1 clause (3): the CLAUDE.md budget is law, not discipline.

CLAUDE.md is loaded into every session. A maintenance rule asking sessions to
keep it small was written into the file itself on 2026-07-25, was read for
fourteen consecutive sessions, and the file grew from 47,000 characters to
190,354 anyway -- because restraint is not a mechanism. This is the mechanism.

THE COUNTING METHOD IS PART OF THE RULING. Characters are counted as the file
is read from disk: decoded UTF-8, with the file's own line endings intact, so a
CRLF counts as two characters. That is the strictest of the available methods
(the LF-normalised count of the same file is ~2.5k lower) and it is the method
the 190,354 figure that motivated R-CM1 was taken with. Counting the looser way
would quietly hand back headroom the ruling did not grant.

THE REAL CHECK AND THE NEGATIVE CONTROL CALL ONE FUNCTION. `check_budget` is
the only place the comparison happens, so the control cannot pass by exercising
a copy of the assertion while the shipped path is broken -- 4B.28 s5a.123's
species, at the seam where it is cheapest to commit.

What this test does NOT enforce: the 40,000-character phase-exit ceiling
CLAUDE.md names for itself. That is an aspiration checked at phase exits by a
human; encoding it here would fail ordinary pointer-form appends. Nor can any
test check R-CM1 clause (1) -- that a session appends only pointer-form lines --
or the ~15-line diff heuristic that rides on it. Those are close-out
obligations, named as such in docs/04.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"

# R-CM1 clause (3), docs/04 2026-08-05. Raising this is a reviewed change: it
# means the budget moved, and the ruling says the number should move only to
# what a measurement of the real context cost says.
BUDGET_CHARS = 150_000


def measure(path: Path) -> int:
    """Characters as a session reads them: UTF-8, line endings intact."""
    return len(path.read_bytes().decode("utf-8"))


def check_budget(path: Path) -> int:
    """The one comparison. Raises AssertionError over budget; returns the size.

    Both the shipped guard and its negative control go through here.
    """
    size = measure(path)
    assert size <= BUDGET_CHARS, (
        f"{path.name} is {size:,} characters against a {BUDGET_CHARS:,} budget "
        f"({size - BUDGET_CHARS:,} over). R-CM1: prose is born in docs/04 or "
        f"docs/07 and referenced from CLAUDE.md, never written here first. "
        f"Move the overflow, do not raise the budget."
    )
    return size


def test_claude_md_is_within_budget():
    assert CLAUDE_MD.is_file(), f"CLAUDE.md not found at {CLAUDE_MD}"
    check_budget(CLAUDE_MD)


def test_the_budget_is_the_ruled_number():
    """A session quietly raising the bar is the failure mode this catches."""
    assert BUDGET_CHARS == 150_000


def test_measure_counts_crlf_as_two(tmp_path):
    """The counting method is part of the ruling -- pin it, both ways."""
    crlf = tmp_path / "crlf.md"
    crlf.write_bytes(b"ab\r\ncd\r\n")
    assert measure(crlf) == 8

    lf = tmp_path / "lf.md"
    lf.write_bytes(b"ab\ncd\n")
    assert measure(lf) == 6


def test_negative_control_a_padded_file_is_refused(tmp_path):
    """The guard must be able to go red, through the SHIPPED comparison.

    Asserts against a padded COPY rather than mutating the real CLAUDE.md, so
    the control cannot leave the repo dirty. The live padded-CLAUDE.md run is
    recorded in docs/closeouts/maint-claude-md-budget.md.
    """
    original = CLAUDE_MD.read_bytes()
    padded = tmp_path / "CLAUDE.md"

    # Green first: an unpadded copy passes the same function.
    padded.write_bytes(original)
    assert check_budget(padded) == measure(CLAUDE_MD)

    # Then red, on the one byte-count that changed.
    padded.write_bytes(original + b"x" * BUDGET_CHARS)
    with pytest.raises(AssertionError, match="against a 150,000 budget"):
        check_budget(padded)
