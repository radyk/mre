#!/usr/bin/env python3
"""Session 4B.12 — read the 4B.12 result files and answer CU1/CU2/CU3.

  CU1  Where is the cliff NOW, against 4B.10's table, and what did R-PD1 do?
  CU2  The two real densities, F004 and F006, measured rather than inferred.
  CU3  Do the hint arms move a failing cell?

4B.10's trap 2 is kept: a duplicated `(orders, alternates, seed, hint_mode)`
means two writers, and this refuses rather than averages. Rows whose
`wall_truncated` is True are EXCLUDED and NAMED — a wall-stopped solve is a
lottery under this repository's own hard rule, not a measurement.

    python tools/spikes/density_4b12/analyze_4b12.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
B10 = HERE.parent / "density_4b10" / "density.jsonl"


def load(paths) -> list[dict]:
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _check(rows, label):
    keys = [(r["orders"], r["alternates"], r["seed"], r.get("hint_mode", "off"))
            for r in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise SystemExit(f"REFUSING TO ANALYZE {label}: duplicated cells "
                         f"{sorted(dupes)[:6]} — concurrent writers")
    kept = [r for r in rows if not r.get("wall_truncated")]
    dropped = [r for r in rows if r.get("wall_truncated")]
    for r in dropped:
        print(f"  EXCLUDED (wall truncation at {r['wall_ceiling_s']}s): "
              f"o={r['orders']} a={r['alternates']} s={r['seed']} "
              f"h={r.get('hint_mode')} wall={r['wall_time']}s")
    return kept, dropped


def _fmt(v, spec="", dash="-"):
    return dash if v is None else format(v, spec)


# ---------------------------------------------------------------------------
def cu1(new, old):
    print("=" * 118)
    print("CU1 — THE RE-BASELINE.  Same worlds, same order counts, same config;")
    print("      the pipeline is master (R-PD1 admits past-due work).")
    print("=" * 118)
    print("A. WHAT R-PD1 DID TO THE INSTANCE, before any solving")
    print(f"{'ord':>5}{'alt':>4}{'ops 4B.10':>11}{'ops NOW':>9}{'ops/m 10':>10}"
          f"{'ops/m NOW':>11}{'util 10':>9}{'util NOW':>10}"
          f"{'past-due adm':>14}{'sched':>7}")
    for (o, a) in sorted({(r["orders"], r["alternates"]) for r in new}):
        n = [r for r in new if r["orders"] == o and r["alternates"] == a]
        p = [r for r in old if r["orders"] == o and r["alternates"] == a]
        n0, p0 = n[0], (p[0] if p else {})
        pd = f"{n0['n_past_due_admitted']}/{n0['n_past_due_all']}"
        print(f"{o:>5}{a:>4}{_fmt(p0.get('n_free_ops'), 'd'):>11}"
              f"{n0['n_free_ops']:>9}"
              f"{_fmt(p0.get('ops_per_machine'), '.0f'):>10}"
              f"{n0['ops_per_machine']:>11.0f}"
              f"{_fmt(p0.get('utilisation_pct'), '.1f'):>9}"
              f"{n0['utilisation_pct']:>10.1f}"
              f"{pd:>14}"
              f"{n0['n_schedulable']:>7}")

    print("\nB. THE COST PROOF, SIDE BY SIDE")
    print(f"{'ord':>5}{'alt':>4}{'ops/m':>7}{'  4B.10 proved':>15}{'  NOW proved':>14}"
          f"{'proof 10':>10}{'proof NOW':>11}{'gap NOW':>10}{'x harder':>10}")
    for (o, a) in sorted({(r["orders"], r["alternates"]) for r in new}):
        n = [r for r in new if r["orders"] == o and r["alternates"] == a]
        p = [r for r in old if r["orders"] == o and r["alternates"] == a]
        nopt = [r for r in n if r.get("stage1_status") == "OPTIMAL"]
        popt = [r for r in p if r.get("stage1_status") == "OPTIMAL"]
        np_ = [r["det_to_proof"] for r in nopt if r.get("det_to_proof") is not None]
        pp = [r["det_to_proof"] for r in popt if r.get("det_to_proof") is not None]
        gaps = [r["gap"] for r in n if r.get("gap") is not None
                and r.get("stage1_status") != "OPTIMAL"]
        mn = st.median(np_) if np_ else None
        mp = st.median(pp) if pp else None
        print(f"{o:>5}{a:>4}{n[0]['ops_per_machine']:>7.0f}"
              f"{(f'{len(popt)}/{len(p)}' if p else 'n/a'):>15}"
              f"{f'{len(nopt)}/{len(n)}':>14}"
              f"{_fmt(mp, '.4f'):>10}{_fmt(mn, '.4f'):>11}"
              f"{(f'{st.median(gaps)*100:.1f}%' if gaps else '-'):>10}"
              f"{(f'{mn/mp:.0f}x' if (mn and mp) else '-'):>10}")

    print("\nC. THE TARDINESS SPLIT (contract 1.11) — the mechanism")
    print(f"{'ord':>5}{'alt':>4}{'ops/m':>7}{'ledger med':>14}{'tardiness':>13}"
          f"{'floor':>13}{'controllable':>14}{'late dem':>10}")
    for (o, a) in sorted({(r["orders"], r["alternates"]) for r in new}):
        n = [r for r in new if r["orders"] == o and r["alternates"] == a]
        led = [r["ledger_total"] for r in n if r.get("ledger_total")]
        tar = [r.get("ledger_tardiness") or 0 for r in n]
        flo = [r.get("ledger_tardiness_floor") or 0 for r in n]
        con = [r.get("ledger_tardiness_controllable") or 0 for r in n]
        lat = [r.get("late_demands") or 0 for r in n]
        print(f"{o:>5}{a:>4}{n[0]['ops_per_machine']:>7.0f}"
              f"{(st.median(led) if led else 0):>14,.0f}"
              f"{st.median(tar):>13,.0f}{st.median(flo):>13,.0f}"
              f"{st.median(con):>14,.0f}{st.median(lat):>10.0f}")

    print("\nD. TARDINESS ONSET — the first density whose CONTROLLABLE tardiness")
    print("   is nonzero. (The FLOOR is nonzero everywhere past-due work exists;")
    print("   it is not a scheduling decision and cannot drive difficulty.)")
    for a in sorted({r["alternates"] for r in new}):
        seq = sorted({(r["orders"], r["ops_per_machine"]) for r in new
                      if r["alternates"] == a})
        first = None
        for o, opm in seq:
            g = [r for r in new if r["orders"] == o and r["alternates"] == a]
            if any((r.get("ledger_tardiness_controllable") or 0) > 0 for r in g):
                first = (o, opm)
                break
        print(f"    alternates={a}: first nonzero CONTROLLABLE tardiness = {first}")

    print("\nE. CLIFF LOCATION")
    for a in sorted({r["alternates"] for r in new}):
        for label, src in (("4B.10", old), ("NOW  ", new)):
            seq = sorted({(r["orders"], r["ops_per_machine"]) for r in src
                          if r["alternates"] == a})
            last_ok, first_bad = None, None
            for o, opm in seq:
                g = [r for r in src if r["orders"] == o and r["alternates"] == a]
                if g and all(r.get("stage1_status") == "OPTIMAL" for r in g):
                    last_ok = (o, opm)
                elif g and first_bad is None:
                    first_bad = (o, opm)
            print(f"    a={a} {label}: last all-OPTIMAL={last_ok}  "
                  f"first non-OPTIMAL={first_bad}")


# ---------------------------------------------------------------------------
def per_cell(rows, title):
    print("\n" + "=" * 118)
    print(title)
    print("=" * 118)
    print(f"{'ord':>5}{'alt':>4}{'seed':>5}{'hint':>7}{'ops':>6}{'ops/m':>7}"
          f"{'util%':>8}{'S1':>9}{'proof':>9}{'gap':>9}{'p0 det':>8}"
          f"{'s1 det':>8}{'s2 det':>8}{'total det':>10}{'ledger':>14}"
          f"{'floor':>13}{'ctrl':>12}{'wall_s':>8}")
    for r in sorted(rows, key=lambda x: (x["orders"], x["alternates"],
                                         x.get("hint_mode", "off"), x["seed"])):
        print(f"{r['orders']:>5}{r['alternates']:>4}{r['seed']:>5}"
              f"{r.get('hint_mode', 'off'):>7}{r['n_free_ops']:>6}"
              f"{r['ops_per_machine']:>7.0f}{(r['utilisation_pct'] or 0):>8.1f}"
              f"{str(r.get('stage1_status'))[:8]:>9}"
              f"{_fmt(r.get('det_to_proof'), '.3f'):>9}"
              f"{_fmt(r.get('gap'), '.4f'):>9}"
              f"{_fmt(r.get('phase0_det'), '.3f'):>8}"
              f"{_fmt(r.get('stage1_det'), '.3f'):>8}"
              f"{_fmt(r.get('stage2_det'), '.3f'):>8}"
              f"{_fmt(r.get('det_total_consumed'), '.3f'):>10}"
              f"{(r.get('ledger_total') or 0):>14,.0f}"
              f"{(r.get('ledger_tardiness_floor') or 0):>13,.0f}"
              f"{(r.get('ledger_tardiness_controllable') or 0):>12,.0f}"
              f"{r['wall_time']:>8.0f}")


def cu3(rows):
    """Arms compared on TOTAL deterministic consumption, per (cell, seed)."""
    arms = defaultdict(dict)
    for r in rows:
        arms[(r["orders"], r["alternates"], r["seed"])][r.get("hint_mode", "off")] = r
    if not any(len(v) > 1 for v in arms.values()):
        return
    print("\n" + "=" * 118)
    print("CU3 — THE HINT ARMS, per seed. Compared on TOTAL consumption (rule a).")
    print("=" * 118)
    print(f"{'ord':>5}{'alt':>4}{'seed':>5}"
          f"{'H0 status':>11}{'H0 gap':>9}{'H0 ledger':>13}"
          f"{'H1 status':>11}{'H1 gap':>9}{'H1 ledger':>13}{'H1 p0':>7}"
          f"{'H2 status':>11}{'H2 gap':>9}{'H2 ledger':>13}{'H2 p0':>7}")
    for k in sorted(arms):
        a = arms[k]
        row = f"{k[0]:>5}{k[1]:>4}{k[2]:>5}"
        for m in ("off", "full", "assign"):
            r = a.get(m)
            if r is None:
                row += f"{'-':>11}{'-':>9}{'-':>13}" + ("" if m == "off" else f"{'-':>7}")
                continue
            row += (f"{str(r.get('stage1_status'))[:9]:>11}"
                    f"{_fmt(r.get('gap'), '.4f'):>9}"
                    f"{(r.get('ledger_total') or 0):>13,.0f}")
            if m != "off":
                row += f"{_fmt(r.get('phase0_det'), '.3f'):>7}"
        print(row)

    # ---- the PAIRED verdict. Arms are compared seed by seed against their own
    # control, never as pooled averages: the cliff is a region where the SEED
    # decides (§5a.27), so a pooled mean over seeds hides the only effect there
    # is. A cell counts as a WIN only if the hinted arm's gap is materially
    # better — 1 percentage point, chosen so solver noise cannot manufacture one.
    EPS = 0.01
    print("\n  PAIRED AGAINST ITS OWN CONTROL (per density, per seed)")
    print(f"{'ord':>5}{'arm':>8}{'n':>4}{'proved H0':>11}{'proved arm':>12}"
          f"{'WIN':>5}{'LOSS':>6}{'TIE':>5}{'median gap H0':>15}{'median gap arm':>16}"
          f"{'median ledger delta':>21}")
    for o in sorted({r["orders"] for r in rows if r["alternates"] == 1}):
        for m in ("full", "assign"):
            pairs = []
            for k, a in arms.items():
                if k[0] != o or "off" not in a or m not in a:
                    continue
                if a["off"]["alternates"] != 1:
                    continue
                pairs.append((a["off"], a[m]))
            if not pairs:
                continue
            def _g(r):
                return 0.0 if r.get("stage1_status") == "OPTIMAL" else (r.get("gap") or 0.0)
            win = sum(1 for c, h in pairs if _g(h) < _g(c) - EPS)
            loss = sum(1 for c, h in pairs if _g(h) > _g(c) + EPS)
            tie = len(pairs) - win - loss
            dl = [100.0 * (h["ledger_total"] - c["ledger_total"]) / c["ledger_total"]
                  for c, h in pairs if c.get("ledger_total") and h.get("ledger_total")]
            print(f"{o:>5}{m:>8}{len(pairs):>4}"
                  f"{sum(1 for c, _ in pairs if c.get('stage1_status')=='OPTIMAL'):>11}"
                  f"{sum(1 for _, h in pairs if h.get('stage1_status')=='OPTIMAL'):>12}"
                  f"{win:>5}{loss:>6}{tie:>5}"
                  f"{st.median([_g(c) for c, _ in pairs])*100:>14.1f}%"
                  f"{st.median([_g(h) for _, h in pairs])*100:>15.1f}%"
                  f"{(f'{st.median(dl):+.2f}%' if dl else '-'):>21}")

    print("\n  VERDICT INPUTS — per arm, over every cell measured")
    for m in ("off", "full", "assign"):
        g = [r for r in rows if r.get("hint_mode", "off") == m]
        if not g:
            continue
        got = [r for r in g if r.get("stage1_status") in ("OPTIMAL", "FEASIBLE")]
        opt = [r for r in g if r.get("stage1_status") == "OPTIMAL"]
        gaps = [r["gap"] for r in g if r.get("gap") is not None]
        print(f"    {m:>7}: n={len(g):>3}  solution found {len(got)}/{len(g)}  "
              f"PROVED {len(opt)}/{len(g)}  "
              f"median gap {(f'{st.median(gaps)*100:.2f}%' if gaps else '-')}")


def main():
    files = sorted(HERE.glob("*.jsonl"))
    if not files:
        raise SystemExit("no result files yet")
    print(f"reading {len(files)} file(s): {', '.join(f.name for f in files)}")
    rows = load(files)
    kept, dropped = _check(rows, "4B.12")
    print(f"rows={len(rows)}  kept={len(kept)}  EXCLUDED={len(dropped)}")
    if kept:
        bad = [r for r in kept if r.get("det_accounting_ok") is False]
        print(f"det-accounting mismatches (phase0+s1+s2 != reported total): {len(bad)}")
    base = [r for r in kept if r.get("hint_mode", "off") == "off"]
    old = load([B10]) if B10.exists() else []
    old = [r for r in old if not r.get("wall_truncated")]
    rebase = [r for r in base if (r["orders"], r["alternates"])
              in {(x["orders"], x["alternates"]) for x in old}]
    if rebase:
        cu1(rebase, old)
    new_cells = [r for r in base if r not in rebase]
    if new_cells:
        per_cell(new_cells, "CU2 — THE REAL DENSITIES (cells 4B.10 did not run)")
    per_cell(kept, "EVERY CELL")
    cu3(kept)


if __name__ == "__main__":
    main()
