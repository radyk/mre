"""Errand 4B.22a Item 3 -- prove the demo board reproduces across PYTHONHASHSEED.

A demo board that does not reproduce cannot be returned to after a laptop
reboot: the deep link would resolve to a schedule whose bars had moved, and
every screenshot, close-out figure and answer taken on it would be about a board
that no longer exists.

`build_rolling_exam_run.py` already re-runs the spine and the window-0 solve
INSIDE ONE PROCESS and requires an identical result (its §DETERMINISM). That
catches an unstable sort or a set iteration reached twice in the same
interpreter. It cannot catch the thing PYTHONHASHSEED changes, because a single
process has ONE hash seed: a `set` or a bare `dict` whose iteration order feeds
the solver would be stable within the process and different in the next one.
Both 4B.22a-era hash-order leaks (the ids_adapter entity write order and the
rolling admitted-set iteration) were exactly that shape.

So this runs the whole path in CHILD PROCESSES, one per seed, and compares a
digest of the placement fingerprint:

    python tools/spikes/demo_board_4b22a/reproduce_across_hashseeds.py \
        --submission <dir> --window-days 14 --frozen-days 1 --seeds 0,1,2

THE SUBMISSION IS GENERATED ONCE AND SHARED. Regenerating per child would put
the generator's own hash-order exposure into the same measurement as the
solver's, and a disagreement would not say which one moved. The generator is
proven separately (`prove_pilot_scale_unchanged.py` compares two runs of it).

Digest inputs, and why each: the committed/active/beyond SPLIT (what the board
draws in which region), every PLACEMENT (resource + start + end), and the solver
STATUS and OBJECTIVE (two boards with identical bars but different reported
proofs are not the same board -- the strip chip would differ).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

CHILD = r'''
import hashlib, json, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, r"{src}")
from mre.modules.rolling_horizon import prepare_plant, build_rolling_view

sub = Path(r"{sub}")
tmp = Path(tempfile.mkdtemp(prefix="hashseed"))
plant = prepare_plant(sub, tmp, reference_date=datetime(2026, 1, 5, tzinfo=timezone.utc))
view = build_rolling_view(plant, window_days={wd}, frozen_days={fd},
                          gravity=True, deterministic=True, seed=42,
                          member_time_limit_s=900.0, det_total={det},
                          persist=False)
fp = {{
    "committed": sorted(view.committed),
    "active": sorted(view.active),
    "beyond": sorted(view.beyond_demand_ids),
    "placements": {{k: (v["resource"], v["start"], v["end"])
                   for k, v in sorted(view.placed.items())}},
    "status": view.status,
    "objective": view.objective,
    "wall_truncated": view.wall_truncated,
}}
blob = json.dumps(fp, sort_keys=True, default=str)
print(json.dumps({{
    "digest": hashlib.sha256(blob.encode()).hexdigest(),
    "committed": len(fp["committed"]), "active": len(fp["active"]),
    "beyond": len(fp["beyond"]), "status": fp["status"],
    "objective": fp["objective"], "wall_truncated": fp["wall_truncated"],
}}))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--submission", required=True)
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--frozen-days", type=int, default=1)
    ap.add_argument("--det-total", type=float, default=6.0,
                    help="must match what the board was minted at; the API's "
                         "default is 6.0 and is not a request field")
    ap.add_argument("--seeds", default="0,1,2")
    args = ap.parse_args(argv)

    src = str(REPO / "src")
    code = CHILD.format(src=src, sub=Path(args.submission).resolve(),
                        wd=args.window_days, fd=args.frozen_days,
                        det=args.det_total)

    out = {}
    for seed in args.seeds.split(","):
        env = dict(os.environ, PYTHONHASHSEED=seed.strip())
        print(f"PYTHONHASHSEED={seed.strip()} ...", flush=True)
        r = subprocess.run([sys.executable, "-c", code], env=env,
                           capture_output=True, text=True, cwd=str(REPO))
        if r.returncode != 0:
            print(r.stdout[-2000:])
            print(r.stderr[-3000:], file=sys.stderr)
            print(f"!! child FAILED at PYTHONHASHSEED={seed}", file=sys.stderr)
            return 1
        row = json.loads(r.stdout.strip().splitlines()[-1])
        out[seed.strip()] = row
        print(f"  digest={row['digest'][:16]}  "
              f"{row['committed']}c/{row['active']}a/{row['beyond']}tray  "
              f"{row['status']} obj={row['objective']} "
              f"truncated={row['wall_truncated']}")

    digests = {v["digest"] for v in out.values()}
    print()
    if len(digests) == 1:
        print(f"IDENTICAL across PYTHONHASHSEED {sorted(out)}: "
              f"{digests.pop()}")
        return 0
    print("!! THE BOARD MOVED BETWEEN HASH SEEDS. It is not a demo board.",
          file=sys.stderr)
    for s, v in out.items():
        print(f"  {s}: {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
