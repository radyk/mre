# Phase 2 Demo Scenario

## Overview

The Phase 2 sample dataset is designed to demonstrate:
1. **merge_by_family_v1** batching policy
2. **Calendar-driven rerouting** with a reconstructed CALENDAR_WINDOW decision
3. **Per-Demand tardiness** invariant (D-07): one ServiceOutcome per constituent Demand

## The demo situation

**WO-2001** and **WO-2002** are both for PROD-007 (Gear Gamma, family `gear`), both
released 2026-07-13 (Monday), and their due dates are 2 days apart (2026-07-13 and
2026-07-15). The `merge_by_family_v1` policy (default window: 3 days) merges them
into a single WorkPackage.

**Merged batch parameters:**
- Combined quantity: 800 units
- Gear cutting step (WC-GEAR, seq 10): 800 × 0.75 min/unit + 60 min setup = 660 min ≈ 11 hours
- Inspection step (WC-INSPECT, seq 20): 800 × 0.75 + 60 = 660 min ≈ 11 hours

**Calendar forcing:**
- M-GEAR-01 (cost_rate=4.0, cheaper, preferred) has a `planned_maintenance` closure
  for all of 2026-07-13 (Monday).
- The merged WP has `earliest_start = 2026-07-13 07:00` (from max of constituent
  release dates), so the solver cannot delay to Tuesday.
- M-GEAR-02 (cost_rate=6.0) is the only gear machine available Monday → forced assignment.

**Scheduling outcome:**
- Gear step: M-GEAR-02, Mon 2026-07-13 07:00 → 18:00 (660 min = 11 hours)
- Inspect step: M-INSP-01 can't start Mon 18:00 (only 60 min left in shift) →
  pushed to Tue 2026-07-14 07:00 → 18:00
- WorkPackage completion: Tue 2026-07-14 18:00

**Per-Demand outcomes:**
- WO-2001 (due Mon 2026-07-13 23:59): completes Tue 18:00 → **18 hours late** ✓
- WO-2002 (due Wed 2026-07-15 23:59): completes Tue 18:00 → **~30 hours early** ✓

## Evidence chain (the Phase 3 query target)

> "Why is WO-2001 late?"

1. **Demand** WO-2001 due 2026-07-13 → batched with WO-2002 to save one gear-cutting setup
   (Decision: DEMAND_MERGE, driver=SETUP_AMORTIZATION, estimated saving=50×1=50, risk=660 min tardiness exposure for WO-2001)
2. **Assignment** gear step → M-GEAR-02 because M-GEAR-01 was closed 2026-07-13 for
   planned_maintenance (Decision: ASSIGNMENT, driver=CALENDAR_WINDOW, basis=reconstructed)
3. **ServiceOutcome** WO-2001: lateness=18h, tardiness_cost=18×60×1.0=1080 (minutes × base_weight)
4. **Finding** SOLVER_NONOPTIMAL if time limit hit; otherwise nothing.

## Tuning notes

- PROD-007 ProductionMinutes=150.0, CostingLotSize=200 → run_rate=(150/200)×60=45 sec/unit=0.75 min/unit
- Shift window 07:00-19:00 = 720 min; gear step 660 min fits in one shift; two steps (1320 min) span two days
- WO-2001 release=2026-07-13 is intentional — forces solver to start on the maintenance day
- M-GEAR-01 rate=4.0 (costmodel.json), M-GEAR-02 rate=6.0 — cost difference creates the CALENDAR_WINDOW decision
