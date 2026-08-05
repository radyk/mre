"""Pin a world: write an off-tree capsule of it and record what it is.

R-PW1(5). The day a world is pinned, a copy of it is written OUTSIDE the repo
tree and its sha256 recorded. A pinned world with no off-tree copy is a standing
defect -- which is what 2026-08-04 cost, and the cost was two boards.

The capsule is self-sufficient on purpose. It carries the run directories, the
submission, and a ``PIN.json`` holding the registry rows and the PLACEMENT
DIGEST, so a future session can both restore the world and PROVE the thing it
restored is the thing that was lost. A zip of the run directory alone would
restore bytes nobody could check.

The digest is the same one ``tests/test_calibration.py`` pins and
``restore_pinned_world.py`` verifies -- one definition, three callers.

    python tools/worlds/pin_world.py --schedule rolling-xxxx-xxx
    python tools/worlds/pin_world.py --schedule <id> --out C:/dev/mre_worlds
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path("C:/dev/mre_worlds")


def placement_digest(doc: dict) -> str:
    bars = doc.get("assignments") or []
    payload = sorted(
        (a["operation_ref"], a["resource_id"],
         (a.get("chunks") or [{}])[0].get("start")) for a in bars)
    return hashlib.sha256(
        json.dumps(payload, default=str).encode()).hexdigest()


def _resolve(stored: str, root: Path) -> Path:
    p = Path(stored)
    if p.is_absolute():
        return p
    parts = p.parts
    if parts and parts[0] == "_data":
        return root.joinpath(*parts[1:])
    return root / p


def _lineage(db, schedule_id):
    """The schedule and every descendant, so a capsule holds a whole board."""
    cur = db.execute("SELECT * FROM schedules")
    cols = [d[0] for d in cur.description]
    rows = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    if schedule_id not in rows:
        return None, {}
    keep, frontier = {schedule_id: rows[schedule_id]}, [schedule_id]
    while frontier:
        pid = frontier.pop()
        for sid, r in rows.items():
            if r.get("parent_schedule_id") == pid and sid not in keep:
                keep[sid] = r
                frontier.append(sid)
    return rows[schedule_id], keep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--data-root", default="_data")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--label", default="", help="short name for the ledger row")
    args = ap.parse_args(argv)

    root = (REPO / args.data_root).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "registry.sqlite")

    row, family = _lineage(db, args.schedule)
    if row is None:
        print(f"{args.schedule} is not registered in {root}", file=sys.stderr)
        return 2

    doc_path = _resolve(row["document_path"], root)
    doc = json.loads(doc_path.read_text("utf-8"))
    digest = placement_digest(doc)

    runs, subs, certs = {}, {}, {}
    for s in family.values():
        cur = db.execute("SELECT * FROM runs WHERE id=?", (s["run_id"],))
        rc = [d[0] for d in cur.description]
        for r in cur.fetchall():
            r = dict(zip(rc, r))
            runs[r["id"]] = r
            if r.get("submission_id"):
                c2 = db.execute("SELECT * FROM submissions WHERE id=?",
                                (r["submission_id"],))
                sc = [d[0] for d in c2.description]
                for u in c2.fetchall():
                    subs[r["submission_id"]] = dict(zip(sc, u))
                c3 = db.execute("SELECT * FROM certificates WHERE "
                                "submission_id=?", (r["submission_id"],))
                cc = [d[0] for d in c3.description]
                for c in c3.fetchall():
                    certs[r["submission_id"]] = dict(zip(cc, c))
    db.close()

    pin = {
        "schedule_id": args.schedule,
        "label": args.label,
        "placement_digest": digest,
        "bars": len(doc.get("assignments") or []),
        "ledger_total": round((doc.get("cost_summary") or {}).get("total", 0), 2),
        "contract_version": doc.get("contract_version"),
        "snapshot_id": doc.get("snapshot_id"),
        "lineage": sorted(family),
        "registry": {"schedules": list(family.values()),
                     "runs": list(runs.values()),
                     "submissions": list(subs.values()),
                     "certificates": list(certs.values())},
    }

    zpath = out / f"{args.schedule}.zip"
    if zpath.exists():
        print(f"capsule already exists, refusing to overwrite: {zpath}",
              file=sys.stderr)
        return 1

    n = 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("PIN.json", json.dumps(pin, indent=2, default=str))
        for r in runs.values():
            d = _resolve(r["out_dir"], root)
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    z.write(f, f"runs/{r['id']}/{f.relative_to(d).as_posix()}")
                    n += 1
        for sid, u in subs.items():
            d = _resolve(u["dir"], root)
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    z.write(f, f"submissions/{sid}/"
                               f"{f.relative_to(d).as_posix()}")
                    n += 1

    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    print(f"capsule  : {zpath}")
    print(f"  files  : {n} ({len(runs)} run dir(s), {len(subs)} submission(s))")
    print(f"  bytes  : {zpath.stat().st_size}")
    print(f"  sha256 : {sha}")
    print("")
    print("LEDGER ROW (paste into docs/worlds/LEDGER.md):")
    print(f"| `{args.schedule}` | {args.label or '-'} | {pin['bars']} bars | "
          f"${pin['ledger_total']:,.2f} | `{digest[:16]}…` | "
          f"`{zpath.name}` | `{sha[:16]}…` |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
