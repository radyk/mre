"""Errand 4B.26 Item 2 -- RENDER THE SWEEP AS THE GRID THAT DECIDES A DEFAULT.

Reads the append-only rows written by `sweep_budget_seed.py` (`sweep.jsonl`) and
by 4B.25's `measure_main_portfolio.py` (`measurements.jsonl`, the 3.0-unit row,
re-used not re-run) and prints:

  1. the (budget x seed) STATUS GRID -- the empty cells are the finding;
  2. the per-cell detail (ledger, det consumed, wall);
  3. the per-budget portfolio summary (publishable of 5, winner, spread, and
     the winner against the seed-42 incumbent).

Plain ASCII, no dependencies. Numbers are printed as measured; nothing here
recomputes a solve.

    python tools/spikes/portfolio_4b25/report_sweep.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: The registered demo board's ledger -- the thing a portfolio must beat to be
#: worth its wall (4B.25 Item 3, reproduced to the cent by seed 42).
INCUMBENT = 2127482.5833333335


def _rows(name: str) -> list:
    p = HERE / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


def _arms() -> list:
    """Every measured arm, oldest first, LAST write per arm label wins."""
    out: dict = {}

    # 4B.25's 3.0-unit sequential row, re-used.
    for r in _rows("measurements.jsonl"):
        if r.get("kind") == "portfolio" and r.get("execution") == "sequential":
            out["demo-3.0"] = {"arm": "demo-3.0", "det_total": 3.0,
                               "world": "demo (280)", "window_days": 10,
                               "wall_total_s": r.get("wall_total_s"),
                               "placed": r.get("placed"),
                               "block": r["block"], "source": "4B.25"}

    for r in _rows("sweep.jsonl"):
        if r.get("kind") != "arm":
            continue
        label = r["arm"]
        world = "demo (280)" if label.startswith("demo") else "mid (170)"
        out[label] = {"arm": label, "det_total": r["det_total"], "world": world,
                      "window_days": r["window_days"],
                      "wall_total_s": r.get("wall_total_s"),
                      "placed": r.get("placed"), "block": r["block"],
                      "source": "4B.26"}
    return list(out.values())


def _fmt_money(v) -> str:
    return "--" if v is None else f"${v:,.2f}"


def main() -> int:
    arms = _arms()
    if not arms:
        print("no measured arms yet")
        return 1

    demo = [a for a in arms if a["world"].startswith("demo")]
    demo.sort(key=lambda a: a["det_total"])
    mid = [a for a in arms if a["world"].startswith("mid")]
    mid.sort(key=lambda a: (a["window_days"], a["det_total"]))

    seeds = [42, 43, 44, 45, 46]

    def grid(group, title, keyfn):
        if not group:
            return
        print(f"\n{title}")
        print("  " + "-" * 62)
        print("  {:<14}".format("budget") + "".join(f"{s:>9}" for s in seeds)
              + "   publishable")
        print("  " + "-" * 62)
        for a in group:
            by = {m["seed"]: m for m in a["block"]["members"]}
            cells = []
            for s in seeds:
                m = by.get(s)
                st = "?" if m is None else (m["status"] or "?")
                cells.append("EMPTY" if st == "UNKNOWN" else st)
            n = len(
                [m for m in a["block"]["members"]
                 if m["selectable"] and m["ledger_total"] is not None])
            print("  {:<14}".format(keyfn(a))
                  + "".join(f"{c:>9}" for c in cells) + f"      {n} of 5")
        print("  " + "-" * 62)
        print("  EMPTY = UNKNOWN, no ledger, ZERO bars published.")

    grid(demo, "STATUS GRID -- demo board (280 orders, window 10 / frozen 1), COLD",
         lambda a: f"{a['det_total']:g} units")
    grid(mid, "STATUS GRID -- mid board (170 orders, frozen 1), COLD, 6.0 units",
         lambda a: f"w{a['window_days']} {a['det_total']:g}u")

    print("\n\nPER-CELL DETAIL")
    print("-" * 96)
    print("{:<18}{:>6}  {:>10}  {:>16}  {:>9}  {:>9}".format(
        "arm", "seed", "status", "ledger", "det", "wall s"))
    print("-" * 96)
    for a in demo + mid:
        for m in a["block"]["members"]:
            det = m["det_consumed"]
            print("{:<18}{:>6}  {:>10}  {:>16}  {:>9}  {:>9}".format(
                a["arm"], m["seed"], m["status"] or "-",
                _fmt_money(m["ledger_total"]),
                "-" if det is None else f"{det:.4f}",
                "-" if m["wall_time_s"] is None else f"{m['wall_time_s']:.1f}"))
        print("-" * 96)

    print("\n\nPER-BUDGET PORTFOLIO SUMMARY  (incumbent = the registered board "
          f"rolling-c9973708-865, {_fmt_money(INCUMBENT)})")
    print("-" * 104)
    print("{:<18}{:>7}  {:>16}  {:>13}  {:>9}  {:>15}  {:>10}".format(
        "arm", "pub/5", "winner ledger", "vs incumbent", "spread%",
        "spread $", "wall s"))
    print("-" * 104)
    for a in demo + mid:
        b = a["block"]
        w = b["winner_ledger_total"]
        n = len([m for m in b["members"]
                 if m["selectable"] and m["ledger_total"] is not None])
        # The incumbent is a fact about the DEMO world. Printing a mid-board
        # ledger against it would put a large, confident, meaningless number in
        # front of a reader -- so the cell is empty and the world column says why.
        delta = ("n/a" if not a["world"].startswith("demo")
                 else "--" if w is None else f"{w - INCUMBENT:+,.2f}")
        sp = b["spread_pct"]
        spa = b["spread_abs"]
        print("{:<18}{:>7}  {:>16}  {:>13}  {:>9}  {:>15}  {:>10}".format(
            a["arm"], f"{n}/5", _fmt_money(w), delta,
            "--" if sp is None else f"{sp:.4f}",
            "--" if spa is None else f"{spa:,.2f}",
            f"{a['wall_total_s']:.1f}" if a["wall_total_s"] else "-"))
    print("-" * 104)
    print("\nNB the 'vs incumbent' column is meaningful only for the demo arms:")
    print("the mid board is a DIFFERENT world and its ledger is not comparable.")

    # -- WHAT K WOULD HAVE BOUGHT --------------------------------------------
    # The members are seeds 42..46 CONSECUTIVE (R-BK1 clause 1), so seeds 42..42+K
    # of a measured arm ARE the K-member portfolio of that arm -- the same fixed
    # set, the same pure selection. No re-solve is needed to read K=1 and K=3 off
    # a K=5 measurement, and none is done here.
    print("\n\nWHAT EACH K WOULD HAVE PUBLISHED  (read off the same members --")
    print("seeds are consecutive, so seeds 42..42+K-1 IS the K-member portfolio)")
    print("-" * 90)
    print("{:<17}{:>3}{:>5}{:>7}{:>17}{:>15}{:>17}".format(
        "arm", "K", "pub", "seed", "winner ledger", "vs incumbent",
        "wall s (K memb)"))
    print("-" * 90)
    for a in demo + mid:
        by = {m["seed"]: m for m in a["block"]["members"]}
        is_demo = a["world"].startswith("demo")
        for k in (1, 3, 5):
            sub = [by[s] for s in range(42, 42 + k) if s in by]
            ok = [m for m in sub
                  if m["selectable"] and m["ledger_total"] is not None]
            wall = sum(m["wall_time_s"] or 0 for m in sub)
            if not ok:
                print("{:<17}{:>3}{:>5}{:>7}{:>17}{:>15}{:>17.1f}".format(
                    a["arm"], k, 0, "--", "EMPTY BOARD", "--", wall))
                continue
            w = min(ok, key=lambda m: (m["ledger_total"], m["seed"]))
            d = (f"{w['ledger_total'] - INCUMBENT:+,.2f}" if is_demo else "n/a")
            print("{:<17}{:>3}{:>5}{:>7}{:>17,.2f}{:>15}{:>17.1f}".format(
                a["arm"], k, len(ok), w["seed"], w["ledger_total"], d, wall))
        print("-" * 90)
    print("\nWall is the SUM OF K MEMBER WALLS, sequential. A PERSISTING solve")
    print("adds one winner re-solve on top (R-BK1: K+1 searches at K>1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
