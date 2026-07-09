# Seeded Defects Catalog

Every defect is deliberate. Tests in `tests/test_adapter.py` and
`tests/test_validator.py` assert these are found with the exact finding codes
and dispositions listed here.

| # | File | Entity / Value | Defect | Expected finding code | Expected disposition |
|---|------|----------------|--------|-----------------------|----------------------|
| 1 | openworkorder.csv | WO-REF-BAD, RouteCode=R-GHOST | Routing code does not exist in routing.csv | `MISSING_REFERENCE` | `excluded` |
| 2 | product.csv | PROD-008, CostingLotSize=0 | Division by zero in run-rate derivation; fallback rate used | `LOW_CONFIDENCE_INPUT` | `defaulted` |
| 3 | openworkorder.csv | WO-PAST-001, ScheduleDate=2025-01-15 | Due date is in the past relative to run date | `TEMPORAL_IMPOSSIBILITY` | `proceeded_flagged` |
| 4 | routinglines.csv | R-GEAR-B seq 20, Workcenter=WC-UNKNOWN | Workcenter code cannot be mapped to any canonical resource | `UNMAPPABLE_VALUE` | `proceeded_flagged` |
| 5 | product.csv | PROD-007, ProductionMinutes=90.0 | run_rate of 90 min/unit is 45x the median (2.0) for the gear family, tested against the seeded scenario's 10x detection threshold (Rep 3, docs/07: the gauntlet-calibrated default of 75.76x is a separate deployment's config and does not apply here) | `STATISTICAL_OUTLIER` | `proceeded_flagged` |
| 6 | openworkorder.csv | WO-DUP-001 (two rows) | Same work-order number appears twice; first row kept, second excluded | `DUPLICATE_IDENTITY` | `excluded` |

## Notes

- Defect 1 is caught by **M1 (Adapter)** at ERP-translation time (routing lookup fails).
- Defect 2 is caught by **M1 (Adapter)**: zero CostingLotSize detected, fallback
  run_rate used, LOW_CONFIDENCE_INPUT emitted; the Demand/OperationSpec are
  included with a warning.
- Defect 3 is caught by **M3 (Validator)** during the semantic check pass.
- Defect 4 is caught by **M1 (Adapter)** when resolving workcenter to resources.
- Defect 5 is caught by **M3 (Validator)** in the statistical-outlier check.
- Defect 6 is caught by **M1 (Adapter)** during identity resolution.

None of these is severity=`blocker`, so the overall go/no-go gate returns **go**.
