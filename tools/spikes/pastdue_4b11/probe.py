#!/usr/bin/env python3
"""Session 4B.11 — THE SPECIMEN PROBE.

One script, run BEFORE and AFTER, so every claim in the close-out is a diff of
the same measurement rather than two differently-shaped observations.

It answers, on `facility_real_pastdue` (60 orders, 21 past due, ref 2026-01-05):

  1. do the past-due demands survive intake (R-PD1 clause 1)?
  2. does GRAVITY prioritize them, or did it have to be told (CU2 b)?
  3. the three measured answers, VERBATIM, driven at the ROUTE level so the
     measurement is deterministic and does not depend on a model parse
     (CU4 a/b/d).
  4. the trailing exclusion note's arithmetic (CU5).
  5. the cost proof the board carries (CU1).

Deterministic: PYTHONHASHSEED=0, workers 1, seed 42.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)
SCRATCH = REPO / "_4b11_scratch"
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"


def oid(d):
    for r in d.get("external_refs") or []:
        if r.get("type") == "order_id":
            return r.get("value")
    return d["id"][:8]


def main():
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    sub = SCRATCH / "sub_pastdue"
    if not (sub / "manifest.json").exists():
        sub.parent.mkdir(parents=True, exist_ok=True)
        generate(sub, scenario="facility_real_pastdue", orders=60, seed=1)

    out = SCRATCH / f"run_{LABEL}"
    plant = prepare_plant(sub, out, reference_date=REF)

    past = [d for d in plant.demands
            if d.get("due") and str(d["due"])[:10] < REF.date().isoformat()]
    excluded = set(plant.excluded_demand_ids)
    sched_ids = {d["id"] for d in plant.schedulable_demands}

    print("=" * 74)
    print(f"1. INTAKE  ({LABEL})")
    print("=" * 74)
    print(f"  demands total           : {len(plant.demands)}")
    print(f"  demands due < ref       : {len(past)}")
    print(f"  excluded_demand_ids     : {len(excluded)}")
    print(f"  past-due AND excluded   : {sum(1 for d in past if d['id'] in excluded)}")
    print(f"  past-due AND schedulable: {sum(1 for d in past if d['id'] in sched_ids)}")

    # persist=True: the window-0 solve is written to the snapshot as a real run,
    # which is what the API's rolling worker does and what the Explainer reads.
    # A persist=False probe measures a snapshot with NO assignments in it and
    # would report "nothing scheduled" for every order, past-due or not.
    view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                              deterministic=True, persist=True,
                              member_time_limit_s=600.0)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc_obj = assemble_rolling_document(plant=plant, view=view,
                                        schedule_id="sched-4b11",
                                        run_id="run-4b11", identity_map=idmap)
    doc = doc_obj.model_dump(mode="json")
    blob = json.dumps(doc, default=str)

    # --- 2. GRAVITY: were they admitted, and in what order? ------------------
    print("\n" + "=" * 74)
    print("2. GRAVITY — ADMITTED, AND WHERE IN THE ORDER?")
    print("=" * 74)
    placed_wos = set()
    for a in doc.get("assignments") or []:
        for wo in a.get("work_orders") or []:
            placed_wos.add(str(wo).upper())
    past_wos = {oid(d).upper() for d in past}
    print(f"  past-due orders PLACED in window 0 : "
          f"{len(past_wos & placed_wos)} of {len(past_wos)}")
    tray = ((doc.get("rolling") or {}).get("beyond_horizon") or [])
    tray_wos = {str(t.get('work_order') or '').upper() for t in tray}
    print(f"  past-due orders in the TRAY        : {len(past_wos & tray_wos)}")
    print(f"  past-due orders NOWHERE            : "
          f"{len(past_wos - placed_wos - tray_wos)}")

    # first-start rank: does past-due work start before on-time work?
    starts: dict[str, str] = {}
    for a in doc.get("assignments") or []:
        ch = a.get("chunks") or []
        s = ch[0].get("start") if ch else None
        for wo in a.get("work_orders") or []:
            w = str(wo).upper()
            if s and (w not in starts or s < starts[w]):
                starts[w] = s
    ranked = sorted(starts.items(), key=lambda kv: kv[1])
    n_past_in_first_q = sum(1 for w, _ in ranked[:max(1, len(ranked) // 4)]
                            if w in past_wos)
    print(f"  placed orders (window 0)           : {len(ranked)}")
    print(f"  past-due among the FIRST QUARTER   : {n_past_in_first_q} "
          f"of {len(past_wos & placed_wos)} past-due placed")
    if ranked:
        print("  first 8 starts:")
        for w, s in ranked[:8]:
            print(f"    {w:<14} {s[:16]}  {'PAST-DUE' if w in past_wos else ''}")

    # --- 3. THE DOCUMENT ------------------------------------------------------
    print("\n" + "=" * 74)
    print("3. CERTIFICATE VISIBILITY")
    print("=" * 74)
    spec = sorted(past, key=lambda x: str(x["due"]))[0]
    spec_order = oid(spec)
    print(f"  specimen: {spec_order} due={str(spec['due'])[:10]}")
    print(f"  document chars                      : {len(blob):,}")
    print(f"  document names the specimen         : {spec_order in blob}")
    solver = doc.get("solver") or {}
    print(f"  solver.status                       : {solver.get('status')}")
    print(f"  solver.gap                          : {solver.get('gap')}")
    print(f"  solver.tiebreak_status              : {solver.get('tiebreak_status')}")
    cs = doc.get("cost_summary") or {}
    print(f"  cost_summary.total                  : {cs.get('total')}")
    print(f"  cost_summary.tardiness              : {cs.get('tardiness')}")
    for k in ("tardiness_floor", "tardiness_controllable"):
        if k in cs:
            print(f"  cost_summary.{k:<22}: {cs.get(k)}")

    # --- 4. THE THREE ANSWERS -------------------------------------------------
    print("\n" + "=" * 74)
    print("4. THE THREE ANSWERS (route-level, deterministic)")
    print("=" * 74)
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.renderers import TemplateRenderer
    from mre.modules.snapshot_store import SnapshotStore

    index = EvidenceIndex().build(out / "runs")
    ex = Explainer(SnapshotStore(out / "snapshots"), index,
                   snapshot_id=plant.snapshot_id)

    def ask(route, **params):
        params.setdefault("question", "")
        b = ex.route(route, params)
        try:
            return TemplateRenderer().render(b)
        except Exception as exc:  # noqa: BLE001
            return f"<render failed: {type(exc).__name__}: {exc}>"

    print(f"\n--- Q1  where is {spec_order}?   [route order-schedule] ---")
    print(ask("order-schedule", order=spec_order,
              question=f"where is {spec_order}?"))
    print(f"\n--- Q2  why isn't {spec_order} scheduled yet?  "
          f"[route why-not-scheduled-yet] ---")
    print(ask("why-not-scheduled-yet", order=spec_order, document=doc,
              question=f"why isn't {spec_order} scheduled yet?"))
    print("\n--- Q3  which orders are already late?  [route late-orders] ---")
    print(ask("late-orders", question="which orders are already late?"))

    # --- 5. THE EXCLUSION ARITHMETIC -----------------------------------------
    print("\n" + "=" * 74)
    print("5. THE EXCLUSION NOTE'S ARITHMETIC (CU5)")
    print("=" * 74)
    summ = ex._excluded_summary()
    print(f"  _excluded_summary(): {json.dumps(summ, default=str)[:400]}")
    labels = sorted(getattr(ex, "_excluded_labels", set()) or set())
    print(f"  _excluded_labels count: {len(labels)}")
    print(f"  sample labels: {labels[:6]}")
    findings = [f for f in index.all_findings()
                if f.get("code") == "TEMPORAL_IMPOSSIBILITY"]
    subs = {s.get("entity_id") for f in findings for s in (f.get("subjects") or [])}
    print(f"  TEMPORAL_IMPOSSIBILITY findings: {len(findings)} "
          f"across {len(subs)} distinct subjects")

    print("\n--- Q4  why were orders excluded?  [route excluded-orders] ---")
    print(ask("excluded-orders", question="why were orders excluded?")[:1400])
    print(f"\n--- Q5  why was {spec_order} excluded?  [route excluded-orders, "
          f"one order] ---")
    print(ask("excluded-orders", order=spec_order,
              question=f"why was {spec_order} excluded?")[:1400])

    # --- 6. THE COST PROOF, VOICED (CU1 b) -----------------------------------
    print("\n" + "=" * 74)
    print("6. THE COST PROOF, VOICED ON A MONEY ANSWER (CU1 b)")
    print("=" * 74)
    from mre.modules.cost_proof import from_evidence
    proof = from_evidence(index)
    print(f"  proof from evidence : status={proof.status} gap={proof.gap_text()}")
    print(f"  strip chip          : {json.dumps(proof.chip(), default=str)}")
    print("\n--- Q6  what is driving the lateness?  [route lateness-cause] ---")
    print(ask("lateness-cause", question="what is driving the lateness?")[:1800])


def reconcile_exclusions():
    """CU5 — PROVE the note reconciles, on a world that HAS exclusions.

    R-PD1 removes the only exclusion the specimen had, so re-running it shows the
    note absent rather than correct. This builds a world with a genuine
    DATA-DEFECT exclusion (a zero-quantity order — clause (2)'s permitted case)
    and checks the arithmetic the 4B.10 note failed:

        scheduled + count == total, and total == demands in the snapshot.
    """
    import csv
    import shutil

    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.renderers import TemplateRenderer
    from mre.modules.rolling_horizon import prepare_plant
    from mre.modules.snapshot_store import SnapshotStore

    src = SCRATCH / "sub_pastdue"
    dst = SCRATCH / "sub_defect"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    rows = list(csv.DictReader((dst / "orders.csv").open(encoding="utf-8")))
    for r in rows[:3]:                       # three genuinely malformed orders
        r["quantity"] = "0"
    with (dst / "orders.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    out = SCRATCH / "run_defect"
    if out.exists():
        shutil.rmtree(out)
    plant = prepare_plant(dst, out, reference_date=REF)
    index = EvidenceIndex().build(out / "runs")
    ex = Explainer(SnapshotStore(out / "snapshots"), index,
                   snapshot_id=plant.snapshot_id)
    summ = ex._excluded_summary()
    n_demands = len(plant.demands)
    print("\n" + "=" * 74)
    print("7. CU5 — THE ARITHMETIC, ON A WORLD THAT HAS EXCLUSIONS")
    print("=" * 74)
    print(f"  demands in snapshot     : {n_demands}")
    print(f"  excluded_demand_ids     : {len(plant.excluded_demand_ids)}")
    print(f"  _excluded_labels (match): {len(ex._excluded_labels)}")
    print(f"  note                    : {json.dumps(summ, default=str)}")
    if summ:
        ok_sum = summ["scheduled"] + summ["count"] == summ["total"]
        ok_world = summ["total"] == n_demands
        ok_names = all(not _looks_like_uuid(o) for o in summ["orders"])
        print(f"  scheduled + count == total : {ok_sum}")
        print(f"  total == demands in world  : {ok_world}")
        print(f"  every name is an ORDER ID  : {ok_names}")
    b = ex.route("late-orders", {"question": "which orders are late?"})
    print("\n--- the trailing note, rendered ---")
    for line in TemplateRenderer().render(b).splitlines():
        if line.startswith("Note:"):
            print(line)


def _looks_like_uuid(s: str) -> bool:
    return len(s) == 36 and s.count("-") == 4


if __name__ == "__main__":
    main()
    reconcile_exclusions()
