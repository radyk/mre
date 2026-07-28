#!/usr/bin/env python3
"""Session 4B.10 ITEM 4 — PAST-DUE WORK, FINALLY EXERCISED.

REPORT ONLY. This session does not re-rule ghost jobs; it hands the design
conversation a LIVE SPECIMEN and a NUMBER instead of a hypothetical.

The standing question, carried since the Glass Box audit:
  * does an already-late order get SCHEDULED LATE, or does it VANISH?
  * if it vanishes, WHERE — validator TEMPORAL_IMPOSSIBILITY, gate exclusion,
    or admission?
  * is the disposition CERTIFICATE-VISIBLE and AI-answerable?

Until 4B.10 no fixture could ask: `pilot_scale`'s `lead_min = 4` makes a
past-due order structurally impossible, and the retired RawAdapter filtered
past-due rows on intake (raw_adapter.py:7). `facility_real` produces them.
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
SCRATCH = REPO / "_4b10_scratch"


def main():
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import prepare_plant

    sub = SCRATCH / "sub_pastdue"
    if not (sub / "manifest.json").exists():
        sub.parent.mkdir(parents=True, exist_ok=True)
        generate(sub, scenario="facility_real_pastdue", orders=60, seed=1)
    marker = json.loads((sub / "feel_fixture.json").read_text(encoding="utf-8"))
    fr = marker["facility_real"]
    print("=" * 74)
    print("THE WORLD")
    print("=" * 74)
    print(f"  scenario  : facility_real_pastdue (F005's book — 25.2% past due)")
    print(f"  orders    : {fr['n_orders']}   machines: {fr['n_resources']}")
    print(f"  past due  : {fr['past_due_orders_generated']} generated "
          f"({100*fr['past_due_orders_generated']/fr['n_orders']:.1f}%), "
          f"declared share {fr['past_due_share_declared']}")

    plant = prepare_plant(sub, SCRATCH / "run_pastdue", reference_date=REF)

    # --- 1. DID THEY SURVIVE INTAKE? -----------------------------------------
    def oid(d):
        for r in d.get("external_refs") or []:
            if r.get("type") == "order_id":
                return r.get("value")
        return d["id"][:8]

    past = [d for d in plant.demands
            if d.get("due") and str(d["due"])[:10] < REF.date().isoformat()]
    excluded = set(plant.excluded_demand_ids)
    sched_ids = {d["id"] for d in plant.schedulable_demands}

    print("\n" + "=" * 74)
    print("1. DOES AN ALREADY-LATE ORDER SURVIVE INTAKE?")
    print("=" * 74)
    print(f"  demands total        : {len(plant.demands)}")
    print(f"  demands due < ref    : {len(past)}")
    print(f"  excluded_demand_ids  : {len(excluded)}")
    print(f"  past-due AND excluded: {sum(1 for d in past if d['id'] in excluded)}")
    print(f"  past-due AND schedulable: {sum(1 for d in past if d['id'] in sched_ids)}")
    verdict = ("VANISHES — every past-due order is excluded before the solver"
               if all(d["id"] in excluded for d in past)
               else "survives at least partly")
    print(f"\n  VERDICT: {verdict}")
    print("  Specimens:")
    for d in sorted(past, key=lambda x: str(x["due"]))[:5]:
        print(f"    {oid(d):<14} due={str(d['due'])[:10]}  "
              f"excluded={d['id'] in excluded}  schedulable={d['id'] in sched_ids}")

    # --- 2. WHERE, EXACTLY? ---------------------------------------------------
    print("\n" + "=" * 74)
    print("2. WHERE DOES IT VANISH?")
    print("=" * 74)
    store = plant.store
    findings = []
    try:
        for rec in store.read_all() if hasattr(store, "read_all") else []:
            if rec.get("record_type") == "Finding":
                findings.append(rec)
    except Exception:
        pass
    if not findings:
        # fall back to the run directory's JSONL sink
        for p in sorted((plant.out_dir).rglob("*.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("record_type") == "Finding":
                    findings.append(rec)
    codes = {}
    for f in findings:
        codes[f.get("code")] = codes.get(f.get("code"), 0) + 1
    print(f"  findings recorded in the run: {len(findings)}")
    for c, n in sorted(codes.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {c:<32} x{n}")

    ti = [f for f in findings if f.get("code") == "TEMPORAL_IMPOSSIBILITY"]
    print(f"\n  TEMPORAL_IMPOSSIBILITY findings: {len(ti)}")
    if ti:
        f = ti[0]
        print(f"    severity   : {f.get('severity')}")
        print(f"    disposition: {f.get('disposition')}")
        print(f"    tier       : {f.get('tier')}")
        print(f"    evidence   : {json.dumps(f.get('evidence'), default=str)[:240]}")
    print("\n  MECHANISM (read from source, not inferred):")
    print("    src/mre/modules/validator.py:186-221, Check 1. A Demand whose")
    print("    `due < reference_date` and which carries NO in_progress/complete")
    print("    wip_operations is added to `excluded_demand_ids` and reported as")
    print("    TEMPORAL_IMPOSSIBILITY / WARNING / disposition=EXCLUDED.")
    print("    It is NOT the M0 gate and NOT gravity admission: the submission")
    print("    grades clean and the demand never reaches `_admit` — it is")
    print("    filtered by `PreparedPlant.schedulable_demands`")
    print("    (rolling_horizon.py:385), which subtracts excluded_demand_ids.")
    print("    The ONLY escape is the docs/06 §5.13 wip_status doorway.")

    # --- 3. IS IT CERTIFICATE-VISIBLE? ---------------------------------------
    print("\n" + "=" * 74)
    print("3. IS THE DISPOSITION CERTIFICATE-VISIBLE?")
    print("=" * 74)
    certs = [p for p in (plant.out_dir).rglob("*certificate*")]
    print(f"  certificate artifacts in the run dir: {[p.name for p in certs]}")
    for p in certs[:2]:
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        hit = "TEMPORAL_IMPOSSIBILITY" in txt
        print(f"    {p.name}: names TEMPORAL_IMPOSSIBILITY = {hit}")
    return plant, past, excluded


if __name__ == "__main__":
    main()
