"""Session W2.3 -- assert a candidate demo board against the gen-2 record.

THE POINT IS THAT IT ASSERTS. The reconstruction session (4x) could prove its
boards were the lost ones only because an instrument had been committed
eighteen days earlier for another purpose; this is that instrument for the
third-generation board, written before the mint rather than after it, so the
figures it checks cannot be back-fitted to whatever came out.

Two halves, deliberately separate:

  IDENTITY  the gen-3 board must reproduce gen-2's PLAN exactly -- the same
            placement digest, bar count, ledger and portfolio story. HEAD has
            moved 1.15 -> 1.17 underneath, and R-SP1's clause that "the
            callback must not perturb" is precisely the claim under test: a
            search history and a first-incumbent capture were added to every
            solve between the two mints. If the digest moves, this session
            STOPS and diffs rather than pinning.

  NEW       what gen-3 must carry that gen-2 cannot -- `solver.progress` with
            the R-SP1 AMENDMENT 1 priced pair, and the contract-1.17
            `statistics` rollups. The bridge check (final_plan_cost == the
            shipped ledger, to the cent) is the amendment's own self-proof
            re-run on a real 386-bar board rather than an 8-job specimen.

    python tools/spikes/gen3_demo_world/verify_gen3.py --schedule <id>

Exit 0 only when every assertion holds. Every check prints its verdict, so a
partial failure is legible rather than a stack trace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# THE GEN-2 RECORD. Every figure here is quoted from a committed source, not
# from a run: docs/worlds/LEDGER.md, the capsule's own PIN.json, and CLAUDE.md's
# demo-board block. They are the claim the mint has to meet.
# ---------------------------------------------------------------------------
GEN2_DIGEST = "8071cdaaf953bc17a952b679c2d055c5ae414264720edae229a4a1eb17ed583a"
GEN2 = {
    "bars": 386,
    "ledger": 1667467.80,
    "committed": 24,
    "tray": 122,
    "k": 3,
    "seed0": 42,
    "winner_seed": 44,
    "spread_pct": 28.0606,
    "spread_abs": 467901.83,
    "members": {42: 2135369.63, 43: 1801222.70, 44: 1667467.80},
    "det_time_s": 10.0,
    "gap_pct_1dp": 89.6,
}


def placement_digest(doc: dict) -> str:
    """R-PW1's ONE definition, copied from tools/worlds/pin_world.py."""
    bars = doc.get("assignments") or []
    payload = sorted(
        (a["operation_ref"], a["resource_id"],
         (a.get("chunks") or [{}])[0].get("start")) for a in bars)
    return hashlib.sha256(
        json.dumps(payload, default=str).encode()).hexdigest()


class Checks:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str, str]] = []

    def eq(self, name, got, want, fmt=str):
        ok = got == want
        self.rows.append((ok, name, fmt(got), fmt(want)))
        return ok

    def close(self, name, got, want, tol=0.005, fmt=lambda v: f"{v:,.2f}"):
        ok = got is not None and abs(got - want) <= tol
        self.rows.append((ok, name, "None" if got is None else fmt(got),
                          fmt(want)))
        return ok

    def truthy(self, name, got, note=""):
        ok = bool(got)
        self.rows.append((ok, name, repr(got)[:48], note or "truthy"))
        return ok

    def report(self, title) -> bool:
        print(f"\n{title}")
        print("-" * 78)
        for ok, name, got, want in self.rows:
            mark = "OK  " if ok else "FAIL"
            print(f"  {mark} {name:<44} {got:>16}"
                  + ("" if ok else f"   want {want}"))
        return all(r[0] for r in self.rows)


def load(schedule_id: str, data_root: Path) -> dict:
    db = sqlite3.connect(data_root / "registry.sqlite")
    row = db.execute("SELECT document_path FROM schedules WHERE id=?",
                     (schedule_id,)).fetchone()
    db.close()
    if row is None:
        raise SystemExit(f"{schedule_id} is not registered in {data_root}")
    return json.loads(Path(row[0]).read_text("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--data-root", default="_data")
    args = ap.parse_args(argv)

    root = (REPO / args.data_root).resolve()
    doc = load(args.schedule, root)
    solver = doc.get("solver") or {}
    rolling = doc.get("rolling") or {}
    cs = doc.get("cost_summary") or {}

    # ------------------------------------------------------------------
    # HALF ONE -- IDENTITY against gen-2
    # ------------------------------------------------------------------
    c = Checks()
    dig = placement_digest(doc)
    c.eq("placement digest", dig, GEN2_DIGEST, lambda v: v[:16] + "...")
    c.eq("bars", len(doc.get("assignments") or []), GEN2["bars"])
    c.close("ledger total", cs.get("total"), GEN2["ledger"])
    c.eq("committed operations", rolling.get("committed_count"),
         GEN2["committed"])
    c.eq("beyond-horizon tray", len(rolling.get("beyond_horizon") or []),
         GEN2["tray"])

    p = solver.get("portfolio") or {}
    c.eq("portfolio K", p.get("k"), GEN2["k"])
    c.eq("portfolio seed0", p.get("seed0"), GEN2["seed0"])
    c.close("portfolio per-member budget", p.get("det_time_s"),
            GEN2["det_time_s"], tol=1e-9, fmt=lambda v: f"{v:.1f}")
    c.eq("winner seed", p.get("winner_seed"), GEN2["winner_seed"])
    c.close("winner ledger total", p.get("winner_ledger_total"),
            GEN2["ledger"])
    c.close("spread abs", p.get("spread_abs"), GEN2["spread_abs"])
    c.close("spread pct", p.get("spread_pct"), GEN2["spread_pct"], tol=0.0005,
            fmt=lambda v: f"{v:.4f}")
    got_members = {m["seed"]: round(m["ledger_total"], 2)
                   for m in (p.get("members") or [])}
    for seed, want in GEN2["members"].items():
        c.close(f"member seed {seed}", got_members.get(seed), want)
    gap = solver.get("gap")
    c.close("gap (1dp)", None if gap is None else round(gap * 100, 1)
            if gap <= 1 else round(gap, 1), GEN2["gap_pct_1dp"], tol=0.05,
            fmt=lambda v: f"{v:.1f}%")
    identity_ok = c.report(f"IDENTITY -- {args.schedule} against gen-2 "
                           f"(rolling-c32a6140-b6b)")

    # ------------------------------------------------------------------
    # HALF TWO -- what gen-3 carries that gen-2 could not
    # ------------------------------------------------------------------
    n = Checks()
    n.eq("contract version", doc.get("contract_version"), "1.17")
    pr = solver.get("progress") or {}
    n.truthy("solver.progress present", bool(pr), "the trail (R-SP1)")
    n.eq("trail priced (AMENDMENT 1)", pr.get("priced"), True)
    n.truthy("trail window_key (clause 1)", pr.get("window_key"),
             "per-window, never summed")
    n.truthy("trail incumbent count", (pr.get("count") or 0) > 1,
             "more than one incumbent")
    # THE BRIDGE SELF-PROOF, on a real board. The first plan's price is a number
    # nobody can check independently; the final plan's is the ledger everyone
    # can. If the bridge marshals its arguments correctly for one it does for
    # both, and this is the only place that is checkable.
    n.close("bridge final_plan_cost == shipped ledger",
            pr.get("final_plan_cost"), round(cs.get("total") or 0.0, 2))
    n.truthy("first_plan_cost > final_plan_cost",
             (pr.get("first_plan_cost") or 0) > (pr.get("final_plan_cost") or 0),
             "the search improved on itself")
    if pr.get("first_plan_cost") and pr.get("dollar_improvement_abs") is not None:
        n.close("dollar rollup decomposes",
                round(pr["final_plan_cost"] + pr["dollar_improvement_abs"], 2),
                round(pr["first_plan_cost"], 2), tol=0.011)

    st = doc.get("statistics") or {}
    n.truthy("statistics block present", bool(st), "contract 1.17")
    n.truthy("late_demands stored", st.get("late_demands") is not None)
    n.truthy("on_time_demands stored", st.get("on_time_demands") is not None)
    n.truthy("changeover_minutes stored",
             st.get("changeover_minutes") is not None)
    util = st.get("utilization_by_resource") or {}
    n.truthy("utilization_by_resource stored", bool(util))
    rated = [u["utilization"] for u in util.values()
             if u.get("utilization") is not None]
    n.truthy("utilization has a denominator somewhere", bool(rated),
             "a ratio with no denominator is the 4B.20 defect")
    if rated:
        top = sorted(rated, reverse=True)[:3]
        n.truthy("busiest machine reads like a real shop (>=50%)",
                 top and top[0] >= 0.50,
                 f"top three {', '.join(f'{x:.0%}' for x in top)}")
    n.truthy("solver.calibration present (R-CAL1)",
             solver.get("calibration") is not None)
    new_ok = n.report("NEW AT HEAD -- the priced trail and the 1.17 rollups")

    print("\n" + "=" * 78)
    print(f"  IDENTITY {'PASS' if identity_ok else 'FAIL'}    "
          f"NEW {'PASS' if new_ok else 'FAIL'}")
    print(f"  digest  : {dig}")
    print(f"  ledger  : ${cs.get('total', 0):,.2f}")
    if pr:
        print(f"  trail   : ${pr.get('first_plan_cost', 0):,.2f} -> "
              f"${pr.get('final_plan_cost', 0):,.2f} "
              f"({pr.get('dollar_improvement_pct')}%) over "
              f"{pr.get('count')} incumbents")
    print("=" * 78)
    return 0 if (identity_ok and new_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
