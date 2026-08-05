"""Is the committed corpus index current with the docs? — the pre-commit check.

Session 4A teaching-graft (d.3), rider R1. THE CORPUS-STALENESS CLASS HAS FOUR
NAMED OCCURRENCES — 4B.33, (c2), the shared-body census micro-session, and (e2)
— and every one of them is the same shape: a session amends `docs/`, forgets to
rebuild `src/mre/corpus_index.json`, and `test_corpus`'s currency gate goes red
somewhere in the middle of a twenty-minute suite. The remedy written down each
time was "remember to rebuild before the suite". **Restraint is not a
mechanism** (R-CM1's own words about the CLAUDE.md budget, one rule over), and
four identical failures is what this repo's law says earns the mechanical fix.

WHAT IT CHECKS, AND WHY THAT AND NOT MORE. Exactly the assertion
`TestCurrency::test_index_matches_the_live_docs` makes: the fingerprint of each
manifest document against the fingerprint the committed index holds. Same
function, one definition — a hook computing its own hash would be a second
opinion that can disagree with the test it is standing in for.

    python tools/check_corpus_currency.py [--staged]

`--staged` is the pre-commit mode: it compares against the **staged** content of
each doc (`git show :path`), not the working tree, because what is about to be
committed is what matters. A doc that is edited but unstaged is not this
commit's problem.

Exit 0 = current. Exit 1 = stale, with the rebuild command printed. Exit 0 is
also returned when the check cannot run at all (no git, no index) — a hook that
blocks commits because it broke is worse than the defect it guards.
"""
from __future__ import annotations

import argparse

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REBUILD = "python tools/build_corpus_index.py"


def _staged_text(rel: str) -> str | None:
    """The STAGED content of a path, or None when it is not staged."""
    try:
        out = subprocess.run(["git", "show", f":{rel}"], cwd=ROOT,
                             capture_output=True, check=False)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staged", action="store_true",
                    help="compare against staged content (pre-commit mode)")
    args = ap.parse_args()

    try:
        # THE CORPUS'S OWN ACCESSOR, not a re-parse of the JSON. The first
        # draft read `payload["documents"]` — the key is `docs` — so the check
        # would have crashed into its own "SKIPPED" branch and reported
        # everything current, forever. A hook that fails open silently is worse
        # than no hook, and this is the ONE definition the currency test uses.
        from mre.modules.corpus import DOCS_DIR, MANIFEST, fingerprint, load_corpus
        corpus = load_corpus()
        if corpus is None:
            raise RuntimeError("the committed corpus index did not load")
        indexed = corpus.doc_fingerprints()
    except Exception as exc:  # noqa: BLE001 — a check that cannot run says so
        print(f"[corpus-currency] SKIPPED — could not load the corpus: {exc}")
        return 0

    stale: list[str] = []
    for doc in MANIFEST:
        rel = f"docs/{doc.filename}"
        if args.staged:
            text = _staged_text(rel)
            if text is None:
                continue          # not staged: not this commit's problem
        else:
            path = DOCS_DIR / doc.filename
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
        if indexed.get(doc.doc_id) != fingerprint(text):
            stale.append(rel)

    if not stale:
        return 0
    where = "staged" if args.staged else "working-tree"
    print("[corpus-currency] THE COMMITTED CORPUS INDEX IS STALE.")
    print(f"[corpus-currency] {where} docs that have moved since it was built:")
    for s in stale:
        print(f"[corpus-currency]     {s}")
    print(f"[corpus-currency] Rebuild it, stage it, and commit again:")
    print(f"[corpus-currency]     {REBUILD}")
    print("[corpus-currency]     git add src/mre/corpus_index.json")
    print("[corpus-currency] (to bypass deliberately: git commit --no-verify)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
