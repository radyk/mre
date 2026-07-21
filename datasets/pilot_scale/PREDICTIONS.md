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
