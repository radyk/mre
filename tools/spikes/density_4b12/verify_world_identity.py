#!/usr/bin/env python3
"""Session 4B.12 CU1 — PROVE THE RE-BASELINE COMPARED THE SAME WORLDS.

The re-baseline's whole claim is that only the PIPELINE changed between 4B.10
and now. That claim is worthless if the generator moved underneath it: a
different book would explain every difference in the table without R-PD1 having
done anything at all.

4B.10's worlds are still on disk in `_4b10_scratch/sub_o<N>_a<A>`; 4B.12
regenerated its own into `_4b12_scratch` from the same pinned generation seed
(1). This compares them BYTE FOR BYTE, file by file — it does not compare
summaries, and it does not accept a missing file as a match.

`manifest.json` is compared with its two CLOCK fields masked (`generated_at`,
`extract_timestamp`) and nothing else: they are the only values the generator
writes from the wall clock, so an unmasked comparison would fail for a reason
that says nothing about the plant. Every other field, and every other file —
including every data table — is compared raw.

The mask is why this is not the whole proof. The complement is git:
`tools/generate_erp_dataset.py` has not been touched since 4B.10's own commit
(6fa67da), so the generator that wrote both sides is the same generator.

    python tools/spikes/density_4b12/verify_world_identity.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OLD = REPO / "_4b10_scratch"
NEW = REPO / "_4b12_scratch"

#: The only fields allowed to differ: both are written from the wall clock.
_CLOCK_FIELDS = ("generated_at", "extract_timestamp")


def _digest(p: Path) -> str:
    if p.name == "manifest.json":
        m = json.loads(p.read_text(encoding="utf-8"))
        for f in _CLOCK_FIELDS:
            m.pop(f, None)
        blob = json.dumps(m, sort_keys=True).encode("utf-8")
    else:
        blob = p.read_bytes()
    return hashlib.sha256(blob).hexdigest()


def compare(sub: str) -> tuple[bool, list[str]]:
    a, b = OLD / sub, NEW / sub
    if not a.exists():
        return False, [f"{sub}: not in _4b10_scratch (no 4B.10 world to compare)"]
    if not b.exists():
        return False, [f"{sub}: not in _4b12_scratch (4B.12 never built it)"]
    fa = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()}
    problems = [f"{sub}: only in 4B.10: {n}" for n in sorted(fa - fb)]
    problems += [f"{sub}: only in 4B.12: {n}" for n in sorted(fb - fa)]
    for n in sorted(fa & fb):
        if _digest(a / n) != _digest(b / n):
            problems.append(f"{sub}: DIFFERS: {n}")
    return not problems, problems


def main() -> int:
    subs = sorted({p.name for p in OLD.glob("sub_o*")}
                  & {p.name for p in NEW.glob("sub_o*")})
    if not subs:
        print("no shared worlds to compare — nothing proved")
        return 1
    all_ok, out = True, []
    for sub in subs:
        ok, problems = compare(sub)
        all_ok &= ok
        out.extend(problems)
        print(f"  {'IDENTICAL' if ok else 'DIFFERENT':>10}  {sub}")
    if out:
        print("\n".join(out))
    print(f"\n{len(subs)} world(s) compared byte-for-byte "
          f"(manifest clock fields masked): "
          f"{'ALL IDENTICAL' if all_ok else 'MISMATCH — the re-baseline is NOT controlled'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
