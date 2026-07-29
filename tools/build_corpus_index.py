"""Build the committed corpus index from ``docs/`` (Session 4B.15 Item 1).

    python tools/build_corpus_index.py            # rebuild + write
    python tools/build_corpus_index.py --check    # verify only, exit 1 on drift

THE CURRENCY MECHANISM. ``docs/`` is deliberately NOT in the runtime image — the
Dockerfile copies it into the TEST stage only, and says so. A corpus that read
``docs/`` at runtime would therefore be EMPTY in production rather than merely
stale, which is a worse failure and a silent one.

So the index is PACKAGE DATA at ``src/mre/corpus_index.json``, carrying a sha256
per source document. ``tests/test_corpus.py`` re-fingerprints the live ``docs/``
against it, so editing a spec without rebuilding is a RED TEST. That is the
enforcement: a build-time check, not a promise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from mre.modules.corpus import (  # noqa: E402
    DOCS_DIR, INDEX_PATH, MANIFEST, build_index, fingerprint,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed index matches docs/; write nothing")
    args = ap.parse_args()

    live = {d.doc_id: fingerprint((DOCS_DIR / d.filename).read_text(encoding="utf-8"))
            for d in MANIFEST}

    if args.check:
        if not INDEX_PATH.exists():
            print(f"MISSING: {INDEX_PATH}")
            return 1
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        indexed = {d["doc_id"]: d["sha256"] for d in payload.get("docs", [])}
        drift = [k for k in live if indexed.get(k) != live[k]]
        missing = [k for k in live if k not in indexed]
        if drift or missing:
            for k in sorted(set(drift) | set(missing)):
                print(f"STALE: {k}")
            print("\nRebuild with: python tools/build_corpus_index.py")
            return 1
        print(f"OK — {len(indexed)} documents, index current")
        return 0

    payload = build_index()
    INDEX_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                          encoding="utf-8")
    by_tier: dict[str, int] = {}
    for p in payload["passages"]:
        by_tier[p["tier"]] = by_tier.get(p["tier"], 0) + 1
    print(f"wrote {INDEX_PATH.relative_to(REPO)}")
    print(f"  documents : {len(payload['docs'])}")
    print(f"  passages  : {len(payload['passages'])}  {by_tier}")
    if payload["dropped_undated"]:
        print(f"  DROPPED (undated, historical tier): {payload['dropped_undated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
