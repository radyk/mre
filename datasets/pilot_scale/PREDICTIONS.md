# pilot_scale — predictions authored BEFORE the solve

Glass-Box discipline (see `datasets/glass_box/README.md`): the plant's physics
are authored deliberately, and its behaviors are **predicted here before any
solve is run**. A contradiction between a prediction and the solve is a finding
to investigate, not a prediction to quietly rewrite.

The plant is built by `tools/generate_erp_dataset.py::_apply_pilot_scale`, sized
against `pilot_profile.json` (volumes/sizes/families/lead-time SHAPE only, per
R-SC1). One facility, 15 machines in 7 capability groups, reference date Monday
2026-01-05, weekday shifts 07:00–19:00 (720 working min/day).

## The plant (authored physics)

| Group | Machines | Rate / speed authored |
|---|---|---|
| CUT | CUT-01/02/03 | $55 / $58 / $62/h — a **$/h split at equal speed** |
| PRESS | PRESS-FAST, PRESS-SLOW | $60 both; SLOW runs at **2× the per-unit time** (a run-time split) |
| MILL | MILL-01/02 | $65 / $68/h |
| PAINT | PAINT-01/02 | $50 both; **setup families** PAINT_RED / PAINT_BLUE, 90-min changeover |
| HEAT | HEAT-01/02 | $70 both; own calendar, a **Saturday overtime** window at 1.5× |
| FINISH | FINISH-01/02/03 | $45 / $47 / $49/h |
| ASM | ASM-01 | $80/h, a **single-machine bottleneck** |

Downtime authored: a plant-wide **planned-maintenance closure** on the 2nd
Wednesday; the **Saturday overtime** HEAT window. Priorities and customers are
**POPULATED** (the Glass Box's eternal warning — an empty priority column is a
silent lie): Acme (critical), Bolt (high), Civic/Delta (standard).

## Predictions (the ~behaviors we expect, before solving)

1. **The monolith does not solve well; a slice does.** The full backlog is
   tardiness-hard and chunk-slot-dense (the splittable P-SPACER work all lands on
   CUT — the gate emits the resumable-density advisory on CUT-01/02/03). A
   monolithic solve stalls at FEASIBLE within a short budget; a short-horizon
   window solves to OPTIMAL in well under a second. This is the entire slicing
   thesis and the reason for the rolling horizon.

2. **PRESS-SLOW is spillover only.** With equal $/h and 2× the run time,
   PRESS-FAST is strictly preferred; PRESS-SLOW is used only when FAST is
   saturated by contending PRESS work (bracket/plate/housing), and each such
   placement bills its own longer duration (a real, priced cross-machine choice).

3. **CUT/MILL/FINISH concentrate on the cheapest alternate until it saturates.**
   The $/h split makes CUT-01 ($55) preferred over CUT-02/03; work spills to the
   dearer machines only under load. A cross-machine ghost on these carries a
   nonzero (Δrate × minutes) price.

4. **PAINT colours separate to avoid changeovers.** The panel products carry
   setup families (PAINT_RED / PAINT_BLUE) with a 90-min RED↔BLUE changeover
   matrix; the optimizer separates the colours (onto different PAINT machines, or
   batched in time) to avoid paying it. Setup-family **affinity is a gravity
   pull** (R-SC2(c)): the rolling horizon pulls same-colour work together.

5. **Splittable spacers chunk at the overnight closure.** A P-SPACER op larger
   than a 720-min shift pauses at 19:00 and resumes 07:00 the next working day —
   never spanning the closed maintenance Wednesday.

6. **ASM-01 is the binding constraint.** Housing and hub orders both route
   through the single ASM-01; it queues under load and is where lateness
   concentrates. Relieving it (not CUT/MILL) is what a planner would target.

7. **Priority orders lead under contention.** Acme (critical, ×8) and Bolt
   (high, ×3) orders are scheduled ahead of standard work when they compete for
   the same window — the populated priority column earns its keep.

8. **The maintenance Wednesday and Saturday overtime bend the schedule.** Work
   flows around the closed Wednesday; HEAT rush work that cannot wait uses the
   Saturday overtime window at the 1.5× premium only when the premium beats the
   tardiness it avoids.

## Authored simplifications (named, not hidden)

- **Order quantities are capped** so a non-splittable op fits one 720-min shift
  (the extract's p99 is 200,000 units — a pilot op cannot be that large and still
  fit a horizon). The heavy-tail SHAPE is preserved; the magnitude is truncated.
  Multi-shift work lives deliberately on the splittable P-SPACER product.
- **Routes are 1–4 ops** (the extract's median is 8). Depth is scaled down to
  keep per-op density tractable while preserving multi-op, cross-machine chains.
- **15 machines, one facility** (the extract spans 174 workcenters across 14
  facilities). A single-facility pilot at a representative machine count; the
  full multi-facility decomposition is a known lever (solver-gap dossier).
- **Alternates are authored on CUT and PRESS only** (the priced-choice groups,
  predictions #2/#3); every other step routes to one machine (round-robin across
  the group, so all 15 machines carry load). Alternates on every op would
  multiply the per-window assignment search and defeat the "a window solves fast"
  property the whole rolling architecture depends on — so the cross-machine
  choice is placed deliberately where the predictions turn on it.

## Graded against the measured solve (Session 4B.2c, 2026-07-22)

Graded post-hoc against a deterministic rolling solve of the 60-order pilot_scale
(window 7 / frozen 2, seed 42, PYTHONHASHSEED=0) plus the committed
`tools/pilot_measurements_report.json`. Honest grades — a WRONG recorded is the
discipline working. **Score: 3 CORRECT · 3 PARTIAL · 1 WRONG · 2 NOT-EVALUABLE**
(predictions 1–8), plus the authored-simplification block CORRECT by construction.

| # | Prediction | Grade | Evidence |
|---|---|---|---|
| 1 | Monolith bad, slice good | **PARTIAL** | The slice half holds — the window curve converges (7-day → $37.7k, 1 late) and a LOADED window reaches first-feasible in 0.275s. But the monolith was NOT solved this session (asserted, not measured), and "a window solves to OPTIMAL well under a second" is CONTRADICTED for a loaded window: solve-to-budget is 4.95s **FEASIBLE**, not OPTIMAL (CU2). |
| 2 | PRESS-SLOW is spillover only | **PARTIAL** | Consistent but under-exercised: PRESS-FAST carried 17 ops, **PRESS-SLOW 0** — FAST was never saturated at this load, so SLOW correctly stayed idle. The priced-spillover event (a SLOW placement billing its 2× duration) never occurred, so that half is unverified. |
| 3 | CUT concentrates on the cheapest | **CORRECT** | CUT-01 ($55) 20 ops / CUT-02 ($58) 14 / CUT-03 ($62) 5 — load concentrates on the cheapest machine, spilling to dearer ones only under load, exactly as predicted. |
| 4 | PAINT colours separate to avoid changeovers | **CORRECT** | RED batched on PAINT-01, BLUE on PAINT-02 → **0 colour changeovers paid** on either machine. The optimizer separated the families to dodge the 90-min matrix. |
| 5 | Splittable spacers chunk at the closure | **NOT-EVALUABLE** | 3 splittable P-SPACER ops exist (min_chunk PT1H), but `committed_ops` stores one start/end per op — the per-chunk pause at the overnight/maintenance closure is not visible in the committed artifact (needs run-window inspection). |
| 6 | ASM-01 is the binding constraint | **WRONG** (at this load) | ASM-01 carried just 4 ops / 1,210 min and is NOT the busiest machine (MILL-01 23 ops / 5,081 min; CUT-01 20). At 60 orders the plant is barely contended (≤1 late), so no lateness "concentrates" anywhere and ASM-01 is not binding. The prediction may hold at heavier load; as stated for the measured instance it is wrong. |
| 7 | Priority orders lead under contention | **NOT-EVALUABLE** | Two findings: (i) priority IS populated but rode **`customer_weight`** (1.0×45 / 3.0×10 / 8.0×5), while canonical `commitment_class` flattened to "standard" for all 60 demands — the priority label did not survive into that field. (ii) At this low-contention load, weight-8 (critical) work does not visibly lead: its mean start-day (~10.4) ≈ standard's (~10.4), confounded by due dates. No contention to force the comparison. |
| 8 | Maintenance Wed + Saturday overtime bend the schedule | **PARTIAL** | Consistent conditional behavior: **0 Saturday ops** (overtime unused — nothing late needed the 1.5× premium), and work flows around the maintenance Wednesday (the only op spanning 2026-01-14 is a splittable P-SPACER pausing across it, not a closure violation). The premium-vs-tardiness trade never fired because the plant wasn't late enough to trigger it. |
| — | Authored simplifications (qty capped / routes 1–4 / 15 machines·1 facility / alternates on CUT·PRESS) | **CORRECT** | 15 resources confirmed; 141 ops / 60 orders ≈ 2.35 ops/order (in the 1–4 band); the forced-alternative probe found an op with 3 eligible machines on a CUT step, others single-eligible — all as authored. |

**What the grading taught.** The two most useful grades are the WRONG (P6) and the
two NOT-EVALUABLE (P5, P7). P6 and P7 share a root: **the 60-order demo instance is
too lightly loaded to exercise the contention the predictions turn on** — ASM-01
never becomes a bottleneck and priority never has to break a tie because almost
nothing is late. A heavier instance (or the pilot volume) is needed to grade the
contention predictions; that is named as connector-era work. P7 also surfaced a
concrete data fact worth carrying: pilot_scale priority lives in `customer_weight`,
not `commitment_class`. The predictions that DID hold cleanly (P3 cheapest-machine
concentration, P4 colour separation) are the ones about the plant's *physics*,
which the solve reproduces regardless of load.
