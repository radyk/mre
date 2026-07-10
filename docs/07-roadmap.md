# Product Roadmap

**Document 7** · Status: v1.4 · Companions: 01–04 (constitution), 05 (Constraint Catalog, in progress), 06 (Incoming Data Spec)

**v1.4:** the Conversational Certificate added (Phase 2 item, remediation catalog, registers extended, website moment in Phase 3).

**v1.3:** WIP/soft-start rescheduling added (IDS v0.3 §5.13, Phase 2 backbone item, mid_replan scenario, invariant amendment).

**v1.2:** restructured demo-first with a six-month clock as forcing function; the reasoning cockpit defined (board + conversation + voice as one surface); three-tier drag-and-drop specification; certification deferred with an explicit trigger; ATP → MES sequenced post-pilot.

---

## 1. The end vision (unchanged, confirmed)

A sellable **manufacturing reasoning engine** for high-mix, make-to-order discrete job shops. Differentiation is *trust*: cost-optimized schedules (customer priority is a cost coefficient); every decision explainable, every number traceable, reconstructed reasoning labeled; ERP data quality graded and reported (the Submission Certificate is a product artifact); the planner can argue with the schedule, test alternatives, and override with recorded authority. Long horizon: ATP/CTP quoting, then MES (actuals, stability, publish-back).

## 2. The clock

**Six months, quality still sets the pace.** The clock is a *forcing function for scope discipline*, never a license to skip exit demos. The unrecoverable failure is presenting the pilot something half-baked — one first impression, spent once. Target position at six months: **pilot live (by month ~5), Stages/Phases 1–4 substantially complete, case study forming.** Explicitly post-window: MES, SOC 2 certification (Type II physically cannot complete in-window), full multi-tenant hardening.

**Week-one spikes (front-load the research-shaped risks):**
1. Chunking at scale — model-size behavior on the scale ladder before Rep 2 is built in full.
2. Solver-gap probe — quick test of facility decomposition on the full gauntlet; if the 87% gap is structural, the sliced daily solve is the blessed operational mode and the research is parked, named, post-pilot. ✅ RUN 2026-07-13, verdict **RED**: perfectly decomposable (0 cross-facility WPs) yet 8/10 facilities and even single-resource shards find no incumbent at mass-splittability density — two named killers (chunk-slot volume on the full horizon; raw per-machine op count), both capped at once by slicing. Sliced daily solve confirmed as the blessed mode; parked directions named in `tools/solver_gap_probe_report.md` + the docs/04 amendment.

**Checkpoint rule:** each month ends with a stage-position review against this document; CLAUDE.md status updated same-day.

## 3. Phases (demo-first)

### Phase 1 — Scheduling cooked (weeks ~1–4)
Stage-A content intact:
- docs/05 Constraint Catalog: four rulings resolved, document drafted with test-status + IDS-doorway columns.
- **Chunking/splittable operations** (legacy semantics, scale-aware: bounded chunk counts, applied only where needed). Acceptance: `chunking_exam` passes; the gauntlet's 173 window-fit exclusions collapse.
- Outlier calibration from recorded distributions; merge feasibility & risk guard (re-enable merge_by_family as non-default).
- **Overtime premium priced in solves.** ✅ DONE 2026-07-12 — premium windows (overtime `added` minus regular availability), delta-priced objective, `production_regular/overtime` ledger split, Decision evidence; `overtime_required` scenario + counterfactual harness (`tests/test_overtime_end_to_end.py`); the resource-rates audit (dormant-register follow-up) closed in the same session — see the docs/04 amendment.
- New generator scenarios: ~~overtime_required~~ (done), dwell_heavy, calendar_chaos, multi_facility_balance, scale ladder (30/300/3K/10K).

**Exit demo:** messy generated plant through `--submission` → certificate → costed schedule (C1+, full decomposition) → why → what-if → verdict. Then the **ticketing gauntlet passes clean** — 173 rescued, costs priced, honest certificate, no accommodation.

### Phase 2 — Demo backbone (weeks ~4–8)
Stage B *demo-sufficient*:
- FastAPI layer: schedule JSON document (cockpit contract), gate / solve / ask / what-if endpoints; run-scoped persistence enforced structurally. ✅ DONE 2026-07-13 — `contracts/schedule_document.py` v1.0 (derived-not-invented; external names only in `*_name`/`work_order` fields with UUID refs alongside; cost decomposition dies at construction), pure assembler with round-trip test, versioned envelopes, REJECTED-never-solves, scenario listing exclusion; see the docs/04 amendment.
- **Warm-start scenario solves from the base schedule** (fixes the exit audit's what-if search-noise caveat). ✅ DONE 2026-07-13 — `apply_solution_hints` (deterministic uuid5 correspondence; modified portions naturally unhinted; calendar-touched resources invalidated), `warm_start_hints` + `solution_info` telemetry; noise case re-measured 0 moves warm vs 51 cold at identical cost delta (a differ string-format inflation bug fixed on the way); see the docs/04 amendment.
- **Solution-pool service** (feeds Tier-1 drag ghosts and pool-based explanations): retain a *diverse* set of near-optimal solutions per published schedule (diversity-constrained enumeration or k perturbed solves), warmed async after publish, invalidated on accepted edits, keyed by schedule version. Also the first muscle of ATP's fast re-solve. ✅ DONE 2026-07-13 — `modules/solution_pool.py` (K warm-started short re-solves, objective ≤ incumbent×(1+X%), randomized seed + start-time no-good cut per member, measured Hamming diversity), contract 1.1 `annotations.pool`, registry pool tables (structurally never in schedule listings), pool endpoints + auto-warm on solve (`pool: true`; warming-on-publish becomes the default when the Phase-3 publish workflow exists), invalidated on supersede; see the docs/04 amendment. Carried qualification (2.3 review): **the pool must become slice-aware before serving sliced-mode schedules** — members rebuild from the run's M5-recorded horizon, which does not reproduce a sliced run's per-slice demand selection; lands with the pool's sliced-mode productionization (parked directions, `tools/solver_gap_probe_report.md`).
- **Cloud deployment, encrypted**: TLS in transit, encryption at rest, secrets management. Single tenant by construction (one pilot); tenant isolation as architectural rule for tenant #2. **No certification this window** — trigger: pilot converts to paid or prospect #2 requires attestation; then Type I → Type II.
- Storage past loose files only where it hurts (run registry, certificate history — SQLite-class). ✅ DONE 2026-07-13 with the API layer — `api/registry.py`: SQLite index (submissions, certificates, runs, schedules); filesystem stores remain the artifact truth. Solver-gap research parked per spike verdict.
- **Conversational Certificate** — the certificate becomes an interrogable surface, not a verdict document; the customer's *first conversation* with the system. Components: (1) a certificate question domain in the explainer router ("why was this rejected?", "what's wrong with my orders file?", "what should I fix first?") reading gate findings already in the evidence store; (2) a **remediation catalog** — a curated, versioned note per finding code (what the check means, typical causes, what a fix looks like, citing the IDS section that defines the rule) so fix-advice is authored knowledge rendered per-case, never LLM improvisation; (3) register mapping — what's-wrong = testimony (findings, evidence, footnotes), how-to-fix = remediation register (authored guidance, spec-cited), what-matters/triage = judgment grounded in severities and counts. **Jurisdiction rule:** remediation coaches toward the IDS requirement, never toward ERP-specific surgery — the spec is ours, their ERP is theirs. Truth manifests for CONDITIONAL/REJECTED scenarios gain expected-remediation assertions.
- **WIP / soft-start rescheduling (IDS v0.3 §5.13):** `wip_status.csv` doorway + gate coherence checks; adapter lands observed state on WorkPackage.state; solver treats complete ops as satisfied, in_progress ops as fixed intervals for remaining duration, and honors the **amended invariant** (no *newly scheduled* start before reference_date; observed in-flight starts exempt) at both clamp sites. Generator scenario **mid_replan** (truth manifest: fixed ops stay put, completed ops free capacity, only the future moves) ships with it per W1. Recurring pilot submissions ARE rescheduling — a live plant's second submission contains WIP or the schedule is fiction.

**Exit demo:** 3,000-order generated submission → schedule via API in minutes, repeatably; scale-ladder timings as regression baselines.

### Phase 3 — The reasoning cockpit (weeks ~8–16, center of gravity)
Not "a Gantt with chat" — **one reasoning surface, three input modes (gesture, language, voice)**, all front-ends to the same machinery (canonical model, evidence, scenario runner, solution pool), sharing session state: same schedule version, same sandbox scenario, same selection.

**Three-tier drag-and-drop:**
- *Tier 0 — legal zones (instant, no solver):* on grab, pure canonical arithmetic shades the board — green (fits), amber (fits, displaces), dim (illegal: capability/calendar/precedence). Computed client-side from the schedule JSON.
- *Tier 1 — ghost slots from the solution pool:* overlay the task's positions in other near-optimal schedules, each labeled with that schedule's known objective delta ("+$120: Tue 09:00 on the other press"). Pre-priced, coherent placements, zero drag-time computation. Pool must be diverse (see Phase 2).
- *Tier 2 — the drop:* compiles to a **pin constraint** (never mutation), re-solves in the what-if sandbox, actual delta shown for accept/reject; accepted edits are Decisions with authority; publish workflow proposed → published.
- Open ruling before build: **drop-pin default** (machine / start / both) — shapes the edit vocabulary.
- Frontend: open-source components (vis-timeline / DHTMLX class) for the demo build; commercial upgrade a later decision.

**Conversational layer on the same surface:** answers highlight bars as they cite them; "what are my options?" glows the same Tier-1 ghosts; drags are narratable ("summarize what I changed today and what it cost" → sourced session narrative, since edits are Decisions). Pool-consensus becomes new testimony ("in 4 of 5 near-optimal schedules this runs on WC-B"). All honesty armor intact: registers never blend; testimony validates against bundles; judgment names its records.

**Voice:** push-to-talk speech-to-text into the same answer() (Web Speech / Whisper-class); spoken responses give the summary sentence and the register aloud ("My take:") while **the screen holds the receipts** — record IDs are never read aloud; ears for the answer, eyes for the footnotes.

**The demo script (exit bar, and the website's centerpiece):** planner asks *why is the Henderson order late* (voice) → sourced answer, bars highlight → *what are my options* → three priced ghosts glow → drag onto one → delta confirms → publish → *summarize my changes* → sourced narrative. Sixty seconds; every number traceable.

**Website (first-class, the demo's home):** positioning from the niche statement; the certificate story upgraded to its interactive form — **upload a sample, get your certificate, ask it questions** (a prospect interrogating their own data's report card in a browser, before anyone signs anything); the cockpit footage; demo access. Kickass, thin, honest.

**Exit demo:** a stranger who plans for a living drives the script cold, no terminal.

### Phase 4 — Pilot (target: live by month ~5)
The ticketing client. Entry conditions (the no-half-baked rule): Phase 1 exit passes **on their data** without accommodation; a non-developer drives the cockpit cold; their live extract gates CONDITIONAL or better. No promises before conditions are met. Their connector, recurring IDS submissions, certificates trending, schedules published in their vocabulary via the identity map. **Exit:** their planner uses it in anger for a month; the certificate/quality trend line is the case study.

## 4. Post-pilot sequence (named, ordered)

1. **ATP/CTP** — the natural prospect question, mechanism already built: a what-if scenario with a hypothetical Demand injected; answers are promise dates *with priced alternatives* ("April 14 normal; April 9 with overtime at $X; April 7 if order Y slips at $Z"), evidence-traced — askable by voice mid-phone-call. Needs: fast/incremental re-solve (Phase 2's pool work is the head start), a `quote_request` IDS doorway, promise-becomes-firm-Demand (locks generalized). Killer feature for prospect #2.
2. **MES horizon** — actuals as observed entities, planned-vs-actual evidence, schedule-stability objective, advisory maturing to trend-backed counsel, multi-user/auth hardening. Scoped from what the pilot teaches.
3. **Certification** — on its trigger (paid conversion or prospect requirement): SOC 2 Type I, then Type II on its long evidence clock. Encryption now; attestation when commerce demands.

## 5. Cross-cutting workstreams

**W1 — Scenario & Anomaly Catalog (the gym, permanently open).** No capability is done without its generator scenario and truth assertions (docs/06 §8). Stage exits run on generated scenarios; reality is reserved for pilots.

**W2 — Documentation & Rulings.** docs/05; the drop-pin ruling; docs/04 amendments same-commit; CLAUDE.md status current at every session end.

**W3 — Go-to-Market surface (real in Phase 3).** The website, the demo script as repeatable asset, the certificate-as-sales-artifact motion, capability matrix = docs/05 with test-status.

**W4 — Security & Compliance.** Encryption + secrets from first cloud deploy; tenant isolation architectural from tenant #2; audit story half-built by the evidence contract; certification on its trigger, post-window.

## 6. Open rulings queue

1. Requirement model: set-with-roles (docs/05, in progress)
2. Interruptibility: three classes (docs/05)
3. ChangeoverRule: attribute-keyed (docs/05)
4. Min/max lags: OperationSpec vs precedence edge (docs/05; lean = edge)
5. Drop-pin default: machine / start / both (Phase 3 entry)

## 7. Standing risks

| Risk | Mitigation |
|---|---|
| Chunking explodes model size | Week-one spike; bounded chunks; chunking_exam + scale ladder gate it |
| Solver gap structural | Probe run 2026-07-13 (RED): sliced daily solve confirmed blessed; research parked with named directions (horizon-capped chunk slots, slice-within-facility + LNS repair) |
| Phase 3 feel-bar iteration overruns | It owns the schedule's largest block; scope discipline via the sixty-second script — ship the script, not the toolkit |
| Pilot live data diverges from historical dump | Certificates trend the divergence; entry conditions on the live extract, not the dump |
| One first impression with the pilot | Entry conditions are objective tests; no demo before they pass |
| Voice/theater outruns honesty | Registers spoken aloud; receipts stay on screen; post-render validation unchanged |
| Remediation advice drifts into ERP-specific instruction | Jurisdiction rule enforced in the remediation register prompt; catalog notes cite IDS sections only; review per code addition |
| WIP invariant amendment regresses the ghost-job fix | Both clamp sites amended together with tests for each; mid_replan asserts no NEW starts pre-reference while in-flight bars render as history |
| Session drift | W2: monthly checkpoint + CLAUDE.md same-day |
