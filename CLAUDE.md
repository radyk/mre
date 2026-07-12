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
