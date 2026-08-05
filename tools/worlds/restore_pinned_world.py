"""Restore a pinned world into a data root from a surviving off-tree copy.

R-PW1(2). A world whose OWN DOCUMENT BYTES survive is not reconstructed, it is
RESTORED: the run directory, the submission and the registry rows are copied
back and the original schedule id comes with them, because the id is not being
re-derived from anything -- it is the id that copy has always carried.

That is the only route by which a RETIRED-LOST id may come back. A re-MINT gets
a new id however exactly its placements reproduce, because `schedule_id` is
``f"rolling-{run_id[:12]}"`` over a ``uuid.uuid4()`` run id (``api/registry.py``)
-- content decides nothing about it, so an id carried onto a re-mint would be a
claim about provenance that the bytes do not support.

The restore is REFUSED unless the copied document's placement digest matches the
digest the caller states. That digest is the committed trace of the lost world
(``tests/test_calibration.py::PINNED_WORLDS``), and checking it is what makes
"this is the same world" an assertion rather than a hope.

    python tools/worlds/restore_pinned_world.py \
        --from _4b25_scratch/dataroot --schedule rolling-c9973708-865 \
        --digest ac86d185... [--also-child 4b3acdab-...] [--apply]

Without ``--apply`` it reports what it would do and writes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SCHEDULE_COLS = ["id", "run_id", "submission_id", "snapshot_id", "status",
                 "contract_version", "is_scenario", "parent_schedule_id",
                 "document_path", "created_at", "pins_json"]
RUN_COLS = ["id", "kind", "submission_id", "base_run_id", "snapshot_id",
            "status", "out_dir", "params_json", "result_json", "error",
            "created_at", "finished_at"]
SUB_COLS = ["id", "created_at", "dir", "source"]
CERT_COLS = ["submission_id", "grade", "costing_grade", "json_path", "md_path",
             "created_at"]


def placement_digest(doc: dict) -> str:
    """The digest tests/test_calibration.py pins -- one definition, quoted."""
    bars = doc.get("assignments") or []
    payload = sorted(
        (a["operation_ref"], a["resource_id"],
         (a.get("chunks") or [{}])[0].get("start")) for a in bars)
    return hashlib.sha256(
        json.dumps(payload, default=str).encode()).hexdigest()


def _resolve(stored: str, root: Path) -> Path:
    """A stored path, resolved against the data root it actually lives in.

    The registry holds BOTH forms -- ``out_dir`` absolute, ``dir`` and
    ``document_path`` relative to the repo root as ``_data\\...``. A copy taken
    from a different data root has to repoint the ``_data`` prefix; anything
    already absolute and present is taken as it stands.
    """
    p = Path(stored)
    if p.is_absolute() and p.exists():
        return p
    parts = p.parts
    if parts and parts[0] in ("_data", "dataroot"):
        return root.joinpath(*parts[1:])
    return root / p


def _rows(db: sqlite3.Connection, table: str, col: str, val: str):
    cur = db.execute(f"SELECT * FROM {table} WHERE {col}=?", (val,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", required=True,
                    help="surviving data-root copy")
    ap.add_argument("--to", dest="dst", default="_data")
    ap.add_argument("--schedule", required=True, help="schedule id to restore")
    ap.add_argument("--digest", required=True,
                    help="the committed placement digest of the lost world")
    ap.add_argument("--also-child", action="append", default=[],
                    help="descendant schedule id to restore with it (repeatable)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    src = (REPO / args.src).resolve() if not Path(args.src).is_absolute() \
        else Path(args.src)
    dst = (REPO / args.dst).resolve() if not Path(args.dst).is_absolute() \
        else Path(args.dst)
    sdb_path, ddb_path = src / "registry.sqlite", dst / "registry.sqlite"
    if not sdb_path.exists():
        print(f"no registry at {sdb_path}", file=sys.stderr)
        return 2

    sdb = sqlite3.connect(sdb_path)
    wanted = [args.schedule] + list(args.also_child)
    scheds: list[dict] = []
    for sid in wanted:
        got = _rows(sdb, "schedules", "id", sid)
        if not got:
            print(f"schedule {sid} is not in {sdb_path}", file=sys.stderr)
            return 2
        scheds.append(got[0])

    # THE CHECK THAT MAKES THIS A RESTORE. The named schedule's document must
    # carry the digest the caller states; a child is copied on the parent's
    # authority and states its own digest for the record instead.
    src_doc_path = _resolve(scheds[0]["document_path"], src)
    root_doc = json.loads(src_doc_path.read_text("utf-8"))
    got_dig = placement_digest(root_doc)
    print(f"source document : {src_doc_path}")
    print(f"  schedule_id   : {root_doc.get('schedule_id')}")
    print(f"  bars          : {len(root_doc.get('assignments') or [])}")
    print(f"  ledger        : "
          f"{(root_doc.get('cost_summary') or {}).get('total')}")
    print(f"  contract      : {root_doc.get('contract_version')}")
    print(f"  digest        : {got_dig}")
    if got_dig != args.digest:
        print(f"REFUSED: digest does not match the stated committed trace\n"
              f"  stated : {args.digest}\n  found  : {got_dig}",
              file=sys.stderr)
        return 1
    print("  >>> digest MATCHES the committed trace -- this is the same world")

    runs, subs, certs = {}, {}, {}
    for s in scheds:
        for r in _rows(sdb, "runs", "id", s["run_id"]):
            runs[r["id"]] = r
            if r.get("submission_id"):
                for u in _rows(sdb, "submissions", "id", r["submission_id"]):
                    subs[u["id"]] = u
                for c in _rows(sdb, "certificates", "submission_id",
                               r["submission_id"]):
                    certs[c["submission_id"]] = c
    sdb.close()

    plan = []
    for r in runs.values():
        plan.append((_resolve(r["out_dir"], src), dst / "runs" / r["id"]))
    for u in subs.values():
        plan.append((_resolve(u["dir"], src), dst / "submissions" / u["id"]))

    print("\nwould copy:")
    for a, b in plan:
        print(f"  {a}\n    -> {b}   (exists at source: {a.exists()})")
    print(f"\nregistry rows: {len(subs)} submission(s), {len(certs)} "
          f"certificate(s), {len(runs)} run(s), {len(scheds)} schedule(s)")
    if not args.apply:
        print("\n(dry run -- pass --apply to write)")
        return 0

    for a, b in plan:
        if not a.exists():
            print(f"source missing: {a}", file=sys.stderr)
            return 1
        if b.exists():
            print(f"destination already exists, refusing: {b}", file=sys.stderr)
            return 1
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(a, b)

    def stored(p: Path) -> str:
        """Write paths back in the form the destination root already uses --
        repo-relative under the working `_data`, absolute anywhere else."""
        try:
            return str(p.relative_to(REPO))
        except ValueError:
            return str(p)

    ddb = sqlite3.connect(ddb_path)
    with ddb:
        for u in subs.values():
            u = dict(u)
            u["dir"] = stored(dst / "submissions" / u["id"])
            ddb.execute(
                f"INSERT OR REPLACE INTO submissions ({','.join(SUB_COLS)}) "
                f"VALUES ({','.join('?' * len(SUB_COLS))})",
                [u.get(c) for c in SUB_COLS])
        for c in certs.values():
            c = dict(c)
            sub_dir = dst / "submissions" / c["submission_id"]
            c["json_path"] = stored(sub_dir / Path(c["json_path"]).name)
            c["md_path"] = stored(sub_dir / Path(c["md_path"]).name)
            ddb.execute(
                f"INSERT OR REPLACE INTO certificates ({','.join(CERT_COLS)}) "
                f"VALUES ({','.join('?' * len(CERT_COLS))})",
                [c.get(x) for x in CERT_COLS])
        for r in runs.values():
            r = dict(r)
            r["out_dir"] = stored(dst / "runs" / r["id"])
            ddb.execute(
                f"INSERT OR REPLACE INTO runs ({','.join(RUN_COLS)}) "
                f"VALUES ({','.join('?' * len(RUN_COLS))})",
                [r.get(c) for c in RUN_COLS])
        for s in scheds:
            s = dict(s)
            s["document_path"] = stored(
                dst / "runs" / s["run_id"] / Path(s["document_path"]).name)
            ddb.execute(
                f"INSERT OR REPLACE INTO schedules ({','.join(SCHEDULE_COLS)}) "
                f"VALUES ({','.join('?' * len(SCHEDULE_COLS))})",
                [s.get(c) for c in SCHEDULE_COLS])
    ddb.close()

    # Prove the restore rather than announce it.
    back = json.loads((dst / "runs" / scheds[0]["run_id"] /
                       Path(scheds[0]["document_path"]).name)
                      .read_text("utf-8"))
    dig2 = placement_digest(back)
    ok = dig2 == args.digest and back.get("schedule_id") == args.schedule
    print(f"\nrestored digest : {dig2}")
    print(f"restored id     : {back.get('schedule_id')}")
    print("RESTORED AND VERIFIED" if ok else "RESTORE VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
