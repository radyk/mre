#!/usr/bin/env python3
"""Session 4B.10 ITEM 4, parts 3-4 — is the past-due disposition VISIBLE?

Part 1-2 (pastdue_probe.py) established that every past-due order VANISHES at
`validator.py` Check 1 with a TEMPORAL_IMPOSSIBILITY / WARNING / EXCLUDED
finding. This asks the two questions that decide whether that is a defensible
behaviour or a silent one:

  3. is the disposition CERTIFICATE-VISIBLE — does the schedule document a
     planner actually reads say anything about the order?
  4. is it AI-ANSWERABLE — does "where is ORD-X?" reach an honest answer?

REPORT ONLY.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)
SCRATCH = REPO / "_4b10_scratch"


# Errand 4B.16a — this spike's own copy of the loader had DRIFTED: it used
# `os.environ.setdefault`, which writes an EMPTY value where the other three
# copies skip it, so a commented-out key here could shadow a real one from the
# environment. It calls `mre.env_local`, the one reader, like everything else.
from mre.env_local import load_env_local as _load_env  # noqa: E402


def main():
    from generate_erp_dataset import generate
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant

    sub = SCRATCH / "sub_pastdue"
    if not (sub / "manifest.json").exists():
        generate(sub, scenario="facility_real_pastdue", orders=60, seed=1)

    plant = prepare_plant(sub, SCRATCH / "run_pastdue_vis", reference_date=REF)
    past = [d for d in plant.demands
            if d.get("due") and str(d["due"])[:10] < REF.date().isoformat()]

    def oid(d):
        for r in d.get("external_refs") or []:
            if r.get("type") == "order_id":
                return r.get("value")
        return d["id"][:8]

    specimen = sorted(past, key=lambda x: str(x["due"]))[0]
    spec_order = oid(specimen)
    print(f"SPECIMEN: {spec_order}  due={str(specimen['due'])[:10]}  "
          f"(reference_date {REF.date()})")
    print(f"past-due demands in this world: {len(past)} of {len(plant.demands)}\n")

    print("=" * 74)
    print("3. IS IT CERTIFICATE-VISIBLE?  (the document a planner reads)")
    print("=" * 74)
    view = build_rolling_view(plant, window_days=14, frozen_days=3, seed=42,
                              deterministic=True, persist=False)
    doc = None
    try:
        from mre.modules.schedule_assembler import assemble_rolling_document
        doc = assemble_rolling_document(plant=plant, view=view,
                                        schedule_id="sched-4b10-pastdue",
                                        run_id="run-4b10-pastdue")
    except Exception as exc:      # noqa: BLE001
        print(f"  (could not assemble a document: {type(exc).__name__}: {exc})")
    if doc is not None and hasattr(doc, "model_dump"):
        doc_obj, doc = doc, doc.model_dump(mode="json")
    blob = json.dumps(doc, default=str) if doc is not None else ""
    print(f"  document assembled: {doc is not None}  "
          f"({len(blob):,} chars)" if doc is not None else "  no document")
    if blob:
        print(f"  document names the specimen order {spec_order!r} : "
              f"{spec_order in blob}")
        print(f"  document names 'TEMPORAL_IMPOSSIBILITY'          : "
              f"{'TEMPORAL_IMPOSSIBILITY' in blob}")
        for token in ("excluded", "past_due", "past due", "temporal"):
            print(f"    contains {token!r:<22}: {token.lower() in blob.lower()}")
        # which regions exist, and is the order in any of them?
        try:
            keys = sorted(doc.keys()) if isinstance(doc, dict) else []
            print(f"  top-level document keys: {keys}")
        except Exception:
            pass

    print(f"\n  view.beyond_demand_ids: {len(getattr(view, 'beyond_demand_ids', []) or [])}")
    print(f"  specimen in beyond_demand_ids: "
          f"{specimen['id'] in set(getattr(view, 'beyond_demand_ids', []) or [])}")
    print("  -> a past-due order is NOT beyond-horizon: the coarse zone never")
    print("     sees it, so the 'tray order is never not in this schedule'")
    print("     guarantee (4B.5) does not cover it.")

    print("\n" + "=" * 74)
    print("4. IS IT AI-ANSWERABLE?  ('where is ORD-X?')")
    print("=" * 74)
    have_env = _load_env()
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  .env.local present: {have_env}   ANTHROPIC_API_KEY set: {have_key}")

    # Does subject resolution find the order at all?
    try:
        from mre.modules.rolling_questions import RollingVocabulary
        vocab = RollingVocabulary(doc) if doc is not None else None
        print(f"  RollingVocabulary built: {vocab is not None}")
        for meth in ("resolve_subject", "resolve", "subject_for"):
            fn = getattr(vocab, meth, None)
            if fn:
                try:
                    print(f"    {meth}({spec_order!r}) -> {fn(spec_order)!r}")
                except Exception as exc:   # noqa: BLE001
                    print(f"    {meth}({spec_order!r}) raised "
                          f"{type(exc).__name__}: {exc}")
                break
        else:
            print(f"    vocabulary methods: "
                  f"{[m for m in dir(vocab) if not m.startswith('_')][:14]}")
    except Exception as exc:      # noqa: BLE001
        print(f"  RollingVocabulary unavailable: {type(exc).__name__}: {exc}")

    if not have_key:
        print("\n  NOT ASKED: no ANTHROPIC_API_KEY. The parse tier is a model and")
        print("  there is no deterministic classifier to fall back on (4A.5c), so")
        print("  an ask here would land on the honest could-not-interpret floor")
        print("  and would measure the missing key, not the routing.")


if __name__ == "__main__":
    main()
