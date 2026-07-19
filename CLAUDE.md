# CLAUDE.md — Manufacturing Reasoning Engine

## What this repository is

An AI-assisted production scheduling platform built around a canonical manufacturing
model, an evidence contract, and OR-Tools CP-SAT. The goal is a **manufacturing
reasoning engine**: schedules that are cost-optimized, constraint-respecting, and —
above all — explainable and traceable.

## Authoritative documents (read these first)

The specifications in `docs/` are the constitution of this project. They were
produced through extensive design work and are **authoritative over any other
source, including this file and the legacy code**:

1. `docs/01-canonical-model-spec.md` — the three-model architecture, all canonical
   entities and their attributes (incl. PrecedenceEdge, docs/01 §5.4a), provenance
   rules, snapshot semantics, design invariants.
2. `docs/02-evidence-contract-spec.md` — record types (Decision, Finding, Metric,
   Event, Artifact, RunContext), controlled vocabularies (12 driver codes,
   18 finding codes), the eight Reporter verbs, sink/consolidation rules.
3. `docs/03-poc-plan.md` — module inventory M0–M10 and the original PoC phases
   (historical; superseded for planning by docs/07).
4. `docs/05-constraint-catalog.md` — the census of scheduling constraints: locked
   rulings (R-B3, R-C3, R-B7/B8, R-A2/A3, R-A4, R-Dwell), the catalog with
   verdict/plane/status per item, acceptance gates (incl. the
   defaults-reproduce-baseline modularity gate).
5. `docs/06-incoming-data-spec.md` — the IDS: submission schema + manifest declared
   semantics, the conformance gate's Tier 1/2/3 checks, the C0–C3
   costing-completeness grade, doorways (customers, setup_transitions, locks,
   wip_status §5.13).
6. `docs/07-roadmap.md` — the live product roadmap (vision, phases, workstreams,
   open rulings queue). **Check this before picking "next work"** — it supersedes
   any hand-written task list here.

`docs/00-README.md` is a one-page orientation. `docs/04-design-history.md` is the
append-only decision log — **read its Amendment log tail before touching any area
it covers**; the full build history (IDS adoption, edge surgery, chunking spikes
and Rep 2, Reps 3–4, overtime premium, the Phase-1 exit audit) lives there, not
here.

## Hard rules (do not violate, do not "improve away")

- **Nothing defines record shapes outside `src/mre/contracts/`.** All modules import
  entity types, record types, and enums from the contracts package.
- **ERP identifiers appear only inside `external_refs`.** The core imports only
  canonical types. Adapters (M1 family) are the only ERP-aware code.
- **No attribute write without its provenance record** — one API, one transaction.
  Provenance classes: observed / derived / defaulted / synthesized. Provenance must
  be TRUTHFUL: writing a constant under an `observed` sidecar is a defect class
  (see 2026-07-12 amendments).
- **The Solver Builder never reads the provenance sidecar.** Validation and planning
  may, via a narrow trust interface. The AI layer reads everything.
- **Every Decision carries `basis`** (observed / reconstructed / policy_applied).
  Solution-extraction assignments are always `reconstructed`.
- **Tardiness is evaluated per Demand** (via Fulfillments), never per WorkPackage.
- **Every run executes against an identified snapshot**; every evidence record
  references its snapshot ID.
- **Metrics with `rollup_of` must decompose exactly**; the consolidator verifies.
- **The AI layer (M10) has no write path** into the canonical model or the
  evidence store.
- Vocabulary changes (driver codes, finding codes, entity attributes) are reviewed
  changes: **add, never repurpose**. Update the relevant spec in `docs/` in the
  same commit.
- **`docs/04-design-history.md` is append-only.** Never recreate or truncate it.
  New material goes only under the "Amendment log" heading as dated entries.
- **Any "identical schedule" claim requires deterministic mode**
  (`--solver-workers 1 --solver-seed …`, `PYTHONHASHSEED=0`) — CP-SAT parallel
  search is not reproducible (2026-07-09 amendment).
- **Phase exits are audited by a fresh session in audit mode** (no fixes unless
  failure; every accommodation named) — the Phase-1 exit found seven
  proven-from-one-side seams this way.

## Repository layout

```
docs/                 Authoritative specifications (living documents)
legacy/               Previous-generation codebase. REFERENCE ONLY — see legacy/README.md
src/mre/contracts/    L1: entity types, record types, enums, provenance structures
src/mre/reporter/     L2+L3: the Reporter (eight verbs), JSONL sink, consolidator
src/mre/modules/      M0 (conformance gate), M1 adapters (sample / raw / IDS),
                      M2–M7 spine, M9 index, M10 explainer, scenario runner,
                      schedule-document assembler
src/mre/api/          FastAPI surface (thin, no business logic) + SQLite
                      run/schedule registry; run-dir minting lives here
src/cockpit/          L-frontend: the reasoning cockpit (Vite + vis-timeline,
                      read-only). Renders a contract-1.2 document from the API;
                      talks to the core over HTTP only. Design tokens in
                      tokens.css. (interim-A, Phase 3)
tools/                Generator, calibration, spikes, viewers, profilers
tests/                Tests derived from the specs — write them from the spec text.
                      tests/cockpit/ = the Playwright screenshot harness (CU5).
```

## Current status

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.4 — schedule freshness
done right (the sixth stale-tab incident) 2026-07-19.** The behavior contract: **the
cockpit must never leave the user unknowingly on anything but the newest relevant
schedule.** 4.3's newer-schedule detection was real but half-scoped, and the sixth
incident proved it blind to the RESUBMIT workflow (fix data in Excel → re-submit mints
a NEW submission id → re-solve → the newer solve was never offered because it was a
different submission). Frontend + one additive `/meta` field + docs; no
solver/model/contract changes. **CU1 — freshness scope fix:** `findNewerSchedule`
(`src/cockpit/src/freshness.js`) compares against the newest LIVE (non-superseded)
schedule across the whole **DATA ROOT**, not the same submission — "relevant" for
single-tenant/dev IS the root; strictly newer by `created_at` (the listing is
`ORDER BY created_at`), a **same-instant tie is NOT newer** (unrelated live boards
never cross-follow), superseded + scenarios never offered. **Multi-tenant scoping is a
NAMED future concern** (docs/04), deliberately NOT pre-built — a tenant boundary is a
property the data root does not model today, so inventing that scope would be the kind
of plausible lie docs/01 forbids; when a second tenant exists the scope narrows from
"the root" to "the tenant's schedules". **CU2 — auto-follow on resubmit (the real
fix):** noticing still depends on the human, so when a newer schedule appears while the
cockpit is bound to an older one AND there is **no uncommitted user state**, the
cockpit **follows it automatically** — a full reload onto the new version + a brief
R-M1-legible toast ("Switched to the new schedule · View previous (<id8>)", one click
back via a `sessionStorage` handoff stashed before the jump and read on the next
boot). **With uncommitted state present, NEVER auto-switch** — fall back to the 4.3
banner, planner decides. "Uncommitted" = a drag phase ≠ `idle` (tentative edit / open
delta card / accept-publish in flight) **or** a pinned conversation (new
`panel.hasUserState()`: a live bar selection, a built-up Q&A history, or an ask
mid-round-trip). An edit-in-flight outranks freshness; generalized, any user
investment does. The watch re-checks on **window focus** + **tab re-show**
(`visibilitychange`) + a 30s interval backstop — focus is the load-bearing signal (a
planner returning from Excel after a data fix is the exact moment). Idempotent per
newer id (no stacked banner); the follow-reload resets state so a chain never loops.
**CU3 — identity made visible:** `Registry.get_schedule_meta` now carries a
**`generation`** counter (1-based ordinal among the data root's non-scenario schedules,
`created_at` asc — a monotonic "solve #N") + **`created_at`**; the top strip renders a
human-scale identity — **"solve #3 · 09:41"** — with the short hex kept in the element
`title`, degrading to the hex (a plain doc / pool member) rather than a blank. Across
all six incidents the hex alone was insufficient: two visually-similar boards read
identically. **Harness:** new `POST /__test__/add-schedule` fixture-server seam injects
a newer schedule into the data-root listing (resolving as a real doc/meta from a base
fixture dir so an auto-follow lands on a coherent board), cleared per test; the three
CU2 flows driven end to end (resubmit-while-viewing **auto-follows** — URL advances +
toast + one click back; an **uncommitted selection** shows the banner and the URL
**never** changes; a **window focus** rechecks + follows), plus CU3 (strip shows "solve
#N · HH:MM") and a strengthened CU6 (no spurious auto-follow on a normal boot — the
static fixtures tie on `created_at`). **Cockpit JS 146 passed** (was 137: +1 freshness
logic, +8 cockpit.spec CU2/CU3 × light+dark); **non-slow Python 1172 passed** (+1
`/meta` identity assertion; `get_schedule_meta` change is additive). See the docs/04
2026-07-19 Session 4.4 amendment and docs/07 v2.26. Lesson: "notice the newer schedule"
and "the user is now on the newer schedule" are different guarantees — the first still
depends on the human, so the sixth incident needed the second; follow automatically
when nothing is at stake, yield to the banner the moment something is, and make the two
boards nameable so a human can tell which one they are on.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.3 — Glass Box audit
riders + R-DP9 (the no-op drop) 2026-07-18.** Eight small findings from Daryn's live
Glass Box audit, batched — no solver/model/contract changes (frontend + one ruling
+ docs + env). **R-DP9 ruled** (docs/04, transcribed): a drop within snap tolerance
of the op's INCUMBENT placement is a NO-OP — the bar settles home with an "already
here" cue and NOTHING is committed (no sandbox re-solve, no zero-delta edit, no
`planner_edit` Decision, no standing pin); tolerance = the existing snap token
(`feel.snap.grid_px × pxToMin`, so "basically didn't move" is a screen distance at
any zoom). The mirror of R-DP8: a real commitment must survive every solve; a
non-commitment must never become one. **CU0 — `.env.local` verified end to end:**
`dev_api.ps1` already loads a gitignored `.env.local` at the repo root into the API
env on startup (existing env wins), so a key reaches the M10 LLM renderer with NO
terminal typing (the 4B.0 claim held); added a committed `.env.local.example`
(gitleaks-guarded; `.env.local` ignored, the `.example` not) + a cockpit README dev
section documenting the `cp .env.local.example .env.local` flow. **CU1 — the
ledger/legend collision (SECOND occlusion incident) made STRUCTURAL:** a new
`.board-chrome` row (`justify-content:space-between; flex-wrap:wrap-reverse`) holds
the legend (left) + a right cluster (zoom controls + the DEV question-ledger dock);
the ledger is no longer `position:fixed` but a thin TAB whose refusal body drops
UPWARD over board space (`bottom:calc(100%+sp-1)`), never over chrome — `wrap-reverse`
lifts the right cluster ABOVE the legend when the board is too narrow, so they can
never intersect; legend visible by default. Harness serves the production build, so
`window.__cockpit.mountDevLedger()` mounts the REAL dock for a bounding-box
non-intersection assertion of {tab, body} × {legend, ask} at two widths (1540/1100).
**CU2 — R-DP9 implemented:** `controller.drop()` short-circuits `isNoOpDrop(target)`
(same resource + within `grid_px×pxToMin`) → `noOpReturn()` (gentle settle, NOT the
R-M1a reject shake) + a neutral `.drag-noop` cue, no card/network; `state().noop`.
Nine existing sandbox-path gesture tests dropped AT `incumbent(op)` — R-DP9 correctly
reclassifies that as a no-op — so they migrated to a genuine legal move (a shared
`legalMove()` reading `tier0For(op).legal_regions`, altKey/no-snap). **CU3 — empty
delta-card copy:** a verdict with an empty moved-set reads "equivalent placement —
nothing else moved" (authored), not blank space under "Same cost". **CU4 —
marker/band legibility:** the due marker decoupled from `--bar-late` to a NEUTRAL
slate rendered DASHED (a met due date is a reference line, not an alarm), distinct
from the solid now/release lines; marker chips FLIP left near the right edge (full
words, no "…ase" clip); downtime hover cards state the WINDOW ("17:00 – 05:00") +
reopen weekday; legend visible by default. **CU5 — zoom affordance:** `.board-zoom`
+/− controls (→ vis's `zoomIn/zoomOut`; Ctrl+wheel/pinch unchanged) + a fading
first-load "Ctrl+scroll to zoom" hint; aria-labelled (accessibility note in docs/04).
**CU6 — newer-schedule detection** (extends 3.8's superseded self-heal): pure
`freshness.js` `findNewerSchedule(boundId, schedules)` — the newest LIVE schedule of
the SAME submission strictly newer than the bound one (never cross-scope, never
guesses on unknown scope) → a dismissible "A newer schedule exists · Open it" info
bar; the stale tab now notices. **CU7 — packed bars distinct:** a right-edge SEAM
(`box-shadow: inset -1px 0 0 0 var(--bar-sep)`, per-theme token) so temporally-
adjacent bars read as DISTINCT at day zoom (asserted on the busy multi_route row —
the glass_box CUT-01 packing shape; no committed glass_box cockpit fixture, an
accommodation named). **Cockpit JS 137 passed** (was 113: +6 freshness logic,
+8 cockpit, +6 planner, +4 gesture ×themes); **non-slow Python 1171 passed, 0 failed**
(frontend/docs/env only — regression guard). See the docs/04 2026-07-18 Session 4.3
amendment and docs/07 v2.25. Lesson: two of these were the same bug in different
clothes — a control that fights the thing beside it (the ledger over the legend) and
a gesture that fabricates a commitment out of no change (the no-op drop); the cure
for both is to make the structure say the truth — one layout row that cannot overlap
itself, and a drop that changed nothing changes nothing.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4B.1 — Glass Box
instruments (the hand-auditable dataset, sabotage menu, walkthrough) 2026-07-18.**
Instruments so Daryn can verify, at his own pace, that (a) the gate catches
deliberate data defects with the right rule/severity/disposition and (b) every
placement in the solved schedule traces back to a row he authored — "read the story
of the solve." This session BUILDS the instruments; it does not run the audit (that
is Daryn's, by design). No solver/model/contract changes — dataset + docs + one
dev-script wiring + one standing test. **CU1 — the glass_box dataset:** a
HAND-AUTHORED, committed IDS submission at `datasets/glass_box/` (manifest + six
required CSVs + cost_model.json), human-readable IDs Daryn can open in Excel: 15
orders, 5 machines (`CUT-01`/`PRESS-FAST`/`PRESS-SLOW`/`PAINT-01`/`HEAT-01`), ref
date Monday 2026-01-05, flat $60/h so a cost difference IS a time difference. NOT
generator output — authored by hand but borrowing the PROVEN minute values from the
generator's narrative builders (470-min contention op, 600-min-op / 5-weekday-slot
overtime economics, the 4B.0 fast/slow-press rate split) so the stories are
reliable, then re-verified by real solve. Seven features present EXACTLY ONCE: (1)
alternative group with honest per-machine rates (`RT-BRACKET` seq10 PRESS-FAST 5
min/u vs PRESS-SLOW 10 — one order takes the slow press, ~$250 more, not late); (2)
a splittable 900-min op (`ORD-03`) pausing at the overnight closure (two chunks); (3)
one order late BY DESIGN from pure capacity contention (`ORD-04` high holds `CUT-01`
Monday → `ORD-05` standard slips to Tuesday, data CLEAN, cause traceable); (4) a
Saturday overtime window rescuing `ORD-11` (600 min × 1.5 = 900) while `ORD-10` takes
Friday; (5) a two-machine precedence chain (`P-WIDGET` CUT→PAINT); (6) a setup_family
changeover (RED `ORD-09` / BLUE `ORD-12` on `PAINT-01`, 90-min colour change); (7)
the control (`ORD-13`, comfortably early). `README.md` narrates the story as
PREDICTIONS AUTHORED BEFORE THE SOLVE (contradiction = a finding, not a rewrite —
they held). Verified live: gate **ACCEPTED/C2/0 findings**; deterministic solve
reproduces all seven byte-identically; total $6956.83 = production 5006 + overtime
900 + setup 680 + tardiness 370.83 (decomposes exactly). **CU2 — the sabotage menu**
(`SABOTAGE_MENU.md`, one page): ten keyed one-cell edits (file · row · column →
value), each naming the rule caught (a real id from the 33), outcome/severity/grade,
and the certificate line — broken product ref (`ids.orders_resolve_to_products`),
impossible due date (`order_dates_internally_consistent`/TEMPORAL_IMPOSSIBILITY),
alt-group step-attr mismatch (#33 `alternative_step_attributes_agree`/AMBIGUOUS_SOURCE,
first-row-wins), statistical outlier (`durations_within_plausible_range`/INFO/**still
ACCEPTED**), duplicate identity, blank key (`key_fields_populated`/MALFORMED_FIELD/
**REJECTED**), unroutable step (`routes_resolve_to_lines`), a false-positive CONTROL
(a legal edit that trips NOTHING), facility mismatch, inactive route used
(`orders_use_active_routes`/LOW_CONFIDENCE_INPUT). Each verified ONCE, mechanically,
so no menu item is wrong about itself. Two build findings recorded: the outlier rule
is a PRODUCT-GROUP statistical check (needs ≥3 members with a low median — the clean
set groups the simple products into one `fabricated` family so the outlier has a
home); a NEGATIVE quantity is NOT a checked defect (no quantity-sign rule), so the
"malformed field" item uses a blank key — the gap noted, not papered over. **CU3 —
the walkthrough** (`WALKTHROUGH.md`, planner-voiced): clean submit → read + interrogate
the certificate (three registers: `what's wrong?`/`how do I fix the worst one?`/`what
should I fix first?`) → sabotage in batches → fix → solve → READ THE STORY (per-feature
question + receipt table, verified against the real explainer — e.g. `why is ORD-05
late?` → CAPACITY_BLOCKED on CUT-01 + 890-min metric) + the ORD-05 TRACE EXERCISE
(CSV row → gate → canonical entity → solver placement → cost ledger → "why" answer).
Exit bar: "you tried to catch it lying and could not." **CU4 — wiring:** `dev_api.ps1
-Scenario glass_box` copies the committed dataset verbatim into `_data/mrd` (no
generator; `.md`/gate_output excluded); ledger + LLM env already flow via `.env.local`
/ `MRE_DEV=1` / `MRE_DATA_ROOT` so audit questions are recorded (AI-track-2 fuel);
`.gitignore` gains `datasets/**/gate_output/`. **Tests:** new `tests/test_glass_box.py`
**19 passed** (1 clean gate + 10 sabotage items + 8 story, Part C slow); full non-slow
Python suite green; frontend untouched. See the docs/04 2026-07-18 Session 4B.1
amendment and docs/07 v2.24. Lesson: to make a system auditable you build the audit's
INSTRUMENTS, not its verdict — a dataset small enough to hold in one's head,
predictions authored BEFORE the solve, a sabotage menu every item of which is proven
right about itself, and a trace walkable by hand and by evidence to the same answer;
trust comes from trying to break it and failing.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4B.0 — IDS
alternative-resource doorway: per-alternative rates (connector-track opener)
2026-07-18.** The alternative-resource doorway (docs/06 §5.3) was HALF-built:
eligible *sets* entered through the CSV since Session 3.1, but per-alternative
*rates* did not. **CU1 (adapter truth, test-FIRST):** `IDSAdapter` grouped
repeated `(route_id, sequence)` rows into ONE `explicit_set` OperationSpec (not
last-wins, not two ops, not a crash) but read the time model from the FIRST ROW
ONLY — silently DROPPING every alternative's own `run_minutes_per_unit` (a
per-alternative rate never reached the solver: the latent silent-wrong, now a
standing regression `tests/test_ids_alternative_groups.py`). And the existing
multi-eligible scenario DID enter through the CSV doorway (generator writes the
rows, `test_multi_route` runs the full pipeline), so B2 pipeline-proof for
eligible *sets* was NOT one-sided — it was per-alternative *rates* that were
unproven. **CU2 (spec):** docs/06 → **v0.5** (§5.3 alternative groups:
per-alternative `setup_minutes`/`run_minutes_per_unit` → `rate_overrides`;
`setup_family`/`dwell`/`splittable`/`min_chunk` are STEP attributes that must
AGREE; `active=false` removes a row; zero active = unroutable; identical triples
= duplicates; `role` RESERVED for B3); docs/01 §5.5
`ResourceRequirement.rate_overrides {resource_ref → {base_setup, run_rate}}`
(empty ⇒ byte-identical guarantee); registry → **33 rules**
(`ids.alternative_step_attributes_agree`, AMBIGUOUS_SOURCE, conditional/degraded,
first-row-wins). **CU3 (implement):** new `ResourceRateOverride` struct +
`ResourceRequirement.rate_overrides`; `Operation.resource_setup_durations` /
`resource_run_durations` (qty-resolved Planner projections); the adapter captures
per-alternative overrides (first row = default, differing alternatives = an
override); the gate detects step-attribute disagreement (`the gate checks; it
never repairs` — the adapter proceeds first-row-wins); the Solver Builder builds a
**variable-duration** encoding for a HETEROGENEOUS op (the end var linked by each
machine's own optional interval, not a fixed `e==s+total`) while a HOMOGENEOUS op
keeps the exact scalar path untouched — the no-map byte-identical guarantee; the
extractor prices the chosen machine from the solved end−start (already honest) and
prices ALTERNATIVES at their own per-resource duration (reducing exactly to the
historical `(alt_rate−rate)×dur` when durations agree). Remediation catalog note
(note_version 1, cites §5.3). **CU4 (pipeline proof, doorway-first):** new
`multi_route_rates` generator scenario (per-alternative run times through the CSV,
EQUAL rates so price is purely duration); the counterfactual
(`tests/test_multi_route_rates.py`, slow) PINS the slow alternative and asserts,
through a real re-solve + extraction, a duration exactly 60 min longer and a
strictly higher cost — **B2 pipeline-proven honestly**; the coverage anomaly
`alternative_step_disagreement` fires the new gate rule. **Non-slow Python 1160
passed, 0 failed** (+12); goldens (sample_data schedule.csv + ledger)
byte-identical; slow guards green (multi_route pool + eligibility_consistency
13/13; multi_route_rates counterfactual 2/2). Frontend untouched. **Riders:**
`dev_api.ps1` loads `.env.local` + defaults `MRE_DEV=1` in dev; `dev_cockpit.ps1`
gains `-Resume` (reuse the last solved schedule, skip submit/solve/alternatives);
Fix-B extension — refusal/near-miss/clarify/refusals bundles short-circuit to
AUTHORED copy with NO LLM round-trip (defense-in-depth over the 4A.1c no-evidence
guard). **Named debts (R-AI1):** a resumable (splittable) op WITH rate_overrides
uses the scalar default duration (per-resource chunk-slot minutes are a follow-up;
the CU4 fixture is splittable=false, so latent); a heterogeneous op's
`var_map.op_durations` scalar (setup-transition adjacency + R-DP8 pin conflict
detection) is the DEFAULT representative — rate-varying pins unexercised this
session. See the docs/04 2026-07-18 Session 4B.0 amendment and docs/07 v2.23.
Lesson: a doorway proved for the STRUCTURE (eligible sets) is not proved for the
VALUES that ride through it (per-alternative rates) — read the adapter's truth
before trusting the claim, and where two rows disagree on a machine property vs an
operation property, split them: vary the rate, agree on the step.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.2 — planner surface
pass 1 (read layer only) 2026-07-17.** The first pass at making the cockpit read
like a PLANNER's board, not a demo Gantt — under one hard rule: **render only
what the model can source truthfully.** No interaction/solver changes.
**Contract 1.5 → 1.6 (additive):** `CalendarWindow.reason` (a closure/overtime
window carries its exception reason — the assembler was DROPPING it, collapsing
every closure to `kind="closure"`); `ServiceOutcomeBlock.customer_name` (resolved
via identity map — never a UUID on screen) `/ quantity`+`quantity_uom`
(`Demand.quantity` is a `Quantity {value,uom}`); `ResourceLane.booked_through` `/
next_open_gap` (per-row absolute facts, server-computed over the SAME flattened
windows the solver's eligibility uses via new `src/mre/modules/row_intelligence.py`
on `eligibility.flatten_resource_windows`). **CU1 — capacity backgrounds + shift
structure:** per-row banding off-shift (complement of declared windows) / closure
/ planned-maintenance / overtime (premium) / open-idle (regular ∩ no-work), both
themes, tokenized, pure-computed in `src/cockpit/legality/capacity.js`; shift-
boundary ticks. **CU2 — time anchors:** a now-line from the run's REFERENCE DATE
(the 3.3b epoch, never wall clock — absent, not faked, when reference_date is
null); due+release markers for the SELECTED order only; one `markers.js` overlay
tracking vis pan/zoom at ~0px drift. **CU3 — hover cards, planner-voiced:** a job
card (order/qty/due/customer/routing/late-tight/pin) + a downtime card (which
calendar state, reason, reopen time), via vis's own hit-test, external refs only.
**CU4 — row intelligence:** utilization % over the VISIBLE window (recomputed
live on pan), booked-through, next-gap — never from the DOM; `rowstats.js` is a
byte-for-byte port of `row_intelligence.py`, the two PINNED by shared fixtures
(`fixtures/rowstats_cases.json`, asserted from BOTH sides); a subtle row-label
strip. **CU5 — operation anatomy:** setup as a hatched leading bar segment (first
visual appearance of setup, from `phases.setup`); split ops as linked pieces with
a dashed kinship connector across each pause — WITHOUT disturbing the single-item
identity drag/citation/rebind rely on (single-chunk bars byte-unchanged; the
split path is additive); the R-DP8 standing-pin unified into the commitment
marker family. **Rider:** the dev question-ledger empty state reworded from "no
dev ledger (set MRE_DEV)" to planner copy naming what it is. **Harness:** a hand-
authored contract-1.6 planner fixture (`tools/build_planner_fixture.py` →
`fixtures/planner/`) exercising every feature the demo scenarios lack;
`planner.spec.mjs` screenshot-asserts each CU on BOTH themes; `rowstats.spec.mjs`
(logic) pins the port. **Non-slow Python 1148 passed, 0 failed**; **cockpit JS 113**
(was 94: +10 planner ×2 themes, +9 rowstats). **Named debts (R-AI1):** the
unplanned-downtime doorway (no observed-actuals channel — the band slot is
RESERVED, not painted — a planned closure is sourceable, a machine that actually
broke is not); utilization/gap have NO ask route yet (AI-track 2). Downtime cards
align with the existing calendar question route. See the docs/04 2026-07-17
Session 4.2 amendment and docs/07 v2.22. Lesson: a planner's board is mostly
ABSENCE made legible — off-shift, idle, closed, waiting; render only what you can
source, and where you can't (unplanned downtime), reserve the slot and name the
debt rather than paint a plausible lie.

**Roadmap position: Phase 3 COMPLETE (qualified); AI-track Session 4A.1c — the
testimony validator passed FABRICATED record citations 2026-07-17.** Live
(screenshots): LLM answers footnoted records that don't exist —
`[record: Nothing scheduled for all]`, `[record: evidence_chain_001]` — and "is
there a better schedule" answered with a schedule LISTING (prose) instead of a
refusal. **Cause:** the 4A.1 validator checked timestamps/numbers/machines + that
SOME footnote existed, but **never that a cited id is REAL**; and
`classify("is there a better schedule")` matched the BARE word "schedule" →
routed to the listing (a deterministic mis-route of an optimality question — "does
a BETTER plan EXIST" is re-optimization the deterministic surface can't answer).
The two defects share a root: an unresolvable question reaching the LLM renderer
with an empty/garbage evidence chain. **Fix A (citations must be real):**
`_build_prompt_material` also returns `known_records` (the real `record_id`s on the
bundle); `_validate_testimony` rule 5 — every `[record: X]` must PREFIX a real id
(the template footnotes an 8-char prefix), else regen → **template fallback** (the
bare `?` placeholder exempt). **Fix B (no-evidence → never the LLM):**
`LLMRenderer.render` short-circuits to the template body BEFORE any LLM call when
`not bundle.ordered_records` — a refusal / near-miss / clarify / empty listing has
nothing to testify from, so the model could only fabricate; authored header IS the
answer. **Fix C (optimality ≠ listing):** new `_OPTIMALITY_TRIGGERS` (better/best/
optimal/improve/cheaper/…) suppress the schedule-listing route → "is there a better
schedule" falls to `unsupported` → the honest refusal (rendered verbatim by B).
**Tests:** `tests/test_testimony_validation.py` (id-shaped + prose-as-citation
rejected → template; real-prefix passes; `?` exempt; empty/refusal bundle renders
with `calls == 0` — LLM never touched); `tests/test_interpreter.py` (better-schedule
→ unsupported/REFUSED, normal listing still routes); `tests/test_ask_chain_api.py`
slow (better-schedule refuses citing NO records; an injected fabricating LLM with a
real key degrades to template, no live `[record: …]` survives). The 14
`test_explainer.py` validator call sites thread `known_records`. **Non-slow Python
green** (+ new fast suites) + ask-chain **12/12** slow; frontend untouched
(backend-only). See the docs/04 2026-07-17 Session 4A.1c amendment and docs/07
v2.21. Lesson: "cite a record" is not "cite a REAL record" — validate the id against
the bundle, and never hand the model an empty evidence chain, because the only
citation it can then produce is a fabricated one.

**Roadmap position: Phase 3 COMPLETE (qualified); AI-track Session 4A.1b — the ask
endpoint 500'd with a real API key (mocked fail-closed ≠ real-path fail-closed)
2026-07-17.** Live: with `ANTHROPIC_API_KEY` set (+ the DEV build's `llm: true`),
the **taxonomy-shaped** question "why is ORD-000004 on F001-RES002?" — which routes
DETERMINISTICALLY — returned **HTTP 500** on `/ask`. The 4A.1 fail-closed tests all
injected a MOCK client, so the real path was never run (the named CI caveat) —
exactly what lived in the gap. **CU1 diagnosis (reproduced, layer named):**
`anthropic.Anthropic(bad_key)` does NOT raise (a bad key surfaces only on the first
CALL); the call `self._client.messages.create(...)` in `LLMRenderer._call_llm`
raises `anthropic.AuthenticationError` (a non-`ImportError`) and **`render()` had no
try/except around it**, so it propagated out of the synchronous handler → 500. The
layer is **response/request execution in the RENDERER**, not construction and not
the interpreter (whose `interpret()` already returns `None` on any exception); and a
deterministic route still renders THROUGH the LLM (testimony is prettified), so the
ordering guarantee must cover RENDER, not just classify-vs-interpret. **CU2 sealed
structurally (defense in depth):** `LLMRenderer.render`/`_render_register`/
`render_judgment` each wrap the whole LLM-touching body in one `try/except` →
deterministic TEMPLATE via a single `_template_fallback` (the renderer now NEVER
raises); `LLMRenderer`/`Interpreter` construction broadened `except ImportError` →
`except Exception`; the API `/ask` path adds the outer belt — `_answer_question`
re-routes DETERMINISTICALLY on a routing raise (interpreter off, ledger not double-
written) and renders through the single `_render_fail_closed` seam, both logging
`EVENT ask.llm_degraded`. A 5xx from the AI stack is no longer reachable. **CU3 the
ordering guarantee as a test:** `test_ask_chain_api.py` `TestAskFailClosedWithRealKey`
drives the endpoint with a genuine (invalid) key + `llm:true`, injecting an auth
failure / a garbage response / a raised exception at the call seam — each **200 +
`[rendered by: template]`**; the ordering test forces BOTH `Interpreter.interpret`
and `LLMRenderer._call_llm` to raise and asserts the taxonomy question still reaches
`route=late-orders`/`source=deterministic` and renders (template). Fast unmocked-
renderer coverage in `tests/test_render_fail_closed.py` (8 — auth/garbage/raised/
malformed-parse/register/construction-raise, real `anthropic.Anthropic` build).
**Non-slow Python 1126 passed** (+8, 0 failed) + slow ask-chain **10/10**; frontend
untouched (backend-only). See the docs/04 2026-07-17 Session 4A.1b amendment and
docs/07 v2.20. Lesson: a fail-closed guarantee proved only against a MOCK is
unproven — exercise real construction and the real call site (the one exception the
mock never throws is the one that reaches the user as a 500), and seal the RENDER
path, not just the router.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.1 — light theme as the
shipped default; theme as a first-class token dimension 2026-07-17.** Product
decision (Daryn's charter, ratified in docs/04): this product's visual language is
TRUST — the document, the ledger, dark ink on light paper; the dark cockpit
signalled *developer tool*. **Light is now the shipped default; dark is an option**
— and light is a DESIGNED theme, not an inversion. **CU1 — theme architecture:**
`src/cockpit/src/tokens.css` split into a STRUCTURAL layer (typography, spacing,
geometry, radii, motion TIMING — durations/easings/amplitudes — and the feel-panel
opacity multipliers; all theme-invariant, no color) + two COLOR files
(`theme-light.css` = `:root, :root[data-theme="light"]` — declared for a bare
`:root` too so the board renders light before any JS, NO flash on the default path;
`theme-dark.css` = `:root[data-theme="dark"]`, equal-specificity attribute selector,
overrides cleanly). Semantic ALIASES that are pure `var()` references (e.g.
`--voice-rec-fill: var(--bar-late)`) stay structural and resolve lazily against the
active theme. One chrome toggle in the top strip (shows the theme you'd switch TO); a
no-flash inline `<head>` script stamps `data-theme` from `?theme=`/`localStorage`
before first paint; `main.js` keeps it synced to URL + storage. Theme choice is a
**tier-2-class preference** (per-deployment default when that layer lands; URL/config
param + toggle now). **The feel panel's visual knobs write to the ACTIVE theme** (the
opacity multipliers mirror to `:root` inline; only one theme renders at once).
**CU2 — the light theme, designed (not inverted):** warm ivory PAPER bg (`#f6f4ef`),
dark-slate ink (`#23262d`), a warm-grey chrome/recess/hairline ramp, soft shadows.
**Lateness palette re-chosen colorblind-safe (deuteranopia checked on the red/amber
pair)** via THREE redundant cues — on-time BLUE (`#2f63bd`, the CVD anchor); tight
(`#d98a2b`, LIGHT warm orange) vs late (`#b5271e`, DARKER red) separated by
LIGHTNESS; and INK POLARITY (tight = dark ink, late = white ink) as a redundant
channel — all bar ink AA on its fill. Shading re-tuned for paper (dim = a cool grey
VEIL, green = a legal tint); **Daryn's dim-dominates-green verdict carries as
SEMANTICS** (opacities re-tune per theme at the feel panel). Ghosts/traces redrawn
(dark ghost-tag chip keeps prices legible over the board). **The tentative bar was
the one place carry ink had to become theme-aware** — the hatch used to sit on a
transparent backing with a hard-coded WHITE label (invisible on paper); 4.1 added
`--carry-ink`/`--tentative-ink`/`--tentative-backing`, so on light the hatch sits
over a translucent PAPER backing (reads NOT-YET-REAL) with DARK ink (legible).
Closures visible without murk; amber STANDING-PIN vs green transient pin-lock both
re-tuned to read on paper; refusal card / legend / cards / ask panel / ledger dock
all carry through the same tokens. **Dark kept working — its pre-4.1 colors moved
VERBATIM under the selector; no design effort on dark this session.** **CU3 —
contrast pass both themes + harness:** micro-chip typography bumped for AA (`--fs-2xs`
9→10px, `--fs-xs`→11px, register chip → semibold); the Playwright harness
**parametrized on `data-theme` via projects** (theme-free `logic` once + `light` +
`dark` each running EVERY rendering spec; each boot appends `&theme=<project>`, so
the **C1 label-vs-bar drift regression is asserted per theme**; screenshots + the
rehearsal report suffixed by theme, `shots/` gitignored). New `cockpit.spec` theme
test: light is the default (fresh context), the toggle flips attribute + palette
(paper base far brighter than the dark base — a designed theme, not a tint), the
chosen theme rides in the URL. **Cockpit JS 94 passed** (logic 6 + light 44 + dark
44; was 49 single-theme), C1 drift green both themes. Python untouched (frontend-
only): non-slow suite green as a regression guard. See docs/04 2026-07-17 Session 4.1
amendment and docs/07 v2.19. Lesson: a theme is a token DIMENSION, not a palette swap
— split structural from color, let one attribute select, design the light theme
rather than inverting the dark one; the single hard-coded `ink-inverse` (the
tentative hatch's white label) was exactly where an inversion would have failed
silently.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.0e — accepted
placements are standing commitments (R-DP8) 2026-07-17.** Live on the gesture
surface: an accepted, then PUBLISHED, edit was silently reverted by the NEXT edit's
re-solve — the delta card was honest ("ORD-000003 RES002→RES001 −1440min" listed as
a *consequence*), but a placement the planner already committed must not be movable
at all. **Cause:** the accept/sandbox re-solve pinned only the ONE op being dropped;
every prior accepted pin was free again, so the optimizer (correctly, for its
objective) undid a cost-neutral cross-machine move to recover a few dollars — a
commitment that survives only until the next solve is no commitment. **Ruling
(R-DP8, docs/04 verbatim):** an accepted edit's pin persists in the schedule lineage
as a STANDING constraint — compiled into EVERY subsequent sandbox, accept, and
scenario solve of that lineage — until explicitly released; an accepted placement is
a commitment WITH AUTHORITY (the `planner_edit` Decision), not a one-solve
preference. Release (`unpin`) is a NAMED carry-forward, not built. **CU1 —
persistence:** cumulative lineage pins live on the version
(`schedules.pins_json` + a `Registry._migrate` that ALTERs the column into pre-4.0e
DBs so old rows read as no-pins); an accept composes the new set
(`standing_pins.compose_lineage_pins`: the drop's op re-committed in place / a fresh
op appended, order-stable, never duplicated). The SINGLE seam is new
`src/mre/modules/standing_pins.py` — the primary drop AND the standing pins bind
through the SAME `apply_pin` (both axes mandatory, `PinUnsatisfiable` never
skipped-and-vouched — the 4.0-hotfix lesson; the 4.0b "give the layers ONE function
to call" discipline); `sandbox.py`/`planner_edit.py`/`scenario.py` all delegate
(`Registry.schedule_pins` gathers them at the API). **Conflict handled honestly:** a
drop INFEASIBLE against the standing pins returns a verdict that NAMES the blocking
commitment (`detect_conflict`, a conflict ONLY on a provable same-resource interval
overlap via the new `VariableMap.op_durations`, so precedence/calendar infeasibility
is never mis-blamed) — never a quiet sacrifice of the older pin. In a scenario the
pins are best-effort (a what-if may re-plan an op away; the applied count lands in
evidence as `standing_pins_applied`, never silent). **CU2 — visibility:** schedule
contract **1.4 → 1.5** (additive `AssignmentBlock.standing_pin`) — a subtle
PERSISTENT standing-pin marker (thin amber edge + faint ring, tokenized
`--standing-pin-*`, distinct from the transient green pin-lock that fades), and a
standing-pinned op is STRUCTURALLY excluded from every moved-set (`_moved_set`
`exclude_ops`, the freshly-dropped op exempt; the cockpit ghost path
`movedSetFromDoc` too) — removed at the source, not filtered. **CU3 — the missing
regression:** `tests/test_standing_pins.py` — fast units (shared seam + registry
round-trip + the pre-4.0e migration) + the two-edit chain END TO END (slow,
`multi_route_distinct`): edit A a cost-neutral cross-machine move accepted +
PUBLISHED, edit B accepted → A's placement UNCHANGED in B's version, A stays
`standing_pin=True`, A's op in NO moved-set of B's Decision; plus a drop onto a
commitment's slot refused (sandbox infeasible, accept 409). The cockpit harness
drives the same flow visually (`gesture.spec.mjs` — the fixture server composes
every ancestor pin into `GET /schedule` + flags them, as the real assembler does).
**Non-slow Python 1118 passed** (+15, 0 failed) + slow `standing_pins` **2/2**,
`planner_edit`/`sandbox`/`scenario` **55/55**, `forced_alternatives`/`eligibility`/
`api_endpoints` green, solver goldens byte-identical; **cockpit JS 49/49** (+1). See
the docs/04 2026-07-17 Session 4.0e amendment and docs/07 v2.18. Lesson: a hard
constraint that lives for exactly one solve is a preference; a commitment must be
compiled into every solve of its lineage, held in the registry, and structurally
un-moveable — the optimizer will otherwise, correctly and quietly, undo the very
decisions the planner made by hand.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.0d — MAX_PATH survives
the bound (the 4.0c fix was validated in a short prefix) 2026-07-16.** Follow-up to
4.0c: on Daryn's real stack **every** accept still failed `FileNotFoundError
[WinError 3]`, now even on a **fresh schedule, depth-1 edit**. **The blind spot,
named:** the 4.0c cap of **90** chars was calibrated against a short temp-dir
prefix; Daryn's real data root (`…\OneDrive\Documents\PythonProjects\mre\_data\…`)
spends ~130 chars before any snapshot id, so a chain grown *near* the cap (an id in
the ~75–90 range, which the collapse deliberately allows) plus
`\entities_serviceoutcome.jsonl` still crossed **MAX_PATH (260)** — the cap raced
the limit without accounting for the real prefix the temp tests never had.
**Reproduced deterministically** at a padded ~136-char prefix: naive write at 265
chars fails; the same write through a `\\?\` extended-length path succeeds
(`os.makedirs`/`open`/`shutil.copy2`/`copytree`/`glob` honor it — `pathlib
.Path.mkdir(parents=True)` does NOT, it walks to `\\?\C:` → `WinError 123`, so the
seam uses the low-level calls). **Fixed all three, in order of preference (defense
in depth): Fix 1 — long-path seam:** new `src/mre/modules/longpath.py` is the
SINGLE seam the snapshot/run store does disk I/O through — `extended(path)` returns
the `\\?\`-prefixed absolute string on Windows (idempotent; UNC-aware; no-op
off-Windows), lifting the 260 limit; `SnapshotStore`,
`registry.prepare_out_dir`, the accept/scenario `copytree`, and `_persist_document`
all route through it, so the **snapshot tree is MAX_PATH-proof regardless of
data-root or chain depth**. **Fix 2 — short opaque snapshot ids:**
`_edit_snapshot_id` no longer embeds lineage — it is a fixed-width
`snap-edit-<sha256(base|hash)[:12]>` = **22 chars**, deterministic per
(base, hash) + distinct per parent; the parent chain lives in the registry's
`parent_schedule_id`, so the on-disk name is tiny however deep the chain (the 4.0c
grow-then-collapse scheme + its 90-char ceiling are gone; `_MAX_EDIT_SNAP_ID_LEN`
repurposed to a guaranteed ceiling of 32 the tests assert against). **Fix 3 — boot
/ `/health` path-budget tripwire:** `longpath.path_budget(root)` reports the
worst-case snapshot path length + `status` (`at_risk` when it exceeds 260 even with
a bounded id) + `long_path_mitigation`; `create_app` **warns loudly at startup** on
an at-risk root and `/health` carries the block — a path-length problem is never
again found only at accept time. **Arithmetic:** Daryn's ~130 prefix → 4.0d opaque
id (22) = 183 (fix 2 alone clears it); a pathological >200 prefix that would push
even the 22-char child past 260 is defeated by fix 1's `\\?\` seam — belt and
suspenders. **Tests at a REALISTIC prefix (the temp-dir blind spot cannot recur):**
`tests/test_longpath.py` (fast — `extended()` shape/idempotency/UNC/pass-through; a
SnapshotStore **write→derive→read round-trip at a >260-char path** with a naive
**negative control** proving the limit is real; `path_budget` ok vs at_risk);
`tests/test_edit_snapshot_id.py` rewritten for the opaque scheme (short/fixed-width/
opaque; a 50-deep chain stays one constant length; deterministic + distinct);
`tests/test_planner_edit.py` `TestAcceptAtARealisticDataRootPrefix` (**slow,
end-to-end** — a real solve+accept under a data root padded so the prefix reaches
~160, deep enough that a 4.0c-era ~88-char id WOULD have crossed 260 [asserted],
succeeds and lands on the pinned resource+start); `/health` gains a `path_budget`
assertion. **Non-slow Python 1103 passed** (+7, 0 failed) + slow `planner_edit`
**11/11** (+1); cockpit untouched (backend-only), **JS 48/48**. **Named residual:**
the shallow run-dir writers (Reporter evidence sink, certificate writers) are not
on the seam — safe at Daryn's real depth, flagged by the budget check for absurd
(>200-char) roots, not silently left. See the docs/04 2026-07-16 Session 4.0d
amendment and docs/07 v2.17. Lesson: a bound validated against a short test prefix
is a bound with an unmeasured margin — pin the budget to the REAL deployment path
length, and prefer making the limit not exist (`\\?\`) over racing it with an
ever-tighter cap.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.0c — the silent
accept (an accept that 409'd on a storage limit, rendered mutely) 2026-07-16.**
Live specimen: schedule `ea1a42f0` in Daryn's `_data` root — sandbox verdict
succeeds (+0.70% proven, ORD-000004 RES001→RES003 on `multi_route_distinct`),
Accept pressed, bar returns to RES001 with **no error** and the **same id** (no
new version). **CU1 — diagnosed against the live registry FIRST:** `ea1a42f0` has
**no child** (`parent_schedule_id`) and is `proposed`, not superseded → the accept
did NOT commit and was NOT a supersede-409 (**suspect 3 — rebind-not-firing —
refuted**); the `runs` table showed **11 failed accept runs, all with the
identical** `FileNotFoundError: [WinError 3] The system cannot find the path
specified` (**suspect 2 confirmed; suspect 1 — the 4.0-hotfix's post-condition —
refuted**). **Mechanism, reproduced deterministically:** `apply_planner_edit`
minted each accepted child as `f"{base_snapshot_id}--edit-{hash}"`, appending
unboundedly; `ea1a42f0`'s snapshot id is a **7-deep, 118-char** `--edit-…` chain,
and at that depth the dir path `…\_data\runs\<uuid>\snapshots\<child>\entities_
serviceoutcome.jsonl` crosses **Windows MAX_PATH (260)** → the child derive
(`shutil.copy2`/`copytree`) fails, `_execute_accept` raises `HTTPException(409,
"accept failed: …")`, and — pre-4.0c — the cockpit's `accept().catch` called
`returnHome(reason, keepCard=false)`, hiding the card AND the reason: a
committed-looking edit vanishing silently (a temp-dir repro passed only because
its shorter prefix stayed under 260 — why it never surfaced in tests). **Named
plainly, per the close:** the hotfix's guard did NOT cause this — the post-solve
R-DP1 post-condition already compares in the canonical minute grid
(`op_start_minutes`, int `solver.Value()`, vs int `pin_start_min`), no datetime
re-serialized, no rounding seam; the 409 came from storage upstream of the check
(hardened anyway: solved start coerced `int()` + comment). **CU2 root-cause fix:**
new `_edit_snapshot_id(base, hash)` bounds the id at `_MAX_EDIT_SNAP_ID_LEN=90` —
shallow chains keep the readable `<base>--edit-<hash>` lineage; deeper ones
**collapse** to `{root}--chain-{sha256(base)[:12]}--edit-{hash}` (`root` = up to
the FIRST edit/chain marker, so a second collapse never re-accumulates `--chain-`
— fixed-width however deep; digest over the exact parent id → deterministic +
collision-free per lineage). Every base is thereafter a root or an already-bounded
child, so **no fresh chain can reach MAX_PATH**; the lineage lives in the
registry's `parent_schedule_id` chain (`ea1a42f0`'s pre-existing 118-char id can't
be retroactively shortened — accepting on it still fails, but now LOUDLY).
**CU3 — a refused accept is LOUD (R-M1a), regardless of cause:** `accept().catch`
on a non-superseded failure calls `card.showRefused({reason})` — an authored line
("Edit not saved · the plan is unchanged" + "This placement couldn't be committed
— the schedule of record still stands. Nothing was changed.") with the raw server
reason kept as a muted `.dc-detail` (never hidden) — then snaps home with
`keepCard=true`; the card wears a `refused` class (rejected border + one-shot
`card-refuse` shake; reduced-motion drops the shake, keeps the text). A silent
bar-goes-home on a committed gesture is no longer reachable. **CU4 — the DEV
question-ledger refusal panel (4A.1) occluded ask:** it was `position:fixed;
right;bottom;z-index 40`, floating over the ask composer — now docked bottom-**left**
(never over ask), **collapsible**, **collapsed by default** (header only; the body,
incl. the "no dev ledger (set MRE_DEV)" empty state, lives inside the docked panel
and loads lazily on first expand). **Tests:** `tests/test_edit_snapshot_id.py`
(fast — shallow lineage kept; the 7-deep `ea1a42f0` shape stays ≤ cap; a 50-deep
accept-on-accept chain never crosses it [caught a mid-session collapse-recursion
bug]; determinism + per-parent distinctness) + a `gesture.spec.mjs` mocked-409
loud-refusal test (`.delta-card.refused` visible with authored line + raw reason;
base id stays bound). **Non-slow Python 1096 passed** (+4) + slow `planner_edit`
**10/10**; **cockpit JS 48/48** (was 47). See the docs/04 2026-07-16 Session 4.0c
amendment and docs/07 v2.16. Lesson: a snapshot id that embeds its whole ancestry
is a path-length bomb on a chained-edit workflow — bound the name, keep the lineage
in the registry; and a hard failure surfaced through `returnHome(reason,
keepCard=false)` IS a silent failure — refuse loudly, never drop the reason.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.0b — Tier-0 vs solver
eligibility unified to one source of truth (R-DP6) 2026-07-16.** Follow-up to the
4.0-hotfix: could Tier-0 GREEN the un-pinnable row the pin then silently skips?
Eligibility was resolved TWICE by hand — the Solver Builder (which resources get
an `op_assign` literal, the set the R-DP1 pin binds) and the schedule-document
assembler (the payload's `eligible_resource_ids`). **CU1 divergence:** the payload
advertised the RAW capability set (`var_map.op_eligible`, pre-prune) while the pin
binds the COMPILED set (`var_map.op_assign`), which the builder further prunes for
**resumable** ops (a capability-eligible resource with no in-horizon calendar
window that could finish it → `_feasible_window_range is None` → no literal) and
**WIP** ops (no free literal). So `payload_eligible(op) ⊇ solver_literals(op)`,
strict-superset-possible → Tier-0 could offer a row the pin silently skips. **A
probe found 0/100 ops diverge on `multi_route_distinct` + `busy_board`** (both
`splittable=0, wip=0` → raw == compiled): the gap is **latent, not active on the
demo path**, then reproduced deterministically on a constructed resumable op.
**Live case, by evidence:** on `busy_board` ORD-000002's RES001 op is eligible on
{RES001,RES003,RES005}, so **RES002 is capability-DIM for it** and its `op_assign`
has no RES002 literal — payload and solver AGREE it is ineligible (data honest);
on `multi_route_distinct` the op IS eligible on {RES001,RES002}, both
green/pinnable (the +0.30% HONEST reproduction). **Neither fixture greens an
un-pinnable row**, and the client `drop()` refuses `!legal` before any
sandbox/ghost path — so refusal enforcement is intact; the live symptom was the
pin-skip the hotfix already closed. **CU2 unify (narrow waist):** new ortools-free
`src/mre/modules/eligibility.py` is the SINGLE definition of `capability_eligible`
(explicit_set/capability resolution, solver order preserved → goldens unchanged),
`feasible_window_range` + `flatten_resource_windows` (moved from the solver), and
`pinnable_resources` (the literal set + a dim reason for pruned rows). The Solver
Builder **delegates** all three (byte-identical solves); the assembler derives
`eligible_resource_ids` = `pinnable_resources(...)` and carries the SAME prune as
truthful `dim_reasons` (`no_calendar_window` / `wip_fixed`) — the two sets equal
**by construction**. Schedule contract **1.3 → 1.4** (additive `dim_reasons`;
`eligible_resource_ids` narrows to the solver-pinnable set — byte-identical on the
demo fixtures, never wider). Cockpit surfaces the reasons (`tier0.js`/`shade.js`/
`controller.js` REASONS: "no open calendar window this horizon"). **CU3 guard:**
`tests/test_eligibility_consistency.py` — (slow) payload `eligible_resource_ids`
== `op_assign` keys for every op on `multi_route_distinct` AND `busy_board`; (fast)
the constructed resumable case (solver prunes the dead machine, payload prunes +
names it, never greened) + the shared resolver's unit cases; and a
`legality.spec.mjs` row-type test (eligible/capability-ineligible/solver-pruned →
**takes/dims/dims**). Related copy noted, not fixed: `planner._eligible_resource_ids`
(OperationSpec allocation, a separate concern). **Non-slow Python 1092 passed**
(+6; `test_declared_but_unread` consumer list gained `eligibility.py`) + the slow
eligibility guard; solver goldens byte-identical; planner_edit/sandbox/
forced_alternatives slow green (R-DP1 accept guard intact); **cockpit JS 47/47**
(was 46). See the docs/04 2026-07-16 Session 4.0b amendment and docs/07 v2.15.
Lesson: when two layers must agree on an invariant, don't have each *compute* it —
give them ONE function to *call*; a payload reporting RAW capability while the pin
binds the COMPILED set is a divergence wearing an "eligible" label.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 4.0-hotfix — an accepted
cross-machine drop landed on the wrong machine (R-DP1 VIOLATED in shipped code)
2026-07-16.** Live report: drag ORD-000002 RES001→RES002, verdict "+0.30% proven,"
Accept → the new version rendered the op back on **RES001** (right time, wrong
machine). **CU1 diagnosis (by evidence, before the fix):** the pin was applied as
`lit = op_assign[op].get(resource); if lit is not None: model.add(lit == 1)` in
BOTH `sandbox.py` and `planner_edit.py`. `op_assign[op]` keys only the op's
**eligible** resources, so a target with no literal → the machine pin **silently
skipped**; the time pin binds alone; the re-solve legally relocates the op to its
cheaper eligible machine and reports a **feasible verdict for a placement never
tested**. Reproduced deterministically: an eligible id-matching cross-machine pin
binds end to end and reproduces the reported **+0.30%** *exactly* (honest); an
**un-pinnable** target yields OPTIMAL/feasible/0.0% while the op stays on the
incumbent — the live symptom. Sandbox and accept use the SAME pin (identical code,
identical cockpit params) — they cannot diverge; the "verdict pinned both, accept
re-compiled differently" hypothesis is **refuted**. **R-DP1 was violated in
shipped code:** the machine axis was offered, not enforced, then vouched for.
**CU2 fix:** the machine pin is **mandatory** — accept **raises** (API 409, base
stands) on an absent start/machine literal + a **post-solve R-DP1 post-condition**
(solved (resource,start) must equal the pin before minting); sandbox **short-
circuits to an honest INFEASIBLE return-home** ("this placement isn't possible")
instead of a false-happy delta. Eligible/same-machine pins unaffected. **CU3 the
permanent assertion:** the 3.4/3.8 suites pinned only same-machine
(`_pin_from_incumbent`) and never asserted placement — added
`TestAcceptHonoursThePinnedResource` (slow, `multi_route_distinct`: cross-machine
accept lands on the pinned resource+start; ineligible pin refused 409/infeasible,
never relocated) + a `gesture.spec.mjs` cross-machine drag→accept→rebind
**rendered-row** assertion + the same R-DP1 end-state check in `rehearsal.spec.mjs`
Beat 4. **Non-slow Python 1086 passed** (new accept tests are slow: planner_edit
**10/10**, sandbox **12/12**); **cockpit JS 46/46** (was 45). See the docs/04
2026-07-16 Session 4.0-hotfix amendment and docs/07 v2.14. Lesson: a hard
invariant applied through `if <exists>:` is a suggestion the code drops the moment
the thing is missing, then reports success — enforce, or refuse; never skip-and-
vouch.

**Roadmap position: Phase 3 COMPLETE (qualified); AI-track Session 4A.1 — R-AI1 +
the interpreter, conversational context, and the question ledger 2026-07-16.**
First AI-track session. **R-AI1 ruled** (docs/04, verbatim — "everything logs
facts and establishes pathways to AI"; every capability ships AI-reachable or
names its debt; intelligence accrues only in reviewable artifacts, never model
state; unanswerable questions are logged facts feeding a human-curated loop). The
M10 router is wrapped WITHOUT changing its routing: `Explainer.answer()` is now
`route(*classify(question))` over a **closed 15-route taxonomy** (`ROUTE_TAXONOMY`),
branch order byte-for-byte preserved — the deterministic path never touches an
LLM. **CU1 interpreter** (`src/mre/modules/interpreter.py`): phrasing →
(route, params, confidence) onto the taxonomy ONLY, invoked only on a
deterministic miss; LLM-backed, strict JSON, **fail-closed** (no key/malformed/
unknown-route/low-conf → honest refusal); params resolve through the identity map
(external refs in, unique-substring, **no id-shape regex**); a high-confidence
fully-resolved route synthesizes its canonical question and re-routes through the
same assemblers. **CU2 context** (`resolve_followup`): deterministic ellipsis
resolution before routing ("and what would fix it?" → against the last order;
"how much?" after an edit → edit-cost), **visible** (resolved question rides back
on `bundle.question`; the cockpit shows an "interpreted as" note); unresolvable →
**clarify**, never a guess; the server stays stateless (the cockpit carries a
4-turn history + selection + session id in the `/ask` body). **CU3 ledger**
(`question_ledger.py`; shape in `contracts/question_ledger.py`): every ask →
one `QuestionLedgerEntry` in its OWN append-only JSONL under the data root
(`ledger/questions.jsonl`), **never** in a run's evidence; carries verbatim +
resolved question, route/REFUSED/NEAR_MISS/CLARIFY, source, confidence, register,
schedule id, session id, and **rephrase linkage** (a refusal → its later
successful rephrase within 180 s = free labeled data); `refusal_clusters()` backs
a DEV-gated cockpit panel; `GET /ledger/refusals` is DEV-gated (404 unless
`MRE_DEV`); a **meta-route** ("what questions couldn't you answer recently?")
reads the ledger — it answers about itself. **CU4 tiered fallback**
(`ask_fallback_copy.py`, all copy AUTHORED): a **near-miss bridge** (confidence in
[0.45, 0.75) OR partial params → the two nearest routes as one-phrase offers)
between routed and refused; the full refusal keeps the planner-language capability
list; no dead ends. **R-AI1 close-out:** evidence = the ledger records; pathway =
the interpreter + taxonomy + the meta-route; **debts NAMED, not built** (AI-track
Session 2/3): WIP has no question domain, cross-run economics has none,
constraint-catalog "why can't it do X" is not conversational. **1086 non-slow
Python passed (0 failed)** (+50) + the slow ask-chain ladder; **cockpit JS 45/45**
(was 44). See the docs/04 2026-07-16 R-AI1 + Session 4A.1 amendments and docs/07
v2.13.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 3.8 — version-lifecycle
continuity in the cockpit 2026-07-16. Queue before Phase-4 design unchanged:
Daryn's grand feel pass + export.** Feel-pass findings: after an accept→publish
the cockpit stayed bound to the **superseded** schedule id — `/ask` returned a raw
"superseded" error, a subsequent accepted drop **returned home** (a committed edit
apparently rendering as a rejection, R-DP1/R-M1a as experienced), and Tier-0
shading/ghosts rendered from the stale version's payload while drops validated
against reality (**zombie legality**). Backend + gesture surface only; no
solver/model changes. **CU2 — diagnose FIRST (which case it was):** reproduced
against the real API — a board stale-bound to a superseded id gets **409 "is
superseded"** on `/sandbox`, `/accept`, and `/ask`, while `/interaction` still
**200s** (no status guard). So the returned-home drop was **NOT** a committed edit
reverting (the suspected case A); it was **case B — the accept/sandbox itself
409'd against a superseded id, the backend never committing** — surfaced by the
controller as a generic `sandbox error`/silent return-home; the zombie legality is
the same asymmetry (interaction served, mutations refused). The backend lifecycle
is correct (accept mints a proposed-with-interaction child; publish supersedes the
immediate parent; sequential edits re-enter accept — all already tested); the
defect is entirely the cockpit's **version binding + superseded-response
handling**. **CU1 — full continuity:** every version change (accept AND publish)
now routes through one `main.js` seam that updates the **URL**
(`history.replaceState`, other params preserved), the strip (new id + live
status), the ask target, the **shared selection** (`panel.clearSelection()` — a
moved op's scope is stale), and the harness hook; the deep-link boot also stamps
the resolved id into the URL. The controller already re-fetches the new version's
interaction + alternatives on accept (`rebindController`); publish keeps the id.
Invariant restated: **no user action may ever be issued against a superseded id
from a live session.** **CU3 — superseded UX:** additive `Registry.live_successor`
(follows the child chain forward to the live descendant) + `successor_id` on a
superseded `GET /meta`; a typed `ApiError.superseded` (409 + "is superseded") +
`resolveSuccessor` in `api.js`. A **deep link** to a superseded id loads read-only
behind a banner ("This plan was replaced by a newer version" + a one-click *View
current (<id8>)* jump) with the **gesture surface deliberately not wired** (never
an editable zombie); a **live** 409 self-heals — the ask panel renders planner
language + a jump (`appendSuperseded`), the controller's drop/accept catch routes
to the live successor. Jumps do a clean full reload bound to the successor.
**Harness — the missing seam:** the hermetic fixture server now models the
lifecycle (records each accept's parent, supersedes the immediate parent on
publish + records the successor, answers `/ask`|`/sandbox`|`/accept`|`/publish`
against a superseded id with **409**, serves `successor_id` on a superseded
`/meta`, composes the whole edit chain's pins in `GET /schedule`, and exposes
`POST /__test__/reset` called before each `boot()` so a publish never leaks across
tests); three new `gesture.spec.mjs` tests — **two consecutive edit→accept
cycles** (hook/controller/URL advance together, each accepted bar stays where
committed), **edit→accept→publish→edit** (post-publish edit re-enters accept on
the published version, never a superseded-id 409→return-home), and the
**superseded deep link** (read-only banner + jump, gesture not wired). **Cockpit
JS 44/44** (was 41); Python **1036 non-slow passed (0 failed)** + planner_edit slow
**7/7** (new `test_superseded_meta_carries_its_live_successor`). See the docs/04
2026-07-16 Session 3.8 amendment and docs/07 v2.12.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 3.7 — voice input
hardening 2026-07-15. Queue before Phase-4 design unchanged: Daryn's grand feel
pass + export.** A bug seen live on the gesture surface: press-and-hold voice
recording streamed the interim transcript into the ask composer, reflowed the
panel, and shifted the **mic button out from under the pressed pointer** —
`pointerup`/`pointerleave` then stopped recognition early and only a **fragment**
was submitted. Two-part fix, voice only (no solver/API/gesture-logic changes).
**CU1 — no layout motion during recording:** the interim transcript renders in a
**fixed-footprint FLOATING overlay** (`.voice-overlay`, absolute + translated
above the composer, fixed height, single-line ellipsis) written ONLY by
`onInterim` — the input is untouched mid-record; the **final** transcript lands in
the input only on **stop**, then runs on the spoken path (register aloud + one
sentence, record ids never voiced — 3.4 contract un-regressed). Nothing under an
active pointer moves (R-M1 spirit). **CU2 — interaction model:** press-and-hold →
**tap-to-start / tap-to-stop toggle** (`voice.js` `createVoiceInput` replaces
`createPushToTalk`; the mic click calls `voice.toggle()`, no pointer-capture
coupling) — push-to-talk **explicitness** preserved (the mic never opens itself);
**unmistakable recording state** (tokenized: mic `.recording` solid-red fill +
pulse + `aria-pressed`; a pulsing `--voice-rec-dot` + "recording" label in the
overlay); **Escape cancels** without submitting (`voice.cancel()`→`abort()`, a
`cancelled` flag suppresses the submit; a `window` keydown active only while
`listening()`); **optional 2.5s silence auto-stop** (`VOICE_SILENCE_MS` + a
`silenceMs` option), **OFF by default** — explicit tap-to-stop is the contract.
The recognizer runs `continuous` + **accumulates finals across result events**
(never resets `finalText` mid-session), which is what keeps the whole sentence
instead of a leading fragment. All voice visuals tokenized in `tokens.css`
(`--voice-rec-*`/`--voice-overlay-*`); a `@media (prefers-reduced-motion)` block
drops the pulse (recording still unmistakable via the solid fill + label).
**Harness:** headless has no microphone, so a **fake `SpeechRecognition`**
injected before page scripts (`window.__VOICE_TEST_RECOGNITION`, honored by
`recognitionCtor()` — harness-only) drives the REAL controller/UI; three new
`gesture.spec.mjs` tests — recording toggles (class + `aria-pressed` + overlay), a
long interim leaves the **mic bounding box unchanged** (≤0.5px) with capture
live, and the **fragment regression** submits the FULL sentence (Escape submits
nothing). **Cockpit JS 41/41** (was 38); Python untouched. See the docs/04
2026-07-15 Session 3.7 amendment and docs/07 v2.11.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 3.6 — R-M1
implementation (motion carries register) 2026-07-15. Queue before Phase-4 design:
exactly Daryn's grand feel pass + export.** Animation only — no solver/API/
gesture-logic changes; the R-M1 ruling implemented as written, consuming the 3.5
motion tokens. **CU1 REJECTION** (`returnHome`): a FAST snap-back of the existing
carry element (`--motion-reject-*`, non-settling ease so it reads "refused" not
"placed") + a brief arrival `reject-shake`; the reason stays in the text channels
(un-regressed). **CU2 REFLOW** (`board.rebind`): ONE implementation unifying the
consequence motion + the 3.4 accept-rebind — a single `.reflowing` class enables a
SIMULTANEOUS eased transition on all bars (`transition-delay:0 !important`,
explicitly no per-bar stagger — CP-SAT re-solves globally), displaced bars get a
one-shot `reflow-moved` highlight. **CU3 OWN PLACEMENT**: the dropped bar never
slides — `pin-lock` is baked into its reposition update and the reflow selector is
`:not(.pin-lock)`, so it SNAPS to the committed spot with a static green pin-lock
ring (distinct from the tentative purple); pin-lock persists until the next
gesture (`board.clearMotionClasses`). **CU4 GHOSTS** (`fadeGhosts`): fade only,
labels fading WITH bars (both `.drag-ghosts` + `.drag-ghost-labels`), on grab +
on-demand arrival. **Reduced motion**: one `@media (prefers-reduced-motion)` block
→ instant; motion classes/semantics intact, rejection still distinct via text.
Four motion end-state harness tests (post-rejection == origin; simultaneous reflow
`transition-delay:0`; pin-lock present post-accept; reduced-motion end-states).
**Cockpit JS 38/38** (was 34); Python untouched. **Carry-forward: the ONLY
remaining Phase-3 item is Daryn's grand feel pass + export** — the tuning panel now
exposes every visual + motion token (incl. the R-M1 group). Phase-4 ENTRY
conditions (cold-stranger cold-drive; cloud in-cloud) are gates, distinct from the
build queue; the rest (slice-awareness, LLM voice normalizer, ghost precompute
dial (a), pool-ghost partial consequences, real auth) are Phase-4+/pilot-gated/
post-pilot. See the docs/04 2026-07-15 Session 3.6 amendment and docs/07 v2.10.

**Roadmap position: Phase 3 COMPLETE (qualified); Session 3.5 — R-M1 ruling +
cockpit design-token pass 2026-07-15. Next: Session 3.6 (R-M1 implementation).**
Two parts, visual-only (zero behavior changes). **Part 1 — R-M1 ruling** ("MOTION
CARRIES REGISTER", docs/04, transcribed verbatim; implementation is 3.6): bar
motion is communication with a fixed vocabulary — (a) REJECTION = fast snap-back
+ subtle shake, no settling ease; (b) REFLOW = smooth SIMULTANEOUS eased
transitions (~300–400ms), never cascaded (CP-SAT re-solves globally; the 3.4
accept-rebind "settle" unifies under this class in 3.6); (c) OWN PLACEMENT =
never moves, a static pin-lock; (d) GHOSTS = fade only, labels fade WITH bars.
All durations/easings/shake are design tokens; semantics fixed by the ruling.
**Part 2 — the token pass:** every cockpit palette/typography/geometry/elevation/
motion value consolidated into `src/cockpit/src/tokens.css` (grepping `cockpit.css`
/`drag.css` for a bare hex or px font-size returns nothing); a typography scale
(`--font-ui`/`--font-mono` + `--fs-*`/`--fw-*`), elevation scale (`--shadow-*`),
bar-geometry tokens (`--bar-radius`/`--bar-sheen`), and general motion durations
added. The **R-M1 motion tokens** (`--motion-reject-*`/`-reflow-*`/`-pinlock-*`/
`-ghost-fade-*`) added NAMED-BUT-UNCONSUMED — 3.6 implements against them; they
are panel-tunable now (`feel.js` `motion.*` + `applyFeel` mirror; the tuning panel
gained group headers + motion/geometry groups). Restrained modernization applied
(calmer chrome, cleaner 4px bars + sheen, better typography, unified elevation) —
sleek, not flashy. **Zero behavior changes: cockpit JS 34/34 unchanged** (shots
gitignored/not pixel-compared; C1 drift ≤1px holds); Python untouched. See the
docs/04 2026-07-15 R-M1 + token-pass amendments and docs/07 v2.9.

**Roadmap position: PHASE 3 COMPLETE (qualified) — exit audit done 2026-07-15;
entering Phase 4 preparation.** A fresh audit session ran the six exit clauses
LIVE on the real dev stack (uvicorn + `busy_board`, deterministic). **One seam
found and FIXED in-session (the audit earning its keep):** the delta card
rendered the SCALED solver objective delta as dollars — on `busy_board` it would
have shown "+$602" for a true ledger cost delta of "+$5.02" (~120×). Fixed:
`SandboxResult` carries `cost_delta_abs`/`cost_delta_pct` from a no-persist
extraction of the re-solve's ledger vs the base total; `apply_planner_edit`
exposes the decomposed `cost_delta` and the accept response carries it; the
cockpit card shows dollars ONLY when ledger-backed and degrades to a
relative-%-vs-current-plan label otherwise (never a false `$`). Re-verified LIVE
("+0.01% cost · +$5.02", decomposing exactly). **Clause verdicts:** C1 (script
LIVE ×2, deterministic legs agree; accept→Decision→publish→supersede→
pool-invalidation→summarize all verified) PASS-qualified (sandbox ships the
honest FLAGGED card within the 15 s budget on busy_board; LLM off — no key; voice
driven programmatically); C2 (honesty armor) FAILED→FIXED→re-verified; C3 (R-DP)
PASS via harness; C4 latency baselines recorded LIVE (first-grab ghosts **6.2 s**,
cached **3.6 ms**, sandbox **15 s = budget→flagged**, grab→shade **5.2 ms**); C5
(cold stranger) **MET-BY-PROXY** — the cold-drive is a NAMED Phase-4 entry
condition; C6 carry-forwards inventoried (**feel tokens NOT yet exported/
committed** — runs on `DEFAULT_FEEL`; cloud in-cloud 2.4b; slice-awareness; LLM
voice normalizer; ghost precompute dial (a); pool-ghost partial consequences;
real auth). `busy_board` = 90 scheduled assignments (the "hundreds of ops"
phrasing was imprecise). **1036 non-slow Python passed (0 failed)** + slow
sandbox/planner_edit ladder + **cockpit 34/34**. See the docs/04 2026-07-15
Phase 3 exit-audit amendment and docs/07 v2.8.

**Roadmap position: Phase 3 BUILD COMPLETE — Session 3.4:
the interim final 2026-07-15.** The last build session of Phase 3; it ends with
the sixty-second script running end to end. Five CUs + three riders.
**CU1** (headline): **accept → Decision → publish**. Accept on the delta card is
REAL — an accepted edit records a `planner_edit` Decision (new decision_type;
**basis=observed**, a human command; **authority MANDATORY**, dev token now / real
auth post-pilot; new optional `Decision.authority`) and mints a NEW **proposed**
schedule version — the base is NEVER mutated ("accept CREATES, never
overwrites"). Backend `modules/planner_edit.py` (`apply_planner_edit`: derive a
child snapshot copying every planned entity but the M7 outputs → warm-start + pin
the dropped op R-DP1 → re-solve under budget → extract is_scenario=False → record
one Decision carrying the decomposed cost delta + annotated moved-set). API
`POST /schedules/{id}/accept` (sync, parent-linked) + `POST /schedules/{id}/
publish` (`Registry.publish_schedule`: proposed → published, supersede the
immediate parent, invalidate its pools). **The registry is the live-lifecycle
truth** — the served document status is frozen at assembly, `/meta` reflects
current state (the strip reads it). Chained edits inherit the reference date from
the ROOT solve (the 3.3b wall-clock trap avoided by construction). Cockpit: the
delta card walks verdict → accepted → published (Accept + Publish LIVE now);
`board.rebind(newDoc)` settles the moved bars into place by re-stamping new
assignments with old bar ids (R-DP7, not a teleport-reload); the controller + ask
panel retarget the new version (sequential edits + asks read the new version).
**CU2**: the sandbox/edit **question domain** — `_summarize_edits` ("summarize
what I changed and what it cost", the closing beat) + `_explain_edit_cost`
(production Δ + setup Δ + tardiness Δ, decomposing exactly + the 3.3 "why"
clauses) over the `planner_edit` Decisions; no new answer path (the Decision is
self-contained evidence); new renderer subject types; honest refusal when no edit
exists. **CU3**: **voice** (`src/cockpit/src/voice.js`) — push-to-talk (Web
Speech, feature-detected, degrades to typed WITHOUT drama) into the SAME ask path
(the deterministic router IS the transcript→route mapper, its "unsupported"
bundle IS the low-confidence refusal — no LLM-interpreter added; the LLM never
authors answers); `spokenSummary` leads with the register aloud + one sentence
and STRIPS every id-shape (record ids NEVER voiced). **CU4**: ghost latency —
pricing fires on pointer-DOWN (dial b, eager=silent) + the K per-machine solves
run in a bounded pool (`ONDEMAND_SOLVE_WORKERS=4`, dial c; CP-SAT frees the GIL
in search, per-solve determinism unchanged); grab→shade 5.2 ms measured; dial (a)
precompute widening already in 3.3, deepening it a carry-forward. **CU5**: the
**rehearsal** (`tests/cockpit/rehearsal.spec.mjs`) — the sixty-second script beat
by beat, screenshot-asserted, each beat's latency recorded to
`shots/rehearsal_report.json`, every beat green (557 ms hermetic total; the REAL
accept→Decision→publish + REAL decomposed edit answer proven against the live API
by the Python tests). **Riders**: dev PS scripts ALREADY self-locate via
`$PSScriptRoot` (confirmed); datetime.now() audit — only the known
validator/solver_builder/scenario fallbacks, none new, accept threads the ref
date from the root solve; feel-token export (`drag/tuning.js` `exportFeel`)
confirmed working. **Cockpit JS 34/34** (7 board + 5 legality + 20 gesture +
rehearsal); **Python 1035 non-slow** (the lone intermittent
`test_scenario_untouched_moves_bounded` is a known CP-SAT-contention flake, green
in isolation) + the new slow ladder (planner_edit, edit_question_domain). See the
docs/04 2026-07-15 Session 3.4 amendment and docs/07 v2.7. **Next: the Phase-3
exit audit** — a fresh session driving the exit demo cold, no terminal.

**Roadmap position: Phase 3 IN PROGRESS — Session 3.3: Tier-1 coverage +
card explainability 2026-07-14.** Five feel-session findings (live on
`busy_board`, schedule `769223cf`), all about the Tier-1 promise failing
QUIETLY or INCOMPLETELY — the mechanics (R-T1a/b/c, R-DP7) held.
**CU1** (coverage): the forced-alternative heuristic WIDENED to v2
(`select_target_ops`: late-demand ops + top-N most-expensive ops
[`DEFAULT_TOP_N_EXPENSIVE`] + slack catch-all; cost DERIVED via
`_incumbent_costs`, a ranking key only) PLUS an ON-DEMAND path
(`build_op_alternatives` + `POST /schedules/{id}/alternatives/op/{op}`):
grabbing an uncovered multi-eligible op fires its solves right then,
pricing EVERY eligible machine (R-T1a K': `add_required_resource_cut`
pins each machine, not the solver's one cheapest escape), appending to
the same pool (`Registry.append_pool_members`, member docs under
`alternatives/op_<op8>/`) so the second grab is instant. Solve bill
guarded: per-op machine cap (`DEFAULT_ONDEMAND_MAX_MACHINES=4`) +
per-solve limit (`DEFAULT_ONDEMAND_TIME_LIMIT_S=6.0`) + API concurrency
cap/dedup (`MAX_CONCURRENT_ONDEMAND=2`, `_ONDEMAND_SEMAPHORE`/
`_ONDEMAND_INFLIGHT`). Cockpit: grab of an uncovered op fires the POST
behind a "pricing alternatives…" shimmer (`.drag-pricing`, absence never
silent), polls `/alternatives`, fades priced ghosts in. **Measured: one
on-demand pricing on the small distinct fixture prices its eligible
machine sub-2s; the `busy_board` raw cost-center is bounded by design
(≤4×6s, ≤2 concurrent), not measured at scale (a Phase-4 profiling
carry-forward).** **CU2** (bug): `alternative_placement.work_orders` was
always `[]` — now resolved from the workpackage→order map
(`_load_alt_context.wp_orders`, same identity-map source as the
assembler); ghost bars wear the work order in their `title`. **CU3**
(explainability): each MAJOR forward-shifted delta-card consequence gains
a one-clause "why" (`sandbox._annotate_move_reasons`, threshold token
`MAJOR_MOVE_THRESHOLD_MIN=60`) from the re-solve's own occupancy
arithmetic — structured (ids), rendered by the card as "blocked on
<machine> until <time>" / "displaced by the dropped op"; a non-contiguous
blocker earns NO clause (never fabricated). No new answer path.
**CU4** (completeness): drop-onto-ghost lazy-fetches the ghost's member
document (`GET /alternatives/{member_index}`), diffs it vs the incumbent
(`movedSetFromDoc`), renders the FULL moved-set — "consequences loading…"
until it lands (R-DP7); a failed fetch keeps the single-bar trace. **CU5**
(guards): `test_certificate_conversation` + `test_ids_end_to_end` exclude
feel fixtures explicitly (the `busy_board` reds retired); `SandboxResult`
echoes `applied_time_limit_s`. Shared `_load_alt_context` +
`_solve_alternative` (forbid|require) back both build modes. **Cockpit JS
30/30** (7 board + 5 legality + 18 gesture); Python non-slow green (+ slow
on-demand + reason tests). Distinct fixture rebuilt (work_orders
populated, member docs + on-demand fixture). See the docs/04 2026-07-14
Session 3.3 amendment and docs/07 v2.6.

**Roadmap position: Phase 3 IN PROGRESS — Session 3.3b: ortools "drift" was
a wall-clock time-bomb 2026-07-15.** The ten standing reds
(`test_defaults_reproduce_baseline` ×2, `test_planner_merge_v2` ×2, four
`test_scenario` + two slow warm-start/merge) blamed on "ortools 9.15 vs the
golden baseline + CP-SAT noise" were **not** solver drift. Root cause: the
manifest-less `sample_data` path left `reference_date=None`, so the validator
used `datetime.now()`; once the machine clock passed WO-2001's 2026-07-13 due
date, WO-2001 was excluded as past-due — removing the late demand, dissolving
the WO-2001/WO-2002 merge, and diverging the golden. **Proven by isolation:**
pinned to `--reference-date 2026-07-09`, ortools **9.15.6755 reproduces every
golden byte-for-byte** (24769.00), so the goldens STAND and no baseline epoch
is regenerated. Fixes: `ortools==9.15.6755` pinned exact + `tests/
test_ortools_pin.py` (installed-vs-pin drift guard, reads pyproject); a new
`--reference-date <ISO>` CLI flag (highest priority; the missing knob for the
sample path); the three regression fixtures pinned to the 2026-07-09 sample
epoch (`test_scenario` also records it in M3 config + derives `base_context` so
the ScenarioRunner re-solve inherits it). **Fixture epochs stated:** sample_data
baselines = 2026-07-09 (now explicit); gauntlet = plant_config (fixed);
generator/cockpit/feel fixtures (`multi_route`, `multi_route_distinct`,
`busy_board`) = **2026-01-05** (fixed `generate()` default, carried in each
manifest — never wall-clock-dated, so NOT rotted, no rebuild). **Full suite
green: 1033 non-slow passed, 0 failed** + the scenario/merge slow ladder (39).
See the docs/04 2026-07-15 amendment and docs/07 3.3b. Lesson: a baseline that
reads `datetime.now()` is a countdown, not a baseline — check the input
population before blaming the solver.

**Roadmap position: Phase 3 IN PROGRESS — Session 3.2d: feel-session
fixes 2026-07-14.** Six items from a live `busy_board` session (Daryn's
hands on the gesture surface). **CU1** (bug): Tier-0 shading now clears
on the **drop→tentative** transition — 3.2c had only covered the
idle-entry paths, and drop is not one; `drag/controller.js`
`clearLegalityOverlays()` retires the wash + ghosts on drop (both the
sandbox and drop-onto-ghost paths) and `redraw()` no longer repaints
shade/ghosts past the dragging phase (new harness test observes
`shade === 0` in-flight through verdict, then a clean discard). **CU2**
(honesty): the stubbed-disabled Accept button now READS as inert (dimmed
+ not-allowed + no hover) with the planner-facing tooltip "Publish
workflow arrives in the next build." **CU3** (bug): the deictic
"Why is this here?" seam — an order-less selection keeps the button
disabled with a hint (no dead enabled control), and programmatic
`board.select()` now fires the shared-selection callback so the ask
panel's scope never goes stale; the router is UNTOUCHED (it only ever
sees the fully-resolved external-ref question, never a literal "this").
**CU4** (wording only): the unsupported-question fallback menu
(`explainer.py`) reworded from `WO-XXXX / M-YYYY / snap-a` id-shapes into
planner language, led by concrete examples from the loaded schedule's
real refs where cheap. **CU5** (feel): two shading-emphasis knobs
(`shade.green_opacity` / `shade.dim_opacity`) added as tuning-panel
sliders + `:root` mirror + `drag.css` opacity multipliers; defaults let
dim + ghosts dominate green (the inversion decision waits on Daryn's
verdict with the knobs). **CU6** (investigate→wire): the M10 LLM
renderer + testimony validator path was already built, reachable, and
fail-closed (no key/package → template; validation failure after one
regen → template) — config-only, so wired for the DEV build (`api.js`
sends `llm`; `main.js` sets it true only under `import.meta.env.DEV`;
production build always templates) and documented in the cockpit README
(key via the API env, gitleaks-guarded). **Cockpit JS 26/26** (7 board +
5 legality + 14 gesture); Python explainer 129 green. See the docs/04
2026-07-14 Session 3.2d amendment and docs/07 v2.5. (Pre-existing,
untouched: `test_certificate_conversation.py[busy_board]` KeyErrors on a
missing truth-manifest key — `busy_board` is a feel fixture, not
truth-bearing; fails identically on 3.2c HEAD.)

**Roadmap position: Phase 3 IN PROGRESS — Session 3.2c: the drag/pan
conflict fix 2026-07-14.** A bug found live on `busy_board`: dragging a bar
sideways panned the whole timeline (vis-timeline's built-in Hammer pan on the
center container ran alongside the controller's bar-carry; the pointer path's
`preventDefault` never touched it). Latent through 3.2b because the harness
drives the phase machine through the programmatic `window.__cockpit.drag` hooks,
which emit no Hammer events — the conflict lives only on the real pointer path.
Fix: `board.setPanZoom(enabled)` toggles vis's `moveable`/`zoomable` (the
vendored `Range._onDrag` re-checks `moveable` on every panmove, so options hold
mid-gesture — no Hammer surgery); the controller suppresses on pointer-down over
a bar (still from the first pixel) and restores on pointer-up (pan resumes the
instant the bar is released, so tentative/verdict stays pannable). Verified by a
NEW real-pointer harness test (window bit-for-bit unchanged mid-drag; a
negative-control run proved it bites) + a shading-lifecycle check (already
correct — no wash survives to an idle board; regression pins added). **Cockpit
JS 24/24** (7 board + 5 legality + 12 gesture); Python untouched. See the
docs/04 2026-07-14 Session 3.2c amendment and docs/07 v2.4.

**Roadmap position: Phase 3 IN PROGRESS — interim B COMPLETE 2026-07-12
(Session 3.2b, the gesture surface).** The interaction layer, rendered against
`multi_route_distinct` (realistic rates → the priced ghosts are the
forced-alternative service's, not the saturated pool's). One overlay in vis's
center container, tracking pan/zoom via a single `redraw()` (the C1 discipline,
extended to ghosts + traces); two entry paths drive the same phase machine —
real pointer events and programmatic `window.__cockpit.drag` hooks
(grab/dragTo/drop/dropAt/discard) the harness uses.
**Data spine (backend, additive, hermetic-testable):** `sandbox.py`
`SandboxResult` gains the **moved-set** (R-DP7: `_moved_set` diffs the pinned
re-solve vs the incumbent, old→new per displaced op, pinned op flagged + first)
+ `delta_abs` + echoed pin; API **`POST /schedules/{id}/sandbox`** (Tier-2
pinned re-solve, R-DP1/R-T1c, sync under the budget token, scenario 409);
`forced_alternatives.py` members carry a compact **`alternative_placement`**
(the Tier-1 ghost bar, no full-doc fetch, CU2); the fixture builder now writes
BOTH the read-only `multi_route` set (unchanged) AND a `fixtures/distinct/`
gesture set (`alternatives.json` = 4 priced cross-machine ghosts +
`sandbox.json` = canned verdict/flagged/no_verdict by op). **CU1** grab →
Tier-0 shading (`drag/shade.js`): green legal / amber displace / dim,
capability-dim distinguished, hover-over-dim one-line reason; **standing
latency regression grab→shade < 100 ms** (payload prefetched, R-T1d).
**CU2** ghosts (`drag/ghosts.js`, R-T1a): forced + pool placements unified,
source-distinguished subtly, each wearing its price / "not feasible this
horizon" verdict, labels legible + tracking (drift ≤ 1 px). **CU3** drag
physics (`drag/magnets.js`, pure; R-DP1/R-DP3): semantic snap (ghosts strongest
→ calendar → adjacency → predecessor → coarse grid) resolving DURING the drag,
Alt disables, dim refuses with boundary-pinning + not-allowed cursor,
release-over-dim returns home animated. **CU4** drop → tentative → verdict
(`drag/controller.js` + `drag/sandboxui.js`, R-DP2/R-T1c): hatched tentative
bar, visible countdown, three honest outcomes (delta card / flagged "bound not
proven" / return-home), drop-onto-ghost near-instant from the vouching schedule;
**accept STUBBED DISABLED** (no publish workflow — a dead-end accept would
violate R-DP7). **CU5** change traces (`drag/traces.js`, R-DP7): moved-set drawn
old→new (ghost-of-old + motion line) held until discard; delta-card line items
linked to bars (click → navigate + pulse); discard restores everything.
**CU6** the tuning panel (`drag/tuning.js`, DEV-BUILD-ONLY): every feel token
live with hot reload + export — never in the production build. Feel-token split:
numeric interaction knobs in `drag/feel.js` (the panel's source, CSS-visible
subset mirrored to `:root`), visual tokens in `tokens.css`. **Tests: cockpit JS
23/23** (7 board + 5 legality + 11 gesture; `tests/cockpit/gesture.spec.mjs`);
**Python 1026 passed** (+4 sandbox API) + the slow sandbox-latency regression on
the distinct fixture (the drop→verdict authority). **Carry-forwards (named):**
the accept/publish path (final session — accept disabled by design so no gesture
mutates canonical state yet); voice (later interim); pool/forced slice-awareness
(pilot-gated, heavier); drop-onto-ghost shows the dropped bar's own trace only
(deeper consequences need the ghost's document); one ghost per op (one cut per
op); and whatever the feel iteration finds once Daryn's hands are on the panel.
See the docs/04 2026-07-12 Session 3.2b amendment and docs/07 v2.3.

**Roadmap position: Phase 3 IN PROGRESS — Session 3.2a interim-B part 1 (the
interaction data spine) COMPLETE 2026-07-12.** Everything interim B needs that
is testable WITHOUT a cursor; the gesture/voice surface is 3.2b.
**CU1** — the split interaction endpoint (R-T1d): schedule **contract 1.2 →
1.3**, `GET /schedules/{id}/interaction` serves the Tier-0 block and the main
`GET /schedules/{id}` document returns to ~1.1 size. Ruled a **MINOR** bump,
honestly: the document schema is unchanged (`interaction` stays optional, always
None on the main endpoint; a thin `_persist_document` writes the main doc +
sibling `interaction.json`), the field was already legitimately None for pool
members, and the sole production consumer is the cockpit (updated same session).
Cockpit `interaction.js` background-fetches after first paint with
stale-while-revalidate; a **stub** `dragEnabled` flag + `data-drag-enabled` host
attr enable on arrival (the gesture surface is 3.2b). Additive:
`OperationInteraction.resumable` (a CU2-discovered Tier-0 window-fit input).
**CU2** — the client-side **Tier-0 legality library** (`src/cockpit/legality/
tier0.js`, pure/framework-free): eligible rows (capability) + legal-start
regions (calendar ∩ precedence floor ∩ window-fit) + the anchor set;
**conservative-error asserted (R-DP6)** — may under-offer green, never greens a
proven-illegal spot; all four dim dimensions tested (`tests/cockpit/
legality.spec.mjs`, incl. resumable window-fit via `latestStartForRemaining`).
**CU3** — the **forced-alternative service** (`src/mre/modules/
forced_alternatives.py`, R-T1a/b): per-op warm-started re-solves carrying a
"not on the incumbent machine" cut (`solver_builder.add_forced_alternative_cut`,
no objective bound) → the TRUE price of each road not taken, stored as
pool-member-class documents (`annotations.pool.source="forced_alternative"`) in
the **same** pool tables (`pools.kind='alternatives'`, `pool_members.source/
verdict/label_json`, nullable doc path — same never-in-listings exclusion, same
supersede invalidation); infeasibility is **first-class**
(`verdict="infeasible_this_horizon"`, no doc). Selection heuristic **v1**
(`select_target_ops`): at-risk demands (late first, then tightest slack) and
their multi-eligible ops, budget-capped. The **price-bought-something
counterfactual** runs on the new **`multi_route_distinct`** generator scenario
(distinct rates + light load → the pool converges): the plain pool crosses
machines ~0 times while the forced service yields ≥1 priced cross-machine
alternative, strictly more (`tests/test_forced_alternatives.py`). API additive:
`POST/GET /schedules/{id}/alternatives` (+ `/{member}`), distinguishable by
source label. **CU4** — the **sandbox latency budget** (`src/mre/modules/
sandbox.py`, R-T1c): `classify_sandbox_outcome` — the pure three-outcome
classifier (verdict / feasible_unproven / no_verdict), budget a **design token**
(`SANDBOX_BUDGET_S = 15.0`), budget-exhaust paths simulated not waited;
`sandbox_pin_resolve` warm-starts + pins one op (machine+time, R-DP1) + solves
under budget. **CI verdict regression runs on `multi_route_distinct`** (proves
fast) — a **CU4 finding**: the saturated `multi_route` fixture is degenerate by
design (the identical-rate R0/R1 pair that surfaces pool ghosts), so a pinned
re-solve there returns a within-budget **FLAGGED** card (outcome 2), never a
hang — the honest second outcome R-T1c designs for, asserted not hidden. Harness
readiness-wait added for the 3.1c 0-bars flake. **1022 non-slow tests green**
(+23) + new slow ladder (forced counterfactual, sandbox latency); **cockpit JS
12/12** (7 board + 5 legality). **Carry-forwards:** pool/forced slice-awareness
(heavier now, pilot-gated, R-T1b); the gesture surface + voice (3.2b); the v1
selection heuristic (will evolve). See the docs/04 2026-07-12 Session 3.2a
amendment and docs/07 v2.2.

**Roadmap position: Phase 3 IN PROGRESS — Session 3.1 interim-A (read-only
cockpit) COMPLETE 2026-07-11 (session 3.1b).** All five commit-units landed;
the read-only board + language mode are in. Gesture (drag, Tier-0/1/2 per
R-DP1–R-DP7) and voice are interim-B and later. **CU3 (done):** the cockpit
shell — `src/cockpit/` (Vite 5, framework-free ES modules, vis-timeline pinned
to the bake-off `7.7.4`, design tokens externalized in `tokens.css`) renders a
**contract-1.2 document from the live API**: resources as rows,
`work_orders`/`external_name` planner vocabulary (never canonical UUIDs on
screen), per-Demand lateness coloring, calendar closures, top strip = contract
version + certificate grade (via the new thin `GET /schedules/{id}/meta`, which
joins the grade from the certificate store — the grade is a submission property,
kept out of the derived-not-invented document). Read-only: `editable:false`,
no drag handlers. (vis-timeline blank-board gotcha recorded in docs/04: pass
`min`/`max` only + `setWindow`, never `start`/`end` options, or the root stays
`visibility:hidden`.) **CU4 (done):** the ask panel embeds M10 (`/ask`);
registers render visibly distinct (testimony/judgment from the additive
`bundle.register`); the answer's cited bars + lanes light up in sync via the
additive `bundle.cited_refs` (`{operations,resources,demands}` — the refs the
answer already cites, surfaced not synthesized; an always-on overlay tags each
cited bar, carrying the 3.0 narrow-bar label lesson); clicking a bar scopes a
deictic "why is this here?". **Honesty armor intact** — the acceptance answer
cites the alternatives' PRICES straight from the reconstructed-assignment
Decision ("Same cost" / "Would cost −N more"); no new answer path, no new LLM
reach. **CU5 (done):** the Playwright harness promoted to `tests/cockpit/`
(hermetic committed `multi_route` fixture + fixture-server standing in for the
API — CI needs no solver): 6 scripted states screenshotted with machine-checked
assertions incl. the standing **C1 label-vs-bar drift regression (≤1.0px)** and
a **mid-pan frame** (3.0b residual closed); **6/6 green** headless.
**Acceptance met LIVE** (not cited from tests): real `multi_route` solve →
cockpit over the Vite→API proxy → ask "why is ORD-000012 on F001-RES002?" →
priced testimony answer → 2 cited bars + 3 lanes glow, `ACCEPTED / C1` strip,
0 page errors — the first frame of the sixty-second script. **999 tests green**
(+4 API: `/meta`, register + cited_refs) + the 5 slow `multi_route` tests.
**Interim-B carry-forwards (named):** the contract-1.2 split-endpoint
`GET /schedules/{id}/interaction` (+35.7% Tier-0 payload, proposed-not-built);
the drag surface (R-DP1–R-DP7); the board overlay reads vis DOM geometry (guarded
by the CU5 drift test); a `renderers.py` "−N more" prose quirk. **Design-thread
(do not attempt):** the parked pool-diversity ghost-realism question under
*distinct* rates. See the docs/04 2026-07-11 Session 3.1b CU3/CU4/CU5 amendments
and docs/07 v2.1. **CU1 (done):** `multi_route` — the capability-routed
generator scenario (docs/05 B2 pipeline-proven). An operation's eligible set is
expressed as multiple `routing_lines` rows sharing one (route_id, sequence); the
IDS adapter groups them into one `explicit_set` OperationSpec (single-row case
byte-identical → defaults-reproduce-baseline holds). A **saturated
identical-rate cheap pair** (R0=R1=$50) is what makes the solution pool actually
surface cross-machine ghosts at a clean near-optimal base — the hard-won lesson:
with distinct rates the optimum is machine-unique and earlier "cross-machine"
readings were artifacts of a *suboptimal* incumbent. `solution_pool` now reports
`diversity.cross_machine_ops`; `tests/test_multi_route.py` asserts structure +
pool cross-machine + the single-eligibility-collapse counterfactual. This closes
the 3.0 "generated data has no legal cross-machine move / no priced ghost"
carry-forward. **CU2 (done):** schedule **contract 1.2** (additive `interaction`
block — the Tier-0 client-side legality payload: per-op eligible sets, durations,
release floors, precedence expanded to operation-instance refs; built only when
the assembler gets `edges`, so 1.1 consumers/pool members are unaffected;
calendar windows + occupancy deliberately not duplicated). Size check on
clean_large: **+1.9 MB / +35.7%** — a split-endpoint (`/schedules/{id}/interaction`)
is **proposed, not implemented**, for interim-B. **Remaining interim-A (NOT
built): CU3** the cockpit shell (production `src/cockpit/` vis-timeline frontend
rendering a contract-1.2 doc from the live API — resources as rows, planner
vocabulary via the identity map, lateness coloring, calendar closures, top strip
= version + grade, design tokens externalized, read-only); **CU4** the ask panel
embedding M10 with cited-bar highlighting + shared selection (deictic "why is
this here?"); **CU5** the Playwright screenshot harness promoted from the spike
into `tests/` (scripted states as screenshot assertions, the C1 0.0px drift check
as a standing regression, CI headless). 995 tests green (non-slow) + the 5
slow `multi_route` pool/counterfactual tests. See the docs/04 2026-07-11
Session 3.1 CU1/CU2 amendments and docs/07 v2.0.

**Roadmap position: Phase 3 IN PROGRESS — frontend substrate SELECTED
(vis-timeline) 2026-07-11 via the bake-off SPIKE + 3.0b extension.** Throwaway
spike (`tools/spikes/frontend_bakeoff/`, nothing ships) choosing the cockpit's
drag-surface substrate. 3.0: both candidates GREEN on the mechanics (custom React
SVG+dnd-kit vs vis-timeline), recommendation *adopt vis-timeline conditional on a
stable overlay follow-up, custom React the fallback*. **3.0b (2026-07-11) ran
that follow-up** — held vis-timeline to the drop ruling's four killer criteria
(`candidate_b_3b.html` + `src_b/main_3b.js`, zoom/pan enabled; harness
`harness/run_3b.mjs` → `shots/report_3b.json` + `b3b_*.png`) and it **cleared all
four CLEAN**: C1 always-on overlay carries the priced ghost labels + hatch and
tracks vis's pan/zoom at **0 px drift** (3.0 in-bar clipping resolved); C2 illegal
rows **visibly refuse the drop mid-drag** (pin at legal boundary + not-allowed
cursor, return home on release); C3 one real magnet via `onMoving` — clean
monotonic falloff, Alt-disable, **no throttle (0.95 call:step)**; C4 **20/20**
headless drags. **Decision rule (all-four-pass → adopt) applied: vis-timeline
SELECTED**; custom React is the zero-blocker fallback. **docs/07 frontend line
updated (v1.8)**; VERDICT.md carries the 3.0b addendum (incl. an honest C3
probe-artifact correction). Residuals disclosed (overlay reads vis DOM geometry;
harness needs the diagonal engage gesture) — neither a failure under evidence.
Carry-forwards unchanged: (a) the generator has **no capability-based
multi-eligible routing** (every op routes to one resource), so it cannot yet
produce a faithful drag fixture — a W1/Phase-3 prerequisite for real
Tier-0/Tier-1 anchor computation; (b) `merge_by_family_v2` traced (design-
reviewed, origin `847fe89`), in the solver-gap dossier's tractability-lever entry
alongside v1. See the docs/04 2026-07-11 Session 3.0 + 3.0b amendments.

**Roadmap position: Phase 2 COMPLETE (qualified) — entering Phase 3.**
Phase-2 exit **audited by a fresh session 2026-07-10** (audit mode, no fixes
unless a clause fails): all five exit-prompt clauses PASS / PASS-WITH-
QUALIFICATION, **fix-free** (Clause 6 addenda resolved at `acb75b8`). Live
evidence: exit demo byte-identical across two fresh API runs (7460 assignments);
API 409/listing invariants; warm-start 0-vs-51-move noise case at identical cost
delta; pool diversity@15min + snapshot byte-identity + supersede-invalidation;
mid_replan WIP counterfactual + sunk-setup ledger; three certificate registers
with §-cited remediation + jurisdiction rule; gauntlet reproduces its golden
byte-identically with the 173-exclusion anchor (default `identity_v1`, 0 merges;
`merge_by_family_v1`/`_v2` both exist as opt-in). **Carried exit qualifications:**
cloud in-cloud confirmations (in-container CI + live `az deployment` + cloud
smoke) OPEN → **2.4b** (Docker/Azure unavailable at audit); raw_data path
bypasses M0 gate / no WIP doorway → Phase 4; pool slice-awareness + warming-on-
publish → Phase 3; two quarantined catalog notes (no IDS §-cite) → design-thread
note_version fix; W1 scenarios `dwell_heavy`/`calendar_chaos`/
`multi_facility_balance` + sentinel-value detector + provenance spot-check guard
+ `yield_factor` false-observed provenance → OPEN, re-parked (W1/Phase 3);
`test_n3000` contention-sensitive. See the docs/04 2026-07-10 exit-audit
amendment and docs/07 v1.7. Certificate session
(groundwork) done 2026-07-10: **the M0 gate is now a Rule Registry** — 32 named
rules (`src/mre/contracts/ids_rules.py`, the single source that renders docs/06
§4), closed outcome vocabulary (satisfied/flagged/degraded/violated), grade as a
pure function of outcomes, evidence-shape refactor (typed `GateFindingEvidence`
with rule_id; banded rules record a Metric, emit a Finding only on non-satisfied;
severity derives from outcome; findings name typed submission-space subjects
`EntityRef(system="IDS")`, reachable by canonical key via the M1 identity map).
Seven checks made real + the routes_resolve_to_lines unfold + the
transition-matrix converse split; `manifest_semantics_declared` recoded
MALFORMED_FIELD→AMBIGUOUS_SOURCE. Coverage-matrix + reverse-guard tests make the
registry complete-by-construction. **840 tests green** (+45). Docs §4 (docs/06),
docs/07 v1.5, docs/02 boundary rule 1, docs/04 amended. **Conversational
Certificate landed 2026-07-10** (catalog v1 frozen, renderer/router/triage
live): frozen `remediation-catalog-v1.yaml` (32 rule notes + 18 fallbacks) at
`src/mre/catalog/`, typed + completeness-tested; three answer registers —
testimony / **remediation** (authored, single-source-of-truth number validator,
fail-closed) / **judgment** (one grade-distance triage: violated → degraded by
closest escape → flagged, quality last); explainer routes cert questions through
identity, never id-shape regex; REJECTED runs answer certificate-only (index
built pre-stop, no snapshot). `APPENDIX_A_BANDS` single source resolves the
catalog's `appendix_a.*` anchors. **Errand (a):** `wip_in_progress_rows_carry_progress`
disposition `DEFAULTED`→`EXCLUDED` (gate + adapter) — no progress value is
invented, the in-flight claim is excluded. **Errand (b):** docs/06 §4 severity
reworded as a function of **(outcome, category)**. **Reported, not fixed** (frozen
prose, report-don't-edit): two quality notes'
`fix_looks_like` carry no resolvable IDS §-cite — quarantined + pinned, a
design-thread note_version fix. **985 tests green** (+145); docs/06 §4 + docs/04
amended. Session 2.4 done
2026-07-14: **cloud deploy, encrypted (W4 baseline)** + the 2.3-review
carry-ins. **CU0:** WIP finding-code review (all five checks reuse existing
codes within their meanings; `wip_sequence_order_violation → LOW_CONFIDENCE_INPUT`
named as closest-to-a-stretch and justified; no new code) · **resumable
in-flight remainder now RESPECTS calendars** (`_place_inflight_remaining`
greedily fills working windows; non-resumable keeps the contiguous carve-out —
"the future respects calendars even when the past didn't") · op-count
reconciliation (13,315/14,042/4,088/4,933 = planner-policy × splittability
rescues) + dossier entry #2 (merge as ~3.3× tractability lever vs the +$260
cost-loss verdict; pilot entry conditions must declare their policy) ·
**sunk-setup ledger** (completed/in-flight ops bill zero movable setup; separate
non-decomposing `sunk_setup_cost` line; counterfactual on mid_replan). **CU1:**
multi-stage Dockerfile (non-root, pinned lockfiles, `/health`, image-as-shipped
CI) + compose parity; `TestGauntletReproducesBaseline` guarded to skip when the
gitignored raw_data is absent. **CU2:** Caddy TLS overlay (`tls internal`) +
encryption-at-rest as a volume property + secrets via env injection only + CI
gitleaks secret-scan + **docs/08-security-posture.md** (single-tenant-by-
construction with the named tenant-#2 trigger). **CU3:** `deploy/azure/` (Bicep +
deploy.sh + provider-swap-boundary README) + provider-agnostic `deploy/smoke.py`;
**exit demo demonstrated locally** — clean_large ~3K orders → ACCEPTED/C1 →
7,460-assignment schedule via the API in ~165s (deterministic), baselines in
`deploy/scale_ladder.json`. **795 tests green** (+5). **Carried gap:**
deploy-verified-LOCALLY, not in-cloud (no Docker / no live Azure this session —
Bicep unvalidated vs ARM, image not built, smoke ran against a local server);
first in-container CI run + live `az deployment` + cloud smoke are the
confirmations. Session 2.3 (WIP) `5600de2`; 2.2 `86e0115`; 2.1 `517b1fe`;
Phase-1 exit audit `9a70e5c`. Qualification carried (owned by Phase 4): the
raw_data path bypasses the M0 gate (no WIP doorway there either) — resolved by
the pilot connector; the raw path is then demo-frozen.

**Phase 2 mission (docs/07):** ~~API layer + schedule JSON contract~~ ·
~~warm-start scenario solves~~ · ~~solution-pool service~~ · ~~solver-gap
probe~~ · ~~WIP/soft-start doorway (docs/06 §5.13 + mid_replan scenario)~~ ·
~~cloud deploy with encryption (W4 baseline; single tenant by construction)~~
(done, sessions 2.1–2.4; cloud deploy verified locally, in-cloud carried) ·
~~Conversational Certificate (router domain + remediation catalog; jurisdiction
rule: coach the IDS requirement, never ERP-specific surgery)~~ (done 2026-07-10).
**Phase 2 mission complete** — all workstreams landed (cloud deploy in-cloud
confirmation still carried from 2.4).

**Small carry-forwards (queue behind Phase 2 items, do not lose):**
`OperationSpec.yield_factor` still carries false observed provenance
(flagged 2026-07-12, not fixed) · sentinel/repeated-identical-value detector
(the 40× `run_rate_seconds=60.0` fingerprint from Rep 3) · provenance
spot-check guard (sampled: `observed` values must appear in the cited source) ·
W1 scenarios not yet built: dwell_heavy, calendar_chaos,
multi_facility_balance (mid_replan now built) · pool warming-on-publish
becomes the default when the Phase-3 publish workflow exists (auto-warm is
opt-in until then) · **pool must become slice-aware before serving
sliced-mode schedules** (2.3 probe carry: members rebuild from the run's
M5 horizon, not a sliced run's per-slice selection) · **cloud deploy
in-cloud confirmation** (2.4 carry: live `az deployment` from `deploy/azure/`
+ cloud smoke, and the first in-container CI run — Docker/Azure both
unavailable in session 2.4, so verified locally only). [extractor
sunk-setup billing — RESOLVED 2.4 CU0.5.]

**Do not hand-maintain a duplicate task list here** — docs/07 is authoritative
and updated same-day per its W2 rule; this section records only position,
qualifications, and carry-forwards.

## Working style

- Write schema/behavior tests **from the spec documents first**, then implement.
  The specs are executable acceptance criteria.
- Python 3.11+, `pyproject.toml` at root, `pytest` for tests (`--runslow` opts
  into the slow ladder). `ortools` stays quarantined to
  solver_builder / solve_runner — the canonical Schedule must remain readable
  with no ortools import (tested).
- Pydantic for contracts (validation-at-construction: "malformed records die at
  the source").
- Deterministic mode for any baseline or regression comparison (see hard rules).
- Legacy code is reference-only for remaining ports (hybrid workcenter capacity,
  setup-matrix shapes): read `legacy/ProFunctv2_8.py`, port the *logic*, never
  the *shapes*.
- A priced feature's test must include the counterfactual proving the price
  bought something (2026-07-12 amendment).
- **Sessions commit to `master` directly and push — no session branches, no
  PRs** (the working pattern since Session 3.0). Push after every session commit
  (see the README). A session branch may exist transiently, but it fast-forwards
  into `master` and is deleted at close; `master` is the trunk.
