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
- Combined quantity: 800 units (400 from WO-2001, 400 from WO-2002)
- PROD-007: ProductionMinutes=90.0, CostingLotSize=200
  run_rate = (90/200) x 60 = 27 sec/unit
- Gear cutting step (WC-GEAR, seq 10): 800 x 27 sec + 60 min setup = 360 + 60 = 420 min (7 h)
- Inspection step (WC-INSPECT, seq 20): same calculation = 420 min (7 h)

**Calendar forcing:**
- M-GEAR-01 (cost_rate=4.0, cheaper, preferred) has a planned_maintenance closure
  for all of 2026-07-13 (Monday).
- The merged WP has earliest_start = 2026-07-13 00:00 (derived from constituent
  release dates), so the solver must start on that Monday.
- M-GEAR-02 (cost_rate=6.0) is the only gear machine available Monday.
- Shift window: 07:00-19:00 (720 min). After gear cutting ends at 14:00, only
  300 min remain in the shift -- not enough for the 420-min inspection step.
- Inspection is pushed to Tuesday 2026-07-14 07:00-14:00.

**Scheduling outcome:**
- Gear cutting: M-GEAR-02, Mon 2026-07-13 07:00 -> 14:00 (420 min)
- Inspection:   M-INSP-01, Tue 2026-07-14 07:00 -> 14:00 (420 min)
- WorkPackage completion: Tue 2026-07-14 14:00

**Per-Demand outcomes:**
- WO-2001 (due Mon 2026-07-13 23:59): completes Tue 14:00 -> +841 min late
- WO-2002 (due Wed 2026-07-15 23:59): completes Tue 14:00 -> ~2039 min early

## PROD-007 as a seeded outlier

PROD-007's ProductionMinutes=90.0 is intentionally high -- 45x the gear-family
median run rate (0.6 sec/unit). The validator (M3) emits a STATISTICAL_OUTLIER
finding (threshold: >10x family median). This is a seeded data quality defect
designed to trigger M3 detection.

The scheduling impact of 90.0 is what drives the demo story: the merged WP takes
14 hours total across two operations, which spans the shift boundary and makes
WO-2001 genuinely late.

## Evidence chain (the Phase 3 query target)

> "Why is WO-2001 late?"

1. Demand WO-2001 due 2026-07-13 batched with WO-2002 to save one gear-cutting setup
   (Decision: DEMAND_MERGE, driver=SETUP_AMORTIZATION, estimated saving=50, risk stated)
2. Assignment gear cutting -> M-GEAR-02 because M-GEAR-01 was closed 2026-07-13 for
   planned_maintenance (Decision: ASSIGNMENT, driver=CALENDAR_WINDOW, basis=reconstructed;
   alternative lists M-GEAR-01 with "Unavailable: no calendar window covers this operation slot.")
3. Inspection pushed to 2026-07-14 because shift ends before op completes if started same day
4. ServiceOutcome WO-2001: lateness=+841 min, tardiness_cost=841 x 1.0 = 841.0

## Tuning notes

- PROD-007 ProductionMinutes=90.0 keeps the STATISTICAL_OUTLIER finding active (45x median)
- Shift window 07:00-19:00 = 720 min; each step at 420 min fits in one shift
- Two sequential steps (840 min total) span two days when gear cutting starts at 07:00
- WO-2001 release=2026-07-13 forces the solver to start on the maintenance day
- M-GEAR-01 rate=4.0, M-GEAR-02 rate=6.0 (costmodel.json); cost difference makes
  CALENDAR_WINDOW the clear driver (not COST_TRADEOFF -- M-GEAR-02 is the more expensive choice)
