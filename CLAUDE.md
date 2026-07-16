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
