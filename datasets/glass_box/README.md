# Glass Box — the hand-auditable dataset

A small IDS submission built to be **read, not just run**. Fifteen orders, five
machines, one facility — few enough to hold in your head and open in Excel. Every
number here was hand-authored; there is no generator behind it. The point is that
you can trace any placement in the solved schedule back to a row you can see.

**These are predictions, written before the solve.** The seven stories below say
what the schedule *will* do and *why*, from the input alone. Solve it, then check
the schedule against these claims. If the solve ever contradicts a prediction,
that is a **finding** — tell someone; do not quietly rewrite the prediction to
match. (`tests/test_glass_box.py` pins all seven; they held when this was built.)

## Run it

```
# 1. The gate reads the submission and issues a certificate.
python -m mre.gate datasets/glass_box
#    -> grade ACCEPTED, costing_grade C2, 0 findings

# 2. The full solve (deterministic — same flags, same schedule, every time).
python -m mre --submission datasets/glass_box --out gb_out \
    --solver-workers 1 --solver-seed 0
#    -> writes gb_out/schedule.csv (open it in Excel)
```

Reference date is **Monday 2026-01-05** (from the manifest). The work week is
Mon–Fri, 07:00–19:00 (a 720-minute shift). Weekends are closed — except one.

## The plant

| Machine     | Calendar  | What runs there |
|-------------|-----------|-----------------|
| `CUT-01`    | Mon–Fri   | widget cut, the rush pair, the long spacer, the shim |
| `PRESS-FAST`| Mon–Fri   | fast press (alternative group) |
| `PRESS-SLOW`| Mon–Fri   | slow backup press (alternative group) |
| `PAINT-01`  | Mon–Fri   | widget paint, the two colour panels |
| `HEAT-01`   | Mon–Fri **+ Sat 2026-01-10 overtime** | heat-treat |

Rates are a flat **$60/h ($1/min)** on every machine, so a cost difference is a
*time* difference. Tardiness is **$25/h** (× priority). Overtime bills at
**1.5×**. That is the whole cost model — see `cost_model.json`.

## The seven stories (one each — everything else is deliberately boring)

1. **Alternative group with real per-machine rates.** `P-BRACKET` step 10 is
   eligible on the fast press (5 min/unit) *or* the slow press (10 min/unit) —
   two rows sharing `(RT-BRACKET, 10)` in `routing_lines.csv`. Three bracket
   orders (`ORD-06/07/08`) are all due Monday. The fast press only fits two in a
   day, so **one bracket runs on `PRESS-SLOW`** — at double the minutes, ~$250
   more. Not late; just the road taken when the fast lane is full.
2. **A splittable op that pauses at a closure.** `ORD-03` (`P-SPACER`) is a single
   900-minute op marked `splittable=true`. No 720-minute shift can hold it, so it
   **runs to 19:00, pauses overnight, and resumes the next morning** — one job,
   two chunks, no work billed to the pause.
3. **One order late by design — pure capacity, not bad data.** `ORD-04` and
   `ORD-05` are identical 470-minute rush jobs, both due Monday, both on `CUT-01`.
   Only one fits Monday. `ORD-04` is **high** priority and wins the day; **`ORD-05`
   (standard) slips to Tuesday and is late.** The cause is contention on `CUT-01`,
   traceable to `ORD-04` — the data is clean.
4. **An overtime window that rescues one specific order.** `HEAT-01` has a Saturday
   (2026-01-10) overtime exception. `ORD-10` and `ORD-11` are both 600-minute heat
   jobs released Friday; Friday fits one. `ORD-10` (due Friday) takes it; **`ORD-11`
   (due Saturday) is saved by the Saturday window** and bills the 1.5× premium.
   Strip that one calendar row and `ORD-11` goes late.
5. **A two-machine precedence chain.** `P-WIDGET` routes `CUT-01` (step 10) →
   `PAINT-01` (step 20). For `ORD-01` and `ORD-02`, **paint cannot start until cut
   finishes** — the second bar always sits after the first.
6. **A setup-family changeover.** `ORD-09` is a RED panel, `ORD-12` a BLUE panel,
   both on `PAINT-01`. Running one colour then the other **incurs a 90-minute
   colour changeover** ($60) from `setup_transitions.csv` — visible as a gap
   between the two panel bars wider than either op's own setup.
7. **The control — comfortably early.** `ORD-13` (`P-SHIM`) is a 20-minute job due
   more than a week out. It finishes the first day with room to spare. Nothing to
   see — which is the point: it is the boring baseline the six stories stand out
   against.

## The order roster

| Order | Product | Machine(s) | Story |
|-------|---------|------------|-------|
| ORD-01 | P-WIDGET | CUT-01 → PAINT-01 | #5 precedence chain |
| ORD-02 | P-WIDGET | CUT-01 → PAINT-01 | #5 precedence chain |
| ORD-03 | P-SPACER | CUT-01 | #2 splittable / pause |
| ORD-04 | P-RUSH (high) | CUT-01 | #3 contention — wins Monday |
| ORD-05 | P-RUSH (std) | CUT-01 | #3 contention — **late** |
| ORD-06 | P-BRACKET | PRESS-FAST | #1 alternative group |
| ORD-07 | P-BRACKET | PRESS-FAST | #1 alternative group |
| ORD-08 | P-BRACKET | **PRESS-SLOW** | #1 the road taken |
| ORD-09 | P-PANEL-RED | PAINT-01 | #6 changeover |
| ORD-10 | P-HEAT | HEAT-01 (Fri) | #4 overtime — takes Friday |
| ORD-11 | P-HEAT | HEAT-01 (**Sat**) | #4 overtime — rescued |
| ORD-12 | P-PANEL-BLUE | PAINT-01 | #6 changeover |
| ORD-13 | P-SHIM | CUT-01 | #7 the control (early) |
| ORD-14 | P-BASIC | HEAT-01 | boring background |
| ORD-15 | P-BASIC | HEAT-01 | boring background |

## Companion documents

- **`SABOTAGE_MENU.md`** — ten keyed one-cell edits and the exact rule each trips.
- **`WALKTHROUGH.md`** — the session script: submit, read the certificate,
  sabotage it, fix it, solve, and read the story of the solve end to end.
